# Phase C Reproducibility and Offline Delivery Package

Date: 2026-09-01
Status: frozen references for the bounded local research closeout

## Canonical code identity

The current executable runtime files match every non-protocol member of the EXP-086 frozen archive:

| Item | Identity |
| --- | --- |
| EXP-086 37-member runtime/protocol archive | `97ee2c550265d864a6dab2b43928cc956eac57ac9c27397ed4efb3ee21440818` |
| Current runtime versus that archive | 0 mismatches |
| Earlier EXP-085 attempt 2 33-member archive | `56386775dd61226ba3fe7f214c89b3a55cad393bb61ed868b77bc5f6082f0435` |
| API requirements lock | `2248edffce1c9a653d9d7e33e0571e5f191229aa02fcab08699766c30362c44d` |
| `start.py` | `f6bffa1e4750ad0805246031fed72be821e67fc4c6fe98d1ce05eb9ff8ab7c74` |
| `static/index.html` | `5e79a3ed18f6bf746511199f9fcfc52e88884ab1a476ed7d8a00468919083bf7` |
| `static/app.js` | `954526d0058c2bc52033e8566b6ddcc3f76943840a01729beb1c07932eb0d805` |
| `static/app.css` | `14eacb4acebe4824b9d0eaf75349eb0b15c6aa616f4120df9780d9ea218e7937` |

Repository HEAD at closeout inspection was `880cab37e6cab201b1646c407af66fb2bd0cbdae` on
`codex/exp061-exp062-preflight-configs`, but the working tree contains the current Phase C implementation and
documentation changes. HEAD is therefore not presented as the release identity. The frozen code archive is the
canonical executable reference until the user separately requests a commit.

## Environments

### Local API environment

| Component | Version |
| --- | --- |
| Python | 3.12.13 |
| SQLite library | 3.53.1 |
| FastAPI | 0.116.1 |
| Uvicorn | 0.35.0 |
| HTTPX | 0.28.1 |
| NumPy | 2.4.6 |

The complete API environment is pinned in `requirements-lock.txt`. `pip check` passed during release QA.

### Frozen model runtime

| Component | Version |
| --- | --- |
| Python | 3.11.15 |
| NumPy | 2.4.6 |
| Torch | 2.9.1 |
| Transformers | 5.14.1 |
| Tokenizers | 0.22.2 |
| MLX | 0.32.0 |
| MLX-LM | 0.31.3 |
| Safetensors | 0.8.0 |

The model runtime is `/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python`. Website dependencies must not
be installed into it. Full model, Router, threshold, prompt, tokenizer, label-order, and asset identities are in
[model-bundle.md](model-bundle.md) and the EXP-066 frozen config referenced there.

## Schema identity

- SQLite tables are code-defined in `topicweb/store.py`; this version does not set a separate
  `PRAGMA user_version`.
- Derived dashboard objects declare `derived.schema_version = topicweb-derived-v1`.
- Database compatibility is therefore bound to the frozen runtime archive and data contract, not to an invented
  standalone SQLite schema number.
- Field definitions and retention behavior are in [data-schema.md](data-schema.md).

## One-command local operation

From this module:

```sh
.venv/bin/python start.py
```

- Open `http://127.0.0.1:8787` and use the locally generated `private/access-token`.
- Health check: `GET http://127.0.0.1:8787/api/health` returns `{"status":"ok"}`.
- Database initialization: `Store` creates the private directory and SQLite tables on first start.
- Stop: send Ctrl-C. Running work is stopped and retained according to its actual terminal state; it is not
  silently resumed.
- The API process does not load model weights. Model work starts in independent child processes only when a task
  reaches inference.
- M1-only does not require M3. Research fails closed if required M3 work fails. Demo may use the current item's M1
  result for registered M3 runtime failure or budget exhaustion and records the fallback reason.
- A second dispatcher or inherited heavy-process lock is rejected; do not delete lock files to bypass it.

## Offline defense snapshots

The snapshots remain local and Git-ignored. They should be replayed as saved evidence rather than recollected
during a defense.

| Snapshot | Local artifact | Identity and use |
| --- | --- | --- |
| Stack Overflow fixed 340-item workload | `private/validation/exp-085/attempt-2/bench/jobs.sqlite3` | File SHA-256 `28ea54d7c3d7eda07db397d843277747613da4c87d7e80269fdbaa17efe3bbf1`; logical source SHA-256 `8c0cc285ff71fd041eb832d5a8422d68dcaad84228a9c3b00d14f213dacd17a4` |
| Python Help fixed 400-item run | `private/validation/exp-086/attempt-1/bench/jobs.sqlite3` | File SHA-256 `020547643df663f31cdd03fd36104b079de1c4acfe11dcc5bc8b1c77f6233b74`; snapshot SHA-256 `1225133c9cbdddabbe12222e79af33805d8120446ffc58c855bd3693b1365e4c` |
| Python Help verified Dashboard | `private/validation/exp-086/attempt-1/dashboard.json` | SHA-256 `8b8753970facb89b7d4d10031b95477736a7efd6b478d443fd773302c790fbcd` |
| Python Help M1 transfer | `private/validation/exp-086/attempt-1/transfers.jsonl` | Transfer identity `4e92e16cd2ea2ebf4a1ffca43f66f1cecf39b5cc004b4cfb6530e3f7178c4558` |

The Discourse experiment completed its registered 400-item task while `sampling_complete=false` and
`collection_complete=false`; one topic was truncated at the item cap. Experiment completion is not content
collection completeness.

## Evidence entry points

- [Release acceptance](release-acceptance.md)
- [User guide](user-guide.md)
- [Defense script](demo-script.md)
- [Thesis integration draft](thesis-integration.md)
- [Final-scope decision](../../experiments/stack-overflow-emotion-gold/protocols/dec-phase-c-final-scope-and-closeout-v1.md)
- `private/reports/final-claims-2026-09-01.md`
- `private/reports/phase-c-final-closeout-2026-09-01.md`
- `private/reports/phase-c1-bounded-runtime-discourse-report-2026-09-01.md`

## Privacy and distribution boundary

The databases, tokens, screenshots, source text, usernames, per-item results, and reports under `private/` are
Git-ignored. Do not upload or publicly serve them. Public code and documentation describe identities and aggregate
evidence only. The package is for local non-commercial research and defense preparation, not public corpus or
commercial content redistribution.
