"""user auth recommendation tables

Revision ID: 001_user_tables
Revises:
Create Date: 2026-11-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_user_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("full_name", sa.String(255), server_default=""),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(50), server_default="user"),
        sa.UniqueConstraint("user_id", "role", name="uq_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.Column("rating", sa.Float(), server_default="0"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book_review"),
    )

    op.create_table(
        "user_books",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="want"),
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book"),
    )

    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("user_id", "book_id", name="uq_wishlist"),
    )

    op.create_table(
        "not_interested_books",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("user_id", "book_id", name="uq_not_interested"),
    )

    op.create_table(
        "recommendation_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("genres", sa.JSON(), nullable=True),
        sa.Column("themes", sa.JSON(), nullable=True),
        sa.Column("reading_mood", sa.String(64), nullable=True),
        sa.Column("reading_frequency", sa.String(64), nullable=True),
        sa.Column("preferred_book_length", sa.String(64), nullable=True),
        sa.Column("favorite_books", sa.JSON(), nullable=True),
    )

    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.Column("feedback", sa.String(32), nullable=False),
        sa.UniqueConstraint("user_id", "book_id", name="uq_rec_feedback"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "book_similarity",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("similar_book_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.UniqueConstraint("book_id", "similar_book_id", name="uq_book_sim"),
    )
    op.create_index("ix_book_similarity_book_id", "book_similarity", ["book_id"])


def downgrade() -> None:
    for table in [
        "book_similarity",
        "refresh_tokens",
        "recommendation_feedback",
        "recommendation_profiles",
        "not_interested_books",
        "wishlist_items",
        "user_books",
        "reviews",
        "user_roles",
        "profiles",
        "users",
    ]:
        op.drop_table(table)
