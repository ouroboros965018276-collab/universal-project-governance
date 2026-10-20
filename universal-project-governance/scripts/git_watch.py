#!/usr/bin/env python3
"""Explicit project-session Git observer, independent of an agent turn.

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
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import git_checkpoint as git
import project_tool as project
import process_guard as guards
import session_lifetime as lifetime

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _PIPE_KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
    _PIPE_KERNEL.PeekNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                           wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD),
                                           wintypes.LPVOID]
    _PIPE_KERNEL.PeekNamedPipe.restype = wintypes.BOOL


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


def _desired(watcher):
    if "desired_running" in watcher:
        return watcher["desired_running"]
    return bool(watcher.get("configuration", {}).get("enabled")
                and watcher.get("status") not in {"stopped", "stopping", "disabled"})


def _legacy_owner(watcher):
    return watcher.get("guard_version") != 1 and bool(
        watcher.get("token") or watcher.get("pid") or watcher.get("status") == "stopping")


def _live(watcher):
    return bool(watcher.get("token") and type(watcher.get("pid")) is int and watcher["pid"] > 0
                and watcher.get("lease_until", 0) > time.time()
                and watcher.get("status") not in {"starting", "stopped", "stopping"})


def _view(watcher):
    value = copy.deepcopy(watcher)
    value["running"] = bool(_live(watcher) and watcher.get("supervisor", {}).get("status")
                            not in {"starting", "recovering", "blocked", "waiting"})
    value["desired_running"] = _desired(watcher)
    if (value.get("token") and not _live(watcher)
            and value.get("status") not in {"starting", "stopped", "stopping"}):
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
    desired = _desired(watcher) if configuration["enabled"] else False
    supervisor = copy.deepcopy(watcher.get("supervisor", {"enabled": False}))
    session_state = copy.deepcopy(watcher.get("session"))
    guard_version = watcher.get("guard_version")
    generation = uuid.uuid4().hex
    token = watcher.get("token") if _live(watcher) and configuration["enabled"] else None
    pid = watcher.get("pid") if token else None
    watcher = {"configuration": configuration, "generation": generation,
               "workflow_id": "git-watch:" + generation, "baseline": observed,
               "status": "configured" if configuration["enabled"] else "disabled",
               "desired_running": desired, "supervisor": supervisor}
    if session_state is not None:
        watcher["session"] = session_state
    if guard_version is not None:
        watcher["guard_version"] = guard_version
    if token:
        watcher.update(token=token, pid=pid, heartbeat=time.time(), lease_until=time.time() + 15)
    _save(path, binding, watcher)
    return _view(watcher)


@project.serialized
def _set_start_intent(root):
    path, binding, policy, watcher = _load(root)
    configuration = validate_configuration(watcher.get("configuration"))
    if not configuration["enabled"] or not policy.get("enabled"):
        raise ValueError("Git watcher is disabled")
    if watcher.get("desired_running") is True and watcher.get("supervisor", {}).get("enabled"):
        return _view(watcher)
    watcher["desired_running"] = True
    watcher.setdefault("supervisor", {})["enabled"] = True
    _save(path, binding, watcher)
    return _view(watcher)


@project.serialized
def _reserve(root, recovering=False):
    # The caller exclusively owns the worker guard, including across spawn.
    path, binding, policy, watcher = _load(root)
    configuration = validate_configuration(watcher.get("configuration"))
    if (not configuration["enabled"] or not policy.get("enabled") or not _desired(watcher)
            or not _session_owned(watcher)
            or (recovering and not watcher.get("supervisor", {}).get("enabled"))):
        return _view(watcher), None
    if _legacy_owner(watcher):
        watcher.update(recovery_blocked=True, reason="legacy-worker-without-native-guard; stop and verify its exit before migration")
        _save(path, binding, watcher)
        return _view(watcher), None
    token = uuid.uuid4().hex
    watcher.update(status="starting", token=token, pid=None, guard_version=1, desired_running=True,
                   heartbeat=time.time(), lease_until=time.time() + 15)
    for key in ["stop_token", "validation_id", "recovery_blocked"]:
        watcher.pop(key, None)
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


def _spawn_worker(root, token, guard):
    argv = [sys.executable, str(Path(__file__).resolve()), "--worker", str(root), "--token", token,
            "--guard-handle", str(guard.handle)]
    return lifetime.spawn(argv, guard=guard, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, cwd=str(root), shell=False)


def _launch(root, recovering=False, with_child=False):
    child = None

    def result(view):
        return (view, child) if with_child else view

    root = project.project_root(root)
    guard = guards.acquire(root, ".upg-worker.guard")
    if guard is None:
        view = status(root)
        view["watcher"].update(idempotent=True, recovery="deferred; native worker or validator still owns guard")
        return result(view)
    with guard:
        # Explicit ticks and standalone Git transactions may outlive their host.
        for name in [".upg-validation.guard", ".upg-checkpoint.guard"]:
            probe = guards.acquire(root, name)
            if probe is None:
                view = status(root)
                view["watcher"].update(recovery="deferred; native project command still active")
                return result(view)
            probe.close()
        view, token = _reserve(root, recovering=recovering)
        if token is None:
            return result(view)
        try:
            child = _spawn_worker(root, token, guard)
        except OSError:
            return result(_start_failed(root, token, "native-worker-launch-failed"))
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            view = status(root)
            state = view["watcher"]
            if state.get("token") != token:
                return result(view)
            if state.get("pid") and state.get("heartbeat", 0) and state.get("status") != "starting":
                return result(view)
            time.sleep(0.05)
        return result(_start_failed(root, token, "native-worker-startup-not-confirmed"))


@project.serialized
def _reserve_supervisor(root):
    # Production callers hold the native supervisor guard across reservation.
    path, binding, policy, watcher = _load(root)
    if not _supervised(policy, watcher):
        return _view(watcher), None
    token = uuid.uuid4().hex
    supervisor = watcher.setdefault("supervisor", {})
    supervisor.update(token=token, pid=None, guard_version=1, status="starting")
    supervisor.pop("reason", None)
    # Native supervisor guard proves the previous supervisor released. Revoke
    # its worker cooperatively; a native validation/checkpoint must release its
    # original guard before this new supervisor can reserve a replacement.
    old_worker = watcher.pop("token", None)
    if old_worker is not None:
        watcher.pop("validation_id", None)
        watcher.update(status="stopping", stop_token=old_worker, lease_until=0,
                       reason="supervisor-owner-replaced; awaiting-native-worker-release")
    _save(path, binding, watcher)
    return _view(watcher), token


def _supervised(policy, watcher):
    return bool(policy.get("enabled") and watcher.get("configuration", {}).get("enabled")
                and watcher.get("supervisor", {}).get("enabled") and _desired(watcher)
                and _session_owned(watcher))


@project.serialized
def _claim_supervisor(root, token):
    path, binding, policy, watcher = _load(root)
    supervisor = watcher.get("supervisor", {})
    if supervisor.get("token") != token or not _supervised(policy, watcher):
        return False
    supervisor.update(pid=os.getpid(), guard_version=1, status="starting")
    _save(path, binding, watcher)
    return True


@project.serialized
def _supervisor_progress(root, token, state, reason=None, release=False):
    path, binding, policy, watcher = _load(root)
    supervisor = watcher.get("supervisor", {})
    if supervisor.get("token") != token:
        return
    if not release and supervisor.get("status") == state and supervisor.get("reason") == reason:
        return
    supervisor["status"] = state
    if reason:
        supervisor["reason"] = reason
    else:
        supervisor.pop("reason", None)
    if state == "stopped" or release:
        supervisor.pop("token", None)
        supervisor["pid"] = None
    _save(path, binding, watcher)


def _spawn_supervisor(root, token, guard):
    argv = [sys.executable, str(Path(__file__).resolve()), "--supervise", str(root), "--token", token,
            "--guard-handle", str(guard.handle)]
    return lifetime.spawn(argv, guard=guard, supervisor=True, stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(root), shell=False)


def _await_supervisor(root, token=None, previous_token=None):
    # Supervisor startup and its later worker startup are distinct handshakes.
    # Give the worker its own eight-second native handshake plus two seconds
    # for reservation/spawn scheduling, after the supervisor confirms its PID.
    # The two phases have a combined maximum of eighteen seconds of waiting.
    supervisor_deadline = time.monotonic() + 8
    worker_deadline = None
    while True:
        view = status(root)
        state = view["watcher"]
        supervisor = state.get("supervisor", {})
        if state.get("session") and not lifetime.active():
            state.update(running=False, status="session-ended", reason="project-session-ended")
            return view
        if token is not None and supervisor.get("token") != token:
            return view
        if not state.get("desired_running"):
            return view
        confirmed = type(supervisor.get("pid")) is int and supervisor["pid"] > 0
        if confirmed and worker_deadline is None:
            worker_deadline = time.monotonic() + 10
        if supervisor.get("status") == "waiting":
            state["recovery"] = "deferred; native project command still active"
            return view
        if supervisor.get("status") == "blocked":
            return view
        if confirmed and _live(state):
            # A lease can outlive its worker. Only this activation probes native
            # ownership; the healthy supervisor still blocks in child.wait().
            fresh = token is not None and state.get("token") != previous_token
            for name in [".upg-validation.guard", ".upg-checkpoint.guard"]:
                probe = guards.acquire(root, name)
                if probe is None:
                    state["recovery"] = "deferred; native project command still active"
                    if not fresh:
                        state["running"] = False
                    return view
                probe.close()
            probe = guards.acquire(root, ".upg-worker.guard")
            if probe is not None:
                probe.close()
            elif supervisor.get("status") == "watching" and (token is None or fresh):
                # Recovery can publish between the snapshot and native probes.
                # Recheck its mandatory state barrier before accepting that owner.
                current = status(root)
                owned = current["watcher"]
                current_supervisor = owned.get("supervisor", {})
                if (owned.get("token") == state.get("token") and owned.get("pid") == state.get("pid")
                        and current_supervisor.get("token") == supervisor.get("token")
                        and current_supervisor.get("status") == "watching" and _live(owned)):
                    return current
        deadline = worker_deadline if worker_deadline is not None else supervisor_deadline
        if time.monotonic() >= deadline:
            # This is a failed caller handshake, not revocation of a legitimate
            # owner. Do not persist a diagnostic that could race a late claim.
            view = copy.deepcopy(view)
            state = view["watcher"]
            state["recovery"] = "deferred; native supervised startup not confirmed within bounded handshake"
            state.setdefault("supervisor", {}).update(
                status="blocked", reason="native-supervised-startup-not-confirmed")
            return view
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))


def _launch_supervisor(root):
    root = project.project_root(root)
    guard = guards.acquire(root, ".upg-supervisor.guard")
    if guard is None:
        view = _await_supervisor(root)
        view["watcher"]["idempotent"] = True
        return view
    with guard:
        view, token = _reserve_supervisor(root)
        if token is None:
            return view
        previous_token = view["watcher"].get("token")
        try:
            _spawn_supervisor(root, token, guard)
        except OSError:
            _supervisor_progress(root, token, "blocked", "native-supervisor-launch-failed", release=True)
            return status(root)
        return _await_supervisor(root, token, previous_token)


def _session_owned(watcher):
    value = lifetime.current()
    session_state = watcher.get("session", {})
    return bool(lifetime.active() and value is not None
                and session_state.get("status") == "active"
                and session_state.get("token") == value.token)


def _session_required(root):
    view = _view(_load(project.project_root(root))[3])
    view["watcher"].update(status="session-required", running=False,
                          reason="project-session-required; use git-watch session with a foreground host adapter")
    return view


@project.serialized
def _bind_session(root, token):
    path, binding, policy, watcher = _load(root)
    configuration = validate_configuration(watcher.get("configuration"))
    if not policy.get("enabled") or not configuration["enabled"]:
        raise ValueError("enable scoped Git and its explicit validators before entering a session")
    acquired = []
    try:
        for name in [".upg-supervisor.guard", ".upg-worker.guard", ".upg-validation.guard", ".upg-checkpoint.guard"]:
            guard = guards.acquire(root, name)
            if guard is None:
                raise ValueError("previous native project owner still active; stop and verify release before session entry")
            acquired.append(guard)
        watcher["session"] = {"token": token, "pid": os.getpid(), "status": "active", "guard_version": 1}
        watcher["desired_running"] = True  # This foreground entry is an explicit start.
        watcher.setdefault("supervisor", {})["enabled"] = True
        watcher.update(status="configured", pid=None, lease_until=0)
        for key in ["token", "stop_token", "validation_id", "recovery_blocked"]:
            watcher.pop(key, None)
        _save(path, binding, watcher)
    finally:
        for guard in reversed(acquired):
            guard.close()


@project.serialized
def _end_session(root, token):
    path, binding, policy, watcher = _load(root)
    if watcher.get("session", {}).get("token") != token:
        return _view(watcher)
    watcher["session"].update(status="ended", pid=None)
    watcher.update(status="session-ended", pid=None, lease_until=0, reason="project-session-ended")
    for key in ["token", "stop_token", "validation_id"]:
        watcher.pop(key, None)
    supervisor = watcher.setdefault("supervisor", {})
    supervisor.pop("token", None)
    supervisor.update(status="stopped", pid=None)
    supervisor.pop("reason", None)
    _save(path, binding, watcher)
    return _view(watcher)


def _retire_released_session(root):
    path, binding, policy, watcher = _load(root)
    session_state = watcher.get("session", {})
    if session_state.get("status") != "active":
        return
    acquired = []
    try:
        for name in [".upg-session.guard", ".upg-supervisor.guard", ".upg-worker.guard",
                     ".upg-validation.guard", ".upg-checkpoint.guard"]:
            guard = guards.acquire(root, name)
            if guard is None:
                return
            acquired.append(guard)
        _end_session(root, session_state["token"])
    finally:
        for guard in reversed(acquired):
            guard.close()


def _session_command(root, command, host, executable):
    """Resolve a fixed foreground contract before creating project state."""
    if host == "command":
        if executable is not None:
            raise ValueError("command host does not accept an executable override")
        return lifetime._argv(command)
    if host not in {"codex-cli", "stdin"}:
        raise ValueError("project session host must be command, codex-cli or stdin")
    if command is not None:
        raise ValueError(host + " host does not accept command arguments")
    if host == "stdin":
        if executable is not None:
            raise ValueError("stdin host does not accept an executable override")
        return None
    if (not isinstance(executable, str) or not executable or "\0" in executable):
        raise ValueError("codex-cli host requires an explicit existing executable")
    resolved = shutil.which(executable)
    if resolved is None:
        raise ValueError("codex-cli executable is unavailable")
    return [resolved, "--no-daemon", "--no-alt-screen", "--cd", str(root)]


def _session_stdin():
    """Accept only a dedicated pipe whose writer owns this project session."""
    try:
        fd = sys.stdin.fileno()
        if type(fd) is not int or fd < 0 or not stat.S_ISFIFO(os.fstat(fd).st_mode):
            raise ValueError("stdin project session requires a dedicated pipe")
        return fd
    except (AttributeError, OSError, ValueError) as error:
        raise ValueError("stdin project session requires a dedicated pipe") from error


def _session_input_available(fd):
    """Poll without blocking, including Windows anonymous-pipe EOF."""
    if os.name != "nt":
        return 4096 if select.select([fd], [], [], 0)[0] else 0
    available = wintypes.DWORD()
    if not _PIPE_KERNEL.PeekNamedPipe(msvcrt.get_osfhandle(fd), None, 0, None,
                                      ctypes.byref(available), None):
        code = ctypes.get_last_error()
        if code == 109:  # ERROR_BROKEN_PIPE: the owning writer closed.
            return -1
        raise ctypes.WinError(code)
    return min(4096, available.value)


def _read_session_input(fd, ended):
    """Discard bounded bytes until EOF; never parse or retain host content."""
    previous_mode = msvcrt.setmode(fd, os.O_BINARY) if os.name == "nt" else None
    try:
        while not ended.is_set():
            available = _session_input_available(fd)
            if available < 0:
                return
            if available:
                if not os.read(fd, min(4096, available)):
                    return
            else:
                ended.wait(0.05)
    finally:
        if previous_mode is not None:
            msvcrt.setmode(fd, previous_mode)


def session(root, command=None, *, host="command", executable=None):
    """Own observers while a foreground child or dedicated input pipe is open.

    Command hosts must wait for their actual project session. The fixed Codex
    profile disables its shared daemon; stdin requires a project-owned pipe.
    Detaching launchers and generic shared-server connections are not adapters.
    """
    root = project.project_root(root)
    command = _session_command(root, command, host, executable)
    input_fd = _session_stdin() if host == "stdin" else None
    project.ensure(root)
    session_guard = guards.acquire(root, ".upg-session.guard")
    if session_guard is None:
        raise ValueError("another foreground project session owns this project")
    with session_guard, lifetime.Session(root) as life:
        _bind_session(root, life.token)
        process = None
        ended = threading.Event()
        outcome = {"returncode": None, "error": None}
        monitor = None
        try:
            if command is not None:
                process = lifetime.run_host(command, cwd=str(root))

            def close_when_host_ends():
                try:
                    if input_fd is not None:
                        _read_session_input(input_fd, ended)
                        outcome["returncode"] = 0
                    else:
                        outcome["returncode"] = process.wait()
                except BaseException as error:
                    outcome["error"] = error
                finally:
                    ended.set()
                    try:
                        life.close()
                    except BaseException as error:
                        outcome["error"] = outcome["error"] or error

            monitor = threading.Thread(target=close_when_host_ends, name="upg-host-session", daemon=True)
            monitor.start()
            delay, retry_at = 1, 0
            while not ended.is_set():
                state = status(root)["watcher"]
                if not _session_owned(state):
                    if not ended.is_set():
                        raise ValueError("project session authority revoked before host exit")
                    break
                child = life.supervisor
                if (_desired(state) and (child is None or child.poll() is not None)
                        and time.monotonic() >= retry_at):
                    try:
                        _launch_supervisor(root)
                        child = life.supervisor
                        if child is not None and child.poll() is None:
                            delay = 1
                        else:
                            delay = min(60, delay * 2)
                    except (OSError, ValueError) as error:
                        if not life.active:
                            break
                        _supervisor_diagnostic(root, state.get("supervisor", {}).get("token"),
                                               "blocked", str(error)[:256])
                        delay = min(60, delay * 2)
                    retry_at = time.monotonic() + delay
                ended.wait(0.2)
        finally:
            ended.set()
            life.close()
            if input_fd is not None and monitor is not None:
                # The cancellable pipe poll cannot survive this session entry.
                monitor.join(timeout=1)
                if monitor.is_alive():
                    raise ValueError("project session input monitor did not stop")
            # Native release is required before acknowledging a stopped session.
            # A journal is retained for interrupted transaction recovery.
            deadline = time.monotonic() + 5
            while True:
                acquired = []
                try:
                    for name in [".upg-supervisor.guard", ".upg-worker.guard",
                                 ".upg-validation.guard", ".upg-checkpoint.guard"]:
                        guard = guards.acquire(root, name)
                        if guard is None:
                            raise ValueError("session native owners have not released")
                        acquired.append(guard)
                    result = _end_session(root, life.token)
                    break
                except ValueError as error:
                    if (not (str(error).startswith("project state writer busy;") or
                             str(error) == "session native owners have not released")
                            or time.monotonic() >= deadline):
                        raise
                    time.sleep(0.05)
                finally:
                    for guard in reversed(acquired):
                        guard.close()
        if outcome["error"] is not None:
            raise outcome["error"]
        result["host_returncode"] = outcome["returncode"]
        return result


def start(root):
    root = project.project_root(root)
    if not lifetime.active() or Path(lifetime.current().root).resolve() != Path(root).resolve():
        return _session_required(root)
    path, binding, policy, watcher = _load(root)
    validate_configuration(watcher.get("configuration"))
    # Re-entering an already requested observer changes no intent. Avoid the
    # writer lock while its native capture or publication legitimately owns it.
    if not (watcher.get("desired_running") is True and _supervised(policy, watcher)):
        _set_start_intent(root)
    return _launch_supervisor(root)


def recover(root):
    """Recover only within an existing foreground capability; never detach at entry."""
    root = project.project_root(root)
    path = project.resolve(root, project.config()["binding_file"])
    if not path.is_file():
        return {"watcher": {"status": "unconfigured", "running": False, "recovery": "binding-missing"}}
    path, binding, policy, watcher = _load(root)
    if not lifetime.active():
        _retire_released_session(root)
        return _session_required(root)
    if not _supervised(policy, watcher):
        view = _view(watcher)
        view["watcher"]["recovery"] = "disabled-or-explicitly-stopped"
        return view
    try:
        return _launch_supervisor(root)
    except ValueError as error:
        if str(error).startswith("project state writer busy;"):
            view = status(root)
            view["watcher"]["recovery"] = "deferred; project writer owns the state"
            return view
        raise


def autostart(root):
    """Project entry hook only; never registers operating-system startup work."""
    return recover(root)


def _supervisor_owned(root, token):
    path, binding, policy, watcher = _load(root)
    return _supervised(policy, watcher) and watcher.get("supervisor", {}).get("token") == token


def _supervisor_diagnostic(root, token, state, reason=None, release=False):
    try:
        _supervisor_progress(root, token, state, reason, release=release)
    except (OSError, ValueError):
        # A busy writer must not turn a diagnostic into loss of supervision.
        # No successful state is claimed if persistence was unavailable.
        pass


def supervise(root, token, guard_handle=None):
    guard = (guards.adopt(root, ".upg-supervisor.guard", guard_handle) if guard_handle is not None
             else guards.acquire(root, ".upg-supervisor.guard"))
    if guard is None:
        return 1
    root = project.project_root(root)
    with guard:
        if not _claim_supervisor(root, token):
            return 1
        delay = 1
        needs_recovery = False
        final_state, final_reason = "stopped", None
        try:
            while _supervisor_owned(root, token):
                began = time.monotonic()
                launch_error = None
                try:
                    if needs_recovery:
                        # This publication is a safety barrier, not best-effort
                        # diagnostics: never reserve a replacement while stale
                        # watching metadata could still describe the old child.
                        _supervisor_progress(root, token, "recovering", "native-worker-exited")
                        needs_recovery = False
                    view, child = _launch(root, recovering=True, with_child=True)
                except (OSError, ValueError, git.CheckpointError) as error:
                    launch_error = str(error)[:256]
                    _supervisor_diagnostic(root, token, "blocked", launch_error)
                    child = None
                    view = {"watcher": {}}
                if child is not None:
                    _supervisor_diagnostic(root, token, "watching")
                    # No polling, Git scan or heartbeat writes while our child
                    # is healthy. Cooperative stop makes this wait return.
                    child.wait()
                    if not _supervisor_owned(root, token):
                        break
                    needs_recovery = True
                    if time.monotonic() - began >= 30:
                        delay = 1
                    pause = delay
                    delay = min(60, delay * 2)
                else:
                    if view["watcher"].get("recovery_blocked"):
                        final_state, final_reason = "blocked", "legacy-worker-without-native-guard"
                        break
                    if "deferred; native" in view["watcher"].get("recovery", ""):
                        # A pre-existing guarded worker is not ours to wait on
                        # or signal. Only guard release permits replacement.
                        _supervisor_diagnostic(root, token, "waiting", "native-project-owner-still-active")
                        pause = 5
                    else:
                        _supervisor_diagnostic(root, token, "blocked", launch_error or "native-worker-launch-not-confirmed")
                        pause = delay
                        delay = min(60, delay * 2)
                until = time.monotonic() + pause
                while time.monotonic() < until and _supervisor_owned(root, token):
                    time.sleep(min(1, max(0, until - time.monotonic())))
        finally:
            _supervisor_diagnostic(root, token, final_state, final_reason, release=True)
    return 0


@project.serialized
def _request_stop(root):
    path, binding, policy, watcher = _load(root)
    watcher["desired_running"] = False
    supervisor = watcher.get("supervisor", {})
    if not supervisor.get("token"):
        supervisor.update(status="stopped", pid=None)
        supervisor.pop("reason", None)
    watcher.pop("recovery_blocked", None)
    token = watcher.pop("token", None)
    watcher.pop("validation_id", None)
    watcher.update(status="stopping" if token else "stopped", stop_token=token,
                   lease_until=0, reason="explicit-stop-request")
    if not token:
        watcher["pid"] = None
    _save(path, binding, watcher)
    return _view(watcher), token



@project.serialized
def _ack_released_stop(root):
    path, binding, policy, watcher = _load(root)
    if _desired(watcher) or _legacy_owner(watcher):
        return
    acquired = []
    try:
        for name in [".upg-supervisor.guard", ".upg-worker.guard", ".upg-validation.guard", ".upg-checkpoint.guard"]:
            guard = guards.acquire(root, name)
            if guard is None:
                return
            acquired.append(guard)
        watcher.update(status="stopped", pid=None, lease_until=0)
        watcher.pop("token", None)
        supervisor = watcher.get("supervisor", {})
        supervisor.pop("token", None)
        supervisor.update(pid=None, status="stopped")
        _save(path, binding, watcher)
    finally:
        for guard in reversed(acquired):
            guard.close()


def stop(root):
    root = project.project_root(root)
    request_deadline = time.monotonic() + 10
    while True:
        try:
            view, token = _request_stop(root)
            break
        except ValueError as error:
            if (not str(error).startswith("project state writer busy;")
                    or time.monotonic() + 2.1 >= request_deadline):
                raise
            time.sleep(0.05)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        view = status(root)
        if (view["watcher"].get("status") != "stopping"
                and not view["watcher"].get("supervisor", {}).get("token")):
            return view
        if view["watcher"].get("guard_version") == 1:
            try:
                _ack_released_stop(root)
            except ValueError as error:
                if not str(error).startswith("project state writer busy;"):
                    raise
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
    if token is not None and (watcher.get("token") != token or not _session_owned(watcher)):
        return {"watcher": {"status": "stopped", "reason": "ownership-revoked"}}, None
    if token is None and _live(watcher):
        # An explicit retry shares the worker token. The validation lease below
        # serializes it with automatic ticks; no second worker is spawned.
        token = watcher["token"]
    if not policy.get("enabled") or not configuration["enabled"]:
        return _view(dict(watcher, status="disabled")), None
    if _legacy_owner(watcher):
        watcher.update(recovery_blocked=True)
        _progress(watcher, "blocked", "legacy-worker-without-native-guard; verify exit before migration")
        _save(path, binding, watcher)
        return _view(watcher), None
    if watcher.get("validation_id"):
        probe = guards.acquire(root, ".upg-validation.guard")
        if probe is None:
            return _view(dict(watcher, status="busy")), None
        probe.close()
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
    validation_guard = guards.acquire(root, ".upg-validation.guard")
    if validation_guard is None:
        return finish("blocked", "native-validator-still-active; recovery deferred")
    validation_id = uuid.uuid4().hex
    lease = sum(v["timeout_seconds"] for v in configuration["validators"]) + 15
    _progress(watcher, "validating", "running-explicit-project-validators", validation_id=validation_id,
              lease_until=time.time() + lease)
    watcher["baseline"] = baseline
    try:
        _save(path, binding, watcher)
    except BaseException:
        validation_guard.close()
        raise
    return None, {"configuration": configuration, "generation": watcher["generation"],
                  "validation_id": validation_id, "token": token, "candidate": copy.deepcopy(candidate),
                  "guard": validation_guard,
                  "session_token": lifetime.current().token if not explicit and lifetime.active() else None}


def _validation_owned(root, prepared):
    path, binding, policy, watcher = _load(root)
    return (policy.get("enabled") and watcher.get("configuration", {}).get("enabled")
            and (prepared.get("session_token") is None or
                 (_session_owned(watcher) and watcher["session"]["token"] == prepared["session_token"]))
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
                process = guards.run(validator["argv"], cwd=str(root), stdin=subprocess.DEVNULL,
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
    if ((prepared.get("session_token") is not None and
         (not _session_owned(watcher) or watcher.get("session", {}).get("token") != prepared["session_token"]))
            or (token is not None and watcher.get("token") != token)
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
    with prepared["guard"], guards.holding(prepared["guard"]):
        passed, validations = _run_validators(root, prepared["configuration"]["validators"], prepared)
        return _publish(root, prepared, passed, validations)


@project.serialized
def _claim(root, token):
    path, binding, policy, watcher = _load(root)
    if (watcher.get("token") != token or not watcher.get("configuration", {}).get("enabled")
            or not _desired(watcher) or watcher.get("guard_version") != 1 or not _session_owned(watcher)):
        return False
    if watcher.get("pid") not in {None, os.getpid()}:
        return False
    _progress(watcher, "running", "native-worker-confirmed", pid=os.getpid())
    supervisor = watcher.get("supervisor", {})
    if (supervisor.get("token") and type(supervisor.get("pid")) is int
            and supervisor["pid"] > 0):
        # Publish readiness with the actual guard-owning worker claim. A later
        # diagnostic write may be busy without losing this atomic handshake.
        supervisor.update(status="watching")
        supervisor.pop("reason", None)
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


def worker(root, token, guard_handle=None):
    guard = (guards.adopt(root, ".upg-worker.guard", guard_handle) if guard_handle is not None
             else guards.acquire(root, ".upg-worker.guard"))
    if guard is None:
        return 1
    with guard, guards.holding(guard):
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
    lifetime.join_from_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--worker")
    mode.add_argument("--recover")
    mode.add_argument("--supervise")
    parser.add_argument("--token")
    parser.add_argument("--guard-handle", type=int)
    args = parser.parse_args()
    if args.recover:
        if args.token or args.guard_handle is not None:
            parser.error("recovery does not accept worker authority")
        value = recover(project.project_root(args.recover))
        print(json.dumps(value, sort_keys=True))
        state = value.get("watcher", {})
        return 1 if (state.get("recovery_blocked")
                     or state.get("status") in {"blocked", "stale", "cancelled"}
                     or state.get("supervisor", {}).get("status") == "blocked") else 0
    if not args.token:
        parser.error("worker requires --token")
    if args.supervise:
        return supervise(project.project_root(args.supervise), args.token, args.guard_handle)
    return worker(project.project_root(args.worker), args.token, args.guard_handle)


if __name__ == "__main__":
    sys.exit(main())
