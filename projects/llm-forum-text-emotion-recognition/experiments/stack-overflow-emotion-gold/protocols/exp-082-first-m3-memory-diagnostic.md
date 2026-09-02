# EXP-082：首次 M3 调用的分阶段内存诊断

Date：2026-08-31。Tier：Minor。RQ-S3；所属有界运行问题为 EXP-079。
用户在只读定位后要求“下一步”，本次执行已说明的单次诊断，不重跑九任务验收。

## 固定范围与预算

一次新推理进程，Research、seed42、audit0、max_qwen_calls=1。使用 EXP-076 已封存
source job `5ab3326150ee448ba326233264967d34` 的原序前七项（ordinals0–6），字符串不变。
前六项冻结路由资格均 false，第七项为 true；绑定 EXP-079 attempt3 plan 中对应的输入 hash。
source snapshot 为 `cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16`。
只读原 DB 的这七项，不访问其余原文、历史 train/validation/test 或外部 gold。

总预算180秒，工作阶段最多150秒，另留最多15秒退出清理及15秒监控/封存余量；任务前安静窗口最多60秒，
仍需10个连续 normal/无已知活子进程/低swap I/O样本。原critical、连续3间隔至少100MiB/s、
RSS12GiB、MLX10GB、父进程1GiB、磁盘512MiB、身份、孤儿与退出检查不变。
不得自动重试、降低门限、量化、换模型或调cache；没有外部模型API费用。

## 保持推理逻辑，新增阶段观察

直接复用原 ProcessRunner 与 frozen inference_process.main，不开HTTP服务、不创建网站任务，
原模型、权重、prompt、tokenizer、阈值、router、数值执行次序不变。前六项保留M1前缀行为。
诊断以新增子进程观察层追踪冻结Python代码中的阶段，不修改原生产文件或复制一套推理算法。
首次MLX import前不为采样提前初始化MLX；原memory/cache设置完成后才读取MLX计数器。
不额外调用eval、清缓存、重置峰值、wired-limit或执行任何优化。

记录request、M1、M3 factory/import、基座load、LoRA装配、adapter/head装载/求值、
tokenization、首次forward等可辨阶段的开始/结束，附monotonic、进程身份、ordinal和
RSS peak、可取得的MLX active/cache/peak。每条flush/fsync；无原文、tensor值、异常文本或locals。
not_loaded/not_sampled/unknown不填成已观测0。取消后未结束的阶段保留未结束，半行不能当完整事件。
观察本身有开销，因此不把这次耗时当效率benchmark，也不声称观察完全不影响调度或资源时序。

## 工件与判断

只写 `forum-topic-emotion-web/private/validation/exp-082/attempt-1/`：plan、claim、
supervisor identity、stdout、系统/进程样本、进程事件、阶段journal、最多七条结果回执及run。
父进程创建工件后仅串行启动一次child，复用原取消/正常退出逻辑。原DB只读，原失败工件不改。
开始前绑定 EXP-079 attempt3 plan/run/verification 的真实哈希及所有复用/新增代码和测试。
先通过合成观察、失败清理和独立核验测试，再执行一次，最后用无模型consumer复核。

诊断目标是缩小压力发生时的阶段范围，不计算新准确率、泛化或系统效率结论。
若发生critical，以最后完整阶段标记及其与系统样本的时间交叠表述，不能从相关时间自动推出
某函数单独造成整机压力。若七项成功完成，也只是本次短诊断完成，不补足EXP-079的9/9。
记录审核Passed与运行安全Passed必须分开；EXP-080仍未获安全前提，本次不自动推进Discourse。
任何失败或未知项均保留工件并停止。本次不训练、不上传、不stage/commit/push。
