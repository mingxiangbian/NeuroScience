import assert from "node:assert/strict";
import * as annotationModel from "../projects/foundations/roadmap/annotation-model.js";

const {
  ANNOTATION_CATEGORIES,
  getAnnotationArchiveNoteId,
  groupAnnotations,
  migrateLegacyAnnotations,
  normalizeAnnotation,
  parseStoredAnnotations,
} = annotationModel;

assert.equal(typeof migrateLegacyAnnotations, "function", "annotation model should export a pure legacy migration helper");
assert.equal(typeof getAnnotationArchiveNoteId, "function", "annotation model should export stable archive note ids");
assert.equal(typeof parseStoredAnnotations, "function", "annotation model should expose recoverable storage parsing");

const malformedStore = parseStoredAnnotations("{not-json");
assert.equal(malformedStore.canPersist, false, "malformed storage should not be overwritten by an empty fallback");
assert.deepEqual(malformedStore.store, { version: 1, items: [] });

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
assert.deepEqual(validStore.store.items.map((item) => item.id), ["keep"]);

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
assert.deepEqual(migratedStore.items[0], currentAnnotation, "current article ids should remain unchanged");
assert.deepEqual(migratedStore.items[1], {
  ...recoverableLegacyNote,
  noteId: "coding-deque-stack-与-queue",
  legacyNoteId: "coding-python-standards",
}, "a quote found in exactly one current article should migrate without losing fields");

const archiveId = getAnnotationArchiveNoteId("evals-debugging");
assert.equal(archiveId, "evals-debugging-legacy-annotations", "archive ids should be stable per module");
assert.deepEqual(migratedStore.items[2], {
  ...archivedHighlight,
  noteId: archiveId,
  legacyNoteId: "evals-debugging-old-resource",
  highlightActive: false,
}, "ambiguous pure highlights should be archived and remain available as records");
assert.deepEqual(migratedStore.items[3], {
  ...archivedWrittenNote,
  noteId: getAnnotationArchiveNoteId("coding"),
  legacyNoteId: "coding-typescript-standards",
  highlightActive: false,
}, "unrecoverable written notes should preserve their quote, note, category, and timestamps");
assert.deepEqual(
  migrateLegacyAnnotations(migratedStore, modules),
  migratedStore,
  "already migrated records should be idempotent",
);
