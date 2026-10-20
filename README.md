# 通用项目治理 UPG

当前候选：**3.0.0-rc.20.3 — Autonomous Git Adoption**。版本以[生成清单](universal-project-governance/VERSION.md)为准，发布、安装和验证状态见[项目状态](PROJECT_STATE.md)。

UPG 帮助不同 Agent 和工程师持续维护同一个项目：依据当前事实定位任务，在正确层次完成关联改动，处理受影响的重复实现、过时内容和技术债，留下可验证、可继续接手的状态。软件、数据、研究、内容、设计和混合项目使用同一治理内核；具体工具能力须由宿主实际验收。

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
| 查重要历史及设计原因 | [变更记录](CHANGELOG.md)、[决策记录](DECISIONS.md) |

索引用来定位相关实现、契约、消费者和测试。遇到路径失效、动态依赖、状态冲突或覆盖不足，再扩大检查范围；索引和读取预算都不能代替完成证据。

## 安装后保持什么

治理语义只在 `governance-src/` 维护，`universal-project-governance/` 由编译器生成。普通项目任务不修改治理核心。当前文档描述有效行为；重要历史进入已有变更、决策或冻结证据，其他位置引用，不建立第二真值。

项目绑定只管理 UPG 自有状态，不重排既有项目。卸载先移除项目绑定，再移除 Skill：

```bash
python upg.py remove --project /path/to/project --agent codex --yes
```

## 有效性边界

RC20 是候选，**不是 Stable**。工程测试、安装通过、短文或较小 diff 都不证明真实净收益。RC19 的[安装审计](audits/rc19-installation.audit.json)是已验证的历史基线；其[独立 B](docs/rc19-tools-independent-v12.md)和[追加 C](docs/rc19-tools-independent-v13.md)均因未知用量中断而未完成，原失败、成本和围栏保留。

正式资格仍为 **UNASSESSED**，锁定试验 **NOT RUN**。实际模型、工具、任务质量、清理、安全和交接收益必须在相同条件下比较，并计入 token、耗时、工具输出、重试及后续维护成本；严重失败不能用其他高分抵消。当前证据见[项目状态](PROJECT_STATE.md)，历史数字保留在各自原始记录。
