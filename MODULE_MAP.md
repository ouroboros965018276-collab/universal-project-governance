# 模块导航

当前候选：**3.0.0-rc.20**。版本与发布状态见[当前项目状态](PROJECT_STATE.md)。

```mermaid
flowchart LR
    source["规范模型、契约与模板"] --> compiler["编译器"]
    compiler --> runtime["生成运行时"]
    runtime --> host["宿主中的智能体"]
    host --> state["项目绑定与当前交接"]
    source --> evolution["离线演化"]
    evolution --> candidate["开发候选"]
    candidate --> gate["独立证据准入与评审"]
    gate -. 获准后修改规范源码 .-> source
```

## 按改动目标定位

| 改动目标 | 源码入口 | 契约与消费者 | 验证入口 | 影响边界 |
|---|---|---|---|---|
| 规则、风险、局部或结构模式 | [治理模型](governance-src/model/governance-model.json)、[规划器](governance-src/runtime-scripts/plan_governance.py) | [任务输入](governance-src/schemas/task-context.schema.json) → [治理计划](governance-src/schemas/governance-plan.schema.json)；[可选项目提示](governance-src/profiles/) | [规则检查](tools/governance_lint.py)、[规划与运行时测试](tests/test_compiled_runtime.py)、[按需工作流测试](tests/test_operational_guidance.py) | 计划投影命中的原闭包及工作流块；完整 Skill 常驻，未知项目提示仍用通用规则 |
| 安装、绑定、完成、导出或卸载 | [仓库命令入口](upg.py) → [生命周期](governance-src/runtime-scripts/project_tool.py) | [执行记录](governance-src/schemas/execution.schema.json)、[灰测报告](governance-src/schemas/field-report.schema.json)；[资格运行器](qualification/lib/execution.py) | [生命周期测试](tests/test_compiled_runtime.py)、[完成结果测试](tests/test_completion_outcomes.py) | 绑定与既有工作流；保留已启用的报告状态和原始开始事实 |
| 状态校验、验证引用或交接 | [状态工具](governance-src/runtime-scripts/state_tool.py) | [执行记录](governance-src/schemas/execution.schema.json) → [交接记录](governance-src/schemas/handoff.schema.json)；生命周期与后续接手者 | [验证连续性测试](tests/test_validation_continuity.py)、[证据连续性测试](tests/test_rc9_evidence_continuity.py) | 按范围、运行标识和已测修订核对证据；后续改动保留待重测状态 |
| 中断恢复、过期索引或源码矛盾 | [事实恢复](governance-src/runtime-scripts/project_facts.py) ← [状态工具](governance-src/runtime-scripts/state_tool.py) | 显式文件范围、[交接契约](governance-src/schemas/handoff.schema.json)；[恢复说明](docs/project-fact-recovery.md) | [恢复测试](tests/test_project_recovery.py)、[真实工具恢复契约测试](tests/test_fact_recovery_tools.py) | 有界静态读取；未知意图、动态行为和未覆盖范围保持未知 |
| 指令表达、生成或完整性 | [指令模板](governance-src/templates/)、[编译器](compiler/compile_governance.py)、[完整性工具源码](governance-src/runtime-scripts/validate_integrity.py) | [治理源码职责](governance-src/README.md#规范职责) → [生成包](universal-project-governance/) | [编译与运行时测试](tests/test_compiled_runtime.py)、[全局指令投影测试](tests/test_context_discipline.py)、[包校验](tools/validate_skill_bundle.py) | 只改规范源码后生成；语义、编译或包字节变化影响运行时及资格身份 |
| 离线反思、搜索、预算或检查点 | [控制器](evolution/controller.py)、[反思](evolution/reflective.py)、[源码桥](evolution/source_bridge.py) | [离线契约](evolution/contracts.py)、[开发协议](evolution/protocol/)；[评估器](evolution/evaluator.py)与[消融](evolution/ablation.py) | [控制器测试](tests/test_evolution_controller.py)、[预算测试](tests/test_evolution_selection_budget.py)、[检查点测试](tests/test_evolution_checkpoint_io.py) | 仅仓库内候选；[独立准入](evolution/promotion.py)决定提案资格，不能直接改已安装包 |
| 原生文件产物测量 | [原生适配器](evolution/native_codex.py)、[产物评分](evolution/task_benchmark.py) | 注册配置、源码与评分身份；[原生测量说明](docs/offline-evolution.md#native-cli-development-adapter) | [适配器测试](tests/test_evolution_native.py)、[产物评分测试](tests/test_evolution_task_benchmark.py)、[费用留存测试](tests/test_native_cost_persistence.py) | 评估返回产物；完成回合用量不等于提供方内部全部尝试费用 |
| 真实文件／Git 工具、收据或传输 | [工具适配器](evolution/tool_codex.py)、[工具代理](evolution/tool_broker.py)、[传输配置](evolution/cli_transport.py) | 工具代理中的任务契约与固定正向检查；[工具传输说明](docs/rc19-tool-transport.md) | [工具测试](tests/test_evolution_tools.py)、[字节收据测试](tests/test_tool_patch_receipts.py) | 仅注册文件及有界工具；解析提交源码，不执行待测应用代码 |
| 官方 API 工具循环与类型化终态 | [仓库 API 适配器](evolution/provider_tools.py) → [工具代理](evolution/tool_broker.py) | [终态 schema](evolution/tool_codex.py)；调用方提供已冻结任务、profile、预算和凭据回调 | [API 工具契约测试](tests/test_provider_tools.py) | 仅仓库实验，不进入安装包；`repo_finish` 独立记录，不代替真实读写和严格评分；未知用量不算零 |
| 真实工具实验、配对分析或费用 | [实验收集与分析](evolution/tool_campaign.py) | [实验协议](evolution/protocol/) → 工具适配器；[既有独立结果](docs/rc19-tools-independent-v13.md) | [实验测试](tests/test_tool_campaign.py) | 现有收集器严格限定两条件；未知调用保留围栏，不能自动重放或算作零费用 |
| 正式资格、执行身份或冻结 | [资格契约](qualification/lib/contracts.py)、[注册与证据](qualification/lib/core.py)、[执行](qualification/lib/execution.py) | [资格协议](qualification/protocol/qualification-v3.json)、[适配器契约](qualification/adapters/adapter.schema.json)；[资格说明](qualification/README.md#reproducible-execution-identity) | [资格测试](tests/test_qualification.py)、[资格校验](tools/validate_qualification.py)、[冻结工具](tools/qualification_freeze.py) | 冻结结果轮开始后不改冻结面；开发证据不能升级为正式资格 |
| 评分、门禁、越界或隐私 | [分析门禁](qualification/analysis/gates.py)、[盲评](qualification/graders/blind_pair.py)、[诊断脱敏](qualification/adapters/diagnostics.py) | 资格协议、场景范围与正向产物契约；[结构越界说明](qualification/README.md#structural-overreach) | [误判测试](tests/test_qualification_false_positives.py)、[资格测试](tests/test_qualification.py)、[安全审计](tools/security_audit.py) | 修复评分缺陷需合法结果与反例；关键安全和越界失败不能由成功率抵消 |
| 文档导航、仓库校验或发布打包 | [导航校验](tools/validate_navigation.py)、[仓库校验](tools/validate_repository.py)、[打包](tools/package_release.py) | [贡献流程](CONTRIBUTING.md)、[发布流程](PUBLISHING.md)、[持续集成](.github/workflows/validate.yml) | [导航测试](tests/test_navigation.py)、[包测试](tests/test_compiled_runtime.py) | 导航只校验链接目标；不证明语义、行为或发布门禁通过 |

## Skill 与计划的边界

Skill 保留全部全局义务；plan 是任务投影，按原 policy 闭包和已解析报告/现有 reporting 状态选取 `operational_guidance`，每块只出现一次。无 helper 仍使用完整 Skill 与手工 index 路由，非平凡工作不得因上下文漏报跳过工作流。旧六条件收集器 [context_campaign](evolution/context_campaign.py) 保留原 inline 契约及[旧实验测试](tests/test_context_campaign.py)，不用于新路由。来源、未知费用和独立证据范围见[选择性映射](docs/upstream-rule-map.md)。

## 公共接口改动

接口或状态格式变化时，从上表契约追到生产者、读取者、仓库命令、适配器和测试；再用实际符号或字段搜索确认消费者。静态入口不能枚举动态调用，发现范围外消费者时保留兼容性结论的限制。结构模式仍受当前任务边界约束，见[源码结构规则](governance-src/README.md#结构范围)。

## 中断后恢复

接手者先核对[当前状态](PROJECT_STATE.md)、[仓库约定](AGENTS.md)、实际工作树差异、已有验证与项目内当前交接，再按上表读取受影响源码和契约。索引、说明或交接与源码冲突时，以当前源码及可核实证据重建事实；摘要和哈希不能证明行为正确。恢复使用既有交接，不另建历史或验证账本。

## 状态与历史

[使用入口](README.md) · [决策](DECISIONS.md) · [变更记录](CHANGELOG.md) · [历史审计](audits/) · [许可与来源](third_party/notices/README.md)。历史记录保留原来的数字、引用和证据范围，不能据此推断当前收益或资格已成立。
