"""Fault-injected native cost accounting; no real CLI or provider dispatch."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
if sys.version_info >= (3, 10):
    from evolution import native_codex as native
    from evolution.contracts import Budget
    from evolution.reflective import BudgetedBackend


def grade_fixture(unused):
    return {"hard": 1, "soft": 1, "loss": 0}


def completed(*, usage=True, exit_code=0, duplicate=False):
    events = [{"type": "thread.started", "thread_id": "synthetic-cost-thread"},
              {"type": "turn.started"},
              {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}}]
    if usage:
        turn = {"type": "turn.completed", "usage": {"input_tokens": 50, "output_tokens": 7,
                                                       "cached_input_tokens": 20}}
        events.append(turn)
        if duplicate:
            events.append(turn)
    return subprocess.CompletedProcess([], exit_code,
        ("\n".join(json.dumps(event) for event in events) + "\n").encode(), b"synthetic stderr")


@unittest.skipIf(sys.version_info < (3, 10), "optional native optimizer requires Python 3.10+")
class NativeCostPersistenceTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "eval-workspaces/tmp-native-cost-tests"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="native-cost-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        binary = self.root / "synthetic-binary"
        binary.write_bytes(b"never executed")
        self.config = {"binary": str(binary), "model": "synthetic-cost-model", "effort": "low",
                       "artifact_root": str(self.root / "artifacts"), "timeout_seconds": 10,
                       "grader": __name__ + ":grade_fixture"}
        self.client = native.NativeCodex(self.config)

    def call(self, key="first", client=None):
        return (client or self.client)._call(key=key, prompt="synthetic cost fixture", bindings={"kind": "test"})

    def assert_fenced(self, invoked):
        with self.assertRaises(native.NativeCallPending):
            self.call("different-key")
        # A fresh instance must also honor existing pending/failure evidence.
        with self.assertRaises(native.NativeCallPending):
            self.call("another-key", native.NativeCodex(self.config))
        self.assertEqual(invoked.call_count, 1)
        self.assertEqual(len(list((self.client.artifacts / "calls").glob("*/pending.json"))), 1)

    def test_stdout_write_failure_preserves_completed_usage_and_blocks_relaunch(self):
        original = Path.write_bytes
        def denied(path, data):
            if path.name == "stdout.raw":
                raise PermissionError("synthetic stdout denied")
            return original(path, data)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, \
                patch.object(Path, "write_bytes", new=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            receipt = raised.exception.provider_receipt
            self.assertEqual(receipt["status"], "raw-evidence-persistence-failed")
            self.assertEqual(receipt["original_status"], "completed")
            self.assertIn("stdout denied", receipt["raw_persistence_error"])
            self.assertEqual(receipt["adapter_retries"], 0)
            self.assert_fenced(invoked)

    def test_stderr_write_failure_keeps_observed_stdout_and_known_charge(self):
        original = Path.write_bytes
        def denied(path, data):
            if path.name == "stderr.raw":
                raise OSError("synthetic stderr denied")
            return original(path, data)
        process = completed()
        with patch.object(native.subprocess, "run", return_value=process) as invoked, patch.object(Path, "write_bytes", new=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            raw = next((self.client.artifacts / "calls").glob("*/stdout.raw"))
            self.assertEqual(raw.read_bytes(), process.stdout)
            self.assert_fenced(invoked)

    def test_result_write_failure_retains_usage_and_failure_receipt(self):
        original = native._atomic
        def denied(path, value):
            if path.name == "result.json":
                raise PermissionError("synthetic result denied")
            return original(path, value)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, patch.object(native, "_atomic", side_effect=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            self.assertEqual(raised.exception.provider_receipt["status"], "post-dispatch-evidence-unconfirmed")
            self.assertFalse(any((self.client.artifacts / "calls").glob("*/result.json")))
            self.assert_fenced(invoked)

    def test_receipt_write_failure_retains_usage_even_when_unknown_receipt_write_also_fails(self):
        original = native._atomic
        def denied(path, value):
            if path.name == "receipt.json":
                raise PermissionError("synthetic all receipts denied")
            return original(path, value)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, patch.object(native, "_atomic", side_effect=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            self.assertIn("all receipts denied", raised.exception.provider_receipt["receipt_persistence_error"])
            self.assertTrue((self.client.artifacts / "UNKNOWN_CALL.json").exists())
            self.assert_fenced(invoked)

    def test_unknown_fence_write_denial_preserves_timeout_usage_and_original_failure(self):
        process = completed()
        timeout = subprocess.TimeoutExpired("synthetic", 10, output=process.stdout, stderr=process.stderr)
        original = Path.open
        def denied(path, *args, **kwargs):
            if path.name == "UNKNOWN_CALL.json":
                raise PermissionError("synthetic fence denied")
            return original(path, *args, **kwargs)
        with patch.object(native.subprocess, "run", side_effect=timeout) as invoked, patch.object(Path, "open", new=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            receipt = raised.exception.provider_receipt
            self.assertEqual(receipt["status"], "timeout-unknown-provider-state")
            self.assertIn("TimeoutExpired", receipt["dispatch_error"])
            self.assertIn("fence denied", receipt["fence_persistence_error"])
            self.assertIs(raised.exception.__cause__, timeout)
            self.assertFalse((self.client.artifacts / "UNKNOWN_CALL.json").exists())
            self.assert_fenced(invoked)

    def test_both_fence_and_receipt_denied_leave_pending_and_memory_block(self):
        atomic, opening = native._atomic, Path.open
        def receipt_denied(path, value):
            if path.name == "receipt.json":
                raise PermissionError("synthetic receipt denied")
            return atomic(path, value)
        def fence_denied(path, *args, **kwargs):
            if path.name == "UNKNOWN_CALL.json":
                raise PermissionError("synthetic fence denied")
            return opening(path, *args, **kwargs)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, \
                patch.object(native, "_atomic", side_effect=receipt_denied), patch.object(Path, "open", new=fence_denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            self.assertIn("receipt_persistence_error", raised.exception.provider_receipt)
            self.assertIn("fence_persistence_error", raised.exception.provider_receipt)
            self.assertTrue(self.client._dispatch_blocked)
            self.assert_fenced(invoked)

    def test_persisted_unconfirmed_receipt_blocks_fresh_client_when_result_exists_and_global_fence_failed(self):
        atomic, opening = native._atomic, Path.open
        def uncertain_receipt(path, value):
            atomic(path, value)
            if path.name == "receipt.json" and value.get("status") == "completed":
                raise PermissionError("synthetic receipt commit acknowledgement lost")
        def fence_denied(path, *args, **kwargs):
            if path.name == "UNKNOWN_CALL.json":
                raise PermissionError("synthetic global fence denied")
            return opening(path, *args, **kwargs)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, \
                patch.object(native, "_atomic", side_effect=uncertain_receipt), patch.object(Path, "open", new=fence_denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            directory = next((self.client.artifacts / "calls").iterdir())
            self.assertTrue((directory / "result.json").exists())
            self.assertTrue((directory / "receipt.json").exists())
            self.assertFalse((self.client.artifacts / "UNKNOWN_CALL.json").exists())
            durable = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(durable["dispatch_evidence_unconfirmed"])
            self.assertEqual(durable["status"], "post-dispatch-evidence-unconfirmed")
            self.assert_fenced(invoked)

    def test_lost_completed_receipt_ack_and_denied_failure_fences_retain_predispatch_lock(self):
        atomic, opening = native._atomic, Path.open
        def receipt_lost_ack(path, value):
            if path.name == "receipt.json":
                if value.get("status") == "completed":
                    atomic(path, value)
                    raise PermissionError("synthetic completed receipt acknowledgement lost")
                raise PermissionError("synthetic failed receipt rewrite denied before write")
            return atomic(path, value)
        def fence_denied(path, *args, **kwargs):
            if path.name == "UNKNOWN_CALL.json":
                raise PermissionError("synthetic global fence denied")
            return opening(path, *args, **kwargs)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, \
                patch.object(native, "_atomic", side_effect=receipt_lost_ack), patch.object(Path, "open", new=fence_denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            self.assertEqual(raised.exception.provider_receipt["status"], "post-dispatch-evidence-unconfirmed")
            directory = next((self.client.artifacts / "calls").iterdir())
            self.assertTrue((directory / "result.json").exists())
            durable = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(durable["status"], "completed")
            self.assertNotIn("dispatch_evidence_unconfirmed", durable)
            self.assertFalse((self.client.artifacts / "UNKNOWN_CALL.json").exists())
            self.assertTrue((self.client.artifacts / ".native-dispatch.lock").exists())
            self.assert_fenced(invoked)

    def test_no_completed_usage_remains_unknown_after_raw_failure(self):
        original = Path.write_bytes
        def denied(path, data):
            if path.name == "stdout.raw":
                raise PermissionError("synthetic raw denied")
            return original(path, data)
        with patch.object(native.subprocess, "run", return_value=completed(usage=False)) as invoked, patch.object(Path, "write_bytes", new=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertIsNone(raised.exception.usage)
            self.assertIsNone(raised.exception.provider_receipt["usage"])
            self.assert_fenced(invoked)

    def test_duplicate_completed_usage_is_not_summed_after_persistence_failure(self):
        original = native._atomic
        def denied(path, value):
            if path.name == "receipt.json":
                raise PermissionError("synthetic receipt denied")
            return original(path, value)
        with patch.object(native.subprocess, "run", return_value=completed(duplicate=True)) as invoked, patch.object(native, "_atomic", side_effect=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertIsNone(raised.exception.usage)
            self.assertIn("receipt_persistence_error", raised.exception.provider_receipt)
            self.assert_fenced(invoked)

    def test_lock_cleanup_failure_is_failed_known_cost_evidence(self):
        original = Path.unlink
        def denied(path, *args, **kwargs):
            if path.name == ".native-dispatch.lock":
                raise PermissionError("synthetic cleanup denied")
            return original(path, *args, **kwargs)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, patch.object(Path, "unlink", new=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            self.assertEqual(raised.exception.provider_receipt["status"], "dispatch-lock-cleanup-failed")
            self.assertTrue((self.client.artifacts / ".native-dispatch.lock").exists())
            self.assert_fenced(invoked)

    def test_cleanup_failure_does_not_replace_original_known_cli_failure(self):
        original = Path.unlink
        def denied(path, *args, **kwargs):
            if path.name == ".native-dispatch.lock":
                raise PermissionError("synthetic cleanup denied")
            return original(path, *args, **kwargs)
        with patch.object(native.subprocess, "run", return_value=completed(exit_code=1)) as invoked, patch.object(Path, "unlink", new=denied):
            with self.assertRaises(native.NativeCallError) as raised:
                self.call()
            self.assertIn("native response failed", str(raised.exception))
            self.assertEqual(raised.exception.usage["total_tokens"], 57)
            self.assertEqual(raised.exception.provider_receipt["exit_code"], 1)
            self.assertEqual(raised.exception.provider_receipt["status"], "failed-native-response")
            self.assertIn("cleanup denied", raised.exception.provider_receipt["dispatch_lock_cleanup_error"])
            self.assert_fenced(invoked)

    def test_budgeted_backend_charges_known_persistence_failure_once_with_zero_retries(self):
        original = Path.write_bytes
        def denied(path, data):
            if path.name == "stdout.raw":
                raise PermissionError("synthetic raw denied")
            return original(path, data)
        budget = Budget(max_calls=80, max_total_tokens=1500000, max_seconds=7200)
        backend = BudgetedBackend(self.client.backend, budget, max_retries=0)
        with patch.object(native.subprocess, "run", return_value=completed()) as invoked, patch.object(Path, "write_bytes", new=denied):
            with self.assertRaises(native.NativeCallError):
                backend(system="fixture", user="fixed synthetic feedback", max_completion_tokens=100, stage="analyst")
        self.assertEqual(budget.calls, 1)
        self.assertEqual(budget.total_tokens, 57)
        self.assertFalse(budget.unknown_usage)
        self.assertEqual(len(budget.records), 1)
        self.assertEqual(invoked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
