"""Explain, per exercise, why a finished cycle is or is not offered for review.

Cycle state is never stored: it is replayed from ``personal_set_log`` every time the
dashboard asks. That makes a missing suggestion hard to reason about from the outside,
so this replays the same derivation and prints every decision it makes along the way.

Run it against the same database the app uses:

    PERSONAL_DATABASE_URL='<the app url>' python tools/diagnose_cycles.py [YYYY-MM-DD]
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from flaskapp.app import create_app
from flaskapp.extensions import db
from flaskapp.personal.models import ExerciseKind
from flaskapp.personal.services import (
    CYCLE_WEEKS,
    _bucket_set_logs_by_week,
    _highest_load_requirement,
    _week_outcome,
    active_exercises,
    exercise_cycle_states,
    is_exercise_cycle_reviewed,
    monday_of,
)

WEEKS_SHOWN = 10


def _plan_summary(exercise, week_no: int) -> str:
    plan = next((p for p in exercise.week_plans if p.week_no == week_no), None)
    if plan is None:
        return f"week {week_no}: NO PLAN ROW"
    indexes, min_reps = _highest_load_requirement(plan)
    return (
        f"week {week_no}: sets={plan.sets} percents={plan.target_percents or [float(plan.target_percent)]} "
        f"reps={plan.target_reps_list or [plan.target_reps]} "
        f"-> top set(s) {sorted(indexes)} need >= {min_reps} reps"
    )


def main() -> None:
    reference_day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    current_monday = monday_of(reference_day)

    app = create_app()
    with app.app_context():
        exercises = active_exercises()
        progressive = [e for e in exercises if e.kind == ExerciseKind.PROGRESSIVE]
        cycles = exercise_cycle_states(exercises, reference_day)
        buckets = _bucket_set_logs_by_week(current_monday, [e.id for e in progressive])

        print(f"reference day {reference_day} (week of {current_monday}), {len(progressive)} progressive exercises\n")

        for exercise in progressive:
            print("=" * 78)
            print(f"{exercise.name}  (id={exercise.id})")
            print(
                f"  target={exercise.target_added_weight_kg} increment={exercise.increment_step_kg} "
                f"rounding={exercise.rounding_step_kg}"
            )
            for week_no in range(1, CYCLE_WEEKS + 1):
                print(f"  {_plan_summary(exercise, week_no)}")

            weeks = buckets.get(exercise.id, {})
            print("  week by week (most recent first):")
            for offset in range(0, WEEKS_SHOWN):
                monday = current_monday - timedelta(weeks=offset)
                logs = weeks.get(monday, [])
                label = "this week" if offset == 0 else f"{offset}w ago  "
                if not logs:
                    print(f"    {label} {monday}  no logs")
                    continue

                outcome = _week_outcome(exercise, logs)
                sets = ", ".join(
                    f"set{log.set_index}:{log.actual_reps}r@w{log.cycle_week}/c{log.cycle_number}"
                    for log in sorted(logs, key=lambda log: (log.performed_at, log.set_index))
                )
                print(
                    f"    {label} {monday}  stamped week {outcome.week_no} cycle {outcome.cycle_number}  "
                    f"success={outcome.success}"
                )
                print(f"                          {sets}")

            cycle = cycles.get(exercise.id)
            if cycle is None:
                print("  derived state: NONE")
                continue

            print(
                f"  derived state: week {cycle.week_no}/{CYCLE_WEEKS} of cycle {cycle.cycle_number}, "
                f"restart={cycle.is_restart}, logged_this_week={cycle.logged_this_week}, "
                f"completed_cycle_number={cycle.completed_cycle_number}"
            )

            if cycle.completed_cycle_number is None:
                print(
                    "  -> NO SUGGESTION: no week stamped week 4 hit its top set, so no cycle "
                    "counts as finished."
                )
            elif exercise.increment_step_kg is None or exercise.target_added_weight_kg is None:
                print("  -> NO SUGGESTION: exercise is missing increment_step_kg or target_added_weight_kg.")
            elif is_exercise_cycle_reviewed(exercise.id, cycle.completed_cycle_number):
                print(
                    f"  -> NO SUGGESTION: cycle {cycle.completed_cycle_number} is already marked "
                    "reviewed in personal_exercise_cycle_review."
                )
            else:
                print(f"  -> SUGGESTION EXPECTED for finished cycle {cycle.completed_cycle_number}.")


if __name__ == "__main__":
    main()
