#!/usr/bin/env python3
"""Install, verify, report, export, and remove bounded project-local UPG state."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

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

def expected_binding():
    idx = index()
    cfg = idx["project_binding"]
    return {
        "schema_version": 1,
        "managed_by": idx["name"],
        "runtime_version": idx["version"],
        "field_test_reporting": bool(cfg["field_test_reporting"]),
        "managed_files": [cfg["binding_file"], cfg["field_report_file"]],
        "field_report_file": cfg["field_report_file"],
        "max_reports": int(cfg["max_reports"]),
    }

def validate_binding(value):
    expected = expected_binding()
    errors = []
    if not isinstance(value, dict):
        return ["binding must be an object"]
    if value.get("managed_by") != expected["managed_by"]:
        errors.append("binding is not owned by universal-project-governance")
    managed = value.get("managed_files")
    if managed != expected["managed_files"]:
        errors.append("managed_files drift detected")
    if value.get("field_report_file") != expected["field_report_file"]:
        errors.append("field_report_file drift detected")
    if value.get("max_reports") != expected["max_reports"]:
        errors.append("max_reports drift detected")
    return errors

def ledger_default():
    return {"schema_version": 1, "runtime_version": index()["version"], "reports": []}

def ensure(project):
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    report_path = resolve(project, cfg["field_report_file"])
    if binding_path.exists():
        current = load_json(binding_path)
        errors = validate_binding(current)
        if errors:
            raise ValueError("; ".join(errors))
    binding = expected_binding()
    write_json_atomic(binding_path, binding)
    if report_path.exists():
        ledger = load_json(report_path)
        if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("reports"), list):
            raise ValueError("field report ledger is invalid")
        ledger["runtime_version"] = index()["version"]
    else:
        ledger = ledger_default()
    write_json_atomic(report_path, ledger)
    return {"binding": str(binding_path), "field_reports": str(report_path), "report_count": len(ledger["reports"])}

def status(project):
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    report_path = resolve(project, cfg["field_report_file"])
    if not binding_path.is_file():
        return {"ok": False, "reason": "binding-missing"}
    binding = load_json(binding_path)
    errors = validate_binding(binding)
    if errors:
        return {"ok": False, "reason": "binding-drift", "errors": errors}
    if not report_path.is_file():
        return {"ok": False, "reason": "field-report-ledger-missing"}
    ledger = load_json(report_path)
    if not isinstance(ledger, dict) or not isinstance(ledger.get("reports"), list):
        return {"ok": False, "reason": "field-report-ledger-invalid"}
    return {
        "ok": True,
        "runtime_version": index()["version"],
        "binding_runtime_version": binding.get("runtime_version"),
        "field_test_reporting": binding.get("field_test_reporting"),
        "managed_files": binding.get("managed_files", []),
        "report_count": len(ledger["reports"]),
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
    secret_markers = [
        "-----BEGIN " + "PRIVATE KEY-----",
        "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
        "g" + "hp_",
        "github" + "_pat_",
        "AK" + "IA",
    ]
    if any(marker in encoded for marker in secret_markers):
        errors.append("field report appears to contain credential material")
    if errors:
        raise ValueError("; ".join(errors))

def record_report(project, input_path):
    ensured = ensure(project)
    cfg = config()
    report_path = resolve(project, cfg["field_report_file"])
    ledger = load_json(report_path)
    if len(ledger["reports"]) >= int(cfg["max_reports"]):
        raise ValueError("field report ledger is full; export and purge it before recording more reports")
    if input_path == "-":
        payload = json.load(sys.stdin)
    else:
        payload = load_json(input_path)
    validate_report(payload)
    entry = dict(payload)
    entry["schema_version"] = 1
    entry["sequence"] = len(ledger["reports"]) + 1
    entry["recorded_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entry["runtime_version"] = index()["version"]
    ledger["runtime_version"] = index()["version"]
    ledger["reports"].append(entry)
    write_json_atomic(report_path, ledger)
    return {"sequence": entry["sequence"], "report_count": len(ledger["reports"]), "path": str(report_path), "binding": ensured["binding"]}

def export_reports(project, output):
    state = status(project)
    if not state.get("ok"):
        raise ValueError("cannot export: project binding is not healthy")
    cfg = config()
    binding = load_json(resolve(project, cfg["binding_file"]))
    ledger = load_json(resolve(project, cfg["field_report_file"]))
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
    write_json_atomic(Path(output), payload)
    return {"output": str(Path(output).resolve()), "reports": len(ledger["reports"])}

def purge_reports(project, yes):
    if not yes:
        raise ValueError("purge requires --yes")
    state = status(project)
    if not state.get("ok"):
        raise ValueError("cannot purge: project binding is not healthy")
    report_path = resolve(project, config()["field_report_file"])
    ledger = ledger_default()
    write_json_atomic(report_path, ledger)
    return {"purged": True, "path": str(report_path)}

def remove(project, yes):
    if not yes:
        raise ValueError("remove requires --yes")
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    report_path = resolve(project, cfg["field_report_file"])
    if binding_path.exists():
        binding = load_json(binding_path)
        errors = validate_binding(binding)
        if errors:
            raise ValueError("refusing to remove drifted/unowned binding: " + "; ".join(errors))
    removed = []
    for path in [report_path, binding_path]:
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
