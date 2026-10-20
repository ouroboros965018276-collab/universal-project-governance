"""Opt-in finite CPython execution transport; import performs no work.
No quality decision is made here. Caller must preserve the original VM contract,
required-call/data-dependency gates and exact-type expected-value comparison.
Only the existing finite VM syntax is admitted. This is not arbitrary Python or
complete-application validation, nor a proof of Docker/kernel vulnerability absence.
No actual Docker execution is authorized by importing or testing this module.
"""
from __future__ import annotations
import ast
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import queue
import re
import stat
import subprocess
import threading
import time
import uuid

DOCKER = r"D:\DockerDesktop\resources\bin\docker.exe"
IMAGE = "docker.io/library/python@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d"
PLATFORM = "linux/amd64"
VM_SHA256 = "cf6a6c207c47f003e7877b2a7f93c7e192415ffa229e80693276d1fb23298286"
OUTPUT_LIMIT = 65536
PROXY_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "FTP_PROXY", "ALL_PROXY", "NO_PROXY",
               "http_proxy", "https_proxy", "ftp_proxy", "all_proxy", "no_proxy")
SECRET = re.compile(rb"(?i)(?:https?://[^/\s:@]+:[^/\s@]+@|authorization\s*:|bearer\s+[A-Za-z0-9_.-]{12,}|sk-[A-Za-z0-9_-]{12,})")

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def sha(x):
    return hashlib.sha256(x).hexdigest()

def strict_json(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise ValueError("duplicate JSON key")
            d[k] = v
        return d
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))

def value(x, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    if count[0] > 32768 or depth > 24: raise ValueError("value bound")
    if x is None or type(x) is bool: return
    if type(x) is int and x.bit_length() <= 256: return
    if type(x) is str and len(x) <= 16384: return
    if type(x) is list and len(x) <= 4096:
        for y in x: value(y, depth+1, count)
        return
    if type(x) is dict and len(x) <= 4096 and all(type(k) is str and len(k) <= 256 for k in x):
        for y in x.values(): value(y, depth+1, count)
        return
    raise ValueError("unsupported value")

def _capture(argv, deadline):
    """Bound stdout+stderr while consuming, not after communicate/run(PIPE)."""
    begin = time.monotonic()
    if begin >= deadline:
        return {"status": "timeout", "exit_code": None, "stdout": b"", "stderr": b"", "observed_bytes": 0}
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, shell=False, creationflags=flags, bufsize=0)
    except OSError:
        return {"status": "launch-error", "exit_code": None, "stdout": b"", "stderr": b"", "observed_bytes": 0}
    q, stop = queue.Queue(maxsize=8), threading.Event()
    def reader(name, stream):
        failed = False
        try:
            while not stop.is_set():
                chunk = stream.read(4096)
                if not chunk: break
                while not stop.is_set():
                    try: q.put((name, chunk), timeout=.02); break
                    except queue.Full: pass
        except Exception as error:
            failed = True
            while not stop.is_set():
                try: q.put(("read-error", (name,type(error).__name__)), timeout=.02); break
                except queue.Full: pass
        finally:
            if not failed:
                while not stop.is_set():
                    try: q.put((name, None), timeout=.02); break
                    except queue.Full: pass
    threads = [threading.Thread(target=reader, args=(name, stream), daemon=True)
               for name, stream in (("stdout", p.stdout), ("stderr", p.stderr))]
    for t in threads: t.start()
    data, ended, observed, status = {"stdout": bytearray(), "stderr": bytearray()}, set(), 0, "completed"
    try:
        while len(ended) < 2:
            if time.monotonic() >= deadline: status = "timeout"; break
            try: name, chunk = q.get(timeout=min(.02, max(.001, deadline-time.monotonic())))
            except queue.Empty: continue
            if name == "read-error": status = "stream-error"; break
            if chunk is None: ended.add(name); continue
            observed += len(chunk)
            room = OUTPUT_LIMIT - sum(map(len, data.values()))
            data[name].extend(chunk[:max(0, room)])
            if len(chunk) > room: status = "output-limit"; break
        if status != "completed":
            stop.set()
            p.kill()
        try: code = p.wait(timeout=max(.01, min(2., deadline-time.monotonic())))
        except subprocess.TimeoutExpired:
            status = "timeout"; stop.set(); p.kill()
            try: code = p.wait(timeout=1.)
            except subprocess.TimeoutExpired: code = None
    finally:
        stop.set()
        for t in threads: t.join(timeout=.1)
        if any(t.is_alive() for t in threads):
            status = "stream-unconfirmed"
        else:
            for stream in (p.stdout, p.stderr):
                try: stream.close()
                except OSError: pass
    return {"status": status, "exit_code": code, "stdout": bytes(data["stdout"]),
            "stderr": bytes(data["stderr"]), "observed_bytes": observed,
            "wall_seconds": time.monotonic()-begin,
            "output_complete": status == "completed"}

RUNNER = r'''
import builtins, hashlib, json, sys, types
from pathlib import Path
def digest(x): return hashlib.sha256(x).hexdigest()
def encode(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def bounded(x,d=0,n=None):
    n=[0] if n is None else n; n[0]+=1
    if d>24 or n[0]>32768: raise RuntimeError("result bound")
    if x is None or type(x) is bool: return
    if type(x) is int and x.bit_length()<=256: return
    if type(x) is str and len(x)<=16384: return
    if type(x) is list and len(x)<=4096:
        for v in x: bounded(v,d+1,n)
        return
    if type(x) is dict and len(x)<=4096 and all(type(k) is str and len(k)<=256 for k in x):
        for v in x.values(): bounded(v,d+1,n)
        return
    raise RuntimeError("result type")
raw=Path("/runner/input.json").read_bytes()
inp=json.loads(raw); sources={}
for p,h in inp["files_sha256"].items():
    b=(Path("/src")/p).read_bytes()
    if digest(b)!=h: raise RuntimeError("source hash")
    if p.endswith(".py"): sources[p[:-3]]=b.decode("utf-8")
loaded={}; loading=set()
def load(name):
    if name in loaded: return loaded[name]
    if name not in sources or name in loading: raise RuntimeError("module import")
    loading.add(name); mod=types.ModuleType(name)
    safe={k:getattr(builtins,k) for k in ("len","str","int","bool","abs","ValueError","TypeError")}
    safe["__import__"]=registered_import
    mod.__dict__.update({"__builtins__":safe,"__name__":name})
    exec(compile(sources[name],"<registered>","exec"),mod.__dict__)
    loading.remove(name);loaded[name]=mod;return mod
def registered_import(name,globals=None,locals=None,fromlist=(),level=0):
    if level or not fromlist: raise RuntimeError("import shape")
    return load(name)
results=[]
for call in inp["invocations"]:
    try:
        result=getattr(load(call["path"][:-3]),call["function"])(*call["args"],**call["kwargs"])
        bounded(result);out={"id":call["id"],"kind":"return","value":result}
    except (ValueError,TypeError) as e:
        out={"id":call["id"],"kind":"raises","exception":type(e).__name__}
    results.append(out)
record={"schema_version":1,"snapshot_sha256":inp["snapshot_sha256"],"input_sha256":digest(raw),
        "runner_sha256":digest(Path("/runner/runner.py").read_bytes()),"results":results}
payload=encode(record)
if len(payload)>32768: raise RuntimeError("output bound")
sys.stdout.buffer.write(payload+b"\n");sys.stdout.buffer.flush()
'''

BATCH_JSON_BYTES = 131072

class _InputBudget:
    """Count the complete compact UTF8 JSON before allocating its encoding."""
    def __init__(self, deadline, maximum=BATCH_JSON_BYTES):
        self.deadline, self.bytes, self.nodes = deadline, 0, 0
        self.maximum = maximum
    def check(self):
        if time.monotonic() >= self.deadline: raise ValueError("input preparation budget exhausted")
    def add(self, count):
        self.check(); self.bytes += count
        if self.bytes > self.maximum: raise ValueError("whole invocation batch byte bound" if self.maximum==BATCH_JSON_BYTES else "whole file batch JSON byte bound")
    def string(self, text, maximum):
        if type(text) is not str or len(text) > maximum: raise ValueError("string bound")
        self.add(2)
        for ch in text:
            code = ord(ch)
            if 0xD800 <= code <= 0xDFFF: raise ValueError("invalid UTF8 surrogate")
            self.add(2 if ch in '\"\\\b\f\n\r\t' else 6 if code < 32 else 1 if code < 128 else 2 if code < 2048 else 3 if code < 65536 else 4)
    def json(self, item, depth=0):
        self.check(); self.nodes += 1
        if depth > 24 or self.nodes > 32768: raise ValueError("whole invocation node bound")
        if item is None: self.add(4)
        elif type(item) is bool: self.add(4 if item else 5)
        elif type(item) is int and item.bit_length() <= 256: self.add(len(str(item)))
        elif type(item) is str: self.string(item, 16384)
        elif type(item) is list and len(item) <= 4096:
            self.add(2 + max(0,len(item)-1))
            for child in item: self.json(child,depth+1)
        elif type(item) is dict and len(item) <= 4096:
            self.add(2 + max(0,len(item)-1) + len(item))
            for key,child in item.items():
                self.string(key,256); self.json(child,depth+1)
        else: raise ValueError("unsupported value")

def _confirmed_absent(receipt, cid):
    if (receipt.get("status") != "completed" or receipt.get("exit_code") != 1
            or not isinstance(cid,str) or re.fullmatch("[0-9a-f]{64}",cid) is None): return False
    # This fixed form is observed from the same Docker container-inspect entry.
    return (receipt.get("stdout") == b"[]\n"
            and receipt.get("stderr") == ("Error response from daemon: No such container: " + cid + "\n").encode("ascii"))

class Failure(Exception):
    def __init__(self, code, unknown=False):
        self.code, self.unknown = code, unknown

def _profile(files):
    # Reuse the pinned parser only; no task oracle/expectation is constructed.
    vm = importlib.import_module("evolution.semantic_contract")
    if sha(Path(vm.__file__).read_bytes()) != VM_SHA256: raise Failure("VM_SOURCE_CHANGED")
    m = vm._Machine.__new__(vm._Machine)
    m.files = files
    m.contract = {"modules": {p: {} for p in files if p.endswith(".py")}}
    m.limits = dict(vm.DEFAULT_LIMITS)
    m.modules, m.globals, m.functions = {}, {}, {}
    m.steps = m.depth = m.expr_depth = m.calls = 0
    try: m._load()
    except (vm._Stop, SyntaxError, ValueError, RecursionError): raise Failure("PROFILE_REJECTED") from None
    return m

def execute_batch(files, invocations, artifacts, remaining_seconds):
    """Return execution evidence, NEVER semantic quality/PASS.
    Caller supplies an already verified broker snapshot, not workspace paths.
    Original host VM required_calls/route and expected-value gates are mandatory
    in any future integration; this interface cannot establish those by itself.
    """
    started=time.monotonic()
    if type(remaining_seconds) not in (int,float) or not math.isfinite(remaining_seconds) or remaining_seconds<=0: raise ValueError("finite remaining wall budget required")
    total_deadline=started+min(float(remaining_seconds),60.)
    deadline=total_deadline-min(8.,(total_deadline-started)/2)
    budget=_InputBudget(deadline)
    source_bytes=0
    if type(files) is not dict or not 1 <= len(files) <= 128: raise ValueError("flat file map required")
    file_budget=_InputBudget(deadline,1048576)
    file_budget.add(2+max(0,len(files)-1)+len(files))
    for p,t in files.items():
        if (type(p) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,127}",p)
                or p in {".",".."} or type(t) is not str or len(t)>262144):
            raise ValueError("invalid registered UTF8 file")
        if p.endswith(".py") and not p[:-3].isidentifier(): raise ValueError("invalid module name")
        budget.check(); raw=t.encode("utf-8"); budget.check(); source_bytes+=len(raw)
        if len(raw)>262144 or source_bytes>1048576: raise ValueError("snapshot byte bound")
        if SECRET.search(raw): raise ValueError("credential-like input rejected")
        file_budget.string(p,128);file_budget.string(t,262144)
    if type(invocations) is not list or not 1 <= len(invocations) <= 64: raise ValueError("bounded invocations required")
    ids=set(); budget.add(2+max(0,len(invocations)-1))
    for c in invocations:
        if type(c) is not dict or set(c)!={"id","path","function","args","kwargs"}: raise ValueError("no oracle/extra fields")
        if type(c["id"]) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",c["id"]) or c["id"] in ids: raise ValueError("unique call id")
        ids.add(c["id"])
        if type(c["path"]) is not str or c["path"] not in files or not c["path"].endswith(".py") or type(c["function"]) is not str or not c["function"].isidentifier() or c["function"].startswith("__"): raise ValueError("registered function required")
        if type(c["args"]) is not list or type(c["kwargs"]) is not dict or any(type(k) is not str or not k.isidentifier() or k.startswith("__") for k in c["kwargs"]): raise ValueError("invalid call")
        budget.json(c)
    if file_budget.bytes+budget.bytes>1048576: raise ValueError("whole files and invocation JSON byte bound")
    budget.check(); invocation_raw=canonical(invocations); budget.check()
    if len(invocation_raw)!=budget.bytes or len(invocation_raw)>BATCH_JSON_BYTES: raise ValueError("invocation encoding byte mismatch")
    if SECRET.search(invocation_raw): raise ValueError("credential-like invocation rejected")
    target=Path(artifacts)
    if not target.is_absolute() or target.exists() or not target.parent.is_dir(): raise ValueError("new owned absolute artifact path required")
    parent=target.parent.resolve(strict=True);root=parent/target.name
    if target.name in {".","..",".git"}: raise ValueError("invalid artifact leaf")
    budget.check(); root.mkdir(); budget.check()
    cleanup_deadline=lambda:total_deadline
    name="rc20-realpy-"+uuid.uuid4().hex
    cid=None;attempted=False;removed=False;command_index=0
    snapshot={}
    for p,t in files.items():
        budget.check(); snapshot[p]=sha(t.encode()); budget.check()
    snapshot_sha=sha(canonical(snapshot));input_obj={"schema_version":1,"files_sha256":snapshot,"snapshot_sha256":snapshot_sha,"invocations":invocations}
    budget.check(); input_raw=canonical(input_obj); runner_raw=RUNNER.encode(); budget.check()
    if len(input_raw)>262144: raise ValueError("encoded input bound")
    cleanup_phase=False
    result={"status":"NOT_EXECUTED","quality_assessed":False,"results":None,"unknown":False,
            "required_host_gates":["original VM contract/required_calls/data-dependency route","original _same exact-type expected-value comparison"],
            "snapshot_sha256":snapshot_sha,"runner_sha256":sha(runner_raw),"input_sha256":sha(input_raw),
            "image_reference":IMAGE,"platform":PLATFORM,"container_removed":False}
    def phase_check(until=None):
        limit=(total_deadline if cleanup_phase else deadline) if until is None else until
        if time.monotonic() >= limit: raise Failure("LOCAL_BUDGET_EXHAUSTED",attempted)
    def staged(path,raw,until=None):
        phase_check(until)
        with path.open("xb") as f: f.write(raw);f.flush();os.fsync(f.fileno())
        phase_check(until)
    def write(name,raw,until=None):
        staged(root/name,raw,until)
    def command(label,args,until=None,inspect=False,allow_error=False):
        nonlocal command_index
        limit=(total_deadline if cleanup_phase else deadline) if until is None else until
        phase_check(limit)
        command_index+=1;prefix=f"{command_index:02d}-{label}"
        write(prefix+".start.json",canonical({"argv":[DOCKER]+args,"monotonic":time.monotonic()}),limit)
        phase_check(limit)
        r=_capture([DOCKER]+args,limit)
        stdout,stderr=r["stdout"],r["stderr"]
        # Returned observations use the reserved total budget, never extend dispatch.
        sensitive_inspect=False
        for key,raw in (("stdout",stdout),("stderr",stderr)):
            if SECRET.search(raw):
                sensitive_inspect=sensitive_inspect or inspect
            else:
                write(prefix+"."+key+".raw",raw,total_deadline)
        write(prefix+".receipt.json",canonical({k:v for k,v in r.items() if k not in {"stdout","stderr"}}|
              {"stdout_sha256":sha(stdout),"stderr_sha256":sha(stderr),"argv":[DOCKER]+args}),total_deadline)
        if sensitive_inspect:raise Failure("SENSITIVE_INSPECT_OUTPUT",True)
        if not allow_error and (r["status"]!="completed" or r["exit_code"]!=0): raise Failure("COMMAND_"+label,r["status"]!="completed" or label in {"create","start","wait","logs","inspect-after"})
        return r
    def obj(raw):
        x=strict_json(raw)
        if type(x) is not list or len(x)!=1 or type(x[0]) is not dict: raise Failure("INSPECT_SHAPE",True)
        return x[0]
    def ownership(x):
        return x.get("Name")=="/"+name and x.get("Config",{}).get("Labels",{}).get("upg.executor.owner")==name and re.fullmatch("[0-9a-f]{64}",x.get("Id","")) and (cid is None or x["Id"]==cid)
    def hostpath(s):
        s=s.replace("\\","/").rstrip("/")
        for prefix in ("/run/desktop/mnt/host/","/host_mnt/"):
            if s.startswith(prefix):
                t=s[len(prefix):]
                if len(t)>2 and t[1]=="/":s=t[0]+":/"+t[2:]
        return s.casefold()
    def verify(x,image_env):
        if not ownership(x):raise Failure("OWNER_MISMATCH",True)
        h,c=x.get("HostConfig",{}),x.get("Config",{})
        expected={"NetworkMode":"none","ReadonlyRootfs":True,"Privileged":False,"Memory":536870912,
                  "MemorySwap":536870912,"NanoCpus":1000000000,"PidsLimit":64,"Init":True,"CgroupnsMode":"private","IpcMode":"private"}
        if any(h.get(k)!=v for k,v in expected.items()) or h.get("CapDrop")!=["ALL"] or h.get("CapAdd") not in (None,[]) or h.get("SecurityOpt")!=["no-new-privileges=true"]:raise Failure("CONFIG_MISMATCH",True)
        if c.get("User")!="65534:65534" or c.get("WorkingDir")!="/tmp" or h.get("PidMode") not in ("",None) or h.get("PortBindings") not in ({},None) or h.get("Devices") not in ([],None) or h.get("DeviceRequests") not in ([],None):raise Failure("CONFIG_MISMATCH",True)
        if set(c.get("Env",[]))!=set(image_env)|{p+"=" for p in PROXY_NAMES} or len(c.get("Env",[]))!=len(set(c.get("Env",[]))):raise Failure("ENV_MISMATCH",True)
        if c.get("Volumes") not in (None,{}) or h.get("RestartPolicy",{}).get("Name")!="no" or x.get("Image")!=image.get("Id") or c.get("Image")!=IMAGE or x.get("Path")!="/usr/bin/env" or x.get("Args")!=["-i","LC_ALL=C.UTF-8","/usr/local/bin/python","-I","-B","/runner/runner.py"]:raise Failure("IMAGE_OR_ENTRYPOINT_MISMATCH",True)
        mounts=x.get("Mounts",[])
        if len(mounts)!=2 or {m.get("Destination") for m in mounts}!={"/src","/runner"}:raise Failure("MOUNT_MISMATCH",True)
        for m in mounts:
            expected_path=root/("src" if m["Destination"]=="/src" else "runner")
            if m.get("Type")!="bind" or m.get("RW") is not False or hostpath(m.get("Source",""))!=hostpath(str(expected_path)):raise Failure("MOUNT_MISMATCH",True)
        if h.get("Tmpfs")!={"/tmp":"rw,nosuid,nodev,noexec,size=32m,uid=65534,gid=65534"}:raise Failure("TMPFS_MISMATCH",True)
        return x
    try:
        phase_check(); m=_profile(files); phase_check()
        if any((c["path"],c["function"]) not in m.functions for c in invocations):raise Failure("FUNCTION_NOT_REGISTERED")
        (root/"src").mkdir();(root/"runner").mkdir()
        for p,t in files.items():
            staged(root/"src"/p,t.encode())
        staged(root/"runner"/"runner.py",runner_raw);staged(root/"runner"/"input.json",input_raw)
        write("snapshot.received.json",canonical(files))
        write("runner.frozen.py",runner_raw);write("input.frozen.json",input_raw)
        write("binding.json",canonical(result|{"files_sha256":snapshot,"profile":"pinned VM parser only; original semantic/dependency gates remain host-owned","total_budget_seconds":total_deadline-started,"cleanup_reserve_seconds":total_deadline-deadline}))
        image=obj(command("image-inspect",["image","inspect",IMAGE])["stdout"])
        digest=IMAGE.split("@")[1]
        if image.get("Os")!="linux" or image.get("Architecture")!="amd64" or image.get("Descriptor",{}).get("digest")!=digest or "python@"+digest not in image.get("RepoDigests",[]):raise Failure("IMAGE_MISMATCH")
        image_env=image.get("Config",{}).get("Env",[])
        write("image-binding.json",canonical({"image_id":image.get("Id"),"descriptor":image.get("Descriptor"),"repo_digests":image.get("RepoDigests"),"resource_profile":"512MiB/1CPU/pids64/32MiB-tmpfs"}))
        args=["create","--name",name,"--label","upg.executor.owner="+name,"--platform",PLATFORM,"--pull","never","--network","none","--user","65534:65534","--cap-drop","ALL","--security-opt","no-new-privileges=true","--read-only","--memory","512m","--memory-swap","512m","--cpus","1","--pids-limit","64","--init","--cgroupns","private","--ipc","private","--restart","no","--stop-timeout","1","--no-healthcheck","--workdir","/tmp","--tmpfs","/tmp:rw,nosuid,nodev,noexec,size=32m,uid=65534,gid=65534"]
        for leaf,dest in (("src","/src"),("runner","/runner")):args+=["--mount","type=bind,source="+str(root/leaf)+",target="+dest+",readonly"]
        for p in PROXY_NAMES:args+=["--env",p+"="]
        args+=["--entrypoint","/usr/bin/env",IMAGE,"-i","LC_ALL=C.UTF-8","/usr/local/bin/python","-I","-B","/runner/runner.py"]
        attempted=True;r=command("create",args)
        cid=r["stdout"].decode("ascii").strip()
        if not re.fullmatch("[0-9a-f]{64}",cid):cid=None;raise Failure("CREATE_ID_UNCONFIRMED",True)
        x=verify(obj(command("inspect-before",["container","inspect",cid],inspect=True)["stdout"]),image_env)
        write("verified-container-before.json",canonical(x))
        command("start",["container","start",cid])
        wait=command("wait",["container","wait",cid])
        logs=command("logs",["container","logs",cid])
        x=verify(obj(command("inspect-after",["container","inspect",cid],inspect=True)["stdout"]),image_env)
        write("verified-container-after.json",canonical(x))
        if wait["stdout"].strip()!=b"0" or x.get("State",{}).get("Running") is not False or x.get("State",{}).get("ExitCode")!=0 or logs["stderr"]:raise Failure("PROCESS_OR_STDERR_FAILURE")
        out=strict_json(logs["stdout"])
        if type(out) is not dict or set(out)!={"schema_version","snapshot_sha256","input_sha256","runner_sha256","results"} or type(out["schema_version"]) is not int or out["schema_version"]!=1:raise Failure("OUTPUT_SCHEMA")
        if any(out[k]!=result[k] for k in ("snapshot_sha256","input_sha256","runner_sha256")):raise Failure("OUTPUT_BINDING")
        rows=out["results"]
        if type(rows) is not list or len(rows)!=len(invocations):raise Failure("OUTPUT_COVERAGE")
        for c,row in zip(invocations,rows):
            if type(row) is not dict or row.get("id")!=c["id"]:raise Failure("OUTPUT_ID")
            if row.get("kind")=="return" and set(row)=={"id","kind","value"}:value(row["value"])
            elif row.get("kind")=="raises" and set(row)=={"id","kind","exception"} and row["exception"] in {"ValueError","TypeError"}:pass
            else:raise Failure("OUTPUT_TAG")
        if any(sha((root/"src"/p).read_bytes())!=h for p,h in snapshot.items()) or sha((root/"runner"/"runner.py").read_bytes())!=result["runner_sha256"] or sha((root/"runner"/"input.json").read_bytes())!=result["input_sha256"]:raise Failure("FROZEN_BYTES_CHANGED",True)
        result.update(status="EXECUTED",results=rows,image_id=image.get("Id"),observed_image_descriptor=image.get("Descriptor"),output_sha256=sha(logs["stdout"]))
    except Failure as e:result.update(status=e.code,unknown=e.unknown)
    except (ValueError,TypeError,KeyError,UnicodeError,OSError,RecursionError) as e:result.update(status="MALFORMED_OR_IO_FAILURE",unknown=True,error_type=type(e).__name__)
    finally:
        cleanup_phase=True
        if attempted:
            try:
                # Resolve uncertain create/start by unique name; never replay either.
                r=command("cleanup-inspect",["container","inspect",cid or name],until=cleanup_deadline(),inspect=True,allow_error=True)
                if r["status"]=="completed" and r["exit_code"]==0:
                    x=obj(r["stdout"])
                    if not ownership(x):raise Failure("CLEANUP_OWNER_MISMATCH",True)
                    cid=x["Id"]
                    rr=command("remove-owned",["container","rm","--force",cid],until=cleanup_deadline(),allow_error=True)
                    check=command("confirm-absent",["container","inspect",cid],until=cleanup_deadline(),inspect=True,allow_error=True)
                    removed=rr["status"]=="completed" and rr["exit_code"]==0 and _confirmed_absent(check,cid)
                # Absence after uncertain create is not proof of no dispatch/execution.
                if not removed:result.update(unknown=True,cleanup_unconfirmed=True)
            except (Failure,ValueError,TypeError,KeyError,UnicodeError,OSError):result.update(unknown=True,cleanup_unconfirmed=True)
        result["container_removed"]=removed
        if attempted and not removed and result["status"]=="EXECUTED":result.update(status="CLEANUP_UNCONFIRMED",results=None)
        for leaf,expected in (("src",set(files)),("runner",{"runner.py","input.json"})):
            p=root/leaf
            if p.is_symlink() or getattr(p,"is_junction",lambda:False)() or p.resolve().parent!=root.resolve():
                result.update(unknown=True,scratch_cleanup_unconfirmed=True)
            elif p.is_dir():
                try:
                    phase_check(total_deadline);children=list(p.iterdir())
                    write(leaf+".cleanup-byte-map.json",canonical({x.name:sha(x.read_bytes()) for x in children if x.is_file() and not x.is_symlink()}))
                    if {x.name for x in children}<=expected and all(x.is_file() and not x.is_symlink() for x in children):
                        for x in children:
                            phase_check(total_deadline);x.unlink();phase_check(total_deadline)
                        phase_check(total_deadline);p.rmdir();phase_check(total_deadline)
                    else:result.update(unknown=True,scratch_cleanup_unconfirmed=True)
                except (Failure,OSError,ValueError):result.update(unknown=True,scratch_cleanup_unconfirmed=True)
        if result["status"]=="EXECUTED" and result["unknown"]:
            result.update(status="INTEGRITY_UNCONFIRMED",results=None)
        result["wall_seconds"]=time.monotonic()-started
        result["command_count"]=command_index
        result["no_quality_decision"]=True
        try:write("result.json",canonical(result),total_deadline)
        except (Failure,OSError):
            result.update(unknown=True,evidence_persistence_unconfirmed=True)
            if result["status"]=="EXECUTED":result.update(status="INTEGRITY_UNCONFIRMED",results=None)
            result["wall_seconds"]=time.monotonic()-started
    return result


EXECUTION_BACKEND = "docker-cpython-finite-v1"
EXECUTION_SUITE = "registered-real-cpython-contracts-v1"
EXECUTION_SUMMARY_FIELDS = frozenset({
    "backend", "status", "unknown", "received_snapshot_sha256", "runner_sha256",
    "input_sha256", "image_reference", "platform", "output_sha256", "probe_count",
    "container_removed", "receipt_ref", "receipt_sha256", "observed_wall_seconds",
})


def execution_summary(snapshot_sha256, probe_count=0, *, status="NOT_APPLICABLE", elapsed=0.):
    """Public metadata only; image/platform describe configuration, not execution."""
    return {"backend": EXECUTION_BACKEND, "status": status, "unknown": False,
            "received_snapshot_sha256": snapshot_sha256, "runner_sha256": None,
            "input_sha256": None, "image_reference": IMAGE, "platform": PLATFORM,
            "output_sha256": None, "probe_count": probe_count, "container_removed": None,
            "receipt_ref": None, "receipt_sha256": None, "observed_wall_seconds": elapsed}


def reserve_execution_artifacts(project_root, artifacts, deadline):
    """Reserve one new outside-project directory; an existing fence is never reused."""
    if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= time.time():
        raise ValueError("execution backend requires a future absolute wall deadline")
    if not isinstance(artifacts, (str, os.PathLike)):
        raise ValueError("execution backend requires a new absolute artifact directory")
    target = Path(artifacts)
    if (not target.is_absolute() or target.name in {"", ".", "..", ".git"}
            or target.exists() or target.is_symlink() or not target.parent.is_dir()):
        raise ValueError("execution artifacts require a new path with an existing parent")
    for parent in (target.parent, *target.parent.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ValueError("execution artifact reparse parents are forbidden")
    target = target.parent.resolve(strict=True) / target.name
    project = Path(project_root).resolve(strict=True)
    if target == project or project in target.parents or target in project.parents:
        raise ValueError("execution artifacts must be outside the project")
    target.mkdir()  # Exclusive directory is the non-reusable broker fence.
    return target


def _receipt_bytes(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 1024 or info.st_size > OUTPUT_LIMIT):
        raise ValueError("execution receipt is not a bounded owned regular file")
    return path.read_bytes()


def validate_with_execution(files, contract, artifacts, remaining_seconds):
    """Full original VM gate, then CPython transport, then original exact oracle.

    The external result receipt may contain invocation/return data. Only this
    bounded summary is returned to the agent. Expected values never enter the
    primitive, its scratch files, mounts, command line, or container.
    """
    started = time.monotonic()
    snapshot = {name: sha(text.encode("utf-8")) for name, text in files.items()}
    snapshot_sha = sha(canonical(snapshot))
    vm = importlib.import_module("evolution.semantic_contract")
    if sha(Path(vm.__file__).read_bytes()) != VM_SHA256:
        summary = execution_summary(snapshot_sha, len(contract["probes"]), status="INFRASTRUCTURE_FAILED",
                                    elapsed=time.monotonic() - started)
        summary["unknown"] = True
        return {"ok": False, "failures": [{"code": "behavior-contract-failed"}]}, summary
    behavior = vm.validate_behavior(files, contract)
    summary = execution_summary(snapshot_sha, len(contract["probes"]), status="NOT_RUN_VM_FAILED")
    if not behavior["ok"]:
        summary["observed_wall_seconds"] = time.monotonic() - started
        return behavior, summary
    invocations = [{"id": "probe-%04d" % index, "path": probe["path"],
                    "function": probe["function"], "args": probe.get("args", []),
                    "kwargs": probe.get("kwargs", {})}
                   for index, probe in enumerate(contract["probes"], 1)]
    summary.update(status="INFRASTRUCTURE_FAILED", unknown=True)
    receipt = Path(artifacts) / "result.json"
    record = None
    try:
        remaining = remaining_seconds - (time.monotonic() - started)
        record = execute_batch(files, invocations, artifacts, remaining)
        raw = _receipt_bytes(receipt)
        summary.update(receipt_ref=Path(artifacts).name + "/result.json", receipt_sha256=sha(raw))
        # AND the returned observation with the immutable bytes, especially when
        # final fsync crossed total_deadline after writing an older success file.
        if (type(record) is not dict or raw != canonical(record)
                or strict_json(raw) != record or type(record.get("unknown")) is not bool
                or type(record.get("container_removed")) is not bool
                or record.get("quality_assessed") is not False or record.get("no_quality_decision") is not True
                or any(record.get(key) for key in ("cleanup_unconfirmed", "scratch_cleanup_unconfirmed", "evidence_persistence_unconfirmed"))):
            raise ValueError("unconfirmed execution result")
        input_raw = canonical({"schema_version": 1, "files_sha256": snapshot,
                               "snapshot_sha256": snapshot_sha, "invocations": invocations})
        bindings = {"snapshot_sha256": snapshot_sha, "runner_sha256": sha(RUNNER.encode()),
                    "input_sha256": sha(input_raw), "image_reference": IMAGE, "platform": PLATFORM}
        if any(record.get(key) != wanted for key, wanted in bindings.items()):
            raise ValueError("execution result binding mismatch")
        if record.get("status") != "EXECUTED":
            # A complete known failure is not an unknown execution state. This
            # never makes infrastructure failure recoverable or quality-pass.
            no_create = not any(Path(artifacts).glob("*-create.start.json"))
            if record["unknown"] is False and (record["container_removed"] or no_create):
                summary.update(unknown=False, container_removed=record["container_removed"])
            raise ValueError("execution did not complete")
        if record["unknown"] is not False or record["container_removed"] is not True:
            raise ValueError("execution state is unconfirmed")
        output = _receipt_bytes(Path(artifacts) / "06-logs.stdout.raw")
        if record.get("output_sha256") != sha(output):
            raise ValueError("execution output binding mismatch")
        payload = strict_json(output)
        expected_keys = {"schema_version", "snapshot_sha256", "runner_sha256", "input_sha256", "results"}
        if (type(payload) is not dict or set(payload) != expected_keys
                or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                or any(payload.get(key) != bindings[key] for key in ("snapshot_sha256", "runner_sha256", "input_sha256"))
                or canonical(payload["results"]) != canonical(record.get("results"))):
            raise ValueError("execution output receipt mismatch")
        rows = record["results"]
        if type(rows) is not list or len(rows) != len(invocations):
            raise ValueError("execution result coverage mismatch")
        matched = True
        for invocation, probe, row in zip(invocations, contract["probes"], rows):
            if type(row) is not dict or row.get("id") != invocation["id"]:
                raise ValueError("execution result id mismatch")
            expected = probe["expect"]
            if row.get("kind") == "return" and set(row) == {"id", "kind", "value"}:
                value(row["value"])
                matched &= "return" in expected and vm._same(row["value"], expected.get("return"))
            elif row.get("kind") == "raises" and set(row) == {"id", "kind", "exception"} and row["exception"] in {"ValueError", "TypeError"}:
                matched &= expected.get("raises") == row["exception"]
            else:
                raise ValueError("execution result tag mismatch")
        summary.update(status="EXECUTED", unknown=False, container_removed=True,
                       runner_sha256=bindings["runner_sha256"], input_sha256=bindings["input_sha256"],
                       output_sha256=record["output_sha256"])
        if not matched:
            behavior = dict(behavior, ok=False, status="FAIL", failures=[{"code": "behavior-contract-failed"}])
    except (Failure, OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        # Preserve any available raw receipt hash; never rewrite a stale result.
        if summary["receipt_ref"] is None:
            try:
                raw = _receipt_bytes(receipt)
                summary.update(receipt_ref=Path(artifacts).name + "/result.json", receipt_sha256=sha(raw))
            except (OSError, ValueError):
                pass
        behavior = dict(behavior, ok=False, status="FAIL", failures=[{"code": "behavior-contract-failed"}])
    summary["observed_wall_seconds"] = time.monotonic() - started
    return behavior, summary
