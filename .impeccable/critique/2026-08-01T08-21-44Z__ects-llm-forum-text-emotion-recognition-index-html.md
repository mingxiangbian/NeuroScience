---
target: 对比之前的样本，看这里的实现有哪些缺点？
total_score: 29
p0_count: 0
p1_count: 2
timestamp: 2026-08-01T08-21-44Z
slug: ects-llm-forum-text-emotion-recognition-index-html
---
Method: dual-agent (A: /root/critique_assessment_a · B: /root/critique_assessment_b)

# 情感识别进度页设计审查

## Design Health Score

| # | Nielsen 启发式 | 分数 | 关键问题 |
|---|---|---:|---|
| 1 | 系统状态可见性 | 3/4 | Current state、证据日期和状态标签清楚，但缺少更紧凑的阶段总览。 |
| 2 | 与真实研究工作匹配 | 4/4 | RQ、EXP、test gate、DEV ONLY 等语言与作者的研究工作高度一致。 |
| 3 | 用户控制与自由 | 2/4 | 有页内索引和文档入口，但三条关键 GitHub 深链接当前无法落到对应标题。 |
| 4 | 一致性与标准 | 3/4 | 视觉和状态体系统一；中英文微标签、重复状态表达仍可收束。 |
| 5 | 错误预防 | 4/4 | 数据集分区、test 消费状态、不可横比说明和公开边界非常严谨。 |
| 6 | 识别优于记忆 | 2/4 | RQ、实验、结论之间仍需人工拼接；移动端后两个 RQ 依赖隐式横滑。 |
| 7 | 灵活性与效率 | 2/4 | 高质量但偏长；大 hero、重复 EXP-028 状态和 7,672px 移动长页拖慢高频复盘。 |
| 8 | 美观与极简 | 3/4 | Cyber Ink 有鲜明身份，不像模板；留白和重复信息略削弱工作台效率。 |
| 9 | 错误恢复 | 3/4 | 有加载、无脚本与边界说明；外链失效时没有替代的页内证据定位。 |
| 10 | 帮助与文档 | 3/4 | README、Evidence Log、Roadmap 齐全，但深链接准确性影响帮助质量。 |
| **总计** |  | **29/40** | **Good：基础扎实，下一步应修复追溯链与高频使用效率。** |

## Anti-Patterns Verdict

**LLM assessment：不像典型 AI 生成网页。** 米色纸张、深墨、克制青蓝与朱砂、衬线大标题形成了清晰的 Cyber Ink 身份；没有通用 SaaS 卡片墙、玻璃拟态或装饰性渐变。问题不是“AI 味”，而是从工作台滑向了编辑式长文。

**Deterministic scan：** 对 `projects/llm-forum-text-emotion-recognition/index.html` 的 detector 原始结果为 `[]`，总命中 0、类别计数 `{}`、无误报。扫描范围不含外链 CSS/JS，因此这只能证明 markup 没触发内置反模式，不能替代布局与运行态审查。

**Visual overlays：** 浏览器运行时只提供只读 evaluate，无法可靠修改 DOM 或注入检测脚本，因此没有可交付的可视 overlay；未启动本地 server。替代证据为线上 1440×1000、默认约 1169px 与 390×844 的实测截图/DOM 测量。

## Overall Impression

当前实现把三个样本统一成了一套可信的研究语言，但“统一”同时削平了各样本最有价值的结构：

| 样本 | 当前保留 | 当前损失 |
|---|---|---|
| A · Research Ledger | Current state、Next、Blocker、Test gates、Recent changes | 一屏项目管理密度；中窄桌面下行动边栏掉到正文末尾。 |
| B · Experimental Observatory | TweetEval / GoEmotions 分区、指标、2×2 对照、负结果 | 两数据集并置和横向实验依赖；不再能一眼看出“实验为何接着实验”。 |
| C · Evidence Map | 左侧 RQ 轨、Verified / Planned / Blocked 边界 | dataset → model → experiment → evidence → future 的显式关系网。 |

最大的机会不是增加功能，而是把当前“优雅的研究报告”重新拉回“每天打开就知道为何、做到哪、接下来做什么的实验工作台”。

## What’s Working

1. **证据卫生是页面最强的资产。** TweetEval official test 与 GoEmotions dev 被严格分开，负结果、test consumed、阈值差异和隐私边界都没有被视觉包装掩盖。
2. **视觉身份成立。** 当前风格比样本 A 更有个人研究站气质，也比样本 B/C 更适合长期沉淀，不会像一次性答辩看板。
3. **响应式基础可靠。** 实测 390px 时 `scrollWidth === clientWidth === 390`，表格和图形成功堆叠，Next action 也被主动前置；问题主要是信息顺序，不是破版。

## Priority Issues

### [P1] 证据深链接与已发布文档不同步

**Why it matters：** 页面把“可追溯证据”当作核心承诺，但 EXP-017、EXP-025/026 和 EXP-028 的链接当前都无法在 GitHub `main` 落到目标标题。`HEAD` 的 Evidence Log 不含 EXP-017/026 标题，Roadmap 仍是 `Phase 4: LLM Comparison`，与页面使用的长 fragment 不一致。这会直接破坏页面最可信的部分。

**Fix：** 先同步发布对应 Evidence Log / Roadmap 内容，或把页面 fragment 改为当前已发布标题；增加对 GitHub heading fragment 的发布前检查。

**Suggested command：** `$impeccable harden`

### [P1] RQ → 实验 → 证据 → 结论的关系表达弱于样本 C

**Why it matters：** 左侧 RQ 只是索引，中央 route 只是阶段摘要，具体 EXP 与 claim 分散在后文。本人重返项目、导师快览时仍要心算“哪个证据回答哪个问题”。

**Fix：** 不必恢复 C 的整张复杂节点图；在每个数据集标题和关键 finding 旁固定显示 `RQ / latest verified EXP / current claim / next dependency` 四项小关系带，并让左侧 RQ 直接定位到相应 claim。

**Suggested command：** `$impeccable shape`

### [P2] 高频复盘被大 hero 和重复状态拖慢

**Why it matters：** 1440px 首屏中工作台从约 y=525 才开始；Current state、Single next action、Future work 的 NOW 三次表达 EXP-028。对作品集是仪式感，对每天查看进度则是摩擦。

**Fix：** 保留视觉身份，但压缩回访态 hero；将 Current state 与 Single next action 合为一条工作带，Future work 只保留 NEXT / SCOPE GATE / LATER。

**Suggested command：** `$impeccable distill`

### [P2] 响应式重排拆散了行动闭环

**Why it matters：** 1180px 以下右侧 working margin 整体落到正文后；390px 虽将 Next 提前，但 Blocker 与 Test gates 仍在约 7,600px 长页末端。RQ 轨横向可滚，却没有明显滑动提示，首屏只露出 B1–B3。用户可能在看到约束前就开始下一实验。

**Fix：** 移动端把 Next + Blocker + Test gates 作为一个紧凑行动模块放在证据正文前；RQ 轨改为两行/可折叠列表，或加入明确的溢出提示与当前 RQ 保证可见。

**Suggested command：** `$impeccable adapt`

### [P3] 完整量尺诚实，但对微小实验差异不够敏感

**Why it matters：** 0–1 量尺正确避免夸大，但 TweetEval 的 0.7926、0.7958、0.8100 在视觉上几乎挤在一起；误差只以 `±` 文本出现。读者能看到排名，却不容易看出 delta、方差与“是否值得继续”的关系。

**Fix：** 保留完整量尺作为主图，同时在关键对照旁增加 delta 与误差范围；将不可比较/阈值 caveat 贴近对应序列，而不是只放在图后说明。

**Suggested command：** `$impeccable clarify`

## Persona Red Flags

**作者本人（日常复盘）**：打开后能立即看到 Current state，但需要越过大 hero，并在 Current state、Next、Future NOW 之间判断哪个才是权威入口；在窄屏下还要滚到文末才能看到 blocker 与 gates。

**导师 / 答辩快览者**：能相信数字边界，却无法在一分钟内从 RQ 直接追到实验、证据和结论；点击三条关键证据深链接也无法到达目标标题，削弱可核验性。

**作品集访客**：会记住纸墨风格和严谨研究纪律，但 EXP/RQ 缩写、长页与低关系密度使“你解决了什么、做出了什么判断”不够快。当前阶段不应为了此画像牺牲作者效率，但应保留未来的摘要层空间。

## Minor Observations

- 中英文混排适合专家工具，但 `Verified / Preserved / In progress` 与中文正文可进一步统一语法，不必全部翻译。
- no-JS 回退仍保留“正在读取”式状态，虽然有 Evidence Log 入口，但语义略矛盾。
- 1169px 附近右栏下移后，页面比 1440px 明显更像单列长报告；1180px 这个断点对常见笔记本窗口较敏感。
- 现阶段没有模型交互不是缺点；页面已经清楚声明 `No model demo in V1`，符合范围。

## Questions to Consider

1. 第一版是否明确以“本人每天复盘效率”为最高优先，而不是兼顾答辩的一分钟叙事？
2. RQ 关系层希望采用“轻量四项关系带”，还是更接近样本 C 的显性证据图？
3. 移动端是否同意把 Next、Blocker、Test gates 合并前置，即使首屏会更密？
4. 数据图是否继续只用完整量尺，还是接受“完整量尺 + delta/误差辅助层”？
