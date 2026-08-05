# GoEmotions Annotation Audit

本目录保存 `EXP-035` 的冻结协议、实现和公开审计产物。它回答一个数据问题：
官方 simplified train 中的 `neutral + emotion` 标签，究竟来自同一标注者共选，还是
多个标注者的不同判断经过 `>=2` 票阈值后合并。

## Verified Result

- 审计了冻结 train 中全部 1,396 条 `neutral + emotion` 样本。
- 1,396/1,396 条均为跨标注者聚合；同一标注者共选为 0/1,396。
- 5 位标注者样本为 1,352 条，4 位标注者样本为 44 条。
- neutral 获 2/3 票的样本分别为 1,249/147 条。
- 39/1,396 条至少含一票 `example_very_unclear`。
- 官方 `>=2` 票规则精确复现全部 simplified labels，错误为 0 条。
- 48 条冻结目的性样本中，6 条被编码为 `context_likely_needed`；该比例不能外推到
  全部数据。

结论是：当前异常标签结构首先应解释为标注聚合协议，而不是单个标注者认为文本同时
“中性且有情绪”。这不排除上下文不足或模型容量问题，但不再支持把直接重复训练当作
首选诊断。

## Files

- [`protocols/exp-035-neutral-cooccurrence-annotation-audit.md`](protocols/exp-035-neutral-cooccurrence-annotation-audit.md)：Major protocol 与冻结判定规则。
- [`../protocols/data-annotation-audit-v1.md`](../protocols/data-annotation-audit-v1.md)：原始标注获取、持久化和 test 边界。
- [`configs/exp-035-neutral-cooccurrence-annotation-audit.json`](configs/exp-035-neutral-cooccurrence-annotation-audit.json)：数据、来源、实现和抽样哈希。
- [`runs/exp-035-neutral-cooccurrence-annotation-audit/REPORT.md`](runs/exp-035-neutral-cooccurrence-annotation-audit/REPORT.md)：公开结论与边界。
- [`runs/exp-035-neutral-cooccurrence-annotation-audit/verification.json`](runs/exp-035-neutral-cooccurrence-annotation-audit/verification.json)：独立复算结果。

## Privacy And Split Boundary

官方原始标注以三个完整 CSV 对象发布，因此运行时流经全部对象字节；只有冻结 train
allowlist 命中的 6,936 行逐标注者记录被保存。非匹配记录不保留字段。原文、comment
ID、rater hash 和自由文本复核笔记均位于 gitignored `runs/**/private/`。

本实验没有获取或读取 simplified dev/test；`data/goemotions/official/test.tsv` 不存在。

## Verification

冻结 config SHA-256：

```text
babfa6094cc8e4300398cd209b8689b0a15039f530ffec47b391bdc0425f51bd
```

独立复算：

```bash
python3 experiments/goemotions/annotation-audit/verify_annotation_audit.py \
  --config experiments/goemotions/annotation-audit/configs/exp-035-neutral-cooccurrence-annotation-audit.json \
  --config-sha256 babfa6094cc8e4300398cd209b8689b0a15039f530ffec47b391bdc0425f51bd \
  --check
```

