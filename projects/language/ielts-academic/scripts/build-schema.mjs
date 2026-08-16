const allowedErrorStatuses = new Set(["active", "improving", "fixed", "regressed"]);
const allowedErrorImpacts = new Set(["high", "medium", "low"]);
const allowedUnitTypes = new Set(["diagnostic", "repair", "mock", "calibration"]);
const allowedUnitStatuses = new Set(["suggested", "ready", "active", "settled"]);
const allowedCalibrationStatuses = new Set(["waiting", "triggered", "decided"]);

const knownFields = {
  scoreProfile: new Set(["schemaVersion", "state", "lastUpdated", "runMode", "target", "currentEstimate", "skills", "risks"]),
  scoreHistoryEntry: new Set(["id", "date", "eventType", "sourceType", "skills", "overall", "confidence", "evidenceRefs", "notes"]),
  error: new Set([
    "id", "skill", "impact", "status", "description", "evidence", "reviewMethod", "openedAt", "lastSeenAt",
    "repairUnitId", "consecutiveCleanSamples", "fixedEvidence",
  ]),
  unitLedger: new Set(["schemaVersion", "mode", "state", "activeUnit", "suggestedUnit", "queue", "settled"]),
  unit: new Set([
    "id", "type", "title", "status", "reason", "nextAction", "durationMinutes", "materialType",
    "expectedArtifact", "reviewMethod", "evidenceRefs", "errorRefs", "settlementCriteria", "openedAt", "settledAt", "decision",
  ]),
  calibrationEvent: new Set(["id", "label", "status", "condition", "evidenceRefs", "decision", "decidedAt"]),
};

function issue(severity, type, path, message, extra = {}) {
  return { severity, type, path, message, ...extra };
}

function hasObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireField(value, path, issues) {
  if (value === undefined) {
    issues.push(issue("fatal", "missing_required_field", path, `${path} is required`));
  }
}

function requireSchemaV2(record, path, issues) {
  if (record?.schemaVersion !== 2) {
    issues.push(issue("fatal", "invalid_schema_version", `${path}.schemaVersion`, `${path}.schemaVersion must be 2`));
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

function validateUnit(unit, path, fatalIssues, warningIssues, expectedStatus = "") {
  if (!hasObject(unit)) {
    fatalIssues.push(issue("fatal", "invalid_type", path, `${path} must be an object`));
    return;
  }
  for (const field of ["id", "type", "title", "status", "nextAction", "materialType", "expectedArtifact", "reviewMethod", "evidenceRefs", "settlementCriteria"]) {
    requireField(unit[field], `${path}.${field}`, fatalIssues);
  }
  warnUnknownFields(unit, path, knownFields.unit, warningIssues);
  if (unit.type && !allowedUnitTypes.has(unit.type)) {
    fatalIssues.push(issue("fatal", "invalid_enum", `${path}.type`, `${unit.type} is not an allowed unit type`));
  }
  if (unit.status && !allowedUnitStatuses.has(unit.status)) {
    fatalIssues.push(issue("fatal", "invalid_enum", `${path}.status`, `${unit.status} is not an allowed unit status`));
  }
  if (expectedStatus && unit.status !== expectedStatus) {
    fatalIssues.push(issue("fatal", "invalid_unit_state", `${path}.status`, `${path}.status must be ${expectedStatus}`));
  }
  const evidenceRefs = normalizeArrayField(unit.evidenceRefs, `${path}.evidenceRefs`, fatalIssues);
  const settlementCriteria = normalizeArrayField(unit.settlementCriteria, `${path}.settlementCriteria`, fatalIssues);
  normalizeArrayField(unit.errorRefs, `${path}.errorRefs`, fatalIssues);
  if (settlementCriteria.length === 0) {
    fatalIssues.push(issue("fatal", "missing_settlement_criteria", `${path}.settlementCriteria`, `${path} must define settlement criteria`));
  }
  if (["diagnostic", "mock"].includes(unit.type) && !(Number(unit.durationMinutes) > 0)) {
    fatalIssues.push(issue("fatal", "missing_timed_duration", `${path}.durationMinutes`, `${path} requires a positive duration`));
  }
  if (expectedStatus === "settled" && evidenceRefs.length === 0) {
    fatalIssues.push(issue("fatal", "missing_settlement_evidence", `${path}.evidenceRefs`, `${path} must include settlement evidence`));
  }
}

function validateSprintPlan(sprintPlan, fatalIssues) {
  if (sprintPlan === undefined || sprintPlan === null) return;
  if (!hasObject(sprintPlan)) {
    fatalIssues.push(issue("fatal", "invalid_type", "sprintPlan", "sprintPlan must be an object"));
    return;
  }
  for (const field of ["schemaVersion", "id", "status", "lastUpdated", "exam", "speakingContingency", "objective", "prioritySystem", "dailyBudget", "operatingRules", "paperEvidenceProtocol", "phases", "checkpoints", "days"]) {
    requireField(sprintPlan[field], `sprintPlan.${field}`, fatalIssues);
  }
  if (sprintPlan.schemaVersion !== 1) {
    fatalIssues.push(issue("fatal", "invalid_schema_version", "sprintPlan.schemaVersion", "sprintPlan.schemaVersion must be 1"));
  }

  const durationDays = Number(sprintPlan.exam?.durationDays);
  if (!(durationDays > 0)) {
    fatalIssues.push(issue("fatal", "invalid_duration", "sprintPlan.exam.durationDays", "sprintPlan.exam.durationDays must be positive"));
  }
  const days = normalizeArrayField(sprintPlan.days, "sprintPlan.days", fatalIssues);
  const phases = normalizeArrayField(sprintPlan.phases, "sprintPlan.phases", fatalIssues);
  const checkpoints = normalizeArrayField(sprintPlan.checkpoints, "sprintPlan.checkpoints", fatalIssues);
  normalizeArrayField(sprintPlan.operatingRules, "sprintPlan.operatingRules", fatalIssues);
  normalizeArrayField(sprintPlan.paperEvidenceProtocol, "sprintPlan.paperEvidenceProtocol", fatalIssues);
  if (Number.isFinite(durationDays) && days.length !== durationDays) {
    fatalIssues.push(issue("fatal", "invalid_sprint_length", "sprintPlan.days", `sprintPlan.days must contain ${durationDays} days`));
  }
  for (const field of ["speakingScheduleStatus", "usualSpeakingWindow", "admissionTicketExpectedBy", "dayOneAvailableMinutes"]) {
    requireField(sprintPlan.exam?.[field], `sprintPlan.exam.${field}`, fatalIssues);
  }
  for (const field of ["startDate", "endDate", "source", "boundary"]) {
    requireField(sprintPlan.exam?.usualSpeakingWindow?.[field], `sprintPlan.exam.usualSpeakingWindow.${field}`, fatalIssues);
  }
  for (const field of ["status", "readinessDeadline", "replanTrigger", "rules"]) {
    requireField(sprintPlan.speakingContingency?.[field], `sprintPlan.speakingContingency.${field}`, fatalIssues);
  }
  normalizeArrayField(sprintPlan.speakingContingency?.rules, "sprintPlan.speakingContingency.rules", fatalIssues);

  const prioritySystem = sprintPlan.prioritySystem;
  if (!hasObject(prioritySystem)) {
    fatalIssues.push(issue("fatal", "invalid_type", "sprintPlan.prioritySystem", "sprintPlan.prioritySystem must be an object"));
  } else {
    for (const field of ["effectiveFrom", "carryPolicy", "levels"]) {
      requireField(prioritySystem[field], `sprintPlan.prioritySystem.${field}`, fatalIssues);
    }
    const levels = normalizeArrayField(prioritySystem.levels, "sprintPlan.prioritySystem.levels", fatalIssues);
    if (levels.length === 0) {
      fatalIssues.push(issue("fatal", "missing_priority_levels", "sprintPlan.prioritySystem.levels", "at least one priority level is required"));
    }
    const levelIds = [];
    levels.forEach((level, index) => {
      const path = `sprintPlan.prioritySystem.levels[${index}]`;
      for (const field of ["id", "label", "reason", "rule"]) {
        requireField(level?.[field], `${path}.${field}`, fatalIssues);
      }
      levelIds.push(level?.id);
    });
    if (new Set(levelIds).size !== levelIds.length) {
      fatalIssues.push(issue("fatal", "duplicate_id", "sprintPlan.prioritySystem.levels", "priority level ids must be unique"));
    }
  }

  const targetProfile = sprintPlan.objective?.targetProfile;
  const targetBands = ["listening", "reading", "writing", "speaking"].map((skill) => Number(targetProfile?.[skill]));
  if (targetBands.some((band) => !Number.isFinite(band))) {
    fatalIssues.push(issue("fatal", "invalid_target_profile", "sprintPlan.objective.targetProfile", "all four target bands must be numeric"));
  } else {
    const targetAverage = targetBands.reduce((sum, band) => sum + band, 0) / 4;
    const targetOverall = Number(sprintPlan.objective?.overall);
    if (!Number.isFinite(targetOverall) || targetAverage < targetOverall - 0.25) {
      fatalIssues.push(issue("fatal", "infeasible_target_math", "sprintPlan.objective.targetProfile", "target profile cannot round to the requested overall band"));
    }
  }

  const templates = sprintPlan.dailyBudget?.templates;
  const templateMinutes = sprintPlan.dailyBudget?.templateMinutes;
  if (!hasObject(templates) || Object.keys(templates).length === 0) {
    fatalIssues.push(issue("fatal", "missing_templates", "sprintPlan.dailyBudget.templates", "at least one daily template is required"));
  }
  if (!hasObject(templateMinutes)) {
    fatalIssues.push(issue("fatal", "missing_template_minutes", "sprintPlan.dailyBudget.templateMinutes", "daily template totals are required"));
  }
  for (const [field, templateId] of [["dayOneAvailableMinutes", "halfDay"], ["standardMinutes", "standard"], ["finalDayMinutes", "taper"]]) {
    const declared = field === "dayOneAvailableMinutes"
      ? Number(sprintPlan.exam?.[field])
      : Number(sprintPlan.dailyBudget?.[field]);
    if (Number.isFinite(declared) && Number(templateMinutes?.[templateId]) !== declared) {
      fatalIssues.push(issue("fatal", "invalid_daily_total", `sprintPlan.dailyBudget.templateMinutes.${templateId}`, `${templateId} must match ${field}`));
    }
  }
  const templateIds = new Set(Object.keys(hasObject(templates) ? templates : {}));
  for (const [templateId, templateBlocks] of Object.entries(hasObject(templates) ? templates : {})) {
    const blocks = normalizeArrayField(templateBlocks, `sprintPlan.dailyBudget.templates.${templateId}`, fatalIssues);
    const blockIds = [];
    let totalMinutes = 0;
    blocks.forEach((block, index) => {
      const path = `sprintPlan.dailyBudget.templates.${templateId}[${index}]`;
      for (const field of ["id", "label", "minutes", "materialType", "expectedArtifact", "reviewMethod"]) {
        requireField(block?.[field], `${path}.${field}`, fatalIssues);
      }
      if (!(Number(block?.minutes) > 0)) {
        fatalIssues.push(issue("fatal", "invalid_duration", `${path}.minutes`, `${path}.minutes must be positive`));
      }
      blockIds.push(block?.id);
      totalMinutes += Number(block?.minutes) || 0;
    });
    if (new Set(blockIds).size !== blockIds.length) {
      fatalIssues.push(issue("fatal", "duplicate_id", `sprintPlan.dailyBudget.templates.${templateId}`, "daily block ids must be unique within a template"));
    }
    const expectedMinutes = Number(templateMinutes?.[templateId]);
    if (Number.isFinite(expectedMinutes) && totalMinutes !== expectedMinutes) {
      fatalIssues.push(issue("fatal", "invalid_daily_total", `sprintPlan.dailyBudget.templates.${templateId}`, `${templateId} totals ${totalMinutes} minutes instead of ${expectedMinutes}`));
    } else if (!Number.isFinite(expectedMinutes)) {
      fatalIssues.push(issue("fatal", "missing_template_minutes", `sprintPlan.dailyBudget.templateMinutes.${templateId}`, `${templateId} requires a numeric total`));
    }
  }
  if (Number(sprintPlan.dailyBudget?.maximumMinutes) < Number(sprintPlan.dailyBudget?.standardMinutes)) {
    fatalIssues.push(issue("fatal", "invalid_daily_limit", "sprintPlan.dailyBudget.maximumMinutes", "maximumMinutes cannot be lower than standardMinutes"));
  }

  const phaseIds = new Set(phases.map((phase) => phase?.id));
  const dayNumbers = [];
  const dayDates = [];
  days.forEach((day, index) => {
    const path = `sprintPlan.days[${index}]`;
    for (const field of ["day", "date", "phase", "template", "focus", "tasks", "gate"]) {
      requireField(day?.[field], `${path}.${field}`, fatalIssues);
    }
    dayNumbers.push(day?.day);
    dayDates.push(day?.date);
    if (!phaseIds.has(day?.phase)) {
      fatalIssues.push(issue("fatal", "missing_reference", `${path}.phase`, `${path} references missing phase ${day?.phase}`));
    }
    if (!templateIds.has(day?.template)) {
      fatalIssues.push(issue("fatal", "missing_reference", `${path}.template`, `${path} references missing template ${day?.template}`));
      return;
    }
    if (!hasObject(day?.tasks)) {
      fatalIssues.push(issue("fatal", "invalid_type", `${path}.tasks`, `${path}.tasks must be an object`));
      return;
    }
    for (const block of templates[day.template]) {
      if (typeof day.tasks[block.id] !== "string" || day.tasks[block.id].trim() === "") {
        fatalIssues.push(issue("fatal", "missing_daily_task", `${path}.tasks.${block.id}`, `${path} must define a task for ${block.id}`));
      }
    }
    if (day?.conditionalReserve !== undefined) {
      for (const field of ["minutes", "condition", "task"]) {
        requireField(day.conditionalReserve?.[field], `${path}.conditionalReserve.${field}`, fatalIssues);
      }
      if (!(Number(day.conditionalReserve?.minutes) > 0)) {
        fatalIssues.push(issue("fatal", "invalid_duration", `${path}.conditionalReserve.minutes`, "conditional reserve minutes must be positive"));
      }
      const baseMinutes = templates[day.template].reduce((sum, block) => sum + (Number(block?.minutes) || 0), 0);
      if (baseMinutes + Number(day.conditionalReserve?.minutes || 0) > Number(sprintPlan.dailyBudget?.maximumMinutes)) {
        fatalIssues.push(issue("fatal", "invalid_daily_limit", `${path}.conditionalReserve`, "base template plus conditional reserve exceeds maximumMinutes"));
      }
    }
  });
  const expectedDayNumbers = Array.from({ length: days.length }, (_, index) => index + 1);
  if (dayNumbers.some((day, index) => day !== expectedDayNumbers[index])) {
    fatalIssues.push(issue("fatal", "invalid_day_sequence", "sprintPlan.days", "sprint days must be ordered consecutively from 1"));
  }
  if (new Set(dayDates).size !== dayDates.length) {
    fatalIssues.push(issue("fatal", "duplicate_date", "sprintPlan.days", "sprint day dates must be unique"));
  }

  const validDays = new Set(dayNumbers);
  checkpoints.forEach((checkpoint, index) => {
    const path = `sprintPlan.checkpoints[${index}]`;
    for (const field of ["id", "day", "date", "label", "requiredEvidence", "decisionRules"]) {
      requireField(checkpoint?.[field], `${path}.${field}`, fatalIssues);
    }
    normalizeArrayField(checkpoint?.decisionRules, `${path}.decisionRules`, fatalIssues);
    if (!validDays.has(checkpoint?.day)) {
      fatalIssues.push(issue("fatal", "missing_reference", `${path}.day`, `${path} references missing sprint day ${checkpoint?.day}`));
    }
  });
}

export function validateSiteDataInputs(inputs) {
  const fatalIssues = [];
  const warningIssues = [];
  const scoreProfile = inputs.scoreProfile ?? {};
  const scoreHistory = inputs.scoreHistory ?? {};
  const errorLog = inputs.errorLog ?? {};
  const unitLedger = inputs.unitLedger ?? {};
  const calibrationEvents = inputs.calibrationEvents ?? {};
  const sprintPlan = inputs.sprintPlan;
  const notes = Array.isArray(inputs.notes) ? inputs.notes : [];
  const journal = Array.isArray(inputs.journal) ? inputs.journal : [];
  const errors = Array.isArray(errorLog.errors) ? errorLog.errors : [];

  for (const [name, record] of Object.entries({ scoreProfile, scoreHistory, errorLog, unitLedger, calibrationEvents })) {
    requireSchemaV2(record, name, fatalIssues);
  }
  validateSprintPlan(sprintPlan, fatalIssues);

  for (const field of ["schemaVersion", "target", "skills", "currentEstimate"]) {
    requireField(scoreProfile[field], `scoreProfile.${field}`, fatalIssues);
  }
  warnUnknownFields(scoreProfile, "scoreProfile", knownFields.scoreProfile, warningIssues);
  if (hasObject(scoreProfile.target) && Object.hasOwn(scoreProfile.target, "timelineWeeks")) {
    fatalIssues.push(issue("fatal", "deprecated_field", "scoreProfile.target.timelineWeeks", "fixed-week runtime fields are not allowed"));
  }
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
      const path = `scoreHistory.entries[${index}]`;
      for (const field of ["id", "date", "eventType", "sourceType", "skills", "confidence", "evidenceRefs"]) {
        requireField(entry?.[field], `${path}.${field}`, fatalIssues);
      }
      if (hasObject(entry) && Object.hasOwn(entry, "week")) {
        fatalIssues.push(issue("fatal", "deprecated_field", `${path}.week`, "score history must be event-based, not week-based"));
      }
      normalizeArrayField(entry?.evidenceRefs, `${path}.evidenceRefs`, fatalIssues);
      warnUnknownFields(entry, path, knownFields.scoreHistoryEntry, warningIssues);
    });
  }

  if (!Array.isArray(errorLog.errors)) {
    fatalIssues.push(issue("fatal", "invalid_type", "errorLog.errors", "errorLog.errors must be an array"));
  } else {
    errors.forEach((errorRecord, index) => {
      const path = `errorLog.errors[${index}]`;
      for (const field of [
        "id", "skill", "impact", "status", "description", "evidence", "reviewMethod", "openedAt", "lastSeenAt",
        "repairUnitId", "consecutiveCleanSamples", "fixedEvidence",
      ]) {
        requireField(errorRecord?.[field], `${path}.${field}`, fatalIssues);
      }
      if (errorRecord?.status && !allowedErrorStatuses.has(errorRecord.status)) {
        fatalIssues.push(issue("fatal", "invalid_enum", `${path}.status`, `${errorRecord.status} is not an allowed error status`));
      }
      if (errorRecord?.impact && !allowedErrorImpacts.has(errorRecord.impact)) {
        fatalIssues.push(issue("fatal", "invalid_enum", `${path}.impact`, `${errorRecord.impact} is not an allowed error impact`));
      }
      normalizeArrayField(errorRecord?.evidence, `${path}.evidence`, fatalIssues);
      const fixedEvidence = normalizeArrayField(errorRecord?.fixedEvidence, `${path}.fixedEvidence`, fatalIssues);
      const independentFixedEvidence = new Set(fixedEvidence).size;
      if (errorRecord?.status === "fixed" && (Number(errorRecord.consecutiveCleanSamples) < 3 || independentFixedEvidence < 3)) {
        fatalIssues.push(issue("fatal", "insufficient_fix_evidence", `${path}.fixedEvidence`, "fixed errors require three independent clean sample references"));
      }
      warnUnknownFields(errorRecord, path, knownFields.error, warningIssues);
    });
  }

  for (const field of ["schemaVersion", "mode", "state", "activeUnit", "suggestedUnit", "queue", "settled"]) {
    requireField(unitLedger[field], `unitLedger.${field}`, fatalIssues);
  }
  warnUnknownFields(unitLedger, "unitLedger", knownFields.unitLedger, warningIssues);
  const queue = normalizeArrayField(unitLedger.queue, "unitLedger.queue", fatalIssues);
  const settled = normalizeArrayField(unitLedger.settled, "unitLedger.settled", fatalIssues);
  if (unitLedger.activeUnit !== null && unitLedger.activeUnit !== undefined) {
    validateUnit(unitLedger.activeUnit, "unitLedger.activeUnit", fatalIssues, warningIssues, "active");
  }
  if (unitLedger.suggestedUnit !== null && unitLedger.suggestedUnit !== undefined) {
    validateUnit(unitLedger.suggestedUnit, "unitLedger.suggestedUnit", fatalIssues, warningIssues, "suggested");
  }
  queue.forEach((unit, index) => validateUnit(unit, `unitLedger.queue[${index}]`, fatalIssues, warningIssues));
  settled.forEach((unit, index) => validateUnit(unit, `unitLedger.settled[${index}]`, fatalIssues, warningIssues, "settled"));
  const allUnits = [unitLedger.activeUnit, unitLedger.suggestedUnit, ...queue, ...settled].filter(hasObject);
  const unitIds = allUnits.map((unit) => unit.id).filter(Boolean);
  if (new Set(unitIds).size !== unitIds.length) {
    fatalIssues.push(issue("fatal", "duplicate_id", "unitLedger", "unit ids must be unique across active, suggested, queue, and settled units"));
  }

  if (!Array.isArray(calibrationEvents.events)) {
    fatalIssues.push(issue("fatal", "invalid_type", "calibrationEvents.events", "calibrationEvents.events must be an array"));
  } else {
    calibrationEvents.events.forEach((event, index) => {
      const path = `calibrationEvents.events[${index}]`;
      for (const field of ["id", "label", "status", "condition", "evidenceRefs", "decision", "decidedAt"]) {
        requireField(event?.[field], `${path}.${field}`, fatalIssues);
      }
      if (event?.status && !allowedCalibrationStatuses.has(event.status)) {
        fatalIssues.push(issue("fatal", "invalid_enum", `${path}.status`, `${event.status} is not an allowed calibration status`));
      }
      normalizeArrayField(event?.evidenceRefs, `${path}.evidenceRefs`, fatalIssues);
      warnUnknownFields(event, path, knownFields.calibrationEvent, warningIssues);
    });
  }

  const errorIds = new Set(errors.map((errorRecord) => errorRecord.id));
  const unitIdSet = new Set(unitIds);
  const noteIds = new Set(notes.map((note) => note.id));

  errors.forEach((errorRecord, index) => {
    if (errorRecord.repairUnitId && !unitIdSet.has(errorRecord.repairUnitId)) {
      fatalIssues.push(issue("fatal", "missing_reference", `errorLog.errors[${index}].repairUnitId`, `${errorRecord.id} references missing unit ${errorRecord.repairUnitId}`));
    }
  });

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
