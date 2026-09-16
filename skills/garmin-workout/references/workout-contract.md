# Internal workout contract v1

The generator accepts a single JSON object. It deliberately describes a workout without Garmin DTO names, identifiers, or API data.

```json
{
  "schema_version": 1,
  "sport": "cycling",
  "name": "Workout title",
  "description": "Optional workout note",
  "ftp_watts": 300,
  "steps": []
}
```

`description` and `ftp_watts` are optional. `ftp_watts` never changes a Garmin target; targets remain percentages because Garmin Connect applies the rider's configured FTP.

Executable steps require `type`, `duration_seconds`, and `target`.

```json
{
  "type": "interval",
  "duration_seconds": 180,
  "instructions": "Ride hard but controlled.",
  "target": {
    "type": "ftp_percent",
    "min_percent": 110,
    "max_percent": 120
  }
}
```

Supported executable types are `warmup`, `interval`, `recovery`, and `cooldown`. A target is either `{ "type": "none" }` or an `ftp_percent` range. Durations are positive whole seconds and instructions are optional.

```json
{
  "type": "repeat",
  "iterations": 5,
  "steps": []
}
```

Repeat blocks may contain executable steps only. A recovery after the final effort is repeated unless it is represented outside the repeat block.
