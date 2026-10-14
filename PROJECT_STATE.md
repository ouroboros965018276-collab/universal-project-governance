# Project State

Current candidate: **3.0.0-rc.20 — Task Context and Complete Change Discipline**.

## 当前工作

基线为 RC19 默认分支 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 正在整合表达相关性、完整改动、证据保真和按需读取；语义由规范源定义：四组执行指引在 Skill 中各保留一次，工作流与恢复细节由既有政策、报告级别和灰测状态按需送入计划。保持 16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；无辅助工具时按同一索引手工解析。

当前维护观察日期为 **2026-10-15 Asia/Shanghai**；精确工作开始时间未知。工程验收、真实对照、默认分支整合与本地安装须分别留存实际结果。未完成的检查不记为通过，缺失用量不记为零；当前不能宣布独立净收益或 Stable。

来源、选用与排除、触发和验收映射由 [upstream-sources.json](third_party/upstream-sources.json) 维护；[鸣谢](THIRD_PARTY_NOTICES.md)保留五个上游及适用许可。三个新增来源的规则组只在预注册对照中消融，不撤销原有正确性、安全、真实性、必需验证或交接约束。

此前的[原生轮次](audits/rc20-native-context.audit.json)、[API v1](audits/rc20-api-tools-v1.audit.json)、[API v2 开发轮次](audits/rc20-api-tools-v2-development.audit.json)及[整模块 AST 前瞻轮次](audits/rc20-prospective-api-v1.audit.json)各自保留失败、混杂与实际费用，不作为独立改善证据。AST 检查误拒等价程序促成有限行为契约；[微型探测](audits/rc20-api-terminal-probe.audit.json)只支持原生工具互操作。旧记录不续跑、重算或合并统计。

评分代理现已接入[有限行为契约](docs/rc20-behavior-contracts.md)，按固定探针、接口、调用关系和保护字节验收；公开支持的子语言，保留历史 AST 检查。[前瞻协议](audits/rc20-semantic-api-v1.preregistration.json)与[预调用身份](audits/rc20-semantic-api-v1.preflight.json)在调用前发布。[终态审计](audits/rc20-semantic-api-v1.audit.json)确认：38 个执行结果、2,656,915 个已知报告 token、18 个严格通过；一笔 DeepSeek 请求用量未知触发全轮停止，六条交接链未到达。原始核账与工具证据 PASS，主要成本 BLOCKED、净收益 FAIL；未知费用保留。独立事实复核覆盖全部 18 份结束报告，限制一处无证据的错误原因归因；复核不能改变机械失败或授予发布。

当前候选核心说明为 6,433 字节；工具入口提供相同的公开路径清单、有界诊断及安全网络阶段记录，分开旧 JSON 与新原生工具结束协议，并移除交接中的无关必读路径，保留保护字节检查。[开发轮次 v3](audits/rc20-tools-v3-development.audit.json)已结束：16 个实际 actor，独立严格通过 6 个，137 次 HTTP、1,492,346 个已报告 token、410.047 秒，无未知用量；两个源端失败，接收者未调用。核账通过不改变任务质量失败，也不证明净收益。

上述输出结构与反馈缺口已修正；[显式推理开发轮](audits/rc20-thinking-development-v1.audit.json)仍未通过：2 个执行结果、0 个严格通过，241,092 个已知报告 token；一笔 MiMo 请求用量未知触发停止，文档及接收者未调用。DeepSeek 漏掉公开空值契约并反复修补；MiMo 最后一笔响应未在执行预算内返回，原因未确认。独立审计器漏列结束工具的失败记录与单独请求绑定补充检查均保留，不改变任务失败或未知费用。下一步检验契约阅读与治理上下文的影响，并修正未来审计器的跨实现测试；旧数据不重评。评分器和 provider helper 仅在仓库实验中使用，不增加 Skill 交付文件或安装依赖。默认分支和本地安装仍为 RC19；开发通过后仍须新冻结任务的独立对照。

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
