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

def task_contract():
    """One explicit synthetic unit; dedicated lifecycle tests own counterexamples."""
    return {"revision": "p1", "scope": ["synthetic lifecycle fixture"],
            "acceptance": ["synthetic fixture state observed"], "constraints": [], "unknowns": [],
            "units": [{"id": "fixture-unit", "outcome": "exercise the stated fixture boundary",
                       "verification": "observe fixture file identities and assert the lifecycle result", "depends_on": []}]}

def task_progress(contract, status, root, paths):
    """Explicit fixture outcome using actual present/deleted file identities."""
    if len(contract["units"]) != 1 or root is None:
        raise ValueError("synthetic task progress requires its explicit project root and one fixture unit")
    passed = status == "complete"
    result = {"id": contract["units"][0]["id"], "status": "passed" if passed else "pending", "evidence": []}
    progress = {"revision": contract["revision"], "results": [result],
                "next_action": None if passed else "continue the next synthetic fixture check"}
    if passed:
        files = []
        # Empty-change fixtures explicitly verify a sentinel's observed absence;
        # real changed paths are always read from this fixture's actual root.
        for relative in paths or ["synthetic-no-change-proof.absent"]:
            path = pathlib.Path(root) / relative
            present = path.is_file()
            files.append(dict(path=relative, sha256=hashlib.sha256(path.read_bytes()).hexdigest() if present else None,
                              executable=path.stat().st_mode & 0o111 if present else 0))
        evidence = ["Synthetic fixture file identities observed; not real-Agent or product acceptance"]
        result.update(evidence=evidence, sources=files)
        progress["acceptance"] = [{"criterion": criterion, "evidence": evidence, "sources": copy.deepcopy(files)}
                                  for criterion in contract["acceptance"]]
    return progress

def seed_legacy_active(tool, root, start, git_snapshot=None):
    """Install observed pre-contract facts without invoking the new begin gate."""
    path = pathlib.Path(root) / ".governance/upg.json"
    binding = tool.load_json(path)
    binding["runtime_version"] = "3.0.0-rc.20.9"
    binding["active_workflow"] = dict(copy.deepcopy(start), observed_at="2026-10-23T00:00:00Z")
    if git_snapshot is not None:
        if not binding["git_checkpoint"]["enabled"] or not git_snapshot.get("ok"):
            raise ValueError("legacy Git fixture requires an actual successful snapshot")
        binding["git_checkpoint"]["start"] = {"workflow_id": start["workflow_id"], "snapshot": git_snapshot}
    tool.write_json_atomic(path, binding)

def report_identity(payload):
    return reviewed_report(dict(payload, workflow_id="engineering-fixture", change=change()))

def reviewed_report(payload, root=None):
    """Synthetic completion evidence only; never an actual semantic audit."""
    if payload.get("status") != "complete":
        return payload
    payload = copy.deepcopy(payload)
    files = []
    for relative in payload["changed_files"]:
        path = pathlib.Path(root) / relative if root is not None else None
        present = path is not None and path.is_file()
        files.append(dict(path=relative, sha256=hashlib.sha256(path.read_bytes()).hexdigest() if present else None,
                          executable=path.stat().st_mode & 0o111 if present else 0))
    payload["completion_review"] = dict(
        review=dict(status="passed", evidence=["Synthetic engineering fixture review; no real-Agent acceptance"], findings=[]),
        audit=dict(status="passed", evidence=["Synthetic engineering fixture audit; no real-Agent acceptance"], findings=[]),
        files=files)
    return payload

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
