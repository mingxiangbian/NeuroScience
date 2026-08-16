# EXP-050: Stack Overflow C0 共享模型预检

- Experiment ID: `EXP-050`
- Tier: Minor
- RQ: `RQ-S1`
- Parent: `DATA-SO-TASK-V1`
- Registered: 2026-08-13
- Status: `Verified`

## Purpose

在正式训练 M1-M4 前，用 24 条确定性选出的 train 样本验证共同输入、六维多标签 loss、
M2/M3 匹配初始化、LoRA 插入与 M4 严格生成格式。本实验不回答哪种模型更好，也不报告
Macro-F1、Accuracy 或其他任务性能。

## Frozen Boundary

- 唯一允许读取的项目数据文件是 `train.jsonl`，SHA-256 为
  `fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc`。
- 禁止读取、glob、遍历或加载 validation、test inputs、sealed test labels 和 source XLSX。
- 样本选择 namespace 为 `EXP-050-train-only-smoke-v1`；24 条必须覆盖六个正标签、neutral
  和 cardinality 2，且每个标签同时有正例和负例。
- 所有阶段最多执行两个 optimizer steps；M4 最多生成四条。任何输出都不进入模型选择。
- 公开产物不得保存原文、逐行标签、sample ID、component ID、raw generation 或预测。

## Pass Gates

1. 静态门：数据、prompt、tokenizer、模型 manifest 哈希准确，label order 完全一致；共享 Qwen
   prompt 的 train token 长度均不超过 384，空 think wrapper 保持在末端。
2. M1 门：RoBERTa 产生 `[batch, 6]` logits，unweighted BCE finite，至少一个 trainable
   parameter 在两步中改变。
3. M2 门：Qwen final-layer 最后一个输入 token hidden 为 `[batch, 2560]`；base 全冻结，只有
   `Linear(2560,6)` 的 15,366 个参数可训练，loss finite 且 head 改变。
4. M3 门：M2/M3 seed 42 的 head 初始 tensor hash 完全相同；LoRA 只插入最后 16 层的 112 个
   固定模块，初始增量为 0；只有 LoRA + head 可训练，head 与至少一个 `lora_b` 在两步中改变。
5. M4 门：assistant target 是 canonical JSON；prompt loss 被 mask；LoRA 插入集合与 M3 相同；
   两步生成式 loss finite；四条 greedy 输出按冻结 parser 解析，invalid 允许出现但不得 retry、
   repair 或改变 parser。
6. 独立 verifier 从源文件、冻结代码与公开聚合产物复算全部声明，validation/test access 均为
   false。任一门失败即停止，不启动 EXP-051～054 正式训练。

## Backend And Budget

M1 使用既有 `emotion-roberta` PyTorch 环境；M2-M4 使用既有 `emotion-llm-mlx`、Qwen3-4B
BF16 和 Apple Metal。总 wall-time 上限 45 分钟，峰值 MLX memory 上限 13 GB，网络/API
禁用，费用 USD 0。未来若正式训练迁移至 CUDA，必须另做同后端 train-only 等价性预检；
本机 EXP-050 不能替代该门。

## Output

运行目录：`model-comparison/runs/exp-050-shared-model-preflight/`。保存冻结代码/config、
`run.json`、各阶段公开报告及独立 verification；临时 smoke 选择、raw output 和权重仅保存在
gitignored private 目录并在验证后删除或继续私有保存。

登记本身不构成模型证据，也不授权正式训练或 validation/test 访问。

## Correction Note (2026-08-13)

第一次执行在 M3 的第 0 步匹配门停止。M2 对 wrapper 的 `head.weight/head.bias` 取 hash，
M3 对 head 本体的 `weight/bias` 取 hash；hash 包含参数名，因此同一 seed 的相同 tensor 被误判为
不同。失败发生在 LoRA 插入和 optimizer step 前，未产生模型结果，也未访问 validation/test。

修正仅统一 digest scope：M2 与 M3 都直接对 head 本体取 hash。模型、数据、seed、初始化、训练、
指标和通过标准均未改变。旧运行目录保留为 `exp-050-shared-model-preflight-attempt-1/`；修正后的
尝试必须从 static 重跑并重新冻结全部文件。

## Execution Result (2026-08-13)

修正后的完整执行通过全部五个 stage，独立 verifier 通过 `77/77` 项检查：

- static：24 条固定 train-only 样本覆盖六个标签、5 条 neutral 和 4 条双标签样本；全量 train
  的 RoBERTa/Qwen 最大长度为 222/341，均未截断。
- M1：两步产生 `[12,6]` logits，BCE finite，分类头参数改变。
- M2：主干冻结，仅 15,366 个线性头参数可训练；pooling/logit shape 为 `[1,2560]`/`[1,6]`。
- M3：M2/M3 第 0 步 head 与 logits hash 匹配，LoRA 初始函数增量严格为 0；112 个插入点、
  7,340,032 个 LoRA 参数及 15,366 个 head 参数符合合同，两步后 112/112 个 `lora_b` 非零。
- M4：M3/M4 LoRA 初始 hash 匹配，assistant-only loss mask 生效，两步 loss finite；四条 greedy
  smoke 输出均被严格 parser 确定性处理，未 retry 或 repair。`0/4` canonical-valid 仅是两步
  smoke 的格式观察，不构成分类性能结论。

成功运行合计 stage wall time 为 44.18 秒，Qwen 阶段峰值 MLX memory 为 8.91 GB。全程只读取
train，未访问 validation/test，未计算 Accuracy、Macro-F1 或其他性能指标；EXP-051 至
EXP-054 的正式执行仍需单独启动。
