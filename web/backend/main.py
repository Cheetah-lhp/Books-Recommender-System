"""
BRS Python API — Book Recommender System Backend
Phục vụ dữ liệu sách từ MySQL (hoặc SQLite fallback / Aiven PostgreSQL) cho frontend React.
"""

import os
import math
import json
import queue
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Literal
from pathlib import Path
from dotenv import load_dotenv

# Nap bien moi truong
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")

import pymysql
import pymysql.cursors
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
if DB_HOST == "mysql":
    DB_HOST = "127.0.0.1"
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Namle123456")
DB_NAME = "goodreads"
SQLITE_PATH = BASE_DIR / "books.db"
MYSQL_POOL_SIZE = max(1, int(os.getenv("MYSQL_POOL_SIZE", "10")))
MYSQL_POOL_TIMEOUT_SECONDS = max(1, int(os.getenv("MYSQL_POOL_TIMEOUT_SECONDS", "5")))
TRENDING_CACHE_TTL_SECONDS = max(0, int(os.getenv("TRENDING_CACHE_TTL_SECONDS", "60")))

_mysql_pool: queue.LifoQueue = queue.LifoQueue(maxsize=MYSQL_POOL_SIZE)
_mysql_pool_slots = threading.BoundedSemaphore(MYSQL_POOL_SIZE)
_trending_cache_lock = threading.Lock()
_trending_cache: dict[int, tuple[float, list["Book"]]] = {}


class PooledConnection:
    """Return a MySQL connection to the process pool when callers close it."""

    def __init__(self, connection):
        self._connection = connection
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        if self._returned:
            return
        self._returned = True
        try:
            if self._connection.open:
                _mysql_pool.put(self._connection)
            else:
                self._connection.close()
        finally:
            _mysql_pool_slots.release()


def _connect_mysql():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=MYSQL_POOL_TIMEOUT_SECONDS,
    )


def _get_pooled_mysql_connection():
    if not _mysql_pool_slots.acquire(timeout=MYSQL_POOL_TIMEOUT_SECONDS):
        raise TimeoutError("Timed out waiting for a MySQL connection")

    try:
        try:
            connection = _mysql_pool.get_nowait()
        except queue.Empty:
            connection = _connect_mysql()
        else:
            try:
                connection.ping(reconnect=True)
            except Exception:
                connection.close()
                connection = _connect_mysql()
        return PooledConnection(connection)
    except Exception:
        _mysql_pool_slots.release()
        raise


def get_conn():
    """Ket noi MySQL uu tien, fallback sang SQLite neu MySQL khong kha dung."""
    try:
        return "mysql", _get_pooled_mysql_connection()
    except TimeoutError as error:
        raise HTTPException(status_code=503, detail="Database connection pool is busy") from error
    except Exception:
        import sqlite3
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        return "sqlite", conn


def format_book(row) -> dict:
    """Chuan hoa du lieu sach tra ve cho Pydantic Model."""
    b = dict(row)
    b["rating"] = float(b.get("rating") or 0)
    b["price"] = float(b.get("price") or 0)
    b["ratings_count"] = int(b.get("ratings_count") or 0)
    tags_raw = b.get("tags")
    if isinstance(tags_raw, str):
        try:
            b["tags"] = json.loads(tags_raw)
        except Exception:
            b["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        b["tags"] = tags_raw
    else:
        b["tags"] = []
    return b


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kiem tra ket noi khi khoi dong
    try:
        db_type, conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM books;")
            res = cur.fetchone()
            count = res["total"] if isinstance(res, dict) else res[0]
            print(f"[BRS API] Ket noi {db_type.upper()} thanh cong. Tong so sach: {count}")
        conn.close()
    except Exception as e:
        print(f"[BRS API] Canh bao ket noi CSDL: {e}")
    yield
    while True:
        try:
            _mysql_pool.get_nowait().close()
        except queue.Empty:
            break


app = FastAPI(
    title="Book Recommender System API",
    description="Backend API phuc vu du lieu sach cho frontend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Pydantic Models ===
class Book(BaseModel):
    id: int
    goodreads_id: Optional[int] = None
    title: str
    author_name: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    isbn: Optional[str] = None
    isbn13: Optional[str] = None
    published_year: Optional[int] = None
    pages: Optional[int] = None
    language: str = "en"
    rating: float = 0
    ratings_count: int = 0
    publisher: Optional[str] = None
    tags: List[str] = []
    trending_rank: Optional[int] = None
    price: float = 0


class PaginatedBooks(BaseModel):
    data: List[Book]
    total: int
    page: int
    limit: int
    pages: int


class SampleReview(BaseModel):
    review_id: str
    user_id: int
    rating: int
    review_text: Optional[str] = None
    date_added: Optional[str] = None


# === Endpoints ===

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Book Recommender System Backend API",
        "version": "1.0.0",
        "database": f"MySQL / SQLite ({DB_NAME})",
        "docs_url": "/docs",
        "endpoints": {
            "health": "/health",
            "books": "/api/books?limit=10",
            "trending": "/api/books/trending?limit=10",
            "top_rated": "/api/books/top-rated?limit=10",
            "search": "/api/books/search?q=Harry%20Potter",
            "categories": "/api/categories"
        }
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "Book Recommender System API"}


@app.get("/api/books", response_model=PaginatedBooks)
def list_books(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    category: Optional[List[str]] = Query(default=None),
    min_rating: Optional[float] = None,
    sort: Literal["rating", "ratings_count", "trending", "title", "published_year"] = "rating",
):
    """Danh sach sach co phan trang, tim kiem va loc the loai."""
    offset = (page - 1) * limit
    params = []
    where_clauses = []

    if q:
        where_clauses.append("(title LIKE %s OR author_name LIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if category:
        category_matches = []
        for term in category:
            normalized_term = term.strip().lower().replace(" ", "%").replace("-", "%")
            if normalized_term:
                category_matches.append("LOWER(category) LIKE %s")
                params.append(f"%{normalized_term}%")
        if category_matches:
            where_clauses.append(
                "goodreads_id IN (SELECT book_id FROM book_categories WHERE "
                + " OR ".join(category_matches)
                + ")"
            )

    if min_rating is not None:
        where_clauses.append("rating >= %s")
        params.append(min_rating)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sort_map = {
        "rating": "rating DESC, ratings_count DESC",
        "ratings_count": "ratings_count DESC",
        "trending": "trending_rank IS NULL, trending_rank ASC, rating DESC",
        "title": "title ASC",
        "published_year": "published_year IS NULL, published_year DESC",
    }
    order_sql = sort_map.get(sort, "rating DESC")

    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            count_sql = f"SELECT COUNT(*) AS total FROM books {where_sql}"
            if db_type == "sqlite":
                count_sql = count_sql.replace("%s", "?")
            cur.execute(count_sql, params)
            res = cur.fetchone()
            total = res["total"] if isinstance(res, dict) else res[0]

            query_sql = f"""
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books {where_sql}
                ORDER BY {order_sql}
                LIMIT %s OFFSET %s
            """
            all_params = params + [limit, offset]
            if db_type == "sqlite":
                query_sql = query_sql.replace("%s", "?")
            cur.execute(query_sql, all_params)
            rows = cur.fetchall()
    finally:
        conn.close()

    books = [Book(**format_book(r)) for r in rows]
    return PaginatedBooks(
        data=books,
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total > 0 else 1,
    )


@app.get("/api/books/trending", response_model=List[Book])
def trending_books(response: Response, limit: int = Query(10, ge=1, le=50)):
    """Sach trending (theo trending_rank hoac ratings_count cao nhat)."""
    cache_control_ttl = min(TRENDING_CACHE_TTL_SECONDS, 60)
    if cache_control_ttl:
        response.headers["Cache-Control"] = (
            f"public, max-age={cache_control_ttl}, s-maxage={cache_control_ttl}, "
            "stale-while-revalidate=300"
        )
    else:
        response.headers["Cache-Control"] = "no-store"

    with _trending_cache_lock:
        now = time.monotonic()
        cached = _trending_cache.get(limit)
        if cached and TRENDING_CACHE_TTL_SECONDS and now - cached[0] < TRENDING_CACHE_TTL_SECONDS:
            return cached[1]

        db_type, conn = get_conn()
        try:
            with conn.cursor() as cur:
                sql = """
                    SELECT id, goodreads_id, title, author_name, description, cover_url,
                           isbn, isbn13, published_year, pages, language, rating,
                           ratings_count, publisher, tags, trending_rank, price
                    FROM books
                    ORDER BY trending_rank IS NULL, trending_rank ASC, ratings_count DESC
                    LIMIT %s
                """
                if db_type == "sqlite":
                    sql = sql.replace("%s", "?")
                cur.execute(sql, [limit])
                rows = cur.fetchall()
        finally:
            conn.close()

        books = [Book(**format_book(r)) for r in rows]
        _trending_cache[limit] = (time.monotonic(), books)
        return books


@app.get("/api/books/top-rated", response_model=List[Book])
def top_rated_books(limit: int = Query(20, ge=1, le=100)):
    """Sach duoc danh gia cao nhat."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                WHERE ratings_count >= 50
                ORDER BY rating DESC, ratings_count DESC
                LIMIT %s
            """
            if db_type == "sqlite":
                sql = sql.replace("%s", "?")
            cur.execute(sql, [limit])
            rows = cur.fetchall()
    finally:
        conn.close()
    return [Book(**format_book(r)) for r in rows]


@app.get("/api/books/search", response_model=List[Book])
def search_books(q: str = Query(..., min_length=2), limit: int = Query(30, ge=1, le=100)):
    """Tim kiem sach theo tieu de hoac tac gia."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                WHERE title LIKE %s OR author_name LIKE %s
                ORDER BY rating DESC, ratings_count DESC
                LIMIT %s
            """
            params = [f"%{q}%", f"%{q}%", limit]
            if db_type == "sqlite":
                sql = sql.replace("%s", "?")
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    return [Book(**format_book(r)) for r in rows]


class BatchBookRequest(BaseModel):
    ids: List[int]


@app.post("/api/books/batch", response_model=List[Book])
def get_books_batch(payload: BatchBookRequest):
    """Lay danh sach sach theo IDs (phuc vu Gio hang & Wishlist)."""
    if not payload.ids:
        return []
    placeholders = ", ".join(["%s"] * len(payload.ids))
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = f"""
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books WHERE id IN ({placeholders})
            """
            if db_type == "sqlite":
                sql = sql.replace("%s", "?")
            cur.execute(sql, payload.ids)
            rows = cur.fetchall()
    finally:
        conn.close()
    return [Book(**format_book(r)) for r in rows]


@app.get("/api/books/{book_id}", response_model=Book)
def get_book(book_id: int):
    """Chi tiet mot cuon sach."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                WHERE id = %s OR goodreads_id = %s
                ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END
                LIMIT 1
            """
            params = [book_id, book_id, book_id]
            if db_type == "sqlite":
                sql = sql.replace("%s", "?")
            cur.execute(sql, params)
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return Book(**format_book(row))


@app.get("/api/books/{book_id}/similar", response_model=List[Book])
def similar_books(
    book_id: int,
    limit: int = Query(8, ge=1, le=24),
    preferred_tags: List[str] = Query(default=[]),
):
    """Rank other books by overlap with this book's tags and saved genres."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            target_sql = """
                SELECT id, goodreads_id, author_name, language
                FROM books
                WHERE id = %s OR goodreads_id = %s
                ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END
                LIMIT 1
            """
            if db_type == "sqlite":
                target_sql = target_sql.replace("%s", "?")
            cur.execute(target_sql, [book_id, book_id, book_id])
            target = cur.fetchone()
            if not target:
                raise HTTPException(status_code=404, detail="Book not found")

            tags_sql = "SELECT category FROM book_categories WHERE book_id = %s"
            if db_type == "sqlite":
                tags_sql = tags_sql.replace("%s", "?")
            cur.execute(tags_sql, [target["goodreads_id"]])
            book_tags = [row["category"] for row in cur.fetchall()]
            def normalize_tag(tag: str) -> str:
                return tag.strip().lower().replace(" ", "-").replace("_", "-")

            book_tag_terms = list(dict.fromkeys(
                normalize_tag(tag) for tag in book_tags if tag and tag.strip()
            ))
            preferred_tag_terms = list(dict.fromkeys(
                normalize_tag(tag) for tag in preferred_tags[:20] if tag and tag.strip()
            ))
            normalized_tags = list(dict.fromkeys([*book_tag_terms, *preferred_tag_terms]))

            if normalized_tags:
                placeholders = ", ".join(["%s"] * len(normalized_tags))
                score_parts = []
                score_params = []
                if book_tag_terms:
                    book_tag_placeholders = ", ".join(["%s"] * len(book_tag_terms))
                    score_parts.append(
                        f"2 * (SELECT COUNT(DISTINCT c.category) FROM book_categories c "
                        f"WHERE c.book_id = b.goodreads_id "
                        f"AND LOWER(REPLACE(c.category, ' ', '-')) IN ({book_tag_placeholders}))"
                    )
                    score_params.extend(book_tag_terms)
                if preferred_tag_terms:
                    preferred_placeholders = ", ".join(["%s"] * len(preferred_tag_terms))
                    score_parts.append(
                        f"(SELECT COUNT(DISTINCT c.category) FROM book_categories c "
                        f"WHERE c.book_id = b.goodreads_id "
                        f"AND LOWER(REPLACE(c.category, ' ', '-')) IN ({preferred_placeholders}))"
                    )
                    score_params.extend(preferred_tag_terms)
                match_score = " + ".join(score_parts) or "0"
                sql = f"""
                    SELECT b.id, b.goodreads_id, b.title, b.author_name, b.description,
                           b.cover_url, b.isbn, b.isbn13, b.published_year, b.pages,
                           b.language, b.rating, b.ratings_count, b.publisher, b.tags,
                           b.trending_rank, b.price,
                           ({match_score}) AS matched_tag_score
                    FROM books b
                    WHERE b.id <> %s
                      AND EXISTS (
                          SELECT 1 FROM book_categories c
                          WHERE c.book_id = b.goodreads_id
                            AND LOWER(REPLACE(c.category, ' ', '-')) IN ({placeholders})
                      )
                    ORDER BY matched_tag_score DESC, b.rating DESC, b.ratings_count DESC
                    LIMIT %s
                """
                if db_type == "sqlite":
                    sql = sql.replace("%s", "?")
                cur.execute(sql, [*score_params, target["id"], *normalized_tags, limit])
            else:
                sql = """
                    SELECT id, goodreads_id, title, author_name, description, cover_url,
                           isbn, isbn13, published_year, pages, language, rating,
                           ratings_count, publisher, tags, trending_rank, price
                    FROM books
                    WHERE id <> %s AND (author_name = %s OR language = %s)
                    ORDER BY CASE WHEN author_name = %s THEN 0 ELSE 1 END,
                             rating DESC, ratings_count DESC
                    LIMIT %s
                """
                if db_type == "sqlite":
                    sql = sql.replace("%s", "?")
                cur.execute(sql, [target["id"], target["author_name"], target["language"], target["author_name"], limit])
            rows = cur.fetchall()
    finally:
        conn.close()
    return [Book(**format_book(row)) for row in rows]


@app.get("/api/books/{book_id}/sample-reviews", response_model=List[SampleReview])
def sample_reviews(book_id: int, limit: int = Query(12, ge=1, le=50)):
    """Read imported sample reviews; the Parquet source data stays unchanged."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            target_sql = """
                SELECT goodreads_id FROM books
                WHERE id = %s OR goodreads_id = %s
                ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END
                LIMIT 1
            """
            if db_type == "sqlite":
                target_sql = target_sql.replace("%s", "?")
            cur.execute(target_sql, [book_id, book_id, book_id])
            target = cur.fetchone()
            if not target:
                raise HTTPException(status_code=404, detail="Book not found")

            reviews_sql = """
                SELECT review_id, user_id, rating, review_text, date_added
                FROM sample_reviews
                WHERE book_id = %s
                ORDER BY date_added DESC
                LIMIT %s
            """
            if db_type == "sqlite":
                reviews_sql = reviews_sql.replace("%s", "?")
            cur.execute(reviews_sql, [target["goodreads_id"], limit])
            rows = cur.fetchall()
    finally:
        conn.close()
    return [SampleReview(**dict(row)) for row in rows]


@app.get("/api/categories")
def list_categories():
    """Danh sach categories co trong CSDL."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT category, COUNT(*) AS count
                FROM book_categories
                GROUP BY category
                ORDER BY count DESC
                LIMIT 50;
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    return [{"name": r["category"], "count": r["count"]} for r in rows]


@app.get("/api/stats")
def stats():
    """Thong ke tong quan CSDL."""
    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM books;")
            r1 = cur.fetchone()
            total = r1["total"] if isinstance(r1, dict) else r1[0]

            cur.execute("SELECT COUNT(*) AS total FROM book_categories;")
            r2 = cur.fetchone()
            cat_total = r2["total"] if isinstance(r2, dict) else r2[0]

            cur.execute("SELECT AVG(rating) AS avg_rating FROM books WHERE ratings_count > 0;")
            r3 = cur.fetchone()
            avg_rating = r3["avg_rating"] if isinstance(r3, dict) else r3[0]
    finally:
        conn.close()
    return {
        "total_books": total,
        "total_category_tags": cat_total,
        "avg_rating": round(float(avg_rating or 0), 2),
    }
