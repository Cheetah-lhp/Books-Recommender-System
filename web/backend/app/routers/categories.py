from typing import List
from fastapi import APIRouter

from app.core.database import get_conn
from app.schemas.book import CategoryItem
import app.repositories.book_repo as repo

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("", response_model=List[CategoryItem])
def list_categories():
    # Danh sach cac the loai pho bien kem so luong sach
    db_type, conn = get_conn()
    try:
        rows = repo.get_categories_summary(conn, db_type, limit=50)
    finally:
        conn.close()
    return [CategoryItem(name=r["category"], count=r["count"]) for r in rows]

