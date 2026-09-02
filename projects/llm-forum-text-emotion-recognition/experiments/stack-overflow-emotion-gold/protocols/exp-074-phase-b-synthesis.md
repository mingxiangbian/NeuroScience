# EXP-074：Phase B 只读综合分析

- Experiment ID：`EXP-074`
- Date：`2026-08-30`
- Tier：`Major read-only synthesis`
- RQ：`RQ-S4`
- Parent：Phase B decision、EXP-070、EXP-072、EXP-075
- Status：方法登记；等待 EXP-075 与 EXP-072 Verified。

## 综合问题与来源

本实验汇总线性可分性、几何漂移与 LoRA 功能消融，分别回答表征收益是否跨训练 seed
复现，以及 Attention/MLP 功能依赖是否稳定。它不新增实验、推理、阈值或结果选择。

只读取已经独立验证的 public aggregate JSON 及其 verification/completion。
输入为 EXP-070 probe aggregates、EXP-075 geometry aggregates、EXP-072 ablation scores；
config 绑定每个来源的 path、bytes、mode、SHA-256。数据范围仍为同一 DATA-SO-TASK-V1
train 的 3,360-row outer-heldout OOF，不把它写成 independent-data validation。
不读取 private 数组、checkpoint、原文、labels、validation 或 test。

EXP-071 原运行 Failed 与 Incident 002 Complete 均保留。用户确认以 post-diagnostic
EXP-075 填补几何证据缺口；本实验不会将其改写为原 EXP-071 预注册成功。

## 两个独立结论

Representation state 复算 Phase B 原规则：seeds 43/44 各自必须在 H27 与 HF 同时满足
five-label Macro-AP delta>0 且 paired duplicate-component bootstrap 95% 下界>0。
2/2、1/2、0/2 pass 分别对应 `Representation effect replicated`、
`Representation effect seed-sensitive`、`No replicated representation effect`。
Seed-42 discovery、H19 sanity、F1 和 geometry 不投票。

Functional dependency 只使用 EXP-072 seeds 43/44 的 five-label Macro-F1。
定义 drop(A)=Full-A，D=drop(A2 Attention-off)-drop(A3 MLP-off)。两 seed 的 D 都
>=0.01 时为 `Stable Attention-dominant dependency`；都<=-0.01 时为
`Stable MLP-dominant dependency`；其余为 `Both contribute / no stable dominance`。
不新增显著性门、最佳 seed 或最优 ablation 选择。

Geometry 只作描述，保留全部 registered points 与 fold aggregates。EXP-075 CKA、
fold summary 或九点 Spearman 为 null 时，报告原 reason，不填补、不删点重算。
HF 是 final-RMSNorm interface；不把它当成普通的相邻 residual layer。

## 输出与验证

保存 Major `run.json`、`stdout.log`、含两种 state 及输入引用的综合结果 JSON，和独立
`verification.json`。正式输出 root 必须全新；失败不覆盖、不自动重试。
Verifier 独立核对来源状态/hash、复算两种 state、确认汇总数字与来源相同，检查
EXP-071 Failed、EXP-075 post-diagnostic 与未定义项的表述没有丢失。

研究报告使用项目规定的 Markdown，放在 Git-ignored private reports 目录。报告包含：
结论摘要；样本、指标与模型定义；probe、geometry、ablation 三组证据；实验设计和独立
验证；失败与不确定性；下一步及仍未回答的问题。使用精确数值表便于论文引用，不新增
不能改变结论的可视化。报告只纳入已验证结果；方法和工件链接支持复核。

只有 EXP-069/070 完成、EXP-075 和 EXP-072 Verified、综合验证 Passed 后才声明 Phase B
最低完成集完成。可选 EXP-073 未执行及 context/C2 暂停须单列，不能隐去或算作已完成。

## 资源和停止条件

最多一次 synthesis 与一次 independent verification，每个最多 3,600 秒，单 CPU
process，RSS 上限 1 GiB，输出上限 32 MiB，API cost=0，不运行模型。
来源未验证、hash 漂移、指标缺失、无法唯一分配 state、private/test 越界或复算不一致
均停止；不能为了写出完整报告替换来源或放宽判据。

本实验支持 same-train cross-training-seed representation replication 与最终联合训练
模型的 inference-time functional dependency。线性 probe、几何相关与消融分别测量
不同性质；综合结果不证明模型或人类的情绪机制，不证明独立数据泛化或部署效率。
