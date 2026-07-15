import assert from "node:assert/strict";
import * as annotationModel from "../projects/foundations/roadmap/annotation-model.js";

const {
  ANNOTATION_STORE_VERSION,
  ANNOTATION_CATEGORIES,
  createAnnotationAnchor,
  getAnnotationArchiveNoteId,
  getAnnotationContextId,
  groupAnnotations,
  migrateLegacyAnnotations,
  normalizeAnnotation,
  parseStoredAnnotations,
  resolveAnnotationAnchor,
} = annotationModel;

assert.equal(ANNOTATION_STORE_VERSION, 2, "annotation storage should expose the v2 schema version");
assert.equal(typeof migrateLegacyAnnotations, "function", "annotation model should export a pure legacy migration helper");
assert.equal(typeof getAnnotationArchiveNoteId, "function", "annotation model should export stable archive note ids");
assert.equal(typeof getAnnotationContextId, "function", "annotation model should expose v1-compatible context ids");
assert.equal(typeof createAnnotationAnchor, "function", "annotation model should create pure text anchors");
assert.equal(typeof resolveAnnotationAnchor, "function", "annotation model should resolve repeated text anchors");
assert.equal(typeof parseStoredAnnotations, "function", "annotation model should expose recoverable storage parsing");

const malformedStore = parseStoredAnnotations("{not-json");
assert.equal(malformedStore.canPersist, false, "malformed storage should not be overwritten by an empty fallback");
assert.deepEqual(malformedStore.store, { version: 2, items: [] });

const emptyStringStore = parseStoredAnnotations("");
assert.equal(emptyStringStore.canPersist, false, "a present empty-string payload is malformed, not a missing store");

const invalidStore = parseStoredAnnotations(JSON.stringify({ version: 1, items: "not-an-array" }));
assert.equal(invalidStore.canPersist, false, "invalid storage shapes should remain recoverable");

const validStore = parseStoredAnnotations(JSON.stringify({
  version: 1,
  items: [
    { id: "keep", projectId: "foundations", mode: "note", note: "保留" },
    { id: "ignore", projectId: "another-project", mode: "note", note: "忽略" },
  ],
}));
assert.equal(validStore.canPersist, true);
assert.equal(validStore.store.version, 2);
assert.deepEqual(validStore.store.items.map((item) => item.id), ["keep"]);

const missingStore = parseStoredAnnotations(null);
assert.equal(missingStore.canPersist, true, "a genuinely missing store may initialize normally");
assert.deepEqual(missingStore.store, { version: 2, items: [] });

const financeStore = parseStoredAnnotations(JSON.stringify({
  version: 1,
  items: [
    { id: "foundations-note", projectId: "foundations", mode: "note", note: "隔离" },
    { id: "finance-note", projectId: "finance", mode: "note", note: "保留" },
  ],
}), "finance");
assert.deepEqual(financeStore.store.items.map((item) => item.id), ["finance-note"], "storage parsing should isolate the active project");

assert.equal(
  getAnnotationContextId({ contextId: "  risk-allocation-overview  ", noteId: "legacy-note" }),
  "risk-allocation-overview",
  "explicit v2 context ids should win and normalize boundary whitespace",
);
assert.equal(
  getAnnotationContextId({ noteId: "coding-单调队列" }),
  "coding-单调队列",
  "v1 note ids should remain stable context ids",
);

const v1StorageItem = {
  id: "legacy-v1-storage",
  projectId: "finance",
  moduleId: "risk-allocation",
  noteId: "risk-allocation-old-note",
  selectedText: "  重复文本\n",
  matchIndex: 1,
  mode: "note",
  category: "reflection",
  note: "保留旧正文",
  highlightActive: true,
  createdAt: "2026-07-01T08:00:00.000Z",
  updatedAt: "2026-07-02T09:00:00.000Z",
};
const parsedV1Store = parseStoredAnnotations(JSON.stringify({ version: 1, items: [v1StorageItem] }), "finance");
const parsedV1Item = parsedV1Store.store.items[0];
assert.equal(parsedV1Store.store.version, 2);
assert.equal(parsedV1Item.contextId, v1StorageItem.noteId, "v1 noteId should populate the v2 context id");
assert.equal(parsedV1Item.selectedText, v1StorageItem.selectedText, "migration should retain the original quote field verbatim");
assert.equal(parsedV1Item.note, v1StorageItem.note, "migration should retain written note content");
assert.equal(parsedV1Item.createdAt, v1StorageItem.createdAt, "migration should retain creation timestamps");
assert.equal(parsedV1Item.updatedAt, v1StorageItem.updatedAt, "migration should retain update timestamps");
assert.deepEqual(parsedV1Item.anchor, {
  selectedText: "重复文本",
  matchIndex: 1,
  prefix: "",
  suffix: "",
}, "v1 flat anchors should gain a normalized v2 anchor without deleting legacy fields");

const repeatedContextText = "前文  重复文本  中段  重复文本  后文";
const rawRepeatedSelection = "  重复文本  ";
const repeatedSelectionStart = repeatedContextText.lastIndexOf(rawRepeatedSelection);
const repeatedAnchorRecord = createAnnotationAnchor({
  contextId: "risk-allocation__section__examples",
  contextText: repeatedContextText,
  selectedText: rawRepeatedSelection,
  selectionStart: repeatedSelectionStart,
});
assert.equal(repeatedAnchorRecord.contextId, "risk-allocation__section__examples");
assert.equal(repeatedAnchorRecord.anchor.selectedText, "重复文本", "selection boundary whitespace should not enter the anchor quote");
assert.equal(repeatedAnchorRecord.anchor.matchIndex, 1, "the second same-block occurrence should retain its occurrence index");
assert.equal(repeatedAnchorRecord.anchor.prefix.endsWith("中段  "), true);
assert.equal(repeatedAnchorRecord.anchor.suffix.startsWith("  后文"), true);

assert.deepEqual(resolveAnnotationAnchor(repeatedContextText, repeatedAnchorRecord), {
  startOffset: repeatedContextText.lastIndexOf("重复文本"),
  endOffset: repeatedContextText.lastIndexOf("重复文本") + "重复文本".length,
  selectedText: "重复文本",
  matchIndex: 1,
}, "an unchanged context should resolve the intended duplicate occurrence");

const contextWithInsertedDuplicate = "前文  重复文本  中段 插入 重复文本  中段  重复文本  后文";
assert.equal(
  resolveAnnotationAnchor(contextWithInsertedDuplicate, repeatedAnchorRecord).startOffset,
  contextWithInsertedDuplicate.lastIndexOf("重复文本"),
  "prefix and suffix should recover the intended quote when a new duplicate changes matchIndex",
);
assert.equal(
  resolveAnnotationAnchor("重复文本 / 重复文本", { selectedText: "重复文本", matchIndex: 1 }).startOffset,
  "重复文本 / ".length,
  "v1 flat anchors should still resolve repeated text by matchIndex",
);
assert.equal(createAnnotationAnchor({
  contextId: "risk-allocation__section__examples",
  contextText: "只有空白",
  selectedText: " \n ",
  selectionStart: 0,
}), null, "whitespace-only selections should not create anchors");

assert.deepEqual(ANNOTATION_CATEGORIES.map((item) => item.id), [
  "understanding",
  "question",
  "reflection",
  "resource",
]);

const legacyNote = normalizeAnnotation({ id: "n1", mode: "note", note: "旧笔记" });
assert.equal(legacyNote.category, "understanding");

const pureHighlight = normalizeAnnotation({ id: "h1", mode: "highlight", note: "" });
assert.equal(pureHighlight.category, "highlight");

const groups = groupAnnotations([
  pureHighlight,
  legacyNote,
  normalizeAnnotation({ id: "q1", mode: "note", note: "为什么？", category: "question" }),
]);
assert.deepEqual(groups.map(({ key, label }) => [key, label]), [
  ["highlight", "高亮"],
  ["understanding", "我的理解"],
  ["question", "待解决问题"],
]);

const modules = [
  {
    id: "coding",
    knowledgeNotes: [
      {
        id: "coding-deque-stack-与-queue",
        title: "deque、stack 与 queue",
        intro: "Stack、queue 和 deque 的区别在于允许从哪一端加入和取出。",
        sections: [{ body: "Queue 遵循先进先出，Python 中通常用 <code>list.append()</code> 入栈。" }],
      },
      {
        id: "coding-单调队列",
        title: "单调队列",
        intro: "单调队列保存仍可能在未来成为答案的候选索引。",
        sections: [{ body: "队首始终是当前窗口最大值。" }],
      },
    ],
  },
  {
    id: "evals-debugging",
    knowledgeNotes: [
      {
        id: "evals-debugging-eval-case-的六层结构",
        title: "Eval Case 的六层结构",
        intro: "共享文本",
        sections: [],
      },
      {
        id: "evals-debugging-benchmark-与-agent-behavior-eval",
        title: "Benchmark 与 Agent Behavior Eval",
        intro: "共享文本",
        sections: [],
      },
    ],
  },
];

const currentAnnotation = {
  id: "current",
  projectId: "foundations",
  moduleId: "coding",
  noteId: "coding-单调队列",
  selectedText: "候选索引",
  mode: "highlight",
  note: "",
  highlightActive: true,
};
const recoverableLegacyNote = {
  id: "recoverable",
  projectId: "foundations",
  moduleId: "coding",
  noteId: "coding-python-standards",
  selectedText: "Python 中通常用 list.append() 入栈",
  matchIndex: 2,
  mode: "note",
  category: "question",
  note: "为什么使用 deque？",
  highlightActive: true,
  createdAt: "2026-07-05T08:00:00.000Z",
  updatedAt: "2026-07-06T09:00:00.000Z",
};
const archivedHighlight = {
  id: "archived-highlight",
  projectId: "foundations",
  moduleId: "evals-debugging",
  noteId: "evals-debugging-old-resource",
  selectedText: "共享文本",
  matchIndex: 0,
  mode: "highlight",
  category: "highlight",
  note: "",
  highlightActive: true,
  createdAt: "2026-07-01T08:00:00.000Z",
  updatedAt: "2026-07-01T08:00:00.000Z",
};
const archivedWrittenNote = {
  id: "archived-note",
  projectId: "foundations",
  moduleId: "coding",
  noteId: "coding-typescript-standards",
  selectedText: "已经不存在的原文",
  matchIndex: 0,
  mode: "note",
  category: "reflection",
  note: "保留这条旧笔记",
  highlightActive: true,
  createdAt: "2026-07-02T08:00:00.000Z",
  updatedAt: "2026-07-03T08:00:00.000Z",
};

const sourceStore = {
  version: 1,
  items: [currentAnnotation, recoverableLegacyNote, archivedHighlight, archivedWrittenNote],
};
const migratedStore = migrateLegacyAnnotations(sourceStore, modules);

assert.notEqual(migratedStore, sourceStore, "migration should return a new store");
assert.deepEqual(sourceStore.items[1], recoverableLegacyNote, "migration should not mutate its input");
assert.equal(migratedStore.version, 2, "legacy migration should always return the v2 store shape");
assert.equal(migratedStore.items[0].noteId, currentAnnotation.noteId, "current article ids should remain unchanged");
assert.equal(migratedStore.items[0].contextId, currentAnnotation.noteId, "current note ids should become stable contexts");
assert.equal(migratedStore.items[0].selectedText, currentAnnotation.selectedText, "current quotes should remain unchanged");
assert.equal(migratedStore.items[1].noteId, "coding-deque-stack-与-queue", "a uniquely recovered quote should follow the renamed article");
assert.equal(migratedStore.items[1].contextId, "coding-deque-stack-与-queue", "a recovered article should become the v2 context");
assert.equal(migratedStore.items[1].legacyNoteId, "coding-python-standards");
assert.equal(migratedStore.items[1].matchIndex, recoverableLegacyNote.matchIndex, "legacy flat fields should be retained verbatim");
assert.equal(migratedStore.items[1].note, recoverableLegacyNote.note);
assert.equal(migratedStore.items[1].category, recoverableLegacyNote.category);
assert.equal(migratedStore.items[1].createdAt, recoverableLegacyNote.createdAt);
assert.equal(migratedStore.items[1].updatedAt, recoverableLegacyNote.updatedAt);
assert.equal(migratedStore.items[1].anchor.selectedText, recoverableLegacyNote.selectedText);
assert.equal(migratedStore.items[1].anchor.matchIndex, 0, "the v2 anchor should use the recovered quote occurrence in current context");
assert.notEqual(migratedStore.items[1].anchor.prefix, undefined);
assert.notEqual(migratedStore.items[1].anchor.suffix, undefined);

const archiveId = getAnnotationArchiveNoteId("evals-debugging");
assert.equal(archiveId, "evals-debugging-legacy-annotations", "archive ids should be stable per module");
assert.equal(migratedStore.items[2].noteId, archiveId, "ambiguous pure highlights should move to the archive");
assert.equal(migratedStore.items[2].contextId, archiveId, "archived records should still have a stable v2 context");
assert.equal(migratedStore.items[2].legacyNoteId, "evals-debugging-old-resource");
assert.equal(migratedStore.items[2].highlightActive, false);
assert.equal(migratedStore.items[2].selectedText, archivedHighlight.selectedText);
assert.equal(migratedStore.items[2].createdAt, archivedHighlight.createdAt);
assert.equal(migratedStore.items[2].updatedAt, archivedHighlight.updatedAt);
assert.equal(migratedStore.items[3].noteId, getAnnotationArchiveNoteId("coding"));
assert.equal(migratedStore.items[3].contextId, getAnnotationArchiveNoteId("coding"));
assert.equal(migratedStore.items[3].legacyNoteId, "coding-typescript-standards");
assert.equal(migratedStore.items[3].highlightActive, false);
assert.equal(migratedStore.items[3].selectedText, archivedWrittenNote.selectedText);
assert.equal(migratedStore.items[3].note, archivedWrittenNote.note);
assert.equal(migratedStore.items[3].category, archivedWrittenNote.category);
assert.equal(migratedStore.items[3].createdAt, archivedWrittenNote.createdAt);
assert.equal(migratedStore.items[3].updatedAt, archivedWrittenNote.updatedAt);

const renamedModules = structuredClone(modules);
renamedModules[0].knowledgeNotes[0].id = "coding-deque-stack-queue-v2";
const migratedAfterSecondRename = migrateLegacyAnnotations(migratedStore, renamedModules);
assert.equal(
  migratedAfterSecondRename.items[1].noteId,
  "coding-deque-stack-queue-v2",
  "an annotation migrated before should follow a second unambiguous article rename",
);
assert.equal(
  migratedAfterSecondRename.items[1].legacyNoteId,
  "coding-python-standards",
  "sequential migrations should retain the original legacy id",
);
assert.deepEqual(
  migratedAfterSecondRename.items[2],
  migratedStore.items[2],
  "records already in the explicit archive should remain stable across later builds",
);
assert.deepEqual(
  migrateLegacyAnnotations(migratedStore, modules),
  migratedStore,
  "already migrated records should be idempotent",
);

const sectionContextAnnotation = normalizeAnnotation({
  id: "section-context",
  projectId: "finance",
  moduleId: "risk-allocation",
  contextId: "risk-allocation__section__allocation-table",
  selectedText: "安全边际",
  mode: "note",
  category: "understanding",
  note: "普通 section 记录",
  highlightActive: true,
  createdAt: "2026-07-08T08:00:00.000Z",
  updatedAt: "2026-07-08T09:00:00.000Z",
  anchor: {
    selectedText: "安全边际",
    matchIndex: 0,
    prefix: "估值需要",
    suffix: "作为缓冲",
  },
});
const migratedSectionContext = migrateLegacyAnnotations({ version: 2, items: [sectionContextAnnotation] }, modules);
assert.deepEqual(
  migratedSectionContext.items[0],
  sectionContextAnnotation,
  "native v2 section contexts without noteId should not be forced into the legacy note archive",
);
