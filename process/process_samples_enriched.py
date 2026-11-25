import os
import sys
from pathlib import Path
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import count, col, when, rand, row_number, explode, regexp_replace, trim, concat_ws, lit, create_map, broadcast

from book_enrichment import enrich_books, load_ol_lookup

DIR = Path(__file__).parent.parent
DATA_DIR = DIR / 'data'
target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getenv('OUTPUT_DIR', 'test_data')
OUTPUT_DIR = Path(target_dir)
if not OUTPUT_DIR.is_absolute():
    OUTPUT_DIR = DIR / OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Thư mục đầu ra: {OUTPUT_DIR}")


def is_done(table_name: str) -> bool:
    return (OUTPUT_DIR / table_name / '_SUCCESS').exists()


spark = SparkSession.builder \
    .appName("SampleGoodreads") \
    .config("spark.driver.memory", "4g") \
    .getOrCreate()

df_book_id_map = spark.read.csv(str(DATA_DIR / 'book_id_map.csv'), header=True, inferSchema=True)
df_user_id_map = spark.read.csv(str(DATA_DIR / 'user_id_map.csv'), header=True, inferSchema=True)

# 1. BOOKS & BOOK_AUTHORS_MAP (Bảng nặng nhất)
if is_done('books') and is_done('book_authors_map'):
    print("[Checkpoint] Bảng books và book_authors_map đã có sẵn, đọc 10,000 sách mẫu để tiếp tục...")
    df_books = spark.read.parquet(str(OUTPUT_DIR / 'books'))
    sampled_books = df_books.select('book_id').distinct()
else:
    df_interactions_all = spark.read.csv(str(DATA_DIR / 'goodreads_interactions.csv'), header=True, inferSchema=True)
    book_popularity = df_interactions_all.groupBy('book_id').agg(count('*').alias('interaction_count'))

    print("Bắt đầu lấy mẫu và xử lý cho books")
    df_books = spark.read.json(str(DATA_DIR / 'goodreads_books.json'))
    df_books = df_books.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
    df_books = df_books.drop('link', 'popular_shelves', 'series').withColumn('image_url', regexp_replace(col('image_url'), r'(\d)[sm]/', r'$1l/')).withColumn('similar_books', concat_ws(',', col('similar_books')))

    # Bổ sung isbn/isbn13/language/ảnh bìa từ Open Library dump
    df_ol_lookup = load_ol_lookup(spark)
    df_books, enrich_stats = enrich_books(df_books, df_ol_lookup)
    print(f"Bổ sung metadata từ Open Library dump: {enrich_stats}")
    print(f"Giữ {enrich_stats['kept']}/{enrich_stats['total']} sách, loại {enrich_stats['dropped_missing_language']} sách thiếu language")

    df_books_with_popularity = df_books.join(book_popularity, on='book_id', how='left').fillna({'interaction_count': 0})
    quantiles = df_books_with_popularity.approxQuantile('interaction_count', [i/10.0 for i in range(1, 10)], 0.01)
    bucket_expr = when(col("interaction_count") <= quantiles[0], 1)
    for i in range(1, 9):
        bucket_expr = bucket_expr.when((col("interaction_count") > quantiles[i-1]) & (col("interaction_count") <= quantiles[i]), i + 1)
    bucket_expr = bucket_expr.otherwise(10)

    df_book_bucketed = df_books_with_popularity.withColumn('bucket', bucket_expr)
    bucket_window = Window.partitionBy('bucket').orderBy(rand(seed=42))
    df_stratified_sampled = df_book_bucketed.withColumn('rn', row_number().over(bucket_window)).filter(col('rn') <= 1000)

    sampled_books = df_stratified_sampled.select('book_id').distinct()
    df_books = df_books.join(broadcast(sampled_books), on='book_id')

    df_book_authors_map = df_books.select(
        col('book_id'),
        explode(col('authors')).alias('authors')
    ).select(
        col('book_id'),
        col('authors.author_id').alias('author_id'),
        col('authors.role').alias('role')
    )

    df_books = df_books.drop('authors')
    df_book_authors_map.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'book_authors_map'))
    df_books.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'books'))

print(f"Kích thước mẫu của books: {sampled_books.count()}")

# 2. INTERACTIONS
if is_done('interactions'):
    print("[Checkpoint] Bảng interactions đã có sẵn, bỏ qua.")
else:
    print("Bắt đầu lấy mẫu và xử lý cho interactions")
    df_interactions = spark.read.csv(str(DATA_DIR / 'goodreads_interactions.csv'), header=True, inferSchema=True)
    df_interactions = df_interactions.join(broadcast(sampled_books), on='book_id')
    df_interactions.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'interactions'))
    print(f"Kích thước mẫu của interactions: {df_interactions.count()}")

# 3. WORKS
if is_done('works'):
    print("[Checkpoint] Bảng works đã có sẵn, bỏ qua.")
else:
    print("Bắt đầu xử lý cho book works")
    df_works = spark.read.json(str(DATA_DIR / 'goodreads_book_works.json'))
    df_works = df_works.join(df_book_id_map, df_works['best_book_id'] == df_book_id_map['book_id']).drop('best_book_id', 'book_id').withColumnRenamed('book_id_csv', 'best_book_id')
    df_works.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'works'))

# 4. GENRES
if is_done('genres'):
    print("[Checkpoint] Bảng genres đã có sẵn, bỏ qua.")
else:
    print("Bắt đầu xử lý cho book genres")
    df_genres = spark.read.json(str(DATA_DIR / 'goodreads_book_genres_initial.json'))
    df_genres = df_genres.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
    df_genres = df_genres.join(broadcast(sampled_books), on='book_id')

    genre_fields = df_genres.schema['genres'].dataType.fieldNames()
    map_expr = create_map([item for field in genre_fields for item in (lit(field), col(f"genres.{field}"))])
    df_genres = df_genres.withColumn('genres_map', map_expr)
    df_genres = df_genres.select(
        col('book_id'),
        explode('genres_map')
    ).withColumnRenamed('key', 'genres').withColumnRenamed('value', 'votes')
    df_genres = df_genres.filter(col('votes').isNotNull())
    df_genres.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'genres'))

# 5. REVIEWS
if is_done('reviews'):
    print("[Checkpoint] Bảng reviews đã có sẵn, bỏ qua.")
else:
    print("Bắt đầu xử lý cho reviews")
    # Tối ưu: Lọc trước theo 10,000 sách mẫu để stream file 16.7GB nhanh, tránh OOM
    sampled_id_map = df_book_id_map.join(
        broadcast(sampled_books),
        df_book_id_map['book_id_csv'] == sampled_books['book_id']
    ).select(
        df_book_id_map['book_id'].cast('string').alias('gr_book_id'),
        df_book_id_map['book_id_csv'].alias('book_id_internal')
    )

    df_reviews = spark.read.json(str(DATA_DIR / 'goodreads_reviews_dedup.json'))
    df_reviews = df_reviews.join(broadcast(sampled_id_map), df_reviews['book_id'] == sampled_id_map['gr_book_id'])
    df_reviews = df_reviews.drop('book_id', 'gr_book_id').withColumnRenamed('book_id_internal', 'book_id')
    df_reviews = df_reviews.join(df_user_id_map, on='user_id').drop('user_id').withColumnRenamed('user_id_csv', 'user_id')
    df_reviews = df_reviews.withColumn('review_text', trim(regexp_replace(col('review_text'), r'[\n\r]+', ' ')))
    df_reviews.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'reviews'))

# 6. AUTHORS
if is_done('authors'):
    print("[Checkpoint] Bảng authors đã có sẵn, bỏ qua.")
else:
    print("Bắt đầu xử lý cho authors")
    df_authors = spark.read.json(str(DATA_DIR / 'goodreads_book_authors.json'))
    df_authors.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'authors'))

# 7. SERIES
if is_done('series'):
    print("[Checkpoint] Bảng series đã có sẵn, bỏ qua.")
else:
    print("Bắt đầu xử lý cho series")
    df_series = spark.read.json(str(DATA_DIR / 'goodreads_book_series.json'))
    df_series.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'series'))

spark.stop()
print("Hoàn tất xử lý toàn bộ dữ liệu mẫu!")
