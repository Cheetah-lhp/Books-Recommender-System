"""Offline job: precompute book_similarity from tag/category overlap."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import get_conn  # noqa: E402


def _tags(raw) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return {str(x).strip().lower() for x in parsed if str(x).strip()}
        except Exception:
            return {t.strip().lower() for t in raw.split(",") if t.strip()}
    return set()


def cosine(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / math.sqrt(len(a) * len(b))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--top-k", type=int, default=12)
    args = parser.parse_args()

    db_type, conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = (
                "SELECT id, tags, author_name FROM books ORDER BY ratings_count DESC LIMIT %s"
                if db_type == "mysql"
                else "SELECT id, tags, author_name FROM books ORDER BY ratings_count DESC LIMIT ?"
            )
            cur.execute(sql, (args.limit,))
            rows = cur.fetchall()

        books = []
        for r in rows:
            if isinstance(r, dict):
                books.append({"id": int(r["id"]), "tags": _tags(r.get("tags")), "author": r.get("author_name")})
            else:
                books.append({"id": int(r[0]), "tags": _tags(r[1]), "author": r[2]})

        # Inverted index for candidate generation
        tag_index: dict[str, list[int]] = defaultdict(list)
        for i, b in enumerate(books):
            for t in b["tags"]:
                tag_index[t].append(i)

        pairs: list[tuple[int, int, float]] = []
        for i, b in enumerate(books):
            candidates = set()
            for t in b["tags"]:
                for j in tag_index[t]:
                    if j != i:
                        candidates.add(j)
            scored = []
            for j in candidates:
                other = books[j]
                score = cosine(b["tags"], other["tags"])
                if b["author"] and b["author"] == other["author"]:
                    score += 0.15
                if score > 0:
                    scored.append((other["id"], score))
            scored.sort(key=lambda x: x[1], reverse=True)
            for sim_id, score in scored[: args.top_k]:
                pairs.append((b["id"], sim_id, float(score)))

        with conn.cursor() as cur:
            if db_type == "mysql":
                cur.execute("DELETE FROM book_similarity")
                cur.executemany(
                    "INSERT INTO book_similarity (book_id, similar_book_id, score) VALUES (%s, %s, %s)",
                    pairs,
                )
            else:
                cur.execute("DELETE FROM book_similarity")
                cur.executemany(
                    "INSERT INTO book_similarity (book_id, similar_book_id, score) VALUES (?, ?, ?)",
                    pairs,
                )
            if hasattr(conn, "commit"):
                conn.commit()
        print(f"[similarity] wrote {len(pairs)} edges for {len(books)} books")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
