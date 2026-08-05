# EXP-038: GoEmotions Frozen Test Gate

Date registered: 2026-08-04  
Tier: Major  
Research questions: RQ-G1, RQ-G2  
Status at registration: test absent; scientific matrix frozen; user authorized one formal test pass

## Question

在官方 GoEmotions full-taxonomy test split 上：

1. EXP-020 的现代 BERT-base-cased 三随机种子复现与论文报告的 BERT test
   Macro-F1 `0.46` 相差多少？
2. 冻结 Qwen3-1.7B prompting 与监督 LoRA 相对同数据集编码器基线增加了什么，还是
   仍主要表现为成本更高的标签生成器？
3. 修复训练 target 与推理 ontology 后，EXP-033 seed 42 是否改变上述结论？

负结果仍然有效：如果 LLM 未超过 BERT，它会给出本地 1.7B 生成式模型在细粒度多标签
情绪识别上的现实边界，并为后续论坛上下文实验提供冻结参照。

## Frozen Evaluation Matrix

正式 test 共 9 个单元，每个单元只推理一次，不在 test 上挑模型、seed 或 ensemble：

| Group | Frozen units | Selection basis before test | Role |
| --- | --- | --- | --- |
| EXP-018 | deterministic TF-IDF + OVR Logistic Regression | 唯一冻结简单基线，threshold=0.5 | sanity baseline |
| EXP-020 | BERT-base-cased seeds 42/43/44 | 论文对齐训练条件，threshold=0.3；三个 seed 全部报告 | primary supervised reproduction |
| EXP-025 | Qwen3-1.7B post-trained, constrained `few-shot-synthetic-3` | dev Macro-F1 规则选定 | frozen prompting comparison |
| EXP-029 | Qwen3-1.7B LoRA seeds 42/43/44, constrained zero-shot | 各 seed 的 dev 规则均选定 zero-shot | historical LoRA comparison |
| EXP-033 | target-aligned Qwen3-1.7B LoRA seed 42, aligned prompt + open-neutral decoder | 唯一已完成且验证的 target-aligned adapter | task-aligned LLM result |

EXP-029 在训练时移除了 1,396 个 `neutral+emotion` target 中的 `neutral`，因此属于
历史 ontology-misaligned 条件。它会被完整报告，但不能与 EXP-033 合并成一个三 seed
统计量，也不是主任务对齐结论。EXP-033 的 dev improvement gate 未通过；本次保留它
是为了回答用户明确提出的 test 行为问题，不据此补训 seeds 43/44。

不纳入 EXP-026、EXP-031、EXP-033 seeds 43/44、新阈值、新提示或新 checkpoint。

## Data Binding

- Source: Google Research `goemotions/data/{train,dev,test}.tsv`.
- Fixed upstream revision: `8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0`.
- Labels: 28 labels in the frozen `emotions.txt` order.
- Expected test rows: 5,427.
- Test is downloaded only after both no-test preflights pass.
- Acquisition may bind transport facts only: byte count, SHA-256, row count, column count and
  uniqueness/range checks. It must not display label distribution, metrics, examples or model output.
- The final config must be identical to the preregistered config after normalizing the bound test
  byte count and SHA-256. Any scientific difference aborts the run.

Raw test text and comment IDs remain under the gitignored
`data/goemotions/official/test.tsv`. Public artifacts contain only one-based row numbers, gold and
predicted labels, scores or generated label JSON, aggregate timing and hashes.

## Metrics And Reporting

Primary metric: Macro-F1 over all 28 labels.

Required auxiliary metrics:

- macro precision and recall;
- Micro-F1, weighted F1 and samples F1;
- strict subset/exact-match accuracy;
- hamming loss and label accuracy;
- per-label precision, recall, F1, gold support and predicted support;
- per-label `[[TN, FP], [FN, TP]]` matrices;
- gold/predicted label cardinality and empty predictions;
- for Qwen: parser validity, finish reasons, tokens, latency, MLX peak memory, constraint
  intervention and API cost.

Three-seed families report mean and sample standard deviation. Single-run conditions are plainly
marked as such. Ranking is descriptive only and cannot trigger post-test selection. The paper's
BERT Macro-F1 `0.46` is an external same-split, nominally same-task reference, not a claim of
bitwise reproduction because this implementation uses modern PyTorch/Transformers/MPS.

## Test Gate And Stop Rules

Before acquisition:

- test path and output path must be absent;
- every source run and independent verification must match its frozen SHA-256;
- TF-IDF and each BERT checkpoint must reproduce the first two saved dev probability rows;
- each Qwen model/adapter must reproduce the first saved dev generated-output hash under its
  frozen prompt and decoder;
- both preflight reports must say `Passed`, `test_split_accessed=false`, and bind the exact
  preregistered config hash.

During formal execution:

- classical/BERT runs first, then five Qwen units;
- technical resume is allowed only from an exact verified prefix with unchanged config hash;
- completed rows are never regenerated;
- no retry, synonym repair, threshold change, prompt change, checkpoint selection or ensemble;
- stop on hash drift, malformed rows, NaN/nonfinite values, MPS/MLX failure, peak MLX memory above
  14 GB, or active Qwen generation time above 4 hours for any one unit.

After execution, a separate verifier reads the saved predictions, independently rebuilds all
metrics and confusion matrices, checks all artifact hashes, and cross-checks each Qwen generation
record against its prediction row. Only `verification.json: status=Verified` permits publication.

## Resource Budget

- Formal test passes: 1 per listed unit, 9 units total.
- BERT/TF-IDF wall time: at most 2 hours total.
- Qwen active generation: at most 4 hours per unit, 20 hours total.
- Peak MLX memory: at most 14 GB.
- External API calls and API cost: none, USD 0.
- Hardware: local Apple M3 with MPS/MLX.

## Thesis Destination

- Results: GoEmotions frozen test comparison table and per-label appendix.
- Discussion: supervised encoder versus local generative classifier; ontology-alignment limitation;
  dev-to-test generalization and the distinction between classification performance and mechanism.
- Evidence log: one EXP-038 entry, with EXP-029 explicitly labeled historical misalignment.

No test result may be used to revise this protocol or rerun the same matrix.
