# Hypotheses: LLM Forum Text Emotion Recognition

---
date: 2026-07-23
status: draft
tags: [emotion-recognition, hypotheses, llm, forum-text]
sources:
  - ../../sources/llm-forum-text-emotion-recognition-sources.md
---

以下均为待验证假设，不是项目结论。

## H1. Zero-shot 或 few-shot LLM 不一定优于领域微调编码器

- Status: draft
- Confidence: low
- Claim type: assistant synthesis

### Hypothesis

在标签明确且训练数据足够的论坛情绪分类任务中，微调后的 BERT/RoBERTa 可能在 Macro-F1、稳定性、成本和延迟上优于 zero-shot 或 few-shot LLM；LLM 的主要优势可能出现在低资源、开放标签或解释生成场景。

### Supporting Evidence

- TweetEval 已验证传统分类器与 RoBERTa 的实验流程；GoEmotions 将提供
  LLM 对照所需的同数据集简单基线与编码器基线。
- LLM 输出还会引入格式解析、版本漂移、成本和延迟问题。

TweetEval 与 GoEmotions 的任务定义不同，前者的分数不是后者 LLM 实验的比较
证据。当前证据只支持在 GoEmotions 内建立比较，不支持预判最终胜者。

### What Would Change the Conclusion

如果固定数据与评估条件下，LLM 在多随机种子或重复调用中稳定提高 Macro-F1，并在成本和延迟约束内保持优势，应提高该路线优先级。

### Test

- GoEmotions 简单多标签基线。
- 在相同 GoEmotions split 上冻结的 BERT/RoBERTa fine-tuning。
- 本地 post-trained LLM 的 zero-shot 与 few-shot。
- 同一本地 post-trained LLM 的 LoRA。
- 编码器冻结后，在同一 GoEmotions 评估协议上比较指标、成本、延迟和格式
  有效率。

## H2. 回复上下文的收益集中在上下文依赖样本，而非所有样本

- Status: draft
- Confidence: low
- Claim type: literature-informed assistant synthesis

### Hypothesis

父回复或完整线程上下文可能主要改善反讽、指代、否定和情绪转移样本，对语义明确的独立文本帮助有限，甚至可能引入噪声。

### Supporting Evidence

- ERC 综述和 DialogueGCN 强调说话者依赖、情绪转移与会话关系。
- 论坛是异步、多分支结构，不能直接等同于线性对话。

### What Would Change the Conclusion

如果上下文在大多数类别和样本类型上稳定提升，并且增益不依赖长度或特定类别，则假设需要改为更一般的上下文收益。

### Test

- 无上下文。
- 仅父回复。
- 回复路径或完整线程。
- 总体指标与上下文依赖子集指标分别报告。

## H3. 细粒度多标签任务的上限首先受标注一致性限制

- Status: draft
- Confidence: low
- Claim type: assistant synthesis

### Hypothesis

当情绪标签从粗粒度单标签扩展到细粒度多标签时，性能下降可能主要来自标签边界含混和标注者分歧，而不只是模型能力不足。

### Supporting Evidence

- GoEmotions 展示了细粒度、多标签论坛评论数据的可行性。
- 论坛文本常包含混合情绪、隐含情绪和语境依赖。

### What Would Change the Conclusion

如果标注一致性较高，但多个合理模型仍在相同类别上失败，则模型表示或训练目标可能是主要瓶颈。

### Test

- 小规模双人标注试验。
- 报告一致性、争议标签和 `unclear/other` 比例。
- 比较粗粒度映射与细粒度标签下的模型结果。

## H4. 检索示例、标签定义与 LoRA 的增益需要分别验证

- Status: draft
- Confidence: low
- Claim type: assistant synthesis

### Hypothesis

检索增强提示或 LoRA 的表面增益可能来自更好的标签说明、示例选择或额外领域数据，而非某个复杂模块本身。

### Supporting Evidence

- InstructERC 同时使用示例检索、辅助任务和参数高效微调。
- 多个组件同时变化时，单次总分无法说明各组件贡献。

### What Would Change the Conclusion

如果严格消融后某个组件在多次运行和多个数据切分上仍有稳定增益，可以把该组件写成项目贡献。

### Test

- 无标签定义 vs. 固定标签定义。
- 随机示例 vs. 语义检索示例。
- 不微调 vs. LoRA。
- 单独与组合报告增益、成本和失败案例。

## H5. 预训练可能已形成可解码的情绪信息，后训练主要改变其可用方式

- Status: draft
- Confidence: low
- Claim type: user-motivated assistant synthesis

### Hypothesis

Qwen3-1.7B-Base 的冻结隐藏表征中可能已经存在可由简单监督 probe 解码的
GoEmotions 标签信息；post-training 可能进一步改变这些信息的线性可解码性，
同时显著增强任务指令、标签映射和输出格式遵循。生成式分类改善不应自动归因于
出现了新的情绪识别机制。

### What Would Change the Conclusion

如果 Base 与 Instruct 在相同 frozen representation、相同 readout 和相同阈值
协议下没有稳定差异，而 Instruct 只在生成式输出有效率上占优，则后训练收益更可能
主要来自任务接口。反之，如果配对 probe 在多个控制下仍出现稳定差异，则支持
后训练改变了相关表征的可解码性，但仍不构成因果机制证据。

### Test

- 固定 revision 的 Qwen3-1.7B-Base 与 Qwen3-1.7B。
- BF16、相同输入、tokenizer 检查、层、pooling 和 train-only threshold protocol。
- 相同的多标签线性 probe 和 label-shuffle negative control。
- 后续可选的层级分析、ablation 或 activation intervention。
