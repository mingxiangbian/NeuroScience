# IELTS Reader Data Consumption And Reliability Design

Date: 2026-07-07

Status: Approved design

## 1. Context

`projects/language/ielts-academic/` 已经有较完整的数据层：`diagnostics/*.json`、`plans/checkpoint-status.json`、`notes/`、`journal/`、`prompts/`、`validation/` 和 `scripts/build-ielts-data.mjs` 都能生成 `site/ielts-data.json`。当前主要缺口不是缺少数据，而是 reader 没有充分消费数据，构建层也没有足够的结构校验。

已核实的现状：

- `projects/language/ielts-academic/site/ielts-reader.js` 约 1600 行，混合了数据适配、渲染、引用、localStorage 状态、annotation 和交互逻辑。
- `laneText(label, week)` 基本只按 week 返回固定文案，未真正按 Listening / Reading / Writing / Speaking 的 skill profile 个性化。
- checkpoint 当前只挂在 `Errors` lane，对用户来说容易被误解为错误日志事件。
- `scoreHistory` 已进入 `site/ielts-data.json`，但 reader 没有实际渲染趋势。
- note / journal 的 `related_errors` 和 `related_notes` 已被 build script 校验，但 UI 仍把很多引用渲染成不能跳转的文本 chip。
- source chip 直接链接到原始 `.md` 相对路径，容易把用户带出 reader 体验。
- task checkbox id 使用数组下标，source 顺序变化时可能错配。
- Markdown preview 是手写轻量 parser，无法覆盖 prompt / validation / notes 常见 Markdown。
- `.github/workflows/pages.yml` 和 `.nojekyll` 已存在，Pages 基础部署路径不是主要缺口；但 workflow 目前没有在上传 artifact 前强制运行 IELTS build 和相关测试。

## 2. Goals

- 让 reader UI 真正消费已有数据：`scoreProfile`、`scoreHistory`、`checkpoints`、`errorLog`、`notes`、`journal`、`promptLibrary`、`validation`。
- 让 build layer 成为数据质量门禁：核心 schema 严格失败，扩展字段宽松 warning。
- 把 Markdown 解析从 reader 移到 build 阶段，reader 只展示安全 HTML。
- 建立内部引用系统：chip 点击留在 reader 内，通过右侧 panel 展示详情和 backlinks。
- 保留 annotation，但明确为本机临时阅读标注，不替代 git 版本化的 `journal/`。
- 修复 task state 正确性，让 checkbox id 稳定。
- 增加模块级错误边界、无障碍语义、平台快捷键文案和对比度检查。
- 让 Pages workflow 在部署前运行 build 和相关测试，防止坏数据进入站点。

## 3. Non-Goals

- 不做后端写回。
- 不自动创建或修改 `journal/entries/*.md`。
- 不改变 IELTS 学习内容语义；可以增加派生字段、引用索引和安全 HTML。
- 不把 Foundations reader 和 IELTS reader 抽象成通用 reader framework。
- 不引入大型前端框架。
- 不把 annotation / task state 作为 repo source of truth。

## 4. Architecture

本次整改分为两层。

### Build/Data Layer

入口仍是 `projects/language/ielts-academic/scripts/build-ielts-data.mjs`，但允许拆 helper：

- `build-schema.mjs`：校验 JSON shape、必需字段、类型、枚举和引用完整性。
- `build-markdown.mjs`：把 Markdown 转成安全 HTML。
- `build-references.mjs`：生成内部 reference targets、backlinks 和 source link metadata。
- `build-sources.mjs`：自动扫描 `prompts/`、`validation/`、`notes/`、`journal/`。

输出仍写入 `projects/language/ielts-academic/site/ielts-data.json`。Reader 不直接读取 Markdown source files。

### Reader/UI Layer

Reader 只消费 build 输出：

- module navigation、search、right panel、task state、annotation state 仍在浏览器端。
- score / error / checkpoint / notes / journal / prompts / validation 均来自 `site/ielts-data.json`。
- 前端可以 reshape 数据用于展示，但不能把 source data 写回 `localStorage` 或 repo。

允许拆分前端模块，例如：

- `reader-state.js`
- `reader-renderers.js`
- `reader-references.js`
- `reader-modules.js`
- `reader-annotations.js`
- `reader-tasks.js`

拆分目标是边界清晰，不是做 framework 化抽象。

## 5. Data Schema And Build Validation

Schema 策略采用“核心严格，扩展宽松”。

### Fatal Build Errors

这些问题必须让 build 失败并阻止 Pages artifact 上传：

- `score-profile.json` 缺 `schemaVersion`、`target`、`skills`、`currentEstimate`。
- skill 缺 `id`、`label`、`estimatedBand`、`confidence`、`riskLevel`。
- `score-history.json` 的 `entries` 不是数组，或 entry 缺 `date`、`week`、`skills`。
- `checkpoint-status.json` 的 `checkpoints` 不是数组，或 checkpoint 缺 `week`、`name`、`purpose`、`status`、`evidenceRequired`。
- `error-log.json` 的 error 缺 `id`、`skill`、`impact`、`status`、`description`。
- `error.status` 不属于 `active`、`improving`、`fixed`、`regressed`。
- `error.impact` 不属于 `high`、`medium`、`low`。
- note / journal 引用不存在的 error 或 note。
- required source file 读取失败。

### Warning Issues

这些问题不阻断 build，但必须进入 `data.build.validationIssues` 并在 Validation module 显示：

- 未知字段。
- 可选展示字段缺失，例如 `reviewMethod`、`nextReview`。
- Markdown 文档缺 frontmatter。
- prompt / validation 文档缺一级标题。
- score history entry 缺 optional notes。
- source link 可生成但不是 reader 内主导航对象。

### Build Output Additions

`site/ielts-data.json` 增加：

- `build.contentUpdatedAt`：来自 `scoreProfile.lastUpdated`。
- `build.generatedAt`：构建日期。测试可以通过 env 固定日期，避免随机输出破坏 deterministic check。
- `build.validationIssues`: `{ severity, type, path, message }[]`。
- `references.targets`: 所有可跳转对象的 `{ id, type, label, moduleId, sectionId, sourcePath }`。
- `references.backlinks`: note / journal / error / prompt / validation 的反向引用。
- `sourceLinks`: 原始 `.md` 路径作为次级入口。
- Markdown source 的 `html` 字段，包含安全 HTML。

`promptSources` 和 `validationSources` 不再手写白名单；build layer 递归扫描对应目录，按 path 排序，生成稳定 id。

## 6. Reader UI Design

### Dashboard

Dashboard 展示：

- target：overall、per-skill floor、timeline。
- current estimate：overall、confidence、summary。
- skill gap：每项 skill 的 estimated band、gap、confidence、riskLevel、unverified dimensions。
- score history：按 date / week 展示 overall 和四项技能趋势。模板态数据不伪造趋势，显示“暂无真实诊断轨迹”。
- validation status：fatal / warning / clean 的计数和入口。

### Swimlane

取消纯静态 `laneText(label, week)`。

每个 skill lane 根据以下数据生成该周重点：

- `scoreProfile.skills[].riskLevel`
- `scoreProfile.skills[].unverifiedDimensions`
- `errorLog.errors` 中对应 skill 的 high / medium impact errors
- checkpoint `evidenceRequired`
- template state / not-yet-run state

Checkpoint 不再出现在 `Errors` lane，而是作为横跨所有 skill 的全局里程碑带。Week 2 / 4 / 6 / 8 显示 checkpoint name、status、decision 和 evidence summary。

如果数据仍是 template state，swimlane 明确显示“诊断前模板态”，避免用户误读为真实个性化训练计划。

### References And Right Panel

所有 `related_errors`、`related_notes`、source chips 都绑定 build layer 生成的 internal reference target。

点击 chip 时：

- 不离开 reader。
- 右侧 panel 显示对象类型、标题、状态、skill、date、摘要、source path、关联对象和 backlinks。
- 提供“跳转到模块位置”按钮。
- 提供次级“查看源文件”链接。

Notes module 必须显示 backlinks：例如某篇 note 被哪些 journal entries 引用。

### Source Links

原始 `.md` 路径不是主导航。Source chip 默认打开 right panel；panel 内再提供 source link。这样用户不会从 reader 的主流程跳到无样式 Markdown。

返回链接需要明确语义。当前 `projects/language/ielts-academic/index.html` 的 `../../` 指向 `projects/` 总目录。如果 label 是“返回项目”，该目标可以保留；如果未来改成“返回语言”，目标必须改成 `../`。

## 7. Markdown Rendering

Markdown 在 build 阶段转换为安全 HTML。

最低支持：

- headings
- unordered / ordered lists
- bold / emphasis
- inline code
- fenced code blocks
- links
- tables
- blockquotes

Reader 不继续扩展 `renderMarkdownPreview`。旧函数可以删除或只保留为 error fallback，不能作为 notes / journal / prompts / validation 的主渲染路径。

HTML sanitization 必须拒绝 script、inline event handlers、unsafe URLs。允许的链接协议限制为 relative path、`https:`、`http:` 和 `mailto:`。

## 8. Annotation And Journal Boundary

Annotation 保留，但定义为本机临时阅读标注：

- 存储位置仍为 `ieltsReader.annotations.v1`。
- UI 文案必须说明“不写回 repo，不替代 journal”。
- 右侧 panel 或 annotation list 增加“复制为 journal 草稿”按钮。

复制为 journal 草稿时，生成 Markdown 文本，包括：

- suggested filename，如 `journal/entries/YYYY-MM-DD-reader-note.md`
- frontmatter 草稿：`date`、`related_notes`、`related_errors`、`source_anchor`
- selected text
- user annotation body
- source object label / path

不会自动写文件。用户手动创建 journal entry。

Annotation 重新定位失败时，不再静默忽略。Annotation list 显示“定位失效”，并保留文本和 source metadata。

## 9. Task State

Task checkbox id 不再使用数组下标。

稳定 id 规则：

1. 如果 source object 有 id，使用 source object id。
2. 加上 field name，例如 `reviewMethod`、`evidenceRequired`、`dailyTask`。
3. 加上 task text 的短 hash。

示例：

```text
error:writing-task2-argument:evidenceRequired:4f9a12
checkpoint:week-6:evidenceRequired:9b103c
```

如果 source 顺序变化，旧 checkbox state 不应错配到另一个任务。旧下标格式可以保留读取兼容，但不再写入。

## 10. Reliability And Error Handling

Reader 初始化分层处理：

- JSON fetch 失败：整页加载失败。
- Data shape 已通过 build schema，但单个 module render 仍可能失败：该 module 显示错误卡片，其余 modules 继续可用。
- Validation module 必须优先可用，用于展示 build validation issues。
- Console 保留可调试错误；UI 不展示完整 stack trace。

模块错误卡片显示：

- module name
- 简短错误说明
- 建议检查 `site/ielts-data.json` 或 build output

## 11. Accessibility And Platform Details

- Swimlane 优先使用 `<table>`、`<thead>`、`<tbody>`、`<th scope="row/col">`。如果保留 CSS Grid，必须加入 `role="table"`、`role="row"`、`role="columnheader"`、`role="rowheader"`、`role="cell"`。
- Search 快捷键提示按平台显示：Mac 为 `⌘ K`，其他平台为 `Ctrl K`。
- 引用 chip、task checkbox、annotation toolbar、right panel jump action 必须可键盘操作。
- 小号浅色文本需要抽查对比度。若不达标，提高 `--reader-ink-muted` 对比度或字号。
- 移动端不能出现全页横向 overflow；right panel 在窄屏应保持 drawer 行为。

## 12. Tests

新增或强化测试：

- Build schema fixture：坏 JSON 让 build 失败；未知字段只产生 warning。
- Build script 自动扫描 `prompts/` 和 `validation/`，不依赖手写白名单。
- `scoreHistory` 必须被 reader contract 消费并出现在 Dashboard。
- Swimlane 不再只按 week 返回静态文案；必须引用 skills / risk / errors / checkpoints。
- Checkpoint 不再只出现在 `Errors` lane。
- Reference chips 必须绑定 internal target，不把 note / error / journal 引用渲染成纯 `span`。
- Source links 不作为主导航直接带出 reader。
- Task IDs 不使用数组下标。
- Markdown HTML 由 build layer 生成，reader 不依赖手写 Markdown parser。
- Annotation 有“复制为 journal 草稿”出口和定位失效提示。
- Module render error boundary 存在。
- Shortcut hint 区分 Mac 和 non-Mac。
- Pages workflow 在 artifact 上传前运行 build 和相关 tests。

保留现有测试：

- `tests/projects-requirements.mjs`
- `tests/ielts-academic-language-project-requirements.mjs`
- `tests/ielts-academic-site-data-requirements.mjs`

必要时新增更聚焦的 tests，例如 `tests/ielts-reader-data-consumption-requirements.mjs` 和 fixture 目录。

## 13. CI / Pages Gate

`.github/workflows/pages.yml` 在 `Prepare Pages artifact` 前增加：

1. setup Node
2. run `node projects/language/ielts-academic/scripts/build-ielts-data.mjs`
3. run `node tests/projects-requirements.mjs`
4. run `node tests/ielts-academic-language-project-requirements.mjs`
5. run `node tests/ielts-academic-site-data-requirements.mjs`
6. run any new IELTS reader data consumption tests

任何 build fatal issue 或测试失败都阻止 Pages artifact 上传。

## 14. Implementation Phases

Implementation plan 应分四阶段：

1. **Build/data integrity**
   - schema 校验
   - source 自动扫描
   - Markdown 转安全 HTML
   - validation issues 输出
   - CI gate

2. **Reader data consumption**
   - score history dashboard
   - skill-aware swimlane
   - global checkpoint milestone band

3. **Internal reference/navigation**
   - reference targets
   - backlinks
   - right panel details
   - source link 降级为次级入口

4. **Reliability/accessibility polish**
   - stable task ids
   - annotation journal draft export
   - module error boundaries
   - shortcut platform text
   - swimlane semantics and contrast checks

每个阶段都需要先写 failing tests，再实现，最后跑相关测试。

## 15. Acceptance Criteria

- `site/ielts-data.json` 包含 `build.validationIssues`、`references.targets`、`references.backlinks`、Markdown `html` 字段和拆分后的 build timestamps。
- Schema fatal errors 会让 build 失败。
- Unknown optional fields 只产生 warning。
- Reader Dashboard 显示 score history 或模板态空状态。
- Swimlane 根据 skill profile / errors / checkpoints 渲染，不再是四个技能完全一样的静态网格。
- Checkpoints 是全局里程碑，不挂在 `Errors` lane。
- Notes / journal / errors 的引用 chip 可点击，并在 right panel 展示详情和 backlinks。
- Source path 不再作为主点击行为把用户带出 reader。
- Markdown 常见格式正确显示。
- Annotation 明确为临时本机状态，并可复制为 journal 草稿。
- Task checkbox id 稳定，不依赖数组下标。
- 单个 module 渲染失败不会拖垮整页。
- Pages workflow 在部署前强制运行 build 和相关 tests。

## 16. Risks And Mitigations

- **范围过大。** 用四阶段 plan 控制，每阶段独立测试和提交。
- **拆分文件引入路径错误。** 保持 `index.html` 的 module script 入口稳定，新增 modules 只由入口 import。
- **Markdown sanitizer 过严导致内容丢失。** 先支持常见 Markdown，不支持的 HTML 直接剥离而不是执行。
- **旧 localStorage task state 不兼容。** 允许读旧格式但只写新稳定 id；不迁移无法可靠映射的旧下标任务。
- **CI build 生成文件造成 diff churn。** Build output 必须 deterministic；test fixture 设置固定 date env。

## 17. Verification Commands

Implementation 完成后至少运行：

```sh
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
node tests/projects-requirements.mjs
node tests/ielts-academic-language-project-requirements.mjs
node tests/ielts-academic-site-data-requirements.mjs
git diff --check
```

若新增测试文件，plan 必须把对应命令加入 verification list。
