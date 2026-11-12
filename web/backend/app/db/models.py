import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("Profile", back_populates="user", uselist=False)
    roles = relationship("UserRole", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="profile")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50), default="user")

    user = relationship("User", back_populates="roles")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book_review"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[float] = mapped_column(Float, default=0)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserBook(Base):
    __tablename__ = "user_books"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="want")  # want|reading|read


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_wishlist"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)


class NotInterestedBook(Base):
    __tablename__ = "not_interested_books"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_not_interested"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)


class RecommendationProfile(Base):
    __tablename__ = "recommendation_profiles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    genres: Mapped[list] = mapped_column(JSON, default=list)
    themes: Mapped[list] = mapped_column(JSON, default=list)
    reading_mood: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reading_frequency: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preferred_book_length: Mapped[str | None] = mapped_column(String(64), nullable=True)
    favorite_books: Mapped[list] = mapped_column(JSON, default=list)


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_rec_feedback"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)
    feedback: Mapped[str] = mapped_column(String(32))  # good | not_for_me


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[int] = mapped_column(Integer, default=0)


class BookSimilarity(Base):
    __tablename__ = "book_similarity"
    __table_args__ = (UniqueConstraint("book_id", "similar_book_id", name="uq_book_sim"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(Integer, index=True)
    similar_book_id: Mapped[int] = mapped_column(Integer, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
