from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
from typing import Any

from sqlalchemy import and_, func, select

from flaskapp.extensions import db
from flaskapp.personal.models import (
    BodyweightSource,
    ExerciseKind,
    LoadKind,
    PersonalBodyweightLog,
    PersonalDailyNote,
    PersonalExercise,
    PersonalExerciseCycleReview,
    PersonalExerciseWeekPlan,
    PersonalNonProgressiveLog,
    PersonalSetLog,
    PersonalWorkoutSessionItem,
    WorkoutMode,
)


CYCLE_WEEKS = 4

# Weeks of history the per-exercise cycle derivation replays when it rebuilds state from the logs.
CYCLE_LOOKBACK_WEEKS = 26


@dataclass
class ExerciseCycleState:
    """Where a single exercise stands in its own four week cycle right now.

    Nothing about the cycle is stored: the state is replayed from the set logs, which
    already stamp every set with the week and cycle it was performed under.
    """

    exercise_id: int
    week_no: int | None
    cycle_number: int | None
    logged_this_week: bool
    week_requirement_met: bool
    previous_week_no: int | None
    previous_week_success: bool
    is_restart: bool
    completed_cycle_number: int | None


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def today_local() -> date:
    return date.today()


def next_week_no(week_no: int) -> int:
    return (week_no % CYCLE_WEEKS) + 1


def round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be positive")
    scaled = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return scaled * step


def planned_weight_for_week(
    exercise: PersonalExercise,
    week_plan: PersonalExerciseWeekPlan,
    set_index: int,
    bodyweight_kg: Decimal | None,
) -> Decimal:
    if exercise.kind != ExerciseKind.PROGRESSIVE:
        raise ValueError("exercise must be progressive")
    if exercise.target_added_weight_kg is None or exercise.rounding_step_kg is None:
        raise ValueError("progressive exercise is missing target or rounding")

    if week_plan.target_percents and len(week_plan.target_percents) >= set_index:
        set_percent = Decimal(str(week_plan.target_percents[set_index - 1]))
    else:
        set_percent = week_plan.target_percent

    percent = set_percent / Decimal("100")

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
    cycle: ExerciseCycleState | None,
    bodyweight_kg: Decimal | None,
) -> dict[str, Any]:
    exercise = session_item.exercise
    exercise_name = exercise.name if exercise is not None else session_item.exercise_name

    if exercise is None:
        raise ValueError("session item exercise is missing")

    if exercise.kind == ExerciseKind.NON_PROGRESSIVE:
        return {
            "session_item_id": session_item.id,
            "exercise_id": exercise.id,
            "exercise_name": exercise_name,
            "kind": exercise.kind.value,
            "set_index": set_index,
            "planned_reps": None,
            "planned_weight_kg": None,
            "target_percent": None,
            "cycle_week": None,
            "cycle_number": None,
        }

    if cycle is None or cycle.week_no is None:
        raise ValueError(f"missing cycle state for exercise {exercise.id}")

    week_no = cycle.week_no
    week_plan = _week_plan_for_exercise(exercise, week_no)
    if set_index < 1:
        raise ValueError("set_index must be >= 1")
    if week_plan.target_reps_list and len(week_plan.target_reps_list) >= set_index:
        target_reps = int(week_plan.target_reps_list[set_index - 1])
    else:
        target_reps = week_plan.target_reps
    if week_plan.target_percents and len(week_plan.target_percents) >= set_index:
        target_percent = Decimal(str(week_plan.target_percents[set_index - 1]))
    else:
        target_percent = week_plan.target_percent

    planned_weight = planned_weight_for_week(exercise, week_plan, set_index, bodyweight_kg)

    return {
        "session_item_id": session_item.id,
        "exercise_id": exercise.id,
        "exercise_name": exercise_name,
        "kind": exercise.kind.value,
        "set_index": set_index,
        "planned_reps": target_reps,
        "planned_weight_kg": float(planned_weight),
        "target_percent": float(target_percent),
        "cycle_week": week_no,
        "cycle_number": cycle.cycle_number,
    }


def build_task_plan(
    session_items: list[PersonalWorkoutSessionItem],
    mode: WorkoutMode,
    cycles: dict[int, ExerciseCycleState],
    bodyweight_kg: Decimal | None,
) -> list[dict[str, Any]]:
    """Build the ordered task list for a workout.

    ``cycles`` maps exercise id to that exercise's own cycle state, so two exercises in
    the same workout can sit in different weeks of their four week plans.
    """

    def cycle_for(session_item: PersonalWorkoutSessionItem) -> ExerciseCycleState | None:
        return cycles.get(session_item.exercise.id)

    def sets_for(session_item: PersonalWorkoutSessionItem) -> int:
        cycle = cycle_for(session_item)
        if cycle is None or cycle.week_no is None:
            raise ValueError(f"missing cycle state for exercise {session_item.exercise.id}")
        return _week_plan_for_exercise(session_item.exercise, cycle.week_no).sets

    if mode == WorkoutMode.SEQUENTIAL:
        tasks: list[dict[str, Any]] = []
        for session_item in session_items:
            exercise = session_item.exercise
            if exercise.kind == ExerciseKind.NON_PROGRESSIVE:
                tasks.append(_task_payload(session_item, 1, None, bodyweight_kg))
                continue

            for set_index in range(1, sets_for(session_item) + 1):
                tasks.append(_task_payload(session_item, set_index, cycle_for(session_item), bodyweight_kg))
        return tasks

    if mode != WorkoutMode.INTERLEAVED:
        raise ValueError("invalid mode")

    progressive_set_counts: list[int] = []
    has_non_progressive = False
    for session_item in session_items:
        if session_item.exercise.kind == ExerciseKind.NON_PROGRESSIVE:
            has_non_progressive = True
        else:
            progressive_set_counts.append(sets_for(session_item))

    non_progressive_target_sets = 1
    if has_non_progressive and progressive_set_counts:
        non_progressive_target_sets = max(progressive_set_counts)

    remaining_sets: dict[int, int] = {}
    next_set_index: dict[int, int] = {}
    for session_item in session_items:
        if session_item.exercise.kind == ExerciseKind.NON_PROGRESSIVE:
            remaining_sets[session_item.id] = non_progressive_target_sets
        else:
            remaining_sets[session_item.id] = sets_for(session_item)
        next_set_index[session_item.id] = 1

    tasks = []
    while any(count > 0 for count in remaining_sets.values()):
        for session_item in session_items:
            if remaining_sets[session_item.id] <= 0:
                continue
            set_index = next_set_index[session_item.id]
            is_non_progressive = session_item.exercise.kind == ExerciseKind.NON_PROGRESSIVE
            tasks.append(
                _task_payload(
                    session_item,
                    set_index,
                    None if is_non_progressive else cycle_for(session_item),
                    bodyweight_kg,
                )
            )
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


def _values_for_set_count(values: list[Any] | None, set_count: int, fallback: Any) -> list[Any]:
    normalized = list(values or [])
    if not normalized:
        normalized = [fallback] * set_count
    elif len(normalized) < set_count:
        normalized.extend([normalized[-1]] * (set_count - len(normalized)))
    return normalized[:set_count]


def _highest_load_requirement(week_plan: PersonalExerciseWeekPlan) -> tuple[set[int], int]:
    set_count = max(week_plan.sets, len(week_plan.target_percents or []), len(week_plan.target_reps_list or []), 1)
    percents = _values_for_set_count(week_plan.target_percents, set_count, float(week_plan.target_percent))
    reps = _values_for_set_count(week_plan.target_reps_list, set_count, week_plan.target_reps)

    max_percent = max(Decimal(str(percent)) for percent in percents)
    high_load_set_indexes = {
        index
        for index, percent in enumerate(percents, start=1)
        if Decimal(str(percent)) == max_percent
    }
    minimum_reps = min(reps[index - 1] for index in high_load_set_indexes)

    return high_load_set_indexes, minimum_reps


def _week_bounds(monday: date) -> tuple[datetime, datetime]:
    start_at = datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(monday + timedelta(days=6), datetime.max.time(), tzinfo=timezone.utc)
    return start_at, end_at


@dataclass
class _WeekOutcome:
    week_no: int
    cycle_number: int
    success: bool


def _week_outcome(exercise: PersonalExercise, logs: list[PersonalSetLog]) -> _WeekOutcome | None:
    """Read back what an exercise did in one calendar week.

    Every set log stamps the week and cycle it was performed under, so the week an
    exercise was actually in is taken from the logs rather than recomputed. The week
    counts as completed when the heaviest set of that week was hit for its target reps.
    """

    if not logs:
        return None

    latest = max(logs, key=lambda log: log.performed_at)
    week_no = latest.cycle_week
    cycle_number = latest.cycle_number

    week_plan = next((plan for plan in exercise.week_plans if plan.week_no == week_no), None)
    if week_plan is None:
        return _WeekOutcome(week_no=week_no, cycle_number=cycle_number, success=False)

    high_load_set_indexes, minimum_reps = _highest_load_requirement(week_plan)
    success = any(
        log.cycle_week == week_no
        and log.set_index in high_load_set_indexes
        and log.actual_reps >= minimum_reps
        for log in logs
    )

    return _WeekOutcome(week_no=week_no, cycle_number=cycle_number, success=success)


def _bucket_set_logs_by_week(
    current_monday: date,
    exercise_ids: list[int],
) -> dict[int, dict[date, list[PersonalSetLog]]]:
    earliest_monday = current_monday - timedelta(weeks=CYCLE_LOOKBACK_WEEKS)
    start_at, _ = _week_bounds(earliest_monday)
    _, end_at = _week_bounds(current_monday)

    statement = (
        select(PersonalSetLog)
        .where(
            and_(
                PersonalSetLog.exercise_id.in_(exercise_ids),
                PersonalSetLog.performed_at >= start_at,
                PersonalSetLog.performed_at <= end_at,
            )
        )
        .order_by(PersonalSetLog.performed_at.asc())
    )

    buckets: dict[int, dict[date, list[PersonalSetLog]]] = defaultdict(lambda: defaultdict(list))
    for log in db.session.execute(statement).scalars().all():
        buckets[log.exercise_id][monday_of(log.performed_at.date())].append(log)
    return buckets


def _last_cycle_numbers(exercise_ids: list[int]) -> dict[int, int]:
    statement = (
        select(PersonalSetLog.exercise_id, func.max(PersonalSetLog.cycle_number))
        .where(PersonalSetLog.exercise_id.in_(exercise_ids))
        .group_by(PersonalSetLog.exercise_id)
    )
    return {
        exercise_id: cycle_number
        for exercise_id, cycle_number in db.session.execute(statement).all()
        if exercise_id is not None and cycle_number is not None
    }


def _latest_completed_cycle_number(
    exercise: PersonalExercise,
    weeks: dict[date, list[PersonalSetLog]],
    current_monday: date,
) -> int | None:
    """The cycle number of the most recent finished cycle, ignoring the running week."""

    monday = current_monday - timedelta(weeks=1)
    earliest_monday = current_monday - timedelta(weeks=CYCLE_LOOKBACK_WEEKS)

    while monday >= earliest_monday:
        outcome = _week_outcome(exercise, weeks.get(monday, []))
        if outcome is not None and outcome.success and outcome.week_no == CYCLE_WEEKS:
            return outcome.cycle_number
        monday -= timedelta(weeks=1)

    return None


def _derive_cycle_state(
    exercise: PersonalExercise,
    weeks: dict[date, list[PersonalSetLog]],
    current_monday: date,
    last_cycle_number: int | None,
) -> ExerciseCycleState:
    this_week = _week_outcome(exercise, weeks.get(current_monday, []))
    previous_week = _week_outcome(exercise, weeks.get(current_monday - timedelta(weeks=1), []))
    completed_cycle_number = _latest_completed_cycle_number(exercise, weeks, current_monday)

    def in_range(week_no: int | None) -> bool:
        return week_no is not None and 1 <= week_no <= CYCLE_WEEKS

    # Already trained this week: the exercise stays in the week it was logged under, so a
    # second workout in the same week repeats that week rather than skipping ahead.
    if this_week is not None and in_range(this_week.week_no):
        return ExerciseCycleState(
            exercise_id=exercise.id,
            week_no=this_week.week_no,
            cycle_number=this_week.cycle_number,
            logged_this_week=True,
            week_requirement_met=this_week.success,
            previous_week_no=previous_week.week_no if previous_week else None,
            previous_week_success=bool(previous_week and previous_week.success),
            is_restart=this_week.week_no == 1,
            completed_cycle_number=completed_cycle_number,
        )

    # Last week was completed at the prescribed load, so the exercise moves on one week,
    # rolling into the next cycle after week 4.
    if previous_week is not None and previous_week.success and in_range(previous_week.week_no):
        wrapped = previous_week.week_no == CYCLE_WEEKS
        return ExerciseCycleState(
            exercise_id=exercise.id,
            week_no=next_week_no(previous_week.week_no),
            cycle_number=previous_week.cycle_number + (1 if wrapped else 0),
            logged_this_week=False,
            week_requirement_met=False,
            previous_week_no=previous_week.week_no,
            previous_week_success=True,
            is_restart=wrapped,
            completed_cycle_number=completed_cycle_number,
        )

    # Missed last week, or missed the load, so the exercise starts over at week 1.
    return ExerciseCycleState(
        exercise_id=exercise.id,
        week_no=1,
        cycle_number=(last_cycle_number + 1) if last_cycle_number is not None else 1,
        logged_this_week=False,
        week_requirement_met=False,
        previous_week_no=previous_week.week_no if previous_week else None,
        previous_week_success=False,
        is_restart=last_cycle_number is not None,
        completed_cycle_number=completed_cycle_number,
    )


def exercise_cycle_states(
    exercises: list[PersonalExercise],
    reference_day: date | None = None,
) -> dict[int, ExerciseCycleState]:
    """Current cycle position of every progressive exercise, keyed by exercise id.

    Non-progressive exercises have no week plan and are left out.
    """

    current_monday = monday_of(reference_day or today_local())
    progressive = [exercise for exercise in exercises if exercise.kind == ExerciseKind.PROGRESSIVE]
    if not progressive:
        return {}

    exercise_ids = [exercise.id for exercise in progressive]
    buckets = _bucket_set_logs_by_week(current_monday, exercise_ids)
    last_cycle_numbers = _last_cycle_numbers(exercise_ids)

    return {
        exercise.id: _derive_cycle_state(
            exercise,
            buckets.get(exercise.id, {}),
            current_monday,
            last_cycle_numbers.get(exercise.id),
        )
        for exercise in progressive
    }


def exercise_cycle_state(
    exercise: PersonalExercise,
    reference_day: date | None = None,
) -> ExerciseCycleState | None:
    return exercise_cycle_states([exercise], reference_day).get(exercise.id)


def is_exercise_cycle_reviewed(exercise_id: int, cycle_number: int) -> bool:
    statement = select(PersonalExerciseCycleReview).where(
        and_(
            PersonalExerciseCycleReview.exercise_id == exercise_id,
            PersonalExerciseCycleReview.cycle_number == cycle_number,
        )
    )
    return db.session.execute(statement).scalars().first() is not None


def mark_exercise_cycle_reviewed(exercise_id: int, cycle_number: int) -> PersonalExerciseCycleReview:
    statement = select(PersonalExerciseCycleReview).where(
        and_(
            PersonalExerciseCycleReview.exercise_id == exercise_id,
            PersonalExerciseCycleReview.cycle_number == cycle_number,
        )
    )
    current = db.session.execute(statement).scalars().first()
    if current is not None:
        return current

    review = PersonalExerciseCycleReview(exercise_id=exercise_id, cycle_number=cycle_number)
    db.session.add(review)
    db.session.flush()
    return review


def active_exercises() -> list[PersonalExercise]:
    statement = (
        select(PersonalExercise)
        .where(PersonalExercise.is_active.is_(True))
        .order_by(PersonalExercise.name.asc())
    )
    return list(db.session.execute(statement).scalars().all())


def evaluate_increase_suggestions(reference_day: date | None = None) -> list[dict[str, Any]]:
    """Exercises that finished a full four week cycle and have not been reviewed yet."""

    exercises = active_exercises()
    cycles = exercise_cycle_states(exercises, reference_day)

    suggestions: list[dict[str, Any]] = []
    for exercise in exercises:
        cycle = cycles.get(exercise.id)
        if cycle is None or cycle.completed_cycle_number is None:
            continue
        if exercise.increment_step_kg is None or exercise.target_added_weight_kg is None:
            continue
        if is_exercise_cycle_reviewed(exercise.id, cycle.completed_cycle_number):
            continue

        suggestions.append(
            {
                "exercise_id": exercise.id,
                "exercise_name": exercise.name,
                "completed_cycle_number": cycle.completed_cycle_number,
                "cycle_week": cycle.week_no,
                "current_target_added_weight_kg": float(exercise.target_added_weight_kg),
                "increment_step_kg": float(exercise.increment_step_kg),
                "suggested_target_added_weight_kg": float(exercise.target_added_weight_kg + exercise.increment_step_kg),
            }
        )

    suggestions.sort(key=lambda item: item["exercise_name"].lower())
    return suggestions


def apply_increase_suggestions(
    accepted_exercise_ids: set[int],
    reference_day: date | None = None,
) -> list[dict[str, Any]]:
    """Raise the targets that were accepted and mark every open suggestion as reviewed."""

    applied: list[dict[str, Any]] = []

    for suggestion in evaluate_increase_suggestions(reference_day):
        exercise = db.session.get(PersonalExercise, suggestion["exercise_id"])
        if exercise is None:
            continue

        if exercise.id in accepted_exercise_ids and exercise.target_added_weight_kg is not None and exercise.increment_step_kg is not None:
            old_target = exercise.target_added_weight_kg
            exercise.target_added_weight_kg = old_target + exercise.increment_step_kg
            applied.append(
                {
                    "exercise_id": exercise.id,
                    "exercise_name": exercise.name,
                    "cycle_number": suggestion["completed_cycle_number"],
                    "old_target_added_weight_kg": float(old_target),
                    "new_target_added_weight_kg": float(exercise.target_added_weight_kg),
                }
            )

        mark_exercise_cycle_reviewed(exercise.id, suggestion["completed_cycle_number"])

    return applied


def weekly_exercise_log_status(reference_day: date | None = None) -> dict[str, Any]:
    current_day = reference_day or today_local()
    week_start = monday_of(current_day)
    week_end = week_start + timedelta(days=6)
    start_at, end_at = _week_bounds(week_start)

    exercises = active_exercises()
    cycles = exercise_cycle_states(exercises, current_day)

    set_logs_statement = select(PersonalSetLog.exercise_id).where(
        and_(
            PersonalSetLog.performed_at >= start_at,
            PersonalSetLog.performed_at <= end_at,
            PersonalSetLog.exercise_id.is_not(None),
        )
    )
    non_progressive_logs_statement = select(PersonalNonProgressiveLog.exercise_id).where(
        and_(
            PersonalNonProgressiveLog.performed_at >= start_at,
            PersonalNonProgressiveLog.performed_at <= end_at,
            PersonalNonProgressiveLog.exercise_id.is_not(None),
        )
    )

    logged_ids = {
        exercise_id
        for exercise_id in db.session.execute(set_logs_statement).scalars().all()
        if exercise_id is not None
    }
    logged_ids.update(
        exercise_id
        for exercise_id in db.session.execute(non_progressive_logs_statement).scalars().all()
        if exercise_id is not None
    )

    def serialize_status_exercise(exercise: PersonalExercise) -> dict[str, Any]:
        cycle = cycles.get(exercise.id)
        target_added_weight_kg = (
            float(exercise.target_added_weight_kg) if exercise.target_added_weight_kg is not None else None
        )

        if cycle is None:
            return {
                "id": exercise.id,
                "name": exercise.name,
                "kind": exercise.kind.value,
                "target_added_weight_kg": target_added_weight_kg,
                "cycle_week": None,
                "cycle_number": None,
                "cycle_weeks": None,
                "next_week_no": None,
                "is_restart": False,
                "week_requirement_met": False,
                "on_track_for_cycle_increase": False,
            }

        return {
            "id": exercise.id,
            "name": exercise.name,
            "kind": exercise.kind.value,
            "target_added_weight_kg": target_added_weight_kg,
            "cycle_week": cycle.week_no,
            "cycle_number": cycle.cycle_number,
            "cycle_weeks": CYCLE_WEEKS,
            "next_week_no": next_week_no(cycle.week_no) if cycle.week_requirement_met else 1,
            "is_restart": cycle.is_restart,
            "week_requirement_met": cycle.week_requirement_met,
            # Being in week N already means weeks 1..N-1 were completed back to back, so
            # clearing this week is all that keeps the exercise on track.
            "on_track_for_cycle_increase": cycle.week_requirement_met,
        }

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "cycle_weeks": CYCLE_WEEKS,
        "logged": [serialize_status_exercise(exercise) for exercise in exercises if exercise.id in logged_ids],
        "not_logged": [serialize_status_exercise(exercise) for exercise in exercises if exercise.id not in logged_ids],
    }


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

    non_progressive_by_day: dict[str, dict[str, Any]] = {}
    for log in non_progressive_logs:
        day = log.performed_at.date().isoformat()
        current = non_progressive_by_day.get(day)
        if current is None:
            non_progressive_by_day[day] = {
                "date": day,
                "performed_at": log.performed_at.isoformat(),
                "exercise_name": log.exercise_name,
                "set_count": 1,
                "note": log.note,
            }
            continue

        current["set_count"] += 1
        if log.note:
            current["note"] = log.note

    return {
        "progressive_logs": [
            {
                "date": log.performed_at.date().isoformat(),
                "performed_at": log.performed_at.isoformat(),
                "set_index": log.set_index,
                "planned_reps": log.planned_reps,
                "actual_reps": log.actual_reps,
                "planned_weight_kg": float(log.planned_weight_kg),
                "logged_weight_kg": float(log.planned_weight_kg),
                "exercise_name": log.exercise_name,
                "cycle_number": log.cycle_number,
                "cycle_week": log.cycle_week,
            }
            for log in set_logs
        ],
        "non_progressive_logs": list(non_progressive_by_day.values()),
    }


def month_history(year: int, month: int) -> dict[str, Any]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)

    set_logs_statement = (
        select(PersonalSetLog)
        .where(
            and_(
                PersonalSetLog.performed_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                PersonalSetLog.performed_at <= datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc),
            )
        )
        .order_by(PersonalSetLog.performed_at.asc())
    )
    set_logs = db.session.execute(set_logs_statement).scalars().all()

    non_progressive_logs_statement = (
        select(PersonalNonProgressiveLog)
        .where(
            and_(
                PersonalNonProgressiveLog.performed_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                PersonalNonProgressiveLog.performed_at <= datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc),
            )
        )
        .order_by(PersonalNonProgressiveLog.performed_at.asc())
    )
    non_progressive_logs = db.session.execute(non_progressive_logs_statement).scalars().all()

    exercises_by_day: dict[date, set[str]] = defaultdict(set)
    for log in set_logs:
        exercises_by_day[log.performed_at.date()].add(log.exercise_name)
    for log in non_progressive_logs:
        exercises_by_day[log.performed_at.date()].add(log.exercise_name)

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
