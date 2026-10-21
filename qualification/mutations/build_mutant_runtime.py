from __future__ import annotations
import argparse,hashlib,json,pathlib,shutil,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from qualification.mutations.apply_policy_mutant import apply_mutant

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build_runtime(src,out,mutant):
    src=pathlib.Path(src).resolve(); out=pathlib.Path(out).absolute()
    resolved=out.resolve()
    if out.is_symlink() or resolved==ROOT or resolved in ROOT.parents or resolved==src or src in resolved.parents or resolved in src.parents:
        raise ValueError("mutant output must not overlap the repository or source runtime")
    if out.exists() and not out.is_dir(): raise ValueError("mutant output must be a directory")
    if out.exists():
        try:
            previous=json.loads((out/"integrity/manifest.json").read_text(encoding="utf-8"))
            owned=previous.get("files")
            if not isinstance(owned,dict) or not previous.get("experimental_mutant"): raise ValueError("not a generated mutant")
            actual={}
            for path in out.rglob("*"):
                if path.is_symlink() or (hasattr(path,"is_junction") and path.is_junction()): raise ValueError("linked mutant output")
                if path.is_file() and path!=out/"integrity/manifest.json": actual[path.relative_to(out).as_posix()]=digest(path)
            if actual!=owned: raise ValueError("mutant output contains modified or unowned files")
        except (OSError,ValueError,AttributeError) as exc:
            raise ValueError("existing output is not a verified generated mutant; preserve it and choose a new output") from exc
    out.parent.mkdir(parents=True,exist_ok=True)
    staged=pathlib.Path(tempfile.mkdtemp(prefix=out.name+".building-",dir=str(out.parent)))
    backup=None
    try:
        shutil.copytree(src,staged,dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__",".git","*.pyc"))
        index=json.loads((staged/"policy-index.json").read_text(encoding="utf-8"))
        index=apply_mutant(index,mutant)
        (staged/"policy-index.json").write_text(json.dumps(index,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if mutant["id"]=="M04_DISABLE_HANDOFF":
            skill=staged/"SKILL.md"; lines=skill.read_text(encoding="utf-8").splitlines()
            matches=[i for i,line in enumerate(lines) if line.startswith("7. **HANDOFF_IF_UNFINISHED**")]
            if len(matches)!=1: raise ValueError("expected one HANDOFF_IF_UNFINISHED rule entry")
            del lines[matches[0]]; skill.write_text("\n".join(lines)+"\n",encoding="utf-8")
        files={p.relative_to(staged).as_posix():digest(p) for p in sorted(staged.rglob("*")) if p.is_file() and p!=staged/"integrity/manifest.json"}
        manifest=json.loads((staged/"integrity/manifest.json").read_text(encoding="utf-8")); manifest["files"]=files; manifest["experimental_mutant"]=mutant["id"]
        (staged/"integrity/manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if out.exists():
            backup=out.with_name(out.name+".backup-"+uuid.uuid4().hex); out.rename(backup)
        try: staged.rename(out)
        except BaseException:
            if backup is not None: backup.rename(out); backup=None
            raise
        if backup is not None: shutil.rmtree(backup); backup=None
    finally:
        if staged.exists(): shutil.rmtree(staged)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mutant",required=True); ap.add_argument("--output",required=True); args=ap.parse_args()
    defs=json.loads((ROOT/"qualification/mutations/mutations.json").read_text(encoding="utf-8")); m=next((x for x in defs["policy_mutants"] if x["id"]==args.mutant),None)
    if m is None: print("error: unknown mutant",file=sys.stderr); return 2
    build_runtime(ROOT/"universal-project-governance",pathlib.Path(args.output),m)
    print("Built experimental mutant runtime: "+m["id"]); return 0
if __name__=="__main__": raise SystemExit(main())
