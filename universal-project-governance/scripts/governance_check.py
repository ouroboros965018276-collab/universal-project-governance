#!/usr/bin/env python3
"""Run the lightweight RC3 governance checks available inside the installed Skill."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run(script: Path, *args: str) -> int:
    cp = subprocess.run([sys.executable, str(script), *args], check=False)
    return cp.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project_root", nargs="?", default=".")
    ap.add_argument("--skill-root")
    ap.add_argument("--base-ref")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_root = Path(args.skill_root).resolve() if args.skill_root else script_dir.parent
    project_root = Path(args.project_root).resolve()

    checks = [
        (script_dir / "validate_integrity.py", [str(skill_root)]),
        (script_dir / "validate_project_governance.py", [str(project_root)]),
        (script_dir / "validate_reports.py", [str(project_root)] + (["--base-ref", args.base_ref] if args.base_ref else [])),
    ]
    failed = 0
    for script, argv in checks:
        failed += 1 if run(script, *argv) else 0
    if failed:
        print(f"Governance check failed: {failed} check(s) failed.", file=sys.stderr)
        return 1
    print("Governance check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
