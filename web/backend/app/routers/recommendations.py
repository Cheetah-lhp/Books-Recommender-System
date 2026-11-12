import hashlib
import json
import time
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_optional_user
from app.core.redis_client import cache_get_json, cache_header, cache_set_json
from app.db.models import User
from app.db.session import get_db
from app.services.recommender import build_sections, recommend

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

_rate: dict[str, list[float]] = {}


class Answers(BaseModel):
    genres: list[str] = []
    themes: list[str] = []
    mood: Optional[str] = None
    frequency: Optional[str] = None
    length: Optional[str] = None
    favorite_books: list[str] = []
    categories: list[str] = []
    reading_mood: Optional[str] = None
    preferred_book_length: Optional[str] = None


def _rate_limit(key: str, limit: int) -> bool:
    now = time.time()
    window = _rate.setdefault(key, [])
    _rate[key] = [t for t in window if now - t < 60]
    if len(_rate[key]) >= limit:
        return False
    _rate[key].append(now)
    return True


def _cache_key(user_id: Optional[str], payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"rec:{user_id or 'anon'}:{digest}"


@router.get("")
def get_recommendations(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    userId: Optional[str] = None,
):
    client = request.client.host if request.client else "unknown"
    if not _rate_limit(f"rec:{client}", settings.RATE_LIMIT_RECOMMEND_PER_MIN):
        return {"books": []}

    uid = user.id if user else userId
    key = _cache_key(uid, {"mode": "get"})
    cached = cache_get_json(key)
    response.headers["X-Cache"] = cache_header(cached is not None)
    if cached is not None:
        return cached

    books = recommend(db if uid else None, user_id=uid, limit=12)
    payload = {"books": books}
    cache_set_json(key, payload, settings.RECOMMENDATION_CACHE_TTL_SECONDS)
    return payload


@router.post("")
def post_recommendations(
    body: Answers,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    client = request.client.host if request.client else "unknown"
    if not _rate_limit(f"rec:{client}", settings.RATE_LIMIT_RECOMMEND_PER_MIN):
        return {"books": []}

    answers = body.model_dump()
    key = _cache_key(user.id if user else None, answers)
    cached = cache_get_json(key)
    response.headers["X-Cache"] = cache_header(cached is not None)
    if cached is not None:
        return cached

    books = recommend(db, user_id=user.id if user else None, answers=answers, limit=12)
    payload = {"books": books}
    cache_set_json(key, payload, settings.RECOMMENDATION_CACHE_TTL_SECONDS)
    return payload


@router.get("/sections")
def get_sections(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    return {"sections": build_sections(db, user.id if user else None)}
