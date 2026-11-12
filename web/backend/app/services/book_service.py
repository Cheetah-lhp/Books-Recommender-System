import json
import threading
import time
from typing import Optional, List
from app.schemas.book import Book
from app.core.config import settings
from app.core.redis_client import cache_get_json, cache_set_json

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
    # Redis first, then in-process memory
    if settings.TRENDING_CACHE_TTL_SECONDS <= 0:
        return None
    redis_hit = cache_get_json(f"trending:{limit}")
    if redis_hit is not None:
        return [Book(**item) for item in redis_hit]
    with _trending_cache_lock:
        now = time.monotonic()
        cached = _trending_cache.get(limit)
        if cached and (now - cached[0] < settings.TRENDING_CACHE_TTL_SECONDS):
            return cached[1]
    return None

def set_cached_trending(limit: int, books: List[Book]) -> None:
    payload = [b.model_dump() for b in books]
    cache_set_json(f"trending:{limit}", payload, settings.TRENDING_CACHE_TTL_SECONDS)
    with _trending_cache_lock:
        _trending_cache[limit] = (time.monotonic(), books)

