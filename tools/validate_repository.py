#!/usr/bin/env python3
"""Validate repository-level release structure and single-source-of-truth invariants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

SKILL_NAME = "universal-project-governance"
REQUIRED_ROOT = {
    "README.md", "AGENTS.md", "PROJECT_STATE.md", "MODULE_MAP.md", "DECISIONS.md",
    "CHANGELOG.md", "PUBLISHING.md", "SECURITY.md", "CONTRIBUTING.md", "LICENSE",
    ".gitignore", ".github/workflows/validate.yml", "evals/evals.json", "evals/trigger_set.json",
}


def skill_version(skill_md: Path):
    text = skill_md.read_text(encoding="utf-8")
    m = re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)["\']?\s*$', text, re.M)
    return m.group(1).strip() if m else None


def first_changelog_version(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^##\s+([^\s—]+)", line)
        if m:
            return m.group(1)
    return None


def validate_evals(path: Path, version: str, errors: list) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid evals JSON: {exc}")
        return
    if data.get("skill_name") != SKILL_NAME:
        errors.append("evals/evals.json skill_name mismatch")
    cases = data.get("evals")
    if not isinstance(cases, list) or len(cases) < 10:
        errors.append("evals/evals.json needs at least 10 behavior cases")
        return
    seen = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"behavior eval {i} is not an object")
            continue
        cid = case.get("id")
        if cid in seen:
            errors.append(f"duplicate behavior eval id {cid!r}")
        seen.add(cid)
        for key in ("id", "prompt", "expected_output", "assertions"):
            if key not in case:
                errors.append(f"behavior eval {i} missing {key}")
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions or any(not isinstance(x, str) or not x.strip() for x in assertions):
            errors.append(f"behavior eval {i} has invalid assertions")


def validate_triggers(path: Path, errors: list) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid trigger-set JSON: {exc}")
        return
    if not isinstance(data, list) or len(data) < 20:
        errors.append("trigger_set must contain at least 20 queries")
        return
    pos = neg = 0
    seen = set()
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"trigger item {i} is not an object")
            continue
        q = item.get("query")
        flag = item.get("should_trigger")
        if not isinstance(q, str) or not q.strip():
            errors.append(f"trigger item {i} query invalid")
        elif q in seen:
            errors.append(f"trigger item {i} duplicates a query")
        else:
            seen.add(q)
        if not isinstance(flag, bool):
            errors.append(f"trigger item {i} should_trigger must be boolean")
        elif flag:
            pos += 1
        else:
            neg += 1
    if pos < 10 or neg < 10:
        errors.append(f"trigger balance too weak: positive={pos}, negative={neg}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    errors = []

    for rel in REQUIRED_ROOT:
        if not (root / rel).exists():
            errors.append(f"missing repository file: {rel}")

    skills = [p for p in root.rglob("SKILL.md") if ".git" not in p.parts and "dist" not in p.parts]
    if len(skills) != 1:
        errors.append(f"repository must contain exactly one source SKILL.md; found {len(skills)}")
        version = None
    else:
        if skills[0].parent.name != SKILL_NAME:
            errors.append(f"Skill directory must be {SKILL_NAME}")
        version = skill_version(skills[0])
        if not version:
            errors.append("Skill metadata.version missing")

    if (root / "LICENSE").exists() and (root / SKILL_NAME / "LICENSE").exists():
        if (root / "LICENSE").read_bytes() != (root / SKILL_NAME / "LICENSE").read_bytes():
            errors.append("repository LICENSE and distributed Skill LICENSE differ")

    if version:
        changelog = first_changelog_version(root / "CHANGELOG.md") if (root / "CHANGELOG.md").exists() else None
        if changelog != version:
            errors.append(f"CHANGELOG latest version {changelog!r} != Skill version {version!r}")
        readme = (root / "README.md").read_text(encoding="utf-8", errors="replace") if (root / "README.md").exists() else ""
        if version not in readme:
            errors.append("README does not mention current Skill version")

    if (root / "evals/evals.json").exists():
        validate_evals(root / "evals/evals.json", version or "", errors)
    if (root / "evals/trigger_set.json").exists():
        validate_triggers(root / "evals/trigger_set.json", errors)

    forbidden_dirs = {"__pycache__", ".venv", "dist", "build", "eval-workspaces", ".pytest_cache"}
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if any(part in forbidden_dirs for part in rel.parts):
            errors.append(f"generated/local artifact tracked in source tree: {rel}")
        if p.is_file() and (p.suffix in {".pyc", ".pyo", ".zip"} or p.name == ".DS_Store"):
            errors.append(f"generated/local file tracked in source tree: {rel}")

    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"Repository check passed: {SKILL_NAME} {version} ({len(skills)} Skill, release/eval/license invariants satisfied).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
