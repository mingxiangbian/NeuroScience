export const ANNOTATION_CATEGORIES = [
  { id: "understanding", label: "我的理解" },
  { id: "question", label: "待解决问题" },
  { id: "reflection", label: "反思" },
  { id: "resource", label: "补充资料" },
];

export const ANNOTATION_STORE_VERSION = 2;

const ANCHOR_CONTEXT_LENGTH = 32;

const CATEGORY_LABELS = new Map([
  ["highlight", "高亮"],
  ...ANNOTATION_CATEGORIES.map((item) => [item.id, item.label]),
]);

function createEmptyStore() {
  return { version: ANNOTATION_STORE_VERSION, items: [] };
}

export function parseStoredAnnotations(raw, projectId = "foundations") {
  if (raw === null) return { store: createEmptyStore(), canPersist: true };
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.items)) {
      return { store: createEmptyStore(), canPersist: false };
    }
    return {
      store: {
        version: ANNOTATION_STORE_VERSION,
        items: parsed.items
          .filter((item) => item && item.projectId === projectId)
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

export function getAnnotationContextId(annotation) {
  if (typeof annotation === "string") return annotation.trim();
  const source = annotation && typeof annotation === "object" ? annotation : {};
  const contextId = String(source.contextId ?? "").trim();
  if (contextId) return contextId;
  return String(source.noteId ?? "").trim();
}

function normalizeSelectionText(value) {
  return String(value ?? "").trim();
}

function toMatchIndex(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function getOccurrenceStarts(text, selectedText) {
  if (!selectedText) return [];
  const starts = [];
  let start = text.indexOf(selectedText);
  while (start !== -1) {
    starts.push(start);
    start = text.indexOf(selectedText, start + selectedText.length);
  }
  return starts;
}

function normalizeAnchor(annotation) {
  const source = annotation && typeof annotation === "object" ? annotation : {};
  const sourceAnchor = source.anchor && typeof source.anchor === "object" ? source.anchor : {};
  const selectedText = normalizeSelectionText(sourceAnchor.selectedText ?? source.selectedText);
  if (!selectedText) return null;
  return {
    ...sourceAnchor,
    selectedText,
    matchIndex: toMatchIndex(sourceAnchor.matchIndex ?? source.matchIndex),
    prefix: String(sourceAnchor.prefix ?? source.prefix ?? ""),
    suffix: String(sourceAnchor.suffix ?? source.suffix ?? ""),
  };
}

export function createAnnotationAnchor({
  contextId,
  contextText,
  selectedText,
  selectionStart,
} = {}) {
  const stableContextId = getAnnotationContextId({ contextId });
  const text = String(contextText ?? "");
  const rawSelectedText = String(selectedText ?? "");
  const normalizedSelectedText = normalizeSelectionText(rawSelectedText);
  if (!stableContextId || !normalizedSelectedText) return null;

  const rawSelectionStart = Number(selectionStart);
  if (!Number.isInteger(rawSelectionStart) || rawSelectionStart < 0) return null;
  const leadingWhitespace = rawSelectedText.length - rawSelectedText.trimStart().length;
  const startOffset = rawSelectionStart + leadingWhitespace;
  const endOffset = startOffset + normalizedSelectedText.length;
  if (text.slice(startOffset, endOffset) !== normalizedSelectedText) return null;

  const occurrenceStarts = getOccurrenceStarts(text, normalizedSelectedText);
  const matchIndex = occurrenceStarts.indexOf(startOffset);
  if (matchIndex < 0) return null;

  return {
    contextId: stableContextId,
    anchor: {
      selectedText: normalizedSelectedText,
      matchIndex,
      prefix: text.slice(Math.max(0, startOffset - ANCHOR_CONTEXT_LENGTH), startOffset),
      suffix: text.slice(endOffset, endOffset + ANCHOR_CONTEXT_LENGTH),
    },
  };
}

function getCommonPrefixLength(left, right) {
  const limit = Math.min(left.length, right.length);
  let length = 0;
  while (length < limit && left[length] === right[length]) length += 1;
  return length;
}

function getCommonSuffixLength(left, right) {
  const limit = Math.min(left.length, right.length);
  let length = 0;
  while (length < limit && left[left.length - 1 - length] === right[right.length - 1 - length]) {
    length += 1;
  }
  return length;
}

export function resolveAnnotationAnchor(contextText, annotation) {
  const text = String(contextText ?? "");
  const anchor = normalizeAnchor(annotation);
  if (!anchor) return null;
  const occurrenceStarts = getOccurrenceStarts(text, anchor.selectedText);
  if (occurrenceStarts.length === 0) return null;

  let resolvedIndex = Math.min(anchor.matchIndex, occurrenceStarts.length - 1);
  if (anchor.prefix || anchor.suffix) {
    const scored = occurrenceStarts.map((startOffset, matchIndex) => {
      const endOffset = startOffset + anchor.selectedText.length;
      const prefix = text.slice(Math.max(0, startOffset - anchor.prefix.length), startOffset);
      const suffix = text.slice(endOffset, endOffset + anchor.suffix.length);
      return {
        matchIndex,
        score: getCommonSuffixLength(anchor.prefix, prefix) + getCommonPrefixLength(anchor.suffix, suffix),
      };
    });
    const highestScore = Math.max(...scored.map((candidate) => candidate.score));
    const bestMatches = scored.filter((candidate) => candidate.score === highestScore);
    if (highestScore > 0 && bestMatches.length === 1) {
      resolvedIndex = bestMatches[0].matchIndex;
    } else if (bestMatches.some((candidate) => candidate.matchIndex === anchor.matchIndex)) {
      resolvedIndex = anchor.matchIndex;
    }
  }

  const startOffset = occurrenceStarts[resolvedIndex];
  return {
    startOffset,
    endOffset: startOffset + anchor.selectedText.length,
    selectedText: anchor.selectedText,
    matchIndex: resolvedIndex,
  };
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

function getArticleAnchor(annotation, article) {
  const contextText = getKnowledgeArticleText(article);
  const selectedText = normalizeComparableText(annotation.selectedText);
  if (!selectedText) return null;
  const occurrenceStarts = getOccurrenceStarts(contextText, selectedText);
  if (occurrenceStarts.length === 0) return null;
  const requestedMatchIndex = toMatchIndex(annotation.anchor?.matchIndex ?? annotation.matchIndex);
  const matchIndex = requestedMatchIndex < occurrenceStarts.length ? requestedMatchIndex : 0;
  return createAnnotationAnchor({
    contextId: article.id,
    contextText,
    selectedText,
    selectionStart: occurrenceStarts[matchIndex],
  });
}

function moveAnnotationToArticle(annotation, article, legacyNoteId) {
  const anchored = getArticleAnchor(annotation, article);
  return {
    ...annotation,
    noteId: article.id,
    contextId: article.id,
    ...(legacyNoteId ? { legacyNoteId } : {}),
    ...(anchored ? { anchor: anchored.anchor } : {}),
  };
}

export function migrateLegacyAnnotations(store, modules) {
  const source = store && typeof store === "object" ? store : {};
  const moduleById = new Map((modules ?? []).map((module) => [module.id, module]));
  const items = Array.isArray(source.items) ? source.items : [];

  return {
    ...source,
    version: ANNOTATION_STORE_VERSION,
    items: items.map((annotation) => {
      if (!annotation || typeof annotation !== "object") return annotation;
      const normalized = normalizeAnnotation(annotation);
      const module = moduleById.get(normalized.moduleId);
      const articles = module?.knowledgeNotes ?? [];
      const archiveNoteId = getAnnotationArchiveNoteId(normalized.moduleId);
      if (normalized.noteId === archiveNoteId || normalized.contextId === archiveNoteId) {
        return {
          ...normalized,
          noteId: archiveNoteId,
          contextId: archiveNoteId,
        };
      }

      const currentArticle = articles.find((article) => (
        article.id === normalized.contextId || article.id === normalized.noteId
      ));
      if (currentArticle) return moveAnnotationToArticle(normalized, currentArticle);

      const hasNativeSectionContext = Boolean(normalized.contextId) && !normalized.noteId;
      if (hasNativeSectionContext) return normalized;

      const selectedText = normalizeComparableText(normalized.selectedText);
      const matchingArticles = selectedText
        ? articles.filter((article) => getKnowledgeArticleText(article).includes(selectedText))
        : [];
      if (matchingArticles.length === 1) {
        return moveAnnotationToArticle(
          normalized,
          matchingArticles[0],
          normalized.legacyNoteId ?? normalized.noteId,
        );
      }

      return {
        ...normalized,
        noteId: archiveNoteId,
        contextId: archiveNoteId,
        legacyNoteId: normalized.legacyNoteId ?? normalized.noteId,
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
  const contextId = getAnnotationContextId(source);
  const anchor = normalizeAnchor(source);
  return {
    ...source,
    category,
    ...(contextId ? { contextId } : {}),
    ...(anchor ? { anchor } : {}),
  };
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
