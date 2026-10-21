from __future__ import annotations
import pathlib
import subprocess
import sys


def prepare_a2_reporting(workspace, skill_path):
    workspace = pathlib.Path(workspace).resolve()
    if not workspace.is_dir(): raise ValueError("A2 reporting workspace must be an existing directory")
    tool = pathlib.Path(skill_path).resolve() / "scripts/project_tool.py"
    if not tool.is_file():
        raise ValueError("A2 qualification Skill is missing scripts/project_tool.py")
    try:
        cp = subprocess.run(
        [sys.executable, str(tool), "install", str(workspace), "--field-test-reporting"],
        cwd=str(workspace),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False, timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("A2 reporting opt-in timed out after 120 seconds") from exc
    if cp.returncode:
        detail = (cp.stderr[-2000:] or cp.stdout[-2000:]).strip() or "no diagnostic output"
        raise RuntimeError("A2 reporting opt-in failed (exit %s): %s" % (cp.returncode, detail))
