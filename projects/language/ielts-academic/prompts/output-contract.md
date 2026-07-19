# Output Contract

The final Orchestrator output must contain:

- Run mode used and independence level
- Score profile and evidence basis
- Score confidence and unverified dimensions
- Skill priority ranking
- Active unit state, including an explicit `not-started` state when applicable
- One suggested next unit with evidence-based reason
- First action, expected artifact, review method, and settlement criteria
- Error priority map
- Regression checks
- Calibration trigger update
- Exam simulation strategy when mock evidence or an external deadline requires it
- Risks to Overall 7.5 and any unconfirmed per-skill requirement

## Unit Format

Every unit must include:

| Field | Required content |
| --- | --- |
| Type | diagnostic, repair, mock, or calibration |
| First action | The first observable action, not a multi-step backlog |
| Material type | Cambridge test, official sample, user essay, recording, transcript, error log, or vocabulary set |
| Expected artifact | Original sample, corrected answer, score profile event, recording, annotated passage, error update, or decision record |
| Review method | Self-check, descriptor-based review, answer-key analysis, pronunciation self-rating, or Orchestrator review |
| Settlement criteria | Evidence that must exist before the unit can be marked settled |

Duration is required only for diagnostic units, mock units, and tasks whose exam value depends on timing. Do not use duration to settle ordinary repair work.

## Missing Evidence Rule

If a dimension is not supported by evidence, label it as unverified and propose one diagnostic unit. Do not mark the unit active until the user begins it.

## Recalibration Rule

Change the active or suggested unit only when new evidence changes score confidence, the high-impact error set, regression status, target stability, or an external hard deadline.
