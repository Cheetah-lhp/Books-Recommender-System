import json
import threading
import time
from typing import Optional, List
from app.schemas.book import Book
from app.core.config import settings

_trending_cache_lock = threading.Lock()
_trending_cache: dict[int, tuple[float, list[Book]]] = {}

def format_book(row) -> dict:
    # Chuan hoa record tu CSDL thanh dict cho Pydantic
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

def get_cached_trending(limit: int) -> Optional[List[Book]]:
    # Lay danh sach trending tu bo nho tam neu con han
    if settings.TRENDING_CACHE_TTL_SECONDS <= 0:
        return None
    with _trending_cache_lock:
        now = time.monotonic()
        cached = _trending_cache.get(limit)
        if cached and (now - cached[0] < settings.TRENDING_CACHE_TTL_SECONDS):
            return cached[1]
    return None

def set_cached_trending(limit: int, books: List[Book]) -> None:
    # Luu danh sach trending vao bo nho tam
    with _trending_cache_lock:
        _trending_cache[limit] = (time.monotonic(), books)

