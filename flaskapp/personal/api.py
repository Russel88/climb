from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from flaskapp.extensions import db
from flaskapp.personal.models import (
    BodyweightSource,
    ExerciseKind,
    PersonalDailyNote,
    PersonalExercise,
    PersonalExerciseWeekPlan,
    PersonalNonProgressiveLog,
    PersonalSetLog,
    PersonalWorkoutSession,
    PersonalWorkoutSessionItem,
    PersonalWorkoutTemplate,
    PersonalWorkoutTemplateItem,
    WorkoutMode,
    WorkoutSource,
)
from flaskapp.personal.serializers import decimal_to_float, serialize_exercise, serialize_session, serialize_template
from flaskapp.personal.services import (
    apply_cycle_suggestions,
    build_task_plan,
    cycle_snapshot,
    evaluate_cycle_suggestions,
    exercise_history,
    get_history_window,
    is_cycle_reviewed,
    latest_bodyweight,
    mark_cycle_reviewed,
    month_history,
    record_bodyweight,
    reset_cycle_to_current_monday,
)
from flaskapp.personal.validation import ValidationError, validate_exercise_payload


personal_api_bp = Blueprint("personal_api", __name__, url_prefix="/personal/api")


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _parse_decimal(value: Any, field_name: str, nullable: bool = False) -> Decimal | None:
    if value is None:
        if nullable:
            return None
        raise ValidationError(f"{field_name} is required")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc


def _parse_iso_date(value: str, field_name: str = "date") -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must use ISO format YYYY-MM-DD") from exc


def _exercise_or_404(exercise_id: int) -> PersonalExercise | tuple[Any, int]:
    exercise = db.session.get(PersonalExercise, exercise_id)
    if exercise is None:
        return _error("exercise not found", 404)
    return exercise


def _template_or_404(template_id: int) -> PersonalWorkoutTemplate | tuple[Any, int]:
    template = db.session.get(PersonalWorkoutTemplate, template_id)
    if template is None:
        return _error("template not found", 404)
    return template


def _session_or_404(session_id: int) -> PersonalWorkoutSession | tuple[Any, int]:
    session = db.session.get(PersonalWorkoutSession, session_id)
    if session is None:
        return _error("session not found", 404)
    return session


@personal_api_bp.errorhandler(ValidationError)
def _validation_error(exc: ValidationError):
    db.session.rollback()
    return _error(str(exc), 400)


@personal_api_bp.errorhandler(IntegrityError)
def _integrity_error(_: IntegrityError):
    db.session.rollback()
    return _error("Database integrity error", 409)


@personal_api_bp.errorhandler(Exception)
def _unhandled_error(exc: Exception):
    db.session.rollback()
    return _error(f"Internal error: {exc}", 500)


@personal_api_bp.route("/cycle/state", methods=["GET"])
def get_cycle_state():
    snapshot = cycle_snapshot()
    db.session.commit()
    reviewed = is_cycle_reviewed(snapshot.cycle_number)
    should_prompt_suggestions = snapshot.cycle_week == 1 and not reviewed

    return jsonify(
        {
            "anchor_monday": snapshot.anchor_monday.isoformat(),
            "current_monday": snapshot.current_monday.isoformat(),
            "cycle_number": snapshot.cycle_number,
            "cycle_week": snapshot.cycle_week,
            "should_prompt_suggestions": should_prompt_suggestions,
        }
    )


@personal_api_bp.route("/cycle/reset", methods=["POST"])
def reset_cycle():
    snapshot = reset_cycle_to_current_monday()
    db.session.commit()
    return jsonify(
        {
            "anchor_monday": snapshot.anchor_monday.isoformat(),
            "current_monday": snapshot.current_monday.isoformat(),
            "cycle_number": snapshot.cycle_number,
            "cycle_week": snapshot.cycle_week,
        }
    )


@personal_api_bp.route("/cycle/suggestions", methods=["GET"])
def get_cycle_suggestions():
    snapshot = cycle_snapshot()
    db.session.commit()
    reviewed = is_cycle_reviewed(snapshot.cycle_number)
    should_prompt = snapshot.cycle_week == 1 and not reviewed

    suggestions = evaluate_cycle_suggestions(snapshot.cycle_number) if should_prompt else []

    return jsonify(
        {
            "cycle_number": snapshot.cycle_number,
            "cycle_week": snapshot.cycle_week,
            "should_prompt": should_prompt,
            "suggestions": suggestions,
        }
    )


@personal_api_bp.route("/cycle/suggestions/apply", methods=["POST"])
def apply_suggestions():
    payload = request.get_json(silent=True) or {}
    accepted_ids_raw = payload.get("accepted_exercise_ids", [])

    if not isinstance(accepted_ids_raw, list):
        raise ValidationError("accepted_exercise_ids must be a list")

    accepted_ids = {int(item) for item in accepted_ids_raw}
    snapshot = cycle_snapshot()

    applied = apply_cycle_suggestions(snapshot.cycle_number, accepted_ids)
    if not accepted_ids:
        mark_cycle_reviewed(snapshot.cycle_number)

    db.session.commit()
    return jsonify({"applied": applied, "cycle_number": snapshot.cycle_number})


@personal_api_bp.route("/exercises", methods=["GET"])
def list_exercises():
    statement = select(PersonalExercise).order_by(PersonalExercise.name.asc())
    exercises = db.session.execute(statement).scalars().all()
    return jsonify([serialize_exercise(exercise) for exercise in exercises])


@personal_api_bp.route("/exercises", methods=["POST"])
def create_exercise():
    payload = validate_exercise_payload(request.get_json(silent=True))

    exercise = PersonalExercise(
        name=payload["name"],
        kind=payload["kind"],
        load_kind=payload["load_kind"],
        target_added_weight_kg=payload["target_added_weight_kg"],
        increment_step_kg=payload["increment_step_kg"],
        rounding_step_kg=payload["rounding_step_kg"],
        is_active=payload["is_active"],
    )

    for week in payload["week_plan"]:
        exercise.week_plans.append(
            PersonalExerciseWeekPlan(
                week_no=week["week_no"],
                sets=week["sets"],
                target_reps=week["target_reps"],
                target_reps_list=list(week["target_reps_list"]),
                target_percent=week["target_percent"],
                target_percents=[float(value) for value in week["target_percents"]],
            )
        )

    db.session.add(exercise)
    db.session.commit()

    return jsonify(serialize_exercise(exercise)), 201


def _sync_week_plans(exercise: PersonalExercise, weeks: list[dict[str, Any]]) -> None:
    existing_by_week = {week.week_no: week for week in exercise.week_plans}
    incoming_week_numbers = {week["week_no"] for week in weeks}

    for week_no, week_plan in list(existing_by_week.items()):
        if week_no not in incoming_week_numbers:
            exercise.week_plans.remove(week_plan)

    for week in weeks:
        week_plan = existing_by_week.get(week["week_no"])
        if week_plan is None:
            week_plan = PersonalExerciseWeekPlan(week_no=week["week_no"])
            exercise.week_plans.append(week_plan)
        week_plan.sets = week["sets"]
        week_plan.target_reps = week["target_reps"]
        week_plan.target_reps_list = list(week["target_reps_list"])
        week_plan.target_percent = week["target_percent"]
        week_plan.target_percents = [float(value) for value in week["target_percents"]]


@personal_api_bp.route("/exercises/<int:exercise_id>", methods=["GET"])
def get_exercise(exercise_id: int):
    result = _exercise_or_404(exercise_id)
    if isinstance(result, tuple):
        return result
    return jsonify(serialize_exercise(result))


@personal_api_bp.route("/exercises/<int:exercise_id>", methods=["PUT"])
def update_exercise(exercise_id: int):
    result = _exercise_or_404(exercise_id)
    if isinstance(result, tuple):
        return result
    exercise = result

    payload = validate_exercise_payload(request.get_json(silent=True))

    if payload["kind"] != exercise.kind:
        raise ValidationError("kind cannot be changed after exercise creation")

    exercise.name = payload["name"]
    exercise.load_kind = payload["load_kind"]
    exercise.target_added_weight_kg = payload["target_added_weight_kg"]
    exercise.increment_step_kg = payload["increment_step_kg"]
    exercise.rounding_step_kg = payload["rounding_step_kg"]
    exercise.is_active = payload["is_active"]

    _sync_week_plans(exercise, payload["week_plan"])

    db.session.commit()
    return jsonify(serialize_exercise(exercise))


@personal_api_bp.route("/exercises/<int:exercise_id>", methods=["DELETE"])
def delete_exercise(exercise_id: int):
    result = _exercise_or_404(exercise_id)
    if isinstance(result, tuple):
        return result
    db.session.delete(result)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("Cannot delete exercise because it is used in templates or workout history", 409)
    return jsonify({"deleted": exercise_id})


@personal_api_bp.route("/templates", methods=["GET"])
def list_templates():
    statement = select(PersonalWorkoutTemplate).order_by(PersonalWorkoutTemplate.name.asc())
    templates = db.session.execute(statement).scalars().all()
    return jsonify([serialize_template(template) for template in templates])


@personal_api_bp.route("/templates", methods=["POST"])
def create_template():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValidationError("name is required")

    exercise_ids = payload.get("exercise_ids")
    if not isinstance(exercise_ids, list) or not exercise_ids:
        raise ValidationError("exercise_ids must be a non-empty list")

    template = PersonalWorkoutTemplate(name=name)
    db.session.add(template)
    db.session.flush()

    for index, exercise_id in enumerate(exercise_ids, start=1):
        exercise = db.session.get(PersonalExercise, int(exercise_id))
        if exercise is None:
            raise ValidationError(f"exercise id {exercise_id} not found")
        template.items.append(PersonalWorkoutTemplateItem(exercise_id=exercise.id, position=index))

    db.session.commit()
    return jsonify(serialize_template(template)), 201


@personal_api_bp.route("/templates/<int:template_id>", methods=["PUT"])
def update_template(template_id: int):
    result = _template_or_404(template_id)
    if isinstance(result, tuple):
        return result
    template = result

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    exercise_ids = payload.get("exercise_ids")

    if name is not None:
        name = str(name).strip()
        if not name:
            raise ValidationError("name cannot be empty")
        template.name = name

    if exercise_ids is not None:
        if not isinstance(exercise_ids, list) or not exercise_ids:
            raise ValidationError("exercise_ids must be a non-empty list")
        template.items.clear()
        for index, exercise_id in enumerate(exercise_ids, start=1):
            exercise = db.session.get(PersonalExercise, int(exercise_id))
            if exercise is None:
                raise ValidationError(f"exercise id {exercise_id} not found")
            template.items.append(PersonalWorkoutTemplateItem(exercise_id=exercise.id, position=index))

    db.session.commit()
    return jsonify(serialize_template(template))


@personal_api_bp.route("/templates/<int:template_id>", methods=["DELETE"])
def delete_template(template_id: int):
    result = _template_or_404(template_id)
    if isinstance(result, tuple):
        return result
    db.session.delete(result)
    db.session.commit()
    return jsonify({"deleted": template_id})


def _resolve_session_exercise_ids(payload: dict[str, Any]) -> tuple[WorkoutSource, int | None, list[int]]:
    source_raw = payload.get("source", WorkoutSource.AD_HOC.value)
    try:
        source = WorkoutSource(source_raw)
    except ValueError as exc:
        raise ValidationError("source must be ad_hoc or template") from exc

    template_id = payload.get("template_id")

    if source == WorkoutSource.TEMPLATE:
        if template_id is None:
            raise ValidationError("template_id is required when source is template")
        template = db.session.get(PersonalWorkoutTemplate, int(template_id))
        if template is None:
            raise ValidationError("template not found")
        ordered_exercise_ids = [item.exercise_id for item in template.items if item.exercise_id is not None]
        if not ordered_exercise_ids:
            raise ValidationError("template has no exercises")
        return source, int(template_id), ordered_exercise_ids

    exercise_ids = payload.get("exercise_ids")
    if not isinstance(exercise_ids, list) or not exercise_ids:
        raise ValidationError("exercise_ids must be a non-empty list for ad_hoc sessions")

    ordered_exercise_ids = [int(item) for item in exercise_ids]
    return source, None, ordered_exercise_ids


def _resolve_mode(payload: dict[str, Any]) -> WorkoutMode:
    mode_raw = payload.get("mode", WorkoutMode.SEQUENTIAL.value)
    try:
        return WorkoutMode(mode_raw)
    except ValueError as exc:
        raise ValidationError("mode must be sequential or interleaved") from exc


def _resolve_session_day(payload: dict[str, Any]) -> date:
    value = payload.get("session_date")
    if value is None:
        return date.today()
    return _parse_iso_date(str(value), "session_date")


@personal_api_bp.route("/workout-sessions/preview", methods=["POST"])
def preview_workout_session():
    payload = request.get_json(silent=True) or {}
    source, template_id, ordered_exercise_ids = _resolve_session_exercise_ids(payload)
    mode = _resolve_mode(payload)
    session_day = _resolve_session_day(payload)

    snapshot = cycle_snapshot(session_day)

    exercises: list[PersonalExercise] = []
    for exercise_id in ordered_exercise_ids:
        exercise = db.session.get(PersonalExercise, exercise_id)
        if exercise is None:
            raise ValidationError(f"exercise {exercise_id} not found")
        exercises.append(exercise)

    needs_bodyweight = any(ex.load_kind and ex.load_kind.value == "bodyweight_external" for ex in exercises)
    bodyweight_input = payload.get("bodyweight_kg")
    bodyweight = _parse_decimal(bodyweight_input, "bodyweight_kg", nullable=True)
    if needs_bodyweight and bodyweight is None:
        latest = latest_bodyweight()
        if latest:
            bodyweight = latest.bodyweight_kg
        else:
            raise ValidationError("bodyweight_kg is required for bodyweight exercises")

    pseudo_items = []
    for index, exercise in enumerate(exercises, start=1):
        item = PersonalWorkoutSessionItem(
            id=index,
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            position=index,
        )
        item.exercise = exercise
        pseudo_items.append(item)

    task_plan = build_task_plan(
        session_items=pseudo_items,
        mode=mode,
        cycle_week=snapshot.cycle_week,
        bodyweight_kg=bodyweight,
    )

    return jsonify(
        {
            "mode": mode.value,
            "source": source.value,
            "template_id": template_id,
            "session_date": session_day.isoformat(),
            "cycle_number": snapshot.cycle_number,
            "cycle_week": snapshot.cycle_week,
            "bodyweight_kg": decimal_to_float(bodyweight),
            "task_count": len(task_plan),
            "first_task": task_plan[0] if task_plan else None,
            "tasks": task_plan,
        }
    )


@personal_api_bp.route("/workout-sessions", methods=["POST"])
def create_workout_session():
    payload = request.get_json(silent=True) or {}
    source, template_id, ordered_exercise_ids = _resolve_session_exercise_ids(payload)
    mode = _resolve_mode(payload)
    session_day = _resolve_session_day(payload)
    snapshot = cycle_snapshot(session_day)

    exercises: list[PersonalExercise] = []
    for exercise_id in ordered_exercise_ids:
        exercise = db.session.get(PersonalExercise, exercise_id)
        if exercise is None:
            raise ValidationError(f"exercise {exercise_id} not found")
        exercises.append(exercise)

    needs_bodyweight = any(ex.load_kind and ex.load_kind.value == "bodyweight_external" for ex in exercises)
    bodyweight_input = payload.get("bodyweight_kg")
    bodyweight = _parse_decimal(bodyweight_input, "bodyweight_kg", nullable=True)
    if needs_bodyweight and bodyweight is None:
        latest = latest_bodyweight()
        if latest:
            bodyweight = latest.bodyweight_kg
        else:
            raise ValidationError("bodyweight_kg is required for bodyweight exercises")

    session = PersonalWorkoutSession(
        session_date=session_day,
        mode=mode,
        source=source,
        template_id=template_id,
        cycle_number=snapshot.cycle_number,
        cycle_week=snapshot.cycle_week,
        bodyweight_kg=bodyweight,
        task_plan=[],
        next_task_index=0,
    )
    db.session.add(session)
    db.session.flush()

    session_items: list[PersonalWorkoutSessionItem] = []
    for index, exercise in enumerate(exercises, start=1):
        item = PersonalWorkoutSessionItem(
            session_id=session.id,
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            position=index,
        )
        item.exercise = exercise
        db.session.add(item)
        db.session.flush()
        session_items.append(item)

    task_plan = build_task_plan(
        session_items=session_items,
        mode=mode,
        cycle_week=snapshot.cycle_week,
        bodyweight_kg=bodyweight,
    )
    session.task_plan = task_plan

    if bodyweight is not None:
        record_bodyweight(bodyweight, BodyweightSource.WORKOUT_START, session.id)

    db.session.commit()
    return jsonify(serialize_session(session)), 201


@personal_api_bp.route("/workout-sessions/<int:session_id>", methods=["GET"])
def get_workout_session(session_id: int):
    result = _session_or_404(session_id)
    if isinstance(result, tuple):
        return result
    return jsonify(serialize_session(result))


@personal_api_bp.route("/workout-sessions/<int:session_id>/tasks/<int:task_index>/complete", methods=["POST"])
def complete_task(session_id: int, task_index: int):
    result = _session_or_404(session_id)
    if isinstance(result, tuple):
        return result
    session = result

    tasks = session.task_plan or []
    if task_index < 0 or task_index >= len(tasks):
        return _error("task_index out of range", 404)

    if session.completed_at is not None:
        return _error("session already completed", 400)

    if task_index != session.next_task_index:
        return _error("task_index must match next_task_index", 409)

    task = tasks[task_index]
    payload = request.get_json(silent=True) or {}

    session_item_id = int(task["session_item_id"])
    exercise_id = int(task["exercise_id"])
    kind = task["kind"]

    if kind == ExerciseKind.PROGRESSIVE.value:
        actual_reps = payload.get("actual_reps")
        if actual_reps is None:
            raise ValidationError("actual_reps is required for progressive tasks")
        actual_reps_int = int(actual_reps)
        if actual_reps_int < 0:
            raise ValidationError("actual_reps must be >= 0")

        planned_weight_kg = _parse_decimal(task.get("planned_weight_kg"), "planned_weight_kg")
        planned_reps = int(task.get("planned_reps"))
        set_index = int(task.get("set_index"))

        exercise_name = str(task.get("exercise_name", "")).strip() or "Unknown exercise"
        log = PersonalSetLog(
            session_id=session.id,
            session_item_id=session_item_id,
            exercise_id=exercise_id,
            exercise_name=exercise_name,
            set_index=set_index,
            planned_reps=planned_reps,
            actual_reps=actual_reps_int,
            planned_weight_kg=planned_weight_kg,
            cycle_number=session.cycle_number,
            cycle_week=session.cycle_week,
        )
        db.session.add(log)
    else:
        note = payload.get("note")
        if note is not None:
            note = str(note).strip() or None

        exercise_name = str(task.get("exercise_name", "")).strip() or "Unknown exercise"
        log = PersonalNonProgressiveLog(
            session_id=session.id,
            exercise_id=exercise_id,
            exercise_name=exercise_name,
            note=note,
        )
        db.session.add(log)

    session.next_task_index += 1
    if session.next_task_index >= len(tasks):
        session.completed_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify(serialize_session(session))


@personal_api_bp.route("/workout-sessions/<int:session_id>/finish", methods=["POST"])
def finish_session(session_id: int):
    result = _session_or_404(session_id)
    if isinstance(result, tuple):
        return result
    session = result

    if session.completed_at is None:
        session.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    return jsonify(serialize_session(session))


@personal_api_bp.route("/history/exercises/<int:exercise_id>", methods=["GET"])
def get_exercise_history(exercise_id: int):
    result = _exercise_or_404(exercise_id)
    if isinstance(result, tuple):
        return result

    range_type = request.args.get("range_type", "weeks")
    value_raw = request.args.get("value", "8")
    try:
        value = int(value_raw)
    except ValueError as exc:
        raise ValidationError("value must be an integer") from exc

    start_day, end_day = get_history_window(range_type, value)
    history = exercise_history(exercise_id, start_day, end_day)

    return jsonify(
        {
            "exercise_id": exercise_id,
            "range_type": range_type,
            "value": value,
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            **history,
        }
    )


@personal_api_bp.route("/history/month", methods=["GET"])
def get_month_history():
    today = date.today()
    year_raw = request.args.get("year", str(today.year))
    month_raw = request.args.get("month", str(today.month))

    try:
        year = int(year_raw)
        month = int(month_raw)
    except ValueError as exc:
        raise ValidationError("year and month must be integers") from exc

    if month < 1 or month > 12:
        raise ValidationError("month must be between 1 and 12")

    return jsonify(month_history(year, month))


@personal_api_bp.route("/notes/<note_day>", methods=["GET"])
def get_note(note_day: str):
    parsed_day = _parse_iso_date(note_day)
    statement = select(PersonalDailyNote).where(PersonalDailyNote.note_date == parsed_day)
    note = db.session.execute(statement).scalars().first()

    return jsonify(
        {
            "date": parsed_day.isoformat(),
            "note_text": note.note_text if note else None,
            "has_note": note is not None,
        }
    )


@personal_api_bp.route("/notes/<note_day>", methods=["PUT"])
def upsert_note(note_day: str):
    parsed_day = _parse_iso_date(note_day)
    payload = request.get_json(silent=True) or {}

    note_text = str(payload.get("note_text", "")).strip()
    if not note_text:
        raise ValidationError("note_text is required")

    statement = select(PersonalDailyNote).where(PersonalDailyNote.note_date == parsed_day)
    note = db.session.execute(statement).scalars().first()

    if note is None:
        note = PersonalDailyNote(note_date=parsed_day, note_text=note_text)
        db.session.add(note)
    else:
        note.note_text = note_text

    db.session.commit()
    return jsonify({"date": parsed_day.isoformat(), "note_text": note.note_text, "has_note": True})


@personal_api_bp.route("/bodyweight/latest", methods=["GET"])
def get_latest_bodyweight():
    latest = latest_bodyweight()
    if latest is None:
        return jsonify({"bodyweight_kg": None, "measured_at": None})

    return jsonify(
        {
            "bodyweight_kg": decimal_to_float(latest.bodyweight_kg),
            "measured_at": latest.measured_at.isoformat(),
            "source": latest.source.value,
            "session_id": latest.session_id,
        }
    )


@personal_api_bp.route("/bodyweight", methods=["POST"])
def add_bodyweight():
    payload = request.get_json(silent=True) or {}
    value = _parse_decimal(payload.get("bodyweight_kg"), "bodyweight_kg")
    entry = record_bodyweight(value, BodyweightSource.MANUAL)
    db.session.commit()
    return (
        jsonify(
            {
                "id": entry.id,
                "bodyweight_kg": decimal_to_float(entry.bodyweight_kg),
                "measured_at": entry.measured_at.isoformat(),
                "source": entry.source.value,
            }
        ),
        201,
    )
