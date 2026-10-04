"""Registration and reviewable evidence for single-trial runners."""
import hashlib
import json
import pathlib
import uuid
from datetime import datetime, timezone
from qualification.lib.contracts import frozen_candidate

def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def registration(args, adapter, kind, scenario, arm, condition=None, source=None):
    started = now()
    if not args.locked_holdout:
        if not args.round_manifest and not args.trial_id:
            return {"trial_id": str(uuid.uuid4()), "round_id": "dev", "repetition": 1, "started_at": started}
        if not args.round_manifest or not args.trial_id:
            raise ValueError("registered development trial requires both --round-manifest and --trial-id")
        manifest = json.loads(pathlib.Path(args.round_manifest).read_text(encoding="utf-8"))
        candidate = frozen_candidate()
        freeze = candidate["identity"]
        protocol = candidate["protocol"]
        if manifest.get("qualification_set") != "dev":
            raise ValueError("development registration requires qualification_set=dev")
        if manifest.get("qualification_fingerprint") != freeze["qualification_fingerprint"] or manifest.get("protocol_revision") != protocol["protocol_revision"]:
            raise ValueError("development registration candidate fingerprint mismatch")
        if type(manifest.get("randomization_seed")) is not int or manifest.get("order_method") != "development-fixed-order":
            raise ValueError("development registration method is invalid")
        slots = [x for x in manifest.get("trials", []) if x.get("trial_id") == args.trial_id]
        if len(slots) != 1:
            raise ValueError("development trial is not uniquely registered")
        slot = slots[0]
        if slot.get("round_id") != manifest.get("round_id") or type(slot.get("repetition")) is not int or slot["repetition"] < 1:
            raise ValueError("development registered round/repetition mismatch")
        for key, value in [("kind", kind), ("scenario_id", scenario), ("arm", arm), ("pair_id", args.pair_id), ("agent", adapter.config.get("agent"))]:
            if slot.get(key) != value:
                raise ValueError("development registered execution mismatch: " + key)
        for key, value in adapter.identity().items():
            if key != "adapter_id" and slot.get(key) != value:
                raise ValueError("development registered adapter mismatch: " + key)
        if pathlib.Path(args.output).exists():
            raise ValueError("development trial output already exists")
        return {"trial_id": args.trial_id, "round_id": manifest["round_id"], "repetition": slot["repetition"], "started_at": started}
    if not args.round_manifest or not args.trial_id:
        raise ValueError("locked trial requires --round-manifest and registered --trial-id")
    manifest = json.loads(pathlib.Path(args.round_manifest).read_text(encoding="utf-8"))
    candidate = frozen_candidate()
    freeze = candidate["identity"]
    protocol = candidate["protocol"]
    if manifest.get("qualification_fingerprint") != freeze["qualification_fingerprint"] or manifest.get("protocol_revision") != protocol["protocol_revision"]:
        raise ValueError("round candidate fingerprint mismatch")
    slots = [x for x in manifest.get("trials", []) if x.get("trial_id") == args.trial_id]
    if len(slots) != 1:
        raise ValueError("trial not uniquely registered")
    slot = slots[0]
    if slot.get("round_id") != manifest.get("round_id") or type(slot.get("repetition")) is not int or not 1 <= slot["repetition"] <= protocol["sampling"]["locked_repetitions_per_cell_max"]:
        raise ValueError("registered round/repetition mismatch")
    for key, value in [("kind", kind), ("scenario_id", scenario), ("arm", arm), ("pair_id", args.pair_id), ("agent", adapter.config.get("agent"))]:
        if slot.get(key) != value:
            raise ValueError("registered execution mismatch: " + key)
    for key, value in adapter.identity().items():
        if key != "adapter_id" and slot.get(key) != value:
            raise ValueError("registered adapter mismatch: " + key)
    if slot.get("isolation_attestation") != adapter.config.get("isolation_attestation"):
        raise ValueError("registered isolation attestation mismatch")
    if condition is not None and slot.get("handoff_condition") != condition:
        raise ValueError("registered handoff condition mismatch")
    if source:
        source.require_locked_holdout()
        if slot.get("source_isolation_attestation") != source.config.get("isolation_attestation"):
            raise ValueError("registered source isolation attestation mismatch")
        for key, value in source.identity().items():
            if key != "adapter_id" and slot.get("source_" + key) != value:
                raise ValueError("registered source adapter mismatch")
        agent = source.config["agent"]
        for key, value in [("source_agent_family", agent["family"]), ("source_model_id", agent["model_id"]), ("source_scaffold_version", agent["scaffold_version"])]:
            if slot.get(key) != value: raise ValueError("registered source model mismatch")
    if pathlib.Path(args.output).exists():
        raise ValueError("immutable trial output already exists")
    return {"trial_id": args.trial_id, "round_id": manifest["round_id"], "repetition": slot["repetition"], "started_at": started}

def persist_evidence(args, trial_id, workspace, lab=None, result=None):
    """Qualification-only state; never copied into the Agent workspace."""
    output = pathlib.Path(args.output).resolve()
    folder = output.parent / "artifacts" / trial_id
    if folder.exists(): raise ValueError("immutable evidence directory already exists")
    folder.mkdir(parents=True)
    before = dict((lab or {}).get("initial_files", {}))
    after = {}
    root = pathlib.Path(workspace)
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if path.is_file() and not path.is_symlink() and ".git" not in path.parts:
            data = path.read_bytes()
            if len(data) > 1_000_000: raise ValueError("qualification artifact exceeds review bound")
            after[path.relative_to(root).as_posix()] = data.decode("utf-8", errors="replace")
    payload = {"trial_id": trial_id, "before": before, "after": after, "execution": result or {}}
    data = (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    path = folder / "manifest.json"; path.write_bytes(data)
    return {"artifact_manifest": str(path), "artifact_manifest_sha256": "sha256:" + hashlib.sha256(data).hexdigest()}
