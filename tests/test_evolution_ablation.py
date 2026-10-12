"""Development matrix plumbing tests, not conditional-contribution evidence."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

OFFLINE_SUPPORTED = sys.version_info >= (3, 10)
if OFFLINE_SUPPORTED:
    from evolution.ablation import _baseline, _real_baseline, run_matrix
    from evolution.promotion import PROTOCOL, ROOT


@unittest.skipUnless(OFFLINE_SUPPORTED, "optional offline evolution requires Python 3.10+")
class EvolutionAblationTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    def test_matrix_dispatches_all_controls_with_identical_caps(self):
        calls = []
        def search(repo, protocol, output, **options):
            calls.append((Path(output).stem, copy.deepcopy(protocol["budget"]), options))
            return {"run_id": Path(output).stem, "stage": "engineering", "status": "completed", "candidates": [],
                    "budget": {"max_calls": protocol["budget"]["model_calls"], "max_total_tokens": protocol["budget"]["tokens"],
                               "max_seconds": protocol["budget"]["wall_seconds"], "calls": 0}}
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", return_value={"engineering": "PASS"}) as historical, \
             patch("evolution.ablation.run_search", side_effect=search):
            output = Path(temporary) / "matrix"
            matrix = run_matrix(ROOT, self.protocol, output)
            self.assertEqual(historical.call_count, 2)
            self.assertEqual(len(calls), 7)
            self.assertEqual(set(matrix["arms"]), set(self.protocol["arms"]))
            self.assertEqual(matrix["status"], "completed")
            self.assertTrue(all(budget == self.protocol["budget"] for _, budget, _ in calls))
            arguments = {name: options for name, _, options in calls}
            self.assertEqual(set(arguments["reflection_only"]["disabled"]), {"annealing", "de", "curvature"})
            self.assertEqual(arguments["without_chaos"]["disabled"], ("annealing",))
            self.assertTrue(arguments["ordinary_annealing"]["ordinary"])
            self.assertFalse(arguments["full"]["ordinary"])
            self.assertEqual(matrix["empirical"]["status"], "BLOCKED")
            self.assertIsNone(matrix["conditional_contributions"])
            self.assertIsNone(matrix["token_savings"])
            self.assertEqual(run_matrix(ROOT, self.protocol, output), matrix)
            self.assertEqual(len(calls), 7)  # Completed arm receipts are reused, never new samples.

    def test_resume_rejects_protocol_drift(self):
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", return_value={"engineering": "PASS"}), \
             patch("evolution.ablation.run_search", return_value={"status": "completed", "stage": "engineering"}):
            output = Path(temporary) / "matrix"
            run_matrix(ROOT, self.protocol, output)
            changed = copy.deepcopy(self.protocol)
            changed["budget"]["model_calls"] += 1
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                run_matrix(ROOT, changed, output)

    def test_failed_dispatch_keeps_completed_arms_and_resumes_next(self):
        attempted = []
        def search(repo, protocol, output, **options):
            name = Path(output).stem
            attempted.append(name)
            if name == "full" and attempted.count("full") == 1:
                raise RuntimeError("interrupted before callback dispatch")
            return {"status": "completed", "stage": "engineering"}
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", return_value={"engineering": "PASS"}) as historical, \
             patch("evolution.ablation.run_search", side_effect=search):
            output = Path(temporary) / "matrix"
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                run_matrix(ROOT, self.protocol, output)
            checkpoint = json.loads((output / "matrix.json").read_text(encoding="utf-8"))
            self.assertTrue(checkpoint["arms"]["reflection_only"]["completed"])
            self.assertEqual(run_matrix(ROOT, self.protocol, output)["status"], "completed")
            self.assertEqual(attempted.count("reflection_only"), 1)
            self.assertEqual(attempted.count("full"), 2)
            self.assertEqual(historical.call_count, 2)

    def test_baseline_requires_real_git_identity(self):
        with self.assertRaisesRegex(ValueError, "full Git commit"):
            _baseline(ROOT, "HEAD")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            _baseline(ROOT, "0" * 40)

    def historical_fixture(self, revision="a" * 40):
        return {"engineering": "PASS", "revision": revision,
                "source_sha256": "synthetic-source", "stage": "historical-baseline-engineering",
                "source": {"model/governance-model.json": json.dumps({"version": revision}),
                           "runtime-scripts/plan_governance.py": "exact historical planner\r\n"},
                "model": {"version": revision, "old_schema": True},
                "execution_artifact": {"compiler": "historical compiler " + revision,
                                       "license": "unit fixture", "runtime": {"SKILL.md": revision + "\r\n"}}}

    def real_protocol(self):
        protocol = copy.deepcopy(self.protocol)
        protocol["model"] = "synthetic-contract-model"
        protocol["search"]["retries"] = 0
        protocol["tasks"] = {"training": [{"id": "train-unit"}],
                             "selection": [{"id": "selection-unit"}],
                             "final": [{"id": "untouched-final-unit"}]}
        return protocol

    def test_real_matrix_replays_both_exact_historical_releases_on_same_development_splits(self):
        requests = []
        def runner(request):
            requests.append(copy.deepcopy(request))
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 5}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        def historical(repo, revision, **options):
            self.assertTrue(options["include_source"])
            return self.historical_fixture(revision)
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", side_effect=historical), \
             patch("evolution.ablation.run_search", return_value={"status": "completed", "stage": "development-real-task"}), \
             patch("evolution.ablation.engine_identity", return_value="unit-engine"), \
             patch("evolution.evaluator.candidate_id", side_effect=AssertionError("historical materialization forbidden")):
            output = Path(temporary) / "matrix"
            matrix = run_matrix(ROOT, self.real_protocol(), output, runner=runner)
            self.assertEqual(matrix["status"], "completed")
            self.assertEqual(len(requests), 4)
            self.assertEqual({row["task"]["id"] for row in requests}, {"train-unit", "selection-unit"})
            for arm in ("rc15", "latest_baseline"):
                summary = matrix["arms"][arm]
                checkpoint = json.loads((output / summary["checkpoint"]).read_text(encoding="utf-8"))
                self.assertEqual(checkpoint["budget"]["calls"], 2)
                self.assertEqual(checkpoint["budget"]["total_tokens"], 10)
                self.assertEqual({row["split"] for row in checkpoint["observations"]}, {"training", "selection"})
                revision = summary["revision"]
                matched = [row for row in requests if row["candidate"]["revision"] == revision]
                self.assertEqual(len(matched), 2)
                for row in matched:
                    self.assertEqual(row["source"], self.historical_fixture(revision)["source"])
                    self.assertEqual(row["execution_artifact"], self.historical_fixture(revision)["execution_artifact"])
                    self.assertNotIn("theta", row["candidate"])
                    self.assertTrue(row["source_sha256"])
            self.assertEqual(run_matrix(ROOT, self.real_protocol(), output, runner=runner), matrix)
            self.assertEqual(len(requests), 4)

    def test_historical_interruption_is_fenced_against_replay(self):
        calls = []
        def runner(request):
            calls.append(request)
            raise KeyboardInterrupt("synthetic interrupted callback")
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", side_effect=lambda *a, **k: self.historical_fixture()), \
             patch("evolution.ablation.engine_identity", return_value="unit-engine"):
            output = Path(temporary) / "historical.json"
            with self.assertRaises(KeyboardInterrupt):
                _real_baseline(ROOT, "a" * 40, self.real_protocol(), output, runner)
            checkpoint = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["pending"]["task_id"], "train-unit")
            with self.assertRaisesRegex(ValueError, "uncertain usage"):
                _real_baseline(ROOT, "a" * 40, self.real_protocol(), output, runner)
            self.assertEqual(len(calls), 1)

    def test_unknown_historical_usage_is_preserved_and_blocks_resume(self):
        calls = []
        def runner(request):
            calls.append(request)
            return {"status": "failed", "provider_receipt": "synthetic-missing-usage", "usage": {}, "error": "fixture"}
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", side_effect=lambda *a, **k: self.historical_fixture()), \
             patch("evolution.ablation.engine_identity", return_value="unit-engine"):
            output = Path(temporary) / "historical.json"
            run = _real_baseline(ROOT, "a" * 40, self.real_protocol(), output, runner)
            self.assertEqual(run["status"], "budget-exhausted")
            self.assertTrue(run["budget"]["unknown_usage"])
            self.assertIsNotNone(run["pending"])
            self.assertEqual(len(run["observations"]), 1)
            with self.assertRaisesRegex(ValueError, "uncertain usage"):
                _real_baseline(ROOT, "a" * 40, self.real_protocol(), output, runner)
            self.assertEqual(len(calls), 1)

    def test_historical_budget_stop_is_not_completed_and_is_not_replayed(self):
        calls = []
        def runner(request):
            calls.append(request)
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 5}, "outcome": {"loss": 1}}
        protocol = self.real_protocol()
        protocol["budget"]["model_calls"] = 1
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", side_effect=lambda *a, **k: self.historical_fixture()), \
             patch("evolution.ablation.engine_identity", return_value="unit-engine"):
            output = Path(temporary) / "historical.json"
            run = _real_baseline(ROOT, "a" * 40, protocol, output, runner)
            self.assertEqual(run["status"], "budget-exhausted")
            self.assertEqual(run["budget"]["calls"], 1)
            self.assertEqual(run["budget"]["total_tokens"], 5)
            self.assertEqual(len(run["observations"]), 1)
            self.assertIsNone(run["pending"])
            self.assertEqual(_real_baseline(ROOT, "a" * 40, protocol, output, runner), run)
            self.assertEqual(len(calls), 1)

    def test_completed_historical_execution_does_not_imply_quality_pass(self):
        def runner(request):
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 5}, "outcome": {"loss": 0, "hard": 0, "soft": 0}}
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", side_effect=lambda *a, **k: self.historical_fixture()), \
             patch("evolution.ablation.engine_identity", return_value="unit-engine"):
            run = _real_baseline(ROOT, "a" * 40, self.real_protocol(), Path(temporary) / "historical.json", runner)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["execution_status"], "PASS")
        self.assertEqual(run["quality_status"], "FAIL")
        self.assertNotIn("replay_status", run)

    def test_last_historical_call_token_overrun_retains_all_observations(self):
        calls = []
        def runner(request):
            calls.append(request)
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 3 if len(calls) == 1 else 8},
                    "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        protocol = self.real_protocol()
        protocol["budget"]["tokens"] = 10
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", side_effect=lambda *a, **k: self.historical_fixture()), \
             patch("evolution.ablation.engine_identity", return_value="unit-engine"):
            output = Path(temporary) / "historical.json"
            run = _real_baseline(ROOT, "a" * 40, protocol, output, runner)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "budget-exhausted")
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(run["budget_overrun"]["tokens"]["actual"], 11)
        self.assertEqual(run["budget"]["total_tokens"], 11)
        self.assertEqual(len(run["observations"]), 2)
        self.assertEqual(run["observations"][-1]["observation"]["usage"]["total_tokens"], 8)

    def test_matrix_does_not_label_budget_exhaustion_completed(self):
        calls = []
        def search(repo, protocol, output, **options):
            name = Path(output).stem
            calls.append(name)
            return {"status": "budget-exhausted" if name == "full" else "completed", "stage": "engineering"}
        with tempfile.TemporaryDirectory() as temporary, patch("evolution.ablation._baseline", return_value={"engineering": "PASS"}), \
             patch("evolution.ablation.run_search", side_effect=search):
            output = Path(temporary) / "matrix"
            matrix = run_matrix(ROOT, self.protocol, output)
            self.assertEqual(matrix["status"], "budget-exhausted")
            self.assertFalse(matrix["arms"]["full"]["completed"])
            self.assertTrue(matrix["arms"]["full"]["terminal"])
            run_matrix(ROOT, self.protocol, output)
            self.assertEqual(calls.count("full"), 1)

    def test_historical_loader_retains_original_compiler_and_runtime(self):
        files = {"compiler/compile_governance.py": "old compiler\r\n", "LICENSE": "unit license",
                 "governance-src/model/governance-model.json": '{"version":"historical"}',
                 "universal-project-governance/SKILL.md": "historical skill\r\n",
                 "universal-project-governance/scripts/plan_governance.py": "historical planner\r\n",
                 "tests/fixtures/governance_plan_cases.json": '{"cases":[{"context":{}}]}'}
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as contents:
            for name, text in files.items():
                data = text.encode("utf-8")
                member = tarfile.TarInfo(name)
                member.size = len(data)
                contents.addfile(member, io.BytesIO(data))
        def command(command, cwd):
            return {"returncode": 0, "stdout": json.dumps({"required_closures": [], "evidence": []}), "stderr": ""}
        with patch("evolution.ablation.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=archive.getvalue())), \
             patch("evolution.ablation._command", side_effect=command):
            result = _baseline(ROOT, "a" * 40, include_source=True)
        self.assertEqual(result["engineering"], "PASS")
        self.assertEqual(result["execution_artifact"]["compiler"], "old compiler\r\n")
        self.assertEqual(result["execution_artifact"]["runtime"]["SKILL.md"], "historical skill\r\n")
        self.assertNotIn("presentation", result["model"])


if __name__ == "__main__":
    unittest.main()
