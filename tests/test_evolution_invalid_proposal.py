"""Charged malformed proposals are rejected candidates, never fake successes."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SUPPORTED = sys.version_info >= (3, 10)
ROOT = Path(__file__).resolve().parents[1]
if SUPPORTED:
    from evolution import controller
    from evolution.skillopt_adapter import Patch, SkillOptLearner, fixture_backend
    from evolution.source_bridge import SourceBridgeError


@unittest.skipUnless(SUPPORTED, "optional offline evolution requires Python 3.10+")
class InvalidProposalTests(unittest.TestCase):
    def protocol(self):
        return {"schema_version": 1, "seed": 1729, "model": "synthetic-unit-model",
                "budget": {"model_calls": 200, "tokens": 100000, "wall_seconds": 120, "candidates": 128},
                "search": {"iterations": 1, "population": 4, "retries": 0},
                "tasks": {"training": [{"id": "train"}], "selection": [{"id": "selection"}],
                          "final": [{"id": "untouched-final"}]}}

    @contextlib.contextmanager
    def engine(self):
        with patch.object(controller, "validate_candidate", return_value={"ok": True, "errors": [], "context_bytes": 1000}), \
             patch.object(controller, "source_hash", return_value="unit-source"), \
             patch.object(controller, "engine_identity", return_value="unit-engine"):
            yield

    def runner(self, request):
        return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                "usage": {"total_tokens": 7}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}

    def invalid_backend(self, calls, unknown=False):
        def backend(**request):
            calls.append(copy.deepcopy(request))
            if request["stage"] == "analyst":
                response = json.dumps({"patch": {"reasoning": "synthetic invalid target",
                    "edits": [{"op": "insert_after", "target": "## policies/EVIDENCE_AFFECTED/closure sha256=50bcd556cf70d736825b5259318ca36cf55519a30ae94d42359b5c60605b937d",
                               "content": "invalid proposal"}]}})
            else:
                response, _ = fixture_backend(**request)
            return response, None if unknown else {"total_tokens": 3}
        return backend

    def test_charged_invalid_target_is_rejected_and_other_operators_select_safely(self):
        calls = []
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            output = Path(temporary) / "run.json"
            run = controller.run_search(ROOT, self.protocol(), output, runner=self.runner,
                                        backend=self.invalid_backend(calls))
        self.assertEqual(run["status"], "completed")
        rejected = [row for row in run["events"] if row["kind"] == "proposal-rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["error_type"], "SourceBridgeError")
        self.assertIn("one policy field", rejected[0]["reason"])
        self.assertTrue(rejected[0]["budget_receipt_attempts"])
        self.assertEqual(run["operator_counts"]["skillopt"]["attempted"], 1)
        self.assertEqual(run["operator_counts"]["skillopt"]["evaluated"], 0)
        self.assertGreater(run["operator_counts"]["annealing"]["attempted"], 0)
        self.assertGreater(run["operator_counts"]["de"]["attempted"], 0)
        self.assertGreater(run["operator_counts"]["curvature"]["attempted"], 0)
        self.assertTrue(run["selection"])
        self.assertIsNone(run["pending"])
        self.assertTrue(all(row["candidate"]["model"] == run["baseline"]["model"] for row in run["candidates"]))
        self.assertTrue(all(row["loss"] == 1 for row in run["candidates"]))
        self.assertEqual(run["budget"]["total_tokens"], sum(row["usage"]["total_tokens"] for row in run["budget"]["records"]))
        self.assertGreaterEqual(run["budget"]["total_tokens"], 3 * len(calls))

    def test_apply_rejection_preserves_available_trace_and_known_learning_cost(self):
        def malformed_patch(learner, rollouts):
            learner.backend(system="synthetic unit", user="synthetic unit", max_completion_tokens=4)
            learner.last_trace = {"unit_trace": "observed synthetic learn result"}
            return Patch.from_dict({"edits": [], "ranking_details": {"source_hash": "stale"}})
        def backend(**request):
            return "synthetic response", {"total_tokens": 3}
        with tempfile.TemporaryDirectory() as temporary, self.engine(), patch.object(SkillOptLearner, "learn", new=malformed_patch):
            run = controller.run_search(ROOT, self.protocol(), Path(temporary) / "run.json", runner=self.runner,
                                        backend=backend, disabled=("annealing", "de", "curvature"))
        self.assertEqual(run["status"], "completed")
        rejected = next(row for row in run["events"] if row["kind"] == "proposal-rejected")
        self.assertEqual(rejected["trace"], {"unit_trace": "observed synthetic learn result"})
        self.assertEqual(run["budget"]["total_tokens"], 14 + 3 * len([row for row in run["events"] if row["kind"] == "proposal-rejected"]))
        self.assertIsNone(run["pending"])

    def test_unknown_charged_usage_keeps_learning_fence_and_never_selects(self):
        calls = []
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, self.protocol(), Path(temporary) / "run.json", runner=self.runner,
                                        backend=self.invalid_backend(calls, unknown=True),
                                        disabled=("annealing", "de", "curvature"))
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertTrue(run["budget"]["unknown_usage"])
        self.assertEqual(run["pending"]["kind"], "learning")
        self.assertNotIn("selection", run)
        self.assertFalse(any(row["kind"] == "proposal-rejected" for row in run["events"]))

    def test_provider_sourcebridge_typed_error_is_not_swallowed_as_a_proposal(self):
        class ProviderError(SourceBridgeError):
            usage = {"total_tokens": 3}
        def backend(**request):
            raise ProviderError("synthetic provider failure")
        with tempfile.TemporaryDirectory() as temporary, self.engine(), contextlib.redirect_stderr(io.StringIO()):
            output = Path(temporary) / "run.json"
            with self.assertRaisesRegex(ProviderError, "provider failure"):
                controller.run_search(ROOT, self.protocol(), output, runner=self.runner, backend=backend,
                                      disabled=("annealing", "de", "curvature"))
            run = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["pending"]["kind"], "learning")
        self.assertFalse(any(row["kind"] == "proposal-rejected" for row in run["events"]))


if __name__ == "__main__":
    unittest.main()
