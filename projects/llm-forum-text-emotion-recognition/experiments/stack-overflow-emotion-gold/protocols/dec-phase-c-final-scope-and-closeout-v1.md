# DEC-PHASE-C-FINAL-SCOPE-AND-CLOSEOUT-V1

Date: 2026-09-01
Status: Frozen decision
Applies to: Phase C / Phase C.1 of the local forum-topic emotion website
Decision authority: user-approved project closeout

## Decision

Phase C is closed under the following final scope:

> Build a local research website for English technical-forum topic emotion analysis and verify, under frozen finite workloads, its staged routing workflow, source traceability, bounded process/resource handling, and one second-forum source-to-result chain.

Lifecycle and outcome are recorded separately:

| Scope | Lifecycle | Outcome |
| --- | --- | --- |
| Phase C.1 | Closed | Verified Pass within the registered bounded workload |
| Phase C | Closed | Completed within bounded local research scope |

The final system tier is:

> **Verified bounded local research prototype with two-source service portability.**

中文：**经过验证的有界本地研究原型，并完成两个技术论坛来源的服务链路迁移。**

“Two-source service portability” means that the same frozen service contract completed a no-gold source-to-result chain on one reviewed Discourse category prefix. It does not mean cross-domain predictive generalization.

## Included final scope

- Local loopback-only FastAPI and SQLite website.
- File upload, Stack Overflow Question Cohort, and reviewed Python Help Discourse adapters.
- Frozen M1-only, Research, and Demo-budget modes.
- Staged M1 prepass and independent M3 replay with same-job transfer accounting.
- Source, input hash, prediction, aggregate, cost, process-exit, and resource evidence.
- Fixed finite-load acceptance on the current 16 GiB machine.
- One formal, anonymous, no-gold Discourse run capped at 400 accepted posts.
- Local-only documentation, reproducibility references, release QA, and defense snapshots.

## Deferred outside the closed scope

The following are future tracks, not missing results inside the closed Phase C scope:

- External-gold predictive generalization, including CancerEmo or JIRA.
- Stack Overflow context recovery and C2 matched ablation.
- Long-running soak, production SLA, multi-user concurrency, restart/failure-recovery SLOs.
- Public deployment, internet exposure, or production security certification.
- Commercial redistribution or a new content-licensing opinion.
- A matched causal experiment claiming that staged residence repaired the earlier memory failures.
- New model training, Router tuning, cutoff adjustment, SAE, or another forum source.

Reopening any deferred track requires a new protocol, its own evidence gate, and a claim limited to that track.

## Selected terminal evidence

| Item | Terminal status | Current use |
| --- | --- | --- |
| EXP-076 | Verified finite source/system closure | Stack Overflow 340-item source and UI evidence |
| EXP-077 | Failed operational workload; audit Passed | Historical negative resource result |
| EXP-079 attempts | Incomplete/Stopped as recorded | Historical negative and diagnostic lineage |
| EXP-080 | Not executed | Not replaced or renamed by EXP-086 |
| EXP-085 attempt 1 | Stopped; verification Failed | Preserved integration failure and repair lineage |
| EXP-085 attempt 2 | Completed; verification Passed; `exp085_complete=true` | Fixed nine-job bounded staged acceptance |
| EXP-086 | Completed; verification Passed; `exp086_complete=true` | One reviewed no-gold Discourse service chain |

EXP-085 attempt 2 completed 9/9 logical jobs, 15/15 model phases, 3,060/3,060 final results, and 5,100/5,100 phase receipts. EXP-086 completed 400/400 final results with 400 M1 attempts, 400 same-job transfer reuses, and 46/46 successful M3 attempts.

## Evidence identities

| Artifact | SHA-256 |
| --- | --- |
| EXP-085 attempt 1 plan | `9de78c110ef9a078025df831138e5acd63d08a596e7c972d5bd13d52f04aec25` |
| EXP-085 attempt 1 run | `b9965aaa8340212a3e49b3d1290febe962c402aeb3e31de97a10dc336f7d4686` |
| EXP-085 attempt 1 verification | `426c3ba406ca42b13942275b8d87384a8e8e9fa71fc9629739ec6b1a0f75bf2f` |
| EXP-085 attempt 1 frozen archive | `76664bc9b6d532e2fc0e81a7b169d25d512f32a72380cd5982e4360c9ce49733` |
| EXP-085 attempt 2 plan | `fc72df94b88315752c0e896af1636779391b4baeee01757041b5d1134faeb28a` |
| EXP-085 attempt 2 run | `3ec838fbfbc68867a98496f80ee0eb34c62cb74c2a3b7467a1554ce45f176b1d` |
| EXP-085 attempt 2 verification | `a33ba29be93e631074b07c140a4fdbad9566b4aa9483633ab31497dcd91af13a` |
| EXP-085 attempt 2 frozen archive | `56386775dd61226ba3fe7f214c89b3a55cad393bb61ed868b77bc5f6082f0435` |
| EXP-086 plan | `09adb1a695b8a4e9a321b6736c0ca8ee021c6219387bb51c1a19e60eddad5ad3` |
| EXP-086 run | `273dff4d562237aac247670fc62ec41077ac714d965eab75f4206469e348814b` |
| EXP-086 verification | `1d49e88655b917c3fec275c8e7f1c66594e588f15d2f26b7b677398298bec450` |
| EXP-086 frozen archive | `97ee2c550265d864a6dab2b43928cc956eac57ac9c27397ed4efb3ee21440818` |

## Source and resource boundaries

- EXP-086 accepted 400 public regular posts from 64 selected topics after 69 request/response pairs.
- It stopped at `item_limit`; one topic was truncated, so `sampling_complete=false` and `collection_complete=false`.
- `exp086_complete=true` means the registered 400-item experiment completed. It does not mean the Python Help category or selected threads were exhaustively collected.
- The 11.5% M3 route rate is descriptive model output, not accuracy, difficulty, or a causal Router effect.
- EXP-085 attempt 2 recorded 12 warning samples; EXP-086 recorded 2. Both had short high-swap intervals but no three-interval stop sequence. Passing does not mean pressure-free operation.
- Sampled RSS, receipt RSS, and MLX lifetime peak use different accounting systems and must not be added.
- Discourse provenance is verified against saved manifests and native-input hashes; the verifier did not perform a second full network crawl.
- CC BY-NC-SA 3.0 metadata supports local non-commercial research traceability, not an automatic commercial redistribution right.

## Supersession policy

The 2026-08-31 `final-claims` and `phase-c-system-report` remain historical snapshots. This decision and the 2026-09-01 final claims/closeout report supersede only their current-status and next-action statements. They do not invalidate EXP-077, EXP-079, EXP-083, or EXP-085 attempt 1 failures, and they do not turn EXP-078 or EXP-080 into executed experiments.

Canonical current entry points:

- `forum-topic-emotion-web/private/reports/final-claims-2026-09-01.md`
- `forum-topic-emotion-web/private/reports/phase-c-final-closeout-2026-09-01.md`
- `forum-topic-emotion-web/docs/release-acceptance.md`
- `forum-topic-emotion-web/docs/reproducibility-package.md`

## Allowed final claim

> On the current 16 GiB local machine, with frozen models, routing, thresholds, and finite registered workloads, the staged website completed all nine EXP-085 acceptance jobs. The same frozen service contract then completed one traceable, no-gold 400-item Python Help source-to-result chain in EXP-086.

## Prohibited extrapolations

- Production-ready, long-running stable, multi-user, or SLA-compliant service.
- External accuracy, F1, calibration, or cross-forum predictive generalization.
- Router accuracy improvement on Discourse.
- Whole-forum or Python-community emotion prevalence.
- Complete Python Help threads, a complete time window, or `collection_complete=true`.
- A causal memory repair or proof that earlier co-residence was the unique failure cause.
- Public or commercial redistribution approval.
- “All Phase C extensions completed.”

## Closeout authorization boundary

This decision authorizes documentation, local release QA, hash verification, and archive references. It does not authorize new training, validation/test access, new source collection, model runs, public deployment, external upload, commit, stage, or push.
