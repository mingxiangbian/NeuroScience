import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { markdownToSafeHtml } from "../projects/language/ielts-academic/scripts/build-markdown.mjs";
import { buildReferenceIndex } from "../projects/language/ielts-academic/scripts/build-references.mjs";
import { findMarkdownDocuments, parseFrontmatter } from "../projects/language/ielts-academic/scripts/build-sources.mjs";
import { validateSiteDataInputs } from "../projects/language/ielts-academic/scripts/build-schema.mjs";

const projectRoot = fileURLToPath(new URL("../projects/language/ielts-academic/", import.meta.url));

function makeValidInputs(overrides = {}) {
  const base = {
    scoreProfile: {
      schemaVersion: 1,
      state: "template",
      lastUpdated: "2026-07-06",
      runMode: "not-yet-run",
      target: { overall: 8, perSkillFloor: 7.5, timelineWeeks: 8 },
      currentEstimate: { overall: null, confidence: "low", summary: "Template state." },
      skills: [
        {
          id: "writing",
          label: "Writing",
          estimatedBand: null,
          confidence: "low",
          evidenceBasis: ["No sample yet."],
          unverifiedDimensions: ["Task 2 argument"],
          riskLevel: "unknown",
        },
      ],
      risks: [],
    },
    scoreHistory: {
      schemaVersion: 1,
      entries: [
        {
          date: "2026-07-06",
          week: 0,
          state: "template",
          runMode: "not-yet-run",
          skills: { listening: null, reading: null, writing: null, speaking: null },
          notes: "Starter row.",
        },
      ],
    },
    errorLog: {
      schemaVersion: 1,
      errors: [
        {
          id: "writing-task2-argument",
          skill: "writing",
          impact: "high",
          status: "active",
          description: "Argument is underdeveloped.",
          evidence: ["Task 2 sample"],
        },
      ],
    },
    checkpoints: {
      schemaVersion: 1,
      checkpoints: [
        {
          week: 2,
          name: "Week 2 Data Quality Check",
          purpose: "Confirm diagnostic evidence.",
          status: "not-started",
          decision: "Pending.",
          evidenceRequired: ["At least one scored sample."],
        },
      ],
    },
    notes: [
      {
        id: "writing/task-2-argument-development",
        path: "notes/writing/task-2-argument-development.md",
        title: "Task 2 argument development",
        relatedErrors: ["writing-task2-argument"],
      },
    ],
    journal: [
      {
        id: "2026-07-06-initial-setup",
        path: "journal/entries/2026-07-06-initial-setup.md",
        title: "Initial setup",
        relatedErrors: ["writing-task2-argument"],
        relatedNotes: ["writing/task-2-argument-development"],
      },
    ],
  };
  return { ...base, ...overrides };
}

const validResult = validateSiteDataInputs(makeValidInputs());
assert.deepEqual(validResult.fatalIssues, []);
assert.equal(Array.isArray(validResult.warningIssues), true);
assert.deepEqual(validResult.warningIssues, []);

const invalidResult = validateSiteDataInputs(makeValidInputs({
  scoreProfile: {
    schemaVersion: 1,
    target: { overall: 8, perSkillFloor: 7.5, timelineWeeks: 8 },
    currentEstimate: { overall: null, confidence: "low", summary: "Missing skills." },
  },
}));
assert.equal(
  invalidResult.fatalIssues.some((issue) => issue.type === "missing_required_field" && issue.path === "scoreProfile.skills"),
  true,
  "missing scoreProfile.skills should be fatal",
);

const warningResult = validateSiteDataInputs(makeValidInputs({
  scoreProfile: {
    ...makeValidInputs().scoreProfile,
    extraPlanningField: true,
  },
}));
assert.equal(
  warningResult.warningIssues.some((issue) => issue.type === "unknown_field" && issue.path === "scoreProfile.extraPlanningField"),
  true,
  "unknown fields should be warnings",
);

const parsed = parseFrontmatter("---\nid: sample\nrelated_errors: [writing-task2-argument]\n---\n# Title\nBody");
assert.equal(parsed.frontmatter.id, "sample");
assert.deepEqual(parsed.frontmatter.related_errors, ["writing-task2-argument"]);
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

const html = markdownToSafeHtml("# Heading\n\nA **bold** item with `code`.\n\n[bad](javascript:alert(1))\n\n<img src=x onerror=alert(1)>\n\n```js\nconsole.log(1)\n```\n\n<script>alert(1)</script>\n");
assert.match(html.html, /<h1[^>]*>Heading<\/h1>/);
assert.match(html.html, /<strong>bold<\/strong>/);
assert.match(html.html, /<code>code<\/code>/);
assert.match(html.html, /<pre><code class="language-js">/);
assert.doesNotMatch(html.html, /<script|alert\(1\)/);
assert.doesNotMatch(html.html, /javascript:|onerror|<img/i);
assert.match(html.text, /Heading/);

const referenceIndex = buildReferenceIndex(makeValidInputs());
assert.equal(referenceIndex.targets.some((target) => target.id === "error:writing-task2-argument"), true);
assert.equal(referenceIndex.targets.some((target) => target.id === "note:writing/task-2-argument-development"), true);
assert.equal(referenceIndex.backlinks["note:writing/task-2-argument-development"].some((link) => link.id === "journal:2026-07-06-initial-setup"), true);
assert.equal(existsSync(new URL("../projects/language/ielts-academic/scripts/build-ielts-data.mjs", import.meta.url)), true);
