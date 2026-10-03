from __future__ import annotations
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualification.analysis.coverage import (
    behavioral_coverage,
    handoff_coverage,
    release_rows,
)
from qualification.analysis.gates import (
    control_validity,
    core_task,
    critical_safety,
    efficiency,
    evaluator_validity,
    generalization,
    governance_uplift,
    handoff,
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
        "evaluator_validity": evaluator_validity(rows, protocol),
        "control_validity": control,
        "critical_safety": critical_safety(rows, protocol, thresholds),
        "core_task_non_inferiority": core_task(rows, thresholds, coverage),
        "governance_uplift": governance_uplift(
            rows, thresholds, coverage, control
        ),
        "handoff": handoff(rows, thresholds, handoff_cov),
        "trigger": trigger(rows, protocol, thresholds),
        "efficiency": efficiency(rows, thresholds, coverage),
        "generalization": generalization(
            rows, protocol, thresholds, coverage
        ),
    }

    ordered = {}
    for name in protocol["gate_order"]:
        ordered[name] = gates[name]

    states = [item["state"] for item in ordered.values()]
    status = (
        "FAIL"
        if "FAIL" in states
        else ("MORE_DATA" if "MORE_DATA" in states else "PASS")
    )

    locked = [
        row for row in rows
        if row.get("environment", {}).get("qualification_set") == "locked"
    ]
    return {
        "schema_version": 2,
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
            "control_validity": ordered["control_validity"],
            "critical_safety": ordered["critical_safety"],
        },
        "notes": [
            "Release qualification uses locked evidence only.",
            "Critical-failure denominators are class-specific exposure populations; trigger and mutation trials never inflate safety exposure.",
            "Gates are lexicographic and non-compensatory; development checkpoints cannot promote Stable.",
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument(
        "--thresholds",
        default="qualification/protocol/thresholds.json",
    )
    parser.add_argument(
        "--protocol",
        default="qualification/protocol/qualification-v2.json",
    )
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
