from __future__ import annotations
import math
import random
import statistics

def pair_key(record):
    agent = record.get("agent") if isinstance(record.get("agent"),dict) else {}
    env = record.get("environment") if isinstance(record.get("environment"),dict) else {}
    return (
        record.get("scenario_id"),
        agent.get("family"),
        agent.get("model_id"),
        agent.get("scaffold_version"),
        env.get("adapter_config_sha256"),
        env.get("adapter_runtime_sha256"),
        env.get("host_tool_name"),
        env.get("host_tool_version"),
        env.get("source_agent_family"),
        env.get("source_adapter_config_sha256"),
        env.get("source_host_tool_name"),
        env.get("source_host_tool_version"),
        env.get("tool_profile"),
        env.get("budget_profile"),
        record.get("pair_id"),
    )

def zero_event_upper_bound(total, alpha=0.05):
    if total <= 0:
        return 1.0
    return 1.0 - math.pow(alpha, 1.0 / total)

def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)

def _arm_map(records):
    grouped = {}
    for record in records:
        if not isinstance(record,dict) or not isinstance(record.get("arm"),str): raise ValueError("paired record requires an arm")
        bucket=grouped.setdefault(pair_key(record), {})
        if record["arm"] in bucket: raise ValueError("duplicate paired arm: "+record["arm"])
        bucket[record["arm"]] = record
    return grouped

def _boolean_outcome(record,field):
    outcome=record.get("outcome")
    if not isinstance(outcome,dict) or type(outcome.get(field)) is not bool:
        raise ValueError("paired outcome requires boolean "+field)
    return outcome[field]

def _observation(record, delta):
    return {
        "agent_family": record.get("agent", {}).get("family") or "<unknown>",
        "scenario_id": record.get("scenario_id") or "<unknown>",
        "pair_id": record.get("pair_id") or "<unknown>",
        "delta": float(delta),
    }

def paired_binary(records, left_arm, right_arm, field):
    pairs = []
    observations = []
    for arms in _arm_map(records).values():
        if left_arm in arms and right_arm in arms:
            left = _boolean_outcome(arms[left_arm],field)
            right = _boolean_outcome(arms[right_arm],field)
            delta = int(right) - int(left)
            pairs.append((left, right))
            observations.append(_observation(arms[right_arm], delta))
    diffs = [obs["delta"] for obs in observations]
    left_only = sum(1 for left, right in pairs if left and not right)
    right_only = sum(1 for left, right in pairs if not left and right)
    return {
        "n": len(pairs),
        "mean_delta": sum(diffs) / float(len(diffs)) if diffs else 0.0,
        "left_only_success": left_only,
        "right_only_success": right_only,
        "mcnemar_exact_p": mcnemar_exact_p(left_only, right_only),
        "observations": observations,
    }

def paired_numeric_ratio(records, numerator_arm, denominator_arm, field):
    ratios = []
    for arms in _arm_map(records).values():
        if numerator_arm not in arms or denominator_arm not in arms:
            continue
        numerator = arms[numerator_arm].get("usage", {}).get(field)
        denominator = arms[denominator_arm].get("usage", {}).get(field)
        if isinstance(numerator, (int, float)) and isinstance(denominator, (int, float)) and denominator > 0:
            ratios.append(numerator / float(denominator))
    return {
        "n": len(ratios),
        "median": statistics.median(ratios) if ratios else None,
        "ratios": ratios,
    }

def paired_condition(records, baseline_condition, treatment_condition, field, higher_is_better=True):
    grouped = {}
    for record in records:
        condition = (
            record.get("outcome", {}).get("handoff_condition")
            or record.get("environment", {}).get("handoff_condition")
        )
        bucket=grouped.setdefault(pair_key(record), {})
        if condition in bucket: raise ValueError("duplicate paired condition: "+str(condition))
        bucket[condition] = record
    observations = []
    for values in grouped.values():
        if baseline_condition not in values or treatment_condition not in values:
            continue
        baseline = _boolean_outcome(values[baseline_condition],field)
        treatment = _boolean_outcome(values[treatment_condition],field)
        if higher_is_better:
            delta = int(treatment) - int(baseline)
        else:
            delta = int(baseline) - int(treatment)
        observations.append(_observation(values[treatment_condition], delta))
    diffs = [obs["delta"] for obs in observations]
    return {
        "n": len(observations),
        "mean_delta": sum(diffs) / float(len(diffs)) if diffs else 0.0,
        "observations": observations,
    }

def hierarchical_bootstrap_delta(observations, seed=1729, reps=4000, alpha=0.05):
    if not observations:
        return {
            "mean_delta": 0.0,
            "ci": [0.0, 0.0],
            "method": "hierarchical-bootstrap",
            "levels": ["agent_family", "scenario_id", "pair_id"],
            "clusters": {"agent_families": 0, "scenarios": 0, "pairs": 0},
        }
    hierarchy = {}
    for obs in observations:
        family = obs["agent_family"]
        scenario = obs["scenario_id"]
        hierarchy.setdefault(family, {}).setdefault(scenario, []).append(float(obs["delta"]))
    families = sorted(hierarchy)
    family_scenarios={family:sorted(hierarchy[family]) for family in families}
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        sample = []
        for __ in range(len(families)):
            family = families[rng.randrange(len(families))]
            scenarios = family_scenarios[family]
            scenario_means=[]
            for ___ in range(len(scenarios)):
                scenario = scenarios[rng.randrange(len(scenarios))]
                values = hierarchy[family][scenario]
                draws=[values[rng.randrange(len(values))] for ____ in range(len(values))]
                scenario_means.append(sum(draws)/len(draws))
            sample.append(sum(scenario_means)/len(scenario_means))
        means.append(sum(sample) / float(len(sample)))
    means.sort()
    lo_index = int((alpha / 2.0) * reps)
    hi_index = min(reps - 1, max(0, int((1.0 - alpha / 2.0) * reps) - 1))
    scenario_count = sum(len(items) for items in hierarchy.values())
    return {
        "mean_delta": sum(sum(sum(values)/len(values) for values in hierarchy[family].values())/len(hierarchy[family]) for family in families)/len(families),
        "ci": [means[lo_index], means[hi_index]],
        "method": "hierarchical-bootstrap",
        "levels": ["agent_family", "scenario_id", "pair_id"],
        "clusters": {
            "agent_families": len(families),
            "scenarios": scenario_count,
            "pairs": len(observations),
        },
        "bootstrap_repetitions": reps,
        "seed": seed,
    }
