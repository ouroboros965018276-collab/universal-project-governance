#!/usr/bin/env python3
"""Build a deterministic ZIP from the compiler-verified installable runtime."""
from __future__ import annotations
import argparse,hashlib,os,re,subprocess,sys,tempfile,zipfile
from pathlib import Path

ZIP_TIME=(1980,1,1,0,0,0)

def run(cmd,root):
    cp=subprocess.run(cmd,cwd=str(root),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
    if cp.returncode!=0: raise RuntimeError(cp.stdout+cp.stderr)

def version(skill):
    m=re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)',(skill/"SKILL.md").read_text(encoding="utf-8"),re.M)
    if not m: raise ValueError("metadata.version missing")
    return m.group(1).strip()

def make_zip(skill,out):
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
        for p in sorted(x for x in skill.rglob("*") if x.is_file() and "__pycache__" not in x.parts and x.suffix not in {".pyc",".pyo"}):
            rel=p.relative_to(skill).as_posix()
            info=zipfile.ZipInfo(skill.name+"/"+rel,date_time=ZIP_TIME)
            info.compress_type=zipfile.ZIP_DEFLATED; info.create_system=3
            info.external_attr=(0o100755 if rel.startswith("scripts/") and p.suffix==".py" else 0o100644)<<16
            zf.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("skill",nargs="?",default="universal-project-governance"); ap.add_argument("--output-dir",default="dist"); args=ap.parse_args()
    repo=Path.cwd().resolve(); skill=(repo/args.skill).resolve() if not Path(args.skill).is_absolute() else Path(args.skill).resolve()
    try:
        run([sys.executable,"compiler/compile_governance.py","--check"],repo)
        run([sys.executable,"tools/governance_lint.py","."],repo)
        run([sys.executable,"tools/validate_skill_bundle.py",skill.name],repo)
        run([sys.executable,str(skill/"scripts/validate_integrity.py"),str(skill)],repo)
        ver=version(skill)
        outdir=Path(args.output_dir); outdir=outdir if outdir.is_absolute() else repo/outdir; outdir.mkdir(parents=True,exist_ok=True)
        archive=outdir/("%s-v%s.zip" % (skill.name,ver)); checksum=Path(str(archive)+".sha256")
        make_zip(skill,archive)
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum.write_text("%s  %s\n" % (digest,archive.name),encoding="utf-8")
        print("archive: %s" % archive); print("sha256:  %s" % digest); print("checksum: %s" % checksum)
    except Exception as exc:
        print("error: %s" % exc,file=sys.stderr); return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
