#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT_NAMES = {"VERSION.md", "LICENSE"}
RUNTIME_EXCLUDE = {"integrity/manifest.json"}

def canonical(obj):
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def hash_paths(paths, root):
    parts = []
    for raw in sorted((pathlib.Path(p) for p in paths), key=lambda p: p.relative_to(root).as_posix()):
        if raw.is_dir():
            files = sorted((x for x in raw.rglob("*") if x.is_file() and "__pycache__" not in x.parts and x.suffix not in {".pyc", ".pyo"}), key=lambda p: p.relative_to(root).as_posix())
        else:
            files = [raw]
        for path in files:
            parts.append(path.relative_to(root).as_posix().encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return sha(b"".join(parts))

def file_tree_hash(root):
    root = pathlib.Path(root)
    parts = []
    for path in sorted((x for x in root.rglob("*") if x.is_file() and "__pycache__" not in x.parts and x.suffix not in {".pyc", ".pyo"}), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        parts.append(rel.encode() + b"\0" + path.read_bytes() + b"\0")
    return sha(b"".join(parts))

def normalize_skill(text):
    return re.sub(
        r'(^\s{2}version:\s*["\']).*?(["\']\s*$)',
        r'\1<BEHAVIOR_VERSION>\2',
        text,
        flags=re.M,
    )

def behavioral_payload(runtime):
    runtime = pathlib.Path(runtime)
    payload = {}
    for path in sorted((x for x in runtime.rglob("*") if x.is_file() and "__pycache__" not in x.parts and x.suffix not in {".pyc", ".pyo"}), key=lambda p: p.relative_to(runtime).as_posix()):
        rel = path.relative_to(runtime).as_posix()
        if rel in RUNTIME_EXCLUDE or rel in ROOT_NAMES:
            continue
        if rel == "SKILL.md":
            payload[rel] = normalize_skill(path.read_text(encoding="utf-8"))
        elif rel == "policy-index.json":
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj.pop("version", None)
            obj.pop("source_sha256", None)
            payload[rel] = obj
        else:
            payload[rel] = path.read_text(encoding="utf-8", errors="replace")
    return payload

def behavioral_fingerprint(runtime):
    return "sha256:" + sha(canonical(behavioral_payload(runtime)))

def expected(root):
    root = pathlib.Path(root).resolve()
    model = json.loads(
        (root / "governance-src/model/governance-model.json").read_text(
            encoding="utf-8"
        )
    )
    runtime = root / "universal-project-governance"

    protocol_hash = hash_paths([root / "qualification/protocol"], root)
    fixture_hash = hash_paths([root / "qualification/fixtures"], root)
    evaluator_hash = hash_paths([
        root / "qualification/analysis",
        root / "qualification/graders",
        root / "qualification/lib",
        root / "qualification/mutations",
    ], root)
    runner_hash = hash_paths([
        root / "qualification/adapters",
        root / "qualification/run_trial.py",
        root / "qualification/run_handoff_trial.py",
        root / "qualification/run_trigger_trial.py",
        root / "qualification/trigger_suite.py",
        root / "qualification/dev_smoke.py",
        root / "qualification/analyze.py",
        root / "qualification/round_manifest.py",
    ], root)
    deployment_hash = hash_paths([root / "upg.py"], root)
    behavior = behavioral_fingerprint(runtime)
    qualification_payload = {
        "hash_algorithm_revision": "repo-relative-posix-v2",
        "identity_tool_sha256": sha(pathlib.Path(__file__).read_bytes()),
        "canonical_source_sha256": file_tree_hash(root / "governance-src"),
        "compiler_sha256": sha((root / "compiler/compile_governance.py").read_bytes()),
        "behavioral_fingerprint": behavior,
        "protocol_sha256": protocol_hash,
        "fixture_set_sha256": fixture_hash,
        "evaluator_sha256": evaluator_hash,
        "runner_sha256": runner_hash,
        "deployment_sha256": deployment_hash,
    }

    return {
        "schema_version": 3,
        "hash_algorithm_revision": "repo-relative-posix-v2",
        "version": model["version"],
        "state": "real-agent-test-freeze",
        "behavioral_fingerprint": behavior,
        "qualification_fingerprint": "sha256:" + sha(canonical(qualification_payload)),
        "governance_model_sha256": "sha256:" + sha(
            (root / "governance-src/model/governance-model.json").read_bytes()
        ),
        "compiler_sha256": "sha256:" + sha(
            (root / "compiler/compile_governance.py").read_bytes()
        ),
        "runtime_tree_sha256": "sha256:" + file_tree_hash(runtime),
        "qualification_protocol_sha256": "sha256:" + protocol_hash,
        "fixture_set_sha256": "sha256:" + fixture_hash,
        "evaluator_sha256": "sha256:" + evaluator_hash,
        "runner_sha256": "sha256:" + runner_hash,
        "deployment_sha256": "sha256:" + deployment_hash,
        "frozen_surfaces": [
            "governance-src",
            "compiler",
            "universal-project-governance",
            "upg.py",
            "qualification/protocol",
            "qualification/fixtures",
            "qualification/analysis",
            "qualification/graders",
            "qualification/lib",
            "qualification/mutations",
            "qualification/adapters",
            "qualification/run_trial.py",
            "qualification/run_handoff_trial.py",
            "qualification/run_trigger_trial.py",
            "qualification/trigger_suite.py",
            "qualification/dev_smoke.py",
            "qualification/analyze.py",
            "qualification/round_manifest.py",
        ],
        "allowed_post_freeze_changes": [
            "immutable qualification result rounds",
            "documentation corrections that do not change frozen semantics",
            "external adapter instances/configuration that satisfy the frozen adapter contract",
        ],
        "freeze_invalidation": (
            "Any change to a frozen surface requires a new qualification fingerprint "
            "and invalidates unfinished/claimed evidence under the prior fingerprint."
        ),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--confirm-freeze", action="store_true")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    path = root / "qualification/FREEZE.json"
    exp = expected(root)
    if args.write:
        if not args.confirm_freeze:
            print("error: --write requires --confirm-freeze", file=sys.stderr)
            return 2
        path.write_bytes((json.dumps(exp, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        print("Real-agent test freeze written.")
        return 0
    if not path.is_file():
        print("error: qualification/FREEZE.json missing", file=sys.stderr)
        return 1
    got = json.loads(path.read_text(encoding="utf-8"))
    if got != exp:
        print("error: qualification freeze drift detected", file=sys.stderr)
        return 1
    print("Real-agent test freeze check passed: %s" % exp["qualification_fingerprint"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
