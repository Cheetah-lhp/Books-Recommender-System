"""add reading_goal_yearly to recommendation_profiles

Revision ID: 002_reading_goal
Revises: 001_user_tables
Create Date: 2026-11-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_reading_goal"
down_revision: Union[str, None] = "001_user_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendation_profiles",
        sa.Column("reading_goal_yearly", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recommendation_profiles", "reading_goal_yearly")
