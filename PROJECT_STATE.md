# 当前项目状态

当前工程升级：**3.0.0-rc.20.3**，已合入主分支并完成本地安装验收。[PR #28](https://github.com/ouroboros965018276-collab/universal-project-governance/pull/28)；[工单 #26](https://github.com/ouroboros965018276-collab/universal-project-governance/issues/26)。唯一当前工程验收记录为 [Git 审计](audits/rc20-git-checkpoints.audit.json)；此前 RC20.2 状态保留在 `3a96b27` 的 Git 历史中。

显式启用范围后，无 Git 项目会建立自己的仓库，尚无首提交时可安全生成首个提交；一次配置的独立观察进程让未调用 begin/finish 的宿主也能保存稳定、经本地校验的改动。冷却、去重、失败退避、快进跟随、原事务恢复、手工工作流优先和停止均由程序执行，见 [Git 自动接管](docs/git-checkpoints.md)。源码阶段已实际自动提交一次，精确重试未新增提交。

源码 `07dbba8` 的两轮 CI 均 **11/11 全部通过**；Linux 和 Windows Python3.11/3.13 各完成1390项测试，零失败、零错误。Python3.8 的版本条件跳过如实保留在审计。开发期1382项通过与恢复校准先13通过1失败、修复后两项复测通过的原始记录均保留，不用旧结果替代最终源码 CI。

安装目录的20个交付文件与合并主分支运行包逐字节相同，安装副本8项真实 Git 检查、新官方进程发现1个已启用 Skill／零发现错误均通过；升级前备份和未受管理文件保留。本验收记录提交自身的后续 CI 以 GitHub 当前提交检查及工单最新验收为准，不为回填运行时间或提交自身哈希循环提交。

本轮新增外部付费模型实测 **0**，未改写原始研究、失败、未知费用或资格判据。独立跨 Agent 质量及 token／总耗时净收益仍未建立，正式资格 UNASSESSED、locked NOT_RUN，尚非 Stable。观察器需要授权的本地 Python/Git 和运行中的系统，不是开机服务；高级 Git 模式、自定义钩子及遗留锁仍可能需要所有者检查。Insight 应用继续保留先前 partial／未整体验收状态，本轮未修改应用。
