# EXP-038 Verifier Amendment

## EXP-038-VERIFY-V2

The registered verifier stopped at EXP-025 row 9 because it compared the ordered
`predicted_label_ids` from generated JSON with IDs reconstructed from a multi-hot
matrix. The two representations contained the same unique labels, but the latter is
always sorted by label ID.

V2 validates that generated IDs are integers, in range and unique, then compares the
sorted ID sets. This is a verification-only correction: no model, prompt, decoder,
checkpoint, prediction, metric, aggregate, frozen config or test data was changed or
rerun. `verification.json` records both the registered verifier hash and the executing
V2 verifier hash.
