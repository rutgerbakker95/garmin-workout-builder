#!/usr/bin/env python3
"""Validate an internal workout document and write an importable Garmin JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, List, Optional

from garmin import GarminReferenceError, to_garmin_workout
from workout import WorkoutValidationError, duration_seconds, validate_workout


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Internal workout JSON document")
    parser.add_argument("--output", required=True, type=Path, help="Garmin JSON output file")
    parser.add_argument(
        "--reference",
        type=Path,
        default=_default_reference_path(),
        help="Working Garmin JSON export used as the private output template",
    )
    args = parser.parse_args(argv)

    try:
        source = _read_json(args.input)
        workout = validate_workout(source)
        reference = _read_json(args.reference)
        garmin_workout = to_garmin_workout(workout, reference)
        _write_json(args.output, garmin_workout)
    except (OSError, json.JSONDecodeError, WorkoutValidationError, GarminReferenceError) as error:
        print(f"Export failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "file": str(args.output.resolve()),
        "workout_name": workout["name"],
        "duration_seconds": duration_seconds(workout),
    }))
    return 0


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _default_reference_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "garmin-reference.json"


def _write_json(path: Path, value: Any) -> None:
    if path.suffix.lower() != ".json":
        raise WorkoutValidationError("output: filename must end in .json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
