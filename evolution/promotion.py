"""Fail-closed independent evidence admission and reviewable source proposals.

This module never qualifies a release or applies a candidate to canonical source.
Hashes and a prior Git freeze establish artifact continuity, not provider or
grader honesty. Independently operated runners remain an explicit trust boundary.
"""
from __future__ import annotations

from datetime import datetime
import difflib
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import stat
import subprocess
import tempfile

from .contracts import candidate_id, canonical_bytes, digest, materialize
from .evaluator import candidate_source, source_hash, validate_candidate

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "evolution/protocol/upg-evolution-v2.json"
RC15 = "0808842e759763c722f77a2fd9b464842480a290"
MODULES = {"reflection", "annealing", "de", "curvature"}


class EvidenceError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise EvidenceError(reason)


def _number(value, name, positive=False):
    _need(type(value) in (int, float) and (not isinstance(value, float) or math.isfinite(value)), "unknown or invalid " + name)
    _need(value > 0 if positive else value >= 0, "invalid " + name)
    return value


def _time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        _need(parsed.tzinfo is not None, "evidence timestamp must include timezone")
        return parsed
    except (TypeError, AttributeError, ValueError) as error:
        raise EvidenceError("invalid evidence timestamp") from error


def _artifact(reference, base):
    _need(isinstance(reference, dict), "missing artifact reference")
    _need(isinstance(reference.get("sha256"), str) and len(reference["sha256"]) == 64,
          "artifact requires a SHA256 digest")
    _need(isinstance(reference.get("path"), str) and reference["path"], "artifact requires a path")
    base = Path(base).resolve()
    path = Path(reference["path"])
    path = path if path.is_absolute() else base / path
    _need(path.resolve().is_relative_to(base), "artifact path escapes its evidence root")
    before = path.lstat()
    _need(stat.S_ISREG(before.st_mode) and not getattr(before, "st_file_attributes", 0) & 1024
          and before.st_size <= 16777216, "artifact must be a bounded regular file")
    with path.open("rb") as stream:
        raw = stream.read(16777217)
    after = path.lstat()
    _need(len(raw) <= 16777216 and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
          (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "artifact changed during reading")
    path = path.resolve()
    _need(hashlib.sha256(raw).hexdigest() == reference["sha256"], "artifact hash mismatch: " + str(path))
    data = json.loads(raw)
    _need(isinstance(data, dict), "artifact must contain an object")
    return data, path.parent


def _git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            timeout=30, check=False)
    _need(result.returncode == 0, "independent freeze Git anchor is unavailable")
    return result.stdout


def _freeze(manifest, repo):
    reference = manifest.get("freeze", {})
    revision, path = reference.get("git_revision"), reference.get("path")
    _need(isinstance(revision, str) and len(revision) == 40 and all(c in "0123456789abcdef" for c in revision),
          "holdout freeze must pin a full Git revision")
    _need(isinstance(path, str) and not Path(path).is_absolute() and ".." not in Path(path).parts,
          "holdout freeze path must stay inside the repository")
    _git(repo, "merge-base", "--is-ancestor", revision, "HEAD")
    raw = _git(repo, "show", revision + ":" + path.replace("\\", "/"))
    _need(hashlib.sha256(raw).hexdigest() == reference.get("sha256"), "frozen manifest hash mismatch")
    frozen = json.loads(raw)
    _need(isinstance(frozen, dict), "frozen evidence must contain an object")
    _need(frozen.get("kind") == "independent-holdout-freeze", "missing independent holdout freeze")
    _need(all(isinstance(frozen.get(key), str) and frozen[key].strip()
              for key in ("independent_actor", "optimizer_actor"))
          and frozen["independent_actor"] != frozen["optimizer_actor"],
          "holdout evaluator must be independent of candidate selection")
    _need(_time(frozen.get("selected_at")) <= _time(frozen.get("frozen_at")),
          "candidate selection happened after the holdout freeze")
    # A freeze added after observations cannot be backdated with a JSON timestamp.
    committed_at = _time(_git(repo, "show", "-s", "--format=%cI", revision).decode().strip())
    _need(_time(frozen.get("frozen_at")) <= committed_at, "freeze timestamp follows its anchor commit")
    grader = frozen.get("grader", {})
    grader_path = grader.get("path")
    _need(isinstance(grader_path, str) and not Path(grader_path).is_absolute() and ".." not in Path(grader_path).parts,
          "independent grader must be pinned in the freeze revision")
    grader_raw = _git(repo, "show", revision + ":" + grader_path.replace("\\", "/"))
    _need(hashlib.sha256(grader_raw).hexdigest() == grader.get("sha256"), "independent grader source hash mismatch")
    frozen["grader_sha256"] = grader["sha256"]
    frozen["anchor_committed_at"] = committed_at
    return frozen


def _splits(frozen):
    splits = frozen.get("splits", {})
    scopes = {}
    by_id = {}
    for name in ("training", "selection", "final"):
        rows = splits.get(name)
        _need(isinstance(rows, list) and rows, "missing frozen " + name + " split")
        for row in rows:
            _need(all(isinstance(row.get(key), str) and row[key] for key in ("task_id", "task_family", "project_id")),
                  "split entry lacks task/project/family identity")
        _need(len({row["task_id"] for row in rows}) == len(rows), "duplicate tasks in frozen split")
        scopes[name] = {key: {row[key] for row in rows} for key in ("task_id", "task_family", "project_id")}
        by_id[name] = {row["task_id"]: row for row in rows}
    for left, right in (("training", "selection"), ("training", "final"), ("selection", "final")):
        for key in scopes[left]:
            _need(not (scopes[left][key] & scopes[right][key]), "holdout leakage across " + key)
    exposed = frozen.get("prior_final_task_ids")
    _need(isinstance(exposed, list), "missing final-set exposure ledger")
    _need(not (set(exposed) & scopes["final"]["task_id"]), "previously exposed final tasks cannot be reused")
    return by_id


def _weights(value, expected, name):
    _need(isinstance(value, dict) and set(value) == set(expected), "incomplete frozen " + name)
    for weight in value.values():
        _number(weight, name, positive=True)
    _need(abs(sum(value.values()) - 1.0) < 1e-8, name + " must sum to one")
    return value


def _claim_request(receipt, seen):
    """One provider call can fund only one observation or optimization arm."""
    _need(receipt.get("kind") == "provider-usage" and receipt.get("provider") and receipt.get("request_id"),
          "provider usage receipt required for every charged attempt")
    key = (receipt["provider"], receipt["request_id"])
    _need(key not in seen, "provider request reused across observations/search arms")
    seen.add(key)
    return key


def _admit(record, base, frozen, protocol, final, seen):
    _need(record.get("kind") == "real_model_task", "synthetic/engineering observations cannot be promoted")
    _need(record.get("independent_sample") is True and record.get("cache_hit") is False,
          "cache reuse is not an independent holdout sample")
    _need(record.get("protocol_sha256") == frozen["protocol_sha256"], "observation protocol mismatch")
    _need(record.get("task_id") in final, "observation is outside frozen final split")
    task = final[record["task_id"]]
    _need(all(record.get(key) == task[key] for key in ("task_family", "project_id")), "task identity mismatch")
    _need(record.get("arm") in protocol["arms"], "unknown comparison arm")
    if record["arm"] == "full":
        _need(record.get("candidate_id") == frozen["candidate_id"], "holdout evaluated a different candidate")
        _need(record.get("source_sha256") == frozen.get("candidate_source_sha256"), "holdout source mismatch")
    if record["arm"] == "rc15":
        _need(record.get("source_revision") == RC15, "primary baseline is not fixed RC15")
    if record["arm"] == "latest_baseline":
        _need(record.get("source_revision") == frozen["baseline_revisions"]["latest_baseline"], "current baseline mismatch")
    _need(_time(record.get("started_at")) > frozen["anchor_committed_at"], "holdout started before the committed freeze")
    for key in ("observation_id", "pair_id", "model_family", "model_id", "config_sha256", "dependencies_sha256"):
        _need(isinstance(record.get(key), str) and record[key], "missing observation " + key)
    _need(record["observation_id"] not in seen["observations"], "replayed observation counted twice")
    seen["observations"].add(record["observation_id"])
    runner = record.get("runner_identity", {})
    _need(runner.get("id") and runner.get("version"), "missing runner identity")
    attempts = record.get("attempts")
    _need(isinstance(attempts, list) and attempts, "missing actual model attempts")
    totals = []
    dollars = []
    for index, attempt in enumerate(attempts):
        _need(attempt.get("attempt") == index and attempt.get("status") in {"completed", "failed"}, "incomplete retry history")
        receipt, _ = _artifact(attempt.get("provider_receipt"), base)
        _need(receipt.get("model_id") == record["model_id"], "provider receipt model mismatch")
        _claim_request(receipt, seen["requests"])
        usage = receipt.get("usage", {})
        total = _number(usage.get("total_tokens"), "provider total_tokens")
        _need(total == attempt.get("usage", {}).get("total_tokens"), "attempt usage differs from provider receipt")
        for field in ("input_tokens", "output_tokens"):
            _number(usage.get(field), "provider " + field)
        totals.append(total)
        cost = usage.get("cost_usd")
        dollars.append(_number(cost, "provider cost_usd") if cost is not None else None)
        _need(_time(receipt.get("observed_at")) >= _time(record["started_at"]), "provider receipt predates task")
    _need(all(attempt["status"] == "failed" for attempt in attempts[:-1]), "calls after a completed task require a separate rework observation")
    _need(sum(totals) == record.get("usage", {}).get("total_tokens"), "failed/retried call costs omitted from total")
    context, _ = _artifact(record.get("context_receipt"), base)
    _need(context.get("kind") == "context-token-measurement" and context.get("tokenizer_id"), "context tokens need a tokenizer receipt")
    _need(context.get("candidate_id") == record.get("candidate_id"), "context receipt candidate mismatch")
    timing, _ = _artifact(record.get("timing_receipt"), base)
    _need(timing.get("kind") == "task-timing" and timing.get("clock") == "monotonic"
          and timing.get("observation_id") == record["observation_id"], "missing actual task timing receipt")
    seconds = _number(timing.get("elapsed_seconds"), "task elapsed time", positive=True)
    _need(seconds == record.get("wall_seconds"), "wall time differs from execution receipt")
    grade, grade_base = _artifact(record.get("grade"), base)
    _need(grade.get("kind") == "executable-task-grade" and grade.get("grader_sha256") == frozen.get("grader_sha256"),
          "grade is not from the frozen independent grader")
    _need(grade.get("observation_id") == record["observation_id"], "grade observation mismatch")
    _need(isinstance(grade.get("artifacts"), list) and grade["artifacts"], "grade has no task output evidence")
    for reference in grade["artifacts"]:
        _artifact(reference, grade_base)
    quality = _number(grade.get("quality_score"), "task quality")
    _need(quality <= 1, "quality score outside 0..1")
    total_requirements = _number(grade.get("core_requirements_total"), "core requirements", positive=True)
    met = _number(grade.get("core_requirements_met"), "core requirements met")
    _need(met <= total_requirements and isinstance(grade.get("critical_failures"), list), "invalid core grade")
    if record["arm"] == "full":
        _need(met == total_requirements and not grade["critical_failures"], "core governance/safety regressed")
    return dict(record, measured_tokens=sum(totals), measured_context_tokens=_number(context.get("token_count"), "context tokens"),
                measured_seconds=seconds, quality=quality,
                measured_dollars=sum(dollars) if all(type(value) in (int, float) for value in dollars) else None)


def _paired(rows, numerator, denominator):
    groups = {}
    for row in rows:
        key = tuple(row[key] for key in ("pair_id", "task_id", "task_family", "project_id", "model_family", "model_id",
                                        "config_sha256", "dependencies_sha256")) + (digest(row["runner_identity"]),)
        _need(row["arm"] not in groups.setdefault(key, {}), "duplicate arm in matched pair")
        groups[key][row["arm"]] = row
    result = []
    for arms in groups.values():
        _need(numerator in arms and denominator in arms, "incomplete paired comparison: " + denominator)
        left, right = arms[numerator], arms[denominator]
        result.append({"model_family": left["model_family"], "task_family": left["task_family"],
                       "tokens": left["measured_tokens"] / _number(right["measured_tokens"], "baseline token cost", True),
                       "context": left["measured_context_tokens"] / _number(right["measured_context_tokens"], "baseline context cost", True),
                       "seconds": left["measured_seconds"] / right["measured_seconds"],
                       "quality": left["quality"] - right["quality"],
                       "token_saving": right["measured_tokens"] - left["measured_tokens"],
                       "time_saving": right["measured_seconds"] - left["measured_seconds"],
                       "dollar_saving": (right["measured_dollars"] - left["measured_dollars"]
                                         if left["measured_dollars"] is not None and right["measured_dollars"] is not None else None)})
    return result


def paired_bootstrap(pairs, field, model_weights, task_weights, inference):
    """Stratified paired resampling with preregistered family weights."""
    cells = {}
    for pair in pairs:
        cells.setdefault((pair["model_family"], pair["task_family"]), []).append(pair[field])
    _need(set(cells) == {(model, task) for model in model_weights for task in task_weights}, "incomplete family comparison matrix")
    rng = random.Random(inference["seed"])
    def average(sample=False):
        value = 0.0
        if sample:
            tasks = sorted(task_weights)
            sampled_tasks = rng.choices(tasks, weights=[task_weights[task] for task in tasks], k=len(tasks))
            for model, weight in sorted(model_weights.items()):
                task_means = []
                for task in sampled_tasks:
                    values = cells[(model, task)]
                    task_means.append(sum(values[rng.randrange(len(values))] for _ in values) / len(values))
                value += weight * sum(task_means) / len(task_means)
            return value
        for (model, task), values in sorted(cells.items()):
            value += model_weights[model] * task_weights[task] * sum(values) / len(values)
        return value
    repetitions = inference["repetitions"]
    _need(type(repetitions) is int and repetitions >= 1000, "insufficient bootstrap repetitions")
    draws = sorted(average(True) for _ in range(repetitions))
    alpha = 1.0 - inference["confidence"]
    return {"point": average(), "ci": [draws[int(alpha / 2 * repetitions)], draws[min(repetitions - 1, int((1 - alpha / 2) * repetitions))]],
            "n": len(pairs), "method": inference["method"], "seed": inference["seed"]}


def _empirical(run, protocol, repo):
    manifest, base = _artifact(run.get("independent_evidence"), repo)
    frozen = _freeze(manifest, repo)
    _need(isinstance(run.get("run_id"), str) and run["run_id"].strip()
          and isinstance(frozen.get("run_id"), str) and frozen["run_id"] == run["run_id"],
          "independent evidence run mismatch")
    _need(frozen.get("protocol_sha256") == digest(protocol), "holdout protocol was not preregistered")
    _need(frozen.get("baseline_revisions", {}).get("rc15") == RC15, "fixed RC15 anchor is missing")
    from .controller import engine_identity
    identities = run.get("identities", {})
    _need(frozen.get("source_sha256") == identities.get("source") == source_hash(repo), "optimization source identity changed")
    _need(frozen.get("engine_sha256") == identities.get("engine") == engine_identity(repo), "optimization engine identity changed")
    latest = frozen.get("baseline_revisions", {}).get("latest_baseline")
    _need(isinstance(latest, str) and len(latest) == 40 and all(character in "0123456789abcdef" for character in latest),
          "latest release baseline must pin an actual revision")
    _need(latest == protocol["baseline"]["latest_revision"], "latest release baseline differs from preregistration")
    _need(_git(repo, "cat-file", "-t", RC15).strip() == b"commit" and _git(repo, "cat-file", "-t", latest).strip() == b"commit",
          "baseline revisions are not available Git commits")
    candidate = next((row.get("candidate", row) for row in run.get("candidates", [])
                      if candidate_id(row.get("candidate", row)) == frozen.get("candidate_id")), None)
    _need(candidate is not None, "frozen candidate missing from optimization run")
    _need(validate_candidate(candidate, repo)["ok"], "frozen candidate does not preserve engineering contracts")
    _need(source_hash(candidate_source(candidate, repo)) == frozen.get("candidate_source_sha256"), "candidate source changed since holdout freeze")
    splits = _splits(frozen)
    final = splits["final"]
    task_families = {row["task_family"] for row in final.values()}
    minimums = protocol["splits"]
    _need(len(task_families) >= minimums["minimum_task_families"], "insufficient independent task-family coverage")
    _need(len({row["task_family"] for row in final.values() if row.get("kind") == "handoff"}) >= minimums["minimum_handoff_task_families"],
          "insufficient frozen handoff coverage")
    seen = {"observations": set(), "requests": set()}
    rows = []
    for reference in manifest.get("records", []):
        record, record_base = _artifact(reference, base)
        rows.append(_admit(record, record_base, frozen, protocol, final, seen))
    _need(rows, "no independent real holdout observations")
    model_families = {row["model_family"] for row in rows}
    _need(len(model_families) >= minimums["minimum_model_families"], "insufficient model-family coverage")
    mw = _weights(frozen.get("model_family_weights"), model_families, "model-family weights")
    tw = _weights(frozen.get("task_family_weights"), task_families, "task-family weights")
    _need({row["arm"] for row in rows} == set(protocol["arms"]), "incomplete control/ablation arms")
    # Recompute call budgets from provider receipts, including failures and ranking.
    budgets = frozen.get("arm_budgets", {})
    optimization = manifest.get("optimization_calls", {})
    search_arms = {name for name, arm in protocol["arms"].items() if arm["search_modules"]}
    _need(set(budgets) == search_arms and len({digest(value) for value in budgets.values()}) == 1,
          "ablations must freeze identical total search budgets")
    _need(set(optimization) == search_arms, "missing ablation optimization cost evidence")
    actual_costs = {}
    for arm in sorted(search_arms):
        tokens, seconds, dollars, requests = 0, 0, [], set()
        for reference in optimization[arm]:
            receipt, _ = _artifact(reference, base)
            key = _claim_request(receipt, seen["requests"])
            requests.add(key)
            tokens += _number(receipt.get("usage", {}).get("total_tokens"), "optimization tokens")
            seconds += _number(receipt.get("wall_seconds"), "optimization wall time")
            dollars.append(receipt.get("usage", {}).get("cost_usd"))
        _need(requests, "ablation search did not execute real model calls")
        _need(len(requests) <= budgets[arm]["model_calls"] and tokens <= budgets[arm]["tokens"]
              and seconds <= budgets[arm]["wall_seconds"], "ablation exceeded frozen budget")
        actual_costs[arm] = {"model_calls": len(requests), "tokens": tokens, "wall_seconds": seconds,
                             "cost_usd": sum(dollars) if all(type(value) in (int, float) and value >= 0 for value in dollars) else None}
    _need(all(actual_costs["full"][key] <= actual_costs[arm][key] for arm in search_arms for key in ("model_calls", "tokens")),
          "full system used more model budget than an ablation/control")
    valid_ids = {candidate_id(row.get("candidate", row)) for row in run.get("candidates", [])}
    modules = {event.get("operator") for event in run.get("events", [])
               if event.get("kind") == "evaluated" and event.get("candidate_id") in valid_ids}
    _need(MODULES <= modules, "four capabilities lack evaluated candidate provenance")
    reports, by_model_family = {}, {}
    thresholds = protocol["thresholds"]
    for arm in protocol["arms"]:
        if arm == "full":
            continue
        pairs = _paired(rows, "full", arm)
        counts = {}
        for pair in pairs:
            key = (pair["model_family"], pair["task_family"])
            counts[key] = counts.get(key, 0) + 1
        _need(counts and min(counts.values()) >= minimums["minimum_pairs_per_family"], "insufficient independent repetitions")
        reports[arm] = {field: paired_bootstrap(pairs, field, mw, tw, protocol["inference"])
                        for field in ("tokens", "context", "seconds", "quality", "token_saving", "time_saving")}
        reports[arm]["dollar_saving"] = (paired_bootstrap(pairs, "dollar_saving", mw, tw, protocol["inference"])
                                         if all(pair["dollar_saving"] is not None for pair in pairs) else None)
        by_model_family[arm] = {family: {field: paired_bootstrap([pair for pair in pairs if pair["model_family"] == family],
                                                               field, {family: 1.0}, tw, protocol["inference"])
                                                for field in ("tokens", "context", "seconds", "quality")}
                                for family in sorted(mw)}
        _need(reports[arm]["quality"]["ci"][0] >= -thresholds["quality_noninferiority_margin"], "quality noninferiority failed: " + arm)
        _need(all(values["quality"]["ci"][0] >= -thresholds["quality_noninferiority_margin"]
                  for values in by_model_family[arm].values()), "quality regressed within a model family: " + arm)
        if arm in {"rc15", "latest_baseline"}:
            _need(reports[arm]["context"]["point"] <= thresholds["governance_context_ratio_max"], "25% context-token reduction not established: " + arm)
            for field, target in (("tokens", "full_task_tokens_ratio_max"), ("seconds", "wall_time_ratio_max")):
                _need(reports[arm][field]["point"] <= thresholds[target] and reports[arm][field]["ci"][1] < thresholds["cost_ratio_ci_upper_exclusive"],
                      "paired cost threshold/CI failed: " + arm + "/" + field)
        else:
            _need(reports[arm]["tokens"]["ci"][1] < 1 and reports[arm]["seconds"]["ci"][1] < 1,
                  "equal-budget conditional contribution not established: " + arm)
    break_even = {}
    for name, cost_field, saving_field in (("tokens", "tokens", "token_saving"), ("time", "wall_seconds", "time_saving")):
        savings = reports["rc15"][saving_field]
        break_even[name + "_tasks"] = actual_costs["full"][cost_field] / savings["point"] if savings["ci"][0] > 0 else None
    money_savings = reports["rc15"]["dollar_saving"]
    money_cost = actual_costs["full"]["cost_usd"]
    break_even["money_tasks"] = (money_cost / money_savings["point"]
                                 if money_cost is not None and money_savings is not None and money_savings["ci"][0] > 0 else None)
    return {"status": "PASS", "candidate_id": frozen["candidate_id"], "comparisons": reports,
            "by_model_family": by_model_family,
            "optimization_costs": actual_costs, "observations": len(rows),
            "break_even": break_even,
            "trust_boundary": "independent runner/provider/grader provenance; hashes establish continuity, not authenticity"}


def verify(run: dict) -> dict:
    """Recompute evidence gates; ignore all user-supplied pass/status booleans."""
    result = {"engineering": "BLOCKED", "empirical": {"status": "BLOCKED", "reasons": []},
              "formal_qualification": "UNASSESSED", "promotion_allowed": False}
    try:
        _need(isinstance(run, dict), "run must be an object")
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        _need(run.get("protocol_sha256") == digest(protocol), "run protocol differs from immutable registered protocol")
        _need(digest(run.get("protocol")) == digest(protocol), "run configuration does not match its registered protocol hash")
        candidates = run.get("candidates", [])
        _need(candidates, "no executable candidates")
        selected_id = run.get("best_candidate_id")
        selected = next((row.get("candidate", row) for row in candidates
                         if candidate_id(row.get("candidate", row)) == selected_id), candidates[0].get("candidate", candidates[0]))
        checks = [validate_candidate(selected, ROOT)]
        result["engineering_checks"] = checks
        result["engineering_scope"] = "selected candidate isolated compile, lint, integrity and fixture plan contracts"
        _need(all(check["ok"] for check in checks), "candidate compiler/core contract validation failed")
        result["engineering"] = "PASS"
        result["empirical"] = _empirical(run, protocol, ROOT)
        result["promotion_allowed"] = True
    except (EvidenceError, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, subprocess.SubprocessError) as error:
        result["empirical"]["reasons"] = [str(error)]
    return result


def propose(run: dict, repo: Path | str, output: Path | str) -> dict:
    """Write a reviewable patch only after independent gates, never apply it."""
    repo, output = Path(repo).resolve(), Path(output).resolve()
    _need(repo == ROOT.resolve(), "proposals must bind the verified canonical repository")
    verification = verify(run)
    if not verification["promotion_allowed"]:
        return {"status": "BLOCKED", "verification": verification}
    selected = verification["empirical"]["candidate_id"]
    candidate = next(row.get("candidate", row) for row in run["candidates"]
                     if candidate_id(row.get("candidate", row)) == selected)
    _need(not output.exists(), "proposal output already exists")
    model_path = repo / "governance-src/model/governance-model.json"
    before = model_path.read_text(encoding="utf-8").splitlines(keepends=True)
    after = (json.dumps(materialize(candidate), indent=2, ensure_ascii=False) + "\n").splitlines(keepends=True)
    patch = "".join(difflib.unified_diff(before, after, fromfile="a/governance-src/model/governance-model.json",
                                      tofile="b/governance-src/model/governance-model.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".upg-proposal-", dir=output.parent) as staging:
        staged = Path(staging) / "proposal"
        staged.mkdir()
        (staged / "candidate.patch").write_text(patch, encoding="utf-8")
        (staged / "verification.json").write_bytes(canonical_bytes(verification))
        # Compilation output is reviewable in the proposal; canonical source remains unchanged.
        (staged / "model.json").write_bytes(canonical_bytes(materialize(candidate)))
        from compiler.compile_governance import compile_runtime
        with tempfile.TemporaryDirectory(prefix="upg-proposal-") as temporary:
            isolated = Path(temporary)
            shutil.copytree(repo / "governance-src", isolated / "governance-src",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            shutil.copyfile(repo / "LICENSE", isolated / "LICENSE")
            (isolated / "governance-src/model/governance-model.json").write_bytes(canonical_bytes(materialize(candidate)))
            compile_runtime(isolated, staged / "universal-project-governance")
        staged.replace(output)
    return {"status": "PROPOSED", "candidate_id": selected, "patch": str(output / "candidate.patch"),
            "formal_qualification": "UNASSESSED"}
