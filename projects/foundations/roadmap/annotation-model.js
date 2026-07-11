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
