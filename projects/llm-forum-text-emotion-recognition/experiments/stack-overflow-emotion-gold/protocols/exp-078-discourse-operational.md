# EXP-078：Python Discourse 无标签运行接入

- Date：2026-08-31
- Tier：Minor，RQ-S3 / Phase C跨平台服务实现。
- 它验证输入与服务可运行，不验证跨域准确率；外部gold实验继续暂停。

## 来源与固定边界

采用已审核的Python官方讨论区 `https://discuss.python.org`，Python Help category 7。
仅公开匿名JSON接口，无账号key、不绕过登录、反爬或访问控制；robots禁止的/search不使用。
条款为CC BY-NC-SA 3.0，限本地非商业研究使用；保留来源URL、作者署名与许可。
详见模块docs/discourse-source-review.md的当前官方来源与可行性记录。

此前只检查了3条raw字段返回（2条唯一帖子，来自2次内容接口请求），没有执行完整语料采集或模型。本次原生输入使用
API `include_raw=true` 返回的raw字符串，不能由cooked HTML清洗、拼接上下文或标题回填。
模型继续冻结seed42 M1/Router/M3。未读取任何gold、历史train/validation/test，不训练或适配。

## 固定采样

category7的topic列表以创建时间降序读取，帖子按post_number升序；固定确定性topic前缀。
不设不存在的完整时间窗，记录实际topic/post IDs、source creation date范围、抓取时间、
请求参数、返回数量、排除数量及停止原因。排除置顶、system/非普通post_type、deleted内容，
均显式计数。正常公开post缺raw不能默默用HTML回填。匿名不可得ID单列unavailable，
不能把它们称为已读取或完整线程；来源实例不同而文本相同仍保留occurrence。

最多100个topic、400个普通公开posts，成功范围300–400条。
使用公开topic JSON的stream和 `/t/{id}/posts.json?post_ids[]=...&include_raw=true` 批量取raw。
最多160次来源请求、900秒、每秒最多1次、每响应2MiB；403/429停止，不自动重试。
沿用单文本64KiB和整体job500上限，source ID、parent/thread、URL及原生输入hash可追溯。

## 执行与检查

一次正式采样+一个Research mode job，max_qwen_calls=500（不对路由施加额外裁剪），audit0。
最多3600秒、RSS12GiB/MLX10GB，global heavy lock；在Soak完成后或不涉及资源安全的负结论后执行。
若Soak出现仍未解决的critical/资源故障，不继续模型负载；可完成来源审核与文档并报告阻塞。

完成条件：原生raw 100%可追溯、300–400条输出schema有效、输入/来源/预测对齐、
HTTP任务最终退出门通过、独立复算记录/成本/聚合一致，Dashboard共用现有组件。
报告M3路由请求率、实际调用/cache/fallback、截断和长度诊断；没有gold，绝不报告accuracy/F1。
不要求路由比例接近15%，不根据结果修改模型、阈值、seed或采样话题。

模块输出 `private/validation/exp-078/attempt-1/`，保存run.json、来源manifest/哈希、job引用、
stdout与只读verification；真实原文只进私有DB，公开文档无全文。异常保留并停止该次任务，
不要覆写失败或把跨平台服务完成写成外部泛化已验证。
