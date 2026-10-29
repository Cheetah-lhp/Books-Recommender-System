"""
Script import 5000 sach tu goodreads_subsets/unified_books.csv vao Aiven PostgreSQL
Chay: python import_books.py [--limit 5000]
"""

import os
import sys
import time
import argparse
import psycopg2
import psycopg2.extras

# Fix UTF-8 stdout tren Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

AIVEN_URL = os.getenv(
    "AIVEN_DATABASE_URL",
    "postgres://avnadmin:YOUR_AIVEN_PASSWORD@database-recommender-system.f.aivencloud.com:21595/defaultdb?sslmode=require"
)

CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "goodreads_subsets", "unified_books.csv"
)


def parse_args():
    p = argparse.ArgumentParser(description="Import sach vao Aiven PostgreSQL")
    p.add_argument("--limit", type=int, default=5000, help="So sach toi da can import (default: 5000)")
    p.add_argument("--batch", type=int, default=500, help="Batch size moi lan insert (default: 500)")
    p.add_argument("--offset", type=int, default=0, help="Bo qua N dong dau (default: 0)")
    return p.parse_args()


def clean_int(val):
    try:
        v = str(val).strip().split('.')[0]
        return int(v) if v and v != 'nan' and v != '' else None
    except Exception:
        return None


def clean_float(val):
    try:
        v = float(str(val).strip())
        return round(v, 2) if v == v else None  # NaN check
    except Exception:
        return None


def clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ('nan', 'none', 'null', '') else None


def parse_tags(val):
    """Chuyển genres/tags string thành list."""
    if not val or str(val).lower() in ('nan', 'none', ''):
        return []
    raw = str(val).strip()
    # Xử lý format: "['fiction', 'romance']" hoặc "fiction,romance"
    if raw.startswith('['):
        import ast
        try:
            items = ast.literal_eval(raw)
            return [str(t).strip().lower() for t in items if t][:20]
        except Exception:
            pass
    return [t.strip().lower() for t in raw.split(',') if t.strip()][:20]


def generate_price(rating, pages):
    """Tạo giá sách giả lập dựa trên rating và số trang."""
    base = 8.99
    if rating and rating > 4.0:
        base += 3.0
    if pages and pages > 400:
        base += 2.0
    elif pages and pages > 600:
        base += 4.0
    import random
    random.seed(int(rating * 100 if rating else 0) + int(pages or 0))
    return round(base + random.uniform(-1.5, 2.5), 2)


def main():
    args = parse_args()

    import csv
    import codecs

    print(f"[Import] Doc file: {CSV_PATH.replace(chr(39), '')}"
          .encode('ascii', errors='replace').decode('ascii'))
    print(f"[Import] Limit: {args.limit} sach, Batch: {args.batch}, Offset: {args.offset}")

    if not os.path.exists(CSV_PATH):
        print(f"[LOI] Khong tim thay file: {CSV_PATH.encode('ascii', errors='replace').decode('ascii')}")
        sys.exit(1)

    conn = psycopg2.connect(AIVEN_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()

    # Đảm bảo extension pg_trgm
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        conn.commit()
    except Exception as e:
        print(f"[WARN] pg_trgm: {e}")
        conn.rollback()

    # Tạo bảng nếu chưa có
    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id              SERIAL PRIMARY KEY,
            goodreads_id    BIGINT UNIQUE,
            title           TEXT NOT NULL,
            author_name     TEXT NOT NULL DEFAULT '',
            description     TEXT,
            cover_url       TEXT,
            isbn            TEXT,
            isbn13          TEXT,
            published_year  INTEGER,
            pages           INTEGER,
            language        TEXT DEFAULT 'en',
            rating          NUMERIC(3,2) DEFAULT 0,
            ratings_count   INTEGER DEFAULT 0,
            publisher       TEXT,
            tags            TEXT[] DEFAULT '{}',
            trending_rank   INTEGER,
            price           NUMERIC(10,2) DEFAULT 0,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS book_categories (
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            category    TEXT NOT NULL,
            PRIMARY KEY (book_id, category)
        );
        CREATE INDEX IF NOT EXISTS idx_books_rating ON books(rating DESC);
        CREATE INDEX IF NOT EXISTS idx_books_ratings_count ON books(ratings_count DESC);
        CREATE INDEX IF NOT EXISTS idx_books_trending ON books(trending_rank ASC NULLS LAST);
    """)
    conn.commit()
    print("[Import] Schema da san sang.")

    # Doc CSV
    batch = []
    imported = 0
    skipped = 0
    start = time.time()

    with open(CSV_PATH, encoding='utf-8', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        print(f"[Import] Cot CSV: {reader.fieldnames}")

        for i, row in enumerate(reader):
            if i < args.offset:
                continue
            if imported >= args.limit:
                break

            title = clean_str(row.get('title') or row.get('Title') or row.get('book_title'))
            if not title:
                skipped += 1
                continue

            goodreads_id = clean_int(
                row.get('book_id') or row.get('goodreads_book_id') or row.get('id')
            )
            author = clean_str(
                row.get('author_name') or row.get('author') or row.get('authors') or 'Unknown'
            ) or 'Unknown'
            description = clean_str(
                row.get('description') or row.get('synopsis') or row.get('summary')
            )
            cover_url = clean_str(
                row.get('image_url') or row.get('cover_url') or row.get('thumbnail')
            )
            isbn = clean_str(row.get('isbn') or row.get('ISBN'))
            isbn13 = clean_str(row.get('isbn13') or row.get('ISBN13'))
            published_year = clean_int(
                row.get('original_publication_year') or row.get('published_year') or row.get('year')
            )
            pages = clean_int(row.get('num_pages') or row.get('pages') or row.get('num_page'))
            language = clean_str(row.get('language_code') or row.get('language')) or 'en'
            if language and len(language) > 10:
                language = 'en'
            rating = clean_float(
                row.get('average_rating') or row.get('rating') or row.get('avg_rating')
            )
            ratings_count = clean_int(
                row.get('ratings_count') or row.get('work_ratings_count') or row.get('num_ratings')
            )
            publisher = clean_str(row.get('publisher') or row.get('Publisher'))
            tags_raw = row.get('genres') or row.get('tags') or row.get('shelves') or row.get('popular_shelves') or ''
            tags = parse_tags(tags_raw)
            price = generate_price(rating, pages)

            batch.append((
                goodreads_id, title, author, description, cover_url,
                isbn, isbn13, published_year, pages, language,
                rating, ratings_count, publisher, tags, price
            ))

            if len(batch) >= args.batch:
                _flush(cur, conn, batch, imported)
                imported += len(batch)
                elapsed = time.time() - start
                print(f"  [{imported}/{args.limit}] Da import | {elapsed:.1f}s")
                batch = []

        # Flush batch cuối
        if batch and imported < args.limit:
            _flush(cur, conn, batch, imported)
            imported += len(batch)

    elapsed = time.time() - start
    print(f"\n[Import] HOAN TAT: {imported} sach | Bo qua: {skipped} | Thoi gian: {elapsed:.1f}s")
    cur.close()
    conn.close()


def _flush(cur, conn, batch, offset):
    """Insert batch vào Aiven, bỏ qua conflict."""
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO books (
            goodreads_id, title, author_name, description, cover_url,
            isbn, isbn13, published_year, pages, language,
            rating, ratings_count, publisher, tags, price
        )
        VALUES %s
        ON CONFLICT (goodreads_id) DO UPDATE SET
            title = EXCLUDED.title,
            author_name = EXCLUDED.author_name,
            description = COALESCE(EXCLUDED.description, books.description),
            cover_url = COALESCE(EXCLUDED.cover_url, books.cover_url),
            rating = COALESCE(EXCLUDED.rating, books.rating),
            ratings_count = COALESCE(EXCLUDED.ratings_count, books.ratings_count),
            tags = EXCLUDED.tags,
            price = EXCLUDED.price
        """,
        batch,
        template=None,
        page_size=200,
    )
    conn.commit()


if __name__ == "__main__":
    main()
