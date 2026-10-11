"""Engineering tests of evidence admission, never product-effectiveness trials."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

OFFLINE_SUPPORTED = sys.version_info >= (3, 10)
if OFFLINE_SUPPORTED:
    from evolution.contracts import Budget, candidate_id, digest, materialize
    from evolution.evaluator import cache_key, canonical_source, evaluate, source_hash, validate_candidate
    from evolution.promotion import (EvidenceError, PROTOCOL, ROOT, _admit, _artifact, _number,
                                     _claim_request, _splits, paired_bootstrap, propose, verify)


def baseline():
    return {"model": json.loads((ROOT / "governance-src/model/governance-model.json").read_text(encoding="utf-8")),
            "theta": [0.5, 0.5, 0.5]}


@unittest.skipUnless(OFFLINE_SUPPORTED, "optional offline evolution requires Python 3.10+")
class EvolutionEvidenceTests(unittest.TestCase):
    def test_source_serialization_is_order_independent_and_sensitive_to_all_sources(self):
        source = canonical_source(ROOT)
        self.assertEqual(source_hash(source), source_hash(dict(reversed(list(source.items())))))
        changed = dict(source)
        changed["runtime-scripts/plan_governance.py"] += "\n# changed\n"
        self.assertNotEqual(source_hash(source), source_hash(changed))

    def test_theta_changes_executable_order_without_losing_required_closure(self):
        candidate = baseline()
        neutral = validate_candidate(candidate, ROOT)
        changed = validate_candidate(dict(candidate, theta=[1.0, 1.0, 1.0]), ROOT)
        self.assertTrue(neutral["ok"], neutral["errors"])
        self.assertTrue(changed["ok"], changed["errors"])
        self.assertNotEqual(neutral["candidate_id"], changed["candidate_id"])
        self.assertEqual([plan["active_rules"] for plan in neutral["plans"]],
                         [plan["active_rules"] for plan in changed["plans"]])
        self.assertNotEqual([plan["execution_order"] for plan in neutral["plans"]],
                            [plan["execution_order"] for plan in changed["plans"]])
        self.assertIn("not tokens", neutral["context_measurement"])

    def test_protected_dependencies_cannot_be_optimized_away(self):
        candidate = baseline()
        candidate["model"]["policies"][3]["requires"] = ["NO_SUCH_RULE"]
        result = validate_candidate(candidate, ROOT)
        self.assertFalse(result["ok"])
        self.assertIn("protected governance semantics", result["errors"][0])

    def test_engineering_mode_cannot_fabricate_model_usage(self):
        result = evaluate(baseline(), {"id": "development-fixture"})
        self.assertEqual(result["kind"], "development_engineering")
        self.assertFalse(result["empirical_eligible"])
        self.assertFalse(result["independent_sample"])
        self.assertIsNone(result["usage"]["total_tokens"])

    def test_failures_retries_and_actual_usage_are_counted(self):
        calls = []
        def runner(request):
            calls.append(request["attempt"])
            usage = {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}
            return {"status": "failed" if request["attempt"] == 0 else "completed",
                    "usage": usage, "provider_receipt": {"request_id": str(request["attempt"])},
                    "outcome": {"loss": 0.25}, "error": "retryable" if request["attempt"] == 0 else None}
        budget = Budget(max_calls=3)
        result = evaluate(baseline(), {"id": "task"}, runner, retries=1, budget=budget,
                          runner_identity={"id": "test-runner", "version": "1"}, source={"a": "b"})
        self.assertEqual(calls, [0, 1])
        self.assertEqual(budget.calls, 2)
        self.assertEqual(result["usage"]["total_tokens"], 20)
        self.assertIsNone(result["usage"]["reasoning_tokens"])
        self.assertEqual(result["outcome"]["loss"], 0.25)

    def test_missing_failed_call_usage_stays_unknown_after_success(self):
        def runner(request):
            if request["attempt"] == 0:
                raise TimeoutError("no provider receipt")
            return {"status": "completed", "usage": {"total_tokens": 5}, "outcome": {"loss": 0}}
        result = evaluate(baseline(), {"id": "task"}, runner, retries=1,
                          runner_identity={"id": "test-runner", "version": "1"})
        self.assertEqual(len(result["attempts"]), 2)
        self.assertIsNone(result["usage"]["total_tokens"])
        self.assertFalse(result["empirical_eligible"])

    def test_cache_reuse_is_not_an_independent_sample_and_all_inputs_bind(self):
        calls, cache = [], {}
        def runner(request):
            calls.append(request)
            return {"status": "completed", "usage": {"total_tokens": 5}, "outcome": {"loss": 0}}
        options = {"model": "test-model", "runner_identity": {"id": "runner", "version": "v1"},
                   "source": {"model.json": "source"}, "config": {"temperature": 0}, "deps": {"revision": "a"}, "cache": cache}
        first = evaluate(baseline(), {"id": "task"}, runner, **options)
        second = evaluate(baseline(), {"id": "task"}, runner, **options)
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertFalse(second["independent_sample"])
        self.assertEqual(len(calls), 1)
        common = [baseline(), {"id": "task"}, "test-model", {"temperature": 0}, {"revision": "a"}, {"id": "runner", "version": "v1"}]
        original = cache_key(*common, source={"a": "1"})
        for index, replacement in ((1, {"id": "other"}), (2, "other-model"), (3, {"temperature": 1}),
                                   (4, {"revision": "b"}), (5, {"id": "runner", "version": "v2"})):
            changed = list(common)
            changed[index] = replacement
            self.assertNotEqual(original, cache_key(*changed, source={"a": "1"}))
        self.assertNotEqual(original, cache_key(*common, source={"a": "2"}))

    def test_artifact_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            path.write_text('{"usage":{"total_tokens":10}}', encoding="utf-8")
            reference = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertEqual(_artifact(reference, path.parent)[0]["usage"]["total_tokens"], 10)
            path.write_text('{"usage":{"total_tokens":0}}', encoding="utf-8")
            with self.assertRaisesRegex(EvidenceError, "hash mismatch"):
                _artifact(reference, path.parent)

    def test_project_family_and_previous_final_leakage_are_rejected(self):
        frozen = {"splits": {name: [{"task_id": name, "task_family": name, "project_id": name}]
                             for name in ("training", "selection", "final")}, "prior_final_task_ids": []}
        self.assertIn("final", _splits(frozen))
        leaked = copy.deepcopy(frozen)
        leaked["splits"]["final"][0]["task_family"] = "training"
        with self.assertRaisesRegex(EvidenceError, "leakage"):
            _splits(leaked)
        exposed = copy.deepcopy(frozen)
        exposed["prior_final_task_ids"] = ["final"]
        with self.assertRaisesRegex(EvidenceError, "exposed"):
            _splits(exposed)

    def test_synthetic_and_cache_observations_are_not_release_evidence(self):
        for record in ({"kind": "synthetic", "pass": True},
                       {"kind": "real_model_task", "independent_sample": True, "cache_hit": True}):
            with self.assertRaises(EvidenceError):
                _admit(record, ROOT, {}, {}, {}, {})
        with self.assertRaises(EvidenceError):
            _number(True, "manual pass flag")

    def test_bootstrap_uses_paired_costs_and_frozen_family_weights(self):
        # Numeric algorithm fixture, explicitly not real task/product evidence.
        pairs = [{"model_family": model, "task_family": task, "tokens": ratio}
                 for model, ratio in (("m1", 0.5), ("m2", 0.9)) for task in ("t1", "t2") for _ in range(8)]
        inference = {"seed": 1729, "repetitions": 1000, "confidence": 0.95, "method": "paired-family-stratified-bootstrap"}
        report = paired_bootstrap(pairs, "tokens", {"m1": 0.75, "m2": 0.25}, {"t1": 0.5, "t2": 0.5}, inference)
        self.assertAlmostEqual(report["point"], 0.6)
        self.assertLess(report["ci"][1], 1)
        self.assertEqual(report, paired_bootstrap(pairs, "tokens", {"m1": 0.75, "m2": 0.25}, {"t1": 0.5, "t2": 0.5}, inference))

    def test_bootstrap_interval_tracks_nonuniform_task_weights(self):
        pairs = [{"model_family": "m", "task_family": task, "tokens": ratio}
                 for task, ratio in (("frequent", 0.1), ("rare", 0.9)) for _ in range(8)]
        report = paired_bootstrap(pairs, "tokens", {"m": 1.0}, {"frequent": 0.999, "rare": 0.001},
                                  {"seed": 1729, "repetitions": 1000, "confidence": 0.95, "method": "paired-family-stratified-bootstrap"})
        self.assertAlmostEqual(report["point"], 0.1008)
        self.assertLess(report["ci"][1], 0.2)  # Uniform family sampling would center near 0.5.

    def test_one_provider_receipt_cannot_be_reused_for_multiple_ablation_arms(self):
        global_requests = set()
        receipt = {"kind": "provider-usage", "provider": "fixture", "request_id": "unique-call"}
        _claim_request(receipt, global_requests)
        with self.assertRaisesRegex(EvidenceError, "across observations/search arms"):
            _claim_request(receipt, global_requests)

    def test_hand_filled_pass_flags_cannot_promote_or_write_source(self):
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        candidate = baseline()
        run = {"run_id": "manual-pass-is-insufficient", "protocol": protocol, "protocol_sha256": digest(protocol),
               "candidates": [{"id": candidate_id(candidate), "candidate": candidate}],
               "empirical_status": "PASS", "pass": True, "core_pass": True,
               "token_ratio": 0.1, "time_ratio": 0.1}
        with patch("evolution.promotion.validate_candidate", return_value={"ok": True}):
            report = verify(run)
            self.assertEqual(report["engineering"], "PASS")
            self.assertEqual(report["empirical"]["status"], "BLOCKED")
            self.assertEqual(report["formal_qualification"], "UNASSESSED")
            self.assertFalse(report["promotion_allowed"])
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "proposal"
                before = source_hash(ROOT)
                self.assertEqual(propose(run, ROOT, output)["status"], "BLOCKED")
                self.assertFalse(output.exists())
                self.assertEqual(source_hash(ROOT), before)

    def test_protocol_pins_baseline_targets_and_complete_ablation(self):
        protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(protocol["baseline"]["rc15_revision"], "0808842e759763c722f77a2fd9b464842480a290")
        self.assertEqual(protocol["thresholds"]["full_task_tokens_ratio_max"], 0.85)
        self.assertEqual(protocol["thresholds"]["governance_context_ratio_max"], 0.75)
        self.assertEqual(protocol["thresholds"]["wall_time_ratio_max"], 0.9)
        self.assertEqual(len(protocol["arms"]), 9)
        self.assertFalse(protocol["evidence"]["manual_pass_flags_are_evidence"])


if __name__ == "__main__":
    unittest.main()
