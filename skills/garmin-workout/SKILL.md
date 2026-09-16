---
name: garmin-workout
description: Create a cycling workout from natural language and return a validated Garmin Connect JSON file that the Share your Garmin Connect workout Chrome extension can import. Use when the user asks for a Garmin cycling workout, intervals, an opener, or an importable Garmin workout file.
---

# Garmin cycling workout workflow

Use this skill only for cycling. Plan the training from the user's request, but never hand-write Garmin DTO fields or IDs. Always create the internal workout document below and call the exporter.

## Ask before exporting

Ask one concise follow-up question when a missing fact would materially change the structure: for example a repeat count, work or recovery duration, target intensity, or whether a recovery follows the final repetition. Do not invent an FTP value. An FTP value is optional for exporting percentage targets, but required if you state the equivalent watts in the user-facing summary.

## Internal workout document

Create JSON matching this contract, then write it to a temporary `input.json` file:

```json
{
  "schema_version": 1,
  "sport": "cycling",
  "name": "5x3 min VO2max",
  "description": "Optional short workout note.",
  "ftp_watts": 300,
  "steps": [
    {
      "type": "warmup",
      "duration_seconds": 900,
      "target": {"type": "ftp_percent", "min_percent": 50, "max_percent": 70}
    },
    {
      "type": "repeat",
      "iterations": 5,
      "steps": [
        {
          "type": "interval",
          "duration_seconds": 180,
          "target": {"type": "ftp_percent", "min_percent": 110, "max_percent": 120}
        },
        {
          "type": "recovery",
          "duration_seconds": 180,
          "target": {"type": "none"}
        }
      ]
    },
    {
      "type": "cooldown",
      "duration_seconds": 600,
      "target": {"type": "none"}
    }
  ]
}
```

An executable step must have `type`, `duration_seconds`, and `target`. Supported types are `warmup`, `interval`, `recovery`, and `cooldown`. Keep optional instruction text in the user-facing workout summary; the current Garmin reference has null step descriptions, so the exporter deliberately preserves that format. A `repeat` has a positive integer `iterations` and a non-empty `steps` list; repeat blocks cannot be nested in v1.

Use `{ "type": "none" }` for a step without a power target. Use `{ "type": "ftp_percent", "min_percent": number, "max_percent": number }` for a percentage-of-FTP range. Keep all durations in whole seconds.

## Export

Run the bundled script after creating the internal document:

```bash
python3 skills/garmin-workout/scripts/export_workout.py \
  --input /tmp/input.json \
  --output /tmp/garmin-workout.json
```

If the exporter returns an error, correct only the internal workout document and run it again. Never fix the generated Garmin JSON by hand.

The installed private plugin contains `assets/garmin-reference.json`, a working Garmin export supplied by the user. The exporter loads it by default. Do not display, return, modify, or add this private reference to version control.

Return the generated `.json` file as a download, followed by a compact summary of the workout and its computed total duration. Do not claim that the file was imported into Garmin unless the user has actually confirmed the Chrome-extension import.

## Boundaries

- Do not use Garmin credentials, APIs, scraping, calendar scheduling, or account data.
- Do not add running, cadence, heart-rate, distance, ramp, open-ended, or nested-repeat steps.
- Do not generate or clear Garmin IDs. The exporter clones the locally configured, working Garmin reference export and changes only proven workout fields.
