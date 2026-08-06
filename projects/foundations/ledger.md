# 台账 · Ledger

> 结算制学习系统的唯一账本。规则见 [ai-professional-roadmap.md](ai-professional-roadmap.md) 的"运行系统"。
> 数字只涨不跌。空窗不记债。没有日期义务——记录日期只是为了日后校准真实节奏。

## 当前状态

- **活动单元**：U2 揭穿作弊
- **已结算**：1 个
- **玩耍券**：0 张

## 断点（下次从这里开始）

> 每次 session 结束写三行：做到哪了 / 下一步第一个动作 / 有没有墙。也可以直接告诉 Claude，由它写。

- **做到哪了**：U1 已结算。完成 causal / non-causal 的 epoch-average loss 对照；causal 每轮略高但快速追上，两组最终接近随机末位决定的 `0.6908` 理论下限。
- **下一步第一个动作**：为 U2 先写一个最小 eval case——固定一段训练中未见的递增前缀，分别定义 teacher-forced 观测与“只给前缀、逐 token 生成”的 expected behavior。
- **有没有墙**：non-causal 与 causal checkpoint 没有分别命名保存，U2 开始时需要先生成两份可区分、不会互相覆盖的模型权重；U1 也没有逐 step 原始 loss 日志，此限制已入结算笔记。

## 结算记录

| # | 日期 | 单元 | 产物 | sessions |
| --- | --- | --- | --- | --- |
| 1 | 2026-08-07 | U1 修掩码 · 实验单元 | `Transformer-Decoder-Toy-Project/loss_mask_comparison.png`、`plot_loss_comparison.py`；[Causal Mask：低 Loss 为什么可能是假象](roadmap/modules/evals-debugging.md#causal-mask低-loss-为什么可能是假象) | ≥2（跨会话） |

## 校准记录

> 事件触发（任一满足，由 Claude 主动发起）：结算满 3 个主线单元 / 一次候选专长试驾结束 / 实验推翻原有理解 / 贾维斯 0.x 设计明显变化 / 进入新阶段。
> 每次四问，几行即可：理解改变了什么？哪个子系统更重要/更不重要了？当前主线仍是信息增益最高的下一步吗？哪个假设该降级、删除或继续验证？
> 结算记录永久只涨；这里的"当前理解"和置信度允许下降。

## 撞墙记录

> 三行墙格式：在做什么 / 卡在哪 / 试过什么。撞墙记录可升级为失败分析笔记，照常结算一个单元。
