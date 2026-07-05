const state = {
  data: null,
  currentModule: null,
  searchQuery: "",
};

const els = {
  shell: document.querySelector("#reader-shell"),
  nav: document.querySelector("#module-nav"),
  sectionLines: document.querySelector("#section-lines"),
  moduleHeader: document.querySelector("#module-header"),
  sectionList: document.querySelector("#section-list"),
  noteLabel: document.querySelector("#note-label"),
  noteSurface: document.querySelector("#note-surface"),
  mobileNoteLabel: document.querySelector("#mobile-note-label"),
  mobileNoteSurface: document.querySelector("#mobile-note-surface"),
  searchInput: document.querySelector("#global-search"),
  searchResults: document.querySelector("#search-results"),
  searchOverlay: document.querySelector("#search-overlay"),
  toggleTheme: document.querySelector("#toggle-theme"),
  toggleNote: document.querySelector("#toggle-note"),
  toggleLeftControls: document.querySelectorAll("[data-toggle-left]"),
  main: document.querySelector("#reader-main"),
};

function resolveUrl(path) {
  return new URL(path, window.location.href);
}

async function fetchJson(path) {
  const response = await fetch(resolveUrl(path));
  if (!response.ok) throw new Error(`Unable to load ${path}`);
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

function getInitialModuleId() {
  const url = new URL(window.location.href);
  const fromQuery = url.searchParams.get("module");
  const fromHash = url.hash.replace(/^#/, "");
  return fromQuery || fromHash || "overview";
}

function getModuleById(moduleId) {
  return state.data?.modules.find((module) => module.id === moduleId);
}

function getSection(module, title) {
  return module.sections?.[title] ?? "";
}

function setTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  document.body.dataset.theme = normalized;
  els.toggleTheme?.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
}

function renderModuleNav() {
  els.nav.innerHTML = "";
  for (const module of state.data.modules) {
    const button = document.createElement("button");
    button.className = "module-nav-item";
    button.type = "button";
    button.dataset.moduleId = module.id;
    button.setAttribute("aria-current", module.id === state.currentModule?.id ? "true" : "false");
    button.innerHTML = `
      <span class="module-nav-title">${escapeHtml(module.title)}</span>
      <span class="module-nav-progress">${escapeHtml(String(module.progress))}%</span>
      <span class="module-nav-meta">${escapeHtml(module.status)} · ${escapeHtml(module.priority)}</span>
    `;
    button.addEventListener("click", () => openModule(module.id));
    els.nav.append(button);
  }
}

function renderSectionRail(module) {
  els.sectionLines.innerHTML = "";
  const sectionTitles = Object.keys(module.sections ?? {});
  sectionTitles.forEach((sectionTitle, index) => {
    const button = document.createElement("button");
    button.className = `section-line${index === 0 ? " is-active" : ""}`;
    button.type = "button";
    button.setAttribute("aria-label", sectionTitle);
    button.addEventListener("click", () => {
      document.querySelector(`[data-section-title="${CSS.escape(sectionTitle)}"]`)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
    els.sectionLines.append(button);
  });
}

function renderCurrentModule() {
  const module = state.currentModule;
  const progress = Math.max(0, Math.min(100, Number(module.progress) || 0));
  els.moduleHeader.innerHTML = `
    <p class="module-kicker">${escapeHtml(state.data.project.title)} · ${escapeHtml(state.data.project.targetRole)}</p>
    <h1 class="module-title">${escapeHtml(module.title)}</h1>
    <p class="module-meta">${escapeHtml(module.status)} · ${escapeHtml(module.priority)} · Updated ${escapeHtml(module.lastUpdated)}</p>
    <div class="progress-meter" aria-label="模块进度">
      <span>${escapeHtml(String(progress))}% complete</span>
      <div class="progress-track"><span class="progress-fill" style="width: ${progress}%"></span></div>
    </div>
  `;

  const mainSections = ["目标", "当前状态", "核心知识", "任务", "时间线", "验收标准", "下一步"];
  const blocks = mainSections
    .map((title) => {
      const body = getSection(module, title);
      if (!body) return "";
      return `
        <article class="module-section" data-section-title="${escapeHtml(title)}">
          <h2>${escapeHtml(title)}</h2>
          <div class="section-body">${body}</div>
        </article>
      `;
    })
    .filter(Boolean)
    .join("");

  els.sectionList.innerHTML = blocks || `
    <article class="status-panel">
      <h2>${escapeHtml(module.title)}</h2>
      <p>这个模块还没有可展示内容。</p>
    </article>
  `;
}

function renderNotePanel() {
  const module = state.currentModule;
  const noteSections = ["资源", "反思", "面试表达"];
  const noteBlocks = noteSections
    .map((title) => {
      const body = getSection(module, title);
      if (!body) return "";
      return `
        <section class="note-block">
          <h3>${escapeHtml(title)}</h3>
          <div>${body}</div>
        </section>
      `;
    })
    .filter(Boolean)
    .join("");

  const label = `Parallel note · ${module.title}`;
  els.noteLabel.textContent = label;
  els.mobileNoteLabel.textContent = label;
  els.noteSurface.innerHTML = noteBlocks;
  els.mobileNoteSurface.innerHTML = noteBlocks;
}

function updateUrl(moduleId) {
  const url = new URL(window.location.href);
  url.searchParams.set("module", moduleId);
  url.hash = "";
  window.history.replaceState({}, "", url);
}

function openModule(moduleId, { syncUrl = true } = {}) {
  const nextModule = getModuleById(moduleId) ?? state.data.modules[0];
  state.currentModule = nextModule;
  if (syncUrl) updateUrl(nextModule.id);
  renderModuleNav();
  renderCurrentModule();
  renderNotePanel();
  renderSectionRail(nextModule);
  els.main.scrollTop = 0;
  els.shell.classList.remove("is-mobile-left-open");
}

function openSearchModal() {
  els.shell.classList.add("is-searching");
  els.searchResults.hidden = false;
}

function closeSearchModal() {
  els.shell.classList.remove("is-searching");
  if (!state.searchQuery) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
  }
}

function getSearchTerms(query) {
  return query.trim().split(/\s+/).filter(Boolean);
}

function highlightTerms(text, query) {
  const terms = getSearchTerms(query).map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (terms.length === 0) return escapeHtml(text);
  const pattern = new RegExp(`(${terms.join("|")})`, "gi");
  const exactPattern = new RegExp(`^(${terms.join("|")})$`, "i");
  return String(text ?? "")
    .split(pattern)
    .map((part) => exactPattern.test(part) ? `<mark class="result-highlight">${escapeHtml(part)}</mark>` : escapeHtml(part))
    .join("");
}

function getSnippet(module, query) {
  const searchText = module.searchText ?? "";
  const lower = searchText.toLowerCase();
  const term = getSearchTerms(query).find((item) => lower.includes(item.toLowerCase()));
  if (!term) return searchText.slice(0, 160);
  const index = lower.indexOf(term.toLowerCase());
  const start = Math.max(0, index - 56);
  const end = Math.min(searchText.length, index + term.length + 128);
  return `${start > 0 ? "..." : ""}${searchText.slice(start, end)}${end < searchText.length ? "..." : ""}`;
}

function getMatchedSection(module, query) {
  const terms = getSearchTerms(query).map((term) => term.toLowerCase());
  for (const [title, html] of Object.entries(module.sections ?? {})) {
    const haystack = `${title} ${html}`.toLowerCase();
    if (terms.some((term) => haystack.includes(term))) return title;
  }
  return "Module";
}

function runSearch(query) {
  state.searchQuery = query.trim();
  if (!state.searchQuery) {
    els.searchResults.hidden = true;
    els.searchResults.innerHTML = "";
    return;
  }

  const terms = getSearchTerms(state.searchQuery).map((term) => term.toLowerCase());
  const results = state.data.modules
    .map((module) => {
      const text = `${module.title} ${module.searchText}`.toLowerCase();
      const score = terms.reduce((sum, term) => sum + (text.includes(term) ? 1 : 0), 0);
      return { module, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 8);

  els.searchResults.hidden = false;
  if (results.length === 0) {
    els.searchResults.innerHTML = `<p class="result-empty">No results found</p>`;
    return;
  }

  els.searchResults.innerHTML = results
    .map(({ module }) => `
      <button class="result-item" type="button" data-module-id="${escapeHtml(module.id)}">
        <span>
          <span class="result-title">${highlightTerms(module.title, state.searchQuery)}</span>
          <span class="result-snippet">${highlightTerms(getSnippet(module, state.searchQuery), state.searchQuery)}</span>
        </span>
        <span class="result-section">${escapeHtml(getMatchedSection(module, state.searchQuery))}</span>
      </button>
    `)
    .join("");

  els.searchResults.querySelectorAll("[data-module-id]").forEach((button) => {
    button.addEventListener("click", () => {
      openModule(button.dataset.moduleId);
      closeSearchModal();
    });
  });
}

function bindEvents() {
  els.toggleTheme.addEventListener("click", () => {
    setTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
  });

  els.toggleNote.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 860px)").matches) {
      els.shell.classList.toggle("is-mobile-note-open");
      return;
    }
    els.shell.classList.toggle("is-note-collapsed");
  });

  els.toggleLeftControls.forEach((button) => {
    button.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 860px)").matches) {
        els.shell.classList.toggle("is-mobile-left-open");
        return;
      }
      els.shell.classList.toggle("is-left-collapsed");
    });
  });

  els.searchInput.addEventListener("focus", openSearchModal);
  els.searchInput.addEventListener("input", () => runSearch(els.searchInput.value));
  els.searchOverlay.addEventListener("click", closeSearchModal);

  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearchModal();
      els.searchInput.focus();
    }
    if (event.key === "Escape") {
      closeSearchModal();
      els.shell.classList.remove("is-mobile-left-open", "is-mobile-note-open");
    }
  });
}

async function init() {
  try {
    state.data = await fetchJson("roadmap/roadmap-data.json");
    bindEvents();
    setTheme("light");
    openModule(getInitialModuleId(), { syncUrl: false });
  } catch (error) {
    els.sectionList.innerHTML = `
      <article class="status-panel">
        <h2>路线图加载失败</h2>
        <p>${escapeHtml(error.message)}</p>
      </article>
    `;
  }
}

init();
