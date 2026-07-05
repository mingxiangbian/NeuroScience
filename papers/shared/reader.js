const PROJECT_ID = "brain-memory-for-ai-agents";
const SEARCH_DEBOUNCE_MS = 260;
const SEMANTIC_SCORE_THRESHOLD = 0.42;
const ANNOTATION_STORAGE_PREFIX = "paperReader.annotations.v1";

const DOMAIN_DIMS = [
  ["agent", ["agent", "agents", "智能体", "llm", "memory architecture", "prompt", "tool"]],
  ["retrieval", ["retrieval", "retrieve", "retrieves", "检索", "召回", "query", "top-k", "similarity"]],
  ["embedding", ["embedding", "embeddings", "向量", "semantic", "语义", "cosine", "相似度"]],
  ["hippocampus", ["hippocampus", "hippocampal", "海马", "dentate", "dg", "ca3"]],
  ["neocortex", ["neocortex", "neocortical", "cortex", "新皮层", "cortical"]],
  ["separation", ["separation", "separate", "distinct", "区分", "分离", "overlap", "lure", "collision"]],
  ["consolidation", ["consolidation", "replay", "slow", "巩固", "重放", "interleaved"]],
  ["evaluation", ["evaluation", "evaluate", "quality", "criterion", "behavior", "评价", "标准", "noise"]],
  ["formula", ["formula", "math", "equation", "公式", "latex", "score", "delta"]],
  ["code", ["code", "python", "algorithm", "伪代码", "代码", "loop"]],
  ["figure", ["figure", "table", "图", "图表", "表格", "schematic"]],
  ["note", ["note", "notes", "笔记", "解释", "learning", "阅读"]]
];

const state = {
  project: null,
  papers: [],
  currentPaper: null,
  currentReading: null,
  allReadings: new Map(),
  searchItems: [],
  activeChunkId: null,
  observer: null,
  scrollSpyHandler: null,
  searchDebounceTimer: null,
  annotations: { version: 1, projectId: PROJECT_ID, items: [] },
  pendingAnnotation: null,
  annotationToolbar: null,
  annotationDeletePopover: null
};

const els = {
  shell: document.querySelector("#reader-shell"),
  main: document.querySelector("#reader-main"),
  nav: document.querySelector("#paper-nav"),
  sectionLines: document.querySelector("#section-lines"),
  paperHeader: document.querySelector("#paper-header"),
  chunkList: document.querySelector("#chunk-list"),
  noteSurface: document.querySelector("#note-surface"),
  mobileNoteSurface: document.querySelector("#mobile-note-surface"),
  noteLabel: document.querySelector("#note-label"),
  mobileNoteLabel: document.querySelector("#mobile-note-label"),
  searchOverlay: document.querySelector("#search-overlay"),
  searchInput: document.querySelector("#global-search"),
  searchResults: document.querySelector("#search-results"),
  toggleLeftControls: document.querySelectorAll("[data-toggle-left]"),
  toggleNote: document.querySelector("#toggle-note"),
  toggleTheme: document.querySelector("#toggle-theme")
};

function resolveUrl(path) {
  return new URL(path, window.location.href);
}

async function fetchJson(path, { optional = false } = {}) {
  const response = await fetch(resolveUrl(path));
  if (!response.ok) {
    if (optional) return null;
    throw new Error(`Unable to load ${path}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeRegExp(value) {
  return String(value ?? "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderMultilineText(value) {
  return escapeHtml(value).replace(/\n/g, "<br>");
}

function getAnnotationStorageKey() {
  return `${ANNOTATION_STORAGE_PREFIX}.${PROJECT_ID}`;
}

function createEmptyAnnotationStore() {
  return {
    version: 1,
    projectId: PROJECT_ID,
    items: []
  };
}

function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(getAnnotationStorageKey());
    if (!raw) return createEmptyAnnotationStore();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.items)) return createEmptyAnnotationStore();
    return {
      version: 1,
      projectId: PROJECT_ID,
      items: parsed.items.filter((item) => item && item.projectId === PROJECT_ID)
    };
  } catch (error) {
    console.warn("Unable to load local annotations", error);
    return createEmptyAnnotationStore();
  }
}

function saveAnnotations(annotations = state.annotations) {
  try {
    window.localStorage.setItem(getAnnotationStorageKey(), JSON.stringify(annotations));
  } catch (error) {
    console.warn("Unable to save local annotations", error);
  }
}

function getAnnotationsForChunk(paperId, chunkId) {
  return state.annotations.items.filter((item) => item.paperId === paperId && item.chunkId === chunkId);
}

function getSourceParagraphFromNode(node) {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
  return element?.closest?.(".source-paragraph") ?? null;
}

function countTextOccurrences(text, needle) {
  if (!needle) return 0;
  let count = 0;
  let index = text.indexOf(needle);
  while (index !== -1) {
    count += 1;
    index = text.indexOf(needle, index + needle.length);
  }
  return count;
}

function getSelectionAnnotationContext() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const selectedText = selection.toString().trim();
  if (selectedText.length < 2) return null;

  const startParagraph = getSourceParagraphFromNode(range.startContainer);
  const endParagraph = getSourceParagraphFromNode(range.endContainer);
  if (!startParagraph || startParagraph !== endParagraph) return null;

  const sourceCard = startParagraph.closest(".chunk-source-card");
  const chunk = startParagraph.closest(".chunk");
  if (!sourceCard || !chunk || !sourceCard.contains(startParagraph)) return null;

  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(sourceCard);
  beforeRange.setEnd(range.startContainer, range.startOffset);
  const matchIndex = countTextOccurrences(beforeRange.toString(), selectedText);
  const rect = range.getBoundingClientRect();

  return {
    selectedText,
    matchIndex,
    paperId: state.currentPaper?.id,
    chunkId: chunk.dataset.chunkId,
    rect
  };
}

function normalizeVector(vector) {
  const magnitude = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0)) || 1;
  return vector.map((value) => value / magnitude);
}

function embedQuery(text) {
  const lower = String(text ?? "").toLowerCase();
  const vector = DOMAIN_DIMS.map(([, terms], index) => {
    let score = 0;
    for (const term of terms) {
      const pattern = term.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const matches = lower.match(new RegExp(pattern, "g"));
      if (matches) score += matches.length;
    }
    score += ((lower.length + index * 17) % 11) / 100;
    return score;
  });
  return normalizeVector(vector);
}

function cosineSimilarity(left, right) {
  const length = Math.min(left.length, right.length);
  let dot = 0;
  let leftMagnitude = 0;
  let rightMagnitude = 0;
  for (let index = 0; index < length; index += 1) {
    dot += left[index] * right[index];
    leftMagnitude += left[index] * left[index];
    rightMagnitude += right[index] * right[index];
  }
  return dot / ((Math.sqrt(leftMagnitude) || 1) * (Math.sqrt(rightMagnitude) || 1));
}

function getPaperById(paperId) {
  return state.papers.find((paper) => paper.id === paperId);
}

function getSectionTitle(reading, sectionId) {
  const section = reading?.paperData.sections.find((entry) => entry.id === sectionId);
  return section?.titleZh ?? section?.title ?? "Section";
}

async function loadReadingPackage(paper) {
  if (state.allReadings.has(paper.id)) return state.allReadings.get(paper.id);
  if (paper.hasReading !== true) {
    state.allReadings.set(paper.id, null);
    return null;
  }
  try {
    const [paperData, chunksData, notesData, embeddingsData, figuresData] = await Promise.all([
      fetchJson(`readings/${paper.id}/paper.json`),
      fetchJson(`readings/${paper.id}/chunks.json`),
      fetchJson(`readings/${paper.id}/notes.json`),
      fetchJson(`readings/${paper.id}/embeddings.json`),
      fetchJson(`readings/${paper.id}/figures.json`, { optional: true })
    ]);
    const reading = {
      paper,
      paperData,
      assetBasePath: `readings/${paper.id}/`,
      chunks: chunksData.chunks ?? [],
      notes: new Map((notesData.notes ?? []).map((note) => [note.chunkId, note.note ?? ""])),
      embeddings: embeddingsData.items ?? [],
      figures: new Map((figuresData?.figures ?? []).map((figure) => [figure.id, figure]))
    };
    state.allReadings.set(paper.id, reading);
    return reading;
  } catch (error) {
    state.allReadings.set(paper.id, null);
    return null;
  }
}

async function loadAllSearchItems() {
  const items = [];
  for (const paper of state.papers) {
    const reading = await loadReadingPackage(paper);
    if (!reading) continue;
    const chunksById = new Map(reading.chunks.map((chunk) => [chunk.id, chunk]));
    for (const item of reading.embeddings) {
      const chunk = chunksById.get(item.chunkId);
      if (!chunk) continue;
      items.push({
        paper,
        reading,
        chunk,
        vector: item.vector,
        searchText: `${chunk.sourceText ?? ""}\n${chunk.zhTranslation ?? ""}\n${chunk.zhExplanation ?? ""}`
      });
    }
  }
  state.searchItems = items;
}

function renderPaperNav() {
  els.nav.innerHTML = "";
  for (const paper of state.papers) {
    const button = document.createElement("button");
    button.className = "paper-nav-item";
    button.type = "button";
    button.dataset.paperId = paper.id;
    button.setAttribute("aria-current", state.currentPaper?.id === paper.id ? "true" : "false");
    button.innerHTML = `<span>${escapeHtml(paper.shortTitle ?? paper.title)}</span>`;
    button.addEventListener("click", () => openPaper(paper.id));
    els.nav.append(button);
  }
}

function renderSectionRail(reading) {
  els.sectionLines.innerHTML = "";
  const sections = reading?.paperData.sections ?? [];
  sections.forEach((section) => {
    const button = document.createElement("button");
    button.className = "section-line";
    button.type = "button";
    button.dataset.sectionId = section.id;
    button.innerHTML = `<span class="section-tooltip">${escapeHtml(section.title)}</span>`;
    button.addEventListener("click", () => {
      const firstChunk = document.querySelector(`.chunk[data-section-id="${CSS.escape(section.id)}"]`);
      firstChunk?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    els.sectionLines.append(button);
  });
}

function renderPaperLinks(paperData) {
  return [
    paperData.sourceFile || state.currentPaper.localFile
      ? `<a href="${escapeHtml(paperData.sourceFile ?? state.currentPaper.localFile)}">原文</a>`
      : "",
    paperData.noteFile || state.currentPaper.noteFile
      ? `<a href="${escapeHtml(paperData.noteFile ?? state.currentPaper.noteFile)}">中文精读</a>`
      : "",
    paperData.source || state.currentPaper.source
      ? `<a href="${escapeHtml(paperData.source ?? state.currentPaper.source)}">来源</a>`
      : ""
  ].filter(Boolean).join("");
}

function renderPaperHeader(reading) {
  const paperData = reading?.paperData ?? state.currentPaper;
  const sections = (paperData.sections ?? [])
    .map((section) => `<button class="section-chip" type="button" data-section-id="${escapeHtml(section.id)}">${escapeHtml(section.titleZh ?? section.title)}</button>`)
    .join("");
  const category = paperData.categoryZh ?? paperData.category ?? "Paper";
  const relation = paperData.relationZh ?? paperData.relation;
  const description = paperData.descriptionZh ?? paperData.description;
  const readingFocus = Array.isArray(paperData.readingFocus)
    ? paperData.readingFocus.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "";

  els.paperHeader.innerHTML = `
    <p class="paper-kicker">${escapeHtml(category)}</p>
    <h1 class="paper-title">${escapeHtml(paperData.title ?? state.currentPaper.title)}</h1>
    <p class="paper-meta">${escapeHtml([paperData.authors, paperData.year].filter(Boolean).join(" · "))}</p>
    ${relation ? `<p class="paper-meta">${escapeHtml(relation)}</p>` : ""}
    ${description ? `<p class="paper-meta">${escapeHtml(description)}</p>` : ""}
    ${readingFocus ? `<ul class="reading-focus">${readingFocus}</ul>` : ""}
    <div class="paper-actions"></div>
    <div class="section-chips">${sections}</div>
  `;

  els.paperHeader.querySelectorAll(".section-chip").forEach((button) => {
    button.addEventListener("click", () => {
      const firstChunk = document.querySelector(`.chunk[data-section-id="${CSS.escape(button.dataset.sectionId)}"]`);
      firstChunk?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderNoChunkPaper() {
  renderPaperHeader(null);
  const actions = els.paperHeader.querySelector(".paper-actions");
  if (actions) {
    actions.classList.add("is-fallback-only");
    actions.innerHTML = renderPaperLinks(state.currentPaper);
  }
  els.chunkList.innerHTML = `
    <article class="status-panel">
      <h2>${escapeHtml(state.currentPaper.shortTitle ?? state.currentPaper.title)}</h2>
      <p>这篇论文已经登记，但还没有整理成 chunk 阅读包。</p>
      <p>当前页面只显示真实论文信息和已有链接，不生成假正文。</p>
    </article>
  `;
  renderSectionRail(null);
  updateNoteSurface("", "");
}

function renderBlock(block, reading) {
  if (!block || block.type === "paragraph") {
    return `<p class="source-paragraph">${escapeHtml(block?.text ?? "")}</p>`;
  }
  if (block.type === "math") return renderMathBlock(block);
  if (block.type === "code") return renderCodeBlock(block);
  if (block.type === "table") return renderTableBlock(block);
  if (block.type === "figure") return renderFigureBlock(block, reading);
  return "";
}

function renderMathBlock(block) {
  const latex = String(block.latex ?? "").trim();
  return `
    <div class="math-block">
      ${block.label ? `<span class="math-label">${escapeHtml(block.label)}</span>` : ""}
      <div class="math-render" data-latex="${escapeHtml(latex)}">${renderLatex(latex)}</div>
    </div>
  `;
}

function renderLatex(latex) {
  if (!latex) return "";
  const renderToString = window.katex?.renderToString;
  if (typeof renderToString !== "function") {
    return `<code class="math-fallback">${escapeHtml(latex)}</code>`;
  }
  try {
    return renderToString(latex, {
      displayMode: true,
      throwOnError: false,
      strict: "ignore",
      trust: false
    });
  } catch {
    return `<code class="math-fallback">${escapeHtml(latex)}</code>`;
  }
}

function renderCodeBlock(block) {
  return `
    <figure class="code-block">
      ${block.caption ? `<figcaption class="code-caption">${escapeHtml(block.caption)}</figcaption>` : ""}
      <pre><code data-language="${escapeHtml(block.language ?? "text")}">${escapeHtml(block.code ?? "")}</code></pre>
    </figure>
  `;
}

function renderTableBlock(block) {
  const headers = (block.columns ?? []).map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const rows = (block.rows ?? [])
    .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`)
    .join("");
  return `
    <figure class="table-block">
      ${block.caption ? `<figcaption class="table-caption">${escapeHtml(block.caption)}</figcaption>` : ""}
      <table>
        <thead><tr>${headers}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </figure>
  `;
}

function renderFigureBlock(block, reading) {
  const figure = reading.figures.get(block.id) ?? block;
  return renderFigure(figure, block.relation, reading);
}

function resolveReadingAssetPath(path, reading) {
  const value = String(path ?? "");
  if (/^(?:[a-z]+:|\/)/i.test(value)) return value;
  return `${reading?.assetBasePath ?? ""}${value}`;
}

function renderFigure(figure, relation = "supporting", reading = null) {
  if (!figure?.file) return "";
  return `
    <figure class="figure-frame" data-relation="${escapeHtml(relation)}">
      <img src="${escapeHtml(resolveReadingAssetPath(figure.file, reading))}" alt="${escapeHtml(figure.label ?? "Figure")}">
      <figcaption class="figure-caption">${escapeHtml(figure.caption ?? "")}</figcaption>
    </figure>
  `;
}

function renderChunk(chunk, reading) {
  const sectionTitle = getSectionTitle(reading, chunk.sectionId);
  const chunkTitle = chunk.title ? `<h2 class="chunk-title">${escapeHtml(chunk.title)}</h2>` : "";
  const blocks = chunk.blocks?.length
    ? chunk.blocks.map((block) => renderBlock(block, reading)).join("")
    : `<p class="source-paragraph">${escapeHtml(chunk.sourceText)}</p>`;
  const inlineFigureIds = new Set((chunk.blocks ?? [])
    .filter((block) => block.type === "figure")
    .map((block) => block.id));
  const supportingFigures = (chunk.figureRefs ?? [])
    .filter((ref) => !inlineFigureIds.has(ref.id))
    .map((ref) => renderFigure(reading.figures.get(ref.id), ref.relation, reading))
    .join("");
  return `
    <article class="chunk" id="${escapeHtml(chunk.id)}" data-chunk-id="${escapeHtml(chunk.id)}" data-section-id="${escapeHtml(chunk.sectionId)}">
      ${chunkTitle}
      <p class="chunk-heading">${escapeHtml(sectionTitle)} · ${escapeHtml(chunk.id)}</p>
      <div class="chunk-source-card">${blocks}${supportingFigures}</div>
      <div class="chunk-divider"></div>
      <div class="chunk-translation">${chunk.zhTranslation ? `<p>${escapeHtml(chunk.zhTranslation)}</p>` : ""}</div>
      <div class="chunk-explanation chunk-explanation-note">${chunk.zhExplanation ? `<p>${escapeHtml(chunk.zhExplanation)}</p>` : ""}</div>
    </article>
  `;
}

function refreshNoteSurfaceForChunk(chunkId = state.activeChunkId) {
  if (!chunkId || !state.currentReading) return;
  updateNoteSurface(chunkId, state.currentReading.notes.get(chunkId) ?? "");
}

function createAnnotationId() {
  return `ann-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createAnnotationFromSelection(mode) {
  const context = state.pendingAnnotation;
  if (!context?.paperId || !context?.chunkId) return;
  const now = new Date().toISOString();
  state.annotations.items.push({
    id: createAnnotationId(),
    projectId: PROJECT_ID,
    paperId: context.paperId,
    chunkId: context.chunkId,
    selectedText: context.selectedText,
    matchIndex: context.matchIndex,
    mode,
    note: "",
    highlightActive: true,
    createdAt: now,
    updatedAt: now
  });
  saveAnnotations();
  state.pendingAnnotation = null;
  window.getSelection()?.removeAllRanges();
  hideAnnotationToolbar();
  applyHighlights(state.currentReading);
  refreshNoteSurfaceForChunk(context.chunkId);
}

function updateAnnotationNote(annotationId, value) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  annotation.note = value;
  annotation.updatedAt = new Date().toISOString();
  saveAnnotations();
  document.querySelectorAll(`.note-annotation-editor[data-annotation-note-id="${CSS.escape(annotationId)}"]`)
    .forEach((editor) => {
      if (editor.value !== value) editor.value = value;
    });
}

function deleteAnnotation(annotationId, behavior) {
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  const chunkId = annotation.chunkId;
  if (behavior === "highlight-only" && annotation.mode === "note") {
    annotation.highlightActive = false;
    annotation.updatedAt = new Date().toISOString();
  } else {
    state.annotations.items = state.annotations.items.filter((item) => item.id !== annotationId);
  }
  saveAnnotations();
  hideAnnotationDeletePopover();
  applyHighlights(state.currentReading);
  refreshNoteSurfaceForChunk(chunkId);
}

function clearHighlights() {
  document.querySelectorAll(".source-highlight").forEach((mark) => {
    mark.replaceWith(document.createTextNode(mark.textContent ?? ""));
  });
}

function getSourceTextNodes(chunkElement) {
  const nodes = [];
  chunkElement.querySelectorAll(".source-paragraph").forEach((paragraph) => {
    const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      nodes.push(node);
      node = walker.nextNode();
    }
  });
  return nodes;
}

function findTextRangeInNodes(nodes, selectedText, matchIndex) {
  const fullText = nodes.map((node) => node.textContent ?? "").join("");
  let startIndex = -1;
  let searchFrom = 0;
  for (let count = 0; count <= matchIndex; count += 1) {
    startIndex = fullText.indexOf(selectedText, searchFrom);
    if (startIndex === -1) return null;
    searchFrom = startIndex + selectedText.length;
  }

  const endIndex = startIndex + selectedText.length;
  let offset = 0;
  let startNode = null;
  let endNode = null;
  let startOffset = 0;
  let endOffset = 0;

  for (const node of nodes) {
    const text = node.textContent ?? "";
    const nextOffset = offset + text.length;
    if (!startNode && startIndex >= offset && startIndex <= nextOffset) {
      startNode = node;
      startOffset = startIndex - offset;
    }
    if (!endNode && endIndex >= offset && endIndex <= nextOffset) {
      endNode = node;
      endOffset = endIndex - offset;
      break;
    }
    offset = nextOffset;
  }

  if (!startNode || !endNode) return null;
  return { startNode, startOffset, endNode, endOffset };
}

function applyHighlight(annotation) {
  if (!annotation.highlightActive) return;
  const chunkElement = document.querySelector(`.chunk[data-chunk-id="${CSS.escape(annotation.chunkId)}"]`);
  if (!chunkElement) return;
  const rangeParts = findTextRangeInNodes(
    getSourceTextNodes(chunkElement),
    annotation.selectedText,
    annotation.matchIndex ?? 0
  );
  if (!rangeParts) return;

  try {
    const range = document.createRange();
    range.setStart(rangeParts.startNode, rangeParts.startOffset);
    range.setEnd(rangeParts.endNode, rangeParts.endOffset);
    const mark = document.createElement("mark");
    mark.className = `source-highlight${annotation.mode === "note" ? " is-note" : ""}`;
    mark.dataset.annotationId = annotation.id;
    range.surroundContents(mark);
  } catch (error) {
    console.warn("Unable to restore local highlight", error);
  }
}

function applyHighlights(reading) {
  clearHighlights();
  if (!reading || !state.currentPaper) return;
  state.annotations.items
    .filter((item) => item.paperId === state.currentPaper.id)
    .forEach((annotation) => applyHighlight(annotation));
}

function renderChunks(reading) {
  els.chunkList.innerHTML = reading.chunks.map((chunk) => renderChunk(chunk, reading)).join("");
  applyHighlights(reading);
  observeChunks(reading);
}

function renderNoteSurface(surface, note, annotations = []) {
  const baseNote = note ? `<p>${renderMultilineText(note)}</p>` : "";
  const annotationMarkup = annotations
    .filter((annotation) => annotation.mode === "note")
    .map((annotation) => `
      <article class="note-annotation${annotation.highlightActive ? "" : " is-detached"}" data-note-annotation-id="${escapeHtml(annotation.id)}">
        <blockquote class="note-annotation-quote">${escapeHtml(annotation.selectedText)}</blockquote>
        <textarea class="note-annotation-editor" data-annotation-note-id="${escapeHtml(annotation.id)}" placeholder="写批注...">${escapeHtml(annotation.note ?? "")}</textarea>
      </article>
    `)
    .join("");
  surface.innerHTML = `${baseNote}${annotationMarkup}`;
  surface.classList.remove("is-changing");
  surface.querySelectorAll(".note-annotation-editor").forEach((editor) => {
    editor.addEventListener("input", () => updateAnnotationNote(editor.dataset.annotationNoteId, editor.value));
  });
}

function updateNoteSurface(chunkId, note) {
  const label = chunkId ? `Parallel note · ${chunkId}` : "Parallel note";
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  const annotations = state.currentPaper && chunkId
    ? getAnnotationsForChunk(state.currentPaper.id, chunkId)
    : [];
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.classList.add("is-changing");
    window.setTimeout(() => renderNoteSurface(surface, note, annotations), 90);
  }
}

function updateActiveSectionRail(sectionId) {
  for (const line of els.sectionLines.children) {
    line.classList.toggle("is-active", line.dataset.sectionId === sectionId);
  }
}

function setActiveChunk(reading, chunkId) {
  if (!chunkId || state.activeChunkId === chunkId) return;
  state.activeChunkId = chunkId;
  const chunk = reading.chunks.find((entry) => entry.id === chunkId);
  const note = reading.notes.get(chunkId) ?? "";
  updateNoteSurface(chunkId, note);
  updateActiveSectionRail(chunk?.sectionId);
}

function getActiveChunkByViewport() {
  const chunks = [...document.querySelectorAll(".chunk")];
  const viewportRect = els.main.getBoundingClientRect();
  const viewportCenter = viewportRect.top + viewportRect.height / 2;
  let best = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  let fallback = null;

  for (const chunk of chunks) {
    const rect = chunk.getBoundingClientRect();
    if (rect.top <= viewportCenter) fallback = chunk;
    if (rect.bottom < viewportRect.top || rect.top > viewportRect.bottom) continue;

    const distance = rect.top <= viewportCenter && rect.bottom >= viewportCenter
      ? 0
      : Math.min(Math.abs(rect.top - viewportCenter), Math.abs(rect.bottom - viewportCenter));

    if (distance < bestDistance) {
      best = chunk;
      bestDistance = distance;
    }
  }

  return best?.dataset.chunkId ?? fallback?.dataset.chunkId ?? chunks[0]?.dataset.chunkId;
}

function updateActiveChunkFromViewport(reading) {
  const chunkId = getActiveChunkByViewport();
  if (chunkId) setActiveChunk(reading, chunkId);
}

function observeChunks(reading) {
  state.observer?.disconnect();
  if (state.scrollSpyHandler) {
    window.removeEventListener("scroll", state.scrollSpyHandler);
    window.removeEventListener("resize", state.scrollSpyHandler);
    els.main.removeEventListener("scroll", state.scrollSpyHandler);
  }
  state.scrollSpyHandler = () => updateActiveChunkFromViewport(reading);
  state.observer = new IntersectionObserver(() => {
    updateActiveChunkFromViewport(reading);
  }, {
    root: els.main,
    rootMargin: "-10% 0px -10% 0px",
    threshold: [0, 0.2, 0.5, 0.8]
  });
  document.querySelectorAll(".chunk").forEach((chunk) => state.observer.observe(chunk));
  els.main.addEventListener("scroll", state.scrollSpyHandler, { passive: true });
  window.addEventListener("resize", state.scrollSpyHandler);
  updateActiveChunkFromViewport(reading);
}

async function openPaper(paperId) {
  const paper = getPaperById(paperId);
  if (!paper) return;
  state.currentPaper = paper;
  state.activeChunkId = null;
  renderPaperNav();
  const reading = await loadReadingPackage(paper);
  state.currentReading = reading;
  const url = new URL(window.location.href);
  url.searchParams.set("paper", paper.id);
  window.history.replaceState({}, "", url);
  if (!reading) {
    renderNoChunkPaper();
    return;
  }
  renderPaperHeader(reading);
  renderSectionRail(reading);
  renderChunks(reading);
}

function openSearchModal() {
  els.shell.classList.add("is-searching");
}

function closeSearchModal() {
  window.clearTimeout(state.searchDebounceTimer);
  setSearchLoading(false);
  els.searchResults.hidden = true;
  els.shell.classList.remove("is-searching");
}

function setSearchLoading(loading) {
  els.shell.classList.toggle("is-search-loading", loading);
}

function scheduleSearch(query) {
  window.clearTimeout(state.searchDebounceTimer);
  const trimmed = query.trim();
  if (!trimmed) {
    setSearchLoading(false);
    runSearch("");
    return;
  }
  setSearchLoading(true);
  state.searchDebounceTimer = window.setTimeout(() => {
    runSearch(trimmed);
    setSearchLoading(false);
  }, SEARCH_DEBOUNCE_MS);
}

function getSearchTerms(query) {
  return query.trim().split(/\s+/).filter(Boolean);
}

function getSearchSnippet(item, query) {
  const fields = [item.chunk.zhTranslation, item.chunk.zhExplanation, item.chunk.sourceText].filter(Boolean);
  const terms = getSearchTerms(query);
  for (const field of fields) {
    const lowerField = field.toLowerCase();
    const matchedTerm = terms.find((term) => lowerField.includes(term.toLowerCase()));
    if (!matchedTerm) continue;
    const index = lowerField.indexOf(matchedTerm.toLowerCase());
    const start = Math.max(0, index - 60);
    const end = Math.min(field.length, index + matchedTerm.length + 120);
    return `${start > 0 ? "..." : ""}${field.slice(start, end)}${end < field.length ? "..." : ""}`;
  }
  return fields[0]?.slice(0, 180) ?? "";
}

function highlightSearchTerms(text, query) {
  const terms = getSearchTerms(query).map(escapeRegExp);
  if (terms.length === 0) return escapeHtml(text);
  const pattern = new RegExp(`(${terms.join("|")})`, "gi");
  const exactPattern = new RegExp(`^(${terms.join("|")})$`, "i");
  return String(text ?? "")
    .split(pattern)
    .map((part) => exactPattern.test(part)
      ? `<mark class="result-highlight">${escapeHtml(part)}</mark>`
      : escapeHtml(part))
    .join("");
}

function getLexicalScore(item, query) {
  const terms = getSearchTerms(query).map((term) => term.toLowerCase());
  const sectionTitle = getSectionTitle(item.reading, item.chunk.sectionId);
  const weightedFields = [
    [item.paper.title, 5],
    [item.paper.shortTitle, 5],
    [sectionTitle, 4],
    [item.chunk.sourceText, 2],
    [item.chunk.zhTranslation, 2],
    [item.chunk.zhExplanation, 2],
    [(item.chunk.keywords ?? []).join(" "), 3]
  ];
  let score = 0;
  for (const [field, weight] of weightedFields) {
    const lower = String(field ?? "").toLowerCase();
    for (const term of terms) {
      if (term && lower.includes(term)) score += weight;
    }
  }
  return score;
}

function getSemanticScore(item, queryVector) {
  return cosineSimilarity(queryVector, item.vector);
}

function hasSemanticSignal(query) {
  const lower = query.toLowerCase();
  return DOMAIN_DIMS.some(([, terms]) => terms.some((term) => lower.includes(term.toLowerCase())));
}

function getHybridSearchResults(query) {
  const queryVector = embedQuery(query);
  const allowSemanticOnly = hasSemanticSignal(query);
  return state.searchItems
    .map((item) => {
      const lexicalScore = getLexicalScore(item, query);
      const semanticScore = getSemanticScore(item, queryVector);
      const score = lexicalScore * 10 + semanticScore;
      return {
        ...item,
        lexicalScore,
        semanticScore,
        score,
        resultType: item.paper.id === state.currentPaper?.id ? "chunk" : "paper"
      };
    })
    .filter(({ lexicalScore, semanticScore }) => {
      const passesRelevanceThreshold = lexicalScore > 0 || semanticScore >= SEMANTIC_SCORE_THRESHOLD;
      return passesRelevanceThreshold && (lexicalScore > 0 || allowSemanticOnly);
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, 8);
}

function renderResultIcon(type) {
  if (type === "paper") {
    return `
      <svg class="result-icon result-icon--paper" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M7 3h7l4 4v14H7V3Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" />
        <path d="M14 3v5h4M9.5 12h5M9.5 16h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
      </svg>
    `;
  }
  return `
    <svg class="result-icon result-icon--chunk" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5 6h14M5 11h14M5 16h9" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
    </svg>
  `;
}

function runSearch(query) {
  const trimmed = query.trim();
  if (!trimmed) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
    return;
  }
  const results = getHybridSearchResults(trimmed);

  els.searchResults.hidden = false;
  if (results.length === 0) {
    els.searchResults.innerHTML = `<div class="result-empty">No results found</div>`;
    return;
  }
  els.searchResults.innerHTML = results.map((item) => {
    const current = item.paper.id === state.currentPaper?.id;
    const title = current ? getSectionTitle(item.reading, item.chunk.sectionId) : item.paper.shortTitle;
    const snippet = getSearchSnippet(item, trimmed);
    return `
      <button class="result-item" type="button" data-paper-id="${escapeHtml(item.paper.id)}" data-chunk-id="${escapeHtml(item.chunk.id)}">
        ${renderResultIcon(item.resultType)}
        <span class="result-copy">
          <span class="result-title">${highlightSearchTerms(title, trimmed)}</span>
          <span class="result-snippet">${highlightSearchTerms(snippet, trimmed)}</span>
        </span>
      </button>
    `;
  }).join("");
  els.searchResults.querySelectorAll(".result-item[data-paper-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await openPaper(button.dataset.paperId);
      document.getElementById(button.dataset.chunkId)?.scrollIntoView({ behavior: "smooth", block: "start" });
      closeSearchModal();
    });
  });
}

function ensureAnnotationToolbar() {
  if (state.annotationToolbar) return state.annotationToolbar;
  const toolbar = document.createElement("div");
  toolbar.className = "annotation-toolbar";
  toolbar.hidden = true;
  toolbar.innerHTML = `
    <button type="button" data-annotation-action="highlight">Highlight</button>
    <button type="button" data-annotation-action="note">Note</button>
  `;
  toolbar.addEventListener("click", (event) => {
    const button = event.target.closest("[data-annotation-action]");
    if (!button) return;
    createAnnotationFromSelection(button.dataset.annotationAction);
  });
  document.body.append(toolbar);
  state.annotationToolbar = toolbar;
  return toolbar;
}

function hideAnnotationToolbar() {
  if (state.annotationToolbar) state.annotationToolbar.hidden = true;
}

function renderAnnotationToolbar() {
  const context = getSelectionAnnotationContext();
  if (!context) {
    state.pendingAnnotation = null;
    hideAnnotationToolbar();
    return;
  }
  state.pendingAnnotation = context;
  const toolbar = ensureAnnotationToolbar();
  toolbar.hidden = false;
  toolbar.style.left = `${Math.min(window.innerWidth - 170, Math.max(12, context.rect.left + context.rect.width / 2 - 76))}px`;
  toolbar.style.top = `${Math.max(12, context.rect.top - 48)}px`;
}

function ensureAnnotationDeletePopover() {
  if (state.annotationDeletePopover) return state.annotationDeletePopover;
  const popover = document.createElement("div");
  popover.className = "annotation-delete-popover";
  popover.hidden = true;
  popover.innerHTML = `
    <button type="button" data-delete-behavior="highlight-only">只删除高亮，保留笔记</button>
    <button type="button" data-delete-behavior="all">高亮和批注一起删除</button>
    <button type="button" data-delete-behavior="cancel">取消</button>
  `;
  popover.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-behavior]");
    if (!button) return;
    const annotationId = popover.dataset.annotationId;
    if (button.dataset.deleteBehavior !== "cancel") {
      deleteAnnotation(annotationId, button.dataset.deleteBehavior);
    }
    hideAnnotationDeletePopover();
  });
  document.body.append(popover);
  state.annotationDeletePopover = popover;
  return popover;
}

function hideAnnotationDeletePopover() {
  if (state.annotationDeletePopover) state.annotationDeletePopover.hidden = true;
}

function showAnnotationDeletePopover(annotationId, rect) {
  const popover = ensureAnnotationDeletePopover();
  popover.dataset.annotationId = annotationId;
  popover.hidden = false;
  popover.style.left = `${Math.min(window.innerWidth - 250, Math.max(12, rect.left))}px`;
  popover.style.top = `${Math.min(window.innerHeight - 130, Math.max(12, rect.bottom + 8))}px`;
}

function bindAnnotationControls() {
  els.chunkList.addEventListener("mouseup", () => window.setTimeout(renderAnnotationToolbar, 0));
  els.chunkList.addEventListener("keyup", () => window.setTimeout(renderAnnotationToolbar, 0));
  els.chunkList.addEventListener("touchend", () => window.setTimeout(renderAnnotationToolbar, 0));
  els.chunkList.addEventListener("click", (event) => {
    const highlight = event.target.closest(".source-highlight");
    if (!highlight) return;
    showAnnotationDeletePopover(highlight.dataset.annotationId, highlight.getBoundingClientRect());
  });
  document.addEventListener("mousedown", (event) => {
    if (state.annotationToolbar?.contains(event.target) || state.annotationDeletePopover?.contains(event.target)) return;
    if (!event.target.closest(".source-highlight")) hideAnnotationDeletePopover();
    if (!event.target.closest(".chunk-source-card")) hideAnnotationToolbar();
  });
}

function bindControls() {
  syncResponsiveState();
  const toggleLeftPanel = () => {
    if (window.matchMedia("(max-width: 860px)").matches) {
      els.shell.classList.toggle("is-mobile-left-open");
      els.shell.classList.remove("is-left-collapsed");
      return;
    }
    els.shell.classList.toggle("is-left-collapsed");
  };
  els.toggleLeftControls.forEach((control) => control.addEventListener("click", toggleLeftPanel));
  els.toggleNote.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 860px)").matches) {
      els.shell.classList.toggle("is-mobile-note-open");
      return;
    }
    els.shell.classList.toggle("is-note-collapsed");
  });
  els.toggleTheme.addEventListener("click", () => {
    const dark = document.body.dataset.theme !== "dark";
    document.body.dataset.theme = dark ? "dark" : "light";
    els.toggleTheme.setAttribute("aria-pressed", String(dark));
  });
  els.searchInput.addEventListener("input", () => scheduleSearch(els.searchInput.value));
  els.searchInput.addEventListener("focus", () => {
    openSearchModal();
    if (els.searchInput.value.trim()) scheduleSearch(els.searchInput.value);
  });
  els.searchOverlay.addEventListener("click", () => closeSearchModal());
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchModal();
      els.searchInput.focus();
      els.searchInput.select();
    }
    if (event.key === "Escape") {
      closeSearchModal();
      els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
    }
  }, { capture: true });
  window.addEventListener("resize", syncResponsiveState);
  bindAnnotationControls();
}

function syncResponsiveState() {
  const narrow = window.matchMedia("(max-width: 1100px)").matches;
  const mobile = window.matchMedia("(max-width: 860px)").matches;
  els.shell.classList.toggle("is-note-collapsed", narrow && !mobile);
  if (!mobile) {
    els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
  }
}

async function initReader() {
  state.annotations = loadAnnotations();
  bindControls();
  const projects = await fetchJson("../manifest.json");
  state.project = projects.find((project) => project.id === PROJECT_ID);
  state.papers = state.project?.papers ?? [];
  renderPaperNav();
  await loadAllSearchItems();
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("paper");
  const firstReadable = state.papers.find((paper) => state.allReadings.get(paper.id));
  await openPaper(requested || firstReadable?.id || state.papers[0]?.id);
}

initReader().catch((error) => {
  console.error(error);
  els.chunkList.innerHTML = `
    <article class="status-panel">
      <h2>阅读器暂时无法加载</h2>
      <p>请检查本地 manifest 和 reading 数据包。</p>
    </article>
  `;
});
