# EXP-056: Stack Overflow M1-M4 Unified Frozen Test Gate

- Experiment ID: `EXP-056`
- Tier: Major
- RQ: `RQ-S1`
- Registered: 2026-08-15
- Current status: `Frozen TEST-READY; test access not authorized`
- Data protocol: `DATA-SO-TASK-V1`

## 1. Purpose

This gate freezes the one-time held-out evaluation for the completed Stack Overflow C0
validation mainline. It does not authorize test access. A separate, explicit user instruction
and a contract-bound authorization record are required before any test input or label is opened.

The gate answers only:

> On the fixed six-label, target-only Stack Overflow task, how do the already selected M1-M4
> model families compare on one untouched duplicate-component-disjoint test split?

It does not select a new model, tune a threshold, train a router, recover context, or establish a
causal effect of generation.

## 2. Frozen units

Exactly 12 units enter the formal test, in this order:

```text
m1-seed-42, m1-seed-43, m1-seed-44
m2-seed-42, m2-seed-43, m2-seed-44
m3-seed-42, m3-seed-43, m3-seed-44
m4-seed-42, m4-seed-43, m4-seed-44
```

- M1: three selected RoBERTa checkpoints from EXP-051.
- M2: frozen Qwen3-4B BF16 plus three selected linear heads from EXP-052.
- M3: three selected Qwen3-4B Classification LoRA adapters and heads from EXP-053.
- M4: three selected Qwen3-4B Generative LoRA adapters from EXP-054.

Each checkpoint, adapter, head, validation run, validation verification and selected validation
threshold is identified by SHA-256 in the machine-readable contract. EXP-055's whole-vector
oracle and any future router are excluded: the oracle is not deployable and no train-OOF router
has passed its gate.

## 3. Frozen prediction rules

All units use target text only and the fixed label order:

```text
[love, joy, surprise, anger, sadness, fear]
```

M1-M3 apply their per-seed shared threshold selected once on validation. There is no per-label
threshold, no test-time calibration and no ensemble. M4 uses the frozen prompt, greedy decoding,
strict JSON parser and invalid-as-all-zero policy. M4 parser validity remains an auxiliary result;
an empty valid list is not a parser failure.

The test runner is split into four irreversible stages:

1. `initialize`: require explicit authorization and create empty append-only outputs.
2. `predict-family`: open test inputs only and produce all three seeds for one family.
3. `seal-predictions`: require all 12 prediction artifacts, freeze their hashes, and certify that
   labels have not been opened.
4. `score`: only after the prediction seal, open labels once, score every unit, aggregate and stop.

Any interrupted family may be rerun only when it has not produced a completed unit artifact.
Completed units are append-only. A resume cannot change the longest completed prediction prefix.

## 4. Metrics and comparisons

Primary metric:

- six-label Macro-F1, reported for each seed and as family mean +/- sample standard deviation
  (`ddof=1`).

Required auxiliary metrics:

- five-label Macro-F1 excluding `surprise`;
- Micro-F1 and weighted F1;
- macro precision and macro recall;
- strict subset accuracy and hamming loss;
- per-label precision, recall, F1, gold support and predicted support;
- empty-output rate and predicted label cardinality;
- M4 parser-valid rate, latency and throughput.

Frozen paired family contrasts use matched seeds:

```text
M2 - M1
M3 - M1
M3 - M2
M4 - M1
M4 - M3
```

For the primary and five-label Macro-F1 contrasts, report the three seed deltas and a
duplicate-component bootstrap interval over the family-mean paired effect (2,000 replicates,
percentile 95% interval). These are descriptive held-out comparisons, not a new selection rule.

`surprise` has only seven test positives by the frozen data manifest. Its individual result and
its effect on six-label Macro-F1 must be reported, but it cannot alone support a broad claim that
one model family is better.

## 5. Test policy

- Test inputs and labels remain sealed while this TEST-READY contract is built and verified.
- A new `exp-056-test-authorization-v1.json` bound to the final contract hash is mandatory.
- All 12 predictions must exist and be hash-sealed before labels are opened.
- Each frozen unit is scored exactly once.
- Test results cannot change thresholds, checkpoints, prompts, parsers, labels or model families.
- Any later work is explicitly `post-test development` and cannot reuse this test as validation.
- No router, oracle, ensemble, best-seed selection or pooled-seed prediction enters the primary
  result.

## 6. Evidence and privacy

Private inputs, labels, probabilities, generations and row-level scored outputs stay under the
Git-ignored `data/stack-overflow-emotion-gold/derived-private/` tree. Public output contains only
configuration hashes, aggregate metrics, per-label aggregates, resource records and verification
results. No Stack Overflow text or row-level label enters Git.

Formal output targets:

```text
experiments/stack-overflow-emotion-gold/test-gate/runs/exp-056-frozen-test/
data/stack-overflow-emotion-gold/derived-private/task-v1/experiments/exp-056-frozen-test/
```

Both targets must be absent at TEST-READY verification time. The preflight verifier may inspect
file existence and byte counts for the sealed test files, but it must not hash or parse either
test file.

## 7. Resource budget and stop conditions

- Local offline execution only; API cost must remain USD 0.
- M1 uses the frozen PyTorch CPU environment; M2-M4 use the frozen MLX environment.
- Maximum total formal wall time: 12 hours.
- Maximum MLX peak memory: 13 GB.
- M4 maximum generation time: 2 hours per seed.

Stop before labels are opened if any model/checkpoint hash drifts, a unit fails schema or row-order
checks, any probability is non-finite, M4's parser contract changes, output directories are not
append-only, or fewer than 12 predictions can be sealed. After labels are opened, a technical
failure may only resume from byte-identical sealed predictions; it cannot rerun inference or alter
the contract.

## 8. Claim boundary

The formal test can support held-out performance, stability, format reliability and resource-cost
claims for these exact frozen systems. It cannot by itself show that generative supervision is
causally responsible for a difference, that Qwen contains a human-like emotion mechanism, that a
router is deployable, or that the result generalizes beyond this small Stack Overflow gold set.
