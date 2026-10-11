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

from .contracts import canonical_bytes, digest
from .controller import callable_identity, checkpoint_lock, engine_identity, run_search, save_run
from .evaluator import source_hash

MODULES = {"skillopt", "annealing", "de", "curvature"}


def _command(command, cwd):
    observed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", timeout=60, check=False)
    return {"command": [Path(str(value)).name if Path(str(value)).is_absolute() else str(value)
                        for value in command],
            "returncode": observed.returncode, "stdout": observed.stdout, "stderr": observed.stderr}


def _baseline(repo, revision):
    """Observe the actual historical runtime, without modern materialization."""
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("baseline must pin a full Git commit")
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", revision],
                             capture_output=True, timeout=60, check=False)
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
        return {"stage": "historical-baseline-engineering", "revision": revision,
                "version": model["version"], "source_sha256": source_hash(isolated),
                "engineering": "PASS" if routed and all(check["returncode"] == 0 for check in checks) else "FAIL",
                "checks": checks, "fixture_contexts": len(routed),
                "context_bytes": len((runtime / "SKILL.md").read_bytes()) + sum(routed) / len(routed) if routed else None,
                "measurement": "skill-bytes-plus-unweighted-mean-fixture-plan-bytes; not tokens",
                "actual_task_usage": None, "independent_holdout": False}


def _summary(run):
    budget = run.get("budget", {})
    return {"run_id": run.get("run_id"), "stage": run.get("stage"), "status": run.get("status"),
            "candidate_count": len(run.get("candidates", [])), "best_candidate_id": run.get("best_candidate_id"),
            "operator_counts": run.get("operator_counts", {}),
            "budget_caps": {key: budget.get(key) for key in ("max_calls", "max_total_tokens", "max_seconds")},
            "attempted_calls": budget.get("calls"),
            "actual_task_usage": None if run.get("stage") == "engineering" else budget,
            "empirical_status": "BLOCKED"}


def run_matrix(repo, protocol, output, runner=None, backend=None):
    with checkpoint_lock(output):
        return _run_matrix(repo, protocol, output, runner=runner, backend=backend)


def _run_matrix(repo, protocol, output, runner=None, backend=None):
    """Resume per-arm checkpoints only when source/protocol/callbacks still match.

    Search arms inherit identical caps. The controller reallocates dispatches for
    disabled modules; using a cap is not evidence that actual costs were equal.
    Historical baseline observations here are engineering checks even when the
    search arms use real development callbacks.
    """
    repo, output = Path(repo).resolve(), Path(output).resolve()
    identity = {"protocol_sha256": digest(protocol), "source_sha256": source_hash(repo),
                "engine_sha256": engine_identity(repo), "runner": callable_identity(runner),
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
        if matrix["arms"].get(name, {}).get("completed"):
            continue
        if name in {"rc15", "latest_baseline"}:
            revision = protocol["baseline"]["rc15_revision" if name == "rc15" else "latest_revision"]
            result = _baseline(repo, revision)
            matrix["arms"][name] = dict(result, completed=True)
        else:
            enabled = {"annealing" if module in {"chaos", "ordinary_annealing"} else module
                       for module in definition["search_modules"]}
            if not enabled <= MODULES:
                raise ValueError("unknown search module in arm " + name)
            arm_path = output / "arms" / (name + ".json")
            run = run_search(repo, protocol, arm_path, runner=runner, backend=backend,
                             resume=arm_path.exists(), disabled=tuple(sorted(MODULES - enabled)),
                             ordinary="ordinary_annealing" in definition["search_modules"])
            matrix["arms"][name] = dict(_summary(run), completed=run.get("status") in {"completed", "budget-exhausted"},
                                       checkpoint="arms/" + name + ".json")
        save_run(matrix_path, matrix)
    matrix["status"] = "completed" if all(value.get("completed") for value in matrix["arms"].values()) else "checkpointed"
    save_run(matrix_path, matrix)
    return matrix
