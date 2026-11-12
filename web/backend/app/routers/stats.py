from fastapi import APIRouter, Response
from app.core.database import get_conn
from app.core.config import settings
from app.core.redis_client import cache_get_json, cache_header, cache_set_json
from app.schemas.book import StatsResponse
import app.repositories.book_repo as repo

router = APIRouter(tags=["system"])

@router.get("/")
def root():
    # Thong tin chung ve API
    return {
        "status": "online",
        "service": "Book Recommender System Backend API",
        "version": "1.1.0",
        "database": f"MySQL / SQLite ({settings.DB_NAME})",
        "docs_url": "/docs",
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "books": "/api/books?limit=10",
            "trending": "/api/books/trending?limit=10",
            "top_rated": "/api/books/top-rated?limit=10",
            "search": "/api/books/search?q=Harry%20Potter",
            "categories": "/api/categories",
            "stats": "/api/stats",
            "recommendations": "/api/recommendations",
            "auth": "/api/auth/login",
        },
    }

@router.get("/health")
def health():
    # Kiem tra trang thai hoat dong (liveness)
    return {"status": "ok", "service": "Book Recommender System API"}

@router.get("/api/stats", response_model=StatsResponse)
def stats(response: Response):
    # Thong ke tong quan ve he thong
    cached = cache_get_json("stats:overview")
    response.headers["X-Cache"] = cache_header(cached is not None)
    if cached is not None:
        return StatsResponse(**cached)

    db_type, conn = get_conn()
    try:
        data = repo.get_database_stats(conn, db_type)
    finally:
        conn.close()
    cache_set_json("stats:overview", data, settings.STATS_CACHE_TTL_SECONDS)
    return StatsResponse(**data)

