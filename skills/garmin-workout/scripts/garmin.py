"""Transform an internal workout model through a proven Garmin workout export."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from workout import duration_seconds


class GarminReferenceError(ValueError):
    """Raised when a supplied Garmin export cannot act as an export template."""


def to_garmin_workout(workout: Dict[str, Any], reference: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a workout to a complete, working Garmin Connect export.

    The output deliberately keeps the reference's root and DTO fields intact.
    The Chrome extension currently sends most of those fields to Garmin due to
    its non-recursive, index-based cleanup implementation.
    """
    segment = _cycling_segment(reference)
    builder = _StepBuilder(segment["workoutSteps"])
    result = copy.deepcopy(reference)

    result["workoutName"] = workout["name"]
    result["description"] = reference.get("description")
    result["estimatedDurationInSecs"] = duration_seconds(workout)
    result["workoutSegments"][0]["workoutSteps"] = [builder.step(step) for step in workout["steps"]]
    return result


def _cycling_segment(reference: Any) -> Dict[str, Any]:
    if not isinstance(reference, dict):
        raise GarminReferenceError("reference: must be a Garmin workout object")
    sport_type = reference.get("sportType")
    if not isinstance(sport_type, dict) or sport_type.get("sportTypeKey") != "cycling":
        raise GarminReferenceError("reference.sportType: must be cycling")
    segments = reference.get("workoutSegments")
    if not isinstance(segments, list) or len(segments) != 1 or not isinstance(segments[0], dict):
        raise GarminReferenceError("reference.workoutSegments: must contain one cycling segment")
    steps = segments[0].get("workoutSteps")
    if not isinstance(steps, list) or not steps:
        raise GarminReferenceError("reference.workoutSegments[0].workoutSteps: must be non-empty")
    return segments[0]


class _StepBuilder:
    def __init__(self, reference_steps: List[Dict[str, Any]]) -> None:
        self.step_order = 0
        self.repeat_count = 0
        self.top_level_templates = _templates_by_type(reference_steps)
        self.repeat_template = self.top_level_templates.get("repeat")
        if self.repeat_template is None:
            raise GarminReferenceError("reference: needs a RepeatGroupDTO template")
        children = self.repeat_template.get("workoutSteps")
        if not isinstance(children, list) or not children:
            raise GarminReferenceError("reference repeat template: must contain executable steps")
        self.repeat_child_templates = _templates_by_type(children)

    def step(self, step: Dict[str, Any], group_number: Optional[int] = None) -> Dict[str, Any]:
        if step["type"] == "repeat":
            return self.repeat(step)

        templates = self.repeat_child_templates if group_number is not None else self.top_level_templates
        if group_number is None and step["type"] not in templates:
            templates = {**self.repeat_child_templates, **self.top_level_templates}
        result = _template_for(templates, step["type"])
        self.step_order += 1
        result["stepOrder"] = self.step_order
        result["childStepId"] = group_number
        result["endConditionValue"] = float(step["duration_seconds"])
        # The reference has null step descriptions. Preserve that proven DTO
        # value instead of emitting unverified arbitrary text into Garmin.
        result["description"] = result.get("description")
        _apply_target(result, step["target"])
        return result

    def repeat(self, step: Dict[str, Any]) -> Dict[str, Any]:
        self.repeat_count += 1
        if self.repeat_count > 1:
            raise GarminReferenceError(
                "workout.steps: one repeat block is supported until a multi-repeat Garmin export is verified"
            )
        result = copy.deepcopy(self.repeat_template)
        self.step_order += 1
        result["stepOrder"] = self.step_order
        group_number = result.get("childStepId")
        if not isinstance(group_number, int):
            raise GarminReferenceError("reference repeat template: childStepId must be an integer")
        result["numberOfIterations"] = step["iterations"]
        result["endConditionValue"] = float(step["iterations"])
        result["workoutSteps"] = [self.step(child, group_number) for child in step["steps"]]
        return result


def _templates_by_type(steps: List[Any]) -> Dict[str, Dict[str, Any]]:
    templates: Dict[str, Dict[str, Any]] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_type = step.get("stepType")
        if not isinstance(step_type, dict):
            continue
        key = step_type.get("stepTypeKey")
        if isinstance(key, str) and key not in templates:
            templates[key] = step
    return templates


def _template_for(templates: Dict[str, Dict[str, Any]], step_type: str) -> Dict[str, Any]:
    template = templates.get(step_type)
    if template is None:
        raise GarminReferenceError(f"reference: lacks a '{step_type}' step template")
    return copy.deepcopy(template)


def _apply_target(step: Dict[str, Any], target: Dict[str, Any]) -> None:
    if target["type"] == "none":
        step["targetType"] = None
        step["targetValueOne"] = None
        step["targetValueTwo"] = None
        step["targetValueUnit"] = None
        step["zoneNumber"] = None
        return

    if not isinstance(step.get("targetType"), dict) or not isinstance(step.get("targetValueUnit"), dict):
        raise GarminReferenceError("reference step: needs a power target template")
    step["targetValueOne"] = target["min_percent"]
    step["targetValueTwo"] = target["max_percent"]
