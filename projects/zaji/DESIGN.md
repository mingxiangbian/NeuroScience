---
name: 札记
description: An independent public notebook with a cool-white field, near-black typography, a Campari-red signal, and purposeful pale-cyan glass.
colors:
  canvas: "#f7f9f9"
  surface: "#ffffff"
  ink: "#111515"
  prose-ink: "#222829"
  muted: "#667071"
  faint: "#657476"
  signal: "#de3048"
  signal-text: "#c2263e"
  cyan: "#d8f3f2"
  cyan-deep: "#b9e6e4"
  link: "#176f74"
  quote-ink: "#344546"
  cold-code: "#edf1f2"
  shadow-teal: "#305c5b"
  syntax-comment: "#657476"
  syntax-keyword: "#a82b45"
  syntax-number: "#7e5a10"
  syntax-type: "#5352a0"
  syntax-variable: "#4d5e60"
typography:
  display:
    fontFamily: '"SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "clamp(58px, 8.5vw, 220px)"
    fontWeight: 900
    lineHeight: 0.98
    letterSpacing: "-0.09em"
  body:
    fontFamily: '"SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.95
  label:
    fontFamily: '"SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "11px"
    fontWeight: 760
    lineHeight: 1.4
    letterSpacing: "0.16em"
  mono:
    fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.7
rounded:
  inline: "4px"
  code: "8px"
  media: "12px"
  media-large: "18px"
  band-mobile: "24px"
  band: "32px"
  lens: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  section: "72px"
  page: "130px"
---

# Design System: 札记

## Creative North Star

**透光台账（Luminous Ledger）**：像一张被持续写入的冷白工作台。内容依靠大尺度无衬线字、开放排版、细线和红色状态信号建立秩序；玻璃只在需要聚焦当前内容时出现。

这套视觉是 `projects/zaji/` 的独立个人品牌，不继承项目目录的米纸、书签和书法语汇。项目目录只负责提供入口。

## Rules

- 红色只表示真实状态：内容流、时间、阅读进度和当前选择。
- 玻璃只用于首页“正在阅读”镜片、连续成果带和成果页单个预览镜片。
- 博客列表与正文保持开放排版，不用卡片包裹。
- 成果使用真实页面截图，不生成伪造界面、指标、图表或奖项。
- 不使用装饰渐变、黑色顶栏、全屏侧边栏、等权卡片网格、头像或照片。
- 移动端始终显示品牌行和导航行，不使用汉堡菜单。
- 正文控制在约 65–72 个字符宽度，图片可以有节制地突破正文宽度。

## Shape and Depth

`8–18px` 圆角用于代码与真实媒体；`24–32px` 只属于连续成果带。镜片可以使用圆或椭圆轮廓。普通内容不加圆角容器和大面积阴影。

玻璃由半透明白/青色、内侧亮边、背景模糊和低对比青色阴影组成。所有透明层从上面的基础色用 `color-mix()` 派生，避免新的散乱色值。
