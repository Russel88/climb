from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flaskapp.extensions import db


def _enum_column(enum_cls: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class ExerciseKind(str, Enum):
    PROGRESSIVE = "progressive"
    NON_PROGRESSIVE = "non_progressive"


class LoadKind(str, Enum):
    EXTERNAL = "external"
    BODYWEIGHT_EXTERNAL = "bodyweight_external"


class WorkoutMode(str, Enum):
    SEQUENTIAL = "sequential"
    INTERLEAVED = "interleaved"


class WorkoutSource(str, Enum):
    TEMPLATE = "template"
    AD_HOC = "ad_hoc"


class BodyweightSource(str, Enum):
    WORKOUT_START = "workout_start"
    MANUAL = "manual"


class PersonalExercise(db.Model):
    __tablename__ = "personal_exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[ExerciseKind] = mapped_column(_enum_column(ExerciseKind, "exercisekind"), nullable=False)
    load_kind: Mapped[Optional[LoadKind]] = mapped_column(_enum_column(LoadKind, "loadkind"), nullable=True)
    target_added_weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    increment_step_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    rounding_step_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    week_plans: Mapped[List["PersonalExerciseWeekPlan"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        order_by="PersonalExerciseWeekPlan.week_no",
    )


class PersonalExerciseWeekPlan(db.Model):
    __tablename__ = "personal_exercise_week_plan"
    __table_args__ = (
        UniqueConstraint("exercise_id", "week_no", name="uq_personal_exercise_week_plan_exercise_week"),
        CheckConstraint("week_no BETWEEN 1 AND 4", name="ck_personal_exercise_week_plan_week_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("personal_exercise.id", ondelete="CASCADE"), nullable=False)
    week_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps_list: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    target_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    target_percents: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)

    exercise: Mapped[PersonalExercise] = relationship(back_populates="week_plans")


class PersonalCycleState(db.Model):
    __tablename__ = "personal_cycle_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week1_anchor_monday: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PersonalWorkoutTemplate(db.Model):
    __tablename__ = "personal_workout_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    items: Mapped[List["PersonalWorkoutTemplateItem"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="PersonalWorkoutTemplateItem.position",
    )


class PersonalWorkoutTemplateItem(db.Model):
    __tablename__ = "personal_workout_template_item"
    __table_args__ = (
        UniqueConstraint("template_id", "position", name="uq_personal_workout_template_item_template_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("personal_workout_template.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("personal_exercise.id", ondelete="RESTRICT"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    template: Mapped[PersonalWorkoutTemplate] = relationship(back_populates="items")
    exercise: Mapped[PersonalExercise] = relationship()


class PersonalWorkoutSession(db.Model):
    __tablename__ = "personal_workout_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[WorkoutMode] = mapped_column(_enum_column(WorkoutMode, "workoutmode"), nullable=False)
    source: Mapped[WorkoutSource] = mapped_column(_enum_column(WorkoutSource, "workoutsource"), nullable=False)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("personal_workout_template.id", ondelete="SET NULL"), nullable=True)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_week: Mapped[int] = mapped_column(Integer, nullable=False)
    bodyweight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    task_plan: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    next_task_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[List["PersonalWorkoutSessionItem"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PersonalWorkoutSessionItem.position",
    )
    template: Mapped[Optional["PersonalWorkoutTemplate"]] = relationship()


class PersonalWorkoutSessionItem(db.Model):
    __tablename__ = "personal_workout_session_item"
    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_personal_workout_session_item_session_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("personal_workout_session.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("personal_exercise.id", ondelete="RESTRICT"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped[PersonalWorkoutSession] = relationship(back_populates="items")
    exercise: Mapped[PersonalExercise] = relationship()


class PersonalSetLog(db.Model):
    __tablename__ = "personal_set_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("personal_workout_session.id", ondelete="CASCADE"), nullable=False)
    session_item_id: Mapped[int] = mapped_column(ForeignKey("personal_workout_session_item.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("personal_exercise.id", ondelete="RESTRICT"), nullable=False)
    set_index: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_week: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonalNonProgressiveLog(db.Model):
    __tablename__ = "personal_non_progressive_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("personal_workout_session.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("personal_exercise.id", ondelete="RESTRICT"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PersonalDailyNote(db.Model):
    __tablename__ = "personal_daily_note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PersonalBodyweightLog(db.Model):
    __tablename__ = "personal_bodyweight_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    bodyweight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    source: Mapped[BodyweightSource] = mapped_column(_enum_column(BodyweightSource, "bodyweightsource"), nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("personal_workout_session.id", ondelete="SET NULL"), nullable=True)


class PersonalCycleReview(db.Model):
    __tablename__ = "personal_cycle_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
