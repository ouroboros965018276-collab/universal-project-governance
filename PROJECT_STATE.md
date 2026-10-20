# 当前项目状态

当前候选：**3.0.0-rc.20.5**，项目会话结束自动停止与活跃会话内监督恢复升级进行中。[工单 #26](https://github.com/ouroboros965018276-collab/universal-project-governance/issues/26) 已重新打开。RC20.4 的独立后台观察器已明确停止，状态为stopped、worker/supervisor PID清空；上一轮会话外持续行为已被用户最新要求撤销。

新代码从前台宿主命令的真实存活期持有会话生存能力；结束或所有者异常退出即终止观察子树，活跃会话内恢复监督退出。没有可靠结束信号的宿主只执行有限检查点／单次观察，不注册系统启动项或注入宿主配置。必要本地校准与10项最终静态／打包门禁已通过；源码CI、主分支及本地安装核对仍待完成，不能据此宣称整体验收。初跑51项失败、Windows管道类型修正及有界单项复核都保留在审计中。

原范围、有效改动识别、阶段校验、300秒冷却、去重和明确停止语义保留。原RC20.4证据见[上一轮固定审计](https://github.com/ouroboros965018276-collab/universal-project-governance/blob/8d7e6db7394e413de2d1a3e60d57d5dcb71de29a/audits/rc20-git-checkpoints.audit.json)，本轮结果归入[当前工程审计](audits/rc20-git-checkpoints.audit.json)。不为状态和CI时间循环提交。

本轮新增外部付费模型实测0。跨Agent质量与token／总耗时净收益未建立，正式UNASSESSED、locked NOT_RUN，尚非Stable。Insight应用仍是先前partial／未整体验收状态。本轮不会宣称任意宿主零配置接管、任意脱离的第三方后代或断电持久性已获得普遍保证。
