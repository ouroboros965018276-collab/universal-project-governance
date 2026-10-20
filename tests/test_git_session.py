"""Necessary native session boundaries; no system startup or model execution."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest import mock

import test_git_watch as fixture

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "governance-src/runtime-scripts"
SPEC = importlib.util.spec_from_file_location("session_lifetime_test_runtime", RUNTIME / "session_lifetime.py")
LIFETIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIFETIME)


@unittest.skipUnless(fixture.shutil.which("git"), "real Git executable required")
class GitSessionTests(unittest.TestCase):
    setUp = fixture.GitWatchTests.setUp
    cleanup = fixture.GitWatchTests.cleanup
    write = fixture.GitWatchTests.write
    git = fixture.GitWatchTests.git
    cli = fixture.GitWatchTests.cli
    watch = fixture.GitWatchTests.watch
    configure = fixture.GitWatchTests.configure
    count = fixture.GitWatchTests.count
    validator_count = fixture.GitWatchTests.validator_count
    wait_for = fixture.GitWatchTests.wait_for
    state = fixture.GitWatchTests.state
    start_session = fixture.GitWatchTests.start_session
    finish_session = fixture.GitWatchTests.finish_session
    close_sessions = fixture.GitWatchTests.close_sessions

    def test_no_session_start_recover_and_ensure_never_spawn_or_validate(self):
        self.configure()
        before = self.state()
        self.write("source.txt", "eligible edit outside an editor session\n")
        denied = self.watch("start", expected=(2,))
        self.assertIn(b"session-required", denied.stdout)
        recovered = self.watch("recover", expected=(0,))["watcher"]
        self.assertFalse(recovered.get("running"))
        self.assertFalse(recovered.get("pid"))
        self.cli("ensure", str(self.root))
        after = self.state()
        self.assertFalse(after.get("pid"))
        self.assertFalse(after.get("supervisor", {}).get("pid"))
        self.assertEqual(after.get("desired_running"), before.get("desired_running"))
        self.assertEqual(after["generation"], before["generation"])
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.validator_count(), 0)
        # Explicit synchronous work is still available without a resident owner.
        self.assertEqual(self.watch("tick")["watcher"]["status"], "committed")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        self.assertEqual(self.watch("tick")["watcher"]["status"], "idle")
        self.assertEqual(self.count(), 2)

    def test_normal_host_end_releases_observers_and_next_project_session_recovers(self):
        self.configure()
        record = self.start_session()
        first = self.state()
        self.write("source.txt", "first session verified stage\n")
        self.wait_for(lambda: self.count() == 2, timeout=60)
        self.finish_session(record)
        stopped = self.state()
        self.assertTrue(stopped["desired_running"], "normal host exit preserves future on-demand intent")
        self.assertFalse(stopped.get("pid"))
        self.assertFalse(stopped.get("supervisor", {}).get("pid"))
        self.write("source.txt", "later source requires a new foreground session\n")
        self.cli("ensure", str(self.root))
        time.sleep(1.1)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        resumed = self.start_session()
        second = self.state()
        self.assertNotEqual(second["session"]["token"], first["session"]["token"])
        self.assertNotEqual(second["supervisor"]["token"], first["supervisor"]["token"])
        self.wait_for(lambda: self.count() == 3, timeout=60)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"later source requires a new foreground session\n")
        # Commit visibility is not completion of the live publisher's writer
        # section. End the resumed session before the finite deduplication tick.
        self.finish_session(resumed)
        before_tick_head = self.git("rev-parse", "HEAD")
        tick = self.watch("tick")
        self.assertIn(tick["watcher"]["status"], ("idle", "committed", "duplicate", "unchanged"), tick)
        self.assertEqual(self.git("rev-parse", "HEAD"), before_tick_head)
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.validator_count(), 2)
        self.assertEqual(self.count(), 3)

    def test_abrupt_owner_exit_stops_native_validation_tree_without_publishing(self):
        self.write(".governance/validation-child.py", "import os,sys,time\nfrom pathlib import Path\n"
                   "p=Path(sys.argv[1])\n(p/'validator-child-pid').write_text(str(os.getpid()))\n"
                   "deadline=time.monotonic()+90\n"
                   "while not (p/'release-validator').exists() and time.monotonic()<deadline:\n time.sleep(.03)\n"
                   "(p/'validator-child-finished').touch()\n")
        self.write(".governance/validate.py", "import json,os,subprocess,sys,time\nfrom pathlib import Path\n"
                   "p=Path(__file__).parent\n"
                   "child=subprocess.Popen([sys.executable,str(p/'validation-child.py'),str(p)])\n"
                   "(p/'native-validation-pids.json').write_text(json.dumps({'validator':os.getpid(),'wrapper':os.getppid(),'child':child.pid}))\n"
                   "child.wait()\n(p/'validator-finished').touch()\n")
        configuration = dict(self.configuration, validators=[{
            "argv": [sys.executable, str(self.root / ".governance/validate.py")], "timeout_seconds": 90}])
        self.watch("configure", configuration, expected=(0,))
        record = self.start_session()
        self.write("source.txt", "unpublished candidate from cancelled project session\n")
        marker = self.root / ".governance/native-validation-pids.json"
        self.wait_for(lambda: marker.exists() and (self.root / ".governance/validator-child-pid").exists(), timeout=40)
        pids = json.loads(marker.read_text())
        self.assertEqual(pids["child"], int((self.root / ".governance/validator-child-pid").read_text()))
        observations = [fixture.ProcessObservation(pid) for pid in pids.values()]
        record["observations"].extend(observations)
        self.assertTrue(all(not item.exited() for item in observations))
        owner = record["process"]
        owner.kill()  # The fixture owns this actual Popen, never a recorded PID.
        owner.wait(timeout=10)
        record["owner_killed"] = True
        self.assertIsNotNone(owner.returncode)
        for item in record["observations"]:
            self.wait_for(item.exited, timeout=10)
        self.assertFalse((self.root / ".governance/validator-finished").exists())
        self.assertFalse((self.root / ".governance/validator-child-finished").exists())
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"fixture baseline\n")
        # Native guard availability proves no hidden wrapper still owns work.
        spec = importlib.util.spec_from_file_location("session_exit_guards", RUNTIME / "process_guard.py")
        guards = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guards)
        for name in [".upg-session.guard", ".upg-supervisor.guard", ".upg-worker.guard", ".upg-validation.guard", ".upg-checkpoint.guard"]:
            with self.subTest(guard=name):
                guard = guards.acquire(self.root, name)
                self.assertIsNotNone(guard, name)
                guard.close()
        self.write(".governance/release-validator", "late release cannot authorize old bytes\n")
        self.cli("ensure", str(self.root))
        time.sleep(.4)
        self.assertEqual(self.count(), 1)
        self.finish_session(record, expected=(-9, 1))


class SessionAuthorityTests(unittest.TestCase):
    def test_absent_or_invalid_native_authority_cannot_be_joined(self):
        with mock.patch.object(LIFETIME, "_CURRENT", None), mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(LIFETIME.join_from_environment())
            self.assertFalse(LIFETIME.active())
            with self.assertRaisesRegex(ValueError, "foreground project session"):
                LIFETIME.spawn([sys.executable, str(RUNTIME / "git_watch.py")])
        with mock.patch.object(LIFETIME, "_CURRENT", None), mock.patch.dict(os.environ, {LIFETIME._ENV: '{}'}, clear=True):
            with self.assertRaisesRegex(ValueError, "invalid inherited"):
                LIFETIME.join_from_environment()

    def test_internal_command_identity_and_root_are_bounded_before_spawn(self):
        for command in [["external-editor", str(RUNTIME / "git_watch.py")],
                        [sys.executable, str(ROOT / "unreviewed.py")], []]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                LIFETIME._argv(command, internal=True)
        with self.assertRaisesRegex(ValueError, "existing directory"):
            LIFETIME.Session(ROOT / "eval-workspaces/nonexistent-session-owner-root")


if __name__ == "__main__":
    unittest.main()
