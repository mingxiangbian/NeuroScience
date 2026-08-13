# Local Human Annotator

This dependency-free local tool executes human-blind pass 1 for
`DATA-FCTX-LABEL-V1` and `DATA-FCTX-SAMPLE-V1`.

## Run

From the repository root:

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/human_annotator/server.py
```

Open `http://127.0.0.1:8765`. The server refuses non-loopback hosts, loads no
external assets and does not expose a generic file route.

Use the synthetic fixture without touching private records:

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/forum-context/annotation/human_annotator/server.py --demo --port 8766
```

## Privacy and state contract

- Stage A responses contain only the target body and progress metadata.
- Stage B context is serialized only after the Stage A decision has been
  atomically written and locked.
- Submitted Stage A and Stage B decisions are immutable through the API.
- The server reads only private views and human pass-1 records. Sealed model
  predictions and sampling-lane metadata are outside its data path.
- Real records are written under
  `data/iac2/annotations/pilot-v1/records/human-pass-1/`, which is gitignored.
- Record directories use mode `0700`; record and session-log files use `0600`.
- Every server session records start, end, Stage A lock and completed-case
  events without copying forum text or emotion labels into the session log.
- A session closes after at most 40 completed cases. More than six contextual
  `unusable` cases activates the frozen quality stop.

The browser never receives a Stage A label after it is locked. Stage B shows
only that the earlier decision exists, preventing later context from changing
the recorded target-only judgment.
