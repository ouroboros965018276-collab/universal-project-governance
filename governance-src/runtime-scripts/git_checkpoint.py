#!/usr/bin/env python3
"""Bounded, opt-in Git checkpoints at observed governance stage boundaries.

The binding owns the journal. Git owns commits and its native index lock; no
timer, push, host-configuration rewrite or parallel ledger is used. Explicit
bootstrap initializes only the selected project and can adopt its first files.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import time
import uuid

MAX_PATHS = 256
MAX_RECEIPTS = 256  # Covers the lifecycle's bounded 200 active stage receipts.
_live = set()


class CheckpointError(Exception):
    pass


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _env(index=None):
    # Caller environment must not redirect this operation to another repository,
    # index, object store, injected config or identity. Repository config remains.
    safe = {"GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_DATE", "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_DATE", "GIT_ASKPASS", "GIT_SSH",
            "GIT_SSH_COMMAND", "GIT_SSH_VARIANT"}
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_") or k.upper() in safe}
    env["GIT_TERMINAL_PROMPT"] = "0"
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    return env


def _git(root, args, index=None, check=True, timeout=30, admin=None):
    executable = shutil.which("git")
    if not executable:
        raise CheckpointError("git-unavailable")
    try:
        env = _env(index)
        if admin is not None:
            env.update(GIT_DIR=str(admin), GIT_WORK_TREE=str(root))
        result = subprocess.run([executable, "--literal-pathspecs", "-C", str(root)] + list(args),
                                env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise CheckpointError("git-command-timeout")
    if check and result.returncode:
        raise CheckpointError("git-%s-failed" % args[0])
    return result


def _text(root, args, index=None, admin=None):
    return _git(root, args, index, admin=admin).stdout.decode("utf-8", "surrogateescape").strip()


def _paths(raw):
    return [p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p]


def _key(path):
    return os.path.normcase(path.replace("/", os.sep))


def _relative(value):
    if not isinstance(value, str) or not value or "\0" in value or "\\" in value or ":" in value:
        raise CheckpointError("unsafe-path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {".", ".."} for p in value.split("/")):
        raise CheckpointError("unsafe-path")
    return path.as_posix()


def _check_environment():
    overrides = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES"}
    if any(k.upper() in overrides or k.upper().startswith("GIT_CONFIG_") for k in os.environ):
        raise CheckpointError("git-environment-redirection-unsupported")


def _head(root, admin=None):
    result = _git(root, ["rev-parse", "--verify", "HEAD"], check=False, admin=admin)
    if result.returncode:
        return None
    head = result.stdout.decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise CheckpointError("invalid-git-head")
    return head


def _index_bytes(index):
    return index.read_bytes() if index.exists() else None


def _index_digest(index):
    raw = _index_bytes(index)
    return _digest(raw) if raw is not None else None


def _empty_tree(root):
    return _text(root, ["hash-object", "-t", "tree", os.devnull])


def _repo(root):
    _check_environment()
    root = Path(root).resolve()
    if (root / ".git").is_symlink():
        raise CheckpointError("symlinked-git-directory")
    top = Path(_text(root, ["rev-parse", "--show-toplevel"])).resolve()
    if top != root:
        raise CheckpointError("project-must-be-git-worktree-root")
    directory = Path(_text(root, ["rev-parse", "--absolute-git-dir"])).resolve()
    branch = _text(root, ["symbolic-ref", "--quiet", "HEAD"])
    head = _head(root)
    if not branch.startswith("refs/heads/"):
        raise CheckpointError("detached-head")
    if head is None and _git(root, ["show-ref", "--verify", "--quiet", branch], check=False).returncode != 1:
        raise CheckpointError("unresolved-git-head")
    for name in ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer"]:
        if (directory / name).exists():
            raise CheckpointError("git-operation-in-progress")
    if _git(root, ["ls-files", "--unmerged", "-z"]).stdout:
        raise CheckpointError("unmerged-index")
    if _text(root, ["rev-parse", "--shared-index-path"]):
        raise CheckpointError("split-index-unsupported")
    sparse = _git(root, ["config", "--bool", "core.sparseCheckout"], check=False)
    if sparse.stdout.strip() == b"true":
        raise CheckpointError("sparse-checkout-unsupported")
    index = directory / "index"
    if index.is_symlink() or (index.exists() and not index.is_file()) or (head is not None and not index.is_file()):
        raise CheckpointError("missing-or-symlinked-index")
    return root, directory, branch, head, index


def _in_scope(path, policy):
    allow = policy.get("allowed_paths", [])
    if not isinstance(allow, list) or not allow:
        raise CheckpointError("allowed-paths-required")
    allowed = [_relative(p) for p in allow if p != "."]
    return "." in allow or any(_key(path) == _key(p) or _key(path).startswith(_key(p) + os.sep) for p in allowed)


def _excluded(path, policy):
    return (any(part.lower() in {".git", ".governance"} for part in PurePosixPath(path).parts)
            or _key(path) in {_key(_relative(p)) for p in policy.get("status_paths", [])})


def _repository_observation(root):
    directory = Path(_text(root, ["rev-parse", "--absolute-git-dir"])).resolve()
    common = Path(_text(root, ["rev-parse", "--git-common-dir"]))
    common = common.resolve() if common.is_absolute() else (root / common).resolve()
    configs = {}
    for path in [common / "config", directory / "config.worktree"]:
        if path.is_symlink():
            raise CheckpointError("symlinked-parent-git-config")
        configs[str(path)] = _digest(path.read_bytes()) if path.is_file() else None
    if (directory / "index").is_symlink():
        raise CheckpointError("symlinked-parent-index")
    branch = _git(root, ["symbolic-ref", "--quiet", "HEAD"], check=False).stdout.decode("utf-8", "surrogateescape").strip()
    return {"root": str(root), "head": _head(root), "branch": branch,
            "index_sha256": _index_digest(directory / "index"), "config_sha256": configs}


def _parent_state(root):
    found = _git(root, ["rev-parse", "--show-toplevel"], check=False)
    if found.returncode:
        return None
    parent = Path(found.stdout.decode("utf-8", "surrogateescape").strip()).resolve()
    return _repository_observation(parent) if parent != root else None


def bootstrap(root, policy):
    """Explicitly initialize this project only; never adopt its parent's Git."""
    initialized = False
    try:
        _check_environment()
        if not isinstance(policy, dict):
            raise CheckpointError("invalid-git-checkpoint-policy")
        root = Path(root).resolve()
        if not root.is_dir():
            raise CheckpointError("project-directory-required")
        local = root / ".git"
        if local.is_symlink():
            raise CheckpointError("symlinked-git-directory")
        if local.exists():
            return dict(capture(root, policy), initialized=False, parent_isolated=False)
        if policy.get("enabled") is not True or policy.get("bootstrap") is not True:
            raise CheckpointError("git-bootstrap-not-enabled")
        _in_scope("bootstrap-policy-probe", policy)  # Validate literal scopes before any write.
        _excluded("bootstrap-policy-probe", policy)
        parent_before = _parent_state(root)
        # Native init respects the owner's project template/default-branch settings.
        # An uncertain command is not repeated: inspect the resulting local repo.
        failure = None
        try:
            process = _git(root, ["init", "--quiet"], check=False)
            if process.returncode:
                failure = "git-init-failed"
        except CheckpointError as error:
            failure = str(error)
        initialized = local.exists()
        if parent_before is not None and parent_before != _repository_observation(Path(parent_before["root"])):
            raise CheckpointError("parent-git-state-changed-during-bootstrap")
        if failure:
            raise CheckpointError(failure)
        snapshot = capture(root, policy)
        return dict(snapshot, initialized=initialized, parent_isolated=parent_before is not None,
                    parent_before=parent_before)
    except (OSError, CheckpointError) as error:
        return {"ok": False, "reason": str(error), "initialized": initialized}


def capture(root, policy):
    """Read the real Git baseline; failed capability checks never grant ownership."""
    try:
        root, directory, branch, head, index = _repo(root)
        records = _git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]).stdout.split(b"\0")
        dirty, untracked, i = [], [], 0
        while i < len(records):
            row = records[i]
            i += 1
            if not row:
                continue
            path = row[3:].decode("utf-8", "surrogateescape")
            dirty.append(path)
            if row[:2] == b"??":
                untracked.append(path)
            if b"R" in row[:2] or b"C" in row[:2]:
                if i < len(records) and records[i]:
                    dirty.append(records[i].decode("utf-8", "surrogateescape"))
                    i += 1
        if head is None:
            # Initial adoption is explicit to this scope; unrelated project files
            # neither grant ownership nor consume its bounded baseline budget.
            dirty = [path for path in dirty if not _excluded(path, policy) and _in_scope(path, policy)]
        if len(set(dirty)) > MAX_PATHS:
            raise CheckpointError("baseline-path-limit")
        adopted = {}
        if head is None:
            for path in untracked:
                if _excluded(path, policy) or not _in_scope(path, policy):
                    continue
                try:
                    adopted.update(_sources(root, [path]))
                except CheckpointError:
                    # Sensitive/symlinked files are never adopted by a broad scope.
                    continue
        return {"ok": True, "head": head, "branch": branch,
                "dirty_paths": sorted(set(dirty)), "adoption_sources": adopted,
                "observed_at": time.time()}
    except (OSError, CheckpointError) as error:
        return {"ok": False, "reason": str(error)}


def _safe_file(root, relative):
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise CheckpointError("symlinked-selected-path")
    if current.exists() and not current.is_file():
        raise CheckpointError("selected-path-is-not-file")
    name = PurePosixPath(relative).name.lower()
    if (name == ".env" or name.startswith(".env.") or name in {"credentials", "credentials.json", "id_rsa", "id_dsa", "id_ed25519"}
            or name.startswith("secrets.") or name.endswith((".pem", ".key", ".p12", ".pfx"))):
        raise CheckpointError("sensitive-selected-path")
    return current


def _sources(root, paths):
    state = {}
    for relative in paths:
        path = _safe_file(root, relative)
        if not path.exists():
            state[relative] = None
        else:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            state[relative] = [digest.hexdigest(), path.stat().st_mode & 0o111]
    return state


def _retire_unchanged(policy, workflow_id, event_id, token, retire_pending=True):
    events = policy.get("deferred_events", {})
    retired = [dict(token=token, event_id=e["event_id"], workflow_id=workflow_id, status="unchanged")
               for token, e in events.items() if retire_pending and e.get("workflow_id") == workflow_id]
    retired.append(dict(token=token, event_id=event_id, workflow_id=workflow_id, status="unchanged"))
    policy["receipts"] = (policy.get("receipts", []) + retired)[-MAX_RECEIPTS:]
    if retire_pending:
        policy["deferred_events"] = {token: e for token, e in events.items() if e.get("workflow_id") != workflow_id}
        policy["pending_paths"] = []
        policy.pop("pending_workflow_id", None)


def _select(root, policy, payload):
    declared = payload.get("changed_files", [])
    pending = policy.get("pending_paths", [])
    if not isinstance(declared, list) or not isinstance(pending, list):
        raise CheckpointError("invalid-checkpoint-paths")
    if pending and policy.get("pending_workflow_id") != payload.get("workflow_id"):
        raise CheckpointError("pending-paths-belong-to-another-workflow")
    _in_scope("checkpoint-policy-probe", policy)
    _excluded("checkpoint-policy-probe", policy)
    dirty = {_key(p) for p in policy["start"]["snapshot"].get("dirty_paths", [])}
    previous_pending = {_key(p) for p in pending}
    adopted = {_key(p) for p in policy["start"]["snapshot"].get("adoption_sources", {})} if policy["start"]["snapshot"].get("head") is None else set()
    selected = set()
    for value in declared + pending:
        path = _relative(value)
        if _excluded(path, policy):
            continue
        if not _in_scope(path, policy):
            continue
        _safe_file(root, path)
        if _key(path) in dirty and _key(path) not in previous_pending and _key(path) not in adopted:
            raise CheckpointError("preexisting-dirty-path")
        if _git(root, ["check-ignore", "--quiet", "--", path], check=False).returncode == 0:
            raise CheckpointError("ignored-selected-path")
        if _git(root, ["ls-files", "--stage", "--", path]).stdout.startswith(b"160000 "):
            raise CheckpointError("submodule-selected-path")
        selected.add(path)
    if len(selected) > MAX_PATHS:
        raise CheckpointError("checkpoint-path-limit")
    return sorted(selected)


def _artifact(directory, journal):
    name = journal.get("artifact_dir", "")
    if not re.fullmatch(r"upg-checkpoint-[0-9a-f]{32}", name):
        raise CheckpointError("invalid-recovery-artifact")
    path = directory / name
    if path.is_symlink() or not path.is_dir():
        raise CheckpointError("missing-recovery-artifact")
    if any((path / name).is_symlink() for name in ["candidate-index", "next-index", "original-index"]):
        raise CheckpointError("symlinked-recovery-artifact")
    return path


def _clean(directory):
    # Exact owned files only; never recursively remove an unexpected artifact.
    admin = directory / "private-admin"
    if admin.is_dir() and not admin.is_symlink():
        for relative in ["HEAD", "HEAD.lock", "commondir", "config.worktree", "COMMIT_EDITMSG", "ORIG_HEAD", "logs/HEAD", "logs/HEAD.lock",
                         "refs/worktree/upg-initial", "refs/worktree/upg-initial.lock",
                         "logs/refs/worktree/upg-initial", "logs/refs/worktree/upg-initial.lock"]:
            path = admin / relative
            parts = PurePosixPath(relative).parts
            if any(admin.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts))):
                continue
            if path.is_file() and not path.is_symlink():
                path.unlink()
        for path in [admin / "refs/worktree", admin / "refs", admin / "logs/refs/worktree", admin / "logs/refs", admin / "logs", admin]:
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != admin.parent and admin in parent.parents):
                continue
            try:
                path.rmdir()
            except OSError:
                pass
    for name in ["candidate-index", "candidate-index.lock", "next-index", "next-index.lock", "original-index"]:
        path = directory / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
    try:
        directory.rmdir()
    except OSError:
        pass


@contextmanager
def _index_lock(index, journal=None):
    lock = index.with_name("index.lock")
    owned, stream, identity = False, None, None
    try:
        try:
            stream = lock.open("xb")
        except FileExistsError:
            if not journal or lock.is_symlink() or _digest(lock.read_bytes()) != journal.get("lock_sha256"):
                raise CheckpointError("git-index-busy")
            owner = journal.get("owner_pid")
            if isinstance(owner, bool) or not isinstance(owner, int) or owner <= 0:
                raise CheckpointError("invalid-checkpoint-owner-metadata")
            if owner != os.getpid():
                # A PID alone cannot prove another process is dead or that it
                # still owns this file. Never signal/probe a Windows process.
                raise CheckpointError("stale-native-index-lock-requires-inspection")
            if journal.get("token") in _live:
                raise CheckpointError("checkpoint-owner-still-running")
            stream = lock.open("r+b")
        owned = True
        stat = os.fstat(stream.fileno())
        identity = stat.st_dev, stat.st_ino
        yield stream, lock
    finally:
        if stream is not None:
            stream.close()
        if owned and lock.is_file() and not lock.is_symlink():
            stat = lock.stat()
            if (stat.st_dev, stat.st_ino) == identity:
                lock.unlink()


def _verify_commit(root, commit, journal):
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        return False
    fields = _text(root, ["show", "-s", "--format=%T%n%P%n%B", commit]).splitlines()
    return (len(fields) >= 3 and fields[0] == journal["tree"] and fields[1] == (journal["parent"] or "")
            and ("UPG-Checkpoint: " + journal["token"]) in fields[2:])


def _private_admin(root, directory, artifact, journal):
    """Use native hooks/signing without permitting commit to publish real HEAD."""
    admin = artifact / "private-admin"
    if admin.is_symlink():
        raise CheckpointError("symlinked-private-git-context")
    if not admin.exists():
        admin.mkdir()
        common = Path(_text(root, ["rev-parse", "--git-common-dir"]))
        common = common.resolve() if common.is_absolute() else (root / common).resolve()
        (admin / "commondir").write_text(common.as_posix() + "\n", encoding="utf-8")
        (admin / "HEAD").write_text((journal["parent"] or "ref: refs/worktree/upg-initial") + "\n", encoding="ascii")
        local_config = directory / "config.worktree"
        if local_config.is_symlink():
            raise CheckpointError("symlinked-worktree-config")
        if local_config.is_file():
            (admin / "config.worktree").write_bytes(local_config.read_bytes())
    if any((admin / name).is_symlink() for name in ["HEAD", "commondir", "config.worktree"]):
        raise CheckpointError("symlinked-private-git-context")
    actual = _git(root, ["config", "--null", "--list"]).stdout
    private = _git(root, ["config", "--null", "--list"], admin=admin).stdout
    if actual != private:
        raise CheckpointError("private-git-config-context-unsupported")
    return admin


def _complete(root, directory, index, binding, save, journal, commit, stream, lock):
    policy = binding["git_checkpoint"]
    artifact = _artifact(directory, journal)
    next_raw = (artifact / "next-index").read_bytes()
    if _digest(next_raw) != journal["next_index_sha256"]:
        raise CheckpointError("prepared-index-drift")
    current = _index_digest(index)
    if current != journal["next_index_sha256"]:
        if current != journal["index_sha256"]:
            raise CheckpointError("real-index-drift")
        if _head(root) != commit:
            raise CheckpointError("head-drift-after-commit")
        stream.seek(0)
        stream.write(next_raw)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        os.replace(str(lock), str(index))
    previous_policy = dict(policy)
    receipt = {"commit": commit, "tree": journal["tree"], "event_id": journal["event_id"],
               "recorded_at": time.time(), "paths": journal["paths"], "workflow_id": journal["workflow_id"],
               "token": journal["token"]}
    policy["last_commit"] = receipt
    covered = [dict(receipt, event_id=e["event_id"], token=token, covered=True)
               for token, e in policy.get("deferred_events", {}).items()
               if e.get("workflow_id") == journal["workflow_id"] and token != journal["token"]]
    policy["receipts"] = (policy.get("receipts", []) + covered + [receipt])[-MAX_RECEIPTS:]
    policy["pending_paths"] = [p for p in policy.get("pending_paths", []) if p not in journal["paths"]]
    if not policy["pending_paths"]:
        policy.pop("pending_workflow_id", None)
    policy["deferred_events"] = {token: e for token, e in policy.get("deferred_events", {}).items()
                                 if e.get("workflow_id") != journal["workflow_id"]}
    policy.pop("journal", None)
    result = {"status": "committed", "reason": "verified-stage", "commit": commit, "paths": journal["paths"]}
    policy["result"] = result
    try:
        save(binding)
    except Exception:
        # The durable binding may still own its journal. Retain recovery
        # artifacts and the pre-receipt state until persistence is confirmed.
        policy.clear()
        policy.update(previous_policy)
        raise
    _clean(artifact)
    return result


def _transact(root, directory, branch, head, index, binding, save, journal):
    policy = binding["git_checkpoint"]
    required = {"event_id", "parent", "branch", "tree", "token", "message", "paths", "sources",
                "index_sha256", "next_index_sha256", "lock_sha256", "artifact_dir", "workflow_id"}
    if not isinstance(journal, dict) or not required.issubset(journal):
        raise CheckpointError("invalid-checkpoint-journal")
    if not isinstance(journal["paths"], list) or len(journal["paths"]) > MAX_PATHS:
        raise CheckpointError("invalid-checkpoint-journal-paths")
    for path in journal["paths"]:
        _relative(path)
    uncertain = journal.get("status") == "uncertain"
    artifact = _artifact(directory, journal)
    with _index_lock(index, journal) as (stream, lock):
        if _text(root, ["symbolic-ref", "--quiet", "HEAD"]) != journal["branch"]:
            raise CheckpointError("branch-drift")
        current_head = _head(root)
        if current_head != journal["parent"]:
            if not _verify_commit(root, current_head, journal):
                raise CheckpointError("pending-checkpoint-head-drift")
            return _complete(root, directory, index, binding, save, journal, current_head, stream, lock)
        if uncertain:
            raise CheckpointError("uncertain-commit-requires-inspection")
        if _index_digest(index) != journal["index_sha256"]:
            raise CheckpointError("real-index-drift")
        if _sources(root, journal["paths"]) != journal["sources"]:
            raise CheckpointError("selected-source-drift")
        if _text(root, ["symbolic-ref", "--quiet", "HEAD"]) != journal["branch"]:
            raise CheckpointError("branch-drift")
        candidate = artifact / "candidate-index"
        if candidate.is_symlink() or _text(root, ["write-tree"], candidate) != journal["tree"]:
            raise CheckpointError("candidate-index-drift")
        next_raw = (artifact / "next-index").read_bytes()
        if _digest(next_raw) != journal["next_index_sha256"]:
            raise CheckpointError("prepared-index-drift")
        stream.write(next_raw)
        stream.flush()
        os.fsync(stream.fileno())
        _live.add(journal["token"])
        try:
            admin = _private_admin(root, directory, artifact, journal)
            prepared = journal.get("prepared_commit")
            if not prepared:
                prepared = _head(root, admin=admin)
                if prepared == journal["parent"]:
                    try:
                        process = _git(root, ["commit", "--quiet", "-m", journal["message"]], candidate,
                                       check=False, timeout=60, admin=admin)
                        failure = "git-commit-rejected" if process.returncode else None
                    except CheckpointError as error:
                        failure = str(error)
                    prepared = _head(root, admin=admin)
                    if prepared == journal["parent"]:
                        if failure == "git-command-timeout":
                            journal["status"] = "uncertain"
                        save(binding)
                        raise CheckpointError(failure or "private-commit-did-not-advance-head")
                if not _verify_commit(root, prepared, journal):
                    journal["status"] = "uncertain"
                    journal["observed_private_commit"] = prepared
                    save(binding)
                    raise CheckpointError("private-commit-parent-tree-or-receipt-mismatch")
                journal["prepared_commit"] = prepared
                journal["status"] = "private-prepared"
                save(binding)
            if not _verify_commit(root, prepared, journal):
                raise CheckpointError("prepared-commit-drift")
            if _sources(root, journal["paths"]) != journal["sources"] or _index_digest(index) != journal["index_sha256"]:
                raise CheckpointError("source-or-index-drift-before-publish")
            if _text(root, ["symbolic-ref", "--quiet", "HEAD"]) != journal["branch"]:
                raise CheckpointError("branch-drift-before-publish")
            try:
                publication = _git(root, ["update-ref", journal["branch"], prepared, journal["parent"] or "0" * len(journal["tree"])], check=False)
                failure = "branch-compare-and-swap-rejected" if publication.returncode else None
            except CheckpointError as error:
                failure = str(error)
            after = _head(root)
            if after != prepared or _text(root, ["symbolic-ref", "--quiet", "HEAD"]) != journal["branch"]:
                if failure == "git-command-timeout":
                    journal["status"] = "uncertain"
                save(binding)
                raise CheckpointError(failure or "head-or-branch-drift-after-publish")
            journal["status"] = "committed"
            journal["commit"] = after
            save(binding)
            return _complete(root, directory, index, binding, save, journal, after, stream, lock)
        finally:
            _live.discard(journal["token"])


def run_checkpoint(root, binding, payload, event_id, save_binding, *, validated_sources=None):
    """Run/recover one automatic checkpoint; metadata failure never invents success."""
    policy = binding.get("git_checkpoint", {})
    if not isinstance(policy, dict):
        return {"status": "blocked", "reason": "invalid-git-checkpoint-policy"}
    if not policy.get("enabled"):
        return {"status": "disabled", "reason": "not-enabled"}

    def result(status, reason, **extra):
        value = dict(status=status, reason=reason, **extra)
        policy["result"] = value
        save_binding(binding)
        return value

    try:
        root, directory, branch, head, index = _repo(root)
        start = policy.get("start", {})
        if isinstance(start, dict) and start.get("workflow_id") != payload.get("workflow_id"):
            older = next((r for r in policy.get("receipts", []) if r.get("event_id") == event_id
                          and r.get("workflow_id") == payload.get("workflow_id")), None)
            if older:
                if older.get("status") == "unchanged":
                    return result("unchanged", "earlier-event-retired-without-commit")
                return result("duplicate", "earlier-workflow-event-already-committed", commit=older["commit"])
        journal = policy.get("journal")
        if journal:
            if not isinstance(journal, dict):
                raise CheckpointError("invalid-checkpoint-journal")
            if journal.get("event_id") != event_id and head == journal.get("parent"):
                raise CheckpointError("previous-checkpoint-pending")
            recovered = _transact(root, directory, branch, head, index, binding, save_binding, journal)
            if journal.get("event_id") == event_id:
                return recovered
            root, directory, branch, head, index = _repo(root)
        start = policy.get("start", {})
        if not isinstance(start, dict) or not isinstance(start.get("snapshot"), dict):
            raise CheckpointError("workflow-git-baseline-required")
        snapshot = start.get("snapshot", {})
        if start.get("workflow_id") != payload.get("workflow_id") or not snapshot.get("ok"):
            raise CheckpointError("workflow-git-baseline-required")
        token = _digest(json.dumps([event_id, snapshot.get("head"), snapshot.get("branch")],
                                  ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        previous = next((r for r in policy.get("receipts", []) if r.get("token") == token), None)
        if previous:
            if previous.get("status") == "unchanged":
                return result("unchanged", "event-retired-without-commit")
            return result("duplicate", "event-already-committed", commit=previous["commit"])
        last_commit = policy.get("last_commit", {})
        owned_head = last_commit.get("commit") if last_commit.get("workflow_id") == payload.get("workflow_id") else None
        expected_head = owned_head if owned_head is not None else snapshot.get("head")
        if branch != snapshot.get("branch") or head != expected_head:
            raise CheckpointError("head-or-branch-moved-since-baseline")
        paths = _select(root, policy, payload)
        if validated_sources is not None and (not isinstance(validated_sources, dict)
                                               or set(paths) != set(validated_sources)
                                               or _sources(root, paths) != validated_sources):
            raise CheckpointError("validated-source-drift")
        if not paths:
            _retire_unchanged(policy, payload.get("workflow_id"), event_id, token, retire_pending=False)
            return result("unchanged", "no-meaningful-declared-paths")
        deferred = policy.get("deferred_events", {})
        original_deferred = deferred.get(token)
        if original_deferred and (paths != original_deferred["paths"]
                                  or _sources(root, paths) != original_deferred["sources"]):
            raise CheckpointError("deferred-event-source-or-scope-drift")
        staged = {_key(p) for p in _paths(_git(root, ["diff", "--cached", "--no-renames", "--name-only", "-z"] + (["HEAD"] if head is not None else [])).stdout)}
        if any(_key(p) in staged for p in paths):
            raise CheckpointError("selected-path-has-staged-changes")
        policy["pending_paths"] = paths
        policy["pending_workflow_id"] = payload.get("workflow_id")
        difference = _git(root, ["diff", "--quiet"] + (["HEAD"] if head is not None else []) + ["--"] + paths, check=False)
        untracked = _git(root, ["ls-files", "--others", "--exclude-standard", "-z", "--"] + paths).stdout
        if difference.returncode > 1:
            raise CheckpointError("git-diff-failed")
        if difference.returncode == 0 and not untracked:
            _retire_unchanged(policy, payload.get("workflow_id"), event_id, token)
            return result("unchanged", "no-effective-git-change")
        if payload.get("integrity") != "pass" or not payload.get("validation"):
            raise CheckpointError("passing-stage-validation-required")
        last = policy.get("last_commit", {}).get("recorded_at", 0)
        interval = policy.get("min_interval_seconds", 300)
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval < 0:
            raise CheckpointError("invalid-minimum-interval")
        boundary = payload.get("git_boundary", "verified")
        if boundary not in {"verified", "handoff", "risk"}:
            raise CheckpointError("invalid-git-boundary")
        flush = payload.get("status") == "complete" or boundary in {"handoff", "risk"}
        if not flush and time.time() - last < interval:
            if token not in deferred:
                if len(deferred) >= 32:
                    raise CheckpointError("deferred-event-limit")
                deferred[token] = {"event_id": event_id, "workflow_id": payload.get("workflow_id"),
                                   "paths": paths, "sources": _sources(root, paths)}
                policy["deferred_events"] = deferred
            return result("deferred", "coalescing-nearby-stages", pending_paths=paths)
        prior = _text(root, ["log", "-1", "--format=%H", "--fixed-strings", "--grep=Checkpoint: " + token]) if head is not None else ""
        if prior:
            return result("duplicate", "git-event-receipt-already-exists", commit=prior)
        for identity in ["GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"]:
            if _git(root, ["-c", "user.useConfigOnly=true", "var", identity], check=False).returncode:
                raise CheckpointError("git-identity-not-configured")
        artifact = directory / ("upg-checkpoint-" + uuid.uuid4().hex)
        artifact.mkdir()
        try:
            with _index_lock(index) as (stream, lock):
                staged = {_key(p) for p in _paths(_git(root, ["diff", "--cached", "--no-renames", "--name-only", "-z"] + (["HEAD"] if head is not None else [])).stdout)}
                if any(_key(p) in staged for p in paths):
                    raise CheckpointError("selected-path-has-staged-changes")
                original = _index_bytes(index)
                (artifact / "original-index").write_bytes(original or b"")
                sources = _sources(root, paths)
                if validated_sources is not None and sources != validated_sources:
                    raise CheckpointError("validated-source-drift")
                candidate = artifact / "candidate-index"
                _git(root, ["read-tree", head] if head is not None else ["read-tree", "--empty"], candidate)
                _git(root, ["add", "-A", "--"] + paths, candidate)
                tree = _text(root, ["write-tree"], candidate)
                if _head(root) != head:
                    raise CheckpointError("head-drift-during-prepare")
                if tree == (_text(root, ["rev-parse", head + "^{tree}"]) if head is not None else _empty_tree(root)):
                    _retire_unchanged(policy, payload.get("workflow_id"), event_id, token)
                    _clean(artifact)
                    return result("unchanged", "candidate-tree-unchanged")
                next_index = artifact / "next-index"
                if original is None:
                    _git(root, ["read-tree", "--empty"], next_index)
                else:
                    next_index.write_bytes(original)
                _git(root, ["reset", "-q", tree, "--"] + paths, next_index)
                next_raw = next_index.read_bytes()
                if _index_digest(index) != (_digest(original) if original is not None else None) or _head(root) != head:
                    raise CheckpointError("head-or-index-drift-during-prepare")
                task = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", str(payload.get("task", "verified change"))).split())[:100]
                stage = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", str(payload.get("checkpoint_id", payload.get("status", "stage")))).split())[:48]
                message = "upg: %s [%s:%s]\n\nUPG-Checkpoint: %s" % (task, boundary, stage, token)
                message += "".join("\nUPG-Covered-Checkpoint: " + covered for covered, e in deferred.items()
                                   if covered != token and e.get("workflow_id") == payload.get("workflow_id"))
                journal = {"status": "prepared", "event_id": event_id, "parent": head,
                           "workflow_id": payload.get("workflow_id"),
                           "message": message, "boundary": boundary,
                           "branch": branch, "tree": tree, "token": token, "paths": paths,
                           "sources": sources, "index_sha256": (_digest(original) if original is not None else None),
                           "next_index_sha256": _digest(next_raw), "lock_sha256": _digest(next_raw),
                           "artifact_dir": artifact.name, "owner_pid": os.getpid()}
                stream.write(next_raw)
                stream.flush()
                os.fsync(stream.fileno())
                policy["journal"] = journal
                save_binding(binding)
            # Reacquire the native lock with the durable intent available. Any
            # external index/HEAD/source change in this interval is rejected.
            return _transact(root, directory, branch, head, index, binding, save_binding, journal)
        except Exception:
            if not policy.get("journal"):
                _clean(artifact)
            raise
    except (OSError, CheckpointError) as error:
        return result("blocked", str(error))
