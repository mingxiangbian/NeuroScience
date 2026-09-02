# 台账 · Ledger

> 结算制学习系统的唯一账本。规则见 [ai-professional-roadmap.md](ai-professional-roadmap.md) 的"运行系统"。
> 数字只涨不跌。空窗不记债。没有日期义务——记录日期只是为了日后校准真实节奏。

> **怎么用（全部操作就四句口令，对 Claude 说）**：
> 「**开工**」= 读断点、直接开干 ｜ 「**记断点**」= 收工留三行 ｜ 「**撞墙**」= 卡住登记、合法离场 ｜ 「**结算 Ux**」= 过判据、落印、记账全由 Claude 代办。
> 网页是展示柜（看台账和主板用的），不是操作台——操作全在对话里。

## 当前状态

- **活动单元**：玩耍单元「DeepSeek-V4 从 Preview 到 GA」；主线 U3 原位暂存
- **已结算**：2 个
- **玩耍券**：0 张（累计获得 1 张，已使用 1 张：DeepSeek-V4 版本审读）
- **进行中玩耍单元**：DeepSeek-V4 从 Preview 到 GA——先分清总体架构、正式发布增量与尚未公开的信息；U3 原位暂存，讨论结算后恢复。

## 断点（下次从这里开始）

> 每次 session 结束写三行：做到哪了 / 下一步第一个动作 / 有没有墙。也可以直接告诉 Claude，由它写。

- **做到哪了**：DeepSeek-V4 版本审读第 1 步已通过：能区分发布 checkpoint、相同架构下的参数变化与 inference effort；能说明 benchmark 测到的是 checkpoint 与 Harness、推理预算、评测设置的组合，也能区分“使用模型”与“解释/复现 GA 增量”所需的证据。修正：Flash Preview → 0731 的 architecture 不变，DeepSeek thinking mode 会忽略 sampling 参数，因此二者不是这次比较中的有效混杂因素。
- **下一步第一个动作**：按 [DeepSeek-V4 主报告阅读验收清单](../../papers/deepseek-v4/reading-checklist.md) 完成主报告阅读；读完后一次性回答 `Q01–Q12`，再共同检查。DSpark 暂不混入本轮。
- **有没有墙**：没有。U3 的六行故事骨架原位保留；U7 的 DeepSeek Harness 生产架构对照尚未进行，只是未来候选，不消耗玩耍券。

## 进行中玩耍单元任务单

### DeepSeek-V4 从 Preview 到 GA

**核心问题**：正式版究竟改变了什么？V4 如何把百万 token 上下文与更快生成变成可部署系统，而哪些能力提升仍不能归因到单一机制？

按问题读，不从第一页顺序通读：

1. **先判版本**：读 [DeepSeek 官方 changelog（2026-08-13 / 2026-07-31）](https://api-docs.deepseek.com/updates/) 与 [DeepSeek-V4-Pro-0813 模型卡](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro-0813)的 Introduction / Notes，分开记录“沿用主干”“重新 post-train”“附加 DSpark”“仍未公开”。
2. **再读主干**：读 [DeepSeek-V4 技术报告 v1](https://arxiv.org/abs/2606.19348)的 Abstract、Figure 2、§2.3、§3.5.1 与 §6，只追一个问题：CSA / HCA 如何减少长上下文的计算和 KV cache，同时仍守住 decoder 的 causal 信息边界？
3. **最后读正式版新增模块**：读 [DSpark](https://arxiv.org/abs/2607.05147)的 Figure 1、§2.1、§3.1–3.2 与 §5.4，追两个问题：为什么 draft 可以并行提出多个 token，却不等于偷看真实未来；target verification 如何保证最终分布不被 draft 擅自改写？

读完回来只带六行，不写流水账：

1. Preview → GA 已确认的变化。
2. 主干中让 1M context 可行的核心机制。
3. DSpark 的 draft → verify 流程。
4. 它与 U1/U2 的 future-token leakage 有何本质区别。
5. 哪个 benchmark 结论不能从现有证据推出，以及为什么。
6. 一个仍未解决的问题，或一个会改变贾维斯 0.x 设计的判断。

**结算信号**：能不看原文解释第 3、4、5 行，并明确区分“论文报告”“正式模型发布说明”“自己的推断”。

## 结算记录

| # | 日期 | 单元 | 产物 | sessions |
| --- | --- | --- | --- | --- |
| 1 | 2026-08-07 | U1 修掩码 · 实验单元 | `Transformer-Decoder-Toy-Project/loss_mask_comparison.png`、`plot_loss_comparison.py`；[Causal Mask：低 Loss 为什么可能是假象](roadmap/modules/evals-debugging.md#causal-mask低-loss-为什么可能是假象) | ≥2（跨会话） |
| 2 | 2026-08-14 | U2 揭穿作弊 · 实验单元 | `DL/transformer/u2_leakage_experiment.py`、`u2_artifacts/u2_results.json`、对比图与两份 checkpoint；[Prefix-only 评估：怎样揭穿 Future-token Leakage](roadmap/modules/evals-debugging.md#prefix-only-评估-怎样揭穿-future-token-leakage) | ≥2（跨会话） |

## 校准记录

> 事件触发（任一满足，由 Claude 主动发起）：结算满 3 个主线单元 / 一次候选专长试驾结束 / 实验推翻原有理解 / 贾维斯 0.x 设计明显变化 / 进入新阶段。
> 每次四问，几行即可：理解改变了什么？哪个子系统更重要/更不重要了？当前主线仍是信息增益最高的下一步吗？哪个假设该降级、删除或继续验证？
> 结算记录永久只涨；这里的"当前理解"和置信度允许下降。

## 撞墙记录

> 三行墙格式：在做什么 / 卡在哪 / 试过什么。撞墙记录可升级为失败分析笔记，照常结算一个单元。
