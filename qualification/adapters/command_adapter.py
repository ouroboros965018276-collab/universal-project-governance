from __future__ import annotations
import hashlib,json,os,pathlib,re,subprocess,tempfile,time
from qualification.lib.contracts import validate_node

def _expand(items,values):
    return [str(x).format(**values) for x in items]

class CommandAdapter(object):
    def __init__(self,config,base_dir=None):
        self.config=config
        self.base_dir=pathlib.Path(base_dir).resolve() if base_dir else pathlib.Path(__file__).resolve().parent

    def identity(self):
        canonical=json.dumps(self.config,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
        runtime_files={"command_adapter.py":pathlib.Path(__file__).read_bytes()}
        for raw in self.config.get("adapter_runtime_files",[]):
            path=pathlib.Path(raw)
            if not path.is_absolute(): path=self.base_dir/path
            if path.is_symlink(): raise ValueError("adapter runtime file is unavailable or symlinked: %s" % raw)
            path=path.resolve()
            if not path.is_file(): raise ValueError("adapter runtime file is unavailable or symlinked: %s" % raw)
            runtime_files[str(raw).replace("\\","/")]=path.read_bytes()
        runtime=b"".join(name.encode("utf-8")+b"\0"+data+b"\0" for name,data in sorted(runtime_files.items()))
        host=self.config.get("host_tool") or {}
        return {
            "adapter_config_sha256":"sha256:"+hashlib.sha256(canonical).hexdigest(),
            "adapter_runtime_sha256":"sha256:"+hashlib.sha256(runtime).hexdigest(),
            "host_tool_name":host.get("name"),
            "host_tool_version":host.get("version"),
            "adapter_id":self.config.get("id"),
        }
    @classmethod
    def from_path(cls,path):
        config=json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        schema=json.loads(pathlib.Path(__file__).with_name("adapter.schema.json").read_text(encoding="utf-8"))
        errors=validate_node(config,schema)
        if errors: raise ValueError("; ".join(errors))
        return cls(config,pathlib.Path(path).resolve().parent)
    def require_locked_holdout(self):
        if self.config.get("sandboxed") is not True or self.config.get("workspace_isolation") not in {"sandbox","container","vm"}:
            raise ValueError("locked holdout requires externally enforced sandbox/container/vm isolation")
        attestation=self.config.get("isolation_attestation")
        if not isinstance(attestation,dict) or not attestation.get("issuer") or not attestation.get("reference") or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(attestation.get("sha256", ""))):
            raise ValueError("locked execution requires an operator isolation attestation; booleans alone are insufficient")
    def supports(self,capability):
        return capability in set(self.config.get("capabilities",[]))
    def _environment(self,skill_path=None):
        env={"PATH":os.environ.get("PATH",""),"HOME":os.environ.get("HOME",""),"LANG":os.environ.get("LANG","C.UTF-8")}
        env.update(self.config.get("environment",{}))
        if skill_path: env["UPG_SKILL_PATH"]=str(pathlib.Path(skill_path).resolve())
        return env
    def _control_values(self,control,workspace,task,condition,skill_path,checkpoint,phase):
        task_file=control/"task.txt"; task_file.write_text(task,encoding="utf-8")
        condition_file=control/"condition.md"; condition_file.write_text(condition or "",encoding="utf-8")
        checkpoint_file=control/"checkpoint.json"; checkpoint_file.write_text(json.dumps(checkpoint or {},indent=2),encoding="utf-8")
        output_file=control/"adapter-output.json"
        values={"workspace":str(workspace),"task_file":str(task_file),"condition_file":str(condition_file),"output_file":str(output_file),"checkpoint_file":str(checkpoint_file),"phase":phase,"skill_path":str(pathlib.Path(skill_path).resolve()) if skill_path else ""}
        return values
    def prepare_skill(self,workspace,task,condition,skill_path,checkpoint=None,phase="single"):
        if not skill_path or not self.config.get("skill_install_command"):
            return
        workspace=pathlib.Path(workspace).resolve()
        with tempfile.TemporaryDirectory(prefix="upg-qualification-setup-") as td:
            control=pathlib.Path(td)
            values=self._control_values(control,workspace,task,condition,skill_path,checkpoint,phase)
            cp=subprocess.run(_expand(self.config["skill_install_command"],values),cwd=str(workspace),env=self._environment(skill_path),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=int(self.config.get("timeout_seconds",900)),check=False)
            if cp.returncode!=0: raise RuntimeError("skill installation failed: "+cp.stderr[-2000:])
    def _execute(self,key,workspace,task,condition,skill_path=None,raw_dir=None,checkpoint=None,phase="single",skill_prepared=False):
        workspace=pathlib.Path(workspace).resolve()
        timeout=int(self.config.get("timeout_seconds",900))
        env=self._environment(skill_path)
        if skill_path and not skill_prepared:
            self.prepare_skill(workspace,task,condition,skill_path,checkpoint,phase)
        with tempfile.TemporaryDirectory(prefix="upg-qualification-control-") as td:
            control=pathlib.Path(td)
            values=self._control_values(control,workspace,task,condition,skill_path,checkpoint,phase)
            output_file=pathlib.Path(values["output_file"])
            command=self.config.get(key)
            if not command: raise ValueError("adapter missing %s" % key)
            started=time.monotonic()
            cp=subprocess.run(_expand(command,values),cwd=str(workspace),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
            elapsed=time.monotonic()-started
            usage={}; events={}
            usage_name=self.config.get("usage_file")
            if usage_name and (workspace/usage_name).is_file():
                usage=json.loads((workspace/usage_name).read_text(encoding="utf-8"))
            if output_file.is_file():
                meta=json.loads(output_file.read_text(encoding="utf-8")); usage.update(meta.get("usage",{})); events=meta.get("events",{})
            usage.setdefault("wall_time_seconds",elapsed)
            def h(text): return hashlib.sha256(text.encode("utf-8",errors="replace")).hexdigest()
            evidence={"stdout_sha256":h(cp.stdout),"stderr_sha256":h(cp.stderr),"exit_code":cp.returncode}
            if raw_dir:
                raw=pathlib.Path(raw_dir); raw.mkdir(parents=True,exist_ok=True)
                (raw/(phase+"-stdout.txt")).write_text(cp.stdout,encoding="utf-8")
                (raw/(phase+"-stderr.txt")).write_text(cp.stderr,encoding="utf-8")
            return {"exit_code":cp.returncode,"usage":usage,"events":events,"evidence":evidence}
    def run(self,workspace,task,condition,skill_path=None,raw_dir=None,phase="single",skill_prepared=False):
        return self._execute("command",workspace,task,condition,skill_path,raw_dir,None,phase,skill_prepared)
    def run_checkpointed(self,workspace,task,condition,checkpoint,skill_path=None,raw_dir=None,phase="agent-a",skill_prepared=False):
        if not self.supports("controlled_checkpoint"): raise ValueError("adapter lacks controlled_checkpoint capability")
        return self._execute("checkpoint_command",workspace,task,condition,skill_path,raw_dir,checkpoint,phase,skill_prepared)
