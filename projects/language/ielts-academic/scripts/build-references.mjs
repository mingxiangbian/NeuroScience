function target(id, type, label, moduleId, sectionId, sourcePath = "") {
  return { id: `${type}:${id}`, rawId: id, type, label, moduleId, sectionId, sourcePath };
}

function addBacklink(backlinks, targetId, source) {
  if (!backlinks[targetId]) backlinks[targetId] = [];
  backlinks[targetId].push(source);
}

export function buildReferenceIndex(inputs) {
  const targets = [];
  const backlinks = {};

  for (const errorRecord of inputs.errorLog?.errors ?? []) {
    targets.push(target(errorRecord.id, "error", errorRecord.description, "errors", `error-${errorRecord.id}`));
  }
  for (const note of inputs.notes ?? []) {
    targets.push(target(note.id, "note", note.title, "notes", `note-${note.id}`, note.path));
  }
  for (const entry of inputs.journal ?? []) {
    targets.push(target(entry.id, "journal", entry.title, "journal", `journal-${entry.id}`, entry.path));
  }
  for (const prompt of inputs.promptLibrary ?? []) {
    targets.push(target(prompt.id, "prompt", prompt.title, "prompt-library", `prompt-${prompt.id}`, prompt.path));
  }
  for (const validationDoc of inputs.validation ?? []) {
    targets.push(target(validationDoc.id, "validation", validationDoc.title, "validation", `validation-${validationDoc.id}`, validationDoc.path));
  }

  for (const note of inputs.notes ?? []) {
    for (const errorId of note.relatedErrors ?? []) {
      addBacklink(backlinks, `error:${errorId}`, { id: `note:${note.id}`, type: "note", label: note.title });
    }
  }

  for (const entry of inputs.journal ?? []) {
    for (const errorId of entry.relatedErrors ?? []) {
      addBacklink(backlinks, `error:${errorId}`, { id: `journal:${entry.id}`, type: "journal", label: entry.title });
    }
    for (const noteId of entry.relatedNotes ?? []) {
      addBacklink(backlinks, `note:${noteId}`, { id: `journal:${entry.id}`, type: "journal", label: entry.title });
    }
  }

  for (const item of targets) {
    if (!backlinks[item.id]) backlinks[item.id] = [];
  }

  return { targets, backlinks };
}
