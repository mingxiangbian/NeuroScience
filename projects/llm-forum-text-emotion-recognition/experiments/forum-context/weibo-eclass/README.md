# Weibo EClass Data Track

This module constructs the frozen single-label Weibo EClass dataset defined by
[`DATA-WEIBO-TASK-V1`](../protocols/data-weibo-eclass-task-v1.md).

It performs source parsing, structural validation, label filtering, target-text
deduplication, leakage-component splitting, paired-view export, and test-label
sealing. It does not train or evaluate a model.

## Status

`DATA-WEIBO-TASK-V1` is `Verified` as of 2026-08-08. The final task contains
8,540 records split into 5,995 train, 1,272 validation and 1,273 sealed-test
records. The independent verifier passed 33/33 checks, and all 10 synthetic
unit tests pass.

The superseded pre-balance output is retained privately as
`derived-private/eclass-v1-pre-balance/`; it is not an experiment input.

## Commands

```bash
python3 experiments/forum-context/weibo-eclass/prepare_weibo_eclass_v1.py
python3 experiments/forum-context/weibo-eclass/verify_weibo_eclass_v1.py
python3 -m unittest discover \
  -s experiments/forum-context/weibo-eclass/tests \
  -p 'test_*.py'
```

Run these commands from `projects/llm-forum-text-emotion-recognition/`.

Private row-level artifacts are written to
`data/weibo-emotion-corpus/derived-private/eclass-v1/` and are ignored by Git.
Only aggregate reports are public.

Public aggregate outputs:

- `data/weibo-emotion-corpus/eclass-v1.manifest.json`
- `experiments/forum-context/weibo-eclass/reports/data-weibo-eclass-v1.json`
- `experiments/forum-context/weibo-eclass/reports/data-weibo-eclass-v1-verification.json`
