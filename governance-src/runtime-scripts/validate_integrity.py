#!/usr/bin/env python3
"""Verify the generated installable Skill against its compiler-produced SHA-256 manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

IGNORE_DIRS = {"__pycache__", ".git"}
IGNORE_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eligible(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p == root / "integrity" / "manifest.json":
            continue
        rel = p.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts) or p.suffix in IGNORE_SUFFIXES:
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    manifest_path = root / "integrity" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print("error: cannot read integrity manifest: %s" % exc, file=sys.stderr)
        return 2
    expected = manifest.get("files", {})
    current = {str(p.relative_to(root)).replace("\\","/"): sha256(p) for p in eligible(root)}
    errors = []
    for rel in sorted(set(expected) | set(current)):
        if rel not in expected:
            errors.append("unexpected runtime file: " + rel)
        elif rel not in current:
            errors.append("missing runtime file: " + rel)
        elif expected[rel] != current[rel]:
            errors.append("integrity mismatch: " + rel)
    if errors:
        for err in errors: print("error: " + err, file=sys.stderr)
        return 1
    print("Integrity check passed (%d generated runtime files)." % len(current))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
