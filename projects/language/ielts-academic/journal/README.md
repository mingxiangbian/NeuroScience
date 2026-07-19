# IELTS Journal

The journal is for dated reflection: evidence quality, confidence, friction, breakthroughs, and exam-readiness concerns. Formal unit state and settlement decisions live in `plans/unit-ledger.json` and `plans/calibration-events.json`.

Journal entries do not feed Orchestrator planning decisions unless the same information is copied into the structured review files.

## Frontmatter Contract

```yaml
---
date: 2026-07-06
related_errors: [E001]
related_notes: [writing/task-2-argument-development]
---
```

`related_errors` must point to IDs in `diagnostics/error-log.json`. `related_notes` must point to note IDs under `notes/`.
