#!/usr/bin/env python3
"""Validate default Universal Project Governance artifacts when a project uses them.

Projects may use equivalent canonical structures. In that case this helper is optional and should not
force creation of duplicate docs.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

STATE_REQUIRED = [
    "## Purpose",
    "## Current state",
    "## Architecture / structure",
    "## Canonical sources of truth",
    "## Major capabilities",
    "## Constraints and invariants",
    "## Validation / operation",
    "## Last meaningful change",
    "## Previous meaningful change",
]
MODULE_REQUIRED = ["Location", "Status", "Function", "Purpose", "Scope", "Invariants", "Change safety"]
CHANGE_REQUIRED = ["When", "What / why", "Before / after", "Validation"]
AMBIGUOUS_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
ISO_TZ = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})\b")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
LABEL_ONLY = re.compile(r"^-\s+\*\*[^*]+:\*\*\s*$")
TABLE_SEPARATOR = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")
PLACEHOLDER_HEADINGS = {"<Stable module / component ID>", "<Exception ID / title>", "<Decision title>"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def section_body(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return None
    level = len(heading) - len(heading.lstrip("#"))
    body: list[str] = []
    for line in lines[start + 1:]:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            next_level = len(stripped) - len(stripped.lstrip("#"))
            if next_level <= level:
                break
        body.append(line)
    return "\n".join(body)


def meaningful_lines(body: str) -> list[str]:
    body = HTML_COMMENT.sub("", body)
    out: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or TABLE_SEPARATOR.fullmatch(line) or LABEL_ONLY.fullmatch(line):
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            # Drop known header-only rows and fully empty template rows.
            lowered = {c.lower() for c in cells}
            if not any(c for c in cells):
                continue
            if lowered <= {
                "concern", "canonical source", "ownership / generation notes",
                "capability", "current implementation", "status", "notes",
                "purpose", "command or procedure", "expected evidence",
            }:
                continue
        out.append(line)
    return out


def validate_when_values(path: Path, text: str, warnings: list[str]) -> None:
    for line in text.splitlines():
        if "**When:**" not in line:
            continue
        value = line.split("**When:**", 1)[1].strip()
        if value and value not in {"UNRESOLVED", "None", "N/A"} and not ISO_TZ.search(value):
            warnings.append(
                f"{path}: non-empty When value is not a timezone-aware ISO timestamp or explicit unresolved marker: {value!r}"
            )


def validate_state(path: Path, errors: list[str], warnings: list[str]) -> None:
    text = read(path)
    for h in STATE_REQUIRED:
        body = section_body(text, h)
        if body is None:
            errors.append(f"{path}: missing required default-template section {h!r}")
            continue
        if not meaningful_lines(body):
            errors.append(f"{path}: section {h!r} is still empty/template-only")
    if AMBIGUOUS_DATE.search(text):
        errors.append(f"{path}: ambiguous numeric date found; use ISO 8601 with timezone")
    validate_when_values(path, text, warnings)


def parse_module_sections(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            starts.append((i, line[3:].strip()))
    sections: list[tuple[str, str]] = []
    for idx, (start, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        sections.append((title, "\n".join(lines[start + 1:end])))
    return sections


def label_value(body: str, label: str) -> str | None:
    pattern = re.compile(rf"^-\s+\*\*{re.escape(label)}:\*\*\s*(.*)$", re.M)
    m = pattern.search(body)
    return None if not m else m.group(1).strip()


def validate_module(path: Path, errors: list[str], warnings: list[str]) -> None:
    text = read(path)
    if AMBIGUOUS_DATE.search(text):
        errors.append(f"{path}: ambiguous numeric date found; use ISO 8601 with timezone")
    sections = [(title, body) for title, body in parse_module_sections(text) if title not in PLACEHOLDER_HEADINGS]
    if not sections:
        errors.append(f"{path}: no populated module entries found; delete the file if a module map is not needed")
        return
    for title, body in sections:
        for label in MODULE_REQUIRED:
            value = label_value(body, label)
            if value is None:
                errors.append(f"{path}: module {title!r} missing field {label!r}")
            elif not value:
                errors.append(f"{path}: module {title!r} field {label!r} is empty")
        for change_heading in ("### Last meaningful change", "### Previous meaningful change"):
            cbody = section_body("## X\n" + body, change_heading)
            if cbody is None:
                errors.append(f"{path}: module {title!r} missing {change_heading!r}")
                continue
            for label in CHANGE_REQUIRED:
                value = label_value(cbody, label)
                if value is None or not value:
                    errors.append(f"{path}: module {title!r} {change_heading!r} has empty/missing {label!r}")
    validate_when_values(path, text, warnings)


def validate_exceptions(path: Path, errors: list[str]) -> None:
    text = read(path)
    sections = parse_module_sections(text)
    real = [(title, body) for title, body in sections if title not in PLACEHOLDER_HEADINGS]
    if not real:
        errors.append(f"{path}: no active exception entries found; delete the default file when no exceptions exist")
        return
    required = [
        "Debt / constraint", "Why it cannot be resolved now", "Evidence", "Risk / failure mode",
        "Affected scope", "Removal condition", "Review / expiry trigger"
    ]
    for title, body in real:
        for label in required:
            value = label_value(body, label)
            if value is None or not value:
                errors.append(f"{path}: exception {title!r} has empty/missing {label!r}")


def validate_decisions(path: Path, errors: list[str]) -> None:
    text = read(path)
    sections = parse_module_sections(text)
    real = [(title, body) for title, body in sections if title not in PLACEHOLDER_HEADINGS]
    if not real:
        errors.append(f"{path}: no active decision entries found; delete the default file when no active decisions exist")
        return
    required = ["Status", "Decision", "Why", "Evidence / constraints", "Consequences", "Applies to", "Revisit when"]
    for title, body in real:
        for label in required:
            value = label_value(body, label)
            if value is None or not value:
                errors.append(f"{path}: decision {title!r} has empty/missing {label!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate default governance artifacts if present")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--state-file", default="PROJECT_STATE.md")
    ap.add_argument("--module-map", default="MODULE_MAP.md")
    ap.add_argument("--exceptions", default="EXCEPTIONS.md")
    ap.add_argument("--decisions", default="DECISIONS.md")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    found = 0

    state = root / args.state_file
    if state.exists():
        found += 1
        validate_state(state, errors, warnings)
    module = root / args.module_map
    if module.exists():
        found += 1
        validate_module(module, errors, warnings)
    exc = root / args.exceptions
    if exc.exists():
        found += 1
        validate_exceptions(exc, errors)
    decisions = root / args.decisions
    if decisions.exists():
        found += 1
        validate_decisions(decisions, errors)

    if found == 0:
        print("No default-named governance artifacts found. This is not an error if the project uses equivalent canonical structures.")
        return 0
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"Governance artifact check passed ({found} artifact(s) inspected, {len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
