# 有界工具传输

工具传输把模型请求交给已注册的仓库代理，使读取、修改、验证和终态都有可核实收据。它属于仓库内开发/评估能力，不随日常 Skill 执行，也不自行授权模型调用。实现入口是[工具适配器](../evolution/tool_codex.py)、[传输配置](../evolution/cli_transport.py)和[仓库代理](../evolution/tool_broker.py)。

## 子进程配置与授权

ToolCodex 为一次已注册执行建立子进程配置：使用既有官方登录、`--ignore-user-config`、只读原生 shell sandbox，禁用 shell/web/apps/plugins/hooks/Agent 工具，只开放一个必需 MCP 服务的五个注册仓库工具。模型不能借此扩大路径、操作或命令范围。

当前适配器设置 `features.code_mode.enabled=false` 与 `features.code_mode_host=true`，仅对五个已注册工具设置精确的 `approval_mode="approve"`。它保留子进程全局 `never` 策略，不改宿主配置或其他服务授权；没有合适入口或能力时在业务派发前失败。

工具注解描述实际效果：读取、搜索、静态验证和状态是只读、幂等、封闭范围；`repo_patch` 修改内容、非幂等并具有 destructiveHint。全部工具的 openWorldHint 为 false。注解不能替代路径检查、当前哈希和实际授权。

绝对 CLI、同目录 code-mode host、Python、Git、broker、adapter、schema 和配置在注册与派发前核对身份；存在的包清单也须对应注册 CLI。文件身份不能证明操作系统实际选择了哪个子进程，未获得执行路径证明的能力保持 unattested。任何旧主机探针都不替代当前入口验收。

## 传输与收据

共享 HTTP 子配置在注册的 CLI exec 命令上禁用普通请求、流和无界连接重试，不覆盖 base URL、认证或请求头。认证恢复仍可能发起请求，提供方内部重试和失败响应计费覆盖保持未知。未知调用不得自动重放或算作零费用。

每次实际派发先持久化 pending，再保留实际 argv/source/output 身份、完整已知用量、结果与时间边界。回调时间包含配置、编译/规划、身份核对、CLI、评分和收据持久化；调用方准备与 IPC/收集成本另计，不能用较小的内部计时替代完整成本。后处理失败保留已经观察到的用量，缺失收据仍使执行证据不完整。

代理要求独立记录实际读取、修改、当前验证/status 和原生终态；报告“完成”或返回文件清单不代替执行。有限 Python 与显式工程后端的具体范围见[行为契约](behavior-contracts.md)。

## 原生产物配对工具

[evolution/experiments/native_paired](../evolution/experiments/native_paired/) 提供可复用的两修订、两请求模型、八个产物任务的串行配对工具。它比较公开 native 回调的产物质量和完整耗时，不能证明仓库工具使用、跨提供方效果或正式资格。默认准备与父进程校验均不派发模型。

准备入口为 `python -B evolution/experiments/native_paired/prepare.py`。repo、output-directory、artifact-root、binary、git-binary、model-catalog 必须是显式绝对路径；treatment-revision 为完整提交 SHA，两个 models 与 protocol-id 也必须显式注册。control-revision 可显式指定，现有默认基线只是工具参数，不代表当前质量结果。输出须是新的 ignored `eval-workspaces/rc19-native-paired-*` 目录，产物目录独立。

准备固定双方源码、编译器、许可、运行包、共同评分器和相同 HTTP 传输，按注册目录中的 low effort 能力核对请求模型。列入目录不证明当前访问、内部模型身份或服务容量。每个修订/模型使用独立持久 worker，冻结首次/重复 context 顺序；每次任务仍需新 CLI 回合与新收据，准备缓存不是新的独立样本。

`python -B evolution/experiments/native_paired/parent.py --spec PATH` 只验证；真实派发还要求新的 output 路径和精确 `--allow-dispatch-protocol-sha256`，并须得到当前用户授权、公开注册与独立审阅。32 次调用、token/时间停止值和配对推断以新生成协议为准；这些是观测预算，不是账单保证。worker 丢失、未知调用、超时或不完整收据保持失败/未知并停止，不通过重启 worker 改变冻结的缓存计划。

维护该工具可运行 `python -B -m unittest discover -s tests -p test_native_paired.py`；测试使用合成快照与收据，不调用模型。当前测试、发布和安装事实只在[项目状态](../PROJECT_STATE.md)登记。
