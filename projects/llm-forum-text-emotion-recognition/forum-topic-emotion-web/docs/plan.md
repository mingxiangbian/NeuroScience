# Phase C 工作进度

## 2026-09-01：最终范围冻结并关闭

用户确认[最终范围决策](../../experiments/stack-overflow-emotion-gold/protocols/dec-phase-c-final-scope-and-closeout-v1.md)：
Phase C.1=`Completed / Verified Pass`；Phase C=`Completed within bounded local research scope`。
当前不再新增同类实验。外部gold、context/C2、长期SLA、多用户、公网部署和商业再发布属于
未来独立范围。旧失败继续有效，EXP-078/080继续Not executed。

## 2026-09-01：Phase C.1最低闭环完成

EXP-086按冻结来源/许可/资源合同完成：400条Python Help公开post，M1/M3阶段各400回执，
46次M3成功、0 fallback；独立source/cost/aggregate/safety verifier Passed。
来源到item limit而非完整时间窗，保留1个truncated topic和无gold边界。

结合EXP-085 attempt2九任务通过，Phase C.1登记的有界运行和第二论坛正式闭环均已完成。
结论只覆盖当前机器固定负载与一次无gold服务链路，不覆盖总体情绪、跨域准确率或SLA。

## 2026-09-01：EXP-085 attempt 2通过，EXP-086随后完成（历史推进记录）

单一回调修复及组合回归后，550项tests通过；attempt 2完成9/9任务、3060结果、5100阶段回执，
独立verification/safety/成本/一致性均通过。通过仅限本机固定负载，保留12个warning和高swap限定。

当时的下一步为EXP-086：固定Python Help category7、100 topics上限、400 posts上限、成功300–400，
Research500/audit0，一次采集和staged推理。只用公开匿名raw、保留许可/来源，不计算accuracy/F1；
该任务现已按协议完成；旧EXP-080和外部gold/context保持不执行。

## 2026-09-01：EXP-085 attempt 1接入失败（历史记录）

完整M1/M3分时网站接入、成本/阶段展示和清理顺序已实现，538项合成测试通过。
实际单次九任务序列98.639秒停止：M1-only340完成，Research的M1预计算340完成，
但回放6项后首次进度回调因参数重名出错。完整verification=Failed/staged_lower_bound_range，
余下7任务及Discourse未启动。进程/服务均已退出，原始采样无资源门触发，不能据此证明M3稳定性。
本次不修冻结工件、不回填事件。随后封存本版、修回调接线并补组合测试，再登记attempt 2；
attempt 1终态继续为Failed。详情及哈希在[HANDOFF](../../experiments/stack-overflow-emotion-gold/HANDOFF.md)。

## Phase C.1：有界运行与第二站点闭环的历史执行链

2026-08-31追加：以下不是原失败的重试。新决策为
[DEC-PHASE-C1](../../experiments/stack-overflow-emotion-gold/protocols/dec-phase-c1-bounded-operational-validation-v1.md)，
EXP-079固定9个fresh-process任务（每个原340条），完成并独立验证安全门后再进入EXP-080。
EXP-080继承原EXP-078采样合同但绑定EXP-079；原EXP-077不变、EXP-078保持未执行。
EXP-079 attempt1因新观察器将Python后代误算为并列worker而取消；代码/工件归档后修正分类。
attempt2在62.498秒触发真实critical pressure：M1完成340/340，Research仅6回执后取消，7任务未启动。
完整verification还因sample36的退出交叠记录缺口Failed；346回执和系统计数仅有单独partial audit。
EXP-080正式采集/Research未执行。EXP-081已记录目标未建立，不代表Phase C.1完成。
随后用户关闭占用应用，并执行只补留痕的attempt3；280项tests通过、原模型和门限不变。
61.144110秒再次因critical停止，仍为1/9完成。此次完整记录独立审核Passed，但运行安全门false；
不能继续080。当前服务/模型均停止，下一步需定位Research峰值内存或明确新的运行环境，不自动重试。
新报告在private/reports/phase-c1-attempt3-reduced-background-report-2026-08-31.md，旧报告保留。
下表保留上一轮事实，不是本阶段成功判定。

后续EXP-082/083诊断已执行：七项Research短诊断成功，但加入完整340项M1前置任务的序列
在Research6/7时触发swap_thrashing。基座/LoRA加载已完成，首次前向未确认返回，终止峰值未知。
记录审核通过，序列/资源未通过；当前370项tests。继续处理资源压力，不自动重跑或推进080。

后续EXP-084分时驻留原型已独立通过：340项M1后，将同次前7项回执交给无M1实例的独立M3进程，
347/347完成、七项功能等价、原资源门通过，438项tests。仍有warning，不证明RSS降低或因果修复。
当时的下一步是扩展完整快照/三模式并接入网站任务接口；该目标后来由EXP-085 attempt 2完成。
EXP-079仍未完成，EXP-080仍未执行。

## 前次阶段记录

Date：2026-08-31。功能与文档已交付；稳定性门未通过，第二站点正式运行安全阻塞。

| 项目 | 当前状态 | 证据 / 尚缺内容 |
| --- | --- | --- |
| C0 数据、模型和任务合同 | 完成 | 原生输入、精确缓存、来源、分母、模式及保留期均固定 |
| C1 上传、Stack Overflow与任务工作台 | 有限验收Verified | EXP-076原4个smoke + source attempt3，340条来源；独立22/22 Passed，旧失败保留 |
| 完整统计和数据控制 | 完成 | 两权重、日周、类型/路由分层、诊断、CSV、单job全文清除；212/212 tests，5任务372条只读QA |
| C2 功能与故障测试 | 实现测试完成 | 取消、晚写、锁、进程退出、回退、资源/身份错误等合成与集成测试 |
| C2 Runtime Soak V2 | 已执行并核验负结果，未完成固定负载 | EXP-077在40.22秒critical pressure停止，1完成/1取消/34未启动；审计Passed不等于Soak Passed |
| C3 Python Help Discourse | 审核、adapter和独立工具完成；正式运行阻塞 | EXP-077为stop-required，不执行EXP-078的300–400条Research任务 |
| C4 CancerEmo / JIRA / 其他外部gold | 用户暂停 | 未下载、未评价，不是泛化结果为负 |
| C5 使用、模型、schema、演示与结论材料 | 已交付当前事实版本 | docs四份材料与private/reports系统报告、Final claims ledger；不隐藏未完成实验 |
| 旧context/C2 | 维持暂停 | 与这里的服务稳定性C2不是同一个分支 |
| 公网部署、长期SLA | 未执行 | 本机有限证据不支持公开生产服务承诺 |

本次不再提交模型任务、重试Soak或绕过前提执行Discourse。后续必须先明确资源问题的处理
方向和新的安全前提；不得原地修改EXP-077协议、负载、模型或终态以取得通过。
网站已恢复用于查看现有历史结果，重放会启动真实新计算，不在当前演示范围。

结果、资源与证据边界见[验收记录](acceptance.md)。原Phase A/B、EXP-076成功与失败均不重跑，
没有stage、commit、push、外部上传或公开部署。
