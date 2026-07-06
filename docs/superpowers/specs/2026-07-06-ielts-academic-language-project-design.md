# IELTS Academic Language Project Design

Date: 2026-07-06
Status: revised after user review; awaiting user review before implementation planning

## Context

The user created `projects/language/` and wants an IELTS Academic improvement project under it. The starting idea is an IELTS multi-agent prompt system that coordinates specialized agents to produce an improvement plan. During brainstorming, the user chose a hybrid sequence:

1. Optimize the reusable IELTS multi-agent prompt system first.
2. Use that prompt system to create a diagnostic-driven IELTS Academic learning package.

The target is intentionally aggressive: move from an estimated IELTS 6.0-6.5 baseline toward **Overall 8.0**, with **each skill at 7.5+**. The project must support flexible study load rather than assume a fixed daily schedule.

User review identified several design gaps that this revision addresses:

- Multi-agent independence was underspecified.
- A fixed 8-week phase calendar could conflict with diagnosis-first planning.
- Checkpoints and workload feasibility warnings were too weak.
- Speaking assessment and LLM examiner calibration needed explicit limits and compensating checks.
- Verification needed content-level dry runs, not only repository hygiene checks.

## Goals

- Create a durable IELTS Academic project package under `projects/language/ielts-academic/`.
- Make the prompt system reusable, explicit, and conflict-aware instead of a simple list of role prompts.
- Support two run modes: true manual multi-session isolation and lightweight single-session simulation.
- Use more than five subagents when useful; the default design uses eight subagents plus one orchestrator.
- Build the learning package around diagnosis first, not assumptions about the user's weakest skill.
- Make the 8-week plan adaptive: phase names can be fixed, but skill time allocation must change based on score evidence, workload, and regression risk.
- Add calibration and confidence labels for LLM-based examiner scoring.
- Provide practical templates for daily training, error logging, weekly review, score-profile versioning, and regression checks.

## Non-Goals

- Do not build a runnable application or automatic orchestration system in this first implementation.
- Do not pretend that a single chat session provides true agent independence.
- Do not create a public-facing web reader unless separately requested.
- Do not claim the user can guarantee Overall 8.0 in 8 weeks; the plan should identify risk and adapt from diagnostic evidence.
- Do not produce generic IELTS advice without task duration, input material type, expected output, and review method.
- Do not treat LLM examiner scores as official IELTS scores.

## Assumptions

- Exam type: IELTS Academic.
- Baseline: approximately IELTS 6.0-6.5, but the project must confirm this through diagnosis.
- Target: Overall 8.0, with each skill 7.5+.
- Timeline: 8 weeks.
- Study load: flexible, with minimum, standard, and stretch-day modes.
- Current weakest skill is unknown, so Week 1 must establish the score profile.
- The aggressive path requires a meaningful weekly time floor. If the user's actual average is below 6 focused hours per week for two consecutive weeks, the system should warn that Overall 8.0 is not a realistic 8-week operating target and should shift to a staged target while preserving the longer-term ambition.

## Project Structure

Implementation should create this structure:

```text
projects/language/
  README.md
  ielts-academic/
    README.md
    prompts/
      orchestrator.md
      run-modes.md
      interaction-protocol.md
      output-contract.md
      calibration-and-validation.md
      agents/
        listening-specialist.md
        reading-specialist.md
        writing-task-1-examiner.md
        writing-task-2-examiner.md
        speaking-examiner.md
        language-error-analyst.md
        diagnostic-score-profile-analyst.md
        study-load-execution-planner.md
    diagnostics/
      diagnostic-input-template.md
      score-profile-template.md
      score-history-template.md
      speaking-audio-self-assessment.md
      error-log-template.md
    plans/
      8-week-diagnostic-driven-plan.md
      daily-flexible-training.md
      checkpoint-rules.md
      weekly-review-template.md
      mock-test-strategy.md
    errors/
      error-priority-map.md
      band-6-to-8-language-map.md
      regression-check-template.md
    validation/
      output-contract-checklist.md
      dry-run-test-cases.md
      examiner-calibration-checklist.md
```

`projects/language/README.md` should act as the language-learning index. `projects/language/ielts-academic/README.md` should be the main entry point for this IELTS project.

## Prompt System Design

The prompt system should behave as a reusable IELTS coaching team, not as a one-shot study-plan generator.

### Run Modes And Agent Isolation

The project must distinguish two run modes.

**Manual multi-session mode** is the recommended mode for baseline diagnosis and major replanning. The user runs each subagent in a separate chat or isolated context using the same input pack. Each subagent produces its report without seeing other subagent outputs. The user then gives all reports to the Orchestrator. This is the only mode that supports a real claim of agent independence.

Expected cost:

- Baseline setup: eight agent runs plus one Orchestrator run.
- Weekly major replanning: only rerun agents whose evidence changed, plus the Orchestrator.
- Practical use points: Week 1 baseline, Week 4 target checkpoint, Week 6 correction, and final exam strategy.

**Single-session simulation mode** is allowed for quick planning, daily adjustments, or low-stakes review. It is not independent. The prompt must label its critique as simulated cross-role critique, not as evidence-isolated multi-agent reasoning.

The first implementation is a prompt/document system, so it will not automate dispatching. If automatic orchestration is desired later, that should become a separate engineering project with `src/`, `tests/`, and runnable validation.

### Orchestrator

The Orchestrator coordinates all subagents and owns the final plan. It must:

- Collect user inputs and detect missing information.
- Choose or confirm the run mode.
- Refuse to invent a personal weakness profile when diagnostic evidence is absent.
- Dispatch subagents with a shared input contract.
- Force cross-agent critique before producing the final output.
- Resolve conflicts according to IELTS scoring priorities, target risk, evidence confidence, and fastest route to the Overall 8.0 / each skill 7.5+ target.
- Produce final outputs that are executable by week and by day.

The Orchestrator owns final decisions. It does not own raw score-profile construction.

### Subagents

Default roster:

1. Listening Specialist
2. Reading Specialist
3. Writing Task 1 Examiner
4. Writing Task 2 Examiner
5. Speaking Examiner
6. Language Error Analyst
7. Diagnostic & Score Profile Analyst
8. Study Load / Execution Planner

Writing Task 1 and Task 2 should be separate because Academic Task 1 information selection and Task 2 argument quality have different failure modes. Diagnostic analysis and execution planning should also be separate from language-error analysis, because score profiling and workload control are planning responsibilities rather than language-scoring responsibilities.

### Responsibility Boundaries

- Diagnostic & Score Profile Analyst owns estimated scores, confidence levels, missing-evidence flags, feasibility warnings, and score-history updates.
- Skill specialists own skill-specific error analysis, drills, and bottleneck hypotheses.
- Language Error Analyst owns cross-skill grammar, collocation, lexical, coherence, and paraphrase patterns.
- Study Load / Execution Planner owns workload feasibility, weekly time allocation, and minimum/standard/stretch task mapping.
- Orchestrator owns final priority ranking, conflict resolution, and the unified plan.

## Input Contract

The prompt system should ask for or accept:

- IELTS type, target score, timeline, and available study load.
- Recent Listening, Reading, Writing, and Speaking scores if available.
- Writing Task 1 and Task 2 samples if available.
- Speaking audio, transcript, audio notes, or self-assessment if available.
- Listening and Reading error examples if available.
- Known constraints such as exam date, daily time variability, and preferred materials.

### Partial Input Handling

Missing input should not force the whole system into a generic diagnostic mode. The system should degrade by skill:

- If Listening and Reading evidence exists, analyze those skills and mark Writing/Speaking as unverified.
- If Writing samples are missing, output Writing diagnostic tasks rather than a Writing score estimate.
- If Speaking has only a transcript, evaluate grammar, vocabulary, and answer structure, but mark pronunciation and real fluency as unverified.
- If workload history is missing, the Study Load Planner should ask for a one-week time log or start with a provisional plan.

Every score estimate must include an evidence basis and confidence level.

## Speaking Assessment Limits

The Speaking Examiner is a text-based agent unless the user provides audio notes or an external transcription and timing summary. It must not pretend to fully score pronunciation or real-time fluency from transcript text alone.

Compensation design:

- `speaking-audio-self-assessment.md` should ask the user to record answers and log approximate speech rate, long pauses, self-corrections, repeated fillers, unclear words, stress/intonation concerns, and intelligibility.
- If no audio evidence exists, Speaking outputs should separate text-visible dimensions from audio-dependent dimensions.
- Speaking scores should be given as a range with confidence, not a single exact band.
- The plan should periodically require recorded Part 2 and Part 3 answers for fluency and pronunciation review.

## Examiner Calibration

Writing and Speaking examiner agents rely on LLM judgment, so the system must treat scores as advisory. The implementation should anchor examiner prompts to the official IELTS band descriptor categories and verify current descriptor sources before writing the prompt files.

Calibration requirements:

- Examiner prompts must require evidence tied to IELTS descriptor categories, not vague impressions.
- Score outputs should use ranges, confidence levels, and reasoned uncertainty.
- `examiner-calibration-checklist.md` should include a calibration routine using known-score or official sample answers when available.
- If a calibration sample is off by more than 0.5 band or the agent cannot justify its rating against descriptor categories, the score profile must mark that examiner as uncalibrated.
- Important Writing samples should be assessed with both a first-pass examiner view and a second-pass consistency check before being used for major replanning.

The system should never present an LLM-generated band estimate as equivalent to an official examiner score.

## Interaction Protocol

The protocol should require these phases:

1. Run-mode selection.
2. Independent agent reports when using manual multi-session mode, or labeled simulated reports when using single-session mode.
3. Cross-agent critique and contradiction detection.
4. Orchestrator conflict resolution.
5. Final unified plan.
6. Weekly review prompt for the next iteration.

The cross-agent critique must include examples such as:

- Writing prioritizes grammar, but Speaking prioritizes fluency; Orchestrator decides whether low-level error cleanup or fluency expansion has higher target risk.
- Reading recommends vocabulary expansion, but Listening identifies synonym-recognition failure; Orchestrator separates passive vocabulary from real-time paraphrase recognition.
- Study Load Planner reduces volume when the plan would exceed the user's actual weekly capacity.

## Output Contract

Final prompt output must include:

- Run mode used and independence level.
- Skill priority ranking.
- Score profile and evidence basis.
- Score confidence and unverified dimensions.
- Adaptive 8-week plan.
- Weekly time allocation by skill.
- Daily training tasks in minimum, standard, and stretch modes.
- Error priority map.
- Regression checks for previously fixed errors.
- Exam simulation strategy.
- Weekly review prompt.
- Explicit risks to Overall 8.0 / each skill 7.5+.

Every task must include duration, material type, expected output, and review method.

## Diagnostic Learning Package Design

The learning package should follow an 8-week structure, but the structure is a planning scaffold rather than an equal-allocation calendar. After Week 1, weekly skill allocation must be diagnosis-weighted.

### Week 1: Diagnostic Baseline

- Complete one timed Listening test and one timed Reading test.
- Produce at least one Academic Writing Task 1 answer and one Task 2 essay.
- Complete Speaking Part 1, Part 2, and Part 3 practice, ideally recorded or transcribed.
- Fill the score profile, score history, and error log templates.
- Generate the first skill priority ranking.
- Establish available weekly time and decide whether the aggressive target is feasible as an 8-week operating target.

### Weeks 2-3: Stabilization

- Remove band 6-6.5 blockers: unstable grammar, spelling loss, weak task response, time misallocation, hesitation, and shallow paraphrase handling.
- Push weak skills toward stable band 7 behavior before high-band polishing.
- Maintain already-strong skills with low-volume review rather than equal training time.

### Weeks 4-6: Band 7.5 Transition

- Writing Task 1: improve information selection, comparison, overview quality, and data accuracy.
- Writing Task 2: improve argument development, paragraph logic, examples, and control of complex grammar.
- Speaking: improve answer expansion, Part 3 abstraction, lexical range, and natural fluency, using audio evidence when possible.
- Listening and Reading: stabilize high-difficulty sections and time pressure.
- Allocate the largest block of time to the skill with the highest target risk, not necessarily to all four skills evenly.

### Weeks 7-8: High-Band Simulation

- Run weekly full or half mock tests.
- Reallocate time toward any skill with a 7.5 risk.
- Maintain stronger skills with lower volume instead of overtraining them.
- Use post-mock review to update the final exam strategy.

## Adaptive Allocation Rules

After Week 1, the plan should assign weekly training weight by evidence:

- Critical gap: a skill estimated below 6.5, or more than 1.0 band below the target, receives 35-50% of the weekly training budget.
- At-risk gap: a skill around 6.5-7.0 receives 20-35%.
- Near-target skill: a skill around 7.0-7.5 receives 15-25%.
- Maintenance skill: a skill already around 7.5+ receives 10-15%, unless recent regression appears.

No skill should drop to zero, because IELTS requires all four skills. However, the system should explicitly permit unequal allocation. For example, if Listening is already near 7.5 and Writing is around 5.5-6.0, Writing should dominate the weekly plan while Listening receives maintenance and high-difficulty checks.

## Checkpoints

The project should use several checkpoints:

- Week 1 baseline: establish score profile, evidence confidence, and workload capacity.
- Week 2 feasibility check: compare planned training volume with actual completed volume and warn early if the time floor is not being met.
- Week 4 target checkpoint: decide whether to continue the Overall 8.0 path or temporarily stage the target at Overall 7.5 / each skill 7.0+.
- Week 6 correction checkpoint: detect plateau, regression, or misallocated training time; reweight skills if needed.
- Week 8 readiness check: decide whether the user is ready for exam execution, should continue training, or should retarget the exam date.

The Week 4 checkpoint rule:

- If multiple skills remain below realistic 7.0 performance, set a stage target of Overall 7.5 / each skill 7.0+ while preserving the longer Overall 8.0 ambition.
- If the score profile shows at least two skills approaching 7.5 and no skill below 7.0, continue the Overall 8.0 path.

## Daily Training Model

Daily work should be flexible:

- Minimum day: 30-45 minutes, preserving continuity with one targeted drill and short error review.
- Standard day: about 90 minutes, covering one main skill, one secondary skill, and error-log update.
- Stretch day: 2-3 hours, used for mock testing, writing revision, speaking recording review, or deep Reading/Listening analysis.

Minimum days are continuity tools, not sufficient evidence that the Overall 8.0 path is feasible. The Study Load / Execution Planner should track weekly totals and warn when the user's actual pattern cannot support the target.

## Error System

The error system should prioritize high-impact, cross-skill issues:

- High impact: grammar errors that affect meaning, task response failure, Writing Task 1 overview failure, Task 2 underdevelopment, repeated spelling loss, Speaking fluency breakdown, Reading time collapse, Listening Section 4 comprehension failure.
- Medium impact: collocation weakness, limited paraphrase range, weak examples, inconsistent pronunciation clarity, slow scanning.
- Low impact: rare advanced vocabulary, stylistic polish, extra topic memorization, and isolated one-off mistakes.

The `band-6-to-8-language-map.md` file should show how to upgrade language without encouraging unnatural memorized phrasing.

### Regression Checks

The error log should track each important error as one of:

- active
- improving
- fixed once
- fixed repeatedly
- regressed

Weekly review should revisit a small number of supposedly fixed errors to see whether they reappear under time pressure. A fixed error should not be removed from the plan until it stays fixed across at least two relevant practice contexts.

## Score Profile Versioning

The score profile should be append-only or snapshot-based. Each weekly update should record:

- date and week number
- estimated score range by skill
- evidence used
- confidence level
- actual study hours completed
- major errors fixed
- errors that regressed
- next-week allocation decision

This prevents weekly reviews from overwriting earlier assumptions and makes trend changes visible.

## Guardrails

- Do not treat the target as guaranteed.
- Do not label single-session role play as true independent multi-agent reasoning.
- Do not let the prompt system output vague tasks like "practice listening more."
- Do not prioritize theory completeness over score gain.
- Do not let Writing templates become rigid memorized essays.
- Do not let Speaking frameworks become scripted answers.
- Do not let vocabulary learning displace exam-task performance unless evidence shows vocabulary is the bottleneck.
- Do not assume one agent's recommendation is correct until it survives cross-agent critique.
- Do not report pronunciation or real-time fluency as verified from transcript-only input.
- Do not use uncalibrated LLM scores as the sole basis for major replanning.

## Verification

After implementation, run repository hygiene checks:

- `git diff --check`
- `node tests/projects-requirements.mjs` if `projects/manifest.json` or project directory listing behavior changes
- Markdown review for internal links and missing files

The implementation should not update `projects/manifest.json` unless the new IELTS project needs to appear in the main project directory page.

Content-level verification is also required:

- Run a dry test with missing user information and confirm the Orchestrator outputs diagnostic tasks instead of inventing a profile.
- Run a partial-input dry test and confirm verified skills are analyzed while missing skills are marked unverified.
- Run a low-workload dry test and confirm the Study Load Planner warns that the aggressive target is not feasible as an 8-week operating target.
- Run an output-contract check and confirm each task includes duration, material type, expected output, and review method.
- Run an examiner-calibration check with known-score or official sample material when available.
- Run a single-session mode test and confirm the output labels critique as simulated rather than independent.

These checks can be manual checklist runs in the first version because this is not yet a runnable automation system.

## Success Criteria

- A user can open `projects/language/ielts-academic/README.md` and understand how to use the project.
- The prompt system can be copied into Codex or another LLM and produces a diagnostic-first plan.
- The system clearly distinguishes true manual multi-session isolation from single-session simulation.
- The learning package provides a concrete 8-week route with flexible workload and adaptive skill allocation.
- The error templates support weekly replanning, regression checks, and score-profile history.
- Examiner scores are descriptor-anchored, confidence-labeled, and treated as advisory.
- The target is consistently stated as Overall 8.0 / each skill 7.5+, with realistic feasibility checks and staged fallback rules.
