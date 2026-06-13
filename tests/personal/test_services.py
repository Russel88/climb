from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import os
import tempfile
from types import SimpleNamespace
import unittest

from flaskapp.app import create_app
from flaskapp.extensions import db
from flaskapp.personal.models import (
    ExerciseKind,
    LoadKind,
    PersonalCycleState,
    PersonalExercise,
    PersonalExerciseWeekPlan,
    PersonalNonProgressiveLog,
    PersonalSetLog,
    PersonalWorkoutSession,
    PersonalWorkoutSessionItem,
    WorkoutMode,
    WorkoutSource,
)
from flaskapp.personal.services import (
    build_task_plan,
    planned_weight_for_week,
    round_down_to_step,
    weekly_exercise_log_status,
)


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


class WeeklyExerciseLogStatusTestCase(unittest.TestCase):
    def setUp(self):
        self.previous_database_url = os.environ.get("PERSONAL_DATABASE_URL")
        fd, self.database_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["PERSONAL_DATABASE_URL"] = f"sqlite:///{self.database_path}"

        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        if self.previous_database_url is None:
            os.environ.pop("PERSONAL_DATABASE_URL", None)
        else:
            os.environ["PERSONAL_DATABASE_URL"] = self.previous_database_url
        os.unlink(self.database_path)

    def test_weekly_status_splits_active_exercises_by_current_week_logs(self):
        pull_up = PersonalExercise(
            name="Pull-up",
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.BODYWEIGHT_EXTERNAL,
            target_added_weight_kg=Decimal("20"),
            increment_step_kg=Decimal("2.5"),
            rounding_step_kg=Decimal("2.5"),
            is_active=True,
        )
        dips = PersonalExercise(
            name="Dips",
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.BODYWEIGHT_EXTERNAL,
            target_added_weight_kg=Decimal("20"),
            increment_step_kg=Decimal("2.5"),
            rounding_step_kg=Decimal("2.5"),
            is_active=True,
        )
        mobility = PersonalExercise(name="Mobility", kind=ExerciseKind.NON_PROGRESSIVE, is_active=True)
        inactive = PersonalExercise(name="Inactive", kind=ExerciseKind.NON_PROGRESSIVE, is_active=False)
        db.session.add_all([pull_up, dips, mobility, inactive])
        db.session.flush()

        session = PersonalWorkoutSession(
            session_date=date(2026, 6, 10),
            mode=WorkoutMode.INTERLEAVED,
            source=WorkoutSource.AD_HOC,
            cycle_number=1,
            cycle_week=1,
            task_plan=[],
            next_task_index=0,
        )
        db.session.add(session)
        db.session.flush()

        session_item = PersonalWorkoutSessionItem(
            session_id=session.id,
            exercise_id=pull_up.id,
            exercise_name=pull_up.name,
            position=1,
        )
        db.session.add(session_item)
        db.session.flush()

        performed_at = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        db.session.add(
            PersonalSetLog(
                session_id=session.id,
                session_item_id=session_item.id,
                exercise_id=pull_up.id,
                exercise_name=pull_up.name,
                set_index=1,
                planned_reps=5,
                actual_reps=5,
                planned_weight_kg=Decimal("20"),
                performed_at=performed_at,
                cycle_number=1,
                cycle_week=1,
            )
        )
        db.session.add(
            PersonalNonProgressiveLog(
                session_id=session.id,
                exercise_id=mobility.id,
                exercise_name=mobility.name,
                performed_at=performed_at,
            )
        )
        db.session.commit()

        result = weekly_exercise_log_status(date(2026, 6, 13))

        self.assertEqual(result["week_start"], "2026-06-08")
        self.assertEqual(result["week_end"], "2026-06-14")
        self.assertEqual({item["name"] for item in result["logged"]}, {"Mobility", "Pull-up"})
        self.assertEqual([item["name"] for item in result["not_logged"]], ["Dips"])
        self.assertFalse(any(item["on_track_for_cycle_increase"] for item in result["logged"]))
        self.assertFalse(any(item["on_track_for_cycle_increase"] for item in result["not_logged"]))

    def test_weekly_status_marks_progressive_exercise_on_track_after_previous_week_high_load_success(self):
        db.session.add(PersonalCycleState(id=1, week1_anchor_monday=date(2026, 6, 1)))

        pull_up = self._progressive_exercise("Pull-up")
        dips = self._progressive_exercise("Dips")
        db.session.add_all([pull_up, dips])
        db.session.flush()

        session = PersonalWorkoutSession(
            session_date=date(2026, 6, 6),
            mode=WorkoutMode.INTERLEAVED,
            source=WorkoutSource.AD_HOC,
            cycle_number=1,
            cycle_week=1,
            task_plan=[],
            next_task_index=0,
        )
        db.session.add(session)
        db.session.flush()

        pull_up_item = PersonalWorkoutSessionItem(
            session_id=session.id,
            exercise_id=pull_up.id,
            exercise_name=pull_up.name,
            position=1,
        )
        dips_item = PersonalWorkoutSessionItem(
            session_id=session.id,
            exercise_id=dips.id,
            exercise_name=dips.name,
            position=2,
        )
        db.session.add_all([pull_up_item, dips_item])
        db.session.flush()

        performed_at = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
        db.session.add(
            PersonalSetLog(
                session_id=session.id,
                session_item_id=pull_up_item.id,
                exercise_id=pull_up.id,
                exercise_name=pull_up.name,
                set_index=6,
                planned_reps=5,
                actual_reps=5,
                planned_weight_kg=Decimal("20"),
                performed_at=performed_at,
                cycle_number=1,
                cycle_week=1,
            )
        )
        db.session.add(
            PersonalSetLog(
                session_id=session.id,
                session_item_id=dips_item.id,
                exercise_id=dips.id,
                exercise_name=dips.name,
                set_index=6,
                planned_reps=5,
                actual_reps=4,
                planned_weight_kg=Decimal("20"),
                performed_at=performed_at,
                cycle_number=1,
                cycle_week=1,
            )
        )
        db.session.commit()

        result = weekly_exercise_log_status(date(2026, 6, 10))
        by_name = {item["name"]: item for item in result["not_logged"]}

        self.assertEqual(result["cycle_week"], 2)
        self.assertTrue(by_name["Pull-up"]["on_track_for_cycle_increase"])
        self.assertFalse(by_name["Dips"]["on_track_for_cycle_increase"])

    def _progressive_exercise(self, name: str) -> PersonalExercise:
        exercise = PersonalExercise(
            name=name,
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.BODYWEIGHT_EXTERNAL,
            target_added_weight_kg=Decimal("20"),
            increment_step_kg=Decimal("2.5"),
            rounding_step_kg=Decimal("2.5"),
            is_active=True,
        )
        for week_no, percents in {
            1: [70, 80, 85, 87, 89, 92],
            2: [70, 80, 85, 88, 90, 93],
            3: [70, 80, 85, 89, 91, 94],
            4: [70, 70, 80, 80, 90, 90],
        }.items():
            exercise.week_plans.append(
                PersonalExerciseWeekPlan(
                    week_no=week_no,
                    sets=6,
                    target_reps=5,
                    target_reps_list=[5, 5, 5, 5, 5, 5],
                    target_percent=Decimal(str(percents[0])),
                    target_percents=percents,
                )
            )
        return exercise


if __name__ == "__main__":
    unittest.main()
