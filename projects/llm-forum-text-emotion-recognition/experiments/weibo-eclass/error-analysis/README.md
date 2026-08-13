# Weibo EClass Error Analysis

This module performs descriptive analysis of already-frozen validation predictions.
It does not train models, rerun inference, change prompts, select checkpoints, or open
the sealed test split.

Current experiment: `EXP-048`, comparing the matched no-adapter Qwen reference and
three EXP-047 LoRA seeds with the three EXP-042 M2 target-only encoder seeds.

Selected raw text and the private case-to-source mapping remain under the gitignored
`runs/**/private/` directory. Tracked artifacts contain derived case IDs only.

Run order:

```bash
python3 experiments/weibo-eclass/error-analysis/test_error_analysis.py
python3 experiments/weibo-eclass/error-analysis/analyze_frozen_dev_errors.py
# Complete manual_annotations.csv from the private review file.
python3 experiments/weibo-eclass/error-analysis/summarize_review.py
python3 experiments/weibo-eclass/error-analysis/verify_error_analysis.py
```
