"""Budgeted, checkpointed joint search. Exploration acceptance is not promotion."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import inspect
import json
import math
from pathlib import Path
import random
import sys
import time
import uuid

from .contracts import Budget, BudgetExceeded, candidate_id, digest
from .evaluator import candidate_source, evaluate, source_hash, validate_candidate
from .search import AdaptiveDE, ChaoticAnnealing, local_sample_points, negative_curvature_candidates

OPERATORS = ("skillopt", "annealing", "de", "curvature")


@contextmanager
def checkpoint_lock(path):
    """One writer per checkpoint; stale locks require explicit reconciliation."""
    lock = Path(str(Path(path).resolve()) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    owner = uuid.uuid4().hex
    try:
        stream = lock.open("x", encoding="ascii")
    except FileExistsError as exc:
        raise ValueError("checkpoint has an active or unreconciled writer lock") from exc
    try:
        stream.write(owner)
        stream.flush()
        yield
    finally:
        stream.close()
        if lock.exists() and lock.read_text(encoding="ascii") == owner:
            lock.unlink()


def save_run(path, run):
    """Atomic same-volume checkpoints; a failed replace preserves last state."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(run, stream, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)


def engine_identity(repo):
    root = Path(repo)
    paths = [p for directory in ("evolution", "third_party/skillopt", "compiler", "tests/fixtures")
             for p in (root / directory).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}]
    paths += [root / "tools/governance_lint.py"]
    return digest({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(paths)})


def callable_identity(function):
    if function is None:
        return {"id": "local-engineering", "version": "no-model-invocation"}
    path = Path(inspect.getfile(function))
    return {"id": function.__module__ + ":" + function.__name__,
            "version": hashlib.sha256(path.read_bytes()).hexdigest()}


def run_search(repo, protocol, output, *, runner=None, backend=None, resume=False,
               disabled=(), ordinary=False, stop_after=None):
    with checkpoint_lock(output):
        return _run_search(repo, protocol, output, runner=runner, backend=backend,
                           resume=resume, disabled=disabled, ordinary=ordinary, stop_after=stop_after)


def _run_search(repo, protocol, output, *, runner=None, backend=None, resume=False,
               disabled=(), ordinary=False, stop_after=None):
    """Execute a bounded search; final/holdout tasks are never sent to operators.

    External callbacks are operator-configured trusted code. Their receipt and
    complete actual usage remain subject to independent evidence admission.
    """
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if sys.version_info < (3, 10):
        raise ValueError("offline evolution requires Python 3.10+; installed runtime supports 3.8+")
    unknown = set(disabled) - set(OPERATORS)
    if unknown:
        raise ValueError("unknown operator: " + ",".join(sorted(unknown)))
    if "skillopt" not in disabled and backend is None and runner is not None:
        raise ValueError("real task mode requires an explicit learner backend or --disable skillopt")
    if (backend is None) != (runner is None) and "skillopt" not in disabled:
        raise ValueError("a real learner requires a real task runner; fixtures cannot mix with empirical tasks")
    budget_spec = protocol["budget"]
    max_candidates = int(budget_spec.get("candidates", 128))
    iterations = int(protocol.get("search", {}).get("iterations", 4))
    population_size = int(protocol.get("search", {}).get("population", 6))
    if not 4 <= population_size <= 64 or not 1 <= max_candidates <= 10000 or not 1 <= iterations <= 1000:
        raise ValueError("invalid bounded search configuration")
    # Redirect round allocation to surviving modules while retaining total caps.
    active_count = len(set(OPERATORS) - set(disabled))
    if active_count:
        iterations = min(1000, math.ceil(iterations * len(OPERATORS) / active_count))
    mode = "engineering" if runner is None else "development-real-task"
    registered = protocol.get("tasks", {})
    split_ids = {}
    for split in ("training", "selection", "final"):
        rows = registered.get(split, [])
        ids = [row["id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate task in " + split + " split")
        split_ids[split] = set(ids)
    if any(split_ids[left] & split_ids[right] for left, right in
           (("training", "selection"), ("training", "final"), ("selection", "final"))):
        raise ValueError("task identity leaks across development/selection/final splits")
    if runner is not None and active_count and not registered.get("selection"):
        raise ValueError("real candidate search requires a separate registered selection split")
    identities = {"source": source_hash(repo), "engine": engine_identity(repo),
                  "runner": callable_identity(runner), "backend": callable_identity(backend),
                  "disabled": sorted(disabled), "ordinary": ordinary}
    if resume:
        run = json.loads(output.read_text(encoding="utf-8"))
        if run["protocol_sha256"] != digest(protocol) or run["identities"] != identities:
            raise ValueError("checkpoint source/protocol/engine/runner identity mismatch")
        if run.get("pending"):
            raise ValueError("an interrupted callback has uncertain usage; reconcile its receipt before resuming")
        budget = Budget.from_state(run["budget"])
        if run["status"] == "completed":
            return run
    else:
        if output.exists():
            raise ValueError("output already exists; use --resume or a new run path")
        baseline = {"model": json.loads((repo / "governance-src/model/governance-model.json").read_text(encoding="utf-8")),
                    "theta": [0.5, 0.5, 0.5], "operator": "baseline"}
        budget = Budget(max_calls=int(budget_spec.get("model_calls", 32)),
                        max_total_tokens=int(budget_spec.get("tokens", 100000)),
                        max_seconds=float(budget_spec.get("wall_seconds", 600)))
        run = {"schema_version": 1, "run_id": output.stem, "protocol": protocol,
               "protocol_sha256": digest(protocol), "identities": identities, "stage": mode,
               "baseline": baseline, "candidates": [], "events": [], "cache": {},
               "operator_counts": {op: {"attempted": 0, "evaluated": 0, "cache_hits": 0, "accepted": 0}
                                   for op in OPERATORS},
               "iteration": 0, "status": "running", "pending": None,
               "search_state": {}, "budget": budget.state()}

    def checkpoint():
        run["budget"] = budget.state()
        save_run(output, run)

    def event(operator, kind, **values):
        run["events"].append({"sequence": len(run["events"]) + 1,
                              "operator": operator, "kind": kind, **values})

    def assess(candidate, operator):
        if budget.elapsed_seconds + time.monotonic() - budget._start >= budget.max_seconds:
            raise BudgetExceeded("wall time exhausted")
        if operator in run["operator_counts"]:
            run["operator_counts"][operator]["attempted"] += 1
        identity = candidate_id(candidate)
        found = next((x for x in run["candidates"] if x["id"] == identity), None)
        if found is not None:
            if operator in run["operator_counts"]:
                run["operator_counts"][operator]["cache_hits"] += 1
            event(operator, "compiled-candidate-cache-hit", candidate_id=identity)
            return found
        if len(run["candidates"]) >= max_candidates:
            raise BudgetExceeded("candidate budget exhausted")
        validation = validate_candidate(candidate, repo)
        observations = []
        loss = None
        if validation["ok"]:
            if runner is None:
                # Bytes are an engineering objective, never token/cost efficacy.
                loss = float(validation["context_bytes"])
            else:
                tasks = protocol.get("tasks", {}).get("training", [])
                if not tasks:
                    raise ValueError("real replay requires preregistered training tasks")
                for task in tasks:
                    run["pending"] = {"kind": "task", "candidate_id": identity, "task_id": task["id"]}
                    checkpoint()
                    observation = evaluate(candidate, task, runner, model=protocol.get("model", "unknown"),
                                           config=protocol.get("runner_config", {}), deps=identities,
                                           runner_identity=identities["runner"], cache=run["cache"], budget=budget,
                                           source=candidate_source(candidate, repo),
                                           retries=int(protocol.get("search", {}).get("retries", 0)))
                    observations.append(observation)
                    run["pending"] = ({"kind": "unreconciled-usage", "candidate_id": identity,
                                       "task_id": task["id"], "observation": observation}
                                      if budget.unknown_usage else None)
                    checkpoint()
                    if budget.unknown_usage:
                        raise BudgetExceeded("actual task usage unknown; independent reconciliation required")
                # A real loss must be supplied by the prespecified task grader.
                losses = [(x.get("outcome") or {}).get("loss") for x in observations]
                if all(x.get("status") == "completed" for x in observations) and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                       and __import__("math").isfinite(x) for x in losses):
                    loss = sum(losses) / len(losses)
        item = {"id": identity, "candidate": copy.deepcopy(candidate), "operator": operator,
                "evaluation": validation, "observations": observations, "loss": loss}
        run["candidates"].append(item)
        if operator in run["operator_counts"]:
            run["operator_counts"][operator]["evaluated"] += 1
        event(operator, "evaluated", candidate_id=identity, loss=loss, hard_ok=validation["ok"])
        checkpoint()
        return item

    def numeric(item):
        return item["loss"] if item["loss"] is not None else 1e300

    try:
        base = assess(run["baseline"], "baseline")
        if not base["evaluation"]["ok"] or base["loss"] is None:
            run["status"] = "no-feasible-baseline"
            event("controller", "baseline-rejected")
            checkpoint()
            return run
        if not active_count:
            run.update(status="completed", best_candidate_id=base["id"], empirical_status="unverified")
            checkpoint()
            return run
        state = run["search_state"]
        if not state:
            seed = int(protocol.get("seed", 1729))
            rng = random.Random(seed)
            pools = {}
            if "de" not in disabled:
                population = [[0.5, 0.5, 0.5]] + [[rng.random() for _ in range(3)] for _ in range(population_size - 1)]
                initial = [assess(dict(run["baseline"], theta=point), "initialization") for point in population]
                de = AdaptiveDE(seed, population, [numeric(item) for item in initial])
                pools[digest(base["candidate"]["model"])] = de.state()
            annealing = ChaoticAnnealing(seed, 3)
            state.update(current=copy.deepcopy(base["candidate"]), current_loss=numeric(base),
                         annealing=annealing.state(), pools=pools, memory={})
        for iteration in range(run["iteration"], iterations):
            current = copy.deepcopy(state["current"])
            annealing = ChaoticAnnealing.from_state(state["annealing"])
            if "skillopt" not in disabled:
                from .skillopt_adapter import SkillOptLearner, SourceBridge, RolloutResult, fixture_backend
                bridge = SourceBridge(current["model"])
                learner = SkillOptLearner(backend or fixture_backend, budget, bridge)
                learner.slow_update_context = state.get("memory", {}).get("slow_update", "")
                learner.meta_skill_context = state.get("memory", {}).get("meta_skill", "")
                if runner is None:
                    rollouts = [RolloutResult(id=x["id"], hard=float(x["evaluation"]["ok"]),
                                              soft=float(x["evaluation"]["ok"]),
                                              task_description="synthetic compiler/planner engineering fixture",
                                              extras={"kind": mode, "measurement": "synthetic"})
                                for x in run["candidates"][-4:]]
                else:
                    rollouts = []
                    for candidate in run["candidates"][-4:]:
                        for observation in candidate["observations"]:
                            outcome = observation.get("outcome") or {}
                            if "hard" not in outcome or "soft" not in outcome:
                                raise ValueError("real learning requires actual task-grader hard/soft evidence")
                            rollouts.append(RolloutResult(id=observation["task_id"], hard=outcome["hard"],
                                                          soft=outcome["soft"], fail_reason=outcome.get("fail_reason", ""),
                                                          task_description=outcome.get("task_description", ""),
                                                          predicted_answer=outcome.get("predicted_answer", ""),
                                                          extras={"observations": observation}))
                run["pending"] = {"kind": "learning", "iteration": iteration}
                checkpoint()
                patch = learner.learn(rollouts)
                run["pending"] = None
                proposal = dict(current, model=bridge.apply(patch), operator="skillopt")
                item = assess(proposal, "skillopt")
                event("skillopt", "patch", patch=patch.to_dict(), trace=learner.last_trace)
                def memory_rows(record):
                    if runner is None:
                        return [RolloutResult(id="compiler-planner", hard=float(record["evaluation"]["ok"]),
                                              soft=float(record["evaluation"]["ok"]),
                                              extras={"measurement": "synthetic"})]
                    rows = []
                    for observation in record["observations"]:
                        outcome = observation.get("outcome") or {}
                        if "hard" not in outcome or "soft" not in outcome:
                            raise ValueError("paired memory requires actual task-grader evidence")
                        rows.append(RolloutResult(id=observation["task_id"], hard=outcome["hard"],
                                                  soft=outcome["soft"], extras={"observation": observation}))
                    return rows
                previous_item = next(x for x in run["candidates"] if x["id"] == candidate_id(current))
                if item["evaluation"]["ok"] and (runner is None or item["observations"]):
                    run["pending"] = {"kind": "memory-update", "iteration": iteration}
                    checkpoint()
                    memory = learner.update_memory(memory_rows(previous_item), memory_rows(item),
                                                   previous_view=bridge.export_view(),
                                                   current_view=SourceBridge(proposal["model"]).export_view())
                    run["pending"] = None
                    state["memory"] = {"slow_update": learner.slow_update_context,
                                       "meta_skill": learner.meta_skill_context}
                    event("skillopt", "optimizer-memory", memory=memory)
                else:
                    event("skillopt", "memory-skipped", reason="hard rejection has no paired replay")
                if numeric(item) < state["current_loss"]:
                    current, state["current_loss"] = proposal, numeric(item)
                    run["operator_counts"]["skillopt"]["accepted"] += 1
            if "annealing" not in disabled:
                theta = annealing.propose(current["theta"])
                if ordinary:
                    rng = random.Random(int(protocol.get("seed", 1729)) + iteration)
                    theta = [min(1.0, max(0.0, x + rng.uniform(-0.2, 0.2))) for x in current["theta"]]
                proposal = dict(current, theta=theta, operator="annealing")
                item = assess(proposal, "annealing")
                accepted = annealing.accept(state["current_loss"], numeric(item),
                                            hard_ok=item["evaluation"]["ok"] and item["loss"] is not None)
                if accepted:
                    current, state["current_loss"] = proposal, numeric(item)
                    run["operator_counts"]["annealing"]["accepted"] += 1
                event("annealing", "exploration-decision", accepted=accepted, candidate_id=item["id"])
            if "de" not in disabled:
                structure = digest(current["model"])
                if structure not in state["pools"]:
                    rng = random.Random(int(protocol.get("seed", 1729)) + iteration)
                    population = [current["theta"]] + [[rng.random() for _ in range(3)] for _ in range(population_size - 1)]
                    items = [assess(dict(current, theta=p), "de") for p in population]
                    de = AdaptiveDE(iteration, population, [numeric(x) for x in items])
                else:
                    de = AdaptiveDE.from_state(state["pools"][structure])
                proposals = de.propose()
                items = [assess(dict(current, theta=p, operator="de"), "de") for p in proposals]
                before = min(de.losses)
                de.select(proposals, [numeric(x) for x in items])
                state["pools"][structure] = de.state()
                best = min(items, key=numeric)
                if numeric(best) < state["current_loss"]:
                    current, state["current_loss"] = best["candidate"], numeric(best)
                if min(de.losses) < before:
                    run["operator_counts"]["de"]["accepted"] += 1
            if "curvature" not in disabled:
                samples = []
                for point in local_sample_points(current["theta"], radius=0.2):
                    item = assess(dict(current, theta=point, operator="curvature"), "curvature")
                    if item["loss"] is not None:
                        samples.append((point, item["loss"]))
                curvature = negative_curvature_candidates(samples, current["theta"], radius=0.2)
                event("curvature", "surrogate-diagnostics", result=curvature)
                for theta in curvature["candidates"]:
                    item = assess(dict(current, theta=theta, operator="curvature"), "curvature")
                    if numeric(item) < state["current_loss"]:
                        current, state["current_loss"] = item["candidate"], numeric(item)
                        run["operator_counts"]["curvature"]["accepted"] += 1
            state.update(current=current, annealing=annealing.state())
            run["iteration"] = iteration + 1
            checkpoint()
            if stop_after is not None and run["iteration"] >= stop_after:
                run["status"] = "checkpointed"
                checkpoint()
                return run
        if runner is not None:
            finalists = sorted((x for x in run["candidates"] if x["loss"] is not None), key=numeric)[:3]
            selection = []
            for finalist in finalists:
                observations = []
                for task in registered["selection"]:
                    run["pending"] = {"kind": "selection-task", "candidate_id": finalist["id"], "task_id": task["id"]}
                    checkpoint()
                    observation = evaluate(finalist["candidate"], task, runner,
                                           model=protocol.get("model", "unknown"), config=protocol.get("runner_config", {}),
                                           deps=identities, runner_identity=identities["runner"], cache=run["cache"],
                                           budget=budget, source=candidate_source(finalist["candidate"], repo),
                                           retries=int(protocol.get("search", {}).get("retries", 0)))
                    observations.append(observation)
                    run["pending"] = ({"kind": "unreconciled-selection-usage", "observation": observation}
                                      if budget.unknown_usage else None)
                    checkpoint()
                    if budget.unknown_usage:
                        raise BudgetExceeded("selection usage unknown; independent reconciliation required")
                losses = [(x.get("outcome") or {}).get("loss") for x in observations]
                loss = (sum(losses) / len(losses) if all(x.get("status") == "completed" for x in observations)
                        and all(type(x) in (int, float) and math.isfinite(x) for x in losses) else None)
                selection.append({"candidate_id": finalist["id"], "loss": loss, "observations": observations})
                event("selection", "independent-development-selection", candidate_id=finalist["id"], loss=loss)
            run["selection"] = selection
            feasible = [x for x in selection if x["loss"] is not None]
            run["selected_candidate_id"] = min(feasible, key=lambda x: x["loss"])["candidate_id"] if feasible else None
        run["status"] = "completed" if runner is None or run.get("selected_candidate_id") else "selection-rejected"
    except BudgetExceeded as exc:
        run["status"] = "budget-exhausted"
        # Unknown usage can follow a charged failure inside a retrying callback.
        # Keep its fence until a human/independent receipt reconciles the call.
        if not budget.unknown_usage:
            run["pending"] = None
        event("controller", "budget-stop", reason=str(exc))
    except Exception as exc:
        run["status"] = "failed"
        event("controller", "failure", error=type(exc).__name__)
        checkpoint()
        raise
    finite = [x for x in run["candidates"] if x["loss"] is not None]
    run["best_candidate_id"] = run.get("selected_candidate_id") or (min(finite, key=numeric)["id"] if finite else None)
    run["best_candidate_origin"] = "selection" if run.get("selected_candidate_id") else "training-or-engineering"
    run["empirical_status"] = "unverified"
    checkpoint()
    return run
