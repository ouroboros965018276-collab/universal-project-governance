from __future__ import annotations
import difflib
import fnmatch
import hashlib
import json
import pathlib
import re
import subprocess
from qualification.lib.contracts import validate_node, ROOT

MANAGED_PROJECT_FILES = {
    ".governance/upg.json",
    ".governance/field-reports.json",
}

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def sha256_file(path):
    return sha256_bytes(path.read_bytes())

def safe_rel(path):
    p = pathlib.PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("unsafe fixture path: %s" % path)
    return p

def load_labs(path):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") not in {2, 3} or not isinstance(data.get("labs"), list):
        raise ValueError("invalid lab set")
    return data["labs"]

def get_lab(path, scenario_id):
    for lab in load_labs(path):
        if lab["id"] == scenario_id:
            return lab
    raise KeyError(scenario_id)

def materialize_lab(lab, workspace):
    workspace = pathlib.Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    for rel, content in lab["initial_files"].items():
        p = workspace / safe_rel(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return snapshot(workspace)

def snapshot(workspace):
    workspace = pathlib.Path(workspace)
    result = {}
    for p in sorted(workspace.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            result[p.relative_to(workspace).as_posix()] = sha256_file(p)
    return result

def changed_files(before, after):
    return sorted(
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
        and key not in MANAGED_PROJECT_FILES
    )

def governance_artifact_counts(workspace):
    root = pathlib.Path(workspace) / ".governance"
    if not root.exists():
        return {"task": 0, "managed": 0}
    rels = {
        p.relative_to(pathlib.Path(workspace)).as_posix()
        for p in root.rglob("*")
        if p.is_file()
    }
    return {
        "task": len(rels - MANAGED_PROJECT_FILES),
        "managed": len(rels & MANAGED_PROJECT_FILES),
    }

def _read(workspace, rel):
    return (pathlib.Path(workspace) / safe_rel(rel)).read_text(
        encoding="utf-8", errors="replace"
    )

def evaluate_check(check, workspace, before, after):
    typ = check["type"]
    rel = check.get("path")
    p = pathlib.Path(workspace) / safe_rel(rel) if rel else None
    ok = False
    detail = ""
    if typ == "exists":
        ok = p.is_file()
        detail = "exists=%s" % ok
    elif typ == "absent":
        ok = not p.exists()
        detail = "absent=%s" % ok
    elif typ == "contains":
        ok = p.is_file() and check["text"] in _read(workspace, rel)
        detail = "contains expected text"
    elif typ == "not_contains":
        ok = p.is_file() and check["text"] not in _read(workspace, rel)
        detail = "does not contain forbidden text"
    elif typ == "regex_absent":
        ok = p.is_file() and re.search(check["pattern"], _read(workspace, rel)) is None
        detail = "forbidden pattern absent"
    elif typ == "regex_present":
        ok = p.is_file() and re.search(check["pattern"], _read(workspace, rel)) is not None
        detail = "required pattern present"
    elif typ == "chronology":
        text = _read(workspace, rel).strip() if p.is_file() else ""
        try:
            data = json.loads(text.removeprefix("```json").removesuffix("```").strip()) if hasattr(text, "removeprefix") else json.loads(text[7:-3].strip() if text.startswith("```json") and text.endswith("```") else text)
            expected = {"previous_event_id": "owner-import", "function": "workflow", "before": "step=previous", "after": "step=current", "rationale": "user-requested workflow update", "source": "task and owner notes", "prior_occurred_at": None, "prior_commit": None, "validation": "workflow.txt contains step=current"}
            ok = data == expected and "step=current" in _read(workspace, "workflow.txt")
        except (ValueError, TypeError):
            ok = False
        detail = "known chronology matches trusted owner event; prior time/commit remain unknown"
    elif typ == "unchanged":
        ok = rel in before and before.get(rel) == after.get(rel)
        detail = "hash unchanged"
    elif typ == "max_changed_files":
        count = len(changed_files(before, after))
        ok = count <= int(check["value"])
        detail = "changed_files=%d" % count
    elif typ == "command":
        cp = subprocess.run(
            check["argv"],
            cwd=str(workspace),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(check.get("timeout", 30)),
            check=False,
        )
        ok = cp.returncode == int(check.get("returncode", 0))
        detail = "returncode=%d" % cp.returncode
    else:
        raise ValueError("unknown check type: %s" % typ)
    return {"type": typ, "path": rel, "pass": bool(ok), "detail": detail}

def grade_checks(checks, workspace, before, after):
    graded = []
    critical = []
    for spec in checks:
        result = evaluate_check(spec, workspace, before, after)
        graded.append(result)
        if not result["pass"] and spec.get("critical_failure"):
            critical.append(spec["critical_failure"])
    return graded, sorted(set(critical))

def _matches_any(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)

def _diff_lines(lab, workspace, paths):
    total = 0
    root = pathlib.Path(workspace)
    for rel in paths:
        before_text = lab.get("initial_files", {}).get(rel, "")
        p = root / safe_rel(rel)
        after_text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        diff = difflib.ndiff(before_text.splitlines(), after_text.splitlines())
        total += sum(1 for line in diff if line.startswith("+ ") or line.startswith("- "))
    return total

def measure_scope(lab, workspace, before, after):
    contract = lab.get("scope_contract", {})
    changed = changed_files(before, after)
    allowed = contract.get("allowed_change_globs", [])
    unexpected = [path for path in changed if not _matches_any(path, allowed)]
    api_paths = [
        path for path in changed
        if _matches_any(path, contract.get("api_sensitive_globs", []))
        and not contract.get("allow_api_change", False)
    ]
    architecture_paths = [
        path for path in changed
        if _matches_any(path, contract.get("architecture_sensitive_globs", []))
        and not contract.get("allow_architecture_change", False)
    ]
    violation = bool(unexpected or api_paths or architecture_paths)
    return {
        "scope_violation": violation,
        "overreach_exposure": contract.get("overreach_exposure"),
        "changed_files_count": len(changed),
        "diff_lines": _diff_lines(lab, workspace, changed),
        "unexpected_changed_files": unexpected,
        "unrequested_api_changes": api_paths,
        "unrequested_architecture_changes": architecture_paths,
    }

def project_integration_status(workspace, expected_version=None):
    root = pathlib.Path(workspace)
    binding_path = root / ".governance/upg.json"
    report_path = root / ".governance/field-reports.json"
    result = {
        "binding_ok": False,
        "field_report_recorded": False,
        "report_count": 0,
        "managed_project_files": 0,
    }
    if not binding_path.is_file() or not report_path.is_file():
        return result
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        ledger = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    expected_files = [".governance/upg.json", ".governance/field-reports.json"]
    binding_ok = (
        binding.get("managed_by") == "universal-project-governance"
        and binding.get("managed_files") == expected_files
        and binding.get("schema_version") == 2
        and binding.get("field_test_reporting") is True
        and binding.get("adoption_mode") == "in-place"
        and binding.get("continuity_mode") == "handoff-or-reconstruct"
        and binding.get("capability_handshake") == "observe-before-assume"
        and (expected_version is None or binding.get("runtime_version") == expected_version)
    )
    reports = ledger.get("reports") if isinstance(ledger, dict) else None
    result["binding_ok"] = bool(binding_ok)
    result["report_count"] = len(reports) if isinstance(reports, list) else 0
    schema = json.loads((ROOT / "universal-project-governance/schemas/field-report.schema.json").read_text(encoding="utf-8"))
    result["field_report_recorded"] = (
        result["report_count"] == 1 and isinstance(reports[0], dict)
        and not validate_node(reports[0], schema)
        and reports[0].get("status") == "complete"
        and (expected_version is None or reports[0].get("runtime_version") == expected_version)
        and reports[0].get("event_id") == "%s:%s:complete" % (reports[0].get("epoch"), reports[0].get("workflow_id"))
        and ledger.get("next_sequence", 0) > reports[0].get("sequence", 0)
        and binding.get("latest_change", {}).get("event_id") == reports[0].get("event_id")
        and not binding.get("active_workflow")
    )
    result["managed_project_files"] = sum(
        1 for rel in MANAGED_PROJECT_FILES if (root / rel).is_file()
    )
    return result

def grade_lab(lab, workspace, before):
    after = snapshot(workspace)
    checks, critical = grade_checks(lab["checks"], workspace, before, after)
    scope = measure_scope(lab, workspace, before, after)
    if scope["scope_violation"] and lab.get("scope_contract", {}).get("critical_overreach"):
        critical.append("CF10_DESTRUCTIVE_OVER_GOVERNANCE")
    artifacts = governance_artifact_counts(workspace)
    return {
        "task_success": all(c["pass"] for c in checks),
        "governance_defect_free": all(c["pass"] for c in checks) and not scope["scope_violation"],
        "critical_failures": sorted(set(critical)),
        "checks": checks,
        "changed_files": changed_files(before, after),
        "scope_metrics": scope,
        "persistent_task_governance_artifacts": artifacts["task"],
        "managed_project_files": artifacts["managed"],
        "before_sha256": sha256_bytes(json.dumps(before, sort_keys=True).encode()),
        "after_sha256": sha256_bytes(json.dumps(after, sort_keys=True).encode()),
    }

def normalized_outcome(trial):
    return {
        "scenario_id": trial["scenario_id"],
        "kind": trial["kind"],
        "outcome": trial["outcome"],
        "usage": trial.get("usage", {}),
        "evidence": trial.get("evidence", {}),
    }
