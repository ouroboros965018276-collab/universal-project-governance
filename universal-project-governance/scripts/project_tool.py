#!/usr/bin/env python3
"""Install, verify, report, export, and remove bounded project-local UPG state."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import sys
import hashlib
import functools
from contextlib import contextmanager
import threading
import time
from state_tool import validate_node

ROOT = Path(__file__).resolve().parents[1]
_locks = threading.local()

def serialized(fn):
    @functools.wraps(fn)
    def wrapped(project, *args, **kwargs):
        root = project_root(project)
        key = str(root)
        held = getattr(_locks, "held", set())
        if key in held:
            return fn(project, *args, **kwargs)
        gov = root / ".governance"
        gov.mkdir(parents=True, exist_ok=True)
        lock = gov / ".upg-write-lock"
        for attempt in range(100):
            try:
                lock.mkdir()
                break
            except FileExistsError:
                time.sleep(0.02)
        else:
            raise ValueError("project state writer busy; after abrupt stop inspect and explicitly remove only the stale .upg-write-lock directory")
        held = set(held); held.add(key); _locks.held = held
        try:
            return fn(project, *args, **kwargs)
        finally:
            held.remove(key); _locks.held = held
            lock.rmdir()
            if not any(gov.iterdir()):
                gov.rmdir()
    return wrapped

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_json_atomic(path, value):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("refusing to write through symlinked managed path")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists() or tmp.is_symlink():
        raise ValueError("temporary managed path already exists: %s" % tmp)
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)

def index():
    return load_json(ROOT / "policy-index.json")

def config():
    return index()["project_binding"]

def project_root(project):
    root = Path(project).resolve()
    gov = root / ".governance"
    if gov.is_symlink():
        raise ValueError("refusing to manage a symlinked .governance directory")
    return root

def resolve(project, rel):
    root = project_root(project)
    path = root / rel
    if path.is_symlink():
        raise ValueError("refusing to manage symlinked path: %s" % rel)
    return path

def _project_origin(project):
    root = project_root(project)
    for child in root.iterdir():
        if child.name != ".governance":
            return "existing"
    gov = root / ".governance"
    if gov.is_dir() and any(child.name != ".upg-write-lock" for child in gov.iterdir()):
        return "existing"
    return "new"

def expected_binding(project_origin="existing"):
    idx = index()
    cfg = idx["project_binding"]
    reporting = bool(cfg["field_test_reporting"])
    managed_files = [cfg["binding_file"]]
    if reporting:
        managed_files.append(cfg["field_report_file"])
    return {
        "schema_version": 2,
        "managed_by": idx["name"],
        "runtime_version": idx["version"],
        "field_test_reporting": reporting,
        "managed_files": managed_files,
        "field_report_file": cfg["field_report_file"] if reporting else None,
        "max_reports": int(cfg["max_reports"]) if reporting else 0,
        "adoption_mode": cfg["adoption_mode"],
        "continuity_mode": cfg["continuity_mode"],
        "capability_handshake": cfg["capability_handshake"],
        "project_origin": project_origin,
    }

def _retirable_reporting_binding(value):
    cfg = config()
    return (
        isinstance(value, dict)
        and value.get("managed_by") == index()["name"]
        and value.get("field_test_reporting") is True
        and value.get("managed_files") == [cfg["binding_file"], cfg["field_report_file"]]
        and value.get("field_report_file") == cfg["field_report_file"]
    )

def _upgradeable_binding(value):
    cfg = config()
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 1
        and value.get("managed_by") == index()["name"]
        and value.get("managed_files") in (
            [cfg["binding_file"]],
            [cfg["binding_file"], cfg["field_report_file"]],
        )
    )

def validate_binding(value):
    origin = value.get("project_origin") if isinstance(value, dict) else "existing"
    expected = expected_binding(origin)
    errors = []
    if not isinstance(value, dict):
        return ["binding must be an object"]
    if value.get("schema_version") != 2:
        errors.append("binding schema_version drift detected")
    if value.get("managed_by") != expected["managed_by"]:
        errors.append("binding is not owned by universal-project-governance")
    if value.get("field_test_reporting") != expected["field_test_reporting"]:
        errors.append("field_test_reporting drift detected")
    if value.get("managed_files") != expected["managed_files"]:
        errors.append("managed_files drift detected")
    if value.get("field_report_file") != expected["field_report_file"]:
        errors.append("field_report_file drift detected")
    if value.get("max_reports") != expected["max_reports"]:
        errors.append("max_reports drift detected")
    for key in ["adoption_mode", "continuity_mode", "capability_handshake"]:
        if value.get(key) != expected[key]:
            errors.append("%s drift detected" % key)
    if value.get("project_origin") not in {"new", "existing"}:
        errors.append("project_origin drift detected")
    return errors
def ledger_default():
    return {"schema_version": 1, "runtime_version": index()["version"], "epoch": 0, "next_sequence": 1, "reports": []}

@serialized
def ensure(project):
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    report_path = resolve(project, cfg["field_report_file"])
    reporting = bool(cfg["field_test_reporting"])
    current = None
    origin = _project_origin(project)
    if binding_path.exists():
        current = load_json(binding_path)
        origin = current.get("project_origin", "existing") if isinstance(current, dict) else "existing"
        if _upgradeable_binding(current):
            errors = []
        else:
            errors = validate_binding(current)
        if errors:
            if not reporting and _retirable_reporting_binding(current):
                if report_path.exists():
                    ledger = load_json(report_path)
                    reports = ledger.get("reports") if isinstance(ledger, dict) else None
                    if not isinstance(reports, list):
                        raise ValueError("cannot retire invalid field report ledger")
                    if reports:
                        raise ValueError("field-test reporting retirement requires export and purge before upgrade")
                    report_path.unlink()
            else:
                raise ValueError("; ".join(errors))

    binding = expected_binding(origin)
    if isinstance(current, dict):
        for key in ["active_workflow", "latest_change", "previous_change", "export_receipt"]:
            if key in current:
                binding[key] = current[key]
    write_json_atomic(binding_path, binding)
    if not reporting:
        return {
            "binding": str(binding_path),
            "field_test_reporting": False,
            "field_reports": None,
            "report_count": 0,
        }

    if report_path.exists():
        ledger = load_json(report_path)
        if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("reports"), list):
            raise ValueError("field report ledger is invalid")
        ledger["runtime_version"] = index()["version"]
        ledger.setdefault("epoch", 0)
        ledger.setdefault("next_sequence", max([x.get("sequence", 0) for x in ledger["reports"] if isinstance(x, dict)] or [0]) + 1)
        sequences = [x.get("sequence") for x in ledger["reports"] if isinstance(x, dict)]
        if any(type(n) is not int or n < 1 for n in sequences) or type(ledger["epoch"]) is not int or ledger["epoch"] < 0 or type(ledger["next_sequence"]) is not int or ledger["next_sequence"] <= max(sequences or [0]):
            raise ValueError("invalid ledger sequence/epoch; reconcile preserved evidence before writing")
    else:
        ledger = ledger_default()
    write_json_atomic(report_path, ledger)
    return {
        "binding": str(binding_path),
        "field_test_reporting": True,
        "field_reports": str(report_path),
        "report_count": len(ledger["reports"]),
    }
def status(project):
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    if not binding_path.is_file():
        return {"ok": False, "reason": "binding-missing"}
    binding = load_json(binding_path)
    errors = validate_binding(binding)
    if errors:
        return {"ok": False, "reason": "binding-drift", "errors": errors}

    reporting = bool(binding.get("field_test_reporting"))
    report_count = 0
    if reporting:
        report_path = resolve(project, cfg["field_report_file"])
        if not report_path.is_file():
            return {"ok": False, "reason": "field-report-ledger-missing"}
        ledger = load_json(report_path)
        if not isinstance(ledger, dict) or not isinstance(ledger.get("reports"), list):
            return {"ok": False, "reason": "field-report-ledger-invalid"}
        report_count = len(ledger["reports"])

    return {
        "ok": True,
        "runtime_version": index()["version"],
        "binding_runtime_version": binding.get("runtime_version"),
        "field_test_reporting": reporting,
        "managed_files": binding.get("managed_files", []),
        "report_count": report_count,
        "project_origin": binding.get("project_origin"),
        "adoption_mode": binding.get("adoption_mode"),
        "continuity_mode": binding.get("continuity_mode"),
        "capability_handshake": binding.get("capability_handshake"),
        "active_workflow": binding.get("active_workflow"),
        "latest_change": binding.get("latest_change"),
        "previous_change": binding.get("previous_change"),
    }
def validate_report(report):
    encoded = json.dumps(report, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 65536:
        raise ValueError("field report exceeds 64 KiB metadata limit")
    required = {
        "task": str,
        "status": str,
        "change_mode": str,
        "scope_guard": str,
        "risk_level": str,
        "active_rules": list,
        "changed_files": list,
        "validation": list,
        "cleanup": list,
        "structural_scope": dict,
        "integrity": str,
        "handoff": str,
        "feedback": list,
    }
    errors = []
    schema = load_json(ROOT / "schemas/field-report.schema.json")
    candidate = dict(report, schema_version=1, sequence=1, epoch=0, event_id="validation", recorded_at="2000-01-01T00:00:00Z", runtime_version=index()["version"])
    errors += validate_node(candidate, schema)
    change = report.get("change", {})
    if isinstance(change, dict) and change.get("occurred_at") is not None and change.get("time_source") in {"unknown", ""}:
        errors.append("known occurrence time requires its observed source")
    for key, typ in required.items():
        if key not in report:
            errors.append("missing report field " + key)
        elif not isinstance(report[key], typ):
            errors.append("report field %s has wrong type" % key)
    if report.get("status") not in {"complete", "partial", "blocked"}:
        errors.append("invalid report status")
    if report.get("change_mode") not in {"local", "structural"}:
        errors.append("invalid report change_mode")
    if report.get("scope_guard") not in {"local-only", "task-bounded-responsible-layer"}:
        errors.append("invalid report scope_guard")
    if report.get("risk_level") not in {"trivial", "low", "medium", "high", "release"}:
        errors.append("invalid report risk_level")
    if report.get("integrity") not in {"pass", "fail", "not-checked"}:
        errors.append("invalid report integrity")
    if report.get("handoff") not in {"not-required", "created", "updated", "closed"}:
        errors.append("invalid report handoff")
    scope = report.get("structural_scope")
    if isinstance(scope, dict):
        for key in ["canonical_layer", "unrelated_changes", "api_changes", "architecture_changes", "overreach_concern"]:
            if key not in scope:
                errors.append("missing structural_scope." + key)
        if "canonical_layer" in scope and not isinstance(scope["canonical_layer"], str):
            errors.append("structural_scope.canonical_layer must be string")
        for key in ["unrelated_changes", "api_changes", "architecture_changes"]:
            if key in scope and not isinstance(scope[key], list):
                errors.append("structural_scope.%s must be list" % key)
        if "overreach_concern" in scope and not isinstance(scope["overreach_concern"], bool):
            errors.append("structural_scope.overreach_concern must be boolean")
    for key in ["active_rules", "changed_files", "validation", "cleanup", "feedback"]:
        if isinstance(report.get(key), list) and any(not isinstance(x, str) for x in report[key]):
            errors.append("%s must contain strings only" % key)
    agent = report.get("agent")
    if agent is not None:
        if not isinstance(agent, dict):
            errors.append("agent must be object")
        elif any(not isinstance(v, str) for v in agent.values()):
            errors.append("agent values must be strings")
    string_values = []
    for key in ["task", "integrity", "handoff", "change_mode", "scope_guard", "risk_level"]:
        if isinstance(report.get(key), str):
            string_values.append(report[key])
    for key in ["active_rules", "changed_files", "validation", "cleanup", "feedback"]:
        if isinstance(report.get(key), list):
            string_values.extend(x for x in report[key] if isinstance(x, str))
    if isinstance(scope, dict):
        if isinstance(scope.get("canonical_layer"), str):
            string_values.append(scope["canonical_layer"])
        for key in ["unrelated_changes", "api_changes", "architecture_changes"]:
            if isinstance(scope.get(key), list):
                string_values.extend(x for x in scope[key] if isinstance(x, str))
    if any(len(value) > 1000 for value in string_values):
        errors.append("field report metadata entries must be <= 1000 characters")
    sensitive_patterns = [
        r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
        r"g" + r"hp_[A-Za-z0-9]{20,}",
        r"github" + r"_pat_[A-Za-z0-9_]{20,}",
        r"AK" + r"IA[0-9A-Z]{16}",
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}={0,2}",
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^,;\s]{6,}",
        r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^/\s:@]+:[^@\s]+@",
    ]
    if any(re.search(pattern, encoded) for pattern in sensitive_patterns):
        errors.append("field report appears to contain credential or secret material")
    if errors:
        raise ValueError("; ".join(errors))

def _reconcile_completion(project, entry):
    if entry["status"] != "complete":
        return
    binding_path = resolve(project, config()["binding_file"])
    binding = load_json(binding_path)
    latest = binding.get("latest_change", {})
    if latest.get("event_id") != entry["event_id"] and entry["sequence"] > latest.get("sequence", 0):
        if latest:
            binding["previous_change"] = latest
        binding["latest_change"] = {key: entry[key] for key in ["event_id", "workflow_id", "sequence", "epoch", "recorded_at", "change"]}
    if binding.get("active_workflow", {}).get("workflow_id") == entry["workflow_id"]:
        binding.pop("active_workflow", None)
    write_json_atomic(binding_path, binding)

@serialized
def begin_workflow(project, input_path):
    payload = load_json(input_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_id"), str) or not payload["workflow_id"]:
        raise ValueError("workflow_id required")
    # Validate the same change contract used at completion; no separate history database.
    change_schema = load_json(ROOT / "schemas/field-report.schema.json")["properties"]["change"]
    errors = validate_node(payload.get("change"), change_schema)
    if errors:
        raise ValueError("; ".join(errors))
    ensure(project)
    binding_path = resolve(project, config()["binding_file"])
    binding = load_json(binding_path)
    active = binding.get("active_workflow")
    if active and active.get("workflow_id") != payload["workflow_id"]:
        raise ValueError("another workflow is unfinished; reconstruct it before replacing its identity")
    if active:
        if {k: v for k, v in active.items() if k != "observed_at"} != payload:
            raise ValueError("conflicting workflow start; preserve the original observed checkpoint")
        return {"active_workflow": active, "idempotent": True}
    parent = binding.get("latest_change", {}).get("event_id")
    if parent and payload["change"].get("parent_event_id") != parent:
        raise ValueError("new workflow must reference the latest completed event")
    if payload["change"].get("occurred_at") is not None and payload["change"].get("time_source") in {"unknown", ""}:
        raise ValueError("known occurrence time requires its observed source")
    payload["observed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    binding["active_workflow"] = payload
    write_json_atomic(binding_path, binding)
    return {"active_workflow": payload}

@serialized
def record_report(project, input_path):
    if not bool(config()["field_test_reporting"]):
        raise ValueError("field-test reporting is disabled for this runtime")
    if input_path == "-":
        payload = json.load(sys.stdin)
    else:
        payload = load_json(input_path)
    validate_report(payload)
    ensured = ensure(project)
    cfg = config()
    report_path = resolve(project, cfg["field_report_file"])
    ledger = load_json(report_path)
    binding = load_json(resolve(project, cfg["binding_file"]))
    active = binding.get("active_workflow")
    if active and active.get("workflow_id") != payload["workflow_id"]:
        raise ValueError("completion does not match the active workflow")
    event_id = "%d:%s:%s" % (ledger["epoch"], payload["workflow_id"], payload["status"])
    auto_fields = {"schema_version", "sequence", "epoch", "event_id", "recorded_at", "runtime_version"}
    for previous in ledger["reports"]:
        if previous.get("event_id") == event_id:
            old_payload = {k: v for k, v in previous.items() if k not in auto_fields}
            if old_payload != payload:
                raise ValueError("conflicting retry for workflow report identity")
            _reconcile_completion(project, previous)
            return {"sequence": previous["sequence"], "report_count": len(ledger["reports"]), "idempotent": True, "event_id": event_id}
    parent = binding.get("latest_change", {}).get("event_id")
    if parent and payload["change"].get("parent_event_id") != parent:
        raise ValueError("completion must reference the latest completed event")
    if len(ledger["reports"]) >= int(cfg["max_reports"]):
        raise ValueError("field report ledger is full; export and purge it before recording more reports")
    entry = dict(payload)
    entry["schema_version"] = 1
    entry["sequence"] = ledger["next_sequence"]
    entry["epoch"] = ledger["epoch"]
    entry["event_id"] = event_id
    ledger["next_sequence"] += 1
    entry["recorded_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    previous_time = next((x.get("recorded_at") for x in reversed(ledger["reports"]) if isinstance(x, dict) and x.get("recorded_at")), None)
    if previous_time and datetime.fromisoformat(entry["recorded_at"].replace("Z", "+00:00")) < datetime.fromisoformat(previous_time.replace("Z", "+00:00")):
        raise ValueError("observed clock moved backwards; reconcile clock/source before recording")
    entry["runtime_version"] = index()["version"]
    ledger["runtime_version"] = index()["version"]
    ledger["reports"].append(entry)
    write_json_atomic(report_path, ledger)
    _reconcile_completion(project, entry)
    return {"sequence": entry["sequence"], "report_count": len(ledger["reports"]), "path": str(report_path), "binding": ensured["binding"]}
@serialized
def export_reports(project, output):
    if not bool(config()["field_test_reporting"]):
        raise ValueError("field-test reporting is disabled for this runtime")
    state = status(project)
    if not state.get("ok"):
        raise ValueError("cannot export: project binding is not healthy")
    cfg = config()
    binding = load_json(resolve(project, cfg["binding_file"]))
    ledger = load_json(resolve(project, cfg["field_report_file"]))
    destination = Path(output).resolve()
    if destination in {resolve(project, cfg["binding_file"]).resolve(), resolve(project, cfg["field_report_file"]).resolve()}:
        raise ValueError("export must not overwrite managed project state")
    payload = {
        "schema_version": 1,
        "export_type": "upg-field-test-reports",
        "runtime_version": index()["version"],
        "binding": {
            "managed_by": binding["managed_by"],
            "field_test_reporting": binding["field_test_reporting"],
        },
        "reports": ledger["reports"],
    }
    write_json_atomic(destination, payload)
    binding["export_receipt"] = {"epoch": ledger.get("epoch", 0), "ledger_sha256": hashlib.sha256(json.dumps(ledger, sort_keys=True).encode("utf-8")).hexdigest(), "output": str(destination), "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    write_json_atomic(resolve(project, cfg["binding_file"]), binding)
    return {"output": str(Path(output).resolve()), "reports": len(ledger["reports"])}
@serialized
def purge_reports(project, yes):
    if not yes:
        raise ValueError("purge requires --yes")
    cfg = config()
    report_path = resolve(project, cfg["field_report_file"])
    if not bool(cfg["field_test_reporting"]):
        if report_path.is_file():
            report_path.unlink()
        return {"purged": True, "path": str(report_path), "field_test_reporting": False}
    state = status(project)
    if not state.get("ok"):
        raise ValueError("cannot purge: project binding is not healthy")
    ledger = ledger_default()
    old = load_json(report_path)
    ledger["next_sequence"] = old.get("next_sequence", max([x.get("sequence", 0) for x in old.get("reports", [])] or [0]) + 1)
    ledger["epoch"] = old.get("epoch", 0) + 1
    binding = load_json(resolve(project, cfg["binding_file"]))
    if binding.get("active_workflow"):
        raise ValueError("cannot rotate reporting epoch while a workflow is unfinished")
    if old.get("reports"):
        receipt = binding.get("export_receipt", {})
        ledger_sha = hashlib.sha256(json.dumps(old, sort_keys=True).encode("utf-8")).hexdigest()
        archive = Path(receipt.get("output", ""))
        if receipt.get("ledger_sha256") != ledger_sha or not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != receipt.get("output_sha256"):
            raise ValueError("export current evidence and preserve the verified export before rotating the reporting epoch")
    write_json_atomic(report_path, ledger)
    return {"purged": True, "path": str(report_path), "field_test_reporting": True}
@serialized
def remove(project, yes):
    if not yes:
        raise ValueError("remove requires --yes")
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    managed_paths = []
    if binding_path.exists():
        binding = load_json(binding_path)
        errors = validate_binding(binding)
        if errors:
            if not bool(cfg["field_test_reporting"]) and _retirable_reporting_binding(binding):
                managed = binding.get("managed_files", [])
            else:
                raise ValueError("refusing to remove drifted/unowned binding: " + "; ".join(errors))
        else:
            managed = binding.get("managed_files", [])
        for rel in managed:
            if rel != cfg["binding_file"]:
                managed_paths.append(resolve(project, rel))
    managed_paths.append(binding_path)

    removed = []
    for path in managed_paths:
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    gov = resolve(project, ".governance")
    for child in [gov / "execution", gov / "feedback", gov / "audits"]:
        if child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass
    if gov.is_dir():
        try:
            gov.rmdir()
        except OSError:
            pass
    return {"removed": removed}
def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ["install", "ensure", "status"]:
        p = sub.add_parser(name)
        p.add_argument("project", nargs="?", default=".")
    report = sub.add_parser("report")
    report.add_argument("project", nargs="?", default=".")
    report.add_argument("--input", required=True)
    workflow = sub.add_parser("begin")
    workflow.add_argument("project", nargs="?", default=".")
    workflow.add_argument("--input", required=True)
    export = sub.add_parser("export")
    export.add_argument("project", nargs="?", default=".")
    export.add_argument("--output", required=True)
    purge = sub.add_parser("purge-reports")
    purge.add_argument("project", nargs="?", default=".")
    purge.add_argument("--yes", action="store_true")
    remove_p = sub.add_parser("remove")
    remove_p.add_argument("project", nargs="?", default=".")
    remove_p.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        if args.cmd in {"install", "ensure"}:
            result = ensure(args.project)
        elif args.cmd == "status":
            result = status(args.project)
            if not result.get("ok"):
                print(json.dumps(result, indent=2, sort_keys=True))
                return 1
        elif args.cmd == "report":
            result = record_report(args.project, args.input)
        elif args.cmd == "begin":
            result = begin_workflow(args.project, args.input)
        elif args.cmd == "export":
            result = export_reports(args.project, args.output)
        elif args.cmd == "purge-reports":
            result = purge_reports(args.project, args.yes)
        elif args.cmd == "remove":
            result = remove(args.project, args.yes)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
