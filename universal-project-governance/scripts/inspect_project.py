#!/usr/bin/env python3
"""Evidence-oriented, read-only project scanner for universal-project-governance.

No network access. No third-party dependencies. It reports observable signals; it does not infer
architecture quality or declare files safe to delete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from typing import Iterable

IGNORE_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "vendor", "dist", "build", "out",
    "target", ".next", ".nuxt", ".cache", ".pytest_cache", "__pycache__", "coverage", ".terraform",
    ".idea", ".gradle", ".mypy_cache", ".ruff_cache", ".tox", ".yarn", ".pnpm-store"
}
SENSITIVE_NAMES = {
    ".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials", "credentials.json",
    "secrets.json", "kubeconfig", "token", "tokens.json"
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs",
    ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".swift", ".scala", ".sh", ".ps1",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".xml", ".sql", ".proto",
    ".graphql", ".tf", ".tfvars", ".dockerfile", ".vue", ".svelte", ".html", ".css", ".scss"
}
MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "uv.lock",
    "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts", "composer.json", "Gemfile",
    "mix.exs", "Package.swift", "*.csproj", "*.sln", "CMakeLists.txt", "Makefile"
}
INSTRUCTION_NAMES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", "CONTRIBUTING.md", "DEVELOPING.md",
    "PROJECT_STATE.md", "MODULE_MAP.md"
}
DOC_NAMES = {"README.md", "ARCHITECTURE.md", "DESIGN.md", "ROADMAP.md", "SPEC.md", "SECURITY.md"}
CI_NAMES = {".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", ".circleci", "azure-pipelines.yml"}
INFRA_NAMES = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "terraform", "k8s", "kubernetes", "helm"
}
DATA_SUFFIXES = {".csv", ".parquet", ".arrow", ".feather", ".avro", ".orc", ".ndjson"}
ML_NAMES = {"mlflow", "wandb", "models", "checkpoints", "notebooks", "dvc.yaml", ".dvc"}


def is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    if name in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    if name.startswith(".env") and name not in {".env.example", ".env.sample", ".env.template"}:
        return True
    stem = path.stem.lower().replace("-", "_").replace(".", "_")
    sensitive_tokens = ("secret", "credential", "private_key", "access_token", "refresh_token", "password", "passwd")
    return any(token in stem for token in sensitive_tokens)


def walk(root: Path, max_files: int) -> tuple[list[Path], bool]:
    """Return a deterministic, bounded file list and whether the scan was truncated.

    Symlinked files/directories are skipped so optional content hashing/marker scans cannot follow a
    link outside the requested project root.
    """
    result: list[Path] = []
    for base, dirs, names in os.walk(root, followlinks=False):
        base_path = Path(base)
        dirs[:] = sorted(
            d for d in dirs
            if d not in IGNORE_DIRS and not (base_path / d).is_symlink()
        )
        for n in sorted(names):
            p = base_path / n
            if p.is_symlink() or is_sensitive(p):
                continue
            result.append(p)
            if len(result) > max_files:
                return result[:max_files], True
    return result, False


def run_git(root: Path, args: list[str]) -> tuple[int, str]:
    if not shutil.which("git"):
        return 127, ""
    try:
        cp = subprocess.run(
            ["git", "-C", str(root), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        return cp.returncode, cp.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def git_facts(root: Path, history: int) -> dict:
    code, top = run_git(root, ["rev-parse", "--show-toplevel"])
    if code != 0:
        return {"available": bool(shutil.which("git")), "repository": False}
    top_path = Path(top).resolve()
    facts = {"available": True, "repository": True, "root": str(top_path)}
    _, branch = run_git(root, ["branch", "--show-current"])
    _, head = run_git(root, ["rev-parse", "--short=12", "HEAD"])
    _, status = run_git(root, ["status", "--porcelain=v1"])
    _, log = run_git(root, ["log", f"-{history}", "--date=iso-strict", "--pretty=format:%h\t%ad\t%s"])
    _, changed = run_git(root, ["log", f"-{history}", "--name-only", "--pretty=format:"])
    facts.update({
        "branch": branch or None,
        "head": head or None,
        "working_tree_entries": [line for line in status.splitlines() if line.strip()],
        "recent_commits": [line for line in log.splitlines() if line.strip()],
        "recent_changed_paths": Counter(line.strip() for line in changed.splitlines() if line.strip()).most_common(25),
    })
    return facts


def name_matches(p: Path, root: Path, names: set[str]) -> bool:
    rel = str(p.relative_to(root)).replace(os.sep, "/")
    return p.name in names or rel in names or any(
        rel.startswith(x.rstrip("/") + "/") for x in names if "/" in x
    )


def classify(root: Path, paths: list[Path], truncated: bool) -> dict:
    by_suffix = Counter((p.suffix.lower() or "<no-extension>") for p in paths)
    manifests, instructions, docs, ci, infra, data, ml = [], [], [], [], [], [], []
    env_examples = []
    for p in paths:
        rel = str(p.relative_to(root)).replace(os.sep, "/")
        name = p.name
        if name in MANIFESTS or any(name.endswith(m[1:]) for m in MANIFESTS if m.startswith("*")):
            manifests.append(rel)
        if name in INSTRUCTION_NAMES:
            instructions.append(rel)
        if name in DOC_NAMES or rel.startswith("docs/"):
            docs.append(rel)
        if name_matches(p, root, CI_NAMES):
            ci.append(rel)
        if name_matches(p, root, INFRA_NAMES) or p.suffix.lower() == ".tf":
            infra.append(rel)
        if p.suffix.lower() in DATA_SUFFIXES:
            data.append(rel)
        if any(part.lower() in ML_NAMES for part in p.parts) or name in ML_NAMES:
            ml.append(rel)
        if name.lower() in {".env.example", ".env.sample", ".env.template"}:
            env_examples.append(rel)
    return {
        "file_count_scanned": len(paths),
        "scan_truncated": truncated,
        "top_suffixes": by_suffix.most_common(20),
        "manifests": sorted(manifests)[:100],
        "project_instructions": sorted(instructions)[:100],
        "documentation_signals": sorted(docs)[:150],
        "ci_cd_signals": sorted(set(ci))[:100],
        "infrastructure_signals": sorted(set(infra))[:100],
        "data_artifacts": sorted(data)[:100],
        "ml_ai_signals": sorted(set(ml))[:100],
        "environment_templates": sorted(env_examples)[:50],
    }


def exact_duplicates(root: Path, paths: list[Path], max_bytes: int = 1_000_000) -> list[list[str]]:
    groups: dict[tuple[int, str], list[str]] = defaultdict(list)
    for p in paths:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size == 0 or size > max_bytes or is_sensitive(p) or p.is_symlink():
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {"Dockerfile", "Makefile"}:
            continue
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            continue
        groups[(size, digest)].append(str(p.relative_to(root)).replace(os.sep, "/"))
    return sorted((sorted(v) for v in groups.values() if len(v) > 1), key=lambda g: tuple(g))


def marker_counts(root: Path, paths: list[Path], max_bytes: int = 500_000) -> dict:
    counts = Counter()
    for p in paths:
        if is_sensitive(p) or p.is_symlink():
            continue
        try:
            if p.stat().st_size > max_bytes:
                continue
        except OSError:
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {"Dockerfile", "Makefile"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for marker in ("TODO", "FIXME", "HACK", "XXX", "DEPRECATED"):
            n = text.count(marker)
            if n:
                counts[marker] += n
    return dict(sorted(counts.items()))


def to_markdown(report: dict) -> str:
    lines = ["# Project Inspection", "", f"Root: `{report['root']}`", ""]
    lines += ["## Observed signals", ""]
    for key, value in report["signals"].items():
        if isinstance(value, list):
            lines.append(f"### {key.replace('_', ' ').title()}")
            if not value:
                lines.append("- None observed in scanned scope.")
            else:
                for item in value[:50]:
                    lines.append(f"- `{item}`" if isinstance(item, str) else f"- `{item[0]}`: {item[1]}")
            lines.append("")
        else:
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
    lines += ["", "## Version control", "", "```json", json.dumps(report["git"], indent=2, ensure_ascii=False), "```", ""]
    if "exact_duplicate_groups" in report:
        lines += ["## Exact duplicate-content signals", ""]
        for g in report["exact_duplicate_groups"]:
            lines.append("- " + ", ".join(f"`{x}`" for x in g))
        if not report["exact_duplicate_groups"]:
            lines.append("- None observed in eligible scanned files.")
        lines.append("")
    if "marker_counts" in report:
        lines += ["## Marker counts (signal only)", "", "```json", json.dumps(report["marker_counts"], indent=2), "```", ""]
    if report["signals"].get("scan_truncated"):
        lines += ["> Scan was truncated by `--max-files`; absence of a signal is not evidence of absence outside the scanned set.", ""]
    lines += ["> Signals are not conclusions. Verify before declaring debt, fragility, or safe deletion.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only project evidence scanner")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--format", choices=("json", "markdown"), default="json")
    ap.add_argument("--output")
    ap.add_argument("--max-files", type=int, default=10000)
    ap.add_argument("--git-history", type=int, default=12)
    ap.add_argument("--duplicates", action="store_true", help="Hash eligible text files to report exact duplicates")
    ap.add_argument("--markers", action="store_true", help="Count TODO/FIXME/HACK/XXX/DEPRECATED markers")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    paths, truncated = walk(root, max(1, args.max_files))
    report = {
        "root": str(root),
        "signals": classify(root, paths, truncated),
        "git": git_facts(root, max(1, args.git_history)),
        "notes": [
            "Sensitive-looking files and symlinks are skipped.",
            "Generated/vendor/cache directories are excluded by default.",
            "All findings are signals requiring contextual verification."
        ]
    }
    if args.duplicates:
        report["exact_duplicate_groups"] = exact_duplicates(root, paths)
    if args.markers:
        report["marker_counts"] = marker_counts(root, paths)

    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.format == "json" else to_markdown(report)
    if args.output:
        out = Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
