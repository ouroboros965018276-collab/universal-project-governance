# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

当前维护观察日期为 **2026-10-16 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

当前候选在 v6 封存后将事实保真指引收敛为对照当前代码、契约和验证检查声明，保留输入域及必要事实。先定位再批读、按授权目标处理边缘契约的指引保持。生成核心为 **6,737 字节**（`b97a3b10…`），规范源身份 `0049006f…`，资格身份 `f78112d7…`；仍为四组指引、16 政策、8 Hot Path、3 默认规则及 18 个交付文件。仓库另有显式标准库 Python 工程配置，执行真实单元测试、包导入、CLI 和文件处理，支持受控删除、未验证与未知分型，以及写入收据绑定的未完成中断；默认及有限 VM 路径保留。[本次工程验收](audits/rc20-registered-project-engineering.audit.json)通过 9 项门禁、922 项测试，另 2 项跳过；202 项受检源码前后一致。公开容器样例与反例通过独立收据核验；新增人工删除样例完成两次实际容器验证，首次独审 88 项通过、133 项输入前后一致。这些均不能代替模型收益。

最近完成的[真实 Python 配对开发轮 v6](audits/rc20-paired-real-python-development-v6.audit.json)有 24 个角色、127 次已知请求，共 **1,370,476** 个报告 token；本轮 pending 为 0。首份独立原始审计 **RAW_INTEGRITY_PASS**，3441 个原始文件、146 项源码及副本前后哈希一致。三名审核者在成本揭盲前锁定全部事实初审：19 项有界支持、5 项 VETO。

v6 使用前一规范身份 `51bdd1a9…` 和有限 CPython 配置。当前 `0049006f…` 及标准库工程配置尚无模型实测收益证据；公开人工样例和纯回归只用于执行器验收，不能重评旧轮或代替独立验证。

| v6 条件 | 机械通过 | 机械与事实均支持 | 报告 token | 角色归属秒数 |
|---|---:|---:|---:|---:|
| RC19 | 8/8 | 7/8 | 458,630 | 472.16 |
| 普通简洁指令对照 | 7/8 | 7/8 | 496,380 | 320.73 |
| RC20 完整组 | 6/8 | 5/8 | 415,466 | 366.49 |

完整组相对 RC19 的 token 下降 **9.41%**、归属耗时下降 **22.38%**；相对普通指令对照，token 下降 **16.30%**、耗时增加 **14.27%**。完整组有两项机械失败及另一项事实否决：未定义工具参数导致提前拒绝、有限语言/边界行为失败、遗漏事实却声称保留，均不能用低成本抵消。提前失败也降低了观测成本，不能称为完成同等任务的节省。数据仅属两个已曝光任务族的开发诊断，**净收益未通过**；共享/启动耗时另列，发布尾部及研究/人工审核总成本未知。

[工程轮 v7](audits/rc20-stdlib-project-development-v7.audit.json)及[v8](audits/rc20-stdlib-project-development-v8.audit.json)因调用和执行器边界问题中断，原失败审计封存。[执行器修正](audits/rc20-runtime-failure-engineering.audit.json)通过九项门禁、931 项回归及六个真实容器用例，另两项回归跳过，公开原始证据独审 PASS。[v9](audits/rc20-stdlib-project-development-v9.audit.json)随后完成 12 次已知请求、71,151 token、pending 为 0；首个角色耗尽请求却未验证，Git 收据校验接口不匹配又触发全局停止，首次原始审计 FAIL。这些工程修正尚不证明模型质量或净收益。

[v10](audits/rc20-stdlib-project-development-v10.audit.json)在 51/54 条工作流后停止，留下 55 个角色记录、193 次有报告用量的请求和一次确认未发送的连接超时，共 **1,036,807 token**、pending 为 0。首次原始独审 PASS：6,189 个原始文件、141 项源码前后一致。首次人工材料抽取因零工具事件角色没有日志而失败，不重抽；人工质量和分组成本未揭盲，整轮不完整，**净收益未建立**。后续只在新身份修正抽取边界并接入原预算内的受限连接重试，旧轮不续跑或重评。

[工具 envelope 修正](audits/rc20-provider-index-engineering.audit.json)接纳合法的可选 ordinal index，并保持原始请求和参数；九项门禁、941 项回归通过，另两项跳过。旧轮没有重评，修正尚不证明任务收益。下一轮将固定新适配器、零事件抽取和原预算内的一次确认未发送连接重试；再以新任务分布、跨 Agent 和来源消融独立验证。默认分支和本地安装仍为 **RC19**。完成调用不证明未来容量或零风险。

[v11 开发对照](audits/rc20-stdlib-project-development-v11.preflight-v2.json)已完成新身份的纯准备；157 项源码绑定，保留同一曝光开发集、运行时、上下文、预算与质量标准。首次纯准备的旧依赖哈希失败保留，随后仅重绑校验器依赖。调用前首审发现旧分析禁止连接重试；新登记明确前瞻修订该条，质量、成本和晋升标准保持不变，首登记与首审保留。[修订登记的独立调用前核验](audits/rc20-stdlib-project-development-v11.precall-closure-v2.json)已通过，157 项源码与 231 项固定输入前后相同；[首次冲突发现](audits/rc20-stdlib-project-development-v11.precall-review.json)保留。当前只发布注册记录，尚未发出该轮模型请求。

历史轮次与原失败结论保留在 [audits/](audits/)，不续跑、重评或绑定当前候选。[v5](audits/rc20-paired-real-python-development-v5.audit.json)的 HTTP 503 留有一次用量未知/pending；新轮 pending 为 0 不清除这一围栏。各轮成本、VETO 和源码身份以各自冻结审计为准。

仓库专用的 API、解释器与隔离执行适配器不随 Skill 安装。人工样例及[工程审计](audits/rc20-cpython-backend-engineering.audit.json)不能替代模型收益；契约能力与限制见[说明](docs/rc20-behavior-contracts.md)。

## 最近一次重要发布：RC19

- 原因：查明 RC18 耗时增加，补足项目事实恢复和真实工具成本记录。
- 发生时间：PR #20 合并于 **2026-10-13T05:51:50Z**，来源为 GitHub `merged_at`；提交 `a98449ce91e8bc60ae0d58fa584cbef7ab87c058`。
- 方法与结果：生成运行时、受控默认分支整合、逐字节部署及独立安装验收。[RC19 安装审计](audits/rc19-installation.audit.json)于 **2026-10-13T05:58:35.911624Z** 观察到 18 个交付文件与合并版本一致、17 个受管哈希、33 条 helper、8 个 BOM 规划输入和官方新进程发现通过。这个时间是验收观察，不是推定的开始时间。
- 限制：[B](docs/rc19-tools-independent-v12.md)与[C](docs/rc19-tools-independent-v13.md)均不完整，净收益门槛 FAIL。RC19 累计 383 次已知完成推理、14,537,062 个报告 token，另 6 次用量未知；原记录与未知调用围栏保留，不继续该候选的追加轮次。安装成功不改变该结论。

RC19 的现状文字后来经 PR #21/#22 同步，`bd4a4d5` 只修正 README 与资格文档，没有改变运行时或其冻结实验身份。历史细节留在原证据及 [CHANGELOG.md](CHANGELOG.md)，不在当前入口重复展开。

## 上一件重要发布：RC18

RC18 修复评分器错误成功判定、压缩指令并记录真实开发对照。PR #19 合并提交为 `29cf112b4629d6b90504b079e95a5370c206a4cb`，GitHub 合并时间 **2026-10-11T21:35:40Z**。该轮总 token 点估计降低 3.84511%，完整回调耗时增加 23.6975%；这引出了 RC19 的耗时诊断。原范围与数字见 [RC18 实测](qualification/pilots/rc18-native/README.md)及[诊断](docs/rc19-latency-diagnosis.md)。

## 验收与接手入口

- 当前维护入口：[MODULE_MAP.md](MODULE_MAP.md)；发布检查：[PUBLISHING.md](PUBLISHING.md)。
- 正式资格：[qualification/README.md](qualification/README.md)，仍 UNASSESSED，locked NOT RUN。现有历史资格失败不重写。
- 本地中断交接由已有 `.governance/handoff.json` 保存；该私有当前状态不随 Skill 交付，不替代版本化政策或冻结实验。
- RC20 的新增真实对照只使用新注册任务和同一工具脚手架；历史中止任务及已曝光开发实例不能重作独立留出。RC19 及开发轮结果也不能包装为独立改善或普遍收益。
