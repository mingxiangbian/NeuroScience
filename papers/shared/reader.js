const PROJECT_ID = "brain-memory-for-ai-agents";

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
  observer: null
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
  searchInput: document.querySelector("#global-search"),
  searchResults: document.querySelector("#search-results"),
  toggleLeft: document.querySelector("#toggle-left"),
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
  return reading?.paperData.sections.find((section) => section.id === sectionId)?.title ?? "Section";
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
        searchText: `${chunk.sourceText ?? ""}\n${chunk.zhExplanation ?? ""}`
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
  sections.forEach((section, index) => {
    const button = document.createElement("button");
    button.className = "section-line";
    button.type = "button";
    button.dataset.sectionId = section.id;
    button.innerHTML = `<span class="section-tooltip">${escapeHtml(section.title)}</span>`;
    button.addEventListener("mouseenter", () => markSectionNeighbors(index));
    button.addEventListener("mouseleave", () => markSectionNeighbors(-1));
    button.addEventListener("click", () => {
      const firstChunk = document.querySelector(`.chunk[data-section-id="${CSS.escape(section.id)}"]`);
      firstChunk?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    els.sectionLines.append(button);
  });
}

function markSectionNeighbors(activeIndex) {
  [...els.sectionLines.children].forEach((line, index) => {
    line.classList.toggle("is-neighbor", Math.abs(index - activeIndex) === 1);
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
    .map((section) => `<button class="section-chip" type="button" data-section-id="${escapeHtml(section.id)}">${escapeHtml(section.title)}</button>`)
    .join("");

  els.paperHeader.innerHTML = `
    <p class="paper-kicker">${escapeHtml(paperData.category ?? "Paper")}</p>
    <h1 class="paper-title">${escapeHtml(paperData.title ?? state.currentPaper.title)}</h1>
    <p class="paper-meta">${escapeHtml([paperData.authors, paperData.year].filter(Boolean).join(" · "))}</p>
    ${paperData.relation ? `<p class="paper-meta">${escapeHtml(paperData.relation)}</p>` : ""}
    ${paperData.description ? `<p class="paper-meta">${escapeHtml(paperData.description)}</p>` : ""}
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
  return renderFigure(figure, block.relation);
}

function renderFigure(figure, relation = "supporting") {
  if (!figure) return "";
  const hasFile = Boolean(figure.file);
  return `
    <figure class="figure-frame" data-relation="${escapeHtml(relation)}">
      ${hasFile ? `<img src="${escapeHtml(figure.file)}" alt="${escapeHtml(figure.label ?? "Figure")}">` : `<div class="figure-placeholder">${escapeHtml(figure.label ?? "Figure pending extraction")}</div>`}
      <figcaption class="figure-caption">${escapeHtml(figure.caption ?? "")}</figcaption>
    </figure>
  `;
}

function renderChunk(chunk, reading) {
  const sectionTitle = getSectionTitle(reading, chunk.sectionId);
  const blocks = chunk.blocks?.length
    ? chunk.blocks.map((block) => renderBlock(block, reading)).join("")
    : `<p class="source-paragraph">${escapeHtml(chunk.sourceText)}</p>`;
  const supportingFigures = (chunk.figureRefs ?? [])
    .map((ref) => renderFigure(reading.figures.get(ref.id), ref.relation))
    .join("");
  return `
    <article class="chunk" id="${escapeHtml(chunk.id)}" data-chunk-id="${escapeHtml(chunk.id)}" data-section-id="${escapeHtml(chunk.sectionId)}">
      <p class="chunk-heading">${escapeHtml(sectionTitle)} · ${escapeHtml(chunk.id)}</p>
      <div class="chunk-source-card">${blocks}${supportingFigures}</div>
      <div class="chunk-divider"></div>
      <div class="chunk-explanation">${chunk.zhExplanation ? `<p>${escapeHtml(chunk.zhExplanation)}</p>` : ""}</div>
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

function observeChunks(reading) {
  state.observer?.disconnect();
  state.observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible) setActiveChunk(reading, visible.target.dataset.chunkId);
  }, {
    rootMargin: "-18% 0px -62% 0px",
    threshold: [0.15, 0.35, 0.6]
  });
  document.querySelectorAll(".chunk").forEach((chunk) => state.observer.observe(chunk));
  setActiveChunk(reading, reading.chunks[0]?.id);
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

function runSearch(query) {
  const trimmed = query.trim();
  els.shell.classList.toggle("is-searching", Boolean(trimmed));
  if (!trimmed) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
    return;
  }
  const queryVector = embedQuery(trimmed);
  const results = state.searchItems
    .map((item) => ({ ...item, score: cosineSimilarity(queryVector, item.vector) }))
    .sort((left, right) => right.score - left.score)
    .slice(0, 8)
    .filter((item) => item.score > 0.08);

  els.searchResults.hidden = false;
  if (results.length === 0) {
    els.searchResults.innerHTML = `<div class="result-item"><span class="result-title">no found</span></div>`;
    return;
  }
  els.searchResults.innerHTML = results.map((item) => {
    const current = item.paper.id === state.currentPaper?.id;
    const title = current ? getSectionTitle(item.reading, item.chunk.sectionId) : item.paper.shortTitle;
    const snippet = item.chunk.zhExplanation || item.chunk.sourceText;
    return `
      <button class="result-item" type="button" data-paper-id="${escapeHtml(item.paper.id)}" data-chunk-id="${escapeHtml(item.chunk.id)}">
        <span class="result-title">${escapeHtml(title)}</span>
        <span class="result-snippet">${escapeHtml(snippet.slice(0, 180))}</span>
      </button>
    `;
  }).join("");
  els.searchResults.querySelectorAll(".result-item[data-paper-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await openPaper(button.dataset.paperId);
      document.getElementById(button.dataset.chunkId)?.scrollIntoView({ behavior: "smooth", block: "start" });
      els.searchResults.hidden = true;
      els.shell.classList.remove("is-searching");
    });
  });
}

function bindControls() {
  syncResponsiveState();
  els.toggleLeft.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 860px)").matches) {
      els.shell.classList.toggle("is-mobile-left-open");
      els.shell.classList.remove("is-left-collapsed");
      return;
    }
    els.shell.classList.toggle("is-left-collapsed");
  });
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
  els.searchInput.addEventListener("input", () => runSearch(els.searchInput.value));
  els.searchInput.addEventListener("focus", () => {
    if (els.searchInput.value.trim()) els.shell.classList.add("is-searching");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      els.searchResults.hidden = true;
      els.shell.classList.remove("is-searching", "is-mobile-left-open", "is-mobile-note-open");
    }
  });
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
