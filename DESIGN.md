---
name: NeuroScience x AI
description: A personal long-use research workspace with rice-paper surfaces, deep ink structure, and restrained reader tooling.
colors:
  ink: "#1f2724"
  paper: "#f4efe3"
  paper-soft: "#fbf8ef"
  paper-warm: "#e8dcc8"
  dai-blue: "#183c49"
  flower-blue: "#2e6f77"
  cinnabar: "#a64338"
  seal-red: "#b24338"
  gold: "#9b7430"
  dark-surface: "#111615"
  dark-ink: "#eef0e7"
typography:
  display:
    fontFamily: "\"Songti SC\", \"STSong\", \"Noto Serif SC\", Georgia, serif"
    fontSize: "clamp(36px, 5vw, 56px)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0"
  headline:
    fontFamily: "\"Songti SC\", \"STSong\", \"Noto Serif SC\", Georgia, serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "0"
  body:
    fontFamily: "\"Inter\", \"SF Pro Text\", \"PingFang SC\", \"Noto Sans SC\", system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.78
  label:
    fontFamily: "\"Inter\", \"SF Pro Text\", \"PingFang SC\", \"Noto Sans SC\", system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.6
    letterSpacing: "0.02em"
  mono:
    fontFamily: "\"SFMono-Regular\", \"Cascadia Code\", \"Roboto Mono\", Consolas, monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "12px"
  reader-toolbar: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  section: "48px"
  page: "64px"
components:
  icon-button:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    size: "42px"
  search-field:
    backgroundColor: "{colors.paper-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "42px"
    padding: "0 12px"
  reader-card:
    backgroundColor: "{colors.paper-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px"
  status-chip:
    backgroundColor: "{colors.paper-soft}"
    textColor: "{colors.dai-blue}"
    rounded: "{rounded.pill}"
    padding: "4px 8px"
  project-card:
    backgroundColor: "{colors.paper-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "clamp(92px, 13vh, 112px) 16px clamp(50px, 6vh, 66px)"
---

# Design System: NeuroScience x AI

## 1. Overview

**Creative North Star: "The Living Research Notebook"**

This system should feel like a personal research instrument that has been used, tuned, and trusted over time. The identity is archival and crafted: pale rice-paper fields, deep ink structure, small cinnabar or blue accents, and dense reader controls that stay quiet until needed.

The workspace is product UI, not a marketing page. Beauty matters because the pages are used repeatedly, but the reader surfaces must keep navigation, search, module status, and context recovery clear. The best pages feel like a careful notebook with working instruments layered onto it, not a generic dashboard.

The visual system explicitly rejects generic AI-generated UI: template SaaS panels, repetitive card grids, decorative gradients, stock dashboard tropes, excessive glass effects, and ornamental moves that make the knowledge base harder to use.

**Key Characteristics:**
- Rice-paper surfaces anchored by deep ink text and thin structural lines.
- Serif or Songti display moments paired with practical sans body text.
- Restrained accent vocabulary: dai blue, flower blue, cinnabar, seal red, and gold.
- Compact, stateful reader chrome with recognizable controls and stable density.
- Project-specific beauty without losing the six-space knowledge map.

## 2. Colors

The palette is a paper-and-ink system with research accents, not a generic warm beige UI.

### Primary
- **Deep Ink**: Main text, icons, line work, and the twin-arc mark. It should carry structure before any accent color is used.
- **Rice Paper**: Default page surface for long reading. It is the workspace ground, not a decorative background.

### Secondary
- **Dai Blue**: Primary reader accent for focus, section progress, active state, and quiet emphasis.
- **Flower Blue**: Homepage and project-index accent when a surface needs a clearer visual signal.

### Tertiary
- **Cinnabar**: Error, priority, annotation, and selected-state accent. It must stay rare.
- **Gold**: Secondary learning/status accent, especially for warning, score, or progress context.

### Neutral
- **Soft Paper**: Panels, cards, toolbar fields, and note containers.
- **Warm Paper**: Large background depth and atmospheric gradients.
- **Dark Surface**: Optional dark reader mode surface. Use only when the page already supports theme switching.
- **Dark Ink**: Text in dark mode.

### Named Rules

**The Ink-First Rule.** Structure is carried by ink, thin lines, spacing, and type before accent color. If every section needs a colored marker to make sense, the hierarchy is wrong.

**The Rare Cinnabar Rule.** Cinnabar and seal red are for priority, selection, warnings, or identity marks. They should not decorate inactive UI.

**The No Generic Beige Rule.** Rice paper is allowed only when it is visibly tied to the existing Cyber Ink identity. Do not turn new pages into generic cream SaaS layouts.

## 3. Typography

**Display Font:** "Songti SC", "STSong", "Noto Serif SC", Georgia, serif
**Body Font:** "Inter", "SF Pro Text", "PingFang SC", "Noto Sans SC", system-ui, sans-serif
**Label/Mono Font:** "SFMono-Regular", "Cascadia Code", "Roboto Mono", Consolas, monospace

**Character:** The type system pairs a research-notebook serif voice with utilitarian product controls. Display typography can feel crafted; labels and controls must stay legible and familiar.

### Hierarchy
- **Display** (700, clamp(36px, 5vw, 56px), 1): Module titles, project-reader headers, and major surface identity.
- **Headline** (700, 24px, 1.25): Section titles and important card headings.
- **Title** (600, 18px, 1.35): Navigation groups, note headings, and compact dashboard titles.
- **Body** (400, 15px, 1.78): Long reader text. Keep prose comfortable; avoid dense paragraph walls without section structure.
- **Label** (600, 12px, 0.02em): Kicker, metadata, compact tags, keyboard hints, and module progress.

### Named Rules

**The Serif Is a Signal Rule.** Use Songti or serif for page and module meaning, not for every label. Buttons, search, metadata, and dense controls stay sans.

**The No Tracked Eyebrow Habit Rule.** Small labels are useful, but do not repeat tiny uppercase tracked eyebrows as section scaffolding. Labels must carry real information.

## 4. Elevation

Depth is mostly tonal and structural: translucent paper panels, thin borders, inset highlights, and low ambient shadows. Shadows are allowed for floating chrome, popovers, search results, and annotation tools, but ordinary content should not become a stack of ghost cards.

### Shadow Vocabulary
- **Reader Chrome Float** (`0 14px 40px rgba(19, 45, 42, 0.16)`): Toolbars and glassy reader controls in Foundations-style surfaces.
- **Popover Lift** (`0 8px 24px rgba(30, 42, 38, 0.16)`): Tooltips, search results, annotation bars, and small overlays.
- **Project Card Lift** (`0 22px 52px rgba(42, 35, 25, 0.18)`): Project index cards only, where physical page lift is part of the browsing metaphor.

### Named Rules

**The Tonal-Layer Rule.** Use background tone and border contrast before adding a shadow. A panel at rest should not need a large blur to separate from the page.

**The No Ghost-Card Rule.** Do not pair a decorative 1px border with a wide soft shadow on every card. Repeated border-plus-blur surfaces are a clear AI UI tell.

## 5. Components

### Buttons
- **Shape:** Reader buttons use a practical rounded square (12px) with a 42px touch target.
- **Primary:** This system currently relies more on icon buttons and active nav items than big CTA buttons. When a primary action exists, use deep ink or dai blue with paper text and compact padding.
- **Hover / Focus:** Hover can tint the paper surface. Focus must remain visible with a blue or ink outline, not just color change.
- **Secondary / Ghost:** Ghost controls may be transparent at rest, but they must show clear hover and pressed states.

### Chips
- **Style:** Pill chips use soft paper backgrounds, dai-blue or ink text, and compact padding.
- **State:** Selected or high-priority chips may use cinnabar only when they reflect a real state such as risk, error, or priority.

### Cards / Containers
- **Corner Style:** Reader containers use 12px. Project index cards use tighter paper-object corners around 6-8px.
- **Background:** Use soft paper, paper-strong, or controlled translucent glass over paper. Avoid pure white card stacks.
- **Shadow Strategy:** Follow the Tonal-Layer Rule; shadows appear for overlays and selected physical cards, not every block.
- **Border:** Thin ink or paper-edge borders are acceptable. Avoid colored side-stripe borders.
- **Internal Padding:** Dense cards use 12px; reader panels use 16-24px; project cards can use larger vertical space when the card itself is the object.

### Inputs / Fields
- **Style:** Search fields use 42px height, 12px radius, paper/glass background, and inline iconography.
- **Focus:** Focus should increase border contrast and keep the field visually anchored. Avoid glowing neon focus rings.
- **Error / Disabled:** Errors should use cinnabar text or border with explanatory copy. Disabled fields must remain readable.

### Navigation
- **Style:** Reader navigation is a three-column shell: module directory, main reading surface, context note panel.
- **States:** Active nav items need both color and positional/state indication. Collapsed sidebars must preserve orientation through rail markers or tooltips.
- **Mobile:** Mobile should collapse side and note panels into drawers without losing search or current-module awareness.

### Signature Component

The reader shell is the signature product component: sticky toolbar, collapsible directory, central module body, section rail, search overlay, and contextual note panel. It should stay coherent across Foundations and Language so the user can switch projects without relearning the interface.

## 6. Do's and Don'ts

### Do:
- **Do** preserve the rice-paper, deep-ink, restrained accent identity when working inside `projects/foundations` and `projects/language`.
- **Do** make module status, current section, next action, and context panel state obvious after the user returns to a page days later.
- **Do** keep long-reading text comfortable: body around 15px, line-height around 1.78, and prose broken into meaningful sections.
- **Do** use the twin-arc mark and existing palette as continuity signals where they support navigation or identity.
- **Do** use compact, familiar product controls for repeated workflows.

### Don't:
- **Don't** redesign the root homepage or `papers/brain-memory-for-ai-agents` by default; PRODUCT.md marks them as already close to target.
- **Don't** ship generic AI-generated UI: template SaaS panels, repetitive card grids, decorative gradients, stock dashboard tropes, or excessive glass effects.
- **Don't** flatten the workspace into a plain documentation site.
- **Don't** spread ornamental Cyber Ink effects into dense reader surfaces when they reduce clarity.
- **Don't** use colored side-stripe borders, gradient text, or decorative grid backgrounds as filler.
- **Don't** let text overflow controls, cards, module labels, or mobile drawers.
