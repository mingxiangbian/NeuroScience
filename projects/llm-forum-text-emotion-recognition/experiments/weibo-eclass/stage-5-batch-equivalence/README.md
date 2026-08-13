# EXP-045: Stage 5 Batch-Equivalence Gate

状态：`Failed`（Minor；仅完成 train-only 初始化，未开始模型推理）

## 失败记录

初始化审计发现 Transformers 5.14.1 的 `apply_chat_template` 默认返回
`BatchEncoding`；运行器将其转成 `list` 后得到的是 `input_ids` 与
`attention_mask` 两个字段名，而不是 token IDs。公开摘要因此错误地显示所有
prompt 长度均为 2，长度分位抽样和 prompt hash 均无效。

本实验在任何模型推理前停止，未读取 validation/test。修复不覆盖本目录，改由
`EXP-046` 显式设置 `return_dict=False` 并校验 token 序列全部为整数。

## 目的

EXP-043 中，332 条 prompt hash 完全相同的 reasoning-on first-clause 样本，在不同
共同批次中只有 273 条最终标签一致。EXP-045 在 train-derived 样本上分离三种来源：

1. 同一 execution mode 跨新进程重放是否稳定；
2. singleton 与 batch 8 是否给出相同最终标签；
3. batch 8 改变共同批次组成后，最终标签是否变化。

本实验不计算分类性能，不读取 validation/test，不训练模型。

## 冻结设计

- 从完整 train 按标签比例分配 16 条，再在标签内按 reasoning-on prompt 长度分位点抽样。
- `singleton-r1/r2`：每次只生成一条，两个新进程重复。
- `batch8-r1/r2`：按冻结 native order 两个新进程重复。
- `batch8-length-stress`：相同 16 条按 prompt length 排序，改变两个 batch 的共同成员。
- 所有条件使用同一 Qwen3-4B BF16、target-only prompt、reasoning on、greedy、
  `max_new_tokens=1024` 和 strict parser。
- 只比较 raw output、parser state 和最终标签；gold label 仅用于 train 抽样分层，
  不用于任何性能指标。

## 预注册决策

1. batch 8 固定重放与 length-stress 的最终标签一致率均为 100%：冻结 batch 8。
2. 否则，singleton 新进程重放为 100%：冻结 singleton。
3. 否则：reasoning-on 不得作为 Stage 5 单次主评估，先登记 reasoning-off 重放门。

即使选择 batch 8，正式 validation 仍必须冻结行顺序、batch size、prefill/completion
batch size、padding/runtime 版本；每个 LoRA adapter 在读取 dev 前还要对同一 train slice
做一次 post-training replay。
