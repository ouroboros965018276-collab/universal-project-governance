"""Finite, pure AST behavior contracts for small registered Python modules.

This is an interpreter for an intentionally narrow language, not a Python
sandbox or a proof of arbitrary program equivalence. Submitted code is parsed,
never imported, compiled, evaluated, or executed by the Python runtime.
"""
from __future__ import annotations

import ast
import hashlib
import keyword
from dataclasses import dataclass, field


DEFAULT_LIMITS = {
    "modules": 24, "source_bytes": 262144, "ast_nodes": 12000,
    "probes": 512, "steps": 20000, "call_depth": 32,
    "expression_depth": 64, "value_depth": 24,
    "collection_items": 16384, "string_chars": 16384, "integer_bits": 256,
    "value_nodes": 32768, "value_chars": 262144,
}
_BUILTINS = {"len", "str", "int", "bool", "abs"}
_METHODS = {"strip", "casefold", "upper", "lower"}
_ERRORS = {"ValueError", "TypeError"}


class BehaviorContractError(ValueError):
    """Safe fixed-code failure; integrations may normalize to ValueError."""


class _Stop(Exception):
    def __init__(self, code, path=None):
        self.code, self.path = code, path


class _Unsupported(_Stop):
    pass


class _Mismatch(_Stop):
    pass


class _Raised(Exception):
    def __init__(self, name, origins=frozenset()):
        self.name, self.origins = name, origins


class _Return(Exception):
    def __init__(self, value):
        self.value = value


@dataclass(frozen=True)
class _Value:
    raw: object
    origins: frozenset = frozenset()
    slots: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _Function:
    path: str
    name: str
    node: ast.FunctionDef


def _dependencies(value):
    result = set(value.origins)
    for item in value.slots.values():
        result.update(_dependencies(item))
    return frozenset(result)


def _with_origins(value, origins):
    return _Value(value.raw, value.origins | origins, value.slots)


def _same(left, right):
    # JSON equality with exact primitive types: True must not satisfy 1.
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    return left == right


def _identifier(name):
    return isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name) and not name.startswith("__")


def _path(path):
    return (isinstance(path, str) and path and len(path) <= 1024 and not any(ord(c) < 32 for c in path)
            and not path.startswith(("/", "\\"))
            and "\\" not in path and ":" not in path
            and all(part not in {"", ".", ".."} for part in path.split("/")))


class _Machine:
    def __init__(self, files, contract):
        self.files, self.contract = files, contract
        self.limits = dict(DEFAULT_LIMITS)
        self.modules, self.globals, self.functions = {}, {}, {}
        self.steps = self.depth = self.expr_depth = 0
        self._check_contract()
        self._load()

    def _check_contract(self, check_files=True):
        c = self.contract
        if not isinstance(self.files, dict) or not isinstance(c, dict) or type(c.get("schema_version")) is not int or c["schema_version"] != 1:
            raise _Mismatch("invalid-contract")
        if set(c) - {"schema_version", "modules", "protected_files", "probes", "limits"}:
            raise _Mismatch("invalid-contract")
        if not isinstance(c.get("limits", {}), dict):
            raise _Mismatch("invalid-limits")
        for key, value in c.get("limits", {}).items():
            if key not in self.limits or type(value) is not int or not 1 <= value <= self.limits[key]:
                raise _Mismatch("invalid-limits")
            self.limits[key] = value
        modules, probes = c.get("modules"), c.get("probes")
        if not isinstance(modules, dict) or not modules or len(modules) > self.limits["modules"]:
            raise _Mismatch("invalid-modules")
        if not isinstance(probes, list) or not probes or len(probes) > self.limits["probes"]:
            raise _Mismatch("invalid-probes")
        if any(not _path(p) or not isinstance(s, str) for p, s in self.files.items()):
            raise _Mismatch("invalid-files")
        for path, spec in modules.items():
            if not _path(path) or not path.endswith(".py") or not isinstance(spec, dict):
                raise _Mismatch("invalid-module")
            if set(spec) - {"required_functions", "constants", "forbidden_symbols", "required_imports", "required_calls"}:
                raise _Mismatch("invalid-module", path)
            if check_files and path not in self.files:
                raise _Mismatch("missing-module", path)
            for field_name in ("required_functions", "constants", "required_imports", "required_calls"):
                if not isinstance(spec.get(field_name, {}), dict):
                    raise _Mismatch("invalid-module", path)
            forbidden = spec.get("forbidden_symbols", [])
            if not isinstance(forbidden, list) or any(not _identifier(n) for n in forbidden):
                raise _Mismatch("invalid-forbidden-symbol", path)
            for name, signature in spec.get("required_functions", {}).items():
                if not _identifier(name) or not isinstance(signature, dict) or set(signature) - {"params", "kwonly", "defaults", "kwdefaults"}:
                    raise _Mismatch("invalid-signature", path)
                positional, kwonly = signature.get("params", []), signature.get("kwonly", [])
                defaults, kwdefaults = signature.get("defaults", {}), signature.get("kwdefaults", {})
                if not isinstance(positional, list) or not isinstance(kwonly, list) or not isinstance(defaults, dict) or not isinstance(kwdefaults, dict):
                    raise _Mismatch("invalid-signature", path)
                names = positional + kwonly
                if len(set(names)) != len(names) or any(not _identifier(n) or n in _BUILTINS | _ERRORS for n in names):
                    raise _Mismatch("invalid-signature", path)
                if set(defaults) - set(positional) or set(kwdefaults) - set(kwonly) or defaults and set(defaults) != set(positional[-len(defaults):]):
                    raise _Mismatch("invalid-signature", path)
                self._value(defaults)
                self._value(kwdefaults)
            for name, expected in spec.get("constants", {}).items():
                if not _identifier(name) or name in _BUILTINS | _ERRORS:
                    raise _Mismatch("invalid-constant", path)
                self._value(expected)
            for local, target in spec.get("required_imports", {}).items():
                if not _identifier(local) or local in _BUILTINS | _ERRORS or not isinstance(target, dict) or set(target) != {"path", "name"} or target["path"] not in modules or not _identifier(target["name"]):
                    raise _Mismatch("invalid-required-import", path)
            for caller, targets in spec.get("required_calls", {}).items():
                if caller not in spec.get("required_functions", {}) or not isinstance(targets, list) or not targets:
                    raise _Mismatch("invalid-required-call", path)
                seen_targets = set()
                for target in targets:
                    if not isinstance(target, dict) or set(target) != {"path", "function"} or target["path"] not in modules or target["function"] not in modules[target["path"]].get("required_functions", {}):
                        raise _Mismatch("invalid-required-call", path)
                    identity = (target["path"], target["function"])
                    if identity in seen_targets:
                        raise _Mismatch("invalid-required-call", path)
                    seen_targets.add(identity)
        protected = c.get("protected_files", {})
        if not isinstance(protected, dict):
            raise _Mismatch("invalid-protected-files")
        for path, digest in protected.items():
            if not _path(path) or not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise _Mismatch("invalid-protected-files")
            if check_files and (path not in self.files or hashlib.sha256(self.files[path].encode("utf-8")).hexdigest() != digest):
                raise _Mismatch("protected-file-mismatch", path)
        for probe in probes:
            if not isinstance(probe, dict) or set(probe) - {"path", "function", "args", "kwargs", "expect"}:
                raise _Mismatch("invalid-probe")
            path, name = probe.get("path"), probe.get("function")
            if path not in modules or name not in modules[path].get("required_functions", {}):
                raise _Mismatch("invalid-probe")
            args, kwargs, expected = probe.get("args", []), probe.get("kwargs", {}), probe.get("expect")
            if not isinstance(args, list) or not isinstance(kwargs, dict) or any(not _identifier(k) for k in kwargs):
                raise _Mismatch("invalid-probe")
            self._value(args)
            self._value(kwargs)
            if not isinstance(expected, dict) or len(expected) != 1 or set(expected) not in ({"return"}, {"raises"}):
                raise _Mismatch("invalid-expectation")
            if "raises" in expected and expected["raises"] not in _ERRORS:
                raise _Mismatch("invalid-expectation")
            if "return" in expected:
                self._value(expected["return"])

    def _tick(self):
        self.steps += 1
        if self.steps > self.limits["steps"]:
            raise _Unsupported("step-limit")

    def _value(self, raw, origins=frozenset(), depth=0, budget=None):
        if budget is None:
            budget = [0, 0]
        budget[0] += 1
        if budget[0] > self.limits["value_nodes"]:
            raise _Unsupported("value-node-limit")
        if depth > self.limits["value_depth"]:
            raise _Unsupported("value-depth-limit")
        slots = {}
        if raw is None or type(raw) is bool:
            pass
        elif type(raw) is int:
            if raw.bit_length() > self.limits["integer_bits"]:
                raise _Unsupported("integer-size-limit")
        elif type(raw) is str:
            budget[1] += len(raw)
            if len(raw) > self.limits["string_chars"]:
                raise _Unsupported("string-size-limit")
            if budget[1] > self.limits["value_chars"]:
                raise _Unsupported("value-character-limit")
        elif type(raw) in {list, dict}:
            if len(raw) > self.limits["collection_items"]:
                raise _Unsupported("collection-size-limit")
            if isinstance(raw, dict) and any(type(k) is not str for k in raw):
                raise _Unsupported("non-json-key")
            if isinstance(raw, dict):
                for key in raw:
                    self._value(key, depth=depth + 1, budget=budget)
            slots = {k: self._value(v, depth=depth + 1, budget=budget) for k, v in
                     (enumerate(raw) if isinstance(raw, list) else raw.items())}
        else:
            raise _Unsupported("non-json-value")
        return _Value(raw, origins, slots)

    def _load(self):
        total = 0
        for path in self.contract["modules"]:
            source = self.files[path]
            if len(source.encode("utf-8")) > self.limits["source_bytes"]:
                raise _Unsupported("source-size-limit", path)
            try:
                tree = ast.parse(source, filename="<registered>")
            except (SyntaxError, ValueError, RecursionError):
                raise _Unsupported("syntax-error", path) from None
            total += sum(1 for _ in ast.walk(tree))
            if total > self.limits["ast_nodes"]:
                raise _Unsupported("ast-node-limit", path)
            self.modules[path], self.globals[path] = tree, {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and not _identifier(node.id):
                    raise _Unsupported("forbidden-name", path)
                if isinstance(node, ast.Attribute) and not _identifier(node.attr):
                    raise _Unsupported("forbidden-attribute", path)
            seen = set()
            for node in tree.body:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    continue
                if isinstance(node, ast.FunctionDef):
                    if not _identifier(node.name) or node.name in seen or node.name in _BUILTINS | _ERRORS:
                        raise _Unsupported("duplicate-or-forbidden-symbol", path)
                    if node.decorator_list or node.returns or node.type_comment or getattr(node, "type_params", []):
                        raise _Unsupported("function-annotations-or-decorators", path)
                    a = node.args
                    if a.vararg or a.kwarg or a.posonlyargs or any(x.annotation or not _identifier(x.arg) or x.arg in _BUILTINS | _ERRORS for x in a.args + a.kwonlyargs):
                        raise _Unsupported("unsupported-signature", path)
                    if len({x.arg for x in a.args + a.kwonlyargs}) != len(a.args + a.kwonlyargs):
                        raise _Unsupported("unsupported-signature", path)
                    for expr in a.defaults + [e for e in a.kw_defaults if e is not None]:
                        self._syntax_expr(expr, path, constant=True)
                    function = _Function(path, node.name, node)
                    self.functions[(path, node.name)] = function
                    self.globals[path][node.name] = function
                    seen.add(node.name)
                    self._syntax_block(node.body, path)
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    if name in seen or name in _BUILTINS | _ERRORS:
                        raise _Unsupported("duplicate-or-forbidden-symbol", path)
                    self._syntax_expr(node.value, path, constant=True)
                    self.globals[path][name] = self._constant_expr(node.value, path)
                    seen.add(name)
                elif isinstance(node, ast.ImportFrom):
                    if node.level or not node.module or any(not _identifier(x.name) or not _identifier(x.asname or x.name) for x in node.names):
                        raise _Unsupported("unsupported-import", path)
                    target = node.module.replace(".", "/") + ".py"
                    if target not in self.contract["modules"]:
                        raise _Unsupported("unregistered-import", path)
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if name in seen or name in _BUILTINS | _ERRORS:
                            raise _Unsupported("duplicate-or-forbidden-symbol", path)
                        self.globals[path][name] = (target, alias.name)
                        seen.add(name)
                else:
                    raise _Unsupported("unsupported-module-statement", path)
        # Resolve only registered exports; no Python import machinery runs.
        for path in self.modules:
            for name in list(self.globals[path]):
                self.globals[path][name] = self._resolve(path, name, set())
            self._structure(path)
            for node in ast.walk(self.modules[path]):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    name = node.func.id
                    target = self.globals[path].get(name)
                    if not isinstance(target, _Function) and not (name in _BUILTINS | _ERRORS and target is None):
                        raise _Unsupported("unregistered-call", path)

    def _resolve(self, path, name, seen):
        if (path, name) in seen:
            raise _Unsupported("import-cycle", path)
        value = self.globals[path].get(name)
        if value is None:
            raise _Mismatch("missing-import-export", path)
        if isinstance(value, tuple):
            return self._resolve(*value, seen | {(path, name)})
        return value

    def _structure(self, path):
        spec = self.contract["modules"][path]
        for name in spec.get("forbidden_symbols", []):
            if not _identifier(name):
                raise _Mismatch("invalid-forbidden-symbol", path)
            if any(isinstance(n, ast.Name) and n.id == name or isinstance(n, ast.FunctionDef) and n.name == name
                   or isinstance(n, ast.arg) and n.arg == name
                   or isinstance(n, ast.Attribute) and n.attr == name
                   or isinstance(n, ast.keyword) and n.arg == name
                   or isinstance(n, ast.alias) and (n.name == name or n.asname == name)
                   for n in ast.walk(self.modules[path])):
                raise _Mismatch("forbidden-symbol-present", path)
        for name, expected in spec.get("constants", {}).items():
            value = self.globals[path].get(name)
            self._value(expected)
            if not isinstance(value, _Value) or not _same(value.raw, expected):
                raise _Mismatch("constant-mismatch", path)
        for name, signature in spec.get("required_functions", {}).items():
            function = self.functions.get((path, name))
            if not function or not isinstance(signature, dict) or set(signature) - {"params", "kwonly", "defaults", "kwdefaults"}:
                raise _Mismatch("required-function-mismatch", path)
            args = function.node.args
            actual = {"params": [x.arg for x in args.args], "kwonly": [x.arg for x in args.kwonlyargs],
                      "defaults": {}, "kwdefaults": {}}
            for parameter, expr in zip(args.args[len(args.args) - len(args.defaults):], args.defaults):
                self._syntax_expr(expr, path, constant=True)
                actual["defaults"][parameter.arg] = self._constant_expr(expr, path).raw
            for parameter, expr in zip(args.kwonlyargs, args.kw_defaults):
                if expr is not None:
                    self._syntax_expr(expr, path, constant=True)
                    actual["kwdefaults"][parameter.arg] = self._constant_expr(expr, path).raw
            wanted = {"params": signature.get("params", []), "kwonly": signature.get("kwonly", []),
                      "defaults": signature.get("defaults", {}), "kwdefaults": signature.get("kwdefaults", {})}
            if not _same(actual, wanted):
                raise _Mismatch("signature-mismatch", path)
        for local, target in spec.get("required_imports", {}).items():
            if not isinstance(target, dict) or set(target) != {"path", "name"}:
                raise _Mismatch("invalid-required-import", path)
            # The key labels the contract import. A source-local alias is not
            # part of the public API and may change without changing its route.
            imported = next((n for n in self.modules[path].body if isinstance(n, ast.ImportFrom)
                             and any(a.name == target["name"] for a in n.names)
                             and n.module.replace(".", "/") + ".py" == target["path"]), None)
            if imported is None:
                raise _Mismatch("required-import-mismatch", path)
        for caller, targets in spec.get("required_calls", {}).items():
            if (path, caller) not in self.functions or not isinstance(targets, list) or not targets:
                raise _Mismatch("invalid-required-call", path)
            for target in targets:
                if not isinstance(target, dict) or set(target) != {"path", "function"} or (target["path"], target["function"]) not in self.functions:
                    raise _Mismatch("invalid-required-call", path)

    def _syntax_block(self, nodes, path):
        for node in nodes:
            if isinstance(node, ast.Assign):
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    raise _Unsupported("unsupported-assignment", path)
                if node.targets[0].id in _BUILTINS | _ERRORS:
                    raise _Unsupported("reserved-name-assignment", path)
                self._syntax_expr(node.value, path)
            elif isinstance(node, ast.Return):
                if node.value is not None:
                    self._syntax_expr(node.value, path)
            elif isinstance(node, ast.If):
                self._syntax_expr(node.test, path)
                self._syntax_block(node.body + node.orelse, path)
            elif isinstance(node, ast.Raise):
                if node.cause or not isinstance(node.exc, (ast.Call, ast.Name)):
                    raise _Unsupported("unsupported-raise", path)
                call = node.exc
                name = call.func.id if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) else getattr(call, "id", None)
                if name not in _ERRORS or isinstance(call, ast.Call) and (len(call.args) > 1 or call.keywords):
                    raise _Unsupported("unsupported-raise", path)
                if isinstance(call, ast.Call):
                    for arg in call.args:
                        self._syntax_expr(arg, path)
            elif isinstance(node, ast.Expr):
                self._syntax_expr(node.value, path)
            else:
                raise _Unsupported("unsupported-function-statement", path)

    def _syntax_expr(self, node, path, constant=False):
        if isinstance(node, ast.Constant):
            self._value(node.value)
        elif isinstance(node, ast.Name):
            if not _identifier(node.id):
                raise _Unsupported("forbidden-name", path)
        elif isinstance(node, ast.List):
            for child in node.elts:
                self._syntax_expr(child, path, constant)
        elif isinstance(node, ast.Dict):
            if any(k is None for k in node.keys):
                raise _Unsupported("dictionary-unpack", path)
            for child in node.keys + node.values:
                self._syntax_expr(child, path, constant)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.UAdd, ast.USub)):
            self._syntax_expr(node.operand, path, constant)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Mod)):
            self._syntax_expr(node.left, path, constant)
            self._syntax_expr(node.right, path, constant)
        elif not constant and isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for child in node.values:
                self._syntax_expr(child, path)
        elif not constant and isinstance(node, ast.Compare) and all(isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn)) for op in node.ops):
            for child in [node.left] + node.comparators:
                self._syntax_expr(child, path)
        elif not constant and isinstance(node, ast.IfExp):
            for child in (node.test, node.body, node.orelse):
                self._syntax_expr(child, path)
        elif not constant and isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            self._syntax_expr(node.value, path)
            self._syntax_expr(node.slice, path)
        elif not constant and isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if not _identifier(node.func.id) or node.func.id in _ERRORS:
                    raise _Unsupported("forbidden-call", path)
            elif isinstance(node.func, ast.Attribute) and node.func.attr in _METHODS:
                self._syntax_expr(node.func.value, path)
            else:
                raise _Unsupported("unsupported-call", path)
            if any(k.arg is None or not _identifier(k.arg) for k in node.keywords):
                raise _Unsupported("unsupported-keyword", path)
            for child in node.args + [k.value for k in node.keywords]:
                self._syntax_expr(child, path)
        else:
            raise _Unsupported("unsupported-expression", path)

    def _expr(self, node, local, path):
        self._tick()
        self.expr_depth += 1
        try:
            if self.expr_depth > self.limits["expression_depth"]:
                raise _Unsupported("expression-depth-limit", path)
            return self._expression(node, local, path)
        except (TypeError, ValueError):
            # User primitive failures are translated only at operand-aware sites.
            raise _Unsupported("internal-operation-error", path) from None
        except (IndexError, KeyError, ZeroDivisionError, OverflowError):
            raise _Unsupported("unsupported-operation-error", path) from None
        finally:
            self.expr_depth -= 1

    @staticmethod
    def _primitive(operation, origins):
        try:
            return operation()
        except (TypeError, ValueError) as error:
            raise _Raised("ValueError" if isinstance(error, ValueError) else "TypeError", origins) from None

    def _constant_expr(self, node, path):
        try:
            return self._expr(node, {}, path)
        except _Raised:
            raise _Mismatch("module-evaluation-error", path) from None

    def _expression(self, node, local, path):
        if isinstance(node, ast.Constant):
            return self._value(node.value)
        if isinstance(node, ast.Name):
            value = local.get(node.id, self.globals[path].get(node.id))
            if not isinstance(value, _Value):
                raise _Unsupported("unbound-or-nonvalue-name", path)
            return value
        if isinstance(node, ast.List):
            values = [self._expr(n, local, path) for n in node.elts]
            value = self._value([v.raw for v in values])
            return _Value(value.raw, slots=dict(enumerate(values)))
        if isinstance(node, ast.Dict):
            keys = [self._expr(n, local, path) for n in node.keys]
            values = [self._expr(n, local, path) for n in node.values]
            raw = self._primitive(lambda: {k.raw: v.raw for k, v in zip(keys, values)},
                frozenset().union(*(_dependencies(v) for v in keys + values)))
            value = self._value(raw)
            return _Value(value.raw, frozenset().union(*(_dependencies(k) for k in keys)), {k.raw: v for k, v in zip(keys, values)})
        if isinstance(node, ast.UnaryOp):
            value = self._expr(node.operand, local, path)
            raw = self._primitive(lambda: not value.raw if isinstance(node.op, ast.Not) else
                +value.raw if isinstance(node.op, ast.UAdd) else -value.raw, _dependencies(value))
            return self._value(raw, _dependencies(value))
        if isinstance(node, ast.BinOp):
            left, right = self._expr(node.left, local, path), self._expr(node.right, local, path)
            if isinstance(node.op, ast.Mult):
                sequence, count = (left.raw, right.raw) if isinstance(left.raw, (str, list)) else (right.raw, left.raw)
                if isinstance(sequence, (str, list)) and type(count) is int and len(sequence) * max(count, 0) > min(self.limits["collection_items"], self.limits["string_chars"]):
                    raise _Unsupported("operation-size-limit", path)
                raw = self._primitive(lambda: left.raw * right.raw, _dependencies(left) | _dependencies(right))
            elif isinstance(node.op, ast.Add):
                raw = self._primitive(lambda: left.raw + right.raw, _dependencies(left) | _dependencies(right))
            elif isinstance(node.op, ast.Sub):
                raw = self._primitive(lambda: left.raw - right.raw, _dependencies(left) | _dependencies(right))
            else:
                if type(left.raw) is not int or type(right.raw) is not int:
                    raise _Unsupported("unsupported-modulo", path)
                raw = self._primitive(lambda: left.raw % right.raw, _dependencies(left) | _dependencies(right))
            return self._value(raw, _dependencies(left) | _dependencies(right))
        if isinstance(node, ast.BoolOp):
            dependencies = frozenset()
            for child in node.values:
                value = self._expr(child, local, path)
                dependencies |= _dependencies(value)
                if isinstance(node.op, ast.And) and not value.raw or isinstance(node.op, ast.Or) and value.raw:
                    break
            return _with_origins(value, dependencies)
        if isinstance(node, ast.Compare):
            left, dependencies = self._expr(node.left, local, path), frozenset()
            for op, child in zip(node.ops, node.comparators):
                right = self._expr(child, local, path)
                a, b = left.raw, right.raw
                if isinstance(op, ast.Eq): raw = self._primitive(lambda: a == b, _dependencies(left) | _dependencies(right))
                elif isinstance(op, ast.NotEq): raw = self._primitive(lambda: a != b, _dependencies(left) | _dependencies(right))
                elif isinstance(op, ast.Lt): raw = self._primitive(lambda: a < b, _dependencies(left) | _dependencies(right))
                elif isinstance(op, ast.LtE): raw = self._primitive(lambda: a <= b, _dependencies(left) | _dependencies(right))
                elif isinstance(op, ast.Gt): raw = self._primitive(lambda: a > b, _dependencies(left) | _dependencies(right))
                elif isinstance(op, ast.GtE): raw = self._primitive(lambda: a >= b, _dependencies(left) | _dependencies(right))
                elif isinstance(op, ast.Is):
                    if b is not None and type(b) is not bool: raise _Unsupported("unsupported-identity", path)
                    raw = a is b
                elif isinstance(op, ast.IsNot):
                    if b is not None and type(b) is not bool: raise _Unsupported("unsupported-identity", path)
                    raw = a is not b
                elif isinstance(op, ast.In): raw = self._primitive(lambda: a in b, _dependencies(left) | _dependencies(right))
                else: raw = self._primitive(lambda: a not in b, _dependencies(left) | _dependencies(right))
                dependencies |= _dependencies(left) | _dependencies(right)
                if not raw: break
                left = right
            return self._value(raw, dependencies)
        if isinstance(node, ast.IfExp):
            condition = self._expr(node.test, local, path)
            return _with_origins(self._expr(node.body if condition.raw else node.orelse, local, path), _dependencies(condition))
        if isinstance(node, ast.Subscript):
            value, index = self._expr(node.value, local, path), self._expr(node.slice, local, path)
            raw = self._primitive(lambda: value.raw[index.raw], _dependencies(value) | _dependencies(index))
            key = index.raw + len(value.raw) if isinstance(value.raw, list) and type(index.raw) is int and index.raw < 0 else index.raw
            item = value.slots[key] if key in value.slots else self._value(raw)
            return _with_origins(item, value.origins | _dependencies(index))
        if isinstance(node, ast.Call):
            args = [self._expr(n, local, path) for n in node.args]
            kwargs = {k.arg: self._expr(k.value, local, path) for k in node.keywords}
            if len(kwargs) != len(node.keywords):
                raise _Unsupported("duplicate-keyword", path)
            origins = frozenset().union(*(_dependencies(v) for v in args + list(kwargs.values())))
            if isinstance(node.func, ast.Attribute):
                receiver = self._expr(node.func.value, local, path)
                if type(receiver.raw) is not str or kwargs or len(args) > (1 if node.func.attr == "strip" else 0):
                    raise _Unsupported("unsupported-method", path)
                origins |= _dependencies(receiver)
                if node.func.attr == "strip": raw = self._primitive(lambda: receiver.raw.strip(*[v.raw for v in args]), origins)
                elif node.func.attr == "casefold": raw = self._primitive(lambda: receiver.raw.casefold(), origins)
                elif node.func.attr == "upper": raw = self._primitive(lambda: receiver.raw.upper(), origins)
                else: raw = self._primitive(lambda: receiver.raw.lower(), origins)
                return self._value(raw, origins)
            name = node.func.id
            function = local.get(name, self.globals[path].get(name))
            if isinstance(function, _Function):
                return self._call(function, args, kwargs)
            if name not in _BUILTINS or function is not None:
                raise _Unsupported("unregistered-call", path)
            if kwargs or len(args) != 1:
                raise _Raised("TypeError", origins)
            raw = args[0].raw
            if name == "len": raw = self._primitive(lambda: len(raw), origins)
            elif name == "str": raw = self._primitive(lambda: str(raw), origins)
            elif name == "int": raw = self._primitive(lambda: int(raw), origins)
            elif name == "bool": raw = self._primitive(lambda: bool(raw), origins)
            else: raw = self._primitive(lambda: abs(raw), origins)
            return self._value(raw, origins)
        raise _Unsupported("unsupported-expression", path)

    def _block(self, nodes, local, path, control=frozenset()):
        for node in nodes:
            self._tick()
            try:
                if isinstance(node, ast.Assign):
                    local[node.targets[0].id] = _with_origins(self._expr(node.value, local, path), control)
                elif isinstance(node, ast.Return):
                    value = self._value(None) if node.value is None else self._expr(node.value, local, path)
                    raise _Return(_with_origins(value, control))
                elif isinstance(node, ast.If):
                    condition = self._expr(node.test, local, path)
                    # Retain the chosen condition for following statements as well:
                    # an early guard determines whether they are reached.
                    branch = node.body if condition.raw else node.orelse
                    alternate = node.orelse if condition.raw else node.body
                    self._block(branch, local, path, control | _dependencies(condition))
                    if self._must_exit(alternate):
                        control |= _dependencies(condition)
                elif isinstance(node, ast.Raise):
                    name = node.exc.id if isinstance(node.exc, ast.Name) else node.exc.func.id
                    origins = control
                    if isinstance(node.exc, ast.Call):
                        for child in node.exc.args:
                            origins |= _dependencies(self._expr(child, local, path))
                    raise _Raised(name, origins)
                else:
                    self._expr(node.value, local, path)
            except _Raised as raised:
                raise _Raised(raised.name, raised.origins | control) from None

    @staticmethod
    def _must_exit(nodes):
        for node in nodes:
            if isinstance(node, (ast.Return, ast.Raise)):
                return True
            if isinstance(node, ast.If) and _Machine._must_exit(node.body) and _Machine._must_exit(node.orelse):
                return True
        return False

    def _check_route(self, function, origins):
        targets = self.contract["modules"][function.path].get("required_calls", {}).get(function.name, [])
        if any((target["path"], target["function"]) not in origins for target in targets):
            raise _Mismatch("required-call-not-in-result", function.path)

    def _call(self, function, args, kwargs):
        self._tick()
        self.depth += 1
        edge = frozenset({(function.path, function.name)})
        try:
            if self.depth > self.limits["call_depth"]:
                raise _Unsupported("call-depth-limit", function.path)
            spec = function.node.args
            positional, kwonly = [p.arg for p in spec.args], [p.arg for p in spec.kwonlyargs]
            if len(args) > len(positional) or set(kwargs) - set(positional + kwonly) or any(p in kwargs for p in positional[:len(args)]):
                raise _Raised("TypeError")
            local = dict(zip(positional, args))
            local.update(kwargs)
            defaults = dict(zip(positional[len(positional) - len(spec.defaults):], spec.defaults))
            defaults.update({p: expr for p, expr in zip(kwonly, spec.kw_defaults) if expr is not None})
            for parameter in positional + kwonly:
                if parameter not in local:
                    if parameter not in defaults:
                        raise _Raised("TypeError")
                    local[parameter] = self._expr(defaults[parameter], {}, function.path)
            try:
                self._block(function.node.body, local, function.path)
                value = self._value(None)
            except _Return as returned:
                value = returned.value
            except _Raised as raised:
                self._check_route(function, raised.origins)
                raise _Raised(raised.name, raised.origins | edge) from None
            self._check_route(function, _dependencies(value))
            return _with_origins(value, edge)
        finally:
            self.depth -= 1

    def probe(self, probe):
        if not isinstance(probe, dict) or set(probe) - {"path", "function", "args", "kwargs", "expect"}:
            raise _Mismatch("invalid-probe")
        function = self.functions.get((probe.get("path"), probe.get("function")))
        expected = probe.get("expect")
        args, kwargs = probe.get("args", []), probe.get("kwargs", {})
        if not function or not isinstance(args, list) or not isinstance(kwargs, dict) or any(not _identifier(k) for k in kwargs):
            raise _Mismatch("invalid-probe")
        if not isinstance(expected, dict) or len(expected) != 1 or set(expected) not in ({"return"}, {"raises"}):
            raise _Mismatch("invalid-expectation")
        if "raises" in expected and expected["raises"] not in _ERRORS:
            raise _Mismatch("invalid-expectation")
        if "return" in expected:
            self._value(expected["return"])
        self.steps = self.depth = self.expr_depth = 0
        try:
            result = self._call(function, [self._value(v) for v in args], {k: self._value(v) for k, v in kwargs.items()})
        except _Raised as raised:
            if expected.get("raises") != raised.name:
                raise _Mismatch("exception-mismatch", function.path) from None
        else:
            if "return" not in expected or not _same(result.raw, expected["return"]):
                raise _Mismatch("return-mismatch", function.path)


def validate_behavior(files, contract):
    """Validate only in-memory strings; return fixed diagnostics, never source.

    PASS means these finite structural checks and probes passed in the supported
    language. It does not establish equivalence outside the registered probes.
    Limits may be lowered by the contract, never increased.
    """
    result = {"ok": False, "status": "FAIL", "checks_total": 0, "checks_passed": 0, "failures": []}
    try:
        machine = _Machine(files, contract)
        result["checks_total"] = 1 + len(contract["probes"])
        result["checks_passed"] = 1
        unsupported = False
        for index, probe in enumerate(contract["probes"]):
            try:
                machine.probe(probe)
            except _Stop as error:
                failure = {"code": error.code, "probe": index}
                if error.path is not None:
                    failure["path"] = error.path
                result["failures"].append(failure)
                unsupported |= isinstance(error, _Unsupported)
            else:
                result["checks_passed"] += 1
        result["status"] = "UNSUPPORTED" if unsupported else "FAIL" if result["failures"] else "PASS"
        result["ok"] = result["status"] == "PASS"
    except _Stop as error:
        result["status"] = "UNSUPPORTED" if isinstance(error, _Unsupported) else "FAIL"
        failure = {"code": error.code}
        if error.path is not None:
            failure["path"] = error.path
        result["failures"].append(failure)
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError, _Raised):
        # Malformed declarative data and parser recursion fail closed.
        result["failures"].append({"code": "invalid-contract-or-limit"})
    return result


validate_modules = validate_behavior


def validate_contract(contract):
    """Pure schema validation; does not require an initially faulty module to pass."""
    result = {"ok": False, "status": "FAIL", "checks_total": 1, "checks_passed": 0, "failures": []}
    try:
        machine = _Machine.__new__(_Machine)
        machine.files, machine.contract = {}, contract
        machine.limits = dict(DEFAULT_LIMITS)
        machine._check_contract(check_files=False)
    except _Stop as error:
        result["status"] = "UNSUPPORTED" if isinstance(error, _Unsupported) else "FAIL"
        failure = {"code": error.code}
        if error.path is not None:
            failure["path"] = error.path
        result["failures"].append(failure)
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
        result["failures"].append({"code": "invalid-contract-or-limit"})
    else:
        result.update(ok=True, status="PASS", checks_passed=1)
    return result


def require_behavior(files, contract):
    result = validate_behavior(files, contract)
    if not result["ok"]:
        raise BehaviorContractError("python-behavior-contract-failed")
    return result
