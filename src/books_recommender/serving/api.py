from __future__ import annotations

import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from books_recommender.serving.runtime import DemoRecommender

BookIds = Annotated[list[str], Field(max_length=1000)]


class Preferences(BaseModel):
    genres: list[str] = Field(default_factory=list, max_length=50)
    favorite_books: BookIds = Field(default_factory=list)


class History(BaseModel):
    book_id: str
    status: str = "to-read"


class Rating(BaseModel):
    book_id: str
    rating: float = Field(ge=0, le=5, allow_inf_nan=False)


class Feedback(BaseModel):
    liked: BookIds = Field(default_factory=list)
    disliked: BookIds = Field(default_factory=list)
    hidden: BookIds = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    userId: str | None = None
    preferences: Preferences = Field(default_factory=Preferences)
    history: list[History] = Field(default_factory=list, max_length=1000)
    ratings: list[Rating] = Field(default_factory=list, max_length=1000)
    feedback: Feedback = Field(default_factory=Feedback)
    candidates: BookIds = Field(default_factory=list)


class CatalogResolver:
    """Translate database books.id via the upstream catalog's goodreads_id field.

    Despite its name, goodreads_id contains book_id_csv in init_sample_data.py.
    Never assume application database IDs are edition IDs, even if both numeric.
    """

    def __init__(self, base_url: str, client: httpx.Client | None = None):
        self.client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=3.0)
        self.lock = threading.Lock()
        self.cache: dict[str, str] = {}
        self.expires = 0.0

    def resolve(self, ids: list[str]) -> dict[str, str]:
        with self.lock:
            if time.monotonic() >= self.expires:
                self.cache.clear()
                self.expires = time.monotonic() + 60.0
            missing = sorted({value for value in ids if value not in self.cache})
            # The existing backend contract accepts numeric database IDs only.
            numeric = [int(value) for value in missing if value.isdecimal()]
            if numeric:
                response = self.client.post("/api/books/batch", json={"ids": numeric})
                response.raise_for_status()
                for row in response.json():
                    if row.get("goodreads_id") is not None:
                        self.cache[str(row["id"])] = str(row["goodreads_id"])
            if len(self.cache) > 10000:
                self.cache = {value: self.cache[value] for value in ids if value in self.cache}
            return {value: self.cache[value] for value in ids if value in self.cache}

    def close(self):
        self.client.close()


def create_app(
    bundle: Path,
    catalog_url: str = "http://127.0.0.1:8000",
    api_key: str | None = None,
    *,
    engine=None,
    resolver=None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine or DemoRecommender(bundle)
        app.state.resolver = resolver or CatalogResolver(catalog_url)
        yield
        app.state.resolver.close()

    app = FastAPI(title="Readora recommender model", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok", "run_id": app.state.engine.manifest["run_id"]}

    @app.post("/recommend")
    def recommend(request: RecommendationRequest, authorization: str | None = Header(default=None)):
        if api_key and not secrets.compare_digest(authorization or "", f"Bearer {api_key}"):
            raise HTTPException(status_code=401, detail="Invalid model API key")
        payload = request.model_dump()
        ids = list(
            dict.fromkeys(
                [
                    *payload["candidates"],
                    *payload["preferences"]["favorite_books"],
                    *[r["book_id"] for r in payload["history"]],
                    *[r["book_id"] for r in payload["ratings"]],
                    *payload["feedback"]["liked"],
                    *payload["feedback"]["disliked"],
                    *payload["feedback"]["hidden"],
                ]
            )
        )
        try:
            mapping = app.state.resolver.resolve(ids)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise HTTPException(status_code=503, detail="Catalog ID lookup unavailable") from error
        return app.state.engine.rerank(payload, mapping)

    return app


def serve(run_dir: Path, host: str, port: int):
    import uvicorn

    app = create_app(
        run_dir / "serving",
        catalog_url=os.getenv("ML_CATALOG_URL", "http://127.0.0.1:8000"),
        api_key=os.getenv("ML_API_KEY") or None,
    )
    uvicorn.run(app, host=host, port=port)
