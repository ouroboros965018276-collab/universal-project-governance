#!/usr/bin/env python3
"""Compile a typed task context into the smallest applicable governance execution plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPORT_ORDER = {"none": 0, "change-note": 1, "engineering": 2, "audit": 3}


def load_index() -> dict:
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "policy-index.json").read_text(encoding="utf-8"))


def normalize_context(args: argparse.Namespace) -> dict:
    if args.context:
        data = json.loads(Path(args.context).read_text(encoding="utf-8"))
    else:
        risk = {}
        for item in args.risk:
            if "=" not in item:
                raise ValueError("--risk expects key=0|1|2")
            key, raw = item.split("=", 1)
            value = int(raw)
            if value < 0 or value > 2:
                raise ValueError("risk values must be 0..2")
            risk[key] = value
        data = {
            "operation": args.operation,
            "domains": args.domain or ["code"],
            "signals": args.signal or [],
            "profiles": args.profile or [],
            "unfinished": args.unfinished,
            "explicit_audit": args.audit,
            "risk": risk,
        }
    data.setdefault("signals", [])
    data.setdefault("profiles", [])
    data.setdefault("unfinished", False)
    data.setdefault("explicit_audit", False)
    data.setdefault("risk", {})
    return data


def validate_context(ctx: dict, index: dict) -> None:
    allowed_ops = set(index["task_contract"]["operations"])
    allowed_domains = set(index["task_contract"]["domains"])
    if ctx.get("operation") not in allowed_ops:
        raise ValueError("unknown operation: %r" % ctx.get("operation"))
    if not isinstance(ctx.get("domains"), list) or any(x not in allowed_domains for x in ctx["domains"]):
        raise ValueError("domains must be a list of known domain IDs")
    dims = index["risk_model"]["dimensions"]
    for key, value in ctx.get("risk", {}).items():
        if key not in dims or not isinstance(value, int) or value < 0 or value > dims[key]["max"]:
            raise ValueError("invalid risk dimension/value: %s=%r" % (key, value))


def trigger_matches(policy: dict, ctx: dict) -> bool:
    t = policy["triggers"]
    return (
        ctx["operation"] in t.get("operations", [])
        or bool(set(ctx["domains"]) & set(t.get("domains", [])))
        or bool(set(ctx.get("signals", [])) & set(t.get("signals", [])))
    )


def risk(index: dict, ctx: dict):
    score = 0
    for key, spec in index["risk_model"]["dimensions"].items():
        score += int(ctx.get("risk", {}).get(key, 0)) * int(spec["weight"])
    if ctx["operation"] == "release":
        return "release", score, "audit"
    level = "high"
    report = "engineering"
    for item in index["risk_model"]["levels"]:
        if item["min"] <= score <= item["max"]:
            level, report = item["id"], item["report"]
            break
    return level, score, report


def compile_plan(index: dict, ctx: dict) -> dict:
    validate_context(ctx, index)
    policies = {p["id"]: p for p in index["policies"]}
    active = set(index["default_rules"])

    for p in index["policies"]:
        if trigger_matches(p, ctx):
            active.add(p["id"])

    for profile_id in ctx.get("profiles", []):
        profile = index["profiles"].get(profile_id)
        if profile is None:
            raise ValueError("unknown profile: %s" % profile_id)
        active.update(profile.get("activates", []))

    if ctx.get("unfinished") or "handoff" in ctx.get("signals", []) or "unfinished" in ctx.get("signals", []):
        active.add("HANDOFF_CONTINUITY")

    stack = list(active)
    while stack:
        rule_id = stack.pop()
        if rule_id not in policies:
            raise ValueError("policy closure references unknown rule: %s" % rule_id)
        for dep in policies[rule_id].get("requires", []):
            if dep not in active:
                active.add(dep)
                stack.append(dep)

    risk_level, risk_score, report = risk(index, ctx)
    handoff = "required" if ctx.get("unfinished") else "not-required"
    evidence = []
    closures = []
    warnings = []

    for rule_id in sorted(active):
        p = policies[rule_id]
        closures.append("%s: %s" % (rule_id, p["closure"]))
        for item in p.get("evidence", []):
            if item not in evidence:
                evidence.append(item)
        pref = p.get("report", "inherit")
        if pref != "inherit" and REPORT_ORDER[pref] > REPORT_ORDER[report]:
            report = pref
        hp = p.get("handoff", "inherit")
        if hp == "required" or (hp == "if_unfinished" and ctx.get("unfinished")):
            handoff = "required"

    if ctx.get("explicit_audit"):
        report = "audit"

    budget = index["complexity_budget"]["default_active_policies_max"]
    if risk_level in {"trivial", "low"} and len(active) > budget:
        warnings.append("low-risk plan activates %d policies; default budget is %d" % (len(active), budget))

    return {
        "version": index["version"],
        "risk_level": risk_level,
        "risk_score": risk_score,
        "active_rules": sorted(active),
        "required_closures": closures,
        "evidence": evidence,
        "report": report,
        "handoff": handoff,
        "warnings": warnings,
    }


def render_markdown(plan: dict) -> str:
    lines = [
        "# Governance Plan",
        "",
        "- **Risk:** %s (%s)" % (plan["risk_level"], plan["risk_score"]),
        "- **Report:** %s" % plan["report"],
        "- **Handoff:** %s" % plan["handoff"],
        "",
        "## Active rules",
    ]
    lines += ["- " + x for x in plan["active_rules"]]
    lines += ["", "## Required closure"]
    lines += ["- " + x for x in plan["required_closures"]]
    lines += ["", "## Evidence"]
    lines += ["- " + x for x in plan["evidence"]]
    if plan["warnings"]:
        lines += ["", "## Warnings"] + ["- " + x for x in plan["warnings"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context")
    ap.add_argument("--operation", default="edit")
    ap.add_argument("--domain", action="append", default=[])
    ap.add_argument("--signal", action="append", default=[])
    ap.add_argument("--profile", action="append", default=[])
    ap.add_argument("--risk", action="append", default=[])
    ap.add_argument("--unfinished", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        index = load_index()
        ctx = normalize_context(args)
        plan = compile_plan(index, ctx)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_markdown(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
