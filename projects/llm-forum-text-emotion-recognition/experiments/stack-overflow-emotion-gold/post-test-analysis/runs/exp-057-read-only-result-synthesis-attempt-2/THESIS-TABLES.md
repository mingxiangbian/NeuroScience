# EXP-057 Thesis Tables

> Read-only synthesis of verified public aggregates. No training, inference,
> threshold selection, private prediction access, or test-label access occurred.

## Validation

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Subset accuracy |
| --- | ---: | ---: | ---: | ---: |
| M1 RoBERTa encoder | 0.617254 +/- 0.011084 | 0.740705 +/- 0.013301 | 0.771139 +/- 0.005645 | 0.760648 +/- 0.021621 |
| M2 Frozen Qwen + linear head | 0.318889 +/- 0.038085 | 0.382667 +/- 0.045702 | 0.514069 +/- 0.022042 | 0.490741 +/- 0.028678 |
| M3 Qwen Classification LoRA | 0.654032 +/- 0.014135 | 0.706724 +/- 0.013816 | 0.759575 +/- 0.003674 | 0.750463 +/- 0.007649 |
| M4 Qwen Generative LoRA | 0.615182 +/- 0.037632 | 0.701182 +/- 0.026073 | 0.755144 +/- 0.009373 | 0.776389 +/- 0.013679 |

## Held-Out Test

| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Weighted-F1 | Subset accuracy | Hamming loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M1 RoBERTa encoder | 0.567459 +/- 0.007814 | 0.680951 +/- 0.009377 | 0.748947 +/- 0.001954 | 0.743941 +/- 0.006278 | 0.750000 +/- 0.017067 | 0.054244 +/- 0.002550 |
| M2 Frozen Qwen + linear head | 0.295226 +/- 0.020587 | 0.354271 +/- 0.024704 | 0.508591 +/- 0.015366 | 0.474565 +/- 0.045017 | 0.502778 +/- 0.046915 | 0.126080 +/- 0.009260 |
| M3 Qwen Classification LoRA | 0.613804 +/- 0.025733 | 0.670216 +/- 0.012032 | 0.753741 +/- 0.003607 | 0.750265 +/- 0.003552 | 0.757407 +/- 0.007127 | 0.051620 +/- 0.001225 |
| M4 Qwen Generative LoRA | 0.547823 +/- 0.015312 | 0.657388 +/- 0.018374 | 0.746167 +/- 0.005484 | 0.734989 +/- 0.009252 | 0.771296 +/- 0.006415 | 0.052778 +/- 0.000835 |

## Frozen Test Contrasts

| Contrast | Macro-F1 delta | 95% CI | Five-label delta | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| M2-M1 | -0.272233 | [-0.310672, -0.227897] | -0.326680 | [-0.372806, -0.273476] |
| M3-M1 | 0.046345 | [-0.008674, 0.089730] | -0.010735 | [-0.046061, 0.024305] |
| M3-M2 | 0.318578 | [0.254425, 0.369327] | 0.315945 | [0.265264, 0.360323] |
| M4-M1 | -0.019636 | [-0.058325, 0.017981] | -0.023563 | [-0.069990, 0.021578] |
| M4-M3 | -0.065981 | [-0.107869, -0.011312] | -0.012828 | [-0.045475, 0.018074] |

## Test Per-Label F1

| Label (support) | M1 | M2 | M3 | M4 |
| --- | ---: | ---: | ---: | ---: |
| love (183) | 0.833069 +/- 0.006778 | 0.623725 +/- 0.059913 | 0.841502 +/- 0.006842 | 0.848050 +/- 0.007714 |
| joy (74) | 0.602446 +/- 0.036392 | 0.193660 +/- 0.170914 | 0.622421 +/- 0.023874 | 0.542468 +/- 0.065150 |
| surprise (7) | 0.000000 +/- 0.000000 | 0.000000 +/- 0.000000 | 0.331746 +/- 0.143675 | 0.000000 +/- 0.000000 |
| anger (132) | 0.789238 +/- 0.012357 | 0.530876 +/- 0.013898 | 0.783076 +/- 0.003858 | 0.781405 +/- 0.005130 |
| sadness (35) | 0.655246 +/- 0.037096 | 0.358578 +/- 0.004383 | 0.629518 +/- 0.030685 | 0.643076 +/- 0.034937 |
| fear (16) | 0.524756 +/- 0.030015 | 0.064516 +/- 0.111745 | 0.474561 +/- 0.075004 | 0.471942 +/- 0.090852 |

## Resource Paths

| Family | Backend | Mean wall/seed (s) | Shared feature (s) | Peak memory (GB) | Parser-valid |
| --- | --- | ---: | ---: | ---: | ---: |
| M1 | PyTorch_CPU | 23.432471 |  |  |  |
| M2 | MLX_Apple_Metal |  | 467.440099 | 8.224866 |  |
| M3 | MLX_Apple_Metal | 610.663857 |  | 8.592561 |  |
| M4 | MLX_Apple_Metal | 1188.416818 |  | 8.594649 | 1.000000 |

## Claim Boundary

- **supported**: M3 outperforms M2 on six-label and five-label test Macro-F1. Both frozen component-bootstrap intervals are above zero.
- **not-established**: M3 robustly outperforms M1. The six-label and five-label M3-M1 intervals both cross zero.
- **supported-with-boundary**: M4 is lower than M3 on the registered six-label primary metric. The six-label M4-M3 interval is below zero; the five-label interval crosses zero.
- **not-supported**: Generation itself caused the M3-M4 difference. M3 and M4 differ in objective, output path, parser, and head, so formulation is bundled.
- **not-supported**: The results reveal an internal or human emotion mechanism. The evidence is held-out behavioral performance only.

`surprise` has only seven held-out positives. Six-label claims must therefore be
reported together with the five-label sensitivity result.
