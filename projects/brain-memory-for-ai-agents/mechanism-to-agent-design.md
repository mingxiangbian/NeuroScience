# Mechanism to Agent Design Map

---
date: 2026-06-18
status: draft
tags: [memory, ai-agent, mechanism-map]
sources:
  - ../../sources/brain-memory-and-agent-memory-sources.md
---

## Purpose

这个文件是项目主轴。它不证明 AI Agent 像大脑，而是把大脑 memory 机制拆成可能有工程价值的计算原则，并标明证据强度、迁移层级和风险。

## Mapping Table

| Brain mechanism | Computational principle | Agent memory design implication | Evidence strength | Claim type | Transfer risk |
| --- | --- | --- | --- | --- | --- |
| Encoding specificity | 检索依赖当前线索与编码线索的重叠 | retrieval 不应只靠关键词，应利用 task state, user state, project context, temporal context | consensus / strong in neuroscience | literature claim -> assistant synthesis | 中：Agent context 不是生理状态 |
| Hippocampal indexing | 用紧凑 index 重新激活分布式表示 | 建立 memory index，指向 raw event、summary、source、project state，而不是只存单条文本 | preliminary for transfer | assistant synthesis | 中：生物 index 和数据库 index 不同 |
| Pattern completion | 不完整线索可补全相关记忆模式 | retrieval 应返回候选 memory cluster，而不是孤立片段 | preliminary | assistant synthesis | 高：补全可能导致 false memory |
| Pattern separation | 相似经历需要保持可区分 | 对相似用户偏好、项目、人物和任务做 disambiguation | preliminary | assistant synthesis | 中：需要 eval 区分相似 memory |
| Engram lifecycle | memory trace 会经历 encoding, consolidation, retrieval, forgetting | Agent memory 需要 lifecycle，不应只 append log | strong for neuroscience, speculative for AI | assistant synthesis | 中 |
| Systems consolidation | 短期、细节丰富记忆可逐渐转成更稳定、抽象的知识 | 从 raw episode 生成 stable preference / semantic note，但保留来源链接 | preliminary for transfer | assistant synthesis | 中：摘要可能丢失关键细节 |
| Reconsolidation | retrieved memory 可能进入可修改状态 | 当旧 memory 被调用并被用户纠正时，应进入 update flow | preliminary for transfer | assistant synthesis | 中：不能把生物可塑性等同于覆盖写入 |
| Forgetting / accessibility | 遗忘可能是存储缺失，也可能是访问失败或主动调节 | 区分 delete, archive, decay, access gating, conflict marking | preliminary | assistant synthesis | 低到中：工程上可直接设计 |
| Emotional salience | 情绪或价值会影响记忆优先级 | Agent 可用 importance / user-confirmed salience 调节 consolidation，但不能把情绪类比滥用 | preliminary | assistant synthesis | 高：AI 没有生物情绪 |
| Offline replay / sleep consolidation | 离线重放可能促进巩固和重组 | Agent 可在 session 后做 memory review, summarization, deduplication | preliminary for transfer | assistant synthesis | 中：离线处理可能引入错误摘要 |
| Prefrontal control | top-down goals influence retrieval and selection | retrieval 应受当前目标、权限和用户意图约束 | preliminary | assistant synthesis | 中 |
| Schema / semanticization | 具体经历可抽象成一般知识或预测结构 | 区分 episode memory 和 semantic / preference memory | consensus at cognitive level, details disputed | assistant synthesis | 中：抽象会污染原始记忆 |

## Design Constraints

### C1. Memory write 需要类型

每次写入前至少区分：

- `episode`: 具体事件、时间、上下文。
- `preference`: 用户偏好。
- `project_state`: 项目状态。
- `semantic_note`: 从多次经历抽象出的稳定知识。
- `procedure`: 用户偏好的工作流。
- `sensitive`: 需要权限、遮蔽或避免写入的信息。

### C2. Retrieval 需要候选和证据

Agent 不应只说“我记得你喜欢 X”。更好的行为是：

- 找到候选 memory。
- 说明置信度。
- 在必要时引用来源或时间。
- 允许用户纠正。

### C3. Consolidation 不能无来源

从 episode 到 preference / semantic note 的转换必须保留来源链：

```text
raw event -> session summary -> consolidated memory -> current answer
```

否则系统无法解释为什么记住了某个偏好，也无法撤回。

### C4. Update 优先于覆盖

当用户纠正旧 memory 时，默认不要静默覆盖。应记录：

- old memory
- new correction
- conflict reason
- update date
- current status

### C5. Forgetting 是功能，不只是清理

Agent memory 至少需要四种 forgetting：

- decay: 随时间降低权重。
- archive: 保留但默认不检索。
- delete: 用户明确删除。
- suppress: 敏感或错误 memory 禁止进入回答。

## Failure Modes

| Failure mode | Description | Possible mitigation |
| --- | --- | --- |
| False personalization | 把一次临时表达当成长期偏好 | write confidence, user confirmation |
| False memory | 模式补全生成未发生过的经历 | source-linked memory, audit trail |
| Over-retrieval | 不相关旧 memory 干扰当前任务 | goal-gated retrieval |
| Memory ossification | 旧偏好阻止系统适应变化 | decay, update, recency-sensitive confidence |
| Privacy leakage | 不该出现的 memory 出现在回答中 | sensitive type, permission gating |
| Summary drift | consolidation 摘要逐步偏离原始事实 | source preservation, periodic review |

## Next Work

- 给每条 mapping 补充至少一个具体文献来源。
- 为 personal assistant 场景定义 memory schema。
- 把 failure modes 转成 eval checklist。
