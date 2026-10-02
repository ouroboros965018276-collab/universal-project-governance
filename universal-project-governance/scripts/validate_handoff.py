#!/usr/bin/env python3
"""Validate a current Handoff Snapshot without requiring historical accumulation."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

REQUIRED = [
    "## Current Objective",
    "## Current State",
    "## Completed",
    "## In Progress",
    "## Important Decisions",
    "## Do Not Change Without Review",
    "## Known Risks / Open Questions",
    "## Validation / Evidence",
    "## Recommended Next Actions",
]
COMMENT = re.compile(r"<!--.*?-->", re.S)


def section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return None
    body = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def meaningful(body: str) -> bool:
    cleaned = COMMENT.sub("", body).strip()
    if not cleaned:
        return False
    values = [x.strip(" -*\t").strip().lower() for x in cleaned.splitlines() if x.strip()]
    return any(v not in {"", "none.", "none", "n/a", "todo"} for v in values) or any(
        v in {"none.", "none", "n/a"} for v in values
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    args = ap.parse_args()
    path = Path(args.file)
    if not path.is_file():
        print(f"error: handoff file not found: {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    errors = []
    if "**Last Updated:**" not in text:
        errors.append("missing Last Updated field")
    for heading in REQUIRED:
        body = section(text, heading)
        if body is None:
            errors.append(f"missing section {heading}")
        elif not meaningful(body):
            errors.append(f"empty handoff section {heading}")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print("Handoff snapshot validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
