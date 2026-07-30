# EXP-016 Protocol: Frozen TweetEval Test Gate

Registration date: 2026-07-30

This protocol was frozen after model selection on train/validation and before
any EXP-016 prediction or project test metric was produced. The user explicitly
approved the one-time formal test gate on 2026-07-30.

## Registration

- Tier: Major
- RQs: RQ-B1, RQ-B2, RQ-B3
- Stage: formal frozen test gate
- Dataset: TweetEval emotion
- Allowed split: official test only
- Training or checkpoint selection: prohibited
- Ensemble: prohibited
- Frozen config:
  `configs/exp-016-frozen-test.json`
- Frozen config SHA-256:
  `52cf70ad7f19bdef69d89cfcfa14951049442f73aafa76e255f08044435a008d`
- Evaluation runner SHA-256:
  `b2f600b68d49ec9b8216fbb1e392726a206df10b70051a223acd251686ca430c`
- Independent verifier SHA-256:
  `d648fddb3e7370d1d1735815c531267bfc4ed33e997693f6562160098d1120b9`

Any functional change to the config, runner, listed model set, metric, or
aggregation rule invalidates this registration. It requires a new post-test
experiment and cannot replace EXP-016.

## Test-Ready Checklist

- [x] The complete frozen model set is listed below.
- [x] Every source run records `test_split_accessed=false`.
- [x] EXP-007, EXP-011, EXP-014, and EXP-015 validation artifacts have passed
  their existing independent verification.
- [x] Every model, checkpoint, source run, verification file, and test input is
  pinned by SHA-256 in the frozen config.
- [x] The primary and auxiliary metrics are fixed before test inference.
- [x] Neural aggregation is fixed to all three seeds, with no seed selection.
- [x] Paired comparisons are fixed before test inference.
- [x] The append-only output path did not exist at registration.
- [x] The user explicitly authorized opening test and executing the formal
  evaluation.

Pass signal: all ten listed model evaluations complete once, independent
metric recomputation passes, and no configuration is changed after results.

## Frozen Conditions

| Condition | Scientific role | Frozen unit(s) | Validation selection |
| --- | --- | --- | --- |
| EXP-007 | Traditional word+character TF-IDF Linear SVM | one fitted pipeline | train-only CV selection followed by one frozen validation confirmation |
| EXP-011 | Generic RoBERTa control without label smoothing | seeds 42, 43, 44 | best validation Macro-F1 checkpoint within each seed |
| EXP-014 | Generic RoBERTa with label smoothing 0.05 | seeds 42, 43, 44 | train-only regularization selection, then best validation checkpoint within each seed |
| EXP-015 | Twitter-domain RoBERTa with label smoothing 0.05 | seeds 42, 43, 44 | same downstream condition as EXP-014, then best validation checkpoint within each seed |

The nine neural checkpoints are fixed as follows:

| Condition | Seed | Selected step | Model SHA-256 |
| --- | ---: | ---: | --- |
| EXP-011 | 42 | 816 | `06693b7490ab70b5371be81d7c05a03cec404323a55929a03a16b7bb5fe37fb8` |
| EXP-011 | 43 | 612 | `44218ec2649683f75a8681eb540d25fc6af0cc0ba88bc5e7210d5096d3525889` |
| EXP-011 | 44 | 1020 | `d011d647939f7e2c38263bc68583db0dd5646db379392ad9e9b76b1a63e06bc0` |
| EXP-014 | 42 | 612 | `a0e2027e8a6bf44cc8623d456775be14c93f28afb7f211c231ef1cc29a2fdbdd` |
| EXP-014 | 43 | 816 | `ca6673f093ba8663a82087e00e5169cccc71a4e3097a327d90ab40a2e5e4183a` |
| EXP-014 | 44 | 1020 | `b4bf295ad6f65cdca4ff1fba5edfc47fcb5196684fa1e6fdcf639df9d5b006a9` |
| EXP-015 | 42 | 612 | `7cbba019b2af0d787ad6e16bc57a4f90de0ec19a51aa28aa36b8cb3932e68308` |
| EXP-015 | 43 | 1020 | `2a33d46cd1d79ec9be18dffe3c66d25431954d3366368c73308225e9a880771a` |
| EXP-015 | 44 | 612 | `ab4880d9fa2896954ad62e6189e85d429073fd127edb6f7155cab2f6c462b3a7` |

The EXP-007 fitted pipeline SHA-256 is
`c4744557448a5b6a3606c21b6ed655e45a19051058b3d1e7aa0d1d53ebca4590`.

## Research Questions

1. How much does the final frozen neural pipeline improve over the traditional
   text baseline on the untouched test split?
2. Does the modest EXP-014 validation improvement from label smoothing remain
   on test when compared by matched seed with EXP-011?
3. Does the EXP-015 Twitter-domain-pretraining improvement remain on test when
   compared by matched seed with EXP-014?

Negative results remain informative. A non-positive EXP-014 minus EXP-011
difference means label smoothing did not generalize under this protocol. A
non-positive EXP-015 minus EXP-014 difference means the validation evidence
for domain-pretraining benefit did not generalize under this protocol.

## Data Contract

Upstream commit:
`4fbd22cd78421f05b1ecdb4fc5725bc7a7bd8f66`

| Input | Rows | SHA-256 |
| --- | ---: | --- |
| `mapping.txt` | 4 | `656dea85d149716af96206ca19bec0d94e9dc6de3f5079f5c7c2a241ec76cadb` |
| `test_text.txt` | 1,421 | `7e1070f5d3e3fcece5bc73680bff9981e90d8f7b2f1009bfe7a01d059d1c6091` |
| `test_labels.txt` | 1,421 | `245072348c711961785be6d395997f97cf7fcda3effeae7805664171dc75f913` |

Label order is fixed as `anger`, `joy`, `optimism`, `sadness`. All conditions
receive the same raw text in the original row order. No test text is written
to tracked artifacts.

## Metrics and Statistics

Primary metric: test Macro-F1.

Required auxiliary outputs:

- Accuracy, macro precision, macro recall, and weighted F1.
- Per-class precision, recall, F1, and support.
- Rows-true, columns-predicted confusion matrix.
- Per-row anonymous row ID, gold label, prediction, and either softmax
  probability or LinearSVC decision score.
- Input, model, config, protocol, prediction, metric, and confusion hashes.
- Inference time for every fitted model or checkpoint.

EXP-007 is reported as one deterministic frozen result. EXP-011, EXP-014, and
EXP-015 are each reported as mean and sample standard deviation across seeds
42, 43, and 44.

The paired seed-level Macro-F1 differences are fixed as:

```text
EXP-014 - EXP-011
EXP-015 - EXP-014
```

An absolute mean difference below `0.005` is interpreted as a practical tie.
This threshold is not a statistical-significance test. Test results cannot be
used to select one seed, create an ensemble, modify preprocessing, or retrain.

## External Reference Boundary

The pinned upstream README reports test Macro-F1 values of 0.647 for its SVM,
0.761 for RoBERTa-Base, 0.720 for RoBERTa-Twitter, and 0.785 for
RoBERTa-Retrained. These are external published configurations, not local
project results. They must remain in a separate comparison column because
their exact preprocessing, training implementation, and run variance are not
identical to EXP-016.

## Artifacts and Verification

The append-only output directory is:

```text
runs/exp-016-frozen-test/
```

It must contain:

- `run.json` and `stdout.log`;
- one EXP-007 prediction/metric/confusion bundle;
- three prediction/metric/confusion bundles for each neural condition;
- `condition_summary.csv` and `seed_results.csv`;
- `verification.json` from `verify_frozen_test.py`.

The verifier independently checks test labels, row order, score argmax,
probability sums, complete metrics, per-class values, confusion matrices,
aggregates, paired comparisons, ranking, and artifact hashes.

## Resource Budget

- Maximum fitted-model/checkpoint evaluations: 10
- Maximum wall time: 60 minutes
- API cost: USD 0
- Device: local Apple MPS for neural inference; local CPU for Linear SVM
- Network: disabled

An input/model hash mismatch, unexpected source test access, non-empty output
directory, missing checkpoint, NaN, OOM, or budget overrun stops the run and
preserves the failure record.

## Thesis Destination

- Main results table: traditional baseline, generic encoder, regularized
  generic encoder, and domain-pretrained encoder.
- Controlled ablation: EXP-011 versus EXP-014.
- Domain-pretraining comparison: EXP-014 versus EXP-015.
- Error analysis input: anonymous test row IDs and model-specific/shared error
  sets, sampled later under a separately frozen rule.
- Limitations: one dataset, three neural seeds, one domain-pretrained encoder,
  and no confidence interval beyond seed variation.
