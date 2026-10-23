# 治理规范源码

`governance-src/` 是分发治理语义的唯一可编辑源码；运行时由编译器生成。

## 规范职责

模型定义 Hot Path、policy 图、风险和结构模式、项目绑定、临时灰测报告及复杂度预算。模板承载常驻指令，schema 定义输入与状态契约，`runtime-scripts/` 提供确定性助手。不要在文档或生成包中建立第二份规则定义。

## 任务投影

四条 `execution_guidance` 在 Skill 中各完整出现一次。计划是已加载 Skill 的任务投影，不能单独替代 Skill；编译器保留全部 16 个基础 policy 定义，planner 按原触发和依赖闭包输出命中的 closure，不再把四条全局 guidance 重复拼入其中。

`operational_guidance` 将原有工作流指令按需投影，不增加 policy：`tracked_state` 由现有结构/交接 policy、已解析的 engineering/audit 报告级别或已启用的 field reporting 触发；`recovery_tools` 随既有交接 policy 触发。同一块即使命中多个条件也只输出一次。所有块先校验，未命中的非法数据也必须拒绝。

无 Python/helper 时，保留完整 Skill，手工匹配 index 的触发、依赖、风险和报告规则，再选择满足 policy、报告级别或 reporting 条件的 operational 块。非平凡、需跟踪或跨会话工作即使输入漏报触发，也必须遵循 `tracked_state` 并纠正上下文；不能因投影缺项而跳过义务。输入字段依既有 schema，不增加调用方开关或加载器。

## 结构范围

结构修改落实在任务所需的最小现有责任层，保留受影响契约、消费者、验证和清理边界；结构模式不授予扩大任务范围的权限。

## 项目绑定

生命周期由 `runtime-scripts/project_tool.py` 管理。新绑定默认只创建 `.governance/upg.json`；明确临时 opt-in 才增加一个有界 ledger。已有设置、基础设施和非空 ledger 在原地采用及升级时保留，不为安装迁移项目。

`finish` 在 reporting 关闭时推进有界 latest/previous，在开启时复用恰一次报告路径。原始 start facts、因果顺序、未知状态和未完成工作流边界不因路由改变。正式资格 A2 运行器仍需显式 opt-in；普通项目不强制采集研究数据。

每次修改正常完成的审查/审计属于 `evidence_fidelity`；适用的非平凡工程路径由 `engineering_workflow` 按既有规则与报告级别选取。新 `complete` 在生命周期写入前通过 `completion_review.py` 核对审查、审计及当前文件身份，历史读取和已完成精确重试保留原事实。字段与边界见[完成输入](../docs/completion-review.md)。

## 修改与验证

源码变化后需要统一生成、lint、完整性、确定性测试和资格冻结校验。已开始的结果轮保留原冻结身份；新源码不能重写旧结果或沿用旧轮的收益结论。

schema 校验使用 `state_tool.py` 已实现的显式子集：类型与联合、对象属性及附加属性 schema、propertyNames、required、const、enum、allOf 与 if/then/else、数组界限与唯一性、字符串界限/模式/RFC3339、数值界限。跨字段计数顺序、运行标识唯一性及恢复身份一致性由相应消费者补充校验；新关键词需要实现和反例测试。

运行器须严格核对当前编译器实际输出的 source、Skill、plan 和交付身份。开发夹具用于检验契约和故障边界；静态测试或字节减少不证明 token、延迟、质量、因果收益或 Stable 资格。
