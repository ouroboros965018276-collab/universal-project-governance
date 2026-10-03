from __future__ import annotations
import math
import random
import statistics

def pair_key(record):
    agent = record.get("agent", {})
    env = record.get("environment", {})
    return (
        record.get("scenario_id"),
        agent.get("family"),
        agent.get("model_id"),
        agent.get("scaffold_version"),
        env.get("adapter_config_sha256"),
        env.get("adapter_runtime_sha256"),
        env.get("host_tool_name"),
        env.get("host_tool_version"),
        env.get("tool_profile"),
        env.get("budget_profile"),
        record.get("pair_id"),
    )

def wilson_interval(successes, total, z=1.959963984540054):
    if total <= 0:
        return (0.0, 1.0)
    p = successes / float(total)
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    half = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denom
    return (max(0.0, center - half), min(1.0, center + half))

def zero_event_upper_bound(total, alpha=0.05):
    if total <= 0:
        return 1.0
    return 1.0 - math.pow(alpha, 1.0 / total)

def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / float(2 ** n)
    return min(1.0, 2.0 * tail)

def _arm_map(records):
    grouped = {}
    for record in records:
        grouped.setdefault(pair_key(record), {})[record["arm"]] = record
    return grouped

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
            left = bool(arms[left_arm]["outcome"].get(field, False))
            right = bool(arms[right_arm]["outcome"].get(field, False))
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
        grouped.setdefault(pair_key(record), {})[condition] = record
    observations = []
    for values in grouped.values():
        if baseline_condition not in values or treatment_condition not in values:
            continue
        baseline = bool(values[baseline_condition]["outcome"].get(field, False))
        treatment = bool(values[treatment_condition]["outcome"].get(field, False))
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
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        sample = []
        for __ in range(len(families)):
            family = families[rng.randrange(len(families))]
            scenarios = sorted(hierarchy[family])
            for ___ in range(len(scenarios)):
                scenario = scenarios[rng.randrange(len(scenarios))]
                values = hierarchy[family][scenario]
                for ____ in range(len(values)):
                    sample.append(values[rng.randrange(len(values))])
        means.append(sum(sample) / float(len(sample)))
    means.sort()
    lo_index = int((alpha / 2.0) * reps)
    hi_index = min(reps - 1, max(0, int((1.0 - alpha / 2.0) * reps) - 1))
    scenario_count = sum(len(items) for items in hierarchy.values())
    return {
        "mean_delta": sum(float(x["delta"]) for x in observations) / float(len(observations)),
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
