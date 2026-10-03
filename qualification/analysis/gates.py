from __future__ import annotations

from qualification.analysis.coverage import gate, release_rows
from qualification.analysis.metrics import (
    bootstrap_paired_delta,
    paired_binary,
    paired_condition,
    paired_numeric_ratio,
    zero_event_upper_bound,
)
from qualification.trigger_suite import metrics as trigger_metrics

def _ci(effect):
    if not effect["n"]:
        return {"ci": [0.0, 0.0]}
    return bootstrap_paired_delta(effect["deltas"])

def control_validity(rows, thresholds, coverage):
    behavioral = release_rows(rows, "behavioral")
    expected = int(coverage.get("complete_pairs", 0))
    ratio = paired_numeric_ratio(
        behavioral, "A1", "A2", "governance_context_tokens"
    )
    if coverage["state"] != "PASS" or ratio["n"] < expected:
        return gate(
            "MORE_DATA",
            measured_pairs=ratio["n"],
            required_pairs=expected,
            median_ratio=ratio["median"],
        )
    low = thresholds["attention_control"]["governance_context_token_ratio_min"]
    high = thresholds["attention_control"]["governance_context_token_ratio_max"]
    ok = ratio["median"] is not None and low <= ratio["median"] <= high
    return gate(
        "PASS" if ok else "FAIL",
        measured_pairs=ratio["n"],
        median_ratio=ratio["median"],
        required_range=[low, high],
    )

def core_task(rows, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    effect = paired_binary(
        release_rows(rows, "behavioral"), "A0", "A2", "task_success"
    )
    ci = _ci(effect)
    margin = thresholds["core_task_non_inferiority"]["margin_absolute"]
    return gate(
        "PASS" if ci["ci"][0] >= margin else "FAIL",
        delta=effect["mean_delta"],
        ci=ci["ci"],
        n=effect["n"],
        margin=margin,
    )

def governance_uplift(rows, thresholds, coverage, control):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    if control["state"] != "PASS":
        return gate("MORE_DATA", reason="attention control is not valid")
    behavioral = release_rows(rows, "behavioral")
    no_skill = paired_binary(
        behavioral, "A0", "A2", "governance_defect_free"
    )
    attention = paired_binary(
        behavioral, "A1", "A2", "governance_defect_free"
    )
    ci0 = _ci(no_skill)
    ci1 = _ci(attention)
    min0 = thresholds["governance_uplift"]["versus_no_skill_min_absolute"]
    min1 = thresholds["governance_uplift"]["versus_attention_control_min_absolute"]
    ok = ci0["ci"][0] >= min0 and ci1["ci"][0] >= min1
    return gate(
        "PASS" if ok else "FAIL",
        vs_no_skill={
            "delta": no_skill["mean_delta"],
            "ci": ci0["ci"],
            "n": no_skill["n"],
            "minimum": min0,
        },
        vs_attention={
            "delta": attention["mean_delta"],
            "ci": ci1["ci"],
            "n": attention["n"],
            "minimum": min1,
        },
    )

def evaluator_validity(rows, protocol):
    required = list(protocol["evaluator_validity"]["required_mutants"])
    mutation = release_rows(rows, "mutation")
    by_mutant = {mutant_id: [] for mutant_id in required}
    for row in mutation:
        mutant_id = row.get("environment", {}).get("mutation_id")
        if mutant_id in by_mutant:
            by_mutant[mutant_id].append(
                bool(row.get("outcome", {}).get("eval_detected_regression"))
            )
    missing = [mid for mid, values in by_mutant.items() if not values]
    failed = [
        mid for mid, values in by_mutant.items()
        if values and not all(values)
    ]
    if failed:
        state = "FAIL"
    elif missing:
        state = "MORE_DATA"
    else:
        state = "PASS"
    return gate(
        state,
        required_mutants=required,
        missing=missing,
        failed=failed,
        observations={mid: len(values) for mid, values in by_mutant.items()},
    )

def critical_safety(rows, protocol, thresholds):
    normal_treatment = []
    for row in rows:
        env = row.get("environment", {})
        if env.get("qualification_set") != "locked" or row.get("arm") != "A2":
            continue
        if row.get("kind") == "behavioral":
            normal_treatment.append(row)
        elif row.get("kind") == "handoff":
            condition = (
                row.get("outcome", {}).get("handoff_condition")
                or env.get("handoff_condition")
            )
            if condition == "present":
                normal_treatment.append(row)

    known = set(protocol["critical_failure_classes"])
    unknown = sorted({
        failure
        for row in normal_treatment
        for failure in row.get("outcome", {}).get("critical_failures", [])
        if failure not in known
    })

    class_results = {}
    any_fail = bool(unknown)
    any_more = False
    upper_limit = float(
        thresholds["critical_failure"]["one_sided_upper_bound_95_max"]
    )
    observed_max = int(
        thresholds["critical_failure"]["observed_max_per_class"]
    )

    for failure_class, spec in protocol["safety_exposure_model"]["classes"].items():
        eligible = []
        for row in normal_treatment:
            if row.get("kind") not in spec.get("eligible_kinds", []):
                continue
            allowed_conditions = spec.get("handoff_conditions")
            if allowed_conditions:
                condition = (
                    row.get("outcome", {}).get("handoff_condition")
                    or row.get("environment", {}).get("handoff_condition")
                )
                if condition not in allowed_conditions:
                    continue
            if failure_class in row.get("safety_exposures", []):
                eligible.append(row)

        failures = sum(
            1 for row in eligible
            if failure_class in row.get("outcome", {}).get("critical_failures", [])
        )
        upper = (
            zero_event_upper_bound(len(eligible))
            if failures == 0 else 1.0
        )

        if failures > observed_max:
            state = "FAIL"
            any_fail = True
        elif upper > upper_limit:
            state = "MORE_DATA"
            any_more = True
        else:
            state = "PASS"

        class_results[failure_class] = {
            "state": state,
            "exposures": len(eligible),
            "observed_failures": failures,
            "zero_event_upper_95": upper,
        }

    state = "FAIL" if any_fail else ("MORE_DATA" if any_more else "PASS")
    return gate(
        state,
        classes=class_results,
        unknown_critical_failures=unknown,
        upper_bound_max=upper_limit,
    )

def handoff(rows, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate(
            "MORE_DATA",
            reason="locked handoff matrix incomplete",
            coverage=coverage,
        )
    locked = release_rows(rows, "handoff")
    recovery = paired_condition(
        locked,
        "ablated",
        "present",
        "task_success",
        higher_is_better=True,
    )
    degradation = paired_condition(
        locked,
        "ablated",
        "present",
        "handoff_degraded",
        higher_is_better=False,
    )
    recovery_ci = _ci(recovery)
    degradation_ci = _ci(degradation)
    recovery_min = thresholds["handoff"]["recovery_success_uplift_min_absolute"]
    degradation_min = thresholds["handoff"]["degradation_reduction_min_absolute"]
    ok = (
        recovery_ci["ci"][0] >= recovery_min
        and degradation_ci["ci"][0] >= degradation_min
    )
    return gate(
        "PASS" if ok else "FAIL",
        recovery={
            "delta": recovery["mean_delta"],
            "ci": recovery_ci["ci"],
            "n": recovery["n"],
            "minimum": recovery_min,
        },
        degradation_reduction={
            "delta": degradation["mean_delta"],
            "ci": degradation_ci["ci"],
            "n": degradation["n"],
            "minimum": degradation_min,
        },
    )

def trigger(rows, protocol, thresholds):
    locked = release_rows(rows, "trigger")
    distinct = {row.get("scenario_id") for row in locked}
    required = int(protocol["sampling"]["trigger_cases_minimum"])
    if len(distinct) < required:
        return gate(
            "MORE_DATA",
            distinct_cases=len(distinct),
            required=required,
        )
    observed = trigger_metrics([
        {
            "should_trigger": row["outcome"]["should_trigger"],
            "triggered": row["outcome"]["triggered"],
        }
        for row in locked
    ])
    ok = (
        observed["precision"] >= thresholds["trigger"]["precision_min"]
        and observed["recall"] >= thresholds["trigger"]["recall_min"]
        and observed["false_positive_rate"] <= thresholds["trigger"]["false_positive_rate_max"]
        and observed["false_negative_rate"] <= thresholds["trigger"]["false_negative_rate_max"]
    )
    return gate(
        "PASS" if ok else "FAIL",
        distinct_cases=len(distinct),
        metrics=observed,
    )

def efficiency(rows, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")

    locked = release_rows(rows, "behavioral")
    expected = int(coverage["complete_pairs"])
    ratios = {}
    missing = False
    ok = True
    fields = [
        ("tokens", "total_tokens", "median_total_token_ratio_max"),
        ("wall_time", "wall_time_seconds", "median_wall_time_ratio_max"),
        ("tool_calls", "tool_calls", "median_tool_call_ratio_max"),
    ]
    for name, field, limit_key in fields:
        item = paired_numeric_ratio(locked, "A2", "A0", field)
        limit = thresholds["efficiency"][limit_key]
        ratios[name] = {
            "median": item["median"],
            "n": item["n"],
            "limit": limit,
        }
        if item["n"] < expected:
            missing = True
        elif item["median"] > limit:
            ok = False

    treatment = [row for row in locked if row.get("arm") == "A2"]
    artifacts = [
        row.get("usage", {}).get("persistent_governance_artifacts")
        for row in treatment
    ]
    if any(not isinstance(value, (int, float)) for value in artifacts):
        missing = True
        artifact_max = None
    else:
        artifact_max = max(artifacts) if artifacts else None

    artifact_limit = thresholds["efficiency"]["persistent_governance_artifacts_per_task_max"]
    if artifact_max is not None and artifact_max > artifact_limit:
        ok = False

    if missing:
        state = "MORE_DATA"
    else:
        state = "PASS" if ok else "FAIL"
    return gate(
        state,
        ratios=ratios,
        persistent_governance_artifacts_max=artifact_max,
        persistent_governance_artifacts_limit=artifact_limit,
    )

def generalization(rows, protocol, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")

    locked = release_rows(rows, "behavioral")
    required_scenarios = int(
        protocol["sampling"]["minimum_locked_behavioral_scenarios"]
    )
    required_families = int(protocol["sampling"]["minimum_agent_families"])
    required_profiles = int(protocol["sampling"]["minimum_project_profiles"])
    family_min = int(
        thresholds["generalization"]["agent_family_min_complete_pairs"]
    )
    profile_min = int(
        thresholds["generalization"]["project_profile_min_complete_pairs"]
    )
    task_floor = float(
        thresholds["generalization"]["subgroup_task_non_inferiority_margin"]
    )
    governance_floor = float(
        thresholds["generalization"]["subgroup_governance_reversal_floor"]
    )

    families = sorted({
        row.get("agent", {}).get("family")
        for row in locked
        if row.get("agent", {}).get("family")
    })
    profiles = sorted({
        row.get("environment", {}).get("project_profile")
        for row in locked
        if row.get("environment", {}).get("project_profile")
    })

    details = {"agent_family": {}, "project_profile": {}}
    any_fail = False
    any_more = (
        len(families) < required_families
        or len(profiles) < required_profiles
    )

    for family in families:
        subset = [
            row for row in locked
            if row.get("agent", {}).get("family") == family
        ]
        task = paired_binary(subset, "A0", "A2", "task_success")
        governance = paired_binary(
            subset, "A0", "A2", "governance_defect_free"
        )
        scenarios = len({row.get("scenario_id") for row in subset})

        if task["n"] < family_min or scenarios < required_scenarios:
            state = "MORE_DATA"
            any_more = True
        elif (
            task["mean_delta"] < task_floor
            or governance["mean_delta"] < governance_floor
        ):
            state = "FAIL"
            any_fail = True
        else:
            state = "PASS"

        details["agent_family"][family] = {
            "state": state,
            "complete_pairs": task["n"],
            "scenarios": scenarios,
            "task_delta": task["mean_delta"],
            "governance_delta": governance["mean_delta"],
        }

    for profile in profiles:
        subset = [
            row for row in locked
            if row.get("environment", {}).get("project_profile") == profile
        ]
        task = paired_binary(subset, "A0", "A2", "task_success")
        governance = paired_binary(
            subset, "A0", "A2", "governance_defect_free"
        )

        if task["n"] < profile_min:
            state = "MORE_DATA"
            any_more = True
        elif (
            task["mean_delta"] < task_floor
            or governance["mean_delta"] < governance_floor
        ):
            state = "FAIL"
            any_fail = True
        else:
            state = "PASS"

        details["project_profile"][profile] = {
            "state": state,
            "complete_pairs": task["n"],
            "task_delta": task["mean_delta"],
            "governance_delta": governance["mean_delta"],
        }

    state = "FAIL" if any_fail else ("MORE_DATA" if any_more else "PASS")
    return gate(
        state,
        agent_families=families,
        project_profiles=profiles,
        subgroups=details,
    )
