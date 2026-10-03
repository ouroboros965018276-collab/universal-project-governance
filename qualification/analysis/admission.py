"""Fail closed before computing release statistics; operator attestations remain external trust anchors."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from qualification.lib.contracts import ROOT, validate_node

def digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

def verify_artifact(row):
    """Review the retained bytes, not just an asserted hash. Unit tests mock this I/O boundary."""
    import pathlib
    try:
        evidence = row["evidence"]
        path = pathlib.Path(evidence["artifact_manifest"])
        if not path.is_file() or path.is_symlink():
            return ["retained artifact unavailable or symlinked"]
        data = path.read_bytes()
        if "sha256:" + hashlib.sha256(data).hexdigest() != evidence["artifact_manifest_sha256"]:
            return ["retained artifact digest mismatch"]
        artifact = json.loads(data.decode("utf-8"))
        if artifact.get("trial_id") != row["trial_id"] or not all(isinstance(artifact.get(k), dict) for k in ["before", "after", "execution"]):
            return ["retained artifact contract mismatch"]
        return []
    except (KeyError, OSError, ValueError, TypeError):
        return ["retained artifact unreadable or malformed"]

def admit(rows, fingerprint, protocol, manifest=None):
    if not rows:
        return {"state": "MORE_DATA", "errors": [], "accepted": 0}
    errors = []
    freeze = json.loads((ROOT / "qualification/FREEZE.json").read_text(encoding="utf-8"))
    from tools.qualification_freeze import expected
    if expected(ROOT) != freeze:
        errors.append("frozen source/runtime/evaluator drift detected")
    if fingerprint != freeze["qualification_fingerprint"]:
        errors.append("requested fingerprint differs from candidate freeze")
    if not isinstance(manifest, dict):
        return {"state": "FAIL", "errors": errors + ["registered round manifest required"], "accepted": 0}
    if manifest.get("qualification_fingerprint") != fingerprint or manifest.get("protocol_revision") != protocol.get("protocol_revision"):
        errors.append("round identity/protocol revision mismatch")
    if type(manifest.get("randomization_seed")) is not int or manifest.get("order_method") != "blocked-temporally-interleaved":
        errors.append("round randomization contract missing")
    schema = json.loads((ROOT / "qualification/protocol/schemas/trial.schema.json").read_text(encoding="utf-8"))
    slots = manifest.get("trials", [])
    if not isinstance(slots, list) or not slots or not all(isinstance(x, dict) and isinstance(x.get("trial_id"), str) for x in slots):
        return {"state": "FAIL", "errors": errors + ["invalid registered trial list"], "accepted": 0}
    planned = {x.get("trial_id"): x for x in slots}
    if len(planned) != len(slots) or None in planned:
        errors.append("invalid/duplicate registered trial identities")
    seen = set(); cells = Counter()
    fixtures = {}
    for kind, filename in [("behavioral", "behavioral-labs.json"), ("handoff", "handoff-labs.json")]:
        fixtures[kind] = {x["id"]: x for x in json.loads((ROOT / "qualification/fixtures/holdout/locked" / filename).read_text(encoding="utf-8"))["labs"]}
    from qualification.trigger_suite import build
    trigger_cases = {x["id"]: x for x in build(json.loads((ROOT / "qualification/fixtures/trigger-families.json").read_text(encoding="utf-8")))}
    for index, row in enumerate(rows):
        prefix = "row %d: " % index
        malformed = validate_node(row, schema)
        if malformed:
            errors.extend(prefix + x for x in malformed); continue
        tid = row["trial_id"]
        if tid in seen:
            errors.append(prefix + "duplicate trial_id")
        seen.add(tid)
        slot = planned.get(tid)
        if not slot:
            errors.append(prefix + "unregistered trial"); continue
        for key in ["kind", "scenario_id", "arm", "pair_id", "repetition", "round_id"]:
            if row.get(key) != slot.get(key): errors.append(prefix + key + " differs from registration")
        if row["round_id"] != manifest.get("round_id"):
            errors.append(prefix + "trial belongs to another round")
        for key in ["agent", "adapter_config_sha256", "adapter_runtime_sha256", "host_tool_name", "host_tool_version", "isolation_attestation"]:
            actual = row.get("agent") if key == "agent" else row["environment"].get(key)
            if actual != slot.get(key): errors.append(prefix + key + " differs from registered execution")
        env = row["environment"]
        for key in ["tool_profile", "budget_profile"]:
            if env.get(key) != slot.get(key): errors.append(prefix + key + " differs from registration")
        if env.get("qualification_set") != "locked": errors.append(prefix + "development evidence cannot promote release")
        if row["fingerprints"] != {"behavioral": freeze["behavioral_fingerprint"], "qualification": fingerprint}:
            errors.append(prefix + "trial fingerprint mismatch")
        try:
            start = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00")); end = datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
            if end < start: errors.append(prefix + "completion before start")
        except ValueError:
            errors.append(prefix + "invalid execution time")
        kind = row["kind"]; lab = fixtures.get(kind, {}).get(row["scenario_id"])
        required_outcomes = {"behavioral": ["task_success", "governance_defect_free", "critical_failures"], "handoff": ["task_success", "governance_defect_free", "critical_failures", "handoff_degraded", "handoff_condition"], "trigger": ["should_trigger", "triggered"], "mutation": ["eval_detected_regression"]}.get(kind, [])
        for key in required_outcomes:
            if key not in row["outcome"]: errors.append(prefix + "required outcome missing: " + key)
        if kind in fixtures:
            if lab is None: errors.append(prefix + "unknown locked scenario")
            elif set(row["safety_exposures"]) != set(lab["safety_exposures"]): errors.append(prefix + "exposure differs from frozen fixture")
            elif env.get("project_profile") != lab["profile"]: errors.append(prefix + "profile differs from frozen fixture")
            if kind == "behavioral" and lab and row["arm"] == "A2" and row["outcome"].get("scope_metrics", {}).get("overreach_exposure") != lab["scope_contract"]["overreach_exposure"]:
                errors.append(prefix + "scope cohort differs from frozen fixture")
        if kind == "trigger":
            case = trigger_cases.get(row["scenario_id"])
            if case is None: errors.append(prefix + "unknown trigger case")
            elif row["outcome"].get("should_trigger") != case["should_trigger"]: errors.append(prefix + "trigger target differs from frozen case")
        if kind == "mutation" and env.get("mutation_id") not in protocol["evaluator_validity"]["required_mutants"]: errors.append(prefix + "unknown mutant")
        if kind == "mutation" and env.get("mutation_id") != slot.get("mutation_id"):
            errors.append(prefix + "mutant differs from registration")
        if kind == "ablation": errors.append(prefix + "exploratory ablation cannot promote release")
        if kind == "handoff":
            for key in ["source_agent_family", "source_adapter_config_sha256", "source_adapter_runtime_sha256", "source_host_tool_name", "source_host_tool_version", "source_model_id", "source_scaffold_version", "source_isolation_attestation"]:
                if not env.get(key) or env[key] != slot.get(key): errors.append(prefix + "source execution identity mismatch: " + key)
            if row["outcome"].get("handoff_condition") != slot.get("handoff_condition"): errors.append(prefix + "handoff condition mismatch")
        cells[(kind, row["scenario_id"], row["agent"]["family"], row["arm"], row["outcome"].get("handoff_condition"))] += 1
        if row["repetition"] > protocol["sampling"]["locked_repetitions_per_cell_max"]: errors.append(prefix + "repetition exceeds preregistered maximum")
        if not row["evidence"].get("artifact_manifest_sha256") or not row["evidence"].get("exit_code") == 0:
            errors.append(prefix + "reviewable artifact identity missing or execution failed")
        errors.extend(prefix + x for x in verify_artifact(row))
    max_reps = protocol["sampling"]["locked_repetitions_per_cell_max"]
    if any(n > max_reps for cell, n in cells.items() if cell[0] in {"behavioral", "handoff"}): errors.append("cell exceeds sampling maximum")
    missing = sorted(set(planned) - seen)
    return {"state": "FAIL" if errors else ("MORE_DATA" if missing else "PASS"), "errors": errors, "missing_trials": missing, "accepted": len(rows) if not errors else 0, "input_sha256": digest(rows), "round_manifest_sha256": digest(manifest)}
