from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User, WishlistItem
from app.db.session import get_db

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


class WishlistIn(BaseModel):
    book_id: str


class WishlistOut(BaseModel):
    id: int
    book_id: str


@router.get("", response_model=list[WishlistOut])
def list_wishlist(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    rows = db.query(WishlistItem).filter(WishlistItem.user_id == user.id).all()
    return [WishlistOut(id=r.id, book_id=r.book_id) for r in rows]


@router.post("", response_model=WishlistOut, status_code=201)
def add_wishlist(
    body: WishlistIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    existing = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user.id, WishlistItem.book_id == body.book_id)
        .first()
    )
    if existing:
        return WishlistOut(id=existing.id, book_id=existing.book_id)
    row = WishlistItem(user_id=user.id, book_id=body.book_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return WishlistOut(id=row.id, book_id=row.book_id)


@router.delete("/{book_id}")
def remove_wishlist(
    book_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = (
        db.query(WishlistItem)
        .filter(WishlistItem.user_id == user.id, WishlistItem.book_id == book_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not in wishlist")
    db.delete(row)
    db.commit()
    return {"ok": True}
