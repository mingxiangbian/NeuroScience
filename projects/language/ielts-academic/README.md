# IELTS Academic

Goal: use real evidence to move toward IELTS Academic Overall 7.5. The current 20-day paper-test sprint uses 6.5 as an operational safety floor; this is a training target, not a claim that every application has the same official minimum.

Current exam boundary: the written paper is on 2026-08-29. The speaking time is not assigned yet; the registration email gives the usual 2026-08-22 to 2026-09-05 window and says the admission ticket is normally released no later than eight days before the written test. The sprint therefore makes speaking exam-ready by 2026-08-21 and replans the 48 hours around the actual appointment when it appears.

Day 1 remains a historical half-day record with 270 focused minutes. From 2026-08-15, the base day is 225 focused minutes: daily speaking plus one Writing or Listening priority. Conditional work can raise a day to about 300 minutes, but the hard ceiling is 420 minutes. Unfinished priority work rolls forward without stacking, while maintenance and optional work can be dropped without make-up debt.

This project has two layers:

1. Prompt system: reusable Orchestrator and subagent prompts for diagnosis, critique, calibration, and replanning.
2. Learning package: diagnostic evidence, one active learning unit, error regression tracking, event-triggered calibration, settlement records, and a deadline-bound exam sprint.

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
6. When an exam date is fixed, follow `plans/exam-sprint.json` for daily maintenance and checkpoints while keeping only one adaptive repair unit active.
7. Track recurring issues in `diagnostics/error-log-template.md`, `diagnostics/error-log.json`, and `errors/regression-check-template.md`.
8. Record durable learning insights in `notes/` and freeform dated reflection in `journal/`.
9. Run `node projects/language/ielts-academic/scripts/build-ielts-data.mjs` before reviewing the static reader or committing evidence updates.

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
- `plans/exam-sprint.json`
- `plans/unit-ledger.json`
- `plans/calibration-events.json`
- `notes/README.md`
- `journal/README.md`
- `scripts/build-ielts-data.mjs`
- `site/ielts-data.json`
- `index.html`
- `validation/dry-run-test-cases.md`
