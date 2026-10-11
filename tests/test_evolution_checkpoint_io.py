"""Windows checkpoint replacement failures retry only persisted bytes."""
import contextlib
import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import call, patch

SUPPORTED = sys.version_info >= (3, 10)
ROOT = Path(__file__).resolve().parents[1]
if SUPPORTED:
    from evolution import controller
    from evolution.controller import save_run


def permission_error(code):
    error = PermissionError("synthetic Windows atomic replacement denial")
    if code is not None:
        error.winerror = code
    return error


def serialized_checkpoint(run):
    text = json.dumps(run, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    return text.replace("\n", os.linesep).encode("utf-8")


@unittest.skipUnless(SUPPORTED, "optional offline evolution requires Python 3.10+")
class CheckpointReplacementTests(unittest.TestCase):
    def protocol(self):
        return {"schema_version": 1, "seed": 1729, "model": "synthetic-unit-model",
                "budget": {"model_calls": 20, "tokens": 100000, "wall_seconds": 120, "candidates": 4},
                "search": {"iterations": 1, "population": 4, "retries": 0},
                "tasks": {"training": [{"id": "train"}], "selection": [{"id": "selection"}],
                          "final": [{"id": "untouched-final"}]}}

    @contextlib.contextmanager
    def controller_engine(self):
        with patch.object(controller, "validate_candidate", return_value={"ok": True, "errors": [], "context_bytes": 1000}), \
             patch.object(controller, "source_hash", return_value="unit-source"), \
             patch.object(controller, "engine_identity", return_value="unit-engine"):
            yield

    def measured_runner(self, requests):
        def runner(request):
            requests.append(request)
            return {"status": "completed", "provider_receipt": "synthetic-unit-receipt",
                    "usage": {"total_tokens": 7}, "outcome": {"hard": 1, "soft": 1, "loss": 1}}
        return runner

    def test_windows_transient_denial_retries_same_fsynced_bytes_then_succeeds(self):
        for code in (5, 32, 33):
            with self.subTest(winerror=code), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "run.json"
                target.write_bytes(b'{"old":true}\n')
                run = {"status": "running", "observations": [{"usage": {"total_tokens": 17}}]}
                expected = serialized_checkpoint(run)
                original_replace = Path.replace
                attempted_bytes = []
                def replace(source, destination):
                    self.assertEqual(destination, target)
                    attempted_bytes.append(source.read_bytes())
                    if len(attempted_bytes) < 3:
                        raise permission_error(code)
                    return original_replace(source, destination)
                with patch("evolution.controller.sys.platform", "win32"), \
                     patch("evolution.controller.Path.replace", autospec=True, side_effect=replace), \
                     patch("evolution.controller.time.sleep") as sleep, patch("os.fsync") as fsync:
                    save_run(target, run)
                self.assertEqual(attempted_bytes, [expected] * 3)
                self.assertEqual(target.read_bytes(), expected)
                self.assertFalse(target.with_suffix(".json.tmp").exists())
                self.assertEqual(sleep.call_args_list, [call(0.02), call(0.04)])
                fsync.assert_called_once()

    def test_persistent_windows_denial_preserves_old_target_and_complete_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run.json"
            old = b'{"old":true}\n'
            target.write_bytes(old)
            run = {"status": "running", "provider_attempts": [{"actual_tokens": 17}]}
            expected = serialized_checkpoint(run)
            attempted_bytes = []
            error = permission_error(5)
            def replace(source, destination):
                attempted_bytes.append(source.read_bytes())
                raise error
            rng_before = random.getstate()
            with patch("evolution.controller.sys.platform", "win32"), \
                 patch("evolution.controller.Path.replace", autospec=True, side_effect=replace), \
                 patch("evolution.controller.time.sleep") as sleep:
                with self.assertRaises(PermissionError) as raised:
                    save_run(target, run)
            self.assertIs(raised.exception, error)
            self.assertEqual(target.read_bytes(), old)
            self.assertEqual(target.with_suffix(".json.tmp").read_bytes(), expected)
            self.assertEqual(attempted_bytes, [expected] * 6)
            self.assertEqual(sleep.call_args_list, [call(0.02), call(0.04), call(0.08), call(0.16), call(0.24)])
            self.assertLessEqual(sum(args.args[0] for args in sleep.call_args_list), 0.6)
            self.assertEqual(random.getstate(), rng_before)

    def test_non_windows_or_unrecognized_permission_error_is_not_retried(self):
        for platform, code in (("linux", 32), ("darwin", 5), ("win32", None), ("win32", 87)):
            with self.subTest(platform=platform, winerror=code), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "run.json"
                old = b'{"old":true}\n'
                target.write_bytes(old)
                error = permission_error(code)
                with patch("evolution.controller.sys.platform", platform), \
                     patch("evolution.controller.Path.replace", autospec=True, side_effect=error) as replace, \
                     patch("evolution.controller.time.sleep") as sleep:
                    with self.assertRaises(PermissionError) as raised:
                        save_run(target, {"new": True})
                self.assertIs(raised.exception, error)
                replace.assert_called_once()
                sleep.assert_not_called()
                self.assertEqual(target.read_bytes(), old)
                self.assertEqual(json.loads(target.with_suffix(".json.tmp").read_text(encoding="utf-8")), {"new": True})

    def test_other_replacement_errors_propagate_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run.json"
            error = OSError("synthetic non-permission replacement failure")
            with patch("evolution.controller.sys.platform", "win32"), \
                 patch("evolution.controller.Path.replace", autospec=True, side_effect=error) as replace, \
                 patch("evolution.controller.time.sleep") as sleep:
                with self.assertRaises(OSError) as raised:
                    save_run(target, {"new": True})
            self.assertIs(raised.exception, error)
            replace.assert_called_once()
            sleep.assert_not_called()
            self.assertFalse(target.exists())
            self.assertTrue(target.with_suffix(".json.tmp").exists())

    def test_controller_persistent_checkpoint_denial_does_not_write_failure_again(self):
        requests, learning, denied_bytes, old_target = [], [], [], []
        error = permission_error(5)
        original_replace = Path.replace
        def backend(**request):
            learning.append(request)
            self.fail("checkpoint failure must stop before another model dispatch")
        def replace(source, destination):
            if requests:
                if not denied_bytes:
                    old_target.append(destination.read_bytes())
                denied_bytes.append(source.read_bytes())
                raise error
            return original_replace(source, destination)
        with tempfile.TemporaryDirectory() as directory, self.controller_engine():
            target = Path(directory) / "run.json"
            with patch("evolution.controller.sys.platform", "win32"), \
                 patch("evolution.controller.Path.replace", autospec=True, side_effect=replace), \
                 patch("evolution.controller.time.sleep") as sleep, \
                 patch.object(controller, "save_run", wraps=save_run) as save:
                with self.assertRaises(PermissionError) as raised:
                    controller.run_search(ROOT, self.protocol(), target,
                                          runner=self.measured_runner(requests), backend=backend)
            self.assertIs(raised.exception, error)
            self.assertEqual(save.call_count, 2)  # Initial fence, then one failed receipt checkpoint.
            self.assertEqual(len(denied_bytes), 6)
            self.assertEqual(denied_bytes, [denied_bytes[0]] * 6)
            self.assertEqual(sleep.call_args_list, [call(0.02), call(0.04), call(0.08), call(0.16), call(0.24)])
            self.assertLessEqual(sum(args.args[0] for args in sleep.call_args_list), 0.6)
            self.assertEqual(target.read_bytes(), old_target[0])
            self.assertEqual(target.with_suffix(".json.tmp").read_bytes(), denied_bytes[0])
            retained = json.loads(denied_bytes[0])
            self.assertEqual(retained["status"], "running")
            self.assertIsNone(retained["pending"])
            self.assertEqual(retained["budget"]["calls"], 1)
            self.assertEqual(retained["budget"]["total_tokens"], 7)
            self.assertEqual(len(retained["cache"]), 1)
            self.assertFalse(any(event["kind"] == "failure" for event in retained["events"]))
        self.assertEqual([request["task"]["id"] for request in requests], ["train"])
        self.assertEqual(learning, [])

    def test_backend_permission_error_still_checkpoints_business_failure(self):
        requests, learning = [], []
        error = permission_error(5)
        error.usage = {"total_tokens": 3}
        def backend(**request):
            learning.append(request)
            raise error
        with tempfile.TemporaryDirectory() as directory, self.controller_engine(), \
             contextlib.redirect_stderr(io.StringIO()):
            target = Path(directory) / "run.json"
            with self.assertRaises(PermissionError) as raised:
                controller.run_search(ROOT, self.protocol(), target,
                                      runner=self.measured_runner(requests), backend=backend,
                                      disabled=("annealing", "de", "curvature"))
            retained = json.loads(target.read_text(encoding="utf-8"))
            self.assertIs(raised.exception, error)
            self.assertEqual(retained["status"], "failed")
            self.assertEqual(retained["events"][-1]["error"], "PermissionError")
            self.assertEqual(retained["budget"]["calls"], 2)
            self.assertEqual(retained["budget"]["total_tokens"], 10)
            self.assertFalse(retained["budget"]["unknown_usage"])
            self.assertFalse(target.with_suffix(".json.tmp").exists())
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(learning), 1)

    def test_validation_failure_still_saves_failed_state(self):
        error = ValueError("synthetic business validation failure")
        with tempfile.TemporaryDirectory() as directory, self.controller_engine(), \
             patch.object(controller, "validate_candidate", side_effect=error):
            target = Path(directory) / "run.json"
            with self.assertRaises(ValueError) as raised:
                controller.run_search(ROOT, self.protocol(), target, disabled=controller.OPERATORS)
            retained = json.loads(target.read_text(encoding="utf-8"))
            self.assertIs(raised.exception, error)
            self.assertEqual(retained["status"], "failed")
            self.assertEqual(retained["events"][-1]["error"], "ValueError")
            self.assertEqual(retained["budget"]["calls"], 0)
            self.assertEqual(retained["candidates"], [])


if __name__ == "__main__":
    unittest.main()
