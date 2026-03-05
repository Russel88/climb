from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
from typing import Any

from sqlalchemy import and_, select

from flaskapp.extensions import db
from flaskapp.personal.models import (
    BodyweightSource,
    ExerciseKind,
    LoadKind,
    PersonalBodyweightLog,
    PersonalCycleReview,
    PersonalCycleState,
    PersonalDailyNote,
    PersonalExercise,
    PersonalExerciseWeekPlan,
    PersonalNonProgressiveLog,
    PersonalSetLog,
    PersonalWorkoutSession,
    PersonalWorkoutSessionItem,
    WorkoutMode,
)


@dataclass
class CycleSnapshot:
    anchor_monday: date
    current_monday: date
    cycle_number: int
    cycle_week: int


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def today_local() -> date:
    return date.today()


def ensure_cycle_state(day: date | None = None) -> PersonalCycleState:
    local_day = day or today_local()
    state = db.session.get(PersonalCycleState, 1)
    if state is None:
        state = PersonalCycleState(id=1, week1_anchor_monday=monday_of(local_day))
        db.session.add(state)
        db.session.flush()
    return state


def cycle_snapshot(day: date | None = None) -> CycleSnapshot:
    local_day = day or today_local()
    state = ensure_cycle_state(local_day)
    current_monday = monday_of(local_day)

    delta_days = (current_monday - state.week1_anchor_monday).days
    weeks_since_anchor = max(0, delta_days // 7)

    cycle_number = (weeks_since_anchor // 4) + 1
    cycle_week = (weeks_since_anchor % 4) + 1

    return CycleSnapshot(
        anchor_monday=state.week1_anchor_monday,
        current_monday=current_monday,
        cycle_number=cycle_number,
        cycle_week=cycle_week,
    )


def reset_cycle_to_current_monday(day: date | None = None) -> CycleSnapshot:
    local_day = day or today_local()
    state = ensure_cycle_state(local_day)
    state.week1_anchor_monday = monday_of(local_day)
    db.session.add(state)
    db.session.flush()
    return cycle_snapshot(local_day)


def round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be positive")
    scaled = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return scaled * step


def planned_weight_for_week(
    exercise: PersonalExercise,
    week_plan: PersonalExerciseWeekPlan,
    bodyweight_kg: Decimal | None,
) -> Decimal:
    if exercise.kind != ExerciseKind.PROGRESSIVE:
        raise ValueError("exercise must be progressive")
    if exercise.target_added_weight_kg is None or exercise.rounding_step_kg is None:
        raise ValueError("progressive exercise is missing target or rounding")

    percent = week_plan.target_percent / Decimal("100")

    if exercise.load_kind == LoadKind.EXTERNAL:
        planned_external = exercise.target_added_weight_kg * percent
    elif exercise.load_kind == LoadKind.BODYWEIGHT_EXTERNAL:
        if bodyweight_kg is None:
            raise ValueError("bodyweight is required for bodyweight exercises")
        planned_total = (bodyweight_kg + exercise.target_added_weight_kg) * percent
        planned_external = planned_total - bodyweight_kg
    else:
        raise ValueError("invalid load kind for progressive exercise")

    return round_down_to_step(planned_external, exercise.rounding_step_kg)


def _week_plan_for_exercise(exercise: PersonalExercise, week_no: int) -> PersonalExerciseWeekPlan:
    for week_plan in exercise.week_plans:
        if week_plan.week_no == week_no:
            return week_plan
    raise ValueError(f"missing week {week_no} configuration for exercise {exercise.id}")


def _task_payload(
    session_item: PersonalWorkoutSessionItem,
    set_index: int,
    week_no: int,
    bodyweight_kg: Decimal | None,
) -> dict[str, Any]:
    exercise = session_item.exercise

    if exercise.kind == ExerciseKind.NON_PROGRESSIVE:
        return {
            "session_item_id": session_item.id,
            "exercise_id": exercise.id,
            "exercise_name": exercise.name,
            "kind": exercise.kind.value,
            "set_index": 1,
            "planned_reps": None,
            "planned_weight_kg": None,
            "target_percent": None,
        }

    week_plan = _week_plan_for_exercise(exercise, week_no)
    planned_weight = planned_weight_for_week(exercise, week_plan, bodyweight_kg)

    return {
        "session_item_id": session_item.id,
        "exercise_id": exercise.id,
        "exercise_name": exercise.name,
        "kind": exercise.kind.value,
        "set_index": set_index,
        "planned_reps": week_plan.target_reps,
        "planned_weight_kg": float(planned_weight),
        "target_percent": float(week_plan.target_percent),
    }


def build_task_plan(
    session_items: list[PersonalWorkoutSessionItem],
    mode: WorkoutMode,
    cycle_week: int,
    bodyweight_kg: Decimal | None,
) -> list[dict[str, Any]]:
    if mode == WorkoutMode.SEQUENTIAL:
        tasks: list[dict[str, Any]] = []
        for session_item in session_items:
            exercise = session_item.exercise
            if exercise.kind == ExerciseKind.NON_PROGRESSIVE:
                tasks.append(_task_payload(session_item, 1, cycle_week, bodyweight_kg))
                continue

            week_plan = _week_plan_for_exercise(exercise, cycle_week)
            for set_index in range(1, week_plan.sets + 1):
                tasks.append(_task_payload(session_item, set_index, cycle_week, bodyweight_kg))
        return tasks

    if mode != WorkoutMode.INTERLEAVED:
        raise ValueError("invalid mode")

    remaining_sets: dict[int, int] = {}
    next_set_index: dict[int, int] = {}
    for session_item in session_items:
        exercise = session_item.exercise
        if exercise.kind == ExerciseKind.NON_PROGRESSIVE:
            remaining_sets[session_item.id] = 1
        else:
            week_plan = _week_plan_for_exercise(exercise, cycle_week)
            remaining_sets[session_item.id] = week_plan.sets
        next_set_index[session_item.id] = 1

    tasks = []
    while any(count > 0 for count in remaining_sets.values()):
        for session_item in session_items:
            if remaining_sets[session_item.id] <= 0:
                continue
            set_index = next_set_index[session_item.id]
            tasks.append(_task_payload(session_item, set_index, cycle_week, bodyweight_kg))
            remaining_sets[session_item.id] -= 1
            next_set_index[session_item.id] += 1

    return tasks


def latest_bodyweight() -> PersonalBodyweightLog | None:
    statement = select(PersonalBodyweightLog).order_by(PersonalBodyweightLog.measured_at.desc()).limit(1)
    return db.session.execute(statement).scalars().first()


def record_bodyweight(bodyweight_kg: Decimal, source: BodyweightSource, session_id: int | None = None) -> PersonalBodyweightLog:
    entry = PersonalBodyweightLog(bodyweight_kg=bodyweight_kg, source=source, session_id=session_id)
    db.session.add(entry)
    db.session.flush()
    return entry


def is_cycle_reviewed(cycle_number: int) -> bool:
    statement = select(PersonalCycleReview).where(PersonalCycleReview.cycle_number == cycle_number)
    return db.session.execute(statement).scalars().first() is not None


def mark_cycle_reviewed(cycle_number: int) -> PersonalCycleReview:
    statement = select(PersonalCycleReview).where(PersonalCycleReview.cycle_number == cycle_number)
    current = db.session.execute(statement).scalars().first()
    if current is not None:
        return current

    review = PersonalCycleReview(cycle_number=cycle_number)
    db.session.add(review)
    db.session.flush()
    return review


def evaluate_cycle_suggestions(cycle_number: int) -> list[dict[str, Any]]:
    previous_cycle = cycle_number - 1
    if previous_cycle < 1:
        return []

    statement = select(PersonalExercise).where(
        and_(
            PersonalExercise.kind == ExerciseKind.PROGRESSIVE,
            PersonalExercise.is_active.is_(True),
        )
    )
    exercises = db.session.execute(statement).scalars().all()

    suggestions: list[dict[str, Any]] = []
    for exercise in exercises:
        if exercise.increment_step_kg is None or exercise.target_added_weight_kg is None:
            continue

        week_plan_map = {plan.week_no: plan for plan in exercise.week_plans}
        if set(week_plan_map.keys()) != {1, 2, 3, 4}:
            continue

        qualifies = True
        for week_no in (1, 2, 3, 4):
            week_plan = week_plan_map[week_no]
            logs_statement = select(PersonalSetLog).where(
                and_(
                    PersonalSetLog.exercise_id == exercise.id,
                    PersonalSetLog.cycle_number == previous_cycle,
                    PersonalSetLog.cycle_week == week_no,
                )
            )
            logs = db.session.execute(logs_statement).scalars().all()

            if len(logs) < week_plan.sets:
                qualifies = False
                break

            if any(log.actual_reps < log.planned_reps for log in logs):
                qualifies = False
                break

        if not qualifies:
            continue

        suggestions.append(
            {
                "exercise_id": exercise.id,
                "exercise_name": exercise.name,
                "current_target_added_weight_kg": float(exercise.target_added_weight_kg),
                "increment_step_kg": float(exercise.increment_step_kg),
                "suggested_target_added_weight_kg": float(exercise.target_added_weight_kg + exercise.increment_step_kg),
            }
        )

    suggestions.sort(key=lambda item: item["exercise_name"].lower())
    return suggestions


def apply_cycle_suggestions(cycle_number: int, accepted_exercise_ids: set[int]) -> list[dict[str, Any]]:
    suggestions = evaluate_cycle_suggestions(cycle_number)
    applied: list[dict[str, Any]] = []
    accepted_by_id = {item["exercise_id"]: item for item in suggestions if item["exercise_id"] in accepted_exercise_ids}

    if not accepted_by_id:
        mark_cycle_reviewed(cycle_number)
        return []

    statement = select(PersonalExercise).where(PersonalExercise.id.in_(accepted_by_id.keys()))
    exercises = db.session.execute(statement).scalars().all()

    for exercise in exercises:
        if exercise.target_added_weight_kg is None or exercise.increment_step_kg is None:
            continue
        old_target = exercise.target_added_weight_kg
        exercise.target_added_weight_kg = old_target + exercise.increment_step_kg
        applied.append(
            {
                "exercise_id": exercise.id,
                "exercise_name": exercise.name,
                "old_target_added_weight_kg": float(old_target),
                "new_target_added_weight_kg": float(exercise.target_added_weight_kg),
            }
        )

    mark_cycle_reviewed(cycle_number)
    return applied


def get_history_window(
    range_type: str,
    value: int,
    reference_day: date | None = None,
) -> tuple[date, date]:
    if value < 1:
        raise ValueError("value must be >= 1")

    today = reference_day or today_local()

    if range_type == "days":
        start = today - timedelta(days=value - 1)
    elif range_type == "weeks":
        start = today - timedelta(days=(7 * value) - 1)
    elif range_type == "months":
        start = today - timedelta(days=(30 * value) - 1)
    else:
        raise ValueError("range_type must be days, weeks, or months")

    return start, today


def exercise_history(exercise_id: int, start_day: date, end_day: date) -> dict[str, Any]:
    set_statement = (
        select(PersonalSetLog)
        .where(
            and_(
                PersonalSetLog.exercise_id == exercise_id,
                PersonalSetLog.performed_at >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
                PersonalSetLog.performed_at
                <= datetime.combine(end_day, datetime.max.time(), tzinfo=timezone.utc),
            )
        )
        .order_by(PersonalSetLog.performed_at.asc())
    )
    set_logs = db.session.execute(set_statement).scalars().all()

    non_progressive_statement = (
        select(PersonalNonProgressiveLog)
        .where(
            and_(
                PersonalNonProgressiveLog.exercise_id == exercise_id,
                PersonalNonProgressiveLog.performed_at
                >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
                PersonalNonProgressiveLog.performed_at
                <= datetime.combine(end_day, datetime.max.time(), tzinfo=timezone.utc),
            )
        )
        .order_by(PersonalNonProgressiveLog.performed_at.asc())
    )
    non_progressive_logs = db.session.execute(non_progressive_statement).scalars().all()

    return {
        "progressive_logs": [
            {
                "date": log.performed_at.date().isoformat(),
                "performed_at": log.performed_at.isoformat(),
                "set_index": log.set_index,
                "planned_reps": log.planned_reps,
                "actual_reps": log.actual_reps,
                "planned_weight_kg": float(log.planned_weight_kg),
                "cycle_number": log.cycle_number,
                "cycle_week": log.cycle_week,
            }
            for log in set_logs
        ],
        "non_progressive_logs": [
            {
                "date": log.performed_at.date().isoformat(),
                "performed_at": log.performed_at.isoformat(),
                "note": log.note,
            }
            for log in non_progressive_logs
        ],
    }


def month_history(year: int, month: int) -> dict[str, Any]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)

    sessions_statement = (
        select(PersonalWorkoutSession)
        .where(
            and_(
                PersonalWorkoutSession.session_date >= start,
                PersonalWorkoutSession.session_date <= end,
            )
        )
        .order_by(PersonalWorkoutSession.session_date.asc())
    )
    sessions = db.session.execute(sessions_statement).scalars().all()

    exercises_by_day: dict[date, set[str]] = defaultdict(set)
    for session in sessions:
        for item in session.items:
            exercises_by_day[session.session_date].add(item.exercise.name)

    notes_statement = (
        select(PersonalDailyNote)
        .where(and_(PersonalDailyNote.note_date >= start, PersonalDailyNote.note_date <= end))
        .order_by(PersonalDailyNote.note_date.asc())
    )
    notes = db.session.execute(notes_statement).scalars().all()
    notes_by_day = {note.note_date: note.note_text for note in notes}

    days = []
    for day in sorted(set(exercises_by_day.keys()) | set(notes_by_day.keys())):
        days.append(
            {
                "date": day.isoformat(),
                "exercise_names": sorted(exercises_by_day.get(day, set())),
                "has_note": day in notes_by_day,
                "note": notes_by_day.get(day),
            }
        )

    return {
        "year": year,
        "month": month,
        "days": days,
    }
