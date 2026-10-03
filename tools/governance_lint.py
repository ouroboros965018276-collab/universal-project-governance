#!/usr/bin/env python3
"""Deterministic static analysis and complexity gate for the canonical governance model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dependency_closure(start, by_id):
    seen = set()
    stack = list(start)
    while stack:
        item = stack.pop()
        if item in seen:
            continue
        seen.add(item)
        if item in by_id:
            stack.extend(by_id[item].get("requires", []))
    return seen


def find_cycle(by_id):
    visiting, done = set(), set()
    path = []
    def visit(node):
        if node in visiting:
            i = path.index(node)
            return path[i:] + [node]
        if node in done:
            return None
        visiting.add(node); path.append(node)
        for dep in by_id[node].get("requires", []):
            if dep in by_id:
                cycle = visit(dep)
                if cycle: return cycle
        path.pop(); visiting.remove(node); done.add(node)
        return None
    for node in sorted(by_id):
        cycle = visit(node)
        if cycle: return cycle
    return None


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("root", nargs="?", default="."); args = ap.parse_args()
    root = Path(args.root).resolve()
    model = load(root / "governance-src" / "model" / "governance-model.json")
    errors, warnings = [], []
    policies = model.get("policies", [])
    ids = [p.get("id") for p in policies]
    if len(ids) != len(set(ids)):
        errors.append("G001 duplicate policy ID")
    by_id = {p["id"]: p for p in policies if isinstance(p.get("id"), str)}
    for pid in ids:
        if not isinstance(pid, str) or not ID_RE.fullmatch(pid):
            errors.append("G002 invalid stable policy ID: %r" % pid)
    for p in policies:
        for dep in p.get("requires", []):
            if dep not in by_id:
                errors.append("G003 %s requires unknown rule %s" % (p["id"], dep))
        for other in p.get("conflicts_with", []):
            if other not in by_id:
                errors.append("G004 %s conflicts with unknown rule %s" % (p["id"], other))
        if p.get("severity") == "blocking" and not p.get("evidence"):
            errors.append("G005 blocking rule %s has no evidence contract" % p["id"])
        if not p.get("eval_tags"):
            errors.append("G006 rule %s has no eval coverage tags" % p["id"])

    cycle = find_cycle(by_id)
    if cycle:
        errors.append("G007 policy dependency cycle: " + " -> ".join(cycle))

    entries = set(model.get("default_rules", []))
    structural = model.get("structural_integration", {})
    structural_policy = structural.get("policy_id")
    if structural_policy:
        if structural_policy not in by_id:
            errors.append("G017 structural integration references unknown rule %s" % structural_policy)
        else:
            entries.add(structural_policy)
    if structural.get("minimum_risk_level") not in {"trivial","low","medium","high"}:
        errors.append("G018 invalid structural-integration minimum risk level")
    for p in policies:
        t = p.get("triggers", {})
        if any(t.get(k) for k in ("operations","domains","signals")):
            entries.add(p["id"])
    profile_dir = root / "governance-src" / "profiles"
    for path in sorted(profile_dir.glob("*.json")):
        profile = load(path)
        for rid in profile.get("activates", []):
            if rid not in by_id:
                errors.append("G008 profile %s references unknown rule %s" % (profile.get("id"), rid))
            else:
                entries.add(rid)
    reachable = dependency_closure(entries, by_id)
    orphan = sorted(set(by_id) - reachable)
    if orphan:
        errors.append("G009 orphan policies: " + ", ".join(orphan))

    budget = model["complexity_budget"]
    if len(model.get("hot_path", [])) > budget["hot_path_max"]:
        errors.append("G010 hot-path invariant budget exceeded")
    default_closure = dependency_closure(model.get("default_rules", []), by_id)
    if len(default_closure) > budget["default_active_policies_max"]:
        errors.append("G011 default active-policy budget exceeded: %d > %d" % (len(default_closure), budget["default_active_policies_max"]))

    for p in policies:
        closure = dependency_closure([p["id"]], by_id)
        for rid in closure:
            conflicts = set(by_id[rid].get("conflicts_with", []))
            hit = conflicts & closure
            if hit:
                errors.append("G012 conflicting rule closure for %s: %s" % (p["id"], ", ".join(sorted(hit))))

    fingerprints = {}
    for p in policies:
        fp = json.dumps({
            "kind":p.get("kind"),"requires":sorted(p.get("requires",[])),
            "applies_to":sorted(p.get("applies_to",[])),"evidence":sorted(p.get("evidence",[])),
            "closure":" ".join(p.get("closure","").lower().split())
        },sort_keys=True)
        if fp in fingerprints:
            warnings.append("G101 semantic duplicate candidate: %s and %s" % (fingerprints[fp], p["id"]))
        fingerprints[fp] = p["id"]

    runtime = root / "universal-project-governance"
    skill = runtime / "SKILL.md"
    if skill.is_file():
        lines = len(skill.read_text(encoding="utf-8").splitlines())
        if lines > budget["runtime_skill_max_lines"]:
            errors.append("G013 runtime SKILL.md budget exceeded: %d > %d" % (lines, budget["runtime_skill_max_lines"]))
        md_count = len([p for p in runtime.rglob("*.md") if p.is_file()])
        if md_count > budget["runtime_markdown_files_max"]:
            errors.append("G014 runtime Markdown-file budget exceeded: %d > %d" % (md_count, budget["runtime_markdown_files_max"]))
        if (runtime / "references").exists():
            errors.append("G015 compiled runtime must not contain references/ document tree")
        if (runtime / "assets").exists():
            errors.append("G016 compiled runtime must not contain Markdown/template assets")

    for w in warnings: print("warning: " + w)
    for e in errors: print("error: " + e, file=sys.stderr)
    if errors: return 1
    print("Governance lint passed: %d policies, %d hot-path invariants, default closure %d, %d advisory warning(s)." % (len(policies), len(model["hot_path"]), len(default_closure), len(warnings)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
