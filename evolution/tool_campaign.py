"""Frozen matched real-tool collection with honest cost and coverage limits.

The bounded broker inspects and edits artifacts; it never executes application
code. Multiple requested OpenAI models are not multiple provider families.
Collection can establish scoped paired benefit, never formal qualification.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import random
import time

from .contracts import Budget, BudgetExceeded, digest
from .controller import checkpoint_lock, engine_identity, save_run
from .tool_broker import TOOLS

CONDITIONS = ("control", "treatment")
BOOTSTRAP_SEED = 19012
BOOTSTRAP_REPETITIONS = 4000


def build_prompt(skill, plan, task_prompt):
    """Preserve exact Skill/planner strings; hidden grader checks stay private."""
    if not isinstance(skill, str) or not isinstance(task_prompt, str):
        raise ValueError("skill and task prompt must be exact strings")
    if isinstance(plan, str):
        if not isinstance(json.loads(plan), dict):
            raise ValueError("planner text must encode an object")
        plan_text = plan
    elif isinstance(plan, dict):
        plan_text = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    else:
        raise ValueError("explicit planner object or exact planner text is required")
    common = ("Perform the maintained-project task with the supplied Skill and task plan. "
              "Use only the provided bounded repository tools. Read the affected files, apply the requested patch, "
              "validate the result and inspect repository status using repo_read, repo_patch, repo_validate and repo_status. "
              "project_tool and persistent governance state are unavailable in this broker; follow the supplied governance plan and disclose the helper gap. "
              "Do not probe unregistered/hidden paths. "
              "The broker cannot execute application code. Finish with only JSON containing summary (string), "
              "validation ('passed' or 'failed'), and helper_gap ('project_tool unavailable in bounded broker').")
    # Delimiters leave plan_text byte-for-byte unchanged inside the prompt.
    return common + "\n\n<governance_skill>\n" + skill + "\n</governance_skill>\n\n<governance_plan>\n" + plan_text + "\n</governance_plan>\n\n<task>\n" + task_prompt + "\n</task>"


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _tasks(private_tasks):
    if isinstance(private_tasks, list):
        ids = [task.get("id") if isinstance(task, dict) else None for task in private_tasks]
        if any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("private task list contains invalid or duplicate IDs")
        private_tasks = dict(zip(ids, private_tasks))
    if not isinstance(private_tasks, dict) or not private_tasks:
        raise ValueError("private_tasks must be a nonempty map keyed by task ID")
    for key, task in private_tasks.items():
        if not isinstance(task, dict) or task.get("id") != key or not isinstance(task.get("family"), str) or not task["family"]:
            raise ValueError("private task IDs/families must be explicit and unique")
        if not isinstance(task.get("prompt"), str):
            raise ValueError("private task requires a prompt")
    return private_tasks


def _plan(condition, task_id):
    if "plan_text" in condition:
        value = condition["plan_text"]
        if isinstance(value, dict):
            if task_id not in value:
                raise ValueError("condition lacks exact planner text for task " + task_id)
            return value[task_id]
        return value
    if "plans" in condition:
        return condition["plans"][task_id]
    return condition.get("plan")


def _order(models, task_ids, seed):
    rng = random.Random(seed)
    pairs = [(model, task_id) for model in models for task_id in task_ids]
    rng.shuffle(pairs)
    first = {model: rng.randrange(2) for model in models}
    seen = dict.fromkeys(models, 0)
    order = []
    for pair_index, (model, task_id) in enumerate(pairs):
        start = (first[model] + seen[model]) % 2
        seen[model] += 1
        conditions = CONDITIONS if start == 0 else tuple(reversed(CONDITIONS))
        for condition in conditions:
            order.append({"model": model, "task_id": task_id, "condition": condition,
                          "pair_index": pair_index, "sample_index": len(order)})
    return order


def _family_order(models, task_ids, seed, private_tasks):
    """Shuffle matched pairs, alternating the first arm within each stratum."""
    rng = random.Random(seed)
    pairs = [(model, task_id) for model in models for task_id in task_ids]
    rng.shuffle(pairs)
    first, seen, order = {}, {}, []
    for pair_index, (model, task_id) in enumerate(pairs):
        group = (model, private_tasks[task_id]["family"])
        if group not in first:
            first[group], seen[group] = rng.randrange(2), 0
        start = (first[group] + seen[group]) % 2
        seen[group] += 1
        conditions = CONDITIONS if start == 0 else tuple(reversed(CONDITIONS))
        for condition in conditions:
            order.append({"model": model, "task_id": task_id, "condition": condition,
                          "pair_index": pair_index, "sample_index": len(order)})
    return order


def _validate(protocol, private_tasks, configs):
    if not isinstance(protocol, dict) or not isinstance(protocol.get("protocol_id"), str) or not protocol["protocol_id"]:
        raise ValueError("explicit protocol_id is required")
    if protocol.get("stage") not in {"development", "independent"}:
        raise ValueError("campaign stage must be development or independent")
    models, task_ids = protocol.get("models"), protocol.get("task_ids")
    for values, name in ((models, "models"), (task_ids, "task_ids")):
        if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
            raise ValueError(name + " must contain unique explicit IDs")
    if type(protocol.get("seed")) is not int:
        raise ValueError("campaign requires an integer order seed")
    if "order_stratification" in protocol:
        if not isinstance(protocol["order_stratification"], str) or protocol["order_stratification"] != "model-task-family":
            raise ValueError("unsupported order_stratification; use model-task-family or omit the field")
    if not isinstance(configs, dict) or set(configs) != set(models):
        raise ValueError("configs must match every requested model exactly")
    if any(not isinstance(config, dict) or config.get("model") != model for model, config in configs.items()):
        raise ValueError("native config/model identity mismatch")
    _tasks(private_tasks)
    if "order_stratification" in protocol and any(not task["family"].strip() for task in private_tasks.values()):
        raise ValueError("model-task-family ordering requires explicit nonempty task families")
    if set(task_ids) != set(private_tasks) or digest(private_tasks) != protocol.get("task_manifest_sha256"):
        raise ValueError("private task manifest differs from preregistration")
    revision = protocol.get("baseline_revision")
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("baseline_revision must be a full Git revision")
    if not isinstance(protocol.get("conditions"), dict) or set(protocol["conditions"]) != set(CONDITIONS):
        raise ValueError("campaign requires exactly control/treatment")
    for name, condition in protocol["conditions"].items():
        if not isinstance(condition, dict) or not isinstance(condition.get("skill"), str):
            raise ValueError("condition requires exact Skill text")
        for field in ("source_sha256", "runtime_sha256", "candidate_sha256"):
            if not _sha(condition.get(field)):
                raise ValueError("condition requires exact " + field)
        for task_id in task_ids:
            build_prompt(condition["skill"], _plan(condition, task_id), private_tasks[task_id]["prompt"])
    acceptance = protocol.get("acceptance", {})
    if not isinstance(acceptance, dict):
        raise ValueError("acceptance thresholds must be an object")
    for key in ("tokens_ci_upper_exclusive", "wall_ci_upper_exclusive", "per_model_ratio_exclusive"):
        value = acceptance.get(key, 1.0)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError("invalid or weakened acceptance threshold: " + key)
    limits = protocol.get("budget", {})
    return Budget(max_calls=limits["model_calls"], max_total_tokens=limits["tokens"], max_seconds=limits["wall_seconds"])


def _normalized_usage(raw):
    if not isinstance(raw, dict):
        return None
    usage = copy.deepcopy(raw)
    for name, alias in (("cached_tokens", "cached_input_tokens"), ("reasoning_tokens", "reasoning_output_tokens")):
        if name not in usage:
            usage[name] = usage.get(alias)
    for name in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens", "reasoning_tokens"):
        value = usage.get(name)
        if value is not None and (type(value) is not int or value < 0):
            return None
    total, inputs, outputs = (usage.get(name) for name in ("total_tokens", "input_tokens", "output_tokens"))
    if total is not None and inputs is not None and outputs is not None and total != inputs + outputs:
        return None
    return usage


def _cli_seconds(raw):
    timing = raw.get("timing")
    if not isinstance(timing, dict):
        timing = (raw.get("receipt") or {}).get("timing")
    return timing.get("cli_seconds") if isinstance(timing, dict) else None


def _phase_timings(raw, elapsed):
    cli = _cli_seconds(raw)
    return {"collector_total_seconds": elapsed, "adapter_seconds": raw.get("wall_seconds"),
            "cli_seconds": cli, "non_cli_seconds": max(0, elapsed - cli) if _finite(cli) else None}


def _transport_failure(raw):
    """Recognize only a known CLI transport error, never a model self-report.

    Ordinary failed tasks remain observations. For a completed, failed no-tool
    result, the raw CLI artifact must be verified before deciding whether the
    known transport-wide failure occurred; unverifiable evidence fences replay.
    """
    if (raw.get("status") != "completed" or (raw.get("quality") or {}).get("hard_pass") is not False
            or raw.get("tool_events") != []):
        return None
    receipt = raw.get("receipt") or {}
    expected = (receipt.get("artifact_sha256") or {}).get("stdout.raw")
    directory = receipt.get("artifact_directory")
    if not _sha(expected) or not isinstance(directory, str) or not Path(directory).is_absolute():
        raise ValueError("transport-stdout-evidence-missing")
    payload = (Path(directory) / "stdout.raw").read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("transport-stdout-sha256-mismatch")
    for line_number, line in enumerate(payload.decode("utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # The adapter also ignores non-JSON CLI diagnostic lines.
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        message = item.get("message") if kind == "error" else None
        prefix = "Code Mode is unavailable because code-mode host is disabled."
        if isinstance(message, str) and message.startswith(prefix):
            return {"code": "code-mode-host-disabled", "stdout_sha256": expected,
                    "event_line": line_number, "event_type": "item.completed", "item_type": "error",
                    "message": message}
        if (kind != "mcp_tool_call" or item.get("status") != "failed"
                or item.get("server") != "upg_repo" or item.get("tool") not in TOOLS):
            continue
        error = item.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        if message != "MCP tool call requires approval, but approval policy is never":
            continue
        arguments = item.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                continue
        if not isinstance(arguments, dict):
            continue
        try:
            arguments_sha256 = digest(arguments)
        except (TypeError, ValueError):
            continue
        return {"code": "registered-mcp-approval-policy-never", "stdout_sha256": expected,
                "event_line": line_number, "event_type": "item.completed", "item_type": kind,
                "server": item["server"], "tool": item["tool"], "arguments_sha256": arguments_sha256,
                "message": message}
    return None


def collect(repo, protocol, private_tasks, configs, output, *, expected_capabilities=None):
    """Serial, resumable collection; every dispatched sample is fenced first."""
    from .tool_codex import ToolCodex
    setup_started = time.perf_counter()
    repo, output = Path(repo).resolve(), Path(output).resolve()
    private_tasks = _tasks(private_tasks)
    budget = _validate(protocol, private_tasks, configs)
    services = {model: ToolCodex(copy.deepcopy(config)) for model, config in configs.items()}
    capabilities = {model: services[model].binding() for model in protocol["models"]}
    if expected_capabilities is not None and digest(capabilities) != digest(expected_capabilities):
        raise ValueError("current tool capabilities differ from the preregistered freeze")
    identities = {"protocol_sha256": digest(protocol), "task_manifest_sha256": digest(private_tasks),
                  "configs_sha256": digest(configs), "capabilities_sha256": digest(capabilities),
                  "engine_sha256": engine_identity(repo), "conditions_sha256": digest(protocol["conditions"])}
    if "order_stratification" in protocol:
        order = _family_order(protocol["models"], protocol["task_ids"], protocol["seed"], private_tasks)
    else:
        order = _order(protocol["models"], protocol["task_ids"], protocol["seed"])
    identities["order_sha256"] = digest(order)
    with checkpoint_lock(output):
        if output.exists():
            run = json.loads(output.read_text(encoding="utf-8"))
            if run.get("identities") != identities or run.get("order") != order:
                raise ValueError("campaign checkpoint protocol/task/config/capability/engine mismatch")
            if run.get("joint_family_intervals_required") is not True:
                raise ValueError("campaign checkpoint lacks required joint-family interval contract")
            if "order_stratification" in protocol and run.get("order_stratification") != protocol["order_stratification"]:
                raise ValueError("campaign checkpoint lacks preregistered order stratification")
            if run.get("pending"):
                raise ValueError("campaign pending call requires independent reconciliation; never automatic replay")
            if run.get("status") != "running":
                return run
            budget = Budget.from_state(run["budget"])
        else:
            run = {"schema_version": 1, "protocol_id": protocol["protocol_id"], "stage": protocol["stage"],
                   "status": "running", "identities": identities, "order": order, "observations": [],
                   "joint_family_intervals_required": True,
                   "pending": None, "budget": budget.state(), "capabilities": capabilities,
                   "models_requested": protocol["models"], "task_ids": protocol["task_ids"],
                   "conditions": {name: {key: value for key, value in condition.items()
                                         if key.endswith("sha256")} for name, condition in protocol["conditions"].items()},
                   "acceptance": protocol.get("acceptance", {}), "baseline_revision": protocol["baseline_revision"],
                   "formal_qualification": "UNASSESSED", "provider_family_scope": "same-provider requested OpenAI models",
                   "application_execution": False, "isolation_attested": False,
                   "source_preparation": protocol.get("source_preparation", {"status": "not measured by collector; source prepared before task calls"}),
                   "collector_setup_seconds": time.perf_counter() - setup_started,
                   "budget_scope": "actual new CLI attempts; token/time stop thresholds are checked after each measured call"}
            if "order_stratification" in protocol:
                run["order_stratification"] = protocol["order_stratification"]

        def checkpoint():
            # Publish one advancing budget snapshot everywhere in this write.
            # Terminal summary work can itself cross a wall stop threshold.
            snapshot = budget.state()
            run["budget"] = snapshot
            if run.get("status") != "running":
                terminal_overrun = budget.overruns(snapshot)
                if terminal_overrun:
                    run["actual_budget_overrun"] = terminal_overrun
                    if run.get("status") == "completed":
                        run.update(status="budget-exhausted", stop_reason="terminal measurement exceeded a stop threshold")
            if isinstance(run.get("summary"), dict):
                run["summary"]["actual_charged_usage"] = copy.deepcopy(snapshot)
                run["summary"]["status"] = run["status"]
                if run["status"] != "completed":
                    run["summary"]["gates"]["complete_matched_collection"] = False
                    run["summary"]["net_benefit_gate"] = "FAIL"
            save_run(output, run)

        checkpoint()
        for item in order[len(run["observations"]):]:
            try:
                budget.reserve()
            except BudgetExceeded as error:
                run.update(status="budget-exhausted", stop_reason=str(error))
                checkpoint()
                return run
            model, task_id, condition_name = item["model"], item["task_id"], item["condition"]
            condition, task = protocol["conditions"][condition_name], private_tasks[task_id]
            sample_id = "%s:%s:%s" % (model, task_id, condition_name)
            bindings = {"campaign_id": protocol["protocol_id"], "sample_id": sample_id,
                        "protocol_sha256": identities["protocol_sha256"], "capability": capabilities[model],
                        "source_sha256": condition["source_sha256"], "runtime_sha256": condition["runtime_sha256"],
                        "candidate_sha256": condition["candidate_sha256"],
                        "task_manifest_sha256": identities["task_manifest_sha256"],
                        "engine_sha256": identities["engine_sha256"]}
            prompt = build_prompt(condition["skill"], _plan(condition, task_id), task["prompt"])
            prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            run["pending"] = dict(item, sample_id=sample_id, bindings_sha256=digest(bindings), prompt_sha256=prompt_sha256)
            checkpoint()
            started = time.perf_counter()
            dispatch_error = False
            try:
                raw = services[model].run(copy.deepcopy(task), prompt=prompt, bindings=bindings)
                if not isinstance(raw, dict):
                    raise ValueError("ToolCodex result must be an object")
                raw = copy.deepcopy(raw)
            except Exception as error:
                dispatch_error = True
                raw = {"status": "failed", "usage": getattr(error, "usage", None),
                       "receipt": getattr(error, "receipt", getattr(error, "provider_receipt", None)),
                       "error": "%s: %s" % (type(error).__name__, error)}
            # Interruptions leave the already durable pending record in place.
            elapsed = time.perf_counter() - started
            receipt = raw.get("receipt") if isinstance(raw.get("receipt"), dict) else {}
            replayed = receipt.get("replayed_from_local_receipt") is True
            usage = _normalized_usage(raw.get("usage"))
            row = dict(item, family=task["family"], sample_id=sample_id, bindings=bindings,
                       prompt_sha256=prompt_sha256, result=raw, collector_wall_seconds=elapsed,
                       phase_timings=_phase_timings(raw, elapsed),
                       usage=usage, independent_sample=not replayed and not dispatch_error, cache_hit=replayed)
            run["observations"].append(row)
            if replayed:
                budget.release_replayed_reservation()
            else:
                budget.record(usage, elapsed_seconds=elapsed, error=raw.get("error"))
            if dispatch_error or not receipt or (not replayed and (usage is None or usage.get("total_tokens") is None)):
                run.update(status="unknown-call-blocked", stop_reason="uncertain call or incomplete evidence; independent reconciliation required")
                run["pending"] = {"kind": "unknown-call", "sample_id": sample_id, "observation_index": len(run["observations"]) - 1}
                checkpoint()
                return run
            try:
                transport_failure = _transport_failure(raw)
            except (OSError, ValueError, UnicodeError) as error:
                run.update(status="unknown-call-blocked",
                           stop_reason="transport evidence could not be verified; independent reconciliation required",
                           transport_evidence_error={"error_type": type(error).__name__,
                                                     "known_usage_retained": True})
                run["pending"] = {"kind": "transport-evidence-unconfirmed", "sample_id": sample_id,
                                  "observation_index": len(run["observations"]) - 1}
                checkpoint()
                return run
            run["pending"] = None
            overrun = budget.overruns()
            if transport_failure:
                run.update(status="blocked_transport", new_protocol_required=True,
                           stop_reason="known CLI tool transport unavailable; a new protocol is required after correction",
                           transport_failure=dict(transport_failure, sample_id=sample_id,
                                                  observation_index=len(run["observations"]) - 1))
                if overrun:
                    run["actual_budget_overrun"] = overrun
                checkpoint()  # Retain the known completed charge before stopping.
                run["summary"] = summarize(run)
                checkpoint()
                return run
            if overrun:
                run.update(status="budget-exhausted", actual_budget_overrun=overrun,
                           stop_reason="measured call exceeded a stop threshold")
                checkpoint()
                return run
            checkpoint()
        run["status"] = "completed"
        checkpoint()
        run["summary"] = summarize(run)
        checkpoint()
        return run


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _value(row, metric):
    if metric == "total_tokens":
        return (row.get("usage") or {}).get("total_tokens")
    if metric == "wall_seconds":
        return row.get("collector_wall_seconds")
    if metric == "cli_wall_seconds":
        return _cli_seconds(row["result"])
    events = row["result"].get("tool_events")
    return len(events) if isinstance(events, list) else None


def _metric(pairs, metric, repetitions, seed):
    if not pairs or any(not _finite(_value(row, metric)) for pair in pairs for row in pair):
        return None
    control = sum(_value(pair[0], metric) for pair in pairs)
    treatment = sum(_value(pair[1], metric) for pair in pairs)
    if control <= 0:
        return {"control_total": control, "treatment_total": treatment, "ratio": None,
                "paired_model_family_bootstrap_95_interval": None}
    blocks = {}
    for pair in pairs:
        blocks.setdefault(pair[0]["model"], {}).setdefault(pair[0]["family"], []).append(pair)
    rng, ratios = random.Random(seed), []
    for unused in range(repetitions):
        sample = []
        for model in sorted(blocks):
            families = sorted(blocks[model])
            for unused_family in families:
                sample.extend(blocks[model][rng.choice(families)])
        denominator = sum(_value(pair[0], metric) for pair in sample)
        if denominator > 0:
            ratios.append(sum(_value(pair[1], metric) for pair in sample) / denominator)
    ratios.sort()
    interval = ([ratios[int(len(ratios) * .025)], ratios[min(len(ratios) - 1, int(len(ratios) * .975))]]
                if ratios else None)
    return {"control_total": control, "treatment_total": treatment, "ratio": treatment / control,
            "savings_fraction": 1 - treatment / control,
            "paired_model_family_bootstrap_95_interval": interval}


def _joint_family_metric(pairs, metric, repetitions, seed):
    """Resample shared families, retaining every model/pair in each block."""
    if not pairs or any(not _finite(_value(row, metric)) for pair in pairs for row in pair):
        return None
    control = sum(_value(pair[0], metric) for pair in pairs)
    treatment = sum(_value(pair[1], metric) for pair in pairs)
    blocks = {}
    for pair in pairs:
        blocks.setdefault(pair[0]["family"], []).append(pair)
    families, ratios, rng = sorted(blocks), [], random.Random(seed)
    if control > 0:
        for unused in range(repetitions):
            sample = [pair for unused_family in families for pair in blocks[rng.choice(families)]]
            denominator = sum(_value(pair[0], metric) for pair in sample)
            if denominator > 0:
                ratios.append(sum(_value(pair[1], metric) for pair in sample) / denominator)
    ratios.sort()
    interval = ([ratios[int(len(ratios) * .025)], ratios[min(len(ratios) - 1, int(len(ratios) * .975))]]
                if ratios else None)
    return {"control_total": control, "treatment_total": treatment,
            "ratio": treatment / control if control > 0 else None,
            "savings_fraction": 1 - treatment / control if control > 0 else None,
            "paired_joint_family_bootstrap_95_interval": interval}


def summarize(run, *, repetitions=BOOTSTRAP_REPETITIONS, seed=BOOTSTRAP_SEED):
    if type(repetitions) is not int or repetitions < 1 or type(seed) is not int:
        raise ValueError("bootstrap repetitions/seed must be explicit valid integers")
    observations = run.get("observations", [])
    cells, duplicate = {}, False
    for row in observations:
        key = (row["model"], row["task_id"], row["condition"])
        duplicate = duplicate or key in cells
        cells[key] = row
    pairs = [(cells[(model, task_id, "control")], cells[(model, task_id, "treatment")])
             for model in run["models_requested"] for task_id in run["task_ids"]
             if all((model, task_id, condition) in cells for condition in CONDITIONS)]
    expected = len(run["models_requested"]) * len(run["task_ids"])
    complete = run.get("status") == "completed" and not duplicate and len(pairs) == expected and len(observations) == expected * 2
    fresh = bool(observations) and all(row.get("independent_sample") is True and not row.get("cache_hit") for row in observations)
    receipt_ids = [(row["result"].get("receipt") or {}).get("receipt_sha256") for row in observations]
    unique_receipts = bool(receipt_ids) and all(_sha(value) for value in receipt_ids) and len(set(receipt_ids)) == len(receipt_ids)
    quality = bool(observations) and all(row["result"].get("status") == "completed"
        and (row["result"].get("quality") or {}).get("hard_pass") is True
        and (row["result"].get("quality") or {}).get("task_success") == 1
        and (row["result"].get("quality") or {}).get("scope_ok") is True
        and (row["result"].get("quality") or {}).get("required_tools_ok") is True for row in observations)
    metrics = {name: _metric(pairs, name, repetitions, seed) for name in ("total_tokens", "wall_seconds", "cli_wall_seconds", "tool_calls")}
    per_model = {model: {name: _metric([pair for pair in pairs if pair[0]["model"] == model], name, repetitions, seed)
                         for name in ("total_tokens", "wall_seconds", "cli_wall_seconds", "tool_calls")} for model in run["models_requested"]}
    thresholds = run.get("acceptance", {})
    gates = {"complete_matched_collection": complete, "all_task_quality_pass": quality,
             "all_new_model_calls": fresh, "unique_raw_call_receipts": unique_receipts,
             "at_least_two_families_per_model": all(len({pair[0]["family"] for pair in pairs if pair[0]["model"] == model}) >= 2
                                                      for model in run["models_requested"])}
    for metric, key in (("total_tokens", "tokens_ci_upper_exclusive"), ("wall_seconds", "wall_ci_upper_exclusive")):
        interval = (metrics[metric] or {}).get("paired_model_family_bootstrap_95_interval")
        gates[metric + "_ci_upper_improves"] = interval is not None and interval[1] < thresholds.get(key, 1.0)
        gates[metric + "_every_model_point_improves"] = all(
            (values[metric] or {}).get("ratio") is not None
            and values[metric]["ratio"] < thresholds.get("per_model_ratio_exclusive", 1.0) for values in per_model.values())
    joint = None
    if "joint_family_intervals_required" in run:
        families_by_model = [{pair[0]["family"] for pair in pairs if pair[0]["model"] == model}
                             for model in run["models_requested"]]
        task_families = {}
        for pair in pairs:
            task_families.setdefault(pair[0]["task_id"], set()).update(row["family"] for row in pair)
        coverage = (run["joint_family_intervals_required"] is True and complete
                    and len(families_by_model) >= 2 and len(families_by_model[0]) >= 2
                    and all(families == families_by_model[0] for families in families_by_model)
                    and all(len(families) == 1 for families in task_families.values()))
        gates["joint_family_complete_cross_model_coverage"] = coverage
        joint = {name: _joint_family_metric(pairs, name, repetitions, seed) if coverage else None
                 for name in ("total_tokens", "wall_seconds")}
        for metric, key in (("total_tokens", "tokens_ci_upper_exclusive"), ("wall_seconds", "wall_ci_upper_exclusive")):
            interval = (joint[metric] or {}).get("paired_joint_family_bootstrap_95_interval")
            gates[metric + "_joint_family_ci_upper_improves"] = interval is not None and interval[1] < thresholds.get(key, 1.0)
    summary = {"status": run.get("status"), "matched_pairs": len(pairs), "expected_pairs": expected,
            "net_benefit_gate": "PASS" if all(gates.values()) else "FAIL", "gates": gates,
            "transport_failure": run.get("transport_failure"),
            "new_protocol_required": run.get("new_protocol_required", False),
            "metrics": metrics, "per_model": per_model, "actual_charged_usage": run.get("budget"),
            "source_preparation": run.get("source_preparation"),
            "formal_qualification": "UNASSESSED", "stage": run.get("stage"),
            "provider_family_scope": "same-provider requested OpenAI models; not multiple provider families",
            "execution_scope": "bounded real repository tools and AST/data inspection; no application-code execution",
            "bootstrap": {"method": "paired-task-family-block-bootstrap-stratified-by-requested-model",
                          "repetitions": repetitions, "seed": seed, "confidence": .95},
            "budget_limit": "actual reported CLI usage; no guaranteed provider token hard pre-cap"}
    if joint is not None:
        summary.update(joint_family_intervals_required=True, joint_family_metrics=joint,
                       joint_family_bootstrap={"method": "paired-shared-task-family-block-bootstrap-joint-across-requested-models",
                                               "block_members": "all matched pairs from all requested models in the sampled family",
                                               "repetitions": repetitions, "seed": seed, "confidence": .95})
    return summary
