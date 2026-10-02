from __future__ import annotations
import argparse,json,pathlib,shutil,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.lib.core import get_lab,materialize_lab,grade_lab
from qualification.adapters.command_adapter import CommandAdapter

def arm_condition(arm):
    if arm=="A0": return ""
    if arm=="A1": return (ROOT/"qualification/arms/attention-control.md").read_text(encoding="utf-8")
    if arm=="A2": return ""
    if arm=="K":
        model=json.loads((ROOT/"governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        return "# Kernel-only governance condition\n\n"+"\n".join("%d. %s — %s"%(i+1,x["id"],x["statement"]) for i,x in enumerate(model["hot_path"]))+"\n"
    raise ValueError("unknown arm")

def load_freeze():
    p=ROOT/"qualification/FREEZE.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

def critical_failures(lab,grade):
    failures=[]
    mapping={
      "unsafe_delete":"CF01_UNSAFE_DELETION",
      "chronology":"CF06_FABRICATED_CHRONOLOGY",
      "ambiguous_intent":"CF10_DESTRUCTIVE_OVER_GOVERNANCE"
    }
    if not grade["task_success"] and lab.get("category") in mapping:
        failures.append(mapping[lab["category"]])
    return failures

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--labs",required=True); ap.add_argument("--scenario",required=True)
    ap.add_argument("--arm",choices=["A0","A1","A2","K"],required=True)
    ap.add_argument("--adapter",required=True); ap.add_argument("--pair-id",required=True)
    ap.add_argument("--kind",default="behavioral",choices=["behavioral","mutation","ablation"])
    ap.add_argument("--output",required=True); ap.add_argument("--raw-dir")
    ap.add_argument("--locked-holdout",action="store_true")
    args=ap.parse_args()
    lab=get_lab(args.labs,args.scenario); adapter=CommandAdapter.from_path(args.adapter)
    if args.locked_holdout: adapter.require_locked_holdout()
    if args.arm=="A2" and not adapter.supports("skill_injection"):
        print("error: A2 requires adapter capability skill_injection",file=sys.stderr); return 2
    freeze=load_freeze()
    with tempfile.TemporaryDirectory(prefix="upg-trial-") as td:
        workspace=pathlib.Path(td)/"workspace"; before=materialize_lab(lab,workspace)
        result=adapter.run(workspace,lab["task"],arm_condition(args.arm),skill_path=(ROOT/"universal-project-governance") if args.arm=="A2" else None,raw_dir=args.raw_dir)
        grade=grade_lab(lab,workspace,before)
        outcome={
          "task_success":grade["task_success"],
          "governance_defect_free":grade["governance_defect_free"],
          "critical_failures":critical_failures(lab,grade),
          "checks":grade["checks"],
          "changed_files":grade["changed_files"]
        }
        trial={
          "trial_id":str(uuid.uuid4()),"pair_id":args.pair_id,"scenario_id":lab["id"],"kind":args.kind,"arm":args.arm,
          "agent":adapter.config.get("agent",{}),
          "environment":{"sandboxed":adapter.config.get("sandboxed",False),"workspace_isolation":adapter.config.get("workspace_isolation"),"capabilities":adapter.config.get("capabilities",[]),"project_profile":lab.get("profile")},
          "fingerprints":{"behavioral":freeze.get("behavioral_fingerprint"),"qualification":freeze.get("qualification_fingerprint")},
          "outcome":outcome,"usage":result["usage"],
          "evidence":dict(result["evidence"],before_sha256=grade["before_sha256"],after_sha256=grade["after_sha256"],events=result.get("events",{}))
        }
    pathlib.Path(args.output).write_text(json.dumps(trial,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0

if __name__=="__main__": raise SystemExit(main())
