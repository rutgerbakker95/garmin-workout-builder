import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "skills" / "garmin-workout" / "scripts" / "export_workout.py"
FIXTURE = ROOT / "tests" / "fixtures" / "reference-3x10-workout.json"
GARMIN_REFERENCE = ROOT / "tests" / "fixtures" / "garmin-reference.json"


class ExportCliTest(unittest.TestCase):
    def test_default_export_uses_public_reference(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "public.json"
            result = subprocess.run(
                [sys.executable, str(EXPORTER), "--input", str(FIXTURE), "--output", str(output)],
                cwd=temporary_directory, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = json.loads(output.read_text())
            self.assertEqual(exported["ownerId"], 200000001)
            self.assertEqual(exported["author"]["fullName"], "Reference")
            self.assertIsNone(exported["author"]["profileImgNameLarge"])
            self.assertEqual(exported["estimatedDurationInSecs"], 5400)

    def test_standalone_skill_uses_bundled_reference_from_another_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            skill = directory / "garmin-workout"
            shutil.copytree(EXPORTER.parent, skill / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            (skill / "assets").mkdir()
            shutil.copyfile(GARMIN_REFERENCE, skill / "assets" / "garmin-reference.json")
            output = directory / "workout.json"
            result = subprocess.run(
                [sys.executable, str(skill / "scripts" / "export_workout.py"),
                 "--input", str(FIXTURE), "--output", str(output)],
                cwd=directory, capture_output=True, text=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["duration_seconds"], 5400)
            self.assertEqual(json.loads(output.read_text())["workoutName"], "3x10 donderdag")

    def test_writes_downloadable_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "3x10.json"
            result = _run(FIXTURE, output)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["duration_seconds"], 5400)
            self.assertEqual(json.loads(output.read_text())["workoutName"], "3x10 donderdag")

    def test_preserves_the_reference_shape_for_zone2_regression(self):
        source = ROOT / "tests" / "fixtures" / "zone2-60min-workout.json"
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "zone2.json"
            result = _run(source, output)
            exported = json.loads(output.read_text())

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["duration_seconds"], 3600)
            self.assertEqual(exported["workoutId"], 100000001)
            self.assertEqual(exported["estimatedDistanceUnit"]["unitId"], None)
            self.assertEqual(exported["workoutSegments"][0]["workoutSteps"][2]["workoutSteps"][0]["stepId"], 300000003)

    def test_invalid_input_does_not_write_a_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "invalid.json"
            output = Path(temporary_directory) / "invalid-output.json"
            source.write_text(json.dumps({"schema_version": 1}))
            result = _run(source, output)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("workout.sport", result.stderr)
            self.assertFalse(output.exists())


def _run(source, output):
    return subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--input",
            str(source),
            "--output",
            str(output),
            "--reference",
            str(GARMIN_REFERENCE),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
