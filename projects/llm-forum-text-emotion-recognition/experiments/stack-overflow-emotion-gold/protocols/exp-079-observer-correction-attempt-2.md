# EXP-079：进程观测器修正与 attempt 2

Date：2026-08-31。范围：修复新观测器的worker身份分类，不改实验问题、输入、模型或安全门。
用户已要求完成有界稳定运行和Discourse正式闭环；本次属于实现错误修正，不是资源门失败后的
自动降门或同attempt重试。原EXP-077资源失败仍不变。

## 已见证据

EXP-079 attempt1于19.483361秒Stopped，原因concurrent_model_processes，0/9完成。
首个M1-only任务已经封存340输入，在0条回执时取消。全部19个pressure样本为normal，
没有critical。本次并未执行Research或Discourse。

sample17的实际父子关系是service70577 → inference70666 → Python descendant70693。
ProcessRunner事件只记录一个推理worker70666的constructor/ready/exit；其returncode为−15。
第二个Python进程PPID=70666、RSS13,238,272B，不是调度器启动的第二个独立worker。
原observer递归取所有Python后代，然后用len(models)>1判断并发，将内部后代误等同于并列worker。
没有保存该后代的完整argv，因此其具体库内用途未知，不能宣称已确认resource_tracker或环境核验。

attempt1已独立核验：status=Passed、exp079_complete=false、stop-required；这只证明观测记录
与当时实现一致，不证明存在两个独立模型或系统无法稳定运行。原run/verification/DB/samples/events
保持不变。22项当时依赖与2项协议逐字归档到attempt1/frozen-code.tar.gz，再修改工作区工具。

## 最小修正

1. 并发worker数按已观测PPID界定：直接由service启动的Python推理root最多1个。
   独立consumer从原ps字段复算，不相信producer自行宣称的角色。
2. 所有已拥有Python后代仍保存。内部descendant/auxiliary角色不是忽略名单：原RSS上限、
   orphan检查、已见PID追踪、任务前安静窗口和退出/absence要求全部覆盖它们。
   如果内部后代超限、变为孤儿或未退出，同样停止；未知角色或birth key不能当作已确认退出。
3. 两个直接root仍必须停止；既有pressure、swap、RSS/MLX、时间、schema和身份门不放宽。
   M1-only/Research/Demo各3任务、每任务原340条、输入次序、各自预算、所有模型资产不变。
4. 新工件只写exp-079/attempt-2。保留attempt1的技术失败，不覆盖、不把其取消当作成功。
   attempt2额外上限仍为9任务/1800秒；累计保留前次已取消的1次任务尝试及未知未回执成本。
   此次只因已证实的观察分类错误允许一次新尝试；再遇资源/真实运行/身份失败仍停止，不循环试验。
5. EXP-080尚未执行，其新依赖固定为EXP-079 attempt2的独立完成/安全终态；同时绑定本修正说明。
   原EXP-078与旧EXP-077不变，不能用本说明把它们晋升为Passed。

先通过单root+内部后代、两个直接root、内部后代超限/孤儿/未退出，以及原完整和部分结果测试，
再启动attempt2。不能依据任何新的模型结果继续改分类或门限。
