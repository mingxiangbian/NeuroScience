# Paper Representation Design

Date: 2026-07-03
Status: Approved design, not yet implemented

## Summary

Build the next-level page under `papers/` as a reusable project reader pattern. The current target is `papers/brain-memory-for-ai-agents/`, but the design must apply to future `papers/<project-id>/` subprojects as well.

`papers/` remains the 文献阁 project directory. Each `papers/<project-id>/` page becomes that project's Paper Representation reader.

The first implementation should use chunk-based reading, offline embeddings, and semantic search. It should not implement local file sync, AI-generated answers, backend APIs, or a global `/papers/reader/` route.

## Page Hierarchy

```text
papers/
  index.html                         # 文献阁总目录

papers/brain-memory-for-ai-agents/
  index.html                         # 记忆与智能体阅读器实例
  readings/<paper-id>/               # 当前项目的 paper 数据包

papers/shared/
  reader.css                         # 可选：通用阅读器样式
  reader.js                          # 可选：通用阅读器逻辑
```

The reader must not be hard-coded as a one-off page for `brain-memory-for-ai-agents`. Future projects should be able to reuse the same layout and data standard by placing their own `index.html` and `readings/` data under `papers/<project-id>/`.

## Architecture

The reader has four visible areas:

1. Top toolbar
2. Left paper directory
3. Center chunk reading area
4. Right parallel note area

Desktop layout:

```text
top toolbar
left paper directory | center chunk reader | right note panel
```

Narrow/mobile layout defaults to the center reader only. The paper directory and note panel are collapsed behind toolbar controls.

The current `papers/brain-memory-for-ai-agents/index.html` should be upgraded from a paper list into this project reader. The project mark in the top-left toolbar links back to `../`, the 文献阁 directory page.

## Toolbar

The toolbar is glass-like and visually consistent with the existing 水墨 / 宣纸 / 玻璃拟态 style.

Left side:

- Project mark: reuse the existing double-arc mark. It links to `../`.
- Paper directory toggle: use a normal sidebar collapse icon. It should sit near the project mark without overlapping or feeling cramped.

Center:

- Global search field.
- Search covers all chunks available in the current project, across papers.
- Clicking the search field applies a global glass/mist focus state to the page, not only to the center reader.
- Search results appear under the search field, separated by simple horizontal lines rather than a heavy rounded result card.
- If there are no results, show `no found`.

Right side:

- Night mode toggle.
- Right note panel toggle. This also serves as the reading-space expansion control: when the note panel is collapsed, the center reader becomes wider.
- Do not create separate controls for note collapse and reader zoom.

## Left Paper Directory

Expanded state:

- Shows every paper in the current project manifest.
- Each row displays only `shortTitle`.
- No hover details.
- Long short titles truncate on one line.
- The selected paper uses a pressed/selected treatment, such as a slightly inset glass surface or deeper pale ink background.
- Do not use a thin active-line marker in expanded mode.

Collapsed state:

- Shows a compact section index for the currently open paper.
- Each pale horizontal line represents a section.
- Hovering a line makes that line longer, thicker, and darker, and displays the section title.
- Adjacent lines respond only by becoming longer, creating a wave by length change. They do not become thicker or darker.
- The collapsed index does not need to display reading progress.

Papers without chunk data still appear in the directory. Opening one shows real paper metadata and links to the source/original note files, but no fake chunks.

## Center Chunk Reader

The center reader is the primary reading surface.

Top paper information:

- Full paper title
- Authors and year
- Source/original link
- Category, group, relation, or description when available
- Section index below the title, using compact chips or line-based anchors

Chunk rendering:

- Each chunk is a reading unit.
- English source text appears inside a light framed card with a subtle shadow.
- Chinese explanation appears outside the card below it.
- A faint horizontal divider separates the English card from the Chinese explanation area.
- The Chinese explanation is not wrapped in another card.
- If a chunk has no Chinese explanation, leave the area visually quiet and do not show an empty-state message.
- Secondary headings may use minimal icons or colored marks instead of numeric labels. Avoid emoji as the main visual language.

Figures:

- Figures are referenced by chunk data.
- The UI enforces consistent max width, max height, and object fitting so extracted figures do not appear as mismatched screenshots.
- Figure captions are stored separately from the image file.
- The first implementation may keep figure support in the schema without extracting figures immediately.

## Right Parallel Notes

Use parallel notes only. Do not implement notation/superscript annotations in the first version.

Desktop:

- The right note panel is always one continuous glass/paper surface while enabled.
- It does not get recreated per chunk.
- As the reader scrolls to a new chunk, only the note content changes.
- If the current chunk has a note, show it.
- If the current chunk has no note, keep the same blank paper surface with no message.
- The panel must not collapse, jump, or change height when note content changes.
- Note content transitions can use a subtle opacity fade.

Mobile:

- The center reader is shown by default.
- The note panel opens as a bottom drawer from the toolbar note toggle.
- It follows the same continuous blank-surface rule when there is no note.

## Data Package Standard

Each paper with chunk data has one package:

```text
papers/<project-id>/readings/<paper-id>/
  paper.json
  chunks.json
  notes.json
  embeddings.json
  figures/
```

### paper.json

Stores paper metadata and section structure.

```json
{
  "id": "mcclelland-1995-complementary-learning-systems",
  "title": "Why There Are Complementary Learning Systems in the Hippocampus and Neocortex",
  "shortTitle": "Complementary Learning Systems",
  "authors": "McClelland, McNaughton, and O'Reilly",
  "year": 1995,
  "category": "Neuroscience memory theory",
  "sourceFile": "../../pdfs/1995-mcclelland-mcnaughton-oreilly-complementary-learning-systems.pdf",
  "sections": [
    { "id": "sec-1", "title": "Introduction" }
  ]
}
```

### chunks.json

Stores the source text, Chinese explanation, and figure references.

```json
{
  "paperId": "mcclelland-1995-complementary-learning-systems",
  "chunks": [
    {
      "id": "ch-001",
      "sectionId": "sec-1",
      "order": 1,
      "sourceText": "English source passage...",
      "zhExplanation": "中文解释，不做逐字全文翻译。",
      "figures": [],
      "keywords": ["hippocampus", "neocortex", "complementary learning systems"]
    }
  ]
}
```

### notes.json

Stores personal notes separately from source chunks.

```json
{
  "paperId": "mcclelland-1995-complementary-learning-systems",
  "notes": [
    {
      "chunkId": "ch-001",
      "note": ""
    }
  ]
}
```

Notes can be empty. Empty notes render as a blank area in the continuous note panel. Notes are not included in the main semantic search index.

### embeddings.json

Stores offline embedding vectors.

```json
{
  "model": "fixed-model-name",
  "indexedFields": ["sourceText", "zhExplanation"],
  "items": [
    {
      "chunkId": "ch-001",
      "vector": [0.01, -0.02]
    }
  ]
}
```

Embedding input is `sourceText + zhExplanation`. Changing either field requires regenerating embeddings. Changing `notes.json` does not require regenerating embeddings.

## Search And Embedding Strategy

Use offline embeddings in the first implementation.

Codex or a local script prepares `chunks.json` and `embeddings.json`. The browser reads static files and performs semantic ranking locally. This keeps GitHub Pages deployment simple and avoids exposed provider keys.

SurrealDB is not a hard dependency for the first version. The reader should define a replaceable `SearchIndex` boundary:

```text
load readings -> load embeddings -> query text -> ranked chunks -> jump to chunk
```

This allows the first implementation to use a lightweight JavaScript vector search. If SurrealDB WASM becomes useful later, it can replace the internal search index without changing the page layout, chunk schema, or note model.

The first version does not generate AI answers. It returns relevant chunks and lets the user inspect the source text, Chinese explanation, and notes.

## First Content Batch

The reader supports all papers listed for the project, but the first high-quality chunk batch should cover three representative papers:

1. Zhang et al. 2024, `A Survey on the Memory Mechanism of Large Language Model based Agents`
2. McClelland, McNaughton, and O'Reilly 1995, `Why There Are Complementary Learning Systems in the Hippocampus and Neocortex`
3. Yassa and Stark 2011, `Pattern separation in the hippocampus`

Other papers remain visible in the directory. If they do not have a `readings/<paper-id>/` package, the reader shows metadata and source links only.

## Paper Chunk Authoring Standard

Agents adding future papers must follow this standard.

Chunking:

- Use natural paragraphs or complete argument units.
- Do not split by fixed word count.
- Do not break one core claim across arbitrary chunks.
- Split very long paragraphs only when the reasoning still remains coherent.
- Use stable chunk ids such as `ch-001`, `ch-002`.

Chinese explanation:

- Explain the chunk's role in the paper's argument.
- Do not create a full line-by-line translation of the paper.
- Separate author claims, evidence, mechanism implications, and relation to AI agent memory when relevant.
- Do not present the agent's own synthesis as the author's conclusion.
- State uncertainty plainly when the evidence is insufficient.
- Keep the writing concise and useful for reading.

Notes:

- Keep personal learning notes in `notes.json`, not inside `chunks.json`.
- Notes can be blank.
- Notes do not enter the main embedding index.

Figures:

- Store extracted images in `figures/`.
- Reference figures by id from chunks.
- Store captions separately.
- Use consistent display constraints in the UI.

## Testing And Acceptance

Structural checks:

- `papers/` remains the 文献阁 project directory.
- `papers/brain-memory-for-ai-agents/` becomes the project reader.
- Do not add `/papers/reader/`.
- The project mark links back to `../`.
- Future projects can reuse the same reader pattern under `papers/<project-id>/`.

Reader behavior:

- Desktop shows toolbar, paper directory, chunk reader, and continuous note panel.
- Mobile defaults to the center reader only.
- Left directory can collapse into a section-line index.
- Right note panel can collapse, expanding the center reader.
- Search is a global page-level layer.
- Search results are separated by horizontal lines.
- Papers without chunks show real metadata and links only.
- Empty notes render as blank continuous note surface, with no message.

Data checks:

- Chunked papers include `paper.json`, `chunks.json`, `notes.json`, and `embeddings.json`.
- `shortTitle` is available for paper directory display.
- Embeddings index `sourceText + zhExplanation`.
- Notes are not indexed.

Deployment constraints:

- No local sync in the first version.
- No backend API.
- No localhost dependency.
- No OpenAI, Anthropic, or other provider key in the browser.
- No AI-generated answer feature in the first version.

