# 投资学习阅读器（Finance Learning Reader）设计

- 日期：2026-07-13
- 状态：设计已批准；实现暂缓（用户明确本次只要设计，不实现）
- 位置：`projects/finance/`
- 项目类型：knowledge / learning（按 `docs/project-creation-workflow.md` 路由）

## 背景与目标

`projects/finance/` 目前只有一份 42KB 的《投资入门详细教程》（`investment_beginner_guide_zh.md`，23 节，含 12 周学习计划、记录模板与术语表）。用户要在整个学习工作区下为投资学习建立一个子项目页，要求：记录学习内容、提升学习效率、便于沉淀成知识库供后续查阅。

用户确认的两个学习效率优先级：

1. **再入性（re-entry）**：打开页面立刻知道学到哪、下一步做什么。
2. **沉淀查阅（retrieval）**：术语、概念随时能检索到。

两者均由 Foundations 阅读器的既有机制覆盖（进度 + Overview 仪表盘；全文搜索 + 模块化），不新增机制。

## 范围

**做**：Foundations 风格 reader/dashboard（方案 A），教程模块化，站点集成。

**不做**（用户已确认）：

- 不做自测题/知识卡机制，不做复盘专栏。
- 不记录真实投资实践（决策日志、持仓、实盘复盘）。站点部署在公开 GitHub Pages，本项目仅含可公开的学习内容。
- 不预建空目录、不做未来功能的占位结构。

## 目录结构

```
projects/finance/
  index.html                    # 阅读器页面（复用 Foundations reader 交互模式）
  README.md                     # 项目定位、当前状态、如何使用
  roadmap/
    modules/*.md                # 概念模块，唯一内容源，手工编辑
    roadmap-data.json           # 构建产物，页面消费
  scripts/
    build-roadmap-data.mjs      # Markdown → JSON 构建脚本
```

## 内容模型

记录四类内容：

| 内容 | 载体 | 说明 |
| --- | --- | --- |
| 教程本体 | `roadmap/modules/*.md` | 现有指南拆分而来，概念为中心 |
| 术语与速查 | 独立模块 | 靠阅读器全文搜索检索 |
| 学习进度 | `roadmap-data.json` 各模块进度值 | 初始为 0，Overview 汇总 |
| 阅读批注 | 阅读器本地批注机制 | 需长期沉淀的笔记写回模块 Markdown，重新构建后上页 |

**原文件处理（已获用户确认）**：`investment_beginner_guide_zh.md` 拆分进模块后删除，git 历史保留。模块是唯一可信源，避免双份内容漂移。

## 模块划分（概念为中心，约 9 个）

| 模块 | 对应指南章节 |
| --- | --- |
| 投资的本质与前提 | §1–3（投资是什么、财务准备、收益/风险/通胀/复利） |
| 资产类别 | §4–7（资产类别、股票、基金/ETF、债券与现金） |
| 风险与配置 | §8–9（风险承受能力、资产配置与分散） |
| 基金与公司分析 | §10–12（判断基金、基本面、三张报表） |
| 估值 | §13–15（估值指标、DCF、估值案例） |
| 交易与执行 | §16–17（开户下单、定投/一次性/再平衡） |
| 行为与流程 | §18–19（常见错误、可执行流程） |
| 学习计划与工具 | §20–21（12 周计划、记录模板） |
| 术语速查与延伸 | §22–23（术语表、延伸资料） |

Overview 是仪表盘，不算模块。时间线（12 周计划）不作主结构，符合工作流默认。实现时可微调归并粒度。

## 页面与数据流

- 复用 Foundations 阅读器交互模式：全文搜索、折叠章节导航栏、本地批注、模块进度。
- Overview 仪表盘内容：总进度、各模块进度、当前建议下一步（12 周计划当前周 + 下一个未完成模块）、术语速查入口。
- 数据流：`modules/*.md` → `scripts/build-roadmap-data.mjs` → `roadmap/roadmap-data.json` → `index.html` 阅读器加载。
- 页面标识使用 `data-page` 属性（如 `finance-roadmap-reader`），标题与返回链接遵循站点主题页规范（`投资 | NeuroScience x AI`、返回 `../index.html`）。
- 代码复用方式（拷贝适配 Foundations 的 reader 资源，还是抽公共库）由实现计划决定；设计层面只约定交互契约与 Foundations 一致。

## 站点集成

- `projects/manifest.json` 新增条目：`id: "finance"`、title **「投资」**（两字书签，与「基石」「语言」同风格）、`folder: "finance/"`、英文 summary、`status: "active"`。
- `tests/projects-requirements.mjs` 中硬编码的书签标题列表（`["基石", "语言", "记忆与智能体"]`）必须同步加入「投资」；该测试会遍历 manifest 标题校验书签字体子集覆盖，因此需按 `assets/fonts/README.md` 流程重新生成含「投」「资」两字的字体子集。
- 构建脚本对格式不合规的模块文件报错退出（fail loudly），不静默跳过。

## 验证清单

- `node --check` 构建脚本与 reader JS。
- 运行构建生成 `roadmap-data.json`。
- `npm run test:projects`。
- `git diff --check`。

## 增长路径

- 新学概念：改或加 `modules/*.md`，跑构建即上页。
- 未来记录投资实践：届时新增 `.local.md` 私密文件（沿用 `projects/foundations/interview_prep_2026-07-09/09_eval_ledger.local.md` 的 gitignore 先例）或新子目录；本期不建。
- 公司研究、开放问题、来源地图：出现时按仓库规则放 `questions/finance/`、`sources/`。

## 已决事项记录

1. 方案 A（标准 Foundations 阅读器），否决轻量主题页（不满足两个优先级）与周任务卡片 UI（实现重、计划走完后闲置）。
2. 仅学习记录，无隐私风险内容上公开站点。
3. 拆分后删除原指南文件。
4. 书签标题「投资」。
