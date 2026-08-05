# GoEmotions Disagreement-aware Evaluation

This module contains two validation-only diagnostics over frozen GoEmotions predictions:

- EXP-036 covers the 174 dev rows whose simplified target contains `neutral` plus another emotion.
- EXP-037 extends the analysis to all 5,426 dev rows and adds clear-rater vote-fraction soft-label
  Macro-F1.

Both compare frozen EXP-020, EXP-029, and EXP-033 predictions. The rater-aware views are diagnostic
only; they neither replace official metrics nor select a model. EXP-037 found that the full-dev
EXP-029 versus EXP-020 gap remains under both soft Macro-F1 and expected individual-rater set-F1.

## Commands

The config SHA-256 is required so the protocol, inputs, comparisons, and decision rules cannot be
changed silently at execution time.

```bash
python3 experiments/goemotions/disagreement-aware-evaluation/run_rater_aware_evaluation.py \
  --config experiments/goemotions/disagreement-aware-evaluation/configs/exp-036-dev-rater-aware-diagnostic.json \
  --config-sha256 <frozen-config-sha256>

python3 experiments/goemotions/disagreement-aware-evaluation/verify_rater_aware_evaluation.py \
  --config experiments/goemotions/disagreement-aware-evaluation/configs/exp-036-dev-rater-aware-diagnostic.json \
  --config-sha256 <frozen-config-sha256> \
  --check
```

EXP-037 uses the frozen config SHA-256
`34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d`:

```bash
python3 experiments/goemotions/disagreement-aware-evaluation/run_full_dev_rater_aware_evaluation.py \
  --config experiments/goemotions/disagreement-aware-evaluation/configs/exp-037-full-dev-rater-aware-diagnostic.json \
  --config-sha256 34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d

python3 experiments/goemotions/disagreement-aware-evaluation/verify_full_dev_rater_aware_evaluation_v2.py \
  --config experiments/goemotions/disagreement-aware-evaluation/configs/exp-037-full-dev-rater-aware-diagnostic.json \
  --config-sha256 34cab8d72d14a961f8ea6f2f18312f010f2ae6d2715272f66926c6305fb3c29d \
  --check
```

The original EXP-037 verifier remains frozen. Its first verification attempt stopped on the JSON
integer-key/string-key serialization mismatch documented in
`protocols/exp-037-verifier-correction-2026-08-04.md`; the V2 wrapper changes only that comparison
and records its own SHA-256 in `verification.json`.
