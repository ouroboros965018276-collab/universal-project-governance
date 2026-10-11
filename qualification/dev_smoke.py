"""Run one registered real-Agent development smoke without release eligibility."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualification.adapters.command_adapter import CommandAdapter
from qualification.analysis.admission import verify_artifact
from qualification.analyze import analyze
from qualification.lib.contracts import frozen_candidate, validate_node


def rejects_development_before_inference(analysis):
    admission_errors = analysis.get("gates", {}).get("evidence_admission", {}).get("errors", [])
    return (
        analysis.get("status") == "FAIL"
        and any("development evidence cannot promote release" in item for item in admission_errors)
        and analysis.get("notes") == ["Evidence rejected before inference."]
        and analysis.get("effects") == {}
    )


def build_manifest(adapter, scenario, round_id):
    candidate = frozen_candidate()
    identity = candidate["identity"]
    pair_id = "%s:%s:A2" % (round_id, scenario)
    trial_id = str(uuid.uuid5(uuid.NAMESPACE_URL, pair_id))
    slot = {
        "trial_id": trial_id,
        "round_id": round_id,
        "kind": "behavioral",
        "scenario_id": scenario,
        "arm": "A2",
        "pair_id": pair_id,
        "repetition": 1,
        "agent": adapter.config["agent"],
        "adapter_config_sha256": adapter.identity()["adapter_config_sha256"],
        "adapter_runtime_sha256": adapter.identity()["adapter_runtime_sha256"],
        "host_tool_name": adapter.identity()["host_tool_name"],
        "host_tool_version": adapter.identity()["host_tool_version"],
        "isolation_attestation": adapter.config.get("isolation_attestation"),
        "tool_profile": adapter.config.get("tool_profile"),
        "budget_profile": adapter.config.get("budget_profile"),
    }
    return {
        "schema_version": 1,
        "qualification_set": "dev",
        "round_id": round_id,
        "qualification_fingerprint": identity["qualification_fingerprint"],
        "protocol_revision": candidate["protocol"]["protocol_revision"],
        "randomization_seed": 0,
        "order_method": "development-fixed-order",
        "trials": [slot],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario", default="dev-small-typo")
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir).resolve()
    if output_dir.exists():
        raise ValueError("smoke output directory already exists; preserve prior evidence and choose a new directory")
    output_dir.mkdir(parents=True)
    round_id = "dev-smoke-" + uuid.uuid4().hex
    adapter = CommandAdapter.from_path(args.adapter)
    if not adapter.supports("skill_injection"):
        raise ValueError("A2 development smoke requires adapter capability skill_injection")
    manifest = build_manifest(adapter, args.scenario, round_id)
    manifest_path = output_dir / "registration.json"
    trial_path = output_dir / "trial.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    command = [
        sys.executable,
        str(ROOT / "qualification/run_trial.py"),
        "--labs",
        str(ROOT / "qualification/fixtures/dev/behavioral-labs.json"),
        "--scenario",
        args.scenario,
        "--arm",
        "A2",
        "--adapter",
        str(pathlib.Path(args.adapter).resolve()),
        "--pair-id",
        manifest["trials"][0]["pair_id"],
        "--round-manifest",
        str(manifest_path),
        "--raw-dir",
        str(output_dir / "raw"),
        "--trial-id",
        manifest["trials"][0]["trial_id"],
        "--output",
        str(trial_path),
    ]
    completed = subprocess.run(command, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise RuntimeError("development trial failed: " + (completed.stderr[-2000:] or completed.stdout[-2000:]))

    trial = json.loads(trial_path.read_text(encoding="utf-8"))
    trial_schema = json.loads((ROOT / "qualification/protocol/schemas/trial.schema.json").read_text(encoding="utf-8"))
    trial_errors = validate_node(trial, trial_schema)
    artifact_errors = verify_artifact(trial)
    candidate = frozen_candidate()
    protocol = json.loads((ROOT / "qualification/protocol/qualification-v3.json").read_text(encoding="utf-8"))
    thresholds = json.loads((ROOT / "qualification/protocol/thresholds.json").read_text(encoding="utf-8"))
    analysis = analyze([trial], thresholds, protocol, candidate["identity"]["qualification_fingerprint"], manifest)
    analysis_path = output_dir / "release-analyzer-check.json"
    analysis_path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    admission_errors = analysis.get("gates", {}).get("evidence_admission", {}).get("errors", [])
    rejected_dev = rejects_development_before_inference(analysis)
    deployment = trial.get("outcome", {}).get("deployment", {})
    checks = {
        "registered_before_execution": trial.get("trial_id") == manifest["trials"][0]["trial_id"],
        "real_agent_process_succeeded": trial.get("evidence", {}).get("exit_code") == 0,
        "trial_schema_valid": not trial_errors,
        "artifact_retained_and_verified": not artifact_errors,
        "task_and_governance_checks_passed": (
            trial.get("outcome", {}).get("task_success") is True
            and trial.get("outcome", {}).get("governance_defect_free") is True
        ),
        "a2_binding_and_single_report_passed": (
            deployment.get("binding_ok") is True
            and deployment.get("field_report_recorded") is True
            and deployment.get("report_count") == 1
        ),
        "release_analyzer_rejects_dev_evidence": rejected_dev,
    }
    summary = {
        "schema_version": 1,
        "smoke_id": round_id,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "qualification_set": "dev",
        "release_eligible": False,
        "candidate_version": candidate["identity"]["version"],
        "behavioral_fingerprint": candidate["identity"]["behavioral_fingerprint"],
        "qualification_fingerprint": candidate["identity"]["qualification_fingerprint"],
        "trial_id": trial.get("trial_id"),
        "adapter_identity": adapter.identity(),
        "agent": adapter.config["agent"],
        "host_tool": adapter.config["host_tool"],
        "workspace_isolation": adapter.config["workspace_isolation"],
        "externally_attested_isolation": bool(adapter.config.get("isolation_attestation")),
        "scenario_id": args.scenario,
        "registered_trials": len(manifest["trials"]),
        "checks": checks,
        "usage": trial.get("usage", {}),
        "release_analyzer_status": analysis.get("status"),
        "release_admission_errors": admission_errors,
        "schema_errors": trial_errors,
        "artifact_errors": artifact_errors,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        raise SystemExit(2)
