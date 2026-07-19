# Dry-Run Test Cases

## Missing-information dry run

Input: target score only.

Expected behavior: Orchestrator preserves an unverified profile, proposes one diagnostic unit, keeps it suggested, and does not invent a personal weakness profile.

## Partial-input dry run

Input: Listening and Reading raw scores, no Writing samples, transcript-only Speaking evidence.

Expected behavior: verified skills are analyzed; one highest-value missing dimension receives a suggested diagnostic unit; Speaking pronunciation and real-time fluency remain unverified.

## Not-started dry run

Input: the source ledger has a suggested D1 unit and `activeUnit: null`.

Expected behavior: the Reader says learning has not started and does not render D1 as active, overdue, or partially complete.

## Single-session mode dry run

Input: user selects single-session simulation mode.

Expected behavior: output states that cross-agent critique is simulated and not independent.

## Output-contract dry run

Input: any Orchestrator plan.

Expected behavior: every unit includes type, first action, material type, expected artifact, review method, and settlement criteria. Duration is required only for diagnostics and mocks.

## Fixed-error evidence dry run

Input: an error is marked `fixed` with fewer than three independent clean sample references.

Expected behavior: schema validation fails with `insufficient_fix_evidence`.
