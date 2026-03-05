from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from flaskapp.personal.models import ExerciseKind, LoadKind


class ValidationError(Exception):
    pass


def _to_decimal(value: Any, field_name: str, nullable: bool = False) -> Decimal | None:
    if value is None:
        if nullable:
            return None
        raise ValidationError(f"{field_name} is required")

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc


def _validate_week_plan(week_plan: Any) -> list[dict[str, Any]]:
    if not isinstance(week_plan, list):
        raise ValidationError("week_plan must be a list")

    normalized: list[dict[str, Any]] = []
    seen_weeks: set[int] = set()

    for entry in week_plan:
        if not isinstance(entry, dict):
            raise ValidationError("week_plan entries must be objects")

        week_no = int(entry.get("week_no", 0))
        sets = int(entry.get("sets", 0))
        target_reps = int(entry.get("target_reps", 0))
        raw_target_percents = entry.get("target_percents")
        target_percents: list[Decimal] = []

        if isinstance(raw_target_percents, list) and raw_target_percents:
            for index, raw_value in enumerate(raw_target_percents, start=1):
                percent = _to_decimal(raw_value, f"target_percents[{index}]")
                if percent <= 0:
                    raise ValidationError(f"target_percents[{index}] must be > 0")
                target_percents.append(percent)
        else:
            target_percent = _to_decimal(entry.get("target_percent"), "target_percent")
            if target_percent <= 0:
                raise ValidationError("target_percent must be > 0")
            target_percents = [target_percent for _ in range(max(sets, 1))]

        if week_no < 1 or week_no > 4:
            raise ValidationError("week_no must be between 1 and 4")
        if week_no in seen_weeks:
            raise ValidationError("week_plan week_no values must be unique")
        if sets < 1:
            raise ValidationError("sets must be >= 1")
        if target_reps < 1:
            raise ValidationError("target_reps must be >= 1")
        if len(target_percents) != sets:
            raise ValidationError("target_percents length must match sets")

        seen_weeks.add(week_no)
        normalized.append(
            {
                "week_no": week_no,
                "sets": sets,
                "target_reps": target_reps,
                "target_percent": target_percents[0],
                "target_percents": target_percents,
            }
        )

    if seen_weeks != {1, 2, 3, 4}:
        raise ValidationError("progressive exercises must include week_no 1-4")

    normalized.sort(key=lambda item: item["week_no"])
    return normalized


def validate_exercise_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object")

    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValidationError("name is required")

    kind_raw = payload.get("kind")
    try:
        kind = ExerciseKind(kind_raw)
    except ValueError as exc:
        raise ValidationError("kind must be progressive or non_progressive") from exc

    normalized: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "is_active": bool(payload.get("is_active", True)),
    }

    if kind == ExerciseKind.NON_PROGRESSIVE:
        normalized["load_kind"] = None
        normalized["target_added_weight_kg"] = None
        normalized["increment_step_kg"] = None
        normalized["rounding_step_kg"] = None
        normalized["week_plan"] = []
        return normalized

    load_kind_raw = payload.get("load_kind")
    try:
        load_kind = LoadKind(load_kind_raw)
    except ValueError as exc:
        raise ValidationError("load_kind must be external or bodyweight_external") from exc

    target_added_weight_kg = _to_decimal(payload.get("target_added_weight_kg"), "target_added_weight_kg")
    increment_step_kg = _to_decimal(payload.get("increment_step_kg"), "increment_step_kg")
    rounding_step_kg = _to_decimal(payload.get("rounding_step_kg"), "rounding_step_kg")

    if increment_step_kg <= 0:
        raise ValidationError("increment_step_kg must be > 0")
    if rounding_step_kg <= 0:
        raise ValidationError("rounding_step_kg must be > 0")

    normalized["load_kind"] = load_kind
    normalized["target_added_weight_kg"] = target_added_weight_kg
    normalized["increment_step_kg"] = increment_step_kg
    normalized["rounding_step_kg"] = rounding_step_kg
    normalized["week_plan"] = _validate_week_plan(payload.get("week_plan"))
    return normalized
