"""Paired development evidence cannot hide quality failures or reuse samples."""
import unittest
import sys
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

if sys.version_info >= (3, 10):
    from evolution.paired import collect, summarize
    from evolution import paired

ROOT = Path(__file__).resolve().parents[1]
CALLS = []


def measured_fixture(request):
    CALLS.append(request)
    return {"status": "completed", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "provider_receipt": {"id": "synthetic-" + str(len(CALLS))},
            "outcome": {"hard": 1, "soft": 1, "loss": 2}}


@unittest.skipIf(sys.version_info < (3, 10), "optional optimizer requires Python 3.10+")
class PairedSummaryTests(unittest.TestCase):
    def test_last_completed_call_cannot_hide_actual_budget_overrun(self):
        baseline = {"engineering": "PASS", "source": {"tiny": "exact historical"},
                    "model": {}, "execution_artifact": {"compiler": "pinned", "license": "pinned"}}
        protocol = {"tasks": {"final": [{"id": "final-only", "family": "synthetic"}]},
                    "baseline": {"latest_revision": "0" * 40}, "paired_budget": {
                    "model_calls": 2, "tokens": 3, "wall_seconds": 60},
                    "development_scope": {"final_order_seed": 18012}, "model": "synthetic", "runner_config": {}}
        CALLS.clear()
        with tempfile.TemporaryDirectory() as directory, patch.object(paired, "_baseline", return_value=baseline), \
                patch.object(paired, "validate_candidate", return_value={"ok": True}), \
                patch.object(paired, "engine_identity", return_value="synthetic-engine"):
            output = Path(directory) / "paired.json"
            result = collect(ROOT, protocol, output, measured_fixture)
            self.assertEqual(len(CALLS), 2)
            self.assertEqual(result["budget"]["total_tokens"], 4)
            self.assertEqual(len(result["observations"]), 2)
            self.assertEqual(result["status"], "budget-exhausted")
            self.assertEqual(result["actual_budget_overrun"], ["total_tokens"])
            self.assertFalse(summarize(result)["task_quality_pass"])
            collect(ROOT, protocol, output, measured_fixture)
            self.assertEqual(len(CALLS), 2)
            result["pending"] = {"unreconciled": True}
            output.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reconciliation"):
                collect(ROOT, protocol, output, measured_fixture)

    def fixture(self):
        rows = []
        for index in range(8):
            for condition, tokens in (("control", 100), ("treatment", 80)):
                rows.append({"condition": condition, "family": str(index // 2), "observation": {
                    "task_id": str(index), "status": "completed", "independent_sample": True, "cache_hit": False,
                    "usage": {"input_tokens": tokens, "output_tokens": 10, "total_tokens": tokens + 10},
                    "wall_seconds": 2, "outcome": {"hard": 1, "soft": 1, "loss": tokens}}})
        return {"observations": rows, "status": "completed", "budget": {"calls": 16}}

    def test_actual_matched_cost_and_quality(self):
        result = summarize(self.fixture())
        self.assertEqual(result["pairs"], 8)
        self.assertTrue(result["task_quality_pass"])
        self.assertTrue(result["all_samples_new_calls"])
        self.assertEqual(result["metrics"]["input_tokens"]["ratio"], 0.8)
        self.assertEqual(result["metrics"]["input_tokens"]["paired_family_bootstrap_95_interval"], [0.8, 0.8])
        self.assertEqual(result["empirical_status"], "BLOCKED")

    def test_fast_failed_task_never_becomes_quality_success(self):
        run = self.fixture()
        run["observations"][1]["observation"]["outcome"].update(hard=0, soft=0, loss=0)
        self.assertFalse(summarize(run)["task_quality_pass"])
        run = self.fixture()
        run["observations"][1]["observation"].update(independent_sample=False, cache_hit=True)
        self.assertFalse(summarize(run)["all_samples_new_calls"])

    def test_incomplete_and_missing_usage_cannot_make_effectiveness_claim(self):
        run = self.fixture()
        run.update(status="budget-exhausted")
        run["observations"].pop()
        run["observations"][0]["observation"]["usage"]["total_tokens"] = None
        result = summarize(run)
        self.assertFalse(result["task_quality_pass"])
        self.assertEqual(result["pairs"], 7)
        self.assertIsNone(result["metrics"]["total_tokens"])
