"""Bounded repository MCP tools; submitted source is parsed, never executed.

This is a development tool profile, not an OS/container isolation claim. The
official CLI retains its existing authentication; none is passed to Git or
placed in the synthetic repository. Only registered text files are accessible.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import time
try:
    import tomllib
except ImportError:  # General runtime/JSON/AST imports remain Python 3.8+.
    tomllib = None
import uuid

MAX_FILE_BYTES = 65536
MAX_TOTAL_BYTES = 1048576
MAX_FILES = 64
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}
TOOLS = ("repo_read", "repo_search", "repo_patch", "repo_validate", "repo_status")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative(name):
    if not isinstance(name, str) or not name or len(name) > 240:
        raise ValueError("invalid registered relative path")
    parts = name.split("/")
    if (PurePosixPath(name).is_absolute() or len(parts) > 16 or "\\" in name or ":" in name
            or any(not p or p in {".", ".."} or p.startswith(".") or p[-1] in " ."
                   or any(ord(c) < 32 or c in '<>\"|?*' for c in p)
                   or p.split(".")[0].upper() in _RESERVED for p in parts)):
        raise ValueError("unsafe registered relative path")
    return parts


def _bounded(value, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    if depth > 48 or count[0] > 10000:
        raise ValueError("structured artifact exceeds complexity limit")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("structured keys must be strings")
            _bounded(item, depth + 1, count)
    elif isinstance(value, list):
        for item in value:
            _bounded(item, depth + 1, count)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("artifact must contain JSON-compatible values")
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("non-finite artifact number")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def normalize(kind, text):
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("artifact exceeds size limit")
    if kind == "text":
        return text
    if kind in {"json", "file_hash_manifest"}:
        value = json.loads(text, object_pairs_hook=_pairs,
                           parse_constant=lambda unused: (_ for _ in ()).throw(ValueError("non-finite JSON")))
        return _bounded(value)
    if kind == "toml":
        if tomllib is None:
            raise ValueError("TOML static tool profile requires Python 3.11+")
        return _bounded(tomllib.loads(text))
    if kind == "python_ast":
        tree = ast.parse(text)
        if sum(1 for unused in ast.walk(tree)) > 10000:
            raise ValueError("Python AST exceeds complexity limit")
        return ast.dump(tree, annotate_fields=True, include_attributes=False)
    raise ValueError("unknown fixed-suite check kind")


def validate_task(task):
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    for key in ("id", "family", "prompt"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            raise ValueError("task requires " + key)
    files, writable, checks = task.get("initial_files"), task.get("writable_files"), task.get("checks")
    if not isinstance(files, dict) or not 0 < len(files) <= MAX_FILES:
        raise ValueError("task requires bounded initial_files")
    if not isinstance(writable, list) or not writable or len(writable) != len(set(writable)):
        raise ValueError("task requires distinct writable_files")
    if not isinstance(checks, list) or not checks or len(checks) > MAX_FILES:
        raise ValueError("nonempty fixed positive checks are required")
    names = set(files) | set(writable)
    if len(names) > MAX_FILES or len({name.casefold() for name in names}) != len(names):
        raise ValueError("file namespace is ambiguous or too large")
    for name in names:
        relative(name)
    total = 0
    for text in files.values():
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError("initial_files must contain bounded UTF-8 text")
        total += len(text.encode("utf-8"))
    if total > MAX_TOTAL_BYTES:
        raise ValueError("initial repository exceeds size limit")
    checked = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"path", "kind", "expected"}:
            raise ValueError("fixed check requires path, kind, expected only")
        if check["path"] not in writable or check["path"] in checked:
            raise ValueError("each checked path must be distinct and writable")
        checked.add(check["path"])
        expected = check["expected"]
        if check["kind"] in {"text", "python_ast"}:
            if not isinstance(expected, str):
                raise ValueError("text/AST expected value must be source text")
            normalize(check["kind"], expected)
        elif check["kind"] == "file_hash_manifest":
            if (not isinstance(expected, dict) or set(expected) != {"sources", "claims"}
                    or not isinstance(expected["sources"], list) or not expected["sources"]
                    or any(not isinstance(name, str) for name in expected["sources"])
                    or len(set(expected["sources"])) != len(expected["sources"])
                    or not set(expected["sources"]) <= names or check["path"] in expected["sources"]
                    or not isinstance(expected["claims"], dict)):
                raise ValueError("file hash manifest requires distinct registered sources and fixed claims")
            _bounded(expected)
            if len(canonical(expected)) > MAX_FILE_BYTES:
                raise ValueError("expected manifest exceeds size limit")
        elif check["kind"] in {"json", "toml"}:
            _bounded(expected)
            if len(canonical(expected)) > MAX_FILE_BYTES:
                raise ValueError("expected artifact exceeds size limit")
        else:
            raise ValueError("unknown fixed check kind")
    if checked != set(writable):
        raise ValueError("every writable path requires a positive fixed check")
    if "required_read_paths" in task:
        paths = task["required_read_paths"]
        if (not isinstance(paths, list) or not paths or len(paths) > MAX_FILES
                or any(not isinstance(name, str) for name in paths)
                or len(set(paths)) != len(paths) or not set(paths) <= set(files)):
            raise ValueError("required reads must name distinct initial repository files")
    required = task.get("required_tools", ["repo_read", "repo_patch", "repo_validate", "repo_status"])
    if not isinstance(required, list) or not set(required) <= set(TOOLS):
        raise ValueError("unknown required tool")
    # These establish actual read/edit/validation/Git execution even if omitted.
    if not {"repo_read", "repo_patch", "repo_validate", "repo_status"} <= set(required):
        raise ValueError("mandatory real tool evidence cannot be disabled")
    return task


def clean_git_environment():
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
                   if key in os.environ}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_CONFIG_SYSTEM=os.devnull, GIT_ATTR_NOSYSTEM="1",
                       GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    return environment


def git_command(binary, root, *arguments):
    return subprocess.run([str(binary), "--no-optional-locks", "-c", "core.fsmonitor=false",
                           "-c", "core.hooksPath=/dev/null", "-c", "core.autocrlf=false",
                           *arguments], cwd=root, env=clean_git_environment(),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=10, check=False)


class RepoBroker:
    def __init__(self, root, task, git_binary, *, audit_file=None, max_calls=32, deadline=None):
        self.root = Path(root).absolute()
        self.task = validate_task(task)
        self.git_binary = Path(git_binary)
        self.audit_file = Path(audit_file) if audit_file else None
        self.max_calls, self.deadline = max_calls, deadline
        self.events = []
        self.terminal_result = None
        if type(max_calls) is not int or not 4 <= max_calls <= 128:
            raise ValueError("tool call cap must be in [4,128]")
        if self.audit_file and self.audit_file.exists():
            raise ValueError("broker audit already exists; no second tool process")
        self.snapshot()

    def path(self, name):
        parts = relative(name)
        if name not in set(self.task["initial_files"]) | set(self.task["writable_files"]):
            raise ValueError("path is outside the registered tool scope")
        current = self.root
        # Reject symlinks and Windows junction/reparse points, including root.
        for part in [None] + parts:
            current = current if part is None else current / part
            if current.exists() or current.is_symlink():
                info = current.lstat()
                if (stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) or 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
                    raise ValueError("symlink/reparse paths are forbidden")
        try:
            current.resolve().relative_to(self.root.resolve())
        except ValueError:
            raise ValueError("path escaped registered repository")
        return current

    def snapshot(self):
        result, total = {}, 0
        for name in set(self.task["initial_files"]) | set(self.task["writable_files"]):
            path = self.path(name)
            if path.exists():
                if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES or path.stat().st_nlink != 1:
                    raise ValueError("registered files must be bounded regular non-hardlinked files")
                raw = path.read_bytes()
                raw.decode("utf-8")
                total += len(raw)
                result[name] = sha(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("repository exceeds byte limit")
        actual = set()
        for directory, subdirs, filenames in os.walk(self.root, followlinks=False):
            if Path(directory) == self.root and ".git" in subdirs:
                subdirs.remove(".git")
            for name in subdirs + filenames:
                child = Path(directory) / name
                info = child.lstat()
                if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) or 0) & 1024:
                    raise ValueError("unregistered reparse path")
            actual.update((Path(directory) / name).relative_to(self.root).as_posix() for name in filenames)
        if actual != set(result) or not set(self.task["initial_files"]) <= actual:
            raise ValueError("unregistered, missing, or deleted repository file")
        return dict(sorted(result.items()))

    def validate(self):
        failures, passed = [], 0
        try:
            files = self.snapshot()
            for name, original in self.task["initial_files"].items():
                if name not in self.task["writable_files"] and files[name] != sha(original.encode("utf-8")):
                    failures.append("protected-file-changed:" + name)
            for check in self.task["checks"]:
                try:
                    value = normalize(check["kind"], self.path(check["path"]).read_text(encoding="utf-8"))
                    expected = (normalize(check["kind"], check["expected"])
                                if check["kind"] in {"text", "python_ast"} else check["expected"])
                    if check["kind"] == "file_hash_manifest":
                        sources = expected["sources"]
                        if any(name not in files for name in sources):
                            raise ValueError("current manifest source is missing")
                        expected = {"source_sha256": {name: files[name] for name in sources},
                                    "claims": expected["claims"]}
                    if canonical(value) != canonical(expected):
                        raise ValueError("positive contract mismatch")
                    passed += 1
                except (OSError, ValueError, SyntaxError, RecursionError, MemoryError) as error:
                    failures.append("contract-failed:" + check["path"] + ":" + type(error).__name__)
        except (OSError, ValueError, UnicodeError) as error:
            failures.append("scope-invalid:" + type(error).__name__)
        return {"ok": not failures, "suite": "registered-static-contracts-v1",
                "checks_passed": passed, "checks_total": len(self.task["checks"]), "failures": failures}

    def read_evidence_failures(self, events):
        """Task-specific whole-file observations must precede the first edit.

        This optional contract belongs only to newly registered recovery tasks.
        Tool metadata, status, hash manifests and later reads cannot stand in
        for successful reads of the actual initial clue bytes.
        """
        required = set(self.task.get("required_read_paths", []))
        seen = set()
        for event in events:
            result = event.get("result", {})
            if not isinstance(result, dict) or result.get("ok") is not True:
                continue
            if event.get("tool") == "repo_patch":
                break
            if event.get("tool") != "repo_read":
                continue
            arguments, files = event.get("arguments", {}), result.get("files", {})
            if not isinstance(arguments, dict) or not isinstance(files, dict):
                continue
            paths = arguments.get("paths", [])
            if not isinstance(paths, list):
                continue
            for name in required.intersection(path for path in paths if isinstance(path, str)):
                initial = self.task["initial_files"][name]
                if files.get(name) == {"text": initial, "sha256": sha(initial.encode("utf-8"))}:
                    seen.add(name)
        missing = required - seen
        return (["required-recovery-reads-before-edit-missing:" + ",".join(sorted(missing))]
                if missing else [])

    def _patch_readback(self, name, expected):
        """Bind success metadata to safely observed disk bytes after the batch."""
        path = self.path(name)
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_FILE_BYTES:
            raise ValueError("patch readback requires a bounded regular non-hardlinked file")
        descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                raise ValueError("patch readback identity changed while opening")
            observed = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
        final = self.path(name).lstat()
        identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink)
        if (identity(opened) != identity(after) or identity(after) != identity(final)
                or observed != expected):
            raise ValueError("patch readback bytes or identity differ from the applied write")
        return {"sha256": sha(observed), "byte_size": len(observed)}

    def _execute(self, tool, arguments):
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if tool == "repo_read":
            if set(arguments) != {"paths"} or not isinstance(arguments["paths"], list) or not 1 <= len(arguments["paths"]) <= MAX_FILES:
                raise ValueError("repo_read requires bounded paths array")
            files = {}
            for name in arguments["paths"]:
                path = self.path(name)
                raw = path.read_bytes()
                if len(raw) > MAX_FILE_BYTES:
                    raise ValueError("read exceeds file limit")
                files[name] = {"text": raw.decode("utf-8"), "sha256": sha(raw)}
            return {"ok": True, "files": files}
        if tool == "repo_search":
            if set(arguments) != {"needle"} or not isinstance(arguments["needle"], str) or not 1 <= len(arguments["needle"]) <= 256:
                raise ValueError("repo_search requires a bounded literal needle")
            matches = []
            for name in self.snapshot():
                for number, line in enumerate(self.path(name).read_text(encoding="utf-8").splitlines(), 1):
                    if arguments["needle"] in line:
                        matches.append({"path": name, "line": number, "text": line[:512]})
                        if len(matches) >= 100:
                            return {"ok": True, "matches": matches, "truncated": True}
            return {"ok": True, "matches": matches, "truncated": False}
        if tool == "repo_patch":
            operations = arguments.get("operations")
            if set(arguments) != {"operations"} or not isinstance(operations, list) or not 1 <= len(operations) <= MAX_FILES:
                raise ValueError("repo_patch requires bounded operations")
            staged, names = [], set()
            resulting_bytes = sum(self.path(name).stat().st_size for name in self.snapshot())
            for operation in operations:
                if not isinstance(operation, dict) or set(operation) != {"path", "old_sha256", "new_text"}:
                    raise ValueError("patch requires path, old_sha256, new_text")
                name, text = operation["path"], operation["new_text"]
                if name not in self.task["writable_files"] or name in names or not isinstance(text, str):
                    raise ValueError("patch path is protected or duplicated")
                names.add(name)
                path = self.path(name)
                old = path.read_bytes() if path.exists() else None
                if operation["old_sha256"] != (sha(old) if old is not None else None):
                    raise ValueError("patch precondition hash mismatch")
                raw = text.encode("utf-8")
                if not raw or len(raw) > MAX_FILE_BYTES or raw == old:
                    raise ValueError("patch must make a nonempty bounded change")
                resulting_bytes += len(raw) - (len(old) if old is not None else 0)
                staged.append((name, path, raw))
            if resulting_bytes > MAX_TOTAL_BYTES:
                raise ValueError("patch exceeds total repository byte limit")
            written, files = [], {}
            try:
                for name, path, raw in staged:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
                    try:
                        with temporary.open("xb") as stream:
                            stream.write(raw)
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.replace(temporary, path)
                        written.append(name)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
                # A later batch write must not invalidate an earlier success receipt.
                for name, path, raw in staged:
                    files[name] = self._patch_readback(name, raw)
            except (OSError, ValueError, UnicodeError) as error:
                return {"ok": False, "changed": sorted(written), "files": dict(sorted(files.items())),
                        "write_state": "partial-or-unverified",
                        "error": type(error).__name__ + ": " + str(error)[:240]}
            return {"ok": True, "changed": sorted(names), "files": dict(sorted(files.items()))}
        if tool == "repo_validate" and not arguments:
            return self.validate()
        if tool == "repo_status" and not arguments:
            result = git_command(self.git_binary, self.root, "status", "--porcelain=v1", "--untracked-files=all")
            if result.returncode:
                raise ValueError("fixed Git status failed")
            return {"ok": True, "argv_profile": "git-status-porcelain-v1",
                    "exit_code": result.returncode, "stdout": result.stdout.decode("utf-8"),
                    "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr)}
        raise ValueError("unregistered tool or invalid arguments")

    def call(self, tool, arguments):
        if self.terminal_result is not None:
            return self.terminal_result
        started = time.perf_counter()
        try:
            if len(self.events) >= self.max_calls or self.deadline is not None and time.time() > self.deadline:
                self.terminal_result = {"ok": False, "error": "tool/time budget exhausted; broker closed"}
                raise ValueError("tool/time budget exhausted")
            self.snapshot()
            result = self._execute(tool, arguments)
        except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired, RecursionError) as error:
            result = {"ok": False, "error": type(error).__name__ + ": " + str(error)[:240]}
        try:
            state = sha(canonical(self.snapshot()))
        except (OSError, ValueError, UnicodeError):
            state = None
        event = {"sequence": len(self.events) + 1, "tool": tool, "arguments": arguments,
                 "arguments_sha256": sha(canonical(arguments)),
                 "result": result, "result_sha256": sha(canonical(result)), "state_sha256": state,
                 "wall_seconds": time.perf_counter() - started}
        self.events.append(event)
        if self.audit_file:
            with self.audit_file.open("ab") as stream:
                stream.write(canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
        return result


def tool_definitions():
    def definition(name, description, properties, required):
        return {"name": name, "description": description,
                "annotations": {"readOnlyHint": name != "repo_patch",
                                "destructiveHint": name == "repo_patch",
                                "idempotentHint": name != "repo_patch", "openWorldHint": False},
                "inputSchema": {"type": "object", "properties": properties, "required": required,
                                "additionalProperties": False}}
    return [
        definition("repo_read", "Read registered repository text files in one batch; returns text and SHA256.",
                   {"paths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": MAX_FILES}}, ["paths"]),
        definition("repo_search", "Search registered text files for a literal string.", {"needle": {"type": "string"}}, ["needle"]),
        definition("repo_patch", "Replace registered writable files using exact prior SHA256; batch independent edits. Returns safely read-back SHA256 and byte size per changed file.",
                   {"operations": {"type": "array", "items": {"type": "object", "properties": {
                       "path": {"type": "string"}, "old_sha256": {"type": ["string", "null"]},
                       "new_text": {"type": "string"}}, "required": ["path", "old_sha256", "new_text"],
                       "additionalProperties": False}}}, ["operations"]),
        definition("repo_validate", "Run the frozen static contract suite. Parses data/AST; never executes application code.", {}, []),
        definition("repo_status", "Run the fixed Git porcelain status command in this repository.", {}, []),
    ]


def serve(spec_file):
    spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    broker = RepoBroker(spec["workspace"], spec["task"], spec["git_binary"],
                        audit_file=spec["audit_file"], max_calls=spec["max_tool_calls"], deadline=spec["deadline"])
    while True:
        raw = sys.stdin.buffer.readline(MAX_TOTAL_BYTES + 1)
        if not raw:
            break
        if len(raw) > MAX_TOTAL_BYTES:
            raise ValueError("MCP message exceeds size limit")
        request = json.loads(raw)
        method, identifier = request.get("method"), request.get("id")
        if identifier is None:
            continue
        response = {"jsonrpc": "2.0", "id": identifier}
        if method == "initialize":
            response["result"] = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                                  "serverInfo": {"name": "upg-bounded-repository", "version": "1"}}
        elif method == "ping":
            response["result"] = {}
        elif method == "tools/list":
            response["result"] = {"tools": tool_definitions()}
        elif method == "tools/call":
            params = request.get("params", {})
            result = broker.call(params.get("name"), params.get("arguments", {}))
            response["result"] = {"content": [{"type": "text", "text": canonical(result).decode("utf-8")}],
                                  "isError": not result["ok"]}
        else:
            response["error"] = {"code": -32601, "message": "method not found"}
        sys.stdout.buffer.write(canonical(response) + b"\n")
        sys.stdout.buffer.flush()
        if broker.terminal_result is not None:
            break


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: tool_broker.py <owner-created-private-spec.json>")
    serve(sys.argv[1])
