# Experiment Artifact and Retention Index

Date: 2026-09-01
Purpose: canonical navigation and deletion boundary for the emotion-recognition project

This index organizes the evidence without moving hash-bound files. Similar names do not imply duplication:
protocol, config, run claim, run output, verification, completion, fold output, and private parameter artifacts
serve different audit roles.

## Canonical project entry points

- [Evidence log](../../evidence-log.md): append-only experiment facts and claims.
- [Research roadmap](../../research-roadmap.md): research questions, dependencies, and current status.
- [HANDOFF](HANDOFF.md): latest execution state and hashes.
- [Phase A closeout](protocols/dec-so-phase-a-closeout-v1.md).
- [Phase B decision](protocols/dec-so-phase-b-representation-v1.md).
- [Phase C final scope](protocols/dec-phase-c-final-scope-and-closeout-v1.md).
- [Phase C release acceptance](../../forum-topic-emotion-web/docs/release-acceptance.md).
- [Phase C reproducibility package](../../forum-topic-emotion-web/docs/reproducibility-package.md).

Current private Phase C claims and reports remain local under:

```text
forum-topic-emotion-web/private/reports/
```

They are Git-ignored by design. The current files are `final-claims-2026-09-01.md`,
`phase-c-final-closeout-2026-09-01.md`, and
`phase-c1-bounded-runtime-discourse-report-2026-09-01.md`. The 2026-08-31 reports remain historical snapshots.

## Retention classes

### A. Public, tracked, append-only evidence

Keep:

- Protocols, amendments, incidents, correction notes, and decision records.
- Frozen configs and public run/verification/completion summaries.
- Runner, verifier, consumer, and test source used to create formal artifacts.
- Environment locks, model manifests, schema contracts, and report tables.
- Failed, stopped, blocked, and Not-executed records as well as successful results.

### B. Private or large reproducibility evidence

Keep locally even when Git-ignored:

- Raw/private data, annotations, sealed inputs, logits, probabilities, representations, bootstrap arrays, and predictions.
- Checkpoints, model snapshots, LoRA adapters, classification heads, Router/scaler parameters, and feature caches.
- `plan.json`, `run-claim.json`, `run.json`, `verification.json`, completion/failure/audit files, and source manifests.
- Frozen source/code archives, phase receipts, transfer records, runtime/process events, system samples, stdout, dashboards, and databases.
- Original failed attempts and later recovery attempts.

Ignored does not mean disposable. These files are excluded for privacy, licensing, size, or local-runtime reasons.

### C. Rebuildable local runtime

Keep while the project remains runnable:

- `forum-topic-emotion-web/.venv/` and its `requirements-lock.txt`.
- Model download metadata inside model snapshots.
- Local access token and dispatcher/database sidecars managed by the running application.

Do not manually delete SQLite WAL/SHM files or experiment locks. Let the owning application close/checkpoint them.

### D. Regenerable clutter

Safe to remove when no process is using it:

- Source-tree `__pycache__/`, `.pyc`, and `.pyo` outside frozen archives and `.venv`.
- `.pytest_cache/`.
- `.DS_Store`.
- Explicit editor swap/backup/temp files after confirming they are not experiment outputs.

## Previous reproduction tracks

The earlier reproduction results remain part of the project evidence and were not removed:

| Track | Canonical tree | Preserve |
| --- | --- | --- |
| TweetEval | `experiments/tweeteval-emotion/` | TF-IDF, SVM, RoBERTa, frozen test gate, error analysis, requirements and run summaries |
| GoEmotions | `experiments/goemotions/` | TF-IDF/BERT/Qwen/LoRA runs, parser controls, test gate, disagreement and annotation audits |
| Weibo EClass | `experiments/weibo-eclass/` | task contracts, context/reasoning runs, batch equivalence, cost gates, test gate, error analysis |
| Forum context | `experiments/forum-context/` | dataset construction, deduplication, annotation/adjudication and public-source audits |
| Stack Overflow mainline | `experiments/stack-overflow-emotion-gold/model-comparison/`, `test-gate/`, `error-analysis/`, `post-test-analysis/` | EXP-050–057 configs, seeds, predictions, test closure, errors and thesis tables |

## Phase A: EXP-058–068

Preserve the complete evidence chain under:

```text
oof-router/configs/
oof-router/runs/
oof-router/private/
protocols/exp-058* through protocols/exp-068*
```

Key parameter/result identities include:

- EXP-058 fold manifests, fold-level M1/M3 logits, batch order, checkpoint/adapter/head identities.
- EXP-059 `cross-fitted-calibration.npz` and calibration/risk/bootstrap outputs.
- EXP-060 `router-oof.npz` and its nested OOF contract.
- EXP-061/062 `paired-oof.npz`, partition contracts, fold outputs, and Router directories.
- EXP-063 replication synthesis run and verification.
- EXP-064 seed-42 inference `bundle.json` and `router-parameters.npz`.
- EXP-065 projection manifest and probability replay.
- EXP-066 runtime manifest, parity output, frozen sources, and completion.
- EXP-067 failed/incomplete benchmark attempts.
- EXP-068 phase synthesis and completion.

Do not remove seed-local calibration copies: they are the exact snapshots bound to prospective replications.

## Phase B: EXP-069–075

Preserve the entire:

```text
phase-b-representation/configs/
phase-b-representation/runs/
phase-b-representation/private/
```

Required evidence includes extraction/probe matrices, fold NPZ files, `representations.npy`, row contracts,
probe and prediction manifests, bootstrap/control outputs, geometry and ablation results, and all independent
verification/completion files. Keep the EXP-071 formal failure and its diagnostic/recovery lineage. EXP-073 is
optional and Not executed; do not invent a run directory for it.

## Phase C: EXP-076–086

Keep all Phase C protocols, including protocols for EXP-078 and EXP-080, which remain Not executed.
Keep the original and corrected EXP-085 protocols separately.

The hash-bound private validation tree must remain at its current path:

```text
forum-topic-emotion-web/private/validation/exp-076/ through exp-086/
```

Important terminal lineage:

- EXP-076 attempts 1/2 failures and attempt 3 Verified source closure.
- EXP-077 Stopped resource result and Passed audit.
- EXP-079 attempts 1–3, including observer correction and resource stops.
- EXP-081 old closeout attempts.
- EXP-082 Completed/Passed short diagnostic.
- EXP-083 Stopped with Passed record audit.
- EXP-084 Completed/Passed transfer prototype.
- EXP-085 attempt 1 Failed and attempt 2 Passed.
- EXP-086 Completed/Passed.
- EXP-078 and EXP-080 protocols with `Not executed` status.

For EXP-085/086, retain at least `plan.json`, `run-claim.json`, `run.json`, `verification.json`,
`frozen-code.tar.gz`, phase receipts, transfers, runtime/process events, system samples, results, dashboards,
the sealed database, and EXP-086 source progress. These files are complementary, not redundant.

## Context/C2 paused branch

Preserve the Blocked/no-result source preflight:

- [REPORT](context-recovery/runs/data-so-context-recovery-v2/source-preflight/attempt-1/REPORT.md)
- [run.json](context-recovery/runs/data-so-context-recovery-v2/source-preflight/attempt-1/run.json)

It records why no download, context recovery, C2 construction, model forward, or training occurred. It is a
negative readiness result, not temporary output.

## Similar-looking files that must not be deduplicated

| Pair or group | Distinct role |
| --- | --- |
| Development config vs run `frozen-sources/config.json` | Editable entry versus actual execution identity |
| `run-claim.json` vs `run.json` | Startup/environment claim versus terminal producer record |
| Run vs verification | Producer output versus independent recomputation |
| Preflight vs formal run | Executability gate versus result-producing execution |
| Failed attempt vs corrected attempt | Historical failure versus later version; correction does not rewrite history |
| Original Failed verifier vs recovery Passed verifier | Original outcome versus bounded consumer/metadata recovery |
| Fold output vs synthesis | Per-fold reproducibility versus aggregate conclusion |
| Public aggregate vs private arrays | Citation surface versus numerical replay inputs |
| Phase receipts vs final results | Physical staged execution versus merged user-facing result |
| Transfer vs final counters | M1/token provenance versus combined cost accounting |
| Database vs result/dashboard export | Sealed source of record versus reviewed projection |
| Samples, process events, runtime events | System resources, process identity, and stage semantics |

## Cleanup record

On 2026-09-01, after checkpoint commit `2de25f4` was pushed, the cleanup removed only:

- 56 source-tree `__pycache__`/`.pytest_cache` directories outside `.venv` and `private`.
- 12 `.DS_Store` files.
- Approximately 20,372 KiB of regenerable local clutter.

No protocol, config, source, test, dataset, model, checkpoint, parameter, run, verification, failure, report,
database, archive, log, or private experiment artifact was moved or deleted.
