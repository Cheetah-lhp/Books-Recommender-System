from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class RecommendationProfileIn(BaseModel):
    genres: list[str] = []
    themes: list[str] = []
    reading_mood: Optional[str] = None
    reading_frequency: Optional[str] = None
    preferred_book_length: Optional[str] = None
    favorite_books: list[str] = []


class FeedbackIn(BaseModel):
    book_id: str
    feedback: str  # good | not_for_me
