# Qwen3-1.7B Post-trained Model

This directory records the official post-trained model used by the local LLM
comparison.

- Upstream repository: `Qwen/Qwen3-1.7B`
- Frozen revision: `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- Training stage: pretraining and post-training
- Official snapshot: `upstream/`
- Local runtime conversion: `mlx-bf16/`
- Integrity record: `manifest.json`
- Status: downloaded, converted, and verified on 2026-07-31

The `upstream/` and `mlx-bf16/` binary directories are gitignored. The MLX copy
is converted locally from the frozen official snapshot with the same environment
used for the paired Base model. It is not quantized.
