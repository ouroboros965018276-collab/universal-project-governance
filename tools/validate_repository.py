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
REQUIRED_RC3_SKILL = {
    "SKILL.md", "INTEGRITY.md", "VERSION.md", "CHANGELOG.md", "LICENSE",
    "integrity/protected-files.json", "integrity/skill-manifest.json", "integrity/checksums.json",
    "references/report-lifecycle-policy.md", "references/feedback-loop.md", "references/version-policy.md",
    "assets/templates/HANDOFF.md", "assets/templates/AGENT_EXECUTION_AUDIT.md",
    "assets/templates/CHANGE_NOTE.md", "assets/templates/ENGINEERING_REPORT.md",
    "assets/templates/GOVERNANCE_FEEDBACK.md", "assets/governance-config.example.json",
    "scripts/validate_integrity.py", "scripts/refresh_integrity.py", "scripts/classify_report.py",
    "scripts/validate_handoff.py", "scripts/validate_reports.py", "scripts/export_evidence_bundle.py",
    "scripts/governance_check.py",
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


def load_json(path: Path, errors: list):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return {}


def validate_evals(path: Path, errors: list) -> None:
    data = load_json(path, errors)
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
        if not isinstance(assertions, list) or not assertions or any(
            not isinstance(x, str) or not x.strip() for x in assertions
        ):
            errors.append(f"behavior eval {i} has invalid assertions")


def validate_triggers(path: Path, errors: list) -> None:
    data = load_json(path, errors)
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

    for misplaced in ("integrity", "references"):
        if (root / misplaced).exists():
            errors.append(f"misplaced repository-root Skill content: {misplaced}/ (must live under {SKILL_NAME}/)")

    skills = [p for p in root.rglob("SKILL.md") if ".git" not in p.parts and "dist" not in p.parts]
    version = None
    skill_root = root / SKILL_NAME
    if len(skills) != 1:
        errors.append(f"repository must contain exactly one source SKILL.md; found {len(skills)}")
    else:
        if skills[0].parent != skill_root:
            errors.append(f"Skill directory must be {SKILL_NAME}")
        version = skill_version(skills[0])
        if not version:
            errors.append("Skill metadata.version missing")

    for rel in REQUIRED_RC3_SKILL:
        if not (skill_root / rel).is_file():
            errors.append(f"missing RC3 distributed Skill file: {rel}")

    if (root / "LICENSE").exists() and (skill_root / "LICENSE").exists():
        if (root / "LICENSE").read_bytes() != (skill_root / "LICENSE").read_bytes():
            errors.append("repository LICENSE and distributed Skill LICENSE differ")

    if version:
        root_changelog = first_changelog_version(root / "CHANGELOG.md")
        skill_changelog = first_changelog_version(skill_root / "CHANGELOG.md")
        if root_changelog != version:
            errors.append(f"root CHANGELOG latest version {root_changelog!r} != Skill version {version!r}")
        if skill_changelog != version:
            errors.append(f"Skill CHANGELOG latest version {skill_changelog!r} != Skill version {version!r}")
        readme = (root / "README.md").read_text(encoding="utf-8", errors="replace")
        if version not in readme:
            errors.append("README does not mention current Skill version")

        manifest = load_json(skill_root / "integrity" / "skill-manifest.json", errors)
        if manifest.get("expected_version") != version:
            errors.append("integrity skill-manifest expected_version mismatch")
        if manifest.get("name") != SKILL_NAME:
            errors.append("integrity skill-manifest name mismatch")

        ledger = load_json(skill_root / "integrity" / "checksums.json", errors)
        if ledger.get("generated_for_version") != version:
            errors.append("integrity checksum ledger version mismatch")
        if not isinstance(ledger.get("files"), dict) or not ledger.get("files"):
            errors.append("integrity checksum ledger must contain protected file hashes")

        policy = load_json(skill_root / "integrity" / "protected-files.json", errors)
        if policy.get("policy") != "protect-all":
            errors.append("integrity policy must remain protect-all")
        if "integrity/checksums.json" not in set(policy.get("exclude", [])):
            errors.append("integrity policy must exclude only its generated checksum ledger from self-hashing")

    if (root / "evals/evals.json").exists():
        validate_evals(root / "evals/evals.json", errors)
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
    print(
        f"Repository check passed: {SKILL_NAME} {version} "
        f"({len(skills)} Skill, RC3 integrity/release/eval/license invariants satisfied)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
