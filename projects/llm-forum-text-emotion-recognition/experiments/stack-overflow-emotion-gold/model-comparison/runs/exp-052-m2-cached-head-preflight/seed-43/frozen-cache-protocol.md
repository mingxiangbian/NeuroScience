# EXP-052 Feature-cache Reuse Gate

- Parent experiment: `EXP-052` / M2 Frozen Qwen + Linear Head
- Tier: Major infrastructure gate; no performance experiment
- RQ: `RQ-S1`
- Registered: 2026-08-14
- Status: `Registered; integrity verification only`

## Purpose

EXP-052 seed 42 已生成并独立验证 train/validation 的冻结 Qwen hidden-state cache。
Qwen、数据、prompt、tokenization、precision 和 pooling 在 M2 三个 seed 间保持不变；seed
只影响线性 head 初始化、batch order 和后续优化。因此，重复执行 Qwen 前向不会增加新的
科学变量，只会增加约 40 分钟计算成本。

本 gate 将 seed 42 cache 冻结为可复用、只读的私有输入。它不训练模型、不计算性能、不读取
test，也不授权 seeds 43/44。

## Reuse Invariants

只有同时满足以下条件，cache 才可复用：

- 实验仍为 `EXP-052` M2 frozen Qwen + linear head；不得用于 EXP-053/M3、EXP-054/M4
  或其他会改变 Qwen 参数的实验。
- 数据为 `DATA-SO-TASK-V1` 的既定 train/validation，文件 SHA-256、行数、sample order
  digest 和 token stream digest 均不变。
- 模型仍为 `Qwen/Qwen3-4B` revision
  `1cfa9a7208912126459214e8b04321603b3df60c`，MLX BF16 未量化。
- prompt、chat template、tokenizer、`enable_thinking=false`、max length 384、truncation 和
  `final_layer_last_non_padding_input_token_after_empty_think_wrapper` pooling 均不变。
- cache 文件 SHA-256、字节数、shape 和 `float32` dtype 均与本 gate 一致，所有值有限。
- consumer 以只读 mmap 打开 cache；训练前后均核验 cache SHA-256，禁止原地标准化、shuffle、
  cast、覆盖或追加。
- consumer 自己生成 seed-specific head、batch order、checkpoint、prediction 和 bootstrap；
  不得复用 seed 42 的 head、optimizer state、batch order 或 validation prediction。

## Frozen Source

源运行必须是已经完成并通过 `70/70` 独立检查的 EXP-052 seed 42 train + validation gate，
且 source run 与 source verification 都明确记录 test 未访问。train/validation feature cache
仍保存在 Git ignored 私有目录；hidden state 可能编码原文信息，不得公开提交。

## Consumer Record

未来每个 seed 的 run 必须额外记录：

- 本 gate 的 `run.json` 与 `verification.json` 路径和 SHA-256。
- cache provenance 为 `verified_seed_42_reuse`。
- 两个 cache 的使用前/使用后 SHA-256。
- `qwen_forward_executed=false`、`feature_extraction_seconds=0` 和实际 cache validation/load
  时间。
- seed-specific head initial hash、batch-order hash，以及缓存之外的全部常规训练与验证产物。

## Invalidating Changes

以下任一变化必须重新提取 feature，不得沿用本 cache：数据或顺序、输入视图/context、标签进入
feature 生成过程、模型 revision、precision/quantization、prompt/chat template、tokenizer、
thinking mode、sequence length、truncation、pooling layer/token 或 hidden-state dtype。

## Explicit Non-authorization

本 gate 只验证复用边界。它不授权 seeds 43/44 的 head 训练或 validation 指标，不授权 test、
TEST-READY、M3/M4、context、router、错误分析或任何新的论文性能结论。后续每个 seed 仍需独立
授权，并把本 gate 的已验证哈希作为前置条件。
