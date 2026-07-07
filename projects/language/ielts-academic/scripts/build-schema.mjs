const allowedErrorStatuses = new Set(["active", "improving", "fixed", "regressed"]);
const allowedErrorImpacts = new Set(["high", "medium", "low"]);

const knownFields = {
  scoreProfile: new Set(["schemaVersion", "state", "lastUpdated", "runMode", "target", "currentEstimate", "skills", "risks"]),
  scoreHistoryEntry: new Set(["date", "week", "state", "runMode", "skills", "overall", "notes"]),
  checkpoint: new Set(["week", "name", "purpose", "status", "decision", "evidenceRequired"]),
  error: new Set(["id", "skill", "impact", "status", "description", "evidence", "nextReview", "reviewMethod"]),
};

function issue(severity, type, path, message, extra = {}) {
  return { severity, type, path, message, ...extra };
}

function hasObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function requireField(value, path, issues) {
  if (value === undefined) {
    issues.push(issue("fatal", "missing_required_field", path, `${path} is required`));
  }
}

function warnUnknownFields(object, path, known, issues) {
  if (!hasObject(object)) return;
  for (const key of Object.keys(object)) {
    if (!known.has(key)) {
      issues.push(issue("warning", "unknown_field", `${path}.${key}`, `${path}.${key} is not part of the core schema`));
    }
  }
}

function normalizeArrayField(value, path, issues) {
  if (value === undefined || value === null) return [];
  if (Array.isArray(value)) return value;
  issues.push(issue("fatal", "invalid_type", path, `${path} must be an array`));
  return [];
}

export function validateSiteDataInputs(inputs) {
  const fatalIssues = [];
  const warningIssues = [];
  const scoreProfile = inputs.scoreProfile ?? {};
  const scoreHistory = inputs.scoreHistory ?? {};
  const errorLog = inputs.errorLog ?? {};
  const checkpoints = inputs.checkpoints ?? {};
  const notes = Array.isArray(inputs.notes) ? inputs.notes : [];
  const journal = Array.isArray(inputs.journal) ? inputs.journal : [];
  const errors = Array.isArray(errorLog.errors) ? errorLog.errors : [];

  for (const field of ["schemaVersion", "target", "skills", "currentEstimate"]) {
    requireField(scoreProfile[field], `scoreProfile.${field}`, fatalIssues);
  }
  warnUnknownFields(scoreProfile, "scoreProfile", knownFields.scoreProfile, warningIssues);
  if (!Array.isArray(scoreProfile.skills)) {
    fatalIssues.push(issue("fatal", "invalid_type", "scoreProfile.skills", "scoreProfile.skills must be an array"));
  } else {
    scoreProfile.skills.forEach((skill, index) => {
      for (const field of ["id", "label", "estimatedBand", "confidence", "riskLevel"]) {
        requireField(skill?.[field], `scoreProfile.skills[${index}].${field}`, fatalIssues);
      }
    });
  }

  if (!Array.isArray(scoreHistory.entries)) {
    fatalIssues.push(issue("fatal", "invalid_type", "scoreHistory.entries", "scoreHistory.entries must be an array"));
  } else {
    scoreHistory.entries.forEach((entry, index) => {
      for (const field of ["date", "week", "skills"]) {
        requireField(entry?.[field], `scoreHistory.entries[${index}].${field}`, fatalIssues);
      }
      warnUnknownFields(entry, `scoreHistory.entries[${index}]`, knownFields.scoreHistoryEntry, warningIssues);
    });
  }

  if (!Array.isArray(checkpoints.checkpoints)) {
    fatalIssues.push(issue("fatal", "invalid_type", "checkpoints.checkpoints", "checkpoints.checkpoints must be an array"));
  } else {
    checkpoints.checkpoints.forEach((checkpoint, index) => {
      for (const field of ["week", "name", "purpose", "status", "evidenceRequired"]) {
        requireField(checkpoint?.[field], `checkpoints.checkpoints[${index}].${field}`, fatalIssues);
      }
      warnUnknownFields(checkpoint, `checkpoints.checkpoints[${index}]`, knownFields.checkpoint, warningIssues);
    });
  }

  if (!Array.isArray(errorLog.errors)) {
    fatalIssues.push(issue("fatal", "invalid_type", "errorLog.errors", "errorLog.errors must be an array"));
  } else {
    errors.forEach((errorRecord, index) => {
      for (const field of ["id", "skill", "impact", "status", "description"]) {
        requireField(errorRecord?.[field], `errorLog.errors[${index}].${field}`, fatalIssues);
      }
      if (errorRecord?.status && !allowedErrorStatuses.has(errorRecord.status)) {
        fatalIssues.push(issue("fatal", "invalid_enum", `errorLog.errors[${index}].status`, `${errorRecord.status} is not an allowed error status`));
      }
      if (errorRecord?.impact && !allowedErrorImpacts.has(errorRecord.impact)) {
        fatalIssues.push(issue("fatal", "invalid_enum", `errorLog.errors[${index}].impact`, `${errorRecord.impact} is not an allowed error impact`));
      }
      warnUnknownFields(errorRecord, `errorLog.errors[${index}]`, knownFields.error, warningIssues);
    });
  }

  const errorIds = new Set(errors.map((errorRecord) => errorRecord.id));
  const noteIds = new Set(notes.map((note) => note.id));

  notes.forEach((note) => {
    const relatedErrors = normalizeArrayField(note.relatedErrors, `${note.id}.relatedErrors`, fatalIssues);
    for (const errorId of relatedErrors) {
      if (!errorIds.has(errorId)) {
        fatalIssues.push(issue("fatal", "missing_reference", `${note.id}.relatedErrors`, `${note.id} references missing error ${errorId}`));
      }
    }
  });

  journal.forEach((entry) => {
    const relatedErrors = normalizeArrayField(entry.relatedErrors, `${entry.id}.relatedErrors`, fatalIssues);
    const relatedNotes = normalizeArrayField(entry.relatedNotes, `${entry.id}.relatedNotes`, fatalIssues);
    for (const errorId of relatedErrors) {
      if (!errorIds.has(errorId)) {
        fatalIssues.push(issue("fatal", "missing_reference", `${entry.id}.relatedErrors`, `${entry.id} references missing error ${errorId}`));
      }
    }
    for (const noteId of relatedNotes) {
      if (!noteIds.has(noteId)) {
        fatalIssues.push(issue("fatal", "missing_reference", `${entry.id}.relatedNotes`, `${entry.id} references missing note ${noteId}`));
      }
    }
  });

  return { fatalIssues, warningIssues };
}
