#!/usr/bin/env python3
"""Refresh the Skill integrity ledger during an explicitly authorized governance upgrade."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def version_from_skill(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)["\']?\s*$', text, re.M)
    if not m:
        raise ValueError("SKILL.md metadata.version not found")
    return m.group(1).strip()


def files_to_hash(root: Path, policy: dict) -> list[Path]:
    excluded = set(policy.get("exclude", []))
    ignored_names = set(policy.get("ignore_names", [])) | {"__pycache__"}
    ignored_suffixes = set(policy.get("ignore_suffixes", [])) | {".pyc", ".pyo"}
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
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh protected Skill checksums")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--confirm-governance-upgrade", action="store_true")
    ap.add_argument("--stdout", action="store_true", help="Print the ledger instead of writing it")
    args = ap.parse_args()

    if not args.confirm_governance_upgrade:
        print(
            "error: refusing checksum refresh without --confirm-governance-upgrade; "
            "ordinary project tasks must not rewrite Skill integrity state",
            file=sys.stderr,
        )
        return 2

    root = Path(args.root).resolve()
    policy_path = root / "integrity" / "protected-files.json"
    if not policy_path.is_file():
        print("error: integrity/protected-files.json missing", file=sys.stderr)
        return 2

    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    version = version_from_skill(root / "SKILL.md")
    files = {
        p.relative_to(root).as_posix(): sha256(p)
        for p in files_to_hash(root, policy)
    }
    ledger = {
        "algorithm": "sha256",
        "generated_for_version": version,
        "files": files,
    }
    payload = json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.stdout:
        sys.stdout.write(payload)
    else:
        target = root / "integrity" / "checksums.json"
        target.write_text(payload, encoding="utf-8")
        print(f"Refreshed integrity ledger for {len(files)} protected files at {target}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
