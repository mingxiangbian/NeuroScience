# EXP-021: Qwen3-1.7B Paired Environment and Provenance Smoke

---
date: 2026-07-31
experiment_id: EXP-021
tier: Minor
rq: RQ-G2
status: completed
preregistered_at: 2026-07-31
completed_at: 2026-07-31
stage: environment-and-model-provenance
---

## Question

在不读取任何项目数据的条件下，当前 Apple Silicon 环境能否：

1. 建立可追溯的本地 MLX-LM 运行环境。
2. 从 Qwen 官方仓库下载固定 revision 的 1.7B Base 与 post-trained 模型。
3. 使用同一版转换工具将二者转换为未量化 MLX BF16。
4. 分别完成一次最小合成推理，证明后续实验链具备技术可行性。

本实验只回答环境和来源可行性，不回答情绪分类性能、post-training 收益或内部
表征问题。

## Fixed Models

| Condition | Official repository | Frozen revision | Training stage |
| --- | --- | --- | --- |
| Post-trained | `Qwen/Qwen3-1.7B` | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` | Pretraining + post-training |
| Base | `Qwen/Qwen3-1.7B-Base` | `ea980cb0a6c2ae4b936e82123acc929f1cec04c1` | Pretraining only |

下载必须指定完整 revision，不允许使用未解析的 `main`。源权重来自官方仓库，
两个条件都由同一个本地环境执行 BF16 MLX 转换，不混用第三方转换仓库。

## Fixed Environment

- Host: local Apple Silicon Mac, 16 GB unified memory.
- Environment path: `/Users/phoenix/miniconda3/envs/emotion-llm-mlx`.
- Python: `3.11`.
- MLX-LM: `0.31.3`.
- Model precision: source precision as published；local runtime copy `bfloat16`.
- Quantization: disabled.
- API or remote inference: none.

安装完成后保存完整 `pip freeze`、Python/macOS/芯片信息和关键包版本。依赖解析出的
MLX、Transformers、tokenizers 与 Hugging Face Hub 版本按实际安装结果记录，不在
运行前伪造。

## Storage and Provenance

```text
projects/llm-forum-text-emotion-recognition/models/
├── qwen3-1.7b/
│   ├── upstream/                 # ignored
│   ├── mlx-bf16/                 # ignored
│   ├── README.md
│   ├── .gitignore
│   └── manifest.json
└── qwen3-1.7b-base/
    ├── upstream/                 # ignored
    ├── mlx-bf16/                 # ignored
    ├── README.md
    ├── .gitignore
    └── manifest.json
```

每个 manifest 至少记录：

- official repo ID、revision、下载时间和下载方法。
- upstream 与 MLX BF16 的逐文件字节数和 SHA-256。
- 转换命令、Python、`mlx-lm` 和 `mlx` 版本。
- 本地相对路径、总字节数、Git ignore 检查结果。

模型权重、Hugging Face cache、转换副本和合成生成文本不得提交到 Git。

## Data Boundary

- 不读取 `data/goemotions/official/`。
- 不读取 GoEmotions train、dev、test、标签文件或已有预测。
- 不读取 TweetEval 数据。
- 只使用代码中直接给出的无标签合成英文短句。
- GoEmotions test 继续不存在且 test gate 保持关闭。

## Smoke Conditions

Post-trained 条件：

- 使用官方 tokenizer chat template。
- 明确关闭 thinking mode。
- greedy decoding。
- 最多生成 8 tokens。

Base 条件：

- 使用 plain completion，不使用聊天模板衡量指令遵循。
- greedy decoding。
- 最多生成 8 tokens。

只检查加载、前向生成和非空输出。不得计算任务 F1、Accuracy 或据此选择 prompt。

## Resource Budget

- Maximum setup attempts: 2.
- Maximum conversion attempts per model: 2.
- Maximum smoke generations per model: 1 successful generation.
- Model and conversion storage: at most 16 GiB total.
- Wall-clock budget: 120 minutes, excluding explicit user pauses or network outage.
- API cost: USD 0.
- Project data rows accessed: 0.

超出预算前停止，保留失败日志，并说明继续、量化或改用官方 MLX conversion 的
代价。不得静默切换到 4-bit。

## Required Artifacts

```text
runs/exp-021-environment-model-smoke/
├── run.json
├── stdout.log
├── environment-lock.txt
└── verification.json
```

模型目录另保存各自的 README 与 manifest。`run.json` 记录命令、Git 状态、运行
时间、硬件、模型 revision、转换状态、数据访问声明和 artifact 哈希。

## Pass Criteria

- 独立环境存在，关键依赖可导入且版本已锁定。
- 两个 official revision 均完整下载。
- 两个模型均由相同环境转换为未量化 MLX BF16。
- upstream 与转换文件的大小、SHA-256 和总量已记录。
- Base 与 post-trained 模型各成功加载并完成一次规定的合成生成。
- 模型二进制被 Git 忽略。
- `verification.json` 复核 revision、文件哈希、依赖版本和零项目数据访问。

任何一项未通过，EXP-021 保持 `Rejected` 或 `In Progress`，不得进入小样本资源
试跑。

## Stop Conditions

- 解析出的远端 revision 与冻结值不一致。
- 下载缺失、文件大小异常或哈希在验证间变化。
- 转换发生 NaN、异常退出或未解释的 OOM。
- 任一命令意外读取项目数据。
- 模型文件未被 Git ignore。
- 需要将项目文本发送给外部服务。

## Execution Result

Completed on 2026-07-31 and independently verified.

- Both frozen official revisions were downloaded and converted in the same environment to
  unquantized MLX BF16.
- Post-trained and Base synthetic smoke generations were non-empty. These checks are not task
  performance evidence.
- Upstream plus converted model storage was `14,437,414,837` bytes; manifests contain per-file
  byte counts and SHA-256 values.
- `accessed_splits` was empty, `project_data_rows` was 0, and validation/test were not accessed.
- The original `pip freeze --local` artifact was empty because of pip's local-package filtering.
  It remains unchanged; the full corrected lock and explanation were appended as
  `environment-lock-corrected.txt` and `correction-2026-07-31-environment-lock.md`.

Run artifacts: [`../runs/exp-021-environment-model-smoke/`](../runs/exp-021-environment-model-smoke/)
