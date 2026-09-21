# Garmin export evidence

The exporter is based on the working `3x10 donderdag.json` Garmin Connect cycling export supplied for this project. The bundled public template replaces personal data, timestamps, image URLs, and workout/account/step identifiers with synthetic values. Structural type and unit IDs and repeat relationships are preserved. A live import of this sanitized template has not yet been verified.

Confirmed from that export:

- Cycling is represented by `sportTypeId: 2` and `sportTypeKey: "cycling"`.
- Time uses condition `2` / `time`, with seconds in `endConditionValue`.
- Power percentage targets use target type `2` / `power.zone` and unit `253` / `percent`.
- Warmup, cooldown, interval, recovery, and repeat have IDs 1, 2, 3, 4, and 6 respectively.
- Repeat groups are `RepeatGroupDTO`; their iteration condition is `7` / `iterations`.
- The reference's 20-minute warmup, 3 × (10-minute interval + 5-minute recovery), 15-minute block, and 10-minute cooldown calculate to the stored 5,400 seconds.

The Chrome extension imports a selected JSON document by POSTing it to Garmin Connect's workout endpoint. Its intended cleanup removes account and calculated fields, but its current published source loops over the cleanup list incorrectly. It also clears only top-level `stepId`s. The exporter therefore clones the configured reference template, preserves its complete DTO shape and identifiers, and changes only the workout fields proven by the reference.

The reference did not include a no-target step or a non-null step description. The exporter maps a no-target internal step to the target DTO fields set to `null`; this mapping requires an import smoke test before it is treated as Garmin-proven behavior. Step instructions remain in the ChatGPT summary until a reference with a non-null description is imported successfully. The reference proves one repeat group only, so the exporter rejects multiple repeat groups instead of inventing new child IDs.
