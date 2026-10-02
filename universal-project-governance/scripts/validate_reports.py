#!/usr/bin/env python3
"""Validate optional .governance report lifecycle and bounded retention."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def load_config(root: Path) -> dict:
    cfg = root / ".governance" / "config.json"
    if not cfg.is_file():
        return {"mode": "standard", "execution_retention": 50}
    return json.loads(cfg.read_text(encoding="utf-8"))


def git_frozen_audit_errors(root: Path, base_ref: str | None) -> list[str]:
    if not base_ref or not (root / ".git").exists():
        return []
    cp = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-status", f"{base_ref}...HEAD", "--", ".governance/audits"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if cp.returncode != 0:
        return []
    errors = []
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        status = line.split("\t", 1)[0]
        if status.startswith(("M", "D", "R")):
            errors.append("frozen audit modified/deleted instead of adding new evidence: " + line)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--base-ref")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    gov = root / ".governance"
    if not gov.is_dir():
        print("No .governance directory found; report lifecycle validation is not required.")
        return 0

    errors = []
    try:
        cfg = load_config(root)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: invalid .governance/config.json: {exc}", file=sys.stderr)
        return 1

    retention = int(cfg.get("execution_retention", 50))
    execution = gov / "execution"
    records = sorted(execution.glob("*.md")) if execution.is_dir() else []
    if len(records) > retention:
        errors.append(
            f"execution audit retention exceeded: {len(records)} records > {retention}; "
            "summarize/archive useful older evidence and remove superseded raw records"
        )

    handoff = gov / "HANDOFF.md"
    if handoff.exists():
        validator = Path(__file__).with_name("validate_handoff.py")
        cp = subprocess.run([sys.executable, str(validator), str(handoff)], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if cp.returncode != 0:
            errors.append("HANDOFF.md invalid: " + (cp.stderr.strip() or cp.stdout.strip()))

    errors.extend(git_frozen_audit_errors(root, args.base_ref))

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"Governance report lifecycle check passed ({len(records)} execution record(s), retention={retention}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
