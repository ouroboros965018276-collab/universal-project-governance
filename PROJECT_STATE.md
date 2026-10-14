# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

当前维护观察日期为 **2026-10-15 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

当前规范源仅收敛两处：交付按需陈述结果、证据和缺口；当前记录遵循**明确声明**的阶段 schema，安全退休旧字段，并保留必要事实与未知。无法表达时披露缺口，不为展示治理另造字段或文件。生成核心为 **6,624 字节**（`75492e34…`），规范源身份 `badb891e…`，新资格身份 `d7888ee6…`；当前版本仍为 RC20 候选。旧身份与旧结果不重绑定，字节减少不等于任务收益。新候选的[工程门禁与完整回归](audits/rc20-stage-schema-engineering.audit.json)通过，真实模型收益仍待新任务检验。

最新[真实 Python 配对开发轮](audits/rc20-paired-real-python-development-v2.audit.json)已经结束并保全：24 个角色、130 次已知请求、1,580,447 个报告 token，pending 为 0。有限 CPython 探针实际执行，机械检查 23/24；唯一失败是接手者读取后剩余时间不足，下一次请求被本地拒绝。没有观察到余额不足响应。

该轮 RC20 完整版与 RC19 均机械通过 8/8，但完整版 token 增加 **22.63%**、角色归属墙时增加 **109.95%**；全组事实审阅另保留 5 项 VETO、11 项 UNKNOWN、8 项有界支持。VETO 涉及报告工具归因及一项存在审阅分歧的文档相关性判断，不能把机械通过写成整体成功。该轮是开发诊断，不证明独立净收益、任意应用安全或突然中断恢复。

下一轮先修正实验规范：明确 JSON 比较方式，并允许接手者更新受影响 README，消除“当前文档必须真实却禁止修改”的冲突。阶段字段返工还受公开比较规则欠说明影响，不能全部归因于 UPG。采用新任务、新身份重新注册；旧严格评分、失败、费用与未知项保持原样。默认分支和本地安装仍为 **RC19**，合并、安装及 Stable 各自受证据门槛约束。

仓库专用的 API、解释器与隔离执行适配器不随 Skill 安装。[显式 CPython 工程审计](audits/rc20-cpython-backend-engineering.audit.json)与人工固定样例回归属于工程证据，不能替代模型任务净收益。历史[原生轮次](audits/rc20-native-context.audit.json)、[API v1](audits/rc20-api-tools-v1.audit.json)、[API v2](audits/rc20-api-tools-v2-development.audit.json)、[AST](audits/rc20-prospective-api-v1.audit.json)、[语义](audits/rc20-semantic-api-v1.audit.json)、[开发 v3](audits/rc20-tools-v3-development.audit.json)、[推理](audits/rc20-thinking-development-v1.audit.json)、[上下文 v1](audits/rc20-contract-context-development-v1.audit.json)、[上下文 v2](audits/rc20-public-contract-context-development-v2.audit.json)和[计划接手 v4](audits/rc20-handoff-tools-development-v4.audit.json)保留原证据；不续跑、重评或合并。有限契约的范围见[说明](docs/rc20-behavior-contracts.md)。

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
