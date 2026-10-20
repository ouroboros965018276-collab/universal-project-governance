"""Bounded raw reads; no model, producer adapter, project execution or CLI."""
from pathlib import Path
import hashlib
import json
import os
import stat
from managed_contract_primary import canonical, sha, strict_json as _strict_json_bytes, valid_sha
from native_instruction_primary import NATIVE_INSTRUCTION
HERE = Path(__file__).resolve().parent

def strict_json(raw):
    # Native function.arguments is text; retained evidence is UTF-8 bytes.
    # Both use the one canonical duplicate/nonfinite rejecting parser.
    if type(raw) is str:raw=raw.encode('utf-8',errors='strict')
    if type(raw) is not bytes:raise ValueError('JSON requires explicit UTF8 bytes or text')
    return _strict_json_bytes(raw)

def require(value, code):
    if not value:
        raise ValueError(code)

def owned_raw(path, maximum=16_777_216):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        info = parent.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&1024, 'linked-raw-namespace')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum, 'ordinary-bounded-owned-raw')
    raw = path.read_bytes()
    after = path.lstat()
    require(len(raw) == before.st_size and
        (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_nlink) ==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_nlink), 'raw-changed-during-read')
    return raw

def tree_map(root):
    """No linked roots, hardlinks, special leaves or mutable read accepted."""
    root = Path(root).absolute()
    info = root.lstat()
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
        and not getattr(info,'st_file_attributes',0)&1024, 'ordinary-raw-root')
    result = {}
    for directory, dirs, leaves in os.walk(root, followlinks=False):
        for name in dirs:
            info = (Path(directory)/name).lstat()
            require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and not getattr(info,'st_file_attributes',0)&1024, 'ordinary-raw-directory')
        for name in leaves:
            path = Path(directory)/name
            result[path.relative_to(root).as_posix()] = sha(owned_raw(path))
    return dict(sorted(result.items()))

def check_source_pins(pins):
    require(type(pins) is dict and pins, 'reader-source-pins-required')
    for name, digest in pins.items():
        require(type(name) is str and name and ':' not in name and '\\' not in name
            and all(p not in ('','.','..') for p in name.split('/')) and valid_sha(digest), 'reader-source-pin-schema')
        require(sha(owned_raw(HERE.joinpath(*name.split('/')))) == digest, 'reader-source-pin-differs')

