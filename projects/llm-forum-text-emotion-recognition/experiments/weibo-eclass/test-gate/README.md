# Weibo EClass Frozen Test Gate

`EXP-049` is the one-time held-out test evaluation for the frozen Weibo EClass
model stack.

- Protocol: [`protocols/exp-049-frozen-test-gate.md`](protocols/exp-049-frozen-test-gate.md)
- Frozen contract: `configs/exp-049-test-ready.json`
- Authorization: `preflight/exp-049-authorization-v1.json`
- TEST-READY verification: `preflight/exp-049-test-ready-verification-v1.json`
- Formal outputs: `runs/exp-049-frozen-test/`
- Private row-level outputs: under the dataset's gitignored `derived-private/`
  tree

The formal sequence is fixed. Nine prediction files are produced without
opening the sealed labels. Only after all nine units complete does the finalizer
open the labels once, compute metrics, and write aggregate public evidence. A
separate verifier then recomputes every reported metric from the saved private
predictions.

No test result may be used to change a prompt, checkpoint, seed, threshold,
model family, or reporting rule.

## Final Status

`EXP-049` is `Frozen / Verified / Consumed`.

- All nine frozen units produced predictions for all 1,273 test rows before
  labels were opened.
- The independent verifier reconstructed 11,457 row-level predictions with
  zero mismatches and confirmed that no model call occurred after label access.
- Encoder Macro-F1 was `0.649621 +/- 0.007365`; Qwen3-4B generative LoRA was
  `0.636612 +/- 0.021429`; the matched no-adapter Qwen reference was `0.316921`.
- LoRA improved over the matched Qwen reference by `+0.319691`, with 95% group
  bootstrap CI `[+0.274779, +0.362068]`.
- LoRA minus encoder was `-0.013009`, with 95% group bootstrap CI
  `[-0.045671, +0.024011]`. The frozen point-estimate rule records degradation,
  but the interval crosses zero, so this does not establish a reliable encoder
  advantage.

Public result: [`runs/exp-049-frozen-test/REPORT.md`](runs/exp-049-frozen-test/REPORT.md)

Independent verification:
[`runs/exp-049-frozen-test/verification.json`](runs/exp-049-frozen-test/verification.json)

## Finalization Incident

The first finalization pass opened the labels once, persisted all scored
predictions and aggregate metrics, then failed while rendering the Markdown
table because non-generative units store `parser` as JSON `null`. The recovery
did not rerun model or metric computation. It read only the persisted aggregate,
fixed the null-safe renderer path, completed the consumed-state transition, and
recorded the repair in
[`finalize-recovery.json`](runs/exp-049-frozen-test/finalize-recovery.json).
The verifier subsequently reproduced all reported values with zero mismatches.
