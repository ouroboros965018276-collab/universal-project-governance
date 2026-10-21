"""Exact execution-input dispatch contracts; these are synthetic unit checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SUPPORTED = sys.version_info >= (3, 10)
if SUPPORTED:
    from evolution.contracts import digest
    from evolution.evaluator import canonical_source, evaluate


@unittest.skipUnless(SUPPORTED, "optional offline evolution requires Python 3.10+")
class ExactDispatchTests(unittest.TestCase):
    def test_historical_identity_and_exact_source_are_delivered_without_materializing(self):
        source = {"templates/SKILL.template.md": "historical\r\n", "model/governance-model.json": "{}"}
        artifact = {"compiler": "old compiler", "runtime": {"SKILL.md": "old runtime\r\n"}}
        candidate = {"model": {"historical_schema": 0}, "revision": "a" * 40}
        seen = []
        def runner(request):
            seen.append(copy.deepcopy(request))
            request["source"]["templates/SKILL.template.md"] = "modified private copy"
            request["execution_artifact"]["runtime"]["SKILL.md"] = "modified private copy"
            return {"status": "completed", "provider_receipt": {"id": "synthetic-unit-receipt"},
                    "usage": {"total_tokens": 7}, "outcome": {"loss": 1, "hard": 1, "soft": 1}}
        with patch("evolution.evaluator.candidate_id", side_effect=AssertionError("modern materialization forbidden")):
            result = evaluate(candidate, {"id": "historical-task"}, runner,
                runner_identity={"id": "unit", "version": "1"}, source=source,
                candidate_identity="b" * 64, execution_artifact=artifact)
        self.assertEqual(seen[0]["source"], source)
        self.assertEqual(seen[0]["execution_artifact"], artifact)
        self.assertEqual(seen[0]["candidate_id"], "b" * 64)
        self.assertEqual(seen[0]["source_sha256"], digest(source))
        self.assertEqual(result["execution_artifact_sha256"], digest(artifact))
        self.assertTrue(result["empirical_eligible"])

    def test_compiler_and_runtime_changes_invalidate_cached_execution(self):
        calls = []
        def runner(request):
            calls.append(request)
            return {"status": "completed", "provider_receipt": {"id": "synthetic-unit-receipt"},
                    "usage": {"total_tokens": 2}, "outcome": {"loss": 1}}
        options = {"runner_identity": {"id": "unit", "version": "1"}, "source": {"model.json": "{}"},
                   "candidate_identity": "c" * 64, "cache": {}}
        artifact = {"compiler": "v1", "runtime": {"SKILL.md": "v1"}}
        evaluate({}, {"id": "task"}, runner, execution_artifact=artifact, **options)
        cached = evaluate({}, {"id": "task"}, runner, execution_artifact=artifact, **options)
        self.assertTrue(cached["cache_hit"])
        for changed in ({"compiler": "v2", "runtime": {"SKILL.md": "v1"}},
                        {"compiler": "v1", "runtime": {"SKILL.md": "v2"}}):
            evaluate({}, {"id": "task"}, runner, execution_artifact=changed, **options)
        self.assertEqual(len(calls), 3)

    def test_exact_source_preserves_utf8_newline_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "governance-src"
            root.mkdir()
            (root / "source.txt").write_bytes("规则\r\n".encode("utf-8"))
            self.assertEqual(canonical_source(temporary), {"source.txt": "规则\r\n"})

    def test_invalid_identity_fails_before_dispatch(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            evaluate({}, {"id": "task"}, lambda request: self.fail("dispatched"), candidate_identity="HEAD")


if __name__ == "__main__":
    unittest.main()
