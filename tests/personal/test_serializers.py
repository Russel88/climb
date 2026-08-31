from __future__ import annotations

from datetime import date
import unittest

from flaskapp.personal.models import (
    PersonalWorkoutSession,
    WorkoutMode,
    WorkoutSource,
)
from flaskapp.personal.serializers import serialize_session


def _task(session_item_id: int, set_index: int) -> dict:
    return {
        "session_item_id": session_item_id,
        "exercise_id": session_item_id,
        "exercise_name": f"Exercise {session_item_id}",
        "kind": "progressive",
        "set_index": set_index,
        "planned_reps": 5,
        "planned_weight_kg": 20.0,
        "target_percent": 90.0,
    }


class SerializeSessionTestCase(unittest.TestCase):
    def _session(self, tasks: list[dict], next_task_index: int) -> PersonalWorkoutSession:
        return PersonalWorkoutSession(
            id=1,
            session_date=date(2026, 6, 10),
            mode=WorkoutMode.INTERLEAVED,
            source=WorkoutSource.AD_HOC,
            task_plan=tasks,
            next_task_index=next_task_index,
        )

    def test_current_task_is_flagged_on_last_set_of_exercise(self):
        tasks = [_task(1, 1), _task(2, 1), _task(1, 2), _task(2, 2)]

        self.assertFalse(serialize_session(self._session(tasks, 0))["current_task"]["is_last_set"])
        self.assertTrue(serialize_session(self._session(tasks, 2))["current_task"]["is_last_set"])
        self.assertTrue(serialize_session(self._session(tasks, 3))["current_task"]["is_last_set"])

    def test_current_task_is_none_when_plan_is_finished(self):
        tasks = [_task(1, 1)]

        self.assertIsNone(serialize_session(self._session(tasks, 1))["current_task"])


if __name__ == "__main__":
    unittest.main()
