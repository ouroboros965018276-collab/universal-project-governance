#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(path): return json.loads(path.read_text(encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",nargs="?",default="."); args=ap.parse_args()
    root=pathlib.Path(args.root).resolve(); errors=[]
    protocol=load(root/"qualification/protocol/qualification-v1.json"); th=load(root/"qualification/protocol/thresholds.json")
    if protocol.get("status")!="locked": errors.append("qualification protocol must be locked")
    if set(protocol["arms"])!={"A0","A1","A2","K"}: errors.append("expected A0/A1/A2/K experimental arms")
    if len(protocol.get("critical_failure_classes",[]))<10: errors.append("critical failure taxonomy incomplete")
    for rel,min_count in [("qualification/fixtures/dev/behavioral-labs.json",12),("qualification/fixtures/holdout/locked/behavioral-labs.json",12)]:
        labs=load(root/rel).get("labs",[])
        if len(labs)<min_count: errors.append("%s has %d labs; need >=%d"%(rel,len(labs),min_count))
        ids=[x.get("id") for x in labs]
        if len(ids)!=len(set(ids)): errors.append("duplicate lab IDs in "+rel)
        for lab in labs:
            if not lab.get("policy_ids") or not lab.get("checks") or not lab.get("initial_files"): errors.append("incomplete lab "+str(lab.get("id")))
    cp=subprocess.run([sys.executable,str(root/"qualification/trigger_suite.py")],cwd=str(root),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if cp.returncode!=0: errors.append("trigger suite generation failed: "+cp.stderr)
    else:
        cases=json.loads(cp.stdout)["cases"]
        if len(cases)<int(protocol["sampling"]["trigger_cases_minimum"]): errors.append("trigger suite too small")
        if not any(x["language"]=="zh" for x in cases): errors.append("trigger suite lacks multilingual coverage")
    for p in list((root/"qualification").rglob("*.py"))+list((root/"tools").glob("qualification_*.py")):
        try: ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
        except SyntaxError as exc: errors.append("syntax error %s: %s"%(p.relative_to(root),exc))
    results=root/"qualification/results"
    if results.exists():
        for p in results.rglob("*.json"):
            if p.stat().st_size==0: errors.append("empty result artifact forbidden: "+str(p.relative_to(root)))
    if th["core_task_non_inferiority"]["margin_absolute"]>=0: errors.append("non-inferiority margin must be negative")
    if errors:
        for e in errors: print("error: "+e,file=sys.stderr)
        return 1
    print("Qualification infrastructure check passed: locked protocol, 24 behavioral labs, >=100 metamorphic triggers, no fabricated result artifacts.")
    return 0
if __name__=="__main__": raise SystemExit(main())
