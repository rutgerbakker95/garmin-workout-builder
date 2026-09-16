import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "garmin-workout" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from garmin import GarminReferenceError, to_garmin_workout  # noqa: E402
from workout import validate_workout  # noqa: E402


class GarminExportTest(unittest.TestCase):
    def setUp(self):
        workout_fixture = ROOT / "tests" / "fixtures" / "reference-3x10-workout.json"
        reference_fixture = ROOT / "tests" / "fixtures" / "garmin-reference.json"
        self.workout = validate_workout(json.loads(workout_fixture.read_text()))
        self.reference = json.loads(reference_fixture.read_text())
        self.exported = to_garmin_workout(self.workout, self.reference)

    def test_reference_shape_preserves_metadata_steps_targets_and_duration(self):
        self.assertEqual(self.exported["sportType"]["sportTypeKey"], "cycling")
        self.assertEqual(self.exported["estimatedDurationInSecs"], 5400)
        self.assertEqual(self.exported["workoutId"], self.reference["workoutId"])
        self.assertEqual(self.exported["ownerId"], self.reference["ownerId"])
        self.assertEqual(self.exported["author"], self.reference["author"])
        self.assertEqual(self.exported["estimatedDistanceUnit"], self.reference["estimatedDistanceUnit"])
        steps = self.exported["workoutSegments"][0]["workoutSteps"]
        self.assertEqual([step["stepOrder"] for step in _flatten(steps)], [1, 2, 3, 4, 5, 6])
        self.assertEqual(steps[0]["targetValueOne"], 50.0)
        self.assertEqual(steps[1]["numberOfIterations"], 3)
        self.assertEqual(steps[1]["workoutSteps"][0]["targetValueTwo"], 94.0)

    def test_reference_identifiers_are_retained_for_extension_compatibility(self):
        steps = self.exported["workoutSegments"][0]["workoutSteps"]

        self.assertEqual(steps[0]["stepId"], self.reference["workoutSegments"][0]["workoutSteps"][0]["stepId"])
        self.assertEqual(
            steps[1]["workoutSteps"][0]["stepId"],
            self.reference["workoutSegments"][0]["workoutSteps"][1]["workoutSteps"][0]["stepId"],
        )

    def test_instruction_text_does_not_change_unproven_garmin_description(self):
        workout = validate_workout({
            "schema_version": 1,
            "sport": "cycling",
            "name": "Easy recovery",
            "steps": [{
                "type": "recovery",
                "duration_seconds": 90,
                "instructions": "Pedal easy.",
                "target": {"type": "none"},
            }],
        })
        step = to_garmin_workout(workout, self.reference)["workoutSegments"][0]["workoutSteps"][0]

        self.assertIsNone(step["description"])
        self.assertIsNone(step["targetType"])
        self.assertIsNone(step["targetValueOne"])
        self.assertIsNone(step["targetValueUnit"])

    def test_multiple_repeat_groups_are_rejected_without_a_proven_template(self):
        workout = validate_workout({
            "schema_version": 1,
            "sport": "cycling",
            "name": "Two repeat groups",
            "steps": [
                {
                    "type": "repeat",
                    "iterations": 2,
                    "steps": [{
                        "type": "interval",
                        "duration_seconds": 60,
                        "target": {"type": "none"},
                    }],
                },
                {
                    "type": "repeat",
                    "iterations": 3,
                    "steps": [{
                        "type": "recovery",
                        "duration_seconds": 30,
                        "target": {"type": "none"},
                    }],
                },
            ],
        })

        with self.assertRaisesRegex(GarminReferenceError, "one repeat block"):
            to_garmin_workout(workout, self.reference)

    def test_reference_is_not_mutated(self):
        before = copy.deepcopy(self.reference)
        to_garmin_workout(self.workout, self.reference)

        self.assertEqual(self.reference, before)


def _flatten(steps):
    for step in steps:
        yield step
        if step["type"] == "RepeatGroupDTO":
            yield from _flatten(step["workoutSteps"])


if __name__ == "__main__":
    unittest.main()
