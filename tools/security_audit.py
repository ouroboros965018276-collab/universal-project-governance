#!/usr/bin/env python3
"""Conservative static security audit for the repository and distributed runtime helpers."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,re,sys
from pathlib import Path
NETWORK_IMPORTS={"socket","urllib","http","ftplib","smtplib","requests","httpx","aiohttp"}; DANGEROUS_CALLS={"eval","exec","compile","os.system","subprocess.Popen","pickle.loads","marshal.loads"}
SECRET_PATTERNS={"private-key":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),"github-pat":re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),"aws-access-key":re.compile(r"\bAKIA[0-9A-Z]{16}\b"),"bearer-token":re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}\b",re.I)}
TEXT_SUFFIXES={".md",".txt",".py",".json",".yaml",".yml",".toml",".ini",".cfg"}
def dotted(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        left=dotted(node.value); return f"{left}.{node.attr}" if left else node.attr
    return ""
# Normalize transparent Python 3.8 Index wrappers and the empty type_params
# field added in 3.12. JSON keeps all remaining labelled AST fields stable.
def portable_ast(value):
    if isinstance(value, ast.AST):
        if type(value).__name__ == "Index": return portable_ast(value.value)
        fields = {name: portable_ast(getattr(value, name, None)) for name in value._fields
                  if not (name == "type_params" and getattr(value, name, None) == [])}
        return [type(value).__name__, fields]
    if isinstance(value, list): return [portable_ast(item) for item in value]
    return value

def worker_launch_digest(fn):
    return hashlib.sha256(json.dumps(portable_ast(fn), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()

# This pins own-script argv, detached flags, DEVNULL I/O and shell=False;
# no general process-launch exception is granted.
OWN_WORKER_LAUNCH_SHA256 = "f27a6b3b4c98d5e5e7196c2565c0d6b3453b8f784de39252cff0935f927583e2"

OWN_GUARDED_LAUNCH_SHA256 = "5b5675ef5434a823860eb5c95030ecedfb73b76cede230b8f5c62e21ef8060ce"

OWN_SUPERVISOR_LAUNCH_SHA256 = "f18b40e98ce5eb1d444da5831da8d74a6b29d518e9d53bd3223a5fd8ce5406a9"

def approved_worker_launch(path, tree, node):
    reviewed = {("git_watch.py", "_spawn_worker"): OWN_WORKER_LAUNCH_SHA256,
                ("git_watch.py", "_spawn_supervisor"): OWN_SUPERVISOR_LAUNCH_SHA256,
                ("process_guard.py", "_spawn_guarded"): OWN_GUARDED_LAUNCH_SHA256}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and node in ast.walk(fn):
            expected = reviewed.get((path.name, fn.name))
            return expected is not None and worker_launch_digest(fn) == expected
    return False

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
                if name in DANGEROUS_CALLS and not (name == "subprocess.Popen" and approved_worker_launch(path, tree, node)): errors.append(f"{path}: dangerous call {name}")
                if name in {"subprocess.run","subprocess.call","subprocess.check_call","subprocess.check_output"}:
                    for kw in node.keywords:
                        if kw.arg=="shell" and isinstance(kw.value,ast.Constant) and kw.value.value is True: errors.append(f"{path}: subprocess shell=True is prohibited")
        if "followlinks=True" in path.read_text(encoding="utf-8",errors="replace"): errors.append(f"{path}: follows directory symlinks")
def secret_scan(root:Path,errors:list)->None:
    ignored={".git",".venv","dist","build","__pycache__","eval-workspaces"}
    paths=[]; pending=[root] if root.is_dir() else []
    while pending:
        directory=pending.pop()
        entries=os.scandir(directory)
        directories=[]
        with entries:
            for entry in entries:
                path=directory/entry.name
                paths.append(path)
                if entry.name in ignored: continue
                is_dir=entry.is_dir(follow_symlinks=False)
                if is_dir: directories.append(path)
        pending.extend(reversed(directories))
    for path in sorted(paths):
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
    print("Security audit passed: no network imports, shell=True, unapproved dynamic execution, symlink-following, or secret-like token patterns detected in governed surfaces."); return 0
if __name__=="__main__": raise SystemExit(main())
