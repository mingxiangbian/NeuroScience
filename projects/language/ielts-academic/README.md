# IELTS Academic

Goal: use real evidence to move toward IELTS Academic Overall 7.5. The per-skill floor remains unconfirmed until an external requirement is supplied.

This project has two layers:

1. Prompt system: reusable Orchestrator and subagent prompts for diagnosis, critique, calibration, and replanning.
2. Learning package: diagnostic evidence, one active learning unit, error regression tracking, event-triggered calibration, and settlement records.

## Static Reader

Serve this project with GitHub Pages or a local static server, then open `index.html`. It renders:

- 现在
- 单元
- 错误
- 证据
- 结算
- 档案
- 系统

The reader uses `site/ielts-data.json`, generated from the repository source files. It does not write back to GitHub, local files, or any backend.

## Recommended Flow

1. Start with `diagnostics/diagnostic-input-template.md`.
2. Choose a run mode in `prompts/run-modes.md`.
3. Use `prompts/orchestrator.md` to coordinate subagent outputs.
4. Update the structured counterparts only from real evidence: `diagnostics/score-profile.json`, `diagnostics/score-history.json`, `diagnostics/error-log.json`, `plans/unit-ledger.json`, and `plans/calibration-events.json`.
5. Follow `plans/event-driven-study-system.md`. Keep `activeUnit` at `null` until the user explicitly begins a unit.
6. Track recurring issues in `diagnostics/error-log-template.md`, `diagnostics/error-log.json`, and `errors/regression-check-template.md`.
7. Record durable learning insights in `notes/` and freeform dated reflection in `journal/`.
8. Run `node projects/language/ielts-academic/scripts/build-ielts-data.mjs` before reviewing the static reader or committing evidence updates.

## Run Modes

- manual multi-session mode: recommended when a diagnostic, regression, mock, or target decision needs true agent isolation.
- single-session simulation mode: useful for low-stakes tactical review. It is not independent and any critique must be labeled as simulated.

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
- `plans/event-driven-study-system.md`
- `plans/unit-ledger.json`
- `plans/calibration-events.json`
- `notes/README.md`
- `journal/README.md`
- `scripts/build-ielts-data.mjs`
- `site/ielts-data.json`
- `index.html`
- `validation/dry-run-test-cases.md`
