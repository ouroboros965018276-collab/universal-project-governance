# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

当前维护观察日期为 **2026-10-15 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

当前候选在 v4 封存后收敛两条既有规则：先选择相关路径再批读；仅按已授权目标改变边缘返回或异常契约。必读、依赖扩读、未知和事实恢复义务保留。生成核心为 **6,642 字节**（`803f1da4…`），规范源身份 `51bdd1a9…`，资格身份 `4cf36631…`。仓库适配器新增显式公开语言提醒，不改变原评分或执行门禁；独立评审发现的命名路径漏测已复现并修正。[本次工程验收](audits/rc20-read-contract-feedback-engineering.audit.json)为 9 项门禁、821 项测试通过及 2 项跳过；这些不证明真实收益，新源码尚待新轮预注册与实测。

最新[真实 Python 配对开发轮 v4](audits/rc20-paired-real-python-development-v4.audit.json)已完成：24 个角色全部返回，独立机械检查通过 21 个；140 次请求共 **1,613,204** 个报告 token，最终 pending 为 0。首份独立原始审计 **RAW_INTEGRITY_PASS**，3478 个原始文件与 128 项源文件及副本前后哈希一致。完整组相对 RC19 的角色归属耗时下降 **30.52%**，但 token 增加 **2.60%**；相对简洁指令对照，token 增加 **6.51%**。三组机械检查均为 7/8；完整组事实审阅为 6 项有界支持、1 项 VETO、1 项因审阅准备偏差受限的 UNKNOWN。完整组把“None 返回 False”改成抛异常并写成已完成，不能用执行器限制解释或挽救。

本轮保留质量与成本失败，未取得可晋升的净收益；其源码身份与当前候选不同。下一步以新任务、相同预算和独立审计验证当前候选，再补齐独立验证与来源消融。默认分支和本地安装仍为 **RC19**。本轮没有实际触发连接重试，不能宣称该恢复策略已获真实故障验证。

历史[开发轮 v3](audits/rc20-paired-real-python-development-v3.audit.json)是不完整轮次，首份独审 RAW_INTEGRITY_FAIL；审计器额外要求受保护源端 README 必读的问题只在后续新身份修正，旧轮未重评。[开发轮 v2](audits/rc20-paired-real-python-development-v2.audit.json)使用旧规范身份，完整组 token 增加 22.63%、角色归属耗时增加 109.95%。历史审计与未知项继续冻结，不续跑、不重评、不重绑定当前候选。

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
