from __future__ import annotations
import statistics

from qualification.analysis.coverage import gate, release_rows
from qualification.analysis.metrics import (
    hierarchical_bootstrap_delta,
    paired_binary,
    paired_condition,
    paired_numeric_ratio,
    zero_event_upper_bound,
)
from qualification.trigger_suite import metrics as trigger_metrics

def _ci(effect, protocol):
    inference = protocol["inference"]
    if not effect["n"]:
        return {
            "ci": [0.0, 0.0],
            "method": inference["method"],
            "levels": inference["levels"],
            "clusters": {"agent_families": 0, "scenarios": 0, "pairs": 0},
        }
    return hierarchical_bootstrap_delta(
        effect["observations"],
        seed=int(inference["seed"]),
        reps=int(inference["bootstrap_repetitions"]),
        alpha=1.0 - float(inference["confidence"]),
    )

def deployment_integrity(rows, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    treatment = [
        row for row in release_rows(rows, "behavioral")
        if row.get("arm") == "A2"
    ]
    expected = int(coverage.get("complete_pairs", 0))
    if len(treatment) < expected:
        return gate("MORE_DATA", treatment_trials=len(treatment), required=expected)
    failures = []
    managed_counts = []
    for row in treatment:
        deployment = row.get("outcome", {}).get("deployment")
        if not isinstance(deployment, dict):
            failures.append({"trial_id": row.get("trial_id"), "reason": "deployment evidence missing"})
            continue
        if not deployment.get("binding_ok"):
            failures.append({"trial_id": row.get("trial_id"), "reason": "project binding invalid/missing"})
        if deployment.get("report_count") != 1:
            failures.append({
                "trial_id": row.get("trial_id"),
                "reason": "completed modifying workflow must record exactly one field report",
                "report_count": deployment.get("report_count"),
            })
        managed = row.get("usage", {}).get("managed_project_files")
        if isinstance(managed, (int, float)):
            managed_counts.append(managed)
        else:
            failures.append({"trial_id": row.get("trial_id"), "reason": "managed project file count missing"})
    max_managed = max(managed_counts) if managed_counts else None
    managed_limit = thresholds["efficiency"]["managed_project_files_max"]
    if max_managed is not None and max_managed > managed_limit:
        failures.append({"reason": "managed project file budget exceeded", "observed": max_managed, "limit": managed_limit})
    return gate(
        "FAIL" if failures else "PASS",
        treatment_trials=len(treatment),
        failures=failures,
        managed_project_files_max=max_managed,
        managed_project_files_limit=managed_limit,
    )

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

def core_task(rows, protocol, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    effect = paired_binary(
        release_rows(rows, "behavioral"), "A0", "A2", "task_success"
    )
    inference = _ci(effect, protocol)
    margin = thresholds["core_task_non_inferiority"]["margin_absolute"]
    return gate(
        "PASS" if inference["ci"][0] >= margin else "FAIL",
        delta=effect["mean_delta"],
        ci=inference["ci"],
        n=effect["n"],
        margin=margin,
        inference=inference,
    )

def governance_uplift(rows, protocol, thresholds, coverage, control):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    if control["state"] != "PASS":
        return gate("MORE_DATA", reason="attention control is not valid")
    behavioral = release_rows(rows, "behavioral")
    no_skill = paired_binary(behavioral, "A0", "A2", "governance_defect_free")
    attention = paired_binary(behavioral, "A1", "A2", "governance_defect_free")
    inf0 = _ci(no_skill, protocol)
    inf1 = _ci(attention, protocol)
    min0 = thresholds["governance_uplift"]["versus_no_skill_min_absolute"]
    min1 = thresholds["governance_uplift"]["versus_attention_control_min_absolute"]
    ok = inf0["ci"][0] >= min0 and inf1["ci"][0] >= min1
    return gate(
        "PASS" if ok else "FAIL",
        vs_no_skill={
            "delta": no_skill["mean_delta"],
            "ci": inf0["ci"],
            "n": no_skill["n"],
            "minimum": min0,
            "inference": inf0,
        },
        vs_attention={
            "delta": attention["mean_delta"],
            "ci": inf1["ci"],
            "n": attention["n"],
            "minimum": min1,
            "inference": inf1,
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
    failed = [mid for mid, values in by_mutant.items() if values and not all(values)]
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
            condition = row.get("outcome", {}).get("handoff_condition") or env.get("handoff_condition")
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
    upper_limit = float(thresholds["critical_failure"]["one_sided_upper_bound_95_max"])
    observed_max = int(thresholds["critical_failure"]["observed_max_per_class"])

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
        upper = zero_event_upper_bound(len(eligible)) if failures == 0 else 1.0
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

def _scope_cohort_result(metrics, spec):
    violations = [value for value in metrics if value.get("scope_violation")]
    upper = zero_event_upper_bound(len(metrics)) if not violations else 1.0
    hard_violation = False
    for value in metrics:
        if len(value.get("unexpected_changed_files", [])) > spec["unexpected_changed_files_max_per_task"]:
            hard_violation = True
        if len(value.get("unrequested_api_changes", [])) > spec["unrequested_api_changes_max_per_task"]:
            hard_violation = True
        if len(value.get("unrequested_architecture_changes", [])) > spec["unrequested_architecture_changes_max_per_task"]:
            hard_violation = True
    if len(violations) > spec["observed_scope_violations_max"] or hard_violation:
        state = "FAIL"
    elif upper > spec["one_sided_upper_bound_95_max"]:
        state = "MORE_DATA"
    else:
        state = "PASS"
    return {
        "state": state,
        "exposures": len(metrics),
        "observed_scope_violations": len(violations),
        "zero_event_upper_95": upper,
        "zero_event_upper_limit": spec["one_sided_upper_bound_95_max"],
        "diagnostics": {
            "median_changed_files": statistics.median([x.get("changed_files_count", 0) for x in metrics]) if metrics else None,
            "median_diff_lines": statistics.median([x.get("diff_lines", 0) for x in metrics]) if metrics else None,
            "max_unexpected_changed_files": max([len(x.get("unexpected_changed_files", [])) for x in metrics] or [0]),
            "max_unrequested_api_changes": max([len(x.get("unrequested_api_changes", [])) for x in metrics] or [0]),
            "max_unrequested_architecture_changes": max([len(x.get("unrequested_architecture_changes", [])) for x in metrics] or [0]),
        },
    }

def structural_overreach(rows, protocol, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    treatment = [
        row for row in release_rows(rows, "behavioral")
        if row.get("arm") == "A2"
    ]
    by_cohort = {
        name: [] for name in protocol["structural_overreach"]["exposure_cohorts"]
    }
    missing = []
    unknown = []
    for row in treatment:
        value = row.get("outcome", {}).get("scope_metrics")
        if not isinstance(value, dict):
            missing.append(row.get("trial_id"))
            continue
        cohort = value.get("overreach_exposure")
        if cohort not in by_cohort:
            unknown.append({"trial_id": row.get("trial_id"), "cohort": cohort})
            continue
        by_cohort[cohort].append(value)
    if missing or unknown:
        return gate(
            "MORE_DATA",
            missing_scope_metrics=missing,
            unknown_exposure_cohorts=unknown,
            measured=sum(len(x) for x in by_cohort.values()),
            required=len(treatment),
        )

    spec = thresholds["structural_overreach"]
    cohorts = {}
    states = []
    for name, cfg in protocol["structural_overreach"]["exposure_cohorts"].items():
        metrics = by_cohort[name]
        minimum_scenarios = int(cfg["minimum_locked_scenarios"])
        scenario_count = len({
            row.get("scenario_id")
            for row in treatment
            if row.get("outcome", {}).get("scope_metrics", {}).get("overreach_exposure") == name
        })
        result = _scope_cohort_result(metrics, spec)
        result["distinct_scenarios"] = scenario_count
        result["minimum_locked_scenarios"] = minimum_scenarios
        if scenario_count < minimum_scenarios and result["state"] != "FAIL":
            result["state"] = "MORE_DATA"
        cohorts[name] = result
        states.append(result["state"])

    state = "FAIL" if "FAIL" in states else ("MORE_DATA" if "MORE_DATA" in states else "PASS")
    return gate(
        state,
        treatment_trials=sum(len(x) for x in by_cohort.values()),
        claim_semantics="local-scope expansion and structural-layer overreach are estimated separately; neither cohort can dilute the other",
        cohorts=cohorts,
    )

def handoff(rows, protocol, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked handoff matrix incomplete", coverage=coverage)
    locked = release_rows(rows, "handoff")
    recovery = paired_condition(locked, "ablated", "present", "task_success", higher_is_better=True)
    degradation = paired_condition(locked, "ablated", "present", "handoff_degraded", higher_is_better=False)
    recovery_inf = _ci(recovery, protocol)
    degradation_inf = _ci(degradation, protocol)
    recovery_min = thresholds["handoff"]["recovery_success_uplift_min_absolute"]
    degradation_min = thresholds["handoff"]["degradation_reduction_min_absolute"]
    ok = recovery_inf["ci"][0] >= recovery_min and degradation_inf["ci"][0] >= degradation_min
    return gate(
        "PASS" if ok else "FAIL",
        recovery={
            "delta": recovery["mean_delta"],
            "ci": recovery_inf["ci"],
            "n": recovery["n"],
            "minimum": recovery_min,
            "inference": recovery_inf,
        },
        degradation_reduction={
            "delta": degradation["mean_delta"],
            "ci": degradation_inf["ci"],
            "n": degradation["n"],
            "minimum": degradation_min,
            "inference": degradation_inf,
        },
    )

def trigger(rows, protocol, thresholds):
    locked = release_rows(rows, "trigger")
    distinct = {row.get("scenario_id") for row in locked}
    required = int(protocol["sampling"]["trigger_cases_minimum"])
    if len(distinct) < required:
        return gate("MORE_DATA", distinct_cases=len(distinct), required=required)
    observed = trigger_metrics([
        {"should_trigger": row["outcome"]["should_trigger"], "triggered": row["outcome"]["triggered"]}
        for row in locked
    ])
    ok = (
        observed["precision"] >= thresholds["trigger"]["precision_min"]
        and observed["recall"] >= thresholds["trigger"]["recall_min"]
        and observed["false_positive_rate"] <= thresholds["trigger"]["false_positive_rate_max"]
        and observed["false_negative_rate"] <= thresholds["trigger"]["false_negative_rate_max"]
    )
    return gate("PASS" if ok else "FAIL", distinct_cases=len(distinct), metrics=observed)

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
        ratios[name] = {"median": item["median"], "n": item["n"], "limit": limit}
        if item["n"] < expected:
            missing = True
        elif item["median"] > limit:
            ok = False

    treatment = [row for row in locked if row.get("arm") == "A2"]
    task_artifacts = [row.get("usage", {}).get("persistent_task_governance_artifacts") for row in treatment]
    managed_files = [row.get("usage", {}).get("managed_project_files") for row in treatment]
    if any(not isinstance(value, (int, float)) for value in task_artifacts + managed_files):
        missing = True
        task_max = None
        managed_max = None
    else:
        task_max = max(task_artifacts) if task_artifacts else None
        managed_max = max(managed_files) if managed_files else None
    task_limit = thresholds["efficiency"]["persistent_task_governance_artifacts_per_task_max"]
    managed_limit = thresholds["efficiency"]["managed_project_files_max"]
    if task_max is not None and task_max > task_limit:
        ok = False
    if managed_max is not None and managed_max > managed_limit:
        ok = False

    state = "MORE_DATA" if missing else ("PASS" if ok else "FAIL")
    return gate(
        state,
        ratios=ratios,
        persistent_task_governance_artifacts_max=task_max,
        persistent_task_governance_artifacts_limit=task_limit,
        managed_project_files_max=managed_max,
        managed_project_files_limit=managed_limit,
    )

def _subgroup_result(subset, protocol, min_pairs, min_scenarios, task_floor, governance_floor):
    task = paired_binary(subset, "A0", "A2", "task_success")
    governance = paired_binary(subset, "A0", "A2", "governance_defect_free")
    scenarios = len({row.get("scenario_id") for row in subset})
    task_inf = _ci(task, protocol)
    governance_inf = _ci(governance, protocol)
    if task["n"] < min_pairs or scenarios < min_scenarios:
        state = "MORE_DATA"
    elif task_inf["ci"][1] < task_floor or governance_inf["ci"][1] < governance_floor:
        state = "FAIL"
    elif task_inf["ci"][0] < task_floor or governance_inf["ci"][0] < governance_floor:
        state = "MORE_DATA"
    else:
        state = "PASS"
    positive = task_inf["ci"][0] >= 0.0 and governance_inf["ci"][0] > 0.0
    return {
        "state": state,
        "complete_pairs": task["n"],
        "scenarios": scenarios,
        "task_delta": task["mean_delta"],
        "task_ci": task_inf["ci"],
        "governance_delta": governance["mean_delta"],
        "governance_ci": governance_inf["ci"],
        "evidence_level": "positive-subgroup-evidence" if positive else "severe-reversal-ruled-out-only",
        "inference_method": protocol["inference"]["method"],
    }

def generalization(rows, protocol, thresholds, coverage):
    if coverage["state"] != "PASS":
        return gate("MORE_DATA", reason="locked behavioral matrix incomplete")
    locked = release_rows(rows, "behavioral")
    required_scenarios = int(protocol["sampling"]["minimum_locked_behavioral_scenarios"])
    required_families = int(protocol["sampling"]["minimum_agent_families"])
    required_profiles = int(protocol["sampling"]["minimum_project_profiles"])
    family_min = int(thresholds["generalization"]["agent_family_min_complete_pairs"])
    profile_min = int(thresholds["generalization"]["project_profile_min_complete_pairs"])
    task_floor = float(thresholds["generalization"]["subgroup_task_non_inferiority_margin"])
    governance_floor = float(thresholds["generalization"]["subgroup_governance_reversal_floor"])

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
    states = []
    for family in families:
        subset = [row for row in locked if row.get("agent", {}).get("family") == family]
        result = _subgroup_result(
            subset, protocol, family_min, required_scenarios, task_floor, governance_floor
        )
        details["agent_family"][family] = result
        states.append(result["state"])
    for profile in profiles:
        subset = [row for row in locked if row.get("environment", {}).get("project_profile") == profile]
        result = _subgroup_result(
            subset, protocol, profile_min, 1, task_floor, governance_floor
        )
        details["project_profile"][profile] = result
        states.append(result["state"])

    if len(families) < required_families or len(profiles) < required_profiles:
        states.append("MORE_DATA")
    state = "FAIL" if "FAIL" in states else ("MORE_DATA" if "MORE_DATA" in states else "PASS")
    return gate(
        state,
        claim_semantics=thresholds["generalization"]["claim_semantics"],
        agent_families=families,
        project_profiles=profiles,
        subgroups=details,
    )
