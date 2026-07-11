import assert from "node:assert/strict";
import {
  ANNOTATION_CATEGORIES,
  groupAnnotations,
  normalizeAnnotation,
} from "../projects/foundations/roadmap/annotation-model.js";

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
