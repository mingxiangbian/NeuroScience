# 台账 · Ledger

> 结算制学习系统的唯一账本。规则见 [ai-professional-roadmap.md](ai-professional-roadmap.md) 的"运行系统"。
> 数字只涨不跌。空窗不记债。没有日期义务——记录日期只是为了日后校准真实节奏。

## 当前状态

- **活动单元**：U1 修掩码
- **已结算**：0 个
- **玩耍券**：0 张

## 断点（下次从这里开始）

> 每次 session 结束写三行：做到哪了 / 下一步第一个动作 / 有没有墙。也可以直接告诉 Claude，由它写。

- U1 未开始。启动动作：打开 `Transformer-Decoder-Toy-Project/model.py` 第 48 行，把 `is_causal=False` 改为 `True`（删掉那行错误注释），跑 `python train.py`，保存 loss 曲线。

## 结算记录

| # | 日期 | 单元 | 产物 | sessions |
| --- | --- | --- | --- | --- |

## 撞墙记录

> 三行墙格式：在做什么 / 卡在哪 / 试过什么。撞墙记录可升级为失败分析笔记，照常结算一个单元。
