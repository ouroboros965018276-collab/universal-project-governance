from __future__ import annotations
import argparse
import json
import pathlib
import sys
import tempfile
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualification.adapters.command_adapter import CommandAdapter
from qualification.lib.core import get_lab, grade_lab, materialize_lab, project_integration_status

def arm_condition(arm):
    if arm == "A0":
        return ""
    if arm == "A1":
        return (ROOT / "qualification/arms/attention-control.md").read_text(
            encoding="utf-8"
        )
    if arm == "A2":
        return ""
    if arm == "K":
        model = json.loads(
            (ROOT / "governance-src/model/governance-model.json").read_text(
                encoding="utf-8"
            )
        )
        return "# Kernel-only governance condition\n\n" + "\n".join(
            "%d. %s — %s" % (i + 1, item["id"], item["statement"])
            for i, item in enumerate(model["hot_path"])
        ) + "\n"
    raise ValueError("unknown arm")

def load_freeze():
    return json.loads(
        (ROOT / "qualification/FREEZE.json").read_text(encoding="utf-8")
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labs", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--arm", choices=["A0", "A1", "A2", "K"], required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument(
        "--kind",
        default="behavioral",
        choices=["behavioral", "mutation", "ablation"],
    )
    parser.add_argument("--mutation-id")
    parser.add_argument("--skill-path")
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-dir")
    parser.add_argument("--locked-holdout", action="store_true")
    args = parser.parse_args()

    if args.kind == "mutation" and (
        args.arm != "A2" or not args.mutation_id or not args.skill_path
    ):
        print(
            "error: mutation trials require A2, --mutation-id, and --skill-path",
            file=sys.stderr,
        )
        return 2
    if args.kind != "mutation" and (args.mutation_id or args.skill_path):
        print(
            "error: custom mutation identity/runtime is allowed only for mutation trials",
            file=sys.stderr,
        )
        return 2

    lab = get_lab(args.labs, args.scenario)
    adapter = CommandAdapter.from_path(args.adapter)
    if args.locked_holdout:
        adapter.require_locked_holdout()
    if args.arm == "A2" and not adapter.supports("skill_injection"):
        print(
            "error: A2 requires adapter capability skill_injection",
            file=sys.stderr,
        )
        return 2

    freeze = load_freeze()
    skill_path = (
        pathlib.Path(args.skill_path).resolve()
        if args.skill_path
        else ROOT / "universal-project-governance"
    )

    with tempfile.TemporaryDirectory(prefix="upg-trial-") as td:
        workspace = pathlib.Path(td) / "workspace"
        before = materialize_lab(lab, workspace)
        result = adapter.run(
            workspace,
            lab["task"],
            arm_condition(args.arm),
            skill_path=skill_path if args.arm == "A2" else None,
            raw_dir=args.raw_dir,
        )
        grade = grade_lab(lab, workspace, before)
        external = [
            item
            for item in result.get("events", {}).get("critical_failures", [])
            if isinstance(item, str)
        ]
        critical = sorted(set(grade["critical_failures"] + external))
        integration = project_integration_status(workspace, freeze.get("version"))
        deployment_required = args.arm == "A2" and args.kind == "behavioral"
        governance_ok = grade["governance_defect_free"]
        if deployment_required and not (integration["binding_ok"] and integration["field_report_recorded"]):
            governance_ok = False
        outcome = {
            "task_success": grade["task_success"],
            "governance_defect_free": governance_ok,
            "critical_failures": critical,
            "checks": grade["checks"],
            "changed_files": grade["changed_files"],
            "scope_metrics": grade["scope_metrics"],
            "deployment": {
                "required": deployment_required,
                "binding_ok": integration["binding_ok"],
                "field_report_recorded": integration["field_report_recorded"],
                "report_count": integration["report_count"],
            },
        }
        if args.kind == "mutation":
            outcome["eval_detected_regression"] = not grade["governance_defect_free"]

        usage = dict(result["usage"])
        usage["persistent_task_governance_artifacts"] = grade[
            "persistent_task_governance_artifacts"
        ]
        usage["managed_project_files"] = grade["managed_project_files"]
        environment = {
            "qualification_set": "locked" if args.locked_holdout else "dev",
            "sandboxed": adapter.config.get("sandboxed", False),
            "workspace_isolation": adapter.config.get("workspace_isolation"),
            "capabilities": adapter.config.get("capabilities", []),
            "project_profile": lab.get("profile"),
            "tool_profile": adapter.config.get("tool_profile"),
            "budget_profile": adapter.config.get("budget_profile"),
        }
        if args.mutation_id:
            environment["mutation_id"] = args.mutation_id

        trial = {
            "schema_version": 3,
            "trial_id": str(uuid.uuid4()),
            "pair_id": args.pair_id,
            "scenario_id": lab["id"],
            "kind": args.kind,
            "arm": args.arm,
            "agent": adapter.config.get("agent", {}),
            "environment": environment,
            "fingerprints": {
                "behavioral": freeze["behavioral_fingerprint"],
                "qualification": freeze["qualification_fingerprint"],
            },
            "safety_exposures": (
                []
                if args.kind == "mutation"
                else list(lab.get("safety_exposures", []))
            ),
            "outcome": outcome,
            "usage": usage,
            "evidence": dict(
                result["evidence"],
                before_sha256=grade["before_sha256"],
                after_sha256=grade["after_sha256"],
                events=result.get("events", {}),
            ),
        }

    pathlib.Path(args.output).write_text(
        json.dumps(trial, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
