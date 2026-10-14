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

The repository API adapter's v4 profile supplies every condition with the same
public path metadata; it does not substitute for required reads. Transport
receipts distinguish completed connection-only failures from requests that may
have started. Unknown or late responses remain fenced, without retries. New
API collectors must explicitly select `build_prompt(...,
terminal_report="native-tool")`; the default JSON terminal prompt preserves
historical collectors. These scaffold changes require new frozen identities and
cannot repair or regrade old observations.

Task definitions live in `evolution/experiments/context_tasks.py`. Import and
metadata discovery do not construct registered instances. A prospective study
must separately freeze its candidate, interpreter, generator, task order, probes,
tool profile and budget before dispatch. Prior exact-AST results remain historical
artifact checks; this new profile cannot retroactively establish their validity.
