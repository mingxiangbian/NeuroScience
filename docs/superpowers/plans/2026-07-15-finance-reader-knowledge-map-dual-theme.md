# Finance Reader Knowledge Map And Dual-Theme Redesign Implementation Plan And Completion Record

> **状态：** 实现、本地 Chrome 验收与用户视觉确认均已完成；发布状态以 `main` 与 GitHub Pages 为准。

**Goal:** 把 Finance 学习页从“古金阅读器”升级为以概念依赖图为核心、默认夜间黑金、支持未来高密度财务数据展示的长期学习与分析工作台，同时修复回顶、选区、批注、笔记栏和无障碍缺陷。

**Architecture:** 保留现有 `modules/*.md -> build-roadmap-data.mjs -> roadmap-data.json -> shared reader` 数据流。Finance 的配色、知识图外观和数据表视觉继续隔离在 `projects/finance/`；主题记忆、真实滚动容器、选区批注、抽屉状态和焦点管理等通用行为在共享 Reader 中做最小修复，并同时回归 Foundations。概念依赖和投资决策作用由 Finance 模块 frontmatter 明确提供，构建时验证，页面不从正文猜关系。

**Tech Stack:** 静态 HTML、作用域化 OKLCH CSS、Vanilla ES Modules、Markdown/Frontmatter 构建、浏览器 `localStorage`、Node `assert` 合同测试、Chrome 实机验收；不增加前端框架或图形库。

## 已确认产品决策

- Overview 的第一职责是快速理解完整知识结构；概念依赖图是主视图，模块进度账表是精确查阅的次级视图。
- 概念节点点击或按 Enter 直接进入模块；聚焦节点时突出前置、下游和它在投资决策中的作用，不做原地展开详情。
- Finance 首次访问默认夜间模式；用户手动切换后按项目独立记忆。Foundations 保持自己的默认与偏好，不读取或监听系统主题。
- 夜间采用“黑曜黑金”，日间采用“深墨框架 + 中性墨白账页”；亮暗主题不是机械反相。
- 金色只表示当前、选中、核心指标和学习进度；钢蓝表示信息、比较、依赖与普通批注；方向性数据统一绿涨红跌；中性灰表示背景、未知和未开始。
- 桌面数据表采用终端式密度；移动端以阅读、复习和批注为主，不承载完整分析终端。
- Finance 普通模块正文、知识文章、列表和表格均可批注；交互文案必须与实际范围一致。
- 桌面笔记栏默认收为窄轨，创建或打开批注时临时展开，并记忆用户主动开合状态；移动端使用底部抽屉。

## 首版知识拓扑

以下关系来自现有九个模块的学习目标，作为实施时的明确数据合同；箭头表示“学习后者前，应该先理解前者”，不是投资操作步骤。`study-plan-tools` 与 `terms-further-reading` 是学习支持节点，保留在总图中，但不伪装成概念前置知识。

| 模块 | 直接前置模块 | 在投资决策中的作用 |
| --- | --- | --- |
| `investment-basics` 投资的本质与前提 | 无 | 先判断是否具备投资条件，并确定资金期限与安全边界 |
| `asset-classes` 资产类别 | `investment-basics` | 判断可选资产代表什么权利、回报来自哪里 |
| `risk-allocation` 风险与配置 | `investment-basics`, `asset-classes` | 确定能承受多少风险、不同资产应配置多少 |
| `fund-company-analysis` 基金与公司分析 | `asset-classes` | 判断候选基金或公司的质量、结构与关键风险 |
| `valuation` 估值 | `risk-allocation`, `fund-company-analysis` | 判断价格隐含了什么假设，以及价格是否留有安全边际 |
| `trading-execution` 交易与执行 | `risk-allocation`, `valuation` | 把仓位、价格、成本与再平衡约束落实为交易方式 |
| `behavior-process` 行为与流程 | `risk-allocation`, `fund-company-analysis`, `valuation`, `trading-execution` | 用检查清单与复盘约束偏差，形成可重复的最终判断流程 |
| `study-plan-tools` 学习计划与工具 | 无；`graph_role: support` | 安排学习顺序与练习，不直接给出买卖结论 |
| `terms-further-reading` 术语速查与延伸 | 无；`graph_role: support` | 在判断过程中补齐术语、公式与来源，不直接给出买卖结论 |

Frontmatter 使用现有简单解析器可稳定处理的单行格式：`prerequisites` 保存逗号分隔的模块 id，`graph_role` 保存 `concept` 或 `support`，`decision_use` 保存一句可独立理解的中文说明。构建器只解析这些显式字段，不从正文猜关系。

## 明确边界

- 不接入行情、财报或投资组合数据源；本轮只建立可承载这些数据的表格与图表视觉契约。
- 不保存持仓、交易、账户、个人财务或投资决策。
- 不新增测验、知识卡、推荐系统、图表编辑器或主题“跟随系统”第三状态。
- 不改变 Foundations 的视觉身份；共享文件只接受跨项目成立的行为与无障碍修复。
- 不复制共享 Reader CSS，不引入图布局或图表依赖。
- 不碰用户已有的未跟踪 `tmp/`。

## 完成标准

1. 首次打开 Finance 无亮色闪烁并显示夜间主题；Finance 与 Foundations 的主题选择分别持久化。
2. Overview 第一屏直接呈现“下一步”和可理解的概念依赖图，不再重复显示 Overview 自身的模块进度。
3. 知识图支持鼠标、键盘和触控；节点关系有文字等价表达，点击/Enter 可直接进入模块。
4. 普通模块切换在桌面和移动断点均立即回顶；搜索定点跳转仍落到目标 section。
5. Finance 所有声明可批注的正文块都能触发工具条；旧批注无损恢复；不支持的跨语义块选区给出明确反馈而非静默失败。
6. 粉色系统选区消失；普通选区、搜索命中、已保存高亮和带笔记批注在两套主题中可区分。
7. 桌面笔记栏默认只占窄轨；移动目录与笔记抽屉具备正确 ARIA、焦点归还和 44px 触控目标。
8. 桌面表格高密、数字可比较；移动表格只在局部横向滚动，页面本身无横向溢出。
9. Finance、Foundations、Projects 与全量测试通过；Chrome 亮暗、桌面、断点与移动验收通过。

## 文件范围

### 新建

- `docs/superpowers/plans/2026-07-15-finance-reader-knowledge-map-dual-theme.md`：本计划。

### 修改

- `docs/superpowers/specs/2026-07-13-finance-learning-reader-design.md`：以本轮已确认决策取代“否决默认黑金”的旧结论，并同步最终验收状态。
- `projects/finance/index.html`：Finance 静态默认暗色、首屏主题恢复、主题/笔记/目录控件语义。
- `projects/finance/finance-theme.css`：双主题语义令牌、黑金壳层、知识图、数据表、选区和响应式视觉。
- `projects/finance/README.md`：主题、批注范围、知识图和本地数据边界。
- `projects/finance/roadmap/modules/*.md`：为九个学习模块增加明确的 `prerequisites` 与 `decision_use` frontmatter；更新 Overview 说明。
- `projects/finance/scripts/build-roadmap-data.mjs`：解析并验证依赖图，生成知识图数据。
- `projects/finance/roadmap/roadmap-data.json`：由构建脚本重新生成，不手改。
- `projects/foundations/roadmap/reader-state-model.js`：加入可纯测的项目默认主题、存储键和初始主题解析。
- `projects/foundations/roadmap/annotation-model.js`：支持通用正文上下文与旧批注迁移。
- `projects/foundations/roadmap/roadmap-reader.js`：主题、Overview 图、回顶、焦点、批注、笔记轨和抽屉行为。
- `projects/foundations/roadmap/roadmap-reader.css`：只加入跨项目成立的滚动、焦点、抽屉、命中区域和 reduced-motion 结构规则。
- `tests/finance-learning-reader-requirements.mjs`：Finance 主题、Overview、批注范围、数据表和页面隔离合同。
- `tests/foundations-reader-state-model.mjs`：项目级主题解析与默认值测试。
- `tests/foundations-annotation-model.mjs`：新旧批注锚点、迁移和分组测试。
- `tests/foundations-roadmap-requirements.mjs`：共享行为和 Foundations 不回归合同。

### 实施偏差

- 原计划拟把知识图解析抽成独立模块并新增单独测试文件。实现审查后确认该逻辑只被 Finance 构建器使用，因此保留在 `build-roadmap-data.mjs`，由 `finance-learning-reader-requirements.mjs` 直接覆盖，避免为单一调用点增加抽象。
- 现有 `test:finance` 已覆盖 Finance 合同，无需修改 `package.json`。

## 实施顺序

### Task 1：先锁定设计来源与失败合同

**目标：** 在写实现前，让旧 spec、数据合同和测试明确反映本轮决定。

- [x] 更新 Finance 设计 spec：默认暗色、双主题材料逻辑、概念依赖图、项目级主题记忆、全正文批注、终端式桌面表格、移动阅读、默认折叠笔记轨。
- [x] 按“首版知识拓扑”在九个学习模块 frontmatter 中写入 `prerequisites`、`graph_role` 和 `decision_use`；不从标题或正文自动推断依赖。
- [x] 为知识图增加失败合同：所有节点必须对应现有模块；禁止自依赖、重复边与循环；每个非 Overview 模块必须有决策作用说明。
- [x] 为主题增加失败合同：Finance 默认 `dark`、Foundations 默认保持 `light`、存储键含 `PROJECT_ID`、非法值回退到项目默认。
- [x] 为回顶、Finance 批注范围、选区样式、笔记默认窄轨和主题控件状态增加静态/纯函数合同。
- [x] 运行聚焦测试，确认它们因缺少新实现而失败，而不是测试本身报语法或路径错误。

**验证：**

```bash
node tests/finance-learning-reader-requirements.mjs
npm run test:finance
npm run test:foundations
```

预期：新合同先红；既有无关测试仍通过。

---

### Task 2：实现项目级主题状态与无闪烁暗色首屏

**目标：** Finance 首访暗色，之后记忆用户选择；Foundations 使用独立键且视觉不变。

- [x] 在 `reader-state-model.js` 中加入纯函数：规范化 `light/dark`、生成项目级存储键、解析“已保存偏好 > HTML 项目默认”的优先级。
- [x] Finance HTML 静态默认改为暗色；在首屏内容绘制前同步恢复该项目已保存的亮/暗值，捕获 localStorage 不可用或非法值。
- [x] 删除异步数据加载后的 `setTheme("light")` 强制覆盖；初始化应尊重已解析的 body 主题。
- [x] 用户点击主题按钮后才持久化；Finance 与 Foundations 使用不同键，不加入 `prefers-color-scheme`。
- [x] 同步按钮 `aria-pressed`、太阳/月亮图标和“切换日间/夜间模式”标签。
- [x] 主题切换只过渡颜色、背景和边界；`prefers-reduced-motion: reduce` 下立即切换。

**验证：**

- 清空 Finance 存储后首次打开为暗色。
- Finance 切到日间并刷新后仍为日间；Foundations 不跟随。
- localStorage 抛错或保存非法值时页面仍能以项目默认主题加载。
- 浏览器录屏/逐帧检查无先亮后暗闪烁。

---

### Task 3：重建 Finance 双主题视觉系统

**目标：** 夜间是黑曜黑金，日间是深墨框架与中性墨白账页；品牌色和数据语义分离。

- [x] 在 `finance-theme.css` 中建立两层令牌：primitive 色阶与 semantic 角色；暗色只重定义 semantic 层。
- [x] 建立三阶表面：页面、正文/表格、抬升控件。暗色靠表面明度而非阴影制造层级；日间靠实色边界与极浅局部阴影。
- [x] 分离金色文字与金色图形；增加钢蓝、上涨绿、下跌红、中性灰、控件边界、进度空轨、选区、搜索命中、批注和表格网格令牌。
- [x] 移除穿过正文的斜线纹理、普通面板宽阴影和默认毛玻璃；控件不再同时使用 1px 边框与 16px 以上模糊阴影。
- [x] 显式定义 `::selection` 与 `::-moz-selection`：日间浅金底深墨字，夜间深金棕底米白字。
- [x] 普通选区、搜索命中、纯高亮和带笔记批注使用不同的背景/下划线/标识组合，不只靠色相。
- [x] 缩小普通模块标题占高，正文宽度控制在 65–75ch；Overview 使用独立紧凑头部。
- [x] 计算并记录正文、小标签、图形、边界和 focus ring 的实际对比度。

**验收信号：** 正文至少 4.5:1；大字、图形与焦点至少 3:1；暗色中金、蓝、绿、红不合并；代码注释和控件边界清晰。

---

### Task 4：把 Overview 改成“概念依赖图 + 学习账表”

**目标：** 第一屏先回答“知识如何相互依赖”，再提供准确的模块状态查阅。

- [x] 构建器从模块 frontmatter 生成 `project.knowledgeGraph`：节点、依赖边、拓扑层、决策作用文字；构建失败时明确指出错误模块。
- [x] Overview 不再渲染“本模块学习进度”；只保留一次整体进度，并把“下一步”放在第一视觉层级。
- [x] 在“下一步”之后渲染概念依赖图；普通节点使用中性表面，当前/聚焦节点使用金色，依赖路径使用钢蓝，无关节点降噪。
- [x] 聚焦/悬停节点时同时突出它的前置和下游，并在固定说明区显示其投资决策作用；不打开悬浮详情卡。
- [x] 点击、Enter 或 Space 直接进入相应模块；返回 Overview 后保留上次聚焦节点。
- [x] 为知识图提供可读名称、操作说明、方向键移动和文本版关系说明；视觉连线不是唯一信息来源。
- [x] 桌面使用稳定的分层拓扑布局；移动端改为纵向依赖层级，不要求缩放或拖动才能读清节点。
- [x] 图下方提供终端式模块账表，列为模块、状态、进度、当前动作；它承担精确查值，不与知识图争夺主层级。

**验收信号：** 1440×900 第一屏看得到“下一步”、知识图主体和账表表头；每个模块恰好一个节点；任一节点均可用键盘进入；320px 无页面级横向溢出。

---

### Task 5：修复模块切换回顶、焦点与导航状态

**目标：** 普通模块切换立即从顶部开始，搜索/章节定点跳转不被破坏。

- [x] 抽出真实滚动容器判断：桌面使用 `#reader-main`，`<= 860px` 使用 `document.scrollingElement`；不要继续固定写 `els.main.scrollTop`。
- [x] 普通模块切换使用即时回顶，避免继承 `scroll-behavior: smooth` 后出现约 1 秒的中间画面。
- [x] 搜索结果和章节 rail 的目标跳转保留定点语义；用户主动滚动仍可取消延迟导航。
- [x] 模块切换后把焦点放到新模块稳定标题或主区域，并通过 live region 宣布模块标题；导航重绘不能把焦点丢到 body。
- [x] 将当前模块按钮滚入左侧导航可视区。
- [x] 放大折叠章节 rail 的真实点击区到至少 44px，视觉线条仍可保持纤细。

**浏览器断点：** 1101/1100px、861/860px、390px；分别从页面底部切换模块并断言真实 scroll owner 为 0。

---

### Task 6：把 Finance 批注扩展到整个模块正文

**目标：** 用户在普通正文、知识文章、列表和表格中选择重要句子时都得到一致的批注工具。

- [x] 给 Finance 的每个可批注语义块分配稳定 context id；普通 section 使用 section id，知识文章继续兼容 note id。
- [x] Finance 通过明确的页面配置启用“全部正文”范围；Foundations 缺省继续保持现有 knowledge-only 范围，避免无意扩大另一项目行为。
- [x] 升级批注记录，保存 module、context、选中文字、match index 与必要的前后文；迁移 v1 `noteId` 数据且不丢摘录、分类、正文和时间戳。
- [x] 首尾空白规范化后再校验选区，修复三击段落时末端换行导致的误拒绝。
- [x] 支持同一语义块内跨多个文本节点的高亮；跨 section/card 的选区不创建无效 DOM，并显示明确提示而非静默无反应。
- [x] 增加 `pointerup`、键盘选区和移动长按后的可靠触发；工具条四边限制在视口内。
- [x] 工具条、已有高亮和删除菜单支持 Tab、Enter/Space、Escape，并在保存/删除后提供读屏状态提示。
- [x] 从批注打开右栏时，以 section/article 标题作为上下文；右栏文案改为“模块正文均可批注”。

**验证内容：** 普通段落、列表、表格单元格、知识文章、重复文本、刷新恢复、v1 数据迁移、右边缘选区、移动长按和纯键盘操作。

---

### Task 7：重做笔记轨与移动抽屉

**目标：** 笔记不再为空时长期占据约四分之一桌面宽度，但需要时能立即进入。

- [x] 桌面默认显示 44–52px 笔记轨；使用明确的笔记图标和数量徽标，展开宽度约 280–320px。
- [x] 用户主动开合状态按项目记忆；新建/打开批注只触发本次临时展开，不错误覆盖长期偏好。
- [x] 展开/折叠前后保持正文 scrollTop，不因 grid 变化跳动。
- [x] 主题、目录、笔记按钮补齐 `aria-controls`、动态 `aria-expanded` 和准确状态文案。
- [x] `<= 1100px` 使用移动底部抽屉：打开后焦点进入，背景退出 Tab 顺序，Escape/遮罩/关闭按钮均可关闭，关闭后归还焦点。
- [x] 抽屉内部独立滚动，编辑框在软键盘和安全区下仍可见。

**验收信号：** 1294px 初始主阅读区明显占主权重；320px 与横屏抽屉不越界；断点切换后视觉状态与 ARIA 状态一致。

---

### Task 8：建立高密财务表格与未来图表视觉契约

**目标：** 当前 Markdown 表格立即获得可用的终端密度，同时为未来数据分析保留一致的颜色与组件接口。

- [x] 渲染后为宽表添加局部滚动容器，保留原生 `table/thead/tbody/th` 语义；静态单元格不进入 Tab 序列。
- [x] 桌面表格行高约 28–32px，标签左对齐、数值右对齐，使用 tabular numerals；表头和首列可按需要 sticky。
- [x] 合计、同比、异常和当前周期通过字重、完整边界、符号与淡洗色表达，不使用粗侧边条。
- [x] 上涨/正值使用绿并保留 `+`/上箭头；下跌/负值使用红并保留 `-`/下箭头；零值与缺失值保持中性。
- [x] 定义未来图表令牌：focal gold、comparison steel-blue、gain green、loss red、benchmark neutral、grid/zero line；单图默认不超过两个非中性色，类别确有必要时最多五个。
- [x] 移动端保持正文阅读字号；宽表只在自身容器横向滚动并固定指标列，不把桌面终端整体缩小，也不制造页面级横向滚动。

**范围提醒：** 本任务不创建虚构财务数据或图表，仅交付可复用的表格样式、语义类和图表色彩合同。

---

### Task 9：综合回归、Chrome 验收与发布门槛

**自动验证：**

```bash
node --check projects/foundations/roadmap/roadmap-reader.js
node --check projects/foundations/roadmap/annotation-model.js
node --check projects/foundations/roadmap/reader-state-model.js
node --check projects/finance/scripts/build-roadmap-data.mjs
node projects/finance/scripts/build-roadmap-data.mjs
npm run test:finance
npm run test:foundations
npm run test:projects
npm run test:all
git diff --check
```

**已完成的 Chrome 验收：**

- 桌面：暗色/日间总览、正文、三栏权重、笔记窄轨和高密表格。
- 390×844、320×568：总览、正文、表格局部滚动、目录、批注和底部笔记抽屉。
- 主题：首次暗色、项目级记忆隔离、切换无闪烁、显式古金选区。
- 交互：模块回顶、搜索定点、节点导航、批注保存/删除/恢复、互斥抽屉、删除弹层、Escape 和焦点归还。
- Foundations 回归：通过共享 Reader 合同和全量项目测试确认默认主题、知识文章范围及基础交互未退化。

**发布门槛：**

1. 本地所有自动检查和 Chrome 验收通过。
2. 将最终亮暗与桌面/移动截图交给用户；只有明确回复“确认”或“通过”才视为视觉验收通过。
3. 验收后合并到 `main`、push，并等待 GitHub Pages workflow 成功。
4. 在部署页重复检查默认夜间、主题记忆、知识图、回顶和批注，再宣告完成。

## 实施与验收记录

- 实现按一个完整功能提交发布，提交信息为 `feat: redesign finance learning reader`。
- “全正文可批注”最终解释为：Finance 的每个正文语义块都可批注；允许同一语义块内跨文本节点，跨 section/card 的超大选区明确提示重新选择，不生成跨多个块的单个高亮。
- 2026-07-15：用户确认知识拓扑、黑金/日间双主题、数据配色和终端式密度方向。
- 2026-07-15：本地自动检查、Chrome 桌面/移动验收与用户最终视觉确认通过。
