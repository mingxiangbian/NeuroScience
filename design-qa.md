# Design QA — Brain Memory for AI Agents Reader

Date: 2026-07-17

Scope: `papers/brain-memory-for-ai-agents/`, shared paper reader UI, Visual Abstract, Research Plate, and Conceptual Lineage.

## Comparison inputs

- First fold: `paper-reader-concept-01-first-fold.png` vs. `reader-implementation-zhang-desktop-final.png`
- Evidence plate: `paper-reader-concept-02-research-plate.png` vs. `reader-implementation-cls-plate-desktop-final.png`
- Concept lineage: `paper-reader-concept-03-concept-lineage.png` vs. `reader-implementation-lineage-desktop-release.png`
- Mobile source figure: `reader-implementation-mobile-figure-lightbox-final.png`
- Dark selected lineage: `reader-implementation-lineage-dark-final.png`

All comparison images were inspected together at matching desktop states. The implementation preserves the pale paper, ink, teal, and vermilion system while using real paper figures rather than redrawn assets.

## Viewports and states checked

- Desktop, 1440 × 1024: survey first fold, CLS featured Research Plate, full Conceptual Lineage, filtered agent lane, and dark mode.
- Mobile, 390 × 844: survey first fold, stacked Research Plate, horizontally scrollable lineage, directory drawer, parallel-note drawer, and expanded semantic search.
- Direct URL reload: `?paper=...&view=lineage` remains in lineage mode.

## Findings resolved

- Moved late-year lineage positions inward and reduced the desktop map minimum width so 2023–2026 labels do not clip behind the inspector.
- Increased lineage row separation and text size to prevent nearby papers from colliding.
- Added extra height to the agent lane so SelfMem and the survey-scope boundary do not overlap.
- Kept the selected paper URL synchronized when a lane filter changes the selected node.
- Enlarged the mobile search pill so the full placeholder remains visible.
- Added a named, modal source-figure viewer that keeps real paper figures at their original dimensions and allows two-axis scrolling on mobile.
- De-emphasized paper relations that do not include the selected lineage node; their labels stay hidden until the relation becomes relevant.
- Raised the dark-theme vermilion to `#e58a80`; measured contrast is 6.01:1 or higher on the reader's dark surfaces.
- Increased source-viewer open and close controls to a 44 px minimum target, and made unsupported dialog browsers open the source image directly.

## Interaction and accessibility checks

- Paper/lineage tabs, lane filters, paper nodes, source links, drawers, scrim, search, and theme toggle work in the browser.
- Mobile drawers are mutually exclusive and close through the scrim.
- The lineage has textual lane and relationship labels; meaning is not conveyed by color alone.
- Focus-visible styles, semantic buttons/tabs, alt text, a named scroll region, reduced-motion handling, and 44 px mobile controls are present.
- Browser console after desktop and mobile interaction: no warnings or errors.
- Independent final visual review: Approved, with no P0 or P1 release blockers.

## Automated checks

- Reading package validation: 11 packages, 0 errors.
- Reader, atlas, import-standard, papers, homepage, and Gurnee requirement tests: passed.
- `node --check papers/shared/reader.js`: passed.
- `git diff --check`: passed.
- Impeccable detector: no findings.

final result: passed
