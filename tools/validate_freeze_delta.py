#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.qualification_freeze import behavioral_fingerprint

def git_show(ref,path):
    cp=subprocess.run(["git","show",ref+":"+path],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if cp.returncode!=0: raise RuntimeError(cp.stderr.decode(errors="replace"))
    return cp.stdout

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--base",default="702529bc32665f1afa3afcdc980906be58704f48"); args=ap.parse_args()
    current=json.loads((ROOT/"governance-src/model/governance-model.json").read_text(encoding="utf-8"))
    base=json.loads(git_show(args.base,"governance-src/model/governance-model.json").decode())
    bv=base.pop("version",None); cv=current.pop("version",None)
    if base!=current:
        print("error: governance semantics changed after RC4 freeze",file=sys.stderr); return 1
    if bv!="2.0.0-rc.4" or cv!="2.0.0-rc.5":
        print("error: unexpected freeze versions %r -> %r"%(bv,cv),file=sys.stderr); return 1
    with tempfile.TemporaryDirectory() as td:
        tmp=pathlib.Path(td)/"runtime"; tmp.mkdir()
        cp=subprocess.run(["git","ls-tree","-r","--name-only",args.base,"universal-project-governance"],cwd=str(ROOT),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        if cp.returncode!=0: print(cp.stderr,file=sys.stderr); return 1
        for full in cp.stdout.splitlines():
            if not full.strip(): continue
            rel=pathlib.PurePosixPath(full).relative_to("universal-project-governance")
            p=tmp/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(git_show(args.base,full))
        oldfp=behavioral_fingerprint(tmp)
    newfp=behavioral_fingerprint(ROOT/"universal-project-governance")
    if oldfp!=newfp:
        print("error: behavioral fingerprint changed from RC4 to RC5: %s != %s"%(oldfp,newfp),file=sys.stderr); return 1
    print("RC4 -> RC5 behavioral freeze passed: version-only governance semantic delta; fingerprint %s" % newfp)
    return 0
if __name__=="__main__": raise SystemExit(main())
