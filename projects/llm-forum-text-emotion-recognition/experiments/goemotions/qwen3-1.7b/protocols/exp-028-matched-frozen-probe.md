# EXP-028: Matched Qwen3-1.7B Base/Post-trained Frozen Probe

Registration date: 2026-08-01 (Asia/Shanghai)

## Registration

- Experiment ID: `EXP-028`
- Tier: `Major`
- RQ: `RQ-G2`
- Parent: `EXP-027`
- Stage: matched frozen-representation probe on GoEmotions train/dev
- Status: registered; formal train/dev run not started
- Config: [`../configs/exp-028-matched-frozen-probe.json`](../configs/exp-028-matched-frozen-probe.json)
- Config SHA-256: `a932e62a1dbbd6d5cf0c46656b74043caedf63ddc488a578d0e5ac8a0ded4cea`
- EXP-027 verification SHA-256:
  `90cbc3ef373c1581c561335120a7f492df17d893cd1ef0f4c030da3d48560119`

Frozen implementation:

- feature extractor SHA-256:
  `c29f5a7ba71a956bf8ed259a9c0461d1a151f3a1e7cb8c444baebf6b8a69dccd`;
- probe fitter/evaluator SHA-256:
  `af64794722d40f4449d84aed2c4cd4d6c53ab254e9e69c3b006938862b7c6909`;
- independent verifier SHA-256:
  `90056c79bfc6f5f176537b2bc05dd273f8fcabbcd70ab29c29b6d12c4d55f605`;
- preflight gate SHA-256:
  `a975bf272b9b2370f48a8f51543b00e9cea9473f9a768f93e84de2490146cefb`.

This registration freezes the design before formal feature extraction or dev result access. It
does not acquire, read, or authorize the GoEmotions test split.

## Research Question and Falsifiable Outcomes

When architecture, parameter scale, precision, token IDs, sequence length, layer, pooling and
supervised linear readout are matched, does Qwen3-1.7B post-training change how linearly decodable
the frozen GoEmotions labels are relative to Qwen3-1.7B-Base?

The competing outcomes are:

- post-trained representations are more linearly decodable;
- Base representations are more linearly decodable;
- the difference is practically negligible;
- the point difference is non-negligible but statistically inconclusive on this dev split.

The directional prior is weak. Instruction/post-training may make task-relevant distinctions more
accessible, but a supervised probe may already recover them from Base representations, and
post-training may redistribute rather than add linearly accessible information. A null or negative
result is therefore valid evidence.

The label-shuffle falsification check asks whether either real probe learns text-label alignment
rather than split artifacts or label priors alone. Each real probe should exceed the maximum of its
three shuffled-label controls by at least `0.02` Macro-F1. Failure is retained and reported as a
validity concern; it is not deleted or repaired after seeing dev results.

## What This Experiment Isolates

EXP-025/026 evaluated the post-trained model as a generative classifier. Those results combine
internal representations, prompt interpretation, language-model decoding, output constraints and
strict label parsing. EXP-028 removes prompt and decoder behavior from the readout:

```text
plain text -> frozen Qwen hidden states -> fixed pooling -> supervised linear probe
```

Both model conditions receive identical raw-text token IDs and the same probe algorithm. The
controlled difference is the paired model checkpoint: pretraining-only Base versus the official
post-trained checkpoint. No chat template, label prompt, generated rationale, constrained decoder,
parser, retry or language-model vocabulary head is used.

This design does not isolate individual post-training datasets or objectives, because the official
post-trained checkpoint combines undocumented or only partially documented stages. It estimates
the aggregate checkpoint-stage difference.

## Frozen Data and Split Discipline

- Dataset protocol: `DATA-GOE-V1`.
- Task: official agreement-filtered GoEmotions, 28-label multi-label classification.
- Train: 43,410 rows,
  SHA-256 `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Dev: 5,426 rows,
  SHA-256 `575489c079c9de1097062a01738f998590d6b7ead66dd1c9fd1d2ba01fd8bc62`.
- Ordered labels: 27 emotions plus `neutral`,
  SHA-256 `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Test: absent, not acquired and prohibited.

Train fits the scaler, real probes and shuffled-label controls. Dev is read once by the frozen
pipeline for evaluation and the paired bootstrap. No threshold, regularization value, pooling rule,
layer, feature transformation or classifier is selected from dev results. The official split and
the previously reviewed exact-text overlap are preserved for benchmark continuity.

The feature extractor reads each TSV row to obtain text and validate row structure, but encoded
labels are not used in tokenization, model inference or pooling. Gold labels are loaded only by the
probe fitter/evaluator after all four feature caches have been created.

## Frozen Paired Models

Base condition:

- `Qwen/Qwen3-1.7B-Base`;
- revision `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`;
- local unquantized MLX BF16 conversion;
- manifest SHA-256:
  `e120c568597bc10aebab9b07ad77c41a8837014860abbe96537098529068d080`.

Post-trained condition:

- `Qwen/Qwen3-1.7B`;
- revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`;
- local unquantized MLX BF16 conversion;
- manifest SHA-256:
  `7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877`.

Both have hidden size 2,048 and 28 transformer layers. Their converted `tokenizer.json` files are
byte-identical, SHA-256
`be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506`.
The runner additionally hashes the complete per-row token-ID stream for each split and rejects the
run if Base and post-trained streams differ.

## Frozen Input and Representation

- Input: raw comment text only.
- Chat template: disabled.
- Special-token insertion: disabled.
- Maximum length: 64 tokens, right truncation.
- Padding: right padding with `<|endoftext|>` ID `151643`.
- Model precision: BF16; no quantization.
- Forward path: `model.model(input_ids)`.
- Layer: final transformer output after final RMSNorm and before the language-model head.
- Pooling: arithmetic mean over non-padding token states.
- Stored feature dtype: float32.

MLX Qwen's causal mask does not receive a separate padding mask. Right-padding tokens occur only
after real tokens, so causal attention prevents them from changing the retained real-token states;
the pooling mask then excludes padding positions. Switching to left padding, last-token pooling,
another layer or a learned pooling function requires a new experiment ID.

Mean pooling summarizes token states with different causal receptive fields. It is a fixed
distributed-representation readout, not a claim that the model uses mean pooling internally to
recognize emotion.

## Frozen Linear Readout

For each condition independently:

1. fit `StandardScaler` on that condition's train features only;
2. apply the fitted scaler to its train and dev features;
3. fit 28 independent binary Logistic Regression models through
   `OneVsRestClassifier`;
4. predict a label when its probability is at least `0.5`.

Classifier parameters:

- `C=1.0`;
- L2 penalty;
- `liblinear` solver;
- `class_weight="balanced"`;
- `max_iter=2000`, `tol=1e-4`;
- classifier random state `20260801`;
- `n_jobs=1`;
- no global or per-label threshold tuning;
- no forced non-empty prediction and no `neutral` suppression.

Separate train-fitted scalers remove trivial checkpoint-level scale differences while applying the
same transformation rule. This is a comparison of linear accessibility after train-only affine
normalization, not of raw hidden-state magnitude.

## Label-shuffle Leakage Control

For seeds `42`, `43` and `44`, the complete multi-label target rows are permuted across train
features. This preserves:

- each label's train frequency;
- each row's label cardinality;
- within-row label co-occurrence.

It breaks the alignment between text representations and labels. The scaler, classifier,
regularization, class weighting, threshold and dev evaluation remain identical. A shuffled model
is never used to select a real probe or tune the protocol.

## Metrics, Statistics and Decision Rule

Primary metric: Macro-F1 over all 28 labels, including classes with no predicted positives.

Required secondary evidence:

- macro, micro, weighted and samples-averaged precision, recall and F1;
- strict subset accuracy;
- Hamming loss and label-level accuracy;
- per-label precision, recall, F1, gold support and predicted support;
- one 2x2 confusion matrix per label;
- gold/predicted label cardinality, empty predictions and `neutral` co-predictions;
- real versus shuffled-label Macro-F1;
- extraction, scaling, fitting and prediction time plus peak MLX memory.

Use 10,000 paired dev-row bootstrap replicates, seed `20260801`, percentile 95% intervals and
batch size 100 for `post-trained - Base` Macro-F1. Bootstrap estimates dev-row sampling
uncertainty; it does not estimate checkpoint, pretraining or probe-hyperparameter uncertainty.

Decision wording is frozen:

- `post-trained_more_linearly_decodable`: delta at least `+0.005` and interval above zero;
- `base_more_linearly_decodable`: delta at most `-0.005` and interval below zero;
- `practical_tie`: absolute delta below `0.005`;
- `inconclusive`: absolute delta at least `0.005` but interval includes zero.

Weighted-F1, individual labels and comparison with EXP-018/020 cannot override this rule. EXP-018
and EXP-020 may be shown as descriptive context, but their different training regimes mean they do
not isolate post-training in this probe comparison.

## Execution Order and Formal Gate

The formal order is fixed:

1. Base train features;
2. Base dev features;
3. post-trained train features;
4. post-trained dev features;
5. both real probes and all six shuffled-label probes;
6. independent verification.

Before step 1, preflight must report `Passed`, the formal output and private-cache roots must be
absent, all frozen hashes must match, both offline environments must match, EXP-027 must remain
verified and `test.tsv` must be absent. The preflight itself reads zero project split rows.

Each extraction command must set:

```text
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
PYTHONNOUSERSITE=1
```

There is one formal run. Interrupted or failed extraction/output directories are preserved for
audit and cannot be silently overwritten. A technical restart requires explicit review and a new
cache/output path or experiment ID.

## Artifacts and Privacy

Local private cache, excluded by the experiment `.gitignore`:

```text
private-cache/exp-028-matched-frozen-probe/
├── base/{train,dev}/{features.npy,metadata.json,stdout.log}
├── post-trained/{train,dev}/{features.npy,metadata.json,stdout.log}
└── probe-models/{base,post-trained}/
```

Pooled representations may retain information about source text and are therefore private even
though they contain no explicit text or comment IDs. They must not be committed or published.

Public formal artifacts:

```text
runs/exp-028-matched-frozen-probe/
├── run.json
├── stdout.log
├── aggregate-metrics.json
├── condition-summary.csv
├── paired-bootstrap.json
├── base/
│   ├── predictions.csv
│   ├── metrics.json
│   ├── per-label-metrics.csv
│   ├── multilabel-confusion-matrix.csv
│   └── label-shuffle/{seed-*-predictions.csv,seed-*-metrics.json}
├── post-trained/...
└── verification.json
```

Public predictions contain only one-based row number, gold/predicted label IDs/names and, for real
probes, 28 probabilities. They contain no raw text, prompt, comment ID or hidden vector.

## Independent Verification

The verifier runs in the locked scikit-learn environment and must:

- verify config, implementation, data, label, model-manifest, tokenizer and artifact hashes;
- verify train/dev row counts and that test remains absent;
- verify Base and post-trained token-stream hashes match for each split;
- load private feature caches and frozen probe models;
- recompute all real probabilities and predictions;
- reconstruct all three label permutations and recompute shuffled predictions;
- independently recompute aggregate and per-label metrics;
- independently recompute the paired bootstrap and decision outcome;
- confirm public prediction schemas contain no raw text or comment IDs;
- report maximum numeric differences and `Passed` or `Failed`.

Only `Passed` formal evidence may enter `evidence-log.md` or the thesis results chapter.

## Resource Budget and Stop Conditions

- Model-sample feature extractions: 97,672 across both conditions.
- Expected raw float32 feature storage: approximately 0.80 GB plus metadata/models.
- Private-cache hard limit: 4.0 GB.
- Feature batch size: 8.
- Per condition/split extraction wall-time limit: 120 minutes.
- Probe fitting/evaluation wall-time limit: 240 minutes.
- End-to-end wall-time limit: 480 minutes.
- Peak MLX memory limit: 14.0 GB.
- API and external compute cost: USD 0.
- Network access: prohibited.

Stop on any hash mismatch, token-stream mismatch, non-finite value, shape/row mismatch,
convergence warning, memory/time limit, unexpected existing output, raw-text publication or test
presence/access. Preserve the failure artifact.

## Evidence-to-Thesis Destination

- Methods: paired checkpoints, plain tokenization, final-layer mean pooling, train-only scaling,
  balanced linear probes, shuffled-label control and paired bootstrap.
- Results `Table-G2-2`: Base versus post-trained real and shuffled-label probe metrics.
- Results `Figure-G2-2`: per-label Base/post-trained F1 differences with support.
- Discussion: whether post-training changes linear accessibility beyond generative prompt/decoder
  behavior observed in EXP-025/026.
- Limitations: dev-only evidence, official checkpoint-stage confounding, one layer/pooling choice,
  supervised probe capacity, no context and no causal intervention.

## Claim Boundary

A positive result supports only this statement: under the frozen input, layer, pooling and linear
readout, GoEmotions labels are more linearly decodable from one checkpoint than the other.

It does not establish:

- that the model experiences emotion;
- that it recognizes emotion by a human-like process;
- that a particular feature or neuron is a causal emotion mechanism;
- that post-training created information absent from Base rather than reorganizing accessibility;
- that the better probe is the better generative classifier, agent or chatbot;
- test-set or cross-domain generalization.

Mechanistic wording requires a later registered intervention, ablation or activation-patching
experiment. SAE, probing or clustering alone remains correlational representation evidence.
