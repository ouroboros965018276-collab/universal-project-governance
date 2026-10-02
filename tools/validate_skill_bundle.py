#!/usr/bin/env python3
"""Validate the compiled installable Universal Project Governance runtime."""
from __future__ import annotations
import argparse, ast, json, re, sys
from pathlib import Path

NAME_RE=re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

def frontmatter(text):
    if not text.startswith("---\n"): return {},["missing frontmatter"]
    end=text.find("\n---\n",4)
    if end<0: return {},["unclosed frontmatter"]
    data={}; current=None; errors=[]
    for raw in text[4:end].splitlines():
        if not raw.strip(): continue
        if raw.startswith("  "):
            if current!="metadata" or ":" not in raw.strip():
                errors.append("unsupported nested frontmatter: "+raw); continue
            k,v=raw.strip().split(":",1); data.setdefault("metadata",{})[k.strip()]=v.strip().strip('"\'')
        else:
            if ":" not in raw: errors.append("invalid frontmatter: "+raw); continue
            k,v=raw.split(":",1); k=k.strip(); v=v.strip()
            current=k if k=="metadata" else None
            data[k]={} if k=="metadata" else v.strip('"\'')
    return data,errors

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",nargs="?",default="."); args=ap.parse_args()
    root=Path(args.root).resolve(); errors=[]; warnings=[]
    skill=root/"SKILL.md"
    if not skill.is_file():
        print("error: SKILL.md missing",file=sys.stderr); return 1
    text=skill.read_text(encoding="utf-8")
    data,fm=frontmatter(text); errors+=fm
    name=data.get("name",""); version=data.get("metadata",{}).get("version","")
    if not NAME_RE.fullmatch(name or ""): errors.append("invalid skill name")
    if name!=root.name: errors.append("frontmatter name must match directory")
    if data.get("license")=="Apache-2.0" and not (root/"LICENSE").is_file(): errors.append("LICENSE missing")
    lines=len(text.splitlines())
    if lines>120: errors.append("runtime SKILL.md complexity budget exceeded: %d > 120" % lines)
    if (root/"references").exists(): errors.append("compiled runtime must not contain references/")
    if (root/"assets").exists(): errors.append("compiled runtime must not contain assets/")
    md_count=len([p for p in root.rglob("*.md") if p.is_file()])
    if md_count>4: errors.append("runtime Markdown budget exceeded: %d > 4" % md_count)
    for req in ["policy-index.json","integrity/manifest.json","schemas/task-context.schema.json","schemas/governance-plan.schema.json","scripts/plan_governance.py","scripts/state_tool.py","scripts/validate_integrity.py"]:
        if not (root/req).is_file(): errors.append("missing compiled runtime file: "+req)
    try:
        index=json.loads((root/"policy-index.json").read_text(encoding="utf-8"))
        if index.get("version")!=version: errors.append("policy-index version mismatch")
        if index.get("architecture")!="compiled-governance": errors.append("policy-index architecture mismatch")
    except Exception as exc: errors.append("invalid policy-index.json: %s" % exc)
    for p in (root/"schemas").glob("*.json"):
        try: json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc: errors.append("invalid schema %s: %s" % (p.name,exc))
    for p in (root/"scripts").glob("*.py"):
        try: ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
        except SyntaxError as exc: errors.append("Python syntax error in %s: %s" % (p.name,exc))
    for p in root.rglob("*"):
        if "__pycache__" in p.parts or p.suffix in {".pyc",".pyo"}: errors.append("generated artifact bundled: %s" % p.relative_to(root))
    for w in warnings: print("warning: "+w)
    for e in errors: print("error: "+e,file=sys.stderr)
    if errors: return 1
    print("Skill bundle check passed: %s %s (%d SKILL.md lines, %d Markdown files)." % (name,version,lines,md_count))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
