# Stage 5 Generative LoRA

`EXP-047` is the verified Major experiment for the Weibo EClass target-only
generative LoRA comparison.

- Protocol: [`../protocols/exp-047-stage-5-generative-lora.md`](../protocols/exp-047-stage-5-generative-lora.md)
- Frozen config: [`config.json`](config.json)
- Frozen registration config: `Registered`; execution authorization was issued separately
- Current experiment status: `Verified through matched validation`
- No-model dry-run: `Passed`
- Independent verification: `11/11 Passed`, zero mismatches
- Train-only gates: seeds 42/43/44 training, load-forward and replay `Passed`
- Matched validation: `Verified`; 5,088 generations; zero verification mismatches
- Test access: sealed and unaccessed

The dry-run rendered and tokenized all 5,995 frozen train rows without truncation;
the maximum sequence length was 289 tokens. It reproduced a private, gitignored
training JSONL with SHA-256
`b3f25d0bb76d0a2678a83501f0a4a4e363d84be0cea82827852da96c7475abcb`
and three train-only runtime configs for seeds 42/43/44. It loaded only the local
tokenizer: no model weights, forward/backward pass, MLX subprocess, validation or
test data were used.

- Dry-run report: [`preflight/exp-047-runner-dry-run.json`](preflight/exp-047-runner-dry-run.json)
- Verification: [`preflight/exp-047-runner-dry-run-verification.json`](preflight/exp-047-runner-dry-run-verification.json)

The dry-run remains a pre-execution artifact and does not itself support performance
claims. Formal execution used separate, hash-bound authorization and contracts.

## Matched Validation Result

| Condition | Macro-F1 | Accuracy | Weighted-F1 | Parser valid |
| --- | ---: | ---: | ---: | ---: |
| no-adapter reference | 0.333598 | 0.222484 | 0.207222 | 0.908805 |
| LoRA seed 42 | 0.552028 | 0.768082 | 0.773339 | 1.000000 |
| LoRA seed 43 | 0.548289 | 0.786164 | 0.770574 | 1.000000 |
| LoRA seed 44 | 0.587096 | 0.783805 | 0.779033 | 1.000000 |

- LoRA Macro-F1: `0.562471 +/- 0.021408`
- Mean delta versus matched reference: `+0.228873` (`material_improvement`)
- Descriptive delta versus EXP-042 M2 target-only: `-0.032454`
- API cost: USD `0`; maximum peak memory: `8.498 GB`
- Result: [`runs/exp-047-stage-5-generative-lora/matched-validation-v1/REPORT.md`](runs/exp-047-stage-5-generative-lora/matched-validation-v1/REPORT.md)
- Verification: [`runs/exp-047-stage-5-generative-lora/matched-validation-v1/verification.json`](runs/exp-047-stage-5-generative-lora/matched-validation-v1/verification.json)

The primary matched contrast establishes a large and stable behavioral gain from
supervised LoRA over the same frozen Qwen runtime. It does not establish that the
LLM exceeds the Chinese encoder, nor that generated reasoning is a faithful internal
mechanism. Frozen dev error analysis is required before the sealed test gate.
