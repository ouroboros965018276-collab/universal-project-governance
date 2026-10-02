from __future__ import annotations
import argparse,json,pathlib,sys,tempfile,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.adapters.command_adapter import CommandAdapter
from qualification.trigger_suite import build

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--adapter",required=True); ap.add_argument("--case-id",required=True); ap.add_argument("--pair-id",required=True); ap.add_argument("--output",required=True); ap.add_argument("--locked-holdout",action="store_true"); args=ap.parse_args()
    adapter=CommandAdapter.from_path(args.adapter)
    if args.locked_holdout: adapter.require_locked_holdout()
    if not adapter.supports("skill_injection") or not adapter.supports("activation_trace"):
        print("error: trigger qualification requires skill_injection + activation_trace capabilities",file=sys.stderr); return 2
    cfg=json.loads((ROOT/"qualification/fixtures/trigger-families.json").read_text(encoding="utf-8")); cases=build(cfg)
    case=next((x for x in cases if x["id"]==args.case_id),None)
    if case is None: print("error: unknown trigger case",file=sys.stderr); return 2
    freeze=json.loads((ROOT/"qualification/FREEZE.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="upg-trigger-") as td:
        result=adapter.run(pathlib.Path(td),case["query"],"",skill_path=ROOT/"universal-project-governance")
    if "skill_activated" not in result["events"]:
        print("error: adapter did not provide skill_activated event",file=sys.stderr); return 2
    trial={"trial_id":str(uuid.uuid4()),"pair_id":args.pair_id,"scenario_id":case["id"],"kind":"trigger","arm":"A2","agent":adapter.config.get("agent",{}),"environment":{"sandboxed":adapter.config.get("sandboxed"),"workspace_isolation":adapter.config.get("workspace_isolation"),"language":case["language"],"object_id":case["object_id"]},"fingerprints":{"behavioral":freeze["behavioral_fingerprint"],"qualification":freeze["qualification_fingerprint"]},"outcome":{"should_trigger":case["should_trigger"],"triggered":bool(result["events"]["skill_activated"]),"critical_failures":[]},"usage":result["usage"],"evidence":result["evidence"]}
    pathlib.Path(args.output).write_text(json.dumps(trial,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
