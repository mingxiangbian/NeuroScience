# Language

This folder collects language-learning projects that need durable prompts, diagnostic templates, and executable study plans.

## Projects

- [IELTS Academic](ielts-academic/) - a diagnostic-driven IELTS Academic project built around reusable multi-agent prompts, adaptive 8-week planning, error regression checks, notes, journal entries, and a [static reader](ielts-academic/index.html).

## Workflow

For the IELTS Academic project, edit the Markdown and JSON source files in `ielts-academic/`, then run:

```bash
node projects/language/ielts-academic/scripts/build-ielts-data.mjs
```

The generated `ielts-academic/site/ielts-data.json` powers the static reader. The browser is read-only; do not store score, error, checkpoint, notes, or journal source data only in local browser state.

## Boundary

This is not a general English notebook. Put reusable learning projects here; put dated session records under `sessions/` only when a conversation itself needs archiving.
