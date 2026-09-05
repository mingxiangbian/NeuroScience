# SQMA-003：Classifier-Free Agent-Dev Preflight

日期：2026-09-04

层级：`Minor / capability and resource / no accuracy`

状态：`Registered / execution authorized for preflight only`

## 1. 目的

使用未经本项目LoRA调参的原始`Qwen/Qwen3-4B`，验证Evidence + Appraisal、Pragmatics Critic、Judge以及Single Agent在classifier-free条件下的Prompt渲染、JSON、evidence substring、采样稳定性、token、latency和本机资源。

本次不读取gold、不计算F1/Hamming，也不能证明Multi-Agent优于Single或Self-Consistency。

## 2. 输入与样本

只读SQMA-002 folds0–2的`gold-free-inference.jsonl`。禁止train-capable、consumer-gold、M1/M3/Router、fold3/4、validation/test。

选择规则：

1. 每个component只保留`source_ordinal`最小的一行；
2. 按`SHA256("SQMA-003-agent-dev-random-v1|" + component_id)`升序；
3. 取前32个component，不使用text内容、gold、label或任何模型结果；
4. rank 0–7为shakedown，8–31为locked；
5. locked中的前8行用于Single三采样稳定性与provisional token control。

## 3. 调用计划

- S3：32行 × 3 roles = 96 calls；
- Single pool：固定8行 × 3 calls = 24 calls，第一个call同时作为S1；
- provisional S2b：同8行另做3 calls = 24 calls，只测量最坏资源与token，不产生正式方法结果；
- physical hard cap：144 calls。

所有调用共享Qwen revision、MLX BF16、`thinking=false`、temperature 0.6、top-p 0.95、top-k 20。seed取`SHA256(namespace|system_id|sample_id|role_id|call_index)`前4字节。无Qwen repair或工具调用。

## 4. Locked通过门

- 全部planned call有终态、seed、prefill/generated token和latency记录；
- raw JSON + v2 semantic validator overall至少98%，每个角色至少95%；
- technical fallback最多1个locked S3 row；out-of-ontology=0；
- 所有声明evidence均为analysis_text exact substring；
- prompt超过4096或命中max-new-token cap即失败；
- 8行三采样Single的mean modal exact-label-set agreement至少0.85；
- Prompt/schema/model/runtime/input hash无漂移，无gold/网络/外部工具访问。

## 5. 资源

- 单重模型、顺序执行；calls不超过144；generated tokens不超过58,368；
- wall不超过4小时；private output不超过512 MiB；
- MLX peak不超过10 GB，RSS不超过12 GiB；二者不相加；
- critical-memory、OOM、kill、orphan均为0。

## 6. 输出与下一门

Private保存选择manifest和逐call raw/parsed输出，不含gold。Public只含aggregate schema/stability/token/latency/resource与access。

通过后，根据locked结果冻结完整672-row Agent-Tune comparison的seed、token ceiling、S2b调用数、wall/storage预算。若保守wall投影超过48小时，或S2b无法容纳至少两个完整Single calls，则不进入Tune。

SQMA-003通过后不自动证明准确率或读取fold3。
