# Project State

当前候选：**3.0.0-rc.20 — Task Context and Complete Change Discipline**。2026-10-20 观察：默认分支和本地安装仍为 RC19；RC20 正在最后工程验收，尚未合并或安装。版本以[生成清单](universal-project-governance/VERSION.md)为准。

## 本轮交付和验收

维护者已明确将本轮收敛为自审、复用既有实测和必要关键回归，不再扩大付费对照。发布的是 RC 工程升级；**独立模型 token／总耗时净收益未建立，正式资格 UNASSESSED，locked NOT RUN，不宣称 Stable 或普遍有效。** 原实验标准及结果不改变。

RC20 将表达相关性、完整改动、事实保真和按需读取放进原有编译链；上游固定来源、许可、适配与排除见[来源映射](docs/upstream-rule-map.md)。规范、工具和运行时通过[模块索引](MODULE_MAP.md)定位，实验适配器不随 Skill 交付。

本次针对 Insight 发现的实际生命周期缺陷：RC19 将一个工作流的所有 partial 更新限定为同一收据，阻止长期任务记录后续阶段。RC20 使用稳定阶段编号，保留不可变开始事实、精确重试和唯一完成身份；两种报告模式保持递增顺序。当前项目状态通过已有 JSON 路径和哈希引用，字节变化会使接手检查失败；最新已完成事项明确属于完成历史。Git 按有意义的验证阶段／风险／交接边界评估检查点，不按工具调用提交。

`D:\Insight` 已通过候选生命周期工具补入一个 partial 阶段：原三条报告和开始事实保留，当前引用指向既有 `execution_status.json`；工程 README 明确账本职责。应用／包版本 2.0.0 与 UPG 运行时版本分开。此次未改应用代码、未重跑应用测试或付费模型，Insight 整体交付与科学验收仍未完成。

当前源的 24 项生命周期回归和 9 项工程门禁通过；整仓回归、最终 CI、默认分支与安装尚待核验。精确记录见[RC20 工程验收](audits/rc20-release-engineering.audit.json)。

## 实测证据的边界

历史真实对照保留在[原始审计](audits/rc20-primary22-insufficient-balance.audit.json)，不重跑已完成任务，不重新打分制造收益。原 54 项已完成；旧 RC20 的确认质量／净收益门槛失败。后续消融、工具任务和中断试验中的失败、未知用量、成本及暴露限制全部保留。

最近工作集对照已停止：8 个发表角色中 7 个完成，80 次 API、已知报告 token 2,192,686，分模型域保留；MiMo 返回完整已结算 `content_filter`。原 FAILED_NO_REPLAY 保留，所属进程已清理，没有再次派发。修复拒绝分类和准备显式低推理配置仅是工程改动，不证明真实收益；新准备任务尚未执行，不是验证结论。

## 最近两次重要发布

RC19：PR #20 于 2026-10-13T05:51:50Z 合并，原因是诊断 RC18 耗时并增加事实恢复；[安装审计](audits/rc19-installation.audit.json)核验 18 个交付文件。默认分支后续文档修正基线为 `bd4a4d5c1c6fb9fca829e410729879d1b01f05b9`。

RC18：PR #19 于 2026-10-11T21:35:40Z 合并，修复评分误判并压缩运行时；原开发测量 token 点估计减少 3.84511%、回调耗时增加 23.6975%，不是已证明的时间收益。详见[历史实测](qualification/pilots/rc18-native/README.md)。

## 接手

本地 `.governance/handoff.json` 记录未完成动作及已结算进程；不替代规范或冻结证据。发布范围见[PUBLISHING.md](PUBLISHING.md)，历史因果见[CHANGELOG.md](CHANGELOG.md)、[DECISIONS.md](DECISIONS.md)。当前状态覆盖，历史证据保留并引用。
