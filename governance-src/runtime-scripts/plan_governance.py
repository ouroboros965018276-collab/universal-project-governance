#!/usr/bin/env python3
"""Compile a typed task context into the smallest applicable governance execution plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from project_tool import status as project_status, validate_node

REPORT_ORDER = {"none": 0, "change-note": 1, "engineering": 2, "audit": 3}


def load_index() -> dict:
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / "policy-index.json").read_text(encoding="utf-8"))


def normalize_context(args: argparse.Namespace) -> dict:
    if args.context:
        if (args.operation is not None or args.domain or args.signal or args.profile
                or args.risk or args.unfinished or args.audit):
            raise ValueError("--context cannot be combined with task normalization flags")
        data = json.loads(Path(args.context).read_text(encoding="utf-8-sig"))
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
            "operation": args.operation or "edit",
            "domains": args.domain or ["code"],
            "signals": args.signal or [],
            "profiles": args.profile or [],
            "unfinished": args.unfinished,
            "explicit_audit": args.audit,
            "risk": risk,
        }
    if not isinstance(data, dict):
        raise ValueError("task context must be an object")
    data.setdefault("signals", [])
    data.setdefault("profiles", [])
    data.setdefault("unfinished", False)
    data.setdefault("explicit_audit", False)
    data.setdefault("risk", {})
    return data


def validate_context(ctx: dict, index: dict) -> None:
    if not isinstance(ctx, dict):
        raise ValueError("task context must be an object")
    dims = index["risk_model"]["dimensions"]
    risk_values = ctx.get("risk", {})
    if isinstance(risk_values, dict):
        for key, value in risk_values.items():
            if key not in dims:
                raise ValueError(
                    "unknown risk dimension: %s (expected one of: %s)"
                    % (key, ", ".join(sorted(dims)))
                )
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "task-context.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_node(ctx, schema)
    if errors:
        raise ValueError("invalid task context: " + "; ".join(errors))


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
        return "release", score, index["risk_model"]["release_operation_forces"]
    level = "high"
    report = "engineering"
    for item in index["risk_model"]["levels"]:
        if item["min"] <= score <= item["max"]:
            level, report = item["id"], item["report"]
            break
    return level, score, report


def operational_closures(index: dict, active: set, field_reporting: bool, report: str) -> list:
    """Read only source-derived blocks selected by existing policy/report state."""
    import re
    groups = index.get("operational_guidance", [])
    if not isinstance(groups, list):
        raise ValueError("invalid operational guidance")
    policy_ids = {policy["id"] for policy in index["policies"]}
    seen, result = set(), []
    for group in groups:
        if (not isinstance(group, dict)
                or set(group) != {"id", "policy_ids", "on_field_reporting", "report_levels", "statement"}):
            raise ValueError("invalid operational guidance block")
        identity, targets, statement = group["id"], group["policy_ids"], group["statement"]
        levels = group["report_levels"]
        if (not isinstance(identity, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", identity) is None
                or identity in seen or not isinstance(targets, list) or not targets
                or any(not isinstance(item, str) or item not in policy_ids for item in targets)
                or len(set(targets)) != len(targets) or type(group["on_field_reporting"]) is not bool
                or not isinstance(levels, list)
                or any(not isinstance(level, str) or level not in REPORT_ORDER for level in levels)
                or len(set(levels)) != len(levels)
                or not isinstance(statement, str) or not statement.strip()):
            raise ValueError("invalid operational guidance routing")
        seen.add(identity)
        if set(targets) & active or report in levels or (group["on_field_reporting"] and field_reporting):
            result.append("Operational %s: %s" % (identity, statement))
    return result


def compile_plan(index: dict, ctx: dict) -> dict:
    validate_context(ctx, index)
    policies = {p["id"]: p for p in index["policies"]}
    if len(policies) != len(index["policies"]):
        raise ValueError("duplicate policy ID in policy index")
    risk_level, risk_score, report = risk(index, ctx)
    active = set(index["default_rules"])

    structural = index["structural_integration"]
    risk_rank = {"trivial": 0, "low": 1, "medium": 2, "high": 3, "release": 4}
    structural_required = (
        ctx["operation"] not in set(structural.get("exempt_operations", []))
        and (
            ctx["operation"] in set(structural.get("force_operations", []))
            or risk_rank[risk_level] >= risk_rank[structural["minimum_risk_level"]]
        )
    )
    if structural_required:
        active.add(structural["policy_id"])

    for p in index["policies"]:
        if trigger_matches(p, ctx):
            active.add(p["id"])

    for profile_id in ctx.get("profiles", []):
        profile = index["profiles"].get(profile_id)
        if profile is None:
            continue  # Unknown project hints retain the universal task/risk closure.
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

    handoff = "required" if ctx.get("unfinished") else "not-required"
    evidence = []
    closures = []
    warnings = []
    unknown_profiles = sorted(set(ctx.get("profiles", [])) - set(index["profiles"]))
    if unknown_profiles:
        warnings.append("unknown optional profiles use universal task/risk rules: " + ", ".join(unknown_profiles))
    assessed_risk = ctx.get("risk", {})
    missing_risk = sorted(set(index["risk_model"]["dimensions"]) - set(assessed_risk))
    if missing_risk:
        assessment = "partially assessed" if assessed_risk else "unassessed"
        warnings.append(
            "risk %s; missing dimensions: %s; level/score are provisional (known facts only), not confirmed risk"
            % (assessment, ", ".join(missing_risk))
        )

    order = index.get("presentation", {}).get("policy_order", sorted(policies))
    if not isinstance(order, list) or len(order) != len(policies) or set(order) != set(policies):
        raise ValueError("invalid presentation policy permutation")
    for rule_id in (rid for rid in order if rid in active):
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

    closures.extend(operational_closures(index, active, ctx.get("field_test_reporting",
        index.get("project_binding", {}).get("field_test_reporting")) is True, report))

    plan = {
        "version": index["version"],
        "change_mode": "structural" if structural["policy_id"] in active else "local",
        "scope_guard": structural["scope_guard"] if structural["policy_id"] in active else "local-only",
        "risk_level": risk_level,
        "risk_score": risk_score,
        "active_rules": sorted(active),
        "required_closures": closures,
        "evidence": evidence,
        "report": report,
        "field_report_obligation": (
            "required-before-completion"
            if ctx.get(
                "field_test_reporting",
                index.get("project_binding", {}).get("field_test_reporting"),
            ) is True
            else "not-required"
        ),
        "field_report_file": index.get("project_binding", {}).get("field_report_file"),
        "handoff": handoff,
        "warnings": warnings,
    }
    continuity = policies.get("HANDOFF_CONTINUITY")
    if continuity is None:
        raise ValueError("policy index is missing HANDOFF_CONTINUITY")
    if set(ctx.get("signals", [])) & set(continuity["triggers"].get("signals", [])):
        # Explicit sibling loading also supports hosts importing this script by path.
        import importlib.util
        spec = importlib.util.spec_from_file_location("_upg_project_facts", Path(__file__).with_name("project_facts.py"))
        if spec is None or spec.loader is None:
            raise ValueError("project fact recovery helper is unavailable")
        try:
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
        except (OSError, ImportError, AttributeError) as exc:
            raise ValueError("project fact recovery helper cannot load") from exc
        recovery = helper.recovery_plan(ctx.get("signals", []))
        if recovery is not None: plan["recovery"] = recovery
    return plan


def render_markdown(plan: dict) -> str:
    lines = [
        "# Governance Plan",
        "",
        "- **Risk:** %s (%s)" % (plan["risk_level"], plan["risk_score"]),
        "- **Change mode:** %s" % plan["change_mode"],
        "- **Scope guard:** %s" % plan["scope_guard"],
        "- **Report:** %s" % plan["report"],
        "- **Field report:** %s" % plan["field_report_obligation"],
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
    if "recovery" in plan:
        lines += ["", "## Project fact recovery (%s)" % plan["recovery"]["mode"]]
        lines += ["- " + x for x in plan["recovery"]["steps"] + plan["recovery"]["constraints"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context")
    ap.add_argument("--operation")
    ap.add_argument("--domain", action="append", default=[])
    ap.add_argument("--signal", action="append", default=[])
    ap.add_argument("--profile", action="append", default=[])
    ap.add_argument("--risk", action="append", default=[])
    ap.add_argument("--project-root", help="read the project binding to resolve field-report obligation")
    ap.add_argument("--unfinished", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        index = load_index()
        ctx = normalize_context(args)
        if args.project_root:
            state = project_status(args.project_root)
            if state.get("ok"):
                ctx["field_test_reporting"] = state["field_test_reporting"]
            elif state.get("reason") == "binding-missing":
                ctx["field_test_reporting"] = index.get("project_binding", {}).get("field_test_reporting", False)
            else:
                raise ValueError("project binding is not healthy: %s" % state.get("reason"))
        plan = compile_plan(index, ctx)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(plan, separators=(",", ":"), ensure_ascii=True))
    else:
        sys.stdout.write(render_markdown(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
