from __future__ import annotations
import argparse,copy,json,pathlib,sys

def apply_mutant(index,mutant):
    out=copy.deepcopy(index); policies=out["policies"]; target=mutant["target"]
    if mutant["operation"]=="remove_policy":
        out["policies"]=[p for p in policies if p["id"]!=target]
        out["default_rules"]=[x for x in out.get("default_rules",[]) if x!=target]
        for p in out["policies"]:
            p["requires"]=[x for x in p.get("requires",[]) if x!=target]
    else:
        p=next((p for p in policies if p["id"]==target),None)
        if p is None: raise ValueError("unknown target policy: "+target)
        if mutant["operation"]=="clear_evidence": p["evidence"]=[]
        elif mutant["operation"]=="force_report": p["report"]=mutant["value"]
        elif mutant["operation"]=="remove_requirement": p["requires"]=[x for x in p.get("requires",[]) if x!=mutant["value"]]
        else: raise ValueError("unknown operation: "+mutant["operation"])
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--index",default="universal-project-governance/policy-index.json"); ap.add_argument("--definitions",default="qualification/mutations/mutations.json"); ap.add_argument("--mutant",required=True); ap.add_argument("--output",required=True); args=ap.parse_args()
    index=json.loads(pathlib.Path(args.index).read_text(encoding="utf-8")); defs=json.loads(pathlib.Path(args.definitions).read_text(encoding="utf-8"))
    m=next((x for x in defs["policy_mutants"] if x["id"]==args.mutant),None)
    if m is None: print("error: unknown mutant",file=sys.stderr); return 2
    pathlib.Path(args.output).write_text(json.dumps(apply_mutant(index,m),indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
