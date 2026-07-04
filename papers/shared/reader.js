const PROJECT_ID = "brain-memory-for-ai-agents";
const SEARCH_DEBOUNCE_MS = 260;
const SEMANTIC_SCORE_THRESHOLD = 0.42;

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
  searchDebounceTimer: null
};

const els = {
  shell: document.querySelector("#reader-shell"),
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
  return `
    <div class="math-block">
      ${block.label ? `<span class="math-label">${escapeHtml(block.label)}</span>` : ""}
      <code>${escapeHtml(block.latex ?? "")}</code>
    </div>
  `;
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

function renderChunks(reading) {
  els.chunkList.innerHTML = reading.chunks.map((chunk) => renderChunk(chunk, reading)).join("");
  observeChunks(reading);
}

function renderNoteSurface(surface, note) {
  surface.textContent = note ?? "";
  surface.classList.remove("is-changing");
}

function updateNoteSurface(chunkId, note) {
  const label = chunkId ? `Parallel note · ${chunkId}` : "Parallel note";
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  for (const surface of [els.noteSurface, els.mobileNoteSurface]) {
    surface.classList.add("is-changing");
    window.setTimeout(() => renderNoteSurface(surface, note), 90);
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
  const viewportCenter = window.innerHeight / 2;
  let best = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  let fallback = null;

  for (const chunk of chunks) {
    const rect = chunk.getBoundingClientRect();
    if (rect.top <= viewportCenter) fallback = chunk;
    if (rect.bottom < 0 || rect.top > window.innerHeight) continue;

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
  }
  state.scrollSpyHandler = () => updateActiveChunkFromViewport(reading);
  state.observer = new IntersectionObserver(() => {
    updateActiveChunkFromViewport(reading);
  }, {
    rootMargin: "-10% 0px -10% 0px",
    threshold: [0, 0.2, 0.5, 0.8]
  });
  document.querySelectorAll(".chunk").forEach((chunk) => state.observer.observe(chunk));
  window.addEventListener("scroll", state.scrollSpyHandler, { passive: true });
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
