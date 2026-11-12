"""
BRS Python API — Book Recommender System Backend
Routers -> Services / Repositories -> Database Pool / SQLAlchemy
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import close_pool, get_conn
from app.core.redis_client import get_redis
import app.repositories.book_repo as repo
from app.routers import (
    auth,
    books,
    categories,
    library,
    recommendations,
    reviews,
    stats,
    users,
    wishlist,
)

logger = logging.getLogger("brs.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db_type, conn = get_conn()
        total = repo.get_total_count(conn, db_type)
        print(f"[BRS API] Ket noi {db_type.upper()} thanh cong. Tong so sach: {total}")
        conn.close()
    except Exception as e:
        print(f"[BRS API] Canh bao ket noi CSDL: {e}")
    yield
    close_pool()


app = FastAPI(
    title="Book Recommender System API",
    description="Backend API + Auth + Recommender cho frontend",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(books.router)
app.include_router(categories.router)
app.include_router(stats.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(wishlist.router)
app.include_router(library.router)
app.include_router(recommendations.router)


@app.get("/ready")
def ready():
    """Readiness: DB required, Redis optional."""
    from fastapi.responses import JSONResponse

    checks = {"database": False, "redis": False}
    try:
        db_type, conn = get_conn()
        repo.get_total_count(conn, db_type)
        conn.close()
        checks["database"] = True
    except Exception as exc:
        logger.warning("ready db fail: %s", exc)
        return JSONResponse({"status": "not_ready", "checks": checks}, status_code=503)
    checks["redis"] = get_redis() is not None
    return {"status": "ready", "checks": checks}
