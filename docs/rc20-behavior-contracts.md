# Bounded Python behavior contracts

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
contracts are outside this text-specific change. Existing reference/initial
Python programs, private behavior probes, interpreter and PASS rules are
unchanged. This corrects future public specification clarity; it does not regrade
historical runs or turn finite probes into an all-input equivalence proof.

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
contracts. This module does not replace those checks or alter historical
`python_ast` behavior. This repository-only Python 3.10+ tool profile uses
`python_behavior` checks whose `expected` is null and a single task-level
`behavior_contract`. Registration validates the contract schema independently of
the intentionally faulty initial implementation. One validation evaluates the
whole contract once and maps its result to each registered Python output path.
Legacy broker results remain unchanged. Behavior checks retain the original
five result fields and failure types, with an additional `diagnostics` list.
The broker projects only fixed categories and registered paths, sorted and
deduplicated with a limit of 16. These hints never contribute to PASS/FAIL;
probe indices, inputs, expected values and source fragments stay private.

仓库 API adapter v5 对所有条件提供同样的公开路径元数据，不能代替实际必需读取。
默认 `profile_id=None` 保留 `response_json_mode=False`、thinking disabled 与
4096 输出上限。显式 `thinking-enabled-8192-v1` 则固定 DeepSeek flash thinking
enabled、`reasoning_effort=low`，MiMo v2.6 pro thinking enabled 且请求完全省略
effort 字段，两者输出上限均为 8192。调用必须显式选择该 profile、JSON mode
false 与 thinking enabled；这是联合 DEVELOPMENT 条件，不能归因成 thinking
单因素收益，也不说明一般 provider 能力。

传输收据区分已完成的连接阶段失败与可能已开始的请求；unknown 或迟到响应继续
保留 fence，不重试。公开格式错误中的 `JSONDecodeError` 仅在路径匹配已注册
`json`/`file_hash_manifest` 检查时允许原工具反馈循环继续；它不是成功，不放宽
no-op、保护、作用域、partial write 或 unknown 规则。新 API collector 必须显式
选 `build_prompt(..., terminal_report="native-tool")`；默认 JSON 终态提示保留
历史 collector 语义。这些变化需要新的冻结身份，不能修复或重算旧观察。

Task definitions live in `evolution/experiments/context_tasks.py`. Import and
metadata discovery do not construct registered instances. A prospective study
must separately freeze its candidate, interpreter, generator, task order, probes,
tool profile and budget before dispatch. Prior exact-AST results remain historical
artifact checks; this new profile cannot retroactively establish their validity.

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
推断其使用了文档，或证明自然导航必然受益。旧协议、质量和统计门不据此重算。

## 证据文件的公开输出形状

证据任务的公开 CONTRACT 以一个 `evidence_contract` 字段给出输出路径、恰好两个
根键 `source_sha256`/`claims`、完整源码路径名单、哈希规则和唯一一份 claim 值。
`source_sha256` 的键必须恰为该名单，值为实际当前文件原始字节的 SHA256 小写
十六进制，不把 CRLF 改写为 LF 后再哈希，也不沿用修改前源码的哈希。`claims`
必须严格采用 `evidence_contract.claims` 的键、值和 JSON 类型；不能另起别名、
增加字段、把 `false` 改为 `0`，或把未知改成已完成。此说明不改变旧封存任务。

## 有限语法诊断

broker 的 `SEMANTIC_DIAGNOSTIC_CODES` 是可公开反馈的固定名单。现有 VM 已产生
的 `unregistered-call`、`function-annotations-or-decorators`、
`unsupported-signature`、`unsupported-import` 等语法码可直接反馈，不再全部
折叠为 `unsupported-language`。输出仍只有 `code`/注册 `path`，排序去重且最多
16 项；未知码仍归入原有通用类别，资源限制保持失败。诊断不改变 VM、正向检查、
质量、作用域或全轮严重错误规则，不透露 probe、索引、输入、期望值和源码片段。
