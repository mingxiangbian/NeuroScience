# EXP-052: M2 Frozen Qwen + Linear Head

- Experiment ID: `EXP-052`
- Tier: Major
- RQ: `RQ-S1`
- Parent: `DATA-SO-TASK-V1`, execution gated by `EXP-050`
- Registered: 2026-08-13
- Status: `Registered; formal execution not authorized`

## Question

冻结的 post-trained Qwen3-4B final representation 中，有多少六标签情绪信息可以由一个线性
head 解码？该实验只支持线性可解码性，不说明内部情绪机制。

## Frozen Configuration

- Qwen: `Qwen/Qwen3-4B` revision `1cfa9a7208912126459214e8b04321603b3df60c`，MLX
  BF16 未量化，manifest SHA-256
  `da447350d9e43213dacc1202da03b50d7e7114b0a4fe2904ff353240b404a641`。
- Prompt: `prompt-v1.json` SHA-256
  `0722ff947ba030cdf5b42358c7ba45a4d0d6372ccf0e2be28d131a0c24bdb90d`；官方 chat
  template hash `a55ee1...74d8`；`enable_thinking=false`，max length 384，right-truncate target
  while preserving the complete chat suffix。取 final norm 后、最后一个非 padding 输入 token。
- Head: 带 bias 的 `Linear(2560,6)`，无 MLP、dropout 或额外 pooling；15,366 个 trainable
  parameters。Qwen 全冻结，private feature cache 使用 float32 并保存来源/prompt/token hash。
- Seeds `42/43/44`；每个 seed 从确定性初始化的新 head 开始；2 epochs、batch 1、6,720
  optimizer steps、AdamW `1e-4`、weight decay `0.01`、unweighted BCE，无 scheduler。

## Matched M2/M3 Contract

对每个 seed，EXP-052 与 EXP-053 必须共享 head 初始 tensor hash、样本 permutation、batch
order、head optimizer、head learning rate、更新步预算和 checkpoint rule。EXP-053 从同一初始
head 开始，不得继承训练后的 M2 head。若 MLX 不能可靠执行不同 LoRA/head learning rate，M3
的共享单优化器率必须在 EXP-050 后、正式结果前写入 correction，并同步说明 M2 公平边界；
不得事后按结果修改。

## Selection, Evidence, Budget

checkpoint、阈值、指标与 test gate 完全沿用共享合同和 EXP-051 的顺序。逐 seed 保存 private
feature/hash、head、validation probabilities 和公开聚合。总预算：feature extraction 4 小时、
三 seed head 训练 1 小时、峰值 MLX 13 GB、API cost 0。任一 Qwen 权重、token、position、
head-init 或 batch-order mismatch 即失败。

论文去向：M2-M3 增量对照和 frozen representation 的相关性证据。
