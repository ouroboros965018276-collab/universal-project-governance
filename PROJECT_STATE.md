# Project State

**3.0.0-rc.20 已合并到默认分支 main，并完成本地全局安装。** 观察日期：2026-10-20，Asia/Shanghai。功能合并为 [PR #24](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/24)，提交 `66fb9e0c4b6a5df8d83895f59a04d187b003b9e4`；版本以[生成清单](universal-project-governance/VERSION.md)为准。发布和安装的机器可读事实统一见[工程验收](audits/rc20-release-engineering.audit.json)。

## 本轮结果

按维护者明确收敛的范围，本轮复用既有实测，仅做自审和关键工程验收，不再扩大付费研究。**独立模型 token／总耗时净收益仍未建立，正式资格 UNASSESSED，locked NOT RUN，不宣称 Stable 或普遍有效。** 原实验标准、失败、成本和未知用量不改写。

RC20 将表达相关性、完整改动、事实保真和按需读取融入既有编译链；五个上游的固定来源、许可、适配与排除见[来源映射](docs/upstream-rule-map.md)，维护入口见[模块索引](MODULE_MAP.md)。实验适配器不随 Skill 交付。

本次修复 RC19 的实际生命周期缺陷：长期工作流无法记录第二次 partial。RC20 使用稳定阶段编号，保留开始事实、精确重试和唯一完成身份，两种报告模式保持递增顺序。已有项目当前状态通过 JSON 路径／哈希引用；接手检查发现字节漂移，完成历史不再被当作活动进度。Git 按有意义的验证阶段、风险或交接边界评估检查点，不按工具调用自动提交。

Insight 的原三条报告、开始事实和完成历史均保留；追加阶段观察及一次实际字节漂移后的核对，现有五条报告。当前引用指向其原有 `execution_status.json`，README 明确账本职责。应用代码未修改，应用测试及付费模型未重跑；应用／包版本 2.0.0 与 UPG 运行时分开，整体验收和科学结论仍未完成。

最终工程源码的[跨平台 CI](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/39410859850) **11/11 通过**；最终全量测试 1,326 项，25 项生命周期回归及 9 项工程门禁通过。默认分支合并树与测试树相同。本地 18 个交付文件与 main 逐字节相同，17 项受管完整性、25 项已安装工具回归、Insight 状态及官方新进程强制发现均通过；发现 1 个启用的 UPG，无重复和加载错误。RC19 备份已读回校验并保留；当前对话的历史加载不由安装验收反向证明，后续回合可使用新安装。

## 历史证据

[原始实测审计](audits/rc20-primary22-insufficient-balance.audit.json)保留已完成的 54 项、后续消融／工具任务、严重否决、未知用量、费用和暴露限制；不重跑已完成任务或重新评分制造收益。最近工作集对照在 8 个发表角色、7 个完成、80 次 API 后停止，已知报告 token 2,192,686；原 FAILED_NO_REPLAY、供应商拒绝和质量缺口保持，所属进程已清理。

## 最近两次重要发布

RC20：2026-10-20T10:59:15Z 合并，修复当前状态接手与多阶段记录，并整合按任务上下文和完整改动纪律；采用重新生成、跨平台回归、受控合并和默认分支逐字节安装验收。工程通过不替代实效资格。

RC19：2026-10-13T05:51:50Z 经 PR #20 合并，原因是诊断 RC18 耗时并增加项目事实恢复；[历史安装验收](audits/rc19-installation.audit.json)核验 18 个交付文件。其独立 B/C 成本收益验证未完成，不能由 RC20 安装改写。

## 接手入口

当前发布状态以本页及其机器可读[验收记录](audits/rc20-release-engineering.audit.json)为准。本地 2026-10-19 的 `.governance/handoff.json` 是保留的历史恢复快照，不代表当前发布状态。必要验证范围见[PUBLISHING.md](PUBLISHING.md)，历史因果见[CHANGELOG.md](CHANGELOG.md)、[DECISIONS.md](DECISIONS.md)。
