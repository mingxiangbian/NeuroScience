# EXP-052 Seed 44 Cache-reuse Authorization

- Experiment: `EXP-052` / M2 Frozen Qwen + Linear Head
- Authorized stages: `seed-44 cache-reuse preflight` followed by exactly one
  formal `train + validation` run
- Authorized at: 2026-08-14
- Basis: the user explicitly instructed the project to execute seed 44 after
  EXP-052 seed 43 passed 99/99 independent checks.

## Scope

This authorization permits exactly:

1. one preflight that revalidates the frozen cache gate, the completed seed-43
   run and verification, train/validation data, read-only cache hashes,
   seed-44 head initialization and batch-order digests;
2. after that preflight passes independent verification, one formal `seed=44`
   linear-head run over the frozen train and validation feature caches;
3. new seed-specific batch orders, optimizer state, checkpoints, validation
   probabilities, bootstrap results and public aggregate metrics for seed 44;
4. reuse of only the seed-42 Qwen feature cache frozen by the verified
   `EXP-052 Feature-cache Reuse Gate`.

The Qwen model is not loaded and no Qwen forward pass is executed. The cache is
opened using NumPy read-only mmap and its SHA-256 is checked before and after
consumer use. Only a freshly initialized bias-enabled `Linear(2560, 6)` head
may receive optimizer updates. Training remains two epochs, batch size 1,
AdamW at `1e-4`, weight decay `0.01`, unweighted BCE and no scheduler. Head
initialization and the continuous NumPy PCG64 permutation stream both use seed
44.

## Gates

Formal execution requires all of the following:

- the feature-cache reuse gate remains `Passed` with 74/74 checks;
- the seed-43 formal run remains `Completed`, its verification remains
  `Passed` with 99/99 checks, and both bound hashes remain unchanged;
- the seed-44 preflight completes and passes its independent verifier;
- train and validation cache path, bytes, SHA-256, shape, dtype, sample order
  and token stream remain identical to the frozen gate;
- the runner has no Qwen/model-loading path and opens both caches read-only;
- seed-44 head initialization and batch orders are independently reproduced;
- test remains sealed and no row-level private artifact enters Git.

## Explicit Non-authorization

This amendment does not authorize Stack Overflow test access, TEST-READY
status, the three-seed aggregate, EXP-053/M3, EXP-054/M4, context recovery,
routing or error analysis. It does not permit reuse of any earlier head,
optimizer state, batch order or validation prediction.
