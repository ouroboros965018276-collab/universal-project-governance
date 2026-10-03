from __future__ import annotations
import hashlib
import json
import pathlib
import re
import subprocess

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
    if data.get("schema_version") not in {1, 2} or not isinstance(data.get("labs"), list):
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
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))

def persistent_governance_artifacts(workspace):
    root = pathlib.Path(workspace) / ".governance"
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file())

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

def grade_lab(lab, workspace, before):
    after = snapshot(workspace)
    checks, critical = grade_checks(lab["checks"], workspace, before, after)
    return {
        "task_success": all(c["pass"] for c in checks),
        "governance_defect_free": all(c["pass"] for c in checks),
        "critical_failures": critical,
        "checks": checks,
        "changed_files": changed_files(before, after),
        "persistent_governance_artifacts": persistent_governance_artifacts(workspace),
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
