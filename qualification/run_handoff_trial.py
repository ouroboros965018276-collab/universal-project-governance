from __future__ import annotations
import argparse,json,pathlib,shutil,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.adapters.command_adapter import CommandAdapter
from qualification.lib.core import get_lab,materialize_lab,grade_lab

def add_usage(a,b):
    keys=set(a)|set(b); out={}
    for k in keys:
        av=a.get(k); bv=b.get(k)
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)): out[k]=av+bv
    out["agent_b_total_tokens"]=b.get("total_tokens")
    out["agent_b_wall_time_seconds"]=b.get("wall_time_seconds")
    out["agent_b_tool_calls"]=b.get("tool_calls")
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--labs",required=True); ap.add_argument("--scenario",required=True); ap.add_argument("--adapter",required=True); ap.add_argument("--condition",choices=["present","ablated"],required=True); ap.add_argument("--pair-id",required=True); ap.add_argument("--output",required=True); ap.add_argument("--raw-dir"); ap.add_argument("--locked-holdout",action="store_true"); args=ap.parse_args()
    lab=get_lab(args.labs,args.scenario); adapter=CommandAdapter.from_path(args.adapter)
    if args.locked_holdout: adapter.require_locked_holdout()
    for cap in ("skill_injection","controlled_checkpoint"):
        if not adapter.supports(cap): print("error: handoff qualification requires "+cap,file=sys.stderr); return 2
    freeze=json.loads((ROOT/"qualification/FREEZE.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="upg-handoff-") as td:
        ws=pathlib.Path(td)/"workspace"; before=materialize_lab(lab,ws)
        a=adapter.run_checkpointed(ws,lab["task"],"",lab["checkpoint"],skill_path=ROOT/"universal-project-governance",raw_dir=args.raw_dir,phase="agent-a")
        if not a["events"].get("checkpoint_reached"):
            print("error: controlled checkpoint was not reached",file=sys.stderr); return 2
        handoff=ws/".governance/handoff.json"
        handoff_was_present=handoff.is_file()
        if args.condition=="ablated" and handoff.exists(): handoff.unlink()
        b=adapter.run(ws,lab["continuation_task"],"",skill_path=ROOT/"universal-project-governance",raw_dir=args.raw_dir,phase="agent-b")
        grade=grade_lab(lab,ws,before)
        critical=[]
        if args.condition=="present" and not handoff_was_present: critical.append("CF09_HANDOFF_DROPS_CRITICAL_RISK")
        outcome={"task_success":grade["task_success"],"governance_defect_free":grade["governance_defect_free"],"critical_failures":critical,"handoff_condition":args.condition,"handoff_created_by_a":handoff_was_present,"checks":grade["checks"],"changed_files":grade["changed_files"]}
        trial={"trial_id":str(uuid.uuid4()),"pair_id":args.pair_id,"scenario_id":lab["id"],"kind":"handoff","arm":"A2","agent":adapter.config.get("agent",{}),"environment":{"sandboxed":adapter.config.get("sandboxed"),"workspace_isolation":adapter.config.get("workspace_isolation"),"project_profile":lab.get("profile"),"handoff_condition":args.condition},"fingerprints":{"behavioral":freeze["behavioral_fingerprint"],"qualification":freeze["qualification_fingerprint"]},"outcome":outcome,"usage":add_usage(a["usage"],b["usage"]),"evidence":{"agent_a":a["evidence"],"agent_b":b["evidence"],"before_sha256":grade["before_sha256"],"after_sha256":grade["after_sha256"]}}
    pathlib.Path(args.output).write_text(json.dumps(trial,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
