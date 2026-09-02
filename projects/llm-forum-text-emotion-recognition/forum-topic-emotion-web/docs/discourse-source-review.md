# Discourse 来源审核：Python Help

日期：2026-08-31。范围：Phase C 的未标注跨论坛运行验证，不是外部金标评价。

## 审核结论

采用 `discuss.python.org` 的 **Python Help，category 7**。允许的用途是当前非商业、本地研究原型：
保留作者用户名、原帖链接和许可说明；原文及逐条输出继续存放在 ignored private 目录。
本次没有审核第二个论坛，也不接收任意 Discourse URL。

网站官方指南明确将论坛用于 Python 及其生态的讨论，使用英语交流，并将 Python Help 用于
技术求助。因此这个分类与现有英语技术文本原型相符；这不等于确认每条帖子都是英语，也不
证明现有模型在这里具有已知准确率。[社区指南](https://discuss.python.org/guidelines)

## 许可与访问边界

网站条款第 3 节将用户贡献置于 **CC BY-NC-SA 3.0 Unported** 下。应用保存来源链接、
作者用户名和许可链接；展示的是截取预览，模型输入则保持原生字符串。不得把当前审核扩展
为商业使用授权，也不自动再发布完整论坛语料。引用了第三方材料的帖子可能另受原材料许可
约束，站点条款不能替代逐项版权审查。[站点条款](https://discuss.python.org/tos)、
[许可说明](https://creativecommons.org/licenses/by-nc-sa/3.0/)

当日匿名请求 `robots.txt` 返回 HTTP 200。适用于本客户端的 wildcard 规则禁止 `/search`、
认证、管理和用户密钥等路径，没有禁止本次使用的 `/c/`、`/t/` JSON 路径。
因此只做固定分类的公开话题遍历，不实现自由关键词搜索，不请求登录、私信、隐藏或删除内容，
不更换身份绕过限流或反爬。[robots.txt](https://discuss.python.org/robots.txt)

Discourse 的全局限流可以由站点管理员调整。上游默认值不是 Python 论坛承诺的配额。
本模块采用更低的客户端速率：请求结束后至少间隔 1 秒；HTTP 403、429 或其他访问错误立即
停止，不自动重试。服务端返回的额外等待时间也必须遵守。[Discourse 限流文档](https://meta.discourse.org/t/available-settings-for-global-rate-limits-and-throttling/78612)

## 当日可行性检查

未携带 cookie、登录状态或 API key，使用明确的 `TopicEmotionResearch/0.1` User-Agent。
只读取分类元数据，以及两条唯一帖子共三次 raw 字段返回；没有保存或输出正文、HTML 或作者。

| 请求 | 实测结果 | 用途 |
| --- | --- | --- |
| `/categories.json` | 200；category 7 为 Python Help，`read_restricted=false` | 确认分类公开 |
| `/c/help/7/l/latest.json?order=created&ascending=false&page=0` | 200；每页 30 个话题，带下一页位置 | 确认创建时间降序与分页 |
| `/t/108811.json?include_raw=true` | 200；2 条普通帖子均含 string 类型 `raw` | 验证匿名原生文本 |
| `/t/108811/posts.json?post_ids[]=300470&include_raw=true&asc=true` | 200；同一帖子 raw hash 与前次相同 | 验证按 ID 取后续帖子 |

两条唯一 raw 的 UTF-8 长度为 546、323 bytes。Post 300470 的两种公开接口返回相同 SHA-256：
`45e794213257809acd9bb1c70b241c483cadf4aacbcdce386794802421517edb`。
这些检查只证明当时接口及字段可用，不代表 300–400 条正式采集已完成。

上游控制器与 serializer 也提供 `include_raw` 和原生 `object.raw` 的实现；生产站点是否可用，
仍以匿名实测为准。[Topics controller](https://github.com/discourse/discourse/blob/main/app/controllers/topics_controller.rb)、
[Post serializer](https://github.com/discourse/discourse/blob/main/app/serializers/post_serializer.rb)

## 冻结的采样与输入合同

入口函数为 `fetch_discourse(request, cancelled, progress)`，请求字段仅为：

```json
{"site":"discuss.python.org","category_id":7,"max_topics":100,"max_items":400}
```

1. 分类列表按话题创建时间降序取前缀，跳过置顶和非公开、非普通话题，逐项计数。
2. 每个话题按公开 `post_stream.stream` 遍历，以 `post_number` 升序读取普通帖子。
   初始响应之外的帖子用同一话题的 `posts.json` 分批请求，每批最多 20 个 ID。
3. `post_type != 1`、system/discobot、明确删除或隐藏的帖子排除并计数。正常公开帖子缺少
   `raw` 则停止；不改走 `/raw/`，不使用 `cooked` 或 HTML-to-text 回填。
4. 返回缺失的 stream ID 单列为 `unavailable_post_ids`；达到条数上限而未读完的话题单列为
   `truncated_topic_ids`。有这些情况时不声称所选线程已全部采集。
5. `model_input_text = raw`，不拼标题、其他回复或上下文；精确 UTF-8 hash 决定推理缓存。
   同文不同帖子保留不同 occurrence。`thread_id` 保存 topic ID；可解析的回复父帖保存 post ID，
   无法解析的父帖显式计数，仍保留来源 `reply_to_post_number`。
6. 模型使用既有六标签顺序，不导入外部标签，不计算这里的 accuracy、F1 或泛化等级。

这不是完整时间窗，也不是全部论坛事件流。时间趋势来自所选帖子的真实创建日期；必须保留
快照中的 topic IDs、请求元数据、排除数与停止原因。不能用采集时间代替发布日期。

## 资源与后续条件

本 adapter 最多 160 请求、900 秒，wire 与解压后响应各不超过 2 MiB；每条模型输入仍不超过
64 KiB，应用全局上限仍为 500 条。本次 EXP-078 固定目标 400，成功门为 300–400 条普通公开帖子。
不足 300、访问被拒绝、原生字段缺失或资源超限时，应报告实际状态，不扩大站点或挑换样本来补齐。

正式采集和模型运行由 EXP-078 登记后执行；当前来源审核不能充当正式实验结果。
今后若变更论坛、分类、商业用途或公开语料发布范围，应重新核对来源与许可。
