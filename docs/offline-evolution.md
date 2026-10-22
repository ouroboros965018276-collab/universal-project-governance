# 离线治理演化

当前候选与安装状态见[项目状态](../PROJECT_STATE.md)。`evolution/` 是仓库内的开发工具，需要 Python 3.10+；已安装 Skill 不依赖模型后端。规范治理源码位于 `governance-src/`，生成包不接受手改。

## 当前职责

| 入口 | 负责的行为 | 验证 |
| --- | --- | --- |
| `contracts`、`controller`、`search/` | 候选合法化、四类搜索、质量配对、共享预算、原子检查点和恢复 | `test_evolution_controller.py`、`test_evolution_selection_budget.py`、`test_evolution_checkpoint_io.py` |
| `reflective`、`source_bridge` | 训练反思、合并和排名、来源哈希绑定的政策文本编辑；最终学习补丁每个政策字段最多一次 | `test_evolution_reflective*.py` |
| `evaluator`、`ablation`、`paired` | 隔离编译、必要闭包保持、按执行输入和重试策略缓存、开发矩阵与完整配对分析 | `test_evolution_evidence.py`、`test_evolution_ablation.py`、`test_evolution_paired.py` |
| `native_codex`、`task_benchmark` | 显式原生 CLI 文件产物任务、正向产物评分和实际回合用量收据 | `test_evolution_native.py`、`test_evolution_task_benchmark.py` |
| `tool_codex`、`tool_broker`、`engineering_broker` | 注册的有界文件和 Git 工具、当前字节收据、工程验证 | `test_evolution_tools.py`、`test_engineering_cli.py`、`test_engineering_broker.py` |
| `semantic_contract`、`isolated_python`、`project_executor` | 有限解释器、显式容器后端与固定工程配方 | `test_semantic_contract.py`、`test_isolated_python.py`、`test_project_executor.py` |
| `provider_tools`、`chat_sse`、`actor_checkpoint` | 显式 API 工具循环、流重建、独立锚定的预算连续恢复 | `test_provider_tools*.py`、`test_actor_checkpoint.py` |
| `engineering_study`、`context_checkpoint` | 前瞻拓扑和配置身份、交接事实与可复用当前工作集 | `test_engineering_study.py`、`test_provider_tools_sse.py`、`test_ocr_evolution_regressions.py` |
| `promotion` | 独立证据准入与原子发布提案 | `test_evolution_evidence.py`、`test_ocr_evolution_regressions.py` |

完整源码、契约和消费者导航见[模块地图](../MODULE_MAP.md)。

## 命令

在仓库根目录使用已验证的 Python 入口：

```text
python -m evolution run --spec evolution/protocol/upg-evolution-v2.json --output eval-workspaces/evolution/run.json
python -m evolution inspect --run eval-workspaces/evolution/run.json
python -m evolution run --spec evolution/protocol/upg-evolution-v2.json --output eval-workspaces/evolution/run.json --resume
python -m evolution ablate --spec evolution/protocol/upg-evolution-v2.json --output eval-workspaces/evolution/matrix
python -m evolution verify --run eval-workspaces/evolution/run.json
python -m evolution propose --run eval-workspaces/evolution/run.json --output eval-workspaces/evolution/proposal
```

默认运行只使用本地合成夹具和编译器／规划器检查。目标是 UTF-8 上下文字节，不能作为任务质量、实际 token、耗时收益或模型效果证据。`verify` 在缺少独立实证时返回非零；`propose` 此时不创建提案。

真实开发调用需要显式 `--runner module:function`，反思还需要 `--backend module:function`。先注册训练和独立选择任务；最终任务不进入学习或选择。`paired` 只接受 runner；可用 `paired_candidate_id` 冻结候选，未提供时仅记录采集时源码身份，事前选定保持未证实。未完成配对不报告配对估计。

## 预算与检查点

失败和重试共同消耗调用、token 与时间预算。已完成回合用量不证明 provider 内部全部尝试均已计费留痕。未知用量、未确认写入或中断调用保留围栏，禁止自动重放。缓存命中不增加样本，能力身份变化不得复用旧收据。

候选、损失及搜索状态在同一边界提交；终态检查点包含摘要与门禁。恢复前核对源码、协议、引擎、回调和预算身份。自己的输出、锁与临时文件不参与引擎摘要。需要外部核对的 pending 调用不能通过重启消除。

## Native CLI development adapter

`UPG_NATIVE_CONFIG` 必须指向操作者明确提供的绝对 JSON 配置路径。配置注册绝对 `binary`、`artifact_root`、模型、推理档位、超时和可信 `grader`。工具不读取或复制登录材料，不更改宿主全局配置，不后台驻留或自动 push。

执行准备代码前，操作者必须在构造客户端之前提供 `execution_inputs_sha256` 摘要列表。摘要由 `native_codex.execution_inputs_identity(source, execution_artifact)` 计算，覆盖完整执行产物与 source 中全部 `.py` 文件；政策文本候选可变化。输入须先通过操作者的独立可信来源核对，不能由待测候选自行决定允许值。没有该注册的配置可用于学习回调，不能执行产物准备。编译器、规划器及其执行依赖改变后需要新注册；旧冻结配置不自动升级。

产物任务校验 JSON 的精确数值和类型、Python AST 或完整文本；不支持的 kind、不可能通过的期望或范围错误在注册时拒绝。CLI 工具任务另外核对真实读写和当前验证。敏感 Git 准备输出只保存长度和哈希，不落原始敏感字节；普通输出保留原始收据。

有限解释器保持调用来源与控制分支来源，不能用解释器内部异常满足任务预期。显式 CPython／工程执行仍保留原 VM、当前字节、执行收据和清理核对；支持范围见[行为契约](behavior-contracts.md)。

## 独立恢复与准入

`provider_tools.run_actor(..., resume_checkpoint=..., trusted_resume_sha256=...)` 需要操作者从独立审计接收的检查点摘要；描述符内的路径与自带哈希不能自行授权恢复。该摘要绑定完整描述符，原请求／工具／时间预算继续累计，检查当前物理前缀及 Git 血缘。执行器或候选不得自行生成信任锚点。

`native_cli_receipts.replay_current_validation` 只重放其收到的权威 journal。需要独立当前字节证明时提供 `current_snapshot_sha256`；只重放 journal 不证明真实磁盘当前状态。

完整独立准入要求见[协议说明](../evolution/protocol/README.md)。开发矩阵、静态完整性或合成测试均不能授予实证通过或正式资格。历史实验文档和注册已移出当前树；需要复核时从 Git 基线 `dc907ea` 按原路径读取完整历史，不复制为另一套当前事实。
