# Project State

当前候选为 **3.0.0-rc.20 — Task Context and Complete Change Discipline**。默认分支和本地安装仍是 **RC19**，提交 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。**RC20 尚未合并或安装，真实净收益未建立。** 更新观察日期：2026-10-19，Asia/Shanghai；本轮精确工作开始时间未知。

## 当前能力与事实入口

表达相关性、完整改动、事实保真和按需读取由[规范源](governance-src/model/governance-model.json)统一编译。生成核心为 7,185 字节，16 项政策、8 项 Hot Path、四组指引和 18 个交付文件；规范身份 `ea045482…`，正式资格指纹 `f08db03a…`。五个上游的固定来源、许可、适配和排除见[来源映射](docs/upstream-rule-map.md)及[许可记录](third_party/notices/README.md)。实验适配器不随 Skill 交付。

源码、契约、消费者和测试按[模块索引](MODULE_MAP.md)定位；不需要为局部修改读取整篇研究历史。当前实验结果及全部原始身份以[本轮审计](audits/rc20-primary22-insufficient-balance.audit.json)为准。

## 当前实测结论与未完成事项

- 原九族对照从第 37 项续跑至 **54/54**，前 36 项未重跑；66 个计划角色的首次盲评先锁定再解盲。RC19、attention、旧 RC20 分别通过 **2/18、4/18、2/18** 个流程；旧 RC20 有严重否决及配对退步，已知 token 少 22.38%，完整耗时多 5.74%，**净收益未通过**。
- 后续固定开发对照为 9 个流程／15 个计划角色，实际执行 10 个，机械成功 2/9；5 个角色因 source 失败未调用。三段 API 共 66 次请求、1,711,012 个已知报告 token；三个 CLI 完成回合分别为 239,197、71,369、110,359 token，属于独立测量域。原失败、pending、未知账单、重复消耗和纠正核验费用全部保留，纠正读取不能改写原研究结果。
- 当前修订明确最后相关编辑后再验证、检查任务义务及保护治理核心。工程 broker 只从真实收据提示缺失操作和过期验证。9 项工程门禁及最近整仓 1,264 项测试通过（3 项跳过）；新增真实 RC19 拓扑的 9 项定向测试通过，提交 `48657f3` 的跨平台 CI 11/11 通过。这些证明工程行为，尚不证明净收益。
- 四个新独立项目、六个阶段已冻结。7 次真实 Docker 控制中，六个正确最终快照通过，删除核心模块的错误快照 0/4 检查通过；收据完整且清理成功，无模型调用。新六条件对照的执行接缝仍在校验，**当前运行时的独立净收益及真实中断恢复尚未证明**。

全部精确身份、失败与成本见[本轮审计](audits/rc20-primary22-insufficient-balance.audit.json)。已暴露任务保留为开发证据，不再称独立 holdout。旧有利主结论保持 BLOCK，未知用量不能当作零成本，严重失败不能被平均分抵消。

合并和安装要求同条件质量不劣、无严重否决，报告 token 各模型域及完整流程耗时优于 RC19 和 attention，并补齐独立接手、当前消融与未暴露任务验证。正式资格 **UNASSESSED**，locked **NOT RUN**；不宣称 Stable，研究总成本与 break-even 仍未知。

## 最近一次重要发布：RC19

PR #20 于 **2026-10-13T05:51:50Z** 合并，提交 `a98449ce91e8bc60ae0d58fa584cbef7ab87c058`。原因是诊断 RC18 耗时增加，并补足项目事实恢复与真实工具成本记录；方法是生成运行时、受控合并、逐字节部署和独立安装验收。

[安装审计](audits/rc19-installation.audit.json)于 **2026-10-13T05:58:35.911624Z** 确认 18 个交付文件与合并版本一致，完整性、规划输入和官方新进程发现通过。该时间是验收观察。[独立 B](docs/rc19-tools-independent-v12.md) 与[追加 C](docs/rc19-tools-independent-v13.md) 均不完整，净收益门槛 FAIL；安装成功不改变该结论。后续 PR #21/#22 只修正文档现状，没有改变冻结运行时。

## 上一件重要发布：RC18

PR #19 于 **2026-10-11T21:35:40Z** 合并，提交 `29cf112b4629d6b90504b079e95a5370c206a4cb`。RC18 修复评分器错误成功判定、压缩指令并记录真实开发对照；该轮 token 点估计降低 **3.84511%**、完整回调耗时增加 **23.6975%**，由此引出 RC19 的耗时诊断。范围与原始结果见 [RC18 实测](qualification/pilots/rc18-native/README.md)及[诊断](docs/rc19-latency-diagnosis.md)。

## 接手入口

- 当前未完成工作和唯一活动进程：本地 `.governance/handoff.json`。它不随 Skill 交付，也不替代规范或冻结证据。
- 发布与资格：[PUBLISHING.md](PUBLISHING.md)、[qualification/README.md](qualification/README.md)。工程边界见[行为契约](docs/rc20-behavior-contracts.md)。
- 重要版本因果：[CHANGELOG.md](CHANGELOG.md)、[DECISIONS.md](DECISIONS.md)。历史审计原件保留，当前状态不重复展开旧轮次。
