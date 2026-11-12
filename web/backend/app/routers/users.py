from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import (
    NotInterestedBook,
    Profile,
    RecommendationFeedback,
    RecommendationProfile,
    User,
    UserRole,
)
from app.db.session import get_db
from app.schemas.auth import FeedbackIn, ProfileUpdate, RecommendationProfileIn

router = APIRouter(prefix="/api/users", tags=["users"])


class ProfileOut(BaseModel):
    id: str
    full_name: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False


@router.get("/me/profile", response_model=ProfileOut)
def get_profile(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    profile = db.get(Profile, user.id)
    roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    return ProfileOut(
        id=user.id,
        full_name=profile.full_name if profile else "",
        bio=profile.bio if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        is_admin=any(r.role == "admin" for r in roles),
    )


@router.patch("/me/profile", response_model=ProfileOut)
def patch_profile(
    body: ProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    profile = db.get(Profile, user.id)
    if not profile:
        profile = Profile(user_id=user.id, full_name="")
        db.add(profile)
    if body.full_name is not None:
        profile.full_name = body.full_name
    if body.bio is not None:
        profile.bio = body.bio
    if body.avatar_url is not None:
        profile.avatar_url = body.avatar_url
    db.commit()
    return get_profile(user, db)


@router.get("/me/recommendation-profile")
def get_rec_profile(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    row = db.get(RecommendationProfile, user.id)
    if not row:
        return RecommendationProfileIn().model_dump()
    return {
        "genres": row.genres or [],
        "themes": row.themes or [],
        "reading_mood": row.reading_mood,
        "reading_frequency": row.reading_frequency,
        "preferred_book_length": row.preferred_book_length,
        "favorite_books": row.favorite_books or [],
    }


@router.put("/me/recommendation-profile")
def put_rec_profile(
    body: RecommendationProfileIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = db.get(RecommendationProfile, user.id)
    if not row:
        row = RecommendationProfile(user_id=user.id)
        db.add(row)
    row.genres = body.genres
    row.themes = body.themes
    row.reading_mood = body.reading_mood
    row.reading_frequency = body.reading_frequency
    row.preferred_book_length = body.preferred_book_length
    row.favorite_books = body.favorite_books
    db.commit()
    return body.model_dump()


@router.post("/me/recommendation-feedback")
def post_feedback(
    body: FeedbackIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    row = (
        db.query(RecommendationFeedback)
        .filter(RecommendationFeedback.user_id == user.id, RecommendationFeedback.book_id == body.book_id)
        .first()
    )
    if row:
        row.feedback = body.feedback
    else:
        db.add(RecommendationFeedback(user_id=user.id, book_id=body.book_id, feedback=body.feedback))
    if body.feedback == "not_for_me":
        exists = (
            db.query(NotInterestedBook)
            .filter(NotInterestedBook.user_id == user.id, NotInterestedBook.book_id == body.book_id)
            .first()
        )
        if not exists:
            db.add(NotInterestedBook(user_id=user.id, book_id=body.book_id))
    db.commit()
    return {"ok": True}
