from __future__ import annotations
import argparse,hashlib,json,pathlib,shutil,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from qualification.mutations.apply_policy_mutant import apply_mutant

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mutant",required=True); ap.add_argument("--output",required=True); args=ap.parse_args()
    defs=json.loads((ROOT/"qualification/mutations/mutations.json").read_text(encoding="utf-8")); m=next((x for x in defs["policy_mutants"] if x["id"]==args.mutant),None)
    if m is None: print("error: unknown mutant",file=sys.stderr); return 2
    src=ROOT/"universal-project-governance"; out=pathlib.Path(args.output)
    if out.exists(): shutil.rmtree(out)
    shutil.copytree(src,out)
    index=json.loads((out/"policy-index.json").read_text(encoding="utf-8")); index=apply_mutant(index,m)
    (out/"policy-index.json").write_text(json.dumps(index,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if m["id"]=="M04_DISABLE_HANDOFF":
        skill=out/"SKILL.md"; lines=[x for x in skill.read_text(encoding="utf-8").splitlines() if "HANDOFF_IF_UNFINISHED" not in x]; skill.write_text("\n".join(lines)+"\n",encoding="utf-8")
    files={}
    for p in sorted(x for x in out.rglob("*") if x.is_file() and x!=out/"integrity/manifest.json"):
        files[p.relative_to(out).as_posix()]=digest(p)
    manifest=json.loads((out/"integrity/manifest.json").read_text(encoding="utf-8")); manifest["files"]=files; manifest["experimental_mutant"]=m["id"]
    (out/"integrity/manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Built experimental mutant runtime: "+m["id"]); return 0
if __name__=="__main__": raise SystemExit(main())
