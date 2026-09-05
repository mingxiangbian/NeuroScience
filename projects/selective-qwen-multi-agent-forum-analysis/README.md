# Selective Qwen Multi-Agent Forum Analysis

更新：2026-09-05

独立研究项目，面向英语技术论坛的六标签情绪识别，研究强主 Agent 与小模型专家的协作收益、错误互补性和选择性调用成本。当前采用 classifier-free 路线，原项目 M1/M3/Router 不进入 Agent 输入。

## 当前方案

| 项目 | 决定或状态 |
| --- | --- |
| 硬件 | 同一主机 2×NVIDIA RTX PRO 6000 96GB；已决定选型，尚未租用或验机 |
| 主 Agent / Judge | Qwen3.8-27B 优先候选，计划驻留 GPU 0 |
| 专家 | Qwen3-8B 与一个待选 8–12B 异构模型，计划驻留 GPU 1 |
| 推理 | BF16 为默认准备方案，不加载项目 LoRA；模型 revision、第二专家、thinking 模式与预算待冻结 |
| 方法比较 | 强 Single Agent、Self-Consistency、同构多角色与异构协作；有稳定协作收益后再进入选择性调用 |
| 当前进度 | 4B 格式预检历史已封存；新模型组合尚未运行，正式 matched comparison 尚未执行 |

完整设计、数据划分、指标和后续顺序见[当前多智能体方案与硬件决策](docs/current-plan.md)。现有结果只能支持相应格式与运行结论，尚不能支持多 Agent 准确率增益。

## 关键入口

- [当前交接与实验状态](HANDOFF.md)：继续工作时先读。
- [4B 阶段方案与实验历史](docs/history.md)：原 README、HANDOFF 历史正文及完整证据索引；含详细结果，仅本地保留，Git忽略。
- [Classifier-free 决策](protocols/dec-sqma-classifier-free-v1.md)：当前路线与旧分类器辅助路线的边界。
- [D0 数据与证据合同](docs/d0-data-evidence-contract.md)：既有 component-disjoint 划分与数据身份；旧重训步骤不自动恢复。

## 目录职责

| 目录 | 内容 |
| --- | --- |
| [docs/](docs/) | 当前方案、数据合同和历史归档 |
| [protocols/](protocols/) · [configs/](configs/) | 实验协议、冻结配置和依赖身份 |
| [prompts/](prompts/) · [schemas/](schemas/) | 各版本角色 Prompt 与输出合同 |
| [scripts/](scripts/) · [tests/](tests/) | runner、scorer、独立 verifier 与合成测试 |
| [runs/](runs/) · [incidents/](incidents/) | 公开运行终态、验证记录和失败登记 |
| `private/` | 被 Git 忽略的受限输入与运行工件，独立迁移和备份 |

已封存工件保持原路径；新阶段通过新的协议与实验编号区分。目录整理只压缩入口文档，不移动历史配置或运行文件。

公开内容已整合到 main 和主目录。当前有效 private 副本仍位于 `/Users/phoenix/.codex/worktrees/72d6/NeuroScience/projects/selective-qwen-multi-agent-forum-analysis/private/`；Git 合并不包含这些数据。在另行迁移并核验前保留该 worktree。
