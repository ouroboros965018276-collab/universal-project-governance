#!/usr/bin/env python3
"""Explicit project-local Git observer, independent of an agent lifecycle.

One token owns a worker. Validators run outside the governance writer lock;
publication rechecks ownership, configuration, HEAD and source bytes under it.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import git_checkpoint as git
import project_tool as project


def validate_configuration(value):
    if not isinstance(value, dict):
        raise ValueError("Git watcher configuration must be an object")
    if set(value) != {"enabled", "poll_seconds", "quiet_seconds", "validators"}:
        raise ValueError("Git watcher configuration requires enabled, poll_seconds, quiet_seconds and validators only")
    if type(value["enabled"]) is not bool:
        raise ValueError("Git watcher enabled must be boolean")
    for name, lower, upper in [("poll_seconds", 1, 60), ("quiet_seconds", 0, 3600)]:
        if type(value[name]) is not int or not lower <= value[name] <= upper:
            raise ValueError("Git watcher %s must be an integer from %s to %s" % (name, lower, upper))
    validators = value["validators"]
    if not isinstance(validators, list) or len(validators) > 8 or (value["enabled"] and not validators):
        raise ValueError("enabled Git watcher requires one to eight explicit validators")
    for validator in validators:
        if not isinstance(validator, dict) or set(validator) != {"argv", "timeout_seconds"}:
            raise ValueError("validator requires argv and timeout_seconds only")
        argv = validator["argv"]
        if (not isinstance(argv, list) or not 1 <= len(argv) <= 32
                or any(not isinstance(arg, str) or not arg or len(arg) > 4096 or "\0" in arg for arg in argv)):
            raise ValueError("validator argv must contain one to 32 bounded nonempty strings")
        seconds = validator["timeout_seconds"]
        if type(seconds) is not int or not 1 <= seconds <= 300:
            raise ValueError("validator timeout_seconds must be an integer from 1 to 300")
    return copy.deepcopy(value)


def _load(root):
    path = project.resolve(root, project.config()["binding_file"])
    binding = project.load_json(path)
    errors = project.validate_binding(binding)
    if errors:
        raise ValueError("invalid project binding: " + "; ".join(errors))
    policy = binding.get("git_checkpoint", {})
    watcher = policy.get("watcher", {})
    if not isinstance(watcher, dict):
        raise ValueError("invalid Git watcher state")
    return path, binding, policy, watcher


def _save(path, binding, watcher):
    binding["git_checkpoint"]["watcher"] = watcher
    project.write_json_atomic(path, binding)


def _live(watcher):
    return bool(watcher.get("token") and watcher.get("lease_until", 0) > time.time()
                and watcher.get("status") not in {"stopped", "stopping"})


def _view(watcher):
    value = copy.deepcopy(watcher)
    value["running"] = _live(watcher)
    if value.get("token") and not value["running"] and value.get("status") != "stopping":
        value["status"] = "stale"
        value["reason"] = "worker-heartbeat-expired; start creates a new ownership token"
    value.setdefault("status", "unconfigured")
    return {"watcher": value}


def status(root):
    """Read state without probing or signalling any operating-system process."""
    return _view(_load(project.project_root(root))[3])


@project.serialized
def configure(root, configuration):
    configuration = validate_configuration(configuration)
    project.ensure(root)
    path, binding, policy, watcher = _load(root)
    if configuration["enabled"] and not policy.get("enabled"):
        raise ValueError("enable scoped Git checkpoints before enabling its watcher")
    if policy.get("journal") or policy.get("pending_paths"):
        raise ValueError("reconcile pending Git checkpoint before configuring watcher")
    if binding.get("active_workflow"):
        raise ValueError("finish the active manual workflow before configuring watcher")
    observed = git.capture(project.project_root(root), policy) if configuration["enabled"] else None
    if configuration["enabled"] and not observed.get("ok"):
        raise ValueError("cannot configure Git watcher: " + observed.get("reason", "baseline unavailable"))
    generation = uuid.uuid4().hex
    token = watcher.get("token") if _live(watcher) and configuration["enabled"] else None
    pid = watcher.get("pid") if token else None
    watcher = {"configuration": configuration, "generation": generation,
               "workflow_id": "git-watch:" + generation, "baseline": observed,
               "status": "configured" if configuration["enabled"] else "disabled"}
    if token:
        watcher.update(token=token, pid=pid, heartbeat=time.time(), lease_until=time.time() + 15)
    _save(path, binding, watcher)
    return _view(watcher)


@project.serialized
def _reserve(root):
    path, binding, policy, watcher = _load(root)
    configuration = validate_configuration(watcher.get("configuration"))
    if not configuration["enabled"] or not policy.get("enabled"):
        raise ValueError("Git watcher is disabled")
    if _live(watcher):
        return _view(watcher), None
    if watcher.get("validation_id") and watcher.get("lease_until", 0) > time.time():
        raise ValueError("Git watcher validation is already running")
    token = uuid.uuid4().hex
    watcher.update(status="starting", token=token, pid=None, heartbeat=time.time(), lease_until=time.time() + 15)
    watcher.pop("stop_token", None)
    _save(path, binding, watcher)
    return _view(watcher), token


@project.serialized
def _start_failed(root, token, reason):
    path, binding, policy, watcher = _load(root)
    if watcher.get("token") == token:
        watcher.pop("token", None)
        watcher.update(status="blocked", reason=reason, pid=None, lease_until=0)
        _save(path, binding, watcher)
    return _view(watcher)


def _spawn_worker(root, token):
    argv = [sys.executable, str(Path(__file__).resolve()), "--worker", str(root), "--token", token]
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
               "stderr": subprocess.DEVNULL, "cwd": str(root), "shell": False}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    # The launch command is fixed; caller configuration cannot replace it.
    return subprocess.Popen(argv, **options)


def start(root):
    root = project.project_root(root)
    view, token = _reserve(root)
    if token is None:
        view["watcher"]["idempotent"] = True
        return view
    try:
        _spawn_worker(root, token)
    except OSError:
        return _start_failed(root, token, "native-worker-launch-failed")
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        view = status(root)
        state = view["watcher"]
        if state.get("token") != token:
            return view
        if state.get("pid") and state.get("heartbeat", 0) and state.get("status") != "starting":
            return view
        time.sleep(0.05)
    return _start_failed(root, token, "native-worker-startup-not-confirmed")


@project.serialized
def _request_stop(root):
    path, binding, policy, watcher = _load(root)
    token = watcher.pop("token", None)
    watcher.pop("validation_id", None)
    watcher.update(status="stopping" if token else "stopped", stop_token=token,
                   lease_until=0, reason="explicit-stop-request")
    if not token:
        watcher["pid"] = None
    _save(path, binding, watcher)
    return _view(watcher), token


def stop(root):
    root = project.project_root(root)
    view, token = _request_stop(root)
    if token is None:
        return view
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        view = status(root)
        if view["watcher"].get("status") != "stopping":
            return view
        time.sleep(0.05)
    # Cooperative cancellation may wait for an already-running validator. No
    # naked PID is used as authority to kill or signal a foreign process.
    return view


def _fingerprint(head, branch, sources):
    return hashlib.sha256(json.dumps([head, branch, sources], sort_keys=True,
                                    ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _advance_baseline(baseline, observed):
    """Retain only original protected dirt, never adopt concurrent new edits."""
    value = copy.deepcopy(observed)
    dirty = set(baseline.get("dirty_paths", [])) & set(observed.get("dirty_paths", []))
    adopted = baseline.get("adoption_sources", {})
    if observed.get("head") is not None:
        dirty -= set(adopted)
        value.pop("adoption_sources", None)
    else:
        value["adoption_sources"] = copy.deepcopy(adopted)
    value["dirty_paths"] = sorted(dirty)
    return value


def _record_attempt(watcher, fingerprint, validations):
    previous = watcher.get("last_attempt", {})
    failures = previous.get("failures", 0) + 1 if previous.get("fingerprint") == fingerprint else 1
    retry_delay = min(300, max(5, watcher["configuration"]["poll_seconds"] * 6) * (2 ** min(failures - 1, 6)))
    watcher["last_attempt"] = {"fingerprint": fingerprint, "validations": validations,
                               "attempted_at": time.time(), "failures": failures,
                               "retry_after": time.time() + retry_delay}


def _progress(watcher, state, reason, **extra):
    watcher.update(status=state, reason=reason, heartbeat=time.time(),
                   lease_until=time.time() + max(15, watcher["configuration"]["poll_seconds"] * 3))
    watcher.update(extra)
    return watcher


def _manual_pending(binding, policy, watcher):
    return (bool(binding.get("active_workflow")) or
            bool((policy.get("journal") or policy.get("pending_paths"))
                 and policy.get("start", {}).get("workflow_id") != watcher.get("workflow_id")))


@project.serialized
def _prepare(root, token, explicit):
    path, binding, policy, watcher = _load(root)
    configuration = validate_configuration(watcher.get("configuration"))
    if token is not None and watcher.get("token") != token:
        return {"watcher": {"status": "stopped", "reason": "ownership-revoked"}}, None
    if token is None and _live(watcher):
        # An explicit retry shares the worker token. The validation lease below
        # serializes it with automatic ticks; no second worker is spawned.
        token = watcher["token"]
    if not policy.get("enabled") or not configuration["enabled"]:
        return _view(dict(watcher, status="disabled")), None
    if watcher.get("validation_id") and watcher.get("lease_until", 0) > time.time():
        return _view(dict(watcher, status="busy")), None
    watcher.pop("validation_id", None)

    def finish(state, reason, **extra):
        _progress(watcher, state, reason, **extra)
        _save(path, binding, watcher)
        return _view(watcher), None

    if _manual_pending(binding, policy, watcher):
        return finish("yielded", "manual-workflow-or-checkpoint-owns-project")
    journal = policy.get("journal")
    if journal:
        if not isinstance(journal, dict):
            return finish("blocked", "invalid-checkpoint-journal")
        # Recovery consumes the original durable transaction and its sources;
        # it never labels another validator run as having passed.
        previous = watcher.get("last_attempt", {})
        if not explicit and time.time() < previous.get("retry_after", 0):
            return finish("waiting", "pending-checkpoint; bounded retry backoff")
        _record_attempt(watcher, previous.get("fingerprint", "journal:" + journal.get("token", "")),
                        previous.get("validations", []))
        recovered = git.run_checkpoint(project.project_root(root), binding,
                                       {"workflow_id": journal.get("workflow_id")}, journal.get("event_id"),
                                       lambda value: project.write_json_atomic(path, value))
        watcher["checkpoint"] = recovered
        if recovered["status"] in {"committed", "duplicate", "unchanged"}:
            current = git.capture(project.project_root(root), policy)
            if current.get("ok"):
                watcher["baseline"] = _advance_baseline(watcher["baseline"], current)
            watcher.pop("candidate", None)
            watcher.pop("last_attempt", None)
        return finish(recovered["status"], recovered.get("reason", "checkpoint-recovery"))
    observed = git.capture(project.project_root(root), policy)
    if not observed.get("ok"):
        return finish("blocked", observed.get("reason", "Git baseline unavailable"))
    baseline = watcher.get("baseline")
    if not isinstance(baseline, dict) or not baseline.get("ok"):
        return finish("blocked", "watcher-baseline-required")
    if observed["branch"] != baseline["branch"]:
        return finish("blocked", "branch-changed; explicitly reconfigure watcher")
    if observed["head"] != baseline["head"]:
        if policy.get("pending_paths"):
            return finish("blocked", "Git-head-changed-with-pending-checkpoint")
        if baseline["head"] is not None:
            if observed["head"] is None:
                return finish("blocked", "Git-head-removed; explicitly reconfigure watcher")
            ancestry = git._git(project.project_root(root),
                                ["merge-base", "--is-ancestor", baseline["head"], observed["head"]], check=False)
            if ancestry.returncode:
                return finish("blocked", "Git-head-not-fast-forward; explicitly reconfigure watcher")
        # A new external ancestry owns a new workflow. Retain configuration and
        # worker ownership; the checkpoint helper still rejects old HEAD reuse.
        watcher["workflow_id"] = "git-watch:" + watcher["generation"] + ":" + uuid.uuid4().hex
        watcher.pop("candidate", None)
        watcher.pop("last_attempt", None)
    baseline = _advance_baseline(baseline, observed)
    watcher["baseline"] = baseline
    shadow = copy.deepcopy(policy)
    shadow["start"] = {"workflow_id": watcher["workflow_id"], "snapshot": baseline}
    adopted = set(baseline.get("adoption_sources", {}))
    protected = {git._key(p) for p in baseline.get("dirty_paths", []) if p not in adopted}
    declared = [p for p in observed["dirty_paths"] if git._key(p) not in protected]
    payload = {"workflow_id": watcher["workflow_id"], "changed_files": declared}
    try:
        paths = git._select(project.project_root(root), shadow, payload)
        sources = git._sources(project.project_root(root), paths)
    except (OSError, git.CheckpointError) as error:
        return finish("blocked", str(error))
    if not paths:
        watcher.pop("candidate", None)
        watcher.pop("last_attempt", None)
        watcher["baseline"] = baseline
        return finish("idle", "no-meaningful-change")
    fingerprint = _fingerprint(observed["head"], observed["branch"], sources)
    candidate = watcher.get("candidate", {})
    if candidate.get("fingerprint") != fingerprint:
        candidate = {"fingerprint": fingerprint, "seen_at": time.time(), "paths": paths,
                     "sources": sources, "head": observed["head"], "branch": observed["branch"]}
        watcher["candidate"] = candidate
    if time.time() - candidate["seen_at"] < configuration["quiet_seconds"]:
        return finish("waiting", "waiting-for-quiet-source-boundary")
    if time.time() - policy.get("last_commit", {}).get("recorded_at", 0) < policy["min_interval_seconds"]:
        return finish("cooldown", "coalescing-nearby-observed-edits")
    previous = watcher.get("last_attempt", {})
    if (not explicit and previous.get("fingerprint") == fingerprint
            and time.time() < previous.get("retry_after", 0)):
        return finish("blocked", "unchanged-failed-candidate; bounded retry backoff")
    validation_id = uuid.uuid4().hex
    lease = sum(v["timeout_seconds"] for v in configuration["validators"]) + 15
    _progress(watcher, "validating", "running-explicit-project-validators", validation_id=validation_id,
              lease_until=time.time() + lease)
    watcher["baseline"] = baseline
    _save(path, binding, watcher)
    return None, {"configuration": configuration, "generation": watcher["generation"],
                  "validation_id": validation_id, "token": token, "candidate": copy.deepcopy(candidate)}


def _validation_owned(root, prepared):
    path, binding, policy, watcher = _load(root)
    return (policy.get("enabled") and watcher.get("configuration", {}).get("enabled")
            and watcher.get("generation") == prepared["generation"]
            and watcher.get("validation_id") == prepared["validation_id"]
            and (prepared["token"] is None or watcher.get("token") == prepared["token"]))


def _run_validators(root, validators, prepared):
    observations = []
    for validator in validators:
        if not _validation_owned(root, prepared):
            return False, observations
        # A bounded read prevents verbose output from consuming process memory.
        with tempfile.TemporaryFile(dir=str(project.project_root(root) / ".governance")) as output:
            try:
                process = subprocess.run(validator["argv"], cwd=str(root), stdin=subprocess.DEVNULL,
                                         stdout=output, stderr=subprocess.STDOUT, shell=False,
                                         timeout=validator["timeout_seconds"], check=False)
                returncode, timed_out = process.returncode, False
            except subprocess.TimeoutExpired:
                returncode, timed_out = None, True
            except OSError:
                returncode, timed_out = None, False
            output.seek(0)
            raw = output.read(8193)
        observations.append({"argv": validator["argv"], "returncode": returncode, "timed_out": timed_out,
                             "output_sha256": hashlib.sha256(raw[:8192]).hexdigest(),
                             "output_truncated": len(raw) > 8192})
        if returncode != 0:
            return False, observations
    return True, observations


@project.serialized
def _publish(root, prepared, passed, validations):
    path, binding, policy, watcher = _load(root)
    token = prepared["token"]
    if ((token is not None and watcher.get("token") != token)
            or watcher.get("generation") != prepared["generation"]
            or watcher.get("validation_id") != prepared["validation_id"]):
        return _view(dict(watcher, status="cancelled", reason="watcher-ownership-or-configuration-changed"))
    watcher.pop("validation_id", None)
    candidate = prepared["candidate"]
    _record_attempt(watcher, candidate["fingerprint"], validations)

    def finish(state, reason):
        _progress(watcher, state, reason)
        _save(path, binding, watcher)
        return _view(watcher)

    if not policy.get("enabled") or not watcher["configuration"]["enabled"]:
        return finish("cancelled", "watcher-disabled-during-validation")
    if _manual_pending(binding, policy, watcher):
        return finish("yielded", "manual-workflow-started-during-validation")
    if not passed:
        return finish("blocked", "project-validator-failed")
    observed = git.capture(project.project_root(root), policy)
    if (not observed.get("ok") or observed.get("head") != candidate["head"]
            or observed.get("branch") != candidate["branch"]):
        return finish("blocked", "Git-head-changed-during-validation")
    try:
        if git._sources(project.project_root(root), candidate["paths"]) != candidate["sources"]:
            return finish("blocked", "selected-source-changed-during-validation")
    except (OSError, git.CheckpointError):
        return finish("blocked", "selected-source-unavailable-after-validation")
    if time.time() - policy.get("last_commit", {}).get("recorded_at", 0) < policy["min_interval_seconds"]:
        return finish("cooldown", "commit-interval-changed-during-validation")
    payload = {"workflow_id": watcher["workflow_id"], "status": "complete", "task": "validated observed project changes",
               "changed_files": candidate["paths"], "integrity": "pass",
               "validation": ["explicit validator %s exited zero" % (i + 1) for i in range(len(validations))],
               "handoff": "not-required"}
    if not policy.get("journal"):
        policy["start"] = {"workflow_id": watcher["workflow_id"], "snapshot": watcher["baseline"]}
    result = git.run_checkpoint(project.project_root(root), binding, payload,
                                "git-watch:" + candidate["fingerprint"],
                                lambda value: project.write_json_atomic(path, value),
                                validated_sources=candidate["sources"])
    watcher = binding["git_checkpoint"]["watcher"]
    watcher["checkpoint"] = result
    if result["status"] in {"committed", "duplicate", "unchanged"}:
        current = git.capture(project.project_root(root), policy)
        if current.get("ok"):
            watcher["baseline"] = _advance_baseline(watcher["baseline"], current)
        watcher.pop("candidate", None)
        watcher.pop("last_attempt", None)
    _progress(watcher, result["status"], result.get("reason", "checkpoint-result"))
    _save(path, binding, watcher)
    return _view(watcher)


def tick(root, token=None):
    root = project.project_root(root)
    view, prepared = _prepare(root, token, explicit=token is None)
    if prepared is None:
        return view
    passed, validations = _run_validators(root, prepared["configuration"]["validators"], prepared)
    return _publish(root, prepared, passed, validations)


@project.serialized
def _claim(root, token):
    path, binding, policy, watcher = _load(root)
    if watcher.get("token") != token or not watcher.get("configuration", {}).get("enabled"):
        return False
    if watcher.get("pid") not in {None, os.getpid()}:
        return False
    _progress(watcher, "running", "native-worker-confirmed", pid=os.getpid())
    _save(path, binding, watcher)
    return True


@project.serialized
def _worker_error(root, token, error):
    path, binding, policy, watcher = _load(root)
    if watcher.get("token") == token:
        _progress(watcher, "blocked", "worker-error: " + str(error)[:256])
        _save(path, binding, watcher)


@project.serialized
def _ack_stop(root, token):
    path, binding, policy, watcher = _load(root)
    if watcher.get("token") is None and watcher.get("stop_token") == token:
        watcher.update(status="stopped", pid=None, lease_until=0)
        _save(path, binding, watcher)


def worker(root, token):
    if not _claim(root, token):
        return 1
    try:
        while True:
            state = status(root)["watcher"]
            if state.get("token") != token or not state.get("configuration", {}).get("enabled"):
                break
            try:
                tick(root, token=token)
            except (OSError, ValueError, git.CheckpointError) as error:
                writer_busy = isinstance(error, ValueError) and str(error).startswith("project state writer busy;")
                if not writer_busy:
                    try:
                        _worker_error(root, token, error)
                    except (OSError, ValueError):
                        # A failed diagnostic write cannot terminate observation.
                        # Its old heartbeat still expires rather than claim health.
                        pass
            time.sleep(state["configuration"]["poll_seconds"])
    finally:
        try:
            _ack_stop(root, token)
        except (OSError, ValueError):
            # Cancellation already revoked ownership. A busy writer may delay
            # acknowledgement; it must not turn cooperative exit into a crash.
            pass
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--token", required=True)
    args = parser.parse_args()
    return worker(project.project_root(args.worker), args.token)


if __name__ == "__main__":
    sys.exit(main())
