const PROJECT_ID = document.body.dataset.projectId ?? "brain-memory-for-ai-agents";
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

const LINEAGE_YEAR_START = 1995;
const LINEAGE_YEAR_END = 2026;
const PAPER_TYPE_LABELS = {
  "theory-simulation": "理论 / 仿真",
  "review-taxonomy": "综述 / 分类",
  "mechanism-review": "机制综述",
  "review-consolidation": "巩固综述",
  "lifecycle-review": "生命周期综述",
  "source-linked-mechanism-study": "机制研究支线",
  "system-paper": "工程系统",
  survey: "综述",
  "arxiv-v1-preprint": "arXiv v1 预印本"
};

const state = {
  project: null,
  atlas: null,
  papers: [],
  currentPaper: null,
  currentReading: null,
  view: "paper",
  lineageFilter: "all",
  selectedLineagePaperId: "yassa-stark-2011-pattern-separation",
  lineageResizeHandler: null,
  allReadings: new Map(),
  searchItems: [],
  activeChunkId: null,
  noteContextKey: null,
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
  sidebar: document.querySelector("#paper-directory"),
  sectionRail: document.querySelector("#section-rail"),
  mobileNoteDrawer: document.querySelector("#mobile-note-drawer"),
  nav: document.querySelector("#paper-nav"),
  lineageControls: document.querySelector("#lineage-controls"),
  lineageView: document.querySelector("#lineage-view"),
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
  panelScrim: document.querySelector("#panel-scrim"),
  viewControls: document.querySelectorAll("[data-reader-view]"),
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
    items: [],
    chunkNotes: {}
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
      items: parsed.items.filter((item) => item && item.projectId === PROJECT_ID),
      chunkNotes: parsed.chunkNotes && typeof parsed.chunkNotes === "object" ? parsed.chunkNotes : {}
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

function getLocalChunkNoteKey(paperId, chunkId) {
  return `${paperId}:${chunkId}`;
}

function getLocalChunkNote(paperId, chunkId) {
  if (!paperId || !chunkId) return "";
  return state.annotations.chunkNotes?.[getLocalChunkNoteKey(paperId, chunkId)] ?? "";
}

function updateLocalChunkNote(paperId, chunkId, value) {
  if (!paperId || !chunkId) return;
  if (!state.annotations.chunkNotes) state.annotations.chunkNotes = {};
  const key = getLocalChunkNoteKey(paperId, chunkId);
  if (value.trim()) {
    state.annotations.chunkNotes[key] = value;
  } else {
    delete state.annotations.chunkNotes[key];
  }
  saveAnnotations();
  document.querySelectorAll(`.note-free-editor[data-local-note-paper-id="${CSS.escape(paperId)}"][data-local-note-chunk-id="${CSS.escape(chunkId)}"]`)
    .forEach((editor) => {
      if (editor.value !== value) editor.value = value;
    });
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
        searchText: [
          chunk.sourceText,
          chunk.zhTranslation,
          chunk.zhExplanation,
          chunk.premise,
          chunk.claim,
          ...(chunk.evidence ?? [])
        ].filter(Boolean).join("\n")
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
    button.innerHTML = `
      <span class="paper-nav-marker" aria-hidden="true"></span>
      <span class="paper-nav-copy">
        <span class="paper-nav-year">${escapeHtml(paper.year)}</span>
        <span class="paper-nav-title">${escapeHtml(paper.shortTitle ?? paper.title)}</span>
      </span>
    `;
    button.addEventListener("click", () => openPaper(paper.id));
    els.nav.append(button);
  }
}

function renderReaderViewControls() {
  const lineage = state.view === "lineage";
  for (const control of els.viewControls) {
    const selected = control.dataset.readerView === state.view;
    control.setAttribute("aria-selected", String(selected));
    control.tabIndex = selected ? 0 : -1;
  }
  els.nav.hidden = lineage;
  els.lineageControls.hidden = !lineage;
  els.paperHeader.hidden = lineage;
  els.chunkList.hidden = lineage;
  els.lineageView.hidden = !lineage;
  els.sectionRail.setAttribute("aria-hidden", String(lineage));
  els.shell.classList.toggle("is-lineage-view", lineage);
}

function getLineageNode(paperId) {
  return state.atlas?.nodes?.find((node) => node.paperId === paperId) ?? null;
}

function renderLineageControls() {
  const lanes = state.atlas?.lanes ?? [];
  const filters = [{ id: "all", labelZh: "全部", labelEn: "All" }, ...lanes];
  const nodes = (state.atlas?.nodes ?? [])
    .filter((node) => state.lineageFilter === "all" || node.lane === state.lineageFilter)
    .sort((left, right) => {
      const leftPaper = getPaperById(left.paperId);
      const rightPaper = getPaperById(right.paperId);
      return (leftPaper?.year ?? 0) - (rightPaper?.year ?? 0);
    });

  els.lineageControls.innerHTML = `
    <fieldset class="lineage-filter-set">
      <legend>筛选视图</legend>
      ${filters.map((filter) => `
        <button class="lineage-filter" type="button" data-lineage-filter="${escapeHtml(filter.id)}" aria-pressed="${String(state.lineageFilter === filter.id)}">
          <span class="lineage-filter-mark lineage-filter-mark--${escapeHtml(filter.id)}" aria-hidden="true"></span>
          <span>${escapeHtml(filter.labelZh)}</span>
          <small>${escapeHtml(filter.labelEn)}</small>
        </button>
      `).join("")}
    </fieldset>
    <div class="lineage-focus-list" aria-label="谱系节点">
      <p class="lineage-controls-title">机制聚焦</p>
      ${nodes.map((node) => {
        const paper = getPaperById(node.paperId);
        return `
          <button class="lineage-focus-item" type="button" data-lineage-paper-id="${escapeHtml(node.paperId)}" aria-pressed="${String(state.selectedLineagePaperId === node.paperId)}">
            <span class="lineage-node-mark lineage-node-mark--${escapeHtml(node.lane)}" aria-hidden="true"></span>
            <span>${escapeHtml(paper?.shortTitle ?? node.paperId)}</span>
          </button>
        `;
      }).join("")}
    </div>
  `;

  els.lineageControls.querySelectorAll("[data-lineage-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const previousSelection = state.selectedLineagePaperId;
      state.lineageFilter = button.dataset.lineageFilter;
      const visibleNodes = (state.atlas?.nodes ?? []).filter((node) => (
        state.lineageFilter === "all" || node.lane === state.lineageFilter
      ));
      if (!visibleNodes.some((node) => node.paperId === state.selectedLineagePaperId)) {
        state.selectedLineagePaperId = visibleNodes[0]?.paperId ?? state.selectedLineagePaperId;
      }
      renderLineageControls();
      renderLineageView();
      renderLineageInspector();
      if (state.selectedLineagePaperId !== previousSelection) {
        const url = new URL(window.location.href);
        url.searchParams.set("paper", state.selectedLineagePaperId);
        url.searchParams.set("view", "lineage");
        url.searchParams.delete("chunk");
        window.history.replaceState({}, "", url);
      }
    });
  });
  els.lineageControls.querySelectorAll("[data-lineage-paper-id]").forEach((button) => {
    button.addEventListener("click", () => selectLineageNode(button.dataset.lineagePaperId));
  });
}

function getLineagePosition(year) {
  const yearStart = Number(state.atlas?.yearStart) || LINEAGE_YEAR_START;
  const yearEnd = Number(state.atlas?.yearEnd) || LINEAGE_YEAR_END;
  const boundedYear = Math.max(yearStart, Math.min(yearEnd, Number(year) || yearStart));
  return 8 + ((boundedYear - yearStart) / Math.max(1, yearEnd - yearStart)) * 80;
}

function getLineageNodeRow(node, laneNodes) {
  const lastYearByRow = [Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY];
  for (const item of laneNodes) {
    const year = Number(getPaperById(item.paperId)?.year) || Number(state.atlas?.yearStart) || LINEAGE_YEAR_START;
    let row = lastYearByRow.findIndex((lastYear) => year - lastYear >= 7);
    if (row === -1) {
      row = lastYearByRow.indexOf(Math.min(...lastYearByRow));
    }
    lastYearByRow[row] = year;
    if (item.paperId === node.paperId) return row;
  }
  return 0;
}

function renderLineageNode(node, laneNodes) {
  const paper = getPaperById(node.paperId);
  if (!paper) return "";
  const selected = state.selectedLineagePaperId === node.paperId;
  const row = getLineageNodeRow(node, laneNodes);
  return `
    <button class="lineage-node lineage-node--${escapeHtml(node.lane)}${selected ? " is-selected" : ""}" type="button" data-lineage-node="${escapeHtml(node.paperId)}" aria-pressed="${String(selected)}" style="--lineage-x: ${getLineagePosition(paper.year).toFixed(3)}%; --lineage-row: ${row};">
      <span class="lineage-node-year">${escapeHtml(paper.year)}</span>
      <span class="lineage-node-symbol" aria-hidden="true"></span>
      <strong>${escapeHtml(paper.shortTitle ?? paper.title)}</strong>
      <small>${escapeHtml(PAPER_TYPE_LABELS[node.paperType] ?? node.paperType)}</small>
    </button>
  `;
}

function renderLineageView() {
  if (!state.atlas) {
    els.lineageView.innerHTML = `<article class="status-panel"><h2>概念谱系暂时无法加载</h2></article>`;
    return;
  }
  const lanes = state.atlas.lanes ?? [];
  const visibleLanes = lanes.filter((lane) => state.lineageFilter === "all" || lane.id === state.lineageFilter);
  const yearStart = Number(state.atlas.yearStart) || LINEAGE_YEAR_START;
  const yearEnd = Number(state.atlas.yearEnd) || LINEAGE_YEAR_END;
  const years = state.atlas.years ?? [1995, 2000, 2005, 2010, 2015, 2020, 2026];
  const visibleNodeIds = new Set((state.atlas.nodes ?? [])
    .filter((node) => state.lineageFilter === "all" || node.lane === state.lineageFilter)
    .map((node) => node.paperId));
  const visibleRelations = (state.atlas.relations ?? [])
    .filter((relation) => visibleNodeIds.has(relation.from) && visibleNodeIds.has(relation.to));
  const showBridgeQuestions = state.lineageFilter === "all" || state.lineageFilter === "brain";

  els.lineageView.innerHTML = `
    <header class="lineage-heading">
      <div>
        <p class="lineage-kicker">Research atlas · ${escapeHtml(yearStart)}–${escapeHtml(yearEnd)}</p>
        <h1>${escapeHtml(state.atlas.titleZh)}</h1>
        <p class="lineage-subtitle">${escapeHtml(state.atlas.titleEn)}</p>
      </div>
      <p class="lineage-disclaimer">${escapeHtml(state.atlas.disclaimerZh)}</p>
    </header>
    <div class="lineage-scroll" tabindex="0" aria-label="横向滚动查看 ${escapeHtml(yearStart)} 至 ${escapeHtml(yearEnd)} 概念谱系">
      <div class="lineage-map">
        <div class="lineage-axis" aria-hidden="true">
          <span class="lineage-axis-label">YEAR</span>
          <div class="lineage-axis-track">
            ${years.map((year) => `<span style="--lineage-x: ${getLineagePosition(year).toFixed(3)}%">${year}</span>`).join("")}
          </div>
        </div>
        <div class="lineage-board">
          <canvas class="lineage-connections" aria-hidden="true"></canvas>
          ${visibleLanes.map((lane) => {
            const laneNodes = (state.atlas.nodes ?? [])
              .filter((node) => node.lane === lane.id)
              .sort((left, right) => (getPaperById(left.paperId)?.year ?? 0) - (getPaperById(right.paperId)?.year ?? 0));
            return `
              <section class="lineage-lane lineage-lane--${escapeHtml(lane.id)}" data-lineage-lane="${escapeHtml(lane.id)}">
                <h2><span>${escapeHtml(lane.labelZh)}</span><small>${escapeHtml(lane.labelEn)}</small></h2>
                <div class="lineage-track">
                  ${laneNodes.map((node) => renderLineageNode(node, laneNodes)).join("")}
                  ${lane.id === "workspace" ? `<p class="workspace-boundary">${escapeHtml(lane.note ?? "active workspace / reportability ≠ long-term memory")}</p>` : ""}
                  ${lane.id === "agent" ? `<p class="survey-scope">${escapeHtml(lane.note ?? "Survey scope · operations synthesis")}</p>` : ""}
                </div>
              </section>
            `;
          }).join("")}
          ${visibleRelations.map((relation, index) => `<span class="lineage-relation-label" data-lineage-relation-index="${index}">${escapeHtml(relation.label)}</span>`).join("")}
          ${showBridgeQuestions ? `
            <section class="lineage-bridge-band" aria-label="跨领域设计问题">
              <h2>Design questions</h2>
              <div>
                ${(state.atlas.bridgeQuestions ?? []).map((question) => `
                  <button type="button" class="lineage-bridge-question${question.sources.includes(state.selectedLineagePaperId) ? " is-selected" : ""}" data-lineage-bridge-sources="${escapeHtml(question.sources.join(","))}">
                    ${escapeHtml(question.labelZh)}
                  </button>
                `).join("")}
              </div>
            </section>
          ` : ""}
        </div>
      </div>
    </div>
    <footer class="lineage-legend" aria-label="概念谱系图例">
      <span><i class="legend-line legend-line--continuity" aria-hidden="true"></i>同领域概念连续性</span>
      <span><i class="legend-line legend-line--explicit" aria-hidden="true"></i>明确前作 / 比较关系</span>
      <span><i class="legend-line legend-line--bridge" aria-hidden="true"></i>项目级设计问题</span>
      <span><i class="legend-boundary" aria-hidden="true"></i>范围边界</span>
    </footer>
  `;

  els.lineageView.querySelectorAll("[data-lineage-node]").forEach((button) => {
    button.addEventListener("click", () => selectLineageNode(button.dataset.lineageNode));
  });
  els.lineageView.querySelectorAll("[data-lineage-bridge-sources]").forEach((button) => {
    button.addEventListener("click", () => {
      const source = button.dataset.lineageBridgeSources.split(",")[0];
      if (source) selectLineageNode(source);
    });
  });

  window.requestAnimationFrame(() => drawLineageConnections(visibleRelations));
}

function drawLineageConnections(relations = []) {
  const board = els.lineageView.querySelector(".lineage-board");
  const canvas = els.lineageView.querySelector(".lineage-connections");
  if (!board || !canvas || board.clientWidth === 0 || board.clientHeight === 0) return;
  const boardRect = board.getBoundingClientRect();
  const ratio = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(boardRect.width * ratio);
  canvas.height = Math.round(boardRect.height * ratio);
  canvas.style.width = `${boardRect.width}px`;
  canvas.style.height = `${boardRect.height}px`;
  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);
  context.clearRect(0, 0, boardRect.width, boardRect.height);
  const styles = getComputedStyle(document.body);
  const ink = styles.getPropertyValue("--reader-blue").trim() || "#183c49";
  const muted = styles.getPropertyValue("--reader-ink-muted-solid").trim() || "#68706d";
  const red = styles.getPropertyValue("--reader-red").trim() || "#a64338";

  relations.forEach((relation, index) => {
    const source = board.querySelector(`[data-lineage-node="${CSS.escape(relation.from)}"]`);
    const target = board.querySelector(`[data-lineage-node="${CSS.escape(relation.to)}"]`);
    if (!source || !target) return;
    const isRelatedToSelection = relation.from === state.selectedLineagePaperId
      || relation.to === state.selectedLineagePaperId;
    const sourceRect = source.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const startX = sourceRect.left - boardRect.left + sourceRect.width / 2;
    const startY = sourceRect.top - boardRect.top + 28;
    const endX = targetRect.left - boardRect.left + targetRect.width / 2;
    const endY = targetRect.top - boardRect.top + 28;
    const routeY = Math.max(12, Math.min(startY, endY) - 24 - index * 8);
    context.beginPath();
    context.moveTo(startX, startY);
    context.lineTo(startX, routeY);
    context.lineTo(endX, routeY);
    context.lineTo(endX, endY);
    context.lineWidth = relation.kind === "explicit-comparator" ? 1.8 : 1.25;
    context.strokeStyle = relation.kind === "explicit-comparator" ? ink : muted;
    context.setLineDash(relation.kind === "explicit-comparator" ? [] : [3, 5]);
    context.globalAlpha = isRelatedToSelection ? 1 : 0.1;
    context.stroke();
    context.globalAlpha = 1;
    const label = board.querySelector(`[data-lineage-relation-index="${index}"]`);
    if (label) {
      label.style.left = `${(startX + endX) / 2}px`;
      label.style.top = `${routeY}px`;
      label.classList.toggle("is-muted", !isRelatedToSelection);
    }
  });

  const selectedNode = board.querySelector(`[data-lineage-node="${CSS.escape(state.selectedLineagePaperId)}"]`);
  const selectedQuestion = board.querySelector(".lineage-bridge-question.is-selected");
  if (selectedNode && selectedQuestion) {
    const sourceRect = selectedNode.getBoundingClientRect();
    const questionRect = selectedQuestion.getBoundingClientRect();
    const startX = sourceRect.left - boardRect.left + sourceRect.width / 2;
    const startY = sourceRect.bottom - boardRect.top - 8;
    const endX = questionRect.left - boardRect.left + 10;
    const endY = questionRect.top - boardRect.top + questionRect.height / 2;
    const bendY = endY - 14;
    context.beginPath();
    context.moveTo(startX, startY);
    context.lineTo(startX, bendY);
    context.lineTo(endX, bendY);
    context.lineTo(endX, endY);
    context.lineWidth = 1.6;
    context.strokeStyle = red;
    context.setLineDash([2, 5]);
    context.stroke();
  }
  context.setLineDash([]);
}

function scheduleLineageRedraw(delay = 0) {
  window.clearTimeout(state.lineageResizeHandler);
  if (state.view !== "lineage") return;
  state.lineageResizeHandler = window.setTimeout(() => {
    const visibleNodeIds = new Set((state.atlas?.nodes ?? [])
      .filter((node) => state.lineageFilter === "all" || node.lane === state.lineageFilter)
      .map((node) => node.paperId));
    drawLineageConnections((state.atlas?.relations ?? [])
      .filter((relation) => visibleNodeIds.has(relation.from) && visibleNodeIds.has(relation.to)));
  }, delay);
}

function renderLineageInspector() {
  const node = getLineageNode(state.selectedLineagePaperId) ?? state.atlas?.nodes?.[0];
  const paper = getPaperById(node?.paperId);
  if (!node || !paper) return;
  const relatedRelations = (state.atlas.relations ?? []).filter((relation) => relation.from === node.paperId || relation.to === node.paperId);
  const bridgeQuestions = (state.atlas.bridgeQuestions ?? []).filter((question) => question.sources.includes(node.paperId));
  const inspectorMarkup = `
    <div class="lineage-inspector">
      <section class="lineage-selected-route">
        <p>${escapeHtml(paper.year)} · ${escapeHtml(PAPER_TYPE_LABELS[node.paperType] ?? node.paperType)}</p>
        <h2>${escapeHtml(paper.shortTitle ?? paper.title)}</h2>
        <span>${escapeHtml(node.motifZh)}</span>
        <button type="button" data-open-lineage-paper="${escapeHtml(paper.id)}">打开论文精读</button>
      </section>
      ${bridgeQuestions.length ? `
        <section class="lineage-inspector-section">
          <h2>项目设计问题</h2>
          <ul>${bridgeQuestions.map((question) => `<li>${escapeHtml(question.labelZh)}</li>`).join("")}</ul>
        </section>
      ` : ""}
      <section class="lineage-inspector-section">
        <h2>关系</h2>
        ${relatedRelations.length ? `<ul>${relatedRelations.map((relation) => `<li><strong>${escapeHtml(relation.label)}</strong><span>${escapeHtml(getPaperById(relation.from === node.paperId ? relation.to : relation.from)?.shortTitle ?? "")}</span></li>`).join("")}</ul>` : `<p>该节点在当前图中保持独立，不强行添加论文间连线。</p>`}
      </section>
      <section class="lineage-inspector-section lineage-inspector-legend">
        <h2>关系图例</h2>
        <p>虚线：同领域概念连续性</p>
        <p>实线：明确前作或比较关系</p>
        <p>朱砂点线：项目级设计问题</p>
      </section>
      <p class="lineage-warning">${escapeHtml(state.atlas.disclaimerEn)}</p>
      <p class="lineage-warning-copy">${escapeHtml(state.atlas.disclaimerZh)}</p>
    </div>
  `;
  const label = "Selected route · Conceptual lineage";
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  state.noteContextKey = `lineage:${paper.id}`;
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.innerHTML = inspectorMarkup;
    surface.classList.remove("is-changing");
    surface.querySelector("[data-open-lineage-paper]")?.addEventListener("click", () => openPaper(paper.id));
  }
}

function selectLineageNode(paperId) {
  if (!getLineageNode(paperId)) return;
  state.selectedLineagePaperId = paperId;
  renderLineageControls();
  renderLineageView();
  renderLineageInspector();
  const url = new URL(window.location.href);
  url.searchParams.set("paper", paperId);
  url.searchParams.set("view", "lineage");
  url.searchParams.delete("chunk");
  window.history.replaceState({}, "", url);
}

function openLineage() {
  const currentNode = getLineageNode(state.currentPaper?.id);
  if (currentNode) state.selectedLineagePaperId = currentNode.paperId;
  state.view = "lineage";
  state.noteContextKey = null;
  stopObservingChunks();
  closeMobilePanels();
  renderReaderViewControls();
  renderLineageControls();
  renderLineageView();
  renderLineageInspector();
  els.main.scrollTo({ top: 0, left: 0, behavior: "auto" });
  const url = new URL(window.location.href);
  url.searchParams.set("view", "lineage");
  url.searchParams.set("paper", state.selectedLineagePaperId);
  url.searchParams.delete("chunk");
  window.history.replaceState({}, "", url);
}

function renderSectionRail(reading) {
  els.sectionLines.innerHTML = "";
  const sections = reading?.paperData.sections ?? [];
  sections.forEach((section) => {
    const button = document.createElement("button");
    button.className = "section-line";
    button.type = "button";
    button.dataset.sectionId = section.id;
    button.setAttribute("aria-label", section.titleZh ?? section.title);
    button.setAttribute("aria-current", "false");
    button.innerHTML = `<span class="section-tooltip">${escapeHtml(section.title)}</span>`;
    button.addEventListener("click", () => scrollToSection(section.id));
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

function renderDeepReadingIntro(paperData) {
  const readingGroups = Array.isArray(paperData.readingGroups) ? paperData.readingGroups : [];
  const groupTitles = new Map(readingGroups.map((group) => [group.id, group.title]));
  const premises = Array.isArray(paperData.premises) ? paperData.premises : [];
  const narrativeSpine = Array.isArray(paperData.narrativeSpine) ? paperData.narrativeSpine : [];
  const misreadings = Array.isArray(paperData.misreadings) ? paperData.misreadings : [];

  if (!premises.length && !narrativeSpine.length && !misreadings.length) return "";

  const premiseMarkup = premises.length
    ? `
      <section class="deep-reading-section deep-reading-premises" aria-label="阅读前提">
        <h2>阅读前提</h2>
        <ul>
          ${premises.map((premise) => `
            <li>
              <strong>${escapeHtml(premise.title ?? "")}</strong>
              <span>${escapeHtml(premise.body ?? "")}</span>
            </li>
          `).join("")}
        </ul>
      </section>
    `
    : "";

  const spineMarkup = narrativeSpine.length
    ? `
      <section class="deep-reading-section reading-spine" aria-label="叙事主线">
        <h2>叙事主线</h2>
        <ol>
          ${narrativeSpine.map((item) => `
            <li>
              <span class="spine-group">${escapeHtml(groupTitles.get(item.groupId) ?? item.groupId ?? "")}</span>
              <span>${escapeHtml(item.summary ?? "")}</span>
            </li>
          `).join("")}
        </ol>
      </section>
    `
    : "";

  const misreadingMarkup = misreadings.length
    ? `
      <section class="deep-reading-section deep-reading-misreadings" aria-label="误读边界">
        <h2>误读边界</h2>
        <ul>
          ${misreadings.map((item) => `
            <li>
              ${item.groupId ? `<span class="spine-group">${escapeHtml(groupTitles.get(item.groupId) ?? item.groupId)}</span>` : ""}
              <span>${escapeHtml(item.text ?? "")}</span>
            </li>
          `).join("")}
        </ul>
      </section>
    `
    : "";

  return `<div class="deep-reading-intro">${premiseMarkup}${spineMarkup}${misreadingMarkup}</div>`;
}

function getScrollBehavior() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

function scrollToSection(sectionId) {
  const firstChunk = document.querySelector(`.chunk[data-section-id="${CSS.escape(sectionId)}"]`);
  firstChunk?.scrollIntoView({ behavior: getScrollBehavior(), block: "start" });
}

function ensureFigureLightbox() {
  const existing = document.querySelector("#figure-lightbox");
  if (existing) return existing;
  const dialog = document.createElement("dialog");
  dialog.id = "figure-lightbox";
  dialog.className = "figure-lightbox";
  dialog.setAttribute("aria-labelledby", "figure-lightbox-title");
  dialog.innerHTML = `
    <div class="figure-lightbox-shell">
      <header class="figure-lightbox-header">
        <div>
          <span>Source figure · original size</span>
          <strong id="figure-lightbox-title"></strong>
        </div>
        <button type="button" data-close-figure-lightbox>关闭</button>
      </header>
      <div class="figure-lightbox-viewport" role="region" aria-label="可滚动的原始尺寸论文图" tabindex="0">
        <img alt="">
      </div>
      <p class="figure-lightbox-hint">滚动查看原始尺寸图像</p>
    </div>
  `;
  dialog.querySelector("[data-close-figure-lightbox]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  document.body.append(dialog);
  return dialog;
}

function openFigureLightbox(trigger) {
  const dialog = ensureFigureLightbox();
  if (typeof dialog.showModal !== "function") {
    window.open(trigger.dataset.figureLightboxSrc, "_blank", "noopener");
    return;
  }
  const image = dialog.querySelector("img");
  const viewport = dialog.querySelector(".figure-lightbox-viewport");
  dialog.querySelector("#figure-lightbox-title").textContent = trigger.dataset.figureLightboxTitle ?? "Source figure";
  image.alt = trigger.dataset.figureLightboxAlt ?? "Source figure";
  image.src = trigger.dataset.figureLightboxSrc;
  viewport.scrollTo({ left: 0, top: 0 });
  dialog.showModal();
  window.requestAnimationFrame(() => viewport.focus({ preventScroll: true }));
}

function renderVisualAbstract(reading) {
  const config = state.atlas?.visualAbstract;
  if (!reading || config?.paperId !== state.currentPaper?.id) return "";
  const figure = reading.figures.get(config.figureId);
  if (!figure?.file) return "";
  return `
    <figure class="visual-abstract" aria-labelledby="visual-abstract-title">
      <div class="visual-abstract-header">
        <div>
          <p class="visual-abstract-label">Visual abstract · Plate ${escapeHtml(config.plateNumber)}</p>
          <h2 id="visual-abstract-title">${escapeHtml(config.titleZh)}</h2>
          <p>${escapeHtml(config.summaryZh)}</p>
        </div>
        <span class="visual-abstract-title-en">${escapeHtml(config.titleEn)}</span>
      </div>
      <div class="visual-abstract-media">
        <img src="${escapeHtml(resolveReadingAssetPath(figure.file, reading))}" alt="${escapeHtml(figure.caption ?? figure.label)}" fetchpriority="high">
      </div>
      <div class="figure-view-tools">
        <button type="button" class="figure-zoom-button" data-figure-lightbox-src="${escapeHtml(resolveReadingAssetPath(figure.file, reading))}" data-figure-lightbox-alt="${escapeHtml(figure.caption ?? figure.label)}" data-figure-lightbox-title="${escapeHtml(config.titleZh)}">
          放大图像 <span>Original size</span>
        </button>
      </div>
      <div class="visual-abstract-anchors" aria-label="视觉摘要阅读锚点">
        ${(config.anchors ?? []).map((anchor, index) => `
          <button type="button" data-visual-section-id="${escapeHtml(anchor.sectionId)}">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <strong>${escapeHtml(anchor.labelZh)}</strong>
            <small>${escapeHtml(anchor.labelEn)}</small>
          </button>
        `).join("")}
      </div>
      <figcaption>${escapeHtml(figure.caption ?? "")}</figcaption>
    </figure>
  `;
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
  const plateIndex = String(Math.max(0, state.papers.findIndex((paper) => paper.id === state.currentPaper?.id)) + 1).padStart(2, "0");

  els.paperHeader.innerHTML = `
    <div class="paper-copy">
      <div class="paper-heading-line">
        <p class="paper-kicker">${escapeHtml(category)}</p>
        <span class="paper-plate-index">Plate ${plateIndex}</span>
      </div>
      <h1 class="paper-title">${escapeHtml(paperData.title ?? state.currentPaper.title)}</h1>
      <p class="paper-meta paper-citation">${escapeHtml([paperData.authors, paperData.year].filter(Boolean).join(" · "))}</p>
      ${relation ? `<p class="paper-meta paper-relation">${escapeHtml(relation)}</p>` : ""}
      ${description ? `<p class="paper-meta paper-description">${escapeHtml(description)}</p>` : ""}
    </div>
    ${renderVisualAbstract(reading)}
    ${readingFocus ? `<ul class="reading-focus">${readingFocus}</ul>` : ""}
    ${renderDeepReadingIntro(paperData)}
    <div class="paper-actions"></div>
    <div class="section-chips">${sections}</div>
  `;

  els.paperHeader.querySelectorAll(".section-chip").forEach((button) => {
    button.addEventListener("click", () => scrollToSection(button.dataset.sectionId));
  });
  els.paperHeader.querySelectorAll("[data-visual-section-id]").forEach((button) => {
    button.addEventListener("click", () => scrollToSection(button.dataset.visualSectionId));
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

function getFeaturedPlateConfig(figureId, reading = state.currentReading) {
  return state.atlas?.featuredPlates?.find((plate) => (
    plate.paperId === reading?.paper?.id && plate.figureId === figureId
  )) ?? null;
}

function getPlateNumber(figure, reading, featuredPlate) {
  if (featuredPlate?.plateNumber) return featuredPlate.plateNumber;
  const paperIndex = Math.max(0, state.papers.findIndex((paper) => paper.id === reading?.paper?.id));
  const figureIndex = Math.max(0, [...(reading?.figures?.values() ?? [])].findIndex((item) => item.id === figure.id));
  return `${String(paperIndex + 1).padStart(2, "0")}.${figureIndex + 1}`;
}

function renderPlateCallout(callout) {
  if (!callout) return "";
  return `
    <aside class="plate-callout plate-callout--${escapeHtml(callout.tone ?? "evidence")}">
      <span class="plate-callout-key">${escapeHtml(callout.key)}</span>
      <strong>${escapeHtml(callout.titleZh)}</strong>
      <p>${escapeHtml(callout.bodyZh)}</p>
    </aside>
  `;
}

function renderFigure(figure, relation = "supporting", reading = null) {
  const featuredPlate = getFeaturedPlateConfig(figure?.id, reading);
  const plateNumber = getPlateNumber(figure ?? {}, reading, featuredPlate);
  const paperTitle = reading?.paper?.shortTitle ?? reading?.paperData?.shortTitle ?? "Source paper";
  const sourceUrl = figure?.sourceUrl ?? reading?.paperData?.source ?? reading?.paper?.source;
  const sourceStamp = [paperTitle, reading?.paper?.year].filter(Boolean).join(" · ");
  const plateTitle = featuredPlate?.title ?? figure?.label ?? "Source figure";
  const methods = featuredPlate?.methods ?? [];
  const callouts = featuredPlate?.callouts ?? [];
  const plateClass = featuredPlate ? " research-plate--featured" : "";
  if (!figure?.file && figure?.sourceUrl) {
    return `
      <figure class="figure-frame research-plate figure-link-card" data-relation="${escapeHtml(relation)}" data-figure-id="${escapeHtml(figure.id ?? "")}">
        <header class="plate-header">
          <span class="plate-index">Plate ${escapeHtml(plateNumber)}</span>
          <span class="plate-source">${escapeHtml(sourceStamp)}</span>
        </header>
        <div class="figure-link-label">${escapeHtml(plateTitle)}</div>
        <figcaption class="figure-caption">${escapeHtml(figure.caption ?? "")}</figcaption>
        <a class="figure-source-link" href="${escapeHtml(figure.sourceUrl)}" target="_blank" rel="noopener">Open source figure</a>
      </figure>
    `;
  }
  if (!figure?.file) return "";
  return `
    <figure class="figure-frame research-plate${plateClass}" data-relation="${escapeHtml(relation)}" data-figure-id="${escapeHtml(figure.id ?? "")}">
      <header class="plate-header">
        <span class="plate-index">Plate ${escapeHtml(plateNumber)}</span>
        <span class="plate-source">${escapeHtml(sourceStamp)} · ${escapeHtml(figure.label ?? "Figure")}</span>
        <span class="plate-relation">${escapeHtml(relation)}</span>
      </header>
      ${methods.length ? `<p class="plate-methods">${methods.map((item) => escapeHtml(item)).join(" / ")}</p>` : ""}
      <div class="plate-figure-stage${callouts.length ? " has-callouts" : ""}">
        ${renderPlateCallout(callouts[0])}
        <div class="plate-figure-media">
          <img src="${escapeHtml(resolveReadingAssetPath(figure.file, reading))}" alt="${escapeHtml(figure.caption ?? figure.label ?? "Figure")}" loading="lazy">
        </div>
        ${renderPlateCallout(callouts[1])}
      </div>
      <div class="figure-view-tools">
        <button type="button" class="figure-zoom-button" data-figure-lightbox-src="${escapeHtml(resolveReadingAssetPath(figure.file, reading))}" data-figure-lightbox-alt="${escapeHtml(figure.caption ?? figure.label ?? "Figure")}" data-figure-lightbox-title="${escapeHtml(plateTitle)}">
          放大图像 <span>Original size</span>
        </button>
      </div>
      <figcaption class="figure-caption plate-paper-caption">${escapeHtml(figure.caption ?? "")}</figcaption>
      <footer class="plate-footer">
        <span>${escapeHtml(figure.sourceFigure ?? figure.label ?? "Source figure")}${figure.sourcePage ? ` · p. ${escapeHtml(figure.sourcePage)}` : ""}</span>
        ${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener">Source stamp · ${escapeHtml(sourceStamp)}</a>` : `<span>Source stamp · ${escapeHtml(sourceStamp)}</span>`}
      </footer>
    </figure>
  `;
}

function getReadingGroup(reading, groupId) {
  return (reading?.paperData?.readingGroups ?? []).find((group) => group.id === groupId);
}

function renderChunkDeepReading(chunk, reading) {
  const group = getReadingGroup(reading, chunk.groupId);
  const evidenceItems = Array.isArray(chunk.evidence) ? chunk.evidence : [];
  if (!group && !chunk.premise && !chunk.claim && evidenceItems.length === 0) return "";
  return `
    <div class="chunk-deep-reading">
      ${group ? `<p class="chunk-group">${escapeHtml(group.title)}</p>` : ""}
      ${chunk.premise ? `<p class="chunk-premise">${escapeHtml(chunk.premise)}</p>` : ""}
      ${chunk.claim ? `<p class="chunk-claim">${escapeHtml(chunk.claim)}</p>` : ""}
      ${evidenceItems.length ? `
        <ul class="chunk-evidence">
          ${evidenceItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      ` : ""}
    </div>
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
      ${renderChunkDeepReading(chunk, reading)}
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

function renderNoteSurface(surface, note, annotations = [], chunkId = "") {
  const baseNote = note ? `<p>${renderMultilineText(note)}</p>` : "";
  const paperId = state.currentPaper?.id ?? "";
  const localNote = getLocalChunkNote(paperId, chunkId);
  const freeEditor = paperId && chunkId
    ? `<textarea class="note-free-editor" data-local-note-paper-id="${escapeHtml(paperId)}" data-local-note-chunk-id="${escapeHtml(chunkId)}" aria-label="编辑当前段落笔记">${escapeHtml(localNote)}</textarea>`
    : "";
  const annotationMarkup = annotations
    .filter((annotation) => annotation.mode === "note")
    .map((annotation) => `
      <article class="note-annotation${annotation.highlightActive ? "" : " is-detached"}" data-note-annotation-id="${escapeHtml(annotation.id)}">
        <blockquote class="note-annotation-quote">${escapeHtml(annotation.selectedText)}</blockquote>
        <textarea class="note-annotation-editor" data-annotation-note-id="${escapeHtml(annotation.id)}" placeholder="写批注...">${escapeHtml(annotation.note ?? "")}</textarea>
      </article>
    `)
    .join("");
  surface.innerHTML = `${baseNote}${freeEditor}${annotationMarkup}`;
  surface.classList.remove("is-changing");
  bindNoteEditors(surface);
}

function bindNoteEditors(surface) {
  surface.querySelectorAll(".note-free-editor").forEach((editor) => {
    editor.addEventListener("input", () => {
      updateLocalChunkNote(editor.dataset.localNotePaperId, editor.dataset.localNoteChunkId, editor.value);
    });
  });
  surface.querySelectorAll(".note-annotation-editor").forEach((editor) => {
    editor.addEventListener("input", () => updateAnnotationNote(editor.dataset.annotationNoteId, editor.value));
  });
}

function getFeaturedPlateForChunk(chunkId) {
  const chunk = state.currentReading?.chunks?.find((item) => item.id === chunkId);
  if (!chunk) return null;
  const figureIds = new Set([
    ...(chunk.blocks ?? []).filter((block) => block.type === "figure").map((block) => block.id),
    ...(chunk.figureRefs ?? []).map((ref) => ref.id)
  ]);
  return state.atlas?.featuredPlates?.find((plate) => (
    plate.paperId === state.currentPaper?.id && figureIds.has(plate.figureId)
  )) ?? null;
}

function renderEvidencePanel(surface, plate, note, chunkId) {
  const paperId = state.currentPaper?.id ?? "";
  const localNote = getLocalChunkNote(paperId, chunkId);
  surface.innerHTML = `
    <div class="evidence-panel">
      <section class="evidence-section">
        <h2>主张</h2>
        <p>${escapeHtml(plate.analysis.claimZh)}</p>
      </section>
      <section class="evidence-section">
        <h2>证据</h2>
        <p>${escapeHtml(plate.analysis.evidenceZh)}</p>
      </section>
      <section class="evidence-section evidence-section--boundary">
        <h2>局限</h2>
        <p>${escapeHtml(plate.analysis.limitationZh)}</p>
      </section>
      <section class="evidence-section evidence-section--synthesis">
        <h2>项目启发</h2>
        <p>${escapeHtml(plate.analysis.synthesisZh)}</p>
      </section>
      ${note ? `<section class="evidence-source-note"><h2>平行笔记</h2><p>${renderMultilineText(note)}</p></section>` : ""}
      <section class="research-note-region">
        <h2>自由笔记</h2>
        <textarea class="note-free-editor research-note-editor" data-local-note-paper-id="${escapeHtml(paperId)}" data-local-note-chunk-id="${escapeHtml(chunkId)}" aria-label="编辑当前证据图版笔记" placeholder="记录你的想法…">${escapeHtml(localNote)}</textarea>
      </section>
    </div>
  `;
  surface.classList.remove("is-changing");
  bindNoteEditors(surface);
}

function renderPaperOverviewPanel(surface) {
  const paperData = state.currentReading?.paperData ?? state.currentPaper;
  const readingFocus = Array.isArray(paperData?.readingFocus) ? paperData.readingFocus : [];
  surface.innerHTML = `
    <div class="paper-overview-panel">
      <p class="paper-overview-relation">${escapeHtml(paperData?.relationZh ?? paperData?.relation ?? "")}</p>
      <h2>阅读问题</h2>
      <ol>
        ${readingFocus.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ol>
      <p class="paper-overview-hint">向下阅读后，这里会切换为当前证据段的平行笔记。</p>
    </div>
  `;
  surface.classList.remove("is-changing");
}

function showPaperOverviewNote() {
  const contextKey = `paper:${state.currentPaper?.id ?? ""}`;
  if (state.noteContextKey === contextKey) return;
  state.noteContextKey = contextKey;
  state.activeChunkId = null;
  const label = `阅读问题 · ${state.currentPaper?.shortTitle ?? "Paper"}`;
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.classList.add("is-changing");
    window.setTimeout(() => {
      if (state.noteContextKey === contextKey) renderPaperOverviewPanel(surface);
    }, 90);
  }
}

function updateNoteSurface(chunkId, note) {
  const featuredPlate = getFeaturedPlateForChunk(chunkId);
  const label = featuredPlate ? `Research Plate · ${featuredPlate.plateNumber}` : (chunkId ? `Parallel note · ${chunkId}` : "Parallel note");
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  const contextKey = `chunk:${state.currentPaper?.id ?? ""}:${chunkId}`;
  state.noteContextKey = contextKey;
  const annotations = state.currentPaper && chunkId
    ? getAnnotationsForChunk(state.currentPaper.id, chunkId)
    : [];
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.classList.add("is-changing");
    window.setTimeout(() => {
      if (state.noteContextKey !== contextKey) return;
      if (featuredPlate) {
        renderEvidencePanel(surface, featuredPlate, note, chunkId);
      } else {
        renderNoteSurface(surface, note, annotations, chunkId);
      }
    }, 90);
  }
}

function updateActiveSectionRail(sectionId) {
  for (const line of els.sectionLines.children) {
    const active = line.dataset.sectionId === sectionId;
    line.classList.toggle("is-active", active);
    line.setAttribute("aria-current", active ? "true" : "false");
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
  if (state.view !== "paper") return;
  const mainRect = els.main.getBoundingClientRect();
  const headerRect = els.paperHeader.getBoundingClientRect();
  const overviewThreshold = mainRect.top + Math.min(180, mainRect.height * 0.24);
  if (headerRect.bottom > overviewThreshold) {
    showPaperOverviewNote();
    updateActiveSectionRail(null);
    return;
  }
  const chunkId = getActiveChunkByViewport();
  if (chunkId) setActiveChunk(reading, chunkId);
}

function stopObservingChunks() {
  state.observer?.disconnect();
  if (state.scrollSpyHandler) {
    window.removeEventListener("scroll", state.scrollSpyHandler);
    window.removeEventListener("resize", state.scrollSpyHandler);
    els.main.removeEventListener("scroll", state.scrollSpyHandler);
  }
  state.observer = null;
  state.scrollSpyHandler = null;
}

function observeChunks(reading) {
  stopObservingChunks();
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

function resetReaderPosition() {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
      els.main.scrollTo({ top: 0, left: 0, behavior: "auto" });
      resolve();
    });
  });
}

async function openPaper(paperId, chunkId = null) {
  const paper = getPaperById(paperId);
  if (!paper) return;
  state.view = "paper";
  state.currentPaper = paper;
  state.selectedLineagePaperId = getLineageNode(paper.id)?.paperId ?? state.selectedLineagePaperId;
  state.activeChunkId = null;
  state.noteContextKey = null;
  stopObservingChunks();
  closeMobilePanels();
  renderReaderViewControls();
  renderPaperNav();
  const reading = await loadReadingPackage(paper);
  state.currentReading = reading;
  const url = new URL(window.location.href);
  url.searchParams.set("paper", paper.id);
  url.searchParams.delete("view");
  if (chunkId) {
    url.searchParams.set("chunk", chunkId);
  } else {
    url.searchParams.delete("chunk");
  }
  window.history.replaceState({}, "", url);
  if (!reading) {
    renderNoChunkPaper();
    await resetReaderPosition();
    return;
  }
  renderPaperHeader(reading);
  renderSectionRail(reading);
  renderChunks(reading);
  await resetReaderPosition();
  if (chunkId) {
    await new Promise((resolve) => window.requestAnimationFrame(resolve));
    const requestedChunk = document.getElementById(chunkId);
    if (requestedChunk) {
      requestedChunk.scrollIntoView({ behavior: "auto", block: "start" });
      setActiveChunk(reading, chunkId);
    }
  }
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
  const fields = [
    item.chunk.zhTranslation,
    item.chunk.zhExplanation,
    item.chunk.claim,
    item.chunk.premise,
    item.chunk.sourceText,
    ...(item.chunk.evidence ?? [])
  ].filter(Boolean);
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
    [item.chunk.claim, 4],
    [item.chunk.premise, 3],
    [item.chunk.sourceText, 2],
    [item.chunk.zhTranslation, 2],
    [item.chunk.zhExplanation, 2],
    [(item.chunk.evidence ?? []).join(" "), 3],
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
      document.getElementById(button.dataset.chunkId)?.scrollIntoView({ behavior: getScrollBehavior(), block: "start" });
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

function renderAnnotationDeleteActions(popover, annotation) {
  popover.innerHTML = annotation?.mode === "note"
    ? `
      <button type="button" data-delete-behavior="highlight-only">只删除高亮，保留笔记</button>
      <button type="button" data-delete-behavior="all">高亮和批注一起删除</button>
      <button type="button" data-delete-behavior="cancel">取消</button>
    `
    : `
      <button type="button" data-delete-behavior="all">取消高亮</button>
      <button type="button" data-delete-behavior="cancel">取消</button>
    `;
}

function ensureAnnotationDeletePopover() {
  if (state.annotationDeletePopover) return state.annotationDeletePopover;
  const popover = document.createElement("div");
  popover.className = "annotation-delete-popover";
  popover.hidden = true;
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
  const annotation = state.annotations.items.find((item) => item.id === annotationId);
  if (!annotation) return;
  const popover = ensureAnnotationDeletePopover();
  popover.dataset.annotationId = annotationId;
  renderAnnotationDeleteActions(popover, annotation);
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
      els.shell.classList.remove("is-mobile-note-open");
      els.shell.classList.remove("is-left-collapsed");
      syncMobilePanelState();
      return;
    }
    els.shell.classList.toggle("is-left-collapsed");
    scheduleLineageRedraw(220);
  };
  els.toggleLeftControls.forEach((control) => control.addEventListener("click", toggleLeftPanel));
  els.toggleNote.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 860px)").matches) {
      els.shell.classList.toggle("is-mobile-note-open");
      els.shell.classList.remove("is-mobile-left-open");
      syncMobilePanelState();
      return;
    }
    els.shell.classList.toggle("is-note-collapsed");
    scheduleLineageRedraw(220);
  });
  els.toggleTheme.addEventListener("click", () => {
    const dark = document.body.dataset.theme !== "dark";
    document.body.dataset.theme = dark ? "dark" : "light";
    els.toggleTheme.setAttribute("aria-pressed", String(dark));
    scheduleLineageRedraw();
  });
  els.viewControls.forEach((control) => {
    control.addEventListener("click", () => {
      if (control.dataset.readerView === "lineage") {
        openLineage();
      } else if (state.currentPaper) {
        openPaper(state.currentPaper.id);
      }
    });
  });
  els.panelScrim.addEventListener("click", closeMobilePanels);
  els.searchInput.addEventListener("input", () => scheduleSearch(els.searchInput.value));
  els.searchInput.addEventListener("focus", () => {
    openSearchModal();
    if (els.searchInput.value.trim()) scheduleSearch(els.searchInput.value);
  });
  els.searchOverlay.addEventListener("click", () => closeSearchModal());
  els.main.addEventListener("click", (event) => {
    const figureTrigger = event.target.closest("[data-figure-lightbox-src]");
    if (figureTrigger) openFigureLightbox(figureTrigger);
  });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchModal();
      els.searchInput.focus();
      els.searchInput.select();
    }
    if (event.key === "Escape") {
      closeSearchModal();
      closeMobilePanels();
    }
  }, { capture: true });
  window.addEventListener("resize", syncResponsiveState);
  bindAnnotationControls();
}

function closeMobilePanels() {
  els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
  syncMobilePanelState();
}

function syncMobilePanelState() {
  const mobile = window.matchMedia("(max-width: 860px)").matches;
  const leftOpen = mobile && els.shell.classList.contains("is-mobile-left-open");
  const noteOpen = mobile && els.shell.classList.contains("is-mobile-note-open");
  const panelOpen = leftOpen || noteOpen;
  els.panelScrim.hidden = !panelOpen;
  els.sidebar.inert = mobile && !leftOpen;
  els.mobileNoteDrawer.inert = !noteOpen;
  els.toggleLeftControls.forEach((control) => control.setAttribute("aria-expanded", String(leftOpen)));
  els.toggleNote.setAttribute("aria-expanded", String(noteOpen));
}

function syncResponsiveState() {
  const narrow = window.matchMedia("(max-width: 1100px)").matches;
  const mobile = window.matchMedia("(max-width: 860px)").matches;
  els.shell.classList.toggle("is-note-collapsed", narrow && !mobile);
  if (!mobile) {
    els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
  }
  syncMobilePanelState();
  scheduleLineageRedraw(80);
}

async function initReader() {
  state.annotations = loadAnnotations();
  bindControls();
  const [projects, atlas] = await Promise.all([
    fetchJson("../manifest.json"),
    fetchJson("research-atlas.json", { optional: true })
  ]);
  state.atlas = atlas;
  state.project = projects.find((project) => project.id === PROJECT_ID);
  state.papers = state.project?.papers ?? [];
  renderPaperNav();
  await loadAllSearchItems();
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("paper");
  const requestedChunk = params.get("chunk");
  const requestedView = params.get("view");
  if (getLineageNode(requested)) state.selectedLineagePaperId = requested;
  const firstReadable = state.papers.find((paper) => state.allReadings.get(paper.id));
  await openPaper(requested || firstReadable?.id || state.papers[0]?.id, requestedChunk);
  if (requestedView === "lineage") openLineage();
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
