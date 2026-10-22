# 资格验证

当前版本、实际验证与发布状态见 [PROJECT_STATE.md](../PROJECT_STATE.md)；运行时版本见 [VERSION.md](../universal-project-governance/VERSION.md)。本目录只供仓库验证使用，不随 Skill 安装。正式资格仍为 UNASSESSED；本次工程修复和离线测试不能建立净收益、跨 Agent 泛化或 Stable 资格。

旧实验驱动、复制运行时及结果快照已从当前源码树退役，原始字节通过 Git 历史恢复。当前实现只有下表列出的维护入口。

| 模块 | 职责与保留原因 |
|---|---|
| `protocol/`、`fixtures/` | 注册实验条件、任务、抽样、门禁及阈值；公开回归样例不能成为新的独立留出集。 |
| `adapters/` | 绑定 Agent、模型、宿主和适配器字节；执行有界命令、收集用量及脱敏公共诊断。 |
| `arms/attention-control.md` | A1 实际执行的注意力对照文本；随运行器一起冻结，修改文本会使旧注册失效。条件身份统一来自 `protocol/qualification-v3.json`，实际注入由 `run_trial.arm_condition` 投影，K 读取规范模型；不另保留未消费的条件 JSON。 |
| `lib/contracts.py` | 同时核对当前冻结身份和有限 JSON 配置，拒绝以调用方参数绕过源码漂移检查。 |
| `lib/execution.py`、`lib/deployment.py` | 在调用前核对注册条件，配置 A2 项目报告，保存完整后再发布不可覆盖的证据。 |
| `lib/core.py` | 评价可观察产物、范围与项目绑定；评分不依赖模型自报完成。 |
| `run_trial.py`、`run_handoff_trial.py`、`run_trigger_trial.py` | 分别运行任务、交接和激活试验；无注册或隔离证明不得冒充正式结果。 |
| `dev_smoke.py` | 检验注册、真实适配器及证据通路；开发烟测始终没有发布资格。 |
| `analysis/`、`analyze.py` | 先准入，再计算配对效果、覆盖和不可相抵的门禁。 |
| `graders/blind_pair.py` | 输出匿名 X/Y 评审输入；可用 `--mapping-output` 将解盲映射单独保存在操作者侧。 |
| `mutations/` | 构造已声明的策略缺陷用于评价器回归；输出只能覆盖完整、未修改的既有 mutant 包。 |
| `api_acceptance/` | 官方 API 接入的显式人工入口及离线假传输测试；离线测试不授权额外付费请求。 |

## Reproducible execution identity

正式注册由 `round_manifest.py` 生成有种子、时间交错的 A0 基线、A1 注意力对照及 A2 UPG 配对矩阵。运行器要求 `--round-manifest` 和注册的 `--trial-id`；交接同时绑定源端与接收端条件。默认计划是同族交接，不能据此宣称跨族配对已经测过。

正式准入需要当前配置/源码指纹、类型正确且身份一致的试验记录、固定任务与暴露标识、唯一注册身份、外部强隔离证明和可读取的原始证据。严重安全失败不可由成功率补偿；缺失数据保持 MORE_DATA，未知费用保持未知。A2 的新鲜工作区显式开启灰测报告，完成修改必须留下且只留下一个有效报告；普通安装仍默认关闭报告。

`protocol/schemas/trial.schema.json` 是单条试验的规范契约。公开归档的 `result.schema.json` 保持自包含嵌入，以兼容当前不支持 `$ref` 的受限校验器；嵌入内容由现有 schema 同步回归检查防止漂移，当前没有自动生成步骤。分析器实际接收 JSONL，并逐条按规范 trial 契约准入。

## Structural overreach

评分按任务范围分别检查意外文件、API/架构越界与变更量。`local_guard` 和 `structural_guard` 分别统计，不能互相稀释风险。

配对推断按 Agent 族、场景、配对/重复三级自举；点估计和重采样使用相同层级权重。至少三个独立 Agent 族的要求不会因增加重采样次数而满足。项目类型子组当前允许只有一个场景，结果最多支持已测子组内的严重反转检查；不能据此增强跨场景泛化结论。改变该最低覆盖要求需要新的预注册设计及独立证据，本次不改变阈值。

产物和执行元数据保存在 Agent 工作区外。CLI 分析默认只读取注册清单旁的 `artifacts/`；归档搬迁时用 `--artifact-root` 明确指定根目录。库调用者应传入同样的可信根目录。读取拒绝符号链接、junction、错误试验位置及超过 64 MB 的清单。原始 stdout/stderr 为字节证据，可能包含敏感内容，必须私有保留并在共享前人工审查；公共诊断脱敏不等于原始证据可公开。摘要与哈希不能代替对真实隔离、独立性、时序和模型身份的外部核验。

`mutations/mutations.json` 的 `repository_mutations` 只列设计目录，当前 builder 不执行这组变异；列表本身不能证明灵敏度或已完成验证。策略构建器拒绝无效/无变化的变异，采用暂存后替换，保留构建失败前的已验证输出。
