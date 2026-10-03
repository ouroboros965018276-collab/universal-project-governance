#!/usr/bin/env python3
"""One-command project-scoped install/remove wrapper for Universal Project Governance."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SKILL_NAME = "universal-project-governance"
SKILLS_CLI = "skills@1.7.0"

def run(command, cwd):
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

def find_installed(project):
    project = Path(project).resolve()
    candidates = sorted(project.glob(".*"))
    for root in candidates:
        if not root.is_dir():
            continue
        for skill in root.glob("**/%s/SKILL.md" % SKILL_NAME):
            return skill.parent
    direct = list(project.glob("**/%s/SKILL.md" % SKILL_NAME))
    return direct[0].parent if direct else None

def project_tool(skill_dir, project, *args):
    command = [sys.executable, str(skill_dir / "scripts/project_tool.py"), *args, str(Path(project).resolve())]
    return run(command, project)

def install(project, agent, source):
    project = Path(project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    if shutil.which("npx") is None:
        raise RuntimeError("npx is required for Skill installation")
    command = [
        "npx", "-y", SKILLS_CLI, "add", source,
        "--skill", SKILL_NAME, "-a", agent, "--copy", "-y",
    ]
    cp = run(command, project)
    if cp.returncode != 0:
        raise RuntimeError("Skill installation failed: " + cp.stderr[-2000:])
    skill_dir = find_installed(project)
    if skill_dir is None:
        raise RuntimeError("Skill CLI completed but installed Skill could not be located")
    integrity = run(
        [sys.executable, str(skill_dir / "scripts/validate_integrity.py"), str(skill_dir)],
        project,
    )
    if integrity.returncode != 0:
        raise RuntimeError("installed Skill integrity failed: " + integrity.stderr[-2000:])
    bound = project_tool(skill_dir, project, "install")
    if bound.returncode != 0:
        raise RuntimeError("project binding install failed: " + bound.stderr[-2000:])
    print("UPG installed and project binding initialized.")
    return 0

def remove(project, agent, yes):
    project = Path(project).resolve()
    skill_dir = find_installed(project)
    fallback = ROOT / "universal-project-governance"
    tool_dir = skill_dir if skill_dir is not None else fallback
    if not yes:
        raise RuntimeError("remove requires --yes")
    if (tool_dir / "scripts/project_tool.py").is_file():
        unbound = project_tool(tool_dir, project, "remove", "--yes")
        if unbound.returncode != 0:
            raise RuntimeError("project binding removal failed: " + unbound.stderr[-2000:])
    if shutil.which("npx") is None:
        raise RuntimeError("npx is required for Skill removal")
    cp = run(
        ["npx", "-y", SKILLS_CLI, "remove", SKILL_NAME, "-a", agent, "-y"],
        project,
    )
    if cp.returncode != 0:
        raise RuntimeError("Skill removal failed: " + cp.stderr[-2000:])
    print("UPG project binding and Skill removed.")
    return 0

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    install_p = sub.add_parser("install")
    install_p.add_argument("--project", default=".")
    install_p.add_argument("--agent", default="codex")
    install_p.add_argument("--source", default=str(ROOT))
    remove_p = sub.add_parser("remove")
    remove_p.add_argument("--project", default=".")
    remove_p.add_argument("--agent", default="codex")
    remove_p.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        if args.cmd == "install":
            return install(args.project, args.agent, args.source)
        return remove(args.project, args.agent, args.yes)
    except (OSError, RuntimeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
