#!/usr/bin/env python3
"""Conservative static security audit for the repository and distributed runtime helpers."""
from __future__ import annotations
import argparse,ast,re,sys
from pathlib import Path
NETWORK_IMPORTS={"socket","urllib","http","ftplib","smtplib","requests","httpx","aiohttp"}; DANGEROUS_CALLS={"eval","exec","compile","os.system","subprocess.Popen","pickle.loads","marshal.loads"}
SECRET_PATTERNS={"private-key":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),"github-pat":re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),"aws-access-key":re.compile(r"\bAKIA[0-9A-Z]{16}\b"),"bearer-token":re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}\b",re.I)}
TEXT_SUFFIXES={".md",".txt",".py",".json",".yaml",".yml",".toml",".ini",".cfg"}
def dotted(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        left=dotted(node.value); return f"{left}.{node.attr}" if left else node.attr
    return ""
def audit_runtime_scripts(skill_root:Path,errors:list,warnings:list)->None:
    for path in sorted((skill_root/"scripts").glob("*.py")):
        try: tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        except SyntaxError as exc: errors.append(f"{path}: syntax error: {exc}"); continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for alias in node.names:
                    root=alias.name.split(".",1)[0]
                    if root in NETWORK_IMPORTS: errors.append(f"{path}: runtime helper imports network module {alias.name}")
            elif isinstance(node,ast.ImportFrom) and node.module:
                root=node.module.split(".",1)[0]
                if root in NETWORK_IMPORTS: errors.append(f"{path}: runtime helper imports network module {node.module}")
            elif isinstance(node,ast.Call):
                name=dotted(node.func)
                if name in DANGEROUS_CALLS: errors.append(f"{path}: dangerous call {name}")
                if name in {"subprocess.run","subprocess.call","subprocess.check_call","subprocess.check_output"}:
                    for kw in node.keywords:
                        if kw.arg=="shell" and isinstance(kw.value,ast.Constant) and kw.value.value is True: errors.append(f"{path}: subprocess shell=True is prohibited")
        if "followlinks=True" in path.read_text(encoding="utf-8",errors="replace"): errors.append(f"{path}: follows directory symlinks")
def secret_scan(root:Path,errors:list)->None:
    ignored={".git",".venv","dist","build","__pycache__","eval-workspaces"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or any(part in ignored for part in path.relative_to(root).parts): continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"LICENSE",".gitignore"}: continue
        if path.stat().st_size>1_000_000: continue
        text=path.read_text(encoding="utf-8",errors="ignore")
        for label,pattern in SECRET_PATTERNS.items():
            if pattern.search(text): errors.append(f"{path.relative_to(root)}: secret-like {label} pattern detected")
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("root",nargs="?",default="."); args=ap.parse_args(); root=Path(args.root).resolve(); skill_root=root/"universal-project-governance"; errors=[]; warnings=[]
    if not skill_root.is_dir(): errors.append("installable Skill directory missing")
    else: audit_runtime_scripts(skill_root,errors,warnings)
    secret_scan(root,errors)
    for w in warnings: print(f"warning: {w}")
    for e in errors: print(f"error: {e}",file=sys.stderr)
    if errors: return 1
    print("Security audit passed: no network imports, shell=True, dangerous dynamic execution, symlink-following, or secret-like token patterns detected in governed surfaces."); return 0
if __name__=="__main__": raise SystemExit(main())
