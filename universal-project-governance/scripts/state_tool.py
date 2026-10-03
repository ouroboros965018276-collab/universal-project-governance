#!/usr/bin/env python3
"""Validate, render, compact, and export schema-first governance state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import re
import math
from datetime import datetime


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def validate_file(path: Path, schema_name: str) -> list:
    schema = load(schema_root() / (schema_name + ".schema.json"))
    data = load(path)
    return validate_node(data, schema)


def bullet_list(title, values):
    lines = ["## " + title, ""]
    if values:
        lines += ["- " + str(x) for x in values]
    else:
        lines.append("- None.")
    lines.append("")
    return lines


def render(path: Path, schema_name: str) -> str:
    data = load(path)
    if schema_name == "handoff":
        lines = ["# Project Handoff", "", "- **Updated:** %s" % data["updated_at"], "- **Goal:** %s" % data["goal"], "- **Status:** %s" % data["status"], ""]
        for key, title in [
            ("completed", "Completed"), ("in_progress", "In progress"), ("decisions", "Important decisions"),
            ("invariants", "Invariants"), ("risks", "Risks / gaps"), ("next_actions", "Next actions"),
            ("validation", "Validation"), ("canonical_sources", "Canonical sources"),
        ]:
            lines += bullet_list(title, data[key])
        return "\n".join(lines).rstrip() + "\n"
    if schema_name == "execution":
        lines = ["# Engineering Execution Evidence", "", "- **Updated:** %s" % data["updated_at"], "- **Level:** %s" % data["level"], "- **Task:** %s" % data["task"], "- **Status:** %s" % data["status"], ""]
        for key, title in [("actions","Actions"),("cleanup","Cleanup"),("validation","Validation"),("findings","Findings"),("governance_feedback","Governance feedback")]:
            lines += bullet_list(title, data[key])
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
    execution = gov / "execution" / "latest.json"
    if execution.is_file():
        data = load(execution)
        if data.get("status") == "complete" and data.get("durable_summary_recorded") and not data.get("retain_for_audit"):
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
    handoff = gov / "handoff.json"
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
    v = sub.add_parser("validate"); v.add_argument("path"); v.add_argument("--schema")
    r = sub.add_parser("render"); r.add_argument("path"); r.add_argument("--schema"); r.add_argument("--output")
    c = sub.add_parser("compact"); c.add_argument("root", nargs="?", default="."); c.add_argument("--apply", action="store_true"); c.add_argument("--close-handoff", action="store_true")
    e = sub.add_parser("export"); e.add_argument("root", nargs="?", default="."); e.add_argument("--output", required=True)
    args = ap.parse_args()
    try:
        if args.cmd in {"validate","render"}:
            path = Path(args.path)
            schema_name = args.schema or infer_schema(path)
            errors = validate_file(path, schema_name)
            if errors:
                for err in errors: print("error: " + err, file=sys.stderr)
                return 1
            if args.cmd == "validate":
                print("Governance state validation passed: %s" % schema_name)
            else:
                text_out = render(path, schema_name)
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
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
