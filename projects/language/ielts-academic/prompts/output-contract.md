# Output Contract

The final Orchestrator output must contain:

- Run mode used and independence level
- Score profile and evidence basis
- Score confidence and unverified dimensions
- Skill priority ranking
- Adaptive 8-week plan
- Weekly time allocation by skill
- Daily training tasks in minimum, standard, and stretch modes
- Error priority map
- Regression checks
- Exam simulation strategy
- Weekly review prompt
- Risks to Overall 8.0 / each skill 7.5+

## Training Task Format

Every task must include:

| Field | Required content |
| --- | --- |
| Duration | Exact time range, such as 30 minutes or 90 minutes |
| Material type | Cambridge test, official sample, user essay, recording, transcript, error log, or vocabulary set |
| Expected output | Written answer, corrected answer, score profile update, recorded answer, annotated passage, or error-log entry |
| Review method | Self-check, descriptor-based review, answer-key analysis, pronunciation self-rating, or Orchestrator review |

## Missing Evidence Rule

If a dimension is not supported by evidence, label it as unverified and assign a diagnostic task.

## Replanning Rule

A weekly plan may change only when new evidence changes score confidence, target risk, workload feasibility, or regression status.
