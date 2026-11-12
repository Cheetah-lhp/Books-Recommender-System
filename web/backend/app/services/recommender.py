"""Heuristic recommender ported from frontend engine.server.ts — runs in FastAPI."""

from __future__ import annotations

import json
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
from app.services.book_service import format_book
import app.repositories.book_repo as repo

THEME_TAGS: dict[str, list[str]] = {
    "Romance": ["romance", "love", "relationships"],
    "Adventure": ["adventure", "quest", "journey"],
    "Mystery": ["mystery", "crime", "thriller", "detective"],
    "Fantasy": ["fantasy", "magic", "dragons"],
    "Sci-Fi": ["science-fiction", "sci-fi", "space"],
    "History": ["history", "historical", "biography"],
    "Self-help": ["self-help", "productivity", "motivation"],
}

MOOD_TAGS: dict[str, list[str]] = {
    "Cozy": ["cozy", "comfort", "feel-good"],
    "Dark": ["dark", "grimdark", "horror"],
    "Uplifting": ["uplifting", "inspirational", "hope"],
    "Thoughtful": ["literary", "philosophy", "reflective"],
    "Exciting": ["action", "adventure", "thriller"],
}


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


def _lc(values: Optional[list[str]]) -> list[str]:
    return [str(v).lower() for v in (values or [])]


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


def _length_bucket(pages: Optional[int]) -> Optional[str]:
    if not pages:
        return None
    if pages < 250:
        return "short"
    if pages <= 450:
        return "medium"
    return "long"


def _preferred_bucket(pref: Optional[str]) -> Optional[str]:
    if not pref:
        return None
    if pref.lower().startswith("short"):
        return "short"
    if pref.lower().startswith("medium"):
        return "medium"
    if pref.lower().startswith("long"):
        return "long"
    return None


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


def load_catalog(limit: int = 500) -> list[dict[str, Any]]:
    """Load candidate books directly from DB (no internal HTTP loops)."""
    db_type, conn = get_conn()
    try:
        _total, rows = repo.get_books_paginated(conn, db_type, min(limit, 100), 0, sort="rating")
        books = [format_book(r) for r in rows]
        # Paginate locally up to `limit` respecting API page size rule
        offset = 100
        while len(books) < limit and offset < limit:
            page_limit = min(100, limit - len(books))
            _t, more = repo.get_books_paginated(conn, db_type, page_limit, offset, sort="rating")
            if not more:
                break
            books.extend(format_book(r) for r in more)
            offset += page_limit
        for b in books:
            b["tags"] = _parse_tags(b.get("tags"))
            b["categories"] = b.get("categories") or b.get("tags") or []
            if not isinstance(b["categories"], list):
                b["categories"] = _parse_tags(b["categories"])
            b["id"] = str(b.get("id"))
        return books
    finally:
        conn.close()


def score_book(book: dict[str, Any], signals: Signals, catalog: list[dict[str, Any]]) -> tuple[float, str]:
    reasons: list[str] = []
    score = float(book.get("rating") or 0)
    tags = _lc(book.get("tags"))
    cats = _lc(book.get("categories"))

    genre_hits = []
    for g in signals.genres:
        g_l = g.lower()
        if any(g_l in c or c in g_l for c in cats) or any(g_l in t or t in g_l for t in tags):
            genre_hits.append(g)
    if genre_hits:
        score += 4 * len(genre_hits)
        reasons.append(f"you enjoy {' and '.join(genre_hits[:2])}")

    theme_hits = []
    for theme in signals.themes:
        theme_tags = _lc(THEME_TAGS.get(theme, [theme]))
        if any(t in tags for t in theme_tags):
            theme_hits.append(theme)
    if theme_hits:
        score += 2 * len(theme_hits)
        reasons.append(f"you like {' and '.join(theme_hits[:2]).lower()} reads")

    mood_tags = _lc(MOOD_TAGS.get(signals.mood or "", []))
    if signals.mood and any(t in tags for t in mood_tags):
        score += 2
        reasons.append(f"you're looking for {signals.mood.lower()}")

    pref = _preferred_bucket(signals.length)
    bucket = _length_bucket(book.get("pages"))
    if pref and bucket:
        if pref == bucket:
            score += 2
            reasons.append(f"it's a {bucket} read, matching your preference")
        else:
            score -= 1.5

    loved_ids = set(signals.positive_book_ids + signals.favorite_book_ids)
    loved = [b for b in catalog if str(b.get("id")) in loved_ids]
    for fav in loved:
        if str(fav.get("id")) == str(book.get("id")):
            continue
        if fav.get("author_name") and fav.get("author_name") == book.get("author_name"):
            score += 3
            reasons.append(f"you liked {fav.get('title')} by the same author")
            break
        overlap = len(set(_lc(fav.get("tags"))) & set(tags))
        cat_overlap = len(set(_lc(fav.get("categories"))) & set(cats))
        if overlap + cat_overlap >= 2:
            score += 2 + overlap * 0.5
            reasons.append(f"it's close to {fav.get('title')}, which you rated highly")
            break

    if signals.liked_book_ids:
        liked_tags = set()
        for b in catalog:
            if str(b.get("id")) in signals.liked_book_ids:
                liked_tags.update(_lc(b.get("tags")))
        score += len([t for t in tags if t in liked_tags])

    if signals.disliked_book_ids:
        disliked_tags = set()
        for b in catalog:
            if str(b.get("id")) in signals.disliked_book_ids:
                disliked_tags.update(_lc(b.get("tags")))
        score -= len([t for t in tags if t in disliked_tags]) * 1.5

    if not signals.genres and not signals.themes:
        score += (1 if book.get("trending_rank") else 0) + min(float(book.get("ratings_count") or 0) / 5000, 2)

    why = (
        f"You may like this because {', and '.join(reasons[:2])}."
        if reasons
        else f"Highly rated in the READORA library ({float(book.get('rating') or 0):.1f}★)."
    )
    return score, why


def _eligible(catalog: list[dict[str, Any]], signals: Signals) -> list[dict[str, Any]]:
    read = {s["book_id"] for s in signals.shelves if s.get("status") == "read"}
    excluded = set(signals.hidden) | set(signals.disliked_book_ids) | read
    return [b for b in catalog if str(b.get("id")) not in excluded]


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

    catalog = load_catalog(500)
    if not catalog:
        return []

    pool = _eligible(catalog, signals)
    ranked = []
    for book in pool:
        score, why = score_book(book, signals, catalog)
        ranked.append({**book, "score": score, "why": why})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:limit]


def build_sections(db: Session, user_id: Optional[str]) -> list[dict[str, Any]]:
    signals = collect_signals(db, user_id) if user_id else Signals()
    catalog = load_catalog(500)
    if not catalog:
        return []
    pool = _eligible(catalog, signals)
    ranked = []
    for book in pool:
        score, why = score_book(book, signals, catalog)
        ranked.append({"book": book, "score": score, "why": why})
    ranked.sort(key=lambda x: x["score"], reverse=True)

    sections = [{"key": "for-you", "title": "Recommended for You", "books": ranked[:12]}]
    if signals.genres:
        top = signals.genres[0]
        in_genre = [
            r
            for r in ranked
            if any(top.lower() in str(v).lower() for v in (r["book"].get("categories") or []) + (r["book"].get("tags") or []))
        ]
        if in_genre:
            sections.append({"key": "genre", "title": f"Because You Like {top}", "books": in_genre[:6]})
    gems = [r for r in ranked if float(r["book"].get("rating") or 0) >= 4.2 and float(r["book"].get("ratings_count") or 0) < 40000][:6]
    if gems:
        sections.append({"key": "gems", "title": "Hidden Gems", "books": gems})
    return [s for s in sections if s["books"]]
