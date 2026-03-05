"""Create personal training schema

Revision ID: 0001_personal_init
Revises: 
Create Date: 2026-03-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_personal_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    exercise_kind = sa.Enum("progressive", "non_progressive", name="exercisekind")
    load_kind = sa.Enum("external", "bodyweight_external", name="loadkind")
    workout_mode = sa.Enum("sequential", "interleaved", name="workoutmode")
    workout_source = sa.Enum("template", "ad_hoc", name="workoutsource")
    bodyweight_source = sa.Enum("workout_start", "manual", name="bodyweightsource")

    bind = op.get_bind()
    exercise_kind.create(bind, checkfirst=True)
    load_kind.create(bind, checkfirst=True)
    workout_mode.create(bind, checkfirst=True)
    workout_source.create(bind, checkfirst=True)
    bodyweight_source.create(bind, checkfirst=True)

    op.create_table(
        "personal_exercise",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", exercise_kind, nullable=False),
        sa.Column("load_kind", load_kind, nullable=True),
        sa.Column("target_added_weight_kg", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("increment_step_kg", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("rounding_step_kg", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_cycle_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("week1_anchor_monday", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_workout_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_workout_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("mode", workout_mode, nullable=False),
        sa.Column("source", workout_source, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("cycle_week", sa.Integer(), nullable=False),
        sa.Column("bodyweight_kg", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("task_plan", sa.JSON(), nullable=False),
        sa.Column("next_task_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["personal_workout_template.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_exercise_week_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("week_no", sa.Integer(), nullable=False),
        sa.Column("sets", sa.Integer(), nullable=False),
        sa.Column("target_reps", sa.Integer(), nullable=False),
        sa.Column("target_percent", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.CheckConstraint("week_no BETWEEN 1 AND 4", name="ck_personal_exercise_week_plan_week_range"),
        sa.ForeignKeyConstraint(["exercise_id"], ["personal_exercise.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "week_no", name="uq_personal_exercise_week_plan_exercise_week"),
    )

    op.create_table(
        "personal_workout_template_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["personal_exercise.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["personal_workout_template.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "position", name="uq_personal_workout_template_item_template_position"),
    )

    op.create_table(
        "personal_workout_session_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["personal_exercise.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["personal_workout_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "position", name="uq_personal_workout_session_item_session_position"),
    )

    op.create_table(
        "personal_set_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("session_item_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("set_index", sa.Integer(), nullable=False),
        sa.Column("planned_reps", sa.Integer(), nullable=False),
        sa.Column("actual_reps", sa.Integer(), nullable=False),
        sa.Column("planned_weight_kg", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("cycle_week", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["personal_exercise.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["personal_workout_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_item_id"], ["personal_workout_session_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_non_progressive_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["personal_exercise.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["personal_workout_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_daily_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_date", sa.Date(), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_date"),
    )

    op.create_table(
        "personal_bodyweight_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("bodyweight_kg", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("source", bodyweight_source, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["personal_workout_session.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "personal_cycle_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_number"),
    )


def downgrade() -> None:
    op.drop_table("personal_cycle_review")
    op.drop_table("personal_bodyweight_log")
    op.drop_table("personal_daily_note")
    op.drop_table("personal_non_progressive_log")
    op.drop_table("personal_set_log")
    op.drop_table("personal_workout_session_item")
    op.drop_table("personal_workout_template_item")
    op.drop_table("personal_exercise_week_plan")
    op.drop_table("personal_workout_session")
    op.drop_table("personal_workout_template")
    op.drop_table("personal_cycle_state")
    op.drop_table("personal_exercise")

    bind = op.get_bind()
    sa.Enum(name="bodyweightsource").drop(bind, checkfirst=True)
    sa.Enum(name="workoutsource").drop(bind, checkfirst=True)
    sa.Enum(name="workoutmode").drop(bind, checkfirst=True)
    sa.Enum(name="loadkind").drop(bind, checkfirst=True)
    sa.Enum(name="exercisekind").drop(bind, checkfirst=True)
