"""
BRS Python API — Book Recommender System Backend
Kết nối Aiven PostgreSQL, serve book data cho frontend React

Chạy: uvicorn main:app --reload --port 8000
"""

import os
import math
from contextlib import asynccontextmanager
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Tự động nạp biến môi trường từ .env
load_dotenv()
load_dotenv(Path(__file__).parent.parent / ".env")

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# === Kết nối PostgreSQL (Aiven Cloud) ===
DEFAULT_DB_URL = "postgres://avnadmin:YOUR_PASSWORD@database-recommender-system.f.aivencloud.com:21595/defaultdb?sslmode=require"
AIVEN_URL = (
    os.getenv("AIVEN_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or DEFAULT_DB_URL
)

def get_conn():
    """Tạo connection mới tới PostgreSQL."""
    return psycopg2.connect(AIVEN_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# === Khởi tạo schema khi startup ===
def init_db():
    """Kiểm tra và chuẩn bị bảng books."""
    with get_conn() as conn:
        with conn.cursor() as cur:
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
            """)
            conn.commit()
    print("[BRS API] Database connection verified.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        print(f"[BRS API] Startup warning: Could not connect to DB ({e}).")
    yield


app = FastAPI(
    title="Book Recommender System API",
    description="Backend API phục vụ dữ liệu sách từ Aiven PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — cho phép kết nối từ cả Cloud domain và localhost
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


# === Endpoints ===

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Book Recommender System Backend API",
        "version": "1.0.0",
        "database": "Aiven Cloud PostgreSQL (2,360,655 books)",
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
    category: Optional[str] = None,
    min_rating: Optional[float] = None,
    sort: str = Query("rating", enum=["rating", "ratings_count", "trending", "title", "published_year"]),
):
    """Danh sách sách có phân trang, tìm kiếm và lọc."""
    offset = (page - 1) * limit
    params = []
    where_clauses = []

    if q:
        where_clauses.append("(title ILIKE %s OR author_name ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if category:
        where_clauses.append(
            "id IN (SELECT book_id FROM book_categories WHERE category ILIKE %s)"
        )
        params.append(f"%{category}%")

    if min_rating is not None:
        where_clauses.append("rating >= %s")
        params.append(min_rating)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sort_map = {
        "rating": "rating DESC, ratings_count DESC",
        "ratings_count": "ratings_count DESC",
        "trending": "trending_rank ASC NULLS LAST, rating DESC",
        "title": "title ASC",
        "published_year": "published_year DESC NULLS LAST",
    }
    order_sql = sort_map.get(sort, "rating DESC")

    with get_conn() as conn:
        with conn.cursor() as cur:
            if not where_sql:
                cur.execute("SELECT COALESCE(reltuples::bigint, 1000000) AS count FROM pg_class WHERE relname = 'books'")
                total = cur.fetchone()["count"]
            else:
                cur.execute(f"SELECT COUNT(*) FROM books {where_sql}", params)
                total = cur.fetchone()["count"]

            cur.execute(
                f"""
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books {where_sql}
                ORDER BY {order_sql}
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = cur.fetchall()

    books = []
    for row in rows:
        b = dict(row)
        b["rating"] = float(b["rating"] or 0)
        b["price"] = float(b["price"] or 0)
        b["ratings_count"] = b["ratings_count"] or 0
        b["tags"] = b["tags"] or []
        books.append(Book(**b))

    return PaginatedBooks(
        data=books,
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit),
    )


@app.get("/api/books/trending", response_model=List[Book])
def trending_books(limit: int = Query(10, ge=1, le=50)):
    """Sách trending (có trending_rank hoặc ratings_count cao nhất)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                ORDER BY trending_rank ASC NULLS LAST, ratings_count DESC
                LIMIT %s
                """,
                [limit],
            )
            rows = cur.fetchall()
    return [Book(**{**dict(r), "rating": float(r["rating"] or 0), "price": float(r["price"] or 0), "ratings_count": r["ratings_count"] or 0, "tags": r["tags"] or []}) for r in rows]


@app.get("/api/books/top-rated", response_model=List[Book])
def top_rated_books(limit: int = Query(20, ge=1, le=100)):
    """Sách được đánh giá cao nhất."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                WHERE ratings_count >= 50
                ORDER BY rating DESC, ratings_count DESC
                LIMIT %s
                """,
                [limit],
            )
            rows = cur.fetchall()
    return [Book(**{**dict(r), "rating": float(r["rating"] or 0), "price": float(r["price"] or 0), "ratings_count": r["ratings_count"] or 0, "tags": r["tags"] or []}) for r in rows]


@app.get("/api/books/search", response_model=List[Book])
def search_books(q: str = Query(..., min_length=2), limit: int = Query(30, ge=1, le=100)):
    """Tìm kiếm sách theo tiêu đề hoặc tên tác giả."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                WHERE title ILIKE %s OR author_name ILIKE %s
                ORDER BY rating DESC, ratings_count DESC
                LIMIT %s
                """,
                [f"%{q}%", f"%{q}%", limit],
            )
            rows = cur.fetchall()
    return [Book(**{**dict(r), "rating": float(r["rating"] or 0), "price": float(r["price"] or 0), "ratings_count": r["ratings_count"] or 0, "tags": r["tags"] or []}) for r in rows]


class BatchBookRequest(BaseModel):
    ids: List[int]

@app.post("/api/books/batch", response_model=List[Book])
def get_books_batch(payload: BatchBookRequest):
    """Lấy danh sách nhiều sách theo IDs (phục vụ Giỏ hàng & Wishlist)."""
    if not payload.ids:
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books WHERE id = ANY(%s)
                """,
                [payload.ids],
            )
            rows = cur.fetchall()
    return [
        Book(**{
            **dict(r),
            "rating": float(r["rating"] or 0),
            "price": float(r["price"] or 0),
            "ratings_count": r["ratings_count"] or 0,
            "tags": r["tags"] or [],
        })
        for r in rows
    ]


@app.get("/api/books/{book_id}", response_model=Book)
def get_book(book_id: int):
    """Chi tiết một cuốn sách."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books WHERE id = %s
                """,
                [book_id],
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    r = dict(row)
    return Book(**{**r, "rating": float(r["rating"] or 0), "price": float(r["price"] or 0), "ratings_count": r["ratings_count"] or 0, "tags": r["tags"] or []})


@app.get("/api/categories")
def list_categories():
    """Danh sách tất cả categories có trong database."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT category, COUNT(*) as count
                FROM book_categories
                GROUP BY category
                ORDER BY count DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
    return [{"name": r["category"], "count": r["count"]} for r in rows]


@app.get("/api/stats")
def stats():
    """Thống kê tổng quan database."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM books")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) as total FROM book_categories")
            cat_total = cur.fetchone()["total"]
            cur.execute("SELECT AVG(rating) as avg_rating FROM books WHERE ratings_count > 0")
            avg_rating = cur.fetchone()["avg_rating"]
    return {
        "total_books": total,
        "total_category_tags": cat_total,
        "avg_rating": round(float(avg_rating or 0), 2),
    }
