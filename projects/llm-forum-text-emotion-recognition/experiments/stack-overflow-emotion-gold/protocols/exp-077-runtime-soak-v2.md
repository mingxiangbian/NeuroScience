# EXP-077：本地服务 Runtime Soak V2

- Date：2026-08-31
- Tier：Major，RQ-S3 系统实现章节。
- 用户范围：连续完成已确认Phase C剩余步骤，不逐门询问；外部gold与context/C2仍暂停。
- 本实验是新的有界服务验证，不重写或“修复”EXP-067/068的历史结论。

## 固定对象与问题

验证实际HTTP API → 私有SQLite → 单dispatcher → 独立模型child在连续任务中的可用性、
计算/缓存计数与暖态内存稳定性。不评价准确率，不训练，不访问历史train/validation/test或新gold。
模型、tokenizer、prompt、阈值、router与数值推理继续沿用EXP-066 seed42完整artifact。
不修改inference_process.py；新telemetry在worker端只读采样，默认生产模式关闭。

输入来自EXP-076已经封存并验证的Python话题job：
`5ab3326150ee448ba326233264967d34`，340条、338个精确输入组，原顺序。
私有snapshot SHA256：`cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`。
父verification SHA256：`7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8`。
旧记录只读，benchmark使用独立数据库，不能覆盖原来源任务。

## 固定工作负载

12轮，每轮顺序 `m1_only → research → demo`，共36个job；每个job使用新的模型进程与空cache。
每个job共420个事件，不突破现有500输入上限：

1. warmup 16：先按精确输入hash去重；依据原M1-only结果的route_eligible分层，在eligible与
   non-eligible中各取字符最长的8条，长度相同时用原ordinal升序。它只用于覆盖初始化/长输入
   内存，不是科学子样本选择；保留全部warmup成本、峰值与时长。
2. measured 340：完整原snapshot按原ordinal顺序；与warmup重复的16条及原生重复会命中cache，
   其余需要真实forward，不用全缓存阶段冒充模型压力测试。
3. cache_tail 64：重放原前64条，独立报告暖cache路径；不进入主要plateau门。

每条事件有独立ID，text逐字不变，phase/source ordinal/input hash在plan.json中冻结。
Research安全上限500次M3，Demo预算20次（包括warmup且失败尝试计入）；audit=0、seed42。
不修改router cutoff，不将15%训练域operating point强制应用到任务。
预定总事件数15,120；任务完成率分母始终36，提前停止不缩小分母。

## 资源与监测

生产网页使用同一app工厂的隔离实例，127.0.0.1:8788，私有目录：
`forum-topic-emotion-web/private/validation/exp-077/attempt-1/bench/`。
主工作台在benchmark期间停止接收新任务，完成后恢复；global heavy lock仍保证单模型进程。
环境继续是网站独立.venv与冻结phase-a-runtime，不安装或改动模型依赖。

- 最多36个job、run阶段总计3600秒，单job沿用3600秒上限，超过总限先取消并保留工件。
- child peak RSS≤12GiB、MLX peak≤10GB；API parent current RSS≤1GiB，磁盘free≥512MiB。
- 每个结果回执后用ps读取child及parent**当前RSS**；ru_maxrss只作峰值上限，不能用于plateau。
- 启用TOPICWEB_TELEMETRY=1；ps命令最多2秒，保存pid、采样时间及bytes，不保存进程环境/原文。
- 系统约1Hz读取kern.memorystatus_vm_pressure_level与vm_stat，保存原始计数、page size与时间。
  sysctl返回的dispatch位值1=normal、2=warning、4=critical，不是内核内部的0/1/2/3枚举。
  依据[Apple sysctl handler](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_memorystatus_notify.c)
  及[event_private.h](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/event_private.h)。
  预先存在的swap使用量不等于本实验thrashing。
- Swap IO rate = 相邻有效样本的(Swapins+Swapouts)增量×page_size/实际秒数。
  相邻dt必须大于0且不超过3秒；正常采样延迟不按恰好1秒计算，也不作补样突发。
  连续至少3个有效间隔达到100MiB/s定义为本实验的thrashing proxy；同时报告累计增量。
  它是系统级操作定义，不能单凭该值将其他应用造成的交换归因到本模型。

监测缺失、不合法counter/time、identity drift、critical pressure、thrashing、资源超限或
实际运行失败时停止后续提交、取消当前job，保留已完成部分。不能把unknown写成normal/0。
Demo原降级行为不改变；若真实M3运行故障触发回退，driver记录并停止后续，不把它当成
正常预算回退或成功稳定性结果。只做预算回退不属于运行故障。
纯plateau未过不触发重调门或重跑；继续完成固定工作负载并报告负结果。

## 预定检查与结论

1. observed任务完成率≥99.5%，预测schema有效率100%，unhandled crash=0。
2. 每job measured阶段前85与后85条回执的child current RSS中位数比≤1.05，共36个门。
3. 每mode将首3轮measured样本合并取中位数，再与末3轮合并中位数比较，比≤1.05，共3个门。
4. parent的对应比率及warmup/cache_tail跨轮比率仅单独报告，不加入未登记的primary门。
5. critical pressure=0、thrashing proxy=0、所有监测可用，资源门通过。
6. 输入与来源身份、420事件phase对齐、实际计算/成功/cache/fallback计数、重复轮预测一致，
   均从保存结果独立检查；冷计算与cache阶段分别报告延迟分布。
   每phase报告n、min/median/p90/p95/max，分位数线性插值；per-item时长不含API与M1引擎初始化，
   job elapsed包含初始化、HTTP与观测开销，不能混用两者解释整体响应时间。

36/36通过只能是该固定工作负载的观察值，不能声称已证明99.5%生产SLA、全天稳定性或外部准确率。
全门通过：Verified operational research prototype（限定本机与固定负载）。
只有plateau/监测证据不足：Functional demo only。
实际crash、critical或资源失败：Runtime unstable on this workload。
任何负结果都原样归档，不为获得通过结果修改负载、warmup、门或已写结果。

## 工件与执行

模块目录命令：`.venv/bin/python scripts/run_soak.py serve` 启动隔离服务，
`.venv/bin/python scripts/run_soak.py run` 连续执行，最后
`.venv/bin/python scripts/verify_soak.py` 做独立只读复算。
真实执行需可读取系统监测的本机权限；不可在受限sandbox中把监测失败当正常值。

固定输出根 `private/validation/exp-077/attempt-1/`：plan.json、run.json、stdout.log、
system-samples.jsonl、bench/jobs.sqlite3、verification.json。run/plan绑定协议、实现、源snapshot、
环境和执行命令；终态create-only，不覆盖已有实验。原始文本仅私有DB，公开报告只含汇总。
实现绑定覆盖生产API/worker/telemetry/core、静态界面与Soak工具；非依赖的EXP-078 runner、
verifier和其专用test文件不属于EXP-077源码快照，可在本实验期间并行完成，但不得改共享实现。
结论进入系统报告与claims ledger，不与Phase A/B行为或表征证据混为一谈。
