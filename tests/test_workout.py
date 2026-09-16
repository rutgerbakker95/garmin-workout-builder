import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "garmin-workout" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from workout import WorkoutValidationError, duration_seconds, validate_workout  # noqa: E402


class WorkoutValidationTest(unittest.TestCase):
    def test_reference_workout_calculates_to_90_minutes(self):
        fixture = ROOT / "tests" / "fixtures" / "reference-3x10-workout.json"
        workout = validate_workout(json.loads(fixture.read_text()))

        self.assertEqual(duration_seconds(workout), 5400)

    def test_rejects_nested_repeat_blocks(self):
        with self.assertRaisesRegex(WorkoutValidationError, "nested repeat"):
            validate_workout({
                "schema_version": 1,
                "sport": "cycling",
                "name": "Nested repeat",
                "steps": [{
                    "type": "repeat",
                    "iterations": 2,
                    "steps": [{"type": "repeat", "iterations": 2, "steps": []}],
                }],
            })

    def test_rejects_inverted_ftp_range(self):
        with self.assertRaisesRegex(WorkoutValidationError, "min_percent"):
            validate_workout({
                "schema_version": 1,
                "sport": "cycling",
                "name": "Invalid range",
                "steps": [{
                    "type": "interval",
                    "duration_seconds": 60,
                    "target": {"type": "ftp_percent", "min_percent": 100, "max_percent": 90},
                }],
            })


if __name__ == "__main__":
    unittest.main()
