# EXP-051 Seed 42 Verification Summary

Status: `Verified` on 2026-08-13. This is a single-seed train + validation
integrity gate, not the registered three-seed M1 result. Test was not accessed.

## Result

| Measure | Fixed 0.5 | Shared threshold 0.25 |
| --- | ---: | ---: |
| Macro-F1 | 0.598759 | 0.604619 |
| Macro precision | 0.590223 | 0.551166 |
| Macro recall | 0.608648 | 0.671676 |
| Micro-F1 | 0.755507 | 0.764645 |
| Weighted-F1 | 0.747289 | 0.759476 |
| Strict subset accuracy | 0.761111 | 0.740278 |
| Hamming loss | 0.051389 | 0.053009 |
| Five-label Macro-F1 without surprise | 0.718511 | 0.725543 |

Epoch 4 was selected by the frozen fixed-threshold rule. The shared-threshold
component-bootstrap Macro-F1 95% interval was `[0.559703, 0.638948]` over 2,000
duplicate-component resamples. `surprise` had seven validation positives, zero
predicted positives and F1 `0`; this low-support failure must remain visible.

## Recovery And Verification

The first MPS attempt stopped during epoch 1 because the unified-memory
allocator reached its safety limit. It produced no complete-epoch validation
metric and is retained at `../../exp-051-m1-roberta/seed-42/`. The safety limit
was not disabled.

A frozen 10-step train-only CPU preflight then passed. The CPU recovery kept the
scientific configuration unchanged, restarted from model initialization and
completed in 1,859.22 seconds with peak process RSS 6.42 GB. CPU and MPS are not
claimed to be bitwise equivalent.

The independent verifier replayed the selected checkpoint and recomputed saved
probabilities, checkpoint and threshold selection, aggregate and per-label
metrics, component bootstrap, hashes, resource gates, split access, Git ignore
and public privacy. It passed `67/67` checks with no failed check. Seeds 43/44
remain unauthorized, and Stack Overflow test remains sealed.
