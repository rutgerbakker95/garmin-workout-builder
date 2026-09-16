"""Validate the Garmin Workout Builder's transport-independent workout model."""

from __future__ import annotations

from typing import Any, Dict, List


class WorkoutValidationError(ValueError):
    """Raised when an internal workout document cannot be exported safely."""


EXECUTABLE_TYPES = {"warmup", "interval", "recovery", "cooldown"}


def validate_workout(workout: Any) -> Dict[str, Any]:
    """Return a normalized v1 cycling workout or raise a path-specific error."""
    document = _object(workout, "workout")
    _exact_keys(document, {"schema_version", "sport", "name", "description", "ftp_watts", "steps"}, "workout")

    if document.get("schema_version") != 1:
        _error("workout.schema_version", "must be 1")
    if document.get("sport") != "cycling":
        _error("workout.sport", "must be 'cycling'")

    normalized: Dict[str, Any] = {
        "schema_version": 1,
        "sport": "cycling",
        "name": _text(document.get("name"), "workout.name", required=True),
        "steps": _steps(document.get("steps"), "workout.steps", allow_repeat=True),
    }

    if "description" in document and document["description"] is not None:
        normalized["description"] = _text(document["description"], "workout.description")
    else:
        normalized["description"] = None

    if "ftp_watts" in document and document["ftp_watts"] is not None:
        normalized["ftp_watts"] = _positive_number(document["ftp_watts"], "workout.ftp_watts")
    else:
        normalized["ftp_watts"] = None

    return normalized


def duration_seconds(workout: Dict[str, Any]) -> int:
    """Calculate duration from the authored steps, including repeat iterations."""
    return sum(_step_duration(step) for step in workout["steps"])


def _step_duration(step: Dict[str, Any]) -> int:
    if step["type"] == "repeat":
        return step["iterations"] * sum(_step_duration(child) for child in step["steps"])
    return step["duration_seconds"]


def _steps(value: Any, path: str, allow_repeat: bool) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _error(path, "must be a non-empty array")
    return [_step(step, f"{path}[{index}]", allow_repeat) for index, step in enumerate(value)]


def _step(value: Any, path: str, allow_repeat: bool) -> Dict[str, Any]:
    step = _object(value, path)
    step_type = step.get("type")

    if step_type == "repeat":
        if not allow_repeat:
            _error(f"{path}.type", "nested repeat blocks are not supported")
        _exact_keys(step, {"type", "iterations", "steps"}, path)
        return {
            "type": "repeat",
            "iterations": _positive_integer(step.get("iterations"), f"{path}.iterations"),
            "steps": _steps(step.get("steps"), f"{path}.steps", allow_repeat=False),
        }

    if step_type not in EXECUTABLE_TYPES:
        _error(f"{path}.type", "must be warmup, interval, recovery, cooldown, or repeat")

    _exact_keys(step, {"type", "duration_seconds", "instructions", "target"}, path)
    normalized: Dict[str, Any] = {
        "type": step_type,
        "duration_seconds": _positive_integer(step.get("duration_seconds"), f"{path}.duration_seconds"),
        "target": _target(step.get("target"), f"{path}.target"),
    }
    if "instructions" in step and step["instructions"] is not None:
        normalized["instructions"] = _text(step["instructions"], f"{path}.instructions")
    else:
        normalized["instructions"] = None
    return normalized


def _target(value: Any, path: str) -> Dict[str, Any]:
    target = _object(value, path)
    target_type = target.get("type")
    if target_type == "none":
        _exact_keys(target, {"type"}, path)
        return {"type": "none"}
    if target_type == "ftp_percent":
        _exact_keys(target, {"type", "min_percent", "max_percent"}, path)
        minimum = _positive_number(target.get("min_percent"), f"{path}.min_percent")
        maximum = _positive_number(target.get("max_percent"), f"{path}.max_percent")
        if minimum > maximum:
            _error(path, "min_percent must not exceed max_percent")
        return {"type": "ftp_percent", "min_percent": minimum, "max_percent": maximum}
    _error(f"{path}.type", "must be 'none' or 'ftp_percent'")


def _object(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        _error(path, "must be an object")
    return value


def _exact_keys(value: Dict[str, Any], allowed: set, path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        _error(path, f"contains unsupported field '{unknown[0]}'")


def _positive_integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _error(path, "must be a positive integer")
    return value


def _positive_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        _error(path, "must be a positive number")
    return float(value)


def _text(value: Any, path: str, required: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        requirement = "a non-empty string" if required else "a non-empty string when supplied"
        _error(path, f"must be {requirement}")
    return value.strip()


def _error(path: str, message: str) -> None:
    raise WorkoutValidationError(f"{path}: {message}")
