import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from pathlib import Path
from itertools import chain
from pyspark.sql import SparkSession, Window
from pyspark.sql.types import StringType
from pyspark.sql.functions import udf, count, col, when, rand, row_number, explode, regexp_replace, trim, concat_ws, lit, create_map, coalesce, broadcast


DIR = Path(__file__).parent.parent
DATA_DIR = DIR / 'data'
OUTPUT_DIR = DIR / 'samples_data'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    .appName("SampleGoodreads") \
    .config("spark.driver.memory", "4g") \
    .getOrCreate()

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

df_book_id_map = spark.read.csv(str(DATA_DIR / 'book_id_map.csv'), header=True, inferSchema=True)
df_user_id_map = spark.read.csv(str(DATA_DIR / 'user_id_map.csv'), header=True, inferSchema=True)

df_interactions = spark.read.csv(str(DATA_DIR / 'goodreads_interactions.csv'), header=True, inferSchema=True)
book_popularity = df_interactions.groupBy('book_id').agg(count('*').alias('interaction_count'))

print("Bắt đầu lấy mẫu và xử lý cho books")

df_books = spark.read.json(str(DATA_DIR / 'goodreads_books.json'))
df_books = df_books.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')

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

df_book_authors_map.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'book_authors_map'))
df_books.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'books'))

print(f"Kích thước mẫu của books: {df_books.count()}")

print("Bắt đầu lấy mẫu và xử lý cho users và interactions")

df_interactions = df_interactions.join(broadcast(sampled_books), on='book_id')

df_interactions.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'interactions'))

print(f"Kích thước mẫu của users: {df_interactions.select('user_id').distinct().count()}")
print(f"Kích thước mẫu của interactions: {df_interactions.count()}")

print("Bắt đầu xử lý cho book works")

df_works = spark.read.json(str(DATA_DIR / 'goodreads_book_works.json'))
df_works = df_works.join(df_book_id_map, df_works['best_book_id'] == df_book_id_map['book_id']).drop('best_book_id', 'book_id').withColumnRenamed('book_id_csv', 'best_book_id')

df_works.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'works'))

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

print("Bắt đầu xứ lý cho reviews")

df_reviews = spark.read.json(str(DATA_DIR / 'goodreads_reviews_dedup.json'))
df_reviews = df_reviews.join(df_book_id_map, on='book_id').drop('book_id').withColumnRenamed('book_id_csv', 'book_id')
df_reviews = df_reviews.join(broadcast(sampled_books), on='book_id')
df_reviews = df_reviews.join(df_user_id_map, on='user_id').drop('user_id').withColumnRenamed('user_id_csv', 'user_id')
df_reviews = df_reviews.withColumn('review_text', trim(regexp_replace(col('review_text'), r'[\n\r]+', ' ')))

df_reviews.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'reviews'))

print("Bắt đầu xử lý cho authors")

df_authors = spark.read.json(str(DATA_DIR / 'goodreads_book_authors.json'))

df_authors.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'authors'))

print("Bắt đầu xử lý cho series")

df_series = spark.read.json(str(DATA_DIR / 'goodreads_book_series.json'))

df_series.write.mode('overwrite').parquet(str(OUTPUT_DIR / 'series'))

spark.stop()
