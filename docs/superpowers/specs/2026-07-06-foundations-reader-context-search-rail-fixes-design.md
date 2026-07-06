# Foundations Reader Context, Search, And Rail Fixes 设计

Date: 2026-07-06
Status: Approved design, awaiting implementation plan

## Summary

本 spec 设计 `projects/foundations/` roadmap reader 的三处小修正：右侧笔记栏严格跟随真实知识卡、搜索支持完整词优先加子串兜底、左侧收起后的横线导航修复 active/hover 状态。目标是修掉当前可观察的交互问题，不扩大成新的 reader 重构。

用户已确认的方向：

- 右侧笔记栏采用严格关联：有对应知识笔记才显示，没有就留空。
- 搜索采用混合匹配：完整词命中优先，子串命中兜底。
- 横线导航采用最小修复：只修 CSS 层叠和第 0 项硬编码 active。
- 不新增视觉 mockup，不重做三栏布局，不改 roadmap 内容本身。

## Problem Diagnosis

### 右侧笔记栏

当前 `getKnowledgeNoteForSection(module, sectionId)` 对普通 section 有 fallback：

- 先查 `sectionId` 是否直接对应知识笔记。
- 如果是“知识笔记”总区块，返回第一条知识笔记。
- 否则返回 `state.activeKnowledgeNoteId` 对应笔记，找不到再返回第一条。

问题是用户阅读“目标 / 当前状态 / 核心知识 / 任务 / 时间线”等普通 section 时，右栏仍会显示上一条或第一条知识笔记。这会让右栏看起来像一块不相关内容，而不是“跟随当前阅读对象的笔记”。

### 搜索

当前 `hasSearchTerm()` 对英文和数字采用整词匹配。这个规则能避免大量误命中，但用户输入 `Trans` 时无法命中 `Transformer`，容易让搜索看起来没有反应。

### 横线导航

当前 `renderSectionRail()` 初始渲染时硬编码第 0 项 active：

```js
button.className = `section-line${index === 0 ? " is-active" : ""}`;
button.setAttribute("aria-current", index === 0 ? "true" : "false");
```

随后 `setActiveSection()` 会重新计算 active 状态。这个“先写默认 active，再由 scrollspy 纠正”的流程没有必要，也容易在未来重构时留下错位状态。

CSS 中 `.section-line:hover` 写在 `.section-line.is-active` 前面，两者优先级相同。active 规则后写会覆盖 hover 规则，所以当前激活的线 hover 时看不出反馈。

## Goals

- 右栏只显示当前知识卡真实关联的结构化笔记和本地学习笔记。
- 普通 section 没有关联知识笔记时，右栏内容区域保持空白。
- 搜索支持部分输入，且完整词命中结果排在子串兜底结果前面。
- 横线导航 active 状态只由 `setActiveSection()` 管理。
- 当前 active 横线 hover 时也有可见反馈。
- 更新测试以防止这些问题回归。

## Non-Goals

- 不给普通 section 新增“阅读提示”“复习提示”或其他右栏占位文案。
- 不新增 `roadmap-data.json` 字段。
- 不修改 `projects/foundations/roadmap/modules/*.md` 内容。
- 不重做 `IntersectionObserver` scrollspy 逻辑。
- 不引入搜索库、embedding search 或 LLM search。
- 不修改 `papers/` reader。
- 不改变本地高亮笔记的 `localStorage` schema。

## Design

### 1. 右栏严格关联

`getKnowledgeNoteForSection(module, sectionId)` 改为只在明确关联时返回 note：

- 如果 `sectionId` 直接等于某个 `knowledgeNotes[].id`，返回该 note。
- 如果 `sectionId` 是“知识笔记”总区块，可以返回当前 `state.activeKnowledgeNoteId` 对应 note；没有 active note 时返回 `null`。
- 其他普通 section 一律返回 `null`。

`renderContextualNotePanel(note)` 必须接受 `null`：

- `note` 存在时，正常渲染 note title、note groups、local annotations。
- `note` 不存在时，右栏 surface 渲染为空字符串。
- 仍可保留右栏外层 label，例如 `学习过程记录 · ${module.title}`，但内容区不显示解释性占位。

`openModule()` 切换模块时不再默认渲染第一条知识笔记。它应先渲染空右栏，再由用户点击知识卡或 scrollspy 进入知识卡 section 后显示对应笔记。

### 2. 搜索完整词优先、子串兜底

搜索保留现有 `searchEntries` 数据源和 `runSearch()` 结构，不新增数据字段。

建议把匹配拆成两个层级：

- exact/whole-word match：英文数字使用词边界；中文和非 ASCII 继续用包含关系。
- partial match：英文数字用 `includes()` 兜底。

`getSearchScore(entry, terms)` 根据匹配层级给分：

- module title 完整词命中分最高。
- section title 完整词命中次高。
- body text 完整词命中再次。
- 子串命中分低于任意同字段完整词命中。

这样 `Transformer` 的完整输入仍然比 `Trans` 更准确；但 `Trans` 不会返回空结果。

### 3. 横线导航最小修复

`renderSectionRail()` 只创建按钮，不设置默认 active：

- class 初始为 `section-line`。
- `aria-current` 初始为 `false`。
- active 状态统一由 `setActiveSection(sectionId)` 设置。

CSS 增加显式 active hover 规则，或把 hover 规则放在 active 规则之后。推荐增加显式规则：

```css
.section-line[aria-current="true"]:hover,
.section-line.is-active:hover {
  width: 36px;
  height: 3px;
  background: var(--reader-section-line-hover);
}
```

邻近线 hover 规则保持不变，不重做导航交互。

## Testing

更新 `tests/foundations-roadmap-requirements.mjs`，增加这些静态约束：

- `getKnowledgeNoteForSection` 不允许对普通 section fallback 到 `state.activeKnowledgeNoteId` 或 `module.knowledgeNotes?.[0]`。
- `renderContextualNotePanel` 需要有 `note` 为空时的空内容处理。
- 搜索代码需要能表达 whole-word 和 partial match 两层匹配。
- `getSearchScore` 需要体现完整词命中优先于子串命中。
- `renderSectionRail()` 不再包含 `index === 0 ? " is-active" : ""`。
- CSS 包含 active hover 显式规则，例如 `.section-line.is-active:hover` 或 `[aria-current="true"]:hover`。

验证命令：

```bash
node --check projects/foundations/roadmap/roadmap-reader.js
node tests/foundations-roadmap-requirements.mjs
node tests/projects-requirements.mjs
node tests/papers-requirements.mjs
node tests/paper-reader-requirements.mjs
git diff --check
```

## Risks And Constraints

- 右栏空白会降低“始终有内容”的视觉密度，但这符合用户确认的严格关联语义。
- 静态测试只能防止明显回归；最终仍需要在浏览器中手动试一次点击知识卡、滚动普通 section、搜索 `Trans`、hover active 横线。
- 搜索仍是轻量本地搜索，不做分词、拼写纠错或语义搜索。
- 这次不重做 scrollspy，因此快速滚动下的 active section 行为只保持现状。

## Acceptance Criteria

- 普通 section 不再让右栏显示上一条或第一条知识笔记。
- 点击知识卡后，右栏显示该知识卡对应的结构化笔记和本地学习笔记。
- 搜索 `Trans` 能命中包含 `Transformer` 的结果。
- 搜索完整词时结果排序不比子串输入更差。
- 当前 active 横线 hover 时可见变长或颜色变化。
- 所有验证命令通过。
