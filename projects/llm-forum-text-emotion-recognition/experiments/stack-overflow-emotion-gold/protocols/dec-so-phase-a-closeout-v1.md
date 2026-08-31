# DEC-SO-PHASE-A-CLOSEOUT-V1: Phase A 收口与 Phase B 放行

- Decision ID: `DEC-SO-PHASE-A-CLOSEOUT-V1`
- Date: `2026-08-26`
- RQ: `RQ-S3` engineering extension
- Parent method: `DEC-SO-PHASE-A-INFERENCE-V1`
- Experiments: `EXP-064` to `EXP-068`
- Source commit: `50ce970e5794867cbbd89c1af600ddbac39ec577`
- Lifecycle status: `Closed`
- Closeout outcome: `Closed with partial success`
- Frozen EXP-068 decision: `Failed or incomplete`

## 1. 收口决策

Phase A 到此停止执行。项目不再重跑、覆盖或修补 `EXP-064` 至 `EXP-068`，也不把
`EXP-067` 调整为 Pass。

三个状态承担不同职责：

| 字段 | 冻结值 | 含义 |
| --- | --- | --- |
| Lifecycle status | `Closed` | Phase A 不再继续运行 |
| Closeout outcome | `Closed with partial success` | 推理原型成功，效率验证未完成 |
| EXP-068 decision state | `Failed or incomplete` | 预注册的 Phase A 全部完成条件没有满足 |

Closeout 不修改 EXP-068 的原始判断。它只在项目层声明 Phase A 已结束，并把下一项工作
切换到 Phase B。

## 2. 冻结结果

| Experiment | Selected terminal state | Verification | Closeout interpretation |
| --- | --- | --- | --- |
| `EXP-064` | `Complete` | 30/30 Passed | Seed-42 numeric inference bundle verified |
| `EXP-065` | attempt-2 `Complete` | 30/30 Passed | Label-free projection and replay verified |
| `EXP-066` | attempt-2 `Complete`; CLI gate open | 35/35 Passed | Headless runtime, checkpoint parity and thin CLI verified |
| `EXP-067` | attempts 1 and 2 `Failed`; each stopped after one worker | unavailable | Formal efficiency benchmark incomplete |
| `EXP-068` | `Complete` | 20/20 Passed | Frozen decision is `Failed or incomplete` |

Phase A 支持的系统分类只有：

> Verified local research demo for the frozen seed-42 headless and CLI stack.

## 3. Terminal evidence bindings

以下 SHA-256 以项目根目录
`projects/llm-forum-text-emotion-recognition/` 为路径基准。

| Evidence | Relative path | SHA-256 |
| --- | --- | --- |
| Phase A method | `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-a-inference-v1.md` | `8baec947857016bad00bb6dae7982a7f20a036a1e3595ee6d3a9faeee96273d7` |
| EXP-064 verification | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-064-seed42-inference-bundle/verification.json` | `00e05110b94da20bdda0c156ce4a90b16afaa84c24a1c3ffe96ade5c440a676e` |
| EXP-064 completion | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-064-seed42-inference-bundle/bundle-complete.json` | `5c8ae89a16b650353b21fc0dce8a015e439122a7c7c0ef240ab4e67445639f72` |
| EXP-065 attempt-2 verification | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-065-label-free-validation-projection/attempt-2/verification.json` | `bc75d1c9668b607d9455809b08a1df8fae1654193d532bd13f8c7f293f73a911` |
| EXP-065 attempt-2 completion | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-065-label-free-validation-projection/attempt-2/projection-complete.json` | `a798d8f7ed74ff199d77f150aff52917f4ba3246222be312d24edec1399ecd01` |
| EXP-066 attempt-2 verification | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/verification.json` | `191507ae69c2a2f0d3f4f7aaf99dca8ee9c3921ade954f503f6e929df946021b` |
| EXP-066 attempt-2 completion | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/runtime-complete.json` | `b039b80a3ba1778d38352fc8ee7c075dc342e17dd127d9acfd1574d99c149408` |
| EXP-067 attempt 1 failure | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-067-steady-state-benchmark/run.json` | `75a5d076d9331082a3126492c6dd415d53b05228153ae67b47adb38c12994140` |
| EXP-067 attempt 2 failure | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-067-steady-state-benchmark/attempt-2/run.json` | `137043c387c663f1162d80b29fb7700ecab4c2ae217121fba5942cc8a09a3fb4` |
| EXP-068 synthesis | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-068-phase-a-synthesis/phase-a-synthesis.json` | `5ea91c455427a88d370b70a8bcc4fb0f4b8117b377de531d6a36cf5a3be62751` |
| EXP-068 verification | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-068-phase-a-synthesis/verification.json` | `3218677649b35b72a221e856b40d0f2f76a4b0be0d5bf92328a6ec57e24fc26c` |
| EXP-068 completion | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-068-phase-a-synthesis/phase-a-complete.json` | `fe20bd9b2ba107699b0e57bf9df1bafb3c4ab5eaea5df160e40e29f8e974597c` |

## 4. Append-only lineage

以下失败保持为正式 lineage，不参与 selected success：

| Attempt | Relative path | SHA-256 |
| --- | --- | --- |
| EXP-065 attempt 1 | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-065-label-free-validation-projection/run.json` | `6be9eaaea889cdc0cb57f55e95e2b88c2ba59c781c47f7cbe7afa1ae521e7edd` |
| EXP-066 attempt 1 | `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/run.json` | `489a8e226efe95856e4096c0262a60d647511df6bd0af1345b95d0f992860e3f` |

两次 EXP-067 failure 永久保留。首个 B0 worker 的局部 latency 不进入正式结果。后续工作
不得放宽旧 RSS gate、补跑剩余 workers 或为 EXP-067 回填 Pass。

## 5. Claim boundary

Phase A 支持：

- seed-42 numeric bundle 可复放；
- label-free projection 与 32-row probability replay 通过验证；
- 32-row checkpoint-to-runtime parity 通过验证；
- thin CLI 可作为本地 research demo。

Phase A 不支持：

- steady-state latency reduction；
- cost、memory 或 deployment-efficiency benefit；
- production readiness；
- independent-data 或 test benefit；
- cross-seed deployment generalization；
- forum generalization；
- Phase A classification-performance claim；
- emotion mechanism interpretation。

## 6. Phase B transition

Phase B 不以 EXP-067 成功为前置条件。Phase B 读取模型、fold 和训练数据的既有冻结证据，
研究 Classification LoRA 的任务相关层级表示与功能依赖。

Phase A router artifact 不进入 Phase B representation extraction、probe、drift 或 LoRA
ablation 的输入。它只可供可选的 Router interpretability 实验读取，且该实验继续归
`RQ-S3`。

下一执行门是 `EXP-069: Phase-B Representation Extraction Preflight`。任何 hidden-state
正式抽取前，EXP-069 必须验证 checkpoint、input rendering、hook 位置、pooling、M2/M3
replay、pre-LoRA equivalence、资源和隐私合同。

本 closeout 不授权模型 forward 或 EXP-069 execution。
