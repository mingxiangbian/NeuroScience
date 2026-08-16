# EXP-051 Seed 42 MPS Attempt Incident

- Status: Failed and retained; not a performance result.
- Failure point: epoch 1 after the step-100 progress log and before the first
  complete-epoch validation evaluation.
- Failure: MPS unified-memory out-of-memory while AdamW requested another
  147.26 MiB. PyTorch reported 8.02 GiB allocated by MPS and 11.98 GiB in other
  allocations.
- Data access: train and validation files were integrity-checked and tokenized;
  no validation performance metric was computed; test was not accessed.
- Unsafe workaround rejected: `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` will not
  be used because it removes the allocator safety limit and may destabilize the
  machine.
- Recovery: use the already registered PyTorch CPU backend with every
  scientific condition unchanged, after a train-only 10-step throughput and
  optimizer-state preflight. The recovery run uses a new append-only directory.

Evidence hashes before this note was added:

- `run.json`: `7733d28711e06ff1db2cd90934711e3c23fe6955fa35f2cf6b62626052e50964`
- `stdout.log`: `c0d4940ee00b29f479b8287d443d453495f57d6b7c82e5789887cb5c34272b93`
