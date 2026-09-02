# EXP-071 Incident 002：CKA 分母失败定位

- 日期：2026-08-30
- Diagnostic ID：`EXP-071-DENOMINATOR-DIAGNOSTIC-INCIDENT-002`
- Incident ID：`EXP-071-FORMAL-INCIDENT-002`
- 类型：Minor technical failure diagnostic
- 父实验：`EXP-071 / RQ-S4.2`
- 范围：定位原 formal attempt 1 的首个不满足正且有限条件的 CKA 分母门；不产生论文科学结果。

## 1. 父失败与边界

研究者保留原 `formal-attempt-1` 的 `run-claim.json`、`failure.json` 和私有
`input-manifest.json`。失败的 error SHA-256 为
`a31cc7801e29fbcef859a21a55bcf161c6390a6245e497b680fd33f3e1e0df8d`，
对应旧 runner 的 `Zero or non-finite CKA denominator`。原 attempt 保持 `Failed`。

本诊断只确定该门在原遍历顺序中的 condition、fold 和类别。研究者不得把诊断完成写成
EXP-071 完成、CKA 结果、表示漂移结论或恢复授权。原方法、tolerance、point、seed role、
aggregation 和 correlation 均保持不变；后续 recovery 需要单独登记。

## 2. 输入与顺序

配置以 path、bytes、mode、SHA-256 绑定原 active formal config、run claim、failure、
input manifest、原方法协议、旧安全 helpers、row contract 与 16 个矩阵。
诊断只核对原 config 的 metadata；不打开其中列出的 AP5/probe 文件。

共享输入 snapshot 只包含本诊断的 protocol、implementation、incident/source artifact records，
不包含 preflight 链。研究者单独校验 preflight 链。新 runner 可以复用 identity-bound 旧 runner
的安全 IO、hash、header、selective-JSON、flock 和 atomic-write helpers；新 verifier 可以复用
旧 independent verifier 的同类 helpers。新 verifier 不得导入新旧 runner，分母计算须独立实现。

原 3,360 rows 与 folds `0,1,2,3,4` 保持不变。每次只选 `fold_id == fold` 的 672 条
outer-heldout rows，按 ordinal 升序读取对应 fold 的 M3 矩阵。禁止读取该 M3 的 2,688 条
outer-train 表示。Row contract 只解码 `ordinal` 和 `fold_id`，不解码 `component_code`。

外层 condition 顺序：

```text
s42:H-1,H7,H15,H19,H20,H27,H31,H35,HF
s43:H19,H27,HF
s44:H19,H27,HF
```

每个 condition 的内层 fold 顺序为 `0,1,2,3,4`，最多 75 pairs。`pairs_examined`
从 1 计数，包含失败 pair。读取首个失败 pair 后停止，不继续后续 condition/fold。

## 3. 原算式与类别

矩阵以 `mmap_mode="r"` 打开，float32、C-order、non-writeable。Runner 与 verifier
把当前两个 `(672,2560)` slice 转为 C-order float64，并检查 shape、dtype 与 finite input。
不得计算 row norm、cosine、relative L2、CKA numerator、normalized CKA、max-abs drift 或 Spearman。

分母算式必须与原 runner 一致：

```python
Xc = X - np.mean(X, axis=0, dtype=np.float64)
Zc = Z - np.mean(Z, axis=0, dtype=np.float64)
K = Xc @ Xc.T
L = Zc @ Zc.T
norm_x = float(np.sum(K * K, dtype=np.float64))
norm_z = float(np.sum(L * L, dtype=np.float64))
denominator = float(np.sqrt(norm_x * norm_z))
```

不得改成分开开方、rescale、epsilon、z-score、unbiased CKA 或其他算式。
NumPy errstate 可以抑制 overflow/invalid warnings，不得改变运算值。

对 `norm_x`、`norm_z`、`denominator` 各自分类：

- `nonfinite`：NaN 或正负 infinity。
- `zero`：等于 0，包含负零。
- `finite_positive`：有限且大于 0。

有限负值触发 unexpected failure，不发布 localization。三个类别全为
`finite_positive` 时继续；否则记录首个 pair 并停止。75 pairs 全通过时报告
`failure_not_reproduced`，状态为 `Failed`，不完成 diagnostic。

## 4. 输出与生命周期

Runner：`static -> initialize -> diagnose`。
Verifier：`static-verify -> static-complete -> diagnostic-verify -> diagnostic-complete`。

Static 只核对 metadata、hash、header、mode、inventory、runtime 和 synthetic fixtures；
不读取 row-contract 或 representation values，也不创建 diagnostic formal roots。
Initialize 只创建 fresh roots、public run claim 与 private input manifest，不读取科学值。
Diagnose 只执行第 2、3 节。Independent verifier 按同一顺序重算首个失败类别。
Diagnostic completion 重放通过的 verification 后封口，不授权原实验 recovery。

Preflight public files：`static.json`、`static-verification.json`、`no-result-complete.json`；
private：`input-contract-manifest.json`。

Diagnostic public files：`run-claim.json`、`run.json`、`verification.json`、
`diagnostic-complete.json`；private：`input-manifest.json`、`diagnostic-manifest.json`。
配置固定 fresh namespace，所有文件 write-once，以同目录临时文件加 no-overwrite 原子发布。

Public localization 对象只含以下字段：

```json
{"condition":"<registered condition>","fold":0,"pairs_examined":1,
 "norm_x":"<category>","norm_z":"<category>","denominator":"<category>"}
```

Public envelope 可包含 artifact identities、status、access flags、resource accounting 和固定 claim
boundary。Public/private/log/exception text 均不得保存精确 norm、denominator、row ordinal、
rowwise value、表示数组或额外 drift metric。私有 manifest 只保存输入身份与同一 categorical
localization，无数组文件。意外失败只保存预定义 error code/type，不保存原始异常文本或数值。

## 5. 资源与终止

沿用 Python 3.10.20、NumPy 2.2.6、arm64 与五项 numeric thread env=1。
Runner/verifier wall ceiling 各 7,200 s，peak RSS 4 GiB，private output 8 MiB，
开始前 free disk 至少 1 GiB，concurrent worker=1，API cost=0。持有 persistent global 与
diagnostic-local flock；锁竞争即拒绝执行，不删除锁文件。

禁止 AP5/labels/component codes/component IDs/sample IDs/probabilities/predictions/text/model/
adapter/tokenizer/forward/validation/test/test-gate/EXP-069 smoke value access。
Identity、hash、mode、inventory、runtime、资源或访问边界漂移即停，保留 Failed 证据。
本诊断完成只支持“已定位原 CKA 分母门的首个失败 pair 与类别”。
