# Stack Overflow Post-Test Analysis

This directory contains bounded, read-only analyses of the consumed Stack Overflow
test split. `EXP-057` only transforms verified public aggregates into thesis-ready
tables. It does not read private predictions or labels and cannot change any frozen
model decision.

Run from the repository root:

```bash
python3 projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/post-test-analysis/analyze_exp057.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/post-test-analysis/configs/exp-057-read-only-result-synthesis-attempt-2.json

python3 projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/post-test-analysis/verify_exp057.py \
  --config projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/post-test-analysis/configs/exp-057-read-only-result-synthesis-attempt-2.json \
  --run-dir projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/post-test-analysis/runs/exp-057-read-only-result-synthesis-attempt-2
```
