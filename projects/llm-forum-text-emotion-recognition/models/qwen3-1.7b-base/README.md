# Qwen3-1.7B Base Model

This directory records the official pretraining-only model used by the paired
post-training control.

- Upstream repository: `Qwen/Qwen3-1.7B-Base`
- Frozen revision: `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`
- Training stage: pretraining only
- Official snapshot: `upstream/`
- Local runtime conversion: `mlx-bf16/`
- Integrity record: `manifest.json`
- Status: downloaded, converted, and verified on 2026-07-31

The `upstream/` and `mlx-bf16/` binary directories are gitignored. The MLX copy
is converted locally from the frozen official snapshot with the same environment
used for the paired post-trained model. It is not quantized.
