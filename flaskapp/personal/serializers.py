from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flaskapp.personal.models import (
    PersonalExercise,
    PersonalWorkoutSession,
    PersonalWorkoutTemplate,
)


def decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def iso_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def serialize_exercise(exercise: PersonalExercise) -> dict[str, Any]:
    week_plan = []
    for item in exercise.week_plans:
        reps_list = item.target_reps_list
        if not reps_list:
            reps_list = [item.target_reps] * item.sets
        percents = item.target_percents
        if not percents:
            percents = [decimal_to_float(item.target_percent)] * item.sets
        week_plan.append(
            {
                "week_no": item.week_no,
                "sets": item.sets,
                "target_reps": item.target_reps,
                "target_reps_list": reps_list,
                "target_percent": decimal_to_float(item.target_percent),
                "target_percents": percents,
            }
        )

    return {
        "id": exercise.id,
        "name": exercise.name,
        "kind": exercise.kind.value,
        "load_kind": exercise.load_kind.value if exercise.load_kind else None,
        "target_added_weight_kg": decimal_to_float(exercise.target_added_weight_kg),
        "increment_step_kg": decimal_to_float(exercise.increment_step_kg),
        "rounding_step_kg": decimal_to_float(exercise.rounding_step_kg),
        "is_active": exercise.is_active,
        "week_plan": week_plan,
    }


def serialize_template(template: PersonalWorkoutTemplate) -> dict[str, Any]:
    return {
        "id": template.id,
        "name": template.name,
        "items": [
            {
                "id": item.id,
                "exercise_id": item.exercise_id,
                "position": item.position,
                "exercise_name": item.exercise.name if item.exercise is not None else "Unknown exercise",
            }
            for item in template.items
        ],
    }


def serialize_session(session: PersonalWorkoutSession) -> dict[str, Any]:
    tasks = session.task_plan or []
    current_task = None
    if 0 <= session.next_task_index < len(tasks):
        current_task = tasks[session.next_task_index]

    return {
        "id": session.id,
        "session_date": iso_date(session.session_date),
        "mode": session.mode.value,
        "source": session.source.value,
        "template_id": session.template_id,
        "cycle_number": session.cycle_number,
        "cycle_week": session.cycle_week,
        "bodyweight_kg": decimal_to_float(session.bodyweight_kg),
        "started_at": iso_datetime(session.started_at),
        "completed_at": iso_datetime(session.completed_at),
        "next_task_index": session.next_task_index,
        "task_count": len(tasks),
        "current_task": current_task,
    }
