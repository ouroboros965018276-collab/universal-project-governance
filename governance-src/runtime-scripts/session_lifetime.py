#!/usr/bin/env python3
"""Native lifetime authority for an explicit foreground project session.

Only the owner retains the EOF pipe's write end. Observer members inherit its
read end; the user's host inherits neither it nor the Windows kill-on-close Job.
No operating-system startup registration or persistent watcher is created.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading
import uuid

_ENV = "_UPG_SESSION_LIFETIME"
_CURRENT = None
_LOCK = threading.RLock()
_INTERNAL = frozenset({"git_watch.py", "process_guard.py"})

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _KERNEL.CreateJobObjectW.restype = wintypes.HANDLE
    _KERNEL.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                               wintypes.LPVOID, wintypes.DWORD]
    _KERNEL.SetInformationJobObject.restype = wintypes.BOOL
    _KERNEL.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _KERNEL.AssignProcessToJobObject.restype = wintypes.BOOL
    _KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL.CloseHandle.restype = wintypes.BOOL
    _KERNEL.GetFileType.argtypes = [wintypes.HANDLE]
    _KERNEL.GetFileType.restype = wintypes.DWORD

    class _BasicLimits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                    ("maximum", ctypes.c_size_t), ("processes", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("reads", "writes", "other", "read_bytes", "write_bytes", "other_bytes")]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [("basic", _BasicLimits), ("io", _IoCounters),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

    def _new_job():
        handle = _KERNEL.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = _ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _KERNEL.SetInformationJobObject(handle, 9, ctypes.byref(limits),
                                                   ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            os.set_handle_inheritable(handle, False)
            return handle
        except BaseException:
            _KERNEL.CloseHandle(handle)
            raise


def current():
    """Return this process's explicitly entered owner or joined member."""
    return _CURRENT


def active():
    value = current()
    return value is not None and value.active


def _wire_handle(fd):
    return msvcrt.get_osfhandle(fd) if os.name == "nt" else fd


def _adopt_pipe(value):
    if type(value) is not int or value < 0:
        raise ValueError("session authority requires an inherited native pipe handle")
    if os.name == "nt":
        if _KERNEL.GetFileType(value) != 3:  # FILE_TYPE_PIPE (0x0003)
            raise ValueError("session authority does not identify a pipe")
        os.set_handle_inheritable(value, False)
        try:
            return msvcrt.open_osfhandle(value, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            _KERNEL.CloseHandle(value)
            raise
    if not stat.S_ISFIFO(os.fstat(value).st_mode):
        raise ValueError("session authority does not identify a pipe")
    os.set_inheritable(value, False)
    return value


def _read_gate(fd):
    data = bytearray()
    try:
        while len(data) < 1024:
            part = os.read(fd, 1)
            if not part:
                raise ValueError("session owner exited before native containment")
            if part == b"\n":
                return json.loads(data.decode("ascii"))
            data.extend(part)
        raise ValueError("session containment gate is oversized")
    finally:
        os.close(fd)


class _Member:
    def __init__(self, root, token, read_fd, group):
        self.root = Path(root)
        self.token = token
        self.read_fd = read_fd
        self.group = group
        self.active = True

    def _revoked(self):
        try:
            # No data is written; data, read error, or EOF all revoke authority.
            os.read(self.read_fd, 1)
        finally:
            self.active = False
            try:
                if os.name != "nt":
                    # Only our currently joined private group, never a recorded PID.
                    if (self.group and os.getpgrp() == self.group
                            and os.getsid(0) == self.group):
                        os.killpg(os.getpgrp(), signal.SIGKILL)
            finally:
                os._exit(0)


def join_from_environment():
    """Join an inherited observer session; absent authority is not invented."""
    with _LOCK:
        return _join_from_environment()


def _join_from_environment():
    global _CURRENT
    if _CURRENT is not None:
        return _CURRENT
    raw = os.environ.get(_ENV)
    if raw is None:
        return None
    spec = json.loads(raw)
    if (not isinstance(spec, dict) or set(spec) != {"root", "token", "read", "group", "gate"}
            or not isinstance(spec["root"], str) or not Path(spec["root"]).is_absolute()
            or not isinstance(spec["token"], str) or len(spec["token"]) != 32
            or any(c not in "0123456789abcdef" for c in spec["token"])):
        raise ValueError("invalid inherited project-session authority")
    read_fd = _adopt_pipe(spec["read"])
    try:
        group = spec["group"]
        if spec["gate"] is not None:
            released = _read_gate(_adopt_pipe(spec["gate"]))
            if (not isinstance(released, dict) or set(released) != {"token", "group"}
                    or released["token"] != spec["token"]):
                raise ValueError("session gate did not confirm native containment")
            group = released["group"]
            if os.name != "nt" and (group != os.getpid() or os.getpgrp() != group
                                      or os.getsid(0) != group):
                raise ValueError("first observer does not own its private session")
        if os.name != "nt" and (type(group) is not int or group <= 1
                                or os.getpgrp() != group or os.getsid(0) != group):
            raise ValueError("observer is outside its inherited private session")
        if os.name == "nt" and group is not None:
            raise ValueError("Windows session cannot carry POSIX group authority")
        value = _Member(spec["root"], spec["token"], read_fd, group)
        threading.Thread(target=value._revoked, name="upg-session-eof", daemon=True).start()
        _CURRENT = value
        return value
    except BaseException:
        os.close(read_fd)
        raise


@contextmanager
def inheritance_options(guards=(), **options):
    """Merge owned guard handles and the session read end for one joined entry.

    Use only for an internal Python entry that calls join_from_environment().
    Native commands below that entry stay in its existing Job/private group.
    """
    import process_guard
    value = current()
    if value is not None and not value.active:
        raise ValueError("project session has ended")
    incoming_env = options.pop("env", None)
    env = without_session_environment(incoming_env)
    extras = list(options.pop("_session_extra_fds", ()))
    gate = options.pop("_session_gate", None)
    group = options.pop("_session_group", None)
    if value is not None:
        extras.append(value.read_fd)
        env[_ENV] = json.dumps({"root": str(value.root), "token": value.token,
                               "read": _wire_handle(value.read_fd),
                               "group": value.group if isinstance(value, _Member) else group,
                               "gate": _wire_handle(gate) if gate is not None else None},
                              separators=(",", ":"))
    with process_guard.inheritance(guards) as inherited:
        result = dict(options, **inherited)
        result["env"] = env
        if os.name == "nt":
            previous = [(fd, os.get_handle_inheritable(_wire_handle(fd))) for fd in extras]
            try:
                handles = list(result["startupinfo"].lpAttributeList["handle_list"])
                for fd, unused in previous:
                    handle = _wire_handle(fd)
                    os.set_handle_inheritable(handle, True)
                    if handle not in handles:
                        handles.append(handle)
                result["startupinfo"].lpAttributeList["handle_list"] = handles
                yield result
            finally:
                for fd, was_inheritable in previous:
                    os.set_handle_inheritable(_wire_handle(fd), was_inheritable)
        else:
            result["pass_fds"] = tuple(dict.fromkeys(list(result.get("pass_fds", ())) + extras))
            yield result


def _argv(value, internal=False):
    if (not isinstance(value, (list, tuple)) or not value
            or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in value)):
        raise ValueError("session command requires explicit nonempty argv strings")
    value = list(value)
    if internal:
        own = Path(__file__).resolve().parent
        if (len(value) < 2 or Path(value[0]).resolve() != Path(sys.executable).resolve()
                or Path(value[1]).resolve().parent != own
                or Path(value[1]).name not in _INTERNAL):
            raise ValueError("session launch must use an own fixed Python runtime entry")
    return value


def spawn(argv, guard=None, guards=(), supervisor=False, **options):
    """Start a fixed observer entry inside its foreground project session."""
    value = current()
    if value is None or not value.active:
        raise ValueError("a live foreground project session is required")
    command = _argv(argv, internal=True)
    if guard is not None:
        if guards:
            raise ValueError("use guard or guards, not both")
        guards = [guard]
    if (options.pop("shell", False) or "executable" in options or "preexec_fn" in options
            or "startupinfo" in options or "pass_fds" in options):
        raise ValueError("session launch cannot replace its fixed native entry")
    options.pop("start_new_session", None)
    options.pop("creationflags", None)
    owner = isinstance(value, Session)
    if owner and not supervisor:
        raise ValueError("session owner may launch only its fixed supervisor entry")
    gate_read = gate_write = None
    process = None
    with _LOCK:
        if not value.active:
            raise ValueError("project session has ended")
        try:
            if owner:
                gate_read, gate_write = os.pipe()
                os.set_inheritable(gate_read, False)
                os.set_inheritable(gate_write, False)
            if os.name == "nt":
                options["creationflags"] = subprocess.CREATE_NO_WINDOW
            elif owner:
                options["start_new_session"] = True
            with inheritance_options(guards, _session_extra_fds=(
                    [gate_read] if gate_read is not None else []),
                    _session_gate=gate_read, **options) as prepared:
                process = subprocess.Popen(command, shell=False, **prepared)
            if owner:
                if os.name == "nt":
                    if not _KERNEL.AssignProcessToJobObject(value.job, int(process._handle)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    group = None
                else:
                    group = process.pid
                payload = (json.dumps({"token": value.token, "group": group},
                                      separators=(",", ":")) + "\n").encode("ascii")
                os.write(gate_write, payload)
                value.supervisor = process
                value._children.append(process)
            return process
        except BaseException:
            if process is not None:
                # This process object was created here; no recorded PID is used.
                process.kill()
                process.wait()
            raise
        finally:
            for fd in (gate_read, gate_write):
                if fd is not None:
                    os.close(fd)


def run_host(argv, **options):
    """Launch an explicit user host without observer handles or Job membership."""
    if not isinstance(current(), Session) or not active():
        raise ValueError("host launch requires its foreground session owner")
    command = _argv(argv)
    if (options.pop("shell", False) or "executable" in options or "preexec_fn" in options
            or "startupinfo" in options or "pass_fds" in options):
        raise ValueError("host launch requires direct argv and ordinary standard streams")
    env = without_session_environment(options.pop("env", None))
    options["close_fds"] = True
    return subprocess.Popen(command, shell=False, env=env, **options)


def without_session_environment(env=None):
    """Strip observer-only authority before invoking an ordinary native command."""
    value = dict(os.environ if env is None else env)
    value.pop(_ENV, None)
    return value


class Session:
    """Own observer lifetime only while this foreground context remains open.

    On POSIX, deliberate descendants that leave their inherited process group
    are outside this mechanism; no arbitrary PID enumeration or global cleanup
    is used. Unsupported native containment always fails instead of detaching.
    """

    def __init__(self, root, token=None):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError("project session root must be an existing directory")
        self.token = token if token is not None else uuid.uuid4().hex
        if (not isinstance(self.token, str) or len(self.token) != 32
                or any(c not in "0123456789abcdef" for c in self.token)):
            raise ValueError("project session token must be a hexadecimal UUID capability")
        self.active = False
        self.read_fd = self.write_fd = None
        self.job = None
        self.group = None
        self.supervisor = None
        self._children = []

    def __enter__(self):
        global _CURRENT
        with _LOCK:
            if _CURRENT is not None:
                raise ValueError("a process can own only one explicit project session")
            try:
                self.read_fd, self.write_fd = os.pipe()
                os.set_inheritable(self.read_fd, False)
                os.set_inheritable(self.write_fd, False)
                if os.name == "nt":
                    self.job = _new_job()
                self.active = True
                _CURRENT = self
                return self
            except BaseException:
                self.close()
                raise

    def close(self):
        global _CURRENT
        errors = []
        with _LOCK:
            self.active = False
            for name in ("write_fd", "job", "read_fd"):
                handle = getattr(self, name)
                setattr(self, name, None)
                if handle is None:
                    continue
                try:
                    if name == "job":
                        if not _KERNEL.CloseHandle(handle):
                            raise ctypes.WinError(ctypes.get_last_error())
                    else:
                        os.close(handle)
                except OSError as exc:
                    errors.append(exc)
            if _CURRENT is self:
                _CURRENT = None
        # EOF/Job closure stops observers, never the separately launched host.
        for child in self._children:
            try:
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    def __exit__(self, *unused):
        self.close()
