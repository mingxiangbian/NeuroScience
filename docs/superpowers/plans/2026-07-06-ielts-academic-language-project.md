# IELTS Academic Language Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `projects/language/ielts-academic/` 下创建一个 IELTS Academic 备考项目包，先提供可复用的 multi-agent prompt 系统，再提供诊断驱动的 8 周学习包、错误系统和内容验证清单。

**Architecture:** 第一版是 Markdown-first project package，不写 runnable app，也不自动调度 subagent。用一个 repo-local requirement test 锁定文件存在性和关键规则；prompt 系统明确区分 `manual multi-session mode` 与 `single-session simulation mode`，学习计划通过 score profile、time budget、checkpoint 和 regression check 做诊断加权。

**Tech Stack:** Markdown documentation, Node.js assertion-based requirement test, repo-local project taxonomy under `projects/`.

---

## Scope Check

这份 spec 涵盖的是一个文档型 IELTS Academic 项目包，不是自动化系统。它包含三类内容，但彼此依赖清楚，可以在同一 implementation plan 内完成：

- `prompts/`：multi-agent prompt 系统和运行协议。
- `diagnostics/`, `plans/`, `errors/`：诊断驱动学习包。
- `validation/` 与 requirement test：内容契约与手动 dry-run 验证。

不创建 `src/`、不创建 CLI、不改 `projects/manifest.json`。除非执行时决定让 IELTS 项目出现在 `projects/index.html` 主目录，否则不运行或修改 `tests/projects-requirements.mjs`。

## File Structure

- Create: `tests/ielts-academic-language-project-requirements.mjs`
  - 静态检查 IELTS 项目包的关键文件和关键规则，防止后续 prompt 或模板缺少 run mode、calibration、partial input、adaptive allocation、checkpoint、regression 等核心设计。
- Create: `projects/language/README.md`
  - `language` 项目的索引页，链接到 IELTS Academic 子项目。
- Create: `projects/language/ielts-academic/README.md`
  - IELTS Academic 项目入口，解释目标、使用顺序、run mode 选择和文件导航。
- Create: `projects/language/ielts-academic/prompts/orchestrator.md`
  - Orchestrator 主 prompt，负责输入检查、run mode 声明、subagent 汇总、冲突解决和最终 plan 输出。
- Create: `projects/language/ielts-academic/prompts/run-modes.md`
  - 明确 manual multi-session mode 与 single-session simulation mode 的使用边界、成本和适用场景。
- Create: `projects/language/ielts-academic/prompts/interaction-protocol.md`
  - 定义 agent 报告、交叉批判、Orchestrator resolution 和 weekly review 的协议。
- Create: `projects/language/ielts-academic/prompts/output-contract.md`
  - 最终输出必须包含的字段，以及每个 training task 的最小结构。
- Create: `projects/language/ielts-academic/prompts/calibration-and-validation.md`
  - IELTS scoring 来源、LLM examiner 局限和 calibration routine。
- Create: eight files under `projects/language/ielts-academic/prompts/agents/`
  - 每个 subagent 一个 prompt，职责边界清晰。
- Create: five files under `projects/language/ielts-academic/diagnostics/`
  - 输入模板、score profile、score history、speaking audio 自评、error log。
- Create: five files under `projects/language/ielts-academic/plans/`
  - 8 周 adaptive plan、daily flexible training、checkpoint rules、weekly review、mock test strategy。
- Create: three files under `projects/language/ielts-academic/errors/`
  - error priority map、band 6 to 8 language map、regression check template。
- Create: three files under `projects/language/ielts-academic/validation/`
  - output contract checklist、dry-run test cases、examiner calibration checklist。

## Official IELTS Source Anchors

执行 Task 3 前先打开这些当前官方或官方合作方来源，prompt 中只引用评分维度和方法，不复制大段 descriptor 表格：

- `https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail`
  - 用于 overall score rounding、Listening / Academic Reading raw score anchor、Writing 和 Speaking 四项评分维度。
- `https://ielts.org/news-and-insights/ielts-writing-band-descriptors-and-key-assessment-criteria`
  - 用于确认 IELTS Writing band descriptors 和 key assessment criteria 的官方发布入口。
- `https://takeielts.britishcouncil.org/sites/default/files/ielts_writing_band_descriptors.pdf`
  - 用于 Writing Task 1 / Task 2 examiner prompt 的 descriptor category anchor。
- `https://takeielts.britishcouncil.org/sites/default/files/ielts_speaking_band_descriptors.pdf`
  - 用于 Speaking examiner prompt 的 Fluency and coherence、Lexical resource、Grammatical range and accuracy、Pronunciation anchor。

## Task 1: Add Requirement Test

**Files:**
- Create: `tests/ielts-academic-language-project-requirements.mjs`

- [ ] **Step 1: Write the failing requirement test**

Create `tests/ielts-academic-language-project-requirements.mjs` with:

```js
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const root = new URL("../projects/language/ielts-academic/", import.meta.url);
const languageReadmeUrl = new URL("../projects/language/README.md", import.meta.url);

const requiredFiles = [
  "../projects/language/README.md",
  "../projects/language/ielts-academic/README.md",
  "../projects/language/ielts-academic/prompts/orchestrator.md",
  "../projects/language/ielts-academic/prompts/run-modes.md",
  "../projects/language/ielts-academic/prompts/interaction-protocol.md",
  "../projects/language/ielts-academic/prompts/output-contract.md",
  "../projects/language/ielts-academic/prompts/calibration-and-validation.md",
  "../projects/language/ielts-academic/prompts/agents/listening-specialist.md",
  "../projects/language/ielts-academic/prompts/agents/reading-specialist.md",
  "../projects/language/ielts-academic/prompts/agents/writing-task-1-examiner.md",
  "../projects/language/ielts-academic/prompts/agents/writing-task-2-examiner.md",
  "../projects/language/ielts-academic/prompts/agents/speaking-examiner.md",
  "../projects/language/ielts-academic/prompts/agents/language-error-analyst.md",
  "../projects/language/ielts-academic/prompts/agents/diagnostic-score-profile-analyst.md",
  "../projects/language/ielts-academic/prompts/agents/study-load-execution-planner.md",
  "../projects/language/ielts-academic/diagnostics/diagnostic-input-template.md",
  "../projects/language/ielts-academic/diagnostics/score-profile-template.md",
  "../projects/language/ielts-academic/diagnostics/score-history-template.md",
  "../projects/language/ielts-academic/diagnostics/speaking-audio-self-assessment.md",
  "../projects/language/ielts-academic/diagnostics/error-log-template.md",
  "../projects/language/ielts-academic/plans/8-week-diagnostic-driven-plan.md",
  "../projects/language/ielts-academic/plans/daily-flexible-training.md",
  "../projects/language/ielts-academic/plans/checkpoint-rules.md",
  "../projects/language/ielts-academic/plans/weekly-review-template.md",
  "../projects/language/ielts-academic/plans/mock-test-strategy.md",
  "../projects/language/ielts-academic/errors/error-priority-map.md",
  "../projects/language/ielts-academic/errors/band-6-to-8-language-map.md",
  "../projects/language/ielts-academic/errors/regression-check-template.md",
  "../projects/language/ielts-academic/validation/output-contract-checklist.md",
  "../projects/language/ielts-academic/validation/dry-run-test-cases.md",
  "../projects/language/ielts-academic/validation/examiner-calibration-checklist.md",
];

for (const path of requiredFiles) {
  assert.equal(existsSync(new URL(path, import.meta.url)), true, `${path} should exist`);
}

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const languageReadme = read("../projects/language/README.md");
const projectReadme = read("../projects/language/ielts-academic/README.md");
const orchestrator = read("../projects/language/ielts-academic/prompts/orchestrator.md");
const runModes = read("../projects/language/ielts-academic/prompts/run-modes.md");
const outputContract = read("../projects/language/ielts-academic/prompts/output-contract.md");
const calibration = read("../projects/language/ielts-academic/prompts/calibration-and-validation.md");
const speaking = read("../projects/language/ielts-academic/prompts/agents/speaking-examiner.md");
const scoreProfile = read("../projects/language/ielts-academic/diagnostics/score-profile-template.md");
const eightWeekPlan = read("../projects/language/ielts-academic/plans/8-week-diagnostic-driven-plan.md");
const checkpoints = read("../projects/language/ielts-academic/plans/checkpoint-rules.md");
const regression = read("../projects/language/ielts-academic/errors/regression-check-template.md");
const dryRuns = read("../projects/language/ielts-academic/validation/dry-run-test-cases.md");

assert.match(languageReadme, /IELTS Academic/, "language README should link to IELTS Academic");
assert.match(projectReadme, /Overall 8\.0/, "project README should state the aggressive overall target");
assert.match(projectReadme, /each skill 7\.5\+/, "project README should state the per-skill floor");
assert.match(projectReadme, /manual multi-session mode/, "project README should explain independent run mode");
assert.match(projectReadme, /single-session simulation mode/, "project README should explain simulation mode");

assert.match(orchestrator, /Do not invent a personal weakness profile/, "orchestrator should refuse unsupported diagnosis");
assert.match(orchestrator, /Run mode used and independence level/, "orchestrator should report run mode and independence level");
assert.match(orchestrator, /duration, material type, expected output, and review method/, "orchestrator should enforce task fields");

assert.match(runModes, /This is the only mode that supports real agent independence/, "run modes should define true independence");
assert.match(runModes, /not independent/, "run modes should label single-session simulation as not independent");

assert.match(outputContract, /Score confidence and unverified dimensions/, "output contract should require confidence and unverified dimensions");
assert.match(outputContract, /Weekly time allocation by skill/, "output contract should require adaptive allocation");
assert.match(outputContract, /Regression checks/, "output contract should require regression checks");

assert.match(calibration, /https:\/\/ielts\.org\/take-a-test\/your-results\/ielts-scoring-in-detail/, "calibration should cite IELTS scoring detail");
assert.match(calibration, /LLM-generated band estimate is advisory/, "calibration should mark LLM scores as advisory");
assert.match(calibration, /more than 0\.5 band/, "calibration should define examiner drift threshold");

assert.match(speaking, /transcript alone cannot verify pronunciation/, "speaking examiner should state transcript limitation");
assert.match(speaking, /score range with confidence/, "speaking examiner should avoid exact transcript-only scores");

assert.match(scoreProfile, /Evidence basis/, "score profile should record evidence basis");
assert.match(scoreProfile, /Confidence/, "score profile should record confidence");
assert.match(scoreProfile, /Unverified dimensions/, "score profile should record unverified dimensions");

assert.match(eightWeekPlan, /diagnosis-weighted/, "8-week plan should be adaptive");
assert.match(eightWeekPlan, /Critical gap/, "8-week plan should define critical gaps");
assert.match(eightWeekPlan, /Maintenance skill/, "8-week plan should preserve maintenance allocation");

assert.match(checkpoints, /Week 2 feasibility check/, "checkpoint rules should include Week 2");
assert.match(checkpoints, /Week 6 correction checkpoint/, "checkpoint rules should include Week 6");
assert.match(checkpoints, /Week 8 readiness check/, "checkpoint rules should include Week 8");
assert.match(checkpoints, /6 focused hours per week/, "checkpoint rules should include the workload floor");

assert.match(regression, /fixed repeatedly/, "regression template should track repeated fixes");
assert.match(regression, /regressed/, "regression template should track regressions");

assert.match(dryRuns, /Missing-information dry run/, "dry runs should test missing input behavior");
assert.match(dryRuns, /Partial-input dry run/, "dry runs should test partial input handling");
assert.match(dryRuns, /Low-workload dry run/, "dry runs should test workload feasibility");
assert.match(dryRuns, /Single-session mode dry run/, "dry runs should test simulation labeling");

assert.equal(root.pathname.endsWith("/projects/language/ielts-academic/"), true);
assert.equal(languageReadmeUrl.pathname.endsWith("/projects/language/README.md"), true);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL with a missing file assertion for `../projects/language/README.md`.

- [ ] **Step 3: Commit the failing test**

Run:

```bash
git add tests/ielts-academic-language-project-requirements.mjs
git commit -m "test: add IELTS language project requirements"
```

Expected: commit succeeds.

## Task 2: Create Project Shell And Entry Points

**Files:**
- Create: `projects/language/README.md`
- Create: `projects/language/ielts-academic/README.md`

- [ ] **Step 1: Create `projects/language/README.md`**

Write this file with these sections:

```md
# Language

This folder collects language-learning projects that need durable prompts, diagnostic templates, and executable study plans.

## Projects

- [IELTS Academic](ielts-academic/) - a diagnostic-driven IELTS Academic project built around a reusable multi-agent prompt system, adaptive 8-week planning, and error regression checks.

## Boundary

This is not a general English notebook. Put reusable learning projects here; put dated session records under `sessions/` only when a conversation itself needs archiving.
```

- [ ] **Step 2: Create `projects/language/ielts-academic/README.md`**

Write the main project entry with these sections and content:

```md
# IELTS Academic

Goal: move from an estimated IELTS 6.0-6.5 baseline toward Overall 8.0, with each skill 7.5+.

This project has two layers:

1. Prompt system: reusable Orchestrator and subagent prompts for diagnosis, critique, calibration, and replanning.
2. Learning package: diagnostic templates, adaptive 8-week plan, daily flexible training, error tracking, and validation checklists.

## Recommended Flow

1. Start with `diagnostics/diagnostic-input-template.md`.
2. Choose a run mode in `prompts/run-modes.md`.
3. Use `prompts/orchestrator.md` to coordinate subagent outputs.
4. Fill `diagnostics/score-profile-template.md` and append weekly updates to `diagnostics/score-history-template.md`.
5. Follow `plans/8-week-diagnostic-driven-plan.md`, adjusting weekly allocation through `plans/checkpoint-rules.md`.
6. Track recurring issues in `diagnostics/error-log-template.md` and `errors/regression-check-template.md`.

## Run Modes

- manual multi-session mode: recommended for Week 1 baseline, Week 4 target checkpoint, Week 6 correction, and final exam strategy. This mode gives each subagent an isolated context and is the only mode that supports real agent independence.
- single-session simulation mode: useful for quick daily planning or low-stakes review. It is not independent and any critique must be labeled as simulated.

## Scoring Caution

LLM examiner scores are advisory. They must be descriptor-anchored, confidence-labeled, and calibrated with known-score or official sample material when available. Do not treat them as official IELTS scores.

## Key Files

- `prompts/orchestrator.md`
- `prompts/run-modes.md`
- `prompts/interaction-protocol.md`
- `prompts/output-contract.md`
- `prompts/calibration-and-validation.md`
- `diagnostics/score-profile-template.md`
- `plans/8-week-diagnostic-driven-plan.md`
- `plans/checkpoint-rules.md`
- `validation/dry-run-test-cases.md`
```

- [ ] **Step 3: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL on the next missing prompt file, `orchestrator.md`.

- [ ] **Step 4: Commit the project shell**

Run:

```bash
git add projects/language/README.md projects/language/ielts-academic/README.md
git commit -m "docs: add IELTS Academic project shell"
```

Expected: commit succeeds.

## Task 3: Create Core Prompt Protocol

**Files:**
- Create: `projects/language/ielts-academic/prompts/orchestrator.md`
- Create: `projects/language/ielts-academic/prompts/run-modes.md`
- Create: `projects/language/ielts-academic/prompts/interaction-protocol.md`
- Create: `projects/language/ielts-academic/prompts/output-contract.md`
- Create: `projects/language/ielts-academic/prompts/calibration-and-validation.md`

- [ ] **Step 1: Create `prompts/orchestrator.md`**

Write a copy-ready prompt with these sections:

```md
# IELTS Orchestrator Agent

You are the IELTS Orchestrator Agent for IELTS Academic.

Target:
- Primary target: Overall 8.0
- Floor target: each skill 7.5+
- Baseline assumption before diagnosis: IELTS 6.0-6.5

## Operating Rules

- Do not directly teach IELTS content unless the final plan requires a short task explanation.
- Do not invent a personal weakness profile when diagnostic evidence is missing.
- Always report: Run mode used and independence level.
- Every final training task must include duration, material type, expected output, and review method.
- Treat LLM examiner scores as advisory, not official IELTS scores.

## Input Check

Before planning, check whether the user supplied:
- IELTS type
- target score
- timeline
- weekly time budget or time log
- recent Listening and Reading raw scores or band estimates
- Writing Task 1 and Task 2 samples
- Speaking audio, transcript, or audio notes
- error examples

If information is missing, produce skill-specific diagnostic tasks instead of a fake profile.

## Run Mode Selection

Ask the user to choose:
- manual multi-session mode for true agent isolation
- single-session simulation mode for quick planning

If single-session simulation mode is used, label all cross-agent critique as simulated.

## Subagent Roster

Use these subagents by default:
1. Listening Specialist
2. Reading Specialist
3. Writing Task 1 Examiner
4. Writing Task 2 Examiner
5. Speaking Examiner
6. Language Error Analyst
7. Diagnostic & Score Profile Analyst
8. Study Load / Execution Planner

## Resolution Rule

Resolve conflicts by:
1. IELTS scoring risk
2. evidence confidence
3. gap to Overall 8.0 / each skill 7.5+
4. weekly time feasibility
5. regression risk

## Final Output

Return:
1. Run mode used and independence level
2. Score profile with evidence basis, confidence, and unverified dimensions
3. Skill priority ranking
4. Adaptive weekly allocation by skill
5. 8-week plan
6. Daily minimum / standard / stretch tasks
7. Error priority map
8. Regression checks
9. Exam simulation strategy
10. Weekly review prompt
11. Risks to Overall 8.0 / each skill 7.5+
```

- [ ] **Step 2: Create `prompts/run-modes.md`**

Write sections:

```md
# Run Modes

## Manual Multi-Session Mode

This is the only mode that supports real agent independence.

Use it for:
- Week 1 baseline
- Week 4 target checkpoint
- Week 6 correction checkpoint
- final exam strategy

Process:
1. Give the same input pack to each subagent in a separate chat or isolated context.
2. Do not show one subagent another subagent's output.
3. Collect all subagent reports.
4. Give the reports to the Orchestrator for conflict resolution.

Cost:
- Baseline: eight subagent runs plus one Orchestrator run.
- Weekly major replanning: rerun only agents whose evidence changed, then rerun Orchestrator.

## Single-Session Simulation Mode

This mode is not independent.

Use it for:
- quick daily adjustment
- low-stakes review
- rough planning when the user accepts weaker independence

Required label:

> This output uses single-session simulation mode. Cross-agent critique is simulated and should not be treated as evidence-isolated multi-agent reasoning.
```

- [ ] **Step 3: Create `prompts/interaction-protocol.md`**

Write sections:

```md
# Interaction Protocol

## Phase 1: Input Pack

The input pack contains exam type, target, timeline, weekly time budget, score evidence, samples, error logs, and constraints.

## Phase 2: Subagent Reports

Each subagent returns:
- Evidence used
- Weak points
- Bottleneck hypothesis
- High-impact drills
- Confidence level
- Missing evidence

## Phase 3: Cross-Agent Critique

Required critiques:
- Writing vs Speaking: grammar cleanup, fluency, and naturalness tradeoff
- Reading vs Listening: vocabulary size vs real-time synonym recognition
- Language Error Analyst vs skill specialists: cross-skill error pattern validation
- Study Load Planner vs all agents: remove work that exceeds actual weekly capacity

## Phase 4: Orchestrator Resolution

The Orchestrator resolves conflicts using scoring risk, confidence, target gap, workload feasibility, and regression risk.

## Phase 5: Weekly Review

Every weekly review updates score history, error status, completed hours, and next-week allocation.
```

- [ ] **Step 4: Create `prompts/output-contract.md`**

Write sections:

```md
# Output Contract

The final Orchestrator output must contain:

- Run mode used and independence level
- Score profile and evidence basis
- Score confidence and unverified dimensions
- Skill priority ranking
- Adaptive 8-week plan
- Weekly time allocation by skill
- Daily training tasks in minimum, standard, and stretch modes
- Error priority map
- Regression checks
- Exam simulation strategy
- Weekly review prompt
- Risks to Overall 8.0 / each skill 7.5+

## Training Task Format

Every task must include:

| Field | Required content |
| --- | --- |
| Duration | Exact time range, such as 30 minutes or 90 minutes |
| Material type | Cambridge test, official sample, user essay, recording, transcript, error log, or vocabulary set |
| Expected output | Written answer, corrected answer, score profile update, recorded answer, annotated passage, or error-log entry |
| Review method | Self-check, descriptor-based review, answer-key analysis, pronunciation self-rating, or Orchestrator review |

## Missing Evidence Rule

If a dimension is not supported by evidence, label it as unverified and assign a diagnostic task.
```

- [ ] **Step 5: Create `prompts/calibration-and-validation.md`**

Write sections:

```md
# Calibration And Validation

## Source Anchors

- IELTS scoring detail: https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail
- IELTS Writing descriptors news entry: https://ielts.org/news-and-insights/ielts-writing-band-descriptors-and-key-assessment-criteria
- British Council Writing band descriptors PDF: https://takeielts.britishcouncil.org/sites/default/files/ielts_writing_band_descriptors.pdf
- British Council Speaking band descriptors PDF: https://takeielts.britishcouncil.org/sites/default/files/ielts_speaking_band_descriptors.pdf

## Examiner Rule

An LLM-generated band estimate is advisory. It is not an official IELTS score.

## Calibration Routine

1. Use a known-score or official sample answer when available.
2. Ask the examiner prompt to score it using descriptor categories.
3. Compare the estimated score to the known score.
4. If the estimate differs by more than 0.5 band, mark that examiner as uncalibrated.
5. If the examiner cannot justify the score against descriptor categories, mark that examiner as uncalibrated.

## Writing Consistency Check

For major replanning, assess important Writing samples twice:
- first-pass examiner judgment
- second-pass consistency check

Use the score range and confidence level in the score profile.
```

- [ ] **Step 6: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL on the first missing agent prompt file.

- [ ] **Step 7: Commit core prompt protocol**

Run:

```bash
git add projects/language/ielts-academic/prompts
git commit -m "docs: add IELTS prompt protocol"
```

Expected: commit succeeds.

## Task 4: Create Subagent Prompts

**Files:**
- Create: `projects/language/ielts-academic/prompts/agents/listening-specialist.md`
- Create: `projects/language/ielts-academic/prompts/agents/reading-specialist.md`
- Create: `projects/language/ielts-academic/prompts/agents/writing-task-1-examiner.md`
- Create: `projects/language/ielts-academic/prompts/agents/writing-task-2-examiner.md`
- Create: `projects/language/ielts-academic/prompts/agents/speaking-examiner.md`
- Create: `projects/language/ielts-academic/prompts/agents/language-error-analyst.md`
- Create: `projects/language/ielts-academic/prompts/agents/diagnostic-score-profile-analyst.md`
- Create: `projects/language/ielts-academic/prompts/agents/study-load-execution-planner.md`

- [ ] **Step 1: Create Listening Specialist prompt**

Include:

```md
# Listening Specialist

Role: analyze IELTS Academic Listening evidence and identify high-impact score bottlenecks.

Focus areas:
- spelling mistakes
- plural/singular loss
- synonym recognition
- speed tracking failure
- Section 4 academic comprehension gap
- answer transfer or computer-based input errors

Output:
- Evidence used
- Estimated band or raw-score range, with confidence
- Weak points
- Bottleneck hypothesis
- Drills with duration, material type, expected output, and review method
- Missing evidence

Do not recommend generic listening practice without a measurable review method.
```

- [ ] **Step 2: Create Reading Specialist prompt**

Include:

```md
# Reading Specialist

Role: analyze IELTS Academic Reading performance and optimize speed x accuracy.

Focus areas:
- TFNG
- Matching headings
- Matching information
- Multiple choice
- sentence completion
- skimming efficiency
- scanning accuracy
- vocabulary obstruction
- time allocation

Output:
- Evidence used
- Estimated band or raw-score range, with confidence
- Question-type bottlenecks
- Time-management model
- Drills with duration, material type, expected output, and review method
- Missing evidence
```

- [ ] **Step 3: Create Writing Task 1 Examiner prompt**

Include:

```md
# Writing Task 1 Examiner

Role: evaluate IELTS Academic Writing Task 1 using descriptor-anchored criteria.

Assessment criteria:
- Task Achievement
- Coherence and Cohesion
- Lexical Resource
- Grammatical Range and Accuracy

Focus areas:
- overview quality
- key feature selection
- comparison accuracy
- data precision
- logical grouping
- chart, map, process, and mixed visual task handling

Output:
- Evidence used
- Score range with confidence
- Criterion-level comments
- High-impact corrections
- Next diagnostic task if evidence is insufficient

Treat the score as advisory, not official.
```

- [ ] **Step 4: Create Writing Task 2 Examiner prompt**

Include:

```md
# Writing Task 2 Examiner

Role: evaluate IELTS Academic Writing Task 2 using descriptor-anchored criteria.

Assessment criteria:
- Task Response
- Coherence and Cohesion
- Lexical Resource
- Grammatical Range and Accuracy

Focus areas:
- position clarity
- idea development
- relevance
- examples and support
- paragraph logic
- cohesion without mechanical template language
- grammar accuracy under complexity

Output:
- Evidence used
- Score range with confidence
- Criterion-level comments
- Argument-quality diagnosis
- High-impact corrections
- Next diagnostic task if evidence is insufficient

Treat the score as advisory, not official.
```

- [ ] **Step 5: Create Speaking Examiner prompt**

Include:

```md
# Speaking Examiner

Role: evaluate IELTS Speaking evidence while separating text-visible and audio-dependent dimensions.

Assessment criteria:
- Fluency and coherence
- Lexical resource
- Grammatical range and accuracy
- Pronunciation

Limits:
- transcript alone cannot verify pronunciation
- transcript alone cannot fully verify real-time fluency, pause length, rhythm, stress, or intonation
- if audio evidence is missing, mark pronunciation and real-time fluency as unverified

Output:
- Evidence used
- Text-visible assessment
- Audio-dependent dimensions and whether they are verified
- Score range with confidence
- Part 1 / Part 2 / Part 3 bottlenecks
- Drills with duration, material type, expected output, and review method
```

- [ ] **Step 6: Create Language Error Analyst prompt**

Include:

```md
# Language Error Analyst

Role: aggregate errors across IELTS skills and identify systemic language problems.

Taxonomy:
- grammar errors
- collocation errors
- lexical limitation
- paraphrase failure
- coherence breakdown
- spelling and morphology
- register and naturalness

Output:
- Cross-skill error map
- High / medium / low impact priority list
- Band 6 to 8 language upgrade path
- Grammar stabilization plan
- Evidence gaps

Do not prioritize rare advanced vocabulary unless evidence shows it is the bottleneck.
```

- [ ] **Step 7: Create Diagnostic & Score Profile Analyst prompt**

Include:

```md
# Diagnostic & Score Profile Analyst

Role: build and maintain the IELTS score profile.

Responsibilities:
- estimate skill score ranges from evidence
- assign confidence levels
- mark unverified dimensions
- detect feasibility risk
- update score history
- recommend next diagnostic evidence

Output:
- Score profile table
- Evidence basis
- Confidence
- Unverified dimensions
- Feasibility warning
- Next evidence request

Do not make final study-plan decisions; the Orchestrator owns final prioritization.
```

- [ ] **Step 8: Create Study Load / Execution Planner prompt**

Include:

```md
# Study Load / Execution Planner

Role: convert priorities into sustainable daily and weekly training.

Responsibilities:
- track actual weekly hours
- apply minimum / standard / stretch day modes
- warn when the aggressive target is infeasible
- protect maintenance time for stronger skills
- reduce overload

Rules:
- If actual average is below 6 focused hours per week for two consecutive weeks, warn that Overall 8.0 is not realistic as an 8-week operating target.
- Minimum days preserve continuity but do not prove target feasibility.
- Every task must include duration, material type, expected output, and review method.
```

- [ ] **Step 9: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL on the first missing diagnostics file.

- [ ] **Step 10: Commit subagent prompts**

Run:

```bash
git add projects/language/ielts-academic/prompts/agents
git commit -m "docs: add IELTS subagent prompts"
```

Expected: commit succeeds.

## Task 5: Create Diagnostic Templates

**Files:**
- Create: `projects/language/ielts-academic/diagnostics/diagnostic-input-template.md`
- Create: `projects/language/ielts-academic/diagnostics/score-profile-template.md`
- Create: `projects/language/ielts-academic/diagnostics/score-history-template.md`
- Create: `projects/language/ielts-academic/diagnostics/speaking-audio-self-assessment.md`
- Create: `projects/language/ielts-academic/diagnostics/error-log-template.md`

- [ ] **Step 1: Create `diagnostic-input-template.md`**

Include:

```md
# Diagnostic Input Template

## Exam Target

- Exam type: IELTS Academic
- Target: Overall 8.0
- Skill floor: each skill 7.5+
- Timeline:
- Exam date:

## Time Budget

- Minimum days per week:
- Standard days per week:
- Stretch days per week:
- Actual focused hours last week:

## Score Evidence

| Skill | Evidence supplied | Score or raw mark | Date | Confidence |
| --- | --- | --- | --- | --- |
| Listening | | | | |
| Reading | | | | |
| Writing Task 1 | | | | |
| Writing Task 2 | | | | |
| Speaking | | | | |

## Samples And Error Evidence

- Listening errors:
- Reading errors:
- Writing Task 1 sample:
- Writing Task 2 sample:
- Speaking transcript or audio notes:
- Known constraints:
```

- [ ] **Step 2: Create `score-profile-template.md`**

Include:

```md
# Score Profile Template

## Current Profile

| Skill | Estimated range | Evidence basis | Confidence | Unverified dimensions | Target risk |
| --- | --- | --- | --- | --- | --- |
| Listening | | | | | |
| Reading | | | | | |
| Writing Task 1 | | | | | |
| Writing Task 2 | | | | | |
| Speaking | | | | | |

## Priority Ranking

1. 
2. 
3. 
4. 

## Feasibility Warning

Record whether the user is meeting the time floor for the Overall 8.0 path.

## Next Evidence Needed

List only evidence that would change the plan.
```

- [ ] **Step 3: Create `score-history-template.md`**

Include:

```md
# Score History Template

Append one entry per weekly review. Do not overwrite earlier entries.

## Entry Format

### Week X - YYYY-MM-DD

| Skill | Estimated range | Evidence used | Confidence | Change since last week |
| --- | --- | --- | --- | --- |
| Listening | | | | |
| Reading | | | | |
| Writing | | | | |
| Speaking | | | | |

- Actual focused hours:
- Major errors fixed:
- Errors that regressed:
- Next-week allocation decision:
- Target status: Overall 8.0 path / staged Overall 7.5 path / retarget exam date
```

- [ ] **Step 4: Create `speaking-audio-self-assessment.md`**

Include:

```md
# Speaking Audio Self-Assessment

Use this after recording IELTS Speaking Part 1, Part 2, or Part 3.

## Recording Metadata

- Date:
- Part:
- Topic:
- Duration:

## Fluency Evidence

- Long pauses over 2 seconds:
- Self-corrections:
- Repeated fillers:
- Lost train of thought:
- Approximate speech rate:

## Pronunciation Evidence

- Words unclear to listener:
- Stress or intonation concerns:
- Rhythm or chunking concerns:
- Sentences that required re-recording:

## Transcript Notes

- Grammar patterns:
- Vocabulary repetition:
- Collocation issues:
- Answer structure:

## Confidence

Mark pronunciation and real-time fluency as unverified if there is no audio or timing evidence.
```

- [ ] **Step 5: Create `error-log-template.md`**

Include:

```md
# Error Log Template

| Date | Skill | Error | Category | Source | Impact | Status | Review date |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Status Values

- active
- improving
- fixed once
- fixed repeatedly
- regressed

## Categories

- grammar
- collocation
- lexical limitation
- paraphrase failure
- coherence breakdown
- spelling or morphology
- timing
- task response
- pronunciation or fluency
```

- [ ] **Step 6: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL on the first missing plan file.

- [ ] **Step 7: Commit diagnostic templates**

Run:

```bash
git add projects/language/ielts-academic/diagnostics
git commit -m "docs: add IELTS diagnostic templates"
```

Expected: commit succeeds.

## Task 6: Create Adaptive Study Plan Documents

**Files:**
- Create: `projects/language/ielts-academic/plans/8-week-diagnostic-driven-plan.md`
- Create: `projects/language/ielts-academic/plans/daily-flexible-training.md`
- Create: `projects/language/ielts-academic/plans/checkpoint-rules.md`
- Create: `projects/language/ielts-academic/plans/weekly-review-template.md`
- Create: `projects/language/ielts-academic/plans/mock-test-strategy.md`

- [ ] **Step 1: Create `8-week-diagnostic-driven-plan.md`**

Include:

```md
# 8-Week Diagnostic-Driven Plan

This is a diagnosis-weighted plan, not an equal-allocation calendar.

## Week 1: Diagnostic Baseline

- Timed Listening test
- Timed Academic Reading test
- One Academic Writing Task 1 response
- One Academic Writing Task 2 essay
- Speaking Part 1, Part 2, and Part 3 recording or transcript
- Score profile and error log setup

## Weeks 2-3: Stabilization

Goal: remove band 6-6.5 blockers before high-band polishing.

Focus examples:
- unstable grammar
- spelling loss
- weak task response
- time misallocation
- hesitation
- shallow paraphrase handling

## Weeks 4-6: Band 7.5 Transition

Goal: move weak skills toward 7.5 behavior while maintaining stronger skills.

## Weeks 7-8: High-Band Simulation

Goal: test exam readiness under pressure and protect any skill at risk of falling below 7.5.

## Adaptive Allocation Rules

- Critical gap: below 6.5, or more than 1.0 band below target, receives 35-50% of weekly training budget.
- At-risk gap: around 6.5-7.0, receives 20-35%.
- Near-target skill: around 7.0-7.5, receives 15-25%.
- Maintenance skill: around 7.5+, receives 10-15%, unless recent regression appears.

No skill drops to zero.
```

- [ ] **Step 2: Create `daily-flexible-training.md`**

Include:

```md
# Daily Flexible Training

## Minimum Day: 30-45 Minutes

- one targeted drill
- one short error review
- one score-history or error-log update when relevant

## Standard Day: About 90 Minutes

- one main skill block
- one secondary skill block
- error-log update

## Stretch Day: 2-3 Hours

- mock section, writing revision, speaking recording review, or deep Reading/Listening analysis

## Task Format

Every task must include:
- duration
- material type
- expected output
- review method
```

- [ ] **Step 3: Create `checkpoint-rules.md`**

Include:

```md
# Checkpoint Rules

## Week 1 Baseline

Establish score profile, evidence confidence, and workload capacity.

## Week 2 Feasibility Check

Compare planned training volume with actual completed volume.

If actual average is below 6 focused hours per week for two consecutive weeks, warn that Overall 8.0 is not realistic as an 8-week operating target.

## Week 4 Target Checkpoint

If multiple skills remain below realistic 7.0 performance, set a staged target of Overall 7.5 / each skill 7.0+ while preserving the longer Overall 8.0 ambition.

If at least two skills approach 7.5 and no skill is below 7.0, continue the Overall 8.0 path.

## Week 6 Correction Checkpoint

Detect plateau, regression, or misallocated training time. Reweight skills when evidence changes.

## Week 8 Readiness Check

Decide whether the user is ready for exam execution, should continue training, or should retarget the exam date.
```

- [ ] **Step 4: Create `weekly-review-template.md`**

Include:

```md
# Weekly Review Template

## Week

- Week number:
- Date:
- Actual focused hours:
- Minimum / standard / stretch days completed:

## Evidence Added

- Listening:
- Reading:
- Writing:
- Speaking:

## Error Status

- Fixed repeatedly:
- Fixed once:
- Improving:
- Active:
- Regressed:

## Allocation Decision

| Skill | Next-week allocation | Reason |
| --- | --- | --- |
| Listening | | |
| Reading | | |
| Writing | | |
| Speaking | | |

## Prompt For Orchestrator

Use my updated score history, error log, and completed-hours record to revise next week's plan. Preserve Overall 8.0 / each skill 7.5+ as the long-term target, but warn if the 8-week operating target is no longer realistic.
```

- [ ] **Step 5: Create `mock-test-strategy.md`**

Include:

```md
# Mock Test Strategy

## Purpose

Mock tests are for readiness evidence, not just practice volume.

## Schedule

- Week 1: diagnostic sections
- Week 4: target checkpoint mock or half mock
- Week 6: correction checkpoint mock or targeted sections
- Week 8: readiness mock

## Review Method

For every mock:
- record raw marks or estimated band
- identify timing failures
- identify repeated errors
- update score history
- change next-week allocation only when the evidence is strong enough
```

- [ ] **Step 6: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL on the first missing error-system file.

- [ ] **Step 7: Commit adaptive plan documents**

Run:

```bash
git add projects/language/ielts-academic/plans
git commit -m "docs: add IELTS adaptive study plans"
```

Expected: commit succeeds.

## Task 7: Create Error System Documents

**Files:**
- Create: `projects/language/ielts-academic/errors/error-priority-map.md`
- Create: `projects/language/ielts-academic/errors/band-6-to-8-language-map.md`
- Create: `projects/language/ielts-academic/errors/regression-check-template.md`

- [ ] **Step 1: Create `error-priority-map.md`**

Include:

```md
# Error Priority Map

## High Impact

- grammar errors that affect meaning
- task response failure
- Writing Task 1 overview failure
- Task 2 underdevelopment
- repeated spelling loss
- Speaking fluency breakdown
- Reading time collapse
- Listening Section 4 comprehension failure

## Medium Impact

- collocation weakness
- limited paraphrase range
- weak examples
- inconsistent pronunciation clarity
- slow scanning

## Low Impact

- rare advanced vocabulary
- stylistic polish
- extra topic memorization
- isolated one-off mistakes
```

- [ ] **Step 2: Create `band-6-to-8-language-map.md`**

Include:

```md
# Band 6 To 8 Language Map

## Upgrade Principles

- prioritize accuracy before ornament
- upgrade collocation and paraphrase through real IELTS tasks
- avoid memorized high-band phrases that sound unnatural
- treat grammar range as useful only when accuracy remains stable

## Band 6 Pattern

- simple vocabulary repeats
- complex sentences break accuracy
- examples stay general
- cohesion is visible and mechanical

## Band 7.5-8 Pattern

- ideas are precise and relevant
- collocations are natural
- paraphrase preserves meaning
- complex grammar is controlled
- cohesion supports logic without drawing attention
```

- [ ] **Step 3: Create `regression-check-template.md`**

Include:

```md
# Regression Check Template

## Error Under Review

- Error:
- Original source:
- Status before check: active / improving / fixed once / fixed repeatedly / regressed

## Retest Context

- Skill:
- Material:
- Time pressure:
- Expected output:

## Result

- Did it reappear:
- Evidence:
- New status:
- Next review date:

An error should not leave active monitoring until it stays fixed across at least two relevant practice contexts.
```

- [ ] **Step 4: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: FAIL on the first missing validation file.

- [ ] **Step 5: Commit error system documents**

Run:

```bash
git add projects/language/ielts-academic/errors
git commit -m "docs: add IELTS error system"
```

Expected: commit succeeds.

## Task 8: Create Validation Documents And Make Test Pass

**Files:**
- Create: `projects/language/ielts-academic/validation/output-contract-checklist.md`
- Create: `projects/language/ielts-academic/validation/dry-run-test-cases.md`
- Create: `projects/language/ielts-academic/validation/examiner-calibration-checklist.md`

- [ ] **Step 1: Create `output-contract-checklist.md`**

Include:

```md
# Output Contract Checklist

Use this to review Orchestrator output.

## Required Fields

- Run mode used and independence level
- Score profile and evidence basis
- Score confidence and unverified dimensions
- Skill priority ranking
- Adaptive 8-week plan
- Weekly time allocation by skill
- Daily training tasks in minimum, standard, and stretch modes
- Error priority map
- Regression checks
- Exam simulation strategy
- Weekly review prompt
- Risks to Overall 8.0 / each skill 7.5+

## Task-Level Check

Each task includes:
- duration
- material type
- expected output
- review method
```

- [ ] **Step 2: Create `dry-run-test-cases.md`**

Include:

```md
# Dry-Run Test Cases

## Missing-Information Dry Run

Input: target score and timeline only.

Expected behavior: Orchestrator outputs diagnostic tasks and does not invent a personal weakness profile.

## Partial-Input Dry Run

Input: Listening and Reading raw scores, no Writing samples, transcript-only Speaking evidence.

Expected behavior: verified skills are analyzed; Writing receives diagnostic tasks; Speaking pronunciation and real-time fluency are marked unverified.

## Low-Workload Dry Run

Input: user completes below 6 focused hours per week for two consecutive weeks.

Expected behavior: Study Load Planner warns that Overall 8.0 is not realistic as an 8-week operating target and recommends a staged target.

## Single-Session Mode Dry Run

Input: user selects single-session simulation mode.

Expected behavior: output states that cross-agent critique is simulated and not independent.
```

- [ ] **Step 3: Create `examiner-calibration-checklist.md`**

Include:

```md
# Examiner Calibration Checklist

## Source Check

- IELTS scoring detail page opened
- Writing descriptor source opened
- Speaking descriptor source opened

## Calibration Sample

- Sample source:
- Known score:
- Examiner estimate:
- Difference:

## Decision

- If the estimate differs by more than 0.5 band, mark the examiner as uncalibrated.
- If the examiner cannot justify the rating against descriptor categories, mark the examiner as uncalibrated.
- If no known-score sample is available, mark calibration as incomplete and keep score confidence lower.

## Advisory Score Rule

Every score must state: LLM-generated band estimate is advisory and not an official IELTS score.
```

- [ ] **Step 4: Run the requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: PASS with no output.

- [ ] **Step 5: Commit validation documents**

Run:

```bash
git add projects/language/ielts-academic/validation
git commit -m "docs: add IELTS validation checklists"
```

Expected: commit succeeds.

## Task 9: Final Verification And Cleanup

**Files:**
- Verify: `tests/ielts-academic-language-project-requirements.mjs`
- Verify: all new files under `projects/language/`

- [ ] **Step 1: Run requirement test**

Run:

```bash
node tests/ielts-academic-language-project-requirements.mjs
```

Expected: PASS with no output.

- [ ] **Step 2: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: PASS with no output.

- [ ] **Step 3: Confirm `projects/manifest.json` was not modified**

Run:

```bash
git diff --name-only HEAD
```

Expected: changed files include `projects/language/**` and `tests/ielts-academic-language-project-requirements.mjs`; they do not include `projects/manifest.json`.

- [ ] **Step 4: Run content spot checks**

Run:

```bash
rg -n "manual multi-session mode|single-session simulation mode|Overall 8\\.0|each skill 7\\.5\\+|LLM-generated band estimate is advisory|transcript alone cannot verify pronunciation|6 focused hours per week|fixed repeatedly|regressed" projects/language/ielts-academic
```

Expected: output shows matches in the relevant prompt, plan, diagnostic, error, and validation files.

- [ ] **Step 5: Commit final verification adjustments if any were needed**

If Step 1-4 required any edits, run:

```bash
git add projects/language tests/ielts-academic-language-project-requirements.mjs
git commit -m "docs: finalize IELTS Academic language project"
```

Expected: commit succeeds only if there were final edits. If no edits were needed, skip this commit and report that verification passed without cleanup changes.

## Self-Review Checklist For The Implementer

- Spec coverage: every file listed in the spec exists or has an intentional reason not to exist.
- Run-mode clarity: no file implies single-session role play is truly independent.
- Diagnostic-first behavior: missing evidence produces diagnostic tasks, not invented scores.
- Speaking limits: transcript-only input never verifies pronunciation or real-time fluency.
- Calibration: examiner scoring is descriptor-anchored, confidence-labeled, and advisory.
- Adaptive allocation: the 8-week plan permits unequal skill weighting after Week 1.
- Checkpoints: Week 2, Week 4, Week 6, and Week 8 are all present.
- Regression: fixed errors are retested before being removed from monitoring.
- Verification: the new Node requirement test and `git diff --check` pass.
