function target(id, type, label, moduleId, sectionId, sourcePath = "") {
  return { id: `${type}:${id}`, rawId: id, type, label, moduleId, sectionId, sourcePath };
}

function addBacklink(backlinks, targetId, source) {
  if (!backlinks[targetId]) backlinks[targetId] = [];
  if (!backlinks[targetId].some((item) => item.id === source.id)) backlinks[targetId].push(source);
}

function toArray(value) {
  return Array.isArray(value) ? value : [];
}

function toUnits(unitLedger) {
  return [
    unitLedger?.activeUnit,
    unitLedger?.suggestedUnit,
    ...toArray(unitLedger?.queue),
    ...toArray(unitLedger?.settled),
  ].filter(Boolean);
}

export function buildReferenceIndex(inputs) {
  const targets = [];
  const backlinks = {};
  const units = toUnits(inputs.unitLedger);
  const errors = toArray(inputs.errorLog?.errors);
  const scoreEvents = toArray(inputs.scoreHistory?.entries);
  const calibrationEvents = toArray(inputs.calibrationEvents?.events);
  const notes = toArray(inputs.notes);
  const journal = toArray(inputs.journal);
  const promptLibrary = toArray(inputs.promptLibrary);
  const validation = toArray(inputs.validation);

  for (const unit of units) {
    targets.push(target(unit.id, "unit", unit.title, "units", `unit-${unit.id}`, "plans/unit-ledger.json"));
  }
  for (const errorRecord of errors) {
    targets.push(target(errorRecord.id, "error", errorRecord.description, "errors", `error-${errorRecord.id}`, "diagnostics/error-log.json"));
  }
  for (const event of scoreEvents) {
    targets.push(target(event.id, "evidence", event.notes || event.id, "evidence", `evidence-${event.id}`, "diagnostics/score-history.json"));
  }
  for (const event of calibrationEvents) {
    targets.push(target(event.id, "calibration", event.label, "settlements", `calibration-${event.id}`, "plans/calibration-events.json"));
  }
  for (const note of notes) {
    targets.push(target(note.id, "note", note.title, "archive", `note-${note.id}`, note.path));
  }
  for (const entry of journal) {
    targets.push(target(entry.id, "journal", entry.title, "archive", `journal-${entry.id}`, entry.path));
  }
  for (const prompt of promptLibrary) {
    targets.push(target(prompt.id, "prompt", prompt.title, "system", `prompt-${prompt.id}`, prompt.path));
  }
  for (const validationDoc of validation) {
    targets.push(target(validationDoc.id, "validation", validationDoc.title, "system", `validation-${validationDoc.id}`, validationDoc.path));
  }

  for (const unit of units) {
    const source = { id: `unit:${unit.id}`, type: "unit", label: unit.title };
    for (const errorId of toArray(unit.errorRefs)) addBacklink(backlinks, `error:${errorId}`, source);
    for (const referenceId of toArray(unit.evidenceRefs)) addBacklink(backlinks, referenceId, source);
  }
  for (const errorRecord of errors) {
    const source = { id: `error:${errorRecord.id}`, type: "error", label: errorRecord.id };
    if (errorRecord.repairUnitId) addBacklink(backlinks, `unit:${errorRecord.repairUnitId}`, source);
    for (const referenceId of toArray(errorRecord.fixedEvidence)) addBacklink(backlinks, referenceId, source);
  }
  for (const event of scoreEvents) {
    const source = { id: `evidence:${event.id}`, type: "evidence", label: event.notes || event.id };
    for (const referenceId of toArray(event.evidenceRefs)) addBacklink(backlinks, referenceId, source);
  }
  for (const event of calibrationEvents) {
    const source = { id: `calibration:${event.id}`, type: "calibration", label: event.label };
    for (const referenceId of toArray(event.evidenceRefs)) addBacklink(backlinks, referenceId, source);
  }
  for (const note of notes) {
    const source = { id: `note:${note.id}`, type: "note", label: note.title };
    for (const errorId of toArray(note.relatedErrors)) addBacklink(backlinks, `error:${errorId}`, source);
  }
  for (const entry of journal) {
    const source = { id: `journal:${entry.id}`, type: "journal", label: entry.title };
    for (const errorId of toArray(entry.relatedErrors)) addBacklink(backlinks, `error:${errorId}`, source);
    for (const noteId of toArray(entry.relatedNotes)) addBacklink(backlinks, `note:${noteId}`, source);
  }

  for (const item of targets) {
    if (!backlinks[item.id]) backlinks[item.id] = [];
  }

  return { targets, backlinks };
}
