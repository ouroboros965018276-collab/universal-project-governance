"""Preregistered six-arm context experiment; no optimizer or promotion path.

The existing official CLI adapter owns fresh threads, bounded tools and raw
receipts. This module only freezes conditions, orders calls and accounts for
their observed costs. Unknown calls are terminal fences, never replay requests.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path

from .contracts import Budget, BudgetExceeded, digest
from .controller import checkpoint_lock, engine_identity, save_run
from .tool_broker import validate_task
from . import tool_campaign as tools

ARMS = ("rc19", "attention", "full_rc20", "minus_decision_relevance",
        "minus_complete_change", "minus_evidence_fidelity")
ABLATIONS = {"minus_decision_relevance": "decision_relevance",
             "minus_complete_change": "complete_change",
             "minus_evidence_fidelity": "evidence_fidelity"}
GUIDANCE_IDS = {"decision_relevance", "complete_change", "evidence_fidelity", "task_scoped_reading"}
ATTENTION_INSTRUCTION = "Keep the response concise and avoid unnecessary engineering."
SEED = 20014


def trusted_arm_models(full_model):
    """Only registered leave-one-guidance-out conditions, never candidates."""
    if not isinstance(full_model, dict):
        raise ValueError("trusted governance model must be an object")
    groups = full_model.get("execution_guidance", [])
    if (not isinstance(groups, list) or len(groups) != 4
            or any(not isinstance(group, dict) or not isinstance(group.get("id"), str)
                   or not isinstance(group.get("statement"), str) or not group["statement"]
                   or not isinstance(group.get("policy_ids"), list)
                   or any(not isinstance(p, str) for p in group["policy_ids"]) for group in groups)
            or {group["id"] for group in groups} != GUIDANCE_IDS):
        raise ValueError("full condition requires the four registered guidance groups")
    result = {"full_rc20": copy.deepcopy(full_model)}
    for arm, removed in ABLATIONS.items():
        model = copy.deepcopy(full_model)
        model["execution_guidance"] = [group for group in model["execution_guidance"] if group["id"] != removed]
        result[arm] = model
    return result


def order(models, task_ids, seed=SEED):
    """Adjacent six-arm blocks; six Williams rows rotate within each model.

    Seven tasks per model leave one extra row: positional balance is within
    one, not an assertion of complete carryover balance over fourteen blocks.
    """
    rng = random.Random(seed)
    pairs = [(model, task_id) for model in models for task_id in task_ids]
    rng.shuffle(pairs)
    labels = list(ARMS)
    rng.shuffle(labels)
    starts = {model: rng.randrange(6) for model in models}
    seen = dict.fromkeys(models, 0)
    base = (0, 1, 5, 2, 4, 3)
    result = []
    for pair_index, (model, task_id) in enumerate(pairs):
        row = (starts[model] + seen[model]) % 6
        seen[model] += 1
        for position, index in enumerate(base):
            result.append({"model": model, "task_id": task_id, "condition": labels[(index + row) % 6],
                           "pair_index": pair_index, "position": position, "williams_row": row,
                           "sample_index": len(result)})
    return result


def _validate(protocol, private_tasks, configs):
    if (not isinstance(protocol, dict) or not isinstance(protocol.get("protocol_id"), str)
            or not protocol["protocol_id"] or protocol.get("stage") != "independent"
            or type(protocol.get("seed")) is not int or protocol["seed"] != SEED
            or protocol.get("optimizer_candidate") is not False):
        raise ValueError("explicit independent non-optimizer protocol with seed 20014 is required")
    models, task_ids = protocol.get("models"), protocol.get("task_ids")
    for values, size, name in ((models, 2, "models"), (task_ids, 7, "task_ids")):
        if (not isinstance(values, list) or len(values) != size
                or any(not isinstance(value, str) or not value.strip() for value in values)
                or len(set(values)) != size):
            raise ValueError(name + " must contain exactly %d distinct IDs" % size)
    if (set(private_tasks) != set(task_ids) or digest(private_tasks) != protocol.get("task_manifest_sha256")
            or len({task["family"] for task in private_tasks.values()}) != 7):
        raise ValueError("seven-family private manifest differs from preregistration")
    for task in private_tasks.values():
        validate_task(task)
    if not isinstance(configs, dict) or set(configs) != set(models):
        raise ValueError("configs must match both registered models")
    common = []
    for model, config in configs.items():
        if (not isinstance(config, dict) or config.get("model") != model
                or type(config.get("timeout_seconds")) not in (int, float)
                or not 0 < config["timeout_seconds"] <= 180 or config.get("max_tool_calls") != 32):
            raise ValueError("registered model requires timeout <=180 and exactly 32 bounded tool calls")
        common.append({key: value for key, value in config.items() if key not in {"model", "artifact_root"}})
    if common[0] != common[1]:
        raise ValueError("both requested models must use matching tool and runtime settings")
    revision = protocol.get("baseline_revision")
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("baseline_revision must be a full Git SHA")
    conditions = protocol.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) != set(ARMS):
        raise ValueError("exactly the six preregistered conditions are required")
    if any(not isinstance(condition, dict) or not isinstance(condition.get("governance_model"), dict)
           for condition in conditions.values()):
        raise ValueError("each trusted condition requires its exact governance_model")
    expected = trusted_arm_models(conditions["full_rc20"]["governance_model"])
    for arm, model in expected.items():
        if conditions[arm].get("governance_model") != model:
            raise ValueError("registered ablation may only remove its guidance group: " + arm)
    baseline = conditions["rc19"]
    baseline_core = copy.deepcopy(baseline["governance_model"])
    full_core = copy.deepcopy(expected["full_rc20"])
    for model in (baseline_core, full_core):
        model.pop("execution_guidance", None)
        model.pop("version", None)
    if (baseline_core != full_core or baseline["governance_model"].get("execution_guidance")
            or len(full_core.get("policies", [])) != 16 or len(full_core.get("hot_path", [])) != 8):
        raise ValueError("RC19 and RC20 must preserve the same core governance model")
    attention = copy.deepcopy(conditions["attention"])
    if attention.pop("attention_instruction", None) != ATTENTION_INSTRUCTION or attention != baseline:
        raise ValueError("attention condition may only append the fixed attention instruction")
    for arm, condition in conditions.items():
        if not isinstance(condition, dict) or not isinstance(condition.get("skill"), str):
            raise ValueError("each condition requires exact compiled Skill text")
        if arm != "attention" and "attention_instruction" in condition:
            raise ValueError("attention instruction is restricted to the attention arm")
        for field in ("source_sha256", "runtime_sha256", "candidate_sha256"):
            if not tools._sha(condition.get(field)):
                raise ValueError("condition requires exact " + field)
        if condition["candidate_sha256"] != digest(condition["governance_model"]):
            raise ValueError("candidate identity must bind the exact trusted arm model")
        guidance = condition["governance_model"].get("execution_guidance", [])
        if not isinstance(guidance, list) or any(not isinstance(group, dict) for group in guidance):
            raise ValueError("execution_guidance must be a list of groups")
        retained = {group["id"] for group in guidance}
        for group in expected["full_rc20"]["execution_guidance"]:
            if condition["skill"].count(group["statement"]) != int(group["id"] in retained):
                raise ValueError("compiled Skill leaks or omits guidance: " + arm + "/" + group["id"])
        for task_id in task_ids:
            plan = tools._plan(condition, task_id)
            tools.build_prompt(condition["skill"], plan, private_tasks[task_id]["prompt"])
            plan = json.loads(plan) if isinstance(plan, str) else plan
            if not isinstance(plan, dict):
                raise ValueError("compiled plan must be an object")
            active, closures = plan.get("active_rules"), plan.get("required_closures")
            if (not isinstance(active, list) or any(not isinstance(value, str) for value in active)
                    or not isinstance(closures, list) or any(not isinstance(value, str) for value in closures)):
                raise ValueError("exact compiled active rules and closures are required")
            text = "\n".join(closures)
            for group in expected["full_rc20"]["execution_guidance"]:
                count = len(set(group["policy_ids"]) & set(active)) if group["id"] in retained else 0
                if text.count(group["statement"]) != count:
                    raise ValueError("compiled plan leaks or omits guidance: " + arm + "/" + group["id"])
    limits = protocol.get("budget", {})
    if (not isinstance(limits, dict) or type(limits.get("model_calls")) is not int or limits["model_calls"] != 84
            or type(limits.get("tokens")) is not int or not 0 < limits["tokens"] <= 10_000_000
            or type(limits.get("wall_seconds")) not in (int, float)
            or not 0 < limits["wall_seconds"] <= 7200):
        raise ValueError("single-round caps are 84 calls, 10M reported tokens and 7200 seconds")
    return Budget(max_calls=84, max_total_tokens=limits["tokens"], max_seconds=limits["wall_seconds"])


def collect(repo, protocol, private_tasks, configs, output, *, expected_capabilities, service_factory=None):
    """Collect a frozen round, preserving pending calls before dispatch.

    Root supplies already compiled/hash-bound conditions; service_factory is a
    test/trusted-runner adapter seam, not an alternative native implementation.
    """
    from .tool_codex import ToolCodex
    repo, output = Path(repo).resolve(), Path(output).resolve()
    private_tasks = tools._tasks(private_tasks)
    budget = _validate(protocol, private_tasks, configs)
    factory = service_factory or ToolCodex
    services = {model: factory(copy.deepcopy(config)) for model, config in configs.items()}
    capabilities = {model: services[model].binding() for model in protocol["models"]}
    if expected_capabilities is None or capabilities != expected_capabilities:
        raise ValueError("current bounded capabilities differ from the preregistered freeze")
    sequence = order(protocol["models"], protocol["task_ids"], protocol["seed"])
    identities = {"protocol_sha256": digest(protocol), "task_manifest_sha256": digest(private_tasks),
                  "configs_sha256": digest(configs), "capabilities_sha256": digest(capabilities),
                  "engine_sha256": engine_identity(repo, excluded=(output,)), "conditions_sha256": digest(protocol["conditions"]),
                  "order_sha256": digest(sequence)}
    with checkpoint_lock(output):
        if output.exists():
            run = json.loads(output.read_text(encoding="utf-8"))
            if run.get("identities") != identities or run.get("order") != sequence:
                raise ValueError("frozen protocol/task/config/driver/order mismatch")
            if run.get("pending"):
                raise ValueError("pending call requires independent reconciliation; never replay")
            observations = run.get("observations", [])
            if (len(observations) > len(sequence) or any(
                    any(row.get(key) != expected[key] for key in expected)
                    for row, expected in zip(observations, sequence))):
                raise ValueError("checkpoint observations do not preserve the frozen order prefix")
            if run.get("status") != "running":
                return run
            budget = Budget.from_state(run["budget"])
            if budget.calls != len(observations) or len(budget.records) != len(observations):
                raise ValueError("checkpoint charges do not match completed fresh observations")
        else:
            run = {"schema_version": 1, "protocol_id": protocol["protocol_id"], "stage": "independent",
                   "status": "running", "identities": identities, "order": sequence, "observations": [],
                   "pending": None, "budget": budget.state(), "models_requested": protocol["models"],
                   "task_ids": protocol["task_ids"], "capabilities": capabilities, "optimizer_candidate": False,
                   "baseline_revision": protocol["baseline_revision"],
                   "arm_group_differences": {arm: {"removed_guidance": removed, "core_model_preserved": True}
                                             for arm, removed in ABLATIONS.items()},
                   "order_limit": "14 six-arm blocks; Williams rotation is approximately balanced, not a full number of six-row cycles",
                   "provider_family_scope": "same-provider requested models; provider-internal selection/retry coverage unverified",
                   "execution_scope": "existing bounded repository tools; no application-code execution",
                   "runner_scope": "official-cli" if service_factory is None else "injected-trusted-runner",
                   "formal_qualification": "UNASSESSED"}

        def checkpoint():
            run["budget"] = budget.state()
            overrun = budget.overruns(run["budget"])
            if overrun:
                run["actual_budget_overrun"] = overrun
                if run["status"] == "completed":
                    run.update(status="budget-exhausted", stop_reason="terminal measurement exceeded stop threshold")
            if isinstance(run.get("summary"), dict):
                run["summary"]["actual_charged_usage"] = copy.deepcopy(run["budget"])
                run["summary"]["status"] = run["status"]
                if run["status"] != "completed":
                    run["summary"]["gates"]["complete_six_arm_collection"] = False
                    run["summary"]["net_benefit_gate"] = "FAIL"
            save_run(output, run)

        checkpoint()
        for item in sequence[len(run["observations"]):]:
            try:
                budget.reserve()
            except BudgetExceeded as error:
                run.update(status="budget-exhausted", stop_reason=str(error))
                checkpoint()
                return run
            model, task_id, arm = item["model"], item["task_id"], item["condition"]
            condition, task = protocol["conditions"][arm], private_tasks[task_id]
            bindings = {"campaign_id": protocol["protocol_id"], "sample_id": "%s:%s:%s" % (model, task_id, arm),
                        "protocol_sha256": identities["protocol_sha256"], "capability": capabilities[model],
                        "task_manifest_sha256": identities["task_manifest_sha256"],
                        "engine_sha256": identities["engine_sha256"], "configs_sha256": identities["configs_sha256"],
                        "order_sha256": identities["order_sha256"],
                        **{key: condition[key] for key in ("source_sha256", "runtime_sha256", "candidate_sha256")}}
            prompt = tools.build_prompt(condition["skill"], tools._plan(condition, task_id), task["prompt"])
            if arm == "attention":
                prompt += "\n\n" + ATTENTION_INSTRUCTION
            prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            run["pending"] = dict(item, bindings_sha256=digest(bindings), prompt_sha256=prompt_sha)
            checkpoint()
            started, dispatch_error = time.perf_counter(), False
            try:
                raw = services[model].run(copy.deepcopy(task), prompt=prompt, bindings=copy.deepcopy(bindings))
                if not isinstance(raw, dict):
                    raise ValueError("bounded runner must return an object")
                raw = copy.deepcopy(raw)
            except Exception as error:
                dispatch_error = True
                raw = {"status": "failed", "usage": getattr(error, "usage", None),
                       "receipt": getattr(error, "provider_receipt", None),
                       "error": "%s: %s" % (type(error).__name__, error)}
            elapsed = time.perf_counter() - started
            usage = tools._normalized_usage(raw.get("usage"))
            receipt = raw.get("receipt") if isinstance(raw.get("receipt"), dict) else {}
            replayed = receipt.get("replayed_from_local_receipt") is True
            run["observations"].append(dict(item, family=task["family"], sample_id=bindings["sample_id"],
                bindings=bindings, prompt_sha256=prompt_sha, result=raw, usage=usage,
                collector_wall_seconds=elapsed, phase_timings=tools._phase_timings(raw, elapsed),
                independent_sample=not replayed and not dispatch_error, cache_hit=replayed))
            if replayed:
                budget.release_replayed_reservation()
            else:
                budget.record(usage, elapsed_seconds=elapsed, error=raw.get("error"))
            ids = [(row["result"].get("receipt") or {}).get("receipt_sha256") for row in run["observations"]]
            threads = [(row["result"].get("receipt") or {}).get("cli_thread_id") for row in run["observations"]]
            uncertain = (dispatch_error or replayed or not tools._sha(receipt.get("receipt_sha256"))
                         or not isinstance(receipt.get("cli_thread_id"), str) or not receipt.get("cli_thread_id")
                         or receipt.get("prompt_sha256") != prompt_sha or len(set(ids)) != len(ids)
                         or len(set(threads)) != len(threads) or usage is None
                         or any(usage.get(key) is None for key in ("input_tokens", "output_tokens", "total_tokens")))
            if uncertain:
                run.update(status="unknown-call-blocked", stop_reason="uncertain usage/receipt/freshness; independent reconciliation required")
                run["pending"] = {"kind": "unknown-call", "observation_index": len(run["observations"]) - 1}
                checkpoint()
                return run
            try:
                transport = tools._transport_failure(raw)
            except (OSError, ValueError, UnicodeError):
                run.update(status="unknown-call-blocked", stop_reason="transport evidence unconfirmed; known charge retained")
                run["pending"] = {"kind": "transport-evidence-unconfirmed"}
                checkpoint()
                return run
            run["pending"] = None
            if transport or budget.overruns():
                run.update(status="blocked_transport" if transport else "budget-exhausted",
                           stop_reason="transport unavailable" if transport else "measured call exceeded stop threshold")
                if transport:
                    run.update(transport_failure=transport, new_protocol_required=True)
                checkpoint()
                return run
            checkpoint()
        run["status"] = "completed"
        checkpoint()
        run["summary"] = summarize(run)
        checkpoint()
        if run["status"] != "completed":
            run["summary"] = summarize(run)
            checkpoint()
        return run


def _quality_pass(result):
    quality = result.get("quality") or {}
    return (result.get("status") == "completed" and quality.get("hard_pass") is True
            and quality.get("task_success") == 1 and quality.get("scope_ok") is True
            and quality.get("required_tools_ok") is True)


def summarize(run, *, repetitions=4000, seed=SEED):
    """Full vs both controls; all ablations remain diagnostic, never winners."""
    if type(repetitions) is not int or repetitions < 1 or type(seed) is not int:
        raise ValueError("valid bootstrap repetitions/seed are required")
    rows = run.get("observations", [])
    cells = {(row["model"], row["task_id"], row["condition"]): row for row in rows}
    expected = {(model, task, arm) for model in run["models_requested"] for task in run["task_ids"] for arm in ARMS}
    complete = run.get("status") == "completed" and len(rows) == len(cells) == 84 and set(cells) == expected
    quality = bool(rows) and all(_quality_pass(row["result"]) for row in rows)
    receipts = [(row["result"].get("receipt") or {}).get("receipt_sha256") for row in rows]
    threads = [(row["result"].get("receipt") or {}).get("cli_thread_id") for row in rows]
    fresh = bool(rows) and all(row.get("independent_sample") is True and not row.get("cache_hit") for row in rows)
    unique = (bool(rows) and all(tools._sha(value) for value in receipts) and len(set(receipts)) == len(receipts)
              and all(isinstance(value, str) and value for value in threads) and len(set(threads)) == len(threads))
    task_families = {task: {row["family"] for row in rows if row["task_id"] == task} for task in run["task_ids"]}
    family_coverage = (len(task_families) == 7 and all(len(values) == 1 for values in task_families.values())
                       and len(set().union(*task_families.values())) == 7)
    known_usage = bool(rows) and all(isinstance(row.get("usage"), dict)
        and all(type(row["usage"].get(key)) is int and row["usage"][key] >= 0
                for key in ("input_tokens", "output_tokens", "total_tokens")) for row in rows)
    ready = complete and quality and fresh and unique and family_coverage and known_usage
    comparisons, diagnostics = {}, {}
    for control in ("rc19", "attention", *ABLATIONS):
        pairs = [(cells[(model, task, control)], cells[(model, task, "full_rc20")])
                 for model in run["models_requested"] for task in run["task_ids"]
                 if (model, task, control) in cells and (model, task, "full_rc20") in cells]
        metrics = {metric: tools._joint_family_metric(pairs, metric, repetitions, seed) if ready else None
                   for metric in ("total_tokens", "wall_seconds")}
        per_model = {model: {metric: tools._metric([pair for pair in pairs if pair[0]["model"] == model],
                                                    metric, repetitions, seed) if ready else None
                             for metric in ("total_tokens", "wall_seconds")} for model in run["models_requested"]}
        result = {"metrics": metrics, "per_model": per_model}
        if control in ABLATIONS:
            diagnostics[control] = dict(result, diagnostic_only=True, selection_allowed=False)
        else:
            comparisons[control] = result
    cost_gates = []
    for comparison in comparisons.values():
        for metric in ("total_tokens", "wall_seconds"):
            interval = (comparison["metrics"][metric] or {}).get("paired_joint_family_bootstrap_95_interval")
            cost_gates.append(interval is not None and interval[1] < 1)
            cost_gates.append(all((values[metric] or {}).get("ratio") is not None
                                  and values[metric]["ratio"] < 1 for values in comparison["per_model"].values()))
    full_rows = [row for row in rows if row["condition"] == "full_rc20"]
    full_failures = sum(not _quality_pass(row["result"]) for row in full_rows)
    return {"status": run.get("status"), "net_benefit_gate": "PASS" if ready and all(cost_gates) else "FAIL",
            "gates": {"complete_six_arm_collection": complete, "all_task_quality_pass": quality,
                      "all_fresh_calls": fresh, "unique_receipts_and_threads": unique,
                      "shared_task_family_coverage": family_coverage, "known_reported_usage": known_usage},
            "comparisons": comparisons, "ablation_diagnostics": diagnostics,
            "actual_charged_usage": copy.deepcopy(run.get("budget")), "optimizer_candidate": False,
            "finite_scope_quality": {"full_arm_trials": len(full_rows), "full_arm_failures": full_failures,
                "zero_failure_one_sided_95_binomial_upper": 1 - .05 ** (1 / len(full_rows))
                    if full_rows and full_failures == 0 else None,
                "population_noninferiority": "UNASSESSED",
                "bound_limit": "illustrative independent-trial binomial bound; task-family/model dependence limits population inference"},
            "bootstrap": {"method": "paired shared task-family blocks retaining both requested models",
                          "repetitions": repetitions, "seed": seed, "confidence": .95},
            "formal_qualification": "UNASSESSED", "order_limit": run.get("order_limit"),
            "cost_limit": "reported completed-turn usage; provider-internal retries unverified; no hard token pre-cap"}
