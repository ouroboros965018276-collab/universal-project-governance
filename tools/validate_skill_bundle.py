#!/usr/bin/env python3
"""Dependency-free structural checker for the installable Universal Project Governance Skill.

This complements (does not replace) the upstream Agent Skills reference validator.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")
ALLOWED_TOP = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def parse_frontmatter(text: str):
    errors = []
    if not text.startswith("---\n"):
        return {}, ["SKILL.md must start with YAML frontmatter"]
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, ["SKILL.md frontmatter is not closed"]
    lines = text[4:end].splitlines()
    data = {}
    current_map = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  "):
            if current_map != "metadata" or ":" not in raw.strip():
                errors.append(f"unsupported nested frontmatter line: {raw}")
                continue
            k, v = raw.strip().split(":", 1)
            data.setdefault("metadata", {})[k.strip()] = v.strip().strip('"\'')
            continue
        if ":" not in raw:
            errors.append(f"invalid frontmatter line: {raw}")
            continue
        k, v = raw.split(":", 1)
        k, v = k.strip(), v.strip()
        current_map = k if k == "metadata" else None
        if k == "metadata":
            data[k] = {}
        else:
            if v in {">", "|", ">-", "|-", ">+", "|+"}:
                errors.append(f"bundled checker requires single-line scalar frontmatter for {k!r}")
            data[k] = v.strip('"\'')
    return data, errors


def check_python(path: Path, errors: list) -> None:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        errors.append(f"Python syntax error in {path}: {exc}")


def validate_json_file(path: Path, errors: list) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON in {path}: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate one installable Agent Skill directory")
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    skill = root / "SKILL.md"
    errors = []
    warnings = []

    if not skill.exists():
        print("error: SKILL.md not found", file=sys.stderr)
        return 1

    all_skills = [p for p in root.rglob("*") if p.is_file() and p.name.lower() == "skill.md"]
    if len(all_skills) != 1:
        errors.append(f"single-skill bundle must contain exactly one SKILL.md; found {len(all_skills)}")

    for artifact in root.rglob("*"):
        rel = artifact.relative_to(root)
        if any(part in {"__pycache__", ".venv", "dist", "build", "eval-workspaces", ".pytest_cache"} for part in rel.parts):
            errors.append(f"generated/local artifact must not be bundled: {rel}")
        if artifact.is_file() and (artifact.suffix in {".pyc", ".pyo", ".zip"} or artifact.name == ".DS_Store"):
            errors.append(f"generated/local file must not be bundled: {rel}")

    text = skill.read_text(encoding="utf-8")
    data, fm_errors = parse_frontmatter(text)
    errors += fm_errors
    unknown = set(data) - ALLOWED_TOP
    if unknown:
        errors.append(f"unsupported top-level frontmatter fields: {sorted(unknown)}")

    name = data.get("name", "")
    desc = data.get("description", "")
    if not name or not NAME_RE.fullmatch(name):
        errors.append("name must be lowercase ASCII alphanumeric/hyphen")
    if name and name != root.name:
        errors.append(f"name {name!r} must match parent directory {root.name!r}")
    if len(name) > 64:
        errors.append("name exceeds 64 characters")
    if not desc:
        errors.append("description is required")
    if len(desc) > 1024:
        errors.append("description exceeds 1024 characters")
    compat = data.get("compatibility", "")
    if compat and len(compat) > 500:
        errors.append("compatibility exceeds 500 characters")

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()):
        errors.append("metadata must be a map of string keys to string values")
        metadata = {}
    version = metadata.get("version", "")
    if not version:
        errors.append("metadata.version is required by this repository's release policy")

    if data.get("license") == "Apache-2.0" and not (root / "LICENSE").is_file():
        errors.append("frontmatter declares Apache-2.0 but Skill LICENSE is missing")

    lines = text.splitlines()
    if len(lines) >= 500:
        warnings.append(f"SKILL.md has {len(lines)} lines; keep below 500 recommended")
    if len(text) > 24000:
        warnings.append(f"SKILL.md is {len(text)} characters; consider more progressive disclosure")

    linked_targets = set()
    for md in root.rglob("*.md"):
        mtext = md.read_text(encoding="utf-8", errors="replace")
        for target in LINK_RE.findall(mtext):
            target = target.split("#", 1)[0]
            if not target:
                continue
            p = (md.parent / target).resolve()
            try:
                p.relative_to(root)
            except ValueError:
                errors.append(f"{md.relative_to(root)} links outside bundle: {target}")
                continue
            if not p.exists():
                errors.append(f"broken local link in {md.relative_to(root)}: {target}")
            else:
                linked_targets.add(p)

    ref_dir = root / "references"
    references = sorted(ref_dir.glob("*.md")) if ref_dir.is_dir() else []
    if not references:
        errors.append("references/ must contain detailed governance references")
    for ref in references:
        if ref.resolve() not in linked_targets:
            warnings.append(f"reference file is not linked from Skill Markdown: {ref.relative_to(root)}")

    script_dir = root / "scripts"
    if not script_dir.is_dir():
        errors.append("scripts/ directory is missing")
    else:
        for py in script_dir.glob("*.py"):
            check_python(py, errors)

    asset_dir = root / "assets"
    if not asset_dir.is_dir():
        errors.append("assets/ directory is missing")
    else:
        for json_path in asset_dir.glob("*.json"):
            validate_json_file(json_path, errors)

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"Skill bundle check passed: {name} {version} ({len(lines)} SKILL.md lines, {len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
