from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import Review, User
from app.db.session import get_db

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class ReviewIn(BaseModel):
    book_id: str
    rating: float = Field(ge=0, le=5)
    body: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    book_id: str
    rating: float
    body: Optional[str] = None


@router.get("/me", response_model=list[ReviewOut])
def list_mine(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    rows = db.query(Review).filter(Review.user_id == user.id).all()
    return [ReviewOut(id=r.id, book_id=r.book_id, rating=r.rating, body=r.body) for r in rows]


@router.get("/book/{book_id}", response_model=list[ReviewOut])
def list_for_book(book_id: str, db: Annotated[Session, Depends(get_db)]):
    rows = (
        db.query(Review)
        .filter(Review.book_id == book_id)
        .order_by(Review.created_at.desc())
        .limit(100)
        .all()
    )
    return [ReviewOut(id=r.id, book_id=r.book_id, rating=r.rating, body=r.body) for r in rows]


@router.post("", response_model=ReviewOut)
def upsert_review(
    body: ReviewIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = db.query(Review).filter(Review.user_id == user.id, Review.book_id == body.book_id).first()
    if row:
        row.rating = body.rating
        row.body = body.body
    else:
        row = Review(user_id=user.id, book_id=body.book_id, rating=body.rating, body=body.body)
        db.add(row)
    db.commit()
    db.refresh(row)
    return ReviewOut(id=row.id, book_id=row.book_id, rating=row.rating, body=row.body)


@router.delete("/{review_id}")
def delete_review(
    review_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = db.query(Review).filter(Review.id == review_id, Review.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
