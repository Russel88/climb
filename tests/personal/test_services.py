from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest

from flaskapp.personal.models import ExerciseKind, LoadKind, WorkoutMode
from flaskapp.personal.services import build_task_plan, planned_weight_for_week, round_down_to_step


class ServicesTestCase(unittest.TestCase):
    def test_round_down_to_step_positive(self):
        self.assertEqual(round_down_to_step(Decimal("13"), Decimal("2.5")), Decimal("12.5"))

    def test_round_down_to_step_negative(self):
        self.assertEqual(round_down_to_step(Decimal("-29"), Decimal("2.5")), Decimal("-30.0"))

    def test_bodyweight_planned_weight(self):
        exercise = SimpleNamespace(
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.BODYWEIGHT_EXTERNAL,
            target_added_weight_kg=Decimal("20"),
            rounding_step_kg=Decimal("2.5"),
        )
        week_plan = SimpleNamespace(target_percent=Decimal("50"), target_percents=[50.0])

        result = planned_weight_for_week(exercise, week_plan, 1, Decimal("80"))

        self.assertEqual(result, Decimal("-30"))

    def test_build_task_plan_interleaved_round_robin(self):
        week_plan_a = SimpleNamespace(week_no=1, sets=2, target_reps=5, target_percent=Decimal("70"), target_percents=[70.0, 75.0])
        week_plan_a.target_reps_list = [5, 3]
        week_plan_b = SimpleNamespace(week_no=1, sets=3, target_reps=6, target_percent=Decimal("80"), target_percents=[80.0, 85.0, 90.0])
        week_plan_b.target_reps_list = [6, 4, 2]

        exercise_a = SimpleNamespace(
            id=1,
            name="Bench Press",
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.EXTERNAL,
            target_added_weight_kg=Decimal("100"),
            rounding_step_kg=Decimal("2.5"),
            week_plans=[week_plan_a],
        )

        exercise_b = SimpleNamespace(
            id=2,
            name="Squat",
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.EXTERNAL,
            target_added_weight_kg=Decimal("120"),
            rounding_step_kg=Decimal("2.5"),
            week_plans=[week_plan_b],
        )

        session_item_a = SimpleNamespace(id=11, exercise=exercise_a)
        session_item_b = SimpleNamespace(id=12, exercise=exercise_b)

        tasks = build_task_plan(
            session_items=[session_item_a, session_item_b],
            mode=WorkoutMode.INTERLEAVED,
            cycle_week=1,
            bodyweight_kg=None,
        )

        order = [(task["exercise_name"], task["set_index"]) for task in tasks]
        self.assertEqual(
            order,
            [
                ("Bench Press", 1),
                ("Squat", 1),
                ("Bench Press", 2),
                ("Squat", 2),
                ("Squat", 3),
            ],
        )
        self.assertEqual(tasks[0]["planned_weight_kg"], 70.0)
        self.assertEqual(tasks[2]["planned_weight_kg"], 75.0)
        self.assertEqual(tasks[2]["planned_reps"], 3)
        self.assertEqual(tasks[4]["planned_reps"], 2)


if __name__ == "__main__":
    unittest.main()
