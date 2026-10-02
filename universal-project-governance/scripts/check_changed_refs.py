#!/usr/bin/env python3
"""Report possible references to renamed/deleted Git paths.

Read-only heuristic: findings require human/agent verification and are never proof of staleness.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

IGNORE_DIRS = {".git", "node_modules", "vendor", "dist", "build", "out", "target", ".venv", "venv", ".cache", "__pycache__"}
TEXT_SUFFIXES = {".md", ".txt", ".rst", ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".sh", ".ps1", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".xml", ".sql", ".tf", ".html", ".css", ".scss"}


def git(root: Path, *args: str) -> tuple[int, str]:
    try:
        cp = subprocess.run(["git", "-C", str(root), *args], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=15, check=False)
        return cp.returncode, cp.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def changed_old_paths(root: Path, base: str | None) -> list[str]:
    commands = []
    if base:
        commands.append(("diff", "--name-status", "--find-renames", f"{base}...HEAD"))
    else:
        commands += [
            ("diff", "--name-status", "--find-renames", "HEAD"),
            ("diff", "--cached", "--name-status", "--find-renames", "HEAD")
        ]
    old = []
    seen = set()
    for cmd in commands:
        code, out = git(root, *cmd)
        if code != 0:
            continue
        for line in out.splitlines():
            parts = line.split("\t")
            if not parts:
                continue
            status = parts[0]
            candidate = None
            if status.startswith("D") and len(parts) >= 2:
                candidate = parts[1]
            elif status.startswith("R") and len(parts) >= 3:
                candidate = parts[1]
            if candidate and candidate not in seen:
                seen.add(candidate)
                old.append(candidate)
    return old


def text_files(root: Path):
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not (Path(base) / d).is_symlink())
        b = Path(base)
        for n in sorted(files):
            p = b / n
            if p.is_symlink():
                continue
            if p.suffix.lower() in TEXT_SUFFIXES or n in {"Dockerfile", "Makefile"}:
                try:
                    if p.stat().st_size <= 1_000_000:
                        yield p
                except OSError:
                    pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Find possible stale references to renamed/deleted Git paths")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--base", help="Compare BASE...HEAD instead of working tree/staged changes")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not shutil.which("git"):
        print("error: git is not available", file=sys.stderr)
        return 2
    code, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        print("error: target is not a Git work tree", file=sys.stderr)
        return 2
    old_paths = changed_old_paths(root, args.base)
    if not old_paths:
        print("No renamed/deleted paths detected in the selected diff.")
        return 0

    files = list(text_files(root))
    findings = []
    for old in old_paths:
        tokens = {old, Path(old).name}
        for p in files:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hits = [t for t in tokens if t and t in text]
            if hits:
                rel = str(p.relative_to(root)).replace(os.sep, "/")
                if rel == old:
                    continue
                findings.append((old, rel, sorted(hits)))

    if not findings:
        print("No literal references to renamed/deleted paths were found in eligible text files.")
        return 0
    print("Possible references to inspect (heuristic; verify context):")
    for old, rel, hits in findings:
        print(f"- old={old!r} referenced-by={rel!r} tokens={','.join(hits)!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
