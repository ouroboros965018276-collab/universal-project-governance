"""Execute the preregistered control matrix with shared search budget caps.

The matrix ledger is a development instrument. Historical baselines are compiled
from their exact Git archives; a matrix alone never supplies independent holdout
evidence, causal contribution estimates, token savings, or qualification.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time

from .contracts import Budget, BudgetExceeded, canonical_bytes, digest
from .controller import callable_identity, checkpoint_lock, engine_identity, run_search, save_run, task_loss
from .evaluator import canonical_source, evaluate, source_hash

MODULES = {"reflection", "annealing", "de", "curvature"}


def _command(command, cwd):
    try:
        observed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                  encoding="utf-8", timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": [str(value) for value in command], "returncode": 1,
                "stdout": "", "stderr": type(error).__name__}
    return {"command": [Path(str(value)).name if Path(str(value)).is_absolute() else str(value)
                        for value in command],
            "returncode": observed.returncode, "stdout": observed.stdout, "stderr": observed.stderr}


def _baseline(repo, revision, *, include_source=False):
    """Observe the actual historical runtime, without modern materialization."""
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("baseline must pin a full Git commit")
    try:
        archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", revision],
                                 capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("baseline Git archive unavailable: " + revision) from error
    if archive.returncode:
        raise ValueError("baseline Git archive unavailable: " + revision)
    with tempfile.TemporaryDirectory(prefix="upg-ablation-baseline-") as temporary:
        isolated = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as contents:
            contents.extractall(isolated, filter="data")
        checks = []
        runtime = isolated / "universal-project-governance"
        for command in ([sys.executable, str(isolated / "compiler/compile_governance.py"), "--repo", str(isolated), "--check"],
                        [sys.executable, str(isolated / "tools/governance_lint.py"), str(isolated)],
                        [sys.executable, str(runtime / "scripts/validate_integrity.py"), str(runtime)]):
            checks.append(_command(command, isolated))
        routed = []
        fixture = json.loads((isolated / "tests/fixtures/governance_plan_cases.json").read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            context = isolated / "ablation-context.json"
            context.write_bytes(canonical_bytes(case["context"]))
            observed = _command([sys.executable, str(runtime / "scripts/plan_governance.py"), "--context", str(context), "--json"], isolated)
            if observed["returncode"]:
                checks.append(observed)
                continue
            plan = json.loads(observed["stdout"])
            routed.append(len(canonical_bytes({key: plan[key] for key in ("required_closures", "evidence")})))
        model = json.loads((isolated / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        result = {"stage": "historical-baseline-engineering", "revision": revision,
                "version": model["version"], "source_sha256": source_hash(isolated),
                "engineering": "PASS" if routed and all(check["returncode"] == 0 for check in checks) else "FAIL",
                "checks": checks, "fixture_contexts": len(routed),
                "context_bytes": len((runtime / "SKILL.md").read_bytes()) + sum(routed) / len(routed) if routed else None,
                "measurement": "skill-bytes-plus-unweighted-mean-fixture-plan-bytes; not tokens",
                "actual_task_usage": None, "independent_holdout": False}
        if include_source:
            # This exact archive is dispatched directly. Never run the current
            # materializer over historical source or claim it was that release.
            result["source"] = canonical_source(isolated)
            result["model"] = model
            result["execution_artifact"] = {
                "compiler": (isolated / "compiler/compile_governance.py").read_bytes().decode("utf-8"),
                "license": (isolated / "LICENSE").read_bytes().decode("utf-8"),
                "runtime": {path.relative_to(runtime).as_posix(): path.read_bytes().decode("utf-8")
                            for path in sorted(runtime.rglob("*")) if path.is_file()
                            and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}}}
        return result


def _real_baseline(repo, revision, protocol, output, runner):
    """Replay a pinned historical release with the same development tasks.

    Per-call pending fences survive process interruption. Unknown charged usage
    cannot be replayed by resuming either the arm or the enclosing matrix.
    """
    with checkpoint_lock(output):
        started = time.monotonic()
        historical = _baseline(repo, revision, include_source=True)
        source, model = historical.pop("source"), historical.pop("model")
        execution_artifact = historical.pop("execution_artifact")
        identities = {"revision": revision, "source": source_hash(source),
                      "execution_artifact": digest(execution_artifact),
                      "protocol": digest(protocol), "engine": engine_identity(repo, excluded=(output,)),
                      "runner": callable_identity(runner)}
        candidate_identity = digest({"historical_revision": revision,
                                     "source_sha256": identities["source"]})
        output = Path(output)
        if output.exists():
            run = json.loads(output.read_text(encoding="utf-8"))
            if run.get("identities") != identities:
                raise ValueError("historical checkpoint source/protocol/engine/runner identity mismatch")
            if run.get("pending"):
                raise ValueError("historical callback has uncertain usage; reconcile its receipt before resuming")
            budget = Budget.from_state(run["budget"])
            if run["status"] in {"completed", "budget-exhausted", "no-feasible-baseline"}:
                return run
        else:
            spec = protocol["budget"]
            budget = Budget(max_calls=int(spec["model_calls"]), max_total_tokens=int(spec["tokens"]),
                            max_seconds=float(spec["wall_seconds"]))
            run = {"schema_version": 1, "run_id": output.stem,
                   "stage": "historical-baseline-real-task", "status": "running",
                   "identities": identities, "engineering": historical,
                   "baseline": {"model": model, "operator": "historical-baseline", "revision": revision},
                   "candidate_id": candidate_identity, "observations": [], "cache": {},
                   "pending": None, "budget": budget.state(), "independent_holdout": False,
                   "empirical_status": "BLOCKED"}
        budget.elapsed_seconds += time.monotonic() - started

        def checkpoint():
            run["budget"] = budget.state()
            overrun = budget.overruns(run["budget"])
            if run["status"] == "completed" and overrun:
                run.update(status="budget-exhausted", budget_overrun=overrun)
            save_run(output, run)

        registered = protocol.get("tasks", {})
        split_ids = {}
        for split in ("training", "selection", "final"):
            ids = [row["id"] for row in registered.get(split, [])]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate task in " + split + " split")
            split_ids[split] = set(ids)
        if not split_ids["training"] or not split_ids["selection"]:
            raise ValueError("real historical replay requires registered training and selection tasks")
        if any(split_ids[left] & split_ids[right] for left, right in
               (("training", "selection"), ("training", "final"), ("selection", "final"))):
            raise ValueError("task identity leaks across development/selection/final splits")
        if historical["engineering"] != "PASS":
            run["status"] = "no-feasible-baseline"
            checkpoint()
            return run
        checkpoint()
        observed = {(row["split"], row["observation"]["task_id"]) for row in run["observations"]}
        try:
            for split in ("training", "selection"):
                for task in registered[split]:
                    if (split, task["id"]) in observed:
                        continue
                    run["pending"] = {"kind": "historical-task", "split": split, "task_id": task["id"]}
                    checkpoint()
                    observation = evaluate(run["baseline"], task, runner,
                        model=protocol.get("model", "unknown"), config=protocol.get("runner_config", {}),
                        deps=identities, runner_identity=identities["runner"], cache=run["cache"],
                        retries=int(protocol.get("search", {}).get("retries", 0)), source=source,
                        budget=budget, candidate_identity=candidate_identity,
                        execution_artifact=execution_artifact)
                    run["observations"].append({"split": split, "observation": observation})
                    run["pending"] = ({"kind": "unreconciled-usage", "split": split,
                                       "task_id": task["id"], "observation": observation}
                                      if budget.unknown_usage else None)
                    checkpoint()
                    if budget.unknown_usage:
                        raise BudgetExceeded("actual historical task usage unknown; reconciliation required")
                    overrun = budget.overruns()
                    if overrun:
                        run["budget_overrun"] = overrun
                        raise BudgetExceeded("observed historical call exceeded hard budget")
            run["status"] = "completed"
            observations = [row["observation"] for row in run["observations"]]
            run["execution_status"] = "PASS" if all(row["status"] == "completed" for row in observations) else "FAIL"
            run["quality_status"] = "PASS" if task_loss(observations) is not None else "FAIL"
            overrun = budget.overruns()
            if overrun:
                run["budget_overrun"] = overrun
                raise BudgetExceeded("observed historical replay exceeded hard budget")
        except BudgetExceeded as error:
            run["status"] = "budget-exhausted"
            overrun = budget.overruns()
            if overrun:
                run["budget_overrun"] = overrun
            run["stop_reason"] = str(error)
            if not budget.unknown_usage:
                run["pending"] = None
        except Exception:
            run["status"] = "failed"
            checkpoint()
            raise
        checkpoint()
        return run


def _summary(run):
    budget = run.get("budget", {})
    return {"run_id": run.get("run_id"), "stage": run.get("stage"), "status": run.get("status"),
            "candidate_count": len(run.get("candidates", [])), "best_candidate_id": run.get("best_candidate_id"),
            "operator_counts": run.get("operator_counts", {}),
            "budget_caps": {key: budget.get(key) for key in ("max_calls", "max_total_tokens", "max_seconds")},
            "attempted_calls": budget.get("calls"),
            "actual_task_usage": None if run.get("stage") == "engineering" else budget,
            "budget_overrun": run.get("budget_overrun"),
            "empirical_status": "BLOCKED"}


def run_matrix(repo, protocol, output, runner=None, backend=None):
    with checkpoint_lock(output):
        return _run_matrix(repo, protocol, output, runner=runner, backend=backend)


def _run_matrix(repo, protocol, output, runner=None, backend=None):
    """Resume per-arm checkpoints only when source/protocol/callbacks still match.

    Search arms inherit identical caps. The controller reallocates dispatches for
    disabled modules; using a cap is not evidence that actual costs were equal.
    Historical arms use the same training and selection tasks when a real
    development runner is supplied; their exact archive runtime stays intact.
    """
    repo, output = Path(repo).resolve(), Path(output).resolve()
    identity = {"protocol_sha256": digest(protocol), "source_sha256": source_hash(repo),
                "engine_sha256": engine_identity(repo, excluded=(output,)), "runner": callable_identity(runner),
                "backend": callable_identity(backend)}
    matrix_path = output / "matrix.json"
    if matrix_path.exists():
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        if matrix.get("identities") != identity:
            raise ValueError("matrix checkpoint source/protocol/engine/runner identity mismatch")
        if matrix.get("status") == "completed":
            return matrix
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("matrix output is nonempty without a matching checkpoint")
        matrix = {"schema_version": 1, "run_id": output.name, "identities": identity,
                  "status": "running", "arms": {}, "budget_caps": protocol["budget"],
                  "empirical": {"status": "BLOCKED", "reason": "development matrix is not independent locked holdout evidence"},
                  "formal_qualification": "UNASSESSED", "conditional_contributions": None,
                  "token_savings": None, "timing_savings": None}
        save_run(matrix_path, matrix)
    for name, definition in protocol["arms"].items():
        if matrix["arms"].get(name, {}).get("terminal") or matrix["arms"].get(name, {}).get("completed"):
            continue
        if name in {"rc15", "latest_baseline"}:
            revision = protocol["baseline"]["rc15_revision" if name == "rc15" else "latest_revision"]
            if runner is None:
                result = _baseline(repo, revision)
                passed = result["engineering"] == "PASS"
                matrix["arms"][name] = dict(result, completed=passed, terminal=True,
                    status="completed" if passed else "no-feasible-baseline")
            else:
                arm_path = output / "arms" / (name + ".json")
                result = _real_baseline(repo, revision, protocol, arm_path, runner)
                matrix["arms"][name] = {"stage": result["stage"], "status": result["status"],
                    "execution_status": result.get("execution_status"), "quality_status": result.get("quality_status"),
                    "budget_overrun": result.get("budget_overrun"),
                    "revision": revision, "source_sha256": result["identities"]["source"],
                    "candidate_id": result["candidate_id"], "actual_task_usage": result["budget"],
                    "observation_count": len(result["observations"]), "empirical_status": "BLOCKED",
                    "completed": result["status"] == "completed",
                    "terminal": not result.get("pending") and result["status"] in {"completed", "budget-exhausted", "no-feasible-baseline"},
                    "checkpoint": "arms/" + name + ".json"}
        else:
            enabled = {"annealing" if module in {"chaos", "ordinary_annealing"} else module
                       for module in definition["search_modules"]}
            if not enabled <= MODULES:
                raise ValueError("unknown search module in arm " + name)
            arm_path = output / "arms" / (name + ".json")
            run = run_search(repo, protocol, arm_path, runner=runner, backend=backend,
                             resume=arm_path.exists(), disabled=tuple(sorted(MODULES - enabled)),
                             ordinary="ordinary_annealing" in definition["search_modules"])
            matrix["arms"][name] = dict(_summary(run), completed=run.get("status") == "completed",
                                       terminal=not run.get("pending") and run.get("status") in {"completed", "budget-exhausted", "no-feasible-baseline", "selection-rejected"},
                                       checkpoint="arms/" + name + ".json")
        save_run(matrix_path, matrix)
    if (matrix["arms"] and set(matrix["arms"]) == set(protocol["arms"])
            and all(value.get("completed") for value in matrix["arms"].values())):
        matrix["status"] = "completed"
    elif any(value.get("status") == "budget-exhausted" for value in matrix["arms"].values()):
        matrix["status"] = "budget-exhausted"
    elif all(value.get("terminal") for value in matrix["arms"].values()):
        matrix["status"] = "incomplete"
    else:
        matrix["status"] = "checkpointed"
    save_run(matrix_path, matrix)
    return matrix
