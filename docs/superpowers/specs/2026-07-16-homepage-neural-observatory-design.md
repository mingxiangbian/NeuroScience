# 首页 Neural Observatory 视觉规格与动效分镜

- 日期：2026-07-16
- 状态：待用户确认视觉规格；尚未进入代码实现
- 页面：`index.html`
- 类型：现有首页增量美化
- 创意主张：**Neural Observatory / 神经观测站**

## 背景与已确认边界

本轮目标不是简化首页，而是在现有动态 3D 大脑、Cyber Ink 米纸界面与研究模块展开机制之上，增加具有神经科学身份的可视化和装点。

用户已经确认以下边界：

1. 保留当前动态 3D 首屏，不改为“海报先行、3D 后增强”。
2. 不以减少动画、减少信息或极简化作为美化目标。
3. `papers/` 目前只有一个入口不是问题，本轮不扩充入口。
4. `projects/brain-memory-for-ai-agents/` 尚未完成，本轮不改。
5. 资源预算只约束实现效率，不改变动态优先的体验策略。
6. 本阶段只确定视觉规格和动效分镜，不修改首页代码。

相关项目约束见：

- `PRODUCT.md`
- `DESIGN.md`
- `tests/homepage-requirements.mjs`
- `assets/brain-human-attribution.md`

## 当前首页基线

首页不是一个待从零装饰的静态页面。当前 `index.html` 已经包含：

- Cyber Ink 米纸底色、纤维、墨洗、界面边框和 twin-arc 标志。
- 本地 NIH 高精度大脑模型与程序化 fallback。
- 玻璃脑材质、ink contour skin、sulcal flow skin。
- 最多约 42 组沟回路径、ribbon、rail 与移动 pulse。
- 六个研究模块的脑区展开、投射弧与内部海马体光带。
- GPU pedestal、六块 paper display、PCB 路线与路线粒子。
- `previewed`、`selected`、`expanded` 三类模块状态。
- 拖拽旋转、滚轮缩放、键盘重置、双阶段入口导航。
- Projects / Papers / paper section 的全局搜索。
- portrait、compact、fallback、reduced-motion 与 reduced-transparency 分支。

因此本轮的准确表述是：

> 将现有 Sulcal Activity Flow 升级为可响应六模块状态的 Neural Observatory Flow，并新增 Atlas focus、品牌轨道和观测仪器层。

不得再创建第二套全脑采样、第二套独立流场或第二个动画循环。

### 当前资源事实

`assets/brain-human.glb` 当前为 13,161,040 bytes，包含：

- 4 个 mesh。
- 215,601 个 position vertex。
- 1,133,103 个 index，约 377,701 个三角形。
- 0 张纹理、0 个 image。
- 依赖旧的 `KHR_materials_pbrSpecularGlossiness` 扩展。

这意味着优化重点是几何量化、压缩和材质格式转换，而不是图片压缩。

## 设计目标

### 使用场景

研究者在有自然光或台灯的工作桌上打开一张“活着的米纸脑图谱”：页面首先是一件可操控的研究对象，随后才展开成知识工作区。它应使人愿意观察、触碰和反复进入，而不是像营销页一样观看一次就离开。

### 核心体验

用户在十秒内应感知到三层含义：

1. 大脑是整个知识空间的主对象。
2. 神经活动、脑区与六个研究目录之间存在可交互的界面映射。
3. 这些脑区名称是知识工作区的设计隐喻，不是神经科学因果结论。

### 成功信号

- 不操作时，首页比当前更有空间深度和生命感，但大脑仍是绝对主角。
- hover 或键盘 focus 任一模块时，脑区、流场、轨道和显示屏同时给出一致反馈。
- 展开后，用户能看懂“脑区 → 信号 → 显示屏 → 目录”的视觉关系。
- 新装饰都能解释其语义，不出现随机星点、无连接网格或泛科技背景。
- 动态首屏、导航语义、搜索、fallback 与现有响应式布局保持不变。

## 创意方向

### 色彩策略

采用 **Committed base + semantic palette**：

- 米纸与深墨继续承担至少 80% 的视觉面积。
- flower blue 与 deep ink 构成观测仪器和品牌轨道。
- 六个模块色只表示真实交互状态，不扩散成彩虹背景。
- cinnabar 继续稀缺，只用于焦点、活动信号或明确选择。
- 不新增霓虹青、纯紫渐变或大面积 bloom。

现有六模块色保持不变：

| 目录 | Workspace region | 3D 色 | 视觉运动性格 |
| --- | --- | --- | --- |
| `knowledge/` | Association Cortex | flower blue | 多分支、跨区汇聚 |
| `projects/` | Prefrontal Planning | cinnabar | 前向、定向、决策式脉冲 |
| `sources/` | Parietal Integration | mineral gold | 多来源向中心收束 |
| `papers/` | Temporal Memory | pine green | 缓慢回环、反复检索 |
| `questions/` | Cingulate | dusk violet | 内侧弧线、冲突监测式往返 |
| `sessions/` | Hippocampal | warm ochre | 成对进入、回放式脉冲 |

这些映射只承担界面隐喻。页面不得展示伪造的 MNI 坐标、Brodmann area、放电频率或解剖概率。

### 参考锚点

- [FlyWire Connectome Gallery](https://join.flywire.ai/gallery)：科学数据本身形成稀疏、发光、分叉的空间装饰。
- [EBRAINS Human Brain Atlas](https://atlases.ebrains.eu/viewer/go/human)：选择脑区后保持 3D 上下文，并显示图层与对象信息。
- [Active Theory](https://activetheory.net/)：暗场体积感、清晰主对象和克制的空间 HUD；本项目只借层次，不复制其暗色品牌。
- [Of the Oak](https://lusion.co/projects/of_the_oak/)：生物主体、空间热点和 instancing 驱动的粒子环境。
- [earth.nullschool](https://earth.nullschool.net/)：运动轨迹同时表达方向、状态和数据结构。

## 视觉层级

新视觉不是任意堆叠。最终层级从后向前固定为：

```text
L0  Rice-paper field + Cyber Ink interface frame        现有，保留
L1  Twin-arc observatory orbit                           新增
L2  Sparse external connectome field                     新增
L3  Glass brain model                                    现有，保留
L4  Semantic Sulcal Activity Flow                        现有流场升级
L5  Workspace-region focus contour                       新增/复用现有 fragment mask
L6  Exploded research modules                            现有，保留
L7  GPU pedestal + PCB routes + project displays         现有，保留
L8  Atlas HUD + module labels + Search                   新增/现有 DOM 层
```

### L1：Twin-arc Observatory Orbit

把标题中的 twin-arc 品牌语言延伸到大脑周围，但不修改标题标志本身。

- 在 `shell` 附近增加两条不闭合椭圆轨道，作为 scene-level 环境层，不随大脑拖拽旋转。
- 左弧较有机：线宽轻微变化、边缘带墨扩散，使用 deep ink / flower blue。
- 右弧较精确：细线、刻度与六个模块锚点，使用 deep ink。
- 初始态只显示完整度约 35%–45% 的断续轨道，避免形成普通行星环。
- 展开时，六个刻度与六块 display 的方向建立对应，但轨道不染成六色。
- 轨道是品牌和界面框架，不模拟真实神经解剖结构。

### L2：External Connectome Field

增加大脑外部的稀疏神经投射，使现有脑表面流场能够延伸到研究模块。

- 桌面上限 18–24 条可见 filament；portrait 12–16 条；compact 8–12 条。
- 路径起点复用已有脑表面样本，终点对应模块或 display 锚点。
- idle 时仅保留极淡深墨/flower-blue 轮廓，不持续显示六色。
- active module 只点亮与它相关的 3–5 条路径，并让一个脉冲从脑区向 display 单向传播。
- filament 必须有 `depthTest: true`、通常 `depthWrite: false`，允许脑回遮挡路径。
- 不使用全屏流体、视频、随机烟雾或 post-processing bloom。

### L4：Semantic Sulcal Activity Flow

保留并升级现有 `createSulcalActivityFlow()`：

- idle：继续表现全脑的缓慢沟回活动。
- preview：活动色向 active module 的色彩轻微偏移，对应区域的流速和局部亮度提高。
- selected：保持稳定焦点，不让其他区域完全变暗。
- expanded：不再在接近完成时突然整层消失；改为表面流场降低至约 20%–30%，同时把视觉动势交接给 external connectome 与 PCB route。
- search open：所有非必要运动降至约 30%，避免与搜索阅读争夺注意力。

不能另起第二套纹理、采样或 `requestAnimationFrame`。

### L5：Workspace-region Focus Contour

利用现有 module bounds、fragment shader 与 `selectionFocus` 接口建立脑区聚焦：

- hover/focus 时出现一层细薄的区域轮廓和局部表面洗色。
- surface module 使用现有 normalized bounds，不克隆第二个完整大脑。
- Cingulate 使用现有 projected arc；Hippocampal 使用现有 internal glow。
- 轮廓颜色来自模块色，最大亮度低于 display 的选中状态。
- 其他区域保持可见，不采用全局压暗到 20% 的“聚光灯”处理。

### L8：Atlas HUD

Atlas HUD 是观测仪器，不是另一张悬浮卡片。

- 插入在 WebGL canvas 与 `.module-layer` 之间。
- `pointer-events: none`，不绑定新的 hover/click 监听。
- 仅在 `expanded && activeModule` 时出现；没有 active module 时保持隐藏。
- 位置使用当前脑区的屏幕投影点，并自动避开标题、六个 display、Search 和视口边缘。
- 结构由细线、刻度、局部坐标和两行文本组成，不使用玻璃卡片和大圆角。
- 可见英文信息限制为：
  - `WORKSPACE REGION`
  - region name
  - folder path
  - `ANALOGICAL MAP`
- 可选坐标只能使用真实的模型局部坐标，并标为 `MODEL XYZ`；默认版本不显示坐标。
- 如果 HUD 仅重复按钮信息，设为 `aria-hidden="true"`，继续让现有 `<button>` 承担无障碍语义。

## 动效分镜

所有时长是目标范围，不应通过人为等待强制满足。

| 阶段 | 时间/触发 | 画面行为 | 目的 |
| --- | --- | --- | --- |
| First frame | 页面开始渲染 | 立即显示米纸、标题、界面框和 WebGL 轨道；不展示静态 poster | 维持动态优先策略 |
| Asset streaming | GLB 下载期间 | WebGL 轨道和少量信号点可运行；不设置虚假最短 loading 时间 | 让等待仍是动态场景，而非替代海报 |
| Brain available | 模型解析完成 | 大脑材质在 420–560ms 内从轮廓/低透明过渡到当前玻璃状态 | 平滑接管主视觉，不阻塞交互 |
| Idle | 无输入 | 大脑沿用缓慢自转；沟回流场运行；轨道每分钟仅完成很小角度偏移 | 建立持续生命感 |
| Pointer hover / keyboard focus | 进入模块标签 | 180–240ms 内聚焦脑区、点亮对应轨道刻度，单个脉冲向 display 传播 | 解释模块关系 |
| Brain expand | 点击大脑 | 沿用现有脑区外移和 pedestal 激活；480–650ms 内由表面流场交接到外部 connectome 与 PCB route | 把“脑”展开成“知识系统” |
| Module preview | hover/focus display 或标签 | HUD 出现，区域轮廓增强；其他模块保持可见 | 允许探索，不改变选择 |
| Module selected | 第一次点击标签 | 220–300ms 内稳定选中色、display 文字打字显示；脉冲节奏降低并持续 | 表示持久选择 |
| Enter module | 再点同一标签，或点击 3D display | 立即导航，不等待离场动画 | 不让装饰妨碍使用 |
| Drag / zoom | 操作大脑 | 大脑、表面流场和区域轮廓共用变换；HUD 重新投影；轨道保持 scene-level 稳定 | 保持空间关系清楚 |
| Search open | 点击 Search 或 `⌘/Ctrl K` | 背景运动降至 30%，HUD 隐藏，搜索层成为唯一高对比焦点 | 支持阅读和输入 |
| Collapse | `Esc` 或点击大脑 | 320–440ms 内逆向收束；轨道刻度归位；外部 filament 回到极淡 idle 状态 | 回到观测对象 |

### 动效材料

- 交互反馈使用 180–300ms，`ease-out-quart` 或 `ease-out-quint`。
- 展开/收束可使用 420–650ms，`ease-out-expo`，不使用 bounce 或 elastic。
- 不动画 `top`、`left`、`width`、`height` 等布局属性；HUD 位移使用 transform。
- 不给每个对象添加独立循环；所有时间状态来自现有 render loop。
- 退出动画约为进入动画时长的 75%。

## 状态模型

Neural Observatory 不拥有独立的选择状态。它只消费现有状态：

```text
expanded
selected
previewed
activeModule = previewed ?? selected
dragging
searchOpen
prefersReducedMotion
```

要求：

- `.module-label` 继续是 pointer 和 keyboard 交互的主要 DOM 控件。
- `previewed` 只增强临时反馈，不写入 `selected`。
- active module 的状态同步驱动 region contour、sulcal flow、orbit tick、connectome pulse、PCB route 与 Atlas HUD。
- 不在各视觉层重复注册模块 hover 监听。

## 响应式与无障碍

### Desktop

- 保留左三/右三 display 布局。
- twin-arc orbit 不进入顶部标题安全区，也不穿过 display 文字区域。
- Atlas HUD 优先使用脑区与 display 之间的空白，不固定贴屏幕角落。

### Portrait

- 沿用现有左右 rail 标签和独立 3D composition。
- 轨道整体缩小，刻度数量不变；external filament 上限降至 12–16 条。
- HUD 只能出现在脑区附近的中央空白，不覆盖左右 rail。

### Compact（`<= 520px`）

- 保留 44px 触控目标。
- 不增加第二组浮动文字；Atlas HUD 合并为模块标签的一条微型 `ANALOGICAL MAP` 状态。
- 外部 filament 上限 8–12 条，脉冲同时最多 2 个。
- 禁止水平溢出；标题、Search 和模块标签仍可完整操作。

### Reduced motion

- 停止大脑自转、轨道转动、纹理滚动、脉冲移动和 display 打字动画。
- 保留静态轨道、静态 filament、区域轮廓和完整文本。
- 展开/收束使用即时状态或一次性短交叉淡化。
- reduced motion 不是退回 poster，也不移除 3D 大脑。

### Reduced transparency

- Atlas HUD 和模块标签使用实色纸面或纯线框。
- 不依赖 backdrop blur 表达层级。

## 实现架构边界

本轮后续实现仍保持静态 GitHub Pages，不引入框架或应用运行时。

推荐接口形态：

```text
createNeuralObservatoryLayer(...)
  -> group
  -> setState(interactionState)
  -> update(time, interactionState)
  -> resize(viewport)
  -> dispose()
```

实现时必须：

- 扩展现有 `createSulcalActivityFlow()`，复用其表面样本、路径、纹理和 pulse geometry。
- 复用 `createModuleFragmentMaterial()` 的 bounds 和 `selectionFocus`，不 clone 新的全脑 mesh。
- twin-arc orbit 作为 `scene` 下的 sibling，不能跟随 `brain-control-root` 拖拽。
- Atlas HUD 只从现有 `setupModuleUi()` 同步状态。
- 继续使用唯一 render loop；禁止新增第二个 `requestAnimationFrame`。
- 粒子、刻度和重复节点优先使用 InstancedMesh、共享 geometry/material 或 shader。
- 不新增视频、额外 GLB、全屏流体或 post-processing pipeline。
- `index.html` 继续作为唯一入口；是否拆分内嵌 CSS/JS 属于之后的独立代码整理，不和视觉实现绑在同一改动中。

## 资源与性能边界

### 动态优先原则

性能优化不能改变为 poster-first、静态首屏或用户触发后才加载 3D。允许做的是：

- 先启动 WebGL render loop，再异步装入高精度模型。
- 在模型下载期间显示真实的动态轨道和信号层。
- 模型就绪后立即接管，不设置人工 loading 延迟。
- 保留 procedural fallback 和 `?fallback` 验证通道，但不把 fallback 当作默认视觉。

### 模型优化

第一阶段只做无明显视觉损失的管线优化：

1. 将 `KHR_materials_pbrSpecularGlossiness` 转换为标准 metallic-roughness。
2. 对 position、normal 和 index 做安全量化。
3. 使用 Meshopt 或 Draco 压缩几何；优先选择能在 Three.js 中稳定解码、解码器体积较小的方案。
4. 不在第一阶段减少三角形或替换成低精模型。
5. 更新原测试中“模型必须大于 10MB”的错误代理指标，改为验证模型合法、细节基线和视觉回归。

目标：在外观无可见退化的前提下，把 13.16MB 模型降到 **不高于 6.5MB**。这是优化目标，不是以牺牲细节换取的硬门槛。

### 新增视觉预算

- 不新增大于 500KB 的 raster/video/GLB 资产。
- 新图层增加的运行时 geometry/buffer 目标不高于 1MB。
- 新图层额外 draw call：idle 目标不高于 12，expanded 目标不高于 18。
- 继续将 renderer DPR 上限保持在 2。
- 1440×900 桌面测试：idle 和 expand 期间平均目标至少 55fps。
- 390×844 移动测试：平均目标至少 45fps，不出现连续可感知卡顿。
- Search 打开时降低背景更新强度，不暂停输入或焦点处理。

以上预算通过真实浏览器测量验证，不以代码行数或主观感觉替代。

## 验收信号

### 视觉

- 大脑、现有沟回流场、GPU pedestal、六 displays 和 PCB routes 均保留。
- 初始状态能够看见 twin-arc 轨道和极淡 external connectome，但不遮挡标题或脑表面。
- hover/focus 任一模块时，region contour、flow、orbit、route 和 HUD 使用同一个 active module。
- 展开时表面流场自然交接到外部 connectome/PCB，而不是突然消失或叠出两套流场。
- 可见 HUD 明确使用 `WORKSPACE REGION` / `ANALOGICAL MAP`，不伪装成真实脑图谱数据。
- 页面仍保持 English-only visible UI。

### 功能

- 初始点击大脑仍切换展开。
- hover/focus 不改变持久选择。
- 第一次点击标签选择，第二次点击进入目录。
- 点击 3D display 仍可直接进入对应目录。
- Search、`⌘/Ctrl K`、`Esc`、`R`、拖拽和缩放保持可用。
- `?fallback` 仍能呈现非 WebGL 页面。

### 响应式与无障碍

- 1440×900、1024×1366 portrait、390×844、320×568 无横向溢出。
- keyboard focus 与 pointer hover 触发一致的 Observatory 状态。
- `prefers-reduced-motion` 下无持续移动，但 3D、区域关系和导航仍完整。
- `prefers-reduced-transparency` 下信息不依赖毛玻璃。
- HUD 不截获 pointer，也不制造重复可访问名称。

### 验证

- `node tests/homepage-requirements.mjs`
- `git diff --check`
- 本地 HTTP 预览，而不是 `file://`
- Chrome 桌面、portrait、390px、320px、reduced-motion 实测
- 对模型优化前后做固定机位截图对比和 glTF 结构检查
- 后续发布时验证 GitHub Pages 构建状态与线上首页

`tests/homepage-requirements.mjs` 当前不包含在 `npm run test:all` 中，必须单独运行。`tests/pages-workflow-requirements.mjs` 存在既有测试漂移，不混入本轮视觉规格。

## 非目标

- 不改变首页为静态或 poster-first。
- 不简化或删除现有 3D、流场、展开、GPU pedestal、显示屏和搜索。
- 不修改 `papers/` 的入口数量。
- 不改 `projects/brain-memory-for-ai-agents/`。
- 不引入真实神经解剖声称或伪造科学数据。
- 不给所有子页面统一套用首页 WebGL 效果。
- 不同时进行单文件拆分、框架迁移或大规模测试重写。
- 不在视觉确认前修改代码。

## 已决事项

1. 首页延续动态 3D 优先策略。
2. 美化采用“有科学语义地增加”，不是减法或极简化。
3. 新方案名为 Neural Observatory / 神经观测站。
4. 参考组合为 FlyWire × EBRAINS × Active Theory / Of the Oak。
5. 当前流场升级为 semantic flow，不新增第二套流场。
6. 新增重点为 twin-arc observatory orbit、external connectome、workspace-region focus contour 与 Atlas HUD。
7. Atlas HUD 必须明确标注知识空间隐喻，不把 AI/目录映射说成真实脑机制。
8. 性能优化必须保持动态体验和高精模型外观，不使用 poster-first 或默认低精替代。
9. 本文确认后，才进入独立实施计划与代码阶段。
