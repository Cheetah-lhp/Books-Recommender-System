"""rename user reviews table from reviews to user_reviews

Revision ID: 003_rename_user_reviews
Revises: 002_reading_goal
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_rename_user_reviews"
down_revision: Union[str, None] = "002_reading_goal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_reviews" in tables:
        return

    # Chi doi ten bang `reviews` cu cua web (co cot `body`), khong dung vao bang Goodreads `reviews`.
    if "reviews" in tables:
        cols = {c["name"] for c in inspector.get_columns("reviews")}
        if "body" in cols and "review_id" not in cols:
            op.rename_table("reviews", "user_reviews")
            return

    op.create_table(
        "user_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(64), nullable=False),
        sa.Column("rating", sa.Float(), server_default="0"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book_review"),
    )
    op.create_index("ix_user_reviews_user_id", "user_reviews", ["user_id"])
    op.create_index("ix_user_reviews_book_id", "user_reviews", ["book_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "user_reviews" in tables and "reviews" not in tables:
        op.rename_table("user_reviews", "reviews")
