# Project State

当前候选为 **3.0.0-rc.20 — Task Context and Complete Change Discipline**；默认分支与本地安装仍为 **RC19**，默认提交 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 尚未合并或安装，真实净收益未建立。观察日期：**2026-10-16 Asia/Shanghai**；精确工作开始时间未知。

## 当前能力与验证

表达相关性、完整改动、事实保真和按需读取统一由[规范源](governance-src/model/governance-model.json)编译。针对最新失败，两个现有指引补足文件存在性、修改语义和收尾预算；新生成核心 **6,909 字节**，仍为四组指引、16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件，规范身份 `3b84fc59…`、新资格身份 `904542bb…`。此前封存实测使用 `0049006f…`／`f78112d7…`，不能验证新候选。五个上游的版本、许可、适配及排除见[来源清单](third_party/upstream-sources.json)和[鸣谢](THIRD_PARTY_NOTICES.md)。仓库专用评测源码不随 Skill 交付。

已推送提交 `bb60947fd1579f7335af16d37b7dc8e75b749352` 的 [11 项 CI](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/38855073310) 全部通过，本地编译、治理、导航和仓库检查通过。这些是工程验证。[API 四阶段](audits/rc20-managed-api-four-phase-calibration-v4.audit.json)、[原生 CLI 正常及已知失败](audits/rc20-native-cli-public-calibration-v8.audit.json)和[四项公开工具契约控制](audits/rc20-public-tool-contract-controls-v3.audit.json)完成首次原始校验及独立字节保全；工具契约控制调用真实模型 **0 次**。它们不证明治理效果或净收益。

当前未发布修复通过九项本地门禁和完整单元测试 **1,110 项（3 项跳过）**，新冻结身份如上。首次隔离测试入口缺少仓库导入路径，两模块导入失败；保留原结果，补足显式路径后的完整运行通过。独立代码复核发现的批次总量回归已修复闭合。[独立新鲜任务离线资格](audits/rc20-fresh-fixture-qualification-v3.audit.json)的 **154 项控制通过**，真实模型调用为 0；任务与评分正文仍未向候选作者暴露，跨模型工程实测尚未开始。

[九族开发配对驱动](qualification/pilots/rc20-primary/README.md)及[v4 紧凑源码修订](qualification/pilots/rc20-primary-v4/README.md)可追溯重建。此前三项整合结果由一份[整合检查点审计](audits/rc20-development-integration-checkpoint-v1.audit.json)保存：

- **九族 v4**：运行与首次原始审计均退出 0，61 个角色原始证明通过、5 个未调用角色保留。首次盲评打包混淆注册中断与实际中断而失败，未完成评分锁；不能据此得出质量或净收益。8,495 项原件归档完成独立字节核验。新 helper 及完整 66 包合成控制经非作者复核，旧轮不重新提取或评分。
- **九族 v6**：[源码](qualification/pilots/rc20-primary-v6/README.md)对应的新轮运行及首次原始审计退出 0，62 个角色原始证明通过、4 个未调用。六名独立评审完成 66 包、522 项要求，全部初评锁定后才解盲；[固定分析原始结果与只读诊断](audits/rc20-primary6-closed-negative-development-v1.audit.json)为负，三臂工作流通过数均为 0，完整组有两项严重否决，主 token 与耗时均为未知。失败来自真实工具契约使用、预算和时限，未发现消费器状态不兼容或模型容量问题；35 次读取未创建路径，两项严重否决均误将片段当整文件替换。当前源码据此改进读取与显式片段修改契约；已锁定初评和原负面结果不变，不能使用已知成本片段宣称节省。
- **四规则组消融**：首轮因读取器计数顺序不一致停止，原轮不重新判定。修复后的[新轮](audits/rc20-guidance-ablation-v2.audit.json)运行与首次原始审计退出 0，16 个角色原始证明通过，16 包、144 项要求全部独立初评锁定后才解盲。四组质量门槛均失败或未知，token／耗时比较均为未知，未证明规则组贡献；不能据此认定任何上游有利或有害。
- **跨 API／CLI 公开接手**：此前[首轮读取异常](audits/rc20-public-mixed-first-failure-v3.audit.json)保留。命令数组读取修复后的新轮发生 CLI 连接发送失败；前两次工具调用成功，无完成回合用量。未观察到容量或余额错误，更深层网络原因未知。新公开校准轮复用身份一致的冻结源码与规划结果，使用新项目、协议和授权，已完成两个方向的两条自然工作流及四个角色，首次原始审计通过；完整运行约 140.60 秒，用量按模型分域记录，[独立字节保全及预算控制](audits/rc20-public-mixed-and-budget-calibrations-v1.audit.json)均已完成。它不证明语义质量、突发中断恢复或净收益，旧轮未知用量不清除。

合并和安装要求完整组质量不劣于 RC19 与 attention control、无严重否决，报告 token 与完整工作流耗时均严格低于两组对照，并补足来源消融、真实跨 Agent 接手和独立未暴露验证。未知用量、意外中断、缺失耗时或超限阻止有利净收益结论。研究、人工及未观测总成本保持未知。正式资格 **UNASSESSED**，locked **NOT RUN**，不宣称 Stable。其他已曝光开发结果、首次失败及冻结实验限制保留在各自 [audits/](audits/)，不绑定为当前候选的有效性证明。

## 最近一次重要发布：RC19

PR #20 于 **2026-10-13T05:51:50Z** 合并，提交 `a98449ce91e8bc60ae0d58fa584cbef7ab87c058`。原因是诊断 RC18 耗时增加，并补足项目事实恢复与真实工具成本记录；方法是生成运行时、受控合并、逐字节部署和独立安装验收。

[安装审计](audits/rc19-installation.audit.json)于 **2026-10-13T05:58:35.911624Z** 确认 18 个交付文件与合并版本一致，完整性、规划输入和官方新进程发现通过。该时间是验收观察。[独立 B](docs/rc19-tools-independent-v12.md) 与[追加 C](docs/rc19-tools-independent-v13.md) 均不完整，净收益门槛 FAIL；安装成功不改变该结论。后续 PR #21/#22 只修正文档现状，没有改变冻结运行时。

## 上一件重要发布：RC18

PR #19 于 **2026-10-11T21:35:40Z** 合并，提交 `29cf112b4629d6b90504b079e95a5370c206a4cb`。RC18 修复评分器错误成功判定、压缩指令并记录真实开发对照；该轮 token 点估计降低 **3.84511%**、完整回调耗时增加 **23.6975%**，由此引出 RC19 的耗时诊断。范围与原始结果见 [RC18 实测](qualification/pilots/rc18-native/README.md)及[诊断](docs/rc19-latency-diagnosis.md)。

## 接手入口

- 按任务定位实现、契约、消费者和测试：[MODULE_MAP.md](MODULE_MAP.md)。
- 发布及资格：[PUBLISHING.md](PUBLISHING.md)、[qualification/README.md](qualification/README.md)。仓库专用实验适配器不随 Skill 安装，边界见[工程契约](docs/rc20-behavior-contracts.md)。
- 本地未完成工作使用既有 `.governance/handoff.json`；它不随 Skill 交付，也不替代版本化政策或冻结证据。
- 重要历史及设计原因：[CHANGELOG.md](CHANGELOG.md)、[DECISIONS.md](DECISIONS.md)。
