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
    if isinstance(value, bytes): return ["bytes", value.hex()]
    return value

def worker_launch_digest(fn):
    return hashlib.sha256(json.dumps(portable_ast(fn), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()

# This pins own-script argv, lifetime containment, ordinary stdio and shell=False;
# no general process-launch exception is granted.
OWN_WORKER_LAUNCH_SHA256 = "69019433c57ec60e10fe2eedea4c44a05093777d85392fdd37a2f5dcf90f884b"

OWN_GUARDED_LAUNCH_SHA256 = "4f35f93a7f55a9a68568c7356ed96ef937873b08c066bbd22d50c3b16ea2d21a"

OWN_SUPERVISOR_LAUNCH_SHA256 = "6d9700d22c0b7dc2066b522269ac9e932abf60c1bcd3d5c507c0d4b6f65047ab"

SESSION_MEMBER_LAUNCH_SHA256 = '71325c51e9ca58e11f4aded2eb124142daa312816abb881eae2e6d4d2303e66c'
SESSION_HOST_LAUNCH_SHA256 = '44b92c247494bd53147046305dc287da7a92e94d06e5d26ae897d537e4ae16e8'

# Review covers the bounded reader and its fixed, read-only Git-query caller.
# Altering command construction, scope, environment, timeout or stream bounds
# invalidates this exception; other Popen calls remain prohibited.
BOUNDED_GIT_QUERY_SHA256 = 'd7cb68c66a3f4ca01715922812b0247bc005796e41b7009a9b0c44ff3aa6357b'
BOUNDED_GIT_STATE_SHA256 = 'b43792f138ec528ab736f291ad670536f0715ad13f08b21077254c9474a98dbb'

def approved_worker_launch(path, tree, node):
    reviewed = {("git_watch.py", "_spawn_worker"): OWN_WORKER_LAUNCH_SHA256,
                ("git_watch.py", "_spawn_supervisor"): OWN_SUPERVISOR_LAUNCH_SHA256,
                ("process_guard.py", "_spawn_guarded"): OWN_GUARDED_LAUNCH_SHA256,
                ("project_facts.py", "_bounded_git_query"): BOUNDED_GIT_QUERY_SHA256,
                ("session_lifetime.py", "spawn"): SESSION_MEMBER_LAUNCH_SHA256,
                ("session_lifetime.py", "run_host"): SESSION_HOST_LAUNCH_SHA256}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and node in ast.walk(fn):
            expected = reviewed.get((path.name, fn.name))
            if path.name == "project_facts.py" and fn.name == "_bounded_git_query":
                caller = next((item for item in tree.body if isinstance(item, ast.FunctionDef)
                               and item.name == "git_state"), None)
                if caller is None or worker_launch_digest(caller) != BOUNDED_GIT_STATE_SHA256:
                    return False
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
