"""Controller contracts; injected objective fixtures are not efficacy evidence."""

import contextlib
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
if sys.version_info >= (3, 10):
    from evolution import contracts, controller, evaluator
    from evolution.__main__ import main
    from evolution.contracts import candidate_id, materialize

REQUESTS = []
BACKEND_REQUESTS = []
DISPATCH = []


def measured_runner(request):
    REQUESTS.append(copy.deepcopy(request))
    DISPATCH.append(("runner", request["task"]["id"]))
    return {
        "status": "completed", "provider_receipt": "synthetic-receipt-for-contract-test",
        "usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7,
                  "cached_tokens": 0, "reasoning_tokens": 0, "cost_usd": 0.01},
        "outcome": {"loss": int(candidate_id(request["candidate"])[:6], 16) / 1000000,
                    "hard": 1.0, "soft": 1.0, "task_description": "synthetic contract grader"},
    }


class ChargedFailure(RuntimeError):
    usage = {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7,
             "cached_tokens": 0, "reasoning_tokens": 0, "cost_usd": 0.01}
    provider_receipt = "synthetic-failed-attempt-receipt"


def retrying_runner(request):
    if not REQUESTS:
        REQUESTS.append(copy.deepcopy(request))
        raise ChargedFailure("synthetic first attempt failed")
    return measured_runner(request)


def unknown_usage_runner(request):
    REQUESTS.append(copy.deepcopy(request))
    raise RuntimeError("synthetic missing provider receipt")


def interrupted_runner(request):
    REQUESTS.append(copy.deepcopy(request))
    raise KeyboardInterrupt("synthetic process interruption")


def measured_backend(**request):
    from evolution.skillopt_adapter import fixture_backend
    BACKEND_REQUESTS.append(copy.deepcopy(request))
    DISPATCH.append(("backend", request.get("stage")))
    response, usage = fixture_backend(**request)
    usage.update(input_tokens=2, output_tokens=3, total_tokens=5)
    return response, usage


@unittest.skipIf(sys.version_info < (3, 10), "optional offline optimizer requires Python 3.10+")
class ControllerTests(unittest.TestCase):
    def setUp(self):
        REQUESTS.clear()
        BACKEND_REQUESTS.clear()
        DISPATCH.clear()
        self.temporary = tempfile.TemporaryDirectory(prefix="upg-controller-test-")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "run.json"

    def protocol(self, iterations=2):
        return {
            "schema_version": 1, "seed": 1729, "model": "synthetic-contract-model",
            "budget": {"model_calls": 200, "tokens": 100000, "wall_seconds": 120,
                       "candidates": 128},
            "search": {"iterations": iterations, "population": 6, "retries": 0},
            "tasks": {"training": [{"id": "training-fixture", "grader": "fixture"}],
                      "selection": [{"id": "selection-must-not-leak"}],
                      "final": [{"id": "final-must-not-leak"}]},
        }

    def engineering_validation(self, candidate, repo):
        # Fast injected engineering objective. The real validator is exercised
        # separately for protected-model rejection and compiler/planner ordering.
        return {"ok": True, "errors": [], "context_bytes": 1000,
                "candidate_id": candidate_id(candidate)}

    @contextlib.contextmanager
    def fast_engine(self):
        with patch.object(controller, "validate_candidate", side_effect=self.engineering_validation), \
                patch.object(controller, "source_hash", return_value="fixed-source-for-unit-test"), \
                patch.object(controller, "engine_identity", return_value="fixed-engine-for-unit-test"):
            yield

    def test_cli_run_dispatches_all_four_real_operator_implementations(self):
        spec = Path(self.temporary.name) / "spec.json"
        spec.write_text(json.dumps(self.protocol(iterations=1)), encoding="utf-8")
        with self.fast_engine(), contextlib.redirect_stdout(io.StringIO()):
            status = main(["run", "--spec", str(spec), "--repo", str(ROOT), "--output", str(self.output)])
        self.assertEqual(status, 0)
        run = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(run["status"], "completed")
        for operator in controller.OPERATORS:
            self.assertGreater(run["operator_counts"][operator]["attempted"], 0, operator)
        self.assertTrue(any(event["operator"] == "skillopt" and event["kind"] == "patch"
                            for event in run["events"]))
        self.assertTrue(any(event["operator"] == "curvature" and event["kind"] == "surrogate-diagnostics"
                            for event in run["events"]))
        self.assertTrue(run["budget"]["records"])
        self.assertTrue(all(record["fixture"] for record in run["budget"]["records"]))
        self.assertTrue(run["search_state"]["memory"]["slow_update"])
        self.assertTrue(run["search_state"]["memory"]["meta_skill"])
        self.assertNotIn("memory", run["baseline"]["model"])
        self.assertEqual(run["empirical_status"], "unverified")

    def test_iteration_boundary_resume_has_identical_candidates_search_and_operator_counts(self):
        full_path = self.output.with_name("full.json")
        spec = self.protocol(iterations=3)
        with self.fast_engine(), contextlib.redirect_stdout(io.StringIO()):
            complete = controller.run_search(ROOT, spec, full_path)
            paused = controller.run_search(ROOT, spec, self.output, stop_after=1)
            self.assertEqual(paused["status"], "checkpointed")
            resumed = controller.run_search(ROOT, spec, self.output, resume=True)
        self.assertEqual(complete["status"], "completed")
        self.assertEqual(complete["candidates"], resumed["candidates"])
        self.assertEqual(complete["search_state"], resumed["search_state"])
        self.assertEqual(complete["operator_counts"], resumed["operator_counts"])
        self.assertEqual(complete["best_candidate_id"], resumed["best_candidate_id"])
        self.assertEqual(complete["budget"]["calls"], resumed["budget"]["calls"])
        # Resume legitimately records an additional baseline cache observation;
        # wall-clock measurements and complete event bytes need not be identical.

    def test_compiled_plateaus_are_evaluated_once(self):
        with self.fast_engine(), contextlib.redirect_stdout(io.StringIO()):
            run = controller.run_search(ROOT, self.protocol(), self.output, disabled=("skillopt",))
        identities = [item["id"] for item in run["candidates"]]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertTrue(any(counts["cache_hits"] for counts in run["operator_counts"].values()))
        baseline = run["baseline"]
        near = dict(baseline, theta=[0.50001, 0.50002, 0.50003])
        self.assertEqual(candidate_id(near), candidate_id(baseline))

    def test_real_runner_has_bound_source_and_training_only_receipts(self):
        with self.fast_engine():
            run = controller.run_search(ROOT, self.protocol(iterations=1), self.output,
                                        runner=measured_runner, disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "completed")
        self.assertGreater(len(REQUESTS), 0)
        self.assertEqual({request["task"]["id"] for request in REQUESTS}, {"training-fixture"})
        observations = [observation for item in run["candidates"] for observation in item["observations"]]
        self.assertTrue(all(observation["source_sha256"] for observation in observations))
        self.assertTrue(all(observation["empirical_eligible"] for observation in observations))
        self.assertTrue(all(observation["runner_identity"]["id"] and observation["runner_identity"]["version"]
                            for observation in observations))
        self.assertEqual(run["budget"]["calls"], len(REQUESTS))
        self.assertEqual(run["budget"]["total_tokens"], 7 * len(REQUESTS))
        self.assertEqual(run["empirical_status"], "unverified")

    def test_charged_failed_attempt_is_counted_before_successful_retry(self):
        protocol = self.protocol(iterations=1)
        protocol["search"]["retries"] = 1
        with self.fast_engine():
            run = controller.run_search(ROOT, protocol, self.output, runner=retrying_runner,
                                        disabled=controller.OPERATORS)
        first = run["candidates"][0]["observations"][0]
        self.assertEqual([item["status"] for item in first["attempts"]], ["failed", "completed"])
        self.assertEqual(first["usage"]["total_tokens"], 14)
        self.assertEqual(run["budget"]["calls"], len(REQUESTS))
        self.assertEqual(run["budget"]["total_tokens"], 7 * len(REQUESTS))

    def test_unknown_usage_stops_dispatch_and_cannot_resume(self):
        protocol = self.protocol(iterations=1)
        protocol["search"]["retries"] = 2
        with self.fast_engine():
            run = controller.run_search(ROOT, protocol, self.output, runner=unknown_usage_runner,
                                        disabled=controller.OPERATORS)
            self.assertEqual(len(REQUESTS), 1)
            self.assertTrue(run["budget"]["unknown_usage"])
            self.assertTrue(run["pending"])
            with self.assertRaisesRegex(ValueError, "uncertain|unknown|reconcil"):
                controller.run_search(ROOT, protocol, self.output, runner=unknown_usage_runner,
                                      disabled=controller.OPERATORS, resume=True)
        self.assertEqual(len(REQUESTS), 1)

    def test_abrupt_callback_interruption_leaves_a_resume_fence(self):
        with self.fast_engine():
            with self.assertRaises(KeyboardInterrupt):
                controller.run_search(ROOT, self.protocol(), self.output, runner=interrupted_runner,
                                      disabled=controller.OPERATORS)
            run = json.loads(self.output.read_text(encoding="utf-8"))
            self.assertEqual(run["pending"]["kind"], "task")
            with self.assertRaisesRegex(ValueError, "uncertain|reconcil"):
                controller.run_search(ROOT, self.protocol(), self.output, runner=interrupted_runner,
                                      disabled=controller.OPERATORS, resume=True)
        self.assertEqual(len(REQUESTS), 1)

    def test_zero_call_and_candidate_budgets_stop_before_dispatch(self):
        protocol = self.protocol()
        protocol["budget"]["model_calls"] = 0
        with self.fast_engine():
            run = controller.run_search(ROOT, protocol, self.output, runner=measured_runner,
                                        disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(REQUESTS, [])
        self.assertEqual(run["budget"]["calls"], 0)
        self.assertIsNone(run["pending"])
        protocol = self.protocol()
        protocol["budget"]["candidates"] = 1
        with self.fast_engine():
            run = controller.run_search(ROOT, protocol, self.output.with_name("candidate-limit.json"),
                                        disabled=("skillopt",))
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(len(run["candidates"]), 1)

    def test_hard_invalid_baseline_never_enters_search_or_corrupts_json(self):
        with self.fast_engine(), patch.object(controller, "validate_candidate",
                                               return_value={"ok": False, "errors": ["synthetic hard failure"]}):
            try:
                controller.run_search(ROOT, self.protocol(), self.output)
            except (ValueError, RuntimeError):
                pass
        run = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertIn(run["status"], ("failed", "no-feasible-baseline"))
        self.assertTrue(all(count["attempted"] == 0 for count in run["operator_counts"].values()))
        self.assertIsNone(run["pending"])

    def test_protocol_or_engine_identity_changes_refuse_resume(self):
        with self.fast_engine():
            controller.run_search(ROOT, self.protocol(iterations=1), self.output,
                                  disabled=controller.OPERATORS)
            altered = self.protocol(iterations=1)
            altered["seed"] += 1
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                controller.run_search(ROOT, altered, self.output, disabled=controller.OPERATORS, resume=True)
            with patch.object(controller, "engine_identity", return_value="different-engine"):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    controller.run_search(ROOT, self.protocol(iterations=1), self.output,
                                          disabled=controller.OPERATORS, resume=True)

    def test_protected_policy_removal_and_dependency_edits_are_rejected(self):
        model = json.loads((ROOT / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        deleted = copy.deepcopy(model)
        deleted["policies"].pop()
        changed = copy.deepcopy(model)
        changed["policies"][0]["requires"] = ["nonexistent-rule"]
        for altered in (deleted, changed):
            result = evaluator.validate_candidate({"model": altered, "theta": [0.5] * 3}, ROOT)
            self.assertFalse(result["ok"])
            self.assertTrue(any("protected governance semantics" in error for error in result["errors"]))

    def test_theta_changes_compiled_execution_order_preserving_required_closure(self):
        def load(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        compiler = load("controller_test_compiler", ROOT / "compiler/compile_governance.py")
        sys.path.insert(0, str(ROOT / "governance-src/runtime-scripts"))
        try:
            planner = load("controller_test_planner", ROOT / "governance-src/runtime-scripts/plan_governance.py")
        finally:
            sys.path.pop(0)
        model = json.loads((ROOT / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        low = compiler.compile_index(ROOT / "governance-src", materialize({"model": model, "theta": [0] * 3}))
        high = compiler.compile_index(ROOT / "governance-src", materialize({"model": model, "theta": [1] * 3}))
        self.assertNotEqual(low["presentation"], high["presentation"])
        cases = json.loads((ROOT / "tests/fixtures/governance_plan_cases.json").read_text(encoding="utf-8"))["cases"]
        observed_order_change = False
        for case in cases:
            before = planner.compile_plan(low, case["context"])
            after = planner.compile_plan(high, case["context"])
            for key in ("active_rules", "scope_guard", "risk_level", "report", "handoff"):
                self.assertEqual(before[key], after[key])
            self.assertEqual(sorted(before["required_closures"]), sorted(after["required_closures"]))
            self.assertEqual(sorted(before["evidence"]), sorted(after["evidence"]))
            observed_order_change |= before["required_closures"] != after["required_closures"]
        self.assertTrue(observed_order_change)

    def test_all_disabled_is_a_single_baseline_control(self):
        with self.fast_engine():
            run = controller.run_search(ROOT, self.protocol(), self.output, disabled=controller.OPERATORS)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(run["candidates"]), 1)
        self.assertEqual(run["candidates"][0]["candidate"]["theta"], [0.5] * 3)
        self.assertEqual(run["budget"]["calls"], 0)
        self.assertTrue(all(count["attempted"] == 0 for count in run["operator_counts"].values()))

    def test_learning_and_task_replay_share_one_call_and_token_ceiling(self):
        protocol = self.protocol(iterations=3)
        protocol["search"]["population"] = 4
        protocol["budget"]["model_calls"] = 8
        with self.fast_engine(), contextlib.redirect_stdout(io.StringIO()):
            run = controller.run_search(ROOT, protocol, self.output, runner=measured_runner,
                                        backend=measured_backend)
        self.assertGreater(len(REQUESTS), 0)
        self.assertGreater(len(BACKEND_REQUESTS), 0)
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(run["budget"]["calls"], 8)
        self.assertEqual(run["budget"]["calls"], len(REQUESTS) + len(BACKEND_REQUESTS))
        self.assertEqual(run["budget"]["total_tokens"], 7 * len(REQUESTS) + 5 * len(BACKEND_REQUESTS))

    def test_cli_verification_and_blocked_proposal_return_nonzero(self):
        self.output.write_text("{}", encoding="utf-8")
        proposal = Path(self.temporary.name) / "proposal"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            verified = main(["verify", "--run", str(self.output)])
            proposed = main(["propose", "--run", str(self.output), "--repo", str(ROOT),
                             "--output", str(proposal)])
        self.assertNotEqual(verified, 0)
        self.assertNotEqual(proposed, 0)
        self.assertFalse(proposal.exists())

    def test_hard_rejected_real_learner_patch_skips_unpaired_memory(self):
        from evolution.skillopt_adapter import SkillOptLearner

        def changed_patch(learner, rollouts):
            policy = next(policy for policy in learner.bridge.model["policies"] if "closure" in policy)
            return learner.bridge.bind_patch({"edits": [{
                "op": "replace", "target": policy["closure"],
                "content": policy["closure"] + " Synthetic candidate change.",
                "update_target": "policies/" + policy["id"] + "/closure",
            }], "reasoning": "synthetic rejected patch contract"})

        def validation(candidate, repo):
            if candidate.get("operator") == "skillopt":
                return {"ok": False, "errors": ["synthetic protected-rule rejection"]}
            return self.engineering_validation(candidate, repo)

        with self.fast_engine(), patch.object(controller, "validate_candidate", side_effect=validation), \
                patch.object(SkillOptLearner, "learn", new=changed_patch), \
                patch.object(SkillOptLearner, "update_memory", side_effect=AssertionError("unpaired memory")) as memory_update:
            run = controller.run_search(ROOT, self.protocol(iterations=1), self.output,
                                        runner=measured_runner, backend=measured_backend,
                                        disabled=("annealing", "de", "curvature"))
        self.assertEqual(run["status"], "completed")
        self.assertEqual([request["task"]["id"] for request in REQUESTS],
                         ["training-fixture", "selection-must-not-leak"])
        rejected = [item for item in run["candidates"] if not item["evaluation"]["ok"]]
        self.assertTrue(rejected)
        self.assertTrue(all(not item["observations"] and item["loss"] is None for item in rejected))
        self.assertEqual(run["operator_counts"]["skillopt"]["accepted"], 0)
        memory_update.assert_not_called()
        self.assertTrue(any(event["kind"] == "memory-skipped" for event in run["events"]))

    def test_selection_is_post_search_and_never_enters_learner_or_final_split(self):
        protocol = self.protocol(iterations=1)
        protocol["search"]["population"] = 4
        with self.fast_engine(), contextlib.redirect_stdout(io.StringIO()):
            run = controller.run_search(ROOT, protocol, self.output,
                                        runner=measured_runner, backend=measured_backend)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["best_candidate_origin"], "selection")
        self.assertTrue(run["selection"])
        self.assertEqual({request["task"]["id"] for request in REQUESTS},
                         {"training-fixture", "selection-must-not-leak"})
        self.assertTrue(all(observation["task_id"] == "training-fixture" for candidate in run["candidates"]
                            for observation in candidate["observations"]))
        self.assertTrue(all(observation["task_id"] == "selection-must-not-leak" for selected in run["selection"]
                            for observation in selected["observations"]))
        first_selection = next(index for index, entry in enumerate(DISPATCH)
                               if entry == ("runner", "selection-must-not-leak"))
        self.assertFalse(any(entry[0] == "backend" for entry in DISPATCH[first_selection:]))
        self.assertTrue(all("selection-must-not-leak" not in request["user"] and
                            "final-must-not-leak" not in request["user"] for request in BACKEND_REQUESTS))

    def test_duplicate_and_overlapping_split_identities_are_rejected_before_calls(self):
        for duplicate in (False, True):
            protocol = self.protocol()
            if duplicate:
                protocol["tasks"]["training"] *= 2
            else:
                protocol["tasks"]["final"] = copy.deepcopy(protocol["tasks"]["training"])
            with self.fast_engine(), self.assertRaisesRegex(ValueError, "duplicate|leaks"):
                controller.run_search(ROOT, protocol, self.output, runner=measured_runner,
                                      disabled=controller.OPERATORS)
        self.assertEqual(REQUESTS, [])

    def test_checkpoint_lock_rejects_another_writer_and_cleans_after_failure(self):
        lock = Path(str(self.output.resolve()) + ".lock")
        with controller.checkpoint_lock(self.output):
            self.assertTrue(lock.exists())
            with self.assertRaisesRegex(ValueError, "writer lock"):
                controller.run_search(ROOT, self.protocol(), self.output)
            self.assertTrue(lock.exists())
        self.assertFalse(lock.exists())
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with controller.checkpoint_lock(self.output):
                raise RuntimeError("synthetic failure")
        self.assertFalse(lock.exists())
        matrix_directory = self.output.parent / "new-matrix"
        with controller.checkpoint_lock(matrix_directory):
            self.assertFalse(matrix_directory.exists())
            self.assertTrue(Path(str(matrix_directory) + ".lock").exists())
        self.assertFalse(Path(str(matrix_directory) + ".lock").exists())


@unittest.skipIf(sys.version_info < (3, 10), "optional offline optimizer requires Python 3.10+")
class BudgetBoundaryTests(unittest.TestCase):
    def test_state_resume_preserves_consumption_without_charging_paused_time(self):
        budget = contracts.Budget(max_calls=3, max_total_tokens=20, max_seconds=5)
        budget._start = 10.0
        with patch.object(contracts.time, "monotonic", return_value=14.0):
            budget.reserve(estimated_tokens=7)
            budget.record({"total_tokens": 7}, elapsed_seconds=0.5)
            state = json.loads(json.dumps(budget.state(), allow_nan=False))
        restored = contracts.Budget.from_state(state)
        restored._start = 100.0
        with patch.object(contracts.time, "monotonic", return_value=100.5):
            self.assertEqual(restored.state()["elapsed_seconds"], 4.5)
            restored.reserve(estimated_tokens=1)
            restored.record({"total_tokens": 1}, elapsed_seconds=0.1)
        self.assertEqual(restored.calls, 2)
        self.assertEqual(restored.total_tokens, 8)
        with patch.object(contracts.time, "monotonic", return_value=101.0):
            with self.assertRaises(contracts.BudgetExceeded):
                restored.reserve()

    def test_exact_token_and_call_boundaries_block_subsequent_dispatch(self):
        budget = contracts.Budget(max_calls=2, max_total_tokens=10, max_seconds=60)
        budget.reserve(estimated_tokens=10)
        budget.record({"total_tokens": 10})
        with self.assertRaises(contracts.BudgetExceeded):
            budget.reserve()
        calls = contracts.Budget(max_calls=1, max_total_tokens=100, max_seconds=60)
        calls.reserve()
        calls.record({"total_tokens": 1})
        with self.assertRaises(contracts.BudgetExceeded):
            calls.reserve()
        tokens = contracts.Budget(max_calls=1, max_total_tokens=0, max_seconds=60)
        with self.assertRaises(contracts.BudgetExceeded):
            tokens.reserve()

    def test_nan_negative_and_boolean_budget_inputs_are_rejected(self):
        for kwargs in ({"max_calls": True}, {"max_total_tokens": -1}, {"max_seconds": math.nan},
                       {"max_seconds": math.inf}, {"max_seconds": 0}):
            with self.assertRaises(ValueError):
                contracts.Budget(**kwargs)
        budget = contracts.Budget()
        for estimate in (-1, True, 0.5):
            with self.assertRaises(ValueError):
                budget.reserve(estimated_tokens=estimate)
        for usage in ({"total_tokens": math.nan}, {"total_tokens": True}, {"total_tokens": -1}):
            with self.assertRaises(ValueError):
                budget.record(usage)
        for elapsed in (math.nan, math.inf, -1):
            with self.assertRaises(ValueError):
                budget.record({"total_tokens": 1}, elapsed_seconds=elapsed)

    def test_invalid_resume_counters_and_clock_are_rejected(self):
        state = contracts.Budget().state()
        for field, invalid in (("calls", -1), ("calls", True), ("total_tokens", -1),
                               ("total_tokens", 1.5), ("elapsed_seconds", math.nan),
                               ("elapsed_seconds", -1), ("unknown_usage", "false"), ("records", {})):
            corrupted = copy.deepcopy(state)
            corrupted[field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                contracts.Budget.from_state(corrupted)


if __name__ == "__main__":
    unittest.main()
