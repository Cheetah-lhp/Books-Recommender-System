"""Bổ sung ISBN / ngôn ngữ / ảnh bìa cho sách Goodreads từ bảng tra cứu Open Library.

Module dùng chung cho process.py và process_samples.py. Các hàm ISBN và ngôn ngữ là
Python thuần (không cần pyspark) để build_ol_lookup.py và test dùng lại được.
"""
import json
import logging
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'
OL_LOOKUP_DIR = Path(os.getenv('OL_LOOKUP_DIR', DATA_DIR / 'ol_isbn_lookup'))
COVER_URL_TEMPLATE = 'https://covers.openlibrary.org/b/id/{cover_id}-L.jpg'

# 'dump' (mặc định): lấy cover_id trực tiếp từ dump. 'api': gọi covers.openlibrary.org theo ISBN như cũ.
IMAGE_SOURCE = os.getenv('IMAGE_SOURCE', 'dump').strip().lower()

MISSING_LANGUAGE_VALUES = ('', '--', 'Select...', 'und')

LANGUAGE_MAPPING = {
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


# ---------------------------------------------------------------------------
# ISBN
# ---------------------------------------------------------------------------

def clean_isbn(value):
    """Bỏ khoảng trắng/dấu gạch nối, viết hoa X. Trả về '' nếu rỗng hoặc không phải chuỗi."""
    if value is None:
        return ''
    text = str(value).strip().replace('-', '').replace(' ', '').upper()
    return text


def is_valid_isbn10(isbn):
    if len(isbn) != 10 or not isbn[:9].isdigit() or not (isbn[9].isdigit() or isbn[9] == 'X'):
        return False
    total = sum((10 - i) * int(ch) for i, ch in enumerate(isbn[:9]))
    total += 10 if isbn[9] == 'X' else int(isbn[9])
    return total % 11 == 0


def is_valid_isbn13(isbn):
    if len(isbn) != 13 or not isbn.isdigit() or isbn[:3] not in ('978', '979'):
        return False
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn[:12]))
    return (10 - total % 10) % 10 == int(isbn[12])


def isbn10_to_13(isbn10):
    """ISBN-10 hợp lệ -> ISBN-13 (tiền tố 978). Trả về None nếu không hợp lệ."""
    isbn10 = clean_isbn(isbn10)
    if not is_valid_isbn10(isbn10):
        return None
    body = '978' + isbn10[:9]
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(body))
    return body + str((10 - total % 10) % 10)


def isbn13_to_10(isbn13):
    """ISBN-13 hợp lệ tiền tố 978 -> ISBN-10. Tiền tố 979 hoặc không hợp lệ trả về None."""
    isbn13 = clean_isbn(isbn13)
    if not is_valid_isbn13(isbn13) or not isbn13.startswith('978'):
        return None
    body = isbn13[3:12]
    total = sum((10 - i) * int(ch) for i, ch in enumerate(body))
    check = (11 - total % 11) % 11
    return body + ('X' if check == 10 else str(check))


def isbn13_key(isbn, isbn13):
    """Khóa ISBN-13 chuẩn hóa của một cuốn sách: ưu tiên isbn13 hợp lệ, nếu không thì đổi từ isbn."""
    candidate = clean_isbn(isbn13)
    if is_valid_isbn13(candidate):
        return candidate
    candidate = clean_isbn(isbn13)
    if is_valid_isbn10(candidate):  # isbn13 bị nhập nhầm ISBN-10
        return isbn10_to_13(candidate)
    candidate = clean_isbn(isbn)
    if is_valid_isbn13(candidate):
        return candidate
    return isbn10_to_13(candidate)


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

def is_missing_language(value):
    return value is None or str(value).strip() in MISSING_LANGUAGE_VALUES


def normalize_language_code(value):
    """Áp mapping cho một mã language có sẵn; giá trị thiếu trả về None."""
    if is_missing_language(value):
        return None
    value = str(value).strip()
    return LANGUAGE_MAPPING.get(value, value)


def normalize_languages(codes):
    """Danh sách mã từ dump -> chuỗi nối dấu phẩy ('en,fr'), giữ thứ tự, bỏ trùng. Rỗng -> None."""
    if not codes:
        return None
    result = []
    for code in codes:
        code = normalize_language_code(code)
        if code and code not in result:
            result.append(code)
    return ','.join(result) if result else None


# ---------------------------------------------------------------------------
# Lookup từ dump
# ---------------------------------------------------------------------------

def read_lookup_quality(lookup_dir=None):
    lookup_dir = Path(lookup_dir or OL_LOOKUP_DIR)
    report_path = lookup_dir / '_quality.json'
    if not report_path.exists():
        raise RuntimeError(
            f"Chưa có bảng tra cứu Open Library tại {lookup_dir}. "
            f"Chạy `python process/build_ol_lookup.py` trước."
        )
    with open(report_path, encoding='utf-8') as f:
        return json.load(f)


def load_ol_lookup(spark, lookup_dir=None):
    """Đọc bảng tra cứu parquet; từ chối nếu báo cáo chất lượng không đạt."""
    lookup_dir = Path(lookup_dir or OL_LOOKUP_DIR)
    report = read_lookup_quality(lookup_dir)
    if report.get('status') != 'pass':
        raise RuntimeError(
            f"Dump Open Library không đạt kiểm tra chất lượng ({report.get('failures')}). "
            f"Xem {lookup_dir / '_quality.json'}."
        )
    return spark.read.parquet(str(lookup_dir))


# ---------------------------------------------------------------------------
# Spark
# ---------------------------------------------------------------------------

_api_session = None


def replace_image_url(isbn, isbn13, size='L'):
    """Đường lùi (IMAGE_SOURCE=api): hỏi covers.openlibrary.org theo ISBN."""
    global _api_session
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry

    if _api_session is None:
        retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'])
        _api_session = requests.Session()
        _api_session.mount('https://', HTTPAdapter(max_retries=retry))

    for code in [isbn, isbn13]:
        if code and str(code).strip():
            url = f'https://covers.openlibrary.org/b/isbn/{str(code).strip()}-{size}.jpg'
            try:
                response = _api_session.get(url, timeout=3)
                if response.status_code == 200 and len(response.content) > 1000:
                    return url
            except Exception:
                pass
    return None


def enrich_books(df_books, df_lookup, image_source=None):
    """Bổ sung isbn/isbn13/language_code/image_url từ lookup rồi loại sách vẫn thiếu language.

    Trả về (df_kept, stats). df_books phải có các cột isbn, isbn13, language_code, image_url.
    DataFrame trung gian được persist (DISK_ONLY) để thống kê không đọc lại nguồn.
    """
    from pyspark import StorageLevel
    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType, StringType

    image_source = (image_source or IMAGE_SOURCE).lower()

    # UDF tham chiếu hàm trong module này; pickle theo giá trị để Python worker không cần import
    # được book_enrichment (phụ thuộc thư mục chạy) và không cần addPyFile.
    import sys
    from pyspark import cloudpickle
    cloudpickle.register_pickle_by_value(sys.modules[__name__])

    isbn13_key_udf = F.udf(isbn13_key, StringType())
    isbn10_from_13_udf = F.udf(isbn13_to_10, StringType())
    isbn13_from_10_udf = F.udf(isbn10_to_13, StringType())
    normalize_languages_udf = F.udf(normalize_languages, StringType())
    normalize_language_code_udf = F.udf(normalize_language_code, StringType())
    fetch_image_url_udf = F.udf(replace_image_url, StringType())

    def blank(name):
        return F.trim(F.coalesce(F.col(name).cast('string'), F.lit(''))) == ''

    lookup = df_lookup.select(
        F.col('isbn13').alias('_isbn_key'),
        F.col('isbn10').alias('_ol_isbn10'),
        F.col('languages').cast(ArrayType(StringType())).alias('_ol_languages'),
        F.col('cover_id').alias('_ol_cover_id'),
    )

    df = df_books.withColumn('_isbn_key', isbn13_key_udf(F.col('isbn'), F.col('isbn13')))
    df = df.join(lookup, on='_isbn_key', how='left')

    # Cờ trạng thái ban đầu
    df = (df
          .withColumn('_need_isbn', blank('isbn'))
          .withColumn('_need_isbn13', blank('isbn13'))
          .withColumn('_need_lang', F.coalesce(F.trim(F.col('language_code')).isin(*MISSING_LANGUAGE_VALUES), F.lit(True)))
          .withColumn('_need_cover', blank('image_url') | F.coalesce(F.col('image_url').contains('/nophoto/'), F.lit(False))))

    # 1. ISBN: chỉ điền chỗ trống, giữ nguyên giá trị gốc nếu không tìm được
    isbn_filled = F.coalesce(isbn10_from_13_udf(F.col('isbn13')), isbn10_from_13_udf(F.col('_isbn_key')), F.col('_ol_isbn10'))
    isbn13_filled = F.coalesce(F.col('_isbn_key'), isbn13_from_10_udf(F.col('isbn')))
    df = (df
          .withColumn('isbn', F.when(F.col('_need_isbn'), F.coalesce(isbn_filled, F.col('isbn'))).otherwise(F.col('isbn')))
          .withColumn('isbn13', F.when(F.col('_need_isbn13'), F.coalesce(isbn13_filled, F.col('isbn13'))).otherwise(F.col('isbn13')))
          .withColumn('_f_isbn', F.col('_need_isbn') & ~blank('isbn'))
          .withColumn('_f_isbn13', F.col('_need_isbn13') & ~blank('isbn13')))

    # 2. Language: có sẵn thì chuẩn hóa mã, thiếu thì lấy tất cả language từ dump
    ol_language = normalize_languages_udf(F.col('_ol_languages'))
    df = (df
          .withColumn('_ol_language', ol_language)
          .withColumn('language_code', F.when(F.col('_need_lang'), F.col('_ol_language'))
                      .otherwise(normalize_language_code_udf(F.col('language_code'))))
          .withColumn('_f_lang', F.col('_need_lang') & F.col('_ol_language').isNotNull()))

    # 3. Ảnh bìa
    if image_source == 'api':
        new_cover = fetch_image_url_udf(F.col('isbn'), F.col('isbn13'))
    else:
        new_cover = F.when(
            F.col('_ol_cover_id').isNotNull(),
            F.concat(F.lit('https://covers.openlibrary.org/b/id/'), F.col('_ol_cover_id').cast('string'), F.lit('-L.jpg')),
        )
    df = (df
          .withColumn('_old_image_url', F.col('image_url'))
          .withColumn('image_url', F.when(F.col('_need_cover'), F.coalesce(new_cover, F.col('image_url'))).otherwise(F.col('image_url')))
          .withColumn('_f_cover', F.col('_need_cover') & (F.col('image_url') != F.col('_old_image_url'))))

    df = df.drop('_isbn_key', '_ol_isbn10', '_ol_languages', '_ol_cover_id', '_ol_language', '_old_image_url')
    df = df.persist(StorageLevel.DISK_ONLY)

    row = df.agg(
        F.count('*').alias('total'),
        F.sum(F.col('_need_isbn').cast('int')).alias('missing_isbn'),
        F.sum(F.col('_need_isbn13').cast('int')).alias('missing_isbn13'),
        F.sum(F.col('_need_lang').cast('int')).alias('missing_language'),
        F.sum(F.col('_need_cover').cast('int')).alias('missing_cover'),
        F.sum(F.col('_f_isbn').cast('int')).alias('isbn_filled'),
        F.sum(F.col('_f_isbn13').cast('int')).alias('isbn13_filled'),
        F.sum(F.col('_f_lang').cast('int')).alias('language_filled'),
        F.sum(F.col('_f_cover').cast('int')).alias('cover_filled'),
        F.sum(F.col('language_code').isNull().cast('int')).alias('dropped_missing_language'),
    ).collect()[0]
    stats = {k: int(v or 0) for k, v in row.asDict().items()}
    stats['kept'] = stats['total'] - stats['dropped_missing_language']
    stats['image_source'] = image_source
    logging.info(f"Bổ sung metadata từ Open Library dump: {stats}")

    flag_cols = ['_need_isbn', '_need_isbn13', '_need_lang', '_need_cover', '_f_isbn', '_f_isbn13', '_f_lang', '_f_cover']
    df_kept = df.filter(F.col('language_code').isNotNull()).drop(*flag_cols)
    return df_kept, stats
