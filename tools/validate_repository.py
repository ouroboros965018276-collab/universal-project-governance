#!/usr/bin/env python3
"""Repository-level RC4 source/runtime/release invariants."""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path

SKILL="universal-project-governance"

def run(cmd,root):
    cp=subprocess.run(cmd,cwd=str(root),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    return cp.returncode,cp.stdout+cp.stderr

def skill_version(path):
    text=path.read_text(encoding="utf-8")
    m=re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)',text,re.M)
    return m.group(1).strip() if m else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",nargs="?",default="."); args=ap.parse_args()
    root=Path(args.root).resolve(); errors=[]
    for rel in ["README.md","CHANGELOG.md","PUBLISHING.md","PROJECT_STATE.md","MODULE_MAP.md","DECISIONS.md","governance-src/model/governance-model.json","compiler/compile_governance.py","tools/governance_lint.py",SKILL+"/SKILL.md"]:
        if not (root/rel).exists(): errors.append("missing repository surface: "+rel)
    try:
        model=json.loads((root/"governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        version=model["version"]
    except Exception as exc:
        print("error: invalid canonical model: %s" % exc,file=sys.stderr); return 1
    runtime_version=skill_version(root/SKILL/"SKILL.md")
    if runtime_version!=version: errors.append("canonical/runtime version mismatch: %r != %r" % (version,runtime_version))
    try:
        index=json.loads((root/SKILL/"policy-index.json").read_text(encoding="utf-8"))
        if index.get("version")!=version: errors.append("policy-index version mismatch")
        if index.get("source_sha256") is None: errors.append("policy-index missing source identity")
    except Exception as exc: errors.append("invalid policy-index: %s" % exc)
    readme=(root/"README.md").read_text(encoding="utf-8",errors="replace") if (root/"README.md").exists() else ""
    if version not in readme: errors.append("README does not mention current version")
    changelog=(root/"CHANGELOG.md").read_text(encoding="utf-8",errors="replace") if (root/"CHANGELOG.md").exists() else ""
    if ("## "+version) not in changelog: errors.append("CHANGELOG latest candidate missing")
    if (root/SKILL/"references").exists() or (root/SKILL/"assets").exists():
        errors.append("legacy document/template tree remains in generated runtime")
    if (root/"RC3_UPGRADE_PLAN.md").exists(): errors.append("obsolete RC3 upgrade plan remains")
    if (root/"audits/PRE_RELEASE_AUDIT.md").exists(): errors.append("ambiguous obsolete generic pre-release audit remains")
    for rel in ["compiler/compile_governance.py","tools/governance_lint.py","tools/validate_skill_bundle.py"]:
        if (root/rel).is_file():
            try:
                compile((root/rel).read_text(encoding="utf-8"),rel,"exec")
            except SyntaxError as exc: errors.append("syntax error %s: %s" % (rel,exc))
    for cmd,label in [
        ([sys.executable,"compiler/compile_governance.py","--check"],"compiler drift"),
        ([sys.executable,"tools/governance_lint.py","."],"governance lint"),
        ([sys.executable,"tools/validate_skill_bundle.py",SKILL],"runtime bundle"),
        ([sys.executable,SKILL+"/scripts/validate_integrity.py",SKILL],"runtime integrity")
    ]:
        code,out=run(cmd,root)
        if code!=0: errors.append("%s failed:\n%s" % (label,out))
    forbidden={"__pycache__",".venv","dist","build",".pytest_cache","eval-workspaces"}
    for p in root.rglob("*"):
        rel=p.relative_to(root)
        if any(part in forbidden for part in rel.parts): errors.append("tracked/generated artifact: %s" % rel)
        if p.is_file() and p.suffix in {".pyc",".pyo",".zip"}: errors.append("tracked/generated file: %s" % rel)
    for e in errors: print("error: "+e,file=sys.stderr)
    if errors: return 1
    print("Repository check passed: %s %s (canonical source + compiled runtime synchronized)." % (SKILL,version))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
