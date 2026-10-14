# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

当前维护观察日期为 **2026-10-15 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

历史[原生轮次](audits/rc20-native-context.audit.json)、[API v1](audits/rc20-api-tools-v1.audit.json)、[API v2](audits/rc20-api-tools-v2-development.audit.json)、[AST 轮次](audits/rc20-prospective-api-v1.audit.json)、[语义前瞻](audits/rc20-semantic-api-v1.audit.json)、[开发 v3](audits/rc20-tools-v3-development.audit.json)、[推理开发](audits/rc20-thinking-development-v1.audit.json)与[上下文开发 v1](audits/rc20-contract-context-development-v1.audit.json)的失败、混杂和费用保持原记录；不续跑、重评或合并。评分代理现按[有限行为契约](docs/rc20-behavior-contracts.md)检查固定探针、接口、调用关系和保护字节。解释器、API 适配器及实验脚本只在仓库中使用，不随 Skill 安装；这些任务没有执行应用代码。

公开文本任务现明确空值、类型转换、前缀与大小写语义，各角色投影经独立复核；原 Python 程序、行为探针和通过条件未变，公开契约及其绑定哈希更新。下述上下文开发 v2 使用该次冻结的 6,433 字节核心；后续候选变化不重写其身份或结果。

当前候选将已有按需读取指引明确为：从任务路径与模块／符号／文档锚点选择初始读取，推迟明确无关的材料；遇到依赖、索引冲突或验证缺口时扩大范围。未增加硬读取上限或新规则组。生成核心为 6,492 字节（`7022d8e6…`），当前资格身份为 `ef3bbf0c…`；旧身份保留在原实验快照。工程基线 `a0b33f8` 的独立语义复核、九项本地门禁和 11 项托管作业通过；769 项测试中 767 项通过、2 项平台跳过，检查前后源码一致（完整记录 `7cb12356…`）。这些检查不证明任务收益，后续实验适配器变化也须单独验证。

实验 API 现新增显式 `thinking-enabled-flash-8192-v1`：DeepSeek 配置保持不变，MiMo 使用 `mimo-v2.6-flash`，输出上限 8192；无回退或重试。旧默认与 Pro 配置的 16 份请求经独立逐字节对照一致，新配置记录实际剩余等待参数。独立复核、九项本地门禁通过，777 项测试中 775 项通过、2 项平台跳过，源码前后一致（记录 `2ce0c735…`）。这只是适配器工程验证，尚未证明 Flash 速度、质量或 RC20 净收益；安装包保持原样。

此前[上下文开发 v2](audits/rc20-public-contract-context-development-v2.audit.json)的六个源端机械结果通过，报告含一项 VETO；RC20 在两模型上的成本方向不同。每格仅一次且顺序未随机，不能推断净收益。旧轮的失败、费用与未知项保留。

最新[计划接手开发 v4](audits/rc20-handoff-tools-development-v4.audit.json)已终止并保全：8 个计划角色仅返回 3 个，2 项机械检查通过，另 5 个未执行，文档角色均未运行。已知报告 token 为 119,552，完整轮次墙时 357.881 秒，另保留一次未知用量及费用预留。一个角色在第四请求等待时耗尽本地 180 秒总预算；底层 HTTP 阶段、供应商状态和最终费用未知，不能归因为余额或排队。

该轮代码／HANDOFF 事实有界支持；报告为 1 份有界支持、1 份仍含未知声明、1 份缺失。独立核账通过不改变这些限制，也不证明净收益。下一步冻结新的文档优先配对接手开发轮；显式后端已通过一次真实回归：人工固定样例的正常执行、结果过大拒绝、超时收据与清理均观察到，源码前后一致（记录 `62a9825b…`）；这不证明模型任务质量、任意应用安全或崩溃恢复。模型任务的真实 CPython 对照仍待运行。默认分支和本地安装仍为 RC19，RC20 合并、安装及 Stable 继续受证据门槛约束。

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
