import os
import sys
import logging
from dotenv import load_dotenv

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
from pathlib import Path
from pyspark import StorageLevel
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.functions import col, explode, regexp_replace, trim, concat_ws, lit, create_map

from book_enrichment import BOOK_SERIES_SCHEMA, book_series_pairs, enrich_books, load_ol_lookup, remap_similar_books
from kcore import k_core

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DIR = Path(os.getenv('DATA_DIR', BASE_DIR / 'data'))
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', BASE_DIR / 'full_data'))
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True, parents=True)
K_CORE = int(os.getenv('K_CORE', '5'))
SPARK_LOCAL_DIR = os.getenv('SPARK_LOCAL_DIR', '/tmp/spark-tmp')
Path(SPARK_LOCAL_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_DIR / 'process.log',
)

spark = SparkSession.builder \
    .appName("Goodreads") \
    .master(os.getenv("SPARK_MASTER", "local[3]")) \
    .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "4g")) \
    .config("spark.sql.shuffle.partitions", os.getenv("SHUFFLE_PARTITIONS", "128")) \
    .config("spark.local.dir", SPARK_LOCAL_DIR) \
    .config("spark.memory.fraction", "0.6") \
    .getOrCreate()


def out_done(table_name):
    return (OUTPUT_DIR / table_name / '_SUCCESS').exists()


def save_to_parquet(df, table_name, partitions=None):
    if out_done(table_name):
        logging.info(f"[Checkpoint] Bảng {table_name} đã hoàn thành trước đó, bỏ qua.")
        return
    logging.info(f"Đang ghi bảng: {table_name}")
    writer_df = df.coalesce(partitions) if partitions else df
    writer_df.write \
        .mode("overwrite") \
        .parquet(str(OUTPUT_DIR / table_name))


# Checkpoint trung gian để chạy lại không phải tính từ đầu
CKPT_DIR = Path(os.getenv('CKPT_DIR', BASE_DIR / 'checkpoints' / 'full'))


def ckpt_done(name):
    return (CKPT_DIR / name / '_SUCCESS').exists()


def write_ckpt(df, name):
    logging.info(f"Ghi checkpoint: {name}")
    df.write.mode("overwrite").parquet(str(CKPT_DIR / name))
    return spark.read.parquet(str(CKPT_DIR / name))


def materialize(df):
    df = df.persist(StorageLevel.DISK_ONLY)
    df.count()
    return df


df_book_id_map = spark.read.csv(str(DIR / 'book_id_map.csv'), header=True, inferSchema=True)
df_user_id_map = spark.read.csv(str(DIR / 'user_id_map.csv'), header=True, inferSchema=True)

# 1. Enrich books (hoặc đọc thẳng từ checkpoint nếu đã chạy xong trước đó)
if ckpt_done('books_enriched'):
    logging.info("Dùng checkpoint books_enriched (bỏ qua đọc lại goodreads_books.json)")
    df_books = spark.read.parquet(str(CKPT_DIR / 'books_enriched'))
else:
    logging.info("Bắt đầu xử lý goodreads_books.json")
    df_ol_lookup = load_ol_lookup(spark)
    df_books = spark.read.json(str(DIR / 'goodreads_books.json'))
    df_books = df_books.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
    df_books = (
        df_books.drop('link', 'popular_shelves', 'series')
        .withColumn('image_url', regexp_replace(col('image_url'), r'(\d)[sm]/', r'$1l/'))
        .withColumn('similar_books', concat_ws(',', col('similar_books')))
    )
    df_books, enrich_stats = enrich_books(df_books, df_ol_lookup)
    logging.info(f"Giữ {enrich_stats['kept']}/{enrich_stats['total']} sách, loại {enrich_stats['dropped_missing_language']} sách thiếu language")
    df_books = write_ckpt(df_books, 'books_enriched')

# Loại sách nhiều ngôn ngữ ('en,fr' hoặc 'mul'): mỗi sách chỉ còn đúng một mã ngôn ngữ.
# Đặt ở đây để áp dụng cả khi đọc checkpoint books_enriched lẫn khi chạy mới, và trước k-core.
df_books = df_books.filter(~(F.col('language_code').contains(',') | (F.col('language_code') == 'mul')))

kept_book_ids = materialize(df_books.select('book_id').distinct())

# 2. Interactions + K-core
logging.info("Bắt đầu xử lý goodreads_interactions.csv")

if K_CORE > 0 and ckpt_done('interactions_kcore'):
    logging.info("Dùng checkpoint interactions_kcore")
    df_interactions = spark.read.parquet(str(CKPT_DIR / 'interactions_kcore'))
else:
    df_interactions = spark.read.csv(str(DIR / 'goodreads_interactions.csv'), header=True, inferSchema=True)
    # Không dùng broadcast() cho bảng > 1.8M dòng để tránh tràn RAM driver
    df_interactions = df_interactions.join(kept_book_ids, on='book_id', how='left_semi')
    if K_CORE > 0:
        df_interactions, _, _, kcore_stats = k_core(df_interactions, k=K_CORE)
        logging.info(f"K-core (k={K_CORE}): {kcore_stats}")
        df_interactions = write_ckpt(df_interactions, 'interactions_kcore')

if K_CORE > 0:
    kept_book_ids.unpersist()
    kept_user_ids = materialize(df_interactions.select('user_id').distinct())
    kept_book_ids = materialize(df_interactions.select('book_id').distinct())
    df_books = df_books.join(kept_book_ids, on='book_id', how='left_semi')
else:
    kept_user_ids = None

logging.info(f"Còn {df_books.count()} sách sau khi lọc")

# Đổi similar_books sang book_id csv, chỉ giữ tham chiếu tới sách còn trong catalog
df_books = remap_similar_books(df_books, df_book_id_map, kept_book_ids)

if not out_done('book_authors_map'):
    df_book_authors_map = df_books.select(
        col('book_id'),
        explode(col('authors')).alias('authors')
    ).select(
        col('book_id'),
        col('authors.author_id').alias('author_id'),
        # Chuẩn hóa role (Translator/translator) trước khi khử trùng; role rỗng giữ nguyên
        F.initcap(trim(col('authors.role'))).alias('role')
    ).dropDuplicates(['book_id', 'author_id', 'role'])
    save_to_parquet(df_book_authors_map, 'book_authors_map', partitions=8)

if not out_done('books'):
    save_to_parquet(df_books.drop('authors'), 'books', partitions=16)

logging.info("Đã xử lý xong books")

if not out_done('works'):
    logging.info("Bắt đầu xử lý goodreads_book_works.json")
    df_works = spark.read.json(str(DIR / 'goodreads_book_works.json'))
    # Đổi best_book_id sang ID csv; bỏ cột book_id (ID Goodreads) của bảng map
    df_works = df_works.join(df_book_id_map, df_works['best_book_id'] == df_book_id_map['book_id'], how='left') \
        .drop('best_book_id', 'book_id') \
        .withColumnRenamed('book_id_csv', 'best_book_id')

    # Ấn bản thật sự còn trong catalog (sau k-core)
    df_editions = spark.read.parquet(str(OUTPUT_DIR / 'books')).select(
        col('book_id').alias('_ed_book_id'),
        col('work_id'),
        F.when(trim(col('ratings_count')).rlike(r'^[+-]?\d+$'), col('ratings_count').cast('long')).alias('_ed_ratings'),
    )

    # Giữ best_book_id nếu còn trong catalog; nếu không thì để null để điền ở dưới
    edition_ids = df_editions.select(col('_ed_book_id').alias('_cat_id')).distinct()
    df_works = (df_works
        .join(edition_ids, df_works['best_book_id'] == edition_ids['_cat_id'], how='left')
        .withColumn('_best_ok', col('_cat_id').isNotNull())
        .drop('_cat_id'))

    # Ấn bản thay thế: ratings_count cao nhất trong các ấn bản còn lại của cùng work
    best_edition = (df_editions
        .withColumn('_rn', F.row_number().over(
            Window.partitionBy('work_id').orderBy(F.col('_ed_ratings').desc_nulls_last(), F.col('_ed_book_id'))))
        .filter(col('_rn') == 1)
        .select('work_id', col('_ed_book_id').alias('_fallback_id')))

    # Inner join: bỏ work không còn ấn bản nào trong catalog
    df_works = (df_works
        .join(best_edition, on='work_id', how='inner')
        .withColumn('best_book_id', F.when(col('_best_ok'), col('best_book_id')).otherwise(col('_fallback_id')))
        .drop('_best_ok', '_fallback_id'))

    save_to_parquet(df_works, 'works', partitions=16)
    logging.info("Đã xử lý xong works")

save_to_parquet(df_interactions, 'interactions')
logging.info("Đã xử lý xong interactions")

if not out_done('genres'):
    logging.info("Bắt đầu xử lý goodreads_book_genres_initial.json")
    df_genres = spark.read.json(str(DIR / 'goodreads_book_genres_initial.json'))
    df_genres = df_genres.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
    df_genres = df_genres.join(kept_book_ids, on='book_id', how='left_semi')

    genre_fields = df_genres.schema['genres'].dataType.fieldNames()
    map_expr = create_map([item for field in genre_fields for item in (lit(field), col(f"genres.{field}"))])
    df_genres = df_genres.withColumn('genres_map', map_expr)
    df_genres = df_genres.select(
        col('book_id'),
        explode('genres_map')
    ).withColumnRenamed('key', 'genres').withColumnRenamed('value', 'votes')
    df_genres = df_genres.filter(col('votes').isNotNull())
    save_to_parquet(df_genres, 'genres', partitions=8)
    logging.info("Đã xử lý xong genres")

if not out_done('reviews'):
    logging.info("Bắt đầu xử lý goodreads_reviews_dedup.json")
    df_reviews = spark.read.json(str(DIR / 'goodreads_reviews_dedup.json'))
    df_reviews = df_reviews.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
    df_reviews = df_reviews.join(kept_book_ids, on='book_id', how='left_semi')
    df_reviews = df_reviews.join(df_user_id_map, on='user_id').drop('user_id').withColumnRenamed('user_id_csv', 'user_id')
    if kept_user_ids is not None:
        df_reviews = df_reviews.join(kept_user_ids, on='user_id', how='left_semi')
    df_reviews = df_reviews.withColumn('review_text', trim(regexp_replace(col('review_text'), r'[\n\r]+', ' ')))
    save_to_parquet(df_reviews, 'reviews', partitions=32)
    logging.info("Đã xử lý xong reviews")

if not out_done('authors'):
    logging.info("Bắt đầu xử lý goodreads_book_authors.json")
    df_authors = spark.read.json(str(DIR / 'goodreads_book_authors.json'))
    save_to_parquet(df_authors, 'authors', partitions=8)
    logging.info("Đã xử lý xong authors")

# Liên kết sách - dãy sách. Độc lập với nhánh books vì cột series đã bị bỏ ở checkpoint books_enriched.
if not out_done('book_series_map'):
    logging.info("Bắt đầu xử lý book_series_map từ goodreads_books.json")
    df_book_series_src = spark.read.schema(BOOK_SERIES_SCHEMA).json(str(DIR / 'goodreads_books.json'))
    df_book_series_map = book_series_pairs(df_book_series_src, df_book_id_map, kept_book_ids)
    save_to_parquet(df_book_series_map, 'book_series_map', partitions=8)
    logging.info("Đã xử lý xong book_series_map")

# Bảng series chỉ giữ dãy còn được sách trong catalog tham chiếu
df_book_series_map = spark.read.parquet(str(OUTPUT_DIR / 'book_series_map'))
if not out_done('series'):
    logging.info("Bắt đầu xử lý goodreads_book_series.json")
    df_series = spark.read.json(str(DIR / 'goodreads_book_series.json'))
    referenced_series = df_book_series_map.select(F.col('series_id').alias('_sid')).distinct()
    df_series = (df_series
        .withColumn('_sid', F.col('series_id').cast('string'))
        .join(referenced_series, on='_sid', how='left_semi')
        .drop('_sid'))
    save_to_parquet(df_series, 'series', partitions=8)
    logging.info("Đã xử lý xong series")

kept_book_ids.unpersist()
if kept_user_ids is not None:
    kept_user_ids.unpersist()

spark.stop()
logging.info("Hoàn tất toàn bộ process_enriched!")
