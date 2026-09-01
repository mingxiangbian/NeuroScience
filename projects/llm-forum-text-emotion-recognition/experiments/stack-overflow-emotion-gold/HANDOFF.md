# Stack Overflow Phase A 到 Phase B 实验交接

### 最终收口（2026-09-01）：Phase C在有界本地研究范围内关闭

用户确认[最终范围决策](protocols/dec-phase-c-final-scope-and-closeout-v1.md)。Phase C.1 lifecycle=`Closed`、
outcome=`Verified Pass within registered bounded workload`；Phase C lifecycle=`Closed`、
outcome=`Completed within bounded local research scope`。最终定级为
`Verified bounded local research prototype with two-source service portability`。

当前唯一claims入口为
`forum-topic-emotion-web/private/reports/final-claims-2026-09-01.md`，最终系统收口为
`forum-topic-emotion-web/private/reports/phase-c-final-closeout-2026-09-01.md`；8月31日报告保留历史快照。
Release QA为579 tests、node/pip/diff checks Passed；隔离浏览器smoke验证三来源、三模式、取消、
刷新/重启恢复和1280/720/390无横向溢出，未运行模型或联网。当前runtime与EXP-086 37成员archive
逐文件0 mismatch。

旧EXP-077/079/083/085 attempt1失败不改，EXP-078/080继续Not executed。外部gold、context/C2、
长期SLA、多用户、公网部署、商业许可、matched memory-causality、新训练和Router调参改为未来独立范围。
本次没有训练/旧split访问/新采集/模型运行/上传/commit/stage/push；不要自动重开这些分支。

### 当前终态（2026-09-01）：EXP-086 staged Discourse正式闭环已通过

EXP-085 attempt2完整通过后，已登记`protocols/exp-086-staged-discourse-formal.md`。
固定来源为discuss.python.org / Python Help category7，query=`max_topics100/max_items400`，
成功门300–400公开普通post；Research500/audit0/seed42。只用匿名原生raw，不访问gold或登录接口。
579/579 tests、producer/consumer/backend Approved及只读环境门通过后，唯一一次正式run已完成：
supervisor PID20897、exec session30557退出0；端口8790，RUN=
`forum-topic-emotion-web/private/validation/exp-086/attempt-1/`。UTC开始2026-09-01T01:37:18.384458，
总225.806977秒；来源采集112.304秒，69/69请求均取得公开响应，未重试或换站点。

来源门接受400条、64个topic，创建时间范围UTC 2026-07-11T23:00:09Z至2026-08-31T23:02:22Z；
400/400来源链接、署名、许可和原生raw hash可追溯。排除1条删除/隐藏、2条非普通post；
0 unavailable stream ID、0 unresolved parent。达到item_limit，最后1个topic截断，
`collection_complete=false`；不能写成完整线程、完整时间窗或论坛总体样本。

M1和独立M3两阶段均400/400、exit0；800阶段回执、400最终结果完整。物理成本：400次M1，
400次transfer reuse，46次M3且46/46成功，0 cache/fallback/audit；M3路由率46/400=11.5%。
1对load和46对forward事件全部闭合；没有旧M3输入参考适用于Discourse，因此只核冻结数学、
同任务transfer、schema、成本与阈值，不声称跨域数值parity或准确率。

独立verification=Passed、exp086_complete=true、operational_state=safe-to-continue、
safety.gate_passed=true。213系统样本：211 normal、2 warning、0 critical/unknown；
最高swap374.571264MiB/s，最长连续高值2，未达3段停止门。采样parent/child RSS峰值
97,042,432/1,287,995,392B；回执历史RSS peak1,859,321,856B、MLX peak8,615,445,276B。
两推理root均exit0，全部3个已见root/aux身份消失，锁和服务已释放。

plan SHA=`09adb1a695b8a4e9a321b6736c0ca8ee021c6219387bb51c1a19e60eddad5ad3`；
run SHA=`273dff4d562237aac247670fc62ec41077ac714d965eab75f4206469e348814b`；
verification SHA=`1d49e88655b917c3fec275c8e7f1c66594e588f15d2f26b7b677398298bec450`。
36个plan源文件和本协议已封存为37成员archive，SHA=
`97ee2c550265d864a6dab2b43928cc956eac57ac9c27397ed4efb3ee21440818`。

结论：既定Phase C.1最低目标“有界稳定运行＋Discourse正式闭环”已完成。
该结论只支持本机固定负载和一次无gold跨论坛服务链路，不支持外部准确率、总体情绪、SLA或商业再发布。
不要重跑或修改EXP-085/086绑定工件。旧EXP-080仍Not executed；CancerEmo等外部gold、context/C2、
公网部署继续暂停，无训练/旧split访问/commit/stage/push。

### 当前终态（2026-09-01）：EXP-085 attempt 2完整通过，允许进入staged Discourse

用户要求下一步。Attempt 1的32个plan源文件和原协议已在修复前封存为33成员archive，
SHA=`76664bc9b6d532e2fc0e81a7b169d25d512f32a72380cd5982e4360c9ce49733`。
只将内部`_event`形参改为positional-only `event_type`，保留payload的`kind`；新增真实JSONL帧
经`StagedProcessRunner`进入绑定`StagedRunner._phase_progress`并写observer/Store成本的组合回归。
未改模型、输入、阈值、router、预算、精度或安全门。新协议为
`protocols/exp-085-staged-website-bounded-acceptance-attempt-2.md`，SHA=
`93d51d1b5a0b02b626cb27f3b6c4688b799a75fcfabb5244235266c26655b83e`。
550/550全套、独立consumer/producer Approved及只读环境门通过后，唯一一次attempt2已完成：
supervisor PID10272、exec session96264退出0；RUN=`forum-topic-emotion-web/private/validation/exp-085/attempt-2/`。
UTC开始2026-09-01T01:03:52.279398，总589.852107秒；9/9逻辑任务、15/15模型阶段、
3060/3060最终结果、5100/5100阶段回执完整。三轮M1-only/Research均completed，三轮Demo均
completed_with_fallback；只有预期15项`m3_budget_exhausted`，无其他fallback。

独立verification=Passed、exp085_complete=true、operational_state=safe-to-continue、
safety.gate_passed=true。完整成本：3042次M1、18次同阶段重复缓存、135次M3且全部成功、
2040次跨阶段复用、0次M3 cache、0 audit；282条M3阶段事件闭合为6对load和135对forward。
全部M1相对原076≤1e-6；历史M3只对ordinal6有082/084参考，其余24个不同M3输入仅由冻结数学、
当前结果schema与三轮一致性约束，不扩大为旧路径全量parity。

557系统样本：545 normal、12 warning、0 critical/unknown；最高swap 778.938116MiB/s，最长连续高值2，
未达3段thrashing门。采样current RSS峰值：parent91,111,424B、child2,971,189,248B；回执历史RSS
peak3,978,166,272B、MLX peak8,528,195,136B。口径不同，不相加；本次通过不是无压力或SLA证据。
15个推理root均exit0、每阶段fresh安静窗口通过，全部24个已见root/aux身份最终消失，锁已释放。

plan SHA=`fc72df94b88315752c0e896af1636779391b4baeee01757041b5d1134faeb28a`；
run SHA=`3ec838fbfbc68867a98496f80ee0eb34c62cb74c2a3b7467a1554ce45f176b1d`；
verification SHA=`a33ba29be93e631074b07c140a4fdbad9566b4aa9483633ab31497dcd91af13a`。
32个plan源文件和本协议已封存为33成员archive，SHA=
`56386775dd61226ba3fe7f214c89b3a55cad393bb61ed868b77bc5f6082f0435`。
不要重跑或修改本次runner/verifier/工件。当前已登记`protocols/exp-086-staged-discourse-formal.md`；
只有该固定来源任务自身通过后才称Discourse闭环完成。外部gold/context仍暂停，无commit/stage/push。

### 当前终态（2026-09-01）：EXP-085新回调接口错误，运行和完整核验未通过

用户要求下一步，已登记`protocols/exp-085-staged-website-bounded-acceptance.md`。
新路径Research/Demo先完整M1、退出/消失/安静窗口，再同任务M1回执驱动独立M3；
完整340输入、三模式、三轮九任务在538项测试和独立Approved后冻结，只执行了一次。
supervisor PID5279、exec session19771已退出1；入口`.venv/bin/python -B scripts/run_staged_runtime.py run`。
RUN=`forum-topic-emotion-web/private/validation/exp-085/attempt-1/`；UTC开始2026-08-31T16:31:17.536157，
耗时98.639333秒，run=Stopped/staged_internal_error。M1-only完成340；Research先完成340项M1，
回放6项后在第7项首次M3进度回调失败。逻辑任务1/9完成、1失败、7未启动；最终结果346条，
阶段回执686条，不能把预计算回执重复计成最终结果。没有成功M3预测。
plan SHA=`9de78c110ef9a078025df831138e5acd63d08a596e7c972d5bd13d52f04aec25`；
run SHA=`b9965aaa8340212a3e49b3d1290febe962c402aeb3e31de97a10dc336f7d4686`；
唯一完整verification=Failed/staged_lower_bound_range，exp085_complete=false、stop-required；
verification SHA=`426c3ba406ca42b13942275b8d87384a8e8e9fa71fc9629739ec6b1a0f75bf2f`。
不再次调用本次runner/verifier，不修改其绑定文件或回填缺失事件。

根因已通过冻结代码只读与无模型内存fixture复现：`staged_worker.py`的`_event(self, kind, **fields)`
收到位置参数`staged_progress`，同时`_phase_progress`转发payload的`kind=begin`，触发
`TypeError: StagedRunner._event() got multiple values for argument 'kind'`。
两个计数先在内存更新，但事件未写入journal；runtime-events中的staged_progress/failure_cost均0条。
Research的API成本下界报M1=338、dup=2、M3attempt=1、transfer=7，而原始回执只见6次transfer、
0个M3结果，且缺少第7次的原始进度事件，故独立consumer拒绝其成本证据边界。不能把0结果写成0尝试，
也不能用静态推理补造原始事件、修改verifier或把Failed降格为Passed。
测试缺口：完整API的假M3后端绕过进度wrapper，真实JSONL测试只收集事件而没有接入此回调。

进程/服务均退出：两M1子进程5357/5916 exit0，M3子进程6408 exit−15，辅助5378/5949也消失。
清理3.082763秒，末样本93覆盖全部5个已见身份；父服务已结束、锁释放。
94个系统样本均normal，无warning/critical/unknown。只读独立安全子集复算通过，但这不是整体
verification通过，也没有完成真实M3工作量，不能据此宣布旧内存问题已解决或九任务稳定性成立。
旧EXP-084的39代码依赖及原协议已在修改生产代码之前封存为40成员archive，逐字节校验，
`forum-topic-emotion-web/private/validation/exp-084/attempt-1/frozen-code.tar.gz`，
SHA=`91ed8d8b0d8d8b631c7ad440cc824cd7dde813c0dc6f997bb1b8839dbef751af`。
后续应使用archive复核旧实现，不将新app/start/UI的正常版本更新误判为旧实验漂移。
旧bridge/runtime/模型、协议及已封存结果不改；EXP-079仍未通过，Discourse仍未执行。
生产已补两阶段成本/缓存语义和阶段UI；公共worker在发布失败终态前先清理进程，避免删除窗口。
本次已按失败即停收尾，没有自动修复、重试或执行Discourse。下一步范围应限于先封存本版代码，
修正事件helper参数重名，补真实JSONL→`_phase_progress`→日志/成本的组合回归，再登记新尝试；
不再增加新模型或新机制。原EXP-079/080状态不变，外部gold/context/C2继续暂停，无commit/stage/push。

### 当前步骤（2026-08-31）：EXP-084模型分时驻留原型已完整通过

用户在EXP-083停止后要求下一步。本次新Minor协议为
`protocols/exp-084-m1-transfer-memory-prototype.md`，不修改生产网站、原模型或任何旧冻结文件。
流程仍为340项M1完成并退出后处理前7项，但第二进程只复用本次M1概率/token缓存，不再创建M1模型，
仅按原模型/路由/阈值进行M3计算。源文件hash校验仍可读取M1权重，不能声称不读M1文件或不import Torch。
成本分列338次M1、2个任务内缓存、7个跨阶段回放和至多1次M3，不把回放计成重复输入或真实forward。
结果等价与EXP-082比较；082只供独立验证，不能给新模型回填。新fingerprint绑定策略/transfer SHA。
全部旧资源门不变，单次两个串行进程、347计划回执、180秒（150工作+15清理+15封存余量）。
438项合成/集成tests及独立安全/语义审查通过后，已执行唯一一次。supervisor97702/session10752
退出0，M1进程97763与独立M3进程98230都正常exit0；辅助进程97785及全部已见身份均确认消失。
UTC开始2026-08-31T14:49:28.048493+00:00，总61.795825秒，2/2阶段、347/347回执完整。
RUN=`forum-topic-emotion-web/private/validation/exp-084/attempt-1/`，已独立verify=Passed，
diagnostic_completed=true、safety.gate_passed=true；不要重复runner/verifier或修改其绑定文件。
plan SHA=`24c1c85d7aadb8a77743203972df4652c1204f2f626ec8f2c6182116e731338f`；
run SHA=`e97540cec9a2cf87bdfe22f99c06a979c50d54603702b260a5a30551ad591d2a`；
verification SHA=`22e667dd23da182b40e5fbb876999ac7465682275258e10a8663640bf4041bd1`。

本次transfer只来自本次完整M1文件，hash=`c0a2131aaf3aab4e6e570f800009730115c045b32161db547b4fa7e64af6d428`。
七项回放概率float32逐值等于同次M1回执；与EXP-082的七项功能输出一致，最大概率差0。
成本为338次真实M1、2个任务内重复缓存、7条跨阶段回放、1次M3，不能将raw cache_hit的2+7称作9个重复输入。
第二进程就绪时m1_instance_absent=true、m1_backend_calls=0；该proof是ready时点观察，
结合无M1 load/predict阶段标记、原型禁止调用路径及回执m1_attempts=0描述此次执行，不当作全程heap普查。

48条阶段记录完整闭合，首次forward已结束。MLX累计peak8,528,195,136B，与EXP-082相同。
阶段历史RSS peak2,142,502,912B，高于EXP-083记录的1,796,702,208B；不能宣称绝对RSS下降。
RSS和MLX active/cache/peak口径不同，也不能相加当整机物理内存。即使本次资源门通过，
也不能把去掉第二M1实例单次归因成旧故障根因已经修复。

59系统样本：2warning（index55/56）、0critical、0unknown/invalid。≥100MiB/s仅index56
结束的一段，269.275804407MiB/s；相邻55/57分别81.025592921/69.007576003MiB/s，最长连续1，
未达thrashing门。该高值间隔跨加载尾部/adapter/分词/forward入口，不能独占归因一个函数。
两个安静窗口和全部退出门通过。所有工件0600并Git-ignored，无训练/新gold/上传/commit/push。

结论：同次M1回执驱动的独立M3原型在本次有限序列中功能等价且通过原安全门。
它尚未集成网站，也未覆盖完整340项Research、Demo或九任务序列；原EXP-079未完成、EXP-080未执行。
下一步应扩展到完整快照/三模式的分阶段执行与网站任务接口，并先验证成本、回退、取消/删除、
输入身份和功能等价，再进行新的有界验收；不把本次短原型直接晋升为生产或Phase C完成。

### 当前步骤（2026-08-31）：EXP-083已因连续换页停止，独立审核通过

用户在EXP-082完成后要求继续。已登记
`protocols/exp-083-m1-prelude-memory-diagnostic.md`：一次有限序列，完整340项M1-only
正常退出并通过原安静窗口后，再运行相同7项Research阶段诊断。入口保持直接子进程，不同时改HTTP。
最多两串行进程、347个回执、1次M3，总180秒（工作150、清理15、封存余量15）。
旧代码/旧协议/旧run均不改；EXP-083使用新driver、薄journal路径适配器和独立verifier。
370项合成/集成tests、方法审查和执行器安全审查通过。唯一一次已经终态，supervisor PID94093、
exec session7602已退出1；M1前置child94163正常退出0，Research child94645取消退出−15，
辅助进程94195/94718及全部已见身份均确认消失。开始UTC2026-08-31T13:59:53.286692+00:00，
plan SHA=`daf611f054a0f870491651798b2f7bd24fbfb30181c41ea88776df14f18fe559`。
模块`private/validation/exp-083/attempt-1/`已封存。运行61.583231秒，M1完成340/340
（338次计算+2缓存），Research6/7回执后取消，合计346/347回执、1/2阶段完成。
run=Stopped / swap_thrashing；独立verify=Passed，但diagnostic_completed=false、safety=false。
run SHA=`1b566d0007ae3bbb6bcfa194472c77ab50ab27cd6ebebec4f0373826f488e417`；
verification SHA=`7276798a09f641f36ba9017af8768cc786c39e4564cd1a5974a3bd7880363a09`。
不重复启动runner/verifier，不修改任何本次绑定代码、协议或旧工件。

59个系统样本含3warning（index54/55/56）、0critical、0unknown/invalid。
达到连续高swap门的区间结束index55/56/57，速率605.465578/281.388891/243.585264MiB/s；
相对run区间分别[57.221111,58.322536]、[58.322536,59.373128]、[59.373128,60.432562]秒。
第一段完全在base_load，第二段跨加载尾部/adapter求值/分词/首次forward入口，第三段位于
first_forward已开始且未确认结束的窗口。触发样本57已经normal；这是swap代理门，不是critical或OOM证据。

阶段journal60条完整，无半行或error事件；基座、LoRA、adapter/head和tokenization已有end。
最后seq59为ordinal6的first_forward begin，未保存end/第七条结果。最后active/peak
8,074,361,888B、cache4,644B均来自前向入口；取消前向的最终峰值和结果未知，不能写成8.074GB峰值。
这些已完成加载阶段的MLX读数与EXP-082相同，但不能把跨阶段swap累计量归因一个函数。
M1前置任务已正常退出且Research前的新10样本安静窗口通过，没有两个推理任务并发；
Research进程内部仍按原设计保留M1和M3。清理开始t60.474940、R退出t60.619185，
最后t61.540810的样本确认4个seen keys全部absent；清理耗时1.067092秒。

已返回M1结果与原源快照一致，Research前六条也与EXP-082已返回的M1结果一致（最大差0）；
没有新的M3结果可比。Research回执成本下界为M1计算6、M3回执成本0，但阶段证明已进入M3，
不能把0个M3结果回执写成没有调用M3。序列未通过，不是记录审核失败，也不是模型内部异常的确诊。
EXP-082成功而EXP-083停止只构成这两次观测；时间、系统状态和前序负载未受控，不能单次因果归因。
后续需要处理加载到首次前向这段的内存/换页压力，不再同条件自动重跑。
原EXP-079未完成、EXP-080未执行；本次不会自动把短序列通过当作九任务验收或推进Discourse。

### 当前步骤（2026-08-31）：EXP-082单次阶段诊断已完成并独立通过

用户在只读定位后继续要求“下一步”，已登记
`protocols/exp-082-first-m3-memory-diagnostic.md`。只执行一个推理进程、原快照前七项，
Research/seed42/audit0/M3预算1；总180秒，工作150秒、清理15秒、监控封存预留15秒。
新driver直接复用原ProcessRunner和Monitor；新child只观察冻结Python阶段，不改旧runtime/模型。
child、driver、独立verifier全部324项tests通过，parent安全审查Approved，阶段契约兼容。
唯一一次已完成：supervisor PID90973、exec session69878已退出0，child PID91040正常退出0；
辅助进程91074和所有已见身份均已确认退出。没有HTTP服务或后续模型运行。
UTC开始2026-08-31T13:00:47.750242+00:00；plan SHA
`896067922d9029e35ccdf1eeb44976bb22fc96a71ce0791424861d16547a5298`。
模块`private/validation/exp-082/attempt-1/`已封存：run=Completed，7/7回执，耗时26.562390秒，
7次M1、1次M3均成功；64条阶段记录闭合。parent退出后独立verify=Passed，
diagnostic_completed=true、safety.gate_passed=true；不要再次运行runner或覆盖verification。
run SHA=`10125ffc1c22bd020dc75f2c05647464be22ea90f8d509b7e3f7e78eb9d4e952`；
verification SHA=`0d98fef8a5662bace2299bd7f11f9d17c99f13b14dca4a7c3765f4fe2ea3deb6`。

本次主要观测：base_load完成后MLX active为8,044,936,200B（相对前值增加8,044,936,192B），
adapter/head求值后8,074,361,888B（增加29,425,688B），first_forward后的累计peak为
8,528,195,136B（相对前值增加453,833,248B）。forward结束active8,074,361,912B，
cache491,587,620B。RSS/active/cache/peak口径不同，不能直接相加当物理内存。
本次MLX记录没有完整基座双份驻留的证据，但不排除未覆盖的分配或重建此前失败的峰值。

25个系统样本：2warning、0critical、0unknown/invalid。≥100MiB/s的swap区间共有3个，
结束于样本20/21/23，速率196.310898/588.254606/333.476438MiB/s；中间样本22仅4.768115，
最长连续高值2，未达3间隔thrashing门。warning样本20/21时点分别落在base_load/first_forward，
但swap速率覆盖相邻采样间隔，不能把整段交换量独占归因于该时点所在函数，也不是精确2秒warning。

结论：原模型在此次七项短诊断中完成首次M3，未复现critical；这不是资源故障已修复。
本次无前置完整340项M1任务，采用直接child入口并新增trace/fsync，前序负载、系统状态、
观察开销未受控，不能据此认定这些差异中的某项解释了与079的差别。后续需对齐完整流程的
运行条件再判断如何处理资源约束；不以本次成功自动重跑九任务或启动Discourse。
原079attempt3保持资源停止，080未执行；诊断不授权自动整轮重跑或Discourse。

### 最新执行点（2026-08-31晚）：EXP-079 attempt3 再次资源停止，已封存

用户要求关闭占用应用并继续，随后明确确认“已经将占用应用退出”。只读进程核对
Chrome/QQ/WeChat/Obsidian/Music/Mail/Notes/Messages/Ghostty 主进程均已退出；
10个系统样本均normal、9间隔swap I/O为0。完整280项tests通过。
attempt2已逐字归档25文件，SHA见新的
`protocols/exp-079-reduced-background-attempt-3.md`。仅修复已见存活进程的原始行留痕，
旧sample36与Failed核验未改。9任务×340条、1800秒及模型/预算/安全门均不变。

attempt3运行61.144110秒，因critical_memory_pressure停止。M1完成340条（338计算+2cache），
Research仅6条回执后取消，7任务未开始；1/9完成。driver session74242退出1。
58系统样本1critical，0warning/unknown/invalid；最大swap292.029245MiB/s，连续高值2间隔，
不满足thrashing proxy。清理1.243173秒，4个已见进程均确认退出；无orphan或并发超限。
服务85867/session49606在只读确认无活动任务后已正常停止，不要重启封存bench。

随后独立verification为Passed，但exp079_complete=false、stop-required，运行安全门false。
run SHA=`990efbb28bf91025b6554d3756e2f471a8edd8eac8a1962535cb98384e2a0722`；
verification SHA=`2f078610f6ff4be0d17fdd047cbca0f6d156425e577ddba34cbe1d30581990ec`。
这是可复核的停止记录，不是稳定运行通过；旧attempt2 Failed没有修复或晋升。
`pre-execution.json`记录用户确认和资源前检；新报告为模块
`private/reports/phase-c1-attempt3-reduced-background-report-2026-08-31.md`。
080绑定已迁移到079attempt3，原9项tests通过，但安全前提未成立，仍未执行。
081只追加attempt2，full_operational_completion=false；旧attempt1不覆盖。
不再同条件自动重跑。下一步需明确Research峰值内存定位或新运行环境，不能直接跳到080。
无训练、旧gold访问、上传、stage/commit/push。

### 后续只读定位（2026-08-31）：下一项应为单次分阶段内存诊断

用户“下一步”后，本轮只读检查现有工件、实际runtime、已安装库源码及模型文件头，
没有加载模型、读取tensor值/原文/gold、修改代码或执行新的验收。
实际`oof-router/runtime_exp066.py`与父attempt2 frozen副本逐字一致，SHA仍为`4cd1c226…e689`；
attempt3的22项代码依赖和9项封存工件hash再次核对一致。

- 可确认的调用路径：`topicweb/inference_process.py:290–309`先M1再route，首次请求M3时才调用
  `m3_factory()`。原快照ordinals0–5路由资格均false，ordinal6为true；两次Research只有前6条回执。
  这支持将排查集中于首个应触发M3的条目处理区间，但没有函数入口事件，不能认定具体加载/前向阶段。
- M3构造（`runtime_exp066.py:244–321`）先校验小型adapter/head，再调用
  `mlx_lm.load(base,lazy=False)`、插LoRA并装载其权重。已安装`mlx_lm/utils.py:415–418`
  在替换权重后求值基座参数。只读Safetensors头部统计：基座398 tensors、4,022,468,096参数，
  BF16 tensor payload 8,044,936,192 bytes（7.49243GiB）；adapter F32为29,360,128 bytes，
  head F32为61,464 bytes。这是文件布局规模，不是实测RAM峰值。
- 已安装MLX0.32.0的`mlx/include/mlx/memory.h:36–40`明确memory limit是图求值的guideline，
  不是全进程瞬态硬上限。bridge在M3构造返回后才调用guard.check（395–401），结果完成后再检查。
  因此设置10GB不保证加载期间不会先出现整机critical；它也不证明此次实际超过了10GB。
  512MiB cache上限只管可回收缓存，不包括活动权重。
- 未找到完整8GB基座被复制两份或全体转F32的静态证据：MLX Module.update替换array引用，
  LoRALinear.from_base复用原linear；默认随机初始化是惰性的，不能直接算作另一套已分配权重。
  classifier调用backbone.model再接六标签head，不计算完整词表logits；cache=None时没有跨请求
  维护的KV cache。普通临时分配、原生I/O或内部算子峰值仍未观测，不能据此排除所有内存问题。
- 缺失的关键证据：ready只证明M1就绪；native stdout/stderr被丢弃，M3阶段没有持久化标记。
  六条回执中的MLX0只属于M3尚未返回结果的前段，不是最终峰值。现有记录不能区分MLX import、
  基座加载、LoRA装配、tokenization或首次forward；ordinal6也可能仍在M1步骤或结果尚未持久化。
  两次最后一条已保存回执到critical相隔2.858073s/2.752797s；这不是函数执行时长。
  不能从整机critical单独归因M3，也不能把尚未持久化的m3_attempts当作0。

官方[MLX memory limit说明](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_memory_limit.html)
及[惰性求值说明](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html)
与本地源码交叉核对；在线文档为0.32.2，本次实际库仍为0.32.0，未升级。

最小下一步：另行登记一次诊断，最多一个推理进程、原快照前7项（前6个M1前缀及首个路由对象），
只回答首次M3停在哪个阶段。先保存阶段开始/结束与可取得的MLX active/cache/peak，保留原整机
pressure/swap、RSS、退出和身份门；不输出原文、tensor值或新科学性能指标。阶段记录先做合成测试，
诊断仍须有单次预算、独立工件且失败即停；不把它当attempt4整轮重跑，也不因诊断成功自动启动080。
本轮只确定诊断范围，未创建或执行该模型诊断；未量化、改模型/阈值、调cache或放宽门限。

Date: 2026-08-30

Workspace: `/Users/phoenix/Assistant/NeuroScience`

Project: `projects/llm-forum-text-emotion-recognition`

当前交接点：Phase A 已由 `DEC-SO-PHASE-A-CLOSEOUT-V1` 收口为
`Closed with partial success`。EXP-068 原始科学终态保持 `Failed or incomplete`；本地
headless/CLI research demo 已验证，deployment-efficiency evidence 未建立。

Phase B 已由 `DEC-SO-PHASE-B-REPRESENTATION-V1` 登记为
`LoRA 表征变化与功能依赖分析`。EXP-069 representation extraction preflight 已完成：
15 个 fold workers 与 assemble 全部完成，模型侧 parity errors 均为 0。Attempt-4 final
verification 因 verifier 混合两个 `manual_logit` 统计口径而保留为 Failed；model-free
verification attempt 2 拆分指标后 25/25 Passed，独立 NumPy head replay 最大误差为
`7.62939453125e-06 < 1e-5`，未重跑模型或修改 source snapshot。EXP-070 方法与 no-result
preflight 也已完成：synthetic tests 15/15、independent verifier 24/24 Passed。
Extraction-only protocol、config、runner、verifier 与 tests 已冻结，synthetic tests 11/11
Passed。Formal worker extraction 已完成 16/16：Frozen base 与 M3 seed 42 各保存 3,360 rows
× 9 points；M3 seeds 43/44 各自 5/5 folds 保存 3,360 rows × 3 points。全部 worker 的 runner
replay、pre-LoRA parity 与 standard-HF parity 均为 0。Seed 44 五折独立 float64 head replay
最大值为 `2.3313519861289933e-06 < 1e-5`；float32 最大值
`1.239776611328125e-05` 只按冻结规则记录为 diagnostic。Frozen assemble 已完成；public
`extraction.json` 状态为 `CompletedAwaitingVerification`，绑定 16 workers、16 matrices 与
private `extraction-manifest.json`。
原 terminal verifier 的跨口径 token-digest 等值条件和 float32 累加条件已在执行前登记为
verifier-only recovery。Append-only verification attempt 2 已执行并 28/28 Passed：runner MLX
最大误差为 `0.0`，float32 diagnostic 最大值为 `1.239776611328125e-05`，float64 gate 最大值为
`2.409579250794991e-06 < 1e-5`。Source snapshot 在 replay 前后保持
`cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad`；未重跑模型、worker
或 assemble，也未修改 source。Formal extraction 已完成。EXP-070 probe consumer、独立
verifier 与 34 项 synthetic tests 现已冻结；
no-result static verifier 25/25 Passed，completion 将 `formal_probe_authorized=true` 绑定到
formal config `sha256=16a66d187bc16c46997e0ab7d729848e03a02bcd088139964debc370d6e5067c`。
Formal probe `initialize` 已完成：public 只有 `run-claim.json`，private 只有
`input-manifest.json` 与 `folds/`。`fit-fold 0–4` 各封存 864/864 binary fits，共 4,320 fits；
aggregate elapsed 为 `10,604.71 s`，最大 peak RSS 为 `1.554 GB`。五个 fold 的
outer-heldout labels 在各自 `fit-fold` 阶段均未解码。`assemble` 随后首次读取全部 3,360 行
train-only outer-heldout labels，并计算 aggregate metrics、三组 label-shuffle controls 和 2,000 次
paired duplicate-component bootstrap。Runner 写入 private `probe-manifest.json` 与 public
`probe.json`，状态为 `CompletedAwaitingVerification`。Seeds 43/44 的 H27/HF votes 均通过，三组
shuffle controls 均未触发 negative-control failure，assemble 的 provisional state 为 2。

执行前审计发现 frozen formal verifier 的 public-privacy predicate 会把 exact-bound
`claim_boundary` 中的方法术语 `component-disjoint` 误判为 component ID。旧 `formal-verify`
尚未执行；当前没有实际 private-data exposure。Append-only verifier-only recovery 已冻结为
verification attempt 2，synthetic tests 12/12、static checks 18/18 Passed，no-result completion
为 `Complete`。Recovery `formal-verify` 随后完成 44/44 independent checks；result digest 与
assemble 完全一致，negative-control failure=False，state 2 `Representation effect replicated`
已通过结果验证。Recovery `formal-complete` 完整重放同一 verification 并写入 terminal
`probe-complete.json`。Source snapshot 保持 `e8e26dd0...50a8`；`formal_probe_complete=true`、
`exp070_complete=true`、`exp071_authorized=false`。EXP-070 已通过 verification attempt 2 完成。

EXP-071 已单独登记并完成 no-result preflight。Attempt 1 因相对 `--config` 路径未在 artifact
identity 序列化前规范化而 Failed；failure 与原 config 保持 append-only。Incident 001 attempt 2
只修复路径规范化并切换 fresh namespace，synthetic tests 53/53、independent static verifier
24/24 Passed，completion 为 `Complete`。静态阶段未读取 representation、row-contract value 或
probe metric value。Active formal config 已冻结并通过 runner/verifier activation gate。Formal
`initialize` 已完成；public 仅有 `run-claim.json`，private 仅有 `input-manifest.json`。Initialize
未读取 scientific values。Formal `analyze` 随后触发注册的 CKA denominator gate，状态为
Failed，error 指纹对应 `Zero or non-finite CKA denominator`。Runner 已读取 `ordinal/fold_id`
与部分 representation values，但尚未读取 9 个 AP5 values，也未写出 geometry 或 drift。
原 failure 本身不记录 condition/fold，不能单凭该文件区分零分母与非有限分母。Source snapshot 经
identity-only 重放保持 `df5e9d00...535d9`。Formal verification 和 completion 均未执行。

Incident 002 已登记为 Minor denominator diagnostic。它只按原顺序定位首个失败 pair，并报告
`norm_x`、`norm_z`、`denominator` 的类别，不保存数值或其他 drift metrics。Diagnostic
no-result preflight 已完成：synthetic 15/15、independent verifier 12/12 Passed。Active diagnostic
config 已冻结。Incident 002 已完成 independent verification（19/19 Passed）与 completion 重放，
终态为 `Complete`。已验证首个失败 pair 为 `s42:H-1 / fold 0`，`pairs_examined=1`，
`norm_x`、`norm_z`、`denominator` 的类别均为 `zero`。AP5、后续 pairs 和其他 drift metrics
均未访问或计算。原 EXP-071 保持 Failed，诊断 run.json 保留其历史状态。

## 1. 新对话先读什么

按以下顺序读取，不要只依赖本文件中的摘要：

1. 项目实验规则：`projects/llm-forum-text-emotion-recognition/AGENTS.md`
2. 本交接：`experiments/stack-overflow-emotion-gold/HANDOFF.md`
3. Phase A closeout：
   `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-a-closeout-v1.md`
4. Phase B 决策协议：
   `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-b-representation-v1.md`
5. EXP-069 verification recovery：
   `experiments/stack-overflow-emotion-gold/protocols/exp-069-verification-attempt-2.md`
6. EXP-070 layerwise probe：
   `experiments/stack-overflow-emotion-gold/protocols/exp-070-layerwise-probe.md`
7. EXP-070 formal extraction：
   `experiments/stack-overflow-emotion-gold/protocols/exp-070-formal-extraction.md`
8. EXP-070 formal extraction verification attempt 2：
   `experiments/stack-overflow-emotion-gold/protocols/exp-070-verification-attempt-2.md`
9. EXP-071 representation drift：
   `experiments/stack-overflow-emotion-gold/protocols/exp-071-representation-drift.md`
   与当前 Incident 002：
   `experiments/stack-overflow-emotion-gold/protocols/exp-071-denominator-diagnostic-incident-002.md`
10. EXP-068 synthesis 与终验：
   `experiments/stack-overflow-emotion-gold/oof-router/runs/exp-068-phase-a-synthesis/`
11. Phase A 方法：
   `experiments/stack-overflow-emotion-gold/protocols/dec-so-phase-a-inference-v1.md`
12. 当前路线：项目根目录 `research-roadmap.md` 的 `RQ-S3` 与 `RQ-S4` 条目
13. Stack Overflow C0 总实验报告：
   `stack-overflow-c0-experiment-report-2026-08-16.md`

`README.md`、`research-roadmap.md` 和 `evidence-log.md` 是长期权威记录。本文件负责
恢复执行现场，不取代它们。

## 2. 历史 RQ-S3 任务与背景

毕设题目：

> Research and Implementation of Emotion Recognition System of Forum Text Based on LLM

Stack Overflow C0 使用六标签多标签任务：

```text
love, joy, surprise, anger, sadness, fear
```

RQ-S3 当时回答：

> 在已经运行 M1 RoBERTa 后，只使用调用 Qwen 前可得的信息，能否识别少量值得升级到
> M3 Qwen3-4B Classification LoRA 的样本，从而在受控 Qwen 调用率下超过单一模型？

EXP-059 的 whole-vector oracle 证明 M1/M3 存在互补上界，但 oracle 使用 gold，不能部署。
EXP-060 的任务是验证这种互补性是否可由真实 pre-Qwen 信号预测。

## 3. 已完成证据链

### 数据与主模型

- `DATA-SO-TASK-V1`：4,800 rows，冻结为 3,360 train / 720 validation / 720 test；
  duplicate-component-disjoint。
- EXP-050：M1-M4 shared preflight，Verified。
- EXP-051 M1：RoBERTa 三 seed。
- EXP-052 M2：Frozen Qwen final-layer last-input-token + linear head 三 seed。
- EXP-053 M3：Qwen3-4B Classification LoRA 三 seed。
- EXP-054 M4：Qwen3-4B Generative LoRA 三 seed。
- EXP-055：M1/M3 validation 错误分析与不可部署 oracle。
- EXP-056：一次性 frozen test，test 此后为 `Consumed`。
- EXP-057：只读结果汇总和 Stack Overflow C0 实验报告。

冻结 test 的三 seed Macro-F1：

| Model | Macro-F1 |
| --- | ---: |
| M1 RoBERTa | `0.567459 +/- 0.007814` |
| M2 Frozen Qwen + linear head | `0.295226 +/- 0.020587` |
| M3 Qwen Classification LoRA | `0.613804 +/- 0.025733` |
| M4 Qwen Generative LoRA | `0.547823 +/- 0.015312` |

结论边界：M3 明确超过 M2；M3-M1 六标签 delta=`+0.046345`，但 bootstrap CI 跨 0；
去除低支持 `surprise` 后 delta=`-0.010735`。M4 六标签 Macro-F1 明确低于 M3。
不能写成“LLM 全面优于 encoder”，也不能从这些行为结果推出内部情绪机制。

### RQ-S3 系统支线

```text
EXP-058 paired M1/M3 train OOF
-> EXP-059 calibration + selective prediction + oracle
-> EXP-060 pre-Qwen deployable router
```

EXP-058：

- 五个 duplicate-component-disjoint folds，每折 672 rows。
- M1/M3 各五个折外模型，共为 3,360 rows 产生配对 raw logits。
- paired artifact SHA-256：
  `e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc`
- final verifier：`26,989/26,989 Passed`。
- 只访问 train；没有计算 performance、calibration、oracle 或 router。

EXP-059：

- M1/M3 均选择 identity calibration。
- selected OOF 六标签 Macro-F1：M1=`0.598919`，M3=`0.637843`。
- 去除 `surprise` 后：M1=`0.718703`，M3=`0.710509`。
- M1 max-entropy abstention 在约 90% coverage 时 Hamming-risk reduction=`20.01%`，
  bootstrap interval=`[16.80%,23.24%]`，属于边界信号。
- M3 margin abstention 在约 80% coverage 时 reduction=`31.57%`，interval=
  `[27.79%,35.74%]`。
- whole-vector oracle 只在 `313/3,360` rows 选择 M3，但相对 M1 六标签/五标签
  Macro-F1 上界为 `+0.109930/+0.087472`；这是不可部署 headroom。
- final verifier：`4,684/4,684 Passed`。

EXP-060：

- protocol 保持 frozen；no-result preflight 历史保持为 synthetic tests `7/7`、runner
  `25/25`、independent verifier `66/66 Passed`；
- formal contract suite `23/23 Passed`；formal independent verifier
  `4,412/4,412 Passed`，最终状态为 `Verified Pass`；
- selected policy=`logistic_router`，实际调用率=`14.9107%`，即 `501/3,360` rows；
- 相对 M1-only，六标签 Macro-F1 delta=`+0.040168`，五标签 Macro-F1
  delta=`+0.006097`，Hamming-loss delta=`-0.004365`；
- router target discrimination：PR-AUC=`0.318653`，ROC-AUC=`0.850804`；
- 2,000 次 duplicate-component bootstrap 95% intervals：调用率
  `[13.6673%,16.2172%]`，六标签 Macro-F1 delta=`[+0.009891,+0.071126]`，
  五标签 delta=`[-0.007688,+0.019733]`，Hamming-loss delta=
  `[-0.006332,-0.002515]`；
- 点估计决定冻结的 development gate；interval 只限定稳定性，五标签区间跨 0；
- 证据严格来自 fully nested `DATA-SO-TASK-V1` train OOF；没有访问 validation/test、
  原始文本或运行 M1/M3 model forward。

该 `Verified Pass` 只支持冻结 seed-42 M1/M3 pair 的开发阶段路由可行性，不是独立 test
结果，也不能外推为通用部署收益。

## 4. EXP-060 冻结合同

### 数据边界

- 只允许 `DATA-SO-TASK-V1` train OOF 3,360 rows。
- validation 禁止用于本实验；test 已消费，绝对禁止重新打开或评分。
- 不加载模型 checkpoint，不运行 M1/M3 forward，不重新训练 M1/M3。
- 不读取原始论坛文本，不启动 context、M2、M4 或新模型分支。

正式 row-level 输入必须是：

```text
experiments/stack-overflow-emotion-gold/oof-router/private/
  exp-058-paired-oof-production/paired-oof.npz
```

使用 EXP-058 raw logits，并从 EXP-059 public calibration record 冻结两边均为 identity。
不要把 `cross-fitted-calibration.npz` 中已有的 threshold-derived 字段直接当 formal router
输入，也不要把 `oracle_choose_m3` 当正式 target。

### Nested cross-fitting

对每个 outer fold `k`：

1. outer held-out 为 fold `k`，其余四折是 router training partition。
2. 对这四个 training folds 分别做 inner held-out：用另外三折选择 M1/M3 threshold，
   再为该 inner fold 构造 threshold-derived features 和 router target。
3. 拼接四个 inner-held-out partitions，拟合 scaler 与 logistic router。
4. 用全部四个 outer-training folds 选择 M1/M3 threshold，再构造 outer fold `k` 的
   features、target 和完整 M1/M3 predictions。
5. 只在 outer fold `k` 上生成 router score；重复五次并恢复 EXP-058 source order。

这是 EXP-060 相比原始三步建议增加的关键防泄漏修正。不得退回到“直接对 EXP-059
cross-fitted rows 再套一层普通五折”的实现。

### Router target

每条样本比较完整六位预测向量的 row Hamming loss：

```text
target=1  iff  Hamming(M3, gold) < Hamming(M1, gold)
target=0  otherwise
```

平局选 M1。M3 和 gold 只能生成 supervised outcome，不能进入 runtime feature matrix。
禁止逐标签混合 M1/M3。

### 14 列 feature whitelist

顺序必须完全固定：

```text
m1_probability_love
m1_probability_joy
m1_probability_surprise
m1_probability_anger
m1_probability_sadness
m1_probability_fear
m1_mean_binary_entropy
m1_max_binary_entropy
m1_minimum_threshold_margin
m1_predicted_cardinality
m1_highest_probability
m1_lowest_probability
character_length
m1_token_length
```

禁止：任何 M3 值、gold/correctness/oracle/disagreement、sample/component/fold ID、raw
text、validation/test statistic、M3 token length。IDs 只能用于对齐、fold integrity 与
component bootstrap，不能作为模型列。

### Policies 与调用率

- R0：M1 only。
- R1：M3 only。
- R2：M1 maximum entropy。
- R3：M1 threshold proximity。
- R4：`StandardScaler + LogisticRegression`，L2、`C=1.0`、balanced、liblinear、
  `max_iter=1000`、`random_state=42`。
- 不做 C grid，不增加 MLP/XGBoost/tree ensemble。
- 另做 100 次 deterministic component-aware random-routing diagnostic，不作为候选 policy。

Frozen nominal Qwen call rates：

```text
0%, 5%, 10%, 15%, 20%, 30%, 50%, 100%
```

cutoff 只可在 outer router-training scores 上确定，再应用到 held-out fold。cutoff ties
全部 route；报告 actual call rate，不能按 held-out scores 排序来强制精确调用率。

### Gate

只从 actual Qwen call rate `<=20%` 的点中按冻结顺序选择 candidate。相对 fully
cross-fitted M1-only，policy 必须同时满足：

1. six-label Macro-F1 gain `>=0.01`；
2. five-label Macro-F1 gain `>=-0.005`；
3. Hamming loss increase `<=1e-12`；
4. 至少一个非 `surprise` 标签 F1 gain `>=0.005`。

R2-R4 任一通过，deployable-routing feasibility 才通过。R4 是否超过 simple heuristics
单独报告；若 heuristic 通过但 R4 不通过，只能支持简单路由，不能声称 learned router 有
增量价值。

对选择点做 2,000 次 duplicate-component bootstrap，seed=`20260817`，报告 95%
percentile intervals。点估计决定 development gate；interval 只决定是否可写成稳定信号。
这仍不是独立 test。

## 5. 新对话的下一项工作

EXP-070 已通过 recovery verification attempt 2 完成。当前没有自动执行的下一门实验：

1. 保持 source formal run、五折 bundles、assemble、verification 和 completion append-only；
2. 保留 state 2 的 train-only outer-heldout linear-accessibility claim boundary；
3. 不把 probe 结果改写成 causal representation、emotion neuron 或 human mechanism；
4. EXP-071 只有在另行登记方法、输入、资源和执行门后才能启动，本次 completion 不构成授权。

不要运行旧 frozen verifier，也不要重跑 extraction verifier、model、worker、probe folds 0–4 或
assemble。Recovery verification 与 completion 必须分步写入 fresh append-only root。

Phase A 与 EXP-069 所有 terminal 目录保持 append-only；不要重跑 EXP-067、EXP-069 workers
或 assemble。C0 test 已消费，Phase B 禁止读取 test text、labels、predictions 或 test-gate
artifacts。

## 6. 已冻结并实现的 formal 细节

以下是 formal config/测试中已冻结的约束，不得在结果后调整：

- component-aware random routing 在 multi-row component 下如何达到最接近的 matched row
  count，以及 overshoot/tie policy；
- threshold grid 精确为 `0.05..0.95 step 0.01`，tie order 为 Macro-F1、Hamming、离 0.5
  最近、较低 threshold；
- candidate operating-point tie order：最高 six-label Macro-F1、最低 Hamming、较低 actual
  call rate、较低 nominal rate；
- routed-system uncertainty 如何从被选 family 的最终概率与 nested threshold 计算；
- PR-AUC/ROC-AUC 在某 outer fold target 缺少类别时的预登记处理：停止或明确记为 undefined，
  不能临时改 fold；
- public/private schema、浮点比较 tolerance 与 artifact modes。

formal 启动前的冻结 stop rules 是：若真实 nested target 出现单类 outer-training
partition、NaN/inf、component leakage、输入 hash drift、formal output 目录非空或
unexpected validation/test path，立即停止，不得用改 seed、改 C、改 fold 或改 target
绕过。正式运行与终验均已按这些规则完成；这些规则继续作为产物审计边界保留。

## 7. 环境与资源

Formal router 使用 CPU 环境：

```text
/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python
Python 3.10.20
NumPy 2.2.6
scikit-learn 1.7.2
```

预算：formal analysis <=30 min，independent verification <=30 min，peak memory <=4 GB，
API/GPU cost=0。正式 analysis wall time 约 `28.16 s`、peak RSS 约 `0.200 GB`；它只拟合
轻量 logistic router，没有重新训练 4B Qwen。

## 8. Append-only 与隐私

- 已完成 run 目录 append-only。不要覆盖或“整理”历史失败记录。
- 不要再次运行 EXP-060 preflight runner 到现有
  `runs/exp-060-pre-qwen-router-preflight/`；该目录已完成并验证，runner 会拒绝覆盖。
- 不要再次运行 EXP-060 formal runner 到现有 `runs/exp-060-pre-qwen-router/` 或覆盖
  `private/exp-060-pre-qwen-router/`；正式 public/private 产物已完成并验证。
- private row-level outputs 位于 `oof-router/private/exp-060-pre-qwen-router/`，目录
  mode `0700`、文件 mode `0600`，且必须保持 Git ignored。
- public artifacts 禁止逐行 ID、fold、gold、logits、probabilities、features、targets、route
  scores/masks、predictions 或原文。
- test 已消费。任何“为了确认 router”重新读 test 的做法都是 test leakage。
- validation 已参与模型开发；EXP-060 正式主证据只来自 train OOF。

## 9. 已知事故，不要重复

- EXP-058 attempt 1：把六位 binary vector 误当标签名列表；修正记录已保留。
- EXP-058 final attempt 1：private fold parent mode 为 `0755`；收紧到 `0700` 后通过，
  paired hash 未变。
- EXP-059 final verifier attempt 1：把 `hamming_risk` 映射到不存在的 classification key；
  正式产物未重跑，修订 verifier 后通过。
- EXP-060 设计审查发现二层 threshold leakage 风险，因此冻结 nested recomputation。
  不得为了代码简单取消这个修正。

## 10. Git 现场

交接时：

```text
branch: codex/exp061-exp062-preflight-configs
HEAD: 50ce970e5794867cbbd89c1af600ddbac39ec577
remote: origin/codex/exp061-exp062-preflight-configs
remote status at transition start: synchronized
```

Commit `50ce970` 已归档并推送 EXP-064 至 EXP-068 的 105 个公共 Phase A 文件。Phase A
closeout、Phase B protocol、本 HANDOFF、experiment README 与 research roadmap 是当前衔接
步骤的新工作，尚未 commit 或 push。

工作树另有用户已有的 IELTS PDF 与 context-recovery source-preflight records。它们不属于
本衔接步骤，不得暂存或修改。

不要 reset、checkout 或删除这些文件。不要使用 `git add .` / `git add -A`。若用户之后要求
提交，先重新查看完整 status，再只暂存明确的项目公共路径；绝不能提交 `private/`、原始论坛
文本、模型权重或 checkpoint。

## 11. 当前事实状态

```text
RQ-S3 router replication: 2/2 prospective seeds Passed
Phase A lifecycle: Closed
Phase A closeout outcome: Closed with partial success
EXP-068 frozen decision: Failed or incomplete
EXP-064 bundle: Complete, verification 30/30 Passed
EXP-065 selected attempt: attempt-2 Complete, verification 30/30 Passed
EXP-066 selected attempt: attempt-2 Complete, verification 35/35 Passed, CLI open
EXP-067 attempts 1/2: Failed by preregistered RSS gate, benchmark incomplete
EXP-068: Complete, verification 20/20 Passed
System classification: Verified local research demo
Deployment-efficiency evidence: Not established
Phase B protocol: Registered under RQ-S4
EXP-069 design: Complete, synthetic tests 15/15 Passed
EXP-069 static runner: CompletedAwaitingVerification
EXP-069 independent static verifier: Passed, 14/14
EXP-069 model/forward access in static: False/False
EXP-069 validation/test access in static: False/False
EXP-069 base attempt-2: Failed before model load, FileNotFoundError
EXP-069 base attempt-3: Complete, independent verifier 23/23 Passed
EXP-069 base max errors: M2 HF=0.0, standard HF=0.0
EXP-069 base resources: 41.46 s, MLX peak 8.21 GB
EXP-069 base M3/validation/test/metrics access: False/False/False/False
EXP-069 fold workers: 15/15 Completed, all recorded parity errors=0.0
EXP-069 aggregate resources: 294.04 s, MLX peak 8.51 GB
EXP-069 attempt-4 final verification: Failed, preserved metric-contract incident
EXP-069 verification attempt-2: 25/25 Passed; NumPy head replay=7.62939453125e-06
EXP-069 overall: Complete via attempt-5-verification-recovery; no model rerun/source mutation
EXP-070 method: Frozen; full extraction owned by EXP-070, smoke fixtures excluded from fitting
EXP-070 synthetic tests: 15/15 Passed
EXP-070 no-result preflight: Complete, independent verifier 24/24 Passed
EXP-070 formal extraction implementation: Frozen, synthetic tests 11/11 Passed
EXP-070 Frozen base: Complete, 3,360 rows x 9 points, M2-HF/standard-HF errors=0.0
EXP-070 Frozen base resources: 2,032.24 s, MLX peak 8.24 GB, resume_count=0
EXP-070 M3 seed 42 / fold 0: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 0 resources: 3,289.41 s, MLX peak 8.60 GB, resume_count=1
EXP-070 fold-0 independent affine replay: float32=1.049041748046875e-05; float64=2.086469194750862e-06
EXP-070 M3 seed 42 / fold 1: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 1 resources: 2,085.12 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-1 independent affine replay: float32=9.5367431640625e-06; float64=1.5347208552896063e-06
EXP-070 M3 seed 42 / fold 2: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 2 resources: 2,093.59 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-2 independent affine replay: float32=7.62939453125e-06; float64=1.5044781136452912e-06
EXP-070 M3 seed 42 / fold 3: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 3 resources: 2,578.34 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-3 independent affine replay: float32=1.049041748046875e-05; float64=1.7814840784780017e-06
EXP-070 M3 seed 42 / fold 4: Complete, 3,360 rows x 9 points, runner/parity errors=0.0
EXP-070 M3 seed 42 / fold 4 resources: 2,151.06 s, MLX peak 8.60 GB, resume_count=0
EXP-070 fold-4 independent affine replay: float32=8.106231689453125e-06; float64=2.0908623792337266e-06
EXP-070 M3 seed 43 / fold 0: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 0 resources: 2,124.92 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold0 affine replay: float32=1.1444091796875e-05; float64=1.912518955649034e-06
EXP-070 M3 seed 43 / fold 1: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 1 resources: 2,380.40 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold1 affine replay: float32=1.1444091796875e-05; float64=2.409579250794991e-06
EXP-070 M3 seed 43 / fold 2: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 2 resources: 2,229.21 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold2 affine replay: float32=1.1444091796875e-05; float64=2.3480084774263332e-06
EXP-070 M3 seed 43 / fold 3: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 3 resources: 1,943.42 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold3 affine replay: float32=1.1444091796875e-05; float64=2.0202858195261797e-06
EXP-070 M3 seed 43 / fold 4: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 43 / fold 4 resources: 2,258.69 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed43/fold4 affine replay: float32=7.62939453125e-06; float64=1.7818263131630374e-06
EXP-070 M3 seed 44 / fold 0: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 0 resources: 2,305.14 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold0 affine replay: float32=1.049041748046875e-05; float64=1.8554483744992467e-06
EXP-070 M3 seed 44 / fold 1: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 1 resources: 2,300.78 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold1 affine replay: float32=1.049041748046875e-05; float64=2.1061606059191718e-06
EXP-070 M3 seed 44 / fold 2: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 2 resources: 2,048.08 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold2 affine replay: float32=1.049041748046875e-05; float64=2.3313519861289933e-06
EXP-070 M3 seed 44 / fold 3: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 3 resources: 2,099.80 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold3 affine replay: float32=1.239776611328125e-05; float64=1.7293328546941211e-06
EXP-070 M3 seed 44 / fold 4: Complete, 3,360 rows x 3 points, runner/parity records=0.0
EXP-070 M3 seed 44 / fold 4 resources: 2,035.08 s, MLX peak 8.60 GB, resume_count=0
EXP-070 seed44/fold4 affine replay: float32=9.5367431640625e-06; float64=1.9140310225651547e-06
EXP-070 formal assemble: Complete, status=CompletedAwaitingVerification, 16 workers/16 matrices
EXP-070 formal assemble resources: total=35,955.28 s, peak MLX=8.60 GB, private bytes=2,890,351,543
EXP-070 extraction manifest: bytes=10,612, sha256=ef8092d7c8704199d7f5d8dce0c240418fde62a0b71ff4ba07a9da45c151d347
EXP-070 public extraction: bytes=1,596, sha256=1ad33d4197517993a07e2af7f9fea14d7185e537a52376c1a400c91237793cfe
EXP-070 verification attempt-2: Passed 28/28, failed=0, formal extraction Complete
EXP-070 attempt-2 max errors: runner MLX=0.0, float32 diagnostic=1.239776611328125e-05, float64 gate=2.409579250794991e-06
EXP-070 attempt-2 snapshot: cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad, unchanged=True
EXP-070 attempt-2 verification: bytes=7,097, sha256=21e41625527702a4d8534225692a5d06fbf672add51eb67395af2a6e8803e5f5
EXP-070 attempt-2 completion: bytes=2,302, sha256=02755a7985e83e988fa5f0e3e2fbfaa22c7255ca1cfa7a8f2191ea5f222cb5cb
EXP-070 formal extraction: Complete via formal-extraction-verification-attempt-2
EXP-070 formal probe protocol: Frozen, bytes=17,832, sha256=0c4d927e9bded6d914700c587b1125de5af745ad91be92d09ae6a1569c853c29
EXP-070 formal probe runner/verifier: bytes=111,545/114,123, frozen identities Passed
EXP-070 formal probe synthetic tests: 34/34 Passed
EXP-070 formal probe static verification: Passed 25/25, failed=0
EXP-070 formal probe static completion: Complete, formal_probe_authorized=True, real probe=False
EXP-070 formal probe preflight config: bytes=30,871, sha256=ae9d729a57eaa759831292fda7fe63584a74ce40d64b9e9652a44708d183f8e5
EXP-070 formal probe config: Frozen, bytes=35,922, sha256=16a66d187bc16c46997e0ab7d729848e03a02bcd088139964debc370d6e5067c
EXP-070 formal probe initialize: Complete, sealed fold prefix=0/5
EXP-070 formal probe run claim: bytes=1,357, sha256=e1cac842098da65c04a7e8537d20ca1dc787ecdf3427244caec4b4e447742455
EXP-070 formal probe input manifest: bytes=21,305, sha256=7e34c0c1e42ce5850d0116776affd0ea96ec903a5a25aff551cd79ee8a504c7c
EXP-070 initialize label/representation/probe/metric access: False/False/False/False
EXP-070 formal probe fold 0: Sealed, 720 main + 144 shuffle fits, elapsed=2,119.20 s, peak RSS=1.507 GB
EXP-070 formal probe fold 0 convergence: main max_iter=29, shuffle max_iter=11, all within 2,000
EXP-070 formal probe fold 0 NPZ: bytes=4,664,038, sha256=b1e71ac421f5463005ce5fd7be18084e4a368ca49de8c23dc228fa75d15a380b
EXP-070 formal probe fold 0 seal: bytes=28,661, sha256=d3f156294fd37f59b4c857a685270ffae8aabdfee0814d3b723c3f126c2ada3a
EXP-070 fold 0 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 1: Sealed, 720 main + 144 shuffle fits, elapsed=2,096.91 s, peak RSS=1.554 GB
EXP-070 formal probe fold 1 convergence: main max_iter=35, shuffle max_iter=10, all within 2,000
EXP-070 formal probe fold 1 NPZ: bytes=4,664,038, sha256=0c237e0d3192225cf619758b1ebab9e881061e33269875d1930b925c0ffd3c81
EXP-070 formal probe fold 1 seal: bytes=28,661, sha256=465ada0d1f9d65243d3766e888cb2a420f6aa51ce2a2b8569eef56ef5696160e
EXP-070 fold 1 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 2: Sealed, 720 main + 144 shuffle fits, elapsed=2,121.81 s, peak RSS=1.475 GB
EXP-070 formal probe fold 2 convergence: main max_iter=29, shuffle max_iter=10, all within 2,000
EXP-070 formal probe fold 2 NPZ: bytes=4,664,038, sha256=f2af1c4ff64dad11b338030885d45cfad1233bb4fcd988b1c0f22b87f9b9a614
EXP-070 formal probe fold 2 seal: bytes=28,663, sha256=b49ac9506c254699bd0a472d51e34103f681a6b2f51ecb354c35847555687224
EXP-070 fold 2 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 3: Sealed, 720 main + 144 shuffle fits, elapsed=2,139.69 s, peak RSS=1.551 GB
EXP-070 formal probe fold 3 convergence: main max_iter=42, shuffle max_iter=10, all within 2,000
EXP-070 formal probe fold 3 NPZ: bytes=4,664,038, sha256=a79210ac75936b10ec73180d96bbebf4dc1a30a1bafb8e071936293d4528faf6
EXP-070 formal probe fold 3 seal: bytes=28,663, sha256=a0c69fade6ced6613f8ea3f0770ec62c768860cad7da0a5e6331098169f39292
EXP-070 fold 3 heldout-label/metric/bootstrap access: False/False/False
EXP-070 formal probe fold 4: Sealed, 720 main + 144 shuffle fits, elapsed=2,127.09 s, peak RSS=1.550 GB
EXP-070 formal probe fold 4 convergence: main max_iter=42, shuffle max_iter=11, all within 2,000
EXP-070 formal probe fold 4 NPZ: bytes=4,664,038, sha256=e8e23151060552f32d4043a2144d6908d687a4108e2d784a2e56966ec6f47b03
EXP-070 formal probe fold 4 seal: bytes=28,662, sha256=907f2eda0006f3ccf5e4925bff0a3e838cb866f0bdf88dbada9f3adbde577ee3
EXP-070 fold 4 heldout-label/metric/bootstrap access: False/False/False
EXP-070 probe fitting: fold prefix 5/5, 4,320/4,320 fits sealed
EXP-070 assemble: CompletedAwaitingVerification, 2,000 bootstrap replicates
EXP-070 assemble resources: elapsed=1,305.92 s, aggregate elapsed=11,910.63 s, max RSS=1.554 GB
EXP-070 public probe: bytes=53,748, sha256=977021e97a5c6a69dc6894161f4717b53c2a651919d7a5655f1b9e6ac246f89b
EXP-070 private probe manifest: bytes=68,146, sha256=307af86570048752e31c098224fe92e1d78c7e875a70f3818810e13543bc9fe0
EXP-070 seed 43 votes: H27 delta=+0.171805, CI=[+0.135379,+0.197979]; HF delta=+0.160120, CI=[+0.125498,+0.190265]; Passed
EXP-070 seed 44 votes: H27 delta=+0.170951, CI=[+0.133225,+0.197842]; HF delta=+0.153390, CI=[+0.118997,+0.183234]; Passed
EXP-070 shuffle controls: 0/3 both-prospective-seeds pass; negative_control_failure=False
EXP-070 assemble provisional state: 2, Representation effect replicated; result identity later verified by recovery attempt 2
EXP-070 assemble outer-heldout labels read after 5/5 seals: True
EXP-070 aggregate metrics/bootstrap: executed; validation/test access: False/False
EXP-070 extraction model/forward: True/True for 16 sealed workers
EXP-070 assemble model/forward: False/False
EXP-070 attempt-2 model/forward/source mutation: False/False/False
EXP-070 frozen formal verifier: Unexecuted
EXP-070 pre-verification blocker: public-privacy false positive on exact-bound method text component-disjoint
EXP-070 source probe.json historical formal-probe/EXP-070 complete flags: False/False; EXP-071 authorized=False
EXP-070 verifier recovery protocol: bytes=9,070, sha256=e908da3625297ddce317fb585b1e8cbc8b46f2c3adeda70b9375f0949f04e187
EXP-070 verifier recovery config: bytes=10,091, sha256=65f3753cb6680d8e17dfb9c3e7df4fd2fbf9274b5e404eb6d3914e6c5514b3cd
EXP-070 verifier recovery verifier/tests: bytes=62,825/39,071, sha256=c6d8def966c2742034f5a287844e1cb6189fb9648468e43bfaa3cc0ec3d4a237/725cea6f3e8b8545e352585e4563b658b7302ddc264a36544489ba3918ce9532
EXP-070 verifier recovery synthetic/static: 12/12 Passed, 18/18 Passed
EXP-070 verifier recovery static verification: bytes=4,289, sha256=abe114ec963208b8a274f976833944cd6dadb07c7f1fc5783292c90590a75829
EXP-070 verifier recovery no-result completion: Complete, bytes=1,679, sha256=1193246a23e9cbce6f9304b5e5771481575408fdf5cf3bd74d9ece68cdf97d6d
EXP-070 verifier recovery static access label/probability/representation: False/False/False
EXP-070 recovery snapshot claim: bytes=2,365, sha256=75e73e2867c8d4eae7444c1a2ff4066ec2bd705b0b29d4cea42625ddb6d55972
EXP-070 recovery verification: Passed 44/44, bytes=5,195, sha256=c39ecb65ccbc706e4a709bacb66d7e292e6d3e379cd0303bc1f1021a12dcf9cf
EXP-070 recovery result digest: 8097645dc0812c95242b517d966790c660e4571ba1196aea691b265027b7f88d
EXP-070 recovery source-verification payload digest: 0f777afadeb953e9958dbe464b7e7b0bff607e6631a738556a35fd3f77836cf3
EXP-070 recovery verified result: negative_control_failure=False, state=2, Representation effect replicated
EXP-070 recovery access label/probability/thresholds/metrics/bootstrap: True/True/True/True/True
EXP-070 recovery access representation/refit/model/forward/validation/test: False/False/False/False/False/False
EXP-070 recovery source snapshot: e8e26dd014d21371041409a78e95be147ac0bd495ad01ff5a268cafaf94b50a8, unchanged=True
EXP-070 recovery completion: Complete, bytes=2,654, sha256=0e15d164b1539d51d2917001629b9ccd5c89d0569fc863a37d61e2990aad0cd2
EXP-070 recovery source-completion payload digest: d23863930ab4f984e0eb61217833011224c9637cc0a192f6c78a44d54b4aa97d
EXP-070 recovery terminal inventory: claim + Passed verification + completion
EXP-070 formal probe/EXP-070 complete: True/True; EXP-071 authorized=False
EXP-070 final state: 2, Representation effect replicated; negative_control_failure=False
EXP-070 completion boundary: EXP-071 unauthorized there; superseded by the separate registration below
EXP-071 method: registered; method sha256=f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210
EXP-071 preflight attempt 1: Failed; relative config path normalization defect; failure preserved
EXP-071 Incident 001 attempt 2: Complete; synthetic 53/53; static verifier 24/24 Passed
EXP-071 static access representation/row-contract-value/probe-metric: False/False/False
EXP-071 active formal config: configs/exp-071-representation-drift-formal-attempt-1.json; bytes=30,400; sha256=0709c963f88242a706784f92d5033fe08eb46fb752d7e59e96607bc259d0ae35
EXP-071 formal initialize: Initialized; run-claim bytes=2,565, sha256=763fee43dbc643cb01b9a477a92ebd9a3e339bbe0740948ab055e8caabc7d937
EXP-071 private input manifest: bytes=5,769, sha256=3e5671aaad9f702d95168a05a5cb3d4d1cf0382550d1ba83196b5792ffe0ec42
EXP-071 formal access representation/row-contract-value/probe-metric: False/False/False
EXP-071 formal analyze: Failed; error=Zero or non-finite CKA denominator; failure bytes=390, sha256=3900425566334ceeac9c920e547cec252504303ac045a52a3b82820c98789d40
EXP-071 analyze access representation/ordinal-fold/AP5: True/True/False
EXP-071 source snapshot after failure: df5e9d00c2464462eb541b3416efe4d96c6836efb43d778699392fe3501535d9, unchanged=True
EXP-071 formal lifecycle: Failed; no geometry/drift/verification/completion; no EXP-071 state
EXP-071 Incident 002 diagnostic preflight: Complete; synthetic 15/15; independent verifier 12/12 Passed
EXP-071 diagnostic minimal snapshot: 28 artifacts, ee5e1c53b090f377795e17551971105f5126d070d1efc3e5e269ba3ce939cff8
EXP-071 active diagnostic config: configs/exp-071-denominator-diagnostic-formal-attempt-1.json; bytes=26,323; sha256=07f06972de22b32b9b9baea74bb000bb506ba6dac00142cc0cd2666739c13080
EXP-071 diagnostic initialize: Initialized; public run-claim bytes=2,171, sha256=10fa878949342c06c3e0e1debe2f933e9e174c70e0387be68ec0874babd33e5b
EXP-071 diagnostic input manifest: bytes=11,624, sha256=ee697f438cf0f78742167b0100c0176ddb2c4c07b7b0aebb9e0b836da1aa7936
EXP-071 diagnostic run: CompletedAwaitingVerification; run.json bytes=2,983, sha256=4ad3446b3a23fb15445790401def833830f8c8eea16d66c4e1aa105c64d2d09d
EXP-071 diagnostic manifest: bytes=16,215, sha256=c1396ec4e4df079aad1f3e9bf2de448896b6249cfa878ae44093a53e7586d211
EXP-071 verified diagnostic localization: s42:H-1, fold=0, pairs_examined=1; norm_x/norm_z/denominator=zero/zero/zero
EXP-071 diagnostic verification: Passed 19/19; bytes=3,668, sha256=d6a445112bb133ed18bffb8d860d1f4db245782df1d6c2730bbb4e363c4a7b5b
EXP-071 diagnostic completion: Complete; bytes=2,146, sha256=2f016322e863575b500ac6e82cb15aa65eeec84e28c034761cba94553f6732d1
EXP-071 diagnostic_complete=True; original_exp071_status=Failed; exp071_complete=False; recovery_authorized=False
EXP-071 diagnostic access representation/ordinal-fold/AP5: True/True/False; no exact-term persistence or other drift metrics
Test status: Consumed; forbidden for development
Phase A evidence commit: 50ce970, pushed
Transition documents: local working-tree changes, not committed
```

EXP-070 已完成，不重跑旧 verifier、model、worker、extraction assemble、probe folds 0–4、probe
assemble、recovery verification 或 completion。EXP-071 formal attempt 1 已 Failed；禁止删除
failure、同 attempt 重跑或执行原 formal verifier。Incident 002 diagnostic 已完成封存，不再重跑
diagnose、diagnostic-verify 或 diagnostic-complete。本次只确认首个 CKA 分母零值位置；原实验
recovery 或 method change 不属于该诊断。Phase B 继续保持
outerheldout OOF、test consumed、private hidden-state 和 append-only 边界。任何 layerwise
probe、drift 或 ablation 结果都不能改写为人类情绪机制或 independent-data mechanism
validation。

### 2026-08-30：EXP-075 完成，进入 EXP-072

用户已确认 post-diagnostic 新 Major EXP-075，并授权连续执行 EXP-075 → EXP-072 → EXP-074。
EXP-075 已完成，不需重跑：26/26 synthetic，75/75 geometry pairs，20/20 independent
verification Passed；`exp075_complete=true`，`exp071_complete=false`。
Public terminal 为 `phase-b-representation/runs/exp-075-degenerate-aware-geometry/attempt-1/verification.json`，
SHA256=`0b2d73bd8775881e43f15578296458dfb541c0be1fe50f3eff71070cfd672468`。
H-1 的五折 CKA 均为 null/zero_centered_variance；九点 Spearman 为
null/undefined_cka_input；其他 70 个 CKA 有定义，pre-LoRA sanity 通过。
Results digest=`35342caaa55116f36b81a90bae7158c5069de045ee612a07a97f7e700127e46b`。

EXP-072 和 EXP-074 独立协议已登记。EXP-072 固定 15 个完整 A0 replay 后再执行 55 个
消融 workers，每个 fresh process；全部预测封存后才评分。不需要逐步骤授权，遇到实际
失败或方法变化仍停止。Context/C2 暂停、EXP-073 可选。

EXP-072 已在 `2026-08-30T03:22:56Z` 启动完整连续执行。49/49 synthetic tests 通过，
119-artifact metadata gate Passed，source snapshot 为
`be16768a22f7d1d3691ddfe27c991b7fd02c5fea5c0d5e6820f8202b54f35549`。
Active config：`phase-b-representation/configs/exp-072-lora-functional-ablation.json`，
9,954 bytes / 0644 / SHA256=`60f670d53fa551a5b43c38dcd1ddb861709e80df9b6b2022e388876db9c75a4e`。

后台 shell 已串联 `run --stage run` → `score_exp072_ablation.py` →
`verify_exp072_ablation.py`，每一步仅在前一步 exit 0 后执行。Exec session=`45924`，
最初 scheduler PID=`10843`；不要重复启动 runner 或手动同时启动 scorer/verifier。
进度在 `phase-b-representation/runs/exp-072-lora-functional-ablation/formal-attempt-1/stdout.log`。
`run-claim.json` 的 Running 是不可改写的历史声明；当前状态应从进程、worker records、
run.json、score.json、verification.json 和 failure records 判断。若 PID 已复用，不能
据 PID 存在就认定本实验仍运行，必须核对 command identity。

App heartbeat `phase-b` 每小时在本任务继续检查；运行中只读取 metadata，失败即暂停
跟进并报告，禁止修改 frozen sources、重试或恢复。EXP-072 Passed 后生成 EXP-074 配置，
绑定七个 verified public inputs，再执行 synthesis → independent verify → private Markdown
研究报告。报告和最低完成集都交付后暂停 heartbeat。

EXP-074 代码与 12/12 synthetic tests 已完成。已按真实 EXP-070 recovery 终态核对
metadata compatibility：verification 用 `source_probe`、`source_snapshot_unchanged`；
completion 通过 `verification` 绑定前者，没有 `run` 或 `source_unchanged` 字段。
当前尚无 EXP-072 评分结果或 EXP-074 正式结果，不得宣称 Phase B 已完成。

### 2026-08-30：最终实验收口

本节取代上节的运行中状态。后台 session 45924 已退出 0，不得重新启动该 pipeline。
EXP-072 于 `2026-08-30T11:09:31Z` 完成全部 70 workers，随后 score 与 independent verifier
均成功；20/20 checks Passed，`exp072_complete=true`。15 个 A0 replay 最大误差均为 0。
推理 wall time=27,993.56 s，MLX peak=8.593 GB，RSS peak=5.553 GB。
Verification SHA256=`896c8a913606ce861676e3da2849830f8b664ff06c1bef777934ba5548f9f3c0`。

EXP-074 active config：`phase-b-representation/configs/exp-074-phase-b-synthesis.json`，
SHA256=`eab598e7988c3e02147946b5642f2a26453c294a44b354400f524e552ad00c89`。
12/12 synthetic tests 通过，正式 synthesis 与 independent verification Passed。
最终 verification：`phase-b-representation/runs/exp-074-phase-b-synthesis/attempt-1/verification.json`，
SHA256=`c1e5dc3e2961cbd4505566f116514e5ca104f26018b08e6fee7fbd0ec0137f88`。
`exp074_complete=true`，`phase_b_minimum_complete=true`，`source_unchanged=true`。
Summary SHA256=`9459600ddb4b1d5809c79e48c1e5f6848c34cdadc48d4a50a3e42fd40ca8133d`。

两项独立结论为 `Representation effect replicated` 与
`Stable Attention-dominant dependency`。确认 seeds43/44 的 D 为 +0.137906/+0.110372；
seed42 的 D 为 −0.164585，方向相反，不能写“三个 seed 一致”。所有结论限定 same-train
outer-heldout；A1 不是重新训练的 M2，深度分组只在 seed42 实施。

报告：`phase-b-representation/private/reports/phase-b-research-report-2026-08-30.md`，
本地 Git-ignored Markdown，reports 目录 0700、报告文件 0600。报告核对已通过：405 个表格
数值单元、213 项差值及科学边界均无待修正问题；10 张表的列结构与 12 个本地链接通过。
Heartbeat `phase-b` 已设置为 PAUSED；本次未 commit/stage/push，Phase B 最低实验集及报告
交付已完成，不再自动运行后续实验。
原 EXP-071 Failed 与诊断 Complete、EXP-075 post-diagnostic、H-1 CKA 和固定九点
Spearman 的 null 均保留。EXP-073 未执行、context/C2 暂停，不属于已完成的扩展实验。

### 2026-08-30：Phase C 本地网站当前交接

用户最新范围：先不做 CancerEmo 等其他数据集的泛化，推进系统其余部分。
新模块为项目根目录 `forum-topic-emotion-web/`，不要改 Phase A/B 的冻结来源。
读模块 README、docs/spec.md、docs/plan.md、docs/acceptance.md 与
`protocols/exp-076-phase-c-local-system.md` 恢复当前状态。

95/95 合成/集成 tests 通过。真实 smoke 四 jobs、每 job 8 条新编英文输入均完成；
Research 每次 3 个实际 M3 forwards + 1 个缓存命中，Demo budget0 显式回退 4 条。
独立函数复算 snapshot、标签统计、成本和重放通过；M1/M3 replay max abs 均为 0。
该 smoke-only 检查不是完整 EXP-076 verification，不能说 Phase C 或真实来源闭环完成。

EXP-076 source job `83dd3569136d42f1abedcfba135c0bd3` 于 fetching 阶段 Failed，
`worker_failed`、manifest null、sealed rows=0，没有进入模型推理。
工件：模块 `private/validation/exp-076/attempt-1/`，包括 smoke/source 各自终态与日志。
原异常未保留为具体类别；只读 API filter、同 query pagesize0 metadata 均能正常访问，
因此目前不能确定原失败原因。只读审查另合成复现无 header gzip/deflate decoder 缺口，
但其与原失败的关联未证实。未在失败后修改代码、重采 posts 或运行完整 verifier。

下一步应先对新模块做最小采集错误留痕/压缩兼容修复，测试通过后再登记有界来源复测；
不需要重跑已经完成的四个模型 smoke jobs，更不重跑 Phase A/B。
继续保留失败工件，不冒充“原 attempt 已修好”。Runtime Soak V2、Discourse 真站接入、
normalized unique-text/完整时间视图和最终答辩材料仍待完成。
Discourse 站点尚未由用户指定；未选站点时 live 入口拒绝。外部 gold 与 context/C2 暂停。

本地服务启动命令为模块 `.venv/bin/python start.py`，监听 127.0.0.1:8787；
本轮服务 PID=44570、exec session=25544，先检查存活，勿重复启动。浏览器已本机登录，
令牌在 ignored `private/access-token`（0600），不要输出或提交令牌。
模型仍使用冻结 conda `phase-a-runtime`，网站依赖在独立 `.venv`；无 stage/commit/push。
原 phase-b heartbeat 保持 PAUSED，未为本地网站创建新自动化。

### 2026-08-31：source attempt 2 已停，明确评论字段阻塞

本节更新上一节的当前执行点。用户“下一步”后，collector已补gzip/deflate/代理明文兼容，
worker已补安全错误类别、阶段、计数与最多4条文件/函数/行号栈帧，112/112 tests通过。
模型bridge、core和fixture均未变；旧source/smoke所有文件保持原hash。
原实现与协议在模块 `private/validation/exp-076/attempt-2/` 归档，38项源码hash匹配。

`.venv/bin/python scripts/validate_local.py source --attempt 2` 已执行一次并退出1。
新job：`3467697c6e954893a59d0c1e17fbaf2a`，error=`source_body_markdown_missing`。
具体定位：第3次API请求、comments/page1、record校验；HTTP200、gzip、4,229 wire bytes、
返回100条且has_more=true。失败前92条问题/回答仅在内存，sealed/predictions=0/0。
没有进入模型推理，没有重跑四个smoke，没有执行完整verifier或第三次采样。
Source terminal SHA256：`205778bf617dac7712010de0367ea544829c4a438bc518bd6f1d94b8a6083a37`。
只读复核source.json与数据库progress一致、代码和继承hash未变；这不是完整EXP-076 Passed。

查到 [上游字段依赖报告](https://meta.stackexchange.com/questions/247899/creating-an-api-filter-with-comment-body-markdown-but-without-comment-body)：
comment.body_markdown可能必须与comment.body同时请求才返回。旧filter只额外请求Markdown；
本次症状相符，但尚未做当前接口字段A/B验证，不能声称已修好或确定原attempt1原因。
下一步应先做最小filter联合字段确认：额外请求comment.body，仍只使用返回的body_markdown，
不把HTML转成模型输入；确认后再登记有界来源复测。保留两次失败，沿用EXP-076，
不要重新运行模型smoke、Phase A/B，或引入复杂Incident/授权链。

旧服务PID44570已在所有任务终态时正常停止。当前修复版服务PID=48767、session=59886，
监听127.0.0.1:8787；恢复时先只读检查，勿重复启动。来源runner session95209已退出1。
浏览器已显示新错误代码，本机token仍在private/access-token。没有stage/commit/push。
外部gold、context/C2、Discourse和Runtime Soak V2本轮均未执行；phase-b heartbeat仍PAUSED。

### 2026-08-31：EXP-076 有限来源验收完成，下一步 Soak V2

本节为当前状态。用户再次“下一步”后，按原protocol追加的attempt3执行了最多5请求的字段
检查：同3个comment IDs，旧filter缺body_markdown 3/3，新filter额外请求comment.body后
两字段返回3/3。没有HTML-to-text回填、没有模型或gold访问。Field-probe SHA256：
`dfe0438fe73f2db5e220aa88359b42e5d620e01f5757220757c8c8a0186e92d7`。
新filter固定为 `nFzTOPGAOEckIq4PwsL9Jd`，只把原生Markdown送模型。

source attempt3已完成：46 questions、46 answers、248 comments，总340/340预测。
同原Python标签、`[2026-08-23,2026-08-30)` UTC窗口；5次API请求，sampling_complete=true。
M1 only：338实际计算+2缓存命中，M3=0、fallback=0。Job耗时32.77s；RSS peak803,782,656 bytes。
Job ID=`5ab3326150ee448ba326233264967d34`。原source1/2 Failed与4个成功smoke都保留，未重跑。

`.venv/bin/python scripts/verify_local.py --attempt 3` 已22/22 Passed，exp076_verified=true。
源码、协议、旧失败/归档、field-probe、来源/parent/time、输入hash、统计、缓存和原重放均已核对。
工件在模块 `private/validation/exp-076/attempt-3/`：

- source.json SHA=`3779713265e507787678e471320834e13f09f9a2a1a8683c69b03603eec9e272`。
- verification.json SHA=`7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8`。
- sealed snapshot SHA=`cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`。
- 数值验收源码在verified-code.tar.gz，SHA=`09d4c2b771edb1920767fc61924a35777fa2c99919d199e4f0ae1225cab891e3`，21项匹配。

数值验收之后，网页链接抽检发现原评论`/posts/{post}`路径404。因此仅修改Store.items的
public projection：使用`/questions/{thread}#comment{comment}_{parent}`，旧地址保留为
recorded_source_url。私有record/source snapshot/model input/预测不改，API与export一致。
实际API核对340条identity/hash及全部248条comment链接映射通过，见presentation-verification.json。
源码验收时134tests，展示修正后147/147。原22项数值verification不覆盖HTTP活性，
不能把link字段覆盖率100%写成匿名HTTP可用率100%；问题/回答HEAD可重定向但网站最终返回403。

不要重跑已有source或overwrite verification；后续代码已有presentation-only差异，旧源码
以verified-code归档为准，不要把当前store.py差异误判成模型或数据漂移。
完整结论与历史见模块docs/acceptance.md，当前工作计划见docs/plan.md。
下一步是有界Runtime Soak V2协议/实现/验收；它不是context/C2恢复，也不是旧EXP-067重跑。
Discourse仍待指定审核站点，外部gold和context/C2继续暂停；Phase C整体尚未完成。

当前服务PID=55532、session=2493，监听127.0.0.1:8787；PID54665已在任务完成后正常停止。
source runner session6371已退出0，字段probe session5349已退出0。先核对进程身份，勿重复启动。
未stage/commit/push、未公开部署或上传数据。phase-b heartbeat继续PAUSED，没有新增自动化。

### 2026-08-31：Phase C功能交付，EXP-077安全停止，EXP-078未执行

本节为当前状态。用户要求一次完成已规定步骤、不逐门授权；该授权不取消资源停止门。
Module：`forum-topic-emotion-web/`。完整两权重/日周/六标签构成/类型路由分层、运行诊断、CSV、
单job全文清除和4份使用材料已实现，212/212tests及JS syntax通过。
已有5成功任务372条新视图/CSV只读复核Passed，原source/smoke逻辑记录不变；
工件`private/validation/phase-c-views-qa.json`和可复核脚本`check_phase_c_views.py`。

已登记并实际执行EXP-077（新Soak，不是旧context/C2），固定36job/15,120事件，不能更改分母。
于UTC02:35:43.987598、elapsed40.221628s在critical_memory_pressure门停止：
M1 job `6c1f57fde85d4da2a5d322039fdd4d0c` completed420/420；Research job
`a510bc76034e43dc97a5bbfdc7872485` cancelled，420已封存、0结果回执；34job未提交。
独立verification Passed，**exp077_complete=false、soak_gate_passed=false、stop-required**。
不要把审核Passed说成benchmark成功，不要重跑、修复/覆盖attempt-1或自动启动后续模型。

M1已确认338forward+82cache，child plateau1.037315≤1.05；cross-job无法评价。
40系统样本含2个critical（相隔约22.7ms，不是2秒），交换超阈值最长连续2间隔，没有达到
3间隔thrashing定义。Research尝试/峰值未知，不能记0或归因M3 OOM。保留全机因果边界。
输出`private/validation/exp-077/attempt-1/`，verification SHA256
`339bd2da52e3bffa0cfe796239ecd857f80becead5f2b829c5cf3a3b03d61f13`；
run SHA=`69c7e18f1dd2664cdef170d9e899a7dd57b6748bbb902af222ad8e4613ddd81e`。
Serve PID61665/session42910及driver session59779已停止/退出1；无模型child存活，停服后6绑定hash一致。

EXP-078：Python Help（discuss.python.org category7）已审核，匿名原生raw两帖子三返回可行；
adapter、固定来源UI、run_discourse_validation.py、verify_discourse_validation.py及tests完成。
因Soak不是safe-to-continue，**未执行正式300–400条采样或Research任务**，不存在正式verification。
这不是Discourse采样失败或数据为0；不能绕过Soak门来补平台数。

本地API恢复为PID62541/session62736，127.0.0.1:8787；仅用于本轮查看已有任务，不提交模型任务。
恢复时仍须核对PID身份；服务启动本身不加载模型。Browser已登录，token不输出。
报告与结论清单位于模块`private/reports/phase-c-system-report-2026-08-31.md`及
`final-claims-2026-08-31.md`，Git-ignored。使用手册/schema/model-bundle/demo-script在docs。
功能和材料已交付，不能宣称完整Phase C实测完成。后续需先确定资源问题的处理方向，
本轮不自动诊断负载、重试、降低门限或恢复C3。外部gold与旧context/C2暂停；无stage/commit/push、
公开部署或数据上传，原phase-b heartbeat维持PAUSED，没有新自动化。

### 2026-08-31：用户继续Phase C.1，当前为实现/静态检查

前一轮可公开项目内容已commit/push为880cab3，private报告/数据/模型没有上传。
用户随后要求继续验证有界稳定运行和Discourse正式闭环，不把原阶段标成全部完成。
已登记DEC-PHASE-C1与EXP-079/080/081；模型与旧077保持不变，080继承078来源合同但绑定新079。
EXP-079固定三轮m1_only/research/demo共9job，每job原340条，无新增warmup/cache tail。
每job前10个normal/no-model/quiet-swap样本，最长60秒；run总1800秒，沿用硬资源门。

当前只检查metadata/空闲状态和编写新脚本，**EXP-079/080正式目录尚未创建，模型未启动**。
旧077所有绑定hash仍吻合；空闲10样本pressure均1、swapIO0、heavy lock可用。
原主服务PID62541已经0active检查后正常停止，不能再把它当存活服务；8789/8790留给新隔离服务。
不要启动第二份主服务或先运行080。三个子agent分工新runner/support、独立079 verifier、080工具；
必须等待完整synthetic roundtrip与freeze信号后再由root执行新实验。

新文件：scripts/run_bounded_runtime.py、bounded_runtime_support.py、verify_bounded_runtime.py；
scripts/run_discourse_formal.py、verify_discourse_formal.py；scripts/closeout_bounded_operational.py。
对应新tests正在完成；已过首批runner/support15项和closeout7项，但不等于全部正式前检查完成。
静态准备中捕获并修正负路径兼容，不动原生产topicweb/static或旧脚本；新依赖清单显式排除080/081
非依赖文件。此后继续按最新工具/tests状态恢复，不重头设计。无本轮新commit/push、无外部gold。

### 2026-08-31：EXP-079已启动，先读实际终态，不重复启动

263/263全套合成tests与两套CLI临时DB全链通过，runner/support/consumer及协议已冻结。
只读兼容审计No findings，22项依赖一致，原340条payload为271,941B、SHA256
`0ffdb01c64c3d55e8c7c0d9958b4d56921578873cbcc0bb0c54e4467b15a070c`。
EXP-079隔离服务PID70577、session99661，127.0.0.1:8789；driver session20393已开始。
输出在模块`private/validation/exp-079/attempt-1/`。run-claim只代表历史启动，当前状态应读
stdout.log、run.json、samples.jsonl和对应bench job状态。运行期间不改22项依赖或协议，
不启动第二份服务/driver、不执行080。driver结束后先确认目标job与子进程终态、停70577，
再运行verify_bounded_runtime.py。只有exp079_complete=true且safe-to-continue才进入080。

EXP-080工具已冻结，9/9专项tests通过，预定8790独立bench：serve→run→只读Dashboard检查
→停服务→verify_discourse_formal.py。EXP-081综合工具有7tests，不在079/080依赖集。
本次报告会新建Phase C.1补充，不覆盖原Phase C报告或旧失败。主8787仍停止，不重复启动。

### 2026-08-31：EXP-079 attempt1观察分类误报，正修正attempt2

Driver20393已退出1，service70577已正常停止，无后续任务。attempt1运行19.483361s，
M1-only job14f50f712d984ec5a9e6a77e16e463bf在0回执时取消，原因concurrent_model_processes。
sample17实际是70577→70666→70693：一个dispatcher直接推理worker及其Python后代，
不是两个并列worker；所有19个pressure样本为normal。额外进程的具体库内功能未记录，不推测。
这属于新observer把全部Python后代视为并列模型的实现错误，不是原EXP-077资源失败复现。

原attempt1独立审核Passed但exp079_complete=false，verification SHA
38144c1fe5478b5f96cb4c40beac2f9e97b3859052de3d42d8779aeec7405ba3。
run SHA14afe2403e4c4bab0da79a5052a9646d4531bb7e337571dd260f1f8a1ff95743。
原22依赖+2协议24文件逐字归档frozen-code.tar.gz，SHA
b94d95df93cbff30c0f5c0384c7b4160c01296fce171627862500b4be481915a。旧工件不修改。

修正说明为exp-079-observer-correction-attempt-2.md。现在只修测量分类：并发门按service直接
推理root数，所有Python后代仍保留资源/seen/orphan/absence检查；两个直接root仍停止，
资源/模型/输入/9任务目标均不改。active新路径exp-079/attempt-2，080依赖转为新终态并绑定
correction。只因已证实的分类误报允许这一次新尝试，不把真实critical/资源失败当技术错误重跑。
三个agent正在完成最小修正与原测试；等待freeze后继续，不得提前启动或覆盖attempt1。
主8787仍停，079 attempt2与080均尚未启动。无新commit/push、无gold/训练或其他数据集。

273/273全套tests通过后，EXP-079 attempt2已启动：service PID71829/session12018，
driver session13785，仍为8789；输出exp-079/attempt-2。不要再启动第二份进程，不改22项依赖
或任何绑定协议。终态仍需先停服务再独立verify；只有该attempt2通过全部门才运行080。
第一轮从M1-only开始；当前进度只读stdout/run与bench metadata，不把run-claim当当前完成状态。

### 2026-08-31最新：attempt2真实资源停止，完整verification Failed，等待资源条件改变

不要继续运行模型。EXP-079 attempt2 driver13785已退出1，service71829/session12018已停；
精确检查71829/71913/71935/72397/72417均无存活进程。主8787也仍停止，历史数据未删。
run=Stopped/critical_memory_pressure，elapsed62.498333167s。M1 job
14fc2780ee944f54ad57b561d022c59b completed340/340、338计算+2cache；Research job
3e046247ab4a4a349c6e053571a7addd cancelled340/6，只有ordinals0–5的M1回执，下一ordinal6应路由。
实际未回执尝试/最终MLX峰值未知，不写成0。共1/9计划job完成，7个未启动。

59系统samples独立复算：normal57/warning1/critical1，无unknown/非法间隔。最后3交换间隔
182.10/189.72/142.38MiB/s；critical在第二个高间隔触发取消，第三个发生在cleanup中才使
thrashing定义成立。swap delta687669248B。不能把全机压力单独归因模型或声称OOM/泄漏。

原完整verification.json为Failed/process_absence_identity，SHA
f3ab1b94efbc1333b3f04c5e094658dd7b1d9b84dba35adf7bb7c68887c373c4，不能覆写或宣传Passed。
唯一缺口sample36（JSONL37行）：seen含71913/71935，absent只列71935，models/orphans空，
selected_ps只有service；71913的exit0/final_gate落在该采样窗口内，但原PS行没留，不能确认
comm/defunct状态或补判absent。sample37以及58的后续退出字段自洽，不倒填缺口。

private/validation/audit_phase_c1_stopped.py只读复核346回执、M1聚合/已知成本和系统计数，
结果attempt2/technical-audit.json为Partial audit only，SHA
a0743603daafb2528b9e491e095b48a7980cc10e8031496ad64d64551b7e4abd。
旧/新原始工件及22项冻结依赖不改；没有verification recovery或attempt3模型执行。
EXP-080目录未创建、没有正式采集/推理。EXP-081/run.json只生成目标未建立的元数据记录，
full_operational_completion=false、bounded_verification_status=Failed；综合完成不是用户目标完成。

新报告private/reports/phase-c1-bounded-operational-report-2026-08-31.md为0600、Git-ignored；
旧Phase C报告不覆盖。当前需要用户先减少背景内存占用或明确其他运行环境；下一次需修正
observer在退出交叠时保留所有已见PID原始行，不能改旧样本取得通过。不得再按相同条件
直接模型重跑、降低门限或绕过079执行080。无本轮commit/push，外部gold和旧context/C2仍暂停。
