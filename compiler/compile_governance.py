#!/usr/bin/env python3
"""Compile canonical governance source into the bounded installable runtime."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import tempfile

RUNTIME_SCHEMA_NAMES = [
    "task-context.schema.json", "governance-plan.schema.json", "handoff.schema.json",
    "execution.schema.json", "feedback.schema.json", "audit.schema.json",
    "field-report.schema.json",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_digest(src: Path) -> str:
    h = hashlib.sha256()
    for p in sorted((x for x in src.rglob("*") if x.is_file() and "__pycache__" not in x.parts and x.suffix not in {".pyc", ".pyo"}), key=lambda p: p.relative_to(src).as_posix()):
        rel = str(p.relative_to(src)).replace("\\", "/")
        h.update(rel.encode("utf-8") + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def execution_guidance(model: dict) -> list:
    """Validate optional canonical guidance before either generated surface."""
    groups = model.get("execution_guidance", [])
    if not isinstance(groups, list):
        raise ValueError("execution_guidance must be a list")
    policy_ids = {policy["id"] for policy in model["policies"]}
    seen = set()
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"id", "policy_ids", "statement"}:
            raise ValueError("guidance requires id, policy_ids and statement")
        identity, targets, statement = group["id"], group["policy_ids"], group["statement"]
        if (not isinstance(identity, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", identity) is None
                or identity in seen):
            raise ValueError("guidance IDs must be unique stable identifiers")
        if (not isinstance(targets, list) or not targets
                or any(not isinstance(item, str) or item not in policy_ids for item in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError("guidance must target existing policies exactly once")
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError("guidance statement must be nonempty")
        seen.add(identity)
    return groups


def operational_guidance(model: dict) -> list:
    """Validate source-derived workflow routing without adding policy nodes."""
    groups = model.get("operational_guidance", [])
    if (not isinstance(groups, list) or any(not isinstance(group, dict)
            or set(group) != {"id", "policy_ids", "on_field_reporting", "report_levels", "statement"}
            or type(group["on_field_reporting"]) is not bool
            or not isinstance(group["report_levels"], list)
            or any(not isinstance(level, str) or level not in {"none", "change-note", "engineering", "audit"}
                   for level in group["report_levels"])
            or len(set(group["report_levels"])) != len(group["report_levels"]) for group in groups)):
        raise ValueError("invalid operational_guidance")
    execution_guidance(dict(model, execution_guidance=[
        {key: group[key] for key in ("id", "policy_ids", "statement")} for group in groups]))
    return groups


def render_skill(src: Path, model: dict) -> str:
    groups = execution_guidance(model)
    operational_guidance(model)
    template = (src / "templates" / "SKILL.template.md").read_text(encoding="utf-8")
    hot = "\n".join("%d. **%s** — %s" % (i + 1, item["id"], item["statement"]) for i, item in enumerate(model["hot_path"]))
    guidance = "\n\n".join("**%s** — %s" % (item["id"], item["statement"]) for item in groups)
    return (template.replace("{{VERSION}}", model["version"]).replace("{{HOT_PATH}}", hot)
            .replace("{{EXECUTION_GUIDANCE}}", guidance))


def compile_index(src: Path, model: dict) -> dict:
    # The loaded Skill carries global guidance; plans project selected base closures.
    execution_guidance(model)
    ids = sorted(p["id"] for p in model["policies"])
    order = model.get("presentation", {}).get("policy_order", ids)
    if (not isinstance(order, list) or any(not isinstance(x, str) for x in order)
            or len(order) != len(ids) or sorted(order) != ids):
        raise ValueError("presentation policy_order must include every policy exactly once")
    profiles = {}
    for path in sorted((src / "profiles").glob("*.json")):
        item = read_json(path)
        profiles[item["id"]] = item
    task_schema = read_json(src / "schemas" / "task-context.schema.json")
    policies = copy.deepcopy(model["policies"])
    result = {
        "schema_version": 1,
        "name": model["name"],
        "version": model["version"],
        "architecture": model["architecture"],
        "source_sha256": source_digest(src),
        "hot_path": model["hot_path"],
        "risk_model": model["risk_model"],
        "structural_integration": model["structural_integration"],
        "project_binding": model["project_binding"],
        "default_rules": model["default_rules"],
        "policies": policies,
        "presentation": {"policy_order": order},
        "profiles": profiles,
        "complexity_budget": model["complexity_budget"],
        "task_contract": {
            "operations": task_schema["properties"]["operation"]["enum"],
            "domains": task_schema["properties"]["domains"]["items"]["enum"],
        },
    }

    if "operational_guidance" in model:
        result["operational_guidance"] = copy.deepcopy(operational_guidance(model))
    return result


def write_text(path: Path, text_value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text_value.encode("utf-8"))


def compile_runtime(repo: Path, output: Path):
    src = repo / "governance-src"
    model = read_json(src / "model" / "governance-model.json")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    write_text(output / "SKILL.md", render_skill(src, model))
    write_text(output / "policy-index.json", json.dumps(compile_index(src, model), indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    write_text(output / "VERSION.md", "# Version\n\nGenerated runtime: **%s**. Canonical version source: governance-src/model/governance-model.json.\n" % model["version"])
    write_text(output / "INTEGRITY.md",
        "# Runtime Integrity\n\nThis directory is compiler-generated. Do not edit it during normal project work. "
        "Run the verified Python 3.8+ executable with scripts/validate_integrity.py . Governance upgrades change canonical governance-src, "
        "then regenerate the runtime and rerun the complete release gates. The local manifest is tamper-evident, "
        "not an authorization boundary; VCS/CI/release digests remain external trust anchors.\n"
    )
    shutil.copyfile(repo / "LICENSE", output / "LICENSE")

    for name in RUNTIME_SCHEMA_NAMES:
        dst = output / "schemas" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / "schemas" / name, dst)
    for path in sorted((src / "runtime-scripts").glob("*.py")):
        dst = output / "scripts" / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)

    files = {}
    for path in sorted(x for x in output.rglob("*") if x.is_file()):
        rel = str(path.relative_to(output)).replace("\\", "/")
        files[rel] = sha256_bytes(path.read_bytes())
    manifest = {
        "schema_version": 1,
        "algorithm": "sha256",
        "generated_for_version": model["version"],
        "source_sha256": source_digest(src),
        "files": files,
    }
    write_text(output / "integrity" / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def compare_dirs(expected: Path, actual: Path):
    def mapping(root):
        return {str(p.relative_to(root)).replace("\\","/"): p.read_bytes() for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    a, b = mapping(expected), mapping(actual)
    errors = []
    for rel in sorted(set(a) | set(b)):
        if rel not in a: errors.append("unexpected generated-runtime file: " + rel)
        elif rel not in b: errors.append("missing generated-runtime file: " + rel)
        elif a[rel] != b[rel]: errors.append("generated-runtime drift: " + rel)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--confirm-generated-runtime-update", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    runtime = repo / "universal-project-governance"
    try:
        if args.write:
            if not args.confirm_generated_runtime_update:
                print("error: --write requires --confirm-generated-runtime-update", file=sys.stderr)
                return 2
            compile_runtime(repo, runtime)
            print("Generated runtime updated.")
            return 0
        with tempfile.TemporaryDirectory() as td:
            expected = Path(td) / "universal-project-governance"
            compile_runtime(repo, expected)
            errors = compare_dirs(expected, runtime)
        if errors:
            for err in errors: print("error: " + err, file=sys.stderr)
            return 1
        print("Generated runtime check passed.")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("error: compiler failure: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
