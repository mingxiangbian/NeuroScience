# HANDOFF · Career Roadmap 视觉改造（2026-07-18）

> 给下一个会话的交接文档。当前状态：**Phase 0 定案完成，未写任何实装代码**。
> 一切现有页面内容保持原样，未删除任何东西。

## 已定案的决定（不要重新讨论）

1. **视觉方向：Mock B「纸上丝印」**——主板图用墨绿单色线稿直接印在宣纸底上（不是甲版的深绿实体面板）。定案 mock 在 `tmp/mock-career-b.html`（甲版 `tmp/mock-career-a.html` 保留作参考，勿删）。
2. **结算印印面 = 单元号**（如 U1）+ 印下小字单元名，白文朱砂印样式。首页的"识"印保持唯一，不复用。
3. **Phase 3（ledger.md 自动摄入 build script）这轮不做**——用户明确否决。
4. 配色/字体全部沿用站点 DESIGN.md：paper `#f4efe3`、ink `#1f2724`、cinnabar `#a64338`、seal-red `#b24338`、gold `#9b7430`、宋体 display、PingFang body、IBM Plex Mono 丝印字。Mock B 专属：draft `#2c4a3c`（墨绿线稿主色）。

## 设计方案（六个改造点，A–E 做，F 否决）

- **A 工作台**：页面顶部唯一大卡 = 活动单元（类型章 + session 数 + 下一步一句话 + 记断点/撞墙两个按钮 + 右侧该单元的"待印"虚线框）。
- **B 台账带**：横排印章收藏——已结算 = 朱砂印（旋转 -2.5°），活动 = 朱砂虚线框，未来 = 淡墨幽灵格；右侧"已结算 n"计数 + 金色齿孔玩耍券票根（"再结算 x 张解锁"）。**进度百分比在本模块取消**，零态永远是"待印"不是"0%"。
- **C 主板图**：贾维斯 0.x 主板 SVG（乙版线稿风）——六子系统插槽、①外部供货虚线框、②③④各五个焊盘=深度阶梯（金=已到达、朱=进行中、淡墨=未到）、U-QUEUE 边缘连接器走线向②布线、CYRENE 0.0 归档芯片 + 朱砂虚线 0.1 SOCKET（U7 点火位）、⑥接地网纹、角落 0.x 小印。SVG 已在 mock 里写好，可直接移植。
- **D 朱批**：单元描述里的顿悟点抽成右侧朱砂侧批栏（竖线 + 「朱批」小章）。
- **E 冻结队列**：低对比卡 + 右侧蓝灰"冻"小章（dai-blue 系，绝不用羞耻灰/红）；远期队列一行斜体铅笔字。四阶段改为水平轨道 + 过孔节点，当前阶段朱砂发光。

## 视觉纪律（实装时必须遵守）

- 无债务视觉：不出现红色警告/逾期/倒计时/可下跌数字；朱砂只用于"已获得"。
- 动效只做一处：落印瞬间（可 Phase 2 再做），其余全静。
- 暗色模式同权：所有新 token 要有 `[data-theme="dark"]` 对应值。
- **不碰共享阅读器全局样式**：走 career-roadmap 专属渲染分支，其他 9 个模块和 finance 阅读器零影响。

## 实装路径（下个会话从这里开始）

**Phase 1（先做，奖励回路）**：工作台 + 台账带 + 印章零态 + 冻结美学（A/B/E）。
**Phase 2**：主板图 + 朱批 + 四阶段轨道（C/D）。

关键工程事实（本会话踩过的坑，别重踩）：

1. `roadmap/roadmap-data.json` 是**生成物**，源 = `roadmap/modules/career-roadmap.md`，生成器 = `scripts/build-roadmap-data.mjs`。CI（Deploy GitHub Pages workflow）跑 `npm run test:all`，其中会重新生成并 `git diff --exit-code` 校验——**手改 JSON 必挂部署**。
2. 渲染入口：`roadmap/roadmap-reader.js` 约 1596 行，overview 已有专属渲染先例（`renderOverviewDashboard`）。照此模式加 `module.id === "career-roadmap"` 分支 → `renderCareerRoadmap(module)`。
3. 单元数据现在是 `任务` section 的 HTML 列表，渲染器不好解析。**建议**：扩展 build script，从 markdown 的任务列表解析出结构化 `units` 字段（id/名称/类型/session 数/状态）注入模块 JSON，渲染器消费它；`tests/foundations-roadmap-requirements.mjs` 的结构断言要同步加。
4. 任务勾选状态存 localStorage（taskState，ID 由 section 标题+分组+序号派生）——改 markup 会换 ID，当前零结算所以无损。
5. 测试已拆过两颗雷：`overallLearningProgress` 改为 0–100 区间校验、career-roadmap 的 `last_updated` 改为日期格式校验（不再钉死具体日期）。
6. CSS 建议：在 `roadmap-reader.css` 尾部加 `.career-` 命名空间段落，或新建 `career.css` 由 reader 按模块加载；勿动现有选择器。
7. 本地预览：仓库根 `python3 -m http.server 8742`，页面 `http://localhost:8742/projects/foundations/?module=career-roadmap`；mock 在 `http://localhost:8742/tmp/mock-career-b.html`。
8. 工作区有**不属于本任务**的未提交改动（`index.html`、`tests/homepage-requirements.mjs`、`assets/homepage-layout.js`、`.impeccable/`）——是首页 PCB 工作，别动、别一起提交。
9. 提交纪律：用户说"push"才提交推送；上两次提交是 `e2ae47c`（计划精修）和 `43edd45`（生成源修复），风格照旧。

## 下个会话的第一个动作

读本文件 → 起本地服务 → 打开 mock B 对照 → 从 Phase 1 的 build script `units` 字段开始动手。
