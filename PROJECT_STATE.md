# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

当前维护观察日期为 **2026-10-15 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

历史[原生轮次](audits/rc20-native-context.audit.json)、[API v1](audits/rc20-api-tools-v1.audit.json)、[API v2](audits/rc20-api-tools-v2-development.audit.json)、[AST 轮次](audits/rc20-prospective-api-v1.audit.json)、[语义前瞻](audits/rc20-semantic-api-v1.audit.json)、[开发 v3](audits/rc20-tools-v3-development.audit.json)、[推理开发](audits/rc20-thinking-development-v1.audit.json)与[上下文开发 v1](audits/rc20-contract-context-development-v1.audit.json)的失败、混杂和费用保持原记录；不续跑、重评或合并。评分代理现按[有限行为契约](docs/rc20-behavior-contracts.md)检查固定探针、接口、调用关系和保护字节。解释器、API 适配器及实验脚本只在仓库中使用，不随 Skill 安装；这些任务没有执行应用代码。

公开文本任务现明确空值、类型转换、前缀与大小写语义，各角色投影经独立复核；原 Python 程序、行为探针和通过条件未变，公开契约及其绑定哈希更新。修正后九项工程门禁通过，769 项测试中 767 项通过、2 项平台跳过；候选核心仍为 6,433 字节。这些检查不证明任务收益。

最新[上下文开发 v2](audits/rc20-public-contract-context-development-v2.audit.json)已结束并独立核账：6 个实际执行结果均通过机械源端契约；代码与 HANDOFF 事实有界支持，5 份报告有界支持、1 份报告含被否决的工作区状态声明。27 个请求均保留响应，329,520 个已知报告 token，轮次执行墙时 352.969 秒，无本轮待核用量；审阅窗口与未知研究 token 另记，旧轮未知费用保持不变。

本轮 RC20 在 DeepSeek 上的 token／耗时高于两组对照，在 MiMo 上较低。每格仅一次、顺序未随机，不能推断净收益。下一步检查初始读取选择，并补齐代码和文档的双向跨模型计划交接；尚未验证真实崩溃恢复。默认分支和本地安装仍为 RC19，RC20 合并、安装及 Stable 均未获本轮证据支持。

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
- RC20 的新增真实对照只使用新注册任务和同一工具脚手架；本次中止任务已曝光，不能重作独立留出。RC19 及开发轮结果也不能包装为独立改善或普遍收益。
