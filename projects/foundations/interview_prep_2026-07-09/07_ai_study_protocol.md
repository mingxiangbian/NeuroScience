# 07 AI 辅助学习协议（7 天冲刺版 v3）

日期：2026-07-10
状态：字节三岗已投（Coze 上下文工程 / Agent Infra 计算 / Agent 评测），面试可能在 3-14 天内到来。

三件套分工：

- **本地面试包**（本文件夹 01-09）＝教案与空白 ledger 模板；真实评测写入 gitignored 的 `09_eval_ledger.local.md`。
- **AI**＝教练、interviewer 或 evaluator；三个角色不能在同一轮盲测里混用。
- **基石网站**＝长期知识库，只沉淀每日冲刺卡和消化后的强知识卡。

## 一、训练合同

- D1 的 210 分钟作为已完成 baseline 保留；D2-D7 每天两个必修 90 分钟块，理解和精力允许时增加第三个 90 分钟块，休息另算。
- 每天至少切换两个主题：一个 Python 基础块 + 一个岗位知识块。第三块在 Context、Agent Runtime、Behavioral 或邀约岗位 overlay 中选择。
- 训练量不靠压缩讲解、worked example 或重构时间解决。只有已经学过的模式才进入 25-45 分钟独立计时；完整 Mock 保留独立评分时间。
- 收到具体邀约后切换岗位 overlay，公共底座（coding、项目证据、system design、behavioral）不取消。
- 每次练习都留下 artifact：原回答/代码/设计图、用时、提示次数、readiness level、failure tag 和复测日期。

## 二、学习循环：基线后先分诊

Baseline 只负责发现缺口。评分为 0 后，先判断是“已有知识但应用错误”，还是“尚未系统学习”；两者不能使用同一补救方式。

### 已有基础：输出优先分支

1. **Attempt**：先在无资料条件下作答或实现。
2. **Targeted review**：只查导致失败的机制或约束，不泛读整章。
3. **Reconstruct**：合上资料，从白纸重新作答或重写代码。
4. **Transfer**：换一个题面、参数或 failure mode 再做一次。
5. **Retest**：失败项进入 D+2 和 D+7；原题通过不等于迁移通过。

### 尚未系统学习：结构化学习分支

1. 标记为 `unlearned`，记录知识层级和前置概念，不要求当天通过 blind hard gate。
2. 按“概念和题意 → 具体数组/trace/case → guided artifact → 小型近迁移变式”建立模型，不用连续追问制造短期模仿；同日变式只检查理解，不代表广泛迁移能力。
3. D+2 可以是学习检查点，只检查概念关系和第一份 guided artifact，不作为 hard gate。
4. 完成必要基础后再做无提示 reconstruct 和 unseen transfer；通常放到 D+7 或更晚。
5. 未见场景独立达到 readiness level 2 后，才把该能力视为可面试。

Coached practice 可以提示和讲解；blind evaluation 禁止提示，且由独立 evaluator 在答题结束后评分。代码必须由本地运行或 judge 验证，AI 不是唯一 correctness oracle。对 `unlearned` 项目，不能把看完一个示范后的复述当作 independent readiness。

当前默认分诊：Python 基础语法和代码阅读属于已有基础；标准库容器、常见数据结构/算法模式、Agent Runtime vocabulary 与 Agent Eval case anatomy 属于 `unlearned`。除非已有独立 artifact 改变结论，Coach 必须先解释概念和题意，再用具体数组、trace 或真实 case 演示，不能用连续追问让用户猜陌生术语。

## 三、内容分层

### D2-D7 核心

1. Python：`list`、`dict`、`set`、stack、queue、`deque`、hash、sliding window 和 BFS；每天一个模式，按讲解、trace、重构、变式完成。
2. Agent Eval：system performance benchmark 与 behavior eval 的区别；case anatomy、tool-call evaluation、bad-case report、自动评测与人工校准；至少一份未见 case 独立达到 readiness level 2。
3. Context Engineering：prompt/context/state/memory 边界，selection、retrieval、compression、scope、conflict、stale memory 和 human review；以 Cyrene 为案例，但区分已实现、定性观察和未验证计划。
4. 项目证据：Cyrene benchmark 的 full/gate profile、deterministic fixture 边界、只看过汇总的事实，以及同步 summarization hook 没有 before/after 数据的证据边界。
5. Behavioral 最小集：先整理 ownership、tradeoff、evidence limitation 三个真实故事；其余故事进入下一阶段。

### 下一阶段或邀约 overlay

1. Agent Infra：operation state machine、reliable tool execution、Tool Router、canonical system design、CS/Node 基础。
2. Coze 深化：attention、KV cache、长上下文代价，以及 `SFT/RLHF/DPO` 的正确边界。
3. 扩展 Coding：tree/graph/heap/DP 与更多 medium transfer。
4. 完整 Behavioral：五个真实故事与每岗三问。

收到某岗位具体邀约时，可以把第三个 90 分钟块升级为该岗位 overlay，但不能挤掉 Python 和当前最低门槛主线。

## 四、盲测协议

### D1 baseline

- 一题未见 medium coding（45 分钟）。
- 一题未见 production Agent system design（30 分钟）。
- 一次 Cyrene deep dive 录音/转写（15 分钟）。
- baseline 前不得打开 02、03、06 的答案内容；保留原始 artifact，后续不能覆盖。

### Mock 隔离

- interviewer 只加载：目标岗位 JD、对应 CV、sealed/unseen question set、时间与流程规则。全局启动规则不得提前加载 ledger 或答案文档。
- interviewer 不加载 02、03、06 的参考答案，也不在过程中评分或提示。
- evaluator 在新会话加载 transcript、artifact、06 的 rubric 和必要证据材料，结束后评分。
- 同一模型也可以承担两个角色，但必须使用不同会话；不能让它凭记忆继续。

### D7 parallel post-test

Coding 从本周已经学习的模式中抽未见变式；岗位块完成未见 Agent Eval case 和 Cyrene Context deep dive。比较 hard gate、用时、hint、failure tag 和证据边界。Agent Infra 若只完成 vocabulary 学习，就继续标为 `unlearned`，不为了形式完整重复 D1 的盲目 system design。

## 五、7 天主题与模块映射

| 天 | 训练时长 | 主题 | 知识沉淀 |
| --- | --- | --- | --- |
| D1 | 210 min | blind baseline + Cyrene 证据与叙事 | Behavioral / Strategy |
| D2 | 180 core / +90 optional | Python 容器 + Eval case anatomy；可选 Cyrene Context pipeline | Coding、Evals & Debugging、RAG & Memory |
| D3 | 180 core / +90 optional | Hash + Context Engineering；可选 Agent Runtime vocabulary | Coding、RAG & Memory、Agent Design |
| D4 | 180 core / +90 optional | Sliding window + Agent behavior eval；可选 Context conflict | Coding、Evals & Debugging、RAG & Memory |
| D5 | 180 core / +90 optional | 已学模式独立检查 + Cyrene case audit；可选 Agent Infra | Coding、Evals & Debugging、Agent Design |
| D6 | 180 core / +90 optional | BFS + Agent Eval mini mock；可选 Coze overlay | Coding、Evals & Debugging、LLM Systems |
| D7 | 180 core / +90 optional | parallel post-test + 下一阶段分流 | Logs + 到期知识卡 |

每日详细时间块以 [05_7_day_schedule.md](05_7_day_schedule.md) 为准。

## 六、可直接粘贴的 Prompt

**Prompt 0｜D1 盲测主持人**

> 你是 baseline proctor。不要加载或引用 02、03、06 的答案，也不要提示。依次给我一题未见过的 medium coding（45 分钟）、一题 production Agent system design（30 分钟），最后让我用 15 分钟介绍并接受 Cyrene 追问。只负责计时、记录原始回答和追问，不评分。题目不得与本文件夹已列样题同题。

**Prompt A｜每日提取与复测**

> 读取 `09_eval_ledger.local.md` 的到期项和今天的主题。先判断到期项是已学习能力还是 `unlearned`：前者出 D+2/D+7 变式，后者只做概念关系或 guided artifact 检查，不能直接盲测。一次处理一个学习块，记录 hint，不能把 coached completion 记为 independent。

**Prompt B｜苏格拉底教练**

> 我在准备字节 {岗位名}。今天学 {概念}。先判断我是否学过前置知识；若属于 `unlearned`，按“解释概念和题意 → 用具体数组/trace/case 完整演示 → 我合资料复述或重写 → 小型独立变式”主持，不要让我猜陌生术语。只有已有基础时才先 attempt。理解机制后，再用苏格拉底追问检查为什么、failure mode、替代方案和验证方法。

**Prompt C1｜Coding 学习教练**

> 今天学习 {数据结构或模式}。先解释用途、核心 Python API 和复杂度，再用一个具体数组逐行运行；随后让我合上资料重新实现，并给一个小型变式。整个块 90 分钟，代码必须由我在本地/judge 执行。记录 hint 和误区，但 coached artifact 不评为 independent。

**Prompt C2｜Coding 独立判题人**

> 模式：{已经学习的模式}。给我一题同级未见变式；我先口述再写代码。你不能给正确代码，只能在我提交 artifact 后指出最小反例。代码由本地/judge 执行；记录总用时、hint、failure tag、测试覆盖和复杂度，再按 06 的 coding hard gate 判定。未学过的数据结构不得用于本次独立检查。

**Prompt D｜盲测 interviewer**

> 你是字节 {Coze 上下文工程/Agent Infra/Agent 评测} interviewer。只读取我提供的目标 JD、对应 CV 和本 prompt，不读取任何面试答案、题库答案、学习笔记、ledger 或历史评分。现场生成未见问题，按 60 分钟结构完成：自我介绍 → 项目深挖 → 岗位知识 → 一道该岗位 system design/case → 可选 coding/component 追问 → 反问。system design/case 不得省略；coding hard gate 可由 Mock 紧邻的独立限时 coding 段提供。全程不提示、不评价、不总结；最后只输出逐字 transcript、每题用时和是否使用提示（应为 0）。

**Prompt E｜独立 evaluator**

> 这是一次已结束的 blind Mock。读取 transcript/artifact、`06_mock_question_bank.md` 的 rubric，以及用于核对事实的 CV/项目证据。不要改写原回答。逐题给 readiness level、分类诊断、failure tag、hard-gate 结果和一条最小修复建议；记录到 `09_eval_ledger.local.md`。事实或代码错误必须为 0，使用实质提示最高为 1。

## 七、网站使用要点

1. 网站是输出端，不是答题时的资料库。blind evaluation 期间关闭网站。
2. 每天只强制写一张冲刺卡和一张最重要弱项知识卡；没有形成稳定理解就不发布。
3. 知识卡仍用「核心理解 / 常见误区 / 面试转译」，但必须来自用户合资料后的重构答案。
4. 原始错答、评分、hint 和复测日期留在 gitignored 的 `09_eval_ledger.local.md`；网站只放可长期复习的知识。
5. GitHub Pages 是公开的，不写私人评价、虚构数字或不愿公开的面试信息。
