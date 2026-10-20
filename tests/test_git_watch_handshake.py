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

    def close(self):
        pass


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
        return WATCH._view({"desired_running": True, "token": "worker-token", "pid": worker_pid,
                            "status": worker_status, "lease_until": time.time() + 120,
                            "supervisor": {"enabled": True, "token": "supervisor-token",
                                           "pid": supervisor_pid, "status": supervisor_status}})

    def launch(self, read, existing=False, guard_state=None):
        self.stack.enter_context(mock.patch.object(WATCH, "status", side_effect=read))
        def acquire(root, name):
            if name == ".upg-supervisor.guard":
                return None if existing else Guard()
            if guard_state is not None:
                return guard_state(name)
            return None if name == ".upg-worker.guard" else Guard()
        self.stack.enter_context(mock.patch.object(WATCH.guards, "acquire", side_effect=acquire))
        reserved = self.view()
        reserved["watcher"]["token"] = "previous-worker-token"
        self.reserve = self.stack.enter_context(mock.patch.object(
            WATCH, "_reserve_supervisor", return_value=(reserved, "supervisor-token")))
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

    def test_new_supervisor_never_accepts_previous_workers_unexpired_lease(self):
        def read(root):
            value = self.view(21, 22, "idle", "watching")
            if self.clock.now < .2:
                value["watcher"]["token"] = "previous-worker-token"
            return value
        result = self.launch(read)
        self.assertEqual(result["watcher"]["token"], "worker-token")
        self.assertGreaterEqual(self.clock.now, .2)
        self.assertTrue(result["watcher"]["running"])

    def test_orphan_native_validation_defers_instead_of_accepting_old_live_lease(self):
        for busy in [".upg-validation.guard", ".upg-checkpoint.guard"]:
            with self.subTest(busy=busy):
                owned = self.view(21, 22, "validating", "watching")
                owned["watcher"].update(token="previous-worker-token", lease_until=time.time() + 2400)
                result = self.launch(lambda root: copy.deepcopy(owned), guard_state=lambda name: None if name == busy else Guard())
                self.assertEqual(result["watcher"]["token"], "previous-worker-token")
                self.assertIn("deferred; native project command still active", result["watcher"]["recovery"])
                self.assertFalse(result["watcher"]["running"])
                self.assertEqual(self.clock.now, 0)

    def test_existing_supervisor_cannot_accept_dead_workers_free_native_guard(self):
        def read(root):
            value = self.view(21, 22, "idle", "watching")
            if self.clock.now < .2:
                value["watcher"]["token"] = "previous-worker-token"
            return value
        def acquire(name):
            if name == ".upg-worker.guard" and self.clock.now >= .2:
                return None
            return Guard()
        result = self.launch(read, existing=True, guard_state=acquire)
        self.assertEqual(result["watcher"]["token"], "worker-token")
        self.assertGreaterEqual(self.clock.now, .2)
        self.spawn.assert_not_called()

    def test_waiting_supervisor_takes_precedence_over_fresh_live_lease(self):
        result = self.launch(lambda root: self.view(21, 22, "idle", "waiting"), existing=True)
        self.assertIn("deferred", result["watcher"]["recovery"])
        self.assertFalse(result["watcher"]["running"])
        self.assertEqual(self.clock.now, 0)

    def test_recovering_supervisor_does_not_treat_reservation_guard_as_old_live_worker(self):
        def read(root):
            if self.clock.now < .2:
                return self.view(21, 22, "idle", "recovering")
            return self.view(21, 23, "running", "watching")
        result = self.launch(read, existing=True)
        self.assertEqual(result["watcher"]["pid"], 23)
        self.assertGreaterEqual(self.clock.now, .2)
        self.assertTrue(result["watcher"]["running"])

    def test_recovery_barrier_published_during_guard_probe_invalidates_old_snapshot(self):
        reads = []
        def read(root):
            reads.append(self.clock.now)
            if len(reads) == 1:
                value = self.view(21, 22, "idle", "watching")
                value["watcher"]["token"] = "previous-worker-token"
                return value
            if len(reads) == 2:
                return self.view(21, 22, "idle", "recovering")
            return self.view(21, 23, "running", "watching")
        result = self.launch(read, existing=True)
        self.assertEqual(result["watcher"]["pid"], 23)
        self.assertEqual(result["watcher"]["token"], "worker-token")
        self.assertGreater(self.clock.now, 0)
        self.assertTrue(result["watcher"]["running"])

    def test_busy_recovery_publication_prevents_replacement_launch_and_uses_backoff(self):
        child = mock.Mock()
        launched = mock.Mock(return_value=(self.view(21, 22, "running", "watching"), child))
        progress = mock.Mock(side_effect=ValueError("project state writer busy; fixture"))
        with mock.patch.object(WATCH.guards, "acquire", return_value=Guard()), \
                mock.patch.object(WATCH, "_claim_supervisor", return_value=True), \
                mock.patch.object(WATCH, "_supervisor_owned", side_effect=lambda *args: self.clock.now < 2), \
                mock.patch.object(WATCH, "_launch", launched), \
                mock.patch.object(WATCH, "_supervisor_progress", progress), \
                mock.patch.object(WATCH, "_supervisor_diagnostic"):
            self.assertEqual(WATCH.supervise(self.root, "supervisor-token"), 0)
        launched.assert_called_once()
        child.wait.assert_called_once()
        progress.assert_called_once_with(self.root, "supervisor-token", "recovering", "native-worker-exited")
        self.assertGreaterEqual(self.clock.now, 2)

    def test_supervision_pending_does_not_fabricate_worker_heartbeat_expiration(self):
        for supervisor_status in ["starting", "recovering", "waiting", "blocked"]:
            with self.subTest(supervisor_status=supervisor_status):
                value = self.view(21, 22, "idle", supervisor_status)["watcher"]
                self.assertFalse(value["running"])
                self.assertEqual(value["status"], "idle")
                self.assertNotIn("worker-heartbeat-expired", value.get("reason", ""))
                self.assertGreater(value["lease_until"], time.time())

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
                        ("running", "recovering", False), ("running", "waiting", False),
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
