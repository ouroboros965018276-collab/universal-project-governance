# 当前项目状态

**3.0.0-rc.20.1 已通过 [PR #25](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/25) 合并到默认分支 main，并完成本地安装验收。** 本次在 RC20 上修复自身审计发现的状态缺陷。发布、安装与实际检查的机器可读观察统一见[自审记录](audits/rc20-self-review.audit.json)。原 RC20 已合并并安装的事实保留在[历史工程验收](audits/rc20-release-engineering.audit.json)。观察日期：2026-10-20，Asia/Shanghai。

## 本次自审

发现并处理四项问题：直接报告在账本保存后、绑定更新前中断可能漏报；特殊工作流名称可能导致事件编号碰撞；本地交接仍写旧发布状态；离线演化文档仍独立声明 RC19。源码修复已重新生成并通过受影响回归及核心发布门禁；旧交接按原始字节保留为历史，文档改为引用现有状态入口。

五个上游的公开鸣谢、固定来源、许可、选择性适配及排除理由均已实现，见[来源映射](docs/upstream-rule-map.md)。按任务读取、相关表达、完整改动、清理、风险路由、事实恢复及有界离线学习已有实现和检查入口，见[模块索引](MODULE_MAP.md)。实现不等于任意模型都会正确执行。

Git 按有意义的验证阶段、风险或交接边界判断检查点，合并相关修改、检查差异、跳过无变化和重复状态提交。当前是 Agent 执行规则；没有后台定时提交服务，不能承诺所有未来宿主绝不重复提交。

## 当前证据与边界

复用既有真实实测，只做必要校准和当前核心改动的工程验收；本次新增付费模型调用为零。原 RC20 的全量测试为 1,326 项，[默认分支 CI](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/39412023393) 11/11 通过；这些是校正前历史证据，校正版[最终源码 CI](https://github.com/ouroboros965018276-collab/universal-project-governance/actions/runs/39416958916) 11/11 通过，Linux 3.11 全量 1,330 项、零失败，另有 28 项安装后生命周期检查和新进程发现通过。完整结果、原失败与范围从自审记录读取。

Insight 已保留旧报告、更新运行时绑定并明确引用原有 `execution_status.json`；`latest_change` 是最近已完成工作流，不能代替尚未完成的 R00-R12 进度。复查发现清理历史证据与派生入口占用同一路径，已先按原始字节封存证据、调整历史引用，再同步三个派生入口并记录第七条真实阶段观察。现有产品状态检查通过，六份原始证据摘要一致；本次不修改应用代码、重跑应用测试或宣告整体验收。

**独立模型 token／总耗时净收益仍未建立，正式资格 UNASSESSED，locked NOT RUN，不是 Stable。** 原实验失败、严重否决、未知用量、成本和暴露限制保留在[既有实测审计](audits/rc20-primary22-insufficient-balance.audit.json)及其引用中。工程通过不证明通用实效，也不保证未来无缺陷。

## 接手与历史

当前发布观察由本页指向的自审记录负责；本地 `.governance/handoff.json` 保存本次真实交接，先核对绑定引用和源码后继续。上一版交接的原始字节保留为历史，不再占用当前入口。

RC20 于 2026-10-20 经 [PR #24](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/24) 合并，修复多阶段记录和外部当前状态引用，并融合上下文与完整改动纪律。RC19 的事实恢复、安装与历史实测见[RC19 验收](audits/rc19-installation.audit.json)。更多因果与版本历史见[变更记录](CHANGELOG.md)、[决策记录](DECISIONS.md)；发布门槛见[PUBLISHING.md](PUBLISHING.md)。
