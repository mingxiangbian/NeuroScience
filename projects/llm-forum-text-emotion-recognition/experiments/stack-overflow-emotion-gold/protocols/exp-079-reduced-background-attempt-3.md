# EXP-079：减少后台应用后的 attempt 3

Date：2026-08-31。用户明确要求“帮我关掉其他的应用并继续”。本次先正常退出无关应用，
再进行一次新的有界验证；保留 Codex/ChatGPT、网络代理及系统组件，不强制结束应用，
不放弃未保存内容。实际退出的应用及前后资源观测另存于本次私有运行记录。
进程 RSS 不能直接解释为回收的物理内存，已有 swap 占用也不单独构成失败。

## 保留的前次结论

attempt 2 在 62.498333167 秒因 critical_memory_pressure 停止：1/9 完成，
1 个 Research 任务取消，7 个未开始。取消前的高 swap 速率连续出现两次，
第三次出现在清理期间；不能把其改写为先发生 thrashing proxy 才停止。
这是整机资源压力证据，尚不能证明 OOM、内存泄漏或单独归因于 M3。

独立 verification 为 Failed(process_absence_identity)：sample 36 的推理进程退出
与采样窗口重叠，已见 birth key 未列入存活或缺席集合，且相应原始 ps 行没有保留。
后续样本不能补写该时点的状态。原 run、samples、DB、events 和 Failed verification
不修改，不用部分技术审计替代通过结论。

修改工具前已将 attempt 2 的 22 项冻结依赖及 3 项协议逐字归档并核对：

- frozen-code.tar.gz：`bbb4237c55548df50a00ac5687a1b6f382ce03d8cf7d6a669d709a7c20b7b281`
- run.json：`41285a06aa7bf66a3bc305aa0100f17da5c04f2154d378285b69d02ba369d950`
- verification.json：`f3ab1b94efbc1333b3f04c5e094658dd7b1d9b84dba35adf7bb7c68887c373c4`

## 仅修复观测留痕

完整 ps 表中，任何已见且 birth key 相同的进程，只要仍存在，就必须保存原始行和
结构化记录，不因 comm 改变或进程退出交叠而丢失。新增 tracked_other 保存已知存活、
但不再符合 Python 名称分类的行；不推断未记录的 defunct 状态。
每个已见 key 必须且只能属于存活或缺席集合。独立 verifier 从原始字段复算身份与 PPID。

所有已知存活进程仍受 RSS、orphan、安静窗口和退出证明约束；并发门仍限制直接推理 root
最多一个。变更名称不能绕过并发或资源门。原 sample 36 必须继续无法通过独立核验。
先完成退出交叠、名称变化、PID reuse、保留后代及完整/部分结果回归，再冻结执行。

## 一次新尝试与不变边界

1. 只写 `exp-079/attempt-3`。保留 attempt 1 的观测分类失败及 attempt 2 的真实资源
   停止和核验失败，不将已取消或未开始任务计入成功。
2. 减少后台应用后重新观测整机状态；每个任务仍要求原定 10 个连续安静样本及低 swap I/O。
   不保证关闭应用足以解决资源压力，不降低 critical、thrashing、RSS 或 MLX 门限。
3. 固定 3 轮 M1-only → Research → Demo，共 9 个任务；每个使用原 340 条完整输入、
   原次序、模型、预算和阈值。仍为 3060 个计划事件、1800 秒总上限。
   未完成时分母仍为 9，历史未回执成本保持未知，不抵消前次失败。
4. 任一真实运行、资源、身份、哈希或独立核验失败即停止后续模型工作，不继续自动重试、
   改预算、调缓存、换模型或放宽安全门。
5. EXP-080 尚未执行。仅在 attempt 3 Completed 且独立 Passed、exp079_complete=true、
   safe-to-continue 后执行原定 Discourse 正式闭环；同时绑定本说明及前次观测修正说明。
   原 EXP-077/078 与旧工件不变。EXP-081 若追加收尾，只写新的 attempt 2，不覆盖旧收尾。

不进行训练、旧 train/validation/test 访问、外部金标泛化、context/C2、对外上传、
commit、stage 或 push。
