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

def hash_paths(paths):
    parts = []
    for raw in sorted(pathlib.Path(p) for p in paths):
        if raw.is_dir():
            files = sorted(x for x in raw.rglob("*") if x.is_file())
        else:
            files = [raw]
        for path in files:
            parts.append(path.as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return sha(b"".join(parts))

def file_tree_hash(root):
    root = pathlib.Path(root)
    parts = []
    for path in sorted(x for x in root.rglob("*") if x.is_file()):
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
    for path in sorted(x for x in runtime.rglob("*") if x.is_file()):
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

    protocol_hash = hash_paths([root / "qualification/protocol"])
    fixture_hash = hash_paths([root / "qualification/fixtures"])
    evaluator_hash = hash_paths([
        root / "qualification/analysis",
        root / "qualification/graders",
        root / "qualification/lib",
        root / "qualification/mutations",
    ])
    runner_hash = hash_paths([
        root / "qualification/adapters",
        root / "qualification/run_trial.py",
        root / "qualification/run_handoff_trial.py",
        root / "qualification/run_trigger_trial.py",
        root / "qualification/trigger_suite.py",
        root / "qualification/analyze.py",
    ])
    behavior = behavioral_fingerprint(runtime)
    qualification_payload = {
        "behavioral_fingerprint": behavior,
        "protocol_sha256": protocol_hash,
        "fixture_set_sha256": fixture_hash,
        "evaluator_sha256": evaluator_hash,
        "runner_sha256": runner_hash,
    }

    return {
        "schema_version": 2,
        "version": model["version"],
        "state": "qualification-freeze",
        "behavioral_fingerprint": behavior,
        "qualification_fingerprint": "sha256:" + sha(
            canonical(qualification_payload)
        ),
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
        "frozen_surfaces": [
            "governance-src",
            "compiler",
            "universal-project-governance",
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
            "qualification/analyze.py",
        ],
        "allowed_post_freeze_changes": [
            "immutable qualification result rounds",
            "documentation corrections that do not change frozen semantics",
        ],
        "freeze_invalidation": (
            "Any change to a frozen surface requires a new qualification "
            "fingerprint and a new result round."
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
            print(
                "error: --write requires --confirm-freeze",
                file=sys.stderr,
            )
            return 2
        path.write_text(
            json.dumps(exp, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("Qualification freeze written.")
        return 0

    if not path.is_file():
        print("error: qualification/FREEZE.json missing", file=sys.stderr)
        return 1

    got = json.loads(path.read_text(encoding="utf-8"))
    if got != exp:
        print(
            "error: qualification freeze drift detected",
            file=sys.stderr,
        )
        return 1

    print(
        "Qualification freeze check passed: %s"
        % exp["qualification_fingerprint"]
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
