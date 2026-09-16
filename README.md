# Garmin Workout Builder

This private ChatGPT/Codex plugin turns a planned cycling workout into Garmin Connect workout JSON. Import the generated file through the Chrome extension **Share your Garmin Connect workout**; this project does not connect to Garmin accounts or APIs.

## What it supports

- Warmup, intervals, recovery, cooldown, and single-level repeat blocks.
- FTP percentage ranges and steps with no power target.
- A short instruction in the generated ChatGPT summary; embedding it in Garmin waits for a proven reference export.
- Duration calculated from the authored steps, including repeat iterations.

## Run locally

Create an internal workout JSON using the contract in [workout-contract.md](skills/garmin-workout/references/workout-contract.md), then run:

```bash
python3 skills/garmin-workout/scripts/export_workout.py \
  --input workout.json \
  --output workout.garmin.json \
  --reference /path/to/working-garmin-export.json
```

The command prints the file path and calculated duration as JSON. It leaves no output file when validation fails. The installed private plugin has a Git-ignored `assets/garmin-reference.json` and uses that working export automatically when `--reference` is omitted.

## Validate

```bash
python3 -m unittest discover -s tests -v
python3 /Users/rutgerbakker/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

The test suite checks the 90-minute 3×10 reference workout, reference-template DTO mapping, no-target output, and the CLI failure boundary. The live acceptance test imports generated examples with the Chrome extension and re-exports them from Garmin Connect.
