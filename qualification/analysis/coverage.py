from __future__ import annotations
from collections import defaultdict
from qualification.analysis.metrics import pair_key

def gate(state, **data):
    result = {"state": state}
    result.update(data)
    return result

def release_rows(rows, kind=None):
    selected = [
        row for row in rows
        if row.get("environment", {}).get("qualification_set") == "locked"
    ]
    if kind is not None:
        selected = [row for row in selected if row.get("kind") == kind]
    return selected

def _primary_groups(rows, arms):
    groups = {}
    malformed = []
    for row in release_rows(rows, "behavioral"):
        if row.get("arm") not in arms:
            continue
        key = pair_key(row)
        bucket = groups.setdefault(key, {})
        if row["arm"] in bucket:
            malformed.append({"pair": list(key), "arm": row["arm"], "error": "duplicate arm"})
        bucket[row["arm"]] = row
    complete = []
    for key, bucket in groups.items():
        if not all(arm in bucket for arm in arms):
            continue
        profiles = {bucket[arm].get("environment", {}).get("project_profile") for arm in arms}
        if len(profiles) != 1:
            malformed.append({"pair": list(key), "error": "project_profile mismatch"})
            continue
        complete.append({"key": key, "rows": bucket, "profile": next(iter(profiles))})
    return complete, malformed

def behavioral_coverage(rows, protocol):
    arms = list(protocol["coverage"]["primary_arms"])
    complete, malformed = _primary_groups(rows, arms)
    locked = release_rows(rows, "behavioral")
    identity_fields = [
        "adapter_config_sha256", "adapter_runtime_sha256",
        "host_tool_name", "host_tool_version",
    ]
    for row in locked:
        env = row.get("environment", {})
        missing_identity = [key for key in identity_fields if not env.get(key)]
        if missing_identity:
            malformed.append({
                "trial_id": row.get("trial_id"),
                "error": "missing reproducibility identity",
                "fields": missing_identity,
            })
    scenarios = sorted({row.get("scenario_id") for row in locked})
    families = sorted({
        row.get("agent", {}).get("family")
        for row in locked
        if row.get("agent", {}).get("family")
    })
    required_scenarios = int(protocol["sampling"]["minimum_locked_behavioral_scenarios"])
    required_families = int(protocol["sampling"]["minimum_agent_families"])
    required_reps = int(protocol["sampling"]["locked_repetitions_per_cell_min"])
    cells = defaultdict(int)
    profile_pairs = defaultdict(int)
    for item in complete:
        key = item["key"]
        cells[(key[0], key[1])] += 1
        profile_pairs[item["profile"]] += 1
    shortfalls = []
    for scenario in scenarios:
        for family in families:
            count = cells[(scenario, family)]
            if count < required_reps:
                shortfalls.append({
                    "scenario_id": scenario,
                    "agent_family": family,
                    "complete_pairs": count,
                    "required": required_reps,
                })
    if malformed:
        state = "FAIL"
    elif len(scenarios) < required_scenarios or len(families) < required_families or shortfalls:
        state = "MORE_DATA"
    else:
        state = "PASS"
    return gate(
        state,
        distinct_locked_scenarios=len(scenarios),
        required_locked_scenarios=required_scenarios,
        agent_families=families,
        required_agent_families=required_families,
        complete_pairs=len(complete),
        cell_shortfalls=shortfalls,
        malformed_pairs=malformed,
        profile_complete_pairs=dict(profile_pairs),
    )

def handoff_coverage(rows, protocol):
    locked = release_rows(rows, "handoff")
    groups = {}
    malformed = []
    for row in locked:
        key = pair_key(row)
        condition = (
            row.get("outcome", {}).get("handoff_condition")
            or row.get("environment", {}).get("handoff_condition")
        )
        bucket = groups.setdefault(key, {})
        if condition in bucket:
            malformed.append({"pair": list(key), "condition": condition, "error": "duplicate condition"})
        bucket[condition] = row
    complete = [
        (key, bucket)
        for key, bucket in groups.items()
        if "present" in bucket and "ablated" in bucket
    ]
    scenarios = sorted({row.get("scenario_id") for row in locked})
    families = sorted({
        row.get("agent", {}).get("family")
        for row in locked
        if row.get("agent", {}).get("family")
    })
    required_scenarios = int(protocol["sampling"]["minimum_locked_handoff_scenarios"])
    required_reps = int(protocol["sampling"]["locked_handoff_repetitions_per_cell_min"])
    required_families = int(protocol["sampling"]["minimum_agent_families"])
    cells = defaultdict(int)
    for key, _ in complete:
        cells[(key[0], key[1])] += 1
    shortfalls = []
    for scenario in scenarios:
        for family in families:
            count = cells[(scenario, family)]
            if count < required_reps:
                shortfalls.append({
                    "scenario_id": scenario,
                    "agent_family": family,
                    "complete_pairs": count,
                    "required": required_reps,
                })
    if malformed:
        state = "FAIL"
    elif len(scenarios) < required_scenarios or len(families) < required_families or shortfalls:
        state = "MORE_DATA"
    else:
        state = "PASS"
    return gate(
        state,
        distinct_locked_scenarios=len(scenarios),
        required_locked_scenarios=required_scenarios,
        agent_families=families,
        required_agent_families=required_families,
        complete_pairs=len(complete),
        cell_shortfalls=shortfalls,
        malformed_pairs=malformed,
    )
