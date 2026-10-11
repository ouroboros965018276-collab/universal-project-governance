"""Offline integration/safety checks; fixtures are not learning evidence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import contextlib
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SUPPORTED = sys.version_info >= (3, 10)
if SUPPORTED:
    from evolution.contracts import Budget, BudgetExceeded
    from evolution.source_bridge import SourceBridge, SourceBridgeError
    from evolution.skillopt_adapter import (
        BudgetedBackend, Patch, RolloutResult, SkillOptLearner,
        UPGEnvAdapter, _upstream, fixture_backend,
    )


def model_fixture():
    return {
        "hot_path": [{"id": "NEVER_WEAKEN", "statement": "Protect canonical truth."}],
        "risk_model": {"threshold": 7},
        "policies": [
            {"id": "A", "closure": "Validate affected behavior.", "requires": ["B"],
             "triggers": {"operations": ["edit"]}},
            {"id": "B", "statement": "Record observed evidence.", "requires": [],
             "triggers": {"operations": ["release"]}},
        ],
    }


@unittest.skipUnless(SUPPORTED, "optional offline evolution optimizer requires Python 3.10+")
class SourceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.model = model_fixture()
        self.bridge = SourceBridge(self.model)

    def patch(self, **edit):
        return self.bridge.bind_patch({"edits": [dict(op="replace", target="Validate affected behavior.",
                                                       content="Validate behavior with observable evidence.", **edit)]})

    def test_view_exposes_only_allowlisted_policy_prose(self):
        view = self.bridge.export_view()
        self.assertIn("policies/A/closure sha256=", view)
        self.assertIn("policies/B/statement sha256=", view)
        self.assertNotIn("Protect canonical truth.", view)
        self.assertNotIn('"threshold"', view)

    def test_application_preserves_source_and_structural_constraints(self):
        result = self.bridge.apply(self.patch())
        self.assertEqual(self.model, model_fixture())
        self.assertEqual(result["hot_path"], self.model["hot_path"])
        self.assertEqual(result["risk_model"], self.model["risk_model"])
        self.assertEqual(result["policies"][0]["requires"], ["B"])
        self.assertEqual(result["policies"][0]["triggers"], {"operations": ["edit"]})
        self.assertEqual(result["policies"][0]["closure"], "Validate behavior with observable evidence.")

    def test_stale_model_or_field_hash_is_rejected(self):
        patch = self.patch().to_dict()
        changed = copy.deepcopy(self.model)
        changed["version"] = "different"
        with self.assertRaises(SourceBridgeError):
            SourceBridge(changed).apply(patch)
        patch["edits"][0]["update_origin"] = "0" * 64
        with self.assertRaises(SourceBridgeError):
            self.bridge.apply(patch)

    def test_unbound_patch_cannot_write_source(self):
        with self.assertRaises(SourceBridgeError):
            self.bridge.apply({"edits": [{"op": "append", "content": "Unbound."}]})

    def test_structural_paths_and_extra_json_fields_are_rejected(self):
        for path in ("hot_path/NEVER_WEAKEN/statement", "policies/A/requires", "risk_model/threshold"):
            with self.subTest(path=path), self.assertRaises(SourceBridgeError):
                self.patch(update_target=path)
        with self.assertRaises(SourceBridgeError):
            self.bridge.bind_patch({"edits": [], "requires": []})

    def test_duplicate_rule_identity_is_rejected(self):
        self.model["policies"][1]["id"] = "A"
        with self.assertRaises(SourceBridgeError):
            SourceBridge(self.model)

    def test_missing_insert_after_rejects_whole_patch(self):
        first = self.patch().to_dict()
        original = self.bridge.model
        bad = copy.deepcopy(first["edits"][0])
        bad.update(op="insert_after", target="nonexistent", content="Must never append.")
        first["edits"].append(bad)
        with self.assertRaises(SourceBridgeError):
            self.bridge.apply(first)
        self.assertEqual(self.bridge.model, original)
        self.assertEqual(self.model, model_fixture())

    def test_duplicate_insert_after_anchor_is_rejected(self):
        self.model["policies"][0]["closure"] = "Repeated. Repeated."
        bridge = SourceBridge(self.model)
        with self.assertRaises(SourceBridgeError):
            bridge.bind_patch({"edits": [{"op": "insert_after", "target": "Repeated.",
                                           "content": "Unsafe ambiguous insertion.",
                                           "update_target": "policies/A/closure"}]})

    def test_sequential_patch_can_anchor_an_earlier_edit(self):
        patch = self.patch().to_dict()
        second = copy.deepcopy(patch["edits"][0])
        second.update(op="insert_after", target="observable evidence.", content="Record the result.")
        patch["edits"].append(second)
        result = self.bridge.apply(patch)
        self.assertIn("Record the result.", result["policies"][0]["closure"])

    def test_cross_field_ambiguous_anchor_and_empty_policy_are_rejected(self):
        self.model["policies"][1]["statement"] = self.model["policies"][0]["closure"]
        bridge = SourceBridge(self.model)
        with self.assertRaises(SourceBridgeError):
            bridge.bind_patch({"edits": [{"op": "delete", "target": "Validate affected behavior."}]})
        with self.assertRaises(SourceBridgeError):
            self.bridge.bind_patch({"edits": [{"op": "delete", "target": "Validate affected behavior."}]})


@unittest.skipUnless(SUPPORTED, "optional offline evolution optimizer requires Python 3.10+")
class SkillOptIntegrationTests(unittest.TestCase):
    def test_all_vendored_source_hashes_and_no_local_modifications(self):
        vendor = ROOT / "third_party" / "skillopt"
        manifest = json.loads((vendor / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["commit"], "343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c")
        self.assertEqual(manifest["local_modifications"], [])
        for rel, expected in manifest["retained_files_sha256"].items():
            self.assertEqual(hashlib.sha256((vendor / rel).read_bytes()).hexdigest(), expected, rel)
        actual = {p.relative_to(vendor).as_posix() for p in (vendor / "skillopt").rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts}
        recorded = {rel for rel in manifest["retained_files_sha256"] if rel.startswith("skillopt/")}
        self.assertEqual(actual, recorded)

    def test_real_upstream_stages_are_loaded_without_provider_router(self):
        for name in ("gradient.reflect", "gradient.aggregate", "optimizer.clip", "optimizer.skill",
                     "optimizer.slow_update", "optimizer.meta_skill"):
            module = _upstream(name)
            self.assertIn(str(ROOT / "third_party" / "skillopt"), module.__file__)
        self.assertEqual(Patch.__module__, "_upg_skillopt_pinned.types")
        self.assertNotIn("_upg_skillopt_pinned.model.azure_openai", sys.modules)

    def test_upstream_reflect_aggregate_and_clip_calls_share_budget(self):
        bridge = SourceBridge(model_fixture())
        budget = Budget(max_calls=4)
        calls = []
        edit_a = {"op": "replace", "target": "Validate affected behavior.", "content": "Verify observed behavior."}
        edit_b = {"op": "replace", "target": "Record observed evidence.", "content": "Record the actual result."}

        def backend(**kwargs):
            calls.append(kwargs)
            stage = kwargs["stage"]
            if stage == "analyst":
                item = edit_a if len(calls) == 1 else edit_b
                result = {"patch": {"edits": [item], "reasoning": "synthetic fixture"}}
            elif stage == "merge":
                result = {"edits": [edit_a, edit_b]}
            else:
                result = {"selected_indices": [1]}
            return json.dumps(result), {"total_tokens": 0, "measurement": "synthetic", "fixture": True}

        learner = SkillOptLearner(backend, budget, bridge, edit_budget=1)
        patch = learner.learn([RolloutResult(id="failed", hard=0, soft=0),
                               RolloutResult(id="passed", hard=1, soft=1)])
        self.assertEqual([row["stage"] for row in calls], ["analyst", "analyst", "merge", "ranking"])
        self.assertEqual(budget.calls, 4)
        self.assertEqual(len(patch.edits), 1)
        self.assertEqual(bridge.apply(patch)["policies"][1]["statement"], "Record the actual result.")
        self.assertTrue(all("retries" not in call for call in calls))

    def test_failed_attempt_and_retry_count_against_shared_call_limit(self):
        class KnownFailure(RuntimeError):
            usage = {"total_tokens": 2}
        budget = Budget(max_calls=2)
        attempts = []
        def backend(**kwargs):
            attempts.append(kwargs)
            raise KnownFailure("synthetic fixture failure")
        wrapped = BudgetedBackend(backend, budget, max_retries=3)
        with self.assertRaises(BudgetExceeded):
            wrapped(system="s", user="u", retries=100)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(budget.calls, 2)
        self.assertEqual(budget.total_tokens, 4)
        self.assertEqual(len(budget.records), 2)

    def test_unknown_usage_stops_further_dispatch(self):
        budget = Budget(max_calls=10)
        calls = []
        def backend(**kwargs):
            calls.append(kwargs)
            return '{"patch":{"edits":[]}}', None
        wrapped = BudgetedBackend(backend, budget)
        wrapped(system="s", user="u")
        with self.assertRaises(BudgetExceeded):
            wrapped(system="s", user="u")
        self.assertEqual(len(calls), 1)
        self.assertTrue(budget.unknown_usage)

    def test_completion_cap_respects_remaining_measured_budget(self):
        budget = Budget(max_calls=2, max_total_tokens=11)
        caps = []
        def backend(**kwargs):
            caps.append(kwargs["max_completion_tokens"])
            return "{}", {"total_tokens": min(7, kwargs["max_completion_tokens"])}
        wrapped = BudgetedBackend(backend, budget)
        wrapped(system="s", user="u", max_completion_tokens=1000)
        wrapped(system="s", user="u", max_completion_tokens=1000)
        self.assertEqual(caps, [11, 4])
        self.assertEqual(budget.total_tokens, 11)

    def test_upstream_error_catch_cannot_hide_budget_exhaustion(self):
        learner = SkillOptLearner(fixture_backend, Budget(max_calls=1), SourceBridge(model_fixture()))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(BudgetExceeded):
            learner.learn([RolloutResult(id="failed", hard=0, soft=0),
                           RolloutResult(id="passed", hard=1, soft=1)])

    def test_synthetic_fixture_is_explicit_and_cost_metadata_survives(self):
        budget = Budget(max_calls=8)
        bridge = SourceBridge(model_fixture())
        learner = SkillOptLearner(fixture_backend, budget, bridge)
        patch = learner.learn([RolloutResult(id="../untrusted-id", hard=0, soft=0,
                                            task_description="实际任务观察")])
        self.assertEqual(len(patch.edits), 1)
        self.assertTrue(budget.records[0]["fixture"])
        self.assertEqual(budget.records[0]["measurement"], "synthetic")
        self.assertEqual(budget.total_tokens, 0)

    def test_longitudinal_memory_reuses_upstream_without_policy_write(self):
        bridge = SourceBridge(model_fixture())
        learner = SkillOptLearner(fixture_backend, Budget(max_calls=4), bridge)
        result = learner.update_memory([RolloutResult(id="a", hard=0, soft=0)],
                                       [RolloutResult(id="a", hard=1, soft=1)],
                                       previous_view=bridge.export_view())
        self.assertIn("slow_update", result)
        self.assertTrue(learner.meta_skill_context)
        self.assertEqual(bridge.model, model_fixture())
        with self.assertRaises(ValueError):
            learner.update_memory([RolloutResult(id="a", hard=0, soft=0)],
                                  [RolloutResult(id="b", hard=1, soft=1)], previous_view="previous")

    def test_environment_invokes_supplied_task_evaluator(self):
        bridge = SourceBridge(model_fixture())
        calls = []
        def evaluate(task, model):
            calls.append((task, model))
            return RolloutResult(id=task["id"], hard=1, soft=0.7,
                                 predicted_answer="actual evaluator answer")
        adapter = UPGEnvAdapter(evaluate, [{"id": "task-a", "task_type": "governance"}], bridge)
        rows = adapter.rollout(adapter.build_train_env(1, 0), bridge.export_view(), "unused")
        self.assertEqual(len(calls), 1)
        self.assertEqual(rows[0]["predicted_answer"], "actual evaluator answer")
        self.assertEqual(rows[0]["soft"], 0.7)
        with self.assertRaises(ValueError):
            adapter.build_eval_env(1, "holdout", 0)


if __name__ == "__main__":
    unittest.main()
