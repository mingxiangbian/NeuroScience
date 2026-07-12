export const ANNOTATION_CATEGORIES = [
  { id: "understanding", label: "我的理解" },
  { id: "question", label: "待解决问题" },
  { id: "reflection", label: "反思" },
  { id: "resource", label: "补充资料" },
];

const CATEGORY_LABELS = new Map([
  ["highlight", "高亮"],
  ...ANNOTATION_CATEGORIES.map((item) => [item.id, item.label]),
]);

function createEmptyStore() {
  return { version: 1, items: [] };
}

export function parseStoredAnnotations(raw) {
  if (raw === null) return { store: createEmptyStore(), canPersist: true };
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.items)) {
      return { store: createEmptyStore(), canPersist: false };
    }
    return {
      store: {
        version: 1,
        items: parsed.items
          .filter((item) => item && item.projectId === "foundations")
          .map(normalizeAnnotation),
      },
      canPersist: true,
    };
  } catch {
    return { store: createEmptyStore(), canPersist: false };
  }
}

export function getAnnotationArchiveNoteId(moduleId) {
  return `${moduleId}-legacy-annotations`;
}

function getKnowledgeArticleText(article) {
  return normalizeComparableText([
    article?.title,
    article?.intro,
    ...(article?.sections ?? []).flatMap((section) => [section?.title, section?.body]),
  ].filter(Boolean).join(" "));
}

function normalizeComparableText(value) {
  const namedEntities = {
    amp: "&",
    apos: "'",
    gt: ">",
    lt: "<",
    nbsp: " ",
    quot: '"',
  };
  return String(value ?? "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&#(x?[0-9a-f]+);/gi, (_, code) => (
      String.fromCodePoint(Number.parseInt(code.replace(/^x/i, ""), /^x/i.test(code) ? 16 : 10))
    ))
    .replace(/&([a-z]+);/gi, (entity, name) => namedEntities[name.toLowerCase()] ?? entity)
    .replace(/\s+/g, " ")
    .trim();
}

export function migrateLegacyAnnotations(store, modules) {
  const source = store && typeof store === "object" ? store : {};
  const moduleById = new Map((modules ?? []).map((module) => [module.id, module]));
  const items = Array.isArray(source.items) ? source.items : [];

  return {
    ...source,
    version: 1,
    items: items.map((annotation) => {
      if (!annotation || typeof annotation !== "object") return annotation;
      const module = moduleById.get(annotation.moduleId);
      const articles = module?.knowledgeNotes ?? [];
      if (articles.some((article) => article.id === annotation.noteId)) return annotation;
      const archiveNoteId = getAnnotationArchiveNoteId(annotation.moduleId);
      if (annotation.noteId === archiveNoteId) return annotation;

      const selectedText = normalizeComparableText(annotation.selectedText);
      const matchingArticles = selectedText
        ? articles.filter((article) => getKnowledgeArticleText(article).includes(selectedText))
        : [];
      if (matchingArticles.length === 1) {
        return {
          ...annotation,
          noteId: matchingArticles[0].id,
          legacyNoteId: annotation.legacyNoteId ?? annotation.noteId,
        };
      }

      return {
        ...annotation,
        noteId: archiveNoteId,
        legacyNoteId: annotation.legacyNoteId ?? annotation.noteId,
        highlightActive: false,
      };
    }),
  };
}

export function normalizeAnnotation(annotation) {
  const source = annotation && typeof annotation === "object" ? annotation : {};
  const validCategory = ANNOTATION_CATEGORIES.some((item) => item.id === source.category);
  const category = source.mode === "highlight" && !source.note
    ? "highlight"
    : validCategory ? source.category : "understanding";
  return { ...source, category };
}

export function groupAnnotations(annotations) {
  const normalized = annotations.map(normalizeAnnotation);
  const orderedKeys = ["highlight", ...ANNOTATION_CATEGORIES.map((item) => item.id)];
  return orderedKeys
    .map((key) => ({
      key,
      label: CATEGORY_LABELS.get(key),
      items: normalized.filter((item) => item.category === key),
    }))
    .filter((group) => group.items.length > 0);
}
