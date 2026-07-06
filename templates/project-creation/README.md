# Project Creation Templates

This is not a generator. It is a compact reference for future Codex runs when the user asks to create a new project from natural-language content.

For the full decision rules, read `docs/project-creation-workflow.md` first.

## Knowledge / Learning / Roadmap

Use when the project is mainly a learning plan, interview prep system, knowledge base, or roadmap.

```text
projects/{slug}/
  index.html
  README.md
  roadmap/
    modules/
      overview.md
      module-name.md
    roadmap-data.json
    roadmap-reader.css
    roadmap-reader.js
  scripts/
    build-roadmap-data.mjs
```

Default page: Foundations-style reader/dashboard.

Required checks:

- `node --check projects/{slug}/roadmap/roadmap-reader.js`
- `node --check projects/{slug}/scripts/build-roadmap-data.mjs`
- Run the project-specific build script.
- `node tests/projects-requirements.mjs` when the project directory page or manifest changes.
- `git diff --check`

## Paper / Topic Reading

Use when the project is mainly a paper, paper cluster, or literature reading packet.

```text
papers/{slug}/
  index.html
  downloaded-papers.md
  notes-cn/
  pdfs/
  html/
sources/{slug}-sources.md
questions/{slug}/open-questions.md
```

Default page: paper reader or structured paper note.

Required checks:

- `node tests/papers-requirements.mjs`
- `node tests/paper-reader-requirements.mjs` when shared reader behavior changes.
- `git diff --check`

## Engineering / Tool / Experiment

Use when the project must run, test, or demonstrate a system.

```text
projects/{slug}/
  README.md
  docs/
    spec.md
    plan.md
  src/
  tests/
```

Default page: no reader unless the user asks for a demo or public project page.

Required checks:

- Project-specific lint/test/build commands from `README.md`.
- Smoke test for the runnable path.
- `node tests/projects-requirements.mjs` when the project directory page or manifest changes.
- `git diff --check`

## Research Project

Use when the project is mainly a durable research question, hypothesis system, mechanism map, or experiment design.

```text
projects/{slug}/
  README.md
  research-roadmap.md
  hypotheses.md
questions/{slug}/open-questions.md
sources/{slug}-sources.md
```

Default page: Markdown-first; add a reader/dashboard only when public navigation materially helps.

Required checks:

- Evidence strength and claim type are explicit.
- `questions/{slug}/open-questions.md` has status and next action.
- Source maps stay in `sources/`.
- `git diff --check`

## Hybrid Project

Use when the project mixes runnable engineering, learning notes, paper reading, and research questions.

```text
projects/{slug}/
  README.md
  docs/
  src/
  tests/
  learning/
questions/{slug}/open-questions.md
sources/{slug}-sources.md
```

Default page: the main artifact controls the homepage. Supporting materials are linked by role instead of merged into one large file.

Required checks:

- Run the checks for each active layer.
- Confirm the project homepage links to supporting learning, source, and question files.
- `git diff --check`
