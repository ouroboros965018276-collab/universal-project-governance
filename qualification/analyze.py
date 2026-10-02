from __future__ import annotations
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.analysis.metrics import paired_binary,zero_event_upper_bound,median_ratio
from qualification.trigger_suite import metrics as trigger_metrics

def load_jsonl(paths):
    rows=[]
    for raw in paths:
        p=pathlib.Path(raw)
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip(): rows.append(json.loads(line))
    return rows

def analyze(rows,thresholds,fingerprint):
    behavioral=[r for r in rows if r["kind"]=="behavioral"]
    handoff=[r for r in rows if r["kind"]=="handoff"]
    trigger=[r for r in rows if r["kind"]=="trigger"]
    a20=paired_binary(behavioral,"A0","A2","task_success")
    g20=paired_binary(behavioral,"A0","A2","governance_defect_free")
    g21=paired_binary(behavioral,"A1","A2","governance_defect_free")
    critical=[cf for r in rows if r["arm"]=="A2" for cf in r["outcome"].get("critical_failures",[])]
    treatment_n=sum(1 for r in rows if r["arm"]=="A2")
    upper=zero_event_upper_bound(treatment_n)
    hand=paired_binary(handoff,"A0","A2","task_success") if handoff else {"n":0,"mean_delta":0.0}
    tm=trigger_metrics([{"should_trigger":r["outcome"]["should_trigger"],"triggered":r["outcome"]["triggered"]} for r in trigger]) if trigger else {"precision":0.0,"recall":0.0,"false_positive_rate":1.0,"false_negative_rate":1.0}
    token_ratio=median_ratio(behavioral,field="total_tokens")
    time_ratio=median_ratio(behavioral,field="wall_time_seconds")
    tool_ratio=median_ratio(behavioral,field="tool_calls")
    min_pairs=thresholds.get("_minimum_pairs",5)
    gates={}
    gates["sample_size"]={"pass":a20["n"]>=min_pairs,"observed":a20["n"],"required":min_pairs}
    gates["core_task_non_inferiority"]={"pass":a20["mean_delta"]>=thresholds["core_task_non_inferiority"]["margin_absolute"],"delta":a20["mean_delta"]}
    gates["governance_uplift_vs_no_skill"]={"pass":g20["mean_delta"]>=thresholds["governance_uplift"]["versus_no_skill_min_absolute"],"delta":g20["mean_delta"]}
    gates["governance_uplift_vs_attention"]={"pass":g21["mean_delta"]>=thresholds["governance_uplift"]["versus_attention_control_min_absolute"],"delta":g21["mean_delta"]}
    gates["critical_failure"]={"pass":len(critical)<=thresholds["critical_failure"]["treatment_observed_max"] and upper<=thresholds["critical_failure"]["treatment_one_sided_upper_bound_95_max"],"observed":len(critical),"n":treatment_n,"upper_95":upper}
    if handoff:
        gates["handoff"]={"pass":hand["mean_delta"]>=thresholds["handoff"]["recovery_success_uplift_min_absolute"],"delta":hand["mean_delta"],"n":hand["n"]}
    if trigger:
        gates["trigger"]={"pass":tm["precision"]>=thresholds["trigger"]["precision_min"] and tm["recall"]>=thresholds["trigger"]["recall_min"] and tm["false_positive_rate"]<=thresholds["trigger"]["false_positive_rate_max"],"metrics":tm}
    eff_ok=True
    for value,limit in ((token_ratio,thresholds["efficiency"]["median_total_token_ratio_max"]),(time_ratio,thresholds["efficiency"]["median_wall_time_ratio_max"]),(tool_ratio,thresholds["efficiency"]["median_tool_call_ratio_max"])):
        if value is not None and value>limit: eff_ok=False
    gates["efficiency"]={"pass":eff_ok,"token_ratio":token_ratio,"wall_time_ratio":time_ratio,"tool_call_ratio":tool_ratio}
    if any(not x["pass"] for k,x in gates.items() if k!="sample_size" and k not in {"handoff","trigger"}):
        status="FAIL"
    elif not gates["sample_size"]["pass"] or ("handoff" in gates and not gates["handoff"]["pass"]) or ("trigger" in gates and not gates["trigger"]["pass"]):
        status="MORE_DATA"
    else:
        status="PASS"
    return {"schema_version":1,"qualification_fingerprint":fingerprint,"status":status,"gates":gates,"sample_sizes":{"rows":len(rows),"behavioral_pairs":a20["n"],"treatment_trials":treatment_n},"effects":{"task_success_A2_minus_A0":a20,"governance_A2_minus_A0":g20,"governance_A2_minus_A1":g21,"handoff":hand,"trigger":tm}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("inputs",nargs="+"); ap.add_argument("--thresholds",default="qualification/protocol/thresholds.json"); ap.add_argument("--fingerprint",required=True); ap.add_argument("--output"); args=ap.parse_args()
    th=json.loads(pathlib.Path(args.thresholds).read_text(encoding="utf-8")); th["_minimum_pairs"]=5
    result=analyze(load_jsonl(args.inputs),th,args.fingerprint)
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output: pathlib.Path(args.output).write_text(text,encoding="utf-8")
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
