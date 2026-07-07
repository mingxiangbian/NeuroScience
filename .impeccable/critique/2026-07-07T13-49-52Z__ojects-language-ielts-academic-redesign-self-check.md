---
target: projects/foundations + projects/language/ielts-academic redesign self-check
total_score: 23
p0_count: 0
p1_count: 3
timestamp: 2026-07-07T13-49-52Z
slug: ojects-language-ielts-academic-redesign-self-check
---
Method: dual-agent (A: 019f3ccc-bc7e-78b3-acc8-4ec397f85b69 · B: 019f3ccc-f861-7282-84d8-b98ee1193d96)

Design Health Score: 23/40

Anti-patterns verdict: This does have AI-slop risk. Detector returned zero findings, but visual inspection found the current redesign is over-concepted: Atlas and Cockpit read as decorative skins over the same reader shell rather than task-serving structures.

Key findings:
- Foundations "Cognitive Atlas" is mostly pasted-on. The contour/circle map layer does not make the learning route more spatial, easier to scan, or easier to resume.
- IELTS "Training Cockpit" maps better to the actual diagnostic content, but the cold blue grid and card stack pushes it toward generic productivity-dashboard UI.
- Both pages are technically stable: no horizontal overflow, no contrast failures, no detector hits.
- Browser evidence found decorative backgrounds in CSS/screenshots and one clipped Foundations atlas-launch container due overflow-hidden decorations.

Priority issues:
[P1] Metaphors lead instead of serve. Fix by replacing literal Atlas/Cockpit hero language with project-specific instruments: Foundations as route ledger, IELTS as evidence/training log.
[P1] Decorative backgrounds reduce long-reading calm. Fix by removing page-wide contour/grid backgrounds and keeping pattern only as a restrained header/sidebar wash if needed.
[P1] Dashboard tropes overpower reader purpose. Fix by replacing big hero cards with compact re-entry strips: current state, next action, evidence gap.
[P2] Mobile starts too heavy. Fix by compressing module headers and hiding decorative launch panels on mobile.
[P2] Identity drift. Fix by returning to rice-paper/deep-ink base with sparse blue/cinnabar/gold state accents instead of page-wide green/blue atmospheres.

What still works:
- The shared reader shell remains useful: directory, main reader, note/context panel, search, theme, annotation affordances.
- IELTS has a real information model around diagnostics, errors, checkpoints, validation, and training tasks.
- The desire to differentiate the two pages is valid; the failed part is the visual method, not the goal.

Recommendation: redesign again, not full rollback. Keep the shell and project differentiation, but remove the literal concept skins and rebuild around "Research Notebook With Project-Specific Instruments".
