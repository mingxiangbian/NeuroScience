# 07 AI 辅助学习协议（7 天冲刺版 v2）

日期：2026-07-10
状态：字节三岗已投（Coze 上下文工程 / Agent Infra 计算 / Agent 评测），面试可能在 3-14 天内到来。

三件套分工：

- **本地面试包**（本文件夹 01-09）＝教案与空白 ledger 模板；真实评测写入 gitignored 的 `09_eval_ledger.local.md`。
- **AI**＝教练、interviewer 或 evaluator；三个角色不能在同一轮盲测里混用。
- **基石网站**＝长期知识库，只沉淀每日冲刺卡和消化后的强知识卡。

## 一、训练合同

- 标准日 180 分钟；D1/D3/D6 重日 210 分钟；休息另算。
- 训练量不靠压缩单题时间解决。每道 coding 仍保留 25 分钟，完整 Mock 保留独立评分时间。
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

1. 标记为 `unlearned`，记录知识层级和前置概念，不要求当天迁移作答。
2. 按“知识地图 → 机制讲解 → worked example → guided artifact”建立模型，不用连续追问制造短期模仿。
3. D+2 可以是学习检查点，只检查概念关系和第一份 guided artifact，不作为 hard gate。
4. 完成必要基础后再做无提示 reconstruct 和 unseen transfer；通常放到 D+7 或更晚。
5. 未见场景独立达到 readiness level 2 后，才把该能力视为可面试。

Coached practice 可以提示和讲解；blind evaluation 禁止提示，且由独立 evaluator 在答题结束后评分。代码必须由本地运行或 judge 验证，AI 不是唯一 correctness oracle。对 `unlearned` 项目，不能把看完一个示范后的复述当作 independent readiness。

## 三、必须补齐的内容

1. 计算机基础：进程/线程/协程、内存与死锁、TCP/UDP、HTTP/HTTPS、URL 到渲染、哈希冲突。
2. Node.js：event loop、microtask/macrotask、async/await、Promise、单线程 I/O concurrency。
3. Transformer/post-training：attention、KV cache、inference constraints，以及两条不同路径：
   - `pretrain → SFT → preference data → explicit RM → PPO-style RLHF`
   - `pretrain → SFT → preference pairs + fixed reference policy → DPO`（经典 DPO 不需要单独训练显式 RM 或 PPO-style online rollouts）
4. Coding：每题 25 分钟，实际运行，记录 hint 和失败类型。
5. Component implementation：Tool Router 或 async executor，覆盖 validation、timeout、cancel、idempotent retry、trace 和 tests。
6. Canonical system design：multi-tenant Agent memory/runtime，覆盖 permissions、HITL、安全、恢复、observability、eval、latency/cost/privacy。
7. Agent eval：两份未见 trace case；从失败层定位到 regression metric。
8. Behavioral：五个真实故事，覆盖 ownership、ambiguity、failure、collaboration、changed mind；不能全部用 Cyrene。
9. 升学答案：如实说明 2027 fall 计划和可实习时长，不把读研包装成不存在的承诺。
10. 真实面试反馈：原题、原答、评分和 D+2/D+7 进入 09 ledger。

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

保持 D1 的能力结构和难度，换题复测。比较 hard gate、用时、hint、failure tag，不只比较总分。

## 五、7 天主题与模块映射

| 天 | 训练时长 | 主题 | 知识沉淀 |
| --- | --- | --- | --- |
| D1 | 210 min | blind baseline + Cyrene 证据与叙事 | Behavioral / Strategy |
| D2 | 180 min | Coze context + Transformer/post-training | LLM Systems、RAG & Memory |
| D3 | 210 min | Infra + canonical system design + Tool Router + CS/Node | Agent Design、Coding |
| D4 | 180 min | Eval + 两个 unseen trace case | Evals & Debugging |
| D5 | 180 min | Coze blind Mock | 最弱能力模块 |
| D6 | 210 min | Infra/Eval blind Mock + 五个行为故事 | 最弱能力模块、Behavioral |
| D7 | 180 min | parallel post-test + 收官 | Logs + 到期知识卡 |

每日详细时间块以 [05_7_day_schedule.md](05_7_day_schedule.md) 为准。

## 六、可直接粘贴的 Prompt

**Prompt 0｜D1 盲测主持人**

> 你是 baseline proctor。不要加载或引用 02、03、06 的答案，也不要提示。依次给我一题未见过的 medium coding（45 分钟）、一题 production Agent system design（30 分钟），最后让我用 15 分钟介绍并接受 Cyrene 追问。只负责计时、记录原始回答和追问，不评分。题目不得与本文件夹已列样题同题。

**Prompt A｜每日提取与复测**

> 读取 `09_eval_ledger.local.md` 的到期项和今天的主题。先出 D+2/D+7 变式，再出今日预习题；一次一题。教学阶段可以在我作答后给答案骨架，但必须记录 hint，不能把 coached completion 记为 independent。

**Prompt B｜苏格拉底教练**

> 我在准备字节 {岗位名}。今天学 {概念}。按“先尝试 → 精准补缺 → 合资料重构 → 换场景迁移”主持。每次从为什么这样设计、什么情况下失败、替代方案和验证方法追问；卡住时只给骨架，让我自己重答。

**Prompt C｜Coding 判题人**

> 题目：{题目}。我先口述再写代码。你不能给正确代码，只能指出致命误解或给最小反例；代码必须由我在本地/judge 执行。记录总用时、hint 次数、失败 tag、测试覆盖和复杂度。25 分钟后按 06 的 coding hard gate 判定。

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
