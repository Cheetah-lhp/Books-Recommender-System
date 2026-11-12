"""User library shelves (user_books)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User, UserBook
from app.db.session import get_db

router = APIRouter(prefix="/api/library", tags=["library"])


class ShelfIn(BaseModel):
    book_id: str
    status: str = Field(default="want", pattern="^(want|reading|read)$")


class ShelfOut(BaseModel):
    id: int
    book_id: str
    status: str


@router.get("/me", response_model=list[ShelfOut])
def list_shelf(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    rows = db.query(UserBook).filter(UserBook.user_id == user.id).all()
    return [ShelfOut(id=r.id, book_id=str(r.book_id), status=r.status) for r in rows]


@router.put("/me", response_model=ShelfOut)
def upsert_shelf(
    body: ShelfIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = (
        db.query(UserBook)
        .filter(UserBook.user_id == user.id, UserBook.book_id == body.book_id)
        .first()
    )
    if row:
        row.status = body.status
    else:
        row = UserBook(user_id=user.id, book_id=body.book_id, status=body.status)
        db.add(row)
    db.commit()
    db.refresh(row)
    return ShelfOut(id=row.id, book_id=str(row.book_id), status=row.status)


@router.delete("/me/{book_id}")
def remove_shelf(
    book_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = (
        db.query(UserBook)
        .filter(UserBook.user_id == user.id, UserBook.book_id == book_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not on shelf")
    db.delete(row)
    db.commit()
    return {"ok": True}
