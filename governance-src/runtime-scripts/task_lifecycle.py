"""Bounded tracked-task contracts and current evidence; never executes planned work."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from completion_review import capture_sources
from state_tool import load, validate_node

ROOT = Path(__file__).resolve().parents[1]
MAX_STATE_BYTES = 32768
ATTEMPTED = {"running", "passed", "failed"}


def schema(name):
    return load(ROOT / "schemas/field-report.schema.json")["properties"][name]


def _valid(value, name):
    errors = validate_node(value, schema(name))
    if errors:
        raise ValueError("invalid " + name + ": " + "; ".join(errors))


def validate_units(units):
    ids = [unit["id"] for unit in units]
    if len(set(ids)) != len(ids):
        raise ValueError("task units require unique IDs")
    graph = {unit["id"]: unit["depends_on"] for unit in units}
    for identity, dependencies in graph.items():
        if identity in dependencies or set(dependencies) - set(ids):
            raise ValueError("task unit dependency is unknown or self-referential")
    visited, pending = set(), set()
    def visit(identity):
        if identity in pending:
            raise ValueError("task unit dependency cycle")
        if identity in visited:
            return
        pending.add(identity)
        for dependency in graph[identity]:
            visit(dependency)
        pending.remove(identity)
        visited.add(identity)
    for identity in ids:
        visit(identity)


def validate_contract(contract):
    _valid(contract, "task_contract")
    validate_units(contract["units"])


def initial_state(contract):
    validate_contract(contract)
    return {"revision": contract["revision"], "units": copy.deepcopy(contract["units"]), "completed": {}}


class Evidence:
    def __init__(self, project, validation_revision="unknown"):
        self.project = Path(project)
        self.validation_revision = validation_revision
        self.sources, self.references = {}, set()

    def add(self, proof):
        if not proof.get("evidence"):
            raise ValueError("passed task result or acceptance requires evidence")
        current = False
        sources = proof.get("sources", [])
        for item in sources:
            path = item["path"]
            expected = [item["sha256"], item["executable"]] if item["sha256"] is not None else None
            if expected is None and item["executable"] != 0:
                raise ValueError("absent task evidence source requires zero executable bits")
            if path in self.sources and self.sources[path] != expected:
                raise ValueError("task evidence has conflicting current source identities")
            self.sources[path] = expected
        current = bool(sources)
        if "current_state" in proof:
            from state_tool import resolve_current_state
            ref = proof["current_state"]
            key = ("state", json.dumps(ref, sort_keys=True))
            if key not in self.references:
                resolve_current_state(self.project, ref)
                self.references.add(key)
            current = True
        if "validation_ref" in proof:
            from state_tool import resolve_validation_ref
            ref = proof["validation_ref"]
            key = ("validation", json.dumps(ref, sort_keys=True))
            if key not in self.references:
                run = resolve_validation_ref(ref, self.project)
                if run["result"] != "passed" or run.get("pending_retest") or run.get("later_changes"):
                    raise ValueError("task validation evidence is not currently passed")
                if self.validation_revision != "unknown" and run["tested_revision"] != self.validation_revision:
                    raise ValueError("task validation evidence tested revision does not match")
                self.references.add(key)
            current = True
        if not current:
            raise ValueError("passed task evidence requires current sources or a verified reference")

    def finish(self):
        if self.sources and capture_sources(self.project, list(self.sources)) != self.sources:
            raise ValueError("task evidence sources are stale; revalidate or invalidate the affected unit")


def verify_evidence(project, payload):
    """Check evidence for an already published historical candidate during recovery."""
    progress = payload.get("task_progress")
    if progress is None:
        return
    _valid(progress, "task_progress")
    evidence = Evidence(project, payload["change"]["validation_revision"])
    for result in progress["results"]:
        if result["status"] == "passed":
            evidence.add(result)
    for acceptance in progress.get("acceptance", []):
        evidence.add(acceptance)
    evidence.finish()


def evaluate(project, payload, active):
    """Validate a new stage and derive one bounded current state, without writing."""
    contract_present = isinstance(active, dict) and "task_contract" in active
    if not contract_present:
        if "task_progress" in payload or "task_contract" in payload:
            raise ValueError("observational or legacy workflow cannot claim task contract execution")
        return None
    contract = active["task_contract"]
    validate_contract(contract)
    progress = payload.get("task_progress")
    if progress is None:
        raise ValueError("contract workflow requires task_progress at every observed boundary")
    _valid(progress, "task_progress")
    if payload["status"] == "complete":
        if progress["next_action"] is not None:
            raise ValueError("complete task progress requires null next_action")
    elif not isinstance(progress["next_action"], str) or not progress["next_action"].strip():
        raise ValueError("unfinished task progress requires a next_action")
    state = copy.deepcopy(active.get("task_state") or initial_state(contract))
    _valid(state, "task_state")
    validate_units(state["units"])
    current_units = {unit["id"]: unit for unit in state["units"]}
    if len(state["completed"]) > 16 or any(identity not in current_units or completed["unit"] != current_units[identity]
            or completed["result"]["id"] != identity or completed["result"]["status"] != "passed"
            for identity, completed in state["completed"].items()):
        raise ValueError("invalid tool-owned completed task unit state")
    replan = progress.get("replan")
    if progress["revision"] != state["revision"]:
        if replan is None or replan["from_revision"] != state["revision"]:
            raise ValueError("task replan requires its current revision and an explicit reason")
        validate_units(replan["units"])
        proposed = {unit["id"]: unit for unit in replan["units"]}
        for identity, completed in state["completed"].items():
            if proposed.get(identity) != completed["unit"]:
                raise ValueError("task replan cannot remove or change a completed unit")
        state["revision"], state["units"] = progress["revision"], copy.deepcopy(replan["units"])
    elif replan is not None:
        raise ValueError("task replan must use a new revision identity")
    units = {unit["id"]: unit for unit in state["units"]}
    results = progress["results"]
    ids = [result["id"] for result in results]
    if len(ids) != len(set(ids)) or set(ids) != set(units):
        raise ValueError("task progress must cover every current unit exactly once")
    by_id = {result["id"]: result for result in results}
    evidence = Evidence(project, payload["change"]["validation_revision"])
    for identity, result in by_id.items():
        if result["status"] in ATTEMPTED and any(by_id[dependency]["status"] != "passed" for dependency in units[identity]["depends_on"]):
            raise ValueError("task unit requires currently passed dependencies")
        if identity in state["completed"] and result["status"] != "passed" and not result.get("invalidation_reason", "").strip():
            raise ValueError("previously passed task unit requires an explicit invalidation_reason")
        if identity in state["completed"] and result["status"] != "passed":
            del state["completed"][identity]
        if result["status"] == "passed":
            evidence.add(result)
            state["completed"][identity] = {"unit": copy.deepcopy(units[identity]), "result": copy.deepcopy(result)}
    accepted = progress.get("acceptance", [])
    criteria = [item["criterion"] for item in accepted]
    if len(criteria) != len(set(criteria)) or set(criteria) - set(contract["acceptance"]):
        raise ValueError("task acceptance evidence must reference distinct original criteria")
    for proof in accepted:
        evidence.add(proof)
    if payload["status"] == "complete":
        if any(result["status"] != "passed" for result in results):
            raise ValueError("normal task completion requires every current unit passed")
        if set(criteria) != set(contract["acceptance"]):
            raise ValueError("normal task completion requires all original acceptance evidence")
    evidence.finish()
    if len(json.dumps(state, ensure_ascii=False).encode("utf-8")) > MAX_STATE_BYTES:
        raise ValueError("bounded task state is full; reduce evidence to current canonical references")
    return state
