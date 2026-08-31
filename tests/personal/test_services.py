from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    ExerciseCycleState,
    apply_increase_suggestions,
    build_task_plan,
    evaluate_increase_suggestions,
    exercise_cycle_state,
    planned_weight_for_week,
    round_down_to_step,
    weekly_exercise_log_status,
)


def _cycle(exercise_id: int, week_no: int, cycle_number: int = 1) -> ExerciseCycleState:
    return ExerciseCycleState(
        exercise_id=exercise_id,
        week_no=week_no,
        cycle_number=cycle_number,
        logged_this_week=False,
        week_requirement_met=False,
        previous_week_no=None,
        previous_week_success=False,
        is_restart=False,
        completed_cycle_number=None,
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

    def test_build_task_plan_interleaves_exercises_sitting_in_different_weeks(self):
        week_plan_a1 = SimpleNamespace(week_no=1, sets=2, target_reps=5, target_percent=Decimal("70"), target_percents=[70.0, 75.0])
        week_plan_a1.target_reps_list = [5, 3]
        week_plan_b2 = SimpleNamespace(week_no=2, sets=3, target_reps=6, target_percent=Decimal("80"), target_percents=[80.0, 85.0, 90.0])
        week_plan_b2.target_reps_list = [6, 4, 2]

        exercise_a = SimpleNamespace(
            id=1,
            name="Bench Press",
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.EXTERNAL,
            target_added_weight_kg=Decimal("100"),
            rounding_step_kg=Decimal("2.5"),
            week_plans=[week_plan_a1],
        )

        exercise_b = SimpleNamespace(
            id=2,
            name="Squat",
            kind=ExerciseKind.PROGRESSIVE,
            load_kind=LoadKind.EXTERNAL,
            target_added_weight_kg=Decimal("120"),
            rounding_step_kg=Decimal("2.5"),
            week_plans=[week_plan_b2],
        )

        session_item_a = SimpleNamespace(id=11, exercise=exercise_a)
        session_item_b = SimpleNamespace(id=12, exercise=exercise_b)

        tasks = build_task_plan(
            session_items=[session_item_a, session_item_b],
            mode=WorkoutMode.INTERLEAVED,
            cycles={1: _cycle(1, 1), 2: _cycle(2, 2, cycle_number=3)},
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

        # Each task carries the week and cycle of its own exercise.
        self.assertEqual([task["cycle_week"] for task in tasks], [1, 2, 1, 2, 2])
        self.assertEqual([task["cycle_number"] for task in tasks], [1, 3, 1, 3, 3])


class PersonalDatabaseTestCase(unittest.TestCase):
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

    def _log_week(
        self,
        exercise: PersonalExercise,
        day: date,
        week_no: int,
        cycle_number: int = 1,
        set_index: int = 6,
        actual_reps: int = 5,
    ) -> None:
        """Record one set for an exercise, stamped with the week it was performed under."""

        session = PersonalWorkoutSession(
            session_date=day,
            mode=WorkoutMode.INTERLEAVED,
            source=WorkoutSource.AD_HOC,
            task_plan=[],
            next_task_index=0,
        )
        db.session.add(session)
        db.session.flush()

        session_item = PersonalWorkoutSessionItem(
            session_id=session.id,
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            position=1,
        )
        db.session.add(session_item)
        db.session.flush()

        db.session.add(
            PersonalSetLog(
                session_id=session.id,
                session_item_id=session_item.id,
                exercise_id=exercise.id,
                exercise_name=exercise.name,
                set_index=set_index,
                planned_reps=5,
                actual_reps=actual_reps,
                planned_weight_kg=Decimal("20"),
                performed_at=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12),
                cycle_number=cycle_number,
                cycle_week=week_no,
            )
        )
        db.session.commit()


class ExerciseCycleStateTestCase(PersonalDatabaseTestCase):
    # 2026-06-08 and 2026-06-15 are consecutive Mondays.
    LAST_WEEK = date(2026, 6, 8)
    THIS_WEEK = date(2026, 6, 15)

    def test_exercise_without_logs_starts_at_week_one(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()

        state = exercise_cycle_state(exercise, self.THIS_WEEK)

        self.assertEqual(state.week_no, 1)
        self.assertEqual(state.cycle_number, 1)
        self.assertFalse(state.logged_this_week)
        self.assertFalse(state.is_restart)

    def test_completing_a_week_advances_to_the_next_week(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()
        self._log_week(exercise, self.LAST_WEEK, week_no=1, actual_reps=5)

        state = exercise_cycle_state(exercise, self.THIS_WEEK)

        self.assertEqual(state.week_no, 2)
        self.assertEqual(state.cycle_number, 1)
        self.assertTrue(state.previous_week_success)

    def test_missing_the_load_restarts_at_week_one_in_a_new_cycle(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()
        self._log_week(exercise, self.LAST_WEEK, week_no=2, cycle_number=4, actual_reps=4)

        state = exercise_cycle_state(exercise, self.THIS_WEEK)

        self.assertEqual(state.week_no, 1)
        self.assertEqual(state.cycle_number, 5)
        self.assertTrue(state.is_restart)
        self.assertFalse(state.previous_week_success)

    def test_skipping_a_week_restarts_at_week_one(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()
        self._log_week(exercise, self.LAST_WEEK - timedelta(weeks=1), week_no=3, cycle_number=2, actual_reps=5)

        state = exercise_cycle_state(exercise, self.THIS_WEEK)

        self.assertEqual(state.week_no, 1)
        self.assertEqual(state.cycle_number, 3)
        self.assertTrue(state.is_restart)

    def test_finishing_week_four_rolls_into_the_next_cycle(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()
        self._log_week(exercise, self.LAST_WEEK, week_no=4, cycle_number=2, set_index=5, actual_reps=5)

        state = exercise_cycle_state(exercise, self.THIS_WEEK)

        self.assertEqual(state.week_no, 1)
        self.assertEqual(state.cycle_number, 3)
        self.assertEqual(state.completed_cycle_number, 2)

    def test_a_second_workout_in_the_same_week_stays_in_that_week(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()
        self._log_week(exercise, self.LAST_WEEK, week_no=1, actual_reps=5)
        self._log_week(exercise, self.THIS_WEEK, week_no=2, actual_reps=5)

        state = exercise_cycle_state(exercise, self.THIS_WEEK + timedelta(days=3))

        self.assertEqual(state.week_no, 2)
        self.assertTrue(state.logged_this_week)
        self.assertTrue(state.week_requirement_met)

    def test_an_open_week_is_not_yet_met(self):
        exercise = self._progressive_exercise("Pull-up")
        db.session.add(exercise)
        db.session.commit()
        self._log_week(exercise, self.THIS_WEEK, week_no=1, set_index=1, actual_reps=5)

        state = exercise_cycle_state(exercise, self.THIS_WEEK)

        self.assertEqual(state.week_no, 1)
        self.assertTrue(state.logged_this_week)
        self.assertFalse(state.week_requirement_met)


class WeeklyExerciseLogStatusTestCase(PersonalDatabaseTestCase):
    LAST_WEEK = date(2026, 6, 8)
    THIS_WEEK = date(2026, 6, 15)

    def test_exercises_run_independent_weeks(self):
        pull_up = self._progressive_exercise("Pull-up")
        dips = self._progressive_exercise("Dips")
        mobility = PersonalExercise(name="Mobility", kind=ExerciseKind.NON_PROGRESSIVE, is_active=True)
        inactive = PersonalExercise(name="Inactive", kind=ExerciseKind.NON_PROGRESSIVE, is_active=False)
        db.session.add_all([pull_up, dips, mobility, inactive])
        db.session.commit()

        # Pull-up cleared weeks 1 and 2 back to back, so it is in week 3 now.
        self._log_week(pull_up, self.LAST_WEEK - timedelta(weeks=1), week_no=1, actual_reps=5)
        self._log_week(pull_up, self.LAST_WEEK, week_no=2, actual_reps=5)
        # Dips missed the top set last week, so it is back at week 1.
        self._log_week(dips, self.LAST_WEEK, week_no=3, actual_reps=3)

        result = weekly_exercise_log_status(self.THIS_WEEK)
        by_name = {item["name"]: item for item in result["logged"] + result["not_logged"]}

        self.assertEqual(result["week_start"], "2026-06-15")
        self.assertEqual(result["week_end"], "2026-06-21")
        self.assertEqual([item["name"] for item in result["logged"]], [])
        self.assertEqual(by_name["Pull-up"]["cycle_week"], 3)
        self.assertEqual(by_name["Dips"]["cycle_week"], 1)
        self.assertEqual(by_name["Pull-up"]["cycle_weeks"], 4)
        self.assertEqual(by_name["Pull-up"]["target_added_weight_kg"], 20.0)
        self.assertIsNone(by_name["Mobility"]["cycle_week"])
        self.assertIsNone(by_name["Mobility"]["target_added_weight_kg"])
        self.assertNotIn("Inactive", by_name)

    def test_logged_split_and_dot_follow_this_week(self):
        pull_up = self._progressive_exercise("Pull-up")
        mobility = PersonalExercise(name="Mobility", kind=ExerciseKind.NON_PROGRESSIVE, is_active=True)
        db.session.add_all([pull_up, mobility])
        db.session.commit()

        self._log_week(pull_up, self.THIS_WEEK, week_no=1, actual_reps=5)
        db.session.add(
            PersonalNonProgressiveLog(
                session_id=db.session.execute(db.select(PersonalWorkoutSession.id)).scalars().first(),
                exercise_id=mobility.id,
                exercise_name=mobility.name,
                performed_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
            )
        )
        db.session.commit()

        result = weekly_exercise_log_status(self.THIS_WEEK + timedelta(days=2))
        by_name = {item["name"]: item for item in result["logged"] + result["not_logged"]}

        self.assertEqual({item["name"] for item in result["logged"]}, {"Mobility", "Pull-up"})
        self.assertTrue(by_name["Pull-up"]["on_track_for_cycle_increase"])
        self.assertEqual(by_name["Pull-up"]["next_week_no"], 2)
        self.assertFalse(by_name["Mobility"]["on_track_for_cycle_increase"])

    def test_open_week_reports_a_restart_next_monday(self):
        pull_up = self._progressive_exercise("Pull-up")
        db.session.add(pull_up)
        db.session.commit()
        self._log_week(pull_up, self.LAST_WEEK, week_no=1, actual_reps=5)

        result = weekly_exercise_log_status(self.THIS_WEEK)
        by_name = {item["name"]: item for item in result["not_logged"]}

        self.assertEqual(by_name["Pull-up"]["cycle_week"], 2)
        self.assertFalse(by_name["Pull-up"]["week_requirement_met"])
        self.assertEqual(by_name["Pull-up"]["next_week_no"], 1)


class IncreaseSuggestionTestCase(PersonalDatabaseTestCase):
    LAST_WEEK = date(2026, 6, 8)
    THIS_WEEK = date(2026, 6, 15)

    def test_completing_week_four_suggests_an_increase_once(self):
        pull_up = self._progressive_exercise("Pull-up")
        dips = self._progressive_exercise("Dips")
        db.session.add_all([pull_up, dips])
        db.session.commit()

        self._log_week(pull_up, self.LAST_WEEK, week_no=4, cycle_number=2, set_index=6, actual_reps=5)
        self._log_week(dips, self.LAST_WEEK, week_no=3, cycle_number=2, actual_reps=5)

        suggestions = evaluate_increase_suggestions(self.THIS_WEEK)
        self.assertEqual([item["exercise_name"] for item in suggestions], ["Pull-up"])
        self.assertEqual(suggestions[0]["suggested_target_added_weight_kg"], 22.5)

        applied = apply_increase_suggestions({pull_up.id}, self.THIS_WEEK)
        db.session.commit()

        self.assertEqual(len(applied), 1)
        self.assertEqual(pull_up.target_added_weight_kg, Decimal("22.5"))
        self.assertEqual(evaluate_increase_suggestions(self.THIS_WEEK), [])

    def test_declining_an_increase_still_clears_the_prompt(self):
        pull_up = self._progressive_exercise("Pull-up")
        db.session.add(pull_up)
        db.session.commit()
        self._log_week(pull_up, self.LAST_WEEK, week_no=4, cycle_number=1, set_index=6, actual_reps=5)

        applied = apply_increase_suggestions(set(), self.THIS_WEEK)
        db.session.commit()

        self.assertEqual(applied, [])
        self.assertEqual(pull_up.target_added_weight_kg, Decimal("20"))
        self.assertEqual(evaluate_increase_suggestions(self.THIS_WEEK), [])


if __name__ == "__main__":
    unittest.main()
