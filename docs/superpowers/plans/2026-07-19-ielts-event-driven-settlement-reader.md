# IELTS 事件触发式结算学习系统与 Reader 重构计划

Date: 2026-07-19

Status: Ready for implementation; visual direction requires an A/B mock selection gate

## 目标

把现有的“8 周日历 + 每日训练 + 固定检查点”系统改造成适合 Phoenix 的“事件触发 + 单线程学习单元 + 证据结算”系统，并在同一套信息架构上制作两版视觉 mock，选定后再改生产页面。

完成后，页面要能在重新打开后的 5 秒内回答四个问题：

1. 当前唯一的活动单元是什么。
2. 下一步第一个动作是什么。
3. 哪个错误或证据让这个单元排在最前面。
4. 已经结算了什么，下一次校准由什么事件触发。

## 已确认决策

- 运营目标改为 IELTS Overall 7.5。
- 不再做逐校语言与 GRE 要求核查。
- 删除 8 周主结构、每日打卡、固定周检查点、周学习时长下限和虚构完成百分比。
- 保留诊断驱动、错误日志、回归检查、LLM 评分校准和多智能体提示词系统。
- 网页是展示柜与档案馆，不是操作台；结算入口仍是与助手的对话。
- 同时只有一个活动单元。队列不是债，空窗不产生逾期状态。
- 考试计时仍保留：限时是考试能力的一部分，但只用于诊断、模考和明确要求限时的训练样本。
- A/B mock 使用同一份内容与同一套交互，只比较视觉语言。

## 需要保留的边界

- `diagnostics/*.json`、`plans/*.json` 和 Markdown 文件继续是 repo source of truth。
- `site/ielts-data.json` 继续由构建脚本生成，浏览器不写回 repo。
- 右侧详情面板继续默认空置，只在用户点击引用或选择内容后显示上下文。
- Notes、Journal、Prompt Library、Validation 的全文仍可搜索和查看，但不再与主学习循环争夺一级视觉权重。
- LLM band 评分继续标为 advisory，并保留证据置信度与未验证维度。
- Overall 7.5 已确认；单项最低线仍是独立字段，未得到明确要求前不得默认为“每项 7.5”。缺失时页面显示“单项线待确认”。

## 不做

- 不增加后端、账户、云同步或 GitHub 自动写回。
- 不让网页按钮完成结算或修改正式成绩、错误、单元状态。
- 不把语言学习并入 Foundations 的同一份 ledger；两者共享原则，不共享账本。
- 不同时维护“事件制”和“8 周制”两套可运行计划。
- 不在 A/B 选择前把任何视觉方向写进生产 CSS。
- 本轮完成后不继续做无数据驱动的页面微调；首个真实诊断单元必须成为下一步。

## 新学习循环

```text
真实输出
  -> 评分与错误信号
  -> 选择一个最高价值错误
  -> 开启一个学习单元
  -> 修订与新样本验证
  -> 结算产物和判据
  -> 更新错误状态、成绩证据和下一单元
  -> 触发条件满足时校准
```

### 单元类型

| 类型 | 用途 | 最小产物 | 结算判据 |
| --- | --- | --- | --- |
| 诊断单元 | 获取一个此前缺失的真实能力证据 | 限时样本、录音或完整题组 + 评分记录 | 样本可定位；评分维度与置信度已记录；至少产生一个可行动判断 |
| 修复单元 | 修正一个高影响错误模式 | 原样本、修订版和差异说明 | 能指出错误机制；修订版消除该错误；留下下一次新样本验证条件 |
| 模考单元 | 验证整体考试执行能力 | 完整限时结果 + 复盘 | 时间、分项表现、失分原因和考试决策均有证据 |
| 校准单元 | 新证据改变目标、排序或考试决策 | 简短决策记录 | 说明什么证据改变了什么决定，并更新活动单元或目标 |

### 错误生命周期

```text
active -> improving -> fixed
   ^          |          |
   +----------+----------+
          recurrence -> regressed
```

- `active -> improving`：完成一次有证据的修订并解释错误机制。
- `improving -> fixed`：连续 3 个独立新样本未再出现同类错误。
- 任意复发：转为 `regressed`，清零连续无错计数，并进入下一轮优先级评估。
- “修好一篇旧答案”不能直接标记 `fixed`。

### 事件触发校准

固定 Week 2/4/6/8 检查点改为以下事件：

1. `baseline-complete`：四项中可提供的诊断证据已录入，首次决定技能优先级。
2. `error-set-changed`：高影响错误集合发生实质变化，重新选择活动单元。
3. `two-mocks-available`：已有两次可比模考，判断 7.5 是否稳定、是否需要调整考试日期。
4. `regression-detected`：已改善或已修复错误复发，重排优先级。
5. `external-deadline-changed`：报名、出分或申请硬期限改变，更新考试执行策略。
6. `target-reached`：证据显示 Overall 7.5 已稳定达到，进入保分与考试执行决策。

## 新数据模型

### `diagnostics/score-profile.json`

- 升级 schema version。
- `target.overall` 改为 `7.5`。
- 移除运行语义中的 `timelineWeeks`。
- `target.perSkillFloor` 允许为 `null`，直到明确要求出现。
- 保留 `currentEstimate`、skills、confidence、risk 和 unverified dimensions。

### `diagnostics/score-history.json`

- 从按 `week` 记录改为按证据事件记录。
- 每条记录包含 `id`、`date`、`eventType`、`sourceType`、skills、overall、confidence 和 evidence refs。
- 不写模板占位成绩；没有真实数据时数组为空。

### `diagnostics/error-log.json`

- 保留现有 id、skill、impact、status、description、evidence 和 review method。
- 增加 `openedAt`、`lastSeenAt`、`repairUnitId`、`consecutiveCleanSamples`、`fixedEvidence`。
- 构建校验负责检查状态与证据是否一致，例如 `fixed` 必须有 3 个独立 clean sample refs。

### 新增 `plans/unit-ledger.json`

作为语言项目唯一活动状态账本：

```json
{
  "schemaVersion": 2,
  "mode": "event-driven-settlement",
  "activeUnit": {
    "id": "D1",
    "type": "diagnostic",
    "title": "写作 Task 2 首次诊断",
    "status": "ready",
    "nextAction": "完成一篇限时 Task 2，并保留原文",
    "evidenceRefs": [],
    "settlementCriteria": []
  },
  "queue": [],
  "settled": []
}
```

首个默认单元选写作 Task 2，是因为它能以最低工具成本产生高密度反馈，不代表预判写作一定是最弱项。真实诊断出现后，队列必须按证据重排。

### 新增 `plans/calibration-events.json`

- 保存触发条件、当前状态、触发证据、决定和决定日期。
- 不含 week number 或固定日期义务。
- 外部考试日期可以记录，但只用于考试执行，不制造内部每日任务。

### 旧计划文件

- `plans/8-week-diagnostic-driven-plan.md`
- `plans/daily-flexible-training.md`
- `plans/checkpoint-rules.md`
- `plans/checkpoint-status.json`
- `plans/weekly-review-template.md`

这些文件不删除历史内容，移动到 `plans/archive/legacy-8-week/`，并在归档 README 中说明它们已退出构建与运行链路。`mock-test-strategy.md` 保留，但改成事件触发版本。

## 新信息架构

保留七个一级分类，但按学习回路组织，不再按文件夹组织：

| 分类 | 主要回答的问题 | 数据来源 |
| --- | --- | --- |
| 现在 | 我此刻只做什么，为什么，第一步是什么 | active unit、target、最高风险证据 |
| 单元 | 当前、排队和已结算单元是什么 | unit ledger |
| 错误 | 哪些错误在燃烧、改善、修复或复发 | error log、derived error counts |
| 证据 | 当前分数判断基于什么，哪些维度仍未验证 | score profile、score events、diagnostic refs |
| 结算 | 哪些产物已通过判据，哪些校准改变了决策 | settled units、calibration events |
| 档案 | 学习笔记、复盘和可复用产物在哪里 | notes、journal、references |
| 系统 | 多智能体提示词、校准方法和数据质量状态 | prompts、validation、build issues |

### 首页“现在”模块

首页不得使用等权指标卡网格。按以下层级排列：

1. 活动单元标题与状态。
2. 下一步第一个动作。
3. 结算判据和证据缺口。
4. 该单元对应的错误或诊断理由。
5. 精简的目标、最新可信成绩和下一个事件触发器。

没有真实数据时显示诚实空状态，不显示 `0.0`、百分比或伪趋势。

## A/B 视觉 mock

两版 mock 必须使用相同的真实内容 fixture、相同模块顺序和相同交互状态。只改变视觉叙事，不能通过删内容让某一版看起来更干净。

### A：外部总线 / 接口认证

- 叙事：语言是认知系统连接外部世界的总线，IELTS 是接口协议认证。
- 视觉语汇：深墨结构、黛蓝有效信号、朱砂误码、金色认证落印。
- 签名组件：一条有语义的“信号路径”连接活动单元、错误、证据和结算；不使用装饰性网格背景。
- 错误日志称为“误码表”，诊断称为“回环测试”，但标准 IELTS 名称必须同时保留，避免隐喻妨碍理解。
- 风险：容易过度主题化。mock 必须证明它仍是可靠工具，而不是概念海报。

### B：考卷 / 红笔批注

- 叙事：页面像一份持续修订、逐步盖章的考试档案。
- 视觉语汇：宣纸、深墨正文、朱砂批注、蓝黑评分注记。
- 签名组件：正文区 + 窄批注边栏；错误是批注，结算是克制的印章。
- 不使用重复卡片堆叠；内容主要靠分栏、细线、留白和字号层级组织。
- 风险：容易退化成普通文档站。mock 必须保留活动状态、引用详情和数据扫描能力。

### Mock 交付与选择门

- 在临时目录生成两版可运行 HTML，不写入生产 reader。
- 每版提供桌面 `1440x1000` 和移动 `390x844` 截图。
- 两版都展示三个状态：无诊断、一个活动修复单元、已有结算记录。
- 选择标准：5 秒重入、信息密度、与 Foundations 的品牌连续性、错误状态辨识、移动端可读性。
- 用户明确回复 `A`、`B` 或修改意见后，才进入生产视觉实现。

## 实施任务

### Task 1：建立迁移保护与红测试

**修改：**

- `tests/ielts-academic-language-project-requirements.mjs`
- `tests/ielts-academic-site-data-requirements.mjs`
- `tests/ielts-build-data-requirements.mjs`
- `tests/ielts-reader-data-consumption-requirements.mjs`

**步骤：**

- [ ] 添加 Overall 7.5、事件记录、unit ledger、calibration events 的结构契约。
- [ ] 添加旧 week/daily/progress 运行语义必须消失的断言。
- [ ] 添加 fixed error 必须有回归证据的 schema fixture。
- [ ] 先运行新测试并确认它们因旧实现而失败。

**通过信号：** 失败原因准确指向尚未实现的新数据结构，而不是无关环境问题。

### Task 2：迁移源文件与 Prompt 合约

**新增：**

- `projects/language/ielts-academic/plans/event-driven-study-system.md`
- `projects/language/ielts-academic/plans/unit-ledger.json`
- `projects/language/ielts-academic/plans/calibration-events.json`
- `projects/language/ielts-academic/plans/archive/legacy-8-week/README.md`

**修改：**

- `projects/language/ielts-academic/README.md`
- `projects/language/ielts-academic/diagnostics/score-profile.json`
- `projects/language/ielts-academic/diagnostics/score-history.json`
- `projects/language/ielts-academic/diagnostics/error-log.json`
- `projects/language/ielts-academic/prompts/orchestrator.md`
- `projects/language/ielts-academic/prompts/output-contract.md`
- `projects/language/ielts-academic/prompts/interaction-protocol.md`
- `projects/language/ielts-academic/prompts/agents/study-load-execution-planner.md`
- `projects/language/ielts-academic/plans/mock-test-strategy.md`

**步骤：**

- [ ] 写入事件触发学习协议和四类单元判据。
- [ ] 建立 D1 写作 Task 2 首次诊断单元，队列保持最小，不预填整条路线。
- [ ] 把 Prompt 输出从 weekly/daily allocation 改为 active unit、next action、artifact、settlement criteria、error update 和 trigger update。
- [ ] 仅对诊断与模考强制 duration；普通修复任务不强制时长。
- [ ] 将旧 8 周文件移入归档并修复引用。

**通过信号：** Prompt 系统不再能生成固定周计划；缺少证据时只生成诊断单元，不编造技能弱点。

### Task 3：升级构建与校验层

**修改：**

- `projects/language/ielts-academic/scripts/build-ielts-data.mjs`
- `projects/language/ielts-academic/scripts/build-schema.mjs`
- `projects/language/ielts-academic/scripts/build-references.mjs`
- `projects/language/ielts-academic/site/ielts-data.json`

**步骤：**

- [ ] 读取 unit ledger 和 calibration events，停止读取运行态 checkpoint JSON。
- [ ] 校验活动单元唯一性、settlement criteria、evidence refs 和错误状态证据。
- [ ] 生成 `derived.errorCounts`、`derived.settledUnitCount`、`derived.currentTrigger`，不生成完成百分比。
- [ ] 为 unit、settlement 和 calibration decision 建立内部引用与 backlinks。
- [ ] 保证构建输出 deterministic。

**通过信号：** 坏的单元或错误状态会阻断 build；没有真实诊断时输出空证据数组而不是模板分数。

### Task 4：先实现无皮肤的信息架构

**修改：**

- `projects/language/ielts-academic/site/ielts-reader.js`
- `projects/language/ielts-academic/site/reader-renderers.js`
- `projects/language/ielts-academic/site/reader-modules.js`
- `projects/language/ielts-academic/site/reader-references.js`
- `projects/language/ielts-academic/site/reader-state.js`
- `projects/language/ielts-academic/index.html`

**步骤：**

- [ ] 把一级模块改为“现在 / 单元 / 错误 / 证据 / 结算 / 档案 / 系统”。
- [ ] 删除 8 周泳道、每日任务清单、导航百分比和 overall progress。
- [ ] 删除 task checkbox 的生产入口；保留 annotation 作为档案阅读辅助。
- [ ] 将 Notes + Journal 合并为档案视图，将 Prompt + Validation 合并为次级系统视图。
- [ ] 让右侧详情面板支持 unit、settlement、calibration 和 error 引用。
- [ ] 以语义顺序和无样式 DOM 检查先验证信息结构。

**通过信号：** 关闭 CSS 后，页面仍能按学习循环读懂；首屏只有一个明确下一动作。

### Task 5：制作并评审 A/B mock

**临时产物：**

- `/tmp/ielts-event-reader-mock/a-interface-certification.html`
- `/tmp/ielts-event-reader-mock/b-exam-annotation.html`
- 对应桌面与移动截图

**步骤：**

- [ ] 从 Task 4 的同一 DOM/fixture 派生两套视觉样式。
- [ ] 检查无诊断、活动单元、已有结算三种状态。
- [ ] 检查 1440x1000 与 390x844，无重叠、截断和横向溢出。
- [ ] 把四张核心截图交给用户，暂停等待 `A` / `B` / 修改意见。

**通过信号：** 用户明确选择视觉方向。没有选择不得开始 Task 6。

### Task 6：实现被选中的生产视觉

**修改：**

- `projects/language/ielts-academic/site/ielts-reader.css`
- 必要时小范围修改 reader markup；不得重新改变已批准的信息架构

**步骤：**

- [ ] 复用全站 rice-paper、deep-ink、dai-blue、cinnabar 和 gold tokens。
- [ ] 用排版、分隔线和状态层级替代重复卡片网格。
- [ ] 活动单元、错误、证据和结算各有稳定但克制的视觉状态。
- [ ] 所有交互具备 hover、focus、active、disabled/loading（适用时）状态。
- [ ] 动效只表达展开、选中和状态变化，并支持 reduced motion。

**通过信号：** 视觉与选择的 mock 一致，同时在真实数据长度下保持密度与可读性。

### Task 7：回归、视觉 QA 与发布门

**步骤：**

- [ ] 运行 `npm run build:ielts`。
- [ ] 运行 `npm run test:ielts`。
- [ ] 运行 `npm run test:all`，确认没有破坏其他静态 reader。
- [ ] 运行 `git diff --check`。
- [ ] 用桌面和移动截图验证无横向 overflow、无空白主区、无面板镜像、无假进度。
- [ ] 验证搜索、模块导航、右侧引用、深色模式和 annotation。
- [ ] 仅暂存 IELTS、相关测试和本计划明确列出的文件，隔离当前工作区其他改动。
- [ ] 用户确认最终页面后再 commit、merge、push，并等待 Pages 成功后核对线上版本。

## 验收标准

- 页面与 README 的运营目标为 Overall 7.5。
- 页面不再出现 8-week、Week 2/4/6/8、daily task、weekly hour floor 或虚构百分比。
- 任意时刻只有一个活动单元，并显示一个明确 next action。
- 没有诊断时不显示 `0.0` 或伪趋势。
- 错误数与状态来自 error log；`fixed` 有连续 3 个新样本证据。
- 校准由证据事件触发，而不是日历触发。
- 首页信息架构回答“现在做什么”，不映射仓库文件夹。
- Prompt/Validation 仍可访问，但不会成为首屏主任务。
- 右侧面板默认空状态，引用点击后才显示详情。
- A/B mock 通过明确用户选择后，生产 CSS 才改变。
- 所有 IELTS 测试、全站测试、构建新鲜度和视觉 QA 通过。

## 风险与控制

- **把 Foundations 规则机械复制到考试训练。** 控制：诊断和模考保留限时；外部考试日期仍可驱动策略。
- **事件制变成没有复测。** 控制：错误状态机和 `two-mocks-available` 触发器把复测写进数据约束。
- **单线程导致其他技能遗忘。** 控制：完整模考负责发现回归；回归事件可以立即重排下一单元，但不同时开启多条主线。
- **隐喻压过可用性。** 控制：A/B 共享信息架构，并用 5 秒重入与移动端可读性做选择标准。
- **旧文件继续误导构建或测试。** 控制：归档而不是并行运行；构建入口和 tests 只接受 v2 schema。
- **继续优化网页替代学习。** 控制：生产发布后，下一动作固定为 D1 真实写作诊断；没有新证据不再启动第二轮设计改造。

## 实施顺序摘要

```text
红测试
  -> 源数据与 Prompt 迁移
  -> 构建/校验迁移
  -> 无皮肤信息架构
  -> A/B mock
  -> 用户选择门
  -> 生产视觉
  -> 全量验证与发布
  -> D1 真实诊断
```
