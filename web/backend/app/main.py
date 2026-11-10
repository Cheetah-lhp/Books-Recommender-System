"""
BRS Python API — Book Recommender System Backend
Kien truc phan tang: Routers -> Services / Repositories -> Database Pool
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import get_conn, close_pool
import app.repositories.book_repo as repo
from app.routers import books, categories, stats

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kiem tra ket noi khi khoi dong
    try:
        db_type, conn = get_conn()
        total = repo.get_total_count(conn, db_type)
        print(f"[BRS API] Ket noi {db_type.upper()} thanh cong. Tong so sach: {total}")
        conn.close()
    except Exception as e:
        print(f"[BRS API] Canh bao ket noi CSDL: {e}")
    yield
    # Don dep ket noi khi dung ung dung
    close_pool()

app = FastAPI(
    title="Book Recommender System API",
    description="Backend API phuc vu du lieu sach cho frontend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dang ky routers
app.include_router(books.router)
app.include_router(categories.router)
app.include_router(stats.router)

