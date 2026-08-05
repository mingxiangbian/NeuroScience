# DATA-FCTX-PR-V1: Forum Context Source and Parent Recovery Gate

Registration date: 2026-08-04 (Asia/Shanghai)

## Registration

- Protocol ID: `DATA-FCTX-PR-V1`
- Status: `CLOSED_CORPUS_AUDIT_COMPLETE_EXTERNAL_RECOVERY_BLOCKED`
- Stage: source, compliance and closed-corpus preflight
- Parent-text access: `GOOGLE_OFFICIAL_RELEASE_ONLY`
- Direct Reddit recovery decision: `NO-GO`
- GoEmotions test access in this preflight: `PROHIBITED_AND_NOT_USED`

### Amendment: 2026-08-04

上一版把“使用 Google 已发布的 GoEmotions raw dataset”和“重新访问 Reddit 获取缺失
parent”合并成同一个阻塞项，边界过严。用户确认本阶段只使用 Google 官方发布内容。
因此：

- 下载官方三份 raw CSV 并在发布语料内部做 `id -> parent_id -> id` self-join 改为
  `GO`；
- 任何 Reddit API、网页抓取或第三方 archive 补齐仍为 `NO-GO`；
- 找不到的 parent 必须保留为 missing，不能从外部回填。

## 1. Purpose

本协议决定下一阶段能否合法、稳定地构造父回复上下文。它先回答数据来源与授权问题，
再允许恢复率和缺失偏差 pilot；不能因为技术上存在 `comment_id` 或 `parent_id` 就默认
可以抓取、保存或训练。

本协议不等于：

- 已获准访问 Reddit 研究数据。
- 已获准把 closed-corpus 中找到的 parent text 用于训练或标注。
- 已决定使用 GoEmotions context augmentation 作为最终数据路线。
- 已冻结 parent recovery pilot 的样本量或定量通过阈值。
- 已授权人工标注、模型训练或新 test 访问。

## 2. Evidence Reviewed

### 2.1 GoEmotions official release

官方 GoEmotions README 说明：

- filtered TSV 的第三列是 comment `id`；
- raw release 包含 `id`、`subreddit`、`link_id`、`parent_id` 和
  `created_utc` 等字段；
- raw release 本身不承诺提供 parent comment text；
- Google Research 仓库声明仓库内 datasets 使用 CC BY 4.0。

Sources:

- Pinned project revision:
  <https://github.com/google-research/google-research/blob/8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0/goemotions/README.md>
- Repository license statement:
  <https://github.com/google-research/google-research>
- Paper:
  <https://aclanthology.org/2020.acl-main.372/>

论文还说明 GoEmotions 来源评论覆盖 Reddit 2005 年至 2019 年 1 月。该时间范围是判断
当前官方研究接口能否覆盖原始 parent 的关键条件。

### 2.2 Current Reddit research boundary

以下是 2026-08-04 查阅的 Reddit 官方页面：

- Developer Platform & Accessing Reddit Data:
  <https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data>
- Reddit for Researchers Program:
  <https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program>
- Responsible Builder Policy:
  <https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy>
- Deleted-data handling:
  <https://support.reddithelp.com/hc/en-us/articles/24656943463828-What-happens-when-I-delete-my-data>

这些来源当前明确：

- 学术研究使用 Reddit 数据的官方授权路径是 Reddit for Researchers（RFR）。
- RFR 申请需要高校隶属、官方邮箱、机构 sponsor，以及伦理审查批准或 exemption。
- 使用 Reddit 内容训练 machine-learning/AI model 需要 Reddit 的明确同意。
- 研究数据不得再分发，且必须处理内容删除和项目结束后的保留/删除要求。
- RFR 当前描述的数据覆盖最近五年历史并有六个月延迟，comments 包含 post 和 parent
  IDs。

### 2.3 Inference and unresolved conflict

**Assistant synthesis:** GoEmotions 原始评论截止于 2019 年 1 月，而 RFR 当前公开说明
只覆盖最近五年历史。因此，RFR 的标准数据范围没有说明能够覆盖 GoEmotions 原始
parent。除非 Reddit 书面确认可提供该历史范围，否则不能假定 RFR 可以完成恢复。

Google 发布数据的 CC BY 4.0 声明与 Reddit 当前研究访问政策属于两个不同层面的
来源条件。本协议不作法律裁决。本阶段把 Google 官方 release 作为封闭数据源，只做
其内部已有记录的 self-join；不向 Reddit 或其他来源请求任何新增内容。

## 3. Local Metadata-Only Preflight

本次只读取现有公开 manifest，没有读取 GoEmotions test 内容，也没有打印或写入任何
comment ID。

| Split | Rows | Unique comment IDs | Duplicate IDs |
| --- | ---: | ---: | ---: |
| train | 43,410 | 43,410 | 0 |
| dev | 5,426 | 5,426 | 0 |

train/dev comment ID overlap 为 0，因此有 48,836 个互异的 train/dev IDs 可作为
closed-corpus join key。后续 `DATA-FCTX-CJ-V1` 已完成实际关联，结果见下一节。

机器可读记录：
[`../preflight/local-filtered-id-inventory.json`](../preflight/local-filtered-id-inventory.json)。

### Closed-corpus audit result

`DATA-FCTX-CJ-V1` 对三份官方 raw CSV 执行了 train/dev 自连接。48,836 个 targets 全部
匹配 metadata 且均有 `parent_id`，但只有 157 个 parent comments 在 raw release 内有
文本；48,679 个缺失 parent text，缺失率为 99.6785%。其中 19,987 个 parent 是
submission，28,692 个是 raw release 未收录的 comment。独立 SQLite 复算零差异。

Raw release 未分 split，因此这 157 个 parent 只证明文本可用性，不自动满足 train/dev/test
泄漏约束，也未获准进入训练。

## 4. Allowed Actions Under This Protocol

在当前 amendment 下允许：

- 阅读现有本地 manifest、公开协议和不含文本/ID 的统计。
- 从 GoEmotions README 指定的 Google Storage URLs 下载三份官方 raw CSV。
- 将 raw CSV 保存在 `data/goemotions/official/full_dataset/`，保持 gitignored。
- 对 train/dev 做闭集 `id -> parent_id -> id` join，并只公开聚合统计、文件哈希和代码。
- 准备导师确认、伦理审查或 exemption、RFR 申请材料。
- 向 Reddit 书面询问历史覆盖、parent/target 使用、AI/ML training、模型保留和发表边界。
- 调研具有明确研究和模型训练许可的替代上下文数据集，但不得静默切换主数据源。
- 在本协议中记录新的官方书面证据。

## 5. Prohibited Actions Until Approval

- 不调用 Reddit Data API、网页端点或 RFR 数据。
- 不抓取 Reddit 页面。
- 不使用 Pushshift、Reddit dump、Common Crawl 或其他第三方存档恢复 parent。
- 不从 Google release 之外补齐缺失 parent。
- 不把 parent text、用户名、permalink 或可逆身份映射写入 Git 或公开产物。
- 不把 Reddit 文本发送给外部 LLM API。
- 不用任何新增 Reddit 文本训练 BERT、Qwen、LoRA、probe 或 SAE。
- 不读取已消费的 GoEmotions test 来选择本阶段样本、规则、模型或阈值。

## 6. Authorization Gates

以下授权门只适用于将来从 Google release 之外恢复缺失 parent。当前 closed-corpus
self-join 使用单独的
[`DATA-FCTX-CJ-V1`](data-closed-corpus-parent-coverage-v1.md)，不等待这些外部访问门。

### Gate A: Institutional sponsorship and ethics

- 导师或其他合格 sponsor 同意使用机构邮箱支持申请。
- 学校伦理审查给出批准或书面 exemption。
- 明确本科生、导师和其他参与者谁可以接触 source data。

### Gate B: Reddit project approval

书面批准必须覆盖：

- 研究目的和具体数据范围。
- target 与 parent comment 的访问。
- 用数据训练或适配 BERT/Qwen/LoRA 等 ML/AI models。
- 本地导出、保存期限、删除同步和项目结束后的销毁方式。
- 模型 checkpoint、派生特征、统计和论文结果能否保留或展示。
- 论文、答辩、GitHub 和 demo 的公开边界。

仅获得普通 developer/API 凭据不构成本门通过。

### Gate C: Historical coverage

Reddit 或获批数据源必须明确确认能覆盖 GoEmotions 所在的 2005--2019 年 1 月范围，
或提供能够合法关联相同 comment IDs 的历史数据。仅凭 RFR 当前“五年历史”的公开说明，
本门不通过。

### Gate D: Source and deletion handling

- 数据源必须可追溯且与批准范围一致。
- deleted/removed 内容不得被恢复或继续使用。
- 必须定义定期删除核查、撤回处理及项目结束后的数据销毁。
- raw text 与 ID 只能进入 gitignored、访问受限的本地目录。

### Gate E: Pilot protocol freeze

完成 A--D 后，另行冻结：

- 只从 train 候选中抽样的样本量和随机种子。
- stratification 与代表性抽样规则。
- `recovered`、`deleted`、`removed`、`missing_parent`、`unsupported_type` 和
  `access_error` 的确定性状态定义。
- 最低恢复率、最大系统性偏差和 API/查询成本阈值。
- 允许保存的字段、哈希和聚合统计。

在这些定量规则冻结前，不执行 recovery pilot。

## 7. Future Pilot Measurements

如果全部授权门通过，pilot 至少报告：

- comment 到 parent ID 的 join coverage。
- parent text 的合法可用率。
- deleted、removed、missing 和 unsupported parent 的比例。
- recovered 与 unrecovered target 在 emotion labels、文本长度、subreddit 和时间上的
  差异。
- parent 类型、重复 thread 和 cross-split thread leakage 风险。
- 数据访问次数、失败率、延迟和人工处理成本。

恢复率本身不足以通过。若 missingness 与 emotion、subreddit、文本长度或时间明显
相关，必须把 Dataset A 降级为受偏样本研究或停止该路线。

## 8. Current Go/No-Go Decision

| Action | Decision | Reason |
| --- | --- | --- |
| 使用现有 train/dev manifest 做无文本统计 | `GO` | 不增加 Reddit 数据访问 |
| 准备导师、伦理和 RFR 材料 | `GO` | 当前唯一可推进的授权路径 |
| 直接调用 Reddit API 恢复 GoEmotions parents | `NO-GO` | 未获 RFR 和 AI-training 明确批准 |
| 使用抓取或第三方 archive 恢复 parents | `NO-GO` | 当前官方政策不允许绕开 RFR |
| 下载 Google 官方 raw CSV 并执行闭集 parent join | `GO` | 不访问 Google release 之外的数据 |
| 用闭集找到的 parent 构建候选对 | `DIAGNOSTIC_ONLY` | 覆盖率仅 0.3215%，且尚未排除 split leakage |
| 构建 Dataset A 或启动标注/训练 | `BLOCKED` | 需先审阅闭集覆盖率并冻结新数据协议 |

## 9. Next Decision

Google release 内部的 train/dev parent coverage audit 已完成，0.3215% 的文本可用率
不足以支持计划中的大规模 Dataset A。下一步不应直接训练，而应在“申请外部授权恢复
历史 parent”与“改用具有明确上下文和训练许可的数据集”之间做来源决策。157 个闭集
候选对只可用于后续另行登记的诊断，不得代表总体结果。
