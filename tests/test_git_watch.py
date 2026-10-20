"""Bounded real-Git and native-worker checks; no external model calls."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from registration_fixture import change

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "universal-project-governance/scripts/project_tool.py"


@unittest.skipUnless(shutil.which("git"), "real Git executable required")
class GitWatchTests(unittest.TestCase):
    def setUp(self):
        self.parent = (ROOT / "eval-workspaces").resolve()
        self.parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="git-watch-", dir=self.parent)
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.cleanup)
        self.git("init", "--template=", "--quiet")
        for key, value in [("user.name", "UPG local watch calibration"),
                           ("user.email", "watch-calibration@example.invalid"),
                           ("core.autocrlf", "false"), ("commit.gpgSign", "false"),
                           ("core.hooksPath", str(self.root / ".git/hooks"))]:
            self.git("config", key, value)
        self.write(".gitignore", ".governance/\n")
        self.write("source.txt", "fixture baseline\n")
        self.write("owner.txt", "owner baseline\n")
        self.write("PROJECT_STATE.md", "fixture state\n")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "watch fixture baseline")
        self.cli("git-configure", str(self.root), "--enable", "--allow-path", ".",
                 "--status-path", "PROJECT_STATE.md", "--min-interval-seconds", "0")
        self.write(".governance/validate.py", "from pathlib import Path\n"
                   "p=Path(__file__).parent\n"
                   "counter=p/'validator-count'\n"
                   "counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')\n"
                   "raise SystemExit(0)\n")
        self.configuration = {"enabled": True, "poll_seconds": 1, "quiet_seconds": 0,
                              "validators": [{"argv": [sys.executable, str(self.root / ".governance/validate.py")],
                                              "timeout_seconds": 10}]}
        self.worker_pid = None

    def cleanup(self):
        if Path(self.temporary.name).resolve() != self.root or self.root.parent != self.parent:
            raise AssertionError("refusing cleanup outside owned watch fixture")
        self.temporary.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def git(self, *args):
        process = subprocess.run([shutil.which("git"), *args], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
        return process.stdout

    def cli(self, *args, expected=(0,)):
        process = subprocess.run([sys.executable, str(CLI), *args], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25, check=False)
        self.assertIn(process.returncode, expected, process.stderr.decode("utf-8", "replace") + process.stdout.decode("utf-8", "replace"))
        if process.returncode == 2:
            return process
        return json.loads(process.stdout.decode("utf-8"))

    def watch(self, action, configuration=None, expected=(0, 1)):
        argv = ["git-watch", str(self.root), "--action", action]
        if configuration is not None:
            path = self.root / ".governance/watch-input.json"
            self.write(".governance/watch-input.json", json.dumps(configuration))
            argv += ["--input", str(path)]
        return self.cli(*argv, expected=expected)

    def configure(self, **changes):
        configuration = dict(self.configuration, **changes)
        return self.watch("configure", configuration, expected=(0,))

    def count(self):
        return int(self.git("rev-list", "--count", "HEAD"))

    def validator_count(self):
        path = self.root / ".governance/validator-count"
        return int(path.read_text()) if path.exists() else 0

    def wait_for(self, condition, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.15)
        self.fail("native watcher did not establish the expected observed state within the bounded deadline")

    def start_worker(self):
        self.addCleanup(self.stop_worker)
        started = self.watch("start", expected=(0,))["watcher"]
        self.worker_pid = started.get("pid")
        self.assertTrue(started["running"], started)
        self.assertIsInstance(self.worker_pid, int, started)
        return started

    def stop_worker(self):
        # Observe the exact owned process rather than infer process exit from
        # a status document. Windows uses a read-only synchronization handle.
        handle = None
        kernel = None
        pid = self.worker_pid
        if pid is not None and os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x00100000, False, pid)
            if not handle and ctypes.get_last_error() != 87:
                self.fail("unable to observe owned worker process exit")
        try:
            stopped = self.watch("stop", expected=(0,))["watcher"]
            self.assertFalse(stopped["running"], stopped)
            if handle:
                self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0, "owned native worker must actually exit")
            elif pid is not None and os.name != "nt":
                def gone():
                    stat = Path("/proc") / str(pid) / "stat"
                    if stat.exists():
                        return stat.read_text().split(")", 1)[1].strip().startswith("Z")
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        return True
                    return False
                self.wait_for(gone, timeout=5)
            self.worker_pid = None
        finally:
            if handle:
                kernel.CloseHandle(handle)

    def test_public_tick_saves_external_editor_change_without_begin_finish_or_ledger(self):
        self.configure()
        self.write("source.txt", "external editor verified change\n")
        result = self.watch("tick")["watcher"]
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"external editor verified change\n")
        state = json.loads((self.root / ".governance/upg.json").read_text())
        self.assertNotIn("active_workflow", state)
        self.assertFalse((self.root / ".governance/field-reports.json").exists())
        self.assertEqual(self.watch("tick")["watcher"]["status"], "idle")
        self.write("PROJECT_STATE.md", "status refresh only\n")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "idle")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)

    def test_preexisting_owner_dirty_path_does_not_block_new_eligible_edit(self):
        self.write("owner.txt", "preexisting owner edit\n")
        self.configure()
        self.write("source.txt", "new verified source\n")
        result = self.watch("tick")["watcher"]
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:owner.txt"), b"owner baseline\n")
        self.assertEqual((self.root / "owner.txt").read_bytes(), b"preexisting owner edit\n")
        self.assertEqual(self.git("diff", "--name-only"), b"owner.txt\n")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")

    def test_quiet_boundary_and_minimum_interval_prevent_frequent_commits(self):
        self.cli("git-configure", str(self.root), "--enable", "--min-interval-seconds", "300")
        self.configure(quiet_seconds=1)
        self.write("source.txt", "first transient edit\n")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "waiting")
        self.write("source.txt", "settled meaningful stage\n")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "waiting")
        self.assertEqual(self.validator_count(), 0)
        time.sleep(1.05)
        self.assertEqual(self.watch("tick")["watcher"]["status"], "committed")
        self.write("source.txt", "nearby later edit\n")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "waiting")
        time.sleep(1.05)
        result = self.watch("tick")["watcher"]
        self.assertEqual(result["status"], "cooldown", result)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)

    def test_invalid_or_missing_validator_never_grants_execution(self):
        original = (self.root / ".governance/upg.json").read_bytes()
        invalids = [{"validators": []}, {"quiet_seconds": -1}, {"poll_seconds": 0},
                    {"validators": [{"argv": "shell text", "timeout_seconds": 1}]},
                    {"validators": [{"argv": [sys.executable], "timeout_seconds": 301}]}]
        for mutation in invalids:
            with self.subTest(mutation=mutation):
                self.watch("configure", dict(self.configuration, **mutation), expected=(2,))
                self.assertEqual((self.root / ".governance/upg.json").read_bytes(), original)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.validator_count(), 0)

    def test_validator_failure_and_source_drift_cannot_publish_old_validation(self):
        self.write(".governance/validate.py", "raise SystemExit(1)\n")
        self.configure()
        self.write("source.txt", "candidate requiring validation\n")
        failed = self.watch("tick")["watcher"]
        self.assertEqual(failed["status"], "blocked", failed)
        self.assertEqual(failed["reason"], "project-validator-failed")
        health = self.cli("status", str(self.root), expected=(1,))
        self.assertFalse(health["ok"])
        self.assertEqual(health["reason"], "git-watcher-pending")
        self.assertEqual(self.count(), 1)
        self.write(".governance/validate.py", "from pathlib import Path\n"
                   "(Path(__file__).parent.parent/'source.txt').write_bytes(b'concurrent later source\\n')\n")
        drift = self.watch("tick")["watcher"]
        self.assertEqual(drift["status"], "blocked", drift)
        self.assertEqual(drift["reason"], "selected-source-changed-during-validation")
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"fixture baseline\n")
        self.write(".governance/validate.py", "raise SystemExit(0)\n")
        recovered = self.watch("tick")["watcher"]
        self.assertEqual(recovered["status"], "committed", recovered)
        self.assertTrue(self.cli("status", str(self.root))["ok"])
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"concurrent later source\n")

    def test_fast_forward_external_commit_rotates_once_and_preserves_quiet_boundary(self):
        original = self.configure(quiet_seconds=1)["watcher"]
        for text in ["first automatic stage\n", "second automatic stage\n"]:
            self.write("source.txt", text)
            self.assertEqual(self.watch("tick")["watcher"]["status"], "waiting")
            time.sleep(1.05)
            committed = self.watch("tick")["watcher"]
            self.assertEqual(committed["status"], "committed", committed)
            self.assertEqual(committed["workflow_id"], original["workflow_id"])
        self.assertEqual(self.count(), 3)
        self.write("owner.txt", "external committed stage\n")
        self.git("add", "--", "owner.txt")
        self.git("commit", "--quiet", "-m", "external owner stage")
        external = self.git("rev-parse", "HEAD").decode().strip()
        self.write("source.txt", "automatic stage after external commit\n")
        waiting = self.watch("tick")["watcher"]
        self.assertEqual(waiting["status"], "waiting", waiting)
        self.assertNotEqual(waiting["workflow_id"], original["workflow_id"])
        self.assertEqual(waiting["generation"], original["generation"])
        self.assertEqual(waiting.get("token"), original.get("token"))
        self.assertEqual(waiting["baseline"]["head"], external)
        time.sleep(1.05)
        committed = self.watch("tick")["watcher"]
        self.assertEqual(committed["status"], "committed", committed)
        self.assertEqual(committed["workflow_id"], waiting["workflow_id"])
        self.assertEqual(self.count(), 5)
        self.git("merge-base", "--is-ancestor", external, "HEAD")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "idle")
        self.assertEqual(self.count(), 5)
        self.assertEqual(self.validator_count(), 3)

    def test_external_head_rollback_stays_blocked_without_rotating_identity(self):
        baseline = self.git("rev-parse", "HEAD").decode().strip()
        configured = self.configure()["watcher"]
        self.write("source.txt", "automatic stage before rollback\n")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "committed")
        # Reset only this verified disposable fixture, never the maintained repo.
        self.assertEqual(self.root.parent, self.parent)
        self.git("reset", "--hard", baseline)
        self.write("source.txt", "edit after external rollback\n")
        blocked = self.watch("tick")["watcher"]
        self.assertEqual(blocked["status"], "blocked", blocked)
        self.assertIn("not-fast-forward", blocked["reason"])
        self.assertEqual(blocked["workflow_id"], configured["workflow_id"])
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), baseline)
        self.assertEqual(self.validator_count(), 1)

    def test_published_commit_with_lost_receipt_recovers_clean_tree_without_new_validation(self):
        self.configure()
        self.write("source.txt", "validated commit before lost receipt\n")
        script = self.root / ".governance/lost-receipt.py"
        self.write(".governance/lost-receipt.py", "import json,sys\nfrom pathlib import Path\n"
                   "sys.path.insert(0,sys.argv[1])\nimport git_watch,project_tool\n"
                   "original=project_tool.write_json_atomic\nobserved=False\n"
                   "def fail_receipt(path,value):\n"
                   " global observed\n policy=value.get('git_checkpoint',{})\n"
                   " if not observed and policy.get('last_commit') and not policy.get('journal'):\n"
                   "  observed=True\n  raise OSError('observed fixture loss before receipt write')\n"
                   " return original(path,value)\n"
                   "project_tool.write_json_atomic=fail_receipt\n"
                   "result=git_watch.tick(Path.cwd())\n"
                   "assert observed, 'fixture did not reach actual receipt write'\n"
                   "assert result['watcher']['status']=='blocked'\n"
                   "state=json.loads((Path.cwd()/'.governance/upg.json').read_text())\n"
                   "assert state['git_checkpoint']['journal']['status']=='committed'\n"
                   "print(json.dumps({'observed_receipt_loss':observed}))\n")
        process = subprocess.run([sys.executable, str(script), str(CLI.parent)], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25, check=False)
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
        self.assertTrue(json.loads(process.stdout)["observed_receipt_loss"])
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("status", "--porcelain"), b"")
        state = json.loads((self.root / ".governance/upg.json").read_text())
        original_event = state["git_checkpoint"]["journal"]["event_id"]
        recovered = self.watch("tick")["watcher"]
        self.assertEqual(recovered["status"], "committed", recovered)
        state = json.loads((self.root / ".governance/upg.json").read_text())
        self.assertNotIn("journal", state["git_checkpoint"])
        self.assertEqual(state["git_checkpoint"]["last_commit"]["event_id"], original_event)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        self.assertEqual(self.watch("tick")["watcher"]["status"], "idle")
        self.assertEqual(self.count(), 2)

    def test_new_dirty_file_during_validation_remains_eligible_for_next_stage(self):
        self.configure()
        self.write(".governance/validate.py", "from pathlib import Path\n"
                   "p=Path(__file__).parent\n"
                   "counter=p/'validator-count'\n"
                   "counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')\n"
                   "(p.parent/'owner.txt').write_bytes(b'new separate file edit during validation\\n')\n")
        self.write("source.txt", "first selected source stage\n")
        self.assertEqual(self.watch("tick")["watcher"]["status"], "committed")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:owner.txt"), b"owner baseline\n")
        second = self.watch("tick")["watcher"]
        self.assertEqual(second["status"], "committed", second)
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.git("show", "HEAD:owner.txt"), b"new separate file edit during validation\n")
        self.assertEqual(self.validator_count(), 2)

    def test_native_worker_retries_temporary_writer_lock_without_exiting(self):
        self.configure()
        started = self.start_worker()
        lock = self.root / ".governance/.upg-write-lock"
        deadline = time.monotonic() + 3
        while True:
            try:
                lock.mkdir()
                break
            except FileExistsError:
                if time.monotonic() > deadline:
                    self.fail("fixture could not reserve its own project writer lock")
                time.sleep(0.05)
        try:
            self.write("source.txt", "edit while manual writer owns project\n")
            time.sleep(6.5)
            self.assertEqual(self.count(), 1)
        finally:
            lock.rmdir()
        self.wait_for(lambda: self.count() == 2)
        current = self.watch("status")["watcher"]
        self.assertEqual(current["pid"], started["pid"])
        self.assertEqual(current["token"], started["token"])
        self.stop_worker()

    def test_stop_during_first_validator_does_not_launch_second_validator(self):
        self.write(".governance/first-validator.py", "from pathlib import Path\nimport time\n"
                   "p=Path(__file__).parent\n(p/'first-started').write_text('started')\n"
                   "deadline=time.monotonic()+10\n"
                   "while not (p/'first-release').exists() and time.monotonic()<deadline:\n time.sleep(.05)\n")
        self.write(".governance/second-validator.py", "from pathlib import Path\n"
                   "(Path(__file__).parent/'second-started').write_text('must not start')\n")
        configuration = dict(self.configuration, validators=[
            {"argv": [sys.executable, str(self.root / ".governance/first-validator.py")], "timeout_seconds": 12},
            {"argv": [sys.executable, str(self.root / ".governance/second-validator.py")], "timeout_seconds": 5}])
        self.watch("configure", configuration, expected=(0,))
        self.start_worker()
        self.write("source.txt", "candidate cancelled after first validator\n")
        self.wait_for(lambda: (self.root / ".governance/first-started").exists())
        stopping = subprocess.Popen([sys.executable, str(CLI), "git-watch", str(self.root), "--action", "stop"],
                                    cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            def revoked():
                state = json.loads((self.root / ".governance/upg.json").read_text())
                return state["git_checkpoint"]["watcher"].get("token") is None
            self.wait_for(revoked, timeout=5)
        finally:
            self.write(".governance/first-release", "release\n")
            output, error = stopping.communicate(timeout=15)
        self.assertEqual(stopping.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.stop_worker()
        self.assertFalse((self.root / ".governance/second-started").exists())
        self.assertEqual(self.count(), 1)

    def test_manual_workflow_takes_priority_without_overwriting_its_baseline(self):
        self.configure()
        start = {"workflow_id": "manual-owner", "change": change()}
        path = self.root / ".governance/manual-start.json"
        self.write(".governance/manual-start.json", json.dumps(start))
        self.cli("begin", str(self.root), "--input", str(path))
        before = json.loads((self.root / ".governance/upg.json").read_text())["git_checkpoint"]["start"]
        self.write("source.txt", "manual owner source edit\n")
        result = self.watch("tick")["watcher"]
        self.assertEqual(result["status"], "yielded", result)
        after = json.loads((self.root / ".governance/upg.json").read_text())["git_checkpoint"]["start"]
        self.assertEqual(after, before)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.validator_count(), 0)

    def test_native_worker_survives_parent_cli_exit_single_instance_stops_and_restarts(self):
        self.configure(quiet_seconds=1)
        started = self.start_worker()
        reconfigured = self.configure(quiet_seconds=1)["watcher"]
        self.assertEqual(reconfigured["pid"], started["pid"])
        self.assertEqual(reconfigured["token"], started["token"])
        again = self.watch("start", expected=(0,))["watcher"]
        self.assertEqual(again["pid"], started["pid"])
        self.assertEqual(again["token"], started["token"])
        self.assertTrue(again["idempotent"])
        self.write("source.txt", "native editor change without lifecycle\n")
        self.wait_for(lambda: self.count() == 2)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"native editor change without lifecycle\n")
        self.stop_worker()
        self.write("source.txt", "edit after explicit stop\n")
        time.sleep(1.1)
        self.assertEqual(self.count(), 2)
        self.start_worker()
        self.wait_for(lambda: self.count() == 3)
        self.stop_worker()
        self.assertEqual(self.validator_count(), 2)

    def test_native_failed_validator_uses_bounded_retry_and_recovers_without_source_change(self):
        self.write(".governance/validate.py", "from pathlib import Path\n"
                   "p=Path(__file__).parent\n"
                   "counter=p/'validator-count'\n"
                   "counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')\n"
                   "raise SystemExit(0 if (p/'allow-validation').exists() else 1)\n")
        self.configure()
        self.start_worker()
        self.write("source.txt", "same source awaiting validator recovery\n")
        self.wait_for(lambda: self.validator_count() == 1)
        time.sleep(2.1)
        self.assertEqual(self.validator_count(), 1, "failed unchanged source must not rerun validation every poll")
        health = self.cli("status", str(self.root), expected=(1,))
        self.assertFalse(health["ok"], "failed candidate remains unhealthy throughout retry backoff")
        self.assertEqual(health["reason"], "git-watcher-pending")
        self.assertEqual(self.count(), 1)
        self.write(".governance/allow-validation", "allow\n")
        self.wait_for(lambda: self.count() == 2, timeout=20)
        self.assertEqual(self.validator_count(), 2)
        self.stop_worker()


if __name__ == "__main__":
    unittest.main()
