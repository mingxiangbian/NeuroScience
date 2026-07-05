# Paper Reader Local Annotations 设计

Date: 2026-07-05
Status: Design approved, awaiting spec review

## Summary

为 `papers/brain-memory-for-ai-agents/` 的 Paper Representation 阅读器增加第一版轻量 annotation 能力：用户可以在英文原文 chunk 中高亮文字，并把高亮原文带入右侧平行笔记区进行批注。

本轮采用用户确认的 **方案 1：轻量本地 annotation 层**。它只使用浏览器本地存储，不写回 GitHub，不新增后端，不改 `notes.json` 源文件，也不做导出/导入。目标是让论文精读时可以把具体句子和个人批注绑定起来，同时保持当前阅读器的简洁结构。

## Scope

### In Scope

- 在 `.chunk-source-card` 英文原文区域选中文字。
- 选区附近出现轻量浮层，提供 `Highlight` 和 `Note`。
- `Highlight` 只保存并恢复原文高亮。
- `Note` 保存高亮，并把选中原文作为引用加入当前 chunk 的右侧平行笔记区。
- 右侧仍复用现有 `Parallel note · ch-xxx` 面板，不创建新的全局 annotation 面板。
- 右侧引用原文和用户批注使用不同视觉样式。
- annotation 数据实时保存到 `localStorage`，刷新后保留。
- 删除高亮时提供确认：只删除高亮、连同批注一起删除、取消。
- 更新 `PAPER_IMPORT_STANDARD.md`，说明本地 annotation 是 runtime 个人层，不属于 reading package 源文件。
- 更新 `tests/paper-reader-requirements.mjs` 的结构和行为断言。

### Out of Scope

- 不写回 `notes.json`、`chunks.json` 或 GitHub 仓库。
- 不新增 `/api/`、localhost backend、SurrealDB runtime、AI provider 或登录系统。
- 不做导出、导入、云同步或跨设备同步。
- 不做多色高亮、标签、过滤、全局批注列表。
- 不在中文翻译、中文解释、代码块、表格、公式或图片 caption 中启用高亮。
- 不改变现有 chunk schema，也不改变 reading package 文件结构。

## User Flow

### 1. 创建纯高亮

1. 用户在英文原文卡片中选中一段文字。
2. 阅读器确认选区属于单个 `.chunk-source-card`。
3. 浮层出现在选区附近，提供 `Highlight` 和 `Note`。
4. 用户点击 `Highlight`。
5. 选中文字被淡色高亮。
6. 高亮记录写入 `localStorage`，刷新后恢复。
7. 右侧平行笔记区不新增批注记录。

### 2. 创建带笔记的高亮

1. 用户选中英文原文。
2. 点击 `Note`。
3. 阅读器给原文加高亮。
4. 右侧当前 chunk 的平行笔记区加入一条 annotation item。
5. annotation item 上半部分显示被选中的英文原文引用。
6. annotation item 下半部分是可编辑批注区域。
7. 用户输入批注时实时保存到 `localStorage`。

右侧面板仍只跟随当前 chunk。滚动到其他 chunk 后，右侧显示那个 chunk 的原始 note 和本地 annotations；滚回当前 chunk 时，本地 annotations 重新出现。

### 3. 删除高亮

用户点击已有高亮时，出现轻量操作浮层，至少提供删除入口。

删除前确认提供三种选择：

- `只删除高亮，保留笔记`：原文高亮消失；右侧 annotation item 保留，但标记为无活动高亮。
- `高亮和批注一起删除`：删除该 annotation 记录。
- `取消`：不做改变。

第一版使用项目内轻量 popover 实现删除确认。不要用浏览器原生 `confirm`，因为它不能自然表达三种选择。

## Visual Design

### Source Highlight

高亮应当克制，避免破坏论文阅读：

- 使用淡朱红或淡金色半透明背景。
- 保留原文字色，不使用强黄色。
- hover 时可稍微加深底色，提示可操作。
- 高亮 span 不改变原文行高，不造成文字跳动。

### Selection Toolbar

选区浮层应当小而明确：

- 显示在选区附近。
- 使用现有玻璃拟态语言，但尺寸要轻。
- 只包含 `Highlight` 和 `Note` 两个按钮。
- 点击页面其他区域或选区消失时关闭。
- 在移动端如果选区浮层定位不稳定，可以退化为出现在 chunk 顶部或底部的紧凑操作条。

### Right Note Surface

右侧仍是原来的平行笔记区，不新增新面板。

展示顺序：

1. 原始 `notes.json` 中当前 chunk 的 note。
2. 当前 chunk 的本地 annotation items。

样式区分：

- 原始 chunk note 保持当前笔记样式。
- 高亮原文引用使用更轻的英文引用样式：小一号、淡蓝灰、左侧细线或浅底。
- 用户批注使用正常中文笔记样式，视觉权重高于引用原文。
- 没有批注时保持原来的连续空白效果，不显示“没有笔记”等提示。

## Data Model

数据保存在浏览器 `localStorage`。

Storage key：

```text
paperReader.annotations.v1.brain-memory-for-ai-agents
```

Value shape：

```json
{
  "version": 1,
  "projectId": "brain-memory-for-ai-agents",
  "items": [
    {
      "id": "ann-...",
      "paperId": "zhang-2024-memory-mechanism-llm-agents",
      "chunkId": "ch-004",
      "selectedText": "The agent first converts observations...",
      "matchIndex": 0,
      "mode": "note",
      "note": "这里对应 memory write 阶段。",
      "highlightActive": true,
      "createdAt": "2026-07-05T00:00:00.000Z",
      "updatedAt": "2026-07-05T00:00:00.000Z"
    }
  ]
}
```

字段规则：

- `id` 是稳定本地 id，可以使用时间戳和随机后缀生成。
- `paperId`、`chunkId` 定位当前 reading package 和 chunk。
- `selectedText` 保存用户选中的英文原文。
- `matchIndex` 用于处理同一 chunk 内重复出现的相同选中文本。
- `mode` 可为 `highlight` 或 `note`。
- `note` 只在 `mode: "note"` 时作为可编辑批注内容；纯高亮可为空字符串。
- `highlightActive` 表示右侧批注是否仍然对应正文中的活动高亮。
- `createdAt` 和 `updatedAt` 使用 ISO 字符串。

## Highlight Restoration

刷新页面或切换 paper 后，阅读器根据当前 paper/chunk 恢复高亮。

第一版采用文本匹配，不引入复杂 range 序列化：

1. 渲染 chunk 原文。
2. 读取当前 paper/chunk 的 annotations。
3. 在 `.chunk-source-card` 的文本节点中查找 `selectedText`。
4. 使用 `matchIndex` 定位第几次出现。
5. 用 `<mark class="source-highlight" data-annotation-id="...">` 包裹匹配文本。

限制：

- 如果原文内容更新导致 `selectedText` 找不到，高亮不恢复，但右侧 note 仍保留。
- 如果同一段文字重复很多次，`matchIndex` 只能提供基础稳定性。
- 第一版只支持英文段落文本选区，不支持跨多个复杂 block 的选区；如果选区跨公式、代码、表格或图片 caption，应拒绝创建高亮。

## Architecture

### HTML

`papers/brain-memory-for-ai-agents/index.html` 可保留现有结构，只需要确认 JS 能动态挂载：

- annotation selection toolbar。
- deletion confirmation popover 或简单确认 UI。

不新增静态全局 annotation sidebar。

### CSS

`papers/shared/reader.css` 新增：

- `.annotation-toolbar`
- `.annotation-toolbar button`
- `.source-highlight`
- `.source-highlight.is-note`
- `.note-annotation`
- `.note-annotation-quote`
- `.note-annotation-editor`
- `.note-annotation.is-detached`

这些样式必须匹配现有水墨、宣纸、玻璃拟态风格，避免强黄色和厚重卡片。

### JS

`papers/shared/reader.js` 新增一组本地 annotation 函数，保持边界清楚：

- `getAnnotationStorageKey()`
- `loadAnnotations()`
- `saveAnnotations()`
- `getAnnotationsForChunk(paperId, chunkId)`
- `createAnnotationFromSelection(mode)`
- `renderAnnotationToolbar(selection)`
- `applyHighlights(reading)`
- `renderNoteSurface(surface, note, annotations)`
- `updateAnnotationNote(annotationId, value)`
- `deleteAnnotation(annotationId, behavior)`

现有 `updateNoteSurface()` 可以扩展为传入当前 chunk 的 annotations，但不要改成渲染所有 chunk 的笔记。右侧仍必须只显示当前 chunk。

## Error Handling

- 选区为空、只包含空白、或不在 `.chunk-source-card` 内：不显示浮层。
- 选区跨多个 chunk：拒绝创建 annotation。
- `localStorage` 写入失败：页面不崩溃；可以在 console warning，UI 保持当前阅读。
- 高亮恢复失败：右侧 annotation 保留，并显示为 detached 状态。
- 用户删除高亮但保留笔记：`highlightActive` 改为 `false`，右侧引用保留。
- 用户点击 detached annotation：不尝试滚动到不存在的高亮。

## Testing

更新 `tests/paper-reader-requirements.mjs`，至少断言：

- `reader.js` 使用 `localStorage` 保存 annotations。
- 存储 key 包含 `paperReader.annotations.v1` 和 project id。
- 存在 `createAnnotationFromSelection`、`applyHighlights`、`updateAnnotationNote`、`deleteAnnotation` 等隔离函数。
- 选区逻辑限制在 `.chunk-source-card`。
- 右侧 note surface 继续由 `updateNoteSurface` 或同等函数按 active chunk 更新。
- 不出现全局 annotation sidebar 或所有 chunk notes 一次性渲染。
- 存在 `Highlight` 和 `Note` 两个操作文本。
- CSS 包含 `.source-highlight`、`.annotation-toolbar`、`.note-annotation-quote`、`.note-annotation-editor`。
- 删除行为包含“只删除高亮”和“高亮和批注一起删除”的分支。
- 继续断言无 `/api/`、localhost backend、SurrealDB runtime、AI provider、GitHub token 或生成式回答。

实现后运行：

```bash
node tests/paper-reader-requirements.mjs
node tests/paper-import-standard-requirements.mjs
node tests/papers-requirements.mjs
node tests/homepage-requirements.mjs
git diff --check
```

## Decision Log

- 用户确认使用文字讨论，不使用 visual companion。
- 用户选择浏览器本地保存，不做后端或 GitHub 写回。
- 用户确认第一版不做导出。
- 用户确认高亮有必要，但应保持轻量。
- 用户确认使用方案 1：轻量本地 annotation 层。
- 用户确认右侧仍复用原来的平行笔记区，不创建独立 annotation 系统。
- 用户要求高亮带到右侧后，引用原文的颜色或字体应区别于原始笔记。
- 用户选择删除前确认，并提供保留笔记或一起删除两个路径。
