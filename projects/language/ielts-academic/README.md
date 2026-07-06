# IELTS Academic

Goal: move from an estimated IELTS 6.0-6.5 baseline toward Overall 8.0, with each skill 7.5+.

This project has two layers:

1. Prompt system: reusable Orchestrator and subagent prompts for diagnosis, critique, calibration, and replanning.
2. Learning package: diagnostic templates, adaptive 8-week plan, daily flexible training, error tracking, and validation checklists.

## Static Reader

Open `index.html` to browse the v2 project reader. It renders:

- Dashboard
- 8-week swimlane
- Errors board
- Notes
- Journal
- Prompt library
- Validation status

The reader uses `site/ielts-data.json`, generated from the repository source files. It does not write back to GitHub, local files, or any backend.

## Recommended Flow

1. Start with `diagnostics/diagnostic-input-template.md`.
2. Choose a run mode in `prompts/run-modes.md`.
3. Use `prompts/orchestrator.md` to coordinate subagent outputs.
4. Fill the human templates and update the structured counterparts: `diagnostics/score-profile.json`, `diagnostics/score-history.json`, `diagnostics/error-log.json`, and `plans/checkpoint-status.json`.
5. Follow `plans/8-week-diagnostic-driven-plan.md`, adjusting weekly allocation through `plans/checkpoint-rules.md`.
6. Track recurring issues in `diagnostics/error-log-template.md`, `diagnostics/error-log.json`, and `errors/regression-check-template.md`.
7. Record durable learning insights in `notes/` and freeform dated reflection in `journal/`.
8. Run `node projects/language/ielts-academic/scripts/build-ielts-data.mjs` before reviewing the static reader or committing weekly updates.

## Run Modes

- manual multi-session mode: recommended for Week 1 baseline, Week 4 target checkpoint, Week 6 correction, and final exam strategy. This mode gives each subagent an isolated context and is the only mode that supports real agent independence.
- single-session simulation mode: useful for quick daily planning or low-stakes review. It is not independent and any critique must be labeled as simulated.

## Scoring Caution

LLM examiner scores are advisory. They must be descriptor-anchored, confidence-labeled, and calibrated with known-score or official sample material when available. Do not treat them as official IELTS scores.

## Key Files

- `prompts/orchestrator.md`
- `prompts/run-modes.md`
- `prompts/interaction-protocol.md`
- `prompts/output-contract.md`
- `prompts/calibration-and-validation.md`
- `diagnostics/score-profile-template.md`
- `diagnostics/score-profile.json`
- `diagnostics/score-history.json`
- `diagnostics/error-log.json`
- `plans/8-week-diagnostic-driven-plan.md`
- `plans/checkpoint-rules.md`
- `plans/checkpoint-status.json`
- `notes/README.md`
- `journal/README.md`
- `scripts/build-ielts-data.mjs`
- `site/ielts-data.json`
- `index.html`
- `validation/dry-run-test-cases.md`
