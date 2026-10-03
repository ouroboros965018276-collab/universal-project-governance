#!/usr/bin/env python3
from __future__ import annotations
import argparse
import ast
import json
import pathlib
import subprocess
import sys

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    errors = []

    protocol_path = root / "qualification/protocol/qualification-v3.json"
    thresholds_path = root / "qualification/protocol/thresholds.json"
    protocol = load(protocol_path) if protocol_path.is_file() else {}
    thresholds = load(thresholds_path) if thresholds_path.is_file() else {}
    if not protocol:
        errors.append("missing qualification-v3.json")
    if not thresholds:
        errors.append("missing thresholds.json")
    for obsolete in ["qualification-v1.json", "qualification-v2.json"]:
        if (root / "qualification/protocol" / obsolete).exists():
            errors.append("obsolete protocol remains: " + obsolete)
    if protocol.get("schema_version") != 3:
        errors.append("qualification protocol schema_version must be 3")
    if thresholds.get("schema_version") != 3:
        errors.append("threshold schema_version must be 3")
    if protocol.get("protocol_id") != "upg-q3" or thresholds.get("protocol_id") != "upg-q3":
        errors.append("protocol/threshold protocol_id must be upg-q3")
    if protocol.get("status") != "locked":
        errors.append("qualification protocol must be locked")
    if set(protocol.get("arms", {})) != {"A0", "A1", "A2", "K"}:
        errors.append("expected A0/A1/A2/K experimental arms")

    required_gates = [
        "coverage",
        "deployment_integrity",
        "evaluator_validity",
        "control_validity",
        "critical_safety",
        "structural_overreach",
        "core_task_non_inferiority",
        "governance_uplift",
        "handoff",
        "trigger",
        "efficiency",
        "generalization",
    ]
    if protocol.get("gate_order") != required_gates:
        errors.append("gate_order must match RC7 non-compensatory release sequence")

    overreach_cohorts = protocol.get("structural_overreach", {}).get("exposure_cohorts", {})
    if set(overreach_cohorts) != {"local_guard", "structural_guard"}:
        errors.append("structural overreach must define local_guard and structural_guard exposure cohorts")
    for name, spec in overreach_cohorts.items():
        if int(spec.get("minimum_locked_scenarios", 0)) < 4:
            errors.append("overreach cohort %s must require >=4 locked scenarios" % name)

    inference = protocol.get("inference", {})
    if inference.get("method") != "hierarchical-bootstrap":
        errors.append("RC7 inference must use hierarchical-bootstrap")
    if inference.get("levels") != ["agent_family", "scenario_id", "pair_id"]:
        errors.append("hierarchical bootstrap levels must be agent_family -> scenario_id -> pair_id")
    if int(inference.get("bootstrap_repetitions", 0)) < 4000:
        errors.append("hierarchical bootstrap repetitions must be >= 4000")
    if float(inference.get("confidence", 0)) != 0.95:
        errors.append("formal inference confidence must be 0.95")

    critical = set(protocol.get("critical_failure_classes", []))
    exposure_classes = set(protocol.get("safety_exposure_model", {}).get("classes", {}))
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
        if payload.get("schema_version") != 3:
            errors.append("%s must use schema_version 3" % rel)
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
                errors.append("lab has unknown safety exposure(s): %s" % ", ".join(sorted(exposures - critical)))
            scope = lab.get("scope_contract")
            if not isinstance(scope, dict):
                errors.append("lab missing scope_contract: " + str(lab.get("id")))
            else:
                required_scope = {
                    "allowed_change_globs", "api_sensitive_globs", "architecture_sensitive_globs",
                    "allow_api_change", "allow_architecture_change", "critical_overreach",
                    "overreach_exposure"
                }
                if set(scope) != required_scope:
                    errors.append("scope_contract keys invalid for " + str(lab.get("id")))
                if scope.get("overreach_exposure") not in {"local_guard", "structural_guard"}:
                    errors.append("invalid overreach_exposure for " + str(lab.get("id")))
            if handoff and not lab.get("checkpoint", {}).get("preserve", []):
                errors.append("handoff lab missing checkpoint preserve contract: " + str(lab.get("id")))

    locked_behavioral = load(root / "qualification/fixtures/holdout/locked/behavioral-labs.json").get("labs", [])
    cohort_counts = {}
    for lab in locked_behavioral:
        cohort = lab.get("scope_contract", {}).get("overreach_exposure")
        cohort_counts[cohort] = cohort_counts.get(cohort, 0) + 1
    for name, spec in protocol.get("structural_overreach", {}).get("exposure_cohorts", {}).items():
        required = int(spec.get("minimum_locked_scenarios", 0))
        if cohort_counts.get(name, 0) < required:
            errors.append("overreach cohort %s has %d locked scenarios; need >= %d" % (name, cohort_counts.get(name, 0), required))

    trigger_cp = subprocess.run(
        [sys.executable, str(root / "qualification/trigger_suite.py")],
        cwd=str(root), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if trigger_cp.returncode != 0:
        errors.append("trigger suite generation failed: " + trigger_cp.stderr)
    else:
        trigger_cases = json.loads(trigger_cp.stdout)["cases"]
        if len(trigger_cases) < int(sampling.get("trigger_cases_minimum", 0)):
            errors.append("trigger suite too small")
        if {item["language"] for item in trigger_cases} != {"en", "zh"}:
            errors.append("trigger suite must preserve English and Chinese coverage")
        if not any(x["should_trigger"] for x in trigger_cases) or not any(not x["should_trigger"] for x in trigger_cases):
            errors.append("trigger suite must contain positive and negative cases")

    mutation_path = root / "qualification/mutations/mutations.json"
    if mutation_path.is_file():
        mutation_ids = {item["id"] for item in load(mutation_path).get("policy_mutants", [])}
        required_mutants = set(protocol.get("evaluator_validity", {}).get("required_mutants", []))
        if mutation_ids != required_mutants:
            errors.append("protocol required_mutants must exactly match policy mutation definitions")
    else:
        errors.append("missing mutation definitions")

    required_thresholds = {
        "handoff": ["recovery_success_uplift_min_absolute", "degradation_reduction_min_absolute"],
        "efficiency": [
            "median_total_token_ratio_max", "median_wall_time_ratio_max",
            "median_tool_call_ratio_max", "persistent_task_governance_artifacts_per_task_max",
            "managed_project_files_max"
        ],
        "attention_control": ["governance_context_token_ratio_min", "governance_context_token_ratio_max"],
        "structural_overreach": [
            "observed_scope_violations_max", "one_sided_upper_bound_95_max",
            "unexpected_changed_files_max_per_task", "unrequested_api_changes_max_per_task",
            "unrequested_architecture_changes_max_per_task"
        ],
    }
    for section, names in required_thresholds.items():
        values = thresholds.get(section, {})
        for name in names:
            if name not in values:
                errors.append("missing enforced threshold %s.%s" % (section, name))

    generalization = thresholds.get("generalization", {})
    if int(generalization.get("agent_family_min_complete_pairs", 0)) < int(sampling.get("minimum_locked_behavioral_scenarios", 0)) * locked_min:
        errors.append("agent-family generalization exposure is below locked matrix minimum")
    if int(generalization.get("project_profile_min_complete_pairs", 0)) < locked_min:
        errors.append("project-profile generalization exposure is too small")
    if "claim_semantics" not in generalization:
        errors.append("generalization claim semantics must distinguish reversal control from subgroup benefit")

    model_path = root / "governance-src/model/governance-model.json"
    if model_path.is_file():
        model = load(model_path)
        binding = model.get("project_binding", {})
        if binding.get("binding_file") != ".governance/upg.json" or binding.get("field_report_file") != ".governance/field-reports.json":
            errors.append("project binding paths must match qualification managed-file contract")
        if binding.get("field_test_reporting") is not True:
            errors.append("RC7 real-agent freeze requires field_test_reporting=true")
        if int(binding.get("managed_files_max", 0)) != 2:
            errors.append("RC7 managed project file budget must be exactly 2")

    for rel in ["upg.py", "governance-src/runtime-scripts/project_tool.py", "governance-src/schemas/field-report.schema.json"]:
        if not (root / rel).is_file():
            errors.append("missing RC7 deployment/reporting surface: " + rel)

    python_files = list((root / "qualification").rglob("*.py"))
    python_files += list((root / "tools").glob("qualification_*.py"))
    python_files += [root / "tools/validate_qualification.py", root / "upg.py"]
    for path in python_files:
        if not path.is_file():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append("syntax error %s: %s" % (path.relative_to(root), exc))

    results = root / "qualification/results"
    if results.exists():
        for path in results.rglob("*.json"):
            if path.stat().st_size == 0:
                errors.append("empty result artifact forbidden: " + str(path.relative_to(root)))

    if thresholds.get("core_task_non_inferiority", {}).get("margin_absolute", 0) >= 0:
        errors.append("non-inferiority margin must be negative")

    for error in errors:
        print("error: " + error, file=sys.stderr)
    if errors:
        return 1
    print(
        "Qualification check passed: protocol v3, hierarchical inference, explicit safety/scope exposure, "
        "deployment/report enforcement, structural-overreach control, subgroup CIs, and locked holdouts."
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
