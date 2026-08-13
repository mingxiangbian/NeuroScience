# Source-blind Diagnostic Adjudicator

Local two-phase reviewer for `DATA-FCTX-ADJ-DIAG-V1`.

## Privacy boundary

- The browser receives full text only for the active blind case.
- Phase 1 responses contain no candidate decisions.
- Phase 2 exposes only `Candidate A/B/C` and compact decisions.
- The server does not read or route `source-map.jsonl`.
- All records remain under the gitignored private data tree.

This pass is diagnostic model-assisted adjudication. It is not independent human
reannotation, inter-annotator agreement, ontology acceptance or formal gold-label
construction.

## Build the frozen bundle

From `projects/llm-forum-text-emotion-recognition/`:

```bash
python3 experiments/forum-context/annotation/build_blind_adjudication_v1.py
```

The command refuses to overwrite an existing bundle or tracked report.

## Run locally

From the repository root:

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/blind_adjudicator/server.py
```

Open `http://127.0.0.1:8766`. A continuous session stops after 20 completed cases.
The next session resumes at the first unlocked phase.

For a one-case synthetic interface check:

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/blind_adjudicator/server.py --demo
```
