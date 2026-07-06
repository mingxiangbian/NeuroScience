# Dry-Run Test Cases

## Missing-information dry run

Input: target score and timeline only.

Expected behavior: Orchestrator outputs diagnostic tasks and does not invent a personal weakness profile.

## Partial-input dry run

Input: Listening and Reading raw scores, no Writing samples, transcript-only Speaking evidence.

Expected behavior: verified skills are analyzed; Writing receives diagnostic tasks; Speaking pronunciation and real-time fluency are marked unverified.

## Low-workload dry run

Input: user completes below 6 focused hours per week for two consecutive weeks.

Expected behavior: Study Load Planner warns that Overall 8.0 is not realistic as an 8-week operating target and recommends a staged target.

## Single-session mode dry run

Input: user selects single-session simulation mode.

Expected behavior: output states that cross-agent critique is simulated and not independent.

## Output-contract dry run

Input: any Orchestrator plan.

Expected behavior: every task includes duration, material type, expected output, and review method.
