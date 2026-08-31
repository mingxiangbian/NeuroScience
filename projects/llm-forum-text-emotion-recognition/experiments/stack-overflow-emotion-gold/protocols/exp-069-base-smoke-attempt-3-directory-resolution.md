# EXP-069 Base Smoke Attempt 3: Directory Resolution Recovery

- Experiment ID: `EXP-069`
- Attempt ID: `attempt-3-base-smoke`
- Date: `2026-08-26`
- Parent failure: `attempt-2-base-smoke`, `FileNotFoundError`
- Status: `Base smoke recovery authorized; fold and assemble closed`

## 1. Failure and correction

Attempt 2 stopped after claim and before model load. Its consumer passed the registered
`models/qwen3-4b/mlx-bf16` directory to the attempt-1 resolver with `must_exist=true`; that resolver
accepts regular files only and raised `FileNotFoundError`.

Attempt 3 changes one implementation rule:

```text
if relative path == frozen parent_config.model.base_path:
    resolve with must_exist=false
    require a real, non-symlink directory
else:
    use the frozen attempt-1 resolver unchanged
```

The recovery does not modify attempt-1 or attempt-2 files. It binds the attempt-2 config, claim,
failure record, runner and verifier by exact identity.

## 2. Unchanged contract

- Same 32 train ordinals and nine representation points
- Same Qwen revision, prompt, tokenizer and M2 cache
- Same float32 `rtol=0`, `atol=1e-5` gates
- Same 20-minute and 10 GB MLX ceilings
- Same cache and Qwen before/after identity checks
- Base smoke only
- Fold smoke and assemble unauthorized
- Training, metrics, validation and test forbidden

## 3. Recovery adapter

The attempt-3 runner imports the exact attempt-2 consumer source. It patches only
`load_source_runner()` to apply the directory rule above and changes the append-only attempt ID and
output roots. The attempt-2 execution function remains unchanged.

The attempt-3 verifier imports the exact model-free attempt-2 verifier, changes only the attempt ID,
and verifies the new output root under the same numeric, access, mode, resource and claim gates.

## 4. Stop and claim boundary

Any new failure seals attempt 3. The maximum claim remains:

> A verified 32-row Frozen-Qwen base representation-path smoke for the frozen Phase B stack.

This recovery supports no M3 parity, classification result, representation effect, functional
dependency, independent-data, deployment or emotion-mechanism claim.
