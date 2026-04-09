"""Decouple logs from exercises and cascade template references on delete

Revision ID: 0004_logs_indep_delete
Revises: 0003_week_set_reps
Create Date: 2026-03-06 00:00:02.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_logs_indep_delete"
down_revision = "0003_week_set_reps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("personal_workout_session_item", sa.Column("exercise_name", sa.String(length=120), nullable=True))
    op.add_column("personal_set_log", sa.Column("exercise_name", sa.String(length=120), nullable=True))
    op.add_column("personal_non_progressive_log", sa.Column("exercise_name", sa.String(length=120), nullable=True))

    op.execute(
        """
        UPDATE personal_workout_session_item psi
        SET exercise_name = pe.name
        FROM personal_exercise pe
        WHERE psi.exercise_id = pe.id
        """
    )
    op.execute("UPDATE personal_workout_session_item SET exercise_name = 'Unknown exercise' WHERE exercise_name IS NULL")

    op.execute(
        """
        UPDATE personal_set_log psl
        SET exercise_name = pe.name
        FROM personal_exercise pe
        WHERE psl.exercise_id = pe.id
        """
    )
    op.execute("UPDATE personal_set_log SET exercise_name = 'Unknown exercise' WHERE exercise_name IS NULL")

    op.execute(
        """
        UPDATE personal_non_progressive_log pnpl
        SET exercise_name = pe.name
        FROM personal_exercise pe
        WHERE pnpl.exercise_id = pe.id
        """
    )
    op.execute("UPDATE personal_non_progressive_log SET exercise_name = 'Unknown exercise' WHERE exercise_name IS NULL")

    op.alter_column("personal_workout_session_item", "exercise_name", nullable=False)
    op.alter_column("personal_set_log", "exercise_name", nullable=False)
    op.alter_column("personal_non_progressive_log", "exercise_name", nullable=False)

    op.drop_constraint("personal_workout_template_item_exercise_id_fkey", "personal_workout_template_item", type_="foreignkey")
    op.create_foreign_key(
        "personal_workout_template_item_exercise_id_fkey",
        "personal_workout_template_item",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("personal_workout_session_item_exercise_id_fkey", "personal_workout_session_item", type_="foreignkey")
    op.alter_column("personal_workout_session_item", "exercise_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "personal_workout_session_item_exercise_id_fkey",
        "personal_workout_session_item",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("personal_set_log_exercise_id_fkey", "personal_set_log", type_="foreignkey")
    op.alter_column("personal_set_log", "exercise_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "personal_set_log_exercise_id_fkey",
        "personal_set_log",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("personal_non_progressive_log_exercise_id_fkey", "personal_non_progressive_log", type_="foreignkey")
    op.alter_column("personal_non_progressive_log", "exercise_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "personal_non_progressive_log_exercise_id_fkey",
        "personal_non_progressive_log",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("personal_non_progressive_log_exercise_id_fkey", "personal_non_progressive_log", type_="foreignkey")
    op.create_foreign_key(
        "personal_non_progressive_log_exercise_id_fkey",
        "personal_non_progressive_log",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("personal_set_log_exercise_id_fkey", "personal_set_log", type_="foreignkey")
    op.create_foreign_key(
        "personal_set_log_exercise_id_fkey",
        "personal_set_log",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("personal_workout_session_item_exercise_id_fkey", "personal_workout_session_item", type_="foreignkey")
    op.create_foreign_key(
        "personal_workout_session_item_exercise_id_fkey",
        "personal_workout_session_item",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("personal_workout_template_item_exercise_id_fkey", "personal_workout_template_item", type_="foreignkey")
    op.create_foreign_key(
        "personal_workout_template_item_exercise_id_fkey",
        "personal_workout_template_item",
        "personal_exercise",
        ["exercise_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_column("personal_non_progressive_log", "exercise_name")
    op.drop_column("personal_set_log", "exercise_name")
    op.drop_column("personal_workout_session_item", "exercise_name")
