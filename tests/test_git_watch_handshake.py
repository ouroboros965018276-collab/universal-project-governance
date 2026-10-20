"""Deterministic startup handshake boundaries; no startup tasks or model calls."""
import contextlib
import copy
import importlib
import io
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "governance-src/runtime-scripts"
# Exercise the canonical functions before compilation without contaminating the
# runtime modules used by other tests in this same discovery process.
with mock.patch.dict(sys.modules):
    for name in ("git_watch", "project_tool", "git_checkpoint", "process_guard", "state_tool", "project_facts"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(SOURCE))
    try:
        WATCH = importlib.import_module("git_watch")
    finally:
        sys.path.pop(0)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Guard:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class GitWatchHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.root = ROOT / "eval-workspaces/unused-handshake-root"
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(WATCH.time, "monotonic", self.clock.monotonic))
        self.stack.enter_context(mock.patch.object(WATCH.time, "sleep", self.clock.sleep))
        self.stack.enter_context(mock.patch.object(WATCH.project, "project_root", lambda value: value))

    def view(self, supervisor_pid=None, worker_pid=None, worker_status="starting", supervisor_status="starting"):
        return {"watcher": {"desired_running": True, "token": "worker-token", "pid": worker_pid,
                            "status": worker_status, "lease_until": time.time() + 120,
                            "supervisor": {"enabled": True, "token": "supervisor-token",
                                           "pid": supervisor_pid, "status": supervisor_status}}}

    def launch(self, read, existing=False):
        self.stack.enter_context(mock.patch.object(WATCH, "status", side_effect=read))
        self.stack.enter_context(mock.patch.object(WATCH.guards, "acquire", return_value=None if existing else Guard()))
        self.reserve = self.stack.enter_context(mock.patch.object(
            WATCH, "_reserve_supervisor", return_value=(self.view(), "supervisor-token")))
        self.spawn = self.stack.enter_context(mock.patch.object(WATCH, "_spawn_supervisor"))
        return WATCH._launch_supervisor(self.root)

    def test_late_supervisor_confirmation_does_not_consume_worker_handshake(self):
        def read(root):
            if self.clock.now < 7.9:
                return self.view()
            if self.clock.now < 15.8:
                return self.view(supervisor_pid=21, supervisor_status="watching")
            return self.view(supervisor_pid=21, worker_pid=22, worker_status="running", supervisor_status="watching")
        result = self.launch(read)
        self.assertEqual(result["watcher"]["pid"], 22)
        self.assertTrue(WATCH._live(result["watcher"]))
        self.assertGreater(self.clock.now, 15)
        self.assertLessEqual(self.clock.now, 18)
        self.spawn.assert_called_once()

    def test_existing_supervisor_waits_for_worker_and_does_not_spawn_again(self):
        def read(root):
            return self.view(supervisor_pid=21, worker_pid=22 if self.clock.now >= 9 else None,
                             worker_status="running" if self.clock.now >= 9 else "starting",
                             supervisor_status="watching")
        result = self.launch(read, existing=True)
        self.assertTrue(WATCH._live(result["watcher"]))
        self.assertTrue(result["watcher"]["idempotent"])
        self.assertGreaterEqual(self.clock.now, 9)
        self.reserve.assert_not_called()
        self.spawn.assert_not_called()

    def test_existing_confirmed_worker_is_immediate_and_idempotent(self):
        result = self.launch(lambda root: self.view(21, 22, "idle", "watching"), existing=True)
        self.assertTrue(WATCH._live(result["watcher"]))
        self.assertTrue(result["watcher"]["idempotent"])
        self.assertEqual(self.clock.now, 0)
        self.spawn.assert_not_called()

    def test_real_native_owner_defer_is_immediate(self):
        result = self.launch(lambda root: self.view(21, None, "starting", "waiting"), existing=True)
        self.assertIn("deferred; native project command still active", result["watcher"]["recovery"])
        self.assertEqual(result["watcher"]["supervisor"]["status"], "waiting")
        self.assertEqual(self.clock.now, 0)
        self.spawn.assert_not_called()

    def test_supervisor_timeout_is_bounded_without_mutating_ownership(self):
        owned = self.view()
        before = copy.deepcopy(owned)
        result = self.launch(lambda root: owned)
        self.assertEqual(self.clock.now, 8)
        self.assertEqual(result["watcher"]["supervisor"]["status"], "blocked")
        self.assertEqual(result["watcher"]["supervisor"]["reason"], "native-supervised-startup-not-confirmed")
        self.assertIn("deferred", result["watcher"]["recovery"])
        self.assertEqual(owned, before)
        self.assertTrue(result["watcher"]["desired_running"])
        self.assertEqual(result["watcher"]["token"], "worker-token")

    def test_worker_phase_timeout_is_bounded_and_starting_pid_is_not_confirmation(self):
        def read(root):
            return self.view(None if self.clock.now < 7.9 else 21, 22,
                             "starting", "starting" if self.clock.now < 7.9 else "watching")
        result = self.launch(read)
        self.assertLessEqual(self.clock.now, 18)
        self.assertGreater(self.clock.now, 17)
        self.assertFalse(WATCH._live(result["watcher"]))
        self.assertEqual(result["watcher"]["supervisor"]["status"], "blocked")

    def test_direct_recover_reports_unconfirmed_startup_as_failure_but_preserves_real_defer(self):
        for state, expected in [(self.view(21, None, "starting", "blocked"), 1),
                                (self.view(21, None, "starting", "waiting"), 0),
                                (self.view(21, 22, "blocked", "watching"), 1)]:
            with self.subTest(expected=expected, state=state):
                with mock.patch.object(WATCH, "recover", return_value=state), \
                        mock.patch.object(sys, "argv", ["git_watch.py", "--recover", str(self.root)]), \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(WATCH.main(), expected)


class GitWatchStartingStatusTests(unittest.TestCase):
    def test_valid_binding_reports_each_unconfirmed_phase_pending_then_confirmed_healthy(self):
        project = WATCH.project
        parent = ROOT / "eval-workspaces"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="git-handshake-state-", dir=parent) as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(root.parent, parent.resolve())
            with mock.patch.object(project, "ROOT", ROOT / "universal-project-governance"), \
                    mock.patch.dict(sys.modules, {"git_watch": WATCH}):
                binding = project.expected_binding()
                policy = binding["git_checkpoint"]
                policy.update(enabled=True, allowed_paths=["."])
                configuration = {"enabled": True, "poll_seconds": 1, "quiet_seconds": 0,
                                 "validators": [{"argv": [sys.executable, "-c", "pass"], "timeout_seconds": 1}]}
                for worker_status, supervisor_status, expected_ok in [
                        ("configured", "starting", False), ("starting", "watching", False),
                        ("running", "watching", True)]:
                    policy["watcher"] = {"configuration": configuration, "desired_running": True,
                                         "status": worker_status, "token": "owned-worker", "pid": 22,
                                         "lease_until": time.time() + 120,
                                         "supervisor": {"enabled": True, "status": supervisor_status,
                                                        "token": "owned-supervisor", "pid": 21}}
                    project.write_json_atomic(root / ".governance/upg.json", binding)
                    actual = project.status(root)
                    self.assertEqual(actual["ok"], expected_ok, actual)
                    if not expected_ok:
                        self.assertEqual(actual["reason"], "git-watcher-pending")


if __name__ == "__main__":
    unittest.main()
