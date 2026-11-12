import math
from typing import Optional, List, Literal
from fastapi import APIRouter, Query, HTTPException, Response

from app.core.database import get_conn
from app.core.config import settings
from app.schemas.book import Book, PaginatedBooks, SampleReview, BatchBookRequest
from app.services.book_service import format_book, get_cached_trending, set_cached_trending
import app.repositories.book_repo as repo

router = APIRouter(prefix="/api/books", tags=["books"])

@router.get("", response_model=PaginatedBooks)
def list_books(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    category: Optional[List[str]] = Query(default=None),
    min_rating: Optional[float] = None,
    sort: Literal["rating", "ratings_count", "trending", "title", "published_year"] = "rating",
):
    # Lay danh sach sach co phan trang va bo loc
    offset = (page - 1) * limit
    db_type, conn = get_conn()
    try:
        total, rows = repo.get_books_paginated(
            conn, db_type, limit, offset, q, category, min_rating, sort
        )
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

@router.get("/trending", response_model=List[Book])
def trending_books(response: Response, limit: int = Query(10, ge=1, le=50)):
    # Danh sach sach dang thinh hanh
    cache_control_ttl = min(settings.TRENDING_CACHE_TTL_SECONDS, 60)
    if cache_control_ttl:
        response.headers["Cache-Control"] = (
            f"public, max-age={cache_control_ttl}, s-maxage={cache_control_ttl}, "
            "stale-while-revalidate=300"
        )
    else:
        response.headers["Cache-Control"] = "no-store"

    cached = get_cached_trending(limit)
    if cached is not None:
        return cached

    db_type, conn = get_conn()
    try:
        rows = repo.get_trending_books(conn, db_type, limit)
    finally:
        conn.close()

    books = [Book(**format_book(r)) for r in rows]
    set_cached_trending(limit, books)
    return books

@router.get("/top-rated", response_model=List[Book])
def top_rated_books(limit: int = Query(20, ge=1, le=100)):
    # Danh sach sach co diem danh gia cao
    db_type, conn = get_conn()
    try:
        rows = repo.get_top_rated_books(conn, db_type, limit)
    finally:
        conn.close()
    return [Book(**format_book(r)) for r in rows]

@router.get("/search", response_model=List[Book])
def search_books(q: str = Query(..., min_length=2), limit: int = Query(30, ge=1, le=100)):
    # Tim kiem sach theo tieu de hoac tac gia
    db_type, conn = get_conn()
    try:
        rows = repo.search_books(conn, db_type, q, limit)
    finally:
        conn.close()
    return [Book(**format_book(r)) for r in rows]

@router.post("/batch", response_model=List[Book])
def get_books_batch(payload: BatchBookRequest):
    # Lay thong tin nhieu sach theo danh sach ID
    if not payload.ids:
        return []
    db_type, conn = get_conn()
    try:
        rows = repo.get_books_batch(conn, db_type, payload.ids)
    finally:
        conn.close()
    return [Book(**format_book(r)) for r in rows]

@router.get("/{book_id}", response_model=Book)
def get_book(book_id: int):
    # Chi tiet mot cuon sach
    db_type, conn = get_conn()
    try:
        row = repo.get_book_by_id(conn, db_type, book_id)
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    return Book(**format_book(row))

@router.get("/{book_id}/similar", response_model=List[Book])
def similar_books(
    book_id: int,
    limit: int = Query(8, ge=1, le=24),
    preferred_tags: List[str] = Query(default=[]),
):
    # Uu tien bang book_similarity (offline job); fallback heuristic the loai/tag
    db_type, conn = get_conn()
    try:
        target = repo.get_book_by_id(conn, db_type, book_id)
        if not target:
            raise HTTPException(status_code=404, detail="Book not found")

        precomputed = []
        try:
            with conn.cursor() as cur:
                sql = (
                    "SELECT similar_book_id FROM book_similarity "
                    "WHERE book_id = %s ORDER BY score DESC LIMIT %s"
                    if db_type == "mysql"
                    else "SELECT similar_book_id FROM book_similarity WHERE book_id = ? ORDER BY score DESC LIMIT ?"
                )
                cur.execute(sql, (book_id, limit))
                precomputed = [r["similar_book_id"] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
        except Exception:
            precomputed = []

        if precomputed:
            rows = repo.get_books_batch(conn, db_type, precomputed)
            return [Book(**format_book(row)) for row in rows]

        book_tags = repo.get_target_book_categories(conn, db_type, target["goodreads_id"])
        def normalize_tag(tag: str) -> str:
            return tag.strip().lower().replace(" ", "-").replace("_", "-")

        book_tag_terms = list(dict.fromkeys(
            normalize_tag(tag) for tag in book_tags if tag and tag.strip()
        ))
        preferred_tag_terms = list(dict.fromkeys(
            normalize_tag(tag) for tag in preferred_tags[:20] if tag and tag.strip()
        ))
        normalized_tags = list(dict.fromkeys([*book_tag_terms, *preferred_tag_terms]))

        rows = repo.get_similar_books(
            conn=conn,
            db_type=db_type,
            target_id=target["id"],
            author_name=target["author_name"],
            language=target["language"],
            book_tag_terms=book_tag_terms,
            preferred_tag_terms=preferred_tag_terms,
            normalized_tags=normalized_tags,
            limit=limit,
        )
    finally:
        conn.close()

    return [Book(**format_book(row)) for row in rows]

@router.get("/{book_id}/sample-reviews", response_model=List[SampleReview])
def sample_reviews(book_id: int, limit: int = Query(12, ge=1, le=50)):
    # Lay danh sach danh gia mau cua sach
    db_type, conn = get_conn()
    try:
        target = repo.get_book_by_id(conn, db_type, book_id)
        if not target:
            raise HTTPException(status_code=404, detail="Book not found")
        rows = repo.get_sample_reviews(conn, db_type, target["goodreads_id"], limit)
    finally:
        conn.close()
    return [SampleReview(**dict(row)) for row in rows]

