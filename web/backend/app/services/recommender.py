"""Hybrid recommender adapter: signals from MySQL, ranking from demo-ete models."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.database import get_conn
from app.db.models import (
    NotInterestedBook,
    RecommendationFeedback,
    RecommendationProfile,
    Review,
    UserBook,
)
from app.services import ml_client
from app.services.book_service import format_book
import app.repositories.book_repo as repo

logger = logging.getLogger(__name__)


@dataclass
class Signals:
    genres: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    mood: Optional[str] = None
    frequency: Optional[str] = None
    length: Optional[str] = None
    favorite_book_ids: list[str] = field(default_factory=list)
    shelves: list[dict[str, str]] = field(default_factory=list)
    ratings: list[dict[str, Any]] = field(default_factory=list)
    positive_book_ids: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)
    disliked_book_ids: list[str] = field(default_factory=list)
    liked_book_ids: list[str] = field(default_factory=list)


def _parse_tags(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def collect_signals(db: Session, user_id: str) -> Signals:
    profile = db.get(RecommendationProfile, user_id)
    shelves = db.query(UserBook).filter(UserBook.user_id == user_id).all()
    reviews = db.query(Review).filter(Review.user_id == user_id).all()
    hidden = db.query(NotInterestedBook).filter(NotInterestedBook.user_id == user_id).all()
    feedback = db.query(RecommendationFeedback).filter(RecommendationFeedback.user_id == user_id).all()

    positive = [str(r.book_id) for r in reviews if (r.rating or 0) >= 4]
    return Signals(
        genres=list(profile.genres or []) if profile else [],
        themes=list(profile.themes or []) if profile else [],
        mood=profile.reading_mood if profile else None,
        frequency=profile.reading_frequency if profile else None,
        length=profile.preferred_book_length if profile else None,
        favorite_book_ids=[str(x) for x in (profile.favorite_books or [])] if profile else [],
        shelves=[{"book_id": str(s.book_id), "status": s.status} for s in shelves],
        ratings=[{"book_id": str(r.book_id), "rating": float(r.rating or 0), "body": r.body} for r in reviews],
        positive_book_ids=positive,
        hidden=[str(h.book_id) for h in hidden],
        disliked_book_ids=[str(f.book_id) for f in feedback if f.feedback == "not_for_me"],
        liked_book_ids=[str(f.book_id) for f in feedback if f.feedback == "good"],
    )


def signals_from_answers(answers: dict[str, Any]) -> Signals:
    return Signals(
        genres=list(answers.get("genres") or answers.get("categories") or []),
        themes=list(answers.get("themes") or []),
        mood=answers.get("mood") or answers.get("reading_mood"),
        frequency=answers.get("frequency") or answers.get("reading_frequency"),
        length=answers.get("length") or answers.get("preferred_book_length"),
        favorite_book_ids=[str(x) for x in (answers.get("favorite_books") or [])],
    )


def _web_ids_from_signals(signals: Signals) -> list[str]:
    return list(
        dict.fromkeys(
            [
                *signals.favorite_book_ids,
                *[s["book_id"] for s in signals.shelves],
                *[r["book_id"] for r in signals.ratings],
                *signals.liked_book_ids,
                *signals.disliked_book_ids,
                *signals.hidden,
            ]
        )
    )


def _resolve_id_map(web_ids: list[str]) -> dict[str, str]:
    """Map application book IDs -> goodreads_id locally (no HTTP to self)."""
    numeric = [int(value) for value in web_ids if str(value).isdecimal()]
    if not numeric:
        return {}
    db_type, conn = get_conn()
    try:
        rows = repo.get_books_batch(conn, db_type, numeric)
    finally:
        conn.close()
    return {
        str(row["id"]): str(row["goodreads_id"])
        for row in rows
        if row.get("goodreads_id") is not None
    }


def _payload_from_signals(signals: Signals, user_id: Optional[str], limit: int) -> dict[str, Any]:
    web_ids = _web_ids_from_signals(signals)
    return {
        "userId": user_id,
        "preferences": {
            "genres": signals.genres,
            "favorite_books": signals.favorite_book_ids,
        },
        "history": signals.shelves,
        "ratings": [{"book_id": r["book_id"], "rating": r["rating"]} for r in signals.ratings],
        "feedback": {
            "liked": signals.liked_book_ids,
            "disliked": signals.disliked_book_ids,
            "hidden": signals.hidden,
        },
        "candidates": [],
        "limit": limit,
        "id_map": _resolve_id_map(web_ids),
    }


def _normalize_book(row: dict[str, Any]) -> dict[str, Any]:
    book = format_book(row)
    book["tags"] = _parse_tags(book.get("tags"))
    book["categories"] = book.get("categories") or book.get("tags") or []
    if not isinstance(book["categories"], list):
        book["categories"] = _parse_tags(book["categories"])
    book["id"] = str(book.get("id"))
    return book


def _hydrate_model_books(model_books: list[dict[str, Any]], id_namespace: str) -> list[dict[str, Any]]:
    if not model_books:
        return []

    raw_ids: list[int] = []
    for item in model_books:
        value = str(item.get("id", ""))
        if value.isdecimal():
            raw_ids.append(int(value))

    if not raw_ids:
        return []

    db_type, conn = get_conn()
    try:
        if id_namespace == "web":
            rows = repo.get_books_batch(conn, db_type, raw_ids)
            by_key = {str(r["id"]): r for r in rows}
            key_of = lambda item: str(item.get("id"))
        else:
            rows = repo.get_books_by_goodreads_ids(conn, db_type, raw_ids)
            by_key = {str(r["goodreads_id"]): r for r in rows if r.get("goodreads_id") is not None}
            key_of = lambda item: str(item.get("id"))
    finally:
        conn.close()

    hydrated: list[dict[str, Any]] = []
    seen_web_ids: set[str] = set()
    for item in model_books:
        row = by_key.get(key_of(item))
        if not row:
            continue
        book = _normalize_book(row)
        if book["id"] in seen_web_ids:
            continue
        seen_web_ids.add(book["id"])
        hydrated.append(
            {
                **book,
                "score": float(item.get("score") or 0),
                "why": str(item.get("reason") or "Recommended by the hybrid model."),
            }
        )
    return hydrated


def _rank_via_model(
    signals: Signals,
    user_id: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    response = ml_client.recommend_from_model(_payload_from_signals(signals, user_id, limit=max(limit, 48)))
    if not response:
        return []
    books = response.get("books") or []
    if not isinstance(books, list):
        return []
    namespace = str(response.get("id_namespace") or "book_id_csv")
    return _hydrate_model_books(books, namespace)[:limit]


def recommend(
    db: Optional[Session],
    user_id: Optional[str] = None,
    answers: Optional[dict[str, Any]] = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    if answers:
        signals = signals_from_answers(answers)
    elif db is not None and user_id:
        signals = collect_signals(db, user_id)
    else:
        signals = Signals()

    return _rank_via_model(signals, user_id, limit)


def build_sections(db: Session, user_id: Optional[str]) -> list[dict[str, Any]]:
    signals = collect_signals(db, user_id) if user_id else Signals()
    has_taste = bool(
        signals.ratings or signals.genres or any(s.get("status") == "read" for s in signals.shelves)
    )
    if not has_taste:
        return []

    ranked_books = _rank_via_model(signals, user_id, limit=48)
    if not ranked_books:
        return []

    ranked = [{"book": {k: v for k, v in b.items() if k not in {"score", "why"}}, "score": b["score"], "why": b["why"]} for b in ranked_books]

    sections: list[dict[str, Any]] = []
    if signals.ratings or any(s.get("status") == "read" for s in signals.shelves):
        sections.append({"key": "based-on-read", "title": "Based on Your Read Shelf", "books": ranked[:12]})
    elif ranked:
        sections.append({"key": "based-on-genres", "title": "Based on Your Favorite Genres", "books": ranked[:12]})

    for genre in signals.genres[:3]:
        in_genre = [
            r
            for r in ranked
            if any(
                genre.lower() in str(v).lower()
                for v in (r["book"].get("categories") or []) + (r["book"].get("tags") or [])
            )
        ]
        if in_genre:
            sections.append(
                {
                    "key": f"genre-{genre.lower().replace(' ', '-')}",
                    "title": f"Because You Like {genre}",
                    "books": in_genre[:6],
                }
            )
    gems = [
        r
        for r in ranked
        if float(r["book"].get("rating") or 0) >= 4.2 and float(r["book"].get("ratings_count") or 0) < 40000
    ][:6]
    if gems:
        sections.append({"key": "gems", "title": "Hidden Gems", "books": gems})
    return [s for s in sections if s["books"]]
