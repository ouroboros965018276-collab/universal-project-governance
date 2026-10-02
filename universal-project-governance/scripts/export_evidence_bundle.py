#!/usr/bin/env python3
"""Export a compact governance evidence bundle without project source code."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DOCS = ("PROJECT_STATE.md", "MODULE_MAP.md", "DECISIONS.md", "EXCEPTIONS.md")
GOV_DOCS = ("HANDOFF.md", "feedback/OPEN.md")
MAX_FILE_BYTES = 250_000


def add_file(parts: list[str], root: Path, path: Path) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
        return
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    parts += [f"\n---\n\n## Source: `{rel}`\n", text.rstrip(), ""]


def main() -> int:
    ap = argparse.ArgumentParser(description="Export governance-only evidence for external review")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--output")
    ap.add_argument("--latest-executions", type=int, default=3)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    parts = [
        "# Governance Evidence Bundle",
        "",
        "> Contains governance documents/evidence only. Project source code is intentionally excluded.",
    ]

    for name in ROOT_DOCS:
        add_file(parts, root, root / name)

    gov = root / ".governance"
    if gov.is_dir():
        for name in GOV_DOCS:
            add_file(parts, root, gov / name)
        execution = gov / "execution"
        if execution.is_dir():
            recent = sorted(execution.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            for path in recent[:max(0, args.latest_executions)]:
                add_file(parts, root, path)
        audits = gov / "audits"
        if audits.is_dir():
            for path in sorted(audits.glob("*.md"))[-3:]:
                add_file(parts, root, path)

    payload = "\n".join(parts).rstrip() + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"Wrote governance evidence bundle: {out}")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
