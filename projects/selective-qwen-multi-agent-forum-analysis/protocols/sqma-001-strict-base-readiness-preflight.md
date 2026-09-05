# SQMA-001：Strict Agent-Dev Base Readiness Preflight

日期：2026-09-03

层级：`Minor / no-result / no-training`

状态：`Registered / execution authorized for static preflight only`

## 1. 目的

SQMA-001只检查 strict Agent-Dev base production 的依赖身份、显式fold计划、scoped-input边界、无模型运行条件和资源门。它不生成M1/M3 logits，也不评价模型或Agent效果。

本次通过最多支持：

> Agent-Dev strict base production 的静态依赖和三折计划已通过无训练preflight；正式训练仍阻塞于独立scoped-input materialization和新的formal protocol。

不得写成strict outputs已产生、Agent preflight已可运行或formal training已授权。

## 2. 当前活动范围

首个formal只允许三个fit：

| Fit | Train folds | Held-out fold | Train rows | Held-out rows |
| --- | --- | ---: | ---: | ---: |
| `dev-h0` | 1,2 | 0 | 1,344 | 672 |
| `dev-h1` | 0,2 | 1 | 1,344 | 672 |
| `dev-h2` | 0,1 | 2 | 1,344 | 672 |

未来的`tune-h3`与三个`final-h*`只在D0中保留为声明性计划。本次不读取其row、创建其路径或给予训练权限。

## 3. Scoped-input硬门

原private train与fold manifest包含全部3,360行。正式Dev训练producer不得打开这两个完整源文件，也不得采用`fold != heldout`式补集选择。

后续必须由独立data steward建立三个fold各自的密封输入：

1. train-capable：text + gold，仅供该fold作为训练成员时使用；
2. gold-free inference：text，无gold，仅供held-out forward；
3. consumer-only gold：只供后续独立评价consumer。

Agent-Dev producer配置只能出现folds 0–2的snapshot记录。snapshot须为0600、保持原train source order、绑定row/component/order hash，并证明fold 3/4 rows为0。

SQMA-001不读取、解析或创建这些private snapshot，只冻结和测试其合同。

## 4. 允许访问

- D0 static contract、dependency manifest及已登记hash；
- SQMA-001 protocol/config/contract/runner/verifier/tests；
- public fold manifest与fold summary；
- M1/M3模型manifest及模型文件的流式身份核对；
- 两个冻结runtime的Python/architecture与dist-info版本；
- synthetic fixtures、free disk和当前进程资源。

## 5. 禁止访问和执行

- 不加载模型、不执行forward、optimizer或训练；
- 不解析private train、private fold manifest、NPZ或任何真实row；
- 不打开Confirm raw NPZ，不访问fold 3/4 text、gold、logits或派生值；
- 不访问原validation/test；
- 不调用Agent，不访问网络，不下载或上传数据；
- 不创建formal训练目录、checkpoint或private row-level output；
- 不计算模型指标、阈值、calibration或Router。

## 6. 静态成功门

1. protocol/config/contract/runner/verifier/tests身份一致，目标output dir在运行前不存在且无symlink。
2. D0 static contract与dependency manifest身份一致；formal相关authorization保持false。
3. 活动计划严格等于三个Dev fit；任一fold 3/4、wildcard、自动发现、重复、缺项或heldout进入train均失败。
4. public fold manifest重放得到固定rows/components、训练与held-out component overlap为0。
5. M1计划为84 steps/epoch、warmup42、4 epochs共336 steps；M3为2,688 optimizer steps。
6. M1/M3模型资产与runtime身份通过，只做hash/metadata核对，不import模型框架。
7. scoped-input三类schema与gold-free held-out logit schema通过synthetic tests；held-out logits禁止`gold`。
8. 独立verifier不import runner或模型库，并重新计算schedule、依赖与public privacy。
9. wall不超过300秒、RSS不超过1 GiB、public output不超过16 MiB、free disk至少20 GiB、0模型/MLX/Agent/网络/孤儿进程。

若静态检查通过但free disk不足，状态只能是`BlockedForFormalResource`。任何identity、access或输出目录漂移均失败即停，不自动修复或重试。

## 7. 输出与完成口径

Public attempt目录只允许：

- `run.json`
- `verification.json`
- `complete.json`，仅在独立verification Passed后生成

不得建立private结果目录。完成记录必须明确：

- `sqma001_complete=true`
- `training_executed=false`
- `model_loaded=false`
- `private_rows_parsed=false`
- `strict_outputs_exist=false`
- `formal_training_authorized=false`
- `next_gate=independent Dev-only scoped-input materialization`

SQMA-001通过后不自动启动下一单元。
