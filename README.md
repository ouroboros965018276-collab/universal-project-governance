# 通用项目治理 UPG

当前候选：**3.0.0-rc.20.8 — Whole-project Contract Reconciliation**。版本以[生成清单](universal-project-governance/VERSION.md)为准，发布、安装和验证状态见[项目状态](PROJECT_STATE.md)。

UPG 帮助不同 Agent 和工程师持续维护同一个项目：依据当前事实定位任务，在正确层次完成关联改动，处理受影响的重复实现、过时内容和技术债，留下可验证、可继续接手的状态。软件、数据、研究、内容、设计和混合项目使用同一治理内核；具体工具能力须由宿主实际验收。

## 组成与职责

| 部分 | 负责什么 | 为什么需要 |
| --- | --- | --- |
| `governance-src/` | 模型、输入与状态契约、指令模板和确定性助手 | 将每条治理语义维护在一个规范来源 |
| `compiler/` → `universal-project-governance/` | 将规范编译成可安装 Skill、计划索引和完整性清单 | 让安装内容可复现、可检查，避免手改分发副本 |
| `upg.py` 与项目生命周期助手 | 安装、绑定、阶段记录、恢复、导出、Git 检查点和移除 | 在保留既有项目的同时建立可接手的当前状态 |
| `evolution/` | 在仓库内生成、评估和筛选治理候选 | 将搜索成本和实验行为与日常 Skill 执行隔离 |
| `qualification/` 与 `tools/` | 验证身份、测试门槛、回归、打包和发布 | 区分工程通过、独立收益证据和正式资格 |
| 来源与许可登记 | 固定所参考概念、文件身份和许可范围 | 说明适配依据，避免把外部文本当作另一套运行规则 |

## 开始使用

从仓库安装并检查项目绑定：

```bash
python upg.py install --project /path/to/project --agent codex
python upg.py status --project /path/to/project
```

使用已验证的 Python 入口；Windows 不应假定 `python3` 可执行。辅助脚本支持 Python 3.8+，仓库内离线学习与评估使用 Python 3.10+。无 Python 或文件系统的宿主可遵循 Skill 核心规则，并明确无法验证的部分。

给 Agent 一个具体任务即可，例如“重命名这个接口，更新受影响调用方与测试，并安全清理旧路径”。普通小改动保留轻量路径；跨模块或高风险工作按影响范围补足验证与交接。新项目绑定默认不收集临时实测报告；需要时显式使用 `--field-test-reporting`。

需要自动保存 Git 阶段时，显式配置允许提交的范围。启用后，已有工作流的 `begin` 记录基线，`finish` 自动识别有效改动、按阶段提交并去重；普通未完成阶段默认间隔 300 秒，完成或显式交接/风险边界时收束待提交改动。无变化、声明的状态文件和开始前已有改动不会触发自动提交。配置、失败恢复与能力边界见 [Git 检查点](docs/git-checkpoints.md)。

## 按任务定位

| 要做什么 | 从哪里进入 |
| --- | --- |
| 修改某个功能、契约或工具 | [模块索引与边界](MODULE_MAP.md) |
| 维护治理规则或编译后的 Skill | [规范源](governance-src/model/governance-model.json)、[维护约定](AGENTS.md) |
| 恢复中断任务或核对过期交接 | [项目事实恢复](docs/project-fact-recovery.md) |
| 配置按阶段自动提交、去重或恢复 | [Git 检查点](docs/git-checkpoints.md) |
| 了解当前变更、验证和未完成事项 | [项目状态](PROJECT_STATE.md) |
| 离线学习与有界优化 | [离线演化](docs/offline-evolution.md) |
| 评估有效性、发布或审计 | [资格协议入口](qualification/README.md)、[发布门槛](PUBLISHING.md) |
| 查来源、许可和选择性适配 | [鸣谢](THIRD_PARTY_NOTICES.md)、[规则来源映射](docs/upstream-rule-map.md) |
| 查最近两次变更及当前设计原因 | [变更记录](CHANGELOG.md)、[设计决策](DECISIONS.md) |

索引用来定位相关实现、契约、消费者和测试。遇到路径失效、动态依赖、状态冲突或覆盖不足，再扩大检查范围；索引和读取预算都不能代替完成证据。

## 安装后保持什么

治理语义只在 `governance-src/` 维护，`universal-project-governance/` 由编译器生成。普通项目任务不修改治理核心。当前文档只描述有效行为；变更记录保留最新与上一次修改及原因，更早内容由 Git 版本历史提供。

项目绑定只管理 UPG 自有状态，不重排既有项目。卸载先移除项目绑定，再移除 Skill：

```bash
python upg.py remove --project /path/to/project --agent codex --yes
```

## 有效性边界

当前版本是候选，**不是 Stable**。工程测试、安装通过、短文或较小 diff 都不证明真实净收益。[当前报告审计](audits/rc20-ocr-report.audit.json)记录本次改动处置与工程验证；它不能代替独立模型比较。

正式资格与锁定试验状态统一见[项目状态](PROJECT_STATE.md)。实际模型、工具、任务质量、清理、安全和交接收益必须在相同条件下比较，并计入 token、耗时、工具输出、重试及后续维护成本；严重失败不能用其他高分抵消。本次升级不增加付费实测。
