# SelfMem Deep Reading Package Design

Date: 2026-07-13
Status: Approved design

## Summary

将 `SelfMem: Self-Optimizing Memory for AI Agents` 加入 `papers/brain-memory-for-ai-agents`，并按现有 `Paper Import Standard` 制作完整的 `verbatim` deep reading package。阅读包必须覆盖正文论证、BEAM 实验、策略优化、限制，以及附录里的优化流程、关键 prompts 和 memory action space；不能把论文压缩成只有摘要和结果数字的展示样本。

论文采用 CC BY 4.0。仓库保存原始 PDF、带署名和来源的真实图表语义裁剪，以及用于阅读的论文原文片段、忠实中文翻译和项目解释。

## Goals

- 在项目论文目录中登记 SelfMem，并提供可直接打开的完整阅读入口。
- 用连续的阅读主线解释“固定记忆机制”到“可优化记忆策略”的问题转变。
- 区分模型参数优化、自然语言策略优化、单次 memory workspace 构建和回答时检索。
- 覆盖方法公式、memory tools、反馈信号、实验设置、主要结果、策略优化和作者限制。
- 使用论文真实图表的最小必要裁剪，不使用整页截图或简陋重绘替代关键证据。
- 保持现有纯静态 reader、平行笔记、本地 annotation 和搜索架构不变。

## Non-Goals

- 不为 SelfMem 新建专用 reader 或修改三栏布局。
- 不实现论文中的 SelfMem runtime、SQLite transcript store、memory tools 或优化器。
- 不新增 SurrealDB、在线 embedding、RAG 回答或 API。
- 不公开预填个人笔记；新包的 `notes.json` 默认全部为空。
- 不逐段搬运参考文献，也不把低阅读价值的附录运行日志做成 chunk。

## Package Identity

- Paper id: `yang-2026-selfmem`
- Short title: `SelfMem`
- Reading directory: `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/`
- Local PDF: `papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf`
- Source: `https://arxiv.org/abs/2607.03726`
- Source mode: `verbatim`
- License: `CC BY 4.0`

`papers/manifest.json` 只有在五个必需 JSON 文件、PDF 和至少一张真实来源图全部存在并通过验证后，才为该条目设置 `hasReading: true`。

## Reading Architecture

`paper.json` 使用 7 个 reading groups：

1. `group-problem`：长上下文仍需要记忆，以及固定策略为何不够。
2. `group-positioning`：SelfMem 与 RAG、MemGPT、A-Mem、Mem0 和 self-improving agents 的关系。
3. `group-framework`：问题定义、不可变 transcript、memory workspace、action space 和反馈。
4. `group-loop`：inspect-write-review-revise 闭环与 memory-conditioned answering。
5. `group-evaluation`：BEAM 设置、baseline 公平性、指标、主要结果和问题类型表现。
6. `group-optimization`：策略迭代、训练/留出划分、最优策略为何不等于最多迭代。
7. `group-implementation-limits`：最终紧凑策略、prompt/tool 规范、作者限制和项目迁移边界。

`narrativeSpine` 与以上 group 一一绑定。`premises` 控制在 5 条以内，至少包括：

- SelfMem 优化的是可读的记忆管理策略，不是模型权重。
- raw transcript 是事实来源，memory workspace 是压缩后的工作指南。
- agent 可选择记忆结构，但 action space、反馈渠道和安全约束仍由框架定义。
- memory feedback 不是单一奖励值，而是质量、成本、检索和审计信号的组合。
- BEAM 上的优势不能自动推出跨 benchmark、模型和生产环境的通用优势。

`misreadings` 至少覆盖：把 self-optimizing 误读成参数训练；把 workspace 误读成事实权威；把同一 harness 下的结果误读成所有生产实现的结论；把单一 benchmark 和 100K 策略优化实验误读成已经验证所有规模的泛化。

## Chunk Coverage

目标为 20 到 24 个 chunk。chunk 按完整论点单元划分，不按页数或固定字数切分。覆盖顺序如下：

- 研究动机与核心假设。
- 固定 memory pipeline 的限制与相关方法定位。
- 形式化问题定义：`H`、`M*`、`Retrieve`、`LLM`。
- transcript store 与只读检查接口。
- memory workspace 与 action space。
- feedback signals 及其非标量化取舍。
- memory construction、review 和 update 公式。
- memory-conditioned answering 与 source-of-truth 关系。
- BEAM 数据规模、问题类型和顺序提问协议。
- baseline、模型配置、judge 与成本口径。
- 100K、500K、1M 主结果及与最强 baseline 的差值。
- 成本、缓存、LLM request 和 embedding request 的解释。
- question-type robustness。
- 策略优化的训练/held-out 规则。
- refinement iteration 与 training-set-size 结果。
- 最终 compact-memory policy。
- memory construction prompt、fixed-evidence answering prompt。
- local repair、global refinement 和 leakage guardrail。
- internal tool action space。
- 局限、可复现性信息和对当前项目的迁移结论。

每个 chunk 必须包含 `sourceText`、`zhTranslation`、`zhExplanation`、`groupId`、一句 `premise`、一句 `claim` 和最多三条 `evidence`。`sourceText` 必须来自 PDF 原文；附录 prompt 可以保留为 `code` block，但不把大段 prompt 重复塞进普通 paragraph。

## Structured Blocks

- 论文公式使用 `math` block，LaTeX 不带 `$` 分隔符。
- Table 1 的核心结果用真实裁图承载，同时用 reader-side `table` block保留关键数值，便于移动端阅读和搜索。
- prompt templates 使用 `code` block，保留关键约束，省略运行时占位数据。
- Table 8 的工具类型、工具名和用途使用 `table` block。
- Table 2 的方法比较以真实裁图为证据；中文解释只总结作者比较维度，不替作者补造实验结论。

## Figure Set

第一版至少保存 5 张真实来源语义裁剪图：

- Figure 2：SelfMem 总体架构与 memory trajectory。
- Table 1：100K、500K、1M 主实验结果。
- Figure 3：BEAM question-type analysis。
- Figure 4：策略优化迭代与训练集规模。
- Table 2：SelfMem 与代表性 memory methods 的定位。

如版面允许，可增加 Figure 1 作为概念引图，但它不能替代 Figure 2 的方法证据。每张图必须记录 `sourcePage`、`sourceFigure`、`cropMode`、裁剪范围说明和 CC BY 4.0 来源。裁剪只保留 figure/table、必要图例和 caption；不得直接保存整页 PDF。

## Search And Notes

`embeddings.json` 为每个 chunk 建立一个静态本地向量项，`indexedFields` 覆盖 `sourceText`、`zhTranslation`、`zhExplanation`、`premise`、`claim` 和 `evidence`。沿用现有包的确定性离线索引格式，不引入模型 key 或后端。

`notes.json` 为每个 chunk 提供空字符串，保持右侧平行笔记连续；用户之后的本地笔记和高亮继续由现有 reader 管理。

## Quality And Evidence Boundaries

- 文献结论：SelfMem 在作者统一 BEAM harness 和报告配置下优于所列 baselines。
- 初步证据：自然语言策略 refinement 可以提高 held-out 表现，但该实验目前集中在 100K 设置。
- 不能推出：SelfMem 在所有模型、benchmark、真实部署或高度特化 baseline 上都占优。
- 不能推出：agent 已自主发明了完全不受人类先验约束的记忆机制；框架仍预先给出原则、工具、反馈和审计约束。
- 项目关联：这篇提供“让 agent 优化 memory policy”的工程方向，但不等同于生物记忆中的突触可塑性、巩固或遗忘机制。

## Files Changed During Implementation

- `papers/manifest.json`
- `papers/brain-memory-for-ai-agents/pdfs/2026-yang-selfmem.pdf`
- `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/paper.json`
- `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/chunks.json`
- `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures.json`
- `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/figures/*`
- `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/notes.json`
- `papers/brain-memory-for-ai-agents/readings/yang-2026-selfmem/embeddings.json`
- Focused requirement tests only if the current tests do not already assert generic manifest/package discovery.

No shared reader code or import-standard change is expected unless implementation exposes a concrete contract gap.

## Verification

Run:

```text
node scripts/validate-reading-packages.mjs brain-memory-for-ai-agents
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

Then serve the site locally and verify:

- `SelfMem` appears in the paper directory and opens through the existing query-string route.
- All chunks render in order with Chinese translation and explanation.
- Math, code, table and figure blocks render without broken assets or horizontal overflow.
- Figure crops are readable on desktop and mobile and do not contain full PDF pages.
- Search can find terms from the main method, results and appendix implementation sections.
- The note rail remains blank but continuous for chunks without notes.
