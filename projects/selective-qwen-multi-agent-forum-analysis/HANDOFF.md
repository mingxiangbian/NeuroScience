# Selective Qwen Multi-Agent Forum Analysis · HANDOFF

日期：2026-09-05

## 当前交接

先读[当前方案](docs/current-plan.md)。用户已决定同一主机 **2×RTX PRO 6000 96GB**；拟用 Qwen3.8-27B 主 Agent 与 Qwen3-8B、一个 8–12B 异构专家，按 GPU 0 主模型、GPU 1 专家、BF16、无项目 LoRA 准备。

云实例尚未创建，具体 GPU 版本/主机、模型 revision、第二专家、thinking 模式及成本预算尚未冻结。当前继续采用 [classifier-free 路线](protocols/dec-sqma-classifier-free-v1.md)；新云端阶段需要独立的环境与模型合同，旧 MLX 预检不构成其通过证据。

## 已验证、失败与未执行状态

| 实验 | 状态与证据边界 |
| --- | --- |
| SQMA-001 | readiness preflight 完成；[verification attempt 3](runs/sqma-001-strict-base-readiness-preflight/attempt-1/verification.json) 通过20/20检查，原 runner 未重跑 |
| SQMA-002 | Dev scoped-input materialization 完成并[验证通过](runs/sqma-002-dev-scoped-input/attempt-1/verification.json)；只密封 folds 0–2 的2,016行 |
| SQMA-003 attempts 1–2 | 均 Failed；[attempt 1](runs/sqma-003-classifier-free-agent-preflight/attempt-1/run.json) 与 [attempt 2](runs/sqma-003-classifier-free-agent-preflight/attempt-2/run.json) 的格式改善未越过冻结能力门 |
| SQMA-006 | [Failed](runs/sqma-006-d1-canonical-output-preflight/attempt-1/run.json)；canonicalization 后 overall、per-role 与 fallback 门仍失败 |
| SQMA-007 | Complete / [verification Passed](runs/sqma-007-dev-c1-visible-judge-shakedown/attempt-1/verification.json)；仅支持16个 visible 样本的固定槽位合同 |
| SQMA-008 | [Failed](runs/sqma-008-dev-c2-locked-acceptance/attempt-1/run.json)；24个 locked 样本中1个非法引用 ID，零容忍合同门失败 |
| SQMA-004/005 | 未执行；输入 materialization 与 matched comparison 的静态代码不构成方法结果 |
| SQMA-009 | 静态准备，继续暂停；[config](configs/sqma-009-judge-v3-restricted-choice-backend-parity.json) 含占位项且执行开关为 false，无 run |
| 新双 GPU 阶段 | 未运行；尚无新模型预检或正式多 Agent 准确率比较 |

SQMA-003、006、008 均没有通过的 verification 或 complete；不能把 runner 完成写成实验通过。保留这些失败终态，不自动重试旧实验，不查看 locked raw，也不据此修改 Prompt。

完整数值、incident、旧设计与公开证据索引保存在[历史归档](docs/history.md)，该文档含详细结果，按用户要求仅本地保留并被Git忽略。

## 下一动作

1. 整理云端输入清单，核对代码、无 gold 输入、scorer 侧 gold 和原始来源身份；private 迁移需单独核验。
2. 冻结候选模型 revision、第二专家、BF16、thinking 模式、固定调用图、输出合同和成本口径，保留强 Single 与 Self-Consistency 对照。
3. 租机后验明两卡型号、环境和资源，在选样与 visible/locked 边界冻结后做32条 Agent-Dev 预检；该预检不评分 gold。
4. 技术预检通过后进入 Agent-Tune matched comparison；有稳定协作收益才选择触发策略，并在全部 Confirm 比较与预算冻结后运行。

网站接入置于方法证据之后；外部金标泛化与 context/C2 继续暂停。后续顺序与研究边界详见[当前方案第10节](docs/current-plan.md#10-后续顺序)。

## 工作区与 private

公开文档、代码、配置和 public run 已整合到 main 与主目录 `/Users/phoenix/Assistant/NeuroScience`。用户删除的 `projects/uestc-fyp-topics-2026-2027/` 三个旧选题文件保持删除，记录在提交 `852406a`。

当前有效 private 副本仍在 `/Users/phoenix/.codex/worktrees/72d6/NeuroScience/projects/selective-qwen-multi-agent-forum-analysis/private/`，被 Git 忽略。公开内容的合并不代表 private 已迁移或备份；迁移并验证前保留72d6工作区。

本轮目录整理将 README 与 HANDOFF 的旧4B历史正文移入 `docs/history.md`。configs、protocols、prompts、schemas、scripts、tests、runs、incidents 与 private 均保持原位置；历史来源仍可按原路径与哈希追溯。
