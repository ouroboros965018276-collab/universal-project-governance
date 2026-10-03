"""Synthetic engine fixtures only. These are not real-Agent evidence or result rounds."""
import copy
import hashlib
import json
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
def freeze():
    return json.loads((ROOT / "qualification/FREEZE.json").read_text(encoding="utf-8"))

def change():
    return {"function": "test", "before": "observed baseline", "after": "observed target", "rationale": "engineering test", "source": "test fixture", "base_revision": "unknown", "result_revision": "unknown", "validation_revision": "unknown", "occurred_at": None, "time_source": "unknown", "parent_event_id": None}

def report_identity(payload):
    return dict(payload, workflow_id="engineering-fixture", change=change())

def registered_fixture(input_rows):
    rows = copy.deepcopy(input_rows); identity = freeze()
    labs = {kind: json.loads((ROOT / "qualification/fixtures/holdout/locked" / name).read_text(encoding="utf-8"))["labs"] for kind, name in [("behavioral", "behavioral-labs.json"), ("handoff", "handoff-labs.json")]}
    slots = []
    for row in rows:
        row["environment"] = copy.deepcopy(row["environment"])
        kind = row["kind"]; old = row["scenario_id"]
        if kind in labs:
            lab = labs[kind][int(old[1:])]; row["scenario_id"] = lab["id"]; row["safety_exposures"] = lab["safety_exposures"]
            row["environment"]["project_profile"] = lab["profile"]
            if kind == "behavioral" and row["arm"] == "A2": row["outcome"]["scope_metrics"]["overreach_exposure"] = lab["scope_contract"]["overreach_exposure"]
        condition = row["outcome"].get("handoff_condition")
        row["trial_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "%s:%s:%s:%s" % (kind, row["pair_id"], row["arm"], condition)))
        row.update(round_id="synthetic-unit-fixture", repetition=int(row["pair_id"].split("-")[-1]) + 1 if kind in labs else 1, started_at="2000-01-01T00:00:00Z", completed_at="2000-01-01T00:00:01Z", evidence={"exit_code": 0, "artifact_manifest": "synthetic-test-boundary", "artifact_manifest_sha256": "sha256:" + "a" * 64})
        row["fingerprints"] = {"behavioral": identity["behavioral_fingerprint"], "qualification": identity["qualification_fingerprint"]}
        env = row["environment"]
        for key in ["adapter_config_sha256", "adapter_runtime_sha256", "source_adapter_config_sha256"]:
            env[key] = "sha256:" + hashlib.sha256(str(env.get(key, "synthetic-" + row["agent"]["family"])).encode()).hexdigest()
        env.setdefault("host_tool_name", "synthetic-host"); env.setdefault("host_tool_version", "1")
        env.update(sandboxed=True, workspace_isolation="container", isolation_attestation={"issuer": "unit-test-only", "reference": "synthetic engineering fixture, not actual isolation", "sha256": "sha256:" + "b" * 64})
        if kind == "handoff": env.update(source_adapter_runtime_sha256="sha256:" + "c" * 64, source_model_id="source-model", source_scaffold_version="1", source_isolation_attestation=env["isolation_attestation"])
        slot = {key: row[key] for key in ["trial_id", "kind", "scenario_id", "arm", "pair_id", "repetition", "round_id", "agent"]}
        slot.update({key: env[key] for key in ["adapter_config_sha256", "adapter_runtime_sha256", "host_tool_name", "host_tool_version", "isolation_attestation"]})
        slot.update(tool_profile=env.get("tool_profile"), budget_profile=env.get("budget_profile"))
        if kind == "mutation": slot["mutation_id"] = env["mutation_id"]
        if kind == "handoff":
            slot["handoff_condition"] = condition
            slot.update({key: env[key] for key in ["source_agent_family", "source_adapter_config_sha256", "source_adapter_runtime_sha256", "source_host_tool_name", "source_host_tool_version", "source_model_id", "source_scaffold_version", "source_isolation_attestation"]})
        slots.append(slot)
    manifest = {"round_id": "synthetic-unit-fixture", "qualification_fingerprint": identity["qualification_fingerprint"], "protocol_revision": "3.1", "randomization_seed": 1729, "order_method": "blocked-temporally-interleaved", "trials": slots, "purpose": "engine regression only"}
    return rows, manifest
