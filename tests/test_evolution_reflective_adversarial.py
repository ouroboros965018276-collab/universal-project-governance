"""Independent no-model adversarial checks for the native learner boundary."""
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
    from evolution.contracts import Budget, BudgetExceeded
    from evolution.reflective import BudgetedBackend, ReflectiveLearner, RolloutResult
    from evolution.source_bridge import SourceBridge, SourceBridgeError


def model():
    return {"policies": [{"id": "A", "closure": "Observe current facts."},
                         {"id": "B", "statement": "Preserve validation."}]}


@unittest.skipUnless(SUPPORTED, "optional learner requires Python 3.10+")
class ReflectiveAdversarialTests(unittest.TestCase):
    def test_consensus_counts_one_support_per_batch_despite_duplicate_edit_entries(self):
        budget = Budget(max_calls=4); bridge = SourceBridge(model()); captured = []
        first = {"op": "append", "target": "", "content": "Record evidence.", "update_target": "policies/A/closure"}
        other = {"op": "append", "target": "", "content": "Keep scope.", "update_target": "policies/B/statement"}
        def backend(**request):
            if request["stage"] == "analyst":
                answer = {"patch": {"edits": [first] * 5 + [other]}}
            else:
                captured.append(request["user"])
                answer = {"edits": [first]}
            return json.dumps(answer), {"total_tokens": 3}
        learner = ReflectiveLearner(backend, budget, bridge, edit_budget=1, max_retries=0)
        learner.learn([RolloutResult(id="single-observed-batch", hard=0, soft=0)])
        payload = json.JSONDecoder().raw_decode(captured[0][captured[0].index('{"instruction"'):])[0]
        self.assertEqual([proposal["support"] for proposal in payload["proposals"]], [1, 1])
        self.assertEqual(budget.total_tokens, 6)
        self.assertEqual(bridge.model, model())

    def test_memory_pairs_by_unique_id_and_uses_only_supplied_training_rows(self):
        budget = Budget(max_calls=2); captured = []
        def backend(**request):
            captured.append(request["user"])
            key = "slow_update_content" if request["stage"] == "slow_update" else "meta_skill_content"
            return json.dumps({key: "Observed training only."}), {"total_tokens": 4}
        learner = ReflectiveLearner(backend, budget, SourceBridge(model()), max_retries=0)
        before = [RolloutResult(id="first", hard=0, soft=.2), RolloutResult(id="second", hard=1, soft=.8)]
        after = [RolloutResult(id="second", hard=1, soft=.9), RolloutResult(id="first", hard=1, soft=.6)]
        learner.update_memory(before, after, previous_view="exact previous view")
        for user in captured:
            payload = json.JSONDecoder().raw_decode(user[user.index('{"instruction"'):])[0]
            self.assertEqual([(p["before"]["id"], p["after"]["id"]) for p in payload["pairs"]],
                             [("first", "first"), ("second", "second")])
            self.assertEqual([p["after"]["soft"] for p in payload["pairs"]], [.6, .9])
        self.assertEqual(budget.total_tokens, 8)
        self.assertEqual(learner.bridge.model, model())

    def test_memory_second_stage_invalid_json_keeps_both_previous_memories_and_paid_cost(self):
        budget = Budget(max_calls=2)
        def backend(**request):
            response = '{"slow_update_content":"new first memory"}' if request["stage"] == "slow_update" else '{"meta_skill_content":NaN}'
            return response, {"total_tokens": 5}
        learner = ReflectiveLearner(backend, budget, SourceBridge(model()), max_retries=0)
        learner.slow_update_context, learner.meta_skill_context = "old slow", "old meta"
        with self.assertRaises(SourceBridgeError):
            learner.update_memory([RolloutResult(id="a", hard=0, soft=0)],
                                  [RolloutResult(id="a", hard=1, soft=1)], previous_view="old view")
        self.assertEqual((learner.slow_update_context, learner.meta_skill_context), ("old slow", "old meta"))
        self.assertEqual((budget.calls, budget.total_tokens), (2, 10))
        self.assertEqual(learner.bridge.model, model())

    def test_memory_unknown_first_usage_blocks_second_stage_without_partial_memory_write(self):
        calls = []; budget = Budget(max_calls=8)
        def backend(**request):
            calls.append(request["stage"])
            return '{"slow_update_content":"unadmitted guidance"}', None
        learner = ReflectiveLearner(backend, budget, SourceBridge(model()), max_retries=3)
        learner.slow_update_context, learner.meta_skill_context = "old slow", "old meta"
        with self.assertRaises(BudgetExceeded):
            learner.update_memory([RolloutResult(id="a", hard=0, soft=0)],
                                  [RolloutResult(id="a", hard=1, soft=1)], previous_view="old view")
        self.assertEqual(calls, ["slow_update"])
        self.assertTrue(budget.unknown_usage)
        self.assertEqual((learner.slow_update_context, learner.meta_skill_context), ("old slow", "old meta"))

    def test_failed_unknown_attempt_never_dispatches_wrapper_retry(self):
        calls = []; budget = Budget(max_calls=8)
        def backend(**request):
            calls.append(request)
            raise RuntimeError("no completed usage")
        wrapped = BudgetedBackend(backend, budget, max_retries=5)
        with self.assertRaises(BudgetExceeded):
            wrapped(system="fixed", user="training only")
        self.assertEqual(len(calls), 1)
        self.assertTrue(budget.unknown_usage)
        self.assertEqual(budget.records[0]["error"], "RuntimeError")

    def test_merge_cannot_inject_structural_edit_and_all_completed_calls_stay_charged(self):
        calls = []; budget = Budget(max_calls=4); bridge = SourceBridge(model())
        def backend(**request):
            calls.append(request["stage"])
            if request["stage"] == "analyst":
                content = "Record evidence." if len(calls) == 1 else "Verify observable state."
                answer = {"patch": {"edits": [{"op": "append", "content": content, "update_target": "policies/A/closure"}]}}
            else:
                answer = {"edits": [{"op": "append", "content": "Weakened", "update_target": "risk_model/threshold"}]}
            return json.dumps(answer), {"total_tokens": 2}
        learner = ReflectiveLearner(backend, budget, bridge, max_retries=0)
        with self.assertRaises(SourceBridgeError):
            learner.learn([RolloutResult(id="failed", hard=0, soft=0), RolloutResult(id="passed", hard=1, soft=1)])
        self.assertEqual(calls, ["analyst", "analyst", "merge"])
        self.assertEqual((budget.calls, budget.total_tokens), (3, 6))
        self.assertEqual(bridge.model, model())

    def test_ranking_subset_cannot_use_anchor_created_by_an_unselected_edit(self):
        budget = Budget(max_calls=3); bridge = SourceBridge(model())
        first = {"op": "replace", "target": "Observe current facts.", "content": "Intermediate anchor.", "update_target": "policies/A/closure"}
        second = {"op": "replace", "target": "Intermediate anchor.", "content": "Final evidence.", "update_target": "policies/A/closure"}
        def backend(**request):
            stage = request["stage"]
            answer = {"patch": {"edits": [first, second]}} if stage == "analyst" else (
                {"edits": [first, second]} if stage == "merge" else {"selected_indices": [1]})
            return json.dumps(answer), {"total_tokens": 2}
        learner = ReflectiveLearner(backend, budget, bridge, edit_budget=1, max_retries=0)
        with self.assertRaisesRegex(SourceBridgeError, "exactly once"):
            learner.learn([RolloutResult(id="training", hard=0, soft=0)])
        self.assertEqual((budget.calls, budget.total_tokens), (3, 6))
        self.assertEqual(bridge.model, model())

    def test_controller_patch_trace_is_snapshot_before_future_memory_requests(self):
        protocol = {"seed": 1729, "budget": {"model_calls": 20, "tokens": 100000, "wall_seconds": 120, "candidates": 4},
                    "search": {"iterations": 1, "population": 4, "retries": 0}}
        with tempfile.TemporaryDirectory(dir=ROOT/"eval-workspaces", prefix="reflective-chronology-") as temporary, \
                patch.object(controller, "validate_candidate", return_value={"ok": True, "errors": [], "context_bytes": 1000}), \
                patch.object(controller, "source_hash", return_value="synthetic-frozen-source"), \
                patch.object(controller, "engine_identity", return_value="synthetic-frozen-engine"):
            run = controller.run_search(ROOT, protocol, Path(temporary)/"run.json", disabled=("annealing", "de", "curvature"))
        event = next(row for row in run["events"] if row["kind"] == "patch")
        self.assertEqual(event["trace"]["model_stages"], ["analyst"])
        self.assertTrue(any(row["kind"] == "optimizer-memory" for row in run["events"]))


if __name__ == "__main__":
    unittest.main()
