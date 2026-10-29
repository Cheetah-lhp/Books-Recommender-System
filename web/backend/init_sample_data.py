"""
Kiem tra va nap du lieu mau tu samples_data vao co so du lieu (MySQL hoac SQLite).
Chi nap neu bang books chua co du lieu.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Nap bien moi truong
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
if DB_HOST == "mysql":
    DB_HOST = "127.0.0.1"
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Namle123456")
DB_NAME = "goodreads"
SQLITE_PATH = BASE_DIR / "books.db"


def get_db_connection():
    """Ket noi MySQL uu tien, fallback sang SQLite neu MySQL khong kha dung."""
    try:
        import pymysql
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            autocommit=True
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.select_db(DB_NAME)
        return "mysql", conn
    except Exception as e:
        import sqlite3
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        return "sqlite", conn


def init_schema(db_type, conn):
    """Khoi tao schema bang books va book_categories."""
    cur = conn.cursor()
    if db_type == "mysql":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INT AUTO_INCREMENT PRIMARY KEY,
                goodreads_id BIGINT UNIQUE,
                title VARCHAR(500) NOT NULL,
                author_name VARCHAR(255) NOT NULL DEFAULT '',
                description TEXT,
                cover_url TEXT,
                isbn VARCHAR(50),
                isbn13 VARCHAR(50),
                published_year INT,
                pages INT,
                language VARCHAR(50) DEFAULT 'en',
                rating DECIMAL(3,2) DEFAULT 0,
                ratings_count INT DEFAULT 0,
                publisher VARCHAR(255),
                tags TEXT,
                trending_rank INT,
                price DECIMAL(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_rating (rating),
                INDEX idx_trending (trending_rank),
                INDEX idx_ratings_count (ratings_count)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS book_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                book_id INT,
                category VARCHAR(100),
                INDEX idx_book (book_id),
                INDEX idx_cat (category)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goodreads_id BIGINT UNIQUE,
                title TEXT NOT NULL,
                author_name TEXT NOT NULL DEFAULT '',
                description TEXT,
                cover_url TEXT,
                isbn TEXT,
                isbn13 TEXT,
                published_year INTEGER,
                pages INTEGER,
                language TEXT DEFAULT 'en',
                rating REAL DEFAULT 0,
                ratings_count INTEGER DEFAULT 0,
                publisher TEXT,
                tags TEXT,
                trending_rank INTEGER,
                price REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS book_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER,
                category TEXT
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cat ON book_categories(category);")
    cur.close()


def check_existing_data(db_type, conn):
    """Kiem tra so luong sach hien co."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM books;")
        row = cur.fetchone()
        count = row[0] if isinstance(row, tuple) else row["COUNT(*)"]
        cur.close()
        return count
    except Exception:
        cur.close()
        return 0


def repair_genre_mappings(db_type, conn, sample_dir):
    """Repair the old exploded genre cross-product from read-only Parquet inputs.

    Only books.tags and book_categories are refreshed; source files and all other
    book/review fields are left untouched. This runs only when every book has
    every category, which identifies the known faulty import.
    """
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(DISTINCT goodreads_id) FROM books")
        row = cur.fetchone()
        book_count = row[0] if isinstance(row, tuple) else row["COUNT(DISTINCT goodreads_id)"]
        cur.execute("SELECT COUNT(DISTINCT category), COUNT(*) FROM book_categories")
        row = cur.fetchone()
        category_count, mapping_count = row if isinstance(row, tuple) else tuple(row)
        cur.execute("""
            SELECT COUNT(*), MIN(category_count), MAX(category_count)
            FROM (
                SELECT book_id, COUNT(DISTINCT category) AS category_count
                FROM book_categories GROUP BY book_id
            ) genre_counts
        """)
        row = cur.fetchone()
        mapped_book_count, min_per_book, max_per_book = row if isinstance(row, tuple) else tuple(row)
        if (
            not book_count
            or not category_count
            or mapping_count != book_count * category_count
            or mapped_book_count != book_count
            or min_per_book != category_count
            or max_per_book != category_count
        ):
            return False

        import pandas as pd

        genres_path = sample_dir / "genres"
        genre_columns = pd.read_parquet(genres_path, engine="pyarrow").columns
        genre_column = "genre" if "genre" in genre_columns else "genres"
        df_genres = pd.read_parquet(genres_path, columns=["book_id", genre_column, "votes"])
        df_genres = df_genres.rename(columns={genre_column: "genre"})
        votes = pd.to_numeric(df_genres["votes"], errors="coerce").fillna(0)
        df_genres = df_genres.loc[votes > 0, ["book_id", "genre"]].dropna()
        df_genres["genre"] = df_genres["genre"].astype(str).str.strip().str.lower()
        df_genres = df_genres[df_genres["genre"] != ""].drop_duplicates(["book_id", "genre"])
        tags_by_book = df_genres.groupby("book_id")["genre"].apply(list).to_dict()

        cur.execute("SELECT goodreads_id FROM books")
        book_ids = [int(row[0] if isinstance(row, tuple) else row["goodreads_id"]) for row in cur.fetchall()]
        book_id_set = set(book_ids)
        delete_sql = "DELETE FROM book_categories"
        update_sql = "UPDATE books SET tags = %s WHERE goodreads_id = %s" if db_type == "mysql" else "UPDATE books SET tags = ? WHERE goodreads_id = ?"
        insert_sql = "INSERT INTO book_categories (book_id, category) VALUES (%s, %s)" if db_type == "mysql" else "INSERT INTO book_categories (book_id, category) VALUES (?, ?)"

        conn.begin() if db_type == "mysql" else None
        cur.execute(delete_sql)
        updates = [(json.dumps(tags_by_book.get(book_id, [])), book_id) for book_id in book_ids]
        categories = [
            (int(book_id), tag)
            for book_id, tags in tags_by_book.items()
            for tag in tags
            if int(book_id) in book_id_set
        ]
        cur.executemany(update_sql, updates)
        if categories:
            cur.executemany(insert_sql, categories)
        conn.commit()
        print(f"[Init Data] Da sua mapping the loai: {len(categories)} the loai hop le cho {book_count} sach.")
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def import_samples():
    """Nap du lieu tu samples_data vao CSDL neu chua co."""
    db_type, conn = get_db_connection()
    init_schema(db_type, conn)

    current_count = check_existing_data(db_type, conn)
    if current_count > 0:
        sample_dir = PROJECT_DIR / "samples_data"
        repair_genre_mappings(db_type, conn, sample_dir)
        print(f"[Init Data] CSDL ({db_type.upper()}) da co san {current_count} cuon sach. Bo qua nap moi.")
        conn.close()
        return

    sample_dir = PROJECT_DIR / "samples_data"
    if not sample_dir.exists() or not (sample_dir / "books").exists():
        print(f"[Init Data] Canh bao: Khong tim thay thu muc samples_data tai {sample_dir}.")
        conn.close()
        return

    print(f"[Init Data] Dang doc va chuan hoa du lieu mau tu {sample_dir.name}...")
    import pandas as pd

    df_books = pd.read_parquet(sample_dir / "books")
    df_map = pd.read_parquet(sample_dir / "book_authors_map")

    # Lay tac gia
    author_ids = set(df_map["author_id"].astype(str))
    df_authors = pd.read_parquet(sample_dir / "authors", columns=["author_id", "name"])
    df_authors = df_authors[df_authors["author_id"].astype(str).isin(author_ids)]
    df_map = df_map.merge(df_authors, on="author_id", how="left")
    authors_by_book = df_map.groupby("book_id")["name"].apply(
        lambda names: ", ".join([str(n) for n in names if pd.notna(n)])
    ).to_dict()

    # Lay the loai
    df_genres = pd.read_parquet(sample_dir / "genres")
    if "genre" not in df_genres.columns and "genres" in df_genres.columns:
        df_genres = df_genres.rename(columns={"genres": "genre"})
    df_genres = df_genres[pd.to_numeric(df_genres["votes"], errors="coerce").fillna(0) > 0]
    tags_by_book = df_genres.groupby("book_id")["genre"].apply(
        lambda items: [str(g).strip().lower() for g in items if pd.notna(g) and str(g).strip()][:10]
    ).to_dict()

    # Sap xep tinh trending_rank
    df_books["ratings_count_num"] = pd.to_numeric(df_books["ratings_count"], errors="coerce").fillna(0).astype(int)
    df_books = df_books.sort_values(by="ratings_count_num", ascending=False).reset_index(drop=True)
    df_books["trending_rank"] = df_books.index + 1

    cur = conn.cursor()
    print(f"[Init Data] Dang chen {len(df_books)} sach vao CSDL {db_type.upper()}...")

    insert_book_sql = """
        INSERT INTO books (
            goodreads_id, title, author_name, description, cover_url,
            isbn, isbn13, published_year, pages, language,
            rating, ratings_count, publisher, tags, trending_rank, price
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """ if db_type == "mysql" else """
        INSERT INTO books (
            goodreads_id, title, author_name, description, cover_url,
            isbn, isbn13, published_year, pages, language,
            rating, ratings_count, publisher, tags, trending_rank, price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    insert_cat_sql = """
        INSERT INTO book_categories (book_id, category) VALUES (%s, %s)
    """ if db_type == "mysql" else """
        INSERT INTO book_categories (book_id, category) VALUES (?, ?)
    """

    book_rows = []
    cat_rows = []

    for idx, row in df_books.iterrows():
        b_id = int(row["book_id"])
        title = str(row["title"] or "Untitled")[:500]
        author = str(authors_by_book.get(b_id) or "Unknown Author")[:255]
        desc = str(row["description"] or "")
        cover = str(row["image_url"] or "")
        # Sua loi bi thay the nham boi regex PySpark
        cover = (
            cover.replace(".col/bookl/", ".com/books/")
            .replace(".col/assetl/", ".com/assets/")
            .replace("images.gr-assets.col/", "images.gr-assets.com/")
            .replace("s.gr-assets.col/", "s.gr-assets.com/")
        )
        isbn = str(row["isbn"] or "")[:50]
        isbn13 = str(row["isbn13"] or "")[:50]

        pub_year = None
        try:
            val = str(row["publication_year"]).strip()
            if val and val != "nan" and val != "":
                pub_year = int(float(val))
        except Exception:
            pass

        pages = None
        try:
            val = str(row["num_pages"]).strip()
            if val and val != "nan" and val != "":
                pages = int(float(val))
        except Exception:
            pass

        lang = str(row["language_code"] or "en")[:50]
        rating = 0.0
        try:
            rating = round(float(row["average_rating"]), 2)
        except Exception:
            pass

        r_count = int(row["ratings_count_num"])
        publisher = str(row["publisher"] or "")[:255]
        tags = tags_by_book.get(b_id, [])
        tags_json = json.dumps(tags)
        t_rank = int(row["trending_rank"])
        price = round(8.99 + (abs(hash(title)) % 1500) / 100.0, 2)

        book_rows.append((
            b_id, title, author, desc, cover,
            isbn, isbn13, pub_year, pages, lang,
            rating, r_count, publisher, tags_json, t_rank, price
        ))

        for cat in tags:
            cat_rows.append((b_id, cat))

    # Chen batch books
    batch_size = 500
    for i in range(0, len(book_rows), batch_size):
        cur.executemany(insert_book_sql, book_rows[i:i + batch_size])

    # Chen batch categories
    for i in range(0, len(cat_rows), batch_size):
        cur.executemany(insert_cat_sql, cat_rows[i:i + batch_size])

    if db_type == "sqlite":
        conn.commit()

    cur.close()
    conn.close()
    print(f"[Init Data] Hoan tat nap {len(book_rows)} sach va {len(cat_rows)} the loai vao {db_type.upper()}.")


def import_sample_reviews():
    """Add the sample review text to its own table; never rewrite Parquet inputs."""
    sample_dir = PROJECT_DIR / "samples_data"
    reviews_dir = sample_dir / "reviews"
    if not reviews_dir.exists():
        print(f"[Init Data] Khong tim thay review samples tai {reviews_dir}.")
        return

    import pandas as pd
    import pyarrow.parquet as pq

    parquet_files = sorted(reviews_dir.glob("*.parquet"))
    expected_count = sum(pq.ParquetFile(path).metadata.num_rows for path in parquet_files)
    db_type, conn = get_db_connection()
    cur = conn.cursor()
    try:
        if db_type == "mysql":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sample_reviews (
                    review_id VARCHAR(128) PRIMARY KEY,
                    book_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    rating TINYINT NOT NULL,
                    review_text LONGTEXT,
                    date_added VARCHAR(64),
                    INDEX idx_sample_reviews_book_date (book_id, date_added)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sample_reviews (
                    review_id TEXT PRIMARY KEY,
                    book_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL,
                    review_text TEXT,
                    date_added TEXT
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_sample_reviews_book_date
                ON sample_reviews (book_id, date_added);
            """)

        cur.execute("SELECT COUNT(*) FROM sample_reviews")
        row = cur.fetchone()
        existing_count = row[0] if isinstance(row, tuple) else row["COUNT(*)"]
        if existing_count >= expected_count:
            print(f"[Init Data] Da co du {existing_count} review mau trong {db_type.upper()}.")
            return

        df_reviews = pd.read_parquet(
            reviews_dir,
            columns=["review_id", "book_id", "user_id", "rating", "review_text", "date_added"],
        )
        insert_sql = """
            INSERT IGNORE INTO sample_reviews
                (review_id, book_id, user_id, rating, review_text, date_added)
            VALUES (%s, %s, %s, %s, %s, %s)
        """ if db_type == "mysql" else """
            INSERT OR IGNORE INTO sample_reviews
                (review_id, book_id, user_id, rating, review_text, date_added)
            VALUES (?, ?, ?, ?, ?, ?)
        """

        batch_size = 1000
        inserted_candidates = 0
        for start in range(0, len(df_reviews), batch_size):
            batch = df_reviews.iloc[start : start + batch_size]
            records = []
            for review_id, book_id, user_id, rating, review_text, date_added in batch.itertuples(index=False, name=None):
                records.append((
                    str(review_id),
                    int(book_id),
                    int(user_id),
                    int(rating),
                    None if pd.isna(review_text) else str(review_text),
                    None if pd.isna(date_added) else str(date_added),
                ))
            cur.executemany(insert_sql, records)
            inserted_candidates += len(records)

        if db_type == "sqlite":
            conn.commit()
        print(f"[Init Data] Da nap {inserted_candidates} review mau (bo qua ID trung) vao {db_type.upper()}.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import_samples()
    import_sample_reviews()

