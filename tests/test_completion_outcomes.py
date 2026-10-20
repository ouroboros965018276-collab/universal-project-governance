"""Completion outcome regressions; synthetic engineering evidence only."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from registration_fixture import change

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "governance-src/runtime-scripts"))
SPEC = importlib.util.spec_from_file_location(
    "completion_project_tool", ROOT / "governance-src/runtime-scripts/project_tool.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def write(path, payload):
    path = Path(path)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def report(start, status="complete"):
    metadata = copy.deepcopy(start["change"])
    metadata.update(after="observed implementation outcome", result_revision="a" * 40,
                    validation_revision="b" * 40, occurred_at="2026-10-10T02:03:04Z",
                    time_source="observed synthetic fixture event")
    return dict(
        workflow_id=start["workflow_id"], change=metadata, task="synthetic completion regression",
        status=status, change_mode="local", scope_guard="local-only", risk_level="low",
        active_rules=[], changed_files=["runtime.py"], validation=["focused fixture passed"],
        cleanup=["superseded path removed"], integrity="pass", handoff="not-required", feedback=[],
        structural_scope=dict(canonical_layer="runtime", unrelated_changes=[], api_changes=[],
                              architecture_changes=[], overreach_concern=False),
    )


class CompletionOutcomeTests(unittest.TestCase):
    def setUp(self):
        # Canonical scripts consume the compiled policy index. No compilation or
        # generated-runtime mutation is required for these source-level checks.
        index = json.loads((ROOT / "universal-project-governance/policy-index.json").read_text(encoding="utf-8"))
        self.index_patch = patch.object(tool, "index", return_value=index)
        self.index_patch.start()
        self.addCleanup(self.index_patch.stop)

    def begin(self, project, reporting, workflow="outcomes", parent=None):
        tool.ensure(project, field_test_reporting=reporting)
        start = dict(workflow_id=workflow, change=change())
        start["change"]["after"] = "planned target, outcome unknown"
        start["change"]["parent_event_id"] = parent
        tool.begin_workflow(project, write(Path(project) / (workflow + "-start.json"), start))
        return start

    def finish(self, project, payload):
        return tool.finish_workflow(project, write(Path(project) / "finish.json", payload))

    def ledger(self, project):
        return json.loads((Path(project) / ".governance/field-reports.json").read_text(encoding="utf-8"))

    def test_actual_outcome_replaces_goal_and_preserves_original_start_in_both_modes(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                completed = report(start)
                self.finish(td, completed)
                state = tool.status(td)
                self.assertIsNone(state["active_workflow"])
                self.assertEqual(state["latest_change"]["change"], completed["change"])
                self.assertEqual(state["latest_change"]["start_change"], start["change"])
                self.assertTrue(self.finish(td, completed)["idempotent"])
                self.assertLessEqual(len(state["managed_files"]), 2)
                if reporting:
                    entries = self.ledger(td)["reports"]
                    self.assertEqual(len(entries), 1)
                    self.assertEqual(entries[0]["start_change"], start["change"])
                    schema = tool.load_json(tool.ROOT / "schemas/field-report.schema.json")
                    self.assertEqual(tool.validate_node(entries[0], schema), [])
                else:
                    self.assertFalse((Path(td) / ".governance/field-reports.json").exists())

    def test_unknown_outcome_facts_remain_allowed(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                completed = report(start)
                completed["change"].update(result_revision="unknown", validation_revision="unknown",
                                           occurred_at=None, time_source="unknown")
                self.finish(td, completed)
                actual = tool.status(td)["latest_change"]["change"]
                self.assertEqual(actual["result_revision"], "unknown")
                self.assertIsNone(actual["occurred_at"])

    def test_completion_and_direct_report_reject_all_immutable_identity_changes(self):
        changes = {"function": "other task", "before": "invented baseline", "rationale": "other intent",
                   "source": "invented source", "base_revision": "c" * 40,
                   "parent_event_id": "invented parent"}
        for reporting in (False, True):
            for field, value in changes.items():
                with self.subTest(reporting=reporting, field=field), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                    start = self.begin(td, reporting)
                    altered = report(start)
                    altered["change"][field] = value
                    path = write(Path(td) / "altered.json", altered)
                    with self.assertRaisesRegex(ValueError, "immutable workflow start facts"):
                        tool.finish_workflow(td, path)
                    if reporting:
                        with self.assertRaisesRegex(ValueError, "immutable workflow start facts"):
                            tool.record_report(td, path)
                        self.assertEqual(self.ledger(td)["reports"], [])
                    self.assertEqual(tool.status(td)["active_workflow"]["change"], start["change"])

    def test_direct_report_accepts_outcome_evolution_with_observed_start(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            start = self.begin(td, True)
            completed = report(start)
            tool.record_report(td, write(Path(td) / "report.json", completed))
            self.assertEqual(tool.status(td)["latest_change"]["change"], completed["change"])
            self.assertEqual(self.ledger(td)["reports"][0]["start_change"], start["change"])

    def test_disabled_direct_report_rejects_before_parsing_or_reading_input(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            tool.ensure(td)
            for path in (Path(td) / "missing.json", write(Path(td) / "invalid.json", {})):
                with self.subTest(path=path.name):
                    with self.assertRaisesRegex(ValueError, "field-test reporting is disabled"):
                        tool.record_report(td, path)

    def test_tool_owned_start_and_recovery_fields_cannot_be_forged(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                forged = report(start)
                forged["start_change"] = copy.deepcopy(start["change"])
                forged["start_change"]["before"] = "invented start"
                with self.assertRaisesRegex(ValueError, "tool-owned"):
                    self.finish(td, forged)
                if reporting:
                    with self.assertRaisesRegex(ValueError, "tool-owned"):
                        tool.record_report(td, write(Path(td) / "forged.json", forged))
                for field in ("last_outcome", "outcome_receipts", "observed_at", "start_change"):
                    forged_start = dict(start, **{field: {}})
                    with self.assertRaisesRegex(ValueError, "tool-owned"):
                        tool.begin_workflow(td, write(Path(td) / "forged-start.json", forged_start))

    def test_partial_blocked_and_complete_keep_current_recovery_evidence(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                partial = report(start, "partial")
                partial["change"]["after"] = "implementation present; validation incomplete"
                partial["validation"] = ["focused check failed at synthetic fixture"]
                partial["handoff"] = "created"
                self.finish(td, partial)
                state = tool.status(td)
                self.assertEqual(state["active_workflow"]["change"], start["change"])
                self.assertEqual(state["active_workflow"]["last_outcome"]["validation"], partial["validation"])
                self.assertIsNone(state["latest_change"])
                self.assertTrue(tool.begin_workflow(td, Path(td) / "outcomes-start.json")["idempotent"])
                blocked = report(start, "blocked")
                blocked["change"]["after"] = "waiting for external fixture input"
                blocked["validation"] = ["external fixture unavailable"]
                self.finish(td, blocked)
                before_retry = tool.status(td)["active_workflow"]
                self.assertTrue(self.finish(td, partial)["idempotent"])
                self.assertEqual(tool.status(td)["active_workflow"], before_retry)
                conflict = copy.deepcopy(partial)
                conflict["validation"] = ["conflicting partial check"]
                with self.assertRaisesRegex(ValueError, "conflicting"):
                    self.finish(td, conflict)
                self.finish(td, report(start))
                state = tool.status(td)
                self.assertIsNone(state["active_workflow"])
                self.assertEqual(state["latest_change"]["start_change"], start["change"])
                if reporting:
                    self.assertEqual([x["status"] for x in self.ledger(td)["reports"]],
                                     ["partial", "blocked", "complete"])

    def test_completed_retry_conflicts_fail_and_old_retries_do_not_rewind_newer_work(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting, "first")
                first = report(start)
                self.finish(td, first)
                altered = copy.deepcopy(first)
                altered["change"]["result_revision"] = "d" * 40
                with self.assertRaisesRegex(ValueError, "conflicting"):
                    self.finish(td, altered)
                parent = tool.status(td)["latest_change"]["event_id"]
                second_start = self.begin(td, reporting, "second", parent)
                active = tool.status(td)["active_workflow"]
                self.assertTrue(self.finish(td, first)["idempotent"])
                self.assertEqual(tool.status(td)["active_workflow"], active)
                self.finish(td, report(second_start))
                latest = tool.status(td)["latest_change"]
                self.assertTrue(self.finish(td, first)["idempotent"])
                self.assertEqual(tool.status(td)["latest_change"], latest)

    def test_completed_workflow_identity_cannot_be_reopened(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                self.finish(td, report(start))
                with self.assertRaisesRegex(ValueError, "already completed"):
                    tool.begin_workflow(td, Path(td) / "outcomes-start.json")

    def test_old_finish_retry_survives_reporting_opt_in_while_new_work_is_active(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            first_start = self.begin(td, False, "first")
            first = report(first_start)
            self.finish(td, first)
            parent = tool.status(td)["latest_change"]["event_id"]
            second_start = self.begin(td, False, "second", parent)
            self.assertTrue(self.finish(td, first)["idempotent"])
            tool.ensure(td, field_test_reporting=True)
            before_retry = tool.status(td)
            self.assertTrue(self.finish(td, first)["idempotent"])
            self.assertEqual(tool.status(td), before_retry)
            self.assertEqual(self.ledger(td)["reports"], [])
            self.assertEqual(self.ledger(td)["next_sequence"], 2)
            self.assertEqual(self.finish(td, report(second_start))["sequence"], 2)

    def test_begin_rejects_retained_ledger_identity_older_than_bounded_checkpoints(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            parent = None
            for workflow in ("first", "second", "third"):
                start = self.begin(td, True, workflow, parent)
                self.finish(td, report(start))
                parent = tool.status(td)["latest_change"]["event_id"]
            repeated = dict(workflow_id="first", change=change())
            repeated["change"]["parent_event_id"] = parent
            before = tool.status(td)
            with self.assertRaisesRegex(ValueError, "already recorded in this epoch"):
                tool.begin_workflow(td, write(Path(td) / "repeat.json", repeated))
            self.assertEqual(tool.status(td), before)

    def test_begin_rejects_direct_partial_or_blocked_ledger_identity(self):
        for status in ("partial", "blocked"):
            with self.subTest(status=status), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                tool.ensure(td, field_test_reporting=True)
                start = dict(workflow_id="direct-record", change=change())
                tool.record_report(td, write(Path(td) / "report.json", report(start, status)))
                self.assertIsNone(tool.status(td)["active_workflow"])
                with self.assertRaisesRegex(ValueError, "already recorded in this epoch"):
                    tool.begin_workflow(td, write(Path(td) / "start.json", start))

    def test_completion_recovers_exactly_once_after_ledger_write_before_binding_update(self):
        for status in ("partial", "complete"):
            with self.subTest(status=status), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, True)
                completed = report(start, status)
                with patch.object(tool, "_reconcile_completion", side_effect=OSError("simulated crash")):
                    with self.assertRaises(OSError):
                        self.finish(td, completed)
                self.assertEqual(len(self.ledger(td)["reports"]), 1)
                self.assertIsNotNone(tool.status(td)["active_workflow"])
                self.assertTrue(self.finish(td, completed)["idempotent"])
                self.assertEqual(len(self.ledger(td)["reports"]), 1)
                state = tool.status(td)
                if status == "complete":
                    self.assertIsNone(state["active_workflow"])
                    self.assertEqual(state["latest_change"]["change"], completed["change"])
                else:
                    self.assertEqual(state["active_workflow"]["last_outcome"]["change"], completed["change"])

    def test_no_report_completion_retries_after_interruption_before_atomic_binding_write(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            start = self.begin(td, False)
            completed = report(start)
            original = tool.write_json_atomic

            def fail_completion(path, value):
                if isinstance(value, dict) and "latest_change" in value:
                    raise OSError("simulated interruption before atomic binding replacement")
                return original(path, value)

            with patch.object(tool, "write_json_atomic", side_effect=fail_completion):
                with self.assertRaises(OSError):
                    self.finish(td, completed)
            self.assertIsNotNone(tool.status(td)["active_workflow"])
            self.finish(td, completed)
            self.assertEqual(tool.status(td)["latest_change"]["sequence"], 1)
            self.assertTrue(self.finish(td, completed)["idempotent"])

    def test_finish_reads_standard_input_once_in_both_modes(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                with patch.object(tool.sys, "stdin", io.StringIO(json.dumps(report(start)))):
                    tool.finish_workflow(td, "-")
                self.assertIsNone(tool.status(td)["active_workflow"])

    def test_multiple_partial_stages_are_ordered_idempotent_and_preserve_history(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                legacy = report(start, "partial")
                self.finish(td, legacy)
                stage = dict(report(start, "partial"), checkpoint_id="verified-stage-2")
                stage["change"]["after"] = "new observed stage, still unfinished"
                self.finish(td, stage)
                state = tool.status(td)
                self.assertEqual(state["current_outcome"]["sequence"], 2)
                self.assertEqual(state["active_workflow"]["change"], start["change"])
                self.assertIsNone(state["latest_change"])
                self.assertTrue(self.finish(td, legacy)["idempotent"])
                self.assertTrue(self.finish(td, stage)["idempotent"])
                self.assertEqual(tool.status(td), state)
                conflict = dict(stage, validation=["different evidence under same stage"])
                with self.assertRaisesRegex(ValueError, "conflicting"):
                    self.finish(td, conflict)
                self.finish(td, report(start))
                self.assertEqual(tool.status(td)["latest_change"]["sequence"], 3)
                if reporting:
                    self.assertEqual([x["sequence"] for x in self.ledger(td)["reports"]], [1, 2, 3])

    def test_current_authority_detects_stale_state_and_is_reconciled_without_mirroring(self):
        import hashlib
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                current = Path(td) / "current.json"
                write(current, {"delivery": "unfinished", "observed": "first"})
                ref = lambda: dict(path="current.json", sha256=hashlib.sha256(current.read_bytes()).hexdigest())
                first = dict(report(start, "partial"), checkpoint_id="first", current_state=ref())
                self.finish(td, first)
                self.assertTrue(tool.status(td)["ok"])
                write(current, {"delivery": "unfinished", "observed": "second"})
                self.assertEqual(tool.status(td)["reason"], "current-state-drift")
                with self.assertRaisesRegex(ValueError, "current_state changed"):
                    self.finish(td, dict(first, checkpoint_id="second"))
                second = dict(report(start, "partial"), checkpoint_id="second", current_state=ref())
                self.finish(td, second)
                self.assertTrue(self.finish(td, first)["idempotent"])
                tool.ensure(td)
                state = tool.status(td)
                self.assertTrue(state["ok"])
                self.assertEqual(state["current_state"], second["current_state"])
                self.assertEqual(state["current_outcome"]["checkpoint_id"], "second")
                self.assertNotIn("delivery", state)  # No copied application truth.
                current.unlink()
                self.assertFalse(tool.status(td)["ok"])

    def test_current_authority_rejects_unsafe_paths_invalid_json_and_self_reference(self):
        import hashlib
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            start = self.begin(td, False)
            for name, raw in [("invalid.json", b'[]'), ("duplicate.json", b'{"a":1,"a":2}')]:
                (Path(td) / name).write_bytes(raw)
                ref = dict(path=name, sha256=hashlib.sha256(raw).hexdigest())
                with self.assertRaises(ValueError):
                    self.finish(td, dict(report(start, "partial"), checkpoint_id="invalid", current_state=ref))
            for name in ("../outside.json", "C:/outside.json", ".governance/upg.json", ".env"):
                with self.assertRaises(ValueError):
                    self.finish(td, dict(report(start, "partial"), checkpoint_id="invalid",
                                         current_state=dict(path=name, sha256="a" * 64)))
            self.assertNotIn("last_outcome", tool.status(td)["active_workflow"])

    def test_checkpoint_identity_does_not_allow_repeated_completion(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                with self.assertRaisesRegex(ValueError, "completion identity remains unique"):
                    self.finish(td, dict(report(start), checkpoint_id="bypass"))

    def test_reporting_opt_in_after_partial_keeps_monotonic_sequence(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            start = self.begin(td, False)
            self.finish(td, dict(report(start, "partial"), checkpoint_id="one"))
            second = dict(report(start, "partial"), checkpoint_id="two")
            self.finish(td, second)
            tool.ensure(td, field_test_reporting=True)
            self.assertEqual(self.ledger(td)["next_sequence"], 3)
            self.assertTrue(self.finish(td, second)["idempotent"])
            self.assertEqual(self.ledger(td)["reports"], [])
            self.finish(td, report(start))
            self.assertEqual(tool.status(td)["latest_change"]["sequence"], 3)

    def test_stage_reference_recovers_after_ledger_commit_before_binding_write(self):
        import hashlib
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            start = self.begin(td, True)
            path = write(Path(td) / "current.json", {"actual": "partial"})
            stage = dict(report(start, "partial"), checkpoint_id="interrupted",
                         current_state=dict(path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            with patch.object(tool, "_reconcile_completion", side_effect=OSError("simulated crash")):
                with self.assertRaises(OSError):
                    self.finish(td, stage)
            self.assertEqual(tool.status(td)["reason"], "checkpoint-unreconciled")
            self.assertTrue(self.finish(td, stage)["idempotent"])
            self.assertEqual(len(self.ledger(td)["reports"]), 1)
            self.assertEqual(tool.status(td)["current_state"], stage["current_state"])

    def test_known_outcome_time_requires_observed_source(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                completed = report(start)
                completed["change"]["time_source"] = "unknown"
                with self.assertRaisesRegex(ValueError, "known occurrence time"):
                    self.finish(td, completed)
                self.assertIsNotNone(tool.status(td)["active_workflow"])

    def test_start_metadata_is_scanned_before_binding_write(self):
        with tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
            tool.ensure(td)
            start = dict(workflow_id="private-start", change=change())
            start["change"]["after"] = "password=" + "synthetic-value"
            with self.assertRaisesRegex(ValueError, "credential or secret"):
                tool.begin_workflow(td, write(Path(td) / "start.json", start))
            self.assertIsNone(tool.status(td)["active_workflow"])

    def test_preserved_legacy_start_is_scanned_before_completion_write(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting), tempfile.TemporaryDirectory(prefix="completion-test-", dir=ROOT) as td:
                start = self.begin(td, reporting)
                binding_path = Path(td) / ".governance/upg.json"
                binding = json.loads(binding_path.read_text(encoding="utf-8"))
                # Model a start recorded by an older runtime without its privacy
                # check. An evolved safe outcome must not copy the old secret.
                binding["active_workflow"]["change"]["after"] = "password=" + "synthetic-value"
                write(binding_path, binding)
                with self.assertRaisesRegex(ValueError, "credential or secret"):
                    self.finish(td, report(start))
                self.assertIsNone(tool.status(td)["latest_change"])
                if reporting:
                    self.assertEqual(self.ledger(td)["reports"], [])


if __name__ == "__main__":
    unittest.main()
