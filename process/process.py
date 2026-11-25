import os
import pymysql
import logging
import requests
from dotenv import load_dotenv
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from itertools import chain
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType
from pyspark.sql.functions import udf, col, explode, regexp_replace, trim, concat_ws, lit, create_map, when, coalesce


load_dotenv()

DIR = Path(__file__).parent.parent / 'data'
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True, parents=True)
DB_HOST = os.getenv('DB_HOST')
DB_URL = os.getenv('DB_URL')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

logging.basicConfig(
    level = logging.INFO, 
    format = '%(asctime)s - %(levelname)s - %(message)s',
    filename = LOG_DIR / 'process.log'
)

retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=['GET']
)

http_session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
http_session.mount('https://', adapter)

spark = SparkSession.builder \
    .appName("Goodreads") \
    .config("spark.driver.memory", "4g") \
    .config("spark.sql.shuffle.partitions", "16") \
    .config("spark.jars.packages", "mysql:mysql-connector-java:8.0.33") \
    .getOrCreate()

connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD)
try:
    with connection.cursor() as cursor:
        sql = 'CREATE DATABASE IF NOT EXISTS goodreads CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
        cursor.execute(sql)
    connection.commit()
    logging.info("Đã có database")
except Exception as e:
    logging.exception("Lỗi khi tạo database")
finally:
    connection.close()

def save_to_mysql(df, table_name):
    logging.info(f"Đang ghi bảng: {table_name}")
    df.coalesce(4).write \
        .format("jdbc") \
        .option("url", f"{DB_URL}?rewriteBatchedStatements=true") \
        .option("dbtable", table_name) \
        .option("user", DB_USER) \
        .option("password", DB_PASSWORD) \
        .option("driver", 'com.mysql.cj.jdbc.Driver') \
        .option("batchsize", "2000") \
        .option("sessionInitStatement", "SET autocommit=0; SET unique_checks=0; SET foreign_key_checks=0;") \
        .mode("overwrite") \
        .save()

def replace_image_url(isbn, isbn13, size='L'):
    for code in [isbn, isbn13]:
        if code and str(code).strip():
            code = str(code).strip()
            url = f'https://covers.openlibrary.org/b/isbn/{code}-{size}.jpg'
            try:
                response = http_session.get(url, timeout=3)
                if response.status_code == 200 and len(response.content) > 1000:
                    return url
            except Exception:
                pass

    return None

fetch_image_url_udf = udf(replace_image_url, StringType())

df_book_id_map = spark.read.csv(str(DIR / 'book_id_map.csv'), header=True, inferSchema=True)
df_user_id_map = spark.read.csv(str(DIR / 'user_id_map.csv'), header=True, inferSchema=True)

logging.info("Bắt đầu xử lý goodreads_books.json")

df_books = spark.read.json(str(DIR / 'goodreads_books.json'))
df_books = df_books.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')

df_book_authors_map = df_books.select(
    col('book_id'),
    explode(col('authors')).alias('authors')
).select(
    col('book_id'),
    col('authors.author_id').alias('author_id'),
    col('authors.role').alias('role')
)

save_to_mysql(df_book_authors_map, 'book_authors_map')

# df_book_shelves_map = df_books.select(
#     col('book_id'),
#     explode('popular_shelves').alias('shelves')
# ).select(
#     col('book_id'),
#     col('shelves.name').alias('shelf_name'),
#     col('shelves.count').cast('int').alias('count')
# )

# save_to_mysql(df_book_shelves_map, 'book_shelves_map')

df_books = df_books.drop('link', 'authors', 'popular_shelves', 'series').withColumn('image_url', regexp_replace(col('image_url'), r'(\d)[sm]/', r'$1l/')).withColumn('similar_books', concat_ws(',', col('similar_books')))
df_books = df_books.withColumn(
    'image_url',
    when(
        col('image_url').contains('/nophoto/'),
        coalesce(
            fetch_image_url_udf(col('isbn'), col('isbn13')),
            col('image_url')
        )
    ).otherwise(col('image_url'))
)

mapping_dict = {
    # Tiếng Anh
    'eng': 'en',    # Tiếng Anh (chuẩn ISO 639-2)
    'en-US': 'en',  # Tiếng Anh (Mỹ)
    'en-GB': 'en',  # Tiếng Anh (Anh)
    'en-CA': 'en',  # Tiếng Anh (Canada)
    'en-IN': 'en',  # Tiếng Anh (Ấn Độ)
    
    # Tiếng Pháp
    'fre': 'fr',    # Tiếng Pháp (chuẩn ISO 639-2/B)
    
    # Tiếng Tây Ban Nha
    'spa': 'es',    # Tiếng Tây Ban Nha
    'es-MX': 'es',  # Tiếng Tây Ban Nha (Mexico)
    
    # Tiếng Đức
    'ger': 'de',    # Tiếng Đức (chuẩn ISO 639-2/B)
    
    # Tiếng Ý
    'ita': 'it',    # Tiếng Ý
    
    # Tiếng Bồ Đào Nha
    'por': 'pt',    # Tiếng Bồ Đào Nha
    'pt-BR': 'pt',  # Tiếng Bồ Đào Nha (Brazil)
    
    # Tiếng Hà Lan
    'dut': 'nl',    # Tiếng Hà Lan (chuẩn ISO 639-2/B)
    'nld': 'nl',    # Tiếng Hà Lan (chuẩn ISO 639-2/T)
    
    # Tiếng Ba Tư (Farsi)
    'per': 'fa',    # Tiếng Ba Tư (chuẩn ISO 639-2/B)
    'pes': 'fa',    # Tiếng Ba Tư Tây (Iranian Persian)
    
    # Tiếng Trung
    'zho': 'zh',    # Tiếng Trung (chuẩn ISO 639-2/T)
    'chi': 'zh',    # Tiếng Trung (chuẩn ISO 639-2/B)
}

map_expr = create_map([lit(x) for x in chain(*mapping_dict.items())])

df_books = df_books.withColumn(
    'language_code',
    when(
        (col('language_code').isNull()) | (trim(col('language_code')).isin("", "--", "Select...", "und")),
        'unknown'
    ).otherwise(coalesce(map_expr[col('language_code')], col('language_code')))
)

save_to_mysql(df_books, 'books')

logging.info("Đã xử lý xong")

logging.info("Bắt đầu xử lý goodreads_book_works.json")

df_works = spark.read.json(str(DIR / 'goodreads_book_works.json'))
df_works = df_works.join(df_book_id_map, df_works['best_book_id'] == df_book_id_map['book_id'], how='left').drop('best_book_id').withColumnRenamed('book_id_csv', 'best_book_id')
save_to_mysql(df_works, 'works')

logging.info("Đã xử lý xong")

logging.info("Bắt đầu xử lý goodreads_interactions.csv")

df_interactions = spark.read.csv(str(DIR / 'goodreads_interactions.csv'), header=True, inferSchema=True)

save_to_mysql(df_interactions, 'interactions')

logging.info("Đã xử lý xong")

logging.info("Bắt đầu xử lý goodreads_book_genres_initial.json")

df_genres = spark.read.json(str(DIR / 'goodreads_book_genres_initial.json'))
df_genres = df_genres.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')

genre_fields = df_genres.schema['genres'].dataType.fieldNames()
map_expr = create_map([item for field in genre_fields for item in (lit(field), col(f"genres.{field}"))])
df_genres = df_genres.withColumn('genres_map', map_expr)
df_genres = df_genres.select(
    col('book_id'),
    explode('genres_map')
).withColumnRenamed('key', 'genres').withColumnRenamed('value', 'votes')
df_genres = df_genres.filter(col('votes').isNotNull())

save_to_mysql(df_genres, 'genres')

logging.info("Đã xử lý xong")

logging.info("Bắt đầu xử lý goodreads_reviews_dedup.json")

df_reviews = spark.read.json(str(DIR / 'goodreads_reviews_dedup.json'))
df_reviews = df_reviews.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
df_reviews = df_reviews.join(df_user_id_map, on='user_id').drop('user_id').withColumnRenamed('user_id_csv', 'user_id')
df_reviews = df_reviews.withColumn('review_text', trim(regexp_replace(col('review_text'), r'[\n\r]+', ' ')))

save_to_mysql(df_reviews, 'reviews')

logging.info("Đã xử lý xong")

logging.info("Bắt đầu xử lý goodreads_book_authors.json")

df_authors = spark.read.json(str(DIR / 'goodreads_book_authors.json'))
save_to_mysql(df_authors, 'authors')

logging.info("Đã xử lý xong")

logging.info("Bắt đầu xử lý goodreads_book_series.json")

df_series = spark.read.json(str(DIR / 'goodreads_book_series.json'))

save_to_mysql(df_series, 'series')

spark.stop()
