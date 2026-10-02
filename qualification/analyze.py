from __future__ import annotations
import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.analysis.metrics import paired_binary,paired_condition,bootstrap_paired_delta,zero_event_upper_bound,median_ratio
from qualification.trigger_suite import metrics as trigger_metrics

def load_jsonl(paths):
    rows=[]
    for raw in paths:
        for line in pathlib.Path(raw).read_text(encoding="utf-8").splitlines():
            if line.strip(): rows.append(json.loads(line))
    return rows

def gate(state,**data):
    out={"state":state}; out.update(data); return out

def analyze(rows,thresholds,protocol,fingerprint):
    min_pairs=int(protocol["sampling"]["min_repetitions_per_pair"])
    behavioral=[r for r in rows if r["kind"]=="behavioral"]
    handoff=[r for r in rows if r["kind"]=="handoff"]
    trigger=[r for r in rows if r["kind"]=="trigger"]
    mutation=[r for r in rows if r["kind"]=="mutation"]
    a20=paired_binary(behavioral,"A0","A2","task_success"); g20=paired_binary(behavioral,"A0","A2","governance_defect_free"); g21=paired_binary(behavioral,"A1","A2","governance_defect_free")
    a20ci=bootstrap_paired_delta(a20["deltas"]) if a20["n"] else {"ci":[0,0]}; g20ci=bootstrap_paired_delta(g20["deltas"]) if g20["n"] else {"ci":[0,0]}; g21ci=bootstrap_paired_delta(g21["deltas"]) if g21["n"] else {"ci":[0,0]}
    gates={}
    if a20["n"]<min_pairs: gates["core_task_non_inferiority"]=gate("MORE_DATA",n=a20["n"],required=min_pairs)
    else: gates["core_task_non_inferiority"]=gate("PASS" if a20ci["ci"][0]>=thresholds["core_task_non_inferiority"]["margin_absolute"] else "FAIL",delta=a20["mean_delta"],ci=a20ci["ci"],n=a20["n"])
    if g20["n"]<min_pairs or g21["n"]<min_pairs: gates["governance_uplift"]=gate("MORE_DATA",n=min(g20["n"],g21["n"]),required=min_pairs)
    else:
        ok=g20ci["ci"][0]>=thresholds["governance_uplift"]["versus_no_skill_min_absolute"] and g21ci["ci"][0]>=thresholds["governance_uplift"]["versus_attention_control_min_absolute"]
        gates["governance_uplift"]=gate("PASS" if ok else "FAIL",vs_no_skill={"delta":g20["mean_delta"],"ci":g20ci["ci"]},vs_attention={"delta":g21["mean_delta"],"ci":g21ci["ci"]})
    treatment=[r for r in rows if r["arm"]=="A2"]; critical=[cf for r in treatment for cf in r["outcome"].get("critical_failures",[])]; upper=zero_event_upper_bound(len(treatment))
    if critical: gates["critical_failure"]=gate("FAIL",observed=len(critical),n=len(treatment),upper_95=upper,classes=sorted(set(critical)))
    elif upper>thresholds["critical_failure"]["treatment_one_sided_upper_bound_95_max"]: gates["critical_failure"]=gate("MORE_DATA",observed=0,n=len(treatment),upper_95=upper)
    else: gates["critical_failure"]=gate("PASS",observed=0,n=len(treatment),upper_95=upper)
    hp=paired_condition(handoff,"ablated","present","task_success")
    if hp["n"]<min_pairs: gates["handoff"]=gate("MORE_DATA",n=hp["n"],required=min_pairs)
    else:
        ci=bootstrap_paired_delta(hp["deltas"]); gates["handoff"]=gate("PASS" if ci["ci"][0]>=thresholds["handoff"]["recovery_success_uplift_min_absolute"] else "FAIL",delta=hp["mean_delta"],ci=ci["ci"],n=hp["n"])
    if len(trigger)<int(protocol["sampling"]["trigger_cases_minimum"]): gates["trigger"]=gate("MORE_DATA",n=len(trigger),required=protocol["sampling"]["trigger_cases_minimum"])
    else:
        tm=trigger_metrics([{"should_trigger":r["outcome"]["should_trigger"],"triggered":r["outcome"]["triggered"]} for r in trigger])
        ok=tm["precision"]>=thresholds["trigger"]["precision_min"] and tm["recall"]>=thresholds["trigger"]["recall_min"] and tm["false_positive_rate"]<=thresholds["trigger"]["false_positive_rate_max"] and tm["false_negative_rate"]<=thresholds["trigger"]["false_negative_rate_max"]
        gates["trigger"]=gate("PASS" if ok else "FAIL",metrics=tm)
    expected_mutants=5; detected={r.get("environment",{}).get("mutation_id"):bool(r["outcome"].get("eval_detected_regression")) for r in mutation}
    if len([k for k in detected if k])<expected_mutants: gates["eval_sensitivity"]=gate("MORE_DATA",detected=detected,required=expected_mutants)
    elif not all(detected.values()): gates["eval_sensitivity"]=gate("FAIL",detected=detected)
    else: gates["eval_sensitivity"]=gate("PASS",detected=detected)
    ratios={"tokens":median_ratio(behavioral,field="total_tokens"),"wall_time":median_ratio(behavioral,field="wall_time_seconds"),"tool_calls":median_ratio(behavioral,field="tool_calls")}
    if any(v is None for v in ratios.values()): gates["efficiency"]=gate("MORE_DATA",ratios=ratios)
    else:
        ok=ratios["tokens"]<=thresholds["efficiency"]["median_total_token_ratio_max"] and ratios["wall_time"]<=thresholds["efficiency"]["median_wall_time_ratio_max"] and ratios["tool_calls"]<=thresholds["efficiency"]["median_tool_call_ratio_max"]
        gates["efficiency"]=gate("PASS" if ok else "FAIL",ratios=ratios)
    fam={r.get("agent",{}).get("family") for r in treatment if r.get("agent",{}).get("family")}; profiles={r.get("environment",{}).get("project_profile") for r in treatment if r.get("environment",{}).get("project_profile")}
    gen_ok=len(fam)>=protocol["sampling"]["minimum_agent_families"] and len(profiles)>=protocol["sampling"]["minimum_project_profiles"]
    gates["generalization"]=gate("PASS" if gen_ok else "MORE_DATA",agent_families=sorted(fam),project_profiles=sorted(profiles))
    states=[x["state"] for x in gates.values()]; status="FAIL" if "FAIL" in states else ("MORE_DATA" if "MORE_DATA" in states else "PASS")
    effects={"task_success_A2_minus_A0":a20,"governance_A2_minus_A0":g20,"governance_A2_minus_A1":g21,"handoff_present_minus_ablated":hp}
    return {"schema_version":1,"qualification_fingerprint":fingerprint,"status":status,"gates":gates,"sample_sizes":{"rows":len(rows),"behavioral_pairs":a20["n"],"treatment_trials":len(treatment),"handoff_pairs":hp["n"],"trigger_trials":len(trigger)},"effects":effects,"notes":["No aggregate score is used; gates are lexicographic and non-compensatory."]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("inputs",nargs="+"); ap.add_argument("--thresholds",default="qualification/protocol/thresholds.json"); ap.add_argument("--protocol",default="qualification/protocol/qualification-v1.json"); ap.add_argument("--fingerprint",required=True); ap.add_argument("--output"); args=ap.parse_args()
    result=analyze(load_jsonl(args.inputs),json.loads(pathlib.Path(args.thresholds).read_text()),json.loads(pathlib.Path(args.protocol).read_text()),args.fingerprint)
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output: pathlib.Path(args.output).write_text(text,encoding="utf-8")
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
