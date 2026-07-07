function target(id, type, label, moduleId, sectionId, sourcePath = "") {
  return { id: `${type}:${id}`, rawId: id, type, label, moduleId, sectionId, sourcePath };
}

function addBacklink(backlinks, targetId, source) {
  if (!backlinks[targetId]) backlinks[targetId] = [];
  backlinks[targetId].push(source);
}

function toArray(value) {
  return Array.isArray(value) ? value : [];
}

export function buildReferenceIndex(inputs) {
  const targets = [];
  const backlinks = {};
  const errors = toArray(inputs.errorLog?.errors);
  const notes = toArray(inputs.notes);
  const journal = toArray(inputs.journal);
  const promptLibrary = toArray(inputs.promptLibrary);
  const validation = toArray(inputs.validation);

  for (const errorRecord of errors) {
    targets.push(target(errorRecord.id, "error", errorRecord.description, "errors", `error-${errorRecord.id}`));
  }
  for (const note of notes) {
    targets.push(target(note.id, "note", note.title, "notes", `note-${note.id}`, note.path));
  }
  for (const entry of journal) {
    targets.push(target(entry.id, "journal", entry.title, "journal", `journal-${entry.id}`, entry.path));
  }
  for (const prompt of promptLibrary) {
    targets.push(target(prompt.id, "prompt", prompt.title, "prompt-library", `prompt-${prompt.id}`, prompt.path));
  }
  for (const validationDoc of validation) {
    targets.push(target(validationDoc.id, "validation", validationDoc.title, "validation", `validation-${validationDoc.id}`, validationDoc.path));
  }

  for (const note of notes) {
    for (const errorId of toArray(note.relatedErrors)) {
      addBacklink(backlinks, `error:${errorId}`, { id: `note:${note.id}`, type: "note", label: note.title });
    }
  }

  for (const entry of journal) {
    for (const errorId of toArray(entry.relatedErrors)) {
      addBacklink(backlinks, `error:${errorId}`, { id: `journal:${entry.id}`, type: "journal", label: entry.title });
    }
    for (const noteId of toArray(entry.relatedNotes)) {
      addBacklink(backlinks, `note:${noteId}`, { id: `journal:${entry.id}`, type: "journal", label: entry.title });
    }
  }

  for (const item of targets) {
    if (!backlinks[item.id]) backlinks[item.id] = [];
  }

  return { targets, backlinks };
}
