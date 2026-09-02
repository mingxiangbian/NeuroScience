# EXP-062: Seed-44 OOF Router Replication

- Experiment ID: `EXP-062`
- Tier: Major
- RQ: `RQ-S3`
- Parent: [DEC-SO-ROUTER-REPLICATION-V1](dec-so-router-replication-v1.md),
  [EXP-058](exp-058-paired-m1-m3-oof.md),
  [EXP-059](exp-059-calibration-selective-prediction.md), and
  [EXP-060](exp-060-pre-qwen-deployable-router.md)
- Registered: 2026-08-17
- Model seed: `44`
- Evidence role: `prospective replication 2 of 2`
- Status: `Registered only; preflight, model loading, training, analysis, and
  formal execution are not authorized by this document`

## Frozen Scope

EXP-062 applies the same complete decision contract as EXP-061, changing only
`model_seed` from `43` to `44`:

1. train five fresh M1 and five fresh M3 OOF models on the unchanged EXP-058
   fold manifest;
2. assemble and independently verify one seed-44 paired raw-logit OOF artifact;
3. run the frozen EXP-059 diagnostics;
4. recompute the frozen EXP-060 inner-3/outer-4 nested thresholds from seed-44
   raw logits and evaluate the identity logistic router at nominal `15%`;
5. freeze its primary gate result without changing any method after seeing
   EXP-061.

EXP-062 must run after separate authorization even when EXP-061 fails; otherwise
the prospective result cannot distinguish `1/2` from `0/2`. EXP-059 temperature
adoption remains diagnostic only. Validation and test access are forbidden.

## Frozen Output Roots And Attempts

Append-only namespace and attempt paths:

```text
public namespace:  experiments/stack-overflow-emotion-gold/oof-router/runs/exp-062-seed-44-router-replication
private namespace: experiments/stack-overflow-emotion-gold/oof-router/private/exp-062-seed-44-router-replication
public attempt:    <public namespace>/attempt-N
private attempt:   <private namespace>/attempt-N
selection record:  <public namespace>/selected-attempt.json
```

Both attempt directories and the selection record must be absent before a formal
attempt. Failure artifacts remain in that attempt; a retry starts fresh in the
next attempt number and cannot resume or overwrite it. After one complete attempt
passes the independent OOF, EXP-059 and EXP-060 verifiers, one immutable
`selected-attempt.json` is written atomically. Attempt directories are never
moved or rewritten.

## Preconditions For Any Later Authorization

- the parameterized runner, verifier, initialization manifest, path guard and
  synthetic seed-43/44 contract tests pass without result computation;
- seed, train, fold, asset, initialization, RNG and batch-order identities bind
  consistently across CLI/config, metadata, checkpoints, paths and verifier;
- EXP-061's frozen protocol and any retained attempt remain unmodified;
- no validation/test path or prior row-level seed artifact is allowlisted;
- the public/private permissions and aggregate-only public allowlist pass;
- the complete attempt fits the inherited EXP-058 resource ceilings and does not
  overlap a registered heavy data-I/O job.

Passing these preconditions still requires a separate explicit instruction before
formal execution. EXP-062 does not itself authorize synthesis, validation
projection, latency benchmarking, or a cross-seed claim.
