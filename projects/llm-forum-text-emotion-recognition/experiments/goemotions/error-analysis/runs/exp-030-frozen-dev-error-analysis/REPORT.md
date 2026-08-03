# EXP-030 Frozen GoEmotions Dev Error Analysis

Status: `Completed; verification pending`

## 范围

本报告只分析 EXP-020、EXP-025 和 EXP-029 已冻结的 GoEmotions dev 预测。
没有重新训练、推理、选 seed、调阈值或读取 test。全部 5,426 条 dev 样本进入
定量分析；定性部分使用在读原文前冻结的 48 条匿名样本。

多 seed 条件中的 `stable correct` 指 3/3 seed 都精确匹配完整标签集合；
`stable wrong` 指 0/3 精确匹配。它们不是 ensemble 指标。

## 整体行为

| Condition | Macro-P | Macro-R | Macro-F1 | Exact-match | Samples-F1 | Predicted labels/row |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EXP-020 BERT | 0.508 | 0.504 | 0.489 | 0.441 | 0.596 | 1.276 |
| EXP-025 frozen Qwen | 0.231 | 0.408 | 0.241 | 0.105 | 0.264 | 1.911 |
| EXP-029 LoRA Qwen | 0.608 | 0.407 | 0.451 | 0.508 | 0.586 | 1.034 |

Gold 平均每行有 `1.176` 个标签。LoRA 的严格 exact-match (`0.508`) 高于 BERT (`0.441`)，但 Macro-F1 低 `0.038`。
这不是矛盾：LoRA 更保守，平均只输出约一个标签，因而在占多数的单标签样本上
更容易得到完整集合正确；Macro-F1 则揭示它对各类别、尤其第二个标签的召回不足。

## 多标签与输出策略

| Slice | Rows | BERT exact | Frozen Qwen exact | LoRA exact | BERT samples-F1 | LoRA samples-F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `single_label` | 4548 | 0.491 | 0.118 | 0.598 | 0.604 | 0.607 |
| `any_multilabel` | 878 | 0.179 | 0.040 | 0.043 | 0.556 | 0.475 |
| `neutral_cooccurrence` | 174 | 0.090 | 0.000 | 0.000 | 0.558 | 0.562 |
| `emotion_only_multilabel` | 704 | 0.201 | 0.050 | 0.054 | 0.555 | 0.453 |
| `long_tail_label` | 512 | 0.285 | 0.102 | 0.281 | 0.507 | 0.438 |

冻结的 Qwen decoder 禁止 `neutral` 与情绪标签共现，因此 `174` 条
gold 共现样本对 EXP-025/029 的 exact-match 在结构上不可达；两者在该 slice 上均为 0。
这些样本没有被删除。该限制最多直接压低约 `0.032` 的总体 exact-match，但不能单独解释
LoRA 的 Macro-F1 差距，因为 Macro-F1 还取决于全部标签的 TP/FP/FN。

LoRA 每 seed 平均约有 `553.3` 条
纯漏标错误，却只有 `65.7` 条
纯多报错误；其主要剩余错误是漏掉第二个标签或用另一个相邻标签替换 gold。

## 类别差异

BERT 相对 LoRA 的最大逐类 F1 优势如下：

| Label | Support | BERT F1 | LoRA F1 | BERT - LoRA |
| --- | ---: | ---: | ---: | ---: |
| annoyance | 303 | 0.380 | 0.179 | +0.202 |
| remorse | 68 | 0.728 | 0.560 | +0.168 |
| nervousness | 21 | 0.377 | 0.249 | +0.128 |
| fear | 90 | 0.653 | 0.546 | +0.108 |
| optimism | 209 | 0.581 | 0.474 | +0.107 |
| surprise | 129 | 0.540 | 0.440 | +0.100 |
| approval | 397 | 0.376 | 0.292 | +0.084 |
| disapproval | 292 | 0.409 | 0.357 | +0.052 |

LoRA 也并非对所有类别都更差；其最大的相对优势为：

| Label | Support | BERT F1 | LoRA F1 | BERT - LoRA |
| --- | ---: | ---: | ---: | ---: |
| relief | 18 | 0.035 | 0.098 | -0.063 |
| grief | 13 | 0.000 | 0.039 | -0.039 |
| disappointment | 163 | 0.303 | 0.326 | -0.022 |
| excitement | 96 | 0.314 | 0.333 | -0.018 |
| confusion | 152 | 0.436 | 0.451 | -0.015 |

这些是同一 dev 上的描述性差异。少数类 support 很小，单类差值不能当作稳定的
总体优劣证据，也不能据此挑 seed。

最常见的 missed-to-spurious 标签对按 model-run-row 计数如下：

| Condition | Missed -> spurious | Count |
| --- | --- | ---: |
| EXP-020 BERT | approval -> neutral | 283 |
| EXP-020 BERT | neutral -> approval | 277 |
| EXP-020 BERT | disapproval -> neutral | 255 |
| EXP-025 frozen Qwen | neutral -> disapproval | 644 |
| EXP-025 frozen Qwen | admiration -> approval | 230 |
| EXP-025 frozen Qwen | neutral -> confusion | 202 |
| EXP-029 LoRA Qwen | approval -> neutral | 450 |
| EXP-029 LoRA Qwen | disapproval -> neutral | 311 |
| EXP-029 LoRA Qwen | annoyance -> neutral | 285 |

`neutral` 与 approval/annoyance/disapproval/curiosity 等相邻判断频繁互换，说明错误
不仅来自类别频率，也来自表达是否被视为带有情绪，以及细粒度标签边界。

## 跨模型转移与稳定性

相对 BERT，LoRA 有 `1263` 条样本的 exact-correct seed 比例提高，
`695` 条降低；其中完整 0/3 -> 3/3 恢复 `304` 条，
3/3 -> 0/3 回退 `122` 条。
这解释了 LoRA 为何能在总体 exact-match 上领先，但不代表它的类别召回更好。

相对 frozen Qwen，LoRA 有 `2681` 条提高、`145` 条降低；
其中稳定恢复 `1915` 条。LoRA 的收益因此不是只修复 JSON
格式，而是大范围改变了标签行为。

三种条件共同稳定判错 `1771` 条，约占 dev 的 `32.64%`。这是一组任务级难例，
但其中仍混有标签歧义、缺失上下文和相邻类别，不应直接归因于共同的模型机制缺陷。

## 定性编码

48 条样本按六个预注册角色各取 8 条。证据 flags 可重叠：

| Possible factor | Cases |
| --- | ---: |
| `lexical_cue_conflict` | 39 |
| `annotation_ambiguity` | 37 |
| `label_overlap` | 19 |
| `mixed_emotion` | 19 |
| `implicit_emotion` | 18 |
| `possible_context_dependency` | 15 |
| `slang_noise` | 11 |
| `minority_class` | 6 |
| `sarcasm_irony` | 4 |
| `negation` | 3 |

| Primary possible source | Cases |
| --- | ---: |
| `overlapping_label_ontology` | 18 |
| `annotation_data_uncertainty` | 9 |
| `model_representation_limitation` | 9 |
| `missing_context` | 6 |
| `output_policy_or_label_mapping` | 5 |
| `surface_form_noise` | 1 |

高频现象是 lexical cue conflict、annotation ambiguity、mixed emotion 和 label overlap。
例如同一句话可同时支持 caring/optimism、anger/annoyance 或 admiration/approval；另一些
文本依赖被省略的论坛上下文，或包含否定、反讽和网络表达。定性样本被刻意富集为错误
与模型转移案例，因此这些计数不能外推为 5,426 条 dev 的总体发生率。

## 官方结果边界

GoEmotions 论文没有发布可与本地 dev 对齐的 validation accuracy。论文 Table 4 的
完整 28 类 BERT Macro-P/R/F1 为 `0.40`/`0.63`/`0.46`，对应最终 test，
不是 validation。官方仓库的代码可以计算 strict multi-label accuracy，但没有给出一个
固定的官方 dev accuracy 数字。

本地 EXP-020 dev Macro-F1 为 `0.489 +/- 0.011`，比官方 test 表中的 `0.46` 高 `0.029`。由于 split、随机性和
实现并未对齐，这只能说明本地结果处于相近尺度，不能写成超过官方或正式复现差值。

## 结论与下一步边界

1. LoRA 已大幅修复 frozen Qwen，但主要形成高 precision、低 cardinality 的保守分类器。
2. BERT 的优势主要体现在多标签覆盖与类别召回；LoRA 的高 exact-match 受单标签占多数影响。
3. neutral 共现禁令是一个已确认的结构性误差源，值得单独预注册 decoder/target ablation。
4. 标签重叠、标注不确定性和缺失上下文同样重要，不能把所有错误归因于模型容量。

任何新 decoder、阈值、LoRA 配置或上下文实验都必须使用新 EXP 编号和预注册规则。
EXP-030 不打开 test gate，也不把定性判断写成机制解释。
