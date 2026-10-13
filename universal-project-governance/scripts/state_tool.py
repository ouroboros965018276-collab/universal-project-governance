#!/usr/bin/env python3
"""Validate, render, compact, and export schema-first governance state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import re
import math
import hashlib
from pathlib import PurePosixPath, PureWindowsPath
from datetime import datetime


def load(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(value): raise ValueError("nonfinite JSON constant: " + value)
    def finite(value):
        number = float(value)
        if not math.isfinite(number): raise ValueError("nonfinite JSON number")
        return number
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant, parse_float=finite)
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds bounded parser depth") from error


def schema_root() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas"


def validate_node(value, schema, where="$"):
    errors = []
    if "const" in schema and (value != schema["const"] or isinstance(value, bool) != isinstance(schema["const"], bool)):
        errors.append("%s must equal %r" % (where, schema["const"]))
    typ = schema.get("type")
    if isinstance(typ, list):
        alternatives = [validate_node(value, dict(schema, type=t), where) for t in typ]
        return [] if any(not e for e in alternatives) else ["%s has no permitted type" % where]
    if typ == "null":
        return errors if value is None else ["%s must be null" % where]
    if typ == "object":
        if not isinstance(value, dict):
            return ["%s must be object" % where]
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(schema.get("properties", {}))
            for key in sorted(unknown):
                errors.append("%s has unknown property %s" % (where, key))
        for req in schema.get("required", []):
            if req not in value:
                errors.append("%s missing required property %s" % (where, req))
        for key, subschema in schema.get("properties", {}).items():
            if key in value:
                errors += validate_node(value[key], subschema, "%s.%s" % (where, key))
    elif typ == "array":
        if not isinstance(value, list):
            return ["%s must be array" % where]
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                errors += validate_node(item, item_schema, "%s[%d]" % (where, i))
    elif typ == "string":
        if not isinstance(value, str):
            errors.append("%s must be string" % where)
        else:
            if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
                errors.append("%s string length out of bounds" % where)
            if "pattern" in schema and re.search(schema["pattern"], value) is None:
                errors.append("%s pattern mismatch" % where)
            if schema.get("format") == "date-time":
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
                        raise ValueError("RFC3339 timezone required")
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    errors.append("%s must be RFC3339 date-time" % where)
    elif typ == "boolean":
        if not isinstance(value, bool):
            errors.append("%s must be boolean" % where)
    elif typ == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append("%s must be integer" % where)
    elif typ == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append("%s must be number" % where)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            errors.append("%s must be finite" % where)
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            errors.append("%s number out of bounds" % where)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            errors.append("%s array length out of bounds" % where)
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            errors.append("%s duplicate items" % where)
    if "enum" in schema and not any(value == item and isinstance(value, bool) == isinstance(item, bool) for item in schema["enum"]):
        errors.append("%s must be one of %r" % (where, schema["enum"]))
    return errors


def validation_run_errors(runs) -> list:
    schema = load(schema_root() / "execution.schema.json")["properties"]["validation_runs"]
    errors = validate_node(runs, schema, "$.validation_runs")
    if errors:
        return errors
    seen = set()
    for run in runs:
        if run["run_id"] in seen:
            errors.append("duplicate validation run_id: %s" % run["run_id"])
        seen.add(run["run_id"])
        passed, total = run.get("passed"), run.get("total")
        if passed is not None and (total is None or passed > total):
            errors.append("validation run %s needs a denominator at least as large as passed" % run["run_id"])
        if run["result"] == "passed" and passed is not None and passed != total:
            errors.append("validation run %s cannot pass with incomplete passing count" % run["run_id"])
    return errors


def reference_path(ref, project_root: Path) -> Path:
    if project_root is None:
        raise ValueError("validation_ref requires --project-root")
    relative = ref["path"]
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    if posix.is_absolute() or windows.drive or windows.root or "\\" in relative or ":" in relative or any(p in {"..", ".", ""} for p in relative.split("/")):
        raise ValueError("validation_ref.path must be a project-relative path without traversal")
    from project_facts import safe_path
    root = Path(project_root).absolute()
    target = safe_path(root, relative)
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("validation_ref.path escapes project root")
    if not target.is_file():
        raise ValueError("validation_ref file unavailable: %s" % relative)
    # Keep reference identity canonical after rejecting unsafe paths. Windows
    # short/long ancestors and lexical '..' aliases can otherwise make compact
    # mistake its own referenced execution file for an unreferenced file.
    return target.resolve(strict=True)


def resolve_validation_ref(ref, project_root: Path, source_bytes=None) -> dict:
    schema = load(schema_root() / "handoff.schema.json")["properties"]["validation_ref"]
    errors = validate_node(ref, schema, "$.validation_ref")
    if errors:
        raise ValueError("; ".join(errors))
    target = reference_path(ref, project_root)
    if source_bytes is None:
        with target.open("rb") as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
    else:
        if not isinstance(source_bytes, bytes): raise ValueError("validation source bytes must be immutable bytes")
        raw = source_bytes
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError("validation_ref source exceeds the 4 MiB read limit")
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("stale validation_ref: source SHA-256 changed; reconcile from canonical truth")
    from project_facts import strict_json
    source = strict_json(raw)
    if "pointer" in ref:
        run = source
        pointer = ref["pointer"]
        if pointer:
            for token in pointer[1:].split("/"):
                if re.search(r"~(?![01])", token):
                    raise ValueError("malformed validation_ref JSON pointer escape")
                token = token.replace("~1", "/").replace("~0", "~")
                if isinstance(run, dict) and token in run:
                    run = run[token]
                elif isinstance(run, list) and re.fullmatch(r"0|[1-9][0-9]*", token) and int(token) < len(run):
                    run = run[int(token)]
                else:
                    raise ValueError("validation_ref pointer unavailable")
        runs = [run]
    else:
        runs = source.get("validation_runs") if isinstance(source, dict) else None
    errors = validation_run_errors(runs)
    if errors:
        raise ValueError("unsupported canonical validation record: " + "; ".join(errors))
    matches = [run for run in runs if run["run_id"] == ref["run_id"]]
    if len(matches) != 1:
        raise ValueError("stale validation_ref: run_id unavailable or ambiguous")
    return matches[0]


def validate_file(path: Path, schema_name: str, project_root: Path = None) -> list:
    schema = load(schema_root() / (schema_name + ".schema.json"))
    data = load(path)
    errors = validate_node(data, schema)
    if not errors and "validation_runs" in data:
        errors += validation_run_errors(data["validation_runs"])
    if not errors and "recovery" in data:
        from project_facts import recovery_errors
        errors += recovery_errors(data["recovery"])
    if not errors and "validation_ref" in data:
        try:
            resolve_validation_ref(data["validation_ref"], project_root)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def bullet_list(title, values):
    lines = ["## " + title, ""]
    if values:
        lines += ["- " + str(x) for x in values]
    else:
        lines.append("- None.")
    lines.append("")
    return lines


def render_validation_runs(runs, current_revision=None):
    lines = ["## Canonical validation runs", "", "Each result applies to its stated scope and tested revision; scopes are not added together.", ""]
    for run in runs:
        pending = run.get("pending_retest", False) or bool(run.get("later_changes")) or (current_revision is not None and current_revision != run["tested_revision"])
        counts = "%s/%s passed" % (run.get("passed", "unknown"), run.get("total", "unknown"))
        counts = counts.replace("None", "unknown")
        lines += ["- **Run:** %s; **Scope:** %s; **Historical result:** %s; **Count:** %s; **Tested revision:** %s; **Retest:** %s." % (run["run_id"], run["scope"], run["result"], counts, run["tested_revision"], "pending" if pending else "not marked pending")]
        if current_revision is not None:
            lines.append("  - Current revision supplied: %s." % current_revision)
        for change in run.get("later_changes", []):
            lines.append("  - Later change: %s" % change)
    return lines + [""]


def render(path: Path, schema_name: str, project_root: Path = None, current_revision=None) -> str:
    data = load(path)
    if schema_name == "handoff":
        lines = ["# Project Handoff", "", "- **Updated:** %s" % data["updated_at"], "- **Goal:** %s" % data["goal"], "- **Status:** %s" % data["status"], ""]
        for key, title in [
            ("completed", "Completed"), ("in_progress", "In progress"), ("decisions", "Important decisions"),
            ("invariants", "Invariants"), ("risks", "Risks / gaps"), ("next_actions", "Next actions"),
            ("validation", "Validation"), ("canonical_sources", "Canonical sources"),
        ]:
            if key == "validation" and "validation_ref" in data:
                title = "Legacy validation notes (canonical results below)"
            lines += bullet_list(title, data[key])
        if "validation_ref" in data:
            run = resolve_validation_ref(data["validation_ref"], project_root)
            lines += ["Canonical reference: %s (run %s)." % (data["validation_ref"]["path"], data["validation_ref"]["run_id"]), ""]
            lines += render_validation_runs([run], current_revision)
        if "recovery" in data:
            recovered = data["recovery"]
            lines += ["## Project fact recovery", "", "Read-only observations and reference fixity do not establish semantic truth or completion.", "",
                      "- Scoped files: %d; carried references: %d; unresolved gaps: %d." %
                      (len(recovered["scope"]), len(recovered["carry_forward_refs"]), len(recovered["gaps"]))]
            lines += bullet_list("Decision delta", recovered["decision_delta"])
            lines += bullet_list("Recovery gaps", recovered["gaps"])
        return "\n".join(lines).rstrip() + "\n"
    if schema_name == "execution":
        lines = ["# Engineering Execution Evidence", "", "- **Updated:** %s" % data["updated_at"], "- **Level:** %s" % data["level"], "- **Task:** %s" % data["task"], "- **Status:** %s" % data["status"], ""]
        for key, title in [("actions","Actions"),("cleanup","Cleanup"),("validation","Validation"),("findings","Findings"),("governance_feedback","Governance feedback")]:
            if key == "validation" and "validation_runs" in data:
                title = "Legacy validation notes (canonical results below)"
            lines += bullet_list(title, data[key])
        if "validation_runs" in data:
            errors = validation_run_errors(data["validation_runs"])
            if errors:
                raise ValueError("; ".join(errors))
            lines += render_validation_runs(data["validation_runs"], current_revision)
        return "\n".join(lines).rstrip() + "\n"
    if schema_name == "feedback":
        lines = ["# Governance Feedback", "", "- **Updated:** %s" % data["updated_at"], ""]
        for item in data["items"]:
            lines += ["## %s" % item["id"], "", "- **Status:** %s" % item["status"], "- **Scope:** %s" % item["scope"], "- **Observation:** %s" % item["observation"], "- **Consequence:** %s" % item["consequence"], "", "### Evidence", ""]
            lines += ["- " + x for x in item["evidence"]] or ["- None."]
            if item.get("proposed_improvement"):
                lines += ["", "### Proposed improvement", "", item["proposed_improvement"]]
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
    if schema_name == "audit":
        lines = ["# Release Audit", "", "- **Created:** %s" % data["created_at"], "- **Version:** %s" % data["version"], "- **Candidate:** %s" % data["candidate"], "- **Artifact SHA-256:** %s" % data["artifact_sha256"], "", "## Gates", ""]
        for gate in data["gates"]:
            lines.append("- **%s:** %s%s" % (gate["name"], gate["result"], (" — " + gate.get("evidence","")) if gate.get("evidence") else ""))
        lines += ["", "## Blockers", ""]
        lines += ["- " + x for x in data["blockers"]] or ["- None."]
        return "\n".join(lines).rstrip() + "\n"
    raise ValueError("unsupported schema renderer: %s" % schema_name)


def infer_schema(path: Path) -> str:
    name = path.name.lower()
    if "handoff" in name:
        return "handoff"
    if "feedback" in name or name == "open.json":
        return "feedback"
    if "audit" in name:
        return "audit"
    if "execution" in str(path).lower() or name == "latest.json":
        return "execution"
    raise ValueError("cannot infer schema; pass --schema")


def compact(root: Path, apply: bool, close_handoff: bool) -> list:
    gov = root / ".governance"
    actions = []
    handoff = gov / "handoff.json"
    referenced = None
    if handoff.is_file():
        ref = load(handoff).get("validation_ref")
        if ref is not None:
            resolve_validation_ref(ref, root)
            referenced = reference_path(ref, root)
    execution = gov / "execution" / "latest.json"
    if execution.is_file():
        data = load(execution)
        if execution.resolve() != referenced and data.get("status") == "complete" and data.get("durable_summary_recorded") and not data.get("retain_for_audit"):
            actions.append("remove completed execution/latest.json after durable reconciliation")
            if apply:
                execution.unlink()
    feedback = gov / "feedback" / "open.json"
    if feedback.is_file():
        data = load(feedback)
        open_items = [x for x in data.get("items", []) if x.get("status") == "open"]
        if len(open_items) != len(data.get("items", [])):
            actions.append("drop resolved feedback items from open.json")
            if apply:
                if open_items:
                    data["items"] = open_items
                    feedback.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                else:
                    feedback.unlink()
    if close_handoff and handoff.is_file():
        data = load(handoff)
        if data.get("status") == "ready" and not data.get("in_progress") and not data.get("next_actions"):
            actions.append("remove closed current handoff")
            if apply:
                handoff.unlink()
    return actions


def export_bundle(root: Path, output: Path) -> None:
    gov = root / ".governance"
    selected = []
    for rel in ["handoff.json", "execution/latest.json", "feedback/open.json"]:
        p = gov / rel
        if p.is_file():
            selected.append((rel, load(p)))
    audits = gov / "audits"
    if audits.is_dir():
        for p in sorted(audits.glob("*.json")):
            selected.append(("audits/" + p.name, load(p)))
    payload = {"schema_version": 1, "files": [{"path": rel, "content": data} for rel, data in selected]}
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("path"); v.add_argument("--schema"); v.add_argument("--project-root")
    r = sub.add_parser("render"); r.add_argument("path"); r.add_argument("--schema"); r.add_argument("--output"); r.add_argument("--project-root"); r.add_argument("--current-revision")
    c = sub.add_parser("compact"); c.add_argument("root", nargs="?", default="."); c.add_argument("--apply", action="store_true"); c.add_argument("--close-handoff", action="store_true")
    e = sub.add_parser("export"); e.add_argument("root", nargs="?", default="."); e.add_argument("--output", required=True)
    f = sub.add_parser("recover", help="read-only task-scoped project fact recovery")
    f.add_argument("root"); f.add_argument("--scope", action="append", required=True)
    f.add_argument("--handoff"); f.add_argument("--git-binary")
    args = ap.parse_args()
    try:
        if args.cmd in {"validate","render"}:
            path = Path(args.path)
            schema_name = args.schema or infer_schema(path)
            errors = validate_file(path, schema_name, Path(args.project_root) if args.project_root else None)
            if errors:
                for err in errors: print("error: " + err, file=sys.stderr)
                return 1
            if args.cmd == "validate":
                print("Governance state validation passed: %s" % schema_name)
            else:
                text_out = render(path, schema_name, Path(args.project_root) if args.project_root else None, args.current_revision)
                if args.output:
                    Path(args.output).write_text(text_out, encoding="utf-8")
                else:
                    sys.stdout.write(text_out)
        elif args.cmd == "compact":
            actions = compact(Path(args.root).resolve(), args.apply, args.close_handoff)
            if actions:
                for action in actions: print(action)
            else:
                print("No governance compaction actions needed.")
        elif args.cmd == "export":
            export_bundle(Path(args.root).resolve(), Path(args.output))
            print("Evidence bundle written: %s" % args.output)
        elif args.cmd == "recover":
            from project_facts import recover
            print(json.dumps(recover(args.root, args.scope, handoff=args.handoff, git_binary=args.git_binary),
                             ensure_ascii=True, allow_nan=False, separators=(",", ":")))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
