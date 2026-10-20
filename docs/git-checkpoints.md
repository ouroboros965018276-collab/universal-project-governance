# Git 阶段检查点

RC20.2 在既有 `project_tool.py begin/finish` 生命周期中执行 Git 阶段提交。它判断已声明范围内的实际差异，按有意义阶段保存；提交成功不代替功能验证。当前发布与验收结果见 [PROJECT_STATE.md](../PROJECT_STATE.md)。

## 启用和使用

使用已验证的 Python 入口，在生成或已安装的 Skill 目录运行辅助脚本。下面的路径仅为示例；按项目授权范围选择源码、测试和文档：

```bash
python scripts/project_tool.py git-configure /path/to/project --enable --allow-path src --allow-path tests --allow-path README.md --status-path PROJECT_STATE.md --min-interval-seconds 300
python scripts/project_tool.py status /path/to/project
```

`--allow-path` 和 `--status-path` 可重复。允许路径是项目内的相对文件或目录；目录覆盖后代，`.` 明确允许整个项目。启用必须提供非空允许范围。声明的状态路径及 `.governance/` 排除在自动提交候选之外，避免状态、时间戳和治理收据反复制造提交。配置保留在 `.governance/upg.json` 的 `git_checkpoint` 中；默认关闭、冷却 300 秒、允许范围和状态路径为空。已有项目的选择不会被安装或普通接手隐式开启。

```bash
python scripts/project_tool.py git-configure /path/to/project --disable
```

启用后继续使用原有工作流输入，不需要另跑提交循环：

1. `begin` 保存本次工作基线。开始前已脏的文件排除在自动提交之外，不能把用户原有改动归入本次成果。
2. 每次实际阶段边界通过 `finish` 上报。候选只来自 `changed_files` 声明的文件和本工作流已有待处理路径，并继续受允许范围约束；有实际差异、`integrity: pass` 和非空验证记录才提交。无变化、重复阶段和声明的状态文件不会生成提交。延期后的精确重试须保持原来源字节与范围；文件继续变化时使用新的已验证阶段。
3. 普通未完成阶段在冷却期内保留待处理改动，后续阶段再判断；完成状态收束待提交改动；未完成工作的真正交接或风险边界须在 finish 输入中显式设置 `"git_boundary": "handoff"` 或 `"git_boundary": "risk"` 才提前收束。省略该字段时默认 `"verified"`，普通交接文件更新不绕过冷却。时间经过本身不会启动提交。

自动保存仍以实际 `begin/finish` 调用为触发入口。它没有后台监控或定时器，不会替未接入生命周期的工具、其他宿主或普通手工编辑自动执行，也不会自动 push。

当前支持已有提交、附着分支、项目根即工作树根的普通仓库及 linked worktree。未初始化、未产生首个提交、分离 HEAD、稀疏检出、分离索引、进行中的合并或变基均会阻止；选中路径含符号链接、子模块、忽略文件或常见密钥文件名也会阻止。这里的验证来自阶段输入和已观察到的路径，不能推断任意文件已验证或自动辨认所有敏感内容。

## 结果和恢复

读取 `finish` 的实际 Git 结果：`committed` 才表示观察到提交成功；`unchanged`、`duplicate`、`disabled` 不产生提交；`deferred` 表示普通阶段仍在等待冷却；`blocked` 表示需处理 Git、范围或恢复问题。待提交改动或阻塞不能描述为已完成 Git 保存。

无 Git、未解决冲突、并发索引变动或提交钩子失败须报告具体失败，不能静默当作成功。未选中的暂存内容保留；选中路径已有暂存改动时阻止，不以全量 `git add` 收集其他工作。提交前后的恢复信息有界保留在原绑定内，Git 事务临时文件位于 Git 私有目录，不增加第二份治理账本。

原生 Git 提交先在私有上下文运行钩子和签名，再核对预期父提交、树与收据，通过分支旧值比较后发布。私有上下文与当前仓库的有效 Git 配置不一致时直接阻止，不修改宿主配置。依赖原始 Git 目录或附着分支的自定义钩子仍可能不适用；实际拒绝结果保留，不能凭配置相同断言任意钩子行为等价。

若提交后进程中断，重试先核对当前 Git 状态与已有事务信息，不能盲目再提交。操作系统强制终止可能留下 UPG 写锁或原生 Git 索引锁；跨进程遗留锁须由所有者检查实际进程、提交、索引和工作树后再恢复，不能直接把锁当作损坏或自动删除。凭当前状态不能证明的提交结果保持待核对。

## 维护契约

规范默认值和唯一指令入口在 [治理模型](../governance-src/model/governance-model.json) 的 `project_binding.git_checkpoint` 与 `tracked_state`；[生命周期](../governance-src/runtime-scripts/project_tool.py) 调用 [Git helper](../governance-src/runtime-scripts/git_checkpoint.py)。修改须保留显式授权范围、已有脏改动隔离、去重、冷却、收束及失败可见性，并在最终运行时和安装副本验证受影响行为。历史付费试验不因 Git 功能测试而重写，确定性回归不证明模型净收益或正式资格。
