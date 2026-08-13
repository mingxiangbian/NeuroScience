# EXP-041 Independent Verification Amendment

---
date: 2026-08-08
audit_id: AUDIT-EXP-041-V1
experiment_id: EXP-041
tier: Minor
status: Passed
parent_protocol: EXP-041
---

## Observed Outcome

The amended verifier passed all 16 registered checks with zero mismatch. It
reparsed all 5,995 train rows, reconstructed all 56 private smoke selections,
independently parsed and aggregated 42 Qwen outputs, verified the exact LoRA
adapter tensors, and found no public raw-text or identifier leakage. Validation
and test remained unaccessed.

## Trigger

The frozen EXP-041 verifier stopped before reading any experiment result because
its source-isolation guard searched its own source text for the literal strings
used inside that same guard. The check was therefore self-matching and could
never pass. No `verification.json` was written, and EXP-041 remained at
`Awaiting Independent Verification`.

## Scope

This amendment does not alter or rerun the dataset selection, prompts, parser,
classical smoke, encoder smoke, Qwen generations, LoRA training, reports or
frozen EXP-041 implementation. It authorizes one new independent audit script
to verify the existing append-only artifacts.

The only logic correction replaces raw source-string matching with Python AST
inspection of actual `import` and `from ... import ...` nodes. Imports from
`run_preflight` and `label_parser` remain forbidden. All existing independent
reconstruction, parser, aggregate, model-inventory, adapter and privacy checks
remain unchanged.

## Frozen Audit

- Script: `experiments/weibo-eclass/stage-2-preflight/verify_preflight_exp041_audit.py`
- SHA-256: `e1fcd95c6801772e4a6905676c1351071cf715938e0e363445af9e75bc6ac4ee`
- Expected experiment: `EXP-041`
- Expected audit ID: `AUDIT-EXP-041-V1`
- Validation access: forbidden.
- Test access: forbidden.
- Output: the existing EXP-041 run directory's append-only `verification.json`.

## Pass Criteria

1. The audit script hash matches this protocol.
2. The original frozen implementation hashes still match EXP-041 config.
3. All 16 independent checks pass with zero mismatch.
4. Only train data is reparsed; validation and test remain untouched.
5. The resulting verification report records this audit ID and the auditing
   script artifact.
