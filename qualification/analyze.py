from __future__ import annotations
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualification.analysis.coverage import behavioral_coverage, handoff_coverage, release_rows
from qualification.analysis.gates import (
    control_validity,
    core_task,
    critical_safety,
    deployment_integrity,
    efficiency,
    evaluator_validity,
    generalization,
    governance_uplift,
    handoff,
    structural_overreach,
    trigger,
)

def load_jsonl(paths):
    rows = []
    for raw in paths:
        for line in pathlib.Path(raw).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows

def analyze(rows, thresholds, protocol, fingerprint):
    coverage = behavioral_coverage(rows, protocol)
    handoff_cov = handoff_coverage(rows, protocol)
    control = control_validity(rows, thresholds, coverage)

    gates = {
        "coverage": coverage,
        "deployment_integrity": deployment_integrity(rows, thresholds, coverage),
        "evaluator_validity": evaluator_validity(rows, protocol),
        "control_validity": control,
        "critical_safety": critical_safety(rows, protocol, thresholds),
        "structural_overreach": structural_overreach(rows, protocol, thresholds, coverage),
        "core_task_non_inferiority": core_task(rows, protocol, thresholds, coverage),
        "governance_uplift": governance_uplift(rows, protocol, thresholds, coverage, control),
        "handoff": handoff(rows, protocol, thresholds, handoff_cov),
        "trigger": trigger(rows, protocol, thresholds),
        "efficiency": efficiency(rows, thresholds, coverage),
        "generalization": generalization(rows, protocol, thresholds, coverage),
    }

    ordered = {name: gates[name] for name in protocol["gate_order"]}
    states = [item["state"] for item in ordered.values()]
    status = "FAIL" if "FAIL" in states else ("MORE_DATA" if "MORE_DATA" in states else "PASS")
    locked = [row for row in rows if row.get("environment", {}).get("qualification_set") == "locked"]

    return {
        "schema_version": 3,
        "qualification_fingerprint": fingerprint,
        "status": status,
        "gates": ordered,
        "sample_sizes": {
            "rows_total": len(rows),
            "rows_locked": len(locked),
            "locked_behavioral": len(release_rows(rows, "behavioral")),
            "locked_handoff": len(release_rows(rows, "handoff")),
            "locked_trigger": len(release_rows(rows, "trigger")),
            "locked_mutation": len(release_rows(rows, "mutation")),
        },
        "effects": {
            "governance_uplift": ordered["governance_uplift"],
            "handoff": ordered["handoff"],
            "generalization": ordered["generalization"],
            "structural_overreach": ordered["structural_overreach"],
        },
        "notes": [
            "Release qualification uses locked evidence only.",
            "Primary confidence intervals use hierarchical bootstrap over agent family, scenario, and repetition/pair.",
            "Generalization PASS rules out preregistered severe subgroup reversal; statistically significant benefit is reported separately per subgroup and is not implied by coverage alone.",
            "Critical-failure denominators remain class-specific exposure populations.",
            "Structural overreach is estimated in separate local-guard and structural-guard exposure cohorts so neither population dilutes the other.",
            "Gates are lexicographic and non-compensatory; development checkpoints cannot promote Stable.",
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--thresholds", default="qualification/protocol/thresholds.json")
    parser.add_argument("--protocol", default="qualification/protocol/qualification-v3.json")
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze(
        load_jsonl(args.inputs),
        json.loads(pathlib.Path(args.thresholds).read_text(encoding="utf-8")),
        json.loads(pathlib.Path(args.protocol).read_text(encoding="utf-8")),
        args.fingerprint,
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        pathlib.Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
