# GoEmotions Test Gate

`EXP-038` performs the one authorized, frozen evaluation on the official GoEmotions test split.
The scientific matrix is registered in
[`protocols/exp-038-frozen-test-gate.md`](protocols/exp-038-frozen-test-gate.md).

Execution order:

1. Run classical/BERT and Qwen preflights against saved dev outputs while `test.tsv` is absent.
2. Acquire and structurally bind the fixed-revision official test file.
3. Create the final transport-bound config without changing scientific fields.
4. Evaluate all 9 units once: EXP-018, three EXP-020 seeds, EXP-025, three historical EXP-029
   seeds, and target-aligned EXP-033 seed 42.
5. Aggregate without selection and independently verify every saved prediction.

The raw test split, models and adapters remain gitignored. Public outputs use anonymous row numbers
and never store source comment text or upstream comment IDs.

## Result

EXP-038 is complete and independently verified. The primary result is BERT-base-cased test
Macro-F1 `0.488328 +/- 0.008771` across three seeds. Target-aligned Qwen3-1.7B LoRA seed 42
reaches `0.444675`; the historical three-seed LoRA family reaches
`0.450652 +/- 0.032175` but remains ontology-misaligned and is not the primary aligned result.

See [`REPORT.md`](REPORT.md) for the complete metric table, paper comparison, resource data,
interpretation boundaries and the transparent verifier-only V2 amendment.
