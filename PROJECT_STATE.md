# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

本轮观察日期为 **2026-10-14 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

RC20 原生 CLI 轮次因一次用量未知而中断；API 开发 v1 受执行器反馈处理混杂，v2 虽完成且原始记录核对通过，严格质量与净收益仍 FAIL，含 MiMo 完整版低于两个对照的反转。失败与成本保留在[原生审计](audits/rc20-native-context.audit.json)、[API v1](audits/rc20-api-tools-v1.audit.json)、[API v2 开发审计](audits/rc20-api-tools-v2-development.audit.json)，不作为独立改善证据。

两个官方 API 的[微型原生工具与报告互操作探测](audits/rc20-api-terminal-probe.audit.json)均通过，共 9 次 HTTP、12,519 个报告 token、无未知用量。它只验证脚手架互操作，不验证治理效益。仓库内 API helper 不随 Skill 安装，不给普通项目新增 provider 或密钥依赖。

本次[前瞻 API 轮次](audits/rc20-prospective-api-v1.audit.json)已中止：独立公开合成反例证明，五个 Python 任务族的整模块 AST 相等检查误拒任务允许的等价实现。前缀核账与工具证据 PASS，终态完整性 FAIL、实验有效性与净收益 BLOCKED；原始记录、一次未知请求及其费用预留保留，六条交接链均未到达。旧记录不续跑、重算或作为改善证据。

评分代理现已接入[有限行为契约](docs/rc20-behavior-contracts.md)，按固定探针、接口、调用关系和保护字节验收；公开支持的子语言，保留历史 AST 检查。工程验证和冻结核对通过后，[新前瞻协议](audits/rc20-semantic-api-v1.preregistration.json)与[预调用审计身份](audits/rc20-semantic-api-v1.preflight.json)已发布，真实配对调用正在运行。主要成本比较包含接手角色，发布前还须独立核对结束报告的事实声明；结果尚未完成审计，不能宣布收益。评分器仅在仓库实验中使用，不增加 Skill 交付文件；默认分支和本地安装仍为 RC19。

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
