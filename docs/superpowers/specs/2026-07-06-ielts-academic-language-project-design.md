# IELTS Academic Language Project Design

Date: 2026-07-06
Status: approved for spec writing; awaiting user review before implementation planning

## Context

The user created `projects/language/` and wants an IELTS Academic improvement project under it. The starting idea is an IELTS multi-agent prompt system that coordinates specialized agents to produce an improvement plan. During brainstorming, the user chose a hybrid sequence:

1. Optimize the reusable IELTS multi-agent prompt system first.
2. Use that prompt system to create a diagnostic-driven IELTS Academic learning package.

The target is intentionally aggressive: move from an estimated IELTS 6.0-6.5 baseline toward **Overall 8.0**, with **each skill at 7.5+**. The project must support flexible study load rather than assume a fixed daily schedule.

## Goals

- Create a durable IELTS Academic project package under `projects/language/ielts-academic/`.
- Make the prompt system reusable, explicit, and conflict-aware instead of a simple list of role prompts.
- Use more than five subagents when useful; the default design uses eight subagents plus one orchestrator.
- Build the learning package around diagnosis first, not assumptions about the user's weakest skill.
- Support an 8-week plan with a Week 4 checkpoint that can downgrade the immediate target if the diagnostic evidence shows the aggressive target is not feasible yet.
- Provide practical templates for daily training, error logging, weekly review, and score-profile updates.

## Non-Goals

- Do not build a runnable application or automation system in this first implementation.
- Do not create a public-facing web reader unless separately requested.
- Do not claim the user can guarantee Overall 8.0 in 8 weeks; the plan should identify risk and adapt from diagnostic evidence.
- Do not produce generic IELTS advice without task duration, input material type, expected output, and review method.

## Assumptions

- Exam type: IELTS Academic.
- Baseline: approximately IELTS 6.0-6.5, but the project must confirm this through diagnosis.
- Target: Overall 8.0, with each skill 7.5+.
- Timeline: 8 weeks.
- Study load: flexible, with minimum, standard, and stretch-day modes.
- Current weakest skill is unknown, so Week 1 must establish the score profile.

## Project Structure

Implementation should create this structure:

```text
projects/language/
  README.md
  ielts-academic/
    README.md
    prompts/
      orchestrator.md
      interaction-protocol.md
      output-contract.md
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
      error-log-template.md
    plans/
      8-week-diagnostic-driven-plan.md
      daily-flexible-training.md
      weekly-review-template.md
      mock-test-strategy.md
    errors/
      error-priority-map.md
      band-6-to-8-language-map.md
```

`projects/language/README.md` should act as the language-learning index. `projects/language/ielts-academic/README.md` should be the main entry point for this IELTS project.

## Prompt System Design

The prompt system should behave as a reusable IELTS coaching team, not as a one-shot study-plan generator.

### Orchestrator

The Orchestrator coordinates all subagents and owns the final plan. It must:

- Collect user inputs and detect missing information.
- Refuse to invent a personal weakness profile when diagnostic evidence is absent.
- Dispatch subagents with a shared input contract.
- Force cross-agent critique before producing the final output.
- Resolve conflicts according to IELTS scoring priorities, target risk, and fastest route to the Overall 8.0 / each skill 7.5+ target.
- Produce final outputs that are executable by week and by day.

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

### Input Contract

The prompt system should ask for or accept:

- IELTS type, target score, timeline, and available study load.
- Recent Listening, Reading, Writing, and Speaking scores if available.
- Writing Task 1 and Task 2 samples if available.
- Speaking transcript, audio notes, or self-assessment if available.
- Listening and Reading error examples if available.
- Known constraints such as exam date, daily time variability, and preferred materials.

If these inputs are missing, the system should output a diagnostic task list instead of a full personalized plan.

### Interaction Protocol

The protocol should require these phases:

1. Independent agent reports.
2. Cross-agent critique and contradiction detection.
3. Orchestrator conflict resolution.
4. Final unified plan.
5. Weekly review prompt for the next iteration.

The cross-agent critique must include examples such as:

- Writing prioritizes grammar, but Speaking prioritizes fluency; Orchestrator decides whether low-level error cleanup or fluency expansion has higher target risk.
- Reading recommends vocabulary expansion, but Listening identifies synonym-recognition failure; Orchestrator separates passive vocabulary from real-time paraphrase recognition.
- Study Load Planner reduces volume when the plan would exceed the user's flexible schedule.

### Output Contract

Final prompt output must include:

- Skill priority ranking.
- Score profile and evidence basis.
- 8-week plan.
- Daily training tasks in minimum, standard, and stretch modes.
- Error priority map.
- Exam simulation strategy.
- Weekly review prompt.
- Explicit risks to Overall 8.0 / each skill 7.5+.

Every task must include duration, material type, expected output, and review method.

## Diagnostic Learning Package Design

The learning package should follow this 8-week structure:

### Week 1: Diagnostic Baseline

- Complete one timed Listening test and one timed Reading test.
- Produce at least one Academic Writing Task 1 answer and one Task 2 essay.
- Complete Speaking Part 1, Part 2, and Part 3 practice, ideally recorded or transcribed.
- Fill the score profile and error log templates.
- Generate the first skill priority ranking.

### Weeks 2-3: Stabilization

- Remove band 6-6.5 blockers: unstable grammar, spelling loss, weak task response, time misallocation, hesitation, and shallow paraphrase handling.
- Push performance toward stable band 7 behavior before high-band polishing.

### Weeks 4-6: Band 7.5 Transition

- Writing Task 1: improve information selection, comparison, overview quality, and data accuracy.
- Writing Task 2: improve argument development, paragraph logic, examples, and control of complex grammar.
- Speaking: improve answer expansion, Part 3 abstraction, lexical range, and natural fluency.
- Listening and Reading: stabilize high-difficulty sections and time pressure.

### Weeks 7-8: High-Band Simulation

- Run weekly full or half mock tests.
- Reallocate time toward any skill with a 7.5 risk.
- Maintain stronger skills with lower volume instead of overtraining them.
- Use post-mock review to update the final exam strategy.

### Week 4 Checkpoint

At the end of Week 4, the project should require a checkpoint:

- If multiple skills remain below realistic 7.0 performance, set a stage target of Overall 7.5 / each skill 7.0+ while preserving the longer Overall 8.0 ambition.
- If the score profile shows at least two skills approaching 7.5 and no skill below 7.0, continue the Overall 8.0 path.

## Daily Training Model

Daily work should be flexible:

- Minimum day: 30-45 minutes, preserving continuity with one targeted drill and short error review.
- Standard day: about 90 minutes, covering one main skill, one secondary skill, and error-log update.
- Stretch day: 2-3 hours, used for mock testing, writing revision, speaking recording review, or deep Reading/Listening analysis.

The Study Load / Execution Planner should prevent plans that require unsustainable daily volume.

## Error System

The error system should prioritize high-impact, cross-skill issues:

- High impact: grammar errors that affect meaning, task response failure, Writing Task 1 overview failure, Task 2 underdevelopment, repeated spelling loss, Speaking fluency breakdown, Reading time collapse, Listening Section 4 comprehension failure.
- Medium impact: collocation weakness, limited paraphrase range, weak examples, inconsistent pronunciation clarity, slow scanning.
- Low impact: rare advanced vocabulary, stylistic polish, extra topic memorization, and isolated one-off mistakes.

The `band-6-to-8-language-map.md` file should show how to upgrade language without encouraging unnatural memorized phrasing.

## Guardrails

- Do not treat the target as guaranteed.
- Do not let the prompt system output vague tasks like "practice listening more."
- Do not prioritize theory completeness over score gain.
- Do not let Writing templates become rigid memorized essays.
- Do not let Speaking frameworks become scripted answers.
- Do not let vocabulary learning displace exam-task performance unless evidence shows vocabulary is the bottleneck.
- Do not assume one agent's recommendation is correct until it survives cross-agent critique.

## Verification

After implementation, run narrow checks:

- `git diff --check`
- `node tests/projects-requirements.mjs` if `projects/manifest.json` or project directory listing behavior changes
- Markdown review for internal links and missing files

The implementation should not update `projects/manifest.json` unless the new IELTS project needs to appear in the main project directory page.

## Success Criteria

- A user can open `projects/language/ielts-academic/README.md` and understand how to use the project.
- The prompt system can be copied into Codex or another LLM and produces a diagnostic-first plan.
- The learning package provides a concrete 8-week route with flexible daily workload.
- The error templates support weekly replanning instead of static advice.
- The target is consistently stated as Overall 8.0 / each skill 7.5+, with a realistic Week 4 checkpoint.
