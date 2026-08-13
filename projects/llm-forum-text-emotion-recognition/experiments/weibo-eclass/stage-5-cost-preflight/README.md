# EXP-044: Stage 5 本地 LoRA 成本预检

状态：`Verified`（Minor；独立校验 13/13）

## 目的

在不读取 validation/test 的前提下，用 Qwen3-4B BF16 和已经通过 EXP-041
验证的精确 LoRA 插入方案运行 200 个训练 step，回答两件事：

1. 16 GB 统一内存的本机能否稳定执行 Stage 5 的真实训练形状；
2. 按完整 5,995 条 train、2/3 epochs、3 seeds 外推时，本地顺序训练需要多久。

本实验只形成资源与实现证据，不报告分类性能，也不替代后续 Stage 5 Major protocol。

## 固定边界

- 数据：`DATA-WEIBO-TASK-V1` 的 train split，SHA-256 已冻结；validation/test 禁止访问。
- 模型：`Qwen/Qwen3-4B` revision
  `1cfa9a7208912126459214e8b04321603b3df60c`，MLX BF16，非量化。
- 输入：target-only；输出：一个严格 JSON 标签。
- 训练目标：label-only SFT，不使用人工或合成 rationale。Qwen3 chat template 自动加入的
  空 `<think>` wrapper 属于模板边界，运行前必须验证。
- LoRA：blocks 20-35，attention q/k/v/o 与 MLP gate/up/down，共 112 个插入点；
  rank 8、scale 20、dropout 0、AdamW、learning rate `1e-5`。
- 抽样：按完整 train 的标签比例分配 200 个名额，再在每个标签内按 token 长度分位点
  系统抽样；样本原文和 ID 只写入 gitignored 私有目录。
- 预算：最多一次 200-step 运行，45 分钟，峰值内存门 13 GB，API 成本 0。

## 运行

```bash
/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-cost-preflight/run_cost_preflight.py

/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/weibo-eclass/stage-5-cost-preflight/verify_cost_preflight.py
```

公开产物位于 `runs/exp-044-local-lora-cost-preflight/`；训练样本、完整 stdout 和 adapter
位于配置指定的 `derived-private/` 目录，不进入 Git。

## 结果

- 200 step 在 `355.254` 秒内完成；稳态中位吞吐 `0.575 step/s`。
- 峰值内存 `8.679 GB`，低于冻结的 `13 GB` 门；无 OOM、NaN 或非有限 adapter 权重。
- 112 个 LoRA 插入点、224 个 adapter tensors 和 `7,340,032` 个可训练参数全部匹配；
  112 个 `lora_b` tensors 均非零，checkpoint 重载后 logits 有限。
- 2 epochs 单 seed 原始训练投影为 `5.79 h`，含 1.25 安全系数为 `7.24 h`；
  3 seeds 顺序训练为 `21.72 h`。3 epochs 对应 `10.86 h/seed` 和 `32.58 h/3 seeds`。
- 投影只含训练，不含 dev 生成、checkpoint 比较和错误分析。本机训练在技术上可行，
  是否值得承受顺序训练时长仍需在 Stage 5 Major protocol 中决定。

详见 [`runs/exp-044-local-lora-cost-preflight/REPORT.md`](runs/exp-044-local-lora-cost-preflight/REPORT.md)
和独立校验
[`verification.json`](runs/exp-044-local-lora-cost-preflight/verification.json)。
