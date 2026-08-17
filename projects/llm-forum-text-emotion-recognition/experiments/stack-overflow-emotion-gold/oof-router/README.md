# OOF Calibration And Router Experiments

This module implements the conditional `RQ-S3` system line:

```text
EXP-058 paired M1/M3 OOF logits
-> EXP-059 calibration and selective prediction
-> EXP-060 pre-Qwen deployable router
```

EXP-058 and EXP-059 are complete. EXP-058 produced one aligned raw-logit pair for all
`3,360` train rows under a deterministic, duplicate-component-disjoint five-fold
assignment; its final verifier passed `26,989/26,989`. EXP-059 then fitted calibration
and thresholds in a second five-fold cross-fitting layer, evaluated selective prediction,
and recomputed the non-deployable whole-vector oracle. Its no-result preflight passed
`22/22`, contract tests passed `7/7`, and amended independent final verification passed
`4,684/4,684`. Neither experiment accessed validation or test.

Both families retained identity calibration: cross-fitted temperature scaling worsened
NLL for M1 and worsened both NLL and Brier for M3. The preregistered abstention point
passed for M1 at about 90% coverage using maximum entropy and for M3 at about 80% using
margin. M1's 20% Hamming-risk reduction is borderline because its component-bootstrap
interval crosses the 20% gate; M3's interval remains above it. The oracle selects M3 for
`313/3,360` rows and leaves positive six-label and five-label Macro-F1 headroom. EXP-060
was then frozen with a 14-column pre-Qwen whitelist, nested threshold recomputation and
a fixed logistic router contract. Its preserved no-result preflight passed `25/25`, its
synthetic preflight tests passed `7/7`, and the preflight verifier passed `66/66`. The
formal contract suite subsequently passed `23/23`, and the formal run is `Verified Pass`
after `4,412/4,412` independent verification checks.

The selected formal policy is the logistic router. It routes `501/3,360` rows
(`14.9107%`) and changes six-label Macro-F1 by `+0.040168`, five-label Macro-F1 by
`+0.006097`, and Hamming loss by `-0.004365` relative to M1-only. Router target
discrimination is PR-AUC=`0.318653` and ROC-AUC=`0.850804`. The 2,000-replicate
duplicate-component bootstrap 95% intervals are `[13.6673%, 16.2172%]` for actual call
rate, `[+0.009891, +0.071126]` for six-label Macro-F1 gain,
`[-0.007688, +0.019733]` for five-label Macro-F1 gain, and
`[-0.006332, -0.002515]` for Hamming-loss delta. The frozen development gate is decided
by the point estimate; the intervals only qualify stability. All evidence is nested
train OOF: EXP-060 did not access validation or test, read raw text, or run M1/M3 model
forward. This is not an independent-test result or evidence of general deployment
benefit.

Historical EXP-058 command record (not a current rerun recipe): the attempt-2 config
pins the then-current protocol bytes, so the builder command intentionally fails the
source-integrity guard against the later canonical protocol. Audit that completed run
through its archived `frozen-sources/`; the verifier command remains valid for the
sealed run directory.

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/build_exp058_fold_manifest.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-058-fold-manifest-preflight-attempt-2.json

python3 projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/verify_exp058_fold_manifest.py \
  --run-dir projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/runs/exp-058-fold-manifest-preflight-attempt-2
```

Fold-0 dry-run stages use their matching environments and the same frozen config:

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/run_exp058_oof_dry_run.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-058-oof-consumer-dry-run-fold-0.json \
  --stage static

/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/run_exp058_oof_dry_run.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-058-oof-consumer-dry-run-fold-0.json \
  --stage m1

/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python \
  projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/run_exp058_oof_dry_run.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-058-oof-consumer-dry-run-fold-0.json \
  --stage m3

python3 projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/verify_exp058_oof_dry_run.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/configs/exp-058-oof-consumer-dry-run-fold-0.json
```

Public fold rows contain only anonymous sample/component IDs and fold IDs. Labels,
logits, probabilities and row-level diagnostic records remain under Git-ignored
`private/` directories. The EXP-058 production report is in
`runs/exp-058-paired-oof-production/REPORT.md`; the verified EXP-059 report is in
`runs/exp-059-calibration-selective-prediction/REPORT.md`. The preserved EXP-060
preflight evidence is in `runs/exp-060-pre-qwen-router-preflight/`. The formal EXP-060
report and independent verification summary are respectively in
`runs/exp-060-pre-qwen-router/REPORT.md` and
`runs/exp-060-pre-qwen-router/VERIFICATION-SUMMARY.md`.
