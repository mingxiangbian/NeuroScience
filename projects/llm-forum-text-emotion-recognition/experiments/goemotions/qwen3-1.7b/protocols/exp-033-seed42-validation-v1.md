# EXP-033 Seed-42 Validation-Only Evaluation V1

## Registration

- Experiment: `EXP-033`
- Evaluation ID: `EXP-033-SEED42-VALIDATION-V1`
- Tier: `Major`
- Stage: final seed-42 adapter validation
- Split: official GoEmotions `dev` only, exactly 5,426 rows
- Test gate: closed; `test.tsv` must be absent and must never be read
- Status: implementation prepared; execution remains blocked until a separate frozen contract is
  created after formal seed-42 training passes independent verification

This protocol prepares evaluation code only. It does not guess or pre-register the final adapter
hash. The later contract must bind the independently verified final adapter and every executable
input before inference begins.

## Question

Does target-aligned EXP-033 training improve the final seed-42 Qwen3-1.7B adapter on the official
GoEmotions validation split under the same aligned prompt and open-neutral output ontology used to
diagnose EXP-029?

This is validation/model-selection evidence. It is not a test result and does not establish an
emotion mechanism or generalization beyond GoEmotions.

## Single Frozen Condition

Exactly one generation is permitted for each of the 5,426 dev rows:

- final seed-42 adapter only; no checkpoint selection;
- prompt: aligned GoEmotions prompt (`exp-031-neutral-cooccurrence-v1` semantics);
- decoder: open-neutral finite-state JSON constraint;
- greedy decoding with temperature `0.0`;
- thinking disabled in the chat template;
- `max_new_tokens = 64`;
- no parser retry, output repair, fallback generation, or second condition;
- any invalid JSON, invalid schema, unknown/duplicate/empty label list, or length-terminated output
  becomes an empty prediction for metrics.

An interrupted process may resume only from the exact append-only prediction prefix. A resumed run
must skip every completed row and may generate only rows that have no stored record. A completed or
terminal resource-gate run can never resume or be overwritten.

## Contract Gate

Execution must receive both a contract path and its expected SHA-256. Before loading the model or
reading dev rows, the runner must reject any contract that does not freeze all of the following:

- this protocol, runner, and independent verifier;
- final adapter weights and `adapter_config.json`;
- independently passed formal-training verification;
- official dev file, ordered labels, aligned prompt, open-neutral constraint, its base constraint,
  generation helper, and `llm_full_dev_metrics.py`;
- local model manifest, repository identity, revision, and every model file;
- Python executable, package versions, complete MLX-LM Python source-tree manifest, and named
  runtime-semantics source files;
- two row-aligned validation prediction references used for paired comparisons;
- output directory, test-absence path, exact decoding policy, metric policy, bootstrap policy,
  slices, resource limits, and decision thresholds.

The training verification must state `Passed`, seed `42`, train-only access, no validation/test
access during training, and validation authorization. Its recalculated adapter config and weights
must match the artifacts frozen by the validation contract.

The contract is created only after the final adapter passes independent training verification. It
must use contract ID `EXP-033-SEED42-VALIDATION-V1`, stage `seed-42-validation-only`, seed `42`,
`dev_rows = 5426`, `test_access = false`, and `final_adapter_only = true`.

The public run directory is fixed to
`experiments/goemotions/qwen3-1.7b/runs/exp-033-target-aligned-lora/validation-seed-42-v1`;
temporary finalization is fixed below
`experiments/goemotions/qwen3-1.7b/private-cache/exp-033-target-aligned-validation/seed-42`.
Keeping validation as a sibling of the frozen `seed-42` training directory preserves the formal
training verifier's append-only directory inventory.

## Metrics

Primary metric:

- Macro-F1 across the ordered 28-label GoEmotions ontology.

Complete auxiliary evidence:

- macro precision/recall;
- micro, weighted, and sample-averaged precision/recall/F1;
- strict subset accuracy, Hamming loss, and label accuracy;
- per-label precision, recall, F1, support, and predicted support;
- per-label multilabel confusion counts (`tn`, `fp`, `fn`, `tp`);
- gold and predicted label cardinality, empty predictions, and neutral co-predictions;
- parser-valid rate, parser-error counts, and finish-reason counts;
- per-row and aggregate generation latency, prompt/generation throughput and token counts;
- maximum observed MLX peak memory and constraint-intervention telemetry.

Every row record stores row number, gold and predicted labels, raw model output, parser status,
finish reason, generation latency, token/resource telemetry, and output hash. Raw forum input text
and comment IDs are not stored in public run artifacts.

## Pre-Registered Slices

Slices are determined only from frozen gold labels and are evaluated without model-driven
selection:

- `all`;
- `single_label` (gold cardinality = 1);
- `multi_label` (gold cardinality > 1);
- `high_cardinality` (gold cardinality >= 3);
- `neutral_only` (the sole gold label is `neutral`);
- `neutral_cooccurrence` (`neutral` plus at least one emotion label);
- `any_neutral` (any gold `neutral` label);
- `without_neutral` (gold does not contain `neutral`).

Each non-empty slice reports the same task metrics plus row count and cardinality diagnostics. A
zero-row slice is reported as empty rather than silently omitted.

## Paired Bootstrap and Decision Rules

The resampling unit is one dev row. Use 10,000 paired bootstrap replicates, RNG seed `20260803`,
batch size `100`, and percentile 95% confidence intervals for Macro-F1 differences. The later
contract must freeze the two row-level reference prediction files and verify that their gold
matrices exactly match the official dev gold matrix.

Pre-registered comparisons:

1. EXP-033 minus selected EXP-025 few-shot: registered reference Macro-F1 `0.241164`, full-precision
   reference `0.2411641547489156`; repetition gate passes only when the full-precision paired delta
   is at least `0.005` (equivalently, EXP-033 Macro-F1 >= `0.2461641547489156`).
2. EXP-033 minus EXP-029 seed-42 under aligned prompt plus open-neutral decoding: reference
   Macro-F1 `0.440637`, full-precision reference `0.4406373760273263`; the target-alignment
   hypothesis gate passes only when the full-precision paired delta is at least `0.005`
   (equivalently, EXP-033 Macro-F1 >= `0.4456373760273263`).
3. BERT-base three-seed mean Macro-F1 `0.489435`: descriptive comparison only, with no gate and no
   paired bootstrap unless row-level frozen predictions are separately supplied later.

The rounded registered reference values above are decision labels. Before evaluation, the contract
must also freeze the full-precision Macro-F1 values recomputed from the paired reference files.
Differences below the registered `0.005` practical threshold are treated as practical ties.

## Resource and Artifact Policy

- Active validation wall time: at most 4 hours, including model load and finalization.
- Peak MLX memory: at most 14 GB.
- API cost: USD 0.
- One dev generation per row; no full-validation rerun under this contract.
- No test file content may be opened. Test absence is checked only as a filesystem gate.
- The output directory must be absent on first execution and is never reused after completion.
- Prediction records are flushed incrementally. Final metrics are built in a private attempt
  directory and atomically promoted only after all rows are present.
- A resume must fully revalidate the saved prediction prefix. Attempt start/end times and charged
  durations are persisted; an unclean interruption is conservatively charged through the next
  resume time, so interrupted overhead cannot evade the four-hour gate.
- The independent verifier must not import the runner. It must re-hash all frozen inputs, rebuild
  gold/prediction matrices from source artifacts, independently recompute complete metrics,
  slices, references, gates, bootstrap results, resource limits, attempt accounting, every public
  CSV field, record order, and split access.

Required final artifacts include `run.json`, `predictions.jsonl`, `predictions.csv`,
`metrics.json`, `per-label-metrics.csv`, `multilabel-confusion-matrix.csv`,
`slice-metrics.json`, `paired-bootstrap.json`, `comparisons.json`, `stdout.log`, and an independent
`verification.json` created only after the run completes.
