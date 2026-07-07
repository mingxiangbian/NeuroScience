---
target: projects/language/ielts-academic/index.html
total_score: 24
p0_count: 0
p1_count: 3
timestamp: 2026-07-07T12-39-35Z
slug: projects-language-ielts-academic-index-html
---
Method: dual-agent (A: 019f3c90-052e-7481-b0fe-fd2af9c1325b · B: 019f3c90-45d0-7762-8b5e-140e13f65f82)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Module/status/progress are visible, but 23% overall in template state is misleading. |
| 2 | Match System / Real World | 3 | IELTS workflow maps well, but template, Run mode, and mixed language feel internal. |
| 3 | User Control and Freedom | 2 | Collapse, search, and Esc exist; drawer/toggle states lack clear expanded semantics. |
| 4 | Consistency and Standards | 2 | Strong shell, but icon controls, overlays, and card patterns drift. |
| 5 | Error Prevention | 2 | Validation/advisory states exist; local checklist/annotation persistence can be misunderstood as durable repo state. |
| 6 | Recognition Rather Than Recall | 3 | Sidebar/search help orientation; collapsed rails and icons require interpretation. |
| 7 | Flexibility and Efficiency | 3 | Cmd/Ctrl+K, URL module state, local tasks, annotations are strong. |
| 8 | Aesthetic and Minimalist Design | 2 | Visual noise and repeated cards weaken long-use reading. |
| 9 | Error Recovery | 2 | Load/module errors handled; localStorage failures mostly disappear into console. |
| 10 | Help and Documentation | 2 | Some empty-state help; primary next study action is not foregrounded. |
| **Total** | | **24/40** | **Acceptable: useful reader, hierarchy and interaction debt remain.** |

## Anti-Patterns Verdict

**LLM assessment:** Moderate AI-slop risk. The structure is real and useful, but the surface contains decorative grid/stripe background, radial gradients, repeated card grids, uppercased mini-labels, and status tiles that feel more generated dashboard than long-use study instrument.

**Deterministic scan:** `node .agents/skills/impeccable/scripts/detect.mjs --json projects/language/ielts-academic/index.html` returned `[]`, exit code 0. No rule hits, no file locations, no false positives.

**Visual overlays:** No reliable user-visible overlay is available. The page loaded successfully and data JSON returned 200, but browser mutation preflight failed, so no Human-tab overlay is claimed.

## Overall Impression

IELTS is functionally richer than Foundations, but visually it reads too much like a generated dashboard. Its biggest opportunity is to replace metric-first presentation with a study-cockpit first screen: diagnostic evidence needed, next artifact, current weak skill, and source trail.

## What's Working

- The three-pane reader architecture matches the project design system and should remain the shared pattern.
- Search, persistent UI state, local tasks, annotations, reference chips, and journal export are genuinely useful.
- The IELTS IA is coherent: dashboard, swimlane, errors, notes, journal, prompts, validation.

## Priority Issues

**[P1] Decorative background undermines the reader**

Why it matters: Grid gradients and repeating stripe overlays make the dense study surface feel more generated than durable. They compete with actual study content.

Fix: Reduce the page ground to quiet rice paper. Keep texture only as a subtle orientation signal, not a full-page pattern.

Suggested command: `$impeccable quieter projects/language/ielts-academic/index.html`

**[P1] Dashboard does not answer “what should I do next?”**

Why it matters: The first screen emphasizes target/run-mode/state/validation metrics, while the real first action is Week 1 diagnostic evidence. Template-state progress creates false reassurance.

Fix: Make the dominant first object “Run Week 1 diagnostic / evidence missing”; demote broad metrics until real diagnostic data exists.

Suggested command: `$impeccable layout projects/language/ielts-academic/index.html`

**[P1] Core controls lack robust focus/expanded states**

Why it matters: The page has power tools, but inconsistent focus and missing expanded state make them less trustworthy and harder to operate repeatedly.

Fix: Add `:focus-visible` vocabulary, update `aria-expanded` for drawers, and expose active/collapsed states consistently.

Suggested command: `$impeccable audit projects/language/ielts-academic/index.html`

**[P2] Cognitive load is high in low-information states**

Why it matters: Four-column Errors and stacked dashboard cards feel heavy before diagnostic evidence exists. The user must parse a system before the system has useful data.

Fix: Use progressive disclosure: one active diagnostic lane first, empty columns collapsed or summarized, lower-density dashboard until evidence arrives.

Suggested command: `$impeccable distill projects/language/ielts-academic/index.html`

**[P2] Card vocabulary is overused**

Why it matters: Metric cards, dashboard cards, content cards, error cards, note cards, and journal cards share a similar bordered translucent treatment, so important actions do not stand out.

Fix: Give study actions a distinct grammar: fewer tiles, stronger section rhythm, clearer source/action pairing.

Suggested command: `$impeccable polish projects/language/ielts-academic/index.html`

## Persona Red Flags

**Returning Learner:** Sees 23% overall and progress percentages while the data is still template-state. That creates false confidence rather than clarity.

**Keyboard-First User:** Cmd/Ctrl+K works, but focus visibility and expanded/collapsed state are inconsistent.

**Mentor/Collaborator:** The module map is understandable, but mixed Chinese/English labels, repo-path chips, and internal states like template require project context.

## Minor Observations

- Mobile search compresses to a very small usable text area.
- Mobile directory drawer overlays readable content with busy translucency.
- Dark mode works, but card surfaces become heavy gray blocks in Errors.
- Some `border-left` state accents are functional but close to the banned side-stripe pattern.

## Questions to Consider

- What if the first screen had one dominant object: Run Week 1 diagnostic?
- Should progress exist before diagnostic evidence exists, or should the UI show evidence missing?
- Can this reader feel less like a dashboard and more like a study cockpit?
