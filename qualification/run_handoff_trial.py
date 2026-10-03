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
from qualification.lib.core import (
    get_lab,
    grade_checks,
    grade_lab,
    materialize_lab,
    snapshot,
    project_integration_status,
)

def add_usage(first, second):
    keys = set(first) | set(second)
    out = {}
    for key in keys:
        a = first.get(key)
        b = second.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out[key] = a + b
    out["agent_b_total_tokens"] = second.get("total_tokens")
    out["agent_b_wall_time_seconds"] = second.get("wall_time_seconds")
    out["agent_b_tool_calls"] = second.get("tool_calls")
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labs", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument(
        "--condition",
        choices=["present", "ablated"],
        required=True,
    )
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-dir")
    parser.add_argument("--locked-holdout", action="store_true")
    args = parser.parse_args()

    lab = get_lab(args.labs, args.scenario)
    adapter = CommandAdapter.from_path(args.adapter)
    if args.locked_holdout:
        adapter.require_locked_holdout()
    for capability in ("skill_injection", "controlled_checkpoint"):
        if not adapter.supports(capability):
            print(
                "error: handoff qualification requires " + capability,
                file=sys.stderr,
            )
            return 2

    freeze = json.loads(
        (ROOT / "qualification/FREEZE.json").read_text(encoding="utf-8")
    )

    with tempfile.TemporaryDirectory(prefix="upg-handoff-") as td:
        workspace = pathlib.Path(td) / "workspace"
        before = materialize_lab(lab, workspace)

        first = adapter.run_checkpointed(
            workspace,
            lab["task"],
            "",
            lab["checkpoint"],
            skill_path=ROOT / "universal-project-governance",
            raw_dir=args.raw_dir,
            phase="agent-a",
        )
        if not first["events"].get("checkpoint_reached"):
            print(
                "error: controlled checkpoint was not reached",
                file=sys.stderr,
            )
            return 2

        after_first = snapshot(workspace)
        preserve_specs = lab.get("checkpoint", {}).get("preserve", [])
        preserve_first, _ = grade_checks(
            preserve_specs,
            workspace,
            before,
            after_first,
        )

        handoff_path = workspace / ".governance/handoff.json"
        handoff_was_present = handoff_path.is_file()
        if args.condition == "ablated" and handoff_path.exists():
            handoff_path.unlink()

        second = adapter.run(
            workspace,
            lab["continuation_task"],
            "",
            skill_path=ROOT / "universal-project-governance",
            raw_dir=args.raw_dir,
            phase="agent-b",
        )

        grade = grade_lab(lab, workspace, before)
        final = snapshot(workspace)
        preserve_final, _ = grade_checks(
            preserve_specs,
            workspace,
            before,
            final,
        )
        degraded = any(
            initial["pass"] and not finished["pass"]
            for initial, finished in zip(preserve_first, preserve_final)
        )

        external = []
        for result in (first, second):
            external.extend(
                item
                for item in result.get("events", {}).get(
                    "critical_failures", []
                )
                if isinstance(item, str)
            )
        critical = list(grade["critical_failures"]) + external
        if args.condition == "present" and not handoff_was_present:
            critical.append("CF09_HANDOFF_DROPS_CRITICAL_RISK")
        critical = sorted(set(critical))

        integration = project_integration_status(workspace, freeze.get("version"))
        governance_ok = grade["governance_defect_free"] and integration["binding_ok"] and integration["field_report_recorded"]
        outcome = {
            "task_success": grade["task_success"],
            "governance_defect_free": governance_ok,
            "critical_failures": critical,
            "handoff_condition": args.condition,
            "handoff_created_by_a": handoff_was_present,
            "handoff_degraded": bool(degraded),
            "checks": grade["checks"],
            "changed_files": grade["changed_files"],
            "scope_metrics": grade["scope_metrics"],
            "deployment": {
                "required": True,
                "binding_ok": integration["binding_ok"],
                "field_report_recorded": integration["field_report_recorded"],
                "report_count": integration["report_count"],
            },
            "preserve_at_checkpoint": preserve_first,
            "preserve_at_finish": preserve_final,
        }
        usage = add_usage(first["usage"], second["usage"])
        usage["persistent_task_governance_artifacts"] = grade[
            "persistent_task_governance_artifacts"
        ]
        usage["managed_project_files"] = grade["managed_project_files"]

        trial = {
            "schema_version": 3,
            "trial_id": str(uuid.uuid4()),
            "pair_id": args.pair_id,
            "scenario_id": lab["id"],
            "kind": "handoff",
            "arm": "A2",
            "agent": adapter.config.get("agent", {}),
            "environment": {
                "qualification_set": (
                    "locked" if args.locked_holdout else "dev"
                ),
                "sandboxed": adapter.config.get("sandboxed"),
                "workspace_isolation": adapter.config.get(
                    "workspace_isolation"
                ),
                "project_profile": lab.get("profile"),
                "tool_profile": adapter.config.get("tool_profile"),
                "budget_profile": adapter.config.get("budget_profile"),
                "handoff_condition": args.condition,
            },
            "fingerprints": {
                "behavioral": freeze["behavioral_fingerprint"],
                "qualification": freeze["qualification_fingerprint"],
            },
            "safety_exposures": list(lab.get("safety_exposures", [])),
            "outcome": outcome,
            "usage": usage,
            "evidence": {
                "agent_a": first["evidence"],
                "agent_b": second["evidence"],
                "before_sha256": grade["before_sha256"],
                "after_sha256": grade["after_sha256"],
            },
        }

    pathlib.Path(args.output).write_text(
        json.dumps(trial, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
