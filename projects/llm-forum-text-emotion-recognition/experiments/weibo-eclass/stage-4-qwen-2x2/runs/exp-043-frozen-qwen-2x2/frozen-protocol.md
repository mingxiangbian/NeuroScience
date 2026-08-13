# EXP-043: Weibo EClass Frozen Qwen Context x Reasoning 2x2

---
date: 2026-08-08
experiment_id: EXP-043
tier: Major
rq: RQ-F1, RQ-F2
status: Registered
stage: stage-4-frozen-qwen-context-reasoning-2x2
dataset_protocol: DATA-WEIBO-TASK-V1
parent_experiment: EXP-041, EXP-042
---

## Question and Expected Contribution

在冻结的 Weibo EClass 七类单标签 validation 上，固定局部前文和 Qwen reasoning mode
是否分别改变最终标签表现，两者是否存在交互？冻结 Qwen 是否达到或超过 EXP-042 的中文
RoBERTa encoder？

正结果可说明 Qwen 的上下文或生成式推理在同任务上提供增量价值。负结果同样有效：它将
说明 4B post-trained decoder 在当前固定标签任务上没有抵消监督 encoder 的性能、格式或
资源优势。本实验不把生成 rationale 当作内部机制证据。

## Frozen Data Boundary

- Dataset protocol: `DATA-WEIBO-TASK-V1`.
- Validation: 1,272 rows, SHA-256
  `99d80e1433bddea7b639983b8fa874e45d585318aa47eb87ab29581e02f72a4a`.
- Train 只允许用于正式 inference 前的 8-row batch/runtime smoke，不计算性能。
- Sealed test inputs and labels are forbidden and absent from the runner config.
- Label order: `anger`, `joy`, `negative`, `neutral`, `no_emotion`, `positive`,
  `sadness`.
- `target_only` 与 `previous_context` 逐条配对；后者只包含冻结 `PrevCL`，不声称是 parent。
- 无前文的 `first_clause` 行在两个 view 中必须渲染为相同 prompt。

## Frozen Model and Prompt

- Model: `Qwen/Qwen3-4B`, revision
  `1cfa9a7208912126459214e8b04321603b3df60c`.
- Local runtime: unquantized MLX BF16 conversion recorded by the frozen model
  manifest; no adapter is loaded.
- Prompt and strict JSON parser are copied from the EXP-041 passed preflight and
  frozen again under EXP-043.
- Output ontology is closed and single-label: `{"label":"<allowed_label>"}`.
- Raw text, prompts, generated reasoning and row-level predictions remain under
  the Git-ignored private data root.

## Frozen 2x2 Conditions

| ID | View | `enable_thinking` |
| --- | --- | --- |
| A | `target_only` | `false` |
| B | `previous_context` | `false` |
| C | `target_only` | `true` |
| D | `previous_context` | `true` |

All conditions use greedy decoding (`temperature=0`), the same model, prompt,
ontology, row order and `max_new_tokens=1024`. Greedy decoding is chosen before
validation to isolate the two factors without adding repeated sampling as a third
factor. MLX batches contain eight rows; batch order is fixed by validation order.

An output that violates the strict parser, omits the reasoning boundary when
thinking is enabled, or reaches the token budget without a valid final JSON is
stored and counted as an incorrect `__invalid__` prediction. It is not repaired,
retried or dropped. Therefore reasoning performance includes its format and token
budget failures as part of deployable behavior.

## Evaluation and Factorial Effects

Primary metric: full-validation Macro-F1 over the seven frozen labels. Auxiliary
outputs: Accuracy, macro precision/recall, Weighted-F1, per-class metrics,
7-by-8 confusion matrix including an `__invalid__` prediction column, strict
parser-valid rate, generated-token counts, batch throughput and peak memory.

Each condition also reports `context_available` and `first_clause` slices. The
paired effects use condition Macro-F1:

- context with reasoning off: `B - A`;
- context with reasoning on: `D - C`;
- reasoning on target only: `C - A`;
- reasoning with context: `D - B`;
- interaction: `(D - C) - (B - A)`.

Paired row bootstrap uses 2,000 resamples and frozen seed
`EXP-043-paired-bootstrap-v1` to report 95% percentile intervals. Intervals describe
sampling uncertainty on this validation set, not repeated-generation variance.

An absolute Macro-F1 difference below `0.005` is a practical tie. Candidate
conditions within `0.005` of the best score are selected in this order: reasoning
off, target only, then lower batch evaluation time. The selected Qwen condition is
compared descriptively with EXP-042 M2 target-only Macro-F1
`0.5949251214214263`; no cross-model significance claim is made from that scalar.

If either context contrast is at least `+0.005` and its paired interval excludes
zero, a later experiment may register correct-vs-shuffled context. EXP-043 itself
does not run that control.

## Resource Gate and Recovery

- API/network access and API cost: forbidden, USD 0.
- Device: local Apple Metal through MLX.
- Formal generations: exactly 5,088, one per row and condition; no retries.
- Maximum new tokens: 1,024 per generation.
- Formal wall-time budget: 24 hours after the train-only smoke.
- Train-only smoke: one 8-row batch with reasoning off and one with reasoning on.
  It must project the full 2x2 below 24 hours with a 1.25 safety multiplier, keep
  peak memory below 20 GB and yield at least one parser-valid output per mode.
- A process interruption may resume only the missing suffix of a condition after
  verifying that existing private rows form an exact, duplicate-free prefix.
  Existing rows are never regenerated or overwritten.
- Stop on source/data/model-manifest hash drift, output-directory reuse, batch
  OOM, nonfinite timing, row-order mismatch, public source-text leakage, test
  access or budget overflow.

Batch latency and throughput characterize offline evaluation only; they are not
reported as single-user interactive latency.

## Planned Artifacts and Thesis Destination

- Public frozen protocol/config/source copies, run status, four aggregate
  condition reports, factorial analysis, report, resource summary and independent
  verification.
- Private raw generations, strict parser records, gold/prediction rows and prompt
  hashes.
- Results chapter: Qwen 2x2 table and context/reasoning interaction figure.
- Discussion chapter: encoder-vs-decoder boundary, parser/token-budget failures and
  the limited meaning of fixed local context.

## Pass Signal

1. Train-only batch/runtime smoke passes without validation/test access.
2. All four conditions contain exactly 1,272 unique, ordered validation outputs.
3. Parser-invalid outputs remain in the denominator and all required metrics,
   slices, factorial effects and resource fields exist.
4. Independent verifier re-parses every raw output and reconstructs all metrics,
   effects, selection and privacy checks with zero mismatch.
5. `run.json` confirms validation access, no test access and no adapter loading.

Passing EXP-043 authorizes a Stage 5 LoRA protocol decision. It does not authorize
LoRA execution, migration or the held-out test gate.
