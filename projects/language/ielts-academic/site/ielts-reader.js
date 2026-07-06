const roots = {
  dashboard: document.querySelector('[data-render="dashboard"]'),
  swimlane: document.querySelector('[data-render="swimlane"]'),
  errors: document.querySelector('[data-render="errors"]'),
  notes: document.querySelector('[data-render="notes"]'),
  journal: document.querySelector('[data-render="journal"]'),
  promptLibrary: document.querySelector('[data-render="prompt-library"]'),
  validation: document.querySelector('[data-render="validation"]'),
};

async function fetchJson(path) {
  const response = await fetch(new URL(path, window.location.href));
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

function renderList(items, getBody) {
  if (!Array.isArray(items) || items.length === 0) {
    return '<p class="empty-state">No entries yet.</p>';
  }

  return `<div class="stack">${items.map((item) => `<article class="list-card">${getBody(item)}</article>`).join("")}</div>`;
}

function renderDashboard(data) {
  const profile = data.scoreProfile ?? {};
  const history = Array.isArray(data.scoreHistory) ? data.scoreHistory : [];
  const latest = history.at(-1);
  roots.dashboard.innerHTML = `
    <div class="metric-grid">
      <article class="metric-card">
        <p class="metric-label">Target</p>
        <p class="metric-value">${escapeHtml(profile.target ?? "Overall 8.0")}</p>
      </article>
      <article class="metric-card">
        <p class="metric-label">Current estimate</p>
        <p class="metric-value">${escapeHtml(latest?.overall ?? "Unverified")}</p>
      </article>
      <article class="metric-card">
        <p class="metric-label">Evidence basis</p>
        <p class="metric-value">${escapeHtml(profile.evidenceBasis ?? "Pending")}</p>
      </article>
      <article class="metric-card">
        <p class="metric-label">Confidence</p>
        <p class="metric-value">${escapeHtml(profile.confidence ?? "Low")}</p>
      </article>
    </div>
  `;
}

function renderSwimlane(data) {
  roots.swimlane.innerHTML = renderList(data.checkpoints, (checkpoint) => `
    <p class="card-kicker">${escapeHtml(checkpoint.week)}</p>
    <strong>${escapeHtml(checkpoint.title)}</strong>
    <p>${escapeHtml(checkpoint.focus)}</p>
  `).replace('class="stack"', 'class="swimlane-grid"');
}

function renderErrors(data) {
  roots.errors.innerHTML = renderList(data.errorLog, (error) => `
    <p class="card-kicker">${escapeHtml(error.skill)}</p>
    <strong>${escapeHtml(error.pattern)}</strong>
    <p class="error-priority">${escapeHtml(error.priority)}</p>
    <p>${escapeHtml(error.nextAction)}</p>
  `).replace('class="stack"', 'class="error-board"');
}

function renderNotes(data) {
  roots.notes.innerHTML = renderList(data.notes, (note) => `
    <p class="card-kicker">${escapeHtml(note.source)}</p>
    <strong>${escapeHtml(note.title)}</strong>
    <p>${escapeHtml(note.body)}</p>
  `);
}

function renderJournal(data) {
  roots.journal.innerHTML = renderList(data.journal, (entry) => `
    <p class="card-kicker">${escapeHtml(entry.date)}</p>
    <strong>${escapeHtml(entry.title)}</strong>
    <p>${escapeHtml(entry.body)}</p>
  `);
}

function renderPromptLibrary(data) {
  roots.promptLibrary.innerHTML = renderList(data.promptLibrary, (prompt) => `
    <p class="card-kicker">${escapeHtml(prompt.mode)}</p>
    <strong>${escapeHtml(prompt.title)}</strong>
    <p>${escapeHtml(prompt.path)}</p>
  `);
}

function renderValidation(data) {
  roots.validation.innerHTML = renderList(data.validation, (check) => `
    <p class="card-kicker">${escapeHtml(check.type)}</p>
    <strong>${escapeHtml(check.title)}</strong>
    <p>${escapeHtml(check.status)}</p>
  `);
}

function render(data) {
  renderDashboard(data);
  renderSwimlane(data);
  renderErrors(data);
  renderNotes(data);
  renderJournal(data);
  renderPromptLibrary(data);
  renderValidation(data);
}

fetchJson("site/ielts-data.json")
  .then(render)
  .catch((error) => {
    roots.dashboard.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`;
  });
