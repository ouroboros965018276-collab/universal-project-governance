"""Bounded final-state review receipts; hashes establish fixity, not semantic review."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from project_facts import safe_project_path

MAX_FILES = 512
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def _key(path):
    return os.path.normcase(path)


def capture_sources(root, paths):
    """Observe explicit regular files, their executable bits, and verified absence."""
    if not isinstance(paths, list) or len(paths) > MAX_FILES:
        raise ValueError("completion review file scope exceeds its bounded limit")
    result, seen, total = {}, set(), 0
    for relative in paths:
        path = safe_project_path(root, relative)
        key = _key(relative)
        if key in seen:
            raise ValueError("completion review contains duplicate file paths")
        seen.add(key)
        if ".git" in relative.lower().split("/") or relative.lower() in {".governance/upg.json", ".governance/field-reports.json"}:
            raise ValueError("completion review cannot include VCS internals or its tool-owned bookkeeping")
        try:
            before = path.stat()
        except FileNotFoundError:
            result[relative] = None
            continue
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("completion review path must be a regular file or deleted file")
        if before.st_size > MAX_FILE_BYTES or total + before.st_size > MAX_TOTAL_BYTES:
            raise ValueError("completion review source bytes exceed their bounded limit")
        digest, size = hashlib.sha256(), 0
        descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                raise ValueError("completion review source changed while being read")
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES:
                    raise ValueError("completion review source bytes exceed their bounded limit")
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        observed = safe_project_path(root, relative).stat()
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_mode)
        if identity(before) != identity(after) or identity(after) != identity(observed) or size != after.st_size:
            raise ValueError("completion review source changed while being read")
        total += size
        result[relative] = [digest.hexdigest(), after.st_mode & 0o111]
    return result


def declared_sources(payload):
    """Read the receipt's expected state without claiming it is still current."""
    return {item["path"]: ([item["sha256"], item["executable"]] if item["sha256"] is not None else None)
            for item in payload["completion_review"]["files"]}


def capture_baseline(root, snapshot):
    """Keep only facts needed to exempt preexisting, still-unchanged dirty files."""
    dirty = [path for path in snapshot.get("dirty_paths", []) if not _bookkeeping(path)]
    candidates, total, metadata = [], 0, 0
    for path in dirty[:MAX_FILES]:
        try:
            source = safe_project_path(root, path)
            size = source.stat().st_size if source.exists() else 0
            cost = len(path.encode("utf-8")) * 2 + 180
            if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES or metadata + cost > 16384:
                continue
            candidates.append(path)
            total += size
            metadata += cost
        except (OSError, ValueError):
            # Unreadable or unsafe preexisting files do not gain an exemption.
            continue
    try:
        observed = capture_sources(root, candidates)
        index_states = _index_states(root, candidates)
    except (OSError, ValueError):
        observed, index_states = {}, {}
    return {"head": snapshot.get("head"), "branch": snapshot.get("branch"),
            "dirty_sources": observed, "dirty_index": index_states}


def _bookkeeping(path):
    # Match existing checkpoint infrastructure exclusions. Explicitly declared
    # project state files are still hashed and reviewed by verify_completion.
    return ".governance" in path.lower().split("/")


def _index_states(root, paths):
    from git_checkpoint import _git
    if not paths:
        return {}
    rows = _git(Path(root), ["ls-files", "--stage", "-z", "--"] + paths).stdout.split(b"\0")
    states = {path: None for path in paths}
    for row in rows:
        if row:
            state, path = row.split(b"\t", 1)
            states[path.decode("utf-8", "surrogateescape")] = state.decode("ascii")
    return states


def _observed_git_changes(root, binding, payload):
    from git_checkpoint import _git, _paths, _repo
    active = binding.get("active_workflow", {})
    start = binding.get("git_checkpoint", {}).get("start", {})
    snapshot = start.get("snapshot", {})
    if start.get("workflow_id") != payload["workflow_id"] or not snapshot.get("ok"):
        return None
    if "completion_baseline" not in active and snapshot.get("dirty_paths"):
        # An upgrade cannot reconstruct the original bytes of inherited owner
        # edits. Keep existing Git ownership guards; do not invent attribution.
        return None
    root, _, branch, _, _ = _repo(Path(root))
    if branch != snapshot.get("branch"):
        raise ValueError("completion review Git branch changed since the observed baseline")
    head = snapshot.get("head")
    args = ["diff", "--no-renames", "--name-only", "-z"]
    changed = set(_paths(_git(root, args + ([head] if head is not None else []) + ["--"]).stdout))
    changed.update(_paths(_git(root, ["diff", "--cached", "--no-renames", "--name-only", "-z"]
                              + ([head] if head is not None else []) + ["--"]).stdout))
    if head is None:
        changed.update(_paths(_git(root, ["ls-files", "--cached", "-z"]).stdout))
    changed.update(_paths(_git(root, ["ls-files", "--others", "--exclude-standard", "-z"]).stdout))
    changed = {path for path in changed if not _bookkeeping(path)}
    if len(changed) > MAX_FILES:
        raise ValueError("completion review observed Git scope exceeds its bounded limit")
    baseline = active.get("completion_baseline", {})
    prior = baseline.get("dirty_sources", {}) if baseline.get("head") == head and baseline.get("branch") == branch else {}
    candidates = sorted(set(changed) & set(prior) & set(baseline.get("dirty_index", {})))
    try:
        current = capture_sources(root, candidates)
        current_index = _index_states(root, candidates)
        for path in candidates:
            if current[path] == prior[path] and current_index[path] == baseline["dirty_index"][path]:
                changed.remove(path)
    except (OSError, ValueError):
        pass
    return changed


def recovery_paths(root, binding, payload):
    """Bound the fresh-review obligation after a historical publication drifted."""
    paths = set(payload["changed_files"])
    from git_checkpoint import CheckpointError
    try:
        paths.update(_observed_git_changes(root, binding, payload) or ())
    except (OSError, ValueError, CheckpointError):
        pass
    if len(paths) > MAX_FILES:
        raise ValueError("completion review recovery scope exceeds its bounded limit")
    return sorted(paths)


def recovery_owned_paths(binding, payload):
    """Carry only existing checkpoint ownership across explicit drift recovery."""
    from git_checkpoint import _excluded, _in_scope
    policy = binding.get("git_checkpoint", {})
    start = policy.get("start", {})
    snapshot = start.get("snapshot", {})
    if not policy.get("enabled") or start.get("workflow_id") != payload["workflow_id"] or not snapshot.get("ok"):
        return []
    dirty = {_key(path) for path in snapshot.get("dirty_paths", [])}
    pending = set(policy.get("pending_paths", [])) if policy.get("pending_workflow_id") == payload["workflow_id"] else set()
    return sorted(path for path in payload["changed_files"]
                  if (_key(path) not in dirty or path in pending) and not _excluded(path, policy) and _in_scope(path, policy))


def recovery_git_identity(root, binding, payload):
    """Retain ownership only at the original verified branch and owned HEAD."""
    policy = binding.get("git_checkpoint", {})
    start = policy.get("start", {})
    snapshot = start.get("snapshot", {})
    if not policy.get("enabled") or start.get("workflow_id") != payload["workflow_id"] or not snapshot.get("ok"):
        return None
    latest = policy.get("last_commit", {})
    owned_head = latest.get("commit") if latest.get("workflow_id") == payload["workflow_id"] else snapshot.get("head")
    expected = {"branch": snapshot.get("branch"), "head": owned_head}
    return expected if matches_git_identity(root, expected) else None


def matches_git_identity(root, expected):
    from git_checkpoint import CheckpointError, _repo
    if not isinstance(expected, dict) or not expected.get("branch"):
        return False
    try:
        _, _, branch, head, _ = _repo(Path(root))
        return branch == expected["branch"] and head == expected.get("head")
    except (OSError, ValueError, CheckpointError):
        return False


def _git_scope(root, binding, payload):
    changed = _observed_git_changes(root, binding, payload)
    if changed is None:
        return "declared-files"
    missing = changed - set(payload["changed_files"])
    if missing:
        raise ValueError("completion review omits observed Git changes: " + ", ".join(sorted(missing)))
    return "observed-git-baseline"


def verify_completion(root, payload, binding):
    """Gate a new normal completion before publishing its durable outcome."""
    if payload.get("status") != "complete":
        return None
    receipt = payload.get("completion_review")
    if not isinstance(receipt, dict):
        raise ValueError("normal completion requires completion_review with review and audit evidence")
    for name in ("review", "audit"):
        check = receipt[name]
        if check["status"] != "passed" or check["findings"] or not check["evidence"]:
            raise ValueError("normal completion requires passed review and audit without unresolved findings")
    paths = [item["path"] for item in receipt["files"]]
    if any(item["sha256"] is None and item["executable"] != 0 for item in receipt["files"]):
        raise ValueError("deleted completion review files require zero executable bits")
    if len({_key(path) for path in paths}) != len(paths) or len({_key(path) for path in payload["changed_files"]}) != len(payload["changed_files"]):
        raise ValueError("completion review contains duplicate file paths")
    if set(paths) != set(payload["changed_files"]):
        raise ValueError("completion review must cover changed_files exactly")
    pending = binding.get("completion_review_pending", {})
    if set(pending.get("paths", [])) - set(paths):
        raise ValueError("completion review must include the pending recovery scope")
    expected = declared_sources(payload)
    if capture_sources(root, paths) != expected:
        raise ValueError("completion review is stale; review and audit the current affected bytes again")
    from git_checkpoint import CheckpointError
    try:
        _git_scope(root, binding, payload)
    except CheckpointError as error:
        raise ValueError("completion review Git observation failed: " + str(error)) from error
    if capture_sources(root, paths) != expected:
        raise ValueError("completion review sources changed during final observation")
    return expected


def main(argv=None):
    """Capture receipt file facts only; never manufacture review or audit passes."""
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--path", action="append", required=True)
    args = parser.parse_args(argv)
    try:
        sources = capture_sources(Path(args.project), args.path)
        files = [dict(path=path, sha256=value[0] if value is not None else None,
                      executable=value[1] if value is not None else 0) for path, value in sources.items()]
        print(json.dumps({"files": files}, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
