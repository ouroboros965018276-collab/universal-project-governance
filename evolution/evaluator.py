"""Compile candidate source and collect replay evidence without inventing usage.

Engineering checks prove executable contracts. Only an injected real task runner
can produce model-task observations; neither text length nor a cache hit is an
independent observation of task cost or quality.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, MutableMapping

from .contracts import canonical_bytes, candidate_id, digest, materialize

USAGE_FIELDS = ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens",
                "total_tokens", "cost_usd")


def canonical_source(repo: Path | str) -> dict:
    """Exact UTF-8 canonical source, including scripts/schemas/templates/profiles."""
    root = Path(repo) / "governance-src"
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(root.rglob("*")) if p.is_file()
            and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}}


def source_hash(source: dict | Path | str) -> str:
    return digest(canonical_source(source) if isinstance(source, (Path, str)) else source)


def candidate_source(candidate: dict, repo: Path | str) -> dict:
    source = canonical_source(repo)
    source["model/governance-model.json"] = canonical_bytes(materialize(candidate)).decode("utf-8")
    return source


def cache_key(candidate: dict, task: dict, model: str, config: dict,
              deps: dict, runner_identity: dict, source: dict | None = None) -> str:
    """Bind every execution input; cache reuse never adds a sample."""
    return digest({"candidate": candidate_id(candidate), "source": source,
                   "task": task, "model": model, "config": config,
                   "dependencies": deps, "runner": runner_identity})


def _protected_model(model: dict) -> dict:
    model = copy.deepcopy(model)
    model.pop("presentation", None)
    for policy in model.get("policies", []):
        policy.pop("closure", None)
    return model


def _command(command: list, cwd: Path) -> dict:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", timeout=60, check=False)
    return {"command": command, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def validate_candidate(candidate: dict, repo: Path | str) -> dict:
    """Compile in an isolated copy and compare required closures across contexts.

    Normative prose edits still require independent behavioral evidence. Static
    preservation of policy IDs and dependencies is deliberately not such proof.
    """
    repo = Path(repo).resolve()
    result = {"ok": False, "errors": [], "checks": [], "plans": []}
    try:
        model = materialize(candidate)
        baseline = json.loads((repo / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        result["candidate_id"] = candidate_id(candidate)
        result["source_sha256"] = source_hash(candidate_source(candidate, repo))
        if _protected_model(model) != _protected_model(baseline):
            raise ValueError("candidate changes protected governance semantics")
        ids = [p["id"] for p in model["policies"]]
        order = model.get("presentation", {}).get("policy_order", ids)
        if sorted(order) != sorted(ids) or len(set(order)) != len(ids):
            raise ValueError("presentation policy_order must be a complete policy permutation")
        compiler_spec = importlib.util.spec_from_file_location("upg_evolution_compiler", repo / "compiler/compile_governance.py")
        compiler = importlib.util.module_from_spec(compiler_spec)
        compiler_spec.loader.exec_module(compiler)
        with tempfile.TemporaryDirectory(prefix="upg-evaluate-") as temporary:
            isolated = Path(temporary)
            shutil.copytree(repo / "governance-src", isolated / "governance-src",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            shutil.copyfile(repo / "LICENSE", isolated / "LICENSE")
            baseline_runtime = isolated / "baseline-runtime"
            compiler.compile_runtime(isolated, baseline_runtime)
            model_path = isolated / "governance-src/model/governance-model.json"
            model_path.write_bytes(canonical_bytes(model))
            runtime = isolated / "universal-project-governance"
            compiler.compile_runtime(isolated, runtime)
            result["checks"].append({"name": "isolated-compile", "returncode": 0})
            for command in ([sys.executable, str(repo / "tools/governance_lint.py"), str(isolated)],
                            [sys.executable, str(runtime / "scripts/validate_integrity.py"), str(runtime)]):
                observed = _command(command, isolated)
                result["checks"].append(observed)
                if observed["returncode"]:
                    result["errors"].append("candidate compiler/lint/integrity check failed")
            contexts = json.loads((repo / "tests/fixtures/governance_plan_cases.json").read_text(encoding="utf-8"))["cases"]
            routed_context_bytes = 0
            for case in contexts:
                context_path = isolated / "context.json"
                context_path.write_bytes(canonical_bytes(case["context"]))
                observed_plans = []
                for compiled in (baseline_runtime, runtime):
                    observed = _command([sys.executable, str(compiled / "scripts/plan_governance.py"),
                                         "--context", str(context_path), "--json"], isolated)
                    if observed["returncode"]:
                        raise ValueError("planner rejected %s: %s" % (case["id"], observed["stderr"]))
                    observed_plans.append(json.loads(observed["stdout"]))
                before, after = observed_plans
                for key in ("active_rules", "risk_level", "risk_score", "change_mode", "scope_guard",
                            "report", "field_report_obligation", "handoff"):
                    if before[key] != after[key]:
                        result["errors"].append("protected plan contract changed: %s/%s" % (case["id"], key))
                if sorted(before["evidence"]) != sorted(after["evidence"]):
                    result["errors"].append("required evidence changed: " + case["id"])
                result["plans"].append({"context_id": case["id"], "active_rules": after["active_rules"],
                                         "execution_order": [line.split(":", 1)[0] for line in after["required_closures"]]})
                routed_context_bytes += len(canonical_bytes({key: after[key] for key in ("required_closures", "evidence")}))
            result["context_bytes"] = len((runtime / "SKILL.md").read_bytes()) + routed_context_bytes / len(contexts)
            result["context_measurement"] = "skill-bytes-plus-unweighted-mean-fixture-plan-bytes; not tokens"
            result["runtime_sha256"] = digest({p.relative_to(runtime).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                                for p in sorted(runtime.rglob("*")) if p.is_file() and "__pycache__" not in p.parts})
        result["ok"] = not result["errors"]
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result["errors"].append(str(error))
    return result


def _usage(raw: object) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for field in USAGE_FIELDS:
        value = raw.get(field)
        valid_type = type(value) in (int, float) if field == "cost_usd" else type(value) is int
        result[field] = (value if valid_type and math.isfinite(value) and value >= 0 else None)
    return result


def _sum_usage(attempts: list) -> dict:
    # Missing any attempted call's usage leaves the aggregate unknown.
    return {field: (sum(values) if all(value is not None for value in values) else None)
            for field in USAGE_FIELDS
            for values in [[attempt["usage"][field] for attempt in attempts]]}


def evaluate(candidate: dict, task: dict, runner: Callable | None = None, *,
             model: str = "unknown", config: dict | None = None, deps: dict | None = None,
             runner_identity: dict | None = None, cache: MutableMapping | None = None,
             retries: int = 0, source: dict | None = None, budget=None) -> dict:
    """Runner(request)->dict with provider usage and task-specific grading evidence.

    Runner exceptions may expose ``usage`` for charged failed calls. All attempts
    remain in the result. A failed attempt without a provider receipt cannot be
    silently charged as zero. The evaluator itself performs no model API calls.
    """
    config, deps, runner_identity = config or {}, deps or {}, runner_identity or {}
    if type(retries) is not int or retries < 0:
        raise ValueError("retries must be a nonnegative integer")
    identity = cache_key(candidate, task, model, config, deps, runner_identity, source)
    if cache is not None and identity in cache:
        result = copy.deepcopy(cache[identity])
        result.update(cache_hit=True, independent_sample=False)
        return result
    result = {"schema_version": 1, "candidate_id": candidate_id(candidate), "cache_key": identity,
              "task_sha256": digest(task), "task_id": task.get("id"), "model": model,
              "runner_identity": runner_identity, "config_sha256": digest(config),
              "dependencies_sha256": digest(deps), "source_sha256": digest(source) if source is not None else None,
              "cache_hit": False, "independent_sample": runner is not None, "attempts": []}
    if runner is None:
        return dict(result, kind="development_engineering", status="NOT_RUN",
                    usage={field: None for field in USAGE_FIELDS}, wall_seconds=None,
                    empirical_eligible=False)
    if not runner_identity.get("id") or not runner_identity.get("version"):
        raise ValueError("real runner requires explicit id and version")
    started = time.perf_counter()
    for attempt_number in range(retries + 1):
        if budget is not None:
            budget.reserve()
        attempt_started = time.perf_counter()
        try:
            raw = runner({"candidate": copy.deepcopy(candidate), "task": copy.deepcopy(task),
                          "model": model, "config": copy.deepcopy(config), "attempt": attempt_number,
                          "cache_key": identity})
            if not isinstance(raw, dict):
                raise ValueError("runner result must be an object")
            status = raw.get("status", "failed")
            if status not in {"completed", "failed"}:
                raise ValueError("runner status must be completed or failed")
            attempt = {"attempt": attempt_number, "status": status, "usage": _usage(raw.get("usage")),
                       "provider_receipt": raw.get("provider_receipt"), "outcome": raw.get("outcome"),
                       "error": raw.get("error"), "wall_seconds": time.perf_counter() - attempt_started}
        except Exception as error:  # A failed external call is itself part of cost evidence.
            attempt = {"attempt": attempt_number, "status": "failed", "usage": _usage(getattr(error, "usage", None)),
                       "provider_receipt": getattr(error, "provider_receipt", None), "outcome": None,
                       "error": "%s: %s" % (type(error).__name__, error),
                       "wall_seconds": time.perf_counter() - attempt_started}
        result["attempts"].append(attempt)
        if budget is not None:
            budget.record(attempt["usage"], attempt["wall_seconds"], attempt["error"])
        if attempt["status"] == "completed":
            break
    result.update(kind="real_model_task", status=result["attempts"][-1]["status"],
                  wall_seconds=time.perf_counter() - started, usage=_sum_usage(result["attempts"]),
                  outcome=result["attempts"][-1]["outcome"])
    result["empirical_eligible"] = bool(source is not None and all(attempt["provider_receipt"]
                                        and attempt["usage"]["total_tokens"] is not None for attempt in result["attempts"]))
    if cache is not None:
        cache[identity] = copy.deepcopy(result)
    return result
