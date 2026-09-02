# DeepSeek-V4 主报告阅读验收清单

- **论文**：DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence
- **arXiv**：[2606.19348](https://arxiv.org/abs/2606.19348) ｜ [HTML 正文](https://arxiv.org/html/2606.19348) ｜ [Hugging Face 论文页](https://huggingface.co/papers/2606.19348)
- **版本核对**：截至 2026-09-01，arXiv 仍只有 2026-04-26 提交的 `v1`，正文描述的是 Preview。
- **本清单范围**：只读 V4 主报告。GA 发布说明、Flash-Vision-Exp 与 DSpark 是外部增量，不混入本次论文验收。

## 怎么使用

- 阅读时不必逐题写长答案；先在脑中定位，读完后统一回来回答 `Q01–Q12`。
- 每题用自己的话回答 2–5 句，并附一个章节、图或表作为证据锚点。
- 每个判断标成以下三类之一：`论文明确报告`、`我的合理推断`、`论文没有回答`。
- 除 `Q03` 指定的效率数字外，不需要记整张 benchmark 表，也不要求推导公式。
- 只有在不看原文时仍能讲清楚，才勾选完成。

## 建议阅读路径

1. **问题与整机图**：Abstract、§1、Figure 1、Figure 2、§2 开头。
2. **长上下文核心**：§2.3、Figures 3–4，尤其 §2.3.3 的 sliding-window branch 与 §2.3.4。
3. **推理时缓存**：§3.5.1、Figure 6；§3.5.2 只需理解共享前缀缓存的取舍。
4. **能力塑造**：§5.1.1、Tables 2–3、Figure 7、§5.1.2。
5. **证据检查**：§5.3.1、Tables 6–7、§5.3.2；需要时再查 Appendix B。
6. **作者边界**：§6。

可以略读：§2.2 的 mHC 数学细节、§2.4 的 Muon 推导、§3.1–3.4 的集群与 kernel 实现、§5.2 的大部分基础设施、完整 benchmark 数字表。它们不影响本轮通过。

## 必答问题

### 一、论文到底解决什么

- [ ] **Q01 · 核心问题与主张**（Abstract、§1）

  Vanilla attention 在超长上下文中造成什么瓶颈？为什么这个瓶颈会同时限制 1M context、long-horizon Agent 和 test-time scaling？论文声称自己解决了什么，又没有声称解决什么？

- [ ] **Q02 · 架构地图**（Figure 2、§2 开头）

  哪些组件继承自 DeepSeek-V3，哪些是 V4 的新增或升级？分别把 DeepSeekMoE、MTP、CSA/HCA、mHC、Muon 放到 attention、FFN、residual connection、training optimization 中正确归类。

- [ ] **Q03 · 效率数字的完整句子**（Abstract、Figure 1、§2.3.4）

  把 `27% inference FLOPs` 与 `10% KV cache` 写成完整比较：哪个模型、什么上下文长度、相对谁、测的是什么？不要把它与 §2.3.4 相对 BF16 GQA8 的约 `2% KV cache` 混成同一个 baseline。

### 二、CSA / HCA 怎样工作，又怎样不作弊

- [ ] **Q04 · CSA 数据流**（Figure 3、§2.3.1）

  不写公式，按顺序解释一次 CSA：原始 token 如何形成压缩 KV、lightning indexer 如何选候选、query 最终注意哪些 compressed entries，以及 sliding-window branch 补了什么。

- [ ] **Q05 · HCA 与混合设计**（Figure 4、§2.3.2）

  HCA 与 CSA 在压缩率、是否再做 sparse selection、保留细粒度信息的方式上有什么不同？论文为什么把两者交错使用？其中哪些理由由正文直接给出，哪些只是你的推断？

- [ ] **Q06 · Causal 信息边界**（§2.3.3）

  一个 query 能访问哪些 compressed blocks，为什么不能访问自身 block 中尚未发生的 token？这与 U1/U2 的 future-token leakage 有什么本质区别？严格 causal 带来了什么局部信息损失，sliding window 如何补偿？

### 三、1M context 为什么不只是一个 attention 公式

- [ ] **Q07 · KV cache 的两本账**（Figure 6、§3.5.1）

  classical KV cache 与 state cache 分别保存什么？尚未凑满一个 compression block 的 tail tokens 为什么不能直接丢掉？这种异构 cache 为什么不能原样套用普通 PagedAttention 的假设？

- [ ] **Q08 · 从算法到可部署系统**（§2.3.4、§3.5、§5.2.1）

  除 CSA/HCA 外，选出至少三项使 1M context 真正可部署的工程措施，并分别说明它减少的是计算、显存/存储、重复 prefill，还是延迟。明确区分“模型架构贡献”与“服务系统贡献”。

### 四、能力是怎样被 post-training 塑造的

- [ ] **Q09 · 两阶段 post-training**（§5.1.1–§5.1.2）

  先训练 domain specialists、再用 multi-teacher On-Policy Distillation 合并能力的流程是什么？SFT、GRPO、teacher、student trajectory、reverse KL 各自扮演什么角色？为什么这不等于直接平均多个专家的权重？

- [ ] **Q10 · Reasoning effort 与 Agent 状态**（Tables 2–3、Figure 7、§5.1.1）

  Non-think、High、Max 在训练条件、推理格式与计算预算上怎样区分？tool-calling 与普通对话为什么采用不同的 reasoning-history 保留策略？挑选 tool-call schema、interleaved thinking 或 Quick Instruction 中的一项，解释它改变的是模型能力、接口可靠性还是系统效率。

### 五、作者的结果究竟支持到哪里

- [ ] **Q11 · Benchmark 因果审计**（§5.3.1–§5.3.2、Tables 6–7）

  任选一个 headline result，完整列出 checkpoint、reasoning mode、prompt/context budget、Harness/工具、test set、metric 与 baseline。哪些条件在论文中可核查？现有对照能支持“这个配置得分更高”，还是足以支持“某个单独机制导致提升”？缺失什么 matched control 或 ablation？

- [ ] **Q12 · 局限与贾维斯判断**（§6，结合全文）

  写出一个作者主动承认的局限、一个你从证据设计中发现但作者没有充分解决的局限，以及一个对贾维斯 0.x 的具体设计判断。最后给出一个会真正改变该判断的后续证据或实验。

## 可选深挖

- [ ] **O01 · mHC**（§2.2）：为什么普通 Hyper-Connections 可能数值不稳定，doubly stochastic constraint 想解决什么？
- [ ] **O02 · Muon**（§2.4）：它相对 AdamW 改变了什么更新过程，论文给了哪些稳定性证据？
- [ ] **O03 · MoE 规模**（§4.2.1）：total parameters 与 activated parameters 有何区别，为什么不能只用总参数量判断每 token 的推理成本？
- [ ] **O04 · Agent 基础设施**（§5.2.5）：sandbox、trajectory logging 与 preemption-safe resumption 分别解决什么生产问题？

## 回来时的回答格式

直接按下面格式一次性回答即可，不必写成正式论文笔记：

```text
Q01.
Q02.
Q03.
Q04.
Q05.
Q06.
Q07.
Q08.
Q09.
Q10.
Q11.
Q12.
```

## 通过标准

- `Q04–Q06` 能脱离原文讲清 CSA、HCA 与 causal boundary。
- `Q09–Q10` 能区分训练得到的能力、推理时预算与 Agent 运行框架。
- `Q11` 能把作者报告、因果归因和缺失证据分开。
- `Q12` 的贾维斯判断必须落到一个接口、状态或评估决策，不能只写“对未来有帮助”。

通过后再单独进入 DSpark；届时重点检查 draft tokens 为什么不等于真实未来信息，以及 target verification 如何保持最终分布。
