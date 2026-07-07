import { escapeHtml, slugify, stripHtml, toList } from "./reader-utils.js";

export function makeKnowledgeNote(id, title, body, groups = [], meta = {}) {
  return {
    id,
    title,
    body,
    groups,
    meta,
  };
}

export function buildSearchEntries(moduleId, moduleTitle, sections, sectionIds, knowledgeNotes) {
  const sectionEntries = Object.entries(sections).map(([sectionTitle, body]) => ({
    id: sectionIds[sectionTitle],
    moduleId,
    moduleTitle,
    sectionTitle,
    text: `${sectionTitle} ${stripHtml(body)}`,
  }));
  const noteEntries = toList(knowledgeNotes).map((note) => ({
    id: note.id,
    moduleId,
    moduleTitle,
    sectionTitle: note.title,
    text: `${note.title} ${stripHtml(note.body)} ${toList(note.groups).map((group) => stripHtml(group.body)).join(" ")}`,
  }));
  return [...sectionEntries, ...noteEntries];
}

export function createReaderModule(config) {
  const sections = config.sections ?? {};
  const sectionIds = {};
  const sectionNotes = {};
  for (const sectionTitle of Object.keys(sections)) {
    const sectionId = `${config.id}-${slugify(sectionTitle)}`;
    sectionIds[sectionTitle] = sectionId;
    sectionNotes[sectionId] = makeKnowledgeNote(sectionId, sectionTitle, sections[sectionTitle]);
  }
  const knowledgeNotes = toList(config.knowledgeNotes);
  const searchEntries = buildSearchEntries(config.id, config.title, sections, sectionIds, knowledgeNotes);

  return {
    id: config.id,
    title: config.title,
    status: config.status ?? "ready",
    priority: config.priority ?? "core",
    learningProgress: config.learningProgress ?? 0,
    lastUpdated: config.lastUpdated ?? "",
    sections,
    sectionIds,
    sectionNotes,
    knowledgeNotes,
    searchEntries,
    searchText: searchEntries.map((entry) => `${entry.sectionTitle} ${entry.text}`).join(" "),
  };
}

export function renderModuleSafely(moduleId, title, renderBody) {
  try {
    return renderBody();
  } catch (error) {
    console.error(`Unable to render IELTS module ${moduleId}`, error);
    return `
      <article class="status-panel module-error" data-module-error="${escapeHtml(moduleId)}">
        <h2>${escapeHtml(title)} 加载失败</h2>
        <p>这个模块暂时无法渲染。请检查 site/ielts-data.json 或 build output。</p>
      </article>
    `;
  }
}
