---
name: 札记
description: A reference-led public notebook built around a truthful record timeline, one red neural signal, and a continuous learning-work canvas.
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
    fontFamily: '"Zaji Script", "STKaiti", "KaiTi", serif'
    fontSize: "clamp(46px, 6vw, 88px)"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0"
  title:
    fontFamily: '"Songti SC", "STSong", "SimSun", serif'
    fontSize: "clamp(36px, 5vw, 72px)"
    fontWeight: 600
    lineHeight: 1.14
    letterSpacing: "-0.02em"
  body:
    fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: '"SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", system-ui, sans-serif'
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0"
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
  glass: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  section: "64px"
  page: "112px"
---

# Design System: 札记

## Creative North Star

**神经信号台账（Neural Signal Ledger）**：像一张正在被写入的冷白研究工作台。上半页是一条真实时间线，下半页是一张连续的学习成果图；一根 Campari 红神经信号把两部分连起来。

视觉构图以用户提供的 1586×992 参考图为基准，但内容全部来自现有 Markdown：四条记录正好对应一篇博客与三项成果，不伪造发布日期或时间。品牌使用项目目录既有的双弧图标；“札记 / 博客 / 成果”使用书法字，文章标题使用宋体。

## Rules

- 红色只表示真实状态：内容流、时间、阅读进度和当前选择。
- 玻璃只用于首页“正在阅读”和连续成果画布；成果索引保留一个有功能意义的预览区域。
- 博客列表与正文保持开放排版，不用卡片包裹。
- 首页成果图用于表达三个真实项目的学习结构；成果详情继续使用真实页面截图，不生成伪造指标、图表或奖项。
- 不使用装饰渐变、黑色顶栏、全屏侧边栏、等权卡片网格、头像或照片。
- 移动端始终显示品牌行和导航行，不使用汉堡菜单。
- 正文控制在约 65–72 个字符宽度，图片可以有节制地突破正文宽度。
- 导航只有“首页 / 博客 / 成果”；“关于”不再占据一级入口。

## Shape and Depth

`8–16px` 圆角用于代码、媒体与两处玻璃表面。普通内容不加圆角容器和大面积阴影。

玻璃由半透明白/青色、细亮边与背景模糊组成，不叠加宽而虚的阴影。所有透明层从上面的基础色用 `color-mix()` 派生，避免新的散乱色值。

## Reference Mapping

- 顶部记录区：年份、红色轨道、四条真实记录、一个“正在阅读”玻璃面。
- 中部信号：`assets/visuals/signal-wave.webp`，承担区段过渡，不是装饰性背景。
- 底部成果画布：`learning-loop.webp`、`memory-system.webp`、`knowledge-network.webp` 分别对应基石、记忆与智能体、投资学习阅读器。
- 博客索引：最新文章置顶，其余内容进入按年份组织的文章归档。
