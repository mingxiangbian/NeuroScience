# EXP-060: Pre-Qwen Deployable Router

Status: protocol frozen; no-result preflight authorized; formal router fitting and
result computation are not authorized by this registration.

Date: 2026-08-17

Tier: Major system experiment

RQ: RQ-S3

## Research Question

Can information available after running M1 RoBERTa, but before calling M3 Qwen,
identify a small subset of Stack Overflow C0 examples for which replacing the complete
M1 six-label prediction with the complete M3 prediction improves the system at a
controlled Qwen call rate?

The falsifiable primary hypothesis is that at least one frozen pre-Qwen routing policy
can call M3 on no more than 20% of rows and improve six-label Macro-F1 over M1 by at
least 0.01 without worsening Hamming loss, materially degrading five-label Macro-F1,
or deriving the apparent gain only from the low-support `surprise` label.

The negative result is decision-relevant: if no policy passes, deploy a single model
with EXP-059 calibration/abstention and close the router branch. EXP-059's oracle
headroom is not evidence that a deployable router exists.

## Frozen Scope And Access Boundary

- Data: `DATA-SO-TASK-V1` train OOF only, 3,360 rows, 3,277 duplicate components.
- Labels: `love`, `joy`, `surprise`, `anger`, `sadness`, `fear`, in that order.
- Upstream model seed: canonical seed 42 only.
- Upstream models: M1 RoBERTa and M3 Qwen3-4B Classification LoRA only.
- Validation and consumed test are forbidden.
- No model checkpoint may be loaded and no M1/M3 forward pass may run.
- No raw Stack Overflow text is opened in this first router version.
- No context, M2, M4, new model family, neural router or label-wise route is added.

The formal run, when separately authorized, may read the private EXP-058 paired OOF
artifact and frozen public EXP-059 calibration decision. It must not use validation or
test for feature selection, threshold selection, operating-point selection or claims.

## Inputs And Frozen Upstream Decisions

Required row-level input:

```text
EXP-058 paired-oof.npz
SHA-256 e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc
```

Required EXP-059 decisions:

- both M1 and M3 selected calibrators are `identity`;
- one shared six-label threshold grid is `0.05, 0.06, ..., 0.95`;
- threshold tie order is highest six-label Macro-F1, lowest Hamming loss, closest to
  0.50, then lower threshold;
- whole-vector ties choose M1;
- EXP-060 headroom gate passed, but its oracle target and result are non-deployable.

Because the selected calibrator is identity, the formal router recomputes probabilities
as `sigmoid(raw_logit)` from EXP-058. It must stop if the frozen EXP-059 calibration
record no longer says identity for both families.

## Nested Cross-Fitting

Simply fitting a router on EXP-059 row-level threshold-derived fields would not be
sufficiently clean. For an outer router fold `k`, an EXP-059 threshold attached to a
different training fold may have been selected using fold `k`. The formal experiment
therefore uses this nested construction:

1. Hold out one of the five duplicate-component-disjoint folds as the outer router
   evaluation fold.
2. For each of the remaining four folds in turn, select M1 and M3 thresholds on the
   other three outer-training folds, then construct that fold's router features and
   target. These four inner-held-out partitions form the router training set.
3. Select M1 and M3 thresholds on all four outer-training folds and construct features,
   target and model predictions for outer fold `k`.
4. Fit the feature scaler and logistic router only on the nested router training rows;
   apply them once to outer fold `k`.
5. Repeat for all five outer folds and restore EXP-058 source order.

This construction ensures that the M1/M3 base predictions, threshold-derived router
training targets, threshold-derived M1 features, scaler and router did not fit the row
on which the routed system is evaluated. Duplicate components remain fold-disjoint.

No logistic hyperparameter search is performed in EXP-060. This avoids another nesting
layer and prevents post-hoc selection on the same OOF evidence.

## Router Target

For each nested partition, threshold the complete M1 and M3 six-label probability
vectors with thresholds fitted only on its permitted training folds. Define:

```text
target = 1  when row_hamming_loss(M3, gold) < row_hamming_loss(M1, gold)
target = 0  otherwise
```

Target 1 means defer to M3; ties select cheaper M1. The target may use M3 and gold only
as supervised training/evaluation outcomes. Neither may enter the deployable feature
matrix or runtime decision. The system always selects one complete six-bit vector;
per-label mixing is forbidden.

The EXP-059 `oracle_choose_m3` array is not used as the formal router target because it
does not satisfy the outer nested-threshold construction above. It remains an upstream
diagnostic only.

## Pre-Qwen Feature Whitelist

The first deployable feature matrix has exactly 14 columns, in this order:

```text
m1_probability_love
m1_probability_joy
m1_probability_surprise
m1_probability_anger
m1_probability_sadness
m1_probability_fear
m1_mean_binary_entropy
m1_max_binary_entropy
m1_minimum_threshold_margin
m1_predicted_cardinality
m1_highest_probability
m1_lowest_probability
character_length
m1_token_length
```

`m1_minimum_threshold_margin` and `m1_predicted_cardinality` use the nested M1 threshold
available for that partition. Character and M1-token lengths come from EXP-058. All 14
features are available before Qwen is called. A `StandardScaler` is fitted inside each
outer router training partition.

Raw M1 logits are omitted because identity probabilities are an invertible, redundant
representation. Sentence, punctuation and casing features are omitted because they
would require reopening raw text. M3 token length is omitted because the first routing
path must not require Qwen tokenization.

Forbidden runtime features include:

- all M3 probabilities, logits, uncertainty, token lengths, hidden states and output;
- gold labels, oracle decisions, correctness, loss and M1-M3 disagreement;
- sample IDs, duplicate-component IDs and fold IDs;
- raw text or any validation/test-derived statistic.

IDs and fold/component membership may be used only for alignment, leakage checks,
cross-fitting and component bootstrap, never as model columns.

## Frozen Policies

The experiment compares:

- R0 `m1_only`: 0% Qwen calls;
- R1 `m3_only`: 100% Qwen calls;
- R2 `m1_max_entropy`: call M3 on the highest M1 maximum-entropy scores;
- R3 `m1_threshold_proximity`: call M3 on the smallest M1 threshold margins;
- R4 `logistic_router`: `StandardScaler` plus L2 logistic regression with
  `C=1.0`, `class_weight=balanced`, `solver=liblinear`, `max_iter=1000` and
  `random_state=42`.

R2 uses maximum entropy because EXP-059 froze it as M1's selected abstention method.
No MLP, tree ensemble, XGBoost or additional feature/model search is allowed.

An explicit random-routing diagnostic uses 100 deterministic component-aware
repetitions at each fold-policy matched call count. It is a comparator, not a candidate
deployment policy.

## Call-Rate Curve

Frozen target Qwen call rates are:

```text
0%, 5%, 10%, 15%, 20%, 30%, 50%, 100%
```

For each outer fold and policy, derive the score cutoff from outer router-training rows
only and apply that cutoff to the held-out fold. Ties at the cutoff are all routed; the
actual held-out call rate is therefore reported and may differ from its target. No
held-out score ranking or gold label may be used to force an exact rate. Gate eligibility
uses actual aggregate call rate, not the nominal target.

## Metrics

Primary system metrics at every policy/rate point:

- six-label Macro-F1;
- five-label Macro-F1 excluding `surprise`;
- Hamming loss;
- actual Qwen call rate.

Secondary system metrics:

- Micro-F1 and strict subset accuracy;
- per-label precision, recall, F1 and support;
- M3 calls per 1,000 rows;
- routed-system risk-coverage using the three EXP-059 uncertainty definitions;
- positive-label retention under abstention.

Router discrimination metrics are diagnostic only: PR-AUC, ROC-AUC, precision and
recall for target 1, target prevalence and convergence. Router accuracy is not a primary
result because the defer target is imbalanced.

The first formal run reports call rate as the directly measured cost proxy. It does not
combine historical CPU and Metal timings into a latency claim. If a deployable policy
passes, a separate warm, batch-size-one system benchmark may be registered; it is not
silently folded into this experiment.

## Frozen Feasibility Gate

For each deployable policy, select its candidate only among points with actual Qwen call
rate no greater than 0.20. Candidate tie order is highest six-label Macro-F1, then lowest
Hamming loss, then lower actual call rate, then lower nominal target rate.

A policy passes only when all conditions hold relative to fully cross-fitted M1-only:

1. six-label Macro-F1 gain is at least `0.01`;
2. five-label Macro-F1 gain is at least `-0.005`;
3. Hamming loss does not increase beyond numeric tolerance `1e-12`;
4. at least one non-`surprise` label has an F1 gain of at least `0.005`.

Condition 4 operationalizes the preregistered requirement that a gain not be produced
only by the 31-row `surprise` support. The first version's deployable-routing gate passes
if any of R2-R4 passes. R4's incremental value over simple uncertainty routing is
reported separately at matched nominal call rates; a passing heuristic with a failing
R4 supports a simple policy, not a learned-router claim.

Use 2,000 duplicate-component bootstrap replicates with seed `20260817` to report 95%
percentile intervals for the selected point's six-label/five-label Macro-F1 deltas,
Hamming-loss delta and call rate. Point estimates determine this development gate;
intervals determine whether the result may additionally be described as statistically
stable. This is train-OOF development evidence, not a new independent test.

If no R2-R4 policy passes, stop the branch. Seeds 43/44, feature expansion, deployment
benchmarking and validation development confirmation are not automatically authorized.

## Outputs And Privacy

Private, Git-ignored, mode-`0600` outputs for a separately authorized formal run:

- fully cross-fitted router scores, targets and route masks;
- nested M1/M3 thresholds and complete selected prediction vectors;
- the 14-column feature matrix and feature-standardization parameters;
- anonymous sample/component/fold alignment required for verification.

Public aggregate outputs:

- `run.json` and frozen source/config copies;
- feature contract and fold-level training summary;
- router discrimination metrics;
- call-rate/performance and random-routing CSV files;
- selected operating point, bootstrap intervals and routed risk-coverage outputs;
- figures, report and independent verification.

No public file may expose row-level IDs, folds, gold, logits, probabilities, features,
targets, route scores, route masks, predictions or text.

## No-Result Preflight

The preflight may inspect source hashes, NPZ headers, file modes, frozen public
calibration decisions, dependency availability and output-path emptiness. It must run
synthetic contract tests and an independent verifier. It must not:

- fit a real scaler or router;
- construct real router targets or route scores;
- compute real call-rate/performance metrics or bootstrap intervals;
- access validation, test, model checkpoints or raw text.

Formal router execution remains blocked until this preflight passes and the user gives
a separate instruction to run EXP-060.

## Resource Budget

No-result preflight:

- CPU wall time: at most 5 minutes for the runner and 5 minutes for verification;
- peak memory: at most 2 GB;
- API cost: USD 0;
- model loading/forward: forbidden.

Separately authorized formal run:

- one canonical seed-42 nested OOF analysis;
- CPU wall time: at most 30 minutes plus 30 minutes independent verification;
- peak memory: at most 4 GB;
- API/GPU cost: USD 0;
- no M1/M3 retraining or forward pass.

## Thesis Destination And Claim Boundary

Target destination: conditional RQ-S3 system methods/results and reproducibility
appendix.

A passed EXP-060 may support only the claim that a frozen pre-Qwen policy showed useful
train-OOF routing signal under this dataset and model pair. It does not establish an
independent-test deployment benefit, causal emotional mechanism, universal LLM value,
or generalization to other forums, models or seeds.
