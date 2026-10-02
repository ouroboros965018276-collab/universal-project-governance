#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,pathlib,re,sys

ROOT_NAMES={"VERSION.md","LICENSE"}
EXCLUDE={"integrity/manifest.json"}

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_tree_hash(root,include=None):
    root=pathlib.Path(root); parts=[]
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        rel=p.relative_to(root).as_posix()
        if include and not include(rel): continue
        parts.append(rel.encode()+b"\0"+p.read_bytes()+b"\0")
    return sha(b"".join(parts))

def normalize_skill(text):
    return re.sub(r'(^\s{2}version:\s*["\']).*?(["\']\s*$)',r'\1<BEHAVIOR_VERSION>\2',text,flags=re.M)

def behavioral_payload(runtime):
    runtime=pathlib.Path(runtime); payload={}
    for p in sorted(x for x in runtime.rglob("*") if x.is_file()):
        rel=p.relative_to(runtime).as_posix()
        if rel in EXCLUDE or rel in ROOT_NAMES: continue
        if rel=="SKILL.md":
            payload[rel]=normalize_skill(p.read_text(encoding="utf-8"))
        elif rel=="policy-index.json":
            obj=json.loads(p.read_text(encoding="utf-8")); obj.pop("version",None); obj.pop("source_sha256",None); payload[rel]=obj
        else:
            payload[rel]=p.read_text(encoding="utf-8",errors="replace")
    return payload

def behavioral_fingerprint(runtime):
    return "sha256:"+sha(canonical(behavioral_payload(runtime)))

def hash_paths(paths):
    parts=[]
    for p in sorted(pathlib.Path(x) for x in paths):
        if p.is_dir():
            for f in sorted(x for x in p.rglob("*") if x.is_file()):
                parts.append(f.as_posix().encode()+b"\0"+f.read_bytes()+b"\0")
        else:
            parts.append(p.as_posix().encode()+b"\0"+p.read_bytes()+b"\0")
    return sha(b"".join(parts))

def expected(root):
    root=pathlib.Path(root).resolve()
    model=json.loads((root/"governance-src/model/governance-model.json").read_text(encoding="utf-8"))
    runtime=root/"universal-project-governance"
    protocol_paths=[root/"qualification/protocol"]
    fixture_paths=[root/"qualification/fixtures"]
    grader_paths=[root/"qualification/graders",root/"qualification/lib/core.py"]
    adapter_paths=[root/"qualification/adapters",root/"qualification/run_trial.py"]
    protocol_hash=hash_paths(protocol_paths)
    fixture_hash=hash_paths(fixture_paths)
    grader_hash=hash_paths(grader_paths)
    adapter_hash=hash_paths(adapter_paths)
    behavior=behavioral_fingerprint(runtime)
    q_payload={"behavioral_fingerprint":behavior,"protocol_sha256":protocol_hash,"fixture_set_sha256":fixture_hash,"grader_sha256":grader_hash,"adapter_contract_sha256":adapter_hash}
    return {
      "schema_version":1,"version":model["version"],"state":"qualification-freeze",
      "behavioral_fingerprint":behavior,
      "qualification_fingerprint":"sha256:"+sha(canonical(q_payload)),
      "governance_model_sha256":"sha256:"+sha((root/"governance-src/model/governance-model.json").read_bytes()),
      "compiler_sha256":"sha256:"+sha((root/"compiler/compile_governance.py").read_bytes()),
      "runtime_tree_sha256":"sha256:"+file_tree_hash(runtime),
      "qualification_protocol_sha256":"sha256:"+protocol_hash,
      "fixture_set_sha256":"sha256:"+fixture_hash,
      "grader_sha256":"sha256:"+grader_hash,
      "adapter_contract_sha256":"sha256:"+adapter_hash,
      "frozen_surfaces":["governance-src/model","governance-src/profiles","governance-src/runtime-scripts","governance-src/schemas","governance-src/templates","compiler","universal-project-governance"],
      "allowed_post_freeze_changes":["qualification results","non-semantic runner bug fixes with qualification invalidation review","grader calibration in a new qualification round","new external agent adapters","development eval expansion","documentation corrections"],
      "forbidden_post_freeze_changes":["new policy IDs","hot-path semantic changes","risk semantic changes","handoff semantic changes","report semantic changes","compiler contract changes","runtime capability expansion"]
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("root",nargs="?",default="."); g=ap.add_mutually_exclusive_group(required=True); g.add_argument("--write",action="store_true"); g.add_argument("--check",action="store_true"); ap.add_argument("--confirm-freeze",action="store_true"); args=ap.parse_args()
    root=pathlib.Path(args.root).resolve(); path=root/"qualification/FREEZE.json"; exp=expected(root)
    if args.write:
        if not args.confirm_freeze: print("error: --write requires --confirm-freeze",file=sys.stderr); return 2
        path.write_text(json.dumps(exp,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print("Qualification freeze written."); return 0
    if not path.is_file(): print("error: qualification/FREEZE.json missing",file=sys.stderr); return 1
    got=json.loads(path.read_text(encoding="utf-8"))
    if got!=exp:
        print("error: qualification freeze drift detected",file=sys.stderr); return 1
    print("Qualification freeze check passed: %s" % exp["qualification_fingerprint"]); return 0
if __name__=="__main__": raise SystemExit(main())
