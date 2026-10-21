#!/usr/bin/env python3
"""Operating-system-held project guards; never infer ownership from a PID.

A stable file remains after release.  Only an open exclusive OS handle is the
lock.  Closing the final inherited handle releases it, including after a crash.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading

_NAME = re.compile(r"\.upg-[a-z0-9][a-z0-9-]*\.guard\Z")
_INHERITANCE_LOCK = threading.RLock()


def _guard_path(root, name):
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("guard name must be a project-local .upg-*.guard basename")
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("guard project root must be an existing directory")
    directory = root / ".governance"
    directory.mkdir(exist_ok=True)
    if _is_reparse(directory):
        raise ValueError("guard directory must not be a symlink or reparse point")
    return directory / name


def _is_reparse(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _KERNEL.CreateFileW.restype = wintypes.HANDLE
    _KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL.CloseHandle.restype = wintypes.BOOL
    _KERNEL.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    _KERNEL.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    _INVALID = ctypes.c_void_p(-1).value

    def _windows_path(handle):
        buffer = ctypes.create_unicode_buffer(32768)
        size = _KERNEL.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not size or size >= len(buffer):
            raise ctypes.WinError(ctypes.get_last_error())
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return os.path.normcase(os.path.normpath(value))
else:
    import fcntl


class Guard:
    """Own one acquired or explicitly inherited lock; close only this handle."""

    def __init__(self, path, handle):
        self.path = Path(path)
        self.handle = handle

    def close(self):
        handle, self.handle = self.handle, None
        if handle is None:
            return
        # flock locks belong to the shared open-file description.  LOCK_UN here
        # would release an inherited child's protection; close our reference only.
        if os.name == "nt":
            if not _KERNEL.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            os.close(handle)

    def __enter__(self):
        if self.handle is None:
            raise ValueError("guard is already closed")
        return self

    def __exit__(self, *unused):
        self.close()


def acquire(root, name):
    """Return an exclusive Guard or None when a live OS handle still owns it."""
    path = _guard_path(root, name)
    if _is_reparse(path):
        raise ValueError("guard file must not be a symlink or reparse point")
    if os.name == "nt":
        handle = _KERNEL.CreateFileW(str(path), 0x80000000 | 0x40000000, 0,
                                     None, 4, 0x80 | 0x00200000, None)
        if handle == _INVALID:
            code = ctypes.get_last_error()
            if code in (32, 33):
                return None
            raise ctypes.WinError(code)
        guard = Guard(path, handle)
        try:
            if _windows_path(handle) != os.path.normcase(os.path.normpath(str(path))) or _is_reparse(path):
                raise ValueError("guard handle does not identify its project file")
            return guard
        except BaseException:
            guard.close()
            raise
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    root_fd = os.open(str(path.parent.parent), directory_flags)
    try:
        directory_fd = os.open(".governance", directory_flags, dir_fd=root_fd)
        try:
            handle = os.open(path.name, flags, 0o600, dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        os.close(root_fd)
    guard = Guard(path, handle)
    try:
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("guard must be one regular project file")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                guard.close()
                return None
            raise
        return guard
    except BaseException:
        guard.close()
        raise


def adopt(root, name, handle):
    """Own an explicitly inherited handle only after checking its file identity."""
    if type(handle) is not int or handle < 0:
        raise ValueError("inherited guard handle must be a nonnegative integer")
    path = _guard_path(root, name)
    if _is_reparse(path):
        raise ValueError("guard file must not be a symlink or reparse point")
    if os.name == "nt":
        if _windows_path(handle) != os.path.normcase(os.path.normpath(str(path))):
            raise ValueError("inherited guard handle belongs to another project file")
        os.set_handle_inheritable(handle, False)
    else:
        actual, expected = os.fstat(handle), os.stat(str(path), follow_symlinks=False)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise ValueError("inherited guard handle belongs to another project file")
        if not stat.S_ISREG(actual.st_mode) or actual.st_nlink != 1:
            raise ValueError("inherited guard is not one regular file")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.set_inheritable(handle, False)
    return Guard(path, handle)


def inherited_kwargs(guards):
    """Return explicit subprocess inheritance options for these owned guards.

    On Windows this temporarily needs inheritable handles.  Call inside
    inheritance() so the flags are restored even when subprocess creation fails.
    No arbitrary handles, shell commands, PID ownership, or lock deletion occurs.
    """
    handles = []
    for guard in guards:
        if not isinstance(guard, Guard) or guard.handle is None:
            raise ValueError("only live acquired guards may be inherited")
        if guard.handle not in handles:
            handles.append(guard.handle)
    if os.name == "nt":
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        startup = subprocess.STARTUPINFO()
        startup.lpAttributeList = {"handle_list": handles}
        return {"startupinfo": startup, "close_fds": True}
    return {"pass_fds": tuple(handles), "close_fds": True}


@contextmanager
def inheritance(guards):
    """Limit Windows inheritable flags to one explicit subprocess creation."""
    guards = tuple(guards)
    with _INHERITANCE_LOCK:
        prior = []
        if os.name == "nt":
            for guard in guards:
                if not isinstance(guard, Guard) or guard.handle is None:
                    raise ValueError("only live acquired guards may be inherited")
                prior.append((guard.handle, os.get_handle_inheritable(guard.handle)))
        try:
            yield inherited_kwargs(guards)
        finally:
            if os.name == "nt":
                for handle, value in prior:
                    os.set_handle_inheritable(handle, value)


_ACTIVE = threading.local()
_PENDING = {}
_PENDING_LOCK = threading.Lock()


def active_guards():
    """The guards this thread must keep alive across native subprocess work."""
    return tuple(getattr(_ACTIVE, "guards", ()))


@contextmanager
def holding(guards):
    """Register an owned guard or iterable for explicit subprocess propagation."""
    if isinstance(guards, Guard):
        guards = (guards,)
    previous = active_guards()
    merged = list(previous)
    for guard in guards:
        if not isinstance(guard, Guard) or guard.handle is None:
            raise ValueError("only live acquired guards may be registered")
        if guard not in merged:
            merged.append(guard)
    _ACTIVE.guards = tuple(merged)
    try:
        yield tuple(merged)
    finally:
        _ACTIVE.guards = previous


def _spawn_guarded(argv, guards, kwargs):
    # Fixed own Python wrapper only; actual argv is interpreted by no shell.
    specs = [{"root": str(guard.path.parent.parent), "name": guard.path.name,
              "handle": guard.handle} for guard in guards]
    if isinstance(argv, (str, bytes, os.PathLike)):
        argv = [argv]
    command = [sys.executable, str(Path(__file__).resolve()), "--hold",
               json.dumps(specs, separators=(",", ":")), "--"] + list(argv)
    options = dict(kwargs)
    if "executable" in options or "preexec_fn" in options or options.get("shell"):
        raise ValueError("guarded subprocess does not support alternate launchers or shells")
    options["shell"] = False
    if os.name == "nt":
        options["creationflags"] = options.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
    import session_lifetime
    if session_lifetime.active():
        return session_lifetime.spawn(command, guards=guards, **options)
    with inheritance(guards) as inherited:
        options.update(inherited)
        return subprocess.Popen(command, **options)


def _reap_pending(process):
    try:
        process.communicate()
    finally:
        with _PENDING_LOCK:
            _PENDING.pop(process, None)


def has_pending():
    """Whether actual native work still holds any guard active in this thread."""
    keys = {str(guard.path) for guard in active_guards()}
    with _PENDING_LOCK:
        return any(keys.intersection(paths) and process.poll() is None
                   for process, paths in _PENDING.items())


def run(argv, timeout=None, check=False, **kwargs):
    """Run a native command while a fixed Python wrapper retains active guards.

    Timeout means the caller stopped waiting, not that arbitrary native hooks
    exited.  The wrapper remains alive until the actual command ends, and another
    command sharing these guards is refused in this process until then.
    """
    guards = active_guards()
    if not guards:
        return subprocess.run(argv, timeout=timeout, check=check, **kwargs)
    keys = {str(guard.path) for guard in guards}
    with _PENDING_LOCK:
        if any(keys.intersection(paths) and process.poll() is None
               for process, paths in _PENDING.items()):
            raise subprocess.TimeoutExpired(argv, timeout or 0,
                                            output=b"previous-native-command-still-running")
    data = kwargs.pop("input", None)
    if data is not None:
        if "stdin" in kwargs:
            raise ValueError("stdin and input arguments may not both be used")
        kwargs["stdin"] = subprocess.PIPE
    if kwargs.pop("capture_output", False):
        if "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError("stdout and stderr cannot be combined with capture_output")
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = _spawn_guarded(argv, guards, kwargs)
    try:
        output, error = process.communicate(input=data, timeout=timeout)
    except BaseException:
        with _PENDING_LOCK:
            _PENDING[process] = keys
        threading.Thread(target=_reap_pending, args=(process,), daemon=True).start()
        raise
    result = subprocess.CompletedProcess(argv, process.returncode, output, error)
    if check:
        result.check_returncode()
    return result


def _hold_command(arguments):
    import session_lifetime
    session_lifetime.join_from_environment()
    if len(arguments) < 4 or arguments[0] != "--hold" or arguments[2] != "--":
        raise ValueError("guard wrapper requires its exact inherited handles and command argv")
    specs = json.loads(arguments[1])
    if not isinstance(specs, list) or not 1 <= len(specs) <= 8:
        raise ValueError("guard wrapper requires one to eight inherited guards")
    handles = []
    for item in specs:
        if not isinstance(item, dict) or set(item) != {"root", "name", "handle"}:
            raise ValueError("invalid inherited guard specification")
        handle = item["handle"]
        if type(handle) is not int or handle < 0 or handle in handles:
            raise ValueError("inherited guard handles must be distinct nonnegative integers")
        handles.append(handle)
    guards = []
    try:
        for item in specs:
            if not isinstance(item, dict) or set(item) != {"root", "name", "handle"}:
                raise ValueError("invalid inherited guard specification")
            guards.append(adopt(item["root"], item["name"], item["handle"]))
        return subprocess.run(arguments[3:], stdin=sys.stdin, stdout=sys.stdout,
                              stderr=sys.stderr, shell=False,
                              env=session_lifetime.without_session_environment()).returncode
    finally:
        for guard in reversed(guards):
            guard.close()


if __name__ == "__main__":
    sys.exit(_hold_command(sys.argv[1:]))
