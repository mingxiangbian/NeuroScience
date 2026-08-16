# EXP-056 一次性冻结测试报告

## 状态

- 状态：**已完成并通过独立验证**
- 本地完成日期：2026-08-16
- 测试范围：720 行，分属 702 个 duplicate components
- 正式单元：M1-M4 x seeds 42/43/44，12/12 完成
- 冻结合同 SHA-256：`bf0330aef1a98085674b7f744fa5c30d2e15f5886cd0d4fa24811f48a52e0966`
- 预测封存 SHA-256：`d1c4554e232335cc917c406b94bd743b8150e060a7b7980611e0f401c3e80ad4`
- 结果 SHA-256：`d7b966ead7105b819db946c970e3f90b6b25514eac8e8e0b71c4ab3a69928cdd`
- 12 份预测产物全部完成 hash seal 后才打开 test labels。
- 访问 test 后没有进行 checkpoint、seed、阈值、parser、prompt 或模型选择。
- Stack Overflow test split 现已**消费**，不得再用于调参或模型选择。

## 主要结果

数值为 seeds 42、43、44 的算术平均值与样本标准差。

| Family | Macro-F1 | Macro-F1 without `surprise` | Micro-F1 | Weighted-F1 | Subset accuracy | Hamming loss | `surprise` F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M1 RoBERTa encoder | `0.567459 +/- 0.007814` | `0.680951 +/- 0.009377` | `0.748947 +/- 0.001954` | `0.743941 +/- 0.006278` | `0.750000 +/- 0.017067` | `0.054244 +/- 0.002550` | `0.000000 +/- 0.000000` |
| M2 Frozen Qwen + linear head | `0.295226 +/- 0.020587` | `0.354271 +/- 0.024704` | `0.508591 +/- 0.015366` | `0.474565 +/- 0.045017` | `0.502778 +/- 0.046915` | `0.126080 +/- 0.009260` | `0.000000 +/- 0.000000` |
| M3 Qwen Classification LoRA | `0.613804 +/- 0.025733` | `0.670216 +/- 0.012032` | `0.753741 +/- 0.003607` | `0.750265 +/- 0.003552` | `0.757407 +/- 0.007127` | `0.051620 +/- 0.001225` | `0.331746 +/- 0.143675` |
| M4 Qwen Generative LoRA | `0.547823 +/- 0.015312` | `0.657388 +/- 0.018374` | `0.746167 +/- 0.005484` | `0.734989 +/- 0.009252` | `0.771296 +/- 0.006415` | `0.052778 +/- 0.000835` | `0.000000 +/- 0.000000` |

M4 的三 seed 共 2,160 条预测全部通过 strict parser。其较高的 subset accuracy 是次指标，
不能覆盖预登记的类别均衡主指标。

## 冻结配对比较

每个差值均按 `second family - first family` 计算。置信区间为 2,000 次
duplicate-component bootstrap 得到的 95% 区间。

| Contrast | Macro-F1 delta | 95% CI | Five-label delta | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| M2 - M1 | `-0.272233` | `[-0.310672, -0.227897]` | `-0.326680` | `[-0.372806, -0.273476]` |
| M3 - M1 | `+0.046345` | `[-0.008674, +0.089730]` | `-0.010735` | `[-0.046061, +0.024305]` |
| M3 - M2 | `+0.318578` | `[+0.254425, +0.369327]` | `+0.315945` | `[+0.265264, +0.360323]` |
| M4 - M1 | `-0.019636` | `[-0.058325, +0.017981]` | `-0.023563` | `[-0.069990, +0.021578]` |
| M4 - M3 | `-0.065981` | `[-0.107869, -0.011312]` | `-0.012828` | `[-0.045475, +0.018074]` |

## 结果解释

1. M3 明确优于 M2。任务特定的 LoRA 适配相对 frozen final-layer last-token representation
   加 linear head 带来了显著 test 收益。
2. M3 没有建立相对 M1 的稳健优势。六标签点估计更高，但置信区间跨 0；去除只有 7 个
   test 正例的 `surprise` 后，点估计略为负值，差异仍不确定。
3. M4 没有在主指标上超过 M3。六标签 M4-M3 区间完全低于 0，五标签差异仍不确定。
4. M4 与 M1 的六标签和五标签 Macro-F1 差异也都不确定。M4 更高的 strict subset
   accuracy 与更保守的完整标签向量预测相容，不能证明 generative formulation 普遍更好。
5. 可支持的有限结论是：Classification LoRA 能使本地 Qwen 在该任务上与强 encoder 竞争，
   但不能证明 LLM 普遍超过 RoBERTa，也不能证明 generation 本身改善了情绪识别。

## 资源记录

| Family | Backend | 正式推理记录 | 峰值内存 | 说明 |
| --- | --- | ---: | ---: | --- |
| M1 | PyTorch CPU | 平均 `23.432 s/seed` | 未记录 | CPU 路径，不与 Metal 用时直接比较 |
| M2 | MLX Metal | shared feature extraction `467.440 s`；heads `0.382/0.002/0.002 s` | `8.225 GB` | 三个 head 共享 hidden cache；0 行截断 |
| M3 | MLX Metal | 平均 `610.664 s/seed` | `8.593 GB` | 0 行截断 |
| M4 | MLX Metal | 平均 `1188.417 s/seed` | `8.595 GB` | 平均约 `1.645 s/row`；parser validity 100%；0 行截断 |

API cost 为 USD 0。M1 使用 CPU，M2 使用一次共享特征提取，M3/M4 使用逐 seed Metal
推理，因此只能报告各路径内部的资源情况，不能据此直接进行跨路径速度排名。

## 执行与验证

冻结执行顺序为：

```text
initialize -> predict M1 -> predict M2 -> predict M3 -> predict M4
-> seal all predictions -> open labels once -> score -> verify
```

M2 首次在受限 sandbox 内启动时因无 Metal device 而在推理前停止，没有产生预测产物，也没有
打开标签。随后使用获批的 native Metal runtime 原样重跑冻结命令并完成；这是执行环境恢复，
不是科学配置变更。

验证证据：

- 执行前 TEST-READY verifier：`89/89 Passed`。
- 冻结 test-gate 单元测试：`6/6 Passed`。
- 评分后独立 verifier：`29/29 Passed`。
- verifier 没有重新打开 sealed test-label source。
- 公开产物不含论坛原文或 source identifiers；私有预测和评分证据仍位于 Git-ignored 私有数据层。

## 证据边界

本实验是 held-out 行为性能比较，不建立内部情绪机制、generation 因果效应、LLM 架构普遍
优势或可部署 router。对已消费 test split 的后续工作只能是预登记的既有冻结预测只读分析；
禁止新调参、checkpoint 选择、阈值修改、prompt 修改或新增候选模型 test 运行。
