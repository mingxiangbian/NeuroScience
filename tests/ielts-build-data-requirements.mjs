import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { markdownToSafeHtml } from "../projects/language/ielts-academic/scripts/build-markdown.mjs";
import { buildReferenceIndex } from "../projects/language/ielts-academic/scripts/build-references.mjs";
import { findMarkdownDocuments, parseFrontmatter } from "../projects/language/ielts-academic/scripts/build-sources.mjs";
import { validateSiteDataInputs } from "../projects/language/ielts-academic/scripts/build-schema.mjs";

function makeSuggestedUnit(overrides = {}) {
  return {
    id: "D1",
    type: "diagnostic",
    title: "写作 Task 2 首次诊断",
    status: "suggested",
    reason: "Collect dense evidence without assuming the weakest skill.",
    nextAction: "Complete a timed Task 2 response.",
    durationMinutes: 40,
    materialType: "official-style Task 2 prompt",
    expectedArtifact: "Original response and scoring record",
    reviewMethod: "Descriptor-based review",
    evidenceRefs: [],
    settlementCriteria: ["Original sample saved", "Confidence recorded"],
    ...overrides,
  };
}

function makeValidSprintPlan(overrides = {}) {
  const base = {
    schemaVersion: 1,
    id: "one-day-sprint",
    status: "active",
    lastUpdated: "2026-08-09",
    exam: {
      date: "2026-08-29",
      writtenMode: "paper",
      speakingDate: null,
      speakingScheduleStatus: "awaiting-admission-ticket",
      usualSpeakingWindow: {
        startDate: "2026-08-22",
        endDate: "2026-09-05",
        source: "registration email",
        boundary: "The appointment remains provisional until the admission ticket is released.",
      },
      admissionTicketExpectedBy: "2026-08-21",
      durationDays: 1,
      dayOneAvailableMinutes: 60,
    },
    speakingContingency: {
      status: "provisional-until-admission-ticket",
      readinessDeadline: "2026-08-20",
      replanTrigger: "Replan when the admission ticket is released.",
      rules: ["Protect the 48 hours around the speaking test."],
    },
    objective: {
      overall: 7.5,
      targetProfile: { listening: 7.5, reading: 7.5, writing: 7.5, speaking: 7.5 },
    },
    prioritySystem: {
      effectiveFrom: "2026-08-15",
      carryPolicy: "Complete the required priority before optional work.",
      levels: [{
        id: "P0",
        label: "Speaking readiness",
        reason: "The speaking appointment may precede the written test.",
        rule: "Keep one unprompted speaking sample each day.",
      }],
    },
    dailyBudget: {
      standardMinutes: 60,
      maximumMinutes: 60,
      finalDayMinutes: 60,
      templateMinutes: { halfDay: 60, standard: 60, taper: 60 },
      templates: {
        halfDay: [{
          id: "focus",
          label: "Focus",
          minutes: 60,
          materialType: "unseen sample",
          expectedArtifact: "original answer",
          reviewMethod: "compare against evidence",
        }],
      },
    },
    operatingRules: ["Keep one active repair unit."],
    paperEvidenceProtocol: ["Photograph the first answer before checking."],
    phases: [{ id: "P1", label: "Start", startDay: 1, endDay: 1, purpose: "Collect evidence." }],
    checkpoints: [{
      id: "CP1",
      day: 1,
      date: "2026-08-09",
      label: "Baseline",
      requiredEvidence: "One original answer.",
      decisionRules: ["Use the evidence to choose the next repair."],
    }],
    days: [{
      day: 1,
      date: "2026-08-09",
      phase: "P1",
      template: "halfDay",
      focus: "Collect a baseline.",
      tasks: { focus: "Complete one unseen sample." },
      gate: "Original answer retained.",
    }],
  };
  return { ...base, ...overrides };
}

function makeValidInputs(overrides = {}) {
  const base = {
    scoreProfile: {
      schemaVersion: 2,
      state: "not-started",
      lastUpdated: "2026-07-19",
      runMode: "not-yet-run",
      target: { overall: 7.5, perSkillFloor: null },
      currentEstimate: null,
      skills: [{
        id: "writing",
        label: "Writing",
        estimatedBand: null,
        confidence: "unverified",
        evidenceBasis: ["No sample yet."],
        unverifiedDimensions: ["Task 2 argument"],
        riskLevel: "unknown",
      }],
      risks: [],
    },
    scoreHistory: { schemaVersion: 2, entries: [] },
    errorLog: { schemaVersion: 2, errors: [] },
    unitLedger: {
      schemaVersion: 2,
      mode: "event-driven-settlement",
      state: "not-started",
      activeUnit: null,
      suggestedUnit: makeSuggestedUnit(),
      queue: [],
      settled: [],
    },
    calibrationEvents: {
      schemaVersion: 2,
      events: [{
        id: "baseline-complete",
        label: "基线证据完成",
        status: "waiting",
        condition: "Available diagnostic evidence has been recorded.",
        evidenceRefs: [],
        decision: null,
        decidedAt: null,
      }],
    },
    notes: [{
      id: "writing/task-2-argument-development",
      path: "notes/writing/task-2-argument-development.md",
      title: "Task 2 argument development",
      relatedErrors: [],
    }],
    journal: [{
      id: "2026-07-06-initial-setup",
      path: "journal/entries/2026-07-06-initial-setup.md",
      title: "Initial setup",
      relatedErrors: [],
      relatedNotes: ["writing/task-2-argument-development"],
    }],
    promptLibrary: [],
    validation: [],
  };
  return { ...base, ...overrides };
}

assert.deepEqual(validateSiteDataInputs(makeValidInputs()), { fatalIssues: [], warningIssues: [] });

assert.deepEqual(
  validateSiteDataInputs(makeValidInputs({ sprintPlan: makeValidSprintPlan() })),
  { fatalIssues: [], warningIssues: [] },
);

const missingSprintTask = makeValidSprintPlan();
missingSprintTask.days[0].tasks = {};
const missingSprintTaskResult = validateSiteDataInputs(makeValidInputs({ sprintPlan: missingSprintTask }));
assert.equal(missingSprintTaskResult.fatalIssues.some((issue) => issue.type === "missing_daily_task"), true);

const missingSprintPriorities = makeValidSprintPlan({ prioritySystem: undefined });
const missingSprintPrioritiesResult = validateSiteDataInputs(makeValidInputs({ sprintPlan: missingSprintPriorities }));
assert.equal(missingSprintPrioritiesResult.fatalIssues.some((issue) => issue.path === "sprintPlan.prioritySystem"), true);

const infeasibleSprint = makeValidSprintPlan({
  objective: {
    overall: 8,
    targetProfile: { listening: 7, reading: 7, writing: 7, speaking: 7 },
  },
});
const infeasibleSprintResult = validateSiteDataInputs(makeValidInputs({ sprintPlan: infeasibleSprint }));
assert.equal(infeasibleSprintResult.fatalIssues.some((issue) => issue.type === "infeasible_target_math"), true);

const missingSkills = validateSiteDataInputs(makeValidInputs({
  scoreProfile: {
    schemaVersion: 2,
    state: "not-started",
    lastUpdated: "2026-07-19",
    runMode: "not-yet-run",
    target: { overall: 7.5, perSkillFloor: null },
    currentEstimate: null,
    risks: [],
  },
}));
assert.equal(missingSkills.fatalIssues.some((issue) => issue.path === "scoreProfile.skills"), true);

const deprecatedTimeline = validateSiteDataInputs(makeValidInputs({
  scoreProfile: {
    ...makeValidInputs().scoreProfile,
    target: { overall: 7.5, perSkillFloor: null, timelineWeeks: 8 },
  },
}));
assert.equal(deprecatedTimeline.fatalIssues.some((issue) => issue.type === "deprecated_field" && issue.path.endsWith("timelineWeeks")), true);

const deprecatedWeek = validateSiteDataInputs(makeValidInputs({
  scoreHistory: {
    schemaVersion: 2,
    entries: [{
      id: "S1",
      date: "2026-07-19",
      eventType: "diagnostic",
      sourceType: "timed-writing",
      skills: { writing: 6.5 },
      overall: null,
      confidence: "medium",
      evidenceRefs: [],
      week: 1,
    }],
  },
}));
assert.equal(deprecatedWeek.fatalIssues.some((issue) => issue.type === "deprecated_field" && issue.path.endsWith(".week")), true);

const malformedErrors = validateSiteDataInputs(makeValidInputs({ errorLog: { schemaVersion: 2, errors: {} } }));
assert.equal(malformedErrors.fatalIssues.some((issue) => issue.path === "errorLog.errors" && issue.type === "invalid_type"), true);

function makeError(overrides = {}) {
  return {
    id: "E1",
    skill: "writing",
    impact: "high",
    status: "active",
    description: "Argument support is missing.",
    evidence: ["evidence:S1"],
    reviewMethod: "Compare original and revision.",
    openedAt: "2026-07-19",
    lastSeenAt: "2026-07-19",
    repairUnitId: null,
    consecutiveCleanSamples: 0,
    fixedEvidence: [],
    ...overrides,
  };
}

const invalidFixedError = validateSiteDataInputs(makeValidInputs({
  errorLog: { schemaVersion: 2, errors: [makeError({ status: "fixed" })] },
}));
assert.equal(invalidFixedError.fatalIssues.some((issue) => issue.type === "insufficient_fix_evidence"), true);

const validFixedError = validateSiteDataInputs(makeValidInputs({
  errorLog: {
    schemaVersion: 2,
    errors: [makeError({
      status: "fixed",
      consecutiveCleanSamples: 3,
      fixedEvidence: ["evidence:S2", "evidence:S3", "evidence:S4"],
    })],
  },
}));
assert.equal(validFixedError.fatalIssues.some((issue) => issue.type === "insufficient_fix_evidence"), false);

const invalidActiveState = validateSiteDataInputs(makeValidInputs({
  unitLedger: {
    ...makeValidInputs().unitLedger,
    activeUnit: makeSuggestedUnit({ id: "D2" }),
  },
}));
assert.equal(invalidActiveState.fatalIssues.some((issue) => issue.type === "invalid_unit_state" && issue.path === "unitLedger.activeUnit.status"), true);

const missingDiagnosticDuration = validateSiteDataInputs(makeValidInputs({
  unitLedger: {
    ...makeValidInputs().unitLedger,
    suggestedUnit: makeSuggestedUnit({ durationMinutes: null }),
  },
}));
assert.equal(missingDiagnosticDuration.fatalIssues.some((issue) => issue.type === "missing_timed_duration"), true);

const duplicateUnit = validateSiteDataInputs(makeValidInputs({
  unitLedger: {
    ...makeValidInputs().unitLedger,
    queue: [makeSuggestedUnit({ status: "ready" })],
  },
}));
assert.equal(duplicateUnit.fatalIssues.some((issue) => issue.type === "duplicate_id"), true);

const malformedRelations = validateSiteDataInputs(makeValidInputs({
  notes: [{ id: "bad-note", relatedErrors: {} }],
  journal: [{ id: "bad-entry", relatedErrors: {}, relatedNotes: {} }],
}));
assert.equal(malformedRelations.fatalIssues.some((issue) => issue.path === "bad-note.relatedErrors"), true);
assert.equal(malformedRelations.fatalIssues.some((issue) => issue.path === "bad-entry.relatedNotes"), true);

const warningResult = validateSiteDataInputs(makeValidInputs({
  scoreProfile: { ...makeValidInputs().scoreProfile, extraPlanningField: true },
}));
assert.equal(warningResult.warningIssues.some((issue) => issue.type === "unknown_field" && issue.path === "scoreProfile.extraPlanningField"), true);

const parsed = parseFrontmatter("---\nid: sample\nrelated_errors: [E1]\n---\n# Title\nBody");
assert.equal(parsed.frontmatter.id, "sample");
assert.deepEqual(parsed.frontmatter.related_errors, ["E1"]);
assert.equal(parsed.body, "# Title\nBody");

const tempDir = mkdtempSync(join(tmpdir(), "ielts-sources-"));
try {
  mkdirSync(join(tempDir, "prompts", "agents"), { recursive: true });
  writeFileSync(join(tempDir, "prompts", "orchestrator.md"), "# Orchestrator\nBody\n");
  writeFileSync(join(tempDir, "prompts", "agents", "new-agent.md"), "# New Agent\nBody\n");
  const docs = findMarkdownDocuments(join(tempDir, "prompts"), tempDir);
  assert.deepEqual(docs.map((doc) => doc.id), ["prompts/agents/new-agent", "prompts/orchestrator"]);
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}

const html = markdownToSafeHtml("# Heading\n\nA **bold** item with `code`.\n\n[good](https://example.com)\n\n[bad](javascript:alert(1))\n\n<img src=x onerror=alert(1)>\n\n```js\nconsole.log(1)\n```\n\n<script>alert(1)</script>\n");
assert.match(html.html, /<h1[^>]*>Heading<\/h1>/);
assert.match(html.html, /<strong>bold<\/strong>/);
assert.match(html.html, /<pre><code class="language-js">/);
assert.doesNotMatch(html.html, /<script|javascript:|onerror|<img|alert\(1\)/i);

const referenceIndex = buildReferenceIndex(makeValidInputs());
assert.equal(referenceIndex.targets.some((target) => target.id === "unit:D1" && target.moduleId === "units"), true);
assert.equal(referenceIndex.targets.some((target) => target.id === "calibration:baseline-complete" && target.moduleId === "settlements"), true);
assert.equal(referenceIndex.targets.some((target) => target.id === "note:writing/task-2-argument-development" && target.moduleId === "archive"), true);
assert.equal(referenceIndex.backlinks["note:writing/task-2-argument-development"].some((link) => link.id === "journal:2026-07-06-initial-setup"), true);
