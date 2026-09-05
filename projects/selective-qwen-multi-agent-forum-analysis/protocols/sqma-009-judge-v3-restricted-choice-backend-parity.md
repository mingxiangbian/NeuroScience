# SQMA-009：JudgeV3 restricted-choice visible backend/parity preflight

## 1. 状态与目的

- Experiment：`SQMA-009`
- Stage：`judge-v3-restricted-choice-visible-backend-parity`
- 当前状态：`StaticDesignAwaitingImplementation`
- 执行授权：`false`
- 数据层级：复用SQMA-007的16个`visible_shakedown` rows，不使用新的locked rows

SQMA-008在24个C2 locked rows中出现1个illegal evidence ID，零容忍合同门因此失败。该结果不授权查看失败row或根据locked输出修Prompt。SQMA-009改为测试一个新的JudgeV3 restricted-choice candidate scorer：每次调用只能在`NONE`与当前Evidence提供的最多3个合法ID之间选择，程序再将六个label calls组装为固定slots。

本实验只验证backend、mask、token seal、terminal contract、assembly与成本记录。它不评分准确率，不比较角色价值，也不恢复或改写SQMA-008终态。

## 2. 与JudgeV2的关系

JudgeV3不是JudgeV2的verification recovery。JudgeV2用一次生成输出六个slots；JudgeV3对每个label分别进行一次受限单token选择，因此每row有6次Judge model calls。Prompt、输出合同、解码方式与计算量均发生变化，必须登记为新实验。

SQMA-009只决定该backend candidate是否技术可用。即使通过，也不能直接替代未来matched comparison中的one-call Judge。任何性能比较必须另行登记一个six-call control，匹配JudgeV3的6次prefill、6次model calls和相应token/latency成本；该control不属于SQMA-009。

## 3. C1 sealed input复用

输入固定为SQMA-007 attempt-1的sealed private artifacts：

- `selection.json`：4,353 bytes，SHA-256 `d06f8528a931f3d2c0ad86a2828e6c111f8f0962c5fdb8fbf6792af18ed5191d`；
- `calls.jsonl`：78,029 bytes，SHA-256 `876ad6c9fb5282a90b713e5f67113bfad5eb3667ce6498ddc36883c1212109f5`；
- `private-manifest.json`：1,723 bytes，SHA-256 `bdaba632deaf7b5731a96685faaa56f4e3be90a9ef806352c7fbbc11462d441e`。

这些identity来自SQMA-007已验证public run；正式consumer仍须在打开private文件前核对path、bytes、SHA-256、0600 mode、private root 0700以及public run/verification/completion identity。

Consumer只复算并复用16个C1 rows的`analysis_text`、validated Evidence和validated Critic。Evidence/Critic raw outputs必须由hash-pinned v3 validator重新验证；SQMA-009不生成新的Evidence或Critic调用。C1 Judge raw output、slots与derived labels不得进入JudgeV3 Prompt、candidate mapping或assembly。进程可能为核对sealed JSONL而解码C1 visible call records，但不得把row文本、raw output、IDs或choice写入public工件。

当前skeleton不授权读取C1 private。gold、classifier、fold 3/4、validation、test与SQMA-008 locked private均禁止访问。

## 4. Option mapping与token seal

每个label call的候选symbol固定为：

| Symbol | Choice |
|---|---|
| `A` | `NONE` |
| `B` | `allowed_evidence_ids[0]`，若存在 |
| `C` | `allowed_evidence_ids[1]`，若存在 |
| `D` | `allowed_evidence_ids[2]`，若存在 |

Evidence spans为0、1、2或3个时，当前mask分别只允许`A`、`A/B`、`A/B/C`或`A/B/C/D`。未映射的symbol必须被mask。

Token seal绑定冻结模型目录中的：

- `tokenizer.json`：11,422,650 bytes，SHA-256 `be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506`；
- `chat_template.jinja`：4,168 bytes，SHA-256 `a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8`。

Runtime必须重新执行`tokenizer.encode(symbol, add_special_tokens=false)`，不得信任config、旧run或public记录中的token IDs。`A/B/C/D`各自必须编码为唯一的单一integer token；decode必须精确还原原symbol，且四个token均不得属于EOS集合。Runtime seal必须在任何Judge generation前写入private并由independent verifier重放。

## 5. 96-call backend contract

16 rows按固定label顺序`love, joy, surprise, anger, sadness, fear`执行6次调用，共96次physical Judge calls。每次context只包含：

- `analysis_text`；
- frozen ontology；
- validated C1 Evidence；
- validated C1 Critic；
- 当前`target_label`；
- `allowed_evidence_ids`；
- 当前`option_mapping`。

Generation namespace固定为`SQMA-009-judge-v3-restricted-choice-v1`；seed material为`namespace|sample_id|target_label|call_index`。虽然greedy choice不依赖随机采样，该identity仍必须逐call记录和重放。

每个label call必须使用：

- 同一冻结`Qwen/Qwen3-4B` revision与MLX BF16模型，不加载adapter；
- `thinking=false`；
- `temperature=0`与greedy sampler；
- `stream_generate(..., max_tokens=1)`；
- `prompt_cache=null`；
- 一个为该call新建的stateless allowed-token mask processor。

Mask processor只保留当前mapping中的token logits，并mask EOS与全部其他vocabulary tokens。Processor不得复用上一次call的候选集合，也不得根据tokens history改变mask。Telemetry可以在processor外部记录调用次数，但计数不得影响allowed set、logits或choice。

`mlx-lm 0.31.3`在`max_tokens=1`时会返回一个terminal `GenerationResponse`，同时可能为了内部未使用的next-token lookahead多次调用processor。Decision source必须是terminal response的integer `token`，不是`response.text`。因此本实验不声称每个label只有一次model forward。

## 6. Deterministic assembly

每row的六个terminal tokens按固定label顺序组装：

- `A`生成空slot；
- `B/C/D`生成只含对应合法Evidence ID的单元素integer array。

Assembly必须产生且只产生`love, joy, surprise, anger, sadness, fear`六个slots；derived labels按同一固定顺序取非空slots。Assembly不得增加或删除choice、转换类型、替换ID、跨label移动ID、读取旧JudgeV2结果或依据文本做语义修复。按此合同，非法Evidence ID不应可构造，但仍须由独立validator逐row验证。

## 7. Technical gate

通过必须同时满足：

- C1 public与sealed private identities全部匹配，16个row及其Evidence/Critic均可确定性重放；
- runtime token seal有效，四个symbol均为唯一单token、round-trip精确且非EOS；
- 96/96 planned calls terminal，且每个row恰有6个labels各1次；
- 96/96 calls各调用一次`stream_generate`；
- 96/96 calls各返回1个response；
- 96/96 calls的`generation_tokens=1`；
- 96/96 calls的`finish_reason="length"`；此处是预期terminal，不计作旧合同中的token-cap failure；
- selected token escape：0；
- selected EOS token：0；
- post-mask dead-end或非有限allowed logits：0；
- unhandled failure：0；
- 16/16 six-label assemblies合同合法；
- illegal Evidence IDs constructed：0；
- semantic repair events：0；
- wall、RSS、MLX peak、generated-token、output-byte、disk与process stability均在冻结边界内。

任何一项失败即停止，不写`complete.json`，也不自动扩大样本、访问SQMA-008 locked raw或启动正式比较。

## 8. Report-only diagnostics

以下指标必须记录，但不参与本次pass/fail：

- processor实际invocation总数与per-call分布；
- MLX mask与pure-Python reference mask的parity诊断；
- terminal token到candidate mapping及assembly的parity诊断；
- 每次prefill tokens、固定96个generated tokens、latency、wall与peak resources；
- MLX内部unused lookahead造成的额外计算边界。

Report-only不等于可以省略。Parity异常必须公开保留为诊断，但只有预登记的escape、EOS、dead-end、unhandled或assembly gate触发失败。Processor invocation count不得被误写为model forward次数。

## 9. 资源与输出

Preflight上限冻结为：

- physical calls：96；
- generated tokens：96；
- wall：7,200 seconds；
- process RSS：12,884,901,888 bytes；
- MLX peak：10,000,000,000 bytes；
- private output：268,435,456 bytes；
- public output：16,777,216 bytes；
- run前free disk：至少21,474,836,480 bytes；
- critical-memory、OOM/kill与orphan process：均为0。

计划private inventory：`token-seal.json`、`calls.jsonl`、`assemblies.jsonl`、`private-manifest.json`。计划public inventory：`run-claim.json`、`run.json`、`verification.json`、`complete.json`。Public只允许aggregates、identity、资源、gate与report-only diagnostics，不得包含row IDs、文本、Evidence/Critic内容、token IDs、per-label choices或assembled slots。

## 10. 证据与公平性边界

SQMA-009复用已查看的C1 visible rows，只能说明restricted-choice backend在这16个样本上的技术行为。即使96/96与16/16通过，也不证明准确率、Evidence相关性、Critic因果作用、总体合同可靠率、Agent-Tune、Agent-Confirm或跨论坛泛化。

JudgeV3的非法ID不可构造来自候选mask和deterministic assembly，不是模型自由生成能力提高。与JudgeV2相比，JudgeV3使用6倍Judge calls并重复6次prefill；在没有future six-call control前，不得把两者的有效率、成本或预测结果解释为公平方法比较。

## 11. 失败与下一门

Runner、token seal、mask、terminal、assembly、resource或independent replay任一硬门失败，SQMA-009终态为`Failed`并登记append-only incident。失败不自动触发Prompt修订、backend替换、retry、SQMA-010、six-call control或formal comparison。

只有producer gate与independent verification均通过时才可创建completion。即使通过，下一步也只是决定是否登记新的JudgeV3 locked acceptance或six-call control；两者都需新的协议与授权。

## 12. 当前静态边界

当前只冻结协议、v5 Prompt/schema/validator/tests、v3/v4 lineage、C1 public/sealed artifact identities、tokenizer/chat-template/source seals、call plan、gate、report-only metrics、资源与输出计划。SQMA-009 runner、independent verifier及其tests尚未实现；config必须保留placeholder且所有authorization为`false`。本阶段不得打开C1 private、加载模型或执行generation。
