"""Add per-set reps list for weekly progression

Revision ID: 0003_week_set_reps
Revises: 0002_week_set_percents
Create Date: 2026-03-06 00:00:01.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_week_set_reps"
down_revision = "0002_week_set_percents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "personal_exercise_week_plan",
        sa.Column("target_reps_list", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("personal_exercise_week_plan", "target_reps_list")
