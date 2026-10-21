#!/usr/bin/env python3
"""Bounded, read-only project fact recovery; the current handoff stays canonical."""
from __future__ import annotations

import hashlib
import ast
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import threading

MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, MAX_DEPTH = 64, 1024 * 1024, 8 * 1024 * 1024, 16
MAX_STATE_BYTES = 256 * 1024
RECOVERY_SIGNALS = {"interrupted", "resume", "recovery", "agent_change", "handoff-missing",
                    "legacy-unknown", "stale-evidence", "contradiction", "no-progress",
                    "opaque-artifact", "behavior-mismatch"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(value): raise ValueError("nonfinite JSON constant: " + value)
    def finite(value):
        number = float(value)
        if not math.isfinite(number): raise ValueError("nonfinite JSON number")
        return number
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant, parse_float=finite)
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds bounded parser depth") from error


def safe_path(root, relative):
    """Reuse the project's explicit-path broker boundary without scanning a tree."""
    if not isinstance(relative, str) or len(relative) > 1024:
        raise ValueError("expected a bounded project-relative file path")
    parts = relative.split("/")
    if (not relative or len(parts) > MAX_DEPTH or PurePosixPath(relative).is_absolute()
            or PureWindowsPath(relative).drive or PureWindowsPath(relative).root
            or "\\" in relative or ":" in relative or any(ord(c) < 32 for c in relative)
            or any(p in {"", ".", ".."} or p.endswith((".", " ")) for p in parts)):
        raise ValueError("unsafe project-relative path")
    reserved = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}
    if any(p.split(".", 1)[0].lower() in reserved for p in parts):
        raise ValueError("reserved filesystem path")
    if any(p.lower().startswith(".env") or p.lower().endswith((".pem", ".key", ".p12", ".pfx"))
           or p.lower().startswith(("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"))
           or p.lower() in {".git", ".aws", ".ssh", ".codex", ".docker", ".kube", ".gnupg",
           ".git-credentials", ".pgpass", "pip.conf", ".yarnrc.yml", ".htpasswd",
           ".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json", "auth.json"} for p in parts):
        raise ValueError("credential or VCS internals are outside fact recovery file scope")
    root = Path(root).absolute()
    for parent in root.parents:
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("project root has a symlink/reparse ancestor")
    current = root
    for part in [None] + parts:
        if part is not None: current = current / part
        try: info = current.lstat()
        except FileNotFoundError: continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("symlink/reparse paths are outside fact recovery scope")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError("hardlinked files are outside fact recovery scope")
    try: current.resolve().relative_to(root.resolve())
    except ValueError: raise ValueError("path escaped project root")
    return current


class Reader:
    def __init__(self, root, max_files=None):
        self.root, self.cache, self.total_bytes, self.attempted = Path(root).absolute(), {}, 0, set()
        self.identities = {}
        self.max_files = MAX_FILES if max_files is None else max_files
        self.raced_paths = set()

    def read(self, name, limit=MAX_FILE_BYTES):
        if name in self.cache:
            raw = self.cache[name]
            if len(raw) > limit: raise ValueError("file exceeds this read limit")
            return raw
        if name in self.attempted: raise ValueError("prior read unavailable; no automatic retry")
        if len(self.attempted) >= self.max_files: raise ValueError("file read budget exhausted")
        self.attempted.add(name)
        path = safe_path(self.root, name)
        before = path.stat()
        if not stat.S_ISREG(before.st_mode): raise ValueError("scope requires explicit regular files, not directories")
        if before.st_size > limit: raise ValueError("file exceeds bounded read limit")
        if self.total_bytes + before.st_size > MAX_TOTAL_BYTES: raise ValueError("total byte budget exhausted")
        # O_NOFOLLOW plus descriptor identity blocks final-component link swaps.
        descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                raise ValueError("scope file identity changed while opening")
            raw = stream.read(min(limit + 1, MAX_TOTAL_BYTES - self.total_bytes))
            self.total_bytes += len(raw)
            after = os.fstat(stream.fileno())
        final = safe_path(self.root, name).stat()
        if (len(raw) > limit or len(raw) != after.st_size
                or (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) !=
                   (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
            raise ValueError("scope file changed or exceeded the read budget")
        self.cache[name] = raw
        self.identities[name] = (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_mode)
        return raw


def declarations(cache, scope):
    """Recognize bounded declarations, never imports, scripts or application behavior."""
    observations, gaps = [], []
    def add(path, kind, name):
        if len(observations) >= 64: raise ValueError("static declaration budget exhausted")
        if not isinstance(name, str) or len(name) > 128: raise ValueError("declaration name exceeds bounded limit")
        row = {"path": path, "kind": kind, "name": name, "basis": "static-declaration-only"}
        if row not in observations: observations.append(row)
    for path in scope:
        raw = cache.get(path)
        if raw is None: continue
        try:
            if path.endswith(".py"):
                if len(raw) > 128 * 1024: raise ValueError("Python declaration parse budget exhausted")
                tree = ast.parse(raw)
                for count, node in enumerate(ast.walk(tree)):
                    if count >= 512: raise ValueError("Python declaration node budget exhausted")
                    if isinstance(node, ast.Import):
                        for alias in node.names: add(path, "dependency", alias.name)
                    if isinstance(node, ast.ImportFrom): add(path, "dependency", "." * node.level + (node.module or ""))
                    if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                        test = node.test
                        if (isinstance(test.left, ast.Name) and test.left.id == "__name__" and len(test.ops) == 1
                                and isinstance(test.ops[0], ast.Eq) and len(test.comparators) == 1
                                and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__"):
                            add(path, "entry", "__main__ guard")
            elif PurePosixPath(path).name == "package.json":
                data = strict_json(raw)
                if not isinstance(data, dict): raise ValueError("package manifest is not an object")
                for key in ("scripts", "dependencies", "devDependencies", "peerDependencies"):
                    entries = data.get(key, {})
                    if not isinstance(entries, dict): raise ValueError("manifest declarations must be objects")
                    for name in sorted(entries): add(path, "entry" if key == "scripts" else "dependency", name)
        except (ValueError, SyntaxError, UnicodeError, RecursionError, MemoryError):
            gaps.append("%s: static declaration analysis partial or unavailable; dynamic behavior remains unknown" % path)
    return observations, gaps


def recovery_errors(view):
    """Check saved-state internal consistency; this does not establish evidence truth."""
    errors, scope, source = [], view["scope"], view["source_state"]
    files = source["files"]
    if [row["path"] for row in files] != scope or source["scope_sha256"] != digest(files):
        errors.append("recovery source identity does not bind the exact ordered scope")
    hashes = {row["path"]: row["sha256"] for row in files if row["status"] == "observed"}
    if any((row["sha256"] is None) != (row["status"] == "unavailable") for row in files):
        errors.append("recovery file status/hash mismatch")
    if len({item["id"] for item in view["evidence"]}) != len(view["evidence"]):
        errors.append("duplicate recovery evidence id")
    if set(source["git"]["changed_paths"]) - set(scope): errors.append("Git changes exceed recovery scope")
    if any(row["path"] not in scope for row in view["static_observations"]):
        errors.append("static observations exceed recovery scope")
    for ref in view["carry_forward_refs"]:
        if hashes.get(ref["path"]) != ref["sha256"]: errors.append("carried reference does not match observed scope bytes")
    for check in view["reference_checks"]:
        actual = hashes.get(check["path"])
        status = "out-of-scope" if check["path"] not in scope else "unavailable" if actual is None else "match" if actual == check["expected_sha256"] else "changed"
        if check["actual_sha256"] != actual or check["status"] != status: errors.append("reference check contradicts observed source identity")
    if [row["id"] for row in view["evidence_checks"]] != [row["id"] for row in view["evidence"]]:
        errors.append("evidence checks do not bind the exact evidence list")
    else:
        for evidence, assessment in zip(view["evidence"], view["evidence_checks"]):
            refs = [evidence["reference"]] + evidence.get("inputs", []) + evidence.get("configuration", [])
            if evidence.get("environment") is not None: refs.append(evidence["environment"])
            fixed = all(hashes.get(ref["path"]) == ref["sha256"] for ref in refs)
            eligible = fixed and bool(evidence.get("coverage"))
            if evidence["kind"] == "dynamic":
                git = source["git"]
                eligible = (eligible and bool(evidence.get("inputs")) and bool(evidence.get("configuration"))
                            and evidence.get("environment") is not None and git["available"]
                            and evidence.get("tested_revision") == git["revision"] and not git["changed_paths"])
            if (assessment["fixity"] != ("match" if fixed else "unverified") or
                    assessment["validity"] != ("eligible-for-review" if eligible else "unverified")):
                errors.append("evidence assessment contradicts its bound references/validity context")
    return errors


def _bounded_git_query(command, *, output_limit, timeout, **options):
    """Collect fixed Git query output with a bound on each buffered stream."""
    process = subprocess.Popen(command, **options)
    outputs, failures = {}, []
    def read_stream(name, stream):
        try:
            # The reading thread owns this buffered stream. Another thread's
            # close() can wait indefinitely for its read lock when a descendant
            # inherited the pipe, even after the direct process was terminated.
            with stream:
                raw = stream.read(output_limit + 1)
                if len(raw) > output_limit:
                    failures.append("Git metadata exceeds bounded output limit")
                    process.kill()
                outputs[name] = raw
        except OSError as exc:
            failures.append(str(exc))
    threads = [threading.Thread(target=read_stream, args=(name, stream), daemon=True)
               for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))]
    try:
        for thread in threads: thread.start()
        process.wait(timeout=timeout)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=timeout)
        for thread in threads:
            if thread.ident is not None: thread.join(timeout=timeout)
        # A thread that started must close its own stream, including after a
        # caller timeout. Only unstarted readers have no read lock to contend.
        for thread,stream in zip(threads,(process.stdout,process.stderr)):
            if thread.ident is None: stream.close()
    if failures or any(thread.is_alive() for thread in threads):
        raise ValueError("Git metadata exceeds bounded output limit or read failed")
    return subprocess.CompletedProcess(command, process.returncode, outputs["stdout"], outputs["stderr"])


def git_state(root, scope, binary, *, reader=None):
    """Compare scoped raw bytes with index/HEAD without worktree conversions.

    Git status and ls-files --modified can execute local clean filters. Only
    metadata queries and cached object comparison are permitted here. Active
    attributes make content semantics unknown, never a false clean claim.
    """
    empty = {"available": False, "root": None, "revision": None, "branch": None, "changed_paths": [],
             "coverage": "explicit-scope-only"}
    if binary is None: return empty, ["Git identity unavailable: no registered Git binary supplied"]
    if not Path(binary).is_absolute() or not Path(binary).is_file():
        raise ValueError("--git-binary requires an existing absolute registered executable")
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_ATTR_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    prefix = [str(binary), "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
              "-c", "core.untrackedCache=false", "-c", "core.autocrlf=false", "-c", "core.pager=cat",
              "-c", "core.attributesFile=" + os.devnull]
    def run(arguments):
        # Each allowed path may appear six times in check-attr output. Bound
        # both streams while reading rather than after communicate buffers all.
        limit = max(65536, 16 * sum(len(os.fsencode(name)) + 256 for name in scope))
        result = _bounded_git_query(prefix + arguments, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, output_limit=limit)
        if result.returncode: raise ValueError("fixed read-only Git query unavailable")
        return result.stdout
    try:
        root = Path(root).absolute()
        if (not isinstance(scope, list) or not 1 <= len(scope) <= MAX_FILES
                or len(set(scope)) != len(scope)):
            raise ValueError("Git scope requires bounded distinct paths")
        for name in scope: safe_path(root, name)
        if reader is None: reader = Reader(root)
        if not isinstance(reader, Reader) or reader.root.resolve() != root.resolve():
            raise ValueError("Git comparison requires the same bounded scope reader")
        git_root = Path(run(["rev-parse", "--show-toplevel"]).decode("utf-8").strip()).resolve()
        revision = run(["rev-parse", "--verify", "HEAD"]).decode("ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision): raise ValueError("Git revision malformed")
        branch = run(["rev-parse", "--abbrev-ref", "HEAD"]).decode("utf-8").strip()
        if len(branch) > 256: raise ValueError("Git branch exceeds metadata limit")
        attributes = ("filter", "text", "eol", "working-tree-encoding", "ident", "crlf")
        # check-attr takes literal pathnames, not status-style pathspec magic.
        raw_attributes = run(["check-attr", "-z"] + list(attributes) + ["--"] + scope).split(b"\0")
        if not raw_attributes or raw_attributes[-1] != b"" or (len(raw_attributes) - 1) % 3:
            raise ValueError("Git attribute metadata malformed")
        seen_attributes = set()
        for offset in range(0, len(raw_attributes) - 1, 3):
            name, attribute, value = (os.fsdecode(item) for item in raw_attributes[offset:offset + 3])
            key = (name, attribute)
            if name not in scope or attribute not in attributes or key in seen_attributes:
                raise ValueError("Git attribute metadata exceeded exact scope")
            seen_attributes.add(key)
            if value not in {"unspecified", "unset"}:
                return empty, ["Git content state unknown: active filter or normalization attributes; no worktree conversion executed"]
        if len(seen_attributes) != len(scope) * len(attributes):
            raise ValueError("Git attribute metadata is incomplete")
        def scoped_name(raw_name):
            path = (git_root / os.fsdecode(raw_name)).resolve()
            try: name = path.relative_to(root.resolve()).as_posix()
            except ValueError: raise ValueError("Git metadata escaped project root")
            if name not in scope: raise ValueError("Git metadata exceeded explicit path scope")
            return name
        pathspecs = [":(literal)" + name for name in scope]
        index, seen_index, changed = {}, set(), set()
        for record in run(["ls-files", "--stage", "--full-name", "-z", "--"] + pathspecs).split(b"\0"):
            if not record: continue
            metadata, separator, path = record.partition(b"\t")
            fields = metadata.split(b" ")
            if (not separator or len(fields) != 3 or fields[0] not in {b"100644", b"100755", b"120000", b"160000"}
                    or not re.fullmatch(b"[0-9a-f]{" + str(len(revision)).encode() + b"}", fields[1])
                    or fields[2] not in {b"0", b"1", b"2", b"3"}):
                raise ValueError("Git index metadata malformed")
            name = scoped_name(path); key = (name, fields[2])
            if key in seen_index: raise ValueError("Git index metadata duplicated")
            seen_index.add(key)
            if fields[2] != b"0" or fields[0] not in {b"100644", b"100755"}:
                changed.add(name)
            else: index[name] = (fields[0], fields[1].decode("ascii"))
        cached = run(["diff-index", "--cached", "--name-only", "-z", "--no-ext-diff", "--no-textconv",
                      "--ignore-submodules=all", "--no-renames", "--no-relative", "--ita-visible-in-index", "HEAD", "--"] + pathspecs)
        changed.update(scoped_name(path) for path in cached.split(b"\0") if path)
        for name in scope:
            if name not in index:
                changed.add(name)  # Includes untracked, ignored and unmerged paths.
                continue
            try:
                raw = reader.read(name)
                current = safe_path(root, name).stat()
                identity = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_mode)
                if identity != reader.identities[name]:
                    raise ValueError("scoped file changed after bounded observation")
            except (OSError, ValueError):
                reader.raced_paths.add(name)
                changed.add(name)
                continue
            algorithm = "sha1" if len(revision) == 40 else "sha256"
            oid = hashlib.new(algorithm, b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if oid != index[name][1]: changed.add(name)
            if os.name != "nt" and bool(current.st_mode & stat.S_IXUSR) != (index[name][0] == b"100755"):
                changed.add(name)
        return dict(empty, available=True, root=str(git_root), revision=revision, branch=branch,
                    changed_paths=sorted(set(changed))), []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return empty, ["Git identity/status unavailable; equivalent source state remains unverified"]


def recovery_plan(signals):
    active = sorted(set(signals) & RECOVERY_SIGNALS)
    if not active: return None
    mode = "specialist-needed" if set(active) & {"opaque-artifact", "behavior-mismatch"} else "static"
    return {"mode": mode, "triggers": active,
            "steps": ["verify task-scoped source, entry and dependency identities", "check referenced evidence and invalidation conditions",
                      "retain hypotheses/conflicts; record decision delta and carried references in the current handoff"],
            "constraints": ["explicit paths and bounded reads only", "hash equality is fixity, not semantic proof",
                            "no project code execution or tool installation", "partial/unknown coverage never proves completion"]}


def recover(root, scope, *, handoff=None, git_binary=None):
    from state_tool import load, schema_root, validate_node, resolve_validation_ref
    if not isinstance(scope, list) or not 1 <= len(scope) <= MAX_FILES or len(set(scope)) != len(scope):
        raise ValueError("recover requires 1..64 unique explicit scope files")
    if os.name == "nt" and len({name.casefold() for name in scope}) != len(scope):
        raise ValueError("scope contains case-insensitive path aliases")
    root = Path(root).absolute(); reader = Reader(root, MAX_FILES + (handoff is not None))
    if not root.is_dir(): raise ValueError("recover requires an existing project root")
    for name in scope: safe_path(root, name)
    previous, gaps = {}, []
    if handoff is not None:
        try:
            previous = strict_json(reader.read(handoff, MAX_STATE_BYTES))
            errors = validate_node(previous, load(schema_root() / "handoff.schema.json"))
            if errors: raise ValueError("invalid handoff schema")
            if "recovery" in previous and recovery_errors(previous["recovery"]):
                raise ValueError("inconsistent handoff recovery identities")
        except (OSError, ValueError): gaps.append("handoff unavailable or invalid; prior intent remains unknown"); previous = {}
    else: gaps.append("handoff not supplied; prior intent remains unknown")
    old = previous.get("recovery", {})
    files = []
    for name in scope:
        try:
            raw = reader.read(name)
            files.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "status": "observed"})
        except (OSError, ValueError) as error:
            files.append({"path": name, "sha256": None, "status": "unavailable"})
            gaps.append("%s: %s" % (name, str(error)))
    git, git_gaps = git_state(root, scope, git_binary, reader=reader); gaps.extend(git_gaps)
    for item in files:
        if item["path"] in reader.raced_paths:
            item.update(sha256=None, status="unavailable")
            reader.cache.pop(item["path"], None)
            gaps.append("%s: scoped bytes changed after observation; prior evidence cannot be inherited" % item["path"])
    source = {"git": git, "files": files, "scope_sha256": digest(files)}
    observations, static_gaps = declarations(reader.cache, scope); gaps.extend(static_gaps)
    current_hashes = {item["path"]: item["sha256"] for item in files if item["status"] == "observed"}
    checks, carried = [], []
    def check_ref(ref):
        actual = current_hashes.get(ref["path"])
        status = "out-of-scope" if ref["path"] not in scope else "unavailable" if actual is None else "match" if actual == ref["sha256"] else "changed"
        result = {"path": ref["path"], "expected_sha256": ref["sha256"], "actual_sha256": actual, "status": status}
        if result not in checks: checks.append(result)
        if status == "match" and ref not in carried:
            if len(carried) < 64: carried.append(ref)
            else: gaps.append("carried reference budget exhausted; remaining references require explicit review")
        return status == "match"
    evidence = old.get("evidence", [])
    evidence_checks = []
    for ref in old.get("carry_forward_refs", []): check_ref(ref)
    for item in evidence:
        refs = [item["reference"]] + item.get("inputs", []) + item.get("configuration", [])
        if item.get("environment") is not None: refs.append(item["environment"])
        fixed = all([check_ref(ref) for ref in refs])
        validity = fixed and bool(item.get("coverage"))
        if item["kind"] == "dynamic":
            validity = (validity and bool(item.get("inputs")) and bool(item.get("configuration")) and item.get("environment") is not None
                        and git["available"] and item.get("tested_revision") == git["revision"] and not git["changed_paths"])
        evidence_checks.append({"id": item["id"], "fixity": "match" if fixed else "unverified",
                                "validity": "eligible-for-review" if validity else "unverified", "semantic_truth": "unassessed"})
        if not validity: gaps.append("evidence %s needs current input/environment/configuration/coverage verification" % item["id"])
    if "validation_ref" in previous:
        ref = previous["validation_ref"]
        if check_ref({"path": ref["path"], "sha256": ref["sha256"]}):
            try:
                run = resolve_validation_ref(ref, root, source_bytes=reader.cache[ref["path"]])
                if (not git["available"] or run["tested_revision"] != git["revision"] or git["changed_paths"]
                        or run.get("pending_retest") or run.get("later_changes")):
                    gaps.append("canonical validation is historical or pending retest against current scoped state")
                else: gaps.append("canonical validation identity matches; input/environment/configuration validity still needs evidence")
            except (OSError, ValueError): gaps.append("canonical validation reference is unavailable or stale")
        else: gaps.append("canonical validation reference requires scoped reconciliation")
    delta = []
    old_source = old.get("source_state")
    if old_source is not None and old_source != source: delta.append("source identity or scoped worktree changed since the carried handoff")
    if any(item["status"] != "match" for item in checks): delta.append("some carried evidence references cannot be reused without reconciliation")
    attempts = old.get("attempts", [])
    stalled = len(attempts) >= 2 and all(not attempt["progress"] for attempt in attempts[-2:]) and attempts[-1]["method"] == attempts[-2]["method"]
    actions = []
    if stalled: actions.append("Switch analysis method or record a bounded blocker before repeating the same no-progress path.")
    if previous.get("recovery", {}).get("contradictions"): actions.append("Resolve contradictory evidence with a task-scoped independent check; preserve unknown intent.")
    if gaps: actions.append("Resolve the listed scope/evidence gaps before inheriting affected claims or mutating dependent behavior.")
    actions.append("Verify only the task-relevant entry, dependencies and consumers; a missing search hit does not prove safe deletion.")
    actions.append("Choose the smallest justified next action; any dynamic check requires a separately authorized safe execution entrance.")
    if len(gaps) > 64: gaps = gaps[:63] + ["gap display budget exhausted; unresolved coverage remains partial"]
    view = {"schema_version": 1, "scope": scope, "source_state": source, "static_observations": observations, "evidence": evidence,
            "reference_checks": checks, "evidence_checks": evidence_checks, "decision_delta": delta,
            "carry_forward_refs": carried, "hypotheses": old.get("hypotheses", []),
            "contradictions": old.get("contradictions", []), "attempts": attempts,
            "gaps": [gap[:1024] for gap in gaps[:64]], "semantic_completion": "unassessed"}
    errors = validate_node(view, load(schema_root() / "handoff.schema.json")["properties"]["recovery"])
    if not errors: errors = recovery_errors(view)
    if errors: raise ValueError("invalid recovery view: " + "; ".join(errors))
    return {"recovery": view, "next_actions": actions,
            "canonical_state": ".governance/handoff.json", "persistence": "read-only derived view; merge into the current handoff only when authorized",
            "coverage": {"files_read": len(reader.cache), "read_attempts": len(reader.attempted), "bytes_read": reader.total_bytes,
                         "scope_only": True, "project_code_executed": False, "completion_proved": False}}
