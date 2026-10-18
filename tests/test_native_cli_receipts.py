"""Synthetic current-validation classification; no project work is executed."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evolution.native_cli_receipts import replay_current_validation


def digest(files):
    hashes = {name: hashlib.sha256(text.encode()).hexdigest()
              for name, text in files.items()}
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class NativeCliReceiptTests(unittest.TestCase):
    def setUp(self):
        self.task = {"initial_files": {"module.py": "before\n"}}
        self.initial = self.task["initial_files"]
        self.final = {"module.py": "after\n"}

    def validation(self, files, ok=True):
        value = {"ok": ok, "failures": [] if ok else ["check-failed"],
                 "execution": {"receipt_ref": "validation-001/result.json"}}
        return {"tool": "repo_validate", "wall_seconds": 0.1,
                "state_sha256": digest(files), "result": value}

    def classify(self, rows, verifier=None):
        seen = []
        def verify(value, task, files):
            self.assertIs(task, self.task)
            seen.append((value, files.copy()))
            if verifier is not None:
                verifier(value, task, files)
        result = replay_current_validation(
            self.task, [event for event, _ in rows],
            receipt_file_states=lambda task, journal: iter(rows),
            verify_validation=verify)
        return result, seen

    def assert_not_run(self, result):
        reason = "required-current-project-validation-missing"
        self.assertTrue(result["not_run"])
        self.assertEqual(result["current_snapshot_validation"], "NOT_RUN")
        self.assertEqual(result["supplied_validation"],
                         {"ok": False, "failures": [reason]})
        self.assertEqual(result["extra_failures"], [reason])
        self.assertTrue(result["all_occurred_execution_receipts_verified"])

    def test_current_pass_and_known_failure_preserve_verified_result(self):
        for ok in (True, False):
            with self.subTest(ok=ok):
                event = self.validation(self.initial, ok)
                result, seen = self.classify([(event, self.initial)])
                self.assertIs(result["supplied_validation"], event["result"])
                self.assertFalse(result["not_run"])
                self.assertEqual(result["current_snapshot_validation"], "EXECUTED")
                self.assertEqual(result["extra_failures"], [])
                self.assertEqual(result["occurred_execution_receipt_count"], 1)
                self.assertTrue(result["all_occurred_execution_receipts_verified"])
                self.assertEqual(seen, [(event["result"], self.initial)])

    def test_patch_after_validation_keeps_history_but_current_is_not_run(self):
        event = self.validation(self.initial)
        patch = {"tool": "repo_patch", "wall_seconds": 0.1,
                 "state_sha256": digest(self.final), "result": {"ok": True}}
        result, seen = self.classify([(event, self.initial), (patch, self.final)])
        self.assert_not_run(result)
        self.assertEqual(result["files"], self.final)
        self.assertEqual(result["occurred_execution_receipt_count"], 1)
        self.assertEqual(seen, [(event["result"], self.initial)])

    def test_never_validated_supplies_failure_without_execution(self):
        result, seen = self.classify([])
        self.assert_not_run(result)
        self.assertEqual(result["occurred_execution_receipt_count"], 0)
        self.assertEqual(seen, [])
        self.assertEqual(result["files"], self.initial)
        self.assertIsNot(result["files"], self.initial)

    def test_historical_unknown_missing_or_unconfirmed_cleanup_propagates(self):
        for error in (ValueError("historical-execution-unknown"),
                      FileNotFoundError("historical-receipt-missing"),
                      ValueError("historical-cleanup-unconfirmed")):
            with self.subTest(reason=str(error)):
                def reject(*args):
                    raise error
                event = self.validation(self.initial)
                with self.assertRaises(type(error)) as caught:
                    self.classify([(event, self.initial)], reject)
                self.assertIs(caught.exception, error)

    def test_last_journal_hash_mismatch_is_rejected(self):
        event = self.validation(self.initial)
        patch = {"tool": "repo_patch", "wall_seconds": 0.1,
                 "state_sha256": digest(self.initial), "result": {"ok": True}}
        with self.assertRaisesRegex(ValueError, "native-final-journal-state"):
            self.classify([(event, self.initial), (patch, self.final)])


if __name__ == "__main__":
    unittest.main()
