#!/usr/bin/env python3
from __future__ import annotations
import argparse
import ast
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    errors = []

    protocol_path = root / "qualification/protocol/qualification-v2.json"
    thresholds_path = root / "qualification/protocol/thresholds.json"
    if not protocol_path.is_file():
        errors.append("missing qualification-v2.json")
        protocol = {}
    else:
        protocol = load(protocol_path)
    if not thresholds_path.is_file():
        errors.append("missing thresholds.json")
        thresholds = {}
    else:
        thresholds = load(thresholds_path)

    if (root / "qualification/protocol/qualification-v1.json").exists():
        errors.append("obsolete qualification-v1.json remains")
    if protocol.get("schema_version") != 2:
        errors.append("qualification protocol schema_version must be 2")
    if thresholds.get("schema_version") != 2:
        errors.append("threshold schema_version must be 2")
    if protocol.get("protocol_id") != thresholds.get("protocol_id"):
        errors.append("protocol/threshold protocol_id mismatch")
    if protocol.get("status") != "locked":
        errors.append("qualification protocol must be locked")
    if set(protocol.get("arms", {})) != {"A0", "A1", "A2", "K"}:
        errors.append("expected A0/A1/A2/K experimental arms")

    required_gates = [
        "coverage",
        "evaluator_validity",
        "control_validity",
        "critical_safety",
        "core_task_non_inferiority",
        "governance_uplift",
        "handoff",
        "trigger",
        "efficiency",
        "generalization",
    ]
    if protocol.get("gate_order") != required_gates:
        errors.append("gate_order must match the RC6 non-compensatory release sequence")

    critical = set(protocol.get("critical_failure_classes", []))
    exposure_classes = set(
        protocol.get("safety_exposure_model", {}).get("classes", {})
    )
    if len(critical) != 10 or critical != exposure_classes:
        errors.append("critical failure classes and exposure model must match exactly")

    sampling = protocol.get("sampling", {})
    dev_min = int(sampling.get("development_repetitions_per_cell_min", 0))
    locked_min = int(sampling.get("locked_repetitions_per_cell_min", 0))
    locked_max = int(sampling.get("locked_repetitions_per_cell_max", 0))
    if dev_min < 3:
        errors.append("development minimum repetitions must be >= 3")
    if locked_min < 8:
        errors.append("locked qualification minimum repetitions must be >= 8")
    if locked_max < locked_min:
        errors.append("locked maximum repetitions must be >= locked minimum")
    if 5 not in sampling.get("checkpoints", []) or 8 not in sampling.get("checkpoints", []):
        errors.append("sampling checkpoints must preserve 5/8 progression")

    lab_requirements = [
        ("qualification/fixtures/dev/behavioral-labs.json", 12, False),
        ("qualification/fixtures/holdout/locked/behavioral-labs.json", 12, False),
        ("qualification/fixtures/dev/handoff-labs.json", 3, True),
        ("qualification/fixtures/holdout/locked/handoff-labs.json", 6, True),
    ]
    for rel, minimum, handoff in lab_requirements:
        path = root / rel
        if not path.is_file():
            errors.append("missing fixture set: " + rel)
            continue
        payload = load(path)
        labs = payload.get("labs", [])
        if payload.get("schema_version") != 2:
            errors.append("%s must use schema_version 2" % rel)
        if len(labs) < minimum:
            errors.append("%s has %d labs; need >= %d" % (rel, len(labs), minimum))
        ids = [lab.get("id") for lab in labs]
        if len(ids) != len(set(ids)):
            errors.append("duplicate lab IDs in " + rel)
        for lab in labs:
            if not lab.get("policy_ids") or not lab.get("checks") or not lab.get("initial_files"):
                errors.append("incomplete lab " + str(lab.get("id")))
            exposures = set(lab.get("safety_exposures", []))
            if not exposures:
                errors.append("lab missing safety_exposures: " + str(lab.get("id")))
            if exposures - critical:
                errors.append(
                    "lab has unknown safety exposure(s): %s"
                    % ", ".join(sorted(exposures - critical))
                )
            if handoff:
                preserve = lab.get("checkpoint", {}).get("preserve", [])
                if not preserve:
                    errors.append(
                        "handoff lab missing checkpoint preserve contract: "
                        + str(lab.get("id"))
                    )

    trigger_cp = subprocess.run(
        [sys.executable, str(root / "qualification/trigger_suite.py")],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if trigger_cp.returncode != 0:
        errors.append("trigger suite generation failed: " + trigger_cp.stderr)
    else:
        trigger_payload = json.loads(trigger_cp.stdout)
        trigger_cases = trigger_payload["cases"]
        if len(trigger_cases) < int(sampling.get("trigger_cases_minimum", 0)):
            errors.append("trigger suite too small")
        languages = {item["language"] for item in trigger_cases}
        if languages != {"en", "zh"}:
            errors.append("trigger suite must preserve English and Chinese coverage")
        if not any(x["should_trigger"] for x in trigger_cases) or not any(
            not x["should_trigger"] for x in trigger_cases
        ):
            errors.append("trigger suite must contain positive and negative cases")

    mutation_path = root / "qualification/mutations/mutations.json"
    if mutation_path.is_file():
        mutation_ids = {
            item["id"] for item in load(mutation_path).get("policy_mutants", [])
        }
        required_mutants = set(
            protocol.get("evaluator_validity", {}).get("required_mutants", [])
        )
        if mutation_ids != required_mutants:
            errors.append(
                "protocol required_mutants must exactly match policy mutation definitions"
            )
    else:
        errors.append("missing mutation definitions")

    required_thresholds = {
        "handoff": [
            "recovery_success_uplift_min_absolute",
            "degradation_reduction_min_absolute",
        ],
        "efficiency": [
            "median_total_token_ratio_max",
            "median_wall_time_ratio_max",
            "median_tool_call_ratio_max",
            "persistent_governance_artifacts_per_task_max",
        ],
        "attention_control": [
            "governance_context_token_ratio_min",
            "governance_context_token_ratio_max",
        ],
    }
    for section, names in required_thresholds.items():
        values = thresholds.get(section, {})
        for name in names:
            if name not in values:
                errors.append("missing enforced threshold %s.%s" % (section, name))

    generalization = thresholds.get("generalization", {})
    if int(generalization.get("agent_family_min_complete_pairs", 0)) < (
        int(sampling.get("minimum_locked_behavioral_scenarios", 0))
        * locked_min
    ):
        errors.append("agent-family generalization exposure is below locked matrix minimum")
    if int(generalization.get("project_profile_min_complete_pairs", 0)) < locked_min:
        errors.append("project-profile generalization exposure is too small")

    python_files = list((root / "qualification").rglob("*.py"))
    python_files += list((root / "tools").glob("qualification_*.py"))
    python_files += [root / "tools/validate_qualification.py"]
    for path in python_files:
        if not path.is_file():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(
                "syntax error %s: %s" % (path.relative_to(root), exc)
            )

    skill = root / "universal-project-governance/SKILL.md"
    model = root / "governance-src/model/governance-model.json"
    if skill.is_file() and model.is_file():
        budget = load(model)["complexity_budget"]["runtime_skill_max_lines"]
        lines = len(skill.read_text(encoding="utf-8").splitlines())
        if lines > budget:
            errors.append(
                "runtime SKILL.md exceeds canonical line budget: %d > %d"
                % (lines, budget)
            )

    results = root / "qualification/results"
    if results.exists():
        for path in results.rglob("*.json"):
            if path.stat().st_size == 0:
                errors.append(
                    "empty result artifact forbidden: "
                    + str(path.relative_to(root))
                )

    if thresholds.get("core_task_non_inferiority", {}).get("margin_absolute", 0) >= 0:
        errors.append("non-inferiority margin must be negative")

    for error in errors:
        print("error: " + error, file=sys.stderr)
    if errors:
        return 1

    print(
        "Qualification check passed: protocol v2, explicit safety exposure, "
        "8+ locked repetitions, dual handoff criteria, control validity, "
        "artifact overhead, subgroup generalization, and executable holdouts."
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
