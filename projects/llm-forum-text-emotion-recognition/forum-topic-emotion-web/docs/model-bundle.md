# Phase C 冻结模型包说明

日期：2026-08-31。本文件是现有部署工件的引用说明，不创建新模型包、不复制权重，也不重新运行历史评价。

## 绑定关系

网站复用 **EXP-066 headless runtime parity attempt 2** 已完成的 seed42 推理合同。部署组合为 M1 RoBERTa、M3 Qwen3-4B 分类 LoRA 与分类头、标准化器和逻辑回归 router。它不是 Phase B 的 15 个 fold 模型，也没有在新网站数据上重新训练、调阈值或调 router。

运行时从父 EXP-066 冻结配置选取部署资产白名单。虽然父配置或 bundle manifest 记录了历史数据来源，网站不沿这些引用打开 projection、replay、OOF 或 gold 数据。

## 元数据身份

下表 SHA-256 来自父冻结记录。前三项小型元数据文件在编写本文时以只读方式重新核对，均匹配；大模型和参数二进制未为文档重新读取或复制。

| 工件 | SHA-256 |
| --- | --- |
| [EXP-066 冻结 config](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/frozen-sources/config.json) | `106db4b86614ac70c84f04a322b046bc1049686099c590997955120993bb9983` |
| [EXP-066 completion](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/runtime-complete.json) | `b039b80a3ba1778d38352fc8ee7c075dc342e17dd127d9acfd1574d99c149408` |
| [父配置绑定的 bundle manifest](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/oof-router/private/exp-064-seed42-inference-bundle/bundle.json) | `a1d99d9638cedcf31dcba382eb2be3a5cffd7eceee442f012cb2d3a1214dbf22` |
| 父 completion 绑定的 verification | `191507ae69c2a2f0d3f4f7aaf99dca8ee9c3921ade954f503f6e929df946021b` |
| 冻结 `runtime_exp066.py` | `4cd1c226d002e713c324bda61dcad841434af25db2bd7ccf2b04742a3f27e689` |
| 父配置中的 `bundle_parameters` | `7e9946205e533501862eeb5c1a7d7f819da6ee607fa6b3e452039bf7ada03b6d` |
| 父配置中的 `m3_adapter` | `3a6d7b24d7a39bbfa97fd8f89cd81d614cf0e441ed82782279dfb2473989efdb` |
| 父配置中的 `m3_head` | `fa09f365c025877f42890d49c97a93134d32f86aac5896aa19b0b7e1946979d7` |
| 父配置中的 `m3_prompt` | `0722ff947ba030cdf5b42358c7ba45a4d0d6372ccf0e2be28d131a0c24bdb90d` |

M1 checkpoint 和 M3 base 的逐文件路径、大小、mode、hash 以冻结 config 的 `runtime_assets` 为准，不在这里生成第二份资产清单。`runtime-complete.json` 的状态为 Complete、CLI gate 为 open；子进程仍会检查它所绑定的 Passed verification，不能用本文代替运行时门禁。

## 标签、阈值与路由

固定标签顺序：`love, joy, surprise, anger, sadness, fear`。M1 和 M3 使用各自冻结的标量阈值，目前均为 **0.31**，以 `score >= threshold` 产生六维决策。六标签都不触发时标为 neutral；这不新增一个经过独立训练的中性类别。

router 使用 14 个固定特征：六个 M1 标签分数、M1 平均/最大二元熵、最小阈值距、预测标签数、最高/最低分数、字符长度、M1 token 长度。标准化后由父 bundle 的逻辑回归评分。

冻结的 router cutoff 为 **0.7796902005928844**，比较符为 `>=`。父训练域运行点的 nominal call rate 为 0.15；网站不会对每个话题重新选前 15%，也不为维持调用率而修改 cutoff。分布变化可能使新话题的实际请求比例不同。

原文不清洗或归一化。M1 最大使用长度为 256 tokens；M3 使用冻结 prompt/chat-template 路径，最大长度为 384 tokens。诊断可以记录截断前后长度，但不会为了得到不同结果修改 prompt、输入或截断合同。

## 环境与执行边界

模型子进程固定使用 `/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python`，Python 3.11.15、arm64。父配置绑定的关键依赖为：

| 依赖 | 版本 |
| --- | --- |
| NumPy | 2.4.6 |
| Torch | 2.9.1 |
| Transformers | 5.14.1 |
| Tokenizers | 0.22.2 |
| MLX | 0.32.0 |
| MLX-LM | 0.31.3 |
| Safetensors | 0.8.0 |

API 使用另一套本模块 Python 3.12 `.venv`，不在 HTTP 进程中加载模型。子进程首次加载前检查部署资产 hash、mode、清单与环境；随后检查已记录的文件身份状态。结束时还需通过最终身份/资源检查并退出 0，不能把“所有逐条预测已返回”直接等同于任务成功。

模型进程强制离线，禁网络访问；来源采集是独立的公开 API 操作，不将上传原文发给外部模型服务。全局重研究任务锁与 dispatcher 继承锁防止与其他重实验或重复服务同时加载模型。

当前单任务上限为 500 条、每条 64 KiB、3600 秒；模型进程 RSS 上限 12 GiB，MLX 上限 10,000,000,000 bytes。网站队列与 collector 还有各自更小的边界，不能把这些上限解释为性能保证。

## 缓存和版本解释

M1/M3 分开缓存，键绑定精确 UTF-8 输入 hash 与运行 fingerprint。fingerprint 包含输入合同版本、bridge 文件 hash、父 config hash 和父 completion hash。规范化 dedup_hash 不参与推理缓存。一次任务结束后缓存消失；新任务或重放不会共享原进程缓存。

默认模式行为、失败降级与未知成本见 [使用手册](/Users/phoenix/Assistant/NeuroScience/projects/llm-forum-text-emotion-recognition/forum-topic-emotion-web/docs/user-guide.md)。derived 统计和来源链接展示修正不重算模型预测，也不改写父模型工件。

这个绑定说明支持部署可追溯性，不新增准确率、跨 seed 部署、外部论坛泛化、长期服务稳定性或情绪机制结论。当前 EXP-077 已因 critical memory pressure 按规则停止，Soak 门未通过，EXP-078 正式运行未继续。父模型身份门通过不能替代整机内存压力与连续工作负载的安全门；本轮不再启动新 Research 或快照重放。
