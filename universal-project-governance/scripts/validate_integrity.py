#!/usr/bin/env python3
"""Validate tamper-evident integrity of an installed Universal Project Governance Skill."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

IGNORED_DIRS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def version_from_skill(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)["\']?\s*$', text, re.M)
    return m.group(1).strip() if m else None


def expected_files(root: Path, policy: dict) -> list[str]:
    excluded = set(policy.get("exclude", []))
    ignored_names = set(policy.get("ignore_names", [])) | IGNORED_DIRS
    ignored_suffixes = set(policy.get("ignore_suffixes", [])) | IGNORED_SUFFIXES
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in excluded:
            continue
        if any(part in ignored_names for part in p.relative_to(root).parts):
            continue
        if p.suffix in ignored_suffixes:
            continue
        out.append(rel)
    return out


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    policy_path = root / "integrity" / "protected-files.json"
    manifest_path = root / "integrity" / "skill-manifest.json"
    checksums_path = root / "integrity" / "checksums.json"
    for p in (root / "SKILL.md", policy_path, manifest_path, checksums_path):
        if not p.is_file():
            errors.append(f"missing integrity input: {p.relative_to(root) if p.is_relative_to(root) else p}")
    if errors:
        return errors

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ledger = json.loads(checksums_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid integrity metadata: {exc}"]

    version = version_from_skill(root / "SKILL.md")
    if not version:
        errors.append("SKILL.md metadata.version not found")
    if manifest.get("expected_version") != version:
        errors.append(f"manifest expected_version {manifest.get('expected_version')!r} != SKILL version {version!r}")
    if ledger.get("generated_for_version") != version:
        errors.append(f"checksum ledger version {ledger.get('generated_for_version')!r} != SKILL version {version!r}")
    if ledger.get("algorithm") != "sha256":
        errors.append("checksum ledger algorithm must be sha256")

    expected = expected_files(root, policy)
    files = ledger.get("files")
    if not isinstance(files, dict):
        errors.append("checksum ledger files must be an object")
        return errors

    expected_set = set(expected)
    ledger_set = set(files)
    missing = sorted(expected_set - ledger_set)
    extra = sorted(ledger_set - expected_set)
    if missing:
        errors.append("checksum ledger missing protected files: " + ", ".join(missing))
    if extra:
        errors.append("checksum ledger contains non-protected/stale files: " + ", ".join(extra))

    for rel in sorted(expected_set & ledger_set):
        actual = sha256(root / rel)
        if files.get(rel) != actual:
            errors.append(f"integrity mismatch: {rel}")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Universal Project Governance Skill integrity")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    errors = validate(root)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if not errors:
            print("Skill integrity check passed: protected distributed files match the SHA-256 ledger.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
