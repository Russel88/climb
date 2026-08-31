"""Give every exercise its own four week cycle

Revision ID: 0005_per_exercise_cycles
Revises: 0004_logs_indep_delete
Create Date: 2026-08-31 00:00:00.000000

Cycles are no longer global. Each exercise now advances through its own four week
plan, derived from the week and cycle already stamped on every row of
``personal_set_log`` - so no training data is rewritten and an in-flight cycle
carries straight over.

``personal_cycle_state`` and ``personal_cycle_review`` are deliberately left in
place: they hold the old global anchor and review markers and are simply no
longer read.
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_per_exercise_cycles"
down_revision = "0004_logs_indep_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personal_exercise_cycle_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["personal_exercise.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "cycle_number", name="uq_personal_exercise_cycle_review_exercise_cycle"),
    )

    # Carry the old global review markers over. A row in personal_cycle_review with
    # cycle_number N recorded the review that ran during cycle N, which covered the
    # completion of cycle N - 1, so that is the cycle each exercise counts as reviewed.
    # Without this, an increase already accepted would be offered a second time.
    op.execute(
        """
        INSERT INTO personal_exercise_cycle_review (exercise_id, cycle_number, reviewed_at)
        SELECT pe.id, pcr.cycle_number - 1, pcr.reviewed_at
        FROM personal_exercise pe
        CROSS JOIN personal_cycle_review pcr
        WHERE pe.kind::text = 'progressive'
          AND pcr.cycle_number > 1
        """
    )

    # A single workout can now mix exercises sitting in different weeks, so the
    # session level cycle stamp no longer has a meaningful value. Existing rows keep
    # theirs; new sessions leave it empty and stamp each set log instead.
    op.alter_column("personal_workout_session", "cycle_number", existing_type=sa.Integer(), nullable=True)
    op.alter_column("personal_workout_session", "cycle_week", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE personal_workout_session SET cycle_number = 1 WHERE cycle_number IS NULL")
    op.execute("UPDATE personal_workout_session SET cycle_week = 1 WHERE cycle_week IS NULL")

    op.alter_column("personal_workout_session", "cycle_week", existing_type=sa.Integer(), nullable=False)
    op.alter_column("personal_workout_session", "cycle_number", existing_type=sa.Integer(), nullable=False)

    op.drop_table("personal_exercise_cycle_review")
