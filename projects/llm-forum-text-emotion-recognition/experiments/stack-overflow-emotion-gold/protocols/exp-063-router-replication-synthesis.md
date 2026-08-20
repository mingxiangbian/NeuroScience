# EXP-063: Prospective Router Replication Synthesis

- Experiment ID: `EXP-063`
- Tier: Major synthesis
- RQ: `RQ-S3`
- Parent: [DEC-SO-ROUTER-REPLICATION-V1](dec-so-router-replication-v1.md),
  [EXP-061](exp-061-seed-43-router-replication.md), and
  [EXP-062](exp-062-seed-44-router-replication.md)
- Registered: 2026-08-17
- Status: `Registered only; synthesis execution is not authorized by this document`

## Question And Input Boundary

Did the two prospective replication seeds pass the one frozen identity-logistic
router gate on the same `DATA-SO-TASK-V1` train data?

EXP-063 is read-only and may consume only independently verified public aggregate
artifacts from seed-42 EXP-060 discovery, EXP-061, and EXP-062. Both prospective
experiments must have a terminal verified pass-or-fail gate result. It may not
open private row-level outputs, fit a model, select a threshold or cutoff, recompute
the router, access validation/test, or treat seed 42 as a replication vote.

## Frozen Synthesis

The report records, without method changes:

- seed 42 as discovery background only;
- EXP-061 and EXP-062 primary pass/fail results;
- prospective pass count out of exactly two;
- nominal and actual call rate;
- six-label and five-label Macro-F1 deltas;
- Hamming-loss delta under tolerance `1e-12`;
- per-label F1 deltas and whether gain remains driven only by `surprise`;
- the 2,000-component-bootstrap intervals as uncertainty descriptions;
- verifier status, artifact hashes, failures, and retained attempt IDs.

The decision table is fixed:

| Prospective results | System decision |
|---|---|
| `2/2` pass | promote only the same-train cross-seed meta-level replication claim |
| `1/2` pass | record seed sensitivity; do not promote the router |
| `0/2` pass | record that seed-42 discovery was not prospectively replicated |

Rows from the three seeds must not be concatenated into a nominal sample of
`10,080`, and no ordinary row-level significance test may treat repeated training
seeds as independent data. Descriptive per-seed values and the frozen pass count
are the primary synthesis.

## Output And Claim Boundary

Any later authorized run uses a new append-only attempt below the frozen public
namespace:

```text
namespace: experiments/stack-overflow-emotion-gold/oof-router/runs/exp-063-router-replication-synthesis
attempt:   <namespace>/attempt-N
selection: <namespace>/selected-attempt.json
```

A failed synthesis attempt is retained and cannot overwrite an earlier attempt or
either input experiment. A verified synthesis is committed only by atomically
creating the immutable selection record; the selected attempt itself is not moved
or rewritten. Before a synthesis attempt, its attempt directory and the selection
record must both be absent; an existing selection record blocks every later
attempt. The selection record binds the selected attempt ID and the exact
EXP-061/062 input run and verification hashes in addition to the synthesis config,
run, verification and public-artifact hashes.

Even `2/2` supports only this conclusion: the frozen pre-Qwen logistic router was
replicated across two prospective training seeds on the same
`DATA-SO-TASK-V1` train data at the meta level. It does not establish independent
data generalization, end-to-end deployment benefit, production latency, or forum
generality. It may justify registering a separate latency benchmark or frozen
validation development projection; it does not authorize either one.
