"""Frozen paired artifact-task collection, independent of search feedback.

This small development holdout cannot grant formal qualification. It compares
the exact pinned baseline with the source-bound canonical neutral candidate;
it never selects a candidate from final responses or retries a failed task.
"""
from __future__ import annotations

import json
from pathlib import Path
import random

from .ablation import _baseline
from .contracts import Budget, BudgetExceeded, candidate_id, digest
from .controller import callable_identity, checkpoint_lock, engine_identity, save_run, task_loss
from .evaluator import candidate_source, evaluate, source_hash, validate_candidate


def collect(repo, protocol, output, runner):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    with checkpoint_lock(output):
        return _collect(repo, protocol, output, runner)


def _collect(repo, protocol, output, runner):
    if not callable(runner):
        raise ValueError("paired collection requires an explicit real runner")
    tasks = protocol["tasks"]["final"]
    if not tasks or len({row["id"] for row in tasks}) != len(tasks):
        raise ValueError("final tasks must be nonempty and uniquely identified")
    development_ids = {row["id"] for split in ("training", "selection") for row in protocol["tasks"].get(split, [])}
    if development_ids & {row["id"] for row in tasks}:
        raise ValueError("development task leaked into paired final set")
    baseline = _baseline(repo, protocol["baseline"]["latest_revision"], include_source=True)
    if baseline["engineering"] != "PASS":
        raise ValueError("historical baseline failed engineering checks before dispatch")
    candidate = {"model": json.loads((repo / "governance-src/model/governance-model.json").read_text(encoding="utf-8")),
                 "theta": [0.5, 0.5, 0.5], "operator": "prespecified-neutral-compression"}
    pinned_candidate = protocol.get("paired_candidate_id")
    if pinned_candidate is not None and pinned_candidate != candidate_id(candidate):
        raise ValueError("paired candidate differs from the owner preregistration")
    validation = validate_candidate(candidate, repo)
    if not validation["ok"]:
        raise ValueError("prespecified candidate failed engineering checks before dispatch")
    sources = {"control": baseline["source"], "treatment": candidate_source(candidate, repo)}
    artifacts = {"control": baseline["execution_artifact"], "treatment": {
        "compiler": (repo / "compiler/compile_governance.py").read_bytes().decode("utf-8"),
        "license": (repo / "LICENSE").read_bytes().decode("utf-8")}}
    candidates = {"control": {"model": baseline["model"], "operator": "historical-baseline"}, "treatment": candidate}
    candidate_ids = {"control": digest({"historical_revision": protocol["baseline"]["latest_revision"],
                                       "source_sha256": source_hash(sources["control"])}),
                     "treatment": candidate_id(candidate)}
    identities = {"source": {key: source_hash(value) for key, value in sources.items()},
                  "artifacts": {key: digest(value) for key, value in artifacts.items()},
                  "engine": engine_identity(repo, excluded=(output,)), "runner": callable_identity(runner), "protocol": digest(protocol)}
    if output.exists():
        run = json.loads(output.read_text(encoding="utf-8"))
        if run["identities"] != identities:
            raise ValueError("paired checkpoint source/protocol/capability mismatch")
        if run.get("pending"):
            raise ValueError("paired pending call requires independent reconciliation, never automatic replay")
        if run["status"] != "running":
            return run
        budget = Budget.from_state(run["budget"])
    else:
        spec = protocol["paired_budget"]
        budget = Budget(max_calls=spec["model_calls"], max_total_tokens=spec["tokens"], max_seconds=spec["wall_seconds"])
        order = []
        rng = random.Random(protocol["development_scope"]["final_order_seed"])
        shuffled = list(range(len(tasks)))
        rng.shuffle(shuffled)
        for index in shuffled:
            conditions = ["control", "treatment"]
            rng.shuffle(conditions)
            order.extend({"task_index": index, "condition": condition} for condition in conditions)
        run = {"schema_version": 1, "stage": "development-paired-final", "status": "running",
               "identities": identities, "candidate_ids": candidate_ids, "order": order,
               "observations": [], "cache": {}, "pending": None, "budget": budget.state(),
               "independent_formal_qualification": False, "empirical_status": "BLOCKED",
               "scope": protocol["development_scope"],
               "candidate_registration": "protocol-pinned" if pinned_candidate is not None else "source-bound-at-collection; prior selection unassessed"}

    def checkpoint():
        run["budget"] = budget.state()
        save_run(output, run)

    checkpoint()
    try:
        for item in run["order"][len(run["observations"]):]:
            condition, task = item["condition"], tasks[item["task_index"]]
            run["pending"] = {"condition": condition, "task_id": task["id"]}
            checkpoint()
            observation = evaluate(candidates[condition], task, runner, model=protocol["model"],
                config=protocol["runner_config"], deps=identities, runner_identity=identities["runner"],
                cache=run["cache"], retries=0, source=sources[condition], budget=budget,
                candidate_identity=candidate_ids[condition], execution_artifact=artifacts[condition])
            run["observations"].append({"condition": condition, "family": task["family"], "observation": observation})
            run["pending"] = {"kind": "unknown-usage", "observation": observation} if budget.unknown_usage else None
            if budget.unknown_usage:
                raise BudgetExceeded("paired final usage unknown; reconcile before further dispatch")
            state = budget.state()
            exceeded = [key for key, maximum in (("calls", "max_calls"), ("total_tokens", "max_total_tokens"),
                                                   ("elapsed_seconds", "max_seconds")) if state[key] > state[maximum]]
            if exceeded:
                run["actual_budget_overrun"] = exceeded
                raise BudgetExceeded("completed native call exceeded budget: " + ",".join(exceeded))
            if observation["status"] != "completed":
                run["status"] = "failed-no-retry"
                checkpoint()
                return run
            checkpoint()
        run["status"] = "completed"
    except BudgetExceeded as error:
        run["status"], run["stop_reason"] = "budget-exhausted", str(error)
        if not budget.unknown_usage:
            run["pending"] = None
    checkpoint()
    return run


def summarize(run, *, repetitions=4000, seed=18012):
    rows = run["observations"]
    by_condition = {condition: [row["observation"] for row in rows if row["condition"] == condition]
                    for condition in ("control", "treatment")}
    matched = {condition: {row["task_id"]: row for row in observations}
               for condition, observations in by_condition.items()}
    task_ids = sorted(set(matched["control"]) & set(matched["treatment"]))
    quality = (run["status"] == "completed" and task_loss(by_condition["control"]) is not None
               and task_loss(by_condition["treatment"], by_condition["control"]) is not None)
    samples_fresh = bool(rows) and all(row["observation"].get("independent_sample") and not row["observation"].get("cache_hit") for row in rows)
    summary = {"status": run["status"], "pairs": len(task_ids), "task_quality_pass": quality,
               "all_samples_new_calls": samples_fresh, "actual_charged_usage": run["budget"],
               "empirical_status": "BLOCKED", "formal_qualification": "UNASSESSED", "metrics": {
                   name: None for name in ("input_tokens", "output_tokens", "total_tokens", "wall_seconds", "cli_wall_seconds")}}
    complete = (run["status"] == "completed" and bool(task_ids)
                and set(matched["control"]) == set(matched["treatment"])
                and len(rows) == 2 * len(task_ids) == len(run.get("order", rows)))
    if not complete:
        summary["inference_scope"] = "Incomplete paired collection; no paired estimates"
        return summary
    family_by_task = {row["observation"]["task_id"]: row["family"] for row in rows}
    families = sorted({family_by_task[key] for key in task_ids})
    groups = [[key for key in task_ids if family_by_task[key] == family] for family in families]
    for name in ("input_tokens", "output_tokens", "total_tokens", "wall_seconds", "cli_wall_seconds"):
        def value(condition, key):
            row = matched[condition][key]
            if name == "cli_wall_seconds":
                return ((row.get("attempts") or [{}])[-1].get("provider_receipt") or {}).get("wall_seconds")
            return row["wall_seconds"] if name == "wall_seconds" else row["usage"].get(name)
        numbers = {condition: [value(condition, key) for key in task_ids] for condition in matched}
        if not task_ids or any(type(number) not in (int, float) for values in numbers.values() for number in values):
            summary["metrics"][name] = None
            continue
        control, treatment = sum(numbers["control"]), sum(numbers["treatment"])
        rng, ratios = random.Random(seed), []
        if control > 0:
            for unused in range(repetitions):
                sampled = [rng.choice(group) for group in groups for unused in group]
                denominator = sum(value("control", key) for key in sampled)
                if denominator > 0:
                    ratios.append(sum(value("treatment", key) for key in sampled) / denominator)
        ratios.sort()
        summary["metrics"][name] = {"control_total": control, "treatment_total": treatment,
            "ratio": treatment / control if control > 0 else None,
            "savings_fraction": 1 - treatment / control if control > 0 else None,
            "paired_family_bootstrap_95_interval": [ratios[int(len(ratios)*0.025)], ratios[min(len(ratios)-1,int(len(ratios)*0.975))]] if ratios else None}
    summary["inference_scope"] = f"{len(task_ids)} registered artifact-task pairs in one requested model; no cross-family Agent/provider or tool-execution claim"
    return summary
