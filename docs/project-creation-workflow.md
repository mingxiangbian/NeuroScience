# Project Creation Workflow

This guide is the repo-local default for future "create a new project" requests. It turns a user's topic, content, and goal into a concrete project structure without re-litigating directories, page style, or basic validation.

Use this guide only inside the `NeuroScience` repo. It does not replace research protocols, paper review standards, or project-specific specs.

## Quick Start For New Projects

When the user asks to create a new project:

1. Infer the project type from the user's goal and content.
2. Pick the default location and output shape from the router below.
3. Ask only when the choice changes long-term organization, privacy, runtime, or overwrite risk.
4. Create the smallest durable project structure that satisfies the goal.
5. Add the project to the relevant directory page or manifest when it should be discoverable.
6. Run the verification checklist before reporting completion.

Do not ask the user to choose a structure when the content is enough to decide. Do not force engineering projects into the Foundations reader.

## Project Type Router

| Type | Trigger signals | Default location | Default presentation |
| --- | --- | --- | --- |
| knowledge / learning / roadmap | learning, prep, roadmap, knowledge base, review, module notes | `projects/{slug}/` | Foundations-style reader/dashboard |
| paper / topic reading | paper, reading notes, citation, method, evidence, limitations | `papers/{slug}/` | Paper reader or structured paper notes |
| engineering / tool / experiment | implement, app, tool, demo, agent, experiment system, runnable code | `projects/{slug}/` | README, spec, plan, source, tests, optional demo |
| research project | research question, hypothesis, mechanism, experiment design, staged conclusion | `projects/{slug}/` | README, research roadmap, hypotheses, linked questions and sources |
| hybrid project | mixes engineering, learning, paper reading, and research | `projects/{slug}/` for the main artifact | Split layers; project homepage links them |

## Directory Rules

- Project core belongs in `projects/{slug}/`.
- Paper-related learning material belongs in `papers/{slug}/`.
- source maps belong in `sources/`, even when they support one project.
- open questions belong in `questions/{slug}/`.
- Dated discussion records belong in `sessions/YYYY-MM-DD-{slug}.md`.
- Do not leave source maps or general open questions inside `projects/{slug}/` as the long-term home.

## Default Outputs

### Knowledge / Learning / Roadmap

Create:

- `projects/{slug}/index.html`
- `projects/{slug}/roadmap/modules/*.md`
- `projects/{slug}/roadmap/roadmap-data.json`
- `projects/{slug}/scripts/build-roadmap-data.mjs`
- A directory entry in `projects/manifest.json` or the current project directory page system

Defaults:

- Initial progress is `0` unless the user explicitly provides completed work.
- `Overview` is a dashboard, not a normal module.
- Main content is concept-centered; timeline is allowed but not the primary structure.
- Right-side notes are associated with knowledge cards; no associated note means blank.
- Reuse the current Foundations reader interaction pattern for search, navigation, local annotations, and collapsed section rail.

### Paper / Topic Reading

Create:

- A paper reader page or structured paper note under `papers/{slug}/`.
- Citation, research question, claim, method, key results, evidence strength, limitations, quality checks, takeaway, and open questions.
- `sources/{slug}-sources.md` when the work creates a source map.
- `questions/{slug}/open-questions.md` when the work creates durable questions.

Defaults:

- Separate literature claims, user hypotheses, and assistant synthesis.
- Use current sources for recent or contested claims.
- Keep PDFs, HTML exports, and notes organized under the paper topic directory when they are paper-specific.

### Engineering / Tool / Experiment

Create:

- `projects/{slug}/README.md`
- `projects/{slug}/docs/spec.md`
- `projects/{slug}/docs/plan.md`
- `projects/{slug}/src/`
- `projects/{slug}/tests/`

Defaults:

- Prioritize a runnable project over a decorative page.
- Add `index.html` only when a browser demo or public project page is part of the goal.
- State run commands, test commands, current limitations, and next engineering checkpoints.
- Do not hide source code behind a reader-style learning page.

### Research Project

Create:

- `projects/{slug}/README.md`
- `projects/{slug}/research-roadmap.md`
- `projects/{slug}/hypotheses.md`
- `questions/{slug}/open-questions.md` when durable questions exist
- `sources/{slug}-sources.md` when source maps exist

Defaults:

- Track evidence strength and claim type.
- Keep competing hypotheses explicit.
- Link sources and questions from the project README instead of moving them into the project folder.

### Hybrid Project

Create the main project under `projects/{slug}/`, then split supporting material by role:

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

Defaults:

- The main artifact controls the homepage.
- Learning pages, source maps, and open questions stay linked but separate.
- If the project includes both a runnable tool and a study roadmap, build the tool structure first and put the reader under `learning/`.

## Ask Only When

Ask a clarification question before creating files only when:

- The project could reasonably belong in both `projects/` and `papers/`, and the wrong location would harm long-term organization.
- The user asks for a public page but the content appears private, personal, or unsuitable for publishing.
- An engineering project requires a runtime choice that cannot be inferred from existing repo context.
- The requested outputs conflict, such as pure static GitHub Pages plus server-side persistence.
- The target directory already exists and would be overwritten.

## Verification Checklist

Always run the narrow checks relevant to the project type:

- Markdown or static-page hygiene: `git diff --check`
- New workflow rule coverage: `node tests/project-creation-workflow-requirements.mjs`
- Project directory coverage: `node tests/projects-requirements.mjs` when `projects/` changes
- Paper directory coverage: `node tests/papers-requirements.mjs` when `papers/` changes
- Reader syntax: `node --check path/to/reader.js` when a reader JS file changes
- Build script syntax: `node --check path/to/build-script.mjs` when a build script changes
- Generated data: run the project-specific build command when Markdown sources feed JSON
- Engineering project checks: run the project-specific lint/test/build command documented in its README

Report which files were created or updated, which commands passed, and any checks that were skipped because the project type did not require them.
