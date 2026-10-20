#!/usr/bin/env python3
"""Install, verify, report, export, and remove bounded project-local UPG state."""
from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timezone
import json
import re
from pathlib import Path, PurePosixPath
import sys
import hashlib
import functools
from contextlib import contextmanager, ExitStack
import threading
import time
from state_tool import validate_node
import process_guard as guards

ROOT = Path(__file__).resolve().parents[1]
_locks = threading.local()
CONTROLLED_GUARDS = frozenset({".upg-writer.guard", ".upg-worker.guard", ".upg-validation.guard", ".upg-checkpoint.guard", ".upg-supervisor.guard"})

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
        legacy = gov / ".upg-write-lock"
        guard = None
        for attempt in range(100):
            if not legacy.exists() and not legacy.is_symlink():
                guard = guards.acquire(root, ".upg-writer.guard")
                if guard is not None:
                    break
            time.sleep(0.02)
        else:
            raise ValueError("project state writer busy; legacy directory locks require explicit owner inspection")
        held = set(held); held.add(key); _locks.held = held
        try:
            with guard, guards.holding(guard):
                return fn(project, *args, **kwargs)
        finally:
            held.remove(key); _locks.held = held
            # Stable guard inodes remain infrastructure. Unlinking on release
            # could let two POSIX open-file descriptions protect different files.

    return wrapped

def load_json(path):
    for attempt in range(3):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.02)

def write_json_atomic(path, value):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("refusing to write through symlinked managed path")
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy = path.with_name(path.name + ".tmp")
    if legacy.exists() or legacy.is_symlink():
        raise ValueError("temporary managed path already exists: %s" % legacy)
    raw = (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".upg-" + uuid.uuid4().hex + ".tmp")
    identity = None
    try:
        with temporary.open("xb") as stream:
            info = os.fstat(stream.fileno())
            identity = info.st_dev, info.st_ino
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != raw:
            raise ValueError("managed temporary write failed readback")
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("managed destination changed to a symlink")
        os.replace(str(temporary), str(path))
    finally:
        if identity is not None and temporary.is_file() and not temporary.is_symlink():
            info = temporary.stat()
            if (info.st_dev, info.st_ino) == identity:
                temporary.unlink()


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
    if gov.is_dir() and any(child.name != ".upg-write-lock" and child.name not in CONTROLLED_GUARDS for child in gov.iterdir()):
        return "existing"
    return "new"

def expected_binding(project_origin="existing", field_test_reporting=None):
    idx = index()
    cfg = idx["project_binding"]
    reporting = cfg["field_test_reporting"] if field_test_reporting is None else field_test_reporting
    if type(reporting) is not bool:
        raise ValueError("field_test_reporting must be boolean")
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
        "git_checkpoint": json.loads(json.dumps(cfg.get("git_checkpoint", {}))),
    }

def _validate_git_policy(policy):
    if not isinstance(policy, dict):
        return ["git_checkpoint must be an object"]
    errors = []
    if type(policy.get("enabled")) is not bool:
        errors.append("git_checkpoint.enabled must be boolean")
    seconds = policy.get("min_interval_seconds")
    if type(seconds) is not int or not 0 <= seconds <= 86400:
        errors.append("git_checkpoint.min_interval_seconds must be an integer from 0 to 86400")
    for key in ("allowed_paths", "status_paths"):
        paths = policy.get(key)
        if not isinstance(paths, list) or len(paths) > 1024:
            errors.append("git_checkpoint.%s must be a bounded path list" % key)
            continue
        for value in paths:
            if (not isinstance(value, str) or not value or len(value) > 1024
                    or "\x00" in value or "\\" in value or re.match(r"^[A-Za-z]:", value)
                    or value.startswith("/") or ".." in PurePosixPath(value).parts
                    or ".git" in PurePosixPath(value).parts):
                errors.append("git_checkpoint.%s requires project-relative literal paths" % key)
                break
    if policy.get("enabled") and not policy.get("allowed_paths"):
        errors.append("enabled Git checkpoints require an explicit allowed path scope")
    if "bootstrap" in policy and type(policy["bootstrap"]) is not bool:
        errors.append("git_checkpoint.bootstrap must be boolean")
    if "watcher" in policy:
        watcher = policy["watcher"]
        if not isinstance(watcher, dict) or not isinstance(watcher.get("configuration"), dict):
            errors.append("git_checkpoint.watcher requires its configuration object")
        else:
            try:
                from git_watch import validate_configuration
                validate_configuration(watcher["configuration"])
            except ValueError as error:
                errors.append(str(error))
            if "desired_running" in watcher and type(watcher["desired_running"]) is not bool:
                errors.append("git_checkpoint.watcher.desired_running must be boolean")
            supervisor = watcher.get("supervisor")
            if supervisor is not None and (not isinstance(supervisor, dict) or type(supervisor.get("enabled")) is not bool):
                errors.append("git_checkpoint.watcher.supervisor.enabled must be boolean")
    return errors

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
    errors = []
    if not isinstance(value, dict):
        return ["binding must be an object"]
    reporting = value.get("field_test_reporting")
    if type(reporting) is not bool:
        errors.append("field_test_reporting must be boolean")
        reporting = None
    expected = expected_binding(origin, reporting)
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
    if "git_checkpoint" in value:
        errors += _validate_git_policy(value["git_checkpoint"])
    return errors
def ledger_default(epoch=0, next_sequence=1):
    return {"schema_version": 1, "runtime_version": index()["version"], "epoch": epoch, "next_sequence": next_sequence, "reports": []}

@serialized
def ensure(project, field_test_reporting=None):
    cfg = config()
    if field_test_reporting is not None and type(field_test_reporting) is not bool:
        raise ValueError("field_test_reporting must be boolean")
    binding_path = resolve(project, cfg["binding_file"])
    report_path = resolve(project, cfg["field_report_file"])
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
            raise ValueError("; ".join(errors))

    existing_reporting = current.get("field_test_reporting") if isinstance(current, dict) else None
    if existing_reporting is True and field_test_reporting is False:
        raise ValueError("disabling project field-test reporting requires an explicit export and ledger-retirement workflow")
    reporting = (
        field_test_reporting
        if field_test_reporting is not None
        else existing_reporting if type(existing_reporting) is bool
        else bool(cfg["field_test_reporting"])
    )

    binding = expected_binding(origin, reporting)
    if isinstance(current, dict):
        for key in ["active_workflow", "latest_change", "previous_change", "export_receipt", "current_state", "current_state_sequence", "git_checkpoint"]:
            if key in current:
                binding[key] = current[key]
    # Add optional capability defaults without changing any existing choice or
    # transient recovery metadata during in-place runtime upgrades.
    defaults = expected_binding(origin, reporting)["git_checkpoint"]
    merged = defaults
    merged.update(binding.get("git_checkpoint", {}))
    binding["git_checkpoint"] = merged
    if not reporting:
        write_json_atomic(binding_path, binding)
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
        latest = current.get("latest_change", {}) if isinstance(current, dict) else {}
        if not isinstance(latest, dict):
            raise ValueError("latest completion state is invalid; reconcile preserved project state before enabling reporting")
        latest_sequence = latest.get("sequence", 0)
        active_sequence = (current or {}).get("active_workflow", {}).get("last_outcome", {}).get("sequence", 0)
        latest_epoch = latest.get("epoch", 0)
        if (type(latest_sequence) is not int or latest_sequence < 0 or type(active_sequence) is not int
                or active_sequence < 0 or type(latest_epoch) is not int or latest_epoch < 0):
            raise ValueError("latest completion sequence/epoch is invalid; reconcile preserved project state before enabling reporting")
        latest_sequence = max(latest_sequence, active_sequence)
        ledger = ledger_default(epoch=latest_epoch, next_sequence=latest_sequence + 1)
    write_json_atomic(report_path, ledger)
    write_json_atomic(binding_path, binding)
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
    pending_outcome = False
    if reporting:
        report_path = resolve(project, cfg["field_report_file"])
        if not report_path.is_file():
            return {"ok": False, "reason": "field-report-ledger-missing"}
        ledger = load_json(report_path)
        if not isinstance(ledger, dict) or not isinstance(ledger.get("reports"), list):
            return {"ok": False, "reason": "field-report-ledger-invalid"}
        report_count = len(ledger["reports"])
        active = binding.get("active_workflow", {})
        pending_outcome = bool(active) and any(
            row.get("workflow_id") == active.get("workflow_id")
            and row.get("sequence", 0) > active.get("last_outcome", {}).get("sequence", 0)
            for row in ledger["reports"] if isinstance(row, dict))
        # The public report command also accepts completed observations without
        # an active workflow. Its ledger commit can precede the binding update.
        pending_outcome = pending_outcome or any(
            row.get("status") == "complete"
            and row.get("sequence", 0) > binding.get("latest_change", {}).get("sequence", 0)
            for row in ledger["reports"] if isinstance(row, dict))

    current_state = binding.get("current_state")
    state_errors = []
    if current_state is not None:
        try:
            _verify_current_state(project, current_state)
        except (OSError, ValueError) as exc:
            state_errors.append(str(exc))
    git_state = binding.get("git_checkpoint", {})
    git_pending = bool(git_state.get("journal")) or (
        git_state.get("enabled") and git_state.get("result", {}).get("status") == "blocked")
    watcher = git_state.get("watcher", {})
    watcher_state = watcher.get("status")
    watcher_stale = bool(watcher.get("token") and watcher.get("lease_until", 0) < time.time()
                         and watcher_state not in {"stopped", "stopping"})
    watcher_pending = bool(git_state.get("enabled") and watcher.get("configuration", {}).get("enabled")
                           and (watcher_stale or watcher.get("recovery_blocked")
                                or watcher.get("supervisor", {}).get("status") == "blocked"
                                or watcher_state in {"blocked", "cancelled", "stale"}))
    return {
        "ok": not state_errors and not pending_outcome and not git_pending and not watcher_pending,
        **({"reason": "git-watcher-pending", "errors": ["Git observer is blocked or its heartbeat is stale; inspect git-watch status before claiming automatic saving"]} if watcher_pending else {}),
        **({"reason": "git-checkpoint-pending", "errors": ["Git checkpoint requires reconciliation; retry its original finish input"]} if git_pending else {}),
        **({"reason": "checkpoint-unreconciled", "errors": ["ledger commit newer than binding checkpoint; retry the original report/finish input"]} if pending_outcome else {}),
        **({"reason": "current-state-drift", "errors": state_errors} if state_errors else {}),
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
        "current_state": current_state,
        "git_checkpoint": git_state,
        "current_outcome": binding.get("active_workflow", {}).get("last_outcome") or binding.get("latest_change"),
        "state_roles": {"current": current_state.get("path") if isinstance(current_state, dict) else "active_workflow.last_outcome (if present)",
                        "latest_change": "latest completed workflow; historical while another workflow is active",
                        "field_reports": "append-only historical observations, not live project state"},
    }

@serialized
def configure_git(project, enabled, allowed_paths=None, status_paths=None, min_interval_seconds=None, bootstrap_enabled=None):
    ensure(project)
    path = resolve(project, config()["binding_file"])
    binding = load_json(path)
    policy = binding["git_checkpoint"]
    if policy.get("journal"):
        raise ValueError("reconcile the pending Git transaction before changing its policy")
    if enabled and (policy.get("pending_paths") or policy.get("deferred_events")):
        if ((allowed_paths is not None and allowed_paths != policy.get("allowed_paths"))
                or (status_paths is not None and status_paths != policy.get("status_paths"))):
            raise ValueError("reconcile pending Git paths before changing their scope")
    policy["enabled"] = enabled
    if bootstrap_enabled is not None:
        policy["bootstrap"] = bootstrap_enabled
    if not enabled:
        # Explicitly disabling future automation abandons only its pending
        # scheduling, never files or Git contents. Live transactions were
        # rejected above and must retain their recovery evidence.
        uncommitted = list(policy.pop("pending_paths", []))
        policy.pop("pending_workflow_id", None)
        policy.pop("deferred_events", None)
    else:
        uncommitted = []
    for key, value in [("allowed_paths", allowed_paths), ("status_paths", status_paths),
                       ("min_interval_seconds", min_interval_seconds)]:
        if value is not None:
            policy[key] = value
    errors = _validate_git_policy(policy)
    if errors:
        raise ValueError("; ".join(errors))
    active = binding.get("active_workflow")
    if enabled:
        from git_checkpoint import bootstrap, capture
        prepared = bootstrap(project_root(project), policy)
        if not prepared.get("ok"):
            raise ValueError("cannot prepare project Git: " + prepared.get("reason", "initialization unavailable"))
        observed = capture(project_root(project), policy)
        if not observed.get("ok"):
            raise ValueError("cannot enable Git checkpoints: " + observed.get("reason", "Git baseline unavailable"))
        if active and policy.get("start", {}).get("workflow_id") != active["workflow_id"]:
            policy["start"] = {"workflow_id": active["workflow_id"], "snapshot": observed}
    policy["result"] = {"status": "configured" if enabled else "disabled"}
    if uncommitted:
        policy["result"]["uncommitted_paths"] = uncommitted
    write_json_atomic(path, binding)
    return {"git_checkpoint": policy}

def _verify_current_state(project, ref):
    """Bind one existing project authority without copying its application schema."""
    from project_facts import Reader, strict_json
    schema = load_json(ROOT / "schemas/field-report.schema.json")["properties"]["current_state"]
    errors = validate_node(ref, schema)
    if errors:
        raise ValueError("invalid current_state: " + "; ".join(errors))
    if ref["path"] in {config()["binding_file"], config()["field_report_file"]}:
        raise ValueError("current_state must reference project truth, not the UPG historical ledger")
    raw = Reader(project_root(project)).read(ref["path"], limit=256 * 1024)
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("current_state changed; reconcile a new checkpoint against project truth")
    if not isinstance(strict_json(raw), dict):
        raise ValueError("current_state must reference a structured JSON object")

def _receipt_key(payload):
    return payload["status"] + (":" + payload["checkpoint_id"] if "checkpoint_id" in payload else "")

def _same_report_identity(entry, payload, epoch):
    # Binding completion checkpoints omit status; ledger entries retain it.
    return (entry.get("epoch", 0) == epoch
            and entry.get("workflow_id") == payload["workflow_id"]
            and entry.get("status", "complete") == payload["status"]
            and entry.get("checkpoint_id") == payload.get("checkpoint_id"))

def _event_id(epoch, payload, retained=()):
    base = "%d:%s:%s" % (epoch, payload["workflow_id"], _receipt_key(payload))
    # Keep existing IDs and ordinary IDs stable. Workflow names may contain
    # delimiters, so a readable ID alone cannot establish report identity.
    used = {entry.get("event_id") for entry in retained if isinstance(entry, dict)}
    event_id = base
    suffix = 0
    while event_id in used:
        suffix += 1
        event_id = base + ":collision-%d" % suffix
    return event_id
def _metadata_errors(value):
    encoded = json.dumps(value, ensure_ascii=False)
    errors = []
    if len(encoded.encode("utf-8")) > 65536:
        errors.append("field report exceeds 64 KiB metadata limit")
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
    return errors

def validate_report(report):
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
    errors = _metadata_errors(report)
    schema = load_json(ROOT / "schemas/field-report.schema.json")
    candidate = dict(report, schema_version=1, sequence=1, epoch=0, event_id="validation", recorded_at="2000-01-01T00:00:00Z", runtime_version=index()["version"])
    errors += validate_node(candidate, schema)
    if "checkpoint_id" in report and report.get("status") == "complete":
        errors.append("checkpoint_id is for partial/blocked stages; completion identity remains unique")
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
    if errors:
        raise ValueError("; ".join(errors))

def _completion_payload_sha256(entry):
    auto_fields = {"schema_version", "sequence", "epoch", "event_id", "recorded_at", "runtime_version", "start_change"}
    payload = {key: value for key, value in entry.items() if key not in auto_fields}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def _read_report(input_path):
    payload = json.load(sys.stdin) if input_path == "-" else load_json(input_path)
    if isinstance(payload, dict) and "start_change" in payload:
        raise ValueError("start_change is tool-owned; preserve the observed workflow start")
    validate_report(payload)
    return payload

def _check_workflow_change(active, payload):
    if active.get("workflow_id") != payload["workflow_id"]:
        raise ValueError("completion does not match the active workflow")
    # Outcomes can become known during work. The observed task, basis and cause
    # remain immutable; the original full start is retained beside the outcome.
    outcome_fields = {"after", "result_revision", "validation_revision", "occurred_at", "time_source"}
    start = active.get("change", {})
    if {k: v for k, v in start.items() if k not in outcome_fields} != {
        k: v for k, v in payload["change"].items() if k not in outcome_fields
    }:
        raise ValueError("completion changes immutable workflow start facts")

def _checkpoint_retry(binding, payload):
    for previous in [binding.get("latest_change", {}), binding.get("previous_change", {})]:
        if not isinstance(previous, dict):
            continue
        if _same_report_identity(previous, payload, previous.get("epoch", 0)):
            if previous.get("payload_sha256") != _completion_payload_sha256(payload):
                raise ValueError("conflicting or unverifiable retry for workflow completion identity")
            return previous
    return None

def _reconcile_completion(project, entry):
    binding_path = resolve(project, config()["binding_file"])
    binding = load_json(binding_path)
    latest = binding.get("latest_change", {})
    payload_sha256 = _completion_payload_sha256(entry)
    active = binding.get("active_workflow", {})
    if entry["status"] != "complete":
        if active.get("workflow_id") != entry["workflow_id"]:
            return
        receipts = active.setdefault("outcome_receipts", {})
        key = _receipt_key(entry)
        previous = receipts.get(key)
        if previous:
            if previous["payload_sha256"] != payload_sha256:
                raise ValueError("conflicting retry for workflow report identity")
            return
        if len(receipts) >= int(config()["max_reports"]):
            raise ValueError("workflow checkpoint receipts full; finish or explicitly split the scoped workflow")
        receipts[key] = {"event_id": entry["event_id"], "payload_sha256": payload_sha256}
        last = active.get("last_outcome", {})
        if entry["sequence"] >= last.get("sequence", 0):
            active["last_outcome"] = {key: entry[key] for key in [
                "event_id", "epoch", "workflow_id", "sequence", "recorded_at", "status", "change", "validation",
                "changed_files", "cleanup", "integrity", "handoff", "feedback",
            ]}
            for optional in ["checkpoint_id", "current_state", "git_boundary"]:
                if optional in entry:
                    active["last_outcome"][optional] = entry[optional]
            if "current_state" in entry and entry["sequence"] >= binding.get("current_state_sequence", 0):
                binding["current_state"] = entry["current_state"]
                binding["current_state_sequence"] = entry["sequence"]
        write_json_atomic(binding_path, binding)
        return
    if latest.get("event_id") == entry["event_id"]:
        if latest.get("payload_sha256") and latest["payload_sha256"] != payload_sha256:
            raise ValueError("conflicting retry for workflow completion identity")
        if binding.get("active_workflow", {}).get("workflow_id") == entry["workflow_id"]:
            binding.pop("active_workflow", None)
            write_json_atomic(binding_path, binding)
        return
    if latest.get("event_id") != entry["event_id"] and entry["sequence"] > latest.get("sequence", 0):
        if latest:
            binding["previous_change"] = latest
        binding["latest_change"] = {key: entry[key] for key in ["event_id", "workflow_id", "sequence", "epoch", "recorded_at", "change"]}
        if "start_change" in entry:
            binding["latest_change"]["start_change"] = entry["start_change"]
        binding["latest_change"]["payload_sha256"] = payload_sha256
        if "current_state" in entry:
            binding["current_state"] = entry["current_state"]
            binding["current_state_sequence"] = entry["sequence"]
    if binding.get("active_workflow", {}).get("workflow_id") == entry["workflow_id"]:
        binding.pop("active_workflow", None)
    write_json_atomic(binding_path, binding)

@serialized
def begin_workflow(project, input_path):
    payload = load_json(input_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_id"), str) or not payload["workflow_id"]:
        raise ValueError("workflow_id required")
    if {"observed_at", "last_outcome", "outcome_receipts", "start_change", "git_start"}.intersection(payload):
        raise ValueError("workflow observation and recovery fields are tool-owned")
    # Validate the same change contract used at completion; no separate history database.
    change_schema = load_json(ROOT / "schemas/field-report.schema.json")["properties"]["change"]
    errors = validate_node(payload.get("change"), change_schema) + _metadata_errors(payload)
    if errors:
        raise ValueError("; ".join(errors))
    ensure(project)
    binding_path = resolve(project, config()["binding_file"])
    binding = load_json(binding_path)
    git_state = binding.get("git_checkpoint", {})
    if (git_state.get("enabled") and (git_state.get("journal") or git_state.get("pending_paths"))
            and git_state.get("start", {}).get("workflow_id") != payload["workflow_id"]):
        raise ValueError("pending Git checkpoint belongs to the previous workflow; reconcile it before starting another")
    active = binding.get("active_workflow")
    if active and active.get("workflow_id") != payload["workflow_id"]:
        raise ValueError("another workflow is unfinished; reconstruct it before replacing its identity")
    if active:
        if {k: v for k, v in active.items() if k not in {"observed_at", "last_outcome", "outcome_receipts"}} != payload:
            raise ValueError("conflicting workflow start; preserve the original observed checkpoint")
        return {"active_workflow": active, "idempotent": True}
    if any(isinstance(value, dict) and value.get("workflow_id") == payload["workflow_id"]
           for value in [binding.get("latest_change"), binding.get("previous_change")]):
        raise ValueError("workflow identity already completed; use a new workflow_id")
    if binding.get("field_test_reporting") is True:
        ledger = load_json(resolve(project, config()["field_report_file"]))
        if any(isinstance(value, dict) and value.get("epoch") == ledger["epoch"]
               and value.get("workflow_id") == payload["workflow_id"] for value in ledger["reports"]):
            raise ValueError("workflow identity already recorded in this epoch; use a new workflow_id")
    parent = binding.get("latest_change", {}).get("event_id")
    if parent and payload["change"].get("parent_event_id") != parent:
        raise ValueError("new workflow must reference the latest completed event")
    if payload["change"].get("occurred_at") is not None and payload["change"].get("time_source") in {"unknown", ""}:
        raise ValueError("known occurrence time requires its observed source")
    payload["observed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    binding["active_workflow"] = payload
    if binding.get("git_checkpoint", {}).get("enabled"):
        from git_checkpoint import bootstrap, capture
        prepared = bootstrap(project_root(project), binding["git_checkpoint"])
        if not prepared.get("ok"):
            raise ValueError("cannot prepare project Git: " + prepared.get("reason", "initialization unavailable"))
        binding["git_checkpoint"]["start"] = {
            "workflow_id": payload["workflow_id"],
            "snapshot": capture(project_root(project), binding["git_checkpoint"]),
        }
    write_json_atomic(binding_path, binding)
    return {"active_workflow": payload}

@serialized
def record_report(project, input_path):
    if ensure(project)["field_test_reporting"] is not True:
        raise ValueError("field-test reporting is disabled for this project; opt in during install")
    return _record_report_payload(project, _read_report(input_path))

def _record_report_payload(project, payload, require_active=False):
    ensured = ensure(project)
    binding = load_json(resolve(project, config()["binding_file"]))
    if binding.get("field_test_reporting") is not True:
        raise ValueError("field-test reporting is disabled for this project; opt in during install")
    cfg = config()
    report_path = resolve(project, cfg["field_report_file"])
    ledger = load_json(report_path)
    binding = load_json(resolve(project, cfg["binding_file"]))
    active = binding.get("active_workflow")
    for previous in ledger["reports"]:
        if _same_report_identity(previous, payload, ledger["epoch"]):
            if _completion_payload_sha256(previous) != _completion_payload_sha256(payload):
                raise ValueError("conflicting retry for workflow report identity")
            _reconcile_completion(project, previous)
            return {"sequence": previous["sequence"], "report_count": len(ledger["reports"]), "idempotent": True, "event_id": previous["event_id"]}
    if require_active:
        previous = _checkpoint_retry(binding, payload)
        if previous:
            return {"sequence": previous["sequence"], "event_id": previous["event_id"], "idempotent": True, "field_test_reporting": True}
    previous = (active or {}).get("outcome_receipts", {}).get(_receipt_key(payload))
    if previous:
        if previous["payload_sha256"] != _completion_payload_sha256(payload):
            raise ValueError("conflicting retry for workflow report identity")
        return {"event_id": previous["event_id"], "idempotent": True, "field_test_reporting": True}
    if active:
        _check_workflow_change(active, payload)
        if payload["status"] != "complete" and len(active.get("outcome_receipts", {})) >= int(cfg["max_reports"]):
            raise ValueError("workflow checkpoint receipts full; finish or explicitly split the scoped workflow")
    elif require_active or "checkpoint_id" in payload:
        raise ValueError("completion does not match an active workflow")
    if payload.get("current_state", binding.get("current_state")) is not None:
        _verify_current_state(project, payload.get("current_state", binding.get("current_state")))
    parent = binding.get("latest_change", {}).get("event_id")
    if parent and payload["change"].get("parent_event_id") != parent:
        raise ValueError("completion must reference the latest completed event")
    if len(ledger["reports"]) >= int(cfg["max_reports"]):
        raise ValueError("field report ledger is full; export and purge it before recording more reports")
    event_id = _event_id(ledger["epoch"], payload, ledger["reports"] + [
        binding.get("latest_change"), binding.get("previous_change")])
    entry = dict(payload)
    if active:
        entry["start_change"] = active["change"]
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
    validate_report(entry)
    ledger["runtime_version"] = index()["version"]
    ledger["reports"].append(entry)
    write_json_atomic(report_path, ledger)
    _reconcile_completion(project, entry)
    return {"sequence": entry["sequence"], "report_count": len(ledger["reports"]), "path": str(report_path), "binding": ensured["binding"]}

@serialized
def finish_workflow(project, input_path):
    payload = _read_report(input_path)
    result = _finish_workflow_payload(project, payload)
    binding_path = resolve(project, config()["binding_file"])
    binding = load_json(binding_path)
    if not binding.get("git_checkpoint", {}).get("enabled"):
        return result
    event_id = result.get("event_id")
    if not event_id:
        active = binding.get("active_workflow", {})
        receipt = active.get("outcome_receipts", {}).get(_receipt_key(payload), {})
        event_id = receipt.get("event_id")
        if not event_id:
            for entry in [binding.get("latest_change", {}), binding.get("previous_change", {})]:
                if isinstance(entry, dict) and _same_report_identity(entry, payload, entry.get("epoch", 0)):
                    event_id = entry.get("event_id")
                    break
    if not event_id:
        raise ValueError("finished outcome lacks its durable Git stage identity")
    from git_checkpoint import run_checkpoint
    git_result = run_checkpoint(project_root(project), binding, payload, event_id,
                                lambda value: write_json_atomic(binding_path, value))
    return dict(result, git_checkpoint=git_result)

def _finish_workflow_payload(project, payload):
    ensured = ensure(project)
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    binding = load_json(binding_path)
    if binding.get("field_test_reporting") is True:
        return _record_report_payload(project, payload, require_active=True)
    active = binding.get("active_workflow")
    latest = binding.get("latest_change", {})
    if not isinstance(latest, dict):
        raise ValueError("latest completion state is invalid; reconcile preserved project state before finishing")
    workflow_id = payload["workflow_id"]
    event_id = _event_id(latest.get("epoch", 0), payload, [latest, binding.get("previous_change")])
    payload_sha256 = _completion_payload_sha256(payload)

    previous = _checkpoint_retry(binding, payload)
    if previous:
        return {"sequence": previous["sequence"], "event_id": previous["event_id"], "idempotent": True, "field_test_reporting": False}
    if not isinstance(active, dict) or active.get("workflow_id") != workflow_id:
        raise ValueError("completion does not match an active workflow")
    _check_workflow_change(active, payload)
    previous = active.get("outcome_receipts", {}).get(_receipt_key(payload))
    if previous:
        if previous["payload_sha256"] != payload_sha256:
            raise ValueError("conflicting retry for workflow report identity")
        return {"status": payload["status"], "completed": False, "idempotent": True, "active_workflow": active, "field_test_reporting": False}
    parent = latest.get("event_id") if isinstance(latest, dict) else None
    if parent and payload["change"].get("parent_event_id") != parent:
        raise ValueError("completion must reference the latest completed event")
    if payload.get("current_state", binding.get("current_state")) is not None:
        _verify_current_state(project, payload.get("current_state", binding.get("current_state")))
    sequences = [latest.get("sequence", 0), active.get("last_outcome", {}).get("sequence", 0)]
    if any(type(n) is not int or n < 0 for n in sequences):
        raise ValueError("latest completion sequence/epoch is invalid; reconcile preserved project state before finishing")
    sequence = max(sequences) + 1
    epoch = latest.get("epoch", 0) if isinstance(latest, dict) else 0
    if type(sequence) is not int or sequence < 1 or type(epoch) is not int or epoch < 0:
        raise ValueError("latest completion sequence/epoch is invalid; reconcile preserved project state before finishing")
    entry = dict(payload)
    entry["start_change"] = active["change"]
    entry["schema_version"] = 1
    entry["sequence"] = sequence
    entry["epoch"] = epoch
    entry["event_id"] = event_id
    entry["recorded_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    previous_time = active.get("last_outcome", {}).get("recorded_at") or latest.get("recorded_at")
    if previous_time and datetime.fromisoformat(entry["recorded_at"].replace("Z", "+00:00")) < datetime.fromisoformat(previous_time.replace("Z", "+00:00")):
        raise ValueError("observed clock moved backwards; reconcile clock/source before finishing")
    entry["runtime_version"] = index()["version"]
    validate_report(entry)
    _reconcile_completion(project, entry)
    if payload["status"] != "complete":
        return {"status": payload["status"], "completed": False, "active_workflow": load_json(binding_path)["active_workflow"], "field_test_reporting": False}
    return {"sequence": sequence, "event_id": event_id, "field_test_reporting": False, "binding": ensured["binding"]}

@serialized
def export_reports(project, output):
    state = status(project)
    if not state.get("ok"):
        raise ValueError("cannot export: project binding is not healthy")
    if state.get("field_test_reporting") is not True:
        raise ValueError("field-test reporting is disabled for this project; there is no ledger to export")
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
    binding_path = resolve(project, cfg["binding_file"])
    if binding_path.is_file():
        state = status(project)
        if not state.get("ok"):
            raise ValueError("cannot purge: project binding is not healthy")
        reporting = state.get("field_test_reporting") is True
    else:
        reporting = bool(cfg["field_test_reporting"])
    if not reporting:
        if report_path.is_file():
            raise ValueError("cannot purge a report ledger that is not owned by this reporting-disabled project binding")
        return {"purged": True, "path": str(report_path), "field_test_reporting": False}
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
def remove(project, yes):
    if not yes:
        raise ValueError("remove requires --yes")
    binding_path = resolve(project, config()["binding_file"])
    if binding_path.is_file():
        binding = load_json(binding_path)
        errors = validate_binding(binding)
        if errors:
            raise ValueError("refusing to remove drifted/unowned binding: " + "; ".join(errors))
        if binding.get("git_checkpoint", {}).get("journal"):
            raise ValueError("reconcile the pending Git transaction before removing its recovery state")
        watcher = binding.get("git_checkpoint", {}).get("watcher", {})
        if watcher.get("token") or watcher.get("pid") or watcher.get("desired_running"):
            import git_watch
            stopped = git_watch.stop(project)["watcher"]
            if stopped.get("status") != "stopped":
                raise ValueError("observer cancellation is pending; wait for its native command before removing state")
        with ExitStack() as ownership:
            for name in [".upg-supervisor.guard", ".upg-worker.guard", ".upg-validation.guard", ".upg-checkpoint.guard"]:
                guard = guards.acquire(project_root(project), name)
                if guard is None:
                    raise ValueError("native project work remains active; wait before removing its ownership state")
                ownership.enter_context(guard)
            return _remove_files(project, yes)
    return _remove_files(project, yes)


@serialized
def _remove_files(project, yes):
    if not yes:
        raise ValueError("remove requires --yes")
    cfg = config()
    binding_path = resolve(project, cfg["binding_file"])
    managed_paths = []
    if binding_path.exists():
        binding = load_json(binding_path)
        errors = validate_binding(binding)
        if errors:
            raise ValueError("refusing to remove drifted/unowned binding: " + "; ".join(errors))
        else:
            managed = binding.get("managed_files", [])
        watcher = binding.get("git_checkpoint", {}).get("watcher", {})
        if watcher.get("token") or watcher.get("pid") or watcher.get("desired_running"):
            raise ValueError("observer ownership changed; explicitly stop before removing state")
        if binding.get("git_checkpoint", {}).get("journal"):
            raise ValueError("reconcile the pending Git transaction before removing its recovery state")
        if binding.get("field_test_reporting") is True:
            state = status(project)
            if not state.get("ok"):
                raise ValueError("refusing to remove unhealthy field-report state")
            ledger = load_json(resolve(project, cfg["field_report_file"]))
            if ledger.get("reports"):
                raise ValueError("export and purge field-report history before removing UPG")
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
        if name in {"install", "ensure"}:
            p.add_argument("--field-test-reporting", action="store_true")
    report = sub.add_parser("report")
    report.add_argument("project", nargs="?", default=".")
    report.add_argument("--input", required=True)
    workflow = sub.add_parser("begin")
    workflow.add_argument("project", nargs="?", default=".")
    workflow.add_argument("--input", required=True)
    finish = sub.add_parser("finish")
    finish.add_argument("project", nargs="?", default=".")
    finish.add_argument("--input", required=True)
    git_policy = sub.add_parser("git-configure")
    git_policy.add_argument("project", nargs="?", default=".")
    mode = git_policy.add_mutually_exclusive_group(required=True)
    mode.add_argument("--enable", action="store_true")
    mode.add_argument("--disable", action="store_true")
    git_policy.add_argument("--allow-path", action="append")
    git_policy.add_argument("--status-path", action="append")
    git_policy.add_argument("--min-interval-seconds", type=int)
    bootstrap_mode = git_policy.add_mutually_exclusive_group()
    bootstrap_mode.add_argument("--bootstrap", dest="bootstrap_enabled", action="store_true")
    bootstrap_mode.add_argument("--no-bootstrap", dest="bootstrap_enabled", action="store_false")
    git_policy.set_defaults(bootstrap_enabled=None)
    watch = sub.add_parser("git-watch")
    watch.add_argument("project", nargs="?", default=".")
    watch.add_argument("--action", choices=["configure", "start", "stop", "status", "tick", "recover"], required=True)
    watch.add_argument("--input")
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
            result = ensure(
                args.project,
                field_test_reporting=True if args.field_test_reporting else None,
            )
        elif args.cmd == "status":
            result = status(args.project)
            if not result.get("ok"):
                print(json.dumps(result, indent=2, sort_keys=True))
                return 1
        elif args.cmd == "report":
            result = record_report(args.project, args.input)
        elif args.cmd == "begin":
            result = begin_workflow(args.project, args.input)
        elif args.cmd == "finish":
            result = finish_workflow(args.project, args.input)
        elif args.cmd == "git-configure":
            result = configure_git(args.project, args.enable, args.allow_path,
                                   args.status_path, args.min_interval_seconds, args.bootstrap_enabled)
        elif args.cmd == "git-watch":
            import git_watch
            if args.action == "configure":
                if not args.input:
                    raise ValueError("git-watch configure requires --input")
                result = git_watch.configure(args.project, load_json(args.input))
            else:
                if args.input:
                    raise ValueError("--input is only accepted for git-watch configure")
                result = getattr(git_watch, args.action)(args.project)
        elif args.cmd == "export":
            result = export_reports(args.project, args.output)
        elif args.cmd == "purge-reports":
            result = purge_reports(args.project, args.yes)
        elif args.cmd == "remove":
            result = remove(args.project, args.yes)
        if args.cmd in {"install", "ensure", "git-configure"}:
            # The ordinary activation entry can restore a configured observer,
            # without requiring the host to adopt begin/finish. Explicit stop
            # remains a durable choice until an explicit start.
            binding = load_json(resolve(args.project, config()["binding_file"]))
            watcher = binding.get("git_checkpoint", {}).get("watcher", {})
            if (binding.get("git_checkpoint", {}).get("enabled")
                    and watcher.get("configuration", {}).get("enabled")
                    and watcher.get("supervisor", {}).get("enabled")):
                import git_watch
                result["watcher"] = git_watch.autostart(args.project)["watcher"]
        print(json.dumps(result, indent=2, sort_keys=True))
        if (result.get("watcher", {}).get("status") in {"blocked", "stale", "cancelled"}
                or result.get("watcher", {}).get("supervisor", {}).get("status") == "blocked"):
            return 1
        if result.get("git_checkpoint", {}).get("status") == "blocked":
            return 1
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
