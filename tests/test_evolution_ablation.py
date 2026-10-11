"""Development matrix plumbing tests, not conditional-contribution evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

OFFLINE_SUPPORTED = sys.version_info >= (3, 10)
if OFFLINE_SUPPORTED:
    from evolution.ablation import _baseline, run_matrix
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
            self.assertEqual(set(arguments["skillopt_only"]["disabled"]), {"annealing", "de", "curvature"})
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
            self.assertTrue(checkpoint["arms"]["skillopt_only"]["completed"])
            self.assertEqual(run_matrix(ROOT, self.protocol, output)["status"], "completed")
            self.assertEqual(attempted.count("skillopt_only"), 1)
            self.assertEqual(attempted.count("full"), 2)
            self.assertEqual(historical.call_count, 2)

    def test_baseline_requires_real_git_identity(self):
        with self.assertRaisesRegex(ValueError, "full Git commit"):
            _baseline(ROOT, "HEAD")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            _baseline(ROOT, "0" * 40)


if __name__ == "__main__":
    unittest.main()
