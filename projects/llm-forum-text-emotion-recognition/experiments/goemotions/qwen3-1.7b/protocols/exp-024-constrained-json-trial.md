# EXP-024: Constrained Label-JSON Repair Trial

Registration date: 2026-07-31 (Asia/Shanghai)

## Registration

- Experiment ID: `EXP-024`
- Tier: `Minor`
- RQ: `RQ-G2 implementation gate`
- Parent: `EXP-022`
- Stage: finite-state constrained-decoding repair
- Status: completed, independently verified and passed
- Config: [`../configs/exp-024-constrained-json-trial.json`](../configs/exp-024-constrained-json-trial.json)
- Config SHA-256: `b16d3cda88d06e4bc89f8201471118be797f1ef668ad0df06f322a6c49e64494`
- Prompt: frozen EXP-022 [`../prompts/exp-022-resource-v1.json`](../prompts/exp-022-resource-v1.json)
- Prompt SHA-256: `2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c`
- Constraint SHA-256: `6e4d1d21d79d2fed3c8a5d118748591db6e72cfcfefb74386f913fb5fd164efa`
- Runner SHA-256: `f004b584a528bb969042f4689a8528c6751c2d53ebd9d2650267e8f8eede7b02`
- Verifier SHA-256: `e8ca2127b436ff7bc398402cae0269beeba2ac3618c9fd7cd9d500f8238fe66a`

## Question and Controlled Change

EXP-022 showed that an unconstrained label-name prompt met all resource checks but failed the
few-shot parser gate. EXP-023 showed that replacing names with numeric IDs made validity worse.
EXP-024 returns to the exact EXP-022 prompt and label-name JSON. Its only change from EXP-022 is a
finite-state token mask passed through MLX-LM `logits_processors`.

The experiment asks whether the constrained decoder can guarantee usable structured outputs
without exceeding the frozen runtime, memory or truncation budgets. It does not assess emotion
classification quality, inspect gold labels, access dev/test, or establish that the unconstrained
model follows the schema.

## Frozen Inputs and Conditions

- Dataset: `DATA-GOE-V1` official agreement-filtered train split.
- Train rows: 43,410; SHA-256
  `1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5`.
- Labels: 28 ordered names; SHA-256
  `45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89`.
- Same 32 anonymous EXP-022 rows, strata and order; selection digest
  `7dcdbe002627948d6e1c5ed4eceb950085585ad0c726333ba3012515dbd8c525`.
- Model: fixed post-trained Qwen3-1.7B MLX BF16 revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
- Same `zero-shot` and `few-shot-synthetic-3` conditions and synthetic examples.
- Same alternating condition order by sample index.
- Greedy decoding, thinking disabled, batch size 1, maximum 64 generated tokens.
- Prompt cache and KV-cache quantization disabled; network/API disabled.
- Dev is prohibited. Test remains absent and prohibited.

The runner parses only text and comment ID to reconstruct the frozen sample. Gold label strings
are discarded immediately and never retained, evaluated or written.

## Frozen Constraint and Parser

The allowed language is exact canonical JSON:

```json
{"labels":["joy","excitement"]}
```

At each generation step, the decoder masks every token that cannot extend the current output to a
complete object satisfying all of these rules:

- exactly one key named `labels`;
- a non-empty list of frozen ontology names;
- no duplicate label;
- `neutral` may appear only by itself;
- no whitespace, prefix, suffix, Markdown, explanation or extra key;
- EOS is permitted only after the complete closing `]}`.

All non-neutral label combinations and orders remain available; the constraint does not force a
single-label task or cap the label count below the 27 non-neutral labels. There is no synonym
mapping, post-hoc repair, retry, fallback to unrestricted generation or deletion of a model choice.

The model still chooses among valid next tokens by its frozen logits. However, 100% format validity
under this decoder would be an engineering property, not evidence of instruction following or
classification accuracy. Any formal Major must report the constraint explicitly.

## Frozen Gate

- 32 fixed train rows and 64 measured generations.
- One synthetic warm-up per condition, excluded from measured summaries.
- Maximum wall time: 30 minutes.
- Peak MLX memory: at most 14.0 GB.
- Linear 5,426-row dev estimate: at most 8 hours per condition.
- Strict parser validity: at least 95% in each condition.
- Generation failures and length-terminated outputs: zero.
- API cost: USD 0.

The runtime estimate includes constrained generation but excludes the one-time model and grammar
initialization from its per-row linear projection. Those initialization times are recorded
separately and included in total wall time.

## Preflight Before Train Access

- Pure grammar checks: 10 valid prefixes, 3 complete outputs and 8 invalid outputs passed.
- Frozen tokenizer coverage: all 28 single labels and representative multi-label outputs passed.
- Candidate token inventory: 14,215 frozen-vocabulary tokens.
- Three synthetic generations passed strict parsing and EOS checks in zero/few-shot conditions.
- The MLX-LM EOS look-ahead path was explicitly tested.

These checks used the public ontology and synthetic text only; they did not read train, dev or test.

## Required Artifacts and Verification

```text
runs/exp-024-constrained-json-trial/
├── run.json
├── summary.json
├── selected-samples.json
├── sample-results.jsonl
├── stdout.log
└── verification.json
```

Public artifacts must not contain raw input text, comment IDs, gold labels or unrestricted raw
generations. Valid outputs may retain canonical label JSON; any invalid output retains only its
hash, size and error category.

The independent verifier must reconstruct and match the EXP-022 sample, verify frozen source and
input hashes, confirm the alternating condition order, validate every retained canonical output,
recompute all aggregates and gates, confirm test is absent and enforce the privacy boundary.

## Decision Rule

A verified pass on every gate permits registration, but not execution, of a formal full-dev
zero/few-shot Major using this disclosed constrained decoder. Failure preserves the run and leaves
full-dev unauthorized.

## Execution Result

EXP-024 completed on 2026-07-31 and passed independent verification of source/input hashes,
sample identity and order, all saved aggregates, the gate calculation and the privacy boundary.

- The same 32 anonymous EXP-022 train rows produced 64 measured generations; gold labels, dev and
  test were not accessed.
- Zero-shot strict validity was `32/32 = 100%`; few-shot strict validity was `32/32 = 100%`.
- All 64 generations ended with `stop`; parser errors, generation failures and length terminations
  were zero.
- Total runtime was `57.8133` seconds. The one-time finite-state constraint initialization took
  `0.2987` seconds for 14,215 candidate vocabulary tokens.
- Peak MLX memory was `3.6541` GB.
- Linear full-dev estimates were `1.0840` hours for zero-shot and `1.4563` hours for few-shot.

Every frozen gate passed. EXP-024 therefore permits registration of a formal full-dev
zero/few-shot Major using the exact disclosed constraint. It does not itself authorize that run or
provide any classification-performance result. The 100% format rate is a decoder guarantee, not a
claim that unconstrained Qwen follows the schema.

Artifacts:

- [`../runs/exp-024-constrained-json-trial/summary.json`](../runs/exp-024-constrained-json-trial/summary.json)
- [`../runs/exp-024-constrained-json-trial/verification.json`](../runs/exp-024-constrained-json-trial/verification.json)
