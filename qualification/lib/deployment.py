from __future__ import annotations
import pathlib
import subprocess
import sys


def prepare_a2_reporting(workspace, skill_path):
    tool = pathlib.Path(skill_path) / "scripts/project_tool.py"
    if not tool.is_file():
        raise ValueError("A2 qualification Skill is missing scripts/project_tool.py")
    cp = subprocess.run(
        [sys.executable, str(tool), "install", str(workspace), "--field-test-reporting"],
        cwd=str(workspace),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode:
        raise RuntimeError("A2 reporting opt-in failed: " + (cp.stderr[-2000:] or cp.stdout[-2000:]))
