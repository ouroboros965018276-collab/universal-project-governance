from __future__ import annotations
import hashlib,json,os,pathlib,subprocess,tempfile,time

def _expand(items,values):
    return [str(x).format(**values) for x in items]

class CommandAdapter(object):
    def __init__(self,config):
        self.config=config
    @classmethod
    def from_path(cls,path):
        return cls(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))
    def require_locked_holdout(self):
        if not self.config.get("sandboxed") or self.config.get("workspace_isolation") not in {"sandbox","container","vm"}:
            raise ValueError("locked holdout requires externally enforced sandbox/container/vm isolation")
    def supports(self,capability):
        return capability in set(self.config.get("capabilities",[]))
    def _execute(self,key,workspace,task,condition,skill_path=None,raw_dir=None,checkpoint=None,phase="single"):
        workspace=pathlib.Path(workspace).resolve()
        timeout=int(self.config.get("timeout_seconds",900))
        env={"PATH":os.environ.get("PATH",""),"HOME":os.environ.get("HOME",""),"LANG":os.environ.get("LANG","C.UTF-8")}
        env.update(self.config.get("environment",{}))
        if skill_path: env["UPG_SKILL_PATH"]=str(pathlib.Path(skill_path).resolve())
        with tempfile.TemporaryDirectory(prefix="upg-qualification-control-") as td:
            control=pathlib.Path(td)
            task_file=control/"task.txt"; task_file.write_text(task,encoding="utf-8")
            condition_file=control/"condition.md"; condition_file.write_text(condition or "",encoding="utf-8")
            checkpoint_file=control/"checkpoint.json"; checkpoint_file.write_text(json.dumps(checkpoint or {},indent=2),encoding="utf-8")
            output_file=control/"adapter-output.json"
            values={"workspace":str(workspace),"task_file":str(task_file),"condition_file":str(condition_file),"output_file":str(output_file),"checkpoint_file":str(checkpoint_file),"phase":phase,"skill_path":str(pathlib.Path(skill_path).resolve()) if skill_path else ""}
            if skill_path and self.config.get("skill_install_command"):
                cp=subprocess.run(_expand(self.config["skill_install_command"],values),cwd=str(workspace),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
                if cp.returncode!=0: raise RuntimeError("skill installation failed: "+cp.stderr[-2000:])
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
    def run(self,workspace,task,condition,skill_path=None,raw_dir=None,phase="single"):
        return self._execute("command",workspace,task,condition,skill_path,raw_dir,None,phase)
    def run_checkpointed(self,workspace,task,condition,checkpoint,skill_path=None,raw_dir=None,phase="agent-a"):
        if not self.supports("controlled_checkpoint"): raise ValueError("adapter lacks controlled_checkpoint capability")
        return self._execute("checkpoint_command",workspace,task,condition,skill_path,raw_dir,checkpoint,phase)
