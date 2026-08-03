# GoEmotions Error Analysis

This module performs descriptive analysis of already-frozen GoEmotions dev
predictions. It does not train models, rerun inference, select checkpoints, or
open the test split.

Current experiment: `EXP-030`, comparing EXP-020 BERT, the selected EXP-025
frozen Qwen condition, and the selected EXP-029 LoRA Qwen condition.

Raw selected comments remain under a gitignored `runs/**/private/` directory.
Tracked artifacts use anonymous row numbers only.
