# EXP-079：Bounded Runtime Acceptance

- Date：2026-08-31；Tier：Major；RQ：RQ-S3系统实现。
- 问题：在明确的本机任务前检查、单任务执行和资源上限内，三种模式能否各完成3个真实快照任务？
- 论文位置：系统有界运行验收表、计算成本/延迟与资源限制。
- 本实验独立于EXP-077，旧失败不改写。本协议在新模型运行前冻结。

## 固定输入与运行

使用EXP-076已验证source job `5ab3326150ee448ba326233264967d34`的全部340条model_input_text，
原ordinal顺序、逐字不变，338个精确输入组，25个冻结假设路由对象（也是25个唯一输入）。
Snapshot SHA256=`cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`；
parent verification SHA256=`7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8`。
原DB只读，新任务通过实际HTTP上传路径进入独立DB；plan绑定原ordinal、input hash及payload hash。

三轮，每轮顺序m1_only → research → demo。共9job，每job340事件，总3,060事件；不增加warmup
或cache tail，原始重复仍按真实occurrence保留。每任务一个新模型进程与空cache，不并发。
M1-only预算0，Research安全上限500，Demo预算20，audit=0，seed42。
不重新拟合、不按当前任务取top-k，不改变父EXP-066 tokenizer/prompt/max_length/权重/阈值/router。
生产topicweb、static及原EXP-076/077/078脚本不修改；新工具和其tests单独添加。

模型环境仍为冻结phase-a-runtime，网站仍为独立.venv。记录网站完整包版本、冻结模型环境、
硬件、Git commit/dirty、实现与协议hash。仅使用metadata检查，不因预检查加载模型。

## 新的有限使用条件

原主工作台在验收期间不接收新任务；EXP-079使用127.0.0.1:8789，独立private DB。
旧EXP-077服务不能重启，原已完成工件只读。保留原global heavy lock和单dispatcher约束。

每个job提交前，最多等待60秒，须取得连续10个有效、约1秒间隔的观察：

- system pressure均normal（公开sysctl值1）；模型子进程数为0。
- 对应9个相邻间隔的swap IO均小于10MiB/s；counter不倒退，dt>0且≤3秒。
- 所有本实验已见模型PID均已退出；上一job已终态。保存readiness所用样本索引，不写“估计就绪”。

此条件是操作性安静窗口，不是“可用内存足够”的保证，也不证明消除原失败原因。若窗口未成立，
不提交该任务，记录未就绪并停止该次pipeline；不循环启动模型试探。不会结束其他应用或清缓存。

## 监测与预算

- 最多9job、整个run（含等待）1800秒；单job沿用3600秒，但以总限更早者停止。
- child peak/current RSS≤12GiB；MLX peak≤10,000,000,000B；API parent current RSS≤1GiB；
  可用磁盘≥512MiB。无外部模型API费用，CPU/GPU成本按实测wall time及资源记录。
- TOPICWEB_TELEMETRY=1复用已有每回执current RSS记录；额外每约1秒读系统pressure/vm_stat以及
  本服务拥有的模型PID/RSS，覆盖首条回执之前的初始化阶段。只保存目标进程与父进程，
  不保存其他应用命令、环境、原文或令牌。服务PID及模型进程集合均可追溯。
- 隔离服务可通过原ProcessRunner的薄观察子类保存process-events.jsonl：构造开始、ready、
  实际returncode和原super.finish成功后的final_gate_passed。它仅添加事件留痕，不改变原退出、
  取消、模型或结果逻辑；不能根据数据库completed标签虚构exit0事件。
- 采样结束后至少等待1秒才进行下一次观测，使用实际monotonic间隔，不追赶补样。
- system pressure仍按1=normal、2=warning、4=critical。正常运行warning只记录，critical立即停止。
- swap rate=(ΔSwapins+ΔSwapouts)×page_size/实际dt；≥100MiB/s连续3有效间隔定义thrashing。
  原有swap占用不算故障。dt≤3秒、counter/page size合法；unknown不得当normal或零。

整个run持续监测。critical、thrashing、监测缺失、资源/身份错误、未知/普通M3运行故障均停止
后续提交；取消当前任务并最多15秒确认终态与子进程退出。只允许Demo预算耗尽的预期回退。
未收到回执的模型尝试/峰值保持未知，不记为0。取消不等于正常退出0；成功job才需要原final gate
及exit0，独立验证同时检查所有已见PID在后续样本中退出、没有孤儿。

## 独立检查和成功判据

9/9全部完成（允许Demo completed_with_fallback且只因budget），3,060/3,060结果schema有效；
M1与原source预测在1e-6内重放一致，三轮同输入的M1/M3决策一致且概率差≤1e-6。
完整快照/输入hash、模式、实际调用/cache/fallback、最终路径和aggregate独立复算。
每任务M1实际338+cache2；Research应25次M3计算；Demo20次M3+5个预算回退对象；
这些预期由冻结源路由资格导出，失败不能靠调cutoff或换样本补齐。

无unhandled exception、invalid schema、critical、thrashing、未知观测、orphan、身份漂移或超限。
每个job的输入前85/后85回执child RSS中位数比及同mode第3/第1job中位数比只报告，不作主要门，
不把allocator归还内存行为解释为系统可用性的唯一标准，也不与EXP-077旧plateau门混用。
记录完整任务elapsed以及逐条latency的n/min/median/p90/p95/max，线性分位数；逐条值不含HTTP
和M1引擎启动，不能拿cache时长冒充完整响应时长。

独立consumer不得调用producer统计函数，可复用旧独立record/aggregate checker。
审核status=Passed只说明工件一致；只有全部完成/安全门通过，exp079_complete=true且
operational_state=safe-to-continue，才允许EXP-080。

## 产物

`forum-topic-emotion-web/private/validation/exp-079/attempt-1/`：service identity、plan、run claim、
stdout、system/process samples、process-events.jsonl、jobs记录、bench DB、run.json和verification.json。
终态create-only。
run绑定实际依赖的生产实现、旧复用helper、新EXP-079 runner/verifier/tests和本协议；
EXP-080/081的非依赖文件不纳入EXP-079，允许在此期间准备，不能改共享生产实现。
run完成/停止后先停隔离服务，再独立verify以封存稳定DB。只写新工件，无旧结果覆盖。
