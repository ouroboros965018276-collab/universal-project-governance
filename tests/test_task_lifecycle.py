"""Bounded task lifecycle mechanics; synthetic evidence, never product acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from registration_fixture import change, reviewed_report, seed_legacy_active

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "governance-src/runtime-scripts"))
SPEC = importlib.util.spec_from_file_location("lifecycle_project_tool", ROOT / "governance-src/runtime-scripts/project_tool.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)
import task_lifecycle
from completion_review import capture_sources


def write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(payload).encode("utf-8"))
    return path


def contract():
    return dict(revision="p1", scope=["synthetic lifecycle mechanics"],
                acceptance=["all fixture boundaries verified"], constraints=["no external execution"],
                unknowns=["fixture target starts unverified"], units=[
                    dict(id="inspect", outcome="observe fixture source", verification="read fixture identity", depends_on=[]),
                    dict(id="verify", outcome="verify fixture result", verification="assert lifecycle output", depends_on=["inspect"])])


class TaskLifecycleTests(unittest.TestCase):
    def setUp(self):
        runtime_index = json.loads((ROOT / "universal-project-governance/policy-index.json").read_text(encoding="utf-8"))
        index_patch = patch.object(tool, "index", return_value=runtime_index)
        index_patch.start()
        self.addCleanup(index_patch.stop)
        temporary = tempfile.TemporaryDirectory(prefix="task-lifecycle-", dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "value.txt").write_bytes(b"observed synthetic value\n")

    def begin(self, reporting=False, value=None):
        tool.ensure(self.root, field_test_reporting=reporting)
        value = value or dict(workflow_id="tracked-task", change=change(), task_contract=contract())
        tool.begin_workflow(self.root, write(self.root / ".governance/start.json", value))
        return value

    def sources(self, paths=("value.txt",)):
        observed = capture_sources(self.root, list(paths))
        return [dict(path=relative, sha256=identity[0] if identity else None,
                     executable=identity[1] if identity else 0) for relative, identity in observed.items()]

    def proof(self):
        return dict(evidence=["Synthetic file identity observed; not product acceptance"], sources=self.sources())

    def payload(self, start, status="complete", statuses=None, checkpoint="step-1"):
        task_contract = start.get("task_contract", contract())
        statuses = statuses or (["passed"] * len(task_contract["units"]) if status == "complete" else ["pending"] * len(task_contract["units"]))
        results = [dict(id=unit["id"], status=state, **(self.proof() if state == "passed" else {"evidence": []}))
                   for unit, state in zip(task_contract["units"], statuses)]
        progress = dict(revision=task_contract["revision"], results=results,
                        next_action=None if status == "complete" else "run the next synthetic check")
        if status == "complete":
            progress["acceptance"] = [dict(criterion=criterion, **self.proof()) for criterion in task_contract["acceptance"]]
        value = dict(workflow_id=start["workflow_id"], change=copy.deepcopy(start["change"]), task="synthetic mechanics",
                     status=status, change_mode="local", scope_guard="local-only", risk_level="low", active_rules=[],
                     changed_files=["value.txt"], validation=["synthetic focused validation"], cleanup=[], integrity="pass",
                     handoff="not-required" if status == "complete" else "created", feedback=[], task_progress=progress,
                     structural_scope=dict(canonical_layer="runtime", unrelated_changes=[], api_changes=[],
                                           architecture_changes=[], overreach_concern=False))
        if status != "complete":
            value["checkpoint_id"] = checkpoint
        return reviewed_report(value, self.root)

    def finish(self, value, direct=False):
        return (tool.record_report if direct else tool.finish_workflow)(
            self.root, write(self.root / ".governance/outcome.json", value))

    def durable(self):
        return {path.name: path.read_bytes() for path in (self.root / ".governance").glob("*.json")
                if path.name not in {"start.json", "outcome.json"}}

    def reject_without_write(self, value, message=None, direct=False):
        before = self.durable()
        with self.assertRaisesRegex(ValueError, message or ".+"):
            self.finish(value, direct=direct)
        self.assertEqual(before, self.durable())

    def test_new_begin_requires_contract_without_legacy_escape(self):
        tool.ensure(self.root)
        for extras in ({}, {"legacy": True}, {"legacy_workflow": True}, {"task_contract": None}):
            with self.subTest(extras=extras):
                start = dict(workflow_id="new-without-contract", change=change(), **extras)
                before = self.durable()
                with self.assertRaises(ValueError):
                    tool.begin_workflow(self.root, write(self.root / ".governance/start.json", start))
                self.assertEqual(before, self.durable())

    def test_contract_graph_and_bounds_are_checked_before_begin(self):
        tool.ensure(self.root)
        invalid = []
        for key, value in (("scope", []), ("acceptance", []), ("unknowns", ["x" * 1001]), ("units", [])):
            bad = contract(); bad[key] = value; invalid.append(bad)
        for dependencies in (["missing"], ["inspect"], ["verify"]):
            bad = contract(); bad["units"][0]["depends_on"] = dependencies; invalid.append(bad)
        duplicate = contract(); duplicate["units"][1]["id"] = "inspect"; invalid.append(duplicate)
        for bad in invalid:
            with self.subTest(contract=bad):
                before = self.durable()
                with self.assertRaises(ValueError):
                    tool.begin_workflow(self.root, write(self.root / ".governance/start.json",
                        dict(workflow_id="invalid-contract", change=change(), task_contract=bad)))
                self.assertEqual(before, self.durable())

    def test_begin_preserves_business_metadata_and_exact_retry(self):
        start = self.begin(value=dict(workflow_id="tracked-task", change=change(), task_contract=contract(), business_context="preserved"))
        active = tool.status(self.root)["active_workflow"]
        self.assertEqual(active["task_contract"], start["task_contract"])
        self.assertEqual(active["business_context"], "preserved")
        self.assertEqual(active["task_state"], task_lifecycle.initial_state(start["task_contract"]))
        before = self.durable()
        self.assertTrue(tool.begin_workflow(self.root, self.root / ".governance/start.json")["idempotent"])
        self.assertEqual(before, self.durable())

    def test_new_begin_cannot_claim_progress_but_historical_exact_start_is_preserved(self):
        tool.ensure(self.root)
        start = dict(workflow_id="old-start-with-metadata", change=change(), task_contract=contract(),
                     task_progress={"historical_business_metadata": "preserved without retroactive execution claim"})
        before = self.durable()
        with self.assertRaisesRegex(ValueError, "observed outcome"):
            tool.begin_workflow(self.root, write(self.root / ".governance/start.json", start))
        self.assertEqual(before, self.durable())
        seed_legacy_active(tool, self.root, start)
        before = self.durable()
        self.assertTrue(tool.begin_workflow(self.root, self.root / ".governance/start.json")["idempotent"])
        self.assertEqual(before, self.durable())

    def test_begin_current_state_is_verified_without_creating_a_new_record(self):
        state = write(self.root / "execution.json", {"observed": "fixture"})
        ref = dict(path="execution.json", sha256=hashlib.sha256(state.read_bytes()).hexdigest())
        start = dict(workflow_id="tracked-task", change=change(), task_contract=contract(), current_state=ref)
        state.write_bytes(b'{}')
        tool.ensure(self.root)
        before = self.durable()
        with self.assertRaisesRegex(ValueError, "SHA|hash|stale|changed"):
            tool.begin_workflow(self.root, write(self.root / ".governance/start.json", start))
        self.assertEqual(before, self.durable())
        ref["sha256"] = hashlib.sha256(state.read_bytes()).hexdigest()
        self.begin(value=start)
        self.assertEqual(tool.status(self.root)["current_state"], ref)

    def test_missing_progress_and_tool_owned_state_cannot_bypass_either_mode(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting):
                start = self.begin(reporting)
                value = self.payload(start)
                value.pop("task_progress")
                self.reject_without_write(value, "requires task_progress")
                value = self.payload(start)
                value["task_state"] = task_lifecycle.initial_state(contract())
                self.reject_without_write(value, "tool-owned")

    def test_dependency_attempts_require_passed_results(self):
        start = self.begin()
        for state in ("running", "passed", "failed"):
            for prior in ("pending", "failed", "blocked", "unknown"):
                with self.subTest(state=state, prior=prior):
                    self.reject_without_write(self.payload(start, "partial", [prior, state]), "dependencies")
        self.finish(self.payload(start, "partial", ["passed", "running"]))

    def test_every_current_unit_must_appear_exactly_once(self):
        start = self.begin()
        for mutation in (lambda rows: rows.pop(), lambda rows: rows.append(copy.deepcopy(rows[0])),
                         lambda rows: rows[1].update(id="unplanned")):
            value = self.payload(start, "partial")
            mutation(value["task_progress"]["results"])
            self.reject_without_write(value, "every current unit")

    def test_unfinished_next_action_and_complete_null_are_enforced(self):
        start = self.begin()
        for status, action in (("partial", None), ("blocked", " "), ("complete", "continue")):
            value = self.payload(start, status)
            value["task_progress"]["next_action"] = action
            self.reject_without_write(value, "next_action|pattern")

    def test_passed_units_require_current_evidence_and_reject_secrets(self):
        start = self.begin()
        for proof in ({"evidence": []}, {"evidence": ["claim without current proof"]},
                      {"evidence": ["api_key=" + "a" * 20], "sources": self.sources()}):
            value = self.payload(start, "partial", ["passed", "pending"])
            value["task_progress"]["results"][0] = dict(id="inspect", status="passed", **proof)
            self.reject_without_write(value)

    def test_stale_bytes_modes_deletions_and_unsafe_paths_reject_before_write(self):
        start = self.begin()
        value = self.payload(start, "partial", ["passed", "pending"])
        (self.root / "value.txt").write_bytes(b"changed\n")
        self.reject_without_write(value, "stale")
        for path in ("../outside", ".git/config", ".governance/upg.json"):
            value = self.payload(start, "partial", ["passed", "pending"])
            value["task_progress"]["results"][0]["sources"] = [dict(path=path, sha256=None, executable=0)]
            self.reject_without_write(value)
        value = self.payload(start, "partial", ["passed", "pending"])
        value["task_progress"]["results"][0]["sources"][0]["executable"] = 73
        self.reject_without_write(value, "stale")
        (self.root / "value.txt").unlink()
        value = self.payload(start, "partial", ["passed", "pending"])
        (self.root / "value.txt").write_bytes(b"recreated\n")
        self.reject_without_write(value, "stale")

    def test_complete_requires_all_passed_and_original_acceptance_then_review(self):
        start = self.begin()
        for mutation, message in ((lambda value: value["task_progress"]["results"][1].update(status="unknown"), "every current unit"),
                                  (lambda value: value["task_progress"].update(acceptance=[]), "original acceptance"),
                                  (lambda value: value["task_progress"]["acceptance"][0].update(criterion="invented"), "original criteria"),
                                  (lambda value: value.pop("completion_review"), "requires completion_review")):
            value = self.payload(start)
            mutation(value)
            self.reject_without_write(value, message)
        self.finish(self.payload(start))

    def test_partial_blocked_complete_preserve_original_and_are_idempotent(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting):
                # Each mode gets its own project and original immutable start.
                if tool.status(self.root).get("latest_change"):
                    self.setUp()
                start = self.begin(reporting)
                partial = self.payload(start, "partial", ["passed", "pending"])
                self.finish(partial)
                before = self.durable()
                self.assertTrue(self.finish(partial)["idempotent"])
                self.assertEqual(before, self.durable())
                blocked = self.payload(start, "blocked", ["passed", "blocked"], "step-2")
                self.finish(blocked)
                active = tool.status(self.root)["active_workflow"]
                self.assertEqual(active["task_contract"], start["task_contract"])
                self.assertEqual(active["change"], start["change"])
                self.assertEqual(active["last_outcome"]["task_progress"], blocked["task_progress"])
                completed = self.payload(start)
                self.finish(completed)
                state = tool.status(self.root)
                self.assertIsNone(state["active_workflow"])
                self.assertEqual(state["latest_change"]["task_contract"], start["task_contract"])
                self.assertEqual(state["latest_change"]["task_progress"], completed["task_progress"])
                self.assertEqual(set(state["latest_change"]["task_state"]["completed"]), {"inspect", "verify"})
                (self.root / "value.txt").write_bytes(b"later unrelated work\n")
                self.assertTrue(self.finish(completed)["idempotent"])

    def test_replan_remaining_units_requires_new_identity_and_preserves_completed(self):
        start = self.begin()
        self.finish(self.payload(start, "partial", ["passed", "pending"]))
        value = self.payload(start, "partial", ["passed", "pending"], "step-2")
        progress = value["task_progress"]
        progress["revision"] = "p2"
        self.reject_without_write(value, "replan")
        units = copy.deepcopy(contract()["units"])
        units[1]["verification"] = "revised remaining verification after observed facts"
        progress["replan"] = dict(from_revision="p1", reason="observed fixture requires a different check", units=units)
        bad = copy.deepcopy(value); bad["task_progress"]["replan"]["units"][0]["outcome"] = "rewrite finished work"
        self.reject_without_write(bad, "completed unit")
        self.finish(value)
        active = tool.status(self.root)["active_workflow"]
        self.assertEqual(active["task_state"]["revision"], "p2")
        self.assertEqual(active["task_contract"], start["task_contract"])
        completed = self.payload(start)
        completed["task_progress"]["revision"] = "p2"
        self.finish(completed)

    def test_passed_evidence_must_be_refreshed_or_explicitly_invalidated(self):
        start = self.begin()
        first = self.payload(start, "partial", ["passed", "pending"])
        self.finish(first)
        (self.root / "value.txt").write_bytes(b"changed after validation\n")
        stale = self.payload(start, "partial", ["passed", "pending"], "step-2")
        stale["task_progress"]["results"][0] = copy.deepcopy(first["task_progress"]["results"][0])
        self.reject_without_write(stale, "stale")
        invalid = self.payload(start, "blocked", ["unknown", "blocked"], "step-2")
        self.reject_without_write(invalid, "invalidation_reason")
        invalid["task_progress"]["results"][0]["invalidation_reason"] = "source changed since previous proof"
        self.finish(invalid)
        self.assertNotIn("inspect", tool.status(self.root)["active_workflow"]["task_state"]["completed"])
        self.finish(self.payload(start))

    def test_explicit_invalidation_allows_replanning_remaining_work_and_preserves_independent_pass(self):
        task_contract = contract()
        task_contract["units"].append(dict(id="independent", outcome="separate fixture check", verification="read separate proof", depends_on=[]))
        start = self.begin(value=dict(workflow_id="tracked-task", change=change(), task_contract=task_contract))
        first = self.payload(start, "partial", ["passed", "passed", "passed"])
        self.finish(first)
        invalid = self.payload(start, "blocked", ["unknown", "passed", "passed"], "step-2")
        invalid["task_progress"]["results"][0]["invalidation_reason"] = "observed source change requires renewed inspection"
        self.reject_without_write(invalid, "dependencies")
        invalid["task_progress"]["results"][1].update(status="blocked", invalidation_reason="prerequisite proof is invalid")
        self.finish(invalid)
        active = tool.status(self.root)["active_workflow"]
        self.assertEqual(set(active["task_state"]["completed"]), {"independent"})
        replanned = self.payload(start, "partial", ["pending", "pending", "passed"], "step-3")
        progress = replanned["task_progress"]
        progress["revision"] = "p2"
        units = copy.deepcopy(task_contract["units"])
        units[0]["verification"] = "repeat inspection against the changed fixture"
        progress["replan"] = dict(from_revision="p1", reason="invalidated proof requires revised remaining verification", units=units)
        bad = copy.deepcopy(replanned); bad["task_progress"]["replan"]["units"][2]["outcome"] = "silently change unaffected completion"
        self.reject_without_write(bad, "completed unit")
        self.finish(replanned)
        final = self.payload(start)
        final["task_progress"]["revision"] = "p2"
        self.finish(final)
        latest = tool.status(self.root)["latest_change"]
        self.assertEqual(latest["task_contract"], task_contract)
        self.assertEqual(latest["task_state"]["units"][0]["verification"], units[0]["verification"])

    def test_supporting_evidence_drift_during_final_gate_rejects_before_publication(self):
        import completion_review
        for reporting in (False, True):
            with self.subTest(reporting=reporting):
                if tool.status(self.root).get("active_workflow"):
                    self.setUp()
                start = self.begin(reporting)
                support = self.root / "support.json"
                support.write_bytes(b'{"observed":"supporting acceptance"}')
                value = self.payload(start)
                value["task_progress"]["acceptance"][0]["sources"] = self.sources(("support.json",))
                original = completion_review.verify_completion
                def drift(project, payload, binding):
                    result = original(project, payload, binding)
                    support.write_bytes(b'{"observed":"changed before publication"}')
                    return result
                with patch.object(completion_review, "verify_completion", side_effect=drift):
                    self.reject_without_write(value, "stale")

    def test_current_state_and_validation_run_references_require_current_passed_records(self):
        start = self.begin()
        state = write(self.root / "execution.json", {"validation_runs": [dict(run_id="focused", scope="synthetic checks",
            result="passed", tested_revision="a" * 40, passed=1, total=1)]})
        ref = dict(path="execution.json", sha256=hashlib.sha256(state.read_bytes()).hexdigest())
        value = self.payload(start, "partial", ["passed", "pending"])
        result = value["task_progress"]["results"][0]
        result.pop("sources"); result["current_state"] = ref
        self.finish(value)
        value = self.payload(start, "partial", ["passed", "pending"], "step-2")
        result = value["task_progress"]["results"][0]
        result.pop("sources"); result["validation_ref"] = dict(ref, run_id="focused")
        value["change"]["validation_revision"] = "b" * 40
        self.reject_without_write(value, "tested revision")
        value["change"]["validation_revision"] = "a" * 40
        record = json.loads(state.read_bytes()); record["validation_runs"][0]["pending_retest"] = True
        write(state, record)
        result["validation_ref"]["sha256"] = hashlib.sha256(state.read_bytes()).hexdigest()
        self.reject_without_write(value, "currently passed")
        record["validation_runs"][0].pop("pending_retest"); write(state, record)
        result["validation_ref"]["sha256"] = hashlib.sha256(state.read_bytes()).hexdigest()
        self.finish(value)

    def test_direct_report_is_observational_without_active_and_gated_with_contract(self):
        tool.ensure(self.root, field_test_reporting=True)
        observational_start = dict(workflow_id="observation", change=change())
        observed = self.payload(observational_start)
        self.reject_without_write(observed, "observational", direct=True)
        observed.pop("task_progress")
        self.finish(observed, direct=True)
        event = tool.status(self.root)["latest_change"]["event_id"]
        start = dict(workflow_id="tracked-task", change=change(), task_contract=contract())
        start["change"]["parent_event_id"] = event
        self.begin(True, start)
        value = self.payload(start); value.pop("task_progress")
        self.reject_without_write(value, "requires task_progress", direct=True)
        self.finish(self.payload(start), direct=True)

    def test_observed_legacy_active_and_old_contract_begin_without_derived_state_are_compatible(self):
        for with_contract in (False, True):
            with self.subTest(with_contract=with_contract):
                if tool.status(self.root).get("latest_change"):
                    self.setUp()
                tool.ensure(self.root)
                start = dict(workflow_id="old-observed", change=change())
                if with_contract:
                    start["task_contract"] = contract()
                seed_legacy_active(tool, self.root, start)
                self.assertTrue(tool.begin_workflow(self.root, write(self.root / ".governance/start.json", start))["idempotent"])
                value = self.payload(start)
                if not with_contract:
                    value.pop("task_progress")
                self.finish(value)
                self.assertTrue(self.finish(value)["idempotent"])

    def test_crash_after_ledger_write_reconciles_same_bounded_task_state(self):
        start = self.begin(True)
        value = self.payload(start, "partial", ["passed", "pending"])
        with patch.object(tool, "_reconcile_completion", side_effect=RuntimeError("synthetic crash after ledger publication")):
            with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
                self.finish(value)
        self.assertEqual(tool.status(self.root)["active_workflow"]["task_state"]["completed"], {})
        self.finish(value)
        self.assertEqual(set(tool.status(self.root)["active_workflow"]["task_state"]["completed"]), {"inspect"})
        self.assertTrue(self.finish(value)["idempotent"])
        self.finish(self.payload(start))

    def test_state_and_metadata_budgets_are_bounded_before_publication(self):
        start = self.begin()
        value = self.payload(start, "partial", ["passed", "pending"])
        with patch.object(task_lifecycle, "MAX_STATE_BYTES", 100):
            self.reject_without_write(value, "bounded task state")
        value["extra_context"] = "x" * 65536
        self.reject_without_write(value, "64|metadata|large")


if __name__ == "__main__":
    unittest.main()
