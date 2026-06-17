# GitHub Pages Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static GitHub Pages homepage with an animated brain/network visual for the neuroscience x AI research workspace.

**Architecture:** Use a single `index.html` with embedded CSS and Canvas JavaScript. Keep the animation layer separate from the navigation/content structure so it can later be replaced by a Three.js scene without changing the homepage content.

**Tech Stack:** HTML, CSS, Canvas 2D, GitHub Pages from the `main` branch root.

---

### Task 1: Static Animated Homepage

**Files:**
- Create: `index.html`
- Modify: `README.md`

- [ ] **Step 1: Create `index.html`**

Implement a full-page static homepage with:
- Canvas brain/network animation.
- Main title and project description.
- Navigation links to `INDEX.md`, `README.md`, `knowledge/`, `papers/`, `projects/`, `sources/`.
- Research workflow overview.
- Reduced-motion support.

- [ ] **Step 2: Update `README.md`**

Add a short homepage section linking to `index.html` and the future GitHub Pages URL.

- [ ] **Step 3: Preview locally**

Run a local static server and verify `index.html` renders.

- [ ] **Step 4: Enable GitHub Pages**

Configure GitHub Pages to serve from `main` branch root.

- [ ] **Step 5: Push and verify**

Commit, push, then verify the GitHub Pages URL or report the exact blocker.
