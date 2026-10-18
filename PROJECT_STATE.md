# Project State

当前候选为 **3.0.0-rc.20 — Task Context and Complete Change Discipline**；默认分支与本地安装仍为 **RC19**，默认提交 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 尚未合并或安装，真实净收益未建立。观察日期：**2026-10-19 Asia/Shanghai**；精确工作开始时间未知。

## 当前能力与验证

表达相关性、完整改动、事实保真和按需读取由[规范源](governance-src/model/governance-model.json)统一编译。当前生成核心 **6,976 字节**，四组指引、16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；规范文件身份 `1ec318f1…`，资格指纹 `269a01eb…`。五个上游的固定来源、许可、适配与排除记录见 [选择性来源映射](docs/upstream-rule-map.md)及[许可记录](third_party/notices/README.md)。实验适配器不随 Skill 交付。

公开校准基线 [source21](audits/rc20-source21-real-backend-and-public-quality.audit.json)完成两模型、15 次请求，报告 394,673 token、无待结算，总耗时约 389 秒。固定镜像和 C 盘挂载的前置验收通过，容器及临时源码清理已确认。首次独立盲审全锁定后解盲：DeepSeek 九项全部通过；MiMo 功能检查通过，但 README 的 Unicode 示例和验证次数存在错误，四项语义要求未通过，无严重否决。不能宣称净收益或晋升。

最新 [source22 九族配对对照](audits/rc20-primary22-insufficient-balance.audit.json)已执行 **54/54 个流程**，前 36 项复用，未重跑。三段分别保留原件：最初 34 项、内存故障前续跑 2 项、本次续跑 18 项；66 个计划角色中实际调用 60 个，6 个接手阶段因前序未达到约定交接点而未调用。66 包、522 项要求的首次独立盲评已锁定并解盲：RC19、attention、RC20 分别通过 **2/18、4/18、2/18** 个流程；RC20 有一项 CSV 数据完整性／公式安全严重否决，并在三个配对块发生退步。原标准主结果和两组中断敏感性均失败，禁止晋升。该结果属于调整前冻结候选 `adefef22…`，不得继承为新候选的效果证据。

原始请求的可观测成本汇总：RC20 已报告 token 比固定 RC19 少约 **22.38%**、比 attention 少约 **13.62%**；完整流程耗时分别增加 **5.74%**、**7.30%**。这些成本仅是已知分量，质量及角色完整性门槛失败后不能作为净收益。暂停同版本后续付费批次，按真实失败修正后再进行独立对照。原 HTTP 402、MemoryError 的未知用量，以及不必要整批重开另耗的 876,827 个已报告 token 均保留。两处汇总程序的元数据错误已在独立修正收据中记录；没有重跑模型、重抽评审包或改变评分标准。

不再重复公开校准。质量、安全、token、完整工作流耗时及独立接手门槛不变；另检查排除余额中断所在整个三臂配对块，以及同时排除内存中断配对块后的结果。API 诊断已补充明确的 HTTP JSON 拒绝原因，同时保留未知用量与禁止自动重试，原 14 项离线回归通过。本次另修复流式轮询的重复正文复制，并覆盖内存异常下的真实 worker／未知费用记录；14 项定向检查和另外 2 项既有非流式检查通过，冻结实测代码未改。这些工程检查不构成效果提升证据。[此前宿主中断](audits/rc20-source21-host-capacity.audit.json)的调用与备份／回退记录仍冻结。

针对本轮真实失败，当前候选已在既有 `EVIDENCE_AFFECTED` 中明确风险相称的关键不变量与异常／组合边界验证，未增加规则数，生成运行时仅增加 171 字节。适配器将已结算的输出截断标记为未完成，并提供独立显式容量配置；旧配置与冻结实测代码保持。后续两次真实尝试均未建立收益：首项完成后遇到审计导入错误，已验证并保留原结果；新登记对照的首个 MiMo 任务在第 17 次请求后触及 512 KiB 输入上限。两次原研究保持 BLOCK，费用、已知失败及未调用分母全部保留。同预算内的事实检查点候选通过离线检查后，按原三类任务和 15 个角色开展开发重测：前两个 API 角色最终功能验证均为 2/2，但缺少必需检索证据，机械验收失败；随后 CLI 结果因缺失共享验证函数中断审计。原 CLI 调用已直接纠正性复核，未重跑模型，机械结果仍失败；原账本、待定项和首次错误未改写。统一向三组公开任务原有工具义务后的开发重测，在 4 次 API 请求、52,290 个已报告 token 后于容器启动前中断：安全扫描将公开的 `task-…` 路径误匹配为密钥。原未知执行和失败不改写，受控容器已独立确认不存在；当前没有付费进程。零模型 Docker 诊断确认两项检查及清理通过；独立审阅发现全局词法边界修复会漏检拼接密钥，因此已撤回。保留原安全规则后，中性机器目录入口的真实 Docker 检查同样 2/2 通过，冻结输入逐字节一致且清理完成，模型调用为零。尚无净收益；已暴露任务不再称为独立 holdout。

此前 [source19 两模型公开校准](audits/rc20-source19-capability-and-environment.audit.json)完成 19 次请求记账、无待结算；DeepSeek 通过，关闭推理的 MiMo 机械失败且语义 **VETO**。旧失败和成本单独保留，不由本轮结果覆盖。

[UltraSpeed 可用性与工具格式核验](audits/rc20-ultraspeed-native-compatibility.audit.json)的两次公开单请求均正常关闭，共报告 1,345 token；启用推理及 strict 后，约 3.1 秒返回符合原 schema 的虚拟补丁调用，未执行工具。新研究配置保留旧配置与本地校验；真实任务质量、同条件成本与持续容量仍未证明。[上一轮](audits/rc20-source18-hybrid-tool-contract.audit.json)及[深度推理耗时诊断](audits/rc20-source17-latency-and-quality.audit.json)保留原结果；不得以速度抵消质量否决或放宽完成标准。

此前[九族配对实测](audits/rc20-primary14-incomplete-transport.audit.json)在第 27 个流程因 HTTP 响应体 `IncompleteRead` 中断。预注册分母仍为 **54 个流程／66 个角色**；已发布 26 个流程、29 个角色记录，第 157 次请求用量与费用未知。原失败、待定预留和未完成范围全部保留；首次整体审计、语义盲评和净收益分析的前置条件未满足。事后确认原 23 个容器及 69 个临时路径不存在，不追认业务成功。较早的[非流式两模型校准及四角色中断控制](audits/rc20-reasoning-input-budget-diagnosis-v1.audit.json)是历史记录，不构成当前净收益证明。

合并与安装仍须完成：

- 固定 RC19、attention control 和完整组的同条件配对；完整组质量不劣、无严重否决，报告 token 和完整工作流耗时均严格低于两组对照。
- 当前候选的四规则组消融、真实 API／CLI 跨 Agent 接手，以及独立未暴露任务验证。
- 生成一致性、完整性、安装副本身份及有效加载核验。

未知用量、缺失耗时、意外中断或超限不能作为零成本或成功。研究、人工及未观测总成本保持未知。正式资格 **UNASSESSED**，locked **NOT RUN**，不宣称 Stable。

此前的[完整九族配对](audits/rc20-primary9-closed-negative-development-v1.audit.json)、[来源消融](audits/rc20-guidance-ablation-v2.audit.json)和[六工作流校准](audits/rc20-public-six-feedback-negative-v1.audit.json)均未证明收益。[跨 API／CLI 公开校准](audits/rc20-public-mixed-and-budget-calibrations-v1.audit.json)只验证了运行、原始记录与预算闭包。[长响应与可选用量修正](audits/rc20-two-pro-reasoning-prefix-v1.audit.json)、[截止时间修正](audits/rc20-clock-entry-correction-v1.audit.json)保留对应首次失败。历史原件、首次评分和未知用量均冻结在各自审计中，不重新判定或绑定为当前有效性证明；早期轮次入口见[开发集成检查点](audits/rc20-development-integration-checkpoint-v1.audit.json)。

## 最近一次重要发布：RC19

PR #20 于 **2026-10-13T05:51:50Z** 合并，提交 `a98449ce91e8bc60ae0d58fa584cbef7ab87c058`。原因是诊断 RC18 耗时增加，并补足项目事实恢复与真实工具成本记录；方法是生成运行时、受控合并、逐字节部署和独立安装验收。

[安装审计](audits/rc19-installation.audit.json)于 **2026-10-13T05:58:35.911624Z** 确认 18 个交付文件与合并版本一致，完整性、规划输入和官方新进程发现通过。该时间是验收观察。[独立 B](docs/rc19-tools-independent-v12.md) 与[追加 C](docs/rc19-tools-independent-v13.md) 均不完整，净收益门槛 FAIL；安装成功不改变该结论。后续 PR #21/#22 只修正文档现状，没有改变冻结运行时。

## 上一件重要发布：RC18

PR #19 于 **2026-10-11T21:35:40Z** 合并，提交 `29cf112b4629d6b90504b079e95a5370c206a4cb`。RC18 修复评分器错误成功判定、压缩指令并记录真实开发对照；该轮 token 点估计降低 **3.84511%**、完整回调耗时增加 **23.6975%**，由此引出 RC19 的耗时诊断。范围与原始结果见 [RC18 实测](qualification/pilots/rc18-native/README.md)及[诊断](docs/rc19-latency-diagnosis.md)。

## 接手入口

- 按任务定位实现、契约、消费者和测试：[MODULE_MAP.md](MODULE_MAP.md)。
- 发布及资格：[PUBLISHING.md](PUBLISHING.md)、[qualification/README.md](qualification/README.md)。实验边界见[工程契约](docs/rc20-behavior-contracts.md)。
- 本地未完成工作使用既有 `.governance/handoff.json`；它不随 Skill 交付，也不替代版本化政策或冻结证据。
- 重要历史及设计原因：[CHANGELOG.md](CHANGELOG.md)、[DECISIONS.md](DECISIONS.md)。
