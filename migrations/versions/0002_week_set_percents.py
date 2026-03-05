"""Add per-set percentages for weekly progression

Revision ID: 0002_week_set_percents
Revises: 0001_personal_init
Create Date: 2026-03-05 00:00:01.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_week_set_percents"
down_revision = "0001_personal_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "personal_exercise_week_plan",
        sa.Column("target_percents", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("personal_exercise_week_plan", "target_percents")
