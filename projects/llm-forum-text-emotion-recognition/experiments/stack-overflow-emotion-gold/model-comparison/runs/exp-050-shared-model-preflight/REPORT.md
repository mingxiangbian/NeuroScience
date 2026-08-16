# EXP-050 Shared Model Preflight

## Status

`Verified` on 2026-08-13. The successful run passed all five train-only stages,
and the independent verifier passed 77/77 checks.

This experiment verifies that the frozen M1-M4 implementations are executable.
It does not estimate classification performance or select a model.

## Data Boundary

- Dataset protocol: `DATA-SO-TASK-V1`
- Row-level input: 24 deterministically selected training rows
- Coverage: all six positive labels, 5 neutral rows, 4 two-label rows
- Validation accessed: no
- Test accessed: no
- Performance metrics computed: no
- Public raw text, row labels, IDs, or raw generations: none

The complete 3,360-row train split was tokenized only to validate the frozen
length contract. RoBERTa had a maximum length of 222 tokens and Qwen had a
maximum length of 341 tokens, below their limits of 256 and 384.

## Gates

| Stage | Verified outcome | Wall time | Peak memory |
| --- | --- | ---: | ---: |
| static | Hashes, label order, deterministic selection, prompt suffix and no-truncation gates passed | 5.05 s | N/A |
| M1 | Two finite BCE updates; logits `[12, 6]`; classifier changed | 5.61 s | N/A |
| M2 | Frozen Qwen; `[1, 2560]` pooled state; 15,366-parameter head changed | 6.98 s | 8.25 GB |
| M3 | Matched M2 head/logits; zero initial LoRA delta; 112 insertions and both optimizers updated | 8.95 s | 8.54 GB |
| M4 | Matched M3 LoRA initialization; assistant-only loss; four outputs parsed without retry | 17.60 s | 8.91 GB |

M3 exposed exactly 7,340,032 LoRA parameters and 15,366 head parameters. All
112 `lora_b` tensors became nonzero after two updates. M4 used the same LoRA
initialization hash and updated the same 112 insertion points.

The four M4 outputs were all invalid under the deliberately strict canonical
JSON parser: three used noncanonical JSON formatting and one repeated a label.
This is an expectedly weak two-step smoke observation, not evidence about M4
accuracy or final format validity after formal training.

## Incident

The first attempt stopped before LoRA insertion or any M3 optimizer step. M2
hashed wrapper-scoped names (`head.weight`, `head.bias`) while M3 hashed the
same tensors with head-scoped names (`weight`, `bias`). Because names are part
of the digest, equal initialization tensors were falsely reported as unequal.

The correction changed only the digest scope. The failed attempt remains in
`../exp-050-shared-model-preflight-attempt-1/`; the successful run restarted
from static and froze the corrected runner.

## Verification

```bash
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/model-comparison/verify_preflight.py
```

The verifier independently reconstructed the sample selection, token-length
summaries, parameter counts, initialization matches, update gates, strict M4
parsing, privacy boundary, resource budget and train-only access contract.

## Decision

EXP-050 clears the implementation gate for formal M1-M4 work. The next formal
experiment is EXP-051: three-seed RoBERTa training and validation under the
already registered protocol. Stack Overflow test remains sealed.
