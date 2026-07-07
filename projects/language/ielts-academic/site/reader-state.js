export const UI_STATE_KEY = "ieltsReader.ui.v1";
export const ANNOTATION_STORAGE_KEY = "ieltsReader.annotations.v1";
export const TASK_STORAGE_KEY = "ieltsReader.tasks.v1";

export function createEmptyAnnotationStore() {
  return {
    version: 1,
    items: [],
  };
}

export function loadAnnotations() {
  try {
    const raw = window.localStorage.getItem(ANNOTATION_STORAGE_KEY);
    if (!raw) return createEmptyAnnotationStore();
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.items)) return createEmptyAnnotationStore();
    return {
      version: 1,
      items: parsed.items.filter((item) => item && item.projectId === "ielts-academic"),
    };
  } catch (error) {
    console.warn("Unable to load IELTS annotations", error);
    return createEmptyAnnotationStore();
  }
}

export function saveAnnotations(annotations) {
  try {
    window.localStorage.setItem(ANNOTATION_STORAGE_KEY, JSON.stringify(annotations));
  } catch (error) {
    console.warn("Unable to save IELTS annotations", error);
  }
}

export function loadTaskState() {
  try {
    const raw = window.localStorage.getItem(TASK_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (error) {
    console.warn("Unable to load task checklist state", error);
    return {};
  }
}

export function saveTaskState(tasks) {
  try {
    window.localStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(tasks));
  } catch (error) {
    console.warn("Unable to save task checklist state", error);
  }
}

export function loadUiState() {
  try {
    const raw = window.localStorage.getItem(UI_STATE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      theme: parsed.theme === "dark" ? "dark" : "light",
      leftCollapsed: Boolean(parsed.leftCollapsed),
      noteCollapsed: Boolean(parsed.noteCollapsed),
    };
  } catch {
    return {
      theme: "light",
      leftCollapsed: false,
      noteCollapsed: false,
    };
  }
}

export function saveUiState(ui) {
  try {
    window.localStorage.setItem(UI_STATE_KEY, JSON.stringify(ui));
  } catch {
    return;
  }
}
