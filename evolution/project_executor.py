"""Opt-in registered stdlib Python projects; import is inert.

Trusted task authors register complete fixed recipes and tests. Models supply only
the current UTF8 source snapshot through repo_validate, never argv/shell/env.
This uses full CPython, without the finite VM. Containers bound accidental faults;
same-UID malicious Python can forge unittest state or interfere with its runner.
It is NOT a proof that arbitrary projects or hostile code are safe or truthful.
"""
from __future__ import annotations

import ast
import base64
import binascii
from enum import Enum
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid

from evolution.isolated_python import (
    DOCKER, IMAGE, PLATFORM, OUTPUT_LIMIT, PROXY_NAMES, SECRET,
    _capture, _confirmed_absent, canonical, sha, strict_json,
)

EXECUTION_BACKEND = "docker-cpython-project-v1"
EXECUTION_SUITE = "registered-python-project-checks-v1"
MAX_FILES = 128
MAX_BYTES = 1048576
MAX_FILE_BYTES = 262144
MAX_CHECKS = 8
CHECK_OUTPUT_LIMIT = 4096
MAX_RECEIPT_BYTES = 262144
PROCESS_ENV = {"LC_ALL": "C.UTF-8"}
PYTHON = "/usr/local/bin/python"
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
SUMMARY_FIELDS = frozenset({
    "backend", "status", "unknown", "received_snapshot_sha256", "contract_sha256",
    "runner_sha256", "input_sha256", "image_reference", "image_id", "platform",
    "output_sha256", "check_count", "container_removed", "scratch_removed",
    "receipt_ref", "receipt_sha256", "observed_wall_seconds",
})


def _relative(path):
    if type(path) is not str or len(path) > 240 or not path or "\\" in path:
        raise ValueError("controlled relative path required")
    parts = path.split("/")
    if len(parts) > 8:
        raise ValueError("path depth bound")
    for part in parts:
        if (not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", part)
                or part.endswith(".") or part.split(".")[0].upper() in
                {"CON", "PRN", "AUX", "NUL", *("COM%d" % i for i in range(10)),
                 *("LPT%d" % i for i in range(10))}):
            raise ValueError("unsafe registered relative path")
    return path


def _file_map(files, *, python_only=False, allow_empty=False, parse_python=True):
    if type(files) is not dict or not (0 if allow_empty else 1) <= len(files) <= MAX_FILES:
        raise ValueError("bounded UTF8 file map required")
    size, folded = 0, set()
    result = {}
    for path, text in files.items():
        _relative(path)
        if path.casefold() in folded:
            raise ValueError("case-ambiguous file path")
        folded.add(path.casefold())
        if type(text) is not str or len(text) > MAX_FILE_BYTES:
            raise ValueError("bounded UTF8 text required")
        raw = text.encode("utf-8")
        size += len(raw)
        if len(raw) > MAX_FILE_BYTES or size > MAX_BYTES or SECRET.search(raw):
            raise ValueError("source byte/credential bound")
        if python_only and not path.endswith(".py"):
            raise ValueError("trusted tests must be Python")
        if path.endswith(".py"):
            if any(not IDENT.fullmatch(p) for p in path[:-3].split("/")):
                raise ValueError("Python module path required")
            if parse_python:
                ast.parse(text, filename=path)  # Registration only; no submitted exec.
        result[path] = raw
    if any(any(other.startswith(path + "/") for other in files) for path in files):
        raise ValueError("file/directory collision")
    return result


def _module(name):
    if type(name) is not str or len(name) > 180 or not all(IDENT.fullmatch(x) for x in name.split(".")):
        raise ValueError("registered dotted module required")
    return name


def _module_file(name, files, *, allow_missing=False):
    path = name.replace(".", "/")
    matches = [p for p in (path + ".py", path + "/__init__.py") if p in files]
    if not matches and allow_missing:
        # Expected origin only, not an observation or a created source file.
        # The isolated recipe records the actual missing/import failure.
        return path + ".py"
    if len(matches) != 1:
        raise ValueError("module must identify one registered file")
    return matches[0]


def _prepare(files, contract, *, runtime_snapshot=False):
    """Pure admission, called only with host-registered task contracts.

    Registration authority is the caller's task registry, not a dict flag. A model
    or repo file must never be allowed to replace this contract.
    """
    if type(runtime_snapshot) is not bool:
        raise ValueError("explicit runtime snapshot mode required")
    source = _file_map(files, allow_empty=runtime_snapshot, parse_python=not runtime_snapshot)
    if (type(contract) is not dict or set(contract) != {"schema_version", "contract_id", "trusted_files", "checks"}
            or type(contract["schema_version"]) is not int or contract["schema_version"] != 1
            or type(contract["contract_id"]) is not str or not SAFE_ID.fullmatch(contract["contract_id"])):
        raise ValueError("registered project contract schema")
    trusted = _file_map(contract["trusted_files"], python_only=True)
    src_tops = {p.split("/")[0].split(".")[0].casefold() for p in source}
    if src_tops & {p.split("/")[0].split(".")[0].casefold() for p in trusted}:
        raise ValueError("trusted/source module collision")
    checks = contract["checks"]
    if type(checks) is not list or not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError("bounded registered checks required")
    ids, unit = set(), False
    for check in checks:
        if type(check) is not dict or type(check.get("id")) is not str or not SAFE_ID.fullmatch(check["id"]) or check["id"] in ids:
            raise ValueError("unique check id required")
        ids.add(check["id"])
        recipe = check.get("recipe")
        if recipe == "unittest":
            if set(check) != {"id", "recipe", "test_modules", "minimum_tests", "expected_test_ids"}:
                raise ValueError("unittest fixed recipe schema")
            modules = check["test_modules"]
            if type(modules) is not list or not 1 <= len(modules) <= 16 or any(type(x) is not str for x in modules) or len(set(modules)) != len(modules):
                raise ValueError("bounded exact test modules required")
            for name in modules:
                _module_file(_module(name), trusted)
            if type(check["minimum_tests"]) is not int or not 1 <= check["minimum_tests"] <= 4096:
                raise ValueError("positive minimum tests required")
            test_ids = check["expected_test_ids"]
            if (type(test_ids) is not list or not check["minimum_tests"] <= len(test_ids) <= 64
                    or any(type(item) is not str or len(item) > 240 or not item
                           or not all(IDENT.fullmatch(p) for p in item.split("."))
                           or not any(item.startswith(name + ".") for name in modules) for item in test_ids)
                    or len(test_ids) != len(set(test_ids)) or len(canonical(test_ids)) > 1536):
                raise ValueError("exact distinct expected unittest IDs required")
            unit = True
        elif recipe == "import":
            if set(check) != {"id", "recipe", "modules"}:
                raise ValueError("import fixed recipe schema")
            modules = check["modules"]
            if type(modules) is not list or not 1 <= len(modules) <= 32 or any(type(x) is not str for x in modules) or len(set(modules)) != len(modules):
                raise ValueError("bounded exact import modules required")
            for name in modules:
                _module_file(_module(name), source, allow_missing=runtime_snapshot)
        elif recipe == "module":
            if set(check) != {"id", "recipe", "module", "args", "stdin", "input_files", "expected_exit", "expected_stdout", "expected_stderr", "expected_files"}:
                raise ValueError("module fixed recipe schema")
            _module_file(_module(check["module"]), source, allow_missing=runtime_snapshot)
            if type(check["args"]) is not list or len(check["args"]) > 16 or any(type(a) is not str or len(a) > 256 or "\x00" in a for a in check["args"]):
                raise ValueError("bounded pre-registered module arguments required")
            for key in ("stdin", "expected_stdout", "expected_stderr"):
                if type(check[key]) is not str or len(check[key].encode("utf-8")) > CHECK_OUTPUT_LIMIT:
                    raise ValueError("bounded registered stream required")
            if len(check["expected_stdout"].encode()) + len(check["expected_stderr"].encode()) > CHECK_OUTPUT_LIMIT:
                raise ValueError("combined expected stream bound")
            if type(check["expected_exit"]) is not int or not 0 <= check["expected_exit"] <= 125:
                raise ValueError("bounded expected exit required")
            _file_map(check["input_files"], allow_empty=True)
            _file_map(check["expected_files"], allow_empty=True)
        else:
            raise ValueError("unregistered recipe; no shell/argv/env/cwd is admitted")
    if not unit:
        raise ValueError("project profile requires positive trusted unittest coverage")
    raw = canonical(contract)
    if len(raw) > MAX_BYTES or SECRET.search(raw):
        raise ValueError("contract byte/credential bound")
    # Exclude completely empty/docstring/pass/ellipsis-only snapshots. Correct
    # implementations remain a trusted-test obligation, not an AST claim.
    def substantive(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return any(substantive(child) for child in node.body)
        return not (isinstance(node, ast.Pass) or isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant) and
                    (type(node.value.value) is str or node.value.value is Ellipsis))
    if not runtime_snapshot and not any(any(substantive(node) for node in ast.parse(raw.decode()).body)
               for p, raw in source.items() if p.endswith(".py")):
        raise ValueError("empty implementation snapshot")
    return {"files_sha256": {p: sha(raw) for p, raw in sorted(source.items())},
            "trusted_files_sha256": {p: sha(raw) for p, raw in sorted(trusted.items())},
            "contract_sha256": sha(raw)}


def validate_contract(contract):
    """Validate host task registration without executing or needing a snapshot.

    Returns a detached canonical JSON copy. Snapshot-specific module existence,
    nonempty source and syntax checks remain strict here. Runtime candidate
    syntax/substance is checked by the fixed isolated checker instead; byte,
    path, trusted-test and contract constraints still precede execution.
    """
    if type(contract) is not dict or type(contract.get("checks")) is not list:
        raise ValueError("registered project contract required")
    files = {}
    for check in contract["checks"]:
        if type(check) is not dict:
            raise ValueError("registered check dict required")
        names = check.get("modules", []) if check.get("recipe") == "import" else [check.get("module")] if check.get("recipe") == "module" else []
        if type(names) is not list:
            raise ValueError("registered module list required")
        for name in names:
            files[_module(name).replace(".", "/") + ".py"] = "registered = True\n"
    if not files:
        files["registered_implementation.py"] = "registered = True\n"
    _prepare(files, contract)
    return strict_json(canonical(contract))


def _execution_input(files, contract, bindings, seconds):
    checks, source_modules, test_modules = [], {}, {}
    for check in contract["checks"]:
        if check["recipe"] == "module":
            checks.append({k: v for k, v in check.items() if not k.startswith("expected_")}
                          | {"expected_file_names": list(check["expected_files"])})
            source_modules[check["module"]] = _module_file(check["module"], files, allow_missing=True)
        else:
            checks.append(check)
            for name in check.get("modules", []):
                source_modules[name] = _module_file(name, files, allow_missing=True)
            for name in check.get("test_modules", []):
                test_modules[name] = _module_file(name, contract["trusted_files"])
    return {"schema_version": 1, **bindings,
            "snapshot_sha256": sha(canonical(bindings["files_sha256"])),
            "checks": checks, "source_module_files": source_modules,
            "test_module_files": test_modules, "checker_sha256": sha(CHECKER.encode()),
            "execution_seconds": seconds}


# Trusted helper executes exact registered checks. It is never user supplied.
CHECKER = r'''
import ast, importlib, importlib.util, json, os, runpy, sys, unittest
from pathlib import Path
inp=json.loads(Path('/runner/input.json').read_text())
check=next(c for c in inp['checks'] if c['id']==sys.argv[1])
outcome={'recipe':check['recipe'],'completed':False}
report=Path('/tmp/work')/check['id']/'outcome.json'
sys.path[:0]=['/trusted','/src']
def require_implementation():
    def substantive(node):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            return any(substantive(child) for child in node.body)
        return not (isinstance(node,ast.Pass) or isinstance(node,ast.Expr)
                    and isinstance(node.value,ast.Constant) and
                    (type(node.value.value) is str or node.value.value is Ellipsis))
    trees=[ast.parse((Path('/src')/name).read_text(encoding='utf-8'),filename='/src/'+name)
           for name in inp['files_sha256'] if name.endswith('.py')]
    if not any(any(substantive(node) for node in tree.body) for tree in trees):
        raise RuntimeError('empty implementation snapshot')
try:
    require_implementation()
    if check['recipe']=='unittest':
        def test_ids(suite):
            for test in suite:
                if isinstance(test,unittest.TestSuite):yield from test_ids(test)
                else:yield test.id()
        class TrackingResult(unittest.TextTestResult):
            def startTest(self,test):
                self.executed_test_ids.append(test.id());super().startTest(test)
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs);self.executed_test_ids=[]
        suite=unittest.TestSuite()
        for name in check['test_modules']:
            mod=importlib.import_module(name)
            if Path(mod.__file__).resolve()!=Path('/trusted')/inp['test_module_files'][name]:
                raise RuntimeError('untrusted test origin')
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(mod))
        loaded_test_ids=list(test_ids(suite))
        result=unittest.TextTestRunner(verbosity=2,resultclass=TrackingResult).run(suite)
        outcome.update(completed=True,tests_run=result.testsRun,skipped=len(result.skipped),
                       failures=len(result.failures),errors=len(result.errors),
                       expected_failures=len(result.expectedFailures),test_ids=loaded_test_ids,
                       executed_test_ids=result.executed_test_ids,
                       unexpected_successes=len(result.unexpectedSuccesses),
                       successful=result.wasSuccessful())
    elif check['recipe']=='import':
        seen={}
        for name in check['modules']:
            mod=importlib.import_module(name)
            path=Path(mod.__file__).resolve()
            if path!=Path('/src')/inp['source_module_files'][name]:
                raise RuntimeError('unregistered import origin')
            seen[name]=str(path)
        outcome.update(completed=True,modules=seen)
    else:
        found=importlib.util.find_spec(check['module'])
        if found is None or found.origin is None or Path(found.origin).resolve()!=Path('/src')/inp['source_module_files'][check['module']]:
            raise RuntimeError('unregistered module origin')
        sys.argv=[check['module']]+check['args']
        try:
            runpy.run_module(check['module'],run_name='__main__',alter_sys=True)
        except SystemExit as e:
            if e.code is not None and type(e.code) is not int:
                raise
            outcome.update(completed=True)
            report.write_text(json.dumps(outcome,sort_keys=True))
            raise
        outcome.update(completed=True)
finally:
    report.write_text(json.dumps(outcome,sort_keys=True))
'''

RUNNER = r'''
import base64, hashlib, json, os, selectors, signal, stat, subprocess, sys, time
from pathlib import Path
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
raw=Path('/runner/input.json').read_bytes();inp=json.loads(raw)
for mount,key in (('/src','files_sha256'),('/trusted','trusted_files_sha256')):
    for name,digest in inp[key].items():
        path=Path(mount)/name
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes())!=digest:
            raise RuntimeError('frozen file binding')
if sha(Path('/runner/checker.py').read_bytes())!=inp['checker_sha256']:
    raise RuntimeError('checker binding')
until=time.monotonic()+inp['execution_seconds']
rows=[]
for check in inp['checks']:
    cwd=Path('/tmp/work')/check['id'];cwd.mkdir(parents=True)
    for name,text in check.get('input_files',{}).items():
        path=cwd/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode())
    argv=['/usr/local/bin/python','-I','-B','/runner/checker.py',check['id']]
    p=subprocess.Popen(argv,cwd=cwd,env={'LC_ALL':'C.UTF-8'},stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    stdin=check.get('stdin','').encode();p.stdin.write(stdin);p.stdin.close()
    selector=selectors.DefaultSelector()
    for key,stream in (('stdout',p.stdout),('stderr',p.stderr)):
        os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,key)
    data={'stdout':bytearray(),'stderr':bytearray()};observed=0;timeout=False;truncated=False
    try:
        while selector.get_map():
            if time.monotonic()>=until:timeout=True;break
            for entry,_ in selector.select(min(.02,max(0,until-time.monotonic()))):
                chunk=os.read(entry.fd,4096)
                if not chunk:selector.unregister(entry.fileobj);continue
                observed+=len(chunk);room=4096-sum(map(len,data.values()))
                data[entry.data].extend(chunk[:max(0,room)])
                if len(chunk)>room:truncated=True;break
            if truncated:break
        if timeout or truncated:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:code=p.wait(timeout=max(.001,min(.2,until-time.monotonic())))
        except subprocess.TimeoutExpired:
            timeout=True
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            code=None
    finally:
        selector.close();p.stdout.close();p.stderr.close()
    outcome=None
    report=cwd/'outcome.json'
    if report.is_file() and not report.is_symlink() and report.stat().st_size<=4096:
        try:outcome=json.loads(report.read_bytes())
        except (ValueError,OSError):pass
    output_files={}
    for name in check.get('expected_file_names',[]):
        path=cwd/name
        try:
            info=path.lstat()
            parents=list(path.parents)[:len(Path(name).parts)-1]
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>262144
                    or any(x.is_symlink() for x in parents) or path.resolve().is_relative_to(cwd) is not True):
                output_files[name]={'invalid':True};continue
            b=path.read_bytes();output_files[name]={'sha256':sha(b),'bytes':len(b)}
        except OSError:output_files[name]={'missing':True}
    streams={}
    for key,b in data.items():
        b=bytes(b);streams[key+'_base64']=base64.b64encode(b).decode()
        streams[key+'_sha256']=sha(b);streams[key+'_bytes']=len(b)
    rows.append(dict(id=check['id'],recipe=check['recipe'],snapshot_sha256=inp['snapshot_sha256'],
                     argv=argv,cwd=str(cwd),env_sha256=sha(encode({'LC_ALL':'C.UTF-8'})),
                     exit_code=code,timeout=timeout,truncated=truncated,observed_bytes=observed,
                     outcome=outcome,output_files=output_files,**streams))
record={'schema_version':1,'snapshot_sha256':inp['snapshot_sha256'],
        'contract_sha256':inp['contract_sha256'],'input_sha256':sha(raw),
        'runner_sha256':sha(Path('/runner/runner.py').read_bytes()),'checks':rows}
payload=encode(record)
if len(payload)>64512:raise RuntimeError('whole result output bound')
sys.stdout.buffer.write(payload+b'\n');sys.stdout.buffer.flush()
'''


class Failure(Exception):
    def __init__(self, code, unknown=False):
        self.code, self.unknown = code, unknown


def _regular(path, maximum=OUTPUT_LIMIT):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 1024 or info.st_size > maximum:
        raise ValueError("bounded owned regular receipt required")
    return path.read_bytes()


def _safe_new_root(artifacts):
    target = Path(artifacts)
    if not target.is_absolute() or target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise ValueError("new owned absolute artifact path required")
    _relative(target.name)
    if any(char in str(target) for char in ",\r\n"):
        raise ValueError("Docker bind source syntax is reserved")
    for parent in (target.parent, *target.parent.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("artifact reparse parents forbidden")
    return target.parent.resolve(strict=True) / target.name


def _owned(container, owner, cid):
    return (container.get("Name") == "/" + owner
            and container.get("Config", {}).get("Labels", {}).get("upg.executor.owner") == owner
            and type(container.get("Id")) is str and HEX.fullmatch(container["Id"])
            and (cid is None or container["Id"] == cid))


def _hostpath(path):
    path = path.replace("\\", "/").rstrip("/")
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            if len(suffix) > 2 and suffix[1] == "/":
                path = suffix[0] + ":/" + suffix[2:]
    return path.casefold()


def _verify_container(container, image, owner, cid, root):
    if not _owned(container, owner, cid):
        raise Failure("OWNER_MISMATCH", True)
    host, config = container.get("HostConfig", {}), container.get("Config", {})
    expected = {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                "Memory": 536870912, "MemorySwap": 536870912, "NanoCpus": 1000000000,
                "PidsLimit": 64, "Init": True, "CgroupnsMode": "private", "IpcMode": "private"}
    if (any(type(host.get(k)) is not type(v) or host.get(k) != v for k, v in expected.items()) or host.get("CapDrop") != ["ALL"]
            or host.get("CapAdd") not in (None, []) or host.get("SecurityOpt") != ["no-new-privileges=true"]
            or host.get("PidMode") not in (None, "") or host.get("PortBindings") not in (None, {})
            or host.get("Devices") not in (None, []) or host.get("DeviceRequests") not in (None, [])
            or host.get("RestartPolicy", {}).get("Name") != "no"
            or host.get("Tmpfs") != {"/tmp": "rw,nosuid,nodev,noexec,size=32m,uid=65534,gid=65534"}
            or config.get("User") != "65534:65534" or config.get("WorkingDir") != "/tmp"
            or config.get("Volumes") not in (None, {}) or config.get("Image") != IMAGE
            or container.get("Image") != image["Id"] or container.get("Path") != "/usr/bin/env"
            or container.get("Args") != ["-i", "LC_ALL=C.UTF-8", PYTHON, "-I", "-B", "/runner/runner.py"]):
        raise Failure("ISOLATION_MISMATCH", True)
    env = config.get("Env", [])
    if (type(env) is not list or len(env) != len(set(env))
            or set(env) != set(image.get("Config", {}).get("Env", [])) | {p + "=" for p in PROXY_NAMES}):
        raise Failure("ENV_MISMATCH", True)
    mounts = container.get("Mounts", [])
    if len(mounts) != 3 or {m.get("Destination") for m in mounts} != {"/src", "/trusted", "/runner"}:
        raise Failure("MOUNT_MISMATCH", True)
    for mount in mounts:
        leaf = {"/src": "src", "/trusted": "trusted", "/runner": "runner"}[mount["Destination"]]
        if (mount.get("Type") != "bind" or mount.get("RW") is not False
                or _hostpath(mount.get("Source", "")) != _hostpath(str(root / leaf))):
            raise Failure("MOUNT_MISMATCH", True)
    return container


def _create_args(root, owner):
    args = ["create", "--name", owner, "--label", "upg.executor.owner=" + owner,
            "--platform", PLATFORM, "--pull", "never", "--network", "none", "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true", "--read-only",
            "--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "64",
            "--init", "--cgroupns", "private", "--ipc", "private", "--restart", "no",
            "--stop-timeout", "1", "--no-healthcheck", "--workdir", "/tmp",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=32m,uid=65534,gid=65534"]
    for leaf, destination in (("src", "/src"), ("trusted", "/trusted"), ("runner", "/runner")):
        args += ["--mount", "type=bind,source=" + str(root / leaf) + ",target=" + destination + ",readonly"]
    for name in PROXY_NAMES:
        args += ["--env", name + "="]
    return args + ["--entrypoint", "/usr/bin/env", IMAGE, "-i", "LC_ALL=C.UTF-8", PYTHON, "-I", "-B", "/runner/runner.py"]


def _verify_image(image):
    digest = IMAGE.split("@", 1)[1]
    if (image.get("Os") != "linux" or image.get("Architecture") != "amd64"
            or image.get("Descriptor", {}).get("digest") != digest
            or "python@" + digest not in image.get("RepoDigests", [])
            or type(image.get("Id")) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", image["Id"])):
        raise Failure("IMAGE_MISMATCH")
    image_env = image.get("Config", {}).get("Env", [])
    if (type(image_env) is not list or len(image_env) > 16 or any(type(e) is not str or "=" not in e
            or e.split("=", 1)[0] not in {"PATH", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256"}
            for e in image_env)):
        raise Failure("IMAGE_ENV_MISMATCH")
    return image


def execution_summary(snapshot_sha256, check_count=0, *, status="NOT_APPLICABLE", elapsed=0.):
    return {"backend": EXECUTION_BACKEND, "status": status, "unknown": False,
            "received_snapshot_sha256": snapshot_sha256, "contract_sha256": None,
            "runner_sha256": None, "input_sha256": None, "image_reference": IMAGE,
            "image_id": None, "platform": PLATFORM, "output_sha256": None,
            "check_count": check_count, "container_removed": None, "scratch_removed": None,
            "receipt_ref": None, "receipt_sha256": None, "observed_wall_seconds": elapsed}


def execute_project(files, contract, artifacts, remaining_seconds):
    """Execute one registered snapshot once; receipt is evidence, never a PASS.

    The existing artifact directory is an unreplayable fence, including prepare
    failures. Callers must preserve unknown state and never retry execution.
    """
    started = time.monotonic()
    if type(remaining_seconds) not in (int, float) or not math.isfinite(remaining_seconds) or remaining_seconds <= 0:
        raise ValueError("finite positive remaining wall budget required")
    total = started + min(float(remaining_seconds), 60.)
    deadline = total - min(8., (total - started) / 2)
    root = _safe_new_root(artifacts)
    root.mkdir()  # Exclusive ownership fence is established before preparation.
    owner = "rc20-project-" + uuid.uuid4().hex
    cid, attempted, removed, cleanup_phase, index = None, False, False, False, 0
    calls, snapshot, bindings, inputs = [], {}, {}, None
    result = {"schema_version": 1, "backend": EXECUTION_BACKEND, "suite": EXECUTION_SUITE,
              "status": "NOT_EXECUTED", "unknown": False, "quality_assessed": False,
              "image_reference": IMAGE, "image_id": None, "platform": PLATFORM,
              "owner": owner, "container_id": None, "container_removed": False,
              "scratch_removed": False, "checks": None, "command_receipts": calls,
              "snapshot_sha256": None, "contract_sha256": None,
              "runner_sha256": sha(RUNNER.encode()), "checker_sha256": sha(CHECKER.encode()),
              "input_sha256": None, "output_sha256": None,
              "total_budget_seconds": total - started, "cleanup_reserve_seconds": total - deadline,
              "wall_seconds_scope": "through cleanup, before final receipt persistence; caller elapsed includes persistence",
              "threat_boundary": "Trusted contracts/tests; no guarantee against malicious Python forging unittest or interfering with same-UID runner."}

    def phase(until=None):
        limit = (total if cleanup_phase else deadline) if until is None else until
        if time.monotonic() >= limit:
            raise Failure("LOCAL_BUDGET_EXHAUSTED", attempted)

    def write(path, raw, until=None):
        phase(until)
        with path.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        phase(until)

    def command(label, args, *, inspect=False, allow_error=False):
        nonlocal index
        phase(); index += 1
        prefix = "%02d-%s" % (index, label)
        argv = [DOCKER] + args
        write(root / (prefix + ".start.json"), canonical({"argv": argv, "monotonic": time.monotonic()}))
        phase()
        response = _capture(argv, total if cleanup_phase else deadline)
        receipt = {k: v for k, v in response.items() if k not in {"stdout", "stderr"}}
        receipt.update(id=prefix, argv=argv)
        sensitive = False
        for key in ("stdout", "stderr"):
            raw = response[key]
            receipt.update({key + "_sha256": sha(raw), key + "_bytes": len(raw)})
            if SECRET.search(raw):
                sensitive = True
            else:
                write(root / (prefix + "." + key + ".raw"), raw, total)
        calls.append(receipt)
        write(root / (prefix + ".receipt.json"), canonical(receipt), total)
        if sensitive:
            raise Failure("SENSITIVE_OUTPUT_REJECTED", True)
        if not allow_error and (response.get("status") != "completed" or response.get("exit_code") != 0):
            raise Failure("COMMAND_" + label, attempted or response.get("status") != "completed")
        return response

    def obj(raw):
        value = strict_json(raw)
        if type(value) is not list or len(value) != 1 or type(value[0]) is not dict:
            raise Failure("INSPECT_SHAPE", attempted)
        return value[0]

    def owned(container):
        return _owned(container, owner, cid)

    def verify(container, image):
        return _verify_container(container, image, owner, cid, root)

    try:
        phase()
        bindings = _prepare(files, contract, runtime_snapshot=True)
        phase()
        snapshot = bindings["files_sha256"]
        result.update(snapshot_sha256=sha(canonical(snapshot)), contract_sha256=bindings["contract_sha256"])
        result["execution_seconds"] = max(.001, deadline - time.monotonic())
        inputs = _execution_input(files, contract, bindings, result["execution_seconds"])
        raw = canonical(inputs)
        if len(raw) > MAX_BYTES:
            raise Failure("INPUT_BOUND")
        result["input_sha256"] = sha(raw)
        for leaf, contents in (("src", files), ("trusted", contract["trusted_files"]),
                               ("runner", {"runner.py": RUNNER, "checker.py": CHECKER, "input.json": raw.decode()})):
            directory = root / leaf; directory.mkdir()
            for path, text in contents.items():
                phase(); target = directory / path; target.parent.mkdir(parents=True, exist_ok=True)
                write(target, text.encode("utf-8"))
        write(root / "input.frozen.json", raw)
        write(root / "contract.frozen.json", canonical(contract))
        write(root / "snapshot.received.json", canonical(files))
        write(root / "binding.json", canonical(result | bindings | {
            "total_budget_seconds": total - started, "cleanup_reserve_seconds": total - deadline}))
        image = obj(command("image-inspect", ["image", "inspect", IMAGE], inspect=True)["stdout"])
        _verify_image(image)
        result["image_id"] = image["Id"]
        attempted = True
        response = command("create", _create_args(root, owner))
        cid = response["stdout"].decode("ascii").strip()
        if not HEX.fullmatch(cid):
            cid = None; raise Failure("CREATE_ID_UNCONFIRMED", True)
        result["container_id"] = cid
        verify(obj(command("inspect-before", ["container", "inspect", cid], inspect=True)["stdout"]), image)
        # Attached output is supervised while the container runs, with one global
        # stdout+stderr cap; timeout kills the CLI then the owned container.
        response = command("start-attach", ["container", "start", "--attach", cid])
        after = verify(obj(command("inspect-after", ["container", "inspect", cid], inspect=True)["stdout"]), image)
        if after.get("State", {}).get("Running") is not False or after.get("State", {}).get("ExitCode") != 0:
            raise Failure("RUNNER_PROCESS_FAILURE")
        if response["stderr"]:
            raise Failure("RUNNER_UNSTRUCTURED_STDERR")
        payload = strict_json(response["stdout"])
        keys = {"schema_version", "snapshot_sha256", "contract_sha256", "input_sha256", "runner_sha256", "checks"}
        if (type(payload) is not dict or set(payload) != keys or type(payload["schema_version"]) is not int
                or payload["schema_version"] != 1 or any(payload.get(k) != result[k] for k in keys - {"checks", "schema_version"})):
            raise Failure("OUTPUT_BINDING", True)
        result.update(checks=payload["checks"], output_sha256=sha(response["stdout"]))
        _check_rows(files, contract, result)  # Strict binding/shape, no PASS here.
        write(root / "output.received.json", response["stdout"], total)
        for leaf, expected in (("src", snapshot), ("trusted", bindings["trusted_files_sha256"]),
                               ("runner", {"runner.py": result["runner_sha256"], "checker.py": result["checker_sha256"], "input.json": result["input_sha256"]})):
            if _tree_hashes(root / leaf) != expected:
                raise Failure("FROZEN_BYTES_CHANGED", True)
        result["status"] = "EXECUTED"
    except Failure as error:
        result.update(status="TERMINAL_UNKNOWN" if error.unknown else error.code,
                      unknown=error.unknown, reason=error.code)
    except (ValueError, TypeError, KeyError, UnicodeError, OSError, RecursionError, SyntaxError) as error:
        result.update(status="TERMINAL_UNKNOWN", unknown=True, reason="PREPARATION_OR_RECEIPT_FAILURE", error_type=type(error).__name__)
    finally:
        cleanup_phase = True
        if attempted:
            try:
                response = command("cleanup-inspect", ["container", "inspect", cid or owner], inspect=True, allow_error=True)
                if response["status"] == "completed" and response["exit_code"] == 0:
                    container = obj(response["stdout"])
                    if not owned(container):
                        raise Failure("CLEANUP_OWNER_MISMATCH", True)
                    cid = container["Id"]; result["container_id"] = cid
                    removal = command("remove-owned", ["container", "rm", "--force", cid], allow_error=True)
                    absent = command("confirm-absent", ["container", "inspect", cid], inspect=True, allow_error=True)
                    removed = removal["status"] == "completed" and removal["exit_code"] == 0 and _confirmed_absent(absent, cid)
                if not removed:
                    raise Failure("CLEANUP_UNCONFIRMED", True)
            except (Failure, ValueError, TypeError, KeyError, UnicodeError, OSError):
                result.update(status="TERMINAL_UNKNOWN", unknown=True, cleanup_unconfirmed=True)
        result["container_removed"] = removed
        try:
            # No arbitrary recursive deletion. Check each owned tree then unlink
            # only registered regular files and their now-empty directories.
            for leaf in ("src", "trusted", "runner"):
                directory = root / leaf
                if directory.exists():
                    paths = _tree_hashes(directory)
                    write(root / (leaf + ".cleanup-byte-map.json"), canonical(paths), total)
                    for name in paths:
                        phase(total); (directory / name).unlink()
                    dirs = sorted((p for p in directory.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
                    for path in dirs:
                        phase(total); path.rmdir()
                    phase(total); directory.rmdir()
            result["scratch_removed"] = True
        except (Failure, OSError, ValueError):
            result.update(status="TERMINAL_UNKNOWN", unknown=True, scratch_cleanup_unconfirmed=True)
        result["wall_seconds"] = time.monotonic() - started
        result["command_count"] = index
        try:
            write(root / "result.json", canonical(result), total)
        except (Failure, OSError, ValueError):
            result.update(status="TERMINAL_UNKNOWN", unknown=True, evidence_persistence_unconfirmed=True)
    return result


def _tree_hashes(directory):
    if directory.is_symlink() or getattr(directory.lstat(), "st_file_attributes", 0) & 1024:
        raise ValueError("owned tree cannot be a reparse point")
    hashes = {}
    pending, paths, count = [directory], [], 0
    while pending:
        parent = pending.pop()
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("owned directory cannot be a reparse point")
        with os.scandir(parent) as entries:
            for entry in entries:
                count += 1
                if count > MAX_FILES * 9:
                    raise ValueError("owned tree entry bound")
                path = Path(entry.path)
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
                    raise ValueError("owned tree contains reparse point")
                if stat.S_ISDIR(info.st_mode):pending.append(path)
                else:paths.append(path)
    for path in paths:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("owned tree contains reparse point")
        if stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError("owned file bound")
            hashes[path.relative_to(directory).as_posix()] = sha(path.read_bytes())
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError("owned tree contains special file")
    return hashes


def _check_rows(files, contract, receipt):
    rows = receipt.get("checks")
    if type(rows) is not list or len(rows) != len(contract["checks"]):
        raise ValueError("check coverage mismatch")
    for check, row in zip(contract["checks"], rows):
        keys = {"id", "recipe", "snapshot_sha256", "argv", "cwd", "env_sha256", "exit_code", "timeout", "truncated", "observed_bytes", "outcome", "output_files",
                "stdout_base64", "stdout_sha256", "stdout_bytes", "stderr_base64", "stderr_sha256", "stderr_bytes"}
        if (type(row) is not dict or set(row) != keys or row.get("id") != check["id"]
                or row.get("recipe") != check["recipe"] or row.get("snapshot_sha256") != receipt["snapshot_sha256"]
                or row.get("argv") != [PYTHON, "-I", "-B", "/runner/checker.py", check["id"]]
                or row.get("cwd") != "/tmp/work/" + check["id"]
                or row.get("env_sha256") != sha(canonical(PROCESS_ENV))
                or type(row.get("timeout")) is not bool or type(row.get("truncated")) is not bool
                or row.get("exit_code") is not None and type(row["exit_code"]) is not int
                or row.get("exit_code") is None and not row.get("timeout") and not row.get("truncated")
                or type(row.get("observed_bytes")) is not int or not 0 <= row["observed_bytes"] <= CHECK_OUTPUT_LIMIT + 4096):
            raise ValueError("check receipt binding/schema mismatch")
        count = 0
        for key in ("stdout", "stderr"):
            if type(row[key + "_base64"]) is not str or len(row[key + "_base64"]) > 5500:
                raise ValueError("check stream encoding bound")
            raw = base64.b64decode(row[key + "_base64"], validate=True)
            if len(raw) > CHECK_OUTPUT_LIMIT or type(row[key + "_bytes"]) is not int or len(raw) != row[key + "_bytes"] or sha(raw) != row[key + "_sha256"] or SECRET.search(raw):
                raise ValueError("check raw stream binding/credential bound")
            count += len(raw)
        if count > CHECK_OUTPUT_LIMIT or count > row["observed_bytes"] or not row["truncated"] and count != row["observed_bytes"]:
            raise ValueError("check combined output bound")
        if type(row["output_files"]) is not dict or set(row["output_files"]) != set(check.get("expected_files", {})):
            raise ValueError("check output file coverage")
        for item in row["output_files"].values():
            if (type(item) is not dict or not (set(item) == {"invalid"} and item["invalid"] is True
                    or set(item) == {"missing"} and item["missing"] is True
                    or set(item) == {"sha256", "bytes"} and type(item["sha256"]) is str
                    and HEX.fullmatch(item["sha256"]) and type(item["bytes"]) is int
                    and 0 <= item["bytes"] <= MAX_FILE_BYTES)):
                raise ValueError("file observation schema")
        outcome = row["outcome"]
        if outcome is None:
            if not (row["timeout"] or row["truncated"]):
                raise ValueError("missing child outcome")
            continue
        if (type(outcome) is not dict or outcome.get("recipe") != check["recipe"]
                or type(outcome.get("completed")) is not bool):
            raise ValueError("child outcome binding")
        if outcome["completed"] is False:
            if set(outcome) != {"recipe", "completed"}:
                raise ValueError("incomplete child outcome schema")
        elif check["recipe"] == "unittest":
            if (set(outcome) != {"recipe", "completed", "tests_run", "skipped", "failures", "errors", "expected_failures", "unexpected_successes", "successful", "test_ids", "executed_test_ids"}
                    or type(outcome["successful"]) is not bool
                    or any(type(outcome[k]) is not int or not 0 <= outcome[k] <= 100000
                           for k in ("tests_run", "skipped", "failures", "errors", "expected_failures", "unexpected_successes"))
                    or outcome["skipped"] > outcome["tests_run"]
                    or any(type(outcome[k]) is not list or len(outcome[k]) > 4096
                           or any(type(item) is not str or len(item) > 240 for item in outcome[k])
                           for k in ("test_ids", "executed_test_ids"))):
                raise ValueError("unittest outcome schema")
        elif check["recipe"] == "import":
            if (set(outcome) != {"recipe", "completed", "modules"} or type(outcome["modules"]) is not dict
                    or set(outcome["modules"]) != set(check["modules"])
                    or any(type(x) is not str for x in outcome["modules"].values())):
                raise ValueError("import outcome schema")
        elif set(outcome) != {"recipe", "completed"}:
            raise ValueError("module outcome schema")
    return rows


def validate_receipt(files, contract, receipt):
    """Pure, read-only host scoring; no execution/replay/VM at final scoring."""
    try:
        bindings = _prepare(files, contract, runtime_snapshot=True)
        snapshot = sha(canonical(bindings["files_sha256"]))
        if (type(receipt) is not dict or type(receipt.get("schema_version")) is not int or receipt.get("schema_version") != 1
                or receipt.get("backend") != EXECUTION_BACKEND or receipt.get("suite") != EXECUTION_SUITE
                or receipt.get("status") != "EXECUTED" or receipt.get("unknown") is not False
                or receipt.get("quality_assessed") is not False or receipt.get("container_removed") is not True
                or receipt.get("scratch_removed") is not True or receipt.get("snapshot_sha256") != snapshot
                or receipt.get("contract_sha256") != bindings["contract_sha256"]
                or receipt.get("runner_sha256") != sha(RUNNER.encode()) or receipt.get("checker_sha256") != sha(CHECKER.encode())
                or receipt.get("image_reference") != IMAGE or receipt.get("platform") != PLATFORM
                or not isinstance(receipt.get("image_id"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["image_id"])
                or type(receipt.get("owner")) is not str or not re.fullmatch(r"rc20-project-[0-9a-f]{32}", receipt["owner"])
                or type(receipt.get("container_id")) is not str or not HEX.fullmatch(receipt["container_id"])
                or type(receipt.get("execution_seconds")) not in (int, float)
                or not math.isfinite(receipt["execution_seconds"]) or not 0 < receipt["execution_seconds"] <= 60
                or any(receipt.get(k) for k in ("cleanup_unconfirmed", "scratch_cleanup_unconfirmed", "evidence_persistence_unconfirmed"))):
            raise ValueError("unconfirmed or stale project receipt")
        rows = _check_rows(files, contract, receipt)
        expected_input = _execution_input(files, contract, bindings, receipt["execution_seconds"])
        payload = {k: receipt[k] for k in ("schema_version", "snapshot_sha256", "contract_sha256", "input_sha256", "runner_sha256", "checks")}
        if (receipt.get("input_sha256") != sha(canonical(expected_input))
                or receipt.get("output_sha256") != sha(canonical(payload) + b"\n")):
            raise ValueError("input/output receipt SHA binding")
        _command_integrity(receipt)
        failures, diagnostics = [], []
        for check, row in zip(contract["checks"], rows):
            outcome = row["outcome"]
            good = (not row["timeout"] and not row["truncated"] and type(outcome) is dict
                    and outcome.get("completed") is True and outcome.get("recipe") == check["recipe"])
            if check["recipe"] == "unittest":
                keys = {"recipe", "completed", "tests_run", "skipped", "failures", "errors", "expected_failures", "unexpected_successes", "successful", "test_ids", "executed_test_ids"}
                good &= (type(outcome) is dict and set(outcome) == keys
                         and all(type(outcome.get(k)) is int and outcome[k] >= 0 for k in ("tests_run", "skipped", "failures", "errors", "expected_failures", "unexpected_successes"))
                         and outcome.get("successful") is True and row["exit_code"] == 0)
                if good:
                    expected_ids = sorted(check["expected_test_ids"])
                    good &= (outcome["tests_run"] == len(expected_ids)
                             and sorted(outcome["test_ids"]) == expected_ids
                             and sorted(outcome["executed_test_ids"]) == expected_ids
                             and outcome["skipped"] == outcome["expected_failures"] == 0
                             and outcome["failures"] == outcome["errors"] == outcome["unexpected_successes"] == 0)
            elif check["recipe"] == "import":
                expected = {name: "/src/" + _module_file(name, files, allow_missing=True) for name in check["modules"]}
                good &= (type(outcome) is dict and set(outcome) == {"recipe", "completed", "modules"}
                         and outcome.get("modules") == expected and row["exit_code"] == 0
                         and all(_module_file(name, files, allow_missing=True) in files for name in check["modules"]))
            else:
                good &= (type(outcome) is dict and set(outcome) == {"recipe", "completed"}
                         and row["exit_code"] == check["expected_exit"]
                         and _module_file(check["module"], files, allow_missing=True) in files)
                for key in ("stdout", "stderr"):
                    raw = check["expected_" + key].encode()
                    good &= row[key + "_sha256"] == sha(raw) and row[key + "_bytes"] == len(raw)
                good &= row["output_files"] == {name: {"sha256": sha(text.encode()), "bytes": len(text.encode())}
                                                for name, text in check["expected_files"].items()}
            if not good:
                failures.append("project-check-failed:" + check["id"])
                # _check_rows already verified exact hashes, sizes, the combined
                # 4096-byte cap and credential rejection for these original bytes.
                diagnostic = {key: row[key] for key in ("id", "recipe", "exit_code", "timeout", "truncated")}
                diagnostic["completed"] = outcome.get("completed") if type(outcome) is dict else None
                for key in ("stdout", "stderr"):
                    diagnostic[key] = base64.b64decode(row[key + "_base64"], validate=True).decode("utf-8", errors="replace")
                    for suffix in ("_sha256", "_bytes"):
                        diagnostic[key + suffix] = row[key + suffix]
                diagnostics.append(diagnostic)
        return {"ok": not failures, "integrity_ok": True, "suite": EXECUTION_SUITE, "checks_passed": len(rows) - len(failures),
                "checks_total": len(rows), "failures": failures, "diagnostics": diagnostics}
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error, SyntaxError, RecursionError):
        return {"ok": False, "integrity_ok": False, "suite": EXECUTION_SUITE, "checks_passed": 0,
                "checks_total": _check_count(contract),
                "failures": ["project-receipt-invalid"], "diagnostics": []}


def _check_count(contract):
    return len(contract["checks"]) if type(contract) is dict and type(contract.get("checks")) is list else 0


def _command_integrity(receipt, artifact_root=None):
    commands = receipt.get("command_receipts")
    labels = ["image-inspect", "create", "inspect-before", "start-attach", "inspect-after", "cleanup-inspect", "remove-owned", "confirm-absent"]
    if type(commands) is not list or len(commands) != len(labels) or receipt.get("command_count") != len(labels):
        raise ValueError("incomplete Docker lifecycle receipts")
    for index, (label, command) in enumerate(zip(labels, commands), 1):
        if (type(command) is not dict or command.get("id") != "%02d-%s" % (index, label)
                or command.get("status") != "completed" or command.get("output_complete") is not True
                or command.get("exit_code") != (1 if label == "confirm-absent" else 0)
                or type(command.get("argv")) is not list or not command["argv"] or command["argv"][0] != DOCKER
                or any(type(arg) is not str for arg in command["argv"])
                or any(type(command.get(k + "_sha256")) is not str or not HEX.fullmatch(command[k + "_sha256"])
                       or type(command.get(k + "_bytes")) is not int or not 0 <= command[k + "_bytes"] <= OUTPUT_LIMIT
                       for k in ("stdout", "stderr"))):
            raise ValueError("Docker command receipt schema")
        argv = command["argv"][1:]
        expected = {
            "image-inspect": ["image", "inspect", IMAGE],
            "inspect-before": ["container", "inspect", receipt["container_id"]],
            "start-attach": ["container", "start", "--attach", receipt["container_id"]],
            "inspect-after": ["container", "inspect", receipt["container_id"]],
            "cleanup-inspect": ["container", "inspect", receipt["container_id"]],
            "remove-owned": ["container", "rm", "--force", receipt["container_id"]],
            "confirm-absent": ["container", "inspect", receipt["container_id"]],
        }
        if label != "create" and argv != expected[label]:
            raise ValueError("Docker lifecycle command mismatch")
        if label == "create":
            mounts = [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == "--mount"]
            if len(mounts) != 3 or not mounts[0].startswith("type=bind,source=") or not mounts[0].endswith(",target=/src,readonly"):
                raise ValueError("Docker create mount schema")
            source = mounts[0][len("type=bind,source="):-len(",target=/src,readonly")]
            inferred_root = Path(source).parent
            if not inferred_root.is_absolute() or artifact_root is not None and inferred_root != artifact_root or argv != _create_args(inferred_root, receipt["owner"]):
                raise ValueError("Docker create binding mismatch")
        if label == "start-attach" and command["stdout_sha256"] != receipt["output_sha256"]:
            raise ValueError("attached raw output digest mismatch")


def _read_project_receipt(files, contract, artifacts, receipt_sha256=None):
    """Read the original external receipt and raw payload; NEVER run anything."""
    root = Path(artifacts)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("absolute original artifact directory required")
    for parent in (root, *root.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("original artifact directory cannot be a reparse point")
    raw = _regular(root / "result.json", MAX_RECEIPT_BYTES)
    if receipt_sha256 is not None and sha(raw) != receipt_sha256:
        raise ValueError("project receipt SHA mismatch")
    receipt = strict_json(raw)
    if type(receipt) is not dict:
        raise ValueError("original result receipt must be a JSON object")
    if receipt.get("status") == "EXECUTED":
        output = _regular(root / "output.received.json")
        payload = strict_json(output)
        input_raw = _regular(root / "input.frozen.json", MAX_BYTES)
        frozen_input = strict_json(input_raw)
        frozen_contract_raw = _regular(root / "contract.frozen.json", MAX_BYTES)
        frozen_contract = strict_json(frozen_contract_raw)
        frozen_snapshot = strict_json(_regular(root / "snapshot.received.json", MAX_BYTES * 6))
        if any(type(value) is not dict for value in (payload, frozen_input, frozen_contract, frozen_snapshot)):
            raise ValueError("original output/input/contract/snapshot must be JSON objects")
        if (sha(output) != receipt.get("output_sha256") or canonical(payload.get("checks")) != canonical(receipt.get("checks"))
                or any(payload.get(k) != receipt.get(k) for k in ("schema_version", "snapshot_sha256", "contract_sha256", "input_sha256", "runner_sha256"))
                or sha(input_raw) != receipt.get("input_sha256")
                or sha(frozen_contract_raw) != receipt.get("contract_sha256") or frozen_contract != contract
                or frozen_snapshot != files):
            raise ValueError("project raw receipt binding mismatch")
        _command_integrity(receipt, root)
        for command in receipt["command_receipts"]:
            prefix = command["id"]
            if strict_json(_regular(root / (prefix + ".receipt.json"))) != command:
                raise ValueError("persisted command receipt mismatch")
            dispatch = strict_json(_regular(root / (prefix + ".start.json")))
            if type(dispatch) is not dict or dispatch.get("argv") != command["argv"]:
                raise ValueError("persisted dispatch argv mismatch")
            for key in ("stdout", "stderr"):
                observed = _regular(root / (prefix + "." + key + ".raw"))
                if sha(observed) != command[key + "_sha256"] or len(observed) != command[key + "_bytes"]:
                    raise ValueError("persisted raw command stream mismatch")
        def one(label):
            observed = strict_json(_regular(root / (label + ".stdout.raw")))
            if type(observed) is not list or len(observed) != 1 or type(observed[0]) is not dict:
                raise ValueError("original inspect JSON schema")
            return observed[0]
        try:
            image = _verify_image(one("01-image-inspect"))
            if image["Id"] != receipt["image_id"]:
                raise ValueError("actual image ID binding mismatch")
            for prefix in ("03-inspect-before", "05-inspect-after", "06-cleanup-inspect"):
                inspected = _verify_container(one(prefix), image, receipt["owner"], receipt["container_id"], root)
                if prefix != "03-inspect-before" and (inspected.get("State", {}).get("Running") is not False or inspected.get("State", {}).get("ExitCode") != 0):
                    raise ValueError("original container exit observation mismatch")
        except Failure as error:
            raise ValueError("original isolation/image/owner receipt mismatch") from error
        absent = receipt["command_receipts"][-1] | {
            "stdout": _regular(root / "08-confirm-absent.stdout.raw"),
            "stderr": _regular(root / "08-confirm-absent.stderr.raw"),
        }
        if not _confirmed_absent(absent, receipt["container_id"]):
            raise ValueError("original container absence not confirmed")
    return validate_receipt(files, contract, receipt), receipt, sha(raw)


class ValidationUnavailable(Enum):
    """Caller-observed journal states, never inferred from model prose.

    NOT_RUN requires an independently checked absence of validation events;
    missing or unverified evidence is UNKNOWN instead.
    """
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"


_PUBLIC_SUMMARY_TOKEN = object()
_TEST_COUNTS = ("tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")


class _VerifiedExecutionSummary(bytes):
    """In-process immutable output of the original-receipt verifier only."""
    __slots__ = ()

    def __new__(cls, value, token):
        if token is not _PUBLIC_SUMMARY_TOKEN:
            raise ValueError("original-receipt verifier summary required")
        return super().__new__(cls, canonical(value))


def _verified_execution_summary(checked, receipt):
    if checked.get("integrity_ok") is not True:
        return ValidationUnavailable.UNKNOWN
    # Never retain IDs, modules, argv, expected values, streams or diagnostics.
    rows = []
    for row in receipt["checks"]:
        outcome = row["outcome"]
        counts = ({key: outcome[key] for key in _TEST_COUNTS}
                  if row["recipe"] == "unittest" and outcome is not None
                  and outcome["completed"] is True and not row["timeout"]
                  and not row["truncated"] else None)
        rows.append({"recipe": row["recipe"], "counts": counts,
                     "timeout": row["timeout"], "truncated": row["truncated"]})
    return _VerifiedExecutionSummary({
        "snapshot_sha256": receipt["snapshot_sha256"], "ok": checked["ok"],
        "checks_total": checked["checks_total"], "checks_passed": checked["checks_passed"],
        "container_removed": receipt["container_removed"], "scratch_removed": receipt["scratch_removed"],
        "rows": rows}, _PUBLIC_SUMMARY_TOKEN)


def public_validation_facts(summary, public_recipes, *, current_snapshot_sha256):
    """Redact one verified validation, without executing or rereading evidence.

    `public_recipes` is the registered public tuple of recipe *kinds*, in order;
    it contains no private check/test IDs or expected answers. An auditor obtains
    the owned summary with read_project_receipt(include_public_summary=True),
    writes these facts into its bound proof, and manual consumers use that proof.
    Counts describe test executions in this validation, not unique project tests.
    This process boundary does not defend against arbitrary trusted Python code.
    """
    if (type(public_recipes) is not tuple or not 1 <= len(public_recipes) <= MAX_CHECKS
            or any(type(recipe) is not str or recipe not in {"unittest", "import", "module"}
                   for recipe in public_recipes)
            or type(current_snapshot_sha256) is not str or not HEX.fullmatch(current_snapshot_sha256)):
        raise ValueError("typed public recipes and current snapshot required")
    counts = {key: 0 for key in _TEST_COUNTS}
    units = public_recipes.count("unittest")
    facts = {"schema": "public-project-validation-facts-v1",
             "current_validation": "UNKNOWN", "observed_validation": "UNKNOWN",
             "execution": {"status": "UNKNOWN", "unknown": True,
                           "container_removed": None, "scratch_removed": None},
             "checks": {"registered": len(public_recipes), "passed": None, "failed": None,
                        "timed_out": None, "truncated": None},
             "unittest": {"status": "UNKNOWN" if units else "NOT_RUN", "registered_recipe_count": units,
                          "completed_recipe_count": None, "counts": None, "known_counts": None,
                          "count_scope": "test-executions-in-this-validation-not-unique-tests"}}
    if type(summary) is ValidationUnavailable:
        if summary is ValidationUnavailable.NOT_RUN:
            facts["current_validation"] = facts["observed_validation"] = "NOT_RUN"
            facts["execution"].update(status="NOT_RUN", unknown=False)
            facts["unittest"]["status"] = "NOT_RUN"
        return facts
    if type(summary) is not _VerifiedExecutionSummary:
        raise ValueError("owned independently verified execution summary required")
    value = strict_json(bytes(summary))
    if tuple(row["recipe"] for row in value["rows"]) != public_recipes:
        raise ValueError("verified/public recipe coverage differs")
    observed = "PASSED" if value["ok"] else "FAILED"
    facts["observed_validation"] = observed
    facts["current_validation"] = (observed if value["snapshot_sha256"] == current_snapshot_sha256 else "STALE")
    facts["execution"].update(status="EXECUTED", unknown=False,
                             container_removed=value["container_removed"], scratch_removed=value["scratch_removed"])
    facts["checks"].update(passed=value["checks_passed"], failed=value["checks_total"] - value["checks_passed"],
                          timed_out=sum(row["timeout"] for row in value["rows"]),
                          truncated=sum(row["truncated"] for row in value["rows"]))
    known = [row["counts"] for row in value["rows"] if row["recipe"] == "unittest" and row["counts"] is not None]
    for row in known:
        for key in _TEST_COUNTS:
            counts[key] += row[key]
    facts["unittest"].update(status="NOT_RUN" if not units else "COMPLETE" if len(known) == units else "INCOMPLETE",
                             completed_recipe_count=len(known), known_counts=counts if known else None,
                             counts=counts.copy() if units and len(known) == units else None)
    return facts


def read_project_receipt(files, contract, artifacts, receipt_sha256=None, *, include_public_summary=False):
    """Pure original-receipt read; malformed JSON shapes become ValueError."""
    if type(include_public_summary) is not bool:
        raise ValueError("explicit public-summary option required")
    try:
        checked, receipt, digest = _read_project_receipt(files, contract, artifacts, receipt_sha256)
        if include_public_summary:
            return checked, receipt, digest, _verified_execution_summary(checked, receipt)
        return checked, receipt, digest
    except (TypeError, KeyError, AttributeError, IndexError, UnicodeError, RecursionError, Failure) as error:
        raise ValueError("malformed original project receipt") from error


def validate_with_project_execution(files, contract, artifacts, remaining_seconds):
    """Broker convenience: one execution followed by pure original-receipt read."""
    started = time.monotonic()
    snapshot = sha(canonical({p: sha(t.encode()) for p, t in files.items()}))
    summary = execution_summary(snapshot, _check_count(contract), status="INFRASTRUCTURE_FAILED")
    try:
        returned = execute_project(files, contract, artifacts, remaining_seconds)
        behavior, receipt, digest = read_project_receipt(files, contract, artifacts)
        if canonical(returned) != canonical(receipt):
            raise ValueError("returned and persisted project receipt mismatch")
        summary.update(status=receipt["status"], unknown=receipt["unknown"],
                       contract_sha256=receipt.get("contract_sha256"), runner_sha256=receipt.get("runner_sha256"),
                       input_sha256=receipt.get("input_sha256"), image_id=receipt.get("image_id"),
                       output_sha256=receipt.get("output_sha256"), container_removed=receipt.get("container_removed"),
                       scratch_removed=receipt.get("scratch_removed"), receipt_ref="result.json", receipt_sha256=digest)
    except (ValueError, TypeError, KeyError, UnicodeError, OSError, RecursionError, SyntaxError):
        summary.update(status="TERMINAL_UNKNOWN", unknown=True)
        behavior = {"ok": False, "integrity_ok": False, "suite": EXECUTION_SUITE, "checks_passed": 0,
                    "checks_total": _check_count(contract), "failures": ["project-receipt-invalid"], "diagnostics": []}
    summary["observed_wall_seconds"] = time.monotonic() - started
    return behavior, summary
