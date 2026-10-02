#!/usr/bin/env python3
"""Create a deterministic ZIP containing only the installable Skill directory."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

EXCLUDED_DIRS = {".git", ".venv", "__pycache__", "dist", "build", ".pytest_cache"}
EXCLUDED_NAMES = {".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def should_include(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith(".zip.sha256"):
        return False
    return path.is_file() and not path.is_symlink()


def version_from_skill(skill: Path) -> str:
    text = skill.read_text(encoding="utf-8")
    m = re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)["\']?\s*$', text, re.M)
    if not m:
        raise ValueError("metadata.version not found in SKILL.md")
    return m.group(1).strip()


def validate_stage(stage: Path, validator: Path) -> None:
    cp = subprocess.run([sys.executable,str(validator),str(stage)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
    if cp.returncode != 0:
        raise RuntimeError("staged bundle validation failed:\n" + cp.stdout + cp.stderr)


def make_zip(stage: Path, output: Path) -> None:
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
        for path in files:
            rel=path.relative_to(stage).as_posix(); info=zipfile.ZipInfo(f"{stage.name}/{rel}",date_time=ZIP_TIME); info.compress_type=zipfile.ZIP_DEFLATED
            mode=0o100755 if rel.startswith("scripts/") and path.suffix==".py" else 0o100644; info.external_attr=mode<<16; info.create_system=3
            zf.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)


def main() -> int:
    ap=argparse.ArgumentParser(description="Build deterministic Universal Project Governance release archive"); ap.add_argument("skill_root",nargs="?",default="universal-project-governance"); ap.add_argument("--output-dir",default="dist"); args=ap.parse_args()
    skill_root=Path(args.skill_root).resolve()
    if not (skill_root/"SKILL.md").is_file(): print(f"error: SKILL.md not found under {skill_root}",file=sys.stderr); return 2
    repo_root=skill_root.parent; validator=repo_root/"tools"/"validate_skill_bundle.py"
    if not validator.is_file(): print(f"error: repository validator not found: {validator}",file=sys.stderr); return 2
    version=version_from_skill(skill_root/"SKILL.md"); out_dir=Path(args.output_dir)
    if not out_dir.is_absolute(): out_dir=(repo_root/out_dir).resolve()
    out_dir.mkdir(parents=True,exist_ok=True); archive=out_dir/f"{skill_root.name}-v{version}.zip"; checksum=Path(str(archive)+".sha256")
    with tempfile.TemporaryDirectory() as td:
        stage=Path(td)/skill_root.name; stage.mkdir()
        for src in sorted(skill_root.rglob("*")):
            if not should_include(src,skill_root): continue
            rel=src.relative_to(skill_root); dst=stage/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst)
        try: validate_stage(stage,validator)
        except RuntimeError as exc: print(f"error: {exc}",file=sys.stderr); return 1
        make_zip(stage,archive)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest(); checksum.write_text(f"{digest}  {archive.name}\n",encoding="utf-8")
    print(f"archive: {archive}"); print(f"sha256:  {digest}"); print(f"checksum: {checksum}"); return 0

if __name__=="__main__": raise SystemExit(main())
