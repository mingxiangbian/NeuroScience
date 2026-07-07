---
target: projects/foundations/index.html
total_score: 23
p0_count: 0
p1_count: 2
timestamp: 2026-07-07T12-39-35Z
slug: projects-foundations-index-html
---
Method: dual-agent (A: 019f3c8f-8b6c-7693-aa16-11510c26495d · B: 019f3c8f-ab7a-75b3-ba31-2d595e77200b)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Progress and active module are visible, but note/search/annotation feedback is weak. |
| 2 | Match System / Real World | 3 | Research language fits, but Chinese UI mixes with Search, Overview, No results found. |
| 3 | User Control and Freedom | 2 | Escape/search/toggles exist, but toggle state and deep re-entry are limited. |
| 4 | Consistency and Standards | 3 | Strong shell consistency, weaker focus/state vocabulary. |
| 5 | Error Prevention | 2 | Local notes/tasks persist, but annotation and data-load failure paths are fragile. |
| 6 | Recognition Rather Than Recall | 2 | Main nav visible, but annotation, note meaning, and rail affordances require discovery. |
| 7 | Flexibility and Efficiency | 3 | Cmd/Ctrl+K, URL module state, collapse controls help power use. |
| 8 | Aesthetic and Minimalist Design | 2 | Beautiful base, but decorative texture/glass and empty note column add noise. |
| 9 | Error Recovery | 2 | Load failure exists, but only exposes a raw message. |
| 10 | Help and Documentation | 1 | No contextual help for reader-specific features. |
| **Total** | | **23/40** | **Acceptable: strong identity, significant long-use UX fixes needed.** |

## Anti-Patterns Verdict

**LLM assessment:** This does not look like generic AI UI at first glance. It has a real research-workspace identity: rice-paper surface, deep ink, serif title voice, and compact reader chrome. The risk is second-order AI slop: decorative grid/stripe texture, repeated glass panels with large blur shadows, dashboard metric cards, and an empty right panel that looks designed before it looks useful.

**Deterministic scan:** `node .agents/skills/impeccable/scripts/detect.mjs --json projects/foundations/index.html` returned `[]`, exit code 0. No rule hits, no file locations, no false positives.

**Visual overlays:** No reliable user-visible overlay is available. Browser evidence loaded the page successfully, but mutable overlay injection was not supported by the Browser runtime, so no Human-tab overlay is claimed.

## Overall Impression

Foundations has the right visual language but opens like a static dashboard instead of a returning-study launch pad. The biggest opportunity is to make the first screen say: where am I, what changed, and what should I do next.

## What's Working

- The three-pane reader shell is fundamentally right for a long-use knowledge base: directory, central reader, context panel.
- Typography supports reading well; the central prose lane is comfortable and differentiated from controls.
- The page feels personal and research-oriented, not like a generic SaaS dashboard.

## Priority Issues

**[P1] Re-entry is emotionally flat**

Why it matters: The default overview shows all progress at 0%, all modules not-started, and a mostly empty right note panel. Returning after days or weeks, the user gets status but not momentum.

Fix: Reframe Overview as a launch pad: next action, last touched area, baseline still unknown, and a contextual reason for the next move. Collapse or populate the note panel when no note exists.

Suggested command: `$impeccable polish projects/foundations/index.html`

**[P1] Mobile chrome is overcrowded**

Why it matters: At 390px, the top toolbar makes brand mark, directory, search, shortcut hint, theme, and note controls compete. The note control is nearly pushed off-screen.

Fix: Collapse search to an icon or active full-width row on mobile, hide the Cmd/Ctrl+K hint, and make directory/note actions stable icon buttons.

Suggested command: `$impeccable adapt projects/foundations/index.html`

**[P2] Ornament is doing too much**

Why it matters: The rice-paper identity works, but grid lines, repeating stripe overlays, and glassy panels add a generated-surface feel and reduce calm long reading.

Fix: Keep paper tone and deep ink; remove obvious grid/stripe texture from dense reader surfaces; reduce repeated blur/shadow.

Suggested command: `$impeccable quieter projects/foundations/index.html`

**[P2] Interaction states are incomplete**

Why it matters: Hover exists in many places, but focus-visible and expanded/pressed states are inconsistent. Keyboard users and power use suffer even if accessibility is not a formal requirement.

Fix: Add consistent focus rings, `aria-expanded` updates for toggles, and visible state feedback for drawers/search/results.

Suggested command: `$impeccable audit projects/foundations/index.html`

**[P2] Powerful features are hidden**

Why it matters: Annotation and contextual note behavior require discovery. Search results truncate too aggressively and empty results use generic English.

Fix: Surface highlight/note affordances inside knowledge cards; make search results more contextual and localize empty-state copy.

Suggested command: `$impeccable clarify projects/foundations/index.html`

## Persona Red Flags

**Alex (Power User):** Cmd/Ctrl+K is good, but there are no visible shortcuts for next module, section jump, note toggle, or marking tasks. Annotation depends on mouse text selection.

**Sam (Keyboard/Structure Dependent):** Icon controls have labels, but focus styling is sparse and stateful drawers lack clear expanded state.

**Casey (Mobile Returning User):** Primary actions sit at the top, toolbar density is high, and the first screen requires re-orientation before action.

## Minor Observations

- Theme toggle appears not to persist between sessions.
- Hash handling treats `#hash` as a module id rather than a section deep link.
- Module title max size exceeds the documented design token ceiling.

## Questions to Consider

- Is Overview supposed to be a dashboard, or the next-session launch pad?
- Are nine 0% modules useful, or do they create a motivation problem?
- Should the right panel ever be visible when it has no note to show?
