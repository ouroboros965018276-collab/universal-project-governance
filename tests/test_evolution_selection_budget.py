"""Selection and native-receipt accounting contracts; no empirical claims."""
import contextlib
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SUPPORTED = sys.version_info >= (3, 10)
ROOT = Path(__file__).resolve().parents[1]
if SUPPORTED:
    from evolution import controller
    from evolution.contracts import Budget
    from evolution.evaluator import evaluate
    from evolution.skillopt_adapter import BudgetedBackend


@unittest.skipUnless(SUPPORTED, "optional offline evolution requires Python 3.10+")
class SelectionBudgetTests(unittest.TestCase):
    def protocol(self, candidates=2, calls=40):
        return {"schema_version": 1, "seed": 1729, "model": "synthetic-unit-model",
                "budget": {"model_calls": calls, "tokens": 100000, "wall_seconds": 120, "candidates": candidates},
                "search": {"iterations": 1, "population": 4, "retries": 0},
                "tasks": {"training": [{"id": "train"}], "selection": [{"id": "selection"}],
                          "final": [{"id": "untouched-final"}]}}

    @contextlib.contextmanager
    def engine(self):
        with patch.object(controller, "validate_candidate", return_value={"ok": True, "errors": [], "context_bytes": 1000}), \
             patch.object(controller, "source_hash", return_value="unit-source"), \
             patch.object(controller, "engine_identity", return_value="unit-engine"):
            yield

    def measured(self, requests):
        def runner(request):
            requests.append(copy.deepcopy(request))
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 7}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        return runner

    def test_candidate_cap_stops_exploration_but_selects_baseline(self):
        requests = []
        def forbidden_backend(**request):
            self.fail("candidate limit must stop learning calls")
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, self.protocol(candidates=1), Path(temporary) / "run.json",
                                        runner=self.measured(requests), backend=forbidden_backend)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["termination_reason"], "candidate-limit")
        self.assertEqual([row["task"]["id"] for row in requests], ["train", "selection"])
        self.assertEqual(run["budget"]["calls"], 2)
        self.assertEqual(run["best_candidate_origin"], "selection")

    def test_partial_population_at_candidate_cap_still_gets_paired_selection(self):
        requests = []
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, self.protocol(candidates=2), Path(temporary) / "run.json",
                                        runner=self.measured(requests), disabled=("skillopt", "annealing", "curvature"))
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["termination_reason"], "candidate-limit")
        self.assertEqual(len(run["candidates"]), 2)
        self.assertEqual(len(run["selection"]), 2)
        self.assertEqual([row["task"]["id"] for row in requests], ["train", "train", "selection", "selection"])

    def test_no_active_operator_still_selects_and_delivers_exact_compiler(self):
        requests = []
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, self.protocol(), Path(temporary) / "run.json",
                                        runner=self.measured(requests), disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "completed")
        self.assertEqual([row["task"]["id"] for row in requests], ["train", "selection"])
        for request in requests:
            self.assertEqual(request["execution_artifact"]["compiler"], (ROOT / "compiler/compile_governance.py").read_bytes().decode("utf-8"))
            self.assertEqual(request["execution_artifact"]["license"], (ROOT / "LICENSE").read_bytes().decode("utf-8"))
            self.assertIsInstance(request["source"], dict)

    def test_model_budget_exhaustion_does_not_claim_selection_completed(self):
        requests = []
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, self.protocol(candidates=1, calls=1), Path(temporary) / "run.json",
                                        runner=self.measured(requests), disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(len(requests), 1)
        self.assertNotIn("selected_candidate_id", run)

    def test_learner_honors_zero_retries(self):
        requests, learning = [], []
        class ChargedError(RuntimeError):
            usage = {"total_tokens": 3}
        def backend(**request):
            learning.append(request)
            raise ChargedError("synthetic charged failure")
        with tempfile.TemporaryDirectory() as temporary, self.engine(), contextlib.redirect_stderr(__import__("io").StringIO()):
            with self.assertRaisesRegex(RuntimeError, "synthetic charged failure"):
                controller.run_search(ROOT, self.protocol(candidates=3), Path(temporary) / "run.json",
                                      runner=self.measured(requests), backend=backend,
                                      disabled=("annealing", "de", "curvature"))
        self.assertEqual(len(learning), 1)

    def test_native_replay_is_not_independent_or_charged_twice(self):
        calls = []
        def runner(request):
            replayed = bool(calls)
            calls.append(request)
            return {"status": "completed", "provider_receipt": {"replayed_from_local_receipt": replayed},
                    "usage": {"total_tokens": 7}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        budget = Budget(max_calls=3)
        options = {"runner_identity": {"id": "unit", "version": "1"}, "source": {"source": "exact"},
                   "candidate_identity": "a" * 64, "budget": budget}
        first = evaluate({}, {"id": "task"}, runner, **options)
        replay = evaluate({}, {"id": "task"}, runner, **options)
        self.assertTrue(first["independent_sample"])
        self.assertFalse(replay["independent_sample"])
        self.assertTrue(replay["replayed_from_local_receipt"])
        self.assertEqual(replay["usage"]["total_tokens"], 7)
        self.assertEqual(replay["charged_usage"]["total_tokens"], 0)
        self.assertEqual(replay["charged_in_this_run"], 0)
        self.assertFalse(replay["empirical_eligible"])
        self.assertEqual(budget.calls, 1)
        self.assertEqual(budget.total_tokens, 7)
        self.assertEqual(len(budget.records), 1)
        self.assertEqual(Budget.from_state(budget.state()).total_tokens, 7)

    def test_learner_native_replay_releases_reservation(self):
        budget = Budget(max_calls=2)
        def backend(**request):
            return "cached response", {"total_tokens": 7, "native_receipt": {"replayed_from_local_receipt": True}}
        wrapped = BudgetedBackend(backend, budget, max_retries=0)
        response, usage = wrapped(system="unit", user="unit", max_completion_tokens=8)
        self.assertEqual(response, "cached response")
        self.assertEqual(usage["total_tokens"], 7)
        self.assertEqual(budget.calls, 0)
        self.assertEqual(budget.total_tokens, 0)
        self.assertEqual(budget.records, [])

    def test_replay_release_requires_exactly_one_outstanding_reservation(self):
        budget = Budget()
        with self.assertRaisesRegex(ValueError, "outstanding"):
            budget.release_replayed_reservation()
        budget.reserve()
        budget.release_replayed_reservation()
        self.assertEqual(budget.calls, 0)
        with self.assertRaisesRegex(ValueError, "outstanding"):
            budget.release_replayed_reservation()

    def test_final_selection_token_overrun_retains_consumed_observation(self):
        requests = []
        def runner(request):
            requests.append(request)
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 3 if len(requests) == 1 else 8},
                    "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        protocol = self.protocol()
        protocol["budget"]["tokens"] = 10
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, protocol, Path(temporary) / "run.json",
                                        runner=runner, disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(run["budget_overrun"]["tokens"], {"actual": 11, "limit": 10, "excess": 1})
        self.assertEqual(run["budget"]["total_tokens"], 11)
        self.assertEqual(run["budget"]["calls"], 2)
        self.assertEqual(run["selection"][0]["observations"][0]["usage"]["total_tokens"], 8)
        self.assertIsNone(run["pending"])

    def test_final_training_token_overrun_retains_partial_candidate(self):
        def runner(request):
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 11}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        protocol = self.protocol()
        protocol["budget"]["tokens"] = 10
        with tempfile.TemporaryDirectory() as temporary, self.engine():
            run = controller.run_search(ROOT, protocol, Path(temporary) / "run.json",
                                        runner=runner, disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(run["stopped_evaluation"]["observations"][0]["usage"]["total_tokens"], 11)
        self.assertEqual(run["budget"]["total_tokens"], 11)

    def test_final_selection_wall_overrun_is_not_completed(self):
        requests = []
        with patch("evolution.contracts.time.monotonic", return_value=0) as clock:
            def runner(request):
                requests.append(request)
                if len(requests) == 2:
                    clock.return_value = 20
                return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                        "usage": {"total_tokens": 1}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}
            protocol = self.protocol()
            protocol["budget"]["wall_seconds"] = 10
            with tempfile.TemporaryDirectory() as temporary, self.engine(), \
                 patch.object(controller, "Budget", side_effect=lambda **kw: Budget(_start=0, **kw)):
                run = controller.run_search(ROOT, protocol, Path(temporary) / "run.json",
                                            runner=runner, disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(run["budget_overrun"]["wall_seconds"]["actual"], 20)
        self.assertEqual(len(run["selection"][0]["observations"]), 1)

    def test_engineering_baseline_final_wall_overrun_is_not_completed(self):
        with patch("evolution.contracts.time.monotonic", return_value=0) as clock:
            def validation(candidate, repo):
                clock.return_value = 20
                return {"ok": True, "errors": [], "context_bytes": 1000}
            protocol = self.protocol()
            protocol["budget"]["wall_seconds"] = 10
            with tempfile.TemporaryDirectory() as temporary, self.engine(), \
                 patch.object(controller, "Budget", side_effect=lambda **kw: Budget(_start=0, **kw)), \
                 patch.object(controller, "validate_candidate", side_effect=validation):
                run = controller.run_search(ROOT, protocol, Path(temporary) / "run.json", disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(len(run["candidates"]), 1)
        self.assertEqual(run["budget_overrun"]["wall_seconds"]["excess"], 10)

    def test_post_call_cap_check_includes_all_metrics_without_mutation(self):
        budget = Budget(max_calls=2, max_total_tokens=10, max_seconds=5)
        observed = {"calls": 3, "total_tokens": 11, "elapsed_seconds": 6}
        self.assertEqual(set(budget.overruns(observed)), {"model_calls", "tokens", "wall_seconds"})
        self.assertEqual(budget.calls, 0)
        self.assertEqual(budget.overruns({"calls": 2, "total_tokens": 10, "elapsed_seconds": 5}), {})


if __name__ == "__main__":
    unittest.main()
