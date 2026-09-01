# EXP-080：Discourse Formal Topic Run

Date：2026-08-31；Tier：Minor；RQ-S3 / Phase C.1。

本次继承EXP-078来源与采样合同，唯一方法变化是以EXP-079新有界验收作为安全依赖，
不用原EXP-077的失败门，也不修改或假称完成EXP-078。只做一次正式采集与Research任务。

## 前提与固定任务

必须同时核对EXP-079 run=Completed、verification=Passed、exp079_complete=true及
operational_state=safe-to-continue，并绑定终态/plan真实hash。否则不创建正式job。
开始前采用EXP-079相同安静窗口；运行中保持相同system/process监测和资源停止条件。

来源：discuss.python.org / Python Help category7；最新创建的公开非置顶topic前缀，
topic内post_number升序。最多100topic/400普通公开post，成功范围300–400条。
原生raw逐字送模型，来源/父帖/创建时间/hash/署名/CC BY-NC-SA3.0及不可得/截断项记录不变。
只做非商业本地研究，无任意URL/站内搜索/登录绕过；403/429停止不重试，不换站点补样本。
最多160来源请求/900秒、请求结束后至少间隔1秒、wire/expanded各2MiB、每文本64KiB。

Research mode、max_qwen_calls500、audit0、seed42；原EXP-066模型、prompt、阈值及router不改。
总run上限3600秒（含采集/等待），RSS12GiB、MLX10GB、API parent1GiB，串行一个模型子进程。
127.0.0.1:8790独立服务/DB；不修改或继续写EXP-079的bench DB，不改变旧来源。

## 完成和独立验证

采样、快照、300–400预测、aggregate/derived和Dashboard API完整，原生输入hash100%对齐，
Research不发生fallback，实际schema有效、资源门和正常子进程退出通过。路由请求率按实测，
不要求15%或人为强制有M3。保存实际M3尝试/成功/cache、token长度/截断、错误与未知计数。

独立consumer复算records、source manifest可审字段、六标签统计、两种权重/日周/分层/诊断、
模式/成本、system/process安全门及artifact/source hash。不读取gold，不跑模型。
复用旧独立checker时只调用适用的纯函数，不给旧EXP-078伪造Passed终态。

只保存的排除计数不能被说成重新扫描来源；没有逐请求时间时不能声称独立重建每段速率。
这些证据限制保留，不因完整任务成功而消失。

固定产物`forum-topic-emotion-web/private/validation/exp-080/attempt-1/`，create-only run与verification。
服务停止后验证；任一失败保留工件并停止，无自动重试。仅支持cross-platform operational
portability，不支持外部gold准确率/Router增益、情绪机制或生产SLA。
