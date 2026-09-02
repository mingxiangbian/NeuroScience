# EXP-061: Seed-43 OOF Router Replication

- Experiment ID: `EXP-061`
- Tier: Major
- RQ: `RQ-S3`
- Parent: [DEC-SO-ROUTER-REPLICATION-V1](dec-so-router-replication-v1.md),
  [EXP-058](exp-058-paired-m1-m3-oof.md),
  [EXP-059](exp-059-calibration-selective-prediction.md), and
  [EXP-060](exp-060-pre-qwen-deployable-router.md)
- Registered: 2026-08-17
- Model seed: `43`
- Evidence role: `prospective replication 1 of 2`
- Status: `Registered only; preflight, model loading, training, analysis, and
  formal execution are not authorized by this document`

## Frozen Scope

EXP-061 applies the complete shared decision contract without scientific changes:

1. train five fresh M1 and five fresh M3 OOF models with `model_seed=43` on the
   frozen EXP-058 fold manifest;
2. assemble and independently verify one seed-43 paired raw-logit OOF artifact;
3. run the frozen EXP-059 identity/temperature and selective-prediction
   diagnostics on that artifact;
4. recompute the frozen EXP-060 inner-3/outer-4 nested thresholds from seed-43
   raw logits and evaluate the identity logistic router at nominal `15%`;
5. freeze the primary gate result before any seed-44 result is inspected.

EXP-059 temperature adoption is diagnostic only. The primary router uses identity
probabilities, the fixed 14 features, fixed logistic configuration and fixed gate
in the parent decision. Validation and test access are forbidden throughout.

## Frozen Output Roots And Attempts

Append-only namespace and attempt paths:

```text
public namespace:  experiments/stack-overflow-emotion-gold/oof-router/runs/exp-061-seed-43-router-replication
private namespace: experiments/stack-overflow-emotion-gold/oof-router/private/exp-061-seed-43-router-replication
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
- no validation/test path or prior row-level seed artifact is allowlisted;
- the public/private permissions and aggregate-only public allowlist pass;
- the complete attempt fits the inherited EXP-058 resource ceilings and does not
  overlap a registered heavy data-I/O job.

Passing these preconditions still requires a separate explicit instruction before
formal execution. EXP-061 does not authorize EXP-062, synthesis, validation
projection, latency benchmarking, or any claim beyond its verified seed-43 result.
