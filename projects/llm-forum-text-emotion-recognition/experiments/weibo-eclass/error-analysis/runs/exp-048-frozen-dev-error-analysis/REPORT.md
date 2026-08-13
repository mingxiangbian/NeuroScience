# EXP-048 Frozen Weibo EClass Dev Error Analysis

Status: `Verified`

## 范围

本报告只分析 EXP-042 与 EXP-047 已冻结的 1,272 条 validation 预测。没有重新训练、
推理、改 prompt、选 checkpoint 或读取 sealed test。定性部分使用在读原文前冻结的
48 条匿名案例；其计数不能外推为 validation 总体发生率。

## 整体结果

| Condition | Accuracy | Macro-P | Macro-R | Macro-F1 | Weighted-F1 | Failed output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Matched no-adapter reference | 0.222 | 0.370 | 0.486 | 0.334 | 0.207 | 0.091 |
| Qwen3-4B LoRA, 3-seed mean | 0.779 | 0.601 | 0.556 | 0.562 | 0.774 | 0.000 |
| Chinese encoder, 3-seed mean | 0.792 | 0.616 | 0.584 | 0.595 | 0.785 | 0.000 |

LoRA 相对 matched reference 的 Macro-F1 提高 `+0.229`，
但仍比 encoder 低 `-0.032`。Accuracy 上 LoRA
与 encoder 的差为 `-0.013`，说明两者总体
命中率接近，但少数类表现和跨 seed 稳定性不同。

## 格式恢复与分类收益

Reference 有 `116` 条输出失败，其中包括无效 parse 或 likely-truncated；
该 slice 的 reference Accuracy 为 `0.000`，LoRA 三 seed 均值为
`0.776`。其中 `85` 条
被 3/3 LoRA seed 稳定恢复。

在剩余 `1156` 条 reference 输出有效的样本上，LoRA Accuracy 仍从
`0.245` 提高到 `0.780`，Macro-F1 从
`0.342` 提高到 `0.578`；并有
`640` 条有效但错误的 reference 结果被
3/3 LoRA seed 稳定恢复。因此，EXP-047 的提升不只是消除 116 条格式失败。

从 Accuracy 的加性分解看，failed-output slice 贡献 `+0.071`，
valid-output slice 贡献 `+0.486`，合计
`+0.557`。Macro-F1 不可这样相加，本报告不作
伪分解。failed-output 行上的恢复也同时可能包含标签变化，不能被写成纯格式因果效应。

## LoRA 与 encoder 的剩余差距

LoRA 相对 encoder 的最大逐类 F1 劣势：

| Label | Support | LoRA F1 | Encoder F1 | LoRA - Encoder |
| --- | ---: | ---: | ---: | ---: |
| sadness | 20 | 0.442 | 0.526 | -0.085 |
| neutral | 60 | 0.293 | 0.359 | -0.066 |
| anger | 43 | 0.499 | 0.539 | -0.040 |
| positive | 97 | 0.549 | 0.579 | -0.029 |

LoRA 相对 encoder 的优势或最小劣势：

| Label | Support | LoRA F1 | Encoder F1 | LoRA - Encoder |
| --- | ---: | ---: | ---: | ---: |
| joy | 61 | 0.729 | 0.728 | +0.000 |
| no_emotion | 881 | 0.885 | 0.889 | -0.004 |
| negative | 110 | 0.541 | 0.545 | -0.004 |

最常见的 LoRA 错误对：

| Gold -> prediction | Mean count across seeds |
| --- | ---: |
| positive -> no_emotion | 33.3 |
| neutral -> no_emotion | 31.7 |
| no_emotion -> neutral | 29.0 |
| negative -> no_emotion | 27.0 |
| no_emotion -> positive | 23.0 |

`no_emotion` 是 881/1,272 的多数类，因此大量 minority -> no_emotion 混淆会让
Accuracy 看起来仍高，却显著压低 Macro-F1。是否属于 `no_emotion`、`neutral`、
`positive/negative` 或具体情绪的边界也不是纯粹的情绪极性判断。

关键切片的三 seed Macro-F1 均值：

| Slice | LoRA | Encoder | LoRA - Encoder |
| --- | ---: | ---: | ---: |
| `no_emotion` | 0.135 | 0.136 | -0.001 |
| `emotion_label` | 0.485 | 0.519 | -0.034 |
| `long_tail_label` | 0.430 | 0.459 | -0.029 |
| `ambiguous_target` | 0.191 | 0.208 | -0.017 |
| `unambiguous_target` | 0.589 | 0.626 | -0.037 |

单类或小切片上的 Macro-F1 会包含许多零 support 类，主要用于相同 slice 上的配对
描述，不应当作独立 benchmark。

## 跨 seed 与跨模型转移

相对 encoder，LoRA 有 `10` 条 0/3 -> 3/3 稳定恢复，
也有 `17` 条 3/3 -> 0/3 稳定回退。相对 reference，
对应数字为 `725` 与 `44`。
这说明 LoRA 不是把 encoder 的决策整体复制过来，而是形成了不同的错误结构。

LoRA seed 两两最终标签一致率均值为 `0.884`，
encoder 为 `0.943`。
少数类 support 小，三组 LoRA seed 的逐类波动不能忽略；论文应继续报告 mean +/- SD，
不能只展示 seed 44。

## 定性编码

共审阅 `48` 条预先抽取案例。Evidence flags 可以重叠：

| Possible factor | Cases |
| --- | ---: |
| `sentiment_emotion_overlap` | 24 |
| `long_tail_class` | 23 |
| `weak_emotion_no_emotion_boundary` | 21 |
| `annotation_ambiguity` | 20 |
| `implicit_emotion` | 20 |
| `possible_context_dependency` | 11 |
| `slang_noise` | 11 |
| `lexical_cue_conflict` | 4 |
| `mixed_emotion` | 3 |
| `negation` | 3 |
| `none_observed` | 1 |
| `sarcasm_irony` | 1 |

| Primary possible source | Cases |
| --- | ---: |
| `annotation_data_uncertainty` | 21 |
| `overlapping_label_ontology` | 13 |
| `model_representation_limitation` | 9 |
| `missing_local_context` | 2 |
| `surface_form_noise` | 2 |
| `output_parser_or_policy` | 1 |

定性代码只表达一位审阅者对所选案例的可能解释。它不能更改数据集标签，也不能证明
模型内部采用了某种情绪机制。尤其 `ambiguous_target` 是上游结构化标志，而
`annotation_ambiguity` 是本次人工判断，两者不可互换。

## 结论与边界

1. LoRA 的提升同时包含格式/可用输出恢复和有效 reference 行上的真实标签行为改善。
2. LoRA 与 encoder 的 Accuracy 接近，但 Macro-F1 仍低，差距集中在少数类和类别边界。
3. 三 seed 的错误并不完全稳定，最终论文必须保留波动与逐类指标。
4. 本次结果只支持行为层错误解释，不支持 hidden-state 或人类情绪机制结论。

EXP-048 不授权据此修改模型或访问 test。下一步应基于已冻结 validation 证据形成
TEST-READY 候选清单；若要新增消融或迁移，必须先登记新的实验。
