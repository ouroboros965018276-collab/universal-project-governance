# Bounded Python behavior contracts

这些仓库内契约让开发任务的行为、工具执行与证据保持可核实；它们不随 Skill 交付，也不自行授权调用模型。各执行配置有独立身份，变更后需要重新注册，不能把旧观察解释成新配置的结果。当前交付与验证状态见[项目状态](../PROJECT_STATE.md)。

| 部分 | 职责 | 存在原因 |
| --- | --- | --- |
| 有限解释器 | 解析公开子语言、运行注册纯函数探针 | 检验行为而不把返回源码当作宿主程序执行 |
| 仓库 broker | 约束工具、读写范围、当前哈希和正向产物 | 防止完成报告、文件清单或空检查代替真实工作 |
| 显式 CPython 后端 | 在固定隔离配置中执行已准入调用并核对收据 | 区分解释器规则通过与真实 Python 执行完成 |
| 工程 executor | 执行注册的导入、unittest、模块 CLI 和文件配方 | 用实际集成结果补足有限探针的覆盖边界 |
| API/CLI 适配器 | 固定配置、预算、传输、工具链和终态身份 | 保留完整已知成本，使失败、迟到和未知可区分 |
| 项目阶段状态 | 保留活动工作、当前引用与最新/上一次完成 | 让后续接手基于当前事实，而非过期成功摘要 |


`validate_contract(contract)` validates only the declarative schema. An initial
implementation can be incorrect while its contract is valid.

`validate_behavior(files, contract)` consumes an in-memory mapping of relative
paths to UTF-8 source text. It returns `ok`, `status` (`PASS`, `FAIL`, or
`UNSUPPORTED`), counts, and fixed diagnostic codes. `require_behavior` raises
`BehaviorContractError`, a `ValueError` subclass with a fixed message, unless the
result is `PASS`. A broker can normalize this to builtin `ValueError` without
exposing private probes or expected values.

The interpreter uses `ast.parse`, never imports or executes submitted modules,
and contains no file, network, subprocess, `exec`, `eval`, or `compile` call.
Trusted Python AST parsing still uses the host's parser. This is a small finite
language interpreter, **not a security sandbox for arbitrary Python**.

The supported subset must be public before an evaluation starts:

- Plain functions with positional and keyword-only parameters and pure defaults;
  constants, local assignment, `if`, `return`, and `raise ValueError/TypeError`.
- `None`, bool, bounded int/string/list/dict values; subscripts; `+`, `-`, `*`,
  integer `%`; comparisons, `and`, `or`, `not`, unary signs and conditional
  expressions. `is`/`is not` are restricted to `None`/bool comparisons.
- `len`, `str`, `int`, `bool`, `abs`; string `strip`, `casefold`, `upper`, `lower`.
- Static absolute `from registered.module import export [as local]`. Imported
  modules must be present in `contract.modules`. No Python import machinery is
  used to resolve them. Local import aliases may change.
- No loops/comprehensions, arbitrary attributes, mutation of collection items,
  classes, decorators/annotations, dynamic imports, dunder identifiers, dynamic
  functions, or host/OS builtins. Syntax outside the subset is rejected even in
  an unreached function/branch. Unsupported operations and resource limits never
  produce `PASS`.

Text-normalization task families additionally publish one structured
`text_normalization` block in their project `CONTRACT.json`. It names the bounded
input domain, the exact **string** sentinel `UNKNOWN`, conversion and empty-text
behavior, and each existing case/prefix mode. Null returns `UNKNOWN` immediately:
it receives no prefix, case conversion or keyword-mode transformation. Every
non-null value uses Python `str(value)`, then `strip()`; empty text raises
`ValueError`. Chinese documentation uses casefold without a prefix; project
recovery prefixes non-null casefolded text. The public API uses casefold without
a prefix for `shout=False`, and prefix plus uppercase for `shout=True`; the
existing public exports and routes define `loud` defaults and forwarding.

Shared public text metadata defines these semantics. Its null and case values
feed the reference source/helper and fixed public examples; the existing
`str`/`strip`/`ValueError` implementation is independently checked against the
public block. Examples include null, empty/blank text and string coercion and
are generated independently of the private challenge sampler. Source and
receiver retain the same text meaning, with writable scope and pending routes
declared separately by stage.
Numeric families and document-maintenance tasks derived from numeric safety
contracts have separate contracts. Public text examples and private behavior
probes remain distinct; finite probes do not establish all-input equivalence.

`DEFAULT_LIMITS` is the exact public limit map. Contracts may only lower it.
Limits cover module/source/AST/probe counts, steps, call/expression/value depth,
individual strings/collections/integers, and aggregate value nodes/characters
(including dictionary keys). No iteration construct is available; recursive
functions are bounded by both call depth and steps. Sequence multiplication is
checked before allocation.

Contract schema version 1 uses top-level `modules`, `protected_files`, `probes`,
and optional `limits`. A module declares `required_functions` (parameter names,
keyword-only names, defaults), `constants`, `forbidden_symbols`,
`required_imports`, and `required_calls`. Probes declare a registered path and
function, args/kwargs, and either a JSON return value or `ValueError`/`TypeError`.
Return comparisons distinguish bool from int. Protected-file SHA256 checks use
the exact input text's UTF-8 bytes, preserving CRLF when the caller supplies it.

`required_imports` keys label contract imports; the canonical path/export is
checked without requiring a particular local alias. `required_calls` uses the
actual registered callee identity. A required callee must contribute to the
returned value or a condition that selects a returning path. Discarded calls,
unused imports, and unselected container values do not satisfy this requirement.
This bounded dependency evidence is **not a general no-bypass proof**: operations
can retain provenance without being mathematically necessary (for example,
multiplication by zero). Finite input probes likewise do not prove behavior for
all Python inputs. Evaluation claims must name the supported subset and fixed
probes, and retain this limitation.

The caller/broker additionally enforces exact registered file namespace, writable
scope, required reads/tools, native-terminal evidence, and evidence-document
contracts. This module does not replace those checks; `python_ast` remains a
separate static check. This repository-only Python 3.10+ tool profile uses
`python_behavior` checks whose `expected` is null and a single task-level
`behavior_contract`. Registration validates the contract schema independently of
the intentionally faulty initial implementation. One validation evaluates the
whole contract once and maps its result to each registered Python output path.
Behavior checks retain the
five result fields and failure types, with an additional `diagnostics` list.
The broker projects only fixed categories and registered paths, sorted and
deduplicated with a limit of 16. These hints never contribute to PASS/FAIL;
probe indices, inputs, expected values and source fragments stay private.

仓库 API adapter 对所有条件提供同样的公开路径元数据，不能代替实际必需读取。
默认 `profile_id=None` 保留 `response_json_mode=False`、thinking disabled 与
4096 输出上限。显式 `thinking-enabled-8192-v1` 则固定 DeepSeek flash thinking
enabled、`reasoning_effort=low`，MiMo v2.6 pro thinking enabled 且请求完全省略
effort 字段，两者输出上限均为 8192。调用必须显式选择该 profile、JSON mode
false 与 thinking enabled；这是联合 DEVELOPMENT 条件，不能归因成 thinking
单因素收益，也不说明一般 provider 能力。

`thinking-enabled-flash-8192-v1` 保持 DeepSeek 配置相同，将 MiMo 固定为
`mimo-v2.6-flash` thinking enabled、effort 字段省略、8192 输出上限。
`thinking-disabled-flash-8192-v1` 固定双方 Flash、thinking disabled、8192 输出上限；
`thinking-disabled-deepseek-pro-mimo-flash-8192-v1` 则固定 DeepSeek Pro / MiMo Flash。
它们都无自动型号切换或未知请求重试。

配置、模型 ID、估计费率及币种以 [provider_tools.py](../evolution/provider_tools.py) 的
`profile_configuration(profile_id)` 返回值为准，注册时绑定配置哈希与持久预算。
这些值是预算估计，不是实时服务报价或账单保证；币种不能相加，API 别名也不证明
提供方内部版本固定。模型目录可见或配置存在不能证明访问、容量、任务质量或收益。

显式 Flash 或 Pro/Flash 配置的请求收据增加 `deadline_telemetry`：同一单调时钟采样的
actor elapsed、实际传给 `_bounded_post` 的等待参数及返回/异常后的 actor elapsed；
它不是底层 socket timeout、服务端延迟或已发送证明。调用配置 hash 绑定到 pending
及 outcome，遥测在 outcome/回调持久化；硬杀在 outcome 前发生时不能补造遥测。
默认单 actor 总预算为 180 秒；显式扩展配置另行绑定预算，延长上限不代表降低耗时。
没有新增未证实的 reasoning budget/effort 参数，完整 opaque reasoning 回传不变。

传输收据区分已完成的连接阶段失败与可能已开始的请求；unknown 或迟到响应继续
保留 fence，不重试。上述两个 disabled 配置可显式启用
`confirmed-pre-http-connect-once-v1`：只允许已证明 HTTP 尚未开始的白名单连接失败，
且须由外层持久预算回调绑定原请求与收据授权一次；新槽位、预留和收据沿用相同请求
正文及剩余原预算。默认不启用；HTTP 503、可能已发送、响应或用量未知均不能授权重试。
公开格式错误中的 `JSONDecodeError` 仅在路径匹配已注册
`json`/`file_hash_manifest` 检查时允许原工具反馈循环继续；它不是成功，不放宽
no-op、保护、作用域、partial write 或 unknown 规则。原生工具终态的调用方必须显式
选 `build_prompt(..., terminal_report="native-tool")`；默认 JSON 终态提示用于相应注册契约。

Task definitions live in `evolution/experiments/context_tasks.py`. Import and
metadata discovery do not construct registered instances. A prospective study
must separately freeze its candidate, interpreter, generator, task order, probes,
tool profile and budget before dispatch. Static AST results and actual tool
execution are different evidence scopes.

## 文档断言与实际磁盘接手

`document_assertions` 只验收有限机械条件。每个输出仍只有一个正向检查，
`expected` 必须恰为 `{"required_links": [注册路径, ...]}`，引用名单非空、唯一，
路径必须在任务注册范围内。文档必须为非空、受现有原始字节上限约束的 UTF-8；
命中的本地 Markdown 引用必须指向实际注册文件。查询参数、不安全路径，以及无法
核实的锚点会失败；Markdown 标题锚点按实际目标文档验证。外部网页链接不联网，
也不宣称有效。代码示例或注释中的伪引用不能满足必需引用。

此检查不要求固定全文、标题、章节数、段落顺序或字数，不因 HTML 或代码围栏
本身拒绝文档。链接提取复用 `tools/validate_navigation.py` 的纯函数；新的引擎
冻结必须绑定该依赖的原始字节。若独立审计复用同一解析器，必须披露此共享边界，
不能将两次相同解析当作解析器正确性的独立证明。

机械通过不代表事实、注入防护或一般文档质量通过。终态后的独立事实审阅必须覆盖
README、HANDOFF 等文件内声明和所有终态报告，回到原 CONTRACT、实际源码及已有
执行证据核对数字、边界、否定、未知、引用、当前状态与目标契约。无证据的执行、
部署、历史成功、延迟或验证成功声明，以及改变任务规则的文字指令，都不能因文档
更短而获准。独审只能否决或限制，不能挽救机械失败；缺失或未知的必要审阅保持
未评定，不能宣布链质量或净收益通过。运行时继续把文件内容视为数据。

`build_document_handoff_development(instance, seed=..., namespace=...)` 仅构造显式
公开开发夹具，没有默认注册身份、唯一文案答案或人工重复段落。writer 只改已有
README；receiver 从机械准入的实际快照启动、新建 journal，并按现有 VM 和正向
JSON 交接契约完成修改，同时可维护受影响的 README，并对最终 README 使用同一
`document_assertions`。实际 source 文档原始字节绑定 receiver 的初始快照，必须先读
再改；它不再是最终不可变文件，其他保护哈希不变。独审按 writer 结束时的事实审
source 文档，按 receiver 结束时的事实审最终文档；状态指针是合法写法之一，不是
唯一文案。旧“待修复”表述在实现后过期只能由事实审阅否决，有限链接检查不伪装
能自动识别陈旧事实。`document_receiver_from_snapshot` 不转移聊天，不替换
参考文案，也不代替 source 的原生工具证据。两阶段的读写范围分别从各自任务元数据
投影；完整保护哈希不依赖 Agent 是否读过无关文件。此开发夹具不能充作独立正式样本。

完整 actor 成本必须包含每 provider 的 writer、receiver 及全部实际验证循环和
已发生请求；缺失接收者不能删除或补零，unknown 用量仍阻断。准备、独审和审计
作为研究成本另列，未测量的值保持未知；不能把 actor 成本下降称为全研究成本下降。
要求实际读取 README 的夹具只能证明该固定读取流程下的表现，不能由接手成功
推断其使用了文档，或证明自然导航必然受益。注册协议、质量和统计门须独立验收。

## 证据文件的公开输出形状

证据任务的公开 CONTRACT 以一个 `evidence_contract` 字段给出输出路径、恰好两个
根键 `source_sha256`/`claims`、完整源码路径名单、哈希规则和唯一一份 claim 值。
`source_sha256` 的键必须恰为该名单，值为实际当前文件原始字节的 SHA256 小写
十六进制，不把 CRLF 改写为 LF 后再哈希，也不沿用修改前源码的哈希。`claims`
必须严格采用 `evidence_contract.claims` 的键、值和 JSON 类型；不能另起别名、
增加字段、把 `false` 改为 `0`，或把未知改成已完成。

## 有限语法诊断

broker 的 `SEMANTIC_DIAGNOSTIC_CODES` 是可公开反馈的固定名单。现有 VM 已产生
的 `unregistered-call`、`function-annotations-or-decorators`、
`unsupported-signature`、`unsupported-import` 等语法码可直接反馈，不再全部
折叠为 `unsupported-language`。输出仍只有 `code`/注册 `path`，排序去重且最多
16 项；未知码仍归入原有通用类别，资源限制保持失败。诊断不改变 VM、正向检查、
质量、作用域或全轮严重错误规则，不透露 probe、索引、输入、期望值和源码片段。

有限 CPython 模式可显式选择 `tool_feedback_policy="public-finite-language-reminder-v1"`。仅在已验证、可继续的 `unregistered-call` 与 `NOT_RUN_VM_FAILED` 结果后，模型工具消息才补充匹配公开语言的 builtin／注册调用提醒；缺失、歧义或不匹配的公开配置保持原消息。默认不启用，原 broker 结果、事件哈希、执行状态和评分不变。新实验须对各组使用同一策略，并独立重建后续请求的实际消息、用量和费用估算。

## 显式有限 CPython 后端

仓库代理默认行为保持不变。显式选择 `docker-cpython-finite-v1` 时，仍先通过完整
VM 契约、必需调用与结果依赖检查，再以固定镜像执行已准入的有限调用，由主机沿用
`_same` 精确比较返回值或异常。容器只接收注册平面 UTF-8 快照和调用参数，不接收
期望值或私有验收清单；不增加工具，不允许 Agent 自选命令、镜像或宿主路径。
它验证有限 CPython 函数行为，不能代表任意 Python、完整应用或全部宿主安全。

该模式要求独占的新建项目外产物目录和绝对截止时间，每次执行保留不可覆盖的
`validation-NNN` 收据；无行为调用为 `NOT_APPLICABLE`，VM 失败不启动容器。
`registered-real-cpython-contracts-v1` 的公开 `execution` 字段只投影绑定哈希、
状态、清理和本次验证观测耗时，不暴露调用参数、结果或期望值。`EXECUTED` 只表示
执行传输完整，仍须主机比较通过；unknown、基础设施失败或清理未确认均不能通过。
primitive 返回状态还必须与实际收据原始字节一致，不能单凭旧成功文件认定成功。
文件系统调用无法由 Python 硬抢占，完整链成本须另计准备、验证、容器与清理；
未确认收据保留原样，不回退 VM 或重放来修补。现有文档与终态事实独审仍只可否决。

## 显式标准库 Python 工程配置

工程 API 可显式选择 `thinking-enabled-engineering-pro-16384-v1`：DeepSeek
`deepseek-v4-pro` 开启 thinking/high，MiMo `mimo-v2.6-pro` 开启 thinking；
每次输出上限 16,384 token，调用方可注册至多 24 请求、600 秒工作时间和 32 工具。
默认请求配置为 12 请求、180 秒；扩展配置只准入显式工程 backend 和持久预算回调。
已观察的 reasoning 字段原样传回，工具选择保持 auto，不自动重试未知请求。
配置、费率估计和预算绑定到收据。提高上限只解决执行
可行性，不能作为质量或成本收益证据；各实验条件须使用同一已注册配置。

可显式选择 `thinking-enabled-engineering-pro-16384-v2`，其模型、费率、输出、
请求数、工作时间、工具数与 v1 相同，仅把完整 canonical 请求 JSON 的字节准入上限
设为 524,288（512 KiB），通过配置 `admission_limits.max_input_bytes`、请求收据及
结果的 `max_input_bytes` 绑定。超限在预算预留与首次凭据加载前停止；预留仍使用实际
`input_utf8_bytes`，不按上限计费。v1 配置为 131,072 字节；文件、工具和证据
读取上限不变。此有限上限不保证 24 次满输出历史均可容纳，亦不裁剪消息或 reasoning；
不会增加续接、重试或工作时间，调用方须在新账本为全部实验条件注册同一配置与费用上限。

原生 API 响应使用独立的 2 MiB 严格 JSON 与结构上限，项目文件和工具参数的 64 KiB
上限保持不变。该推理配置中，计费主数一致而可选 reasoning 细分计数无效时，仅细分项
为未知，原始计数保留；主数、加总和缓存计数仍严格校验。
显式 `reasoning_continuation_policy="empty-reasoning-length-continue-once-v1"` 可在已知、
及时、无工具且正文为空的推理长度截断后，保留原 reasoning 并请求一次续接；默认关闭。
续接使用剩余原预算，不执行工具、不提交报告；再次截断、普通结束、非空正文、未知或
迟到响应不能续接。收据绑定策略，读取器须从原响应重建后续消息与次数。

显式 `thinking-enabled-engineering-pro-16384-v3` 沿用 v2 的模型、预算及推理续接，
通过官方 Chat SSE 接收响应。最多保留 8 MiB 原始响应，单事件 256 KiB、65536 个块，
组装结果最多 2 MiB；工具及项目文件上限不变。只有完整 finish、有效 usage、DONE、
正常 HTTP EOF、请求线程退出且证据持久化后，才能交付及时且合法的工具调用。
工具片段非法仍保留完整已知用量；断流保留已观察分量和未知预留，不自动重试。
这项传输能力不构成任务质量、成本或网络可靠性改善的证据；旧轮未知用量不能补算。

`stdlib-python-project-v1` 使用独立身份 `official-chat-api-registered-project-v1` 和
`docker-cpython-project-v1`，复用原 API 循环及受控文件操作。只接受固定 Pro/Flash
模型配置、持久预算回调和注册任务；默认和有限 VM 配置使用各自注册契约。

`ToolCodex` 也可通过显式 `broker_profile_id="stdlib-python-project-v1"` 使用同一工程代理，
身份为 `codex-exec-required-stdlib-project-mcp-v1`。CLI 仅开放五个注册 MCP 工具，
结束报告使用原生 JSON schema；API 使用 `repo_finish`。CLI 的完成回合用量不证明
内部 HTTP 请求数、全部重试费用或受控中断能力，不能套用 API 的逐请求预留结论。
模型发送前，项目模式将固定 Git 初始化的 intent、原始双流、退出码、耗时和来源绑定
写入工作区外的 `preparation/git-init/`。持久化失败或初始化失败保留锁和未派发记录；
未知异常文字不进入对外原因字段。既有成功收据的准备证据发生漂移时拒绝重放。

`repo_validate` 执行可信任务注册的标准库包导入、unittest、模块 CLI 与文件处理配方，
模型不能提交 shell、任意 argv、环境或镜像。测试必须匹配完整 ID 与数量；零测试、
跳过、预期失败或文本 PASS 不能替代成功检查。

工程配置允许一次已证明整批未执行的参数 schema 纠正，拒绝收据先持久化，原预算继续计数；
越界、部分写入和未知均终止。现存文件修改前须有当前读取或已确认写入证据。
`initial_paths` 表示现存文件，`writable_files` 也可包含允许新建的路径。`repo_read` 对范围内
尚不存在的可写文件返回 `exists: false, text: null, sha256: null`；这不构成已读取内容的证据。
仅该工程配置的 `repo_patch` 允许 `new_text: null` 删除已读取、旧哈希匹配的既存可写文件；
未提供 `old_text` 时，字符串替换整个文件。提供非空 `old_text` 时，它须在当前文件中恰好匹配
一次，仅该片段替换为字符串 `new_text`，其余内容保留；仍须当前读取和完整文件 SHA，不能
用于新建或删除文件。空 `new_text` 可删除匹配片段，空文件、无变化和歧义匹配仍拒绝。
这些行为须绑定注册源码。整批先验证范围、前置哈希及字节限制，再核实写入或缺席状态；
部分或未确认改动停止。只有确认删除的路径可以缺席，未经工具删除或无授权复现仍拒绝。
每次执行绑定源码、契约、runner、原始双流、退出、隔离和清理；终态只复核当前原始收据，
不再次执行。缺失、篡改或过期证据不能通过；执行未知保留 pending，已知 API 用量仍保留。

工程 `repo_status` 另给出由现有收据派生的 `completion_readiness`：缺失的成功必需工具、当前验证状态与当前 status。它不执行验证，不改变预算、评分或路径限制；就绪仅说明这些证据齐备，不代表任务或安全通过。后续编辑会使受影响验证过期，模型须在原预算内补齐或如实保留未完成。反馈按当前源码身份核对，不能回写已完成观察。

当前快照从未验证或最后验证后又改动，属于任务失败的 `NOT_RUN`；过期验证先按原始文件
快照回读收据，不能覆盖当前改动。已经尝试的执行若原始收据缺失、篡改或状态不明，仍为
执行未知；这两种状态都不能算验证成功，也不补跑容器来改写既有观察。

可信测试与契约注册仍严格解析。运行时候选源码的语法错误、空实现或缺失模块由隔离配方
实际检查，记录为已知任务失败，允许模型在剩余原预算内修复。模块执行前核对 `/src`
来源，不能因目标删除而运行同名标准库模块。失败工具结果的 `diagnostics` 只投影完整
收据中通过哈希、字节上限及凭据检查的原始双流；每项最多 4096 字节，最多八项。
成功或执行未知时为空；收据复核须精确重现诊断，不增加隐式重跑。

显式受控中断仅允许首个成功 `repo_patch` 位于请求批次末尾，并由持久授权、工具链、当前
快照和下一请求身份共同绑定。适配器在下一预算预留或请求之前停止；源端未完成、不评分，
保留其 actor pending，与未知费用预留分开。接手只能使用源端实际磁盘，独立完成当前验证；
该路径不能清除先前未知、补写意图或把中断算成成功。

API 可另行显式选择 `settlement_policy="work-deadline-accounting-only-settlement-600s-v1"`，
使用身份 `official-chat-api-registered-project-settlement-v1`。默认配置工作预算至多 180 秒，
上述显式工程推理配置至多 600 秒；
截止后只观察同一在途请求，绝对观察截止为原工作截止加 600 秒，不新增请求、工具或成功报告。
完整迟到响应可结算一次用量，但任务为 `work-deadline-settled-unfinished`，成功标记为 false，
actor pending 保留。worker 只发布有界内存观测，主线程负责原始收据和 accounting；
已开始的远端请求不因此取消，线程存活与完成字段也不证明远端取消或清理。
完整用量遇到 close 错误仍保留已知分量；不完整响应、持久化或结算不确定性继续保留预留和围栏。
外层协议须绑定字段、观察与工作预算及全部实际等待成本；collector、ledger 和 auditor
必须匹配该配置，不能仅改标签复用或事后补算未观察到的用量。

工程适配器可显式绑定首次准备之前的绝对 actor 工作时钟，并选择
`before-first-repository-tool-delivery-v1` 或 `first-confirmed-repo-patch-request-tail-v1`。
前者在首批参数验证后、实际交付工具前停止；后者保留首次成功修改所在请求的完整工具尾部，
包括该批次中的多次修改或已知验证失败。两者要求已知请求用量、闭合 worker、持久授权、
原始工具链和当前状态一致，且不能新增请求。源端保持未完成、不做完成评分；其安全与事实
缺陷仍可否决接手结果。默认入口不启用该机制；本地契约测试不代表远端迟到结算能力已经验证。

显式 `thinking-enabled-engineering-ultraspeed-strict-dslow32768-mimo65536-checkpoint-working-set-once-sse-v1`
保留一次有界会话检查点，并从原始工具收据重建仍与当前 SHA 一致的已读或已确认写入正文。
未携带的路径明确列出，删除内容不恢复，未知意图不补写，验证过期状态不清除。
该配置在完整工具批次交付后且输入达到 64 KiB 时尝试压缩；完整事实超过 64 KiB、恢复输入超过 256 KiB，或未严格缩小输入时，
保留原会话而不截断事实。请求、工具、工作与结算预算不增加，其他配置使用各自字节契约。
事实投影和边界以[检查点实现](../evolution/context_checkpoint.py)为准；相关测试不代表真实 token 或耗时收益。

[工程路由](../evolution/engineering_study.py)声明单模型与跨提供方接手条件、任务族、角色和共享预算。
拓扑及上限只从注册配置导出，不将各角色上限解释为可同时用满的总预算；未使用原生 CLI 的流程
不构成原生 CLI 证据。是否允许恢复须在派发前核对，后续修复不能消除原有失败或未知。

这些实验配置不随 Skill 交付。`project_tool` 不可用，按既有手工状态路径披露绑定与报告缺口。
范围限注册标准库工程；同进程、同 UID 的恶意 Python 仍可干扰 unittest 或 runner，
不能由固定 ID 检查宣称防伪、任意项目安全、完整应用正确或正式资格。来源消融、模型净收益
及独立任务验证分别验收；公开人工执行器样例不代替这些证据。


## 当前状态与阶段记录

`project_tool finish` 的 `checkpoint_id` 只用于 partial/blocked，标识一次真实阶段边界；同编号同载荷幂等，同编号不同载荷拒绝，新的阶段可继续同一活动工作流。完成身份唯一，原开始事实和旧报告不改写。两种报告模式均递增序号；报告关闭后再开启也不回退。

可选 `current_state: {"path": "project-relative/state.json", "sha256": "64 lowercase hex"}` 引用项目已有当前状态 JSON，不复制其业务字段。`status` 返回当前引用、活动结果及字段职责；引用缺失、路径不安全或字节变化时返回不健康，接手者须回到项目事实核对并记录新阶段。引用只能证明字节一致，不能证明业务断言正确。`latest_change`/`previous_change` 保留已完成事项的因果历史；账本是历史观察。未使用工具或未注册引用的项目不能声称自动发现全部状态漂移。

Git 按项目与用户策略，在有意义且已验证的阶段、风险或交接边界评估检查点；合并相关修改，检查差异，跳过未改变或重复状态提交。没有按每次工具调用自动提交的定时器、Hook 或自动 push。
