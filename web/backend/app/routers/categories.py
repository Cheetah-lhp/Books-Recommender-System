from typing import List
from fastapi import APIRouter, Response

from app.core.config import settings
from app.core.database import get_conn
from app.core.redis_client import cache_get_json, cache_header, cache_set_json
from app.schemas.book import CategoryItem
import app.repositories.book_repo as repo

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("", response_model=List[CategoryItem])
def list_categories(response: Response):
    # Danh sach cac the loai pho bien kem so luong sach
    cached = cache_get_json("categories:summary")
    response.headers["X-Cache"] = cache_header(cached is not None)
    if cached is not None:
        return [CategoryItem(**item) for item in cached]

    db_type, conn = get_conn()
    try:
        rows = repo.get_categories_summary(conn, db_type, limit=50)
    finally:
        conn.close()
    items = [CategoryItem(name=r["category"], count=r["count"]) for r in rows]
    cache_set_json(
        "categories:summary",
        [i.model_dump() for i in items],
        settings.CATEGORIES_CACHE_TTL_SECONDS,
    )
    return items

