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

def paired_binary(records, left_arm, right_arm, field):
    pairs = []
    for arms in _arm_map(records).values():
        if left_arm in arms and right_arm in arms:
            pairs.append((
                bool(arms[left_arm]["outcome"].get(field, False)),
                bool(arms[right_arm]["outcome"].get(field, False)),
            ))
    diffs = [int(right) - int(left) for left, right in pairs]
    left_only = sum(1 for left, right in pairs if left and not right)
    right_only = sum(1 for left, right in pairs if not left and right)
    return {
        "n": len(pairs),
        "mean_delta": sum(diffs) / float(len(diffs)) if diffs else 0.0,
        "left_only_success": left_only,
        "right_only_success": right_only,
        "mcnemar_exact_p": mcnemar_exact_p(left_only, right_only),
        "deltas": diffs,
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
        grouped.setdefault(pair_key(record), {})[condition] = bool(record["outcome"].get(field, False))
    pairs = [
        values for values in grouped.values()
        if baseline_condition in values and treatment_condition in values
    ]
    if higher_is_better:
        diffs = [
            int(values[treatment_condition]) - int(values[baseline_condition])
            for values in pairs
        ]
    else:
        diffs = [
            int(values[baseline_condition]) - int(values[treatment_condition])
            for values in pairs
        ]
    return {
        "n": len(pairs),
        "mean_delta": sum(diffs) / float(len(diffs)) if diffs else 0.0,
        "deltas": diffs,
    }

def bootstrap_paired_delta(values, seed=1729, reps=4000, alpha=0.05):
    if not values:
        return {"median_delta": 0.0, "mean_delta": 0.0, "ci": [0.0, 0.0]}
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(reps):
        sample = [values[rng.randrange(n)] for __ in range(n)]
        means.append(sum(sample) / float(n))
    means.sort()
    lo = means[int((alpha / 2.0) * reps)]
    hi = means[min(reps - 1, max(0, int((1.0 - alpha / 2.0) * reps) - 1))]
    return {
        "median_delta": statistics.median(values),
        "mean_delta": sum(values) / float(n),
        "ci": [lo, hi],
    }
