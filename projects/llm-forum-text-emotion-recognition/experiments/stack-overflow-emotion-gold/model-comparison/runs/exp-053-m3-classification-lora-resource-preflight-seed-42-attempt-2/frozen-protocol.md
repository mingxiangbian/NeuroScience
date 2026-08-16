# EXP-053: M3 Qwen Classification LoRA

- Experiment ID: `EXP-053`
- Tier: Major
- RQ: `RQ-S1`
- Parent: `EXP-052`, execution gated by `EXP-050`
- Registered: 2026-08-13
- Status: `Registered; formal execution not authorized`

## Question

在 pooling、linear head、初始化、数据顺序和更新预算与 M2 匹配时，LoRA 任务适配是否提高
classification interface 下的多标签识别？有效对比是 `M3 - M2`，不是 LLM 与 encoder 的
纯架构因果比较。

## Frozen Configuration

M3 继承 EXP-052 的 Qwen、prompt、tokenization、final-token pooling、head、三 seed、2 epochs、
batch 1、6,720 steps、checkpoint 和阈值规则。loss 为 unweighted binary cross entropy with
logits。head 每个 seed 必须与对应 M2 的初始 tensor hash 一致。

LoRA 只插入 blocks 20-35 的以下 7 个模块：`q_proj/k_proj/v_proj/o_proj` 与
`gate_proj/up_proj/down_proj`，共 112 个 insertion points；rank 8、scale 20、dropout 0，
MLX 默认随机 `lora_a` + zero `lora_b`，因此初始 LoRA 增量严格为 0，而不是把 A/B 都置零。
使用 AdamW `1e-5`、weight decay `0.01` 和 gradient checkpointing。只有 LoRA tensors 与
15,366-parameter head 可训练；base、embedding、norm 与 LM head 全冻结。

当前共享合同为单一运行中的 LoRA `1e-5` 与 head `1e-4`。EXP-050 必须先证明独立 optimizer
更新不会破坏参数白名单和 M2/M3 batch equivalence；若实现不能可靠支持，必须在任何正式
seed 前登记 correction，不能静默退化为一个 learning rate。

## Evaluation And Claim Boundary

评价与 EXP-052 完全一致。主对比按 seed 配对报告 `M3 - M2` Macro-F1、component bootstrap
区间、逐类收益、wall time、训练 token 和峰值内存。M1 vs M3 只作强 encoder 与
classification-style LLM 的行为/成本比较。线性 probe 或 LoRA 性能不构成机制证据。

三 seed 总预算 24 GPU/Metal 小时，峰值 13 GB，API cost 0；每 seed 一次正式训练。初始 logits
不与 M2 相等、LoRA insertion/count 不符、base 参数改变、loss non-finite 或任一 seed 缺失均
判 Failed，且不进入 TEST-READY。

论文去向：Results 的适配增量与成本表，Discussion 的 representation/adaptation 边界。
