# Project State

当前候选为 **3.0.0-rc.20 — Task Context and Complete Change Discipline**；默认分支与本地安装仍为 **RC19**，默认提交 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。RC20 尚未合并或安装，真实净收益未建立。观察日期：**2026-10-18 Asia/Shanghai**；精确工作开始时间未知。

## 当前能力与验证

表达相关性、完整改动、事实保真和按需读取由[规范源](governance-src/model/governance-model.json)统一编译。当前生成核心 **6,976 字节**，四组指引、16 项政策、8 项 Hot Path、3 项默认规则和 18 个交付文件；规范身份 `adefef22…`，资格指纹 `74075f35…`。五个上游的固定来源、许可、适配与排除记录见 [选择性来源映射](docs/upstream-rule-map.md)及[许可记录](third_party/notices/README.md)。实验适配器不随 Skill 交付。

最近的[两模型真实工具校准及四角色中断控制](audits/rc20-reasoning-input-budget-diagnosis-v1.audit.json)均已关闭，首次原始校验与最终账本核验通过。两模型轮 12 次请求全部结算，已知报告用量 **257,899 token**，关闭记录发布前约 **607.69 秒**；两个盲审包、18 项要求的初评先全部锁定，再揭盲：**MiMo 完整通过，DeepSeek 为未完成／UNKNOWN**。DeepSeek 在约 208.50 秒时触发旧的 131,072 字节请求上限，未更新 README、验证或收尾；未耗尽 600 秒，也未观察到余额或容量错误。当前已增加显式 v2 工程配置，仅将请求体上限设为 524,288 字节；64 项针对性测试通过。原失败、v1／默认配置及项目文件、工具和证据读取限制保留；新轮须统一注册该配置。

四角色控制验证了两家模型在首次工具调用前、首次修改后两个固定边界的原始证据闭包；6 次请求结算、无待定预留。它没有接手方，不能证明任务质量、真实接手或净收益。最近代码提交 `7a59f93` 的 [11 项 CI](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/39088085914) 通过；这些工程检查不代替真实效果证据。

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
