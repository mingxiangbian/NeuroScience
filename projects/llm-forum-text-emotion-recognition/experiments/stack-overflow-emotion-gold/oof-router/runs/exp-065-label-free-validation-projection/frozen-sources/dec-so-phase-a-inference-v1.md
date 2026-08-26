# DEC-SO-PHASE-A-INFERENCE-V1: 最终推理原型与本地效率验证方法

- Decision ID: `DEC-SO-PHASE-A-INFERENCE-V1`
- Date: `2026-08-24`
- RQ: `RQ-S3` engineering extension
- Parent evidence: `EXP-058` to `EXP-063`
- Parent decision: `DEC-SO-ROUTER-REPLICATION-V1`
- Status: `Method registered; execution not started`
- Primary seed: `42`

## 1. 方法决策

Phase A 只回答一个工程问题：在冻结的 seed-42 M1/M3 pair 和 15% nominal
router operating point 下，能否构造一个结果可复放、端到端可计时、资源占用可接受的
本地开发推理原型。这里的效率只指 model-loaded steady-state；不包含进程启动与模型加载。

本阶段不重新回答模型是否优于 baseline，也不产生独立泛化证据。seed 42 被选为
canonical bundle，是因为它是 EXP-058 至 EXP-060 的 discovery identity，而不是因为它
在 seed 43/44 中表现最好。全 OOF refit 只生成 inference artifact；不得在同一批 OOF
rows 上报告性能、置信区间或新的模型选择结论。

允许的主张上限是：

> A verified local-development inference prototype for the frozen seed-42 pair.

禁止把结果表述为 production deployment、independent-test benefit、cross-seed deployment
benefit、forum generalization 或 emotion mechanism evidence。

## 2. 核心实验与顺序

| ID | 目的 | 主要输出 |
| --- | --- | --- |
| `EXP-064` | 用 3,360 条 seed-42 paired OOF 一次性拟合 inference bundle | canonical numeric router bundle |
| `EXP-065` | 独立生成 label-free validation projection 与 32-row replay reference | private projection and replay artifacts |
| `EXP-066` | 实现 headless runtime，并完成 checkpoint-to-runtime parity | verified core API and thin CLI |
| `EXP-067` | 在统一硬件上比较 B0/B1/B2 的端到端延迟与资源 | paired benchmark evidence |
| `EXP-068` | 只读汇总 Phase A 结果并分配最终状态 | public synthesis |

执行顺序固定为 `EXP-064 -> EXP-065 -> EXP-066 -> EXP-067 -> EXP-068`。前一步未通过
独立 verification，后一步不得开始。任一步失败即停，不用新超参数、替代数据或后验
operating point 自动补救。

## 3. 本阶段的纳入与排除范围

### 3.1 纳入

- seed-42 M1 selected checkpoint；
- seed-42 M3 selected checkpoint；
- seed-42 `paired-oof.npz`；
- frozen six-label order: `love, joy, surprise, anger, sadness, fear`；
- headless single-text API；
- parity 通过后生成的薄 CLI；
- B0 M1-only、B1 M3-only、B2 routed 三种模式；
- batch size 1 的本地交互式 latency、memory 和 route-call measurements。

### 3.2 排除

- seed 43/44 inference bundles；
- M1/M3 再训练或模型微调；除 `EXP-064` 预注册的一次性 full-OOF inference-parameter
  fit 外，禁止 threshold/router/cutoff 搜索、调参或结果后修改；
- B3、cold-start、独立 worker、server queue 或 lazy-worker benchmark；
- Gradio、Web UI、网络服务、容器或云部署；
- validation/test performance recomputation；
- Stack Overflow context 恢复或 C2 matched ablation；
- 对原始 test input、test labels、test-gate evidence 的任何访问。

上述排除项只能由新的方法登记开启，不能作为本阶段失败后的自动替代方案。

## 4. 输入语义与数据边界

### 4.1 推理输入

第一个 runtime 版本只接受一条 UTF-8 plain target text。CLI 必须用 strict UTF-8 解码；
Python API 只接受 `str`。输入原样交给两个冻结 tokenizer，保留大小写、空白和标点，
并沿用各 checkpoint 的 frozen truncation/padding contract。

本阶段不新增 HTML stripping、Markdown parsing、code removal、Unicode normalization、
spell correction、context concatenation 或其他 cleaning。任何新预处理都会改变输入分布，
必须另行登记。

### 4.2 进程级读取 allowlist

每个 runner 必须先解析并记录其 exact input allowlist；未列入的文件访问 fail closed。
symlink、路径越界、哈希不符、identity 不符或间接 manifest 指向 deny target 时立即停止。

- `EXP-064` 只可读取 seed-42 `paired-oof.npz`、冻结 config/source 和必要 Python packages；
  不可读取 checkpoint、validation 或 test artifacts。
- `EXP-065` 的独立 data-steward consumer 可读取 frozen validation source container、
  M1/M3 historical validation probability stacks，以及与它们对应的两份 `selection.json`。
  M1 selection 必须为 epoch 4，M3 selection 必须为 epoch 2。它是唯一可以打开这些
  label-bearing validation artifacts 的 Phase A consumer；mixed-split duplicate mapping
  不在 allowlist 中。
- `EXP-066` 可读取 `EXP-064` bundle、`EXP-065` 两个派生 artifact、seed-42 M1/M3
  checkpoints、tokenizers 和 local Qwen3-4B base。它不得读取原始 validation container
  或历史 validation NPZ。
- `EXP-067` 只可读取 verified runtime、verified bundle、两个 checkpoints、local base 和
  `EXP-065` label-free 720-row projection；不得读取 replay probabilities、原始 validation
  container 或任何 label-bearing artifact。
- `EXP-068` 只读 verified public manifests 与 aggregate benchmark outputs。

全局 hard deny targets 包括原始 test data、test labels、test split manifests、test-gate
directories，以及任何解析后指向这些对象的 manifest entry。deny target 的访问尝试本身
必须造成当前 experiment `Failed`，不得退化为 warning。

### 4.3 `EXP-065` label-free projection

原始 `validation.jsonl` 同时包含 text 和 labels，因此不能直接交给 runtime 或 benchmark。
`EXP-065` 由独立 data-steward consumer 在私有目录中一次性生成：

project-root-relative exact sources 为：

```text
data/stack-overflow-emotion-gold/derived-private/task-v1/validation.jsonl
experiments/stack-overflow-emotion-gold/model-comparison/private/exp-051-m1-roberta-cpu-recovery/seed-42/validation-predictions.npz
experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-051-m1-roberta-cpu-recovery/seed-42/selection.json
experiments/stack-overflow-emotion-gold/model-comparison/private/exp-053-m3-classification-lora/seed-42/validation-predictions.npz
experiments/stack-overflow-emotion-gold/model-comparison/runs/exp-053-m3-classification-lora/seed-42/selection.json
```

1. `validation-text-projection.jsonl`: 720 rows，保持 frozen validation order；每行只能有
   `ordinal`、`opaque_component_group`、`text` 三个字段。
2. `validation-probability-replay-32.npz`: exact keyset 为 `ordinal`、`m1_probabilities`、
   `m3_probabilities`。`ordinal` 是 little-endian int16 `(32,)`，两个 probability arrays
   均为 little-endian float32 `(32, 6)` 且 finite in `[0, 1]`；不得含 gold、prediction、
   correctness、sample ID、component ID 或 text。
3. `projection-manifest.json`: 记录所有 source containers 和两份 selection records 的
   exact path、bytes、SHA-256、mode、schema、row count、field allowlist、selected epoch、
   output hashes、source-order verification 和代码 hash。它必须明确写出：label-bearing
   containers were accessed, but label values were neither used nor persisted。

`ordinal` 是 `0..719` 的 dense index。data steward 只使用 validation container 自身的
`component_id` 在内存中构造等价关系，再按首次出现顺序编码为 dense integer；不得读取
mixed-split duplicate mapping。输出的 `opaque_component_group` 不保留原始 ID。32 个
replay ordinals 固定为：

```text
floor(k * 719 / 31 + 0.5), for k = 0, 1, ..., 31
```

两份 historical probability NPZ 保存的是 epoch stack，不是已切片的 selected-epoch
matrix。data steward 必须校验两份 `selection.json`，分别取
`probabilities[selected_epoch - 1]`，即 M1 stack index 3 和 M3 stack index 1。它可在
内存中使用 historical sample IDs 验证两个 stack 与 validation order 完全对齐，但不得把
这些 IDs 写入任一 Phase A artifact。NPZ 读取一律 `allow_pickle=False`。

## 5. `EXP-064`: canonical inference bundle

### 5.1 输入与一次性状态

唯一数据输入为 seed-42 paired OOF production artifact：

```text
oof-router/private/exp-058-paired-oof-production/paired-oof.npz
```

输入必须是 3,360 rows、six-label order 完全一致，并通过 registered bytes、SHA-256、array
schema、dtype、finite-value 和 source-order checks。输出目录必须不存在；runner 采用
append-only one-shot write。状态只能从 `Registered` 进入 `CompletedAwaitingVerification`，
再由独立 verifier 进入 `Complete`；任一失败进入 `Failed`，不得原地覆盖重跑。

Correction (`2026-08-26`): seed-42 discovery 使用的是早期非 attempt layout，不存在
`selected-attempt.json` 或 `oof-complete.json`。EXP-064 的 legacy lineage 因此绑定现存的
EXP-058 `run.json` + final Passed `verification.json`、paired OOF identity，以及 EXP-060
`run.json` + Passed `verification.json`；不得回填旧目录或制造替代 completion record。

`EXP-064` 不重开 tokenizer 或 checkpoint。它对 paired artifact 中的 `m1_logits` 与
`m3_logits` 复用 EXP-060 `stable_sigmoid` 得到 identity probabilities，并直接读取
`character_lengths` 与已经按 M1 frozen truncation contract 计算的 `m1_token_lengths`。
`EXP-066` 才在 live text 上用同一 tokenizer/truncation contract 重算这两个 length values。

### 5.2 full-OOF threshold refit

M1 与 M3 各拟合一个 shared six-label threshold。候选网格固定为 `0.05..0.95`，步长
`0.01`，calibrator 固定为 identity。选择顺序完全复用 EXP-060：

1. six-label Macro-F1 最高；
2. 在 `1e-12` tolerance 内并列时 Hamming loss 最低；
3. 再并列时离 `0.5` 最近；
4. 再并列时 threshold 较低者优先。

这一步使用 gold 仅构造 inference parameters，不输出或解释同数据 performance。

### 5.3 router target 与 14 个 features

每行 target 以完整 six-bit vector 计算：只有当 M3 row Hamming loss 严格小于 M1 时为
`1`；相等时为 `0`，即 tie to M1。

features 的顺序和定义冻结为：

1. `m1_probability_love`
2. `m1_probability_joy`
3. `m1_probability_surprise`
4. `m1_probability_anger`
5. `m1_probability_sadness`
6. `m1_probability_fear`
7. `m1_mean_binary_entropy`
8. `m1_max_binary_entropy`
9. `m1_minimum_threshold_margin`
10. `m1_predicted_cardinality`
11. `m1_highest_probability`
12. `m1_lowest_probability`
13. `character_length`
14. `m1_token_length`

entropy 使用 natural log，并将 probabilities clip 到 `[1e-15, 1-1e-15]`。minimum
threshold margin 是六个 M1 probabilities 到 full-OOF selected M1 threshold 的最小绝对
距离。在 `EXP-064` 中，token length 直接取 paired artifact 已保存的 truncated
`m1_token_lengths`；在 live runtime 中，它必须由 frozen M1 tokenizer 按同一 truncation
contract 得到。不得使用 M3 output、M3 token length、gold/correctness、
sample/component/fold ID、raw text value 或 validation/test statistic 作为 router feature。

### 5.4 scaler、router 与 cutoff

- `StandardScaler` 在全部 3,360 OOF feature rows 上拟合；
- `LogisticRegression(penalty="l2", C=1.0, class_weight="balanced",
  solver="liblinear", max_iter=1000, random_state=42)`；
- 不做 hyperparameter search；
- router target 若不是 exact `{0, 1}` 两类则停止，不采用 single-class fallback；
- nominal target call rate 固定为 `0.15`；
- `count = ceil(0.15 * 3360)`；
- cutoff 是降序 score 中第 `count` 个值；
- runtime 以 `score >= cutoff` route，cutoff ties 全部调用 M3。

### 5.5 canonical serialization

不得用 `joblib`、pickle 或任意可执行反序列化格式。bundle 由两部分组成：

- numeric NPZ 的 exact keyset 为 `scaler_mean`、`scaler_var`、`scaler_scale`、`classes`、
  `coef`、`intercept`。前三者是 little-endian float64 `(14,)`，`classes` 是 exact
  little-endian int64 `[0, 1]`，`coef` 是 little-endian float64 `(1, 14)`，`intercept`
  是 little-endian float64 `(1,)`；禁止 object dtype，所有浮点值必须 finite，读取时固定
  `allow_pickle=False`；
- canonical JSON：schema version、label/feature order、M1/M3 thresholds、calibrator、
  sigmoid rule、router hyperparameters、cutoff、tie policy、nominal rate、dtype、shape、
  source identities 和 numeric NPZ hash。

JSON 使用 UTF-8、sorted keys、compact separators、`allow_nan=false` 和一个 terminal newline。
每个 experiment 的 identity manifest 必须为其实际 allowlist 中每一项记录 exact
path/bytes/SHA-256/mode，并按职责绑定：上述 seed-42 legacy run/verification records 与
paired OOF；M1 selected checkpoint/tokenizer；M3 adapter/head、base revision 与 tokenizer；两份
historical validation probability stacks 和 selection records；以及 runner/config/verifier
hashes 与 environment versions。未被某 runner 读取的资产由相应后续 verifier 核验，不得
为补 lineage 扩大 runner allowlist。artifact hash 用于 lineage；它不授权对 ordinary
inference request 计算或保存 content hash。

独立 verifier 必须自行加载 numeric arrays 并重建 scaler、stable sigmoid、router scores、
cutoff 和 route mask，不得 import runner。它验证 bundle 可完整复放，但不计算 OOF model
performance。

## 6. `EXP-066`: headless runtime 与 parity

runtime config 必须逐文件绑定以下 three roots 的 exact bytes/SHA-256/mode，不接受按目录名
推断的 latest checkpoint：

```text
experiments/stack-overflow-emotion-gold/model-comparison/private/exp-051-m1-roberta-cpu-recovery/seed-42/selected-checkpoint/
experiments/stack-overflow-emotion-gold/model-comparison/private/exp-053-m3-classification-lora/seed-42/selected-checkpoint/
models/qwen3-4b/mlx-bf16/
```

### 6.1 core API

冻结入口为：

```python
predict(text: str, allow_qwen: bool = True, include_diagnostics: bool = False)
```

标准返回至少包含 six-bit prediction、ordered active labels、`neutral` flag、used path 和
degraded flag。若 six-bit vector 全为 0，`neutral=true`，但不得把 neutral 当作第七个训练
label。`include_diagnostics=false` 时不返回 probabilities、route score 或 thresholds。

调用顺序固定为：

1. M1 tokenize/inference，获得 six probabilities；
2. 用 bundle 构造 14 features 并计算 route score；
3. `allow_qwen=true` 且 `score >= cutoff` 时调用 M3，否则使用 M1；
4. 对实际使用模型应用其 full-OOF threshold；
5. 物化最终 six-bit vector、labels 和 neutral flag。

正式 parity 与 benchmark 使用 `allow_fallback=false`。研究 demo 可在 M3 runtime error 时
回退 M1，但必须返回 `degraded=true` 和明确 warning；该调用不能计入 verified evidence。

### 6.2 32-row probability replay parity

parity 输入由 `EXP-065` projection 与 replay NPZ 按 ordinal 连接。历史 artifacts 没有 raw
logits，因此本阶段检查 selected-epoch probabilities，不虚构 logit replay。

runtime runner 对 32 条 text 重新执行 M1/M3 checkpoints；独立 verifier 不 import runtime，
而是独立实现 tokenizer/model invocation、feature construction、scaler、sigmoid、cutoff 和
thresholding。至少验证：

- M1 probability max absolute error `<= 1e-5`；
- M3 probability max absolute error `<= 1e-5`，与 EXP-053 historical replay gate 一致；
- 14-feature matrix max absolute error `<= 1e-8`；
- standardized features、router scores max absolute error `<= 1e-8`；
- route mask、selected model、final six-bit vector、active labels 和 neutral flag exact match；
- 无 NaN/Inf、shape drift、label-order drift、fallback 或 row-order drift。

若当前 backend 无法满足 probability tolerance，应停止并登记 runtime incompatibility；不得
放宽 tolerance、改 checkpoint 或只保留 prediction-vector parity。

### 6.3 薄 CLI

只有 parity 全部通过后才创建 CLI。CLI 只负责 strict UTF-8 input、调用 core API、输出
JSON 和设置 nonzero exit status；不得复制模型或 router logic。CLI/UI 演示不是 parity 的
替代证据，Gradio 留到后续阶段。

ordinary requests 默认不落盘，不保存 raw text、token IDs、probabilities、content hash 或
row-level diagnostics。显式 debug 也只能把 diagnostics 返回当前调用者，不建立持久日志。

## 7. `EXP-067`: B0/B1/B2 benchmark

### 7.1 比较对象

- `B0 M1-only`: 执行 M1 并物化 M1 final output；
- `B1 M3-only`: 执行 M3 并物化 M3 final output；
- `B2 routed`: 执行 M1、14-feature/router；仅对 routed rows 执行 M3，再物化 final output。

三个模式使用相同的 verified checkpoints、tokenizers、720-row projection、batch size 1 和
frozen row order。B0/B1 是 runtime cost references，不产生新的分类性能结论。

### 7.2 resource smoke 与 residency

B0 的 exact resident set 只有 M1，B1 只有 M3，B2 同时 resident M1 与 M3。这是三个实际
system modes 的组成差异，B2/B1 contrast 有意包含双模型常驻造成的 memory-pressure cost；
不得在 B0/B1 中加载未使用模型来人为配平。

M1 backend 固定为 PyTorch CPU，M3 固定为 MLX Metal。PyTorch intra-op/inter-op、
`OMP_NUM_THREADS`、`VECLIB_MAXIMUM_THREADS` 均固定为 `1`，tokenizer parallelism 关闭；三个
模式不得另开 dataloader 或 tokenizer worker。正式计时前，只用 synthetic warmup text
执行 no-result resource smoke，并验证 B2 的两个模型可同时加载、推理和同步，且系统
memory pressure 未进入 critical/red。

若 both-resident smoke 失败，`EXP-067` 停止并记为 resource-blocked。不得在同一 experiment
中静默切到 lazy load、unload/reload、B3 或 worker process；这些方案需要单独预登记后再测。

### 7.3 进程、顺序与 warmup

每个 `mode x repetition` 使用 fresh process，共 9 个 timed processes。三次 repetition 的
mode 顺序用固定 Latin square：

```text
rep-1: B0, B1, B2
rep-2: B1, B2, B0
rep-3: B2, B0, B1
```

每个 fresh process 先用不属于 720-row projection 的 synthetic UTF-8 strings warm up。
B0 只 warm M1 至少两次，B1 只 warm M3 至少两次，B2 warm M1/router，并用
benchmark-only forcing 让 route-to-M3 与 no-route path 各完成至少两次 inference and
synchronization。timed rows 禁止 forcing；warmup observations 不进入统计量。

使用与 EXP-058 至 EXP-063 相同的 heavy-workload mutex：

```text
oof-router/private/locks/heavy-research-workload.lock
```

每次 run 记录 commit、macOS、chip、RAM、power source、thermal state、Python、PyTorch、MLX、
Transformers 版本。锁冲突、thermal state 非 nominal、power source drift、model/backend drift
或 device drift 时停止该 attempt。

### 7.4 timing contract

计时器固定为 `time.perf_counter_ns()`。端到端 total 从读取内存中的 Python `str` 后、
tokenization 前开始，到 final output dict 的所有 CPU-visible values 完全物化后结束。文件
I/O、进程启动、model load、warmup 和 CLI rendering 不计入 per-row total。

每行记录以下 mutually exclusive components。component sum 与 total 的绝对差必须
`<= max(1 ms, 0.02 x total)`；超出说明 instrumentation 不完整并使 attempt 失败：

- `tokenize_preprocess_ns`
- `m1_inference_ns`
- `feature_router_ns`
- `m3_inference_ns`
- `postprocess_materialize_ns`
- `total_ns`

PyTorch CPU tensors 必须在 segment 结束前物化为 CPU-visible values；PyTorch MPS 不属于
本方法，出现时按 backend drift 停止。MLX 在 segment 边界对所需 arrays 调用
`mx.eval(...)`，再读取 CPU-visible values。不得用异步 dispatch time 替代完成时间。

B2 三次 repetition 的 route mask、route count 与 selected path 必须逐 row exact match。
nominal rate 为 15%，ties 可使 actual rate 略高，但 actual M3 call rate 必须 `<= 0.20`。
任何 timed fallback、inference error、retry、row skip 或 output-shape drift 都使 benchmark
失败。

### 7.5 memory contract

每个 fresh process 在 model load 前先记录 15 秒、1 Hz 的 idle baseline；load 后继续每秒
采样一次，并在 post-load、post-warmup、timed peak、post-run 四个 checkpoint 记录：

- process RSS；
- process `ru_maxrss` high-watermark；
- MLX active、cache 与 reset-after-load peak high-watermark；
- macOS memory-pressure 原始状态与 frozen `normal/warn/critical` 映射；
- compressed memory；
- `vm_stat` monotonic `Pageouts`/`Swapouts` counters，按其报告的 page size 转换为 bytes。

RSS 与 MLX memory 分开报告，不相加伪造 total。资源门槛固定为：

- 无 OOM 或 forced termination；
- memory pressure 从未进入 critical/red；
- 只有当 timed pageout 或 swapout rate 高于 idle baseline rate 加 `1 page/s`，并且同一
  counter 的 timed total increase 超过 `16 pages` 时，才判为 thrashing failure；
- post-run RSS `<= 1.10 x post-warmup RSS`。

任一门槛失败时，不得给出 deployment-ready 结论。

### 7.6 统计与效率判据

primary point estimate 使用三个 repetitions 的全部 paired rows。primary contrast 为 B2
相对 B1 的 end-to-end reduction：

```text
reduction = 1 - mean_latency(B2) / mean_latency(B1)
```

进行 10,000 次 hierarchical paired bootstrap，seed 固定为 `20260824`。每次先从三个
repetition blocks 中有放回抽取 3 个 block，再从 `opaque_component_group` 中有放回抽取
全部 groups；B1/B2 始终使用相同的 repetition 与 group draws，并保留每个抽中 group 的
全部 rows。报告 percentile 95% CI。P95 contrast 在相同 hierarchical draws 中计算
`P95(B2) - P95(B1)`。public aggregate 另列每个 repetition 的 reduction 与 P95，但不以
单次 repetition 替代 primary hierarchical CI。

效率等级：

- `Strong`: reduction CI lower bound `>= 0.50`；
- `Moderate`: reduction CI lower bound `>= 0.10` 且 `< 0.50`；
- `Insufficient`: reduction CI lower bound `< 0.10`。

无论等级如何，正向效率结论还要求：P95 difference 的 95% CI upper bound `<= 0`、
actual M3 call rate `<= 0.20`、zero error/fallback，以及全部 memory gates 通过。B0 只作为
M1 cost reference；不得用 B0 替换 B1 作为 primary speedup denominator。

## 8. 输出、权限与隐私

private directories 设为 mode `0700`，private files 设为 `0600`。以下对象只能保留在
private tree：projection text、replay probabilities、row-level route mask、row-level latency、
memory samples、model/bundle parameters、checkpoint paths 和 failure traces 中可能出现的输入。

public outputs 仅允许：

- experiment identity、method/config hashes 与 verifier status；
- aggregate latency mean/median/P95、bootstrap CI、route-call rate；
- aggregate RSS/MLX peaks 与 memory-gate status；
- zero-error/fallback status；
- claim boundary 和最终状态。

public outputs 不得包含 text、token IDs、probability vectors、prediction vectors、row ordinal、
component group、content hash、private absolute path 或可反推单条样本的信息。

## 9. 验证独立性与停止条件

每个 experiment 都必须冻结 config、runner 和 independent verifier。verifier 可以复用明确
登记的数学定义，但不得 import runner/runtime modules，也不得相信 runner 写出的 derived
summary。verification 至少重算 schema、hash、row counts、array constraints 和本实验的核心
判据。

出现以下任一情况立即停止当前及后续 experiments：

- input identity/hash/schema/order/mode drift；
- allowlist violation、test access 或 privacy leak；
- label-bearing validation artifact 被 `EXP-066/067` 打开；
- bundle 非 canonical、反序列化需要 pickle 或 replay 不一致；
- parity tolerance、route mask 或 final output 不一致；
- formal benchmark 出现 fallback、retry、row skip、async timing 或 resource-gate failure；
- verifier 非零退出或任一 required check 为 `Failed`。

停止后只登记 failure evidence；不得自动改方法、阈值、cutoff、backend 或 workload 继续。

## 10. `EXP-068` 决策规则

`EXP-068` 不读取 row-level/private evidence，只根据 verified manifests 与 aggregate outputs
分配一个状态：

1. `Verified local development inference prototype`: EXP-064/065/066/067 全部通过，
   效率至少为 Moderate，P95、call-rate、zero-error/fallback 和 memory gates 全部通过。
2. `Retained as research demo`: bundle 与 parity 通过，但效率为 Insufficient，或完整
   deployment-efficiency gates 未通过；只能保留为 headless/CLI research demo。
3. `Failed or incomplete`: bundle/parity 失败、隐私边界破坏、formal benchmark 未完成，
   或 verifier 无法给出可信结论。

即使达到第 1 状态，evidence strength 仍限于同一台本地设备、同一组 frozen checkpoints、
single-text batch size 1、model-loaded steady-state 和 label-free validation text workload。
它不包含 cold start/model load，不升级 EXP-063 的模型泛化结论，也不授权 test evaluation。

## 11. 完成定义

Phase A 只有在以下条件全部满足后才算方法意义上的完成：

- five experiment IDs 均有 frozen identity 与终态；
- seed-42 numeric bundle 可由 independent verifier 重建；
- runtime 对 32-row replay 完成 checkpoint-to-output parity；
- B0/B1/B2 在 frozen 720-row workload 上完成三次 fresh-process repetitions；
- latency CI、P95、call rate、errors/fallback 和 memory gates 均有可审计 aggregate output；
- `EXP-068` 按预注册规则给出唯一状态与严格 claim boundary。

未满足上述任一项时，应报告具体缺口，不以“原型能启动”代替 Phase A 完成。
