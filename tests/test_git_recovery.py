"""Necessary native-process recovery checks; no scheduled task or paid calls."""
import json
import shutil
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_git_watch as fixture


class GitRecoveryTests(unittest.TestCase):
    # Reuse only the existing disposable real-Git fixture, not its test methods.
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
    start_worker = fixture.GitWatchTests.start_worker
    stop_worker = fixture.GitWatchTests.stop_worker
    state = fixture.GitWatchTests.state
    start_session = fixture.GitWatchTests.start_session
    finish_session = fixture.GitWatchTests.finish_session
    close_sessions = fixture.GitWatchTests.close_sessions

    def enable_recovery_fixture(self):
        # Exercise project-session recovery intent without host startup tasks.
        path = self.root / ".governance/upg.json"
        binding = json.loads(path.read_text())
        binding["git_checkpoint"]["watcher"]["supervisor"] = {"enabled": True, "fixture": True}
        self.write(".governance/upg.json", json.dumps(binding))

    def owned_worker_host(self):
        # Copy the delivered runtime only inside this disposable fixture. The
        # sole injected hook retains _spawn_worker's actual Popen in its real
        # supervisor, so every supported Python can inject an exact-child crash.
        runtime = self.root / ".governance/recovery-runtime"
        shutil.copytree(fixture.CLI.parent.parent, runtime,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        copied_watch = runtime / "scripts/git_watch.py"
        hook = """
if __name__ == "__main__" and "--supervise" in sys.argv:
    _recovery_original_spawn = _spawn_worker
    _recovery_fault_claimed = False
    def _recovery_owned_spawn(*args):
        global _recovery_fault_claimed
        child = _recovery_original_spawn(*args)
        if not _recovery_fault_claimed:
            _recovery_fault_claimed = True
            def crash_exact_child():
                p = Path.cwd() / ".governance"
                deadline = time.monotonic() + 45
                while not (p / "kill-owned-worker").exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                if not (p / "kill-owned-worker").exists():
                    return
                child.kill()
                child.wait(timeout=10)
                assert child.returncode is not None
                (p / "owned-worker-exited").write_text(str(child.returncode))
            threading.Thread(target=crash_exact_child, daemon=True).start()
        return child
    _spawn_worker = _recovery_owned_spawn

"""
        source = copied_watch.read_text(encoding="utf-8")
        marker = 'if __name__ == "__main__":'
        self.assertEqual(source.count(marker), 1)
        copied_watch.write_bytes(source.replace(marker, hook + marker).encode("utf-8"))
        self.write(".governance/owned-host.py", """import json,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import git_watch
root=Path.cwd()
p=root/'.governance'
ended=threading.Event()
def recover_requests():
    sequence=1
    while not ended.is_set():
        request=p/('recover-request-'+str(sequence))
        if not request.exists():
            ended.wait(.03)
            continue
        response=p/('recover-response-'+str(sequence)+'.json')
        value=git_watch.recover(root)
        candidate=response.with_suffix('.tmp')
        candidate.write_text(json.dumps(value))
        candidate.replace(response)
        sequence+=1
thread=threading.Thread(target=recover_requests,daemon=True)
thread.start()
try:
    result=git_watch.session(root,sys.argv[2:])
    assert result['host_returncode']==0,result
finally:
    ended.set()
    thread.join(timeout=2)
""")
        # Existing public-session fixture passes the canonical CLI directory as
        # argv[1]; this wrapper substitutes only our instrumented copied runtime.
        owner = self.root / ".governance/recovery-session.py"
        self.write(".governance/recovery-session.py",
                   "import runpy,sys\nfrom pathlib import Path\n"
                   "sys.argv[1]=str(Path.cwd()/'.governance/recovery-runtime/scripts')\n"
                   "runpy.run_path(str(Path.cwd()/'.governance/owned-host.py'),run_name='__main__')\n")
        record = self.start_session(owner)
        self.current_session = record
        view = self.state()
        self.worker_pid = view["pid"]
        self.recovery_request = 0
        return record["process"], view

    def recover_inside_session(self):
        self.recovery_request += 1
        number = str(self.recovery_request)
        self.write(".governance/recover-request-" + number, "recover inside the live foreground owner\n")
        response = self.root / (".governance/recover-response-" + number + ".json")
        self.wait_for(response.exists, timeout=20)
        return json.loads(response.read_text())["watcher"]

    def crash_owned_worker(self, host):
        # The actual supervisor owns this Popen and kills only its exact child.
        # Its foreground session remains alive throughout orphan/defer recovery.
        self.write(".governance/kill-owned-worker", "controlled native crash\n")
        self.wait_for(lambda: (self.root / ".governance/owned-worker-exited").exists(), timeout=10)
        self.assertIsNone(host.poll(), "session owner must remain alive for recovery")
        self.worker_pid = None

    def test_native_crash_recovers_original_scope_and_deduplicates(self):
        configured = self.configure()["watcher"]
        self.enable_recovery_fixture()
        host, previous = self.owned_worker_host()
        self.crash_owned_worker(host)
        self.write("source.txt", "source after actual worker crash\n")
        recovered = self.recover_inside_session()
        self.assertTrue(recovered["running"], recovered)
        self.assertNotEqual(recovered["token"], previous["token"])
        self.assertEqual(recovered["generation"], configured["generation"])
        self.worker_pid = recovered["pid"]
        self.wait_for(lambda: self.count() == 2)
        again = self.recover_inside_session()
        self.assertEqual(again["token"], recovered["token"])
        self.assertEqual(again["pid"], recovered["pid"])
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        self.stop_worker()

    def test_live_orphan_validator_defers_then_recovers_without_waiting_long_lease(self):
        self.write(".governance/orphan-validator.py", "from pathlib import Path\nimport time\n"
                   "p=Path(__file__).parent\nc=p/'orphan-count'\n"
                   "c.write_text(str(int(c.read_text())+1) if c.exists() else '1')\n"
                   "(p/'orphan-started').write_text('started')\ndeadline=time.monotonic()+30\n"
                   "while not (p/'orphan-release').exists() and time.monotonic()<deadline:\n time.sleep(.05)\n"
                   "assert (p/'orphan-release').exists()\n(p/'orphan-finished').write_text('finished')\n")
        validators = [{"argv": [sys.executable, str(self.root / ".governance/orphan-validator.py")], "timeout_seconds": 300}]
        validators += [{"argv": [sys.executable, "-c", "pass"], "timeout_seconds": 300} for _ in range(7)]
        self.configure(validators=validators)
        self.enable_recovery_fixture()
        host, previous = self.owned_worker_host()
        self.addCleanup(lambda: self.write(".governance/orphan-release", "cleanup release\n"))
        self.write("source.txt", "source awaiting original orphan validator\n")
        self.wait_for(lambda: (self.root / ".governance/orphan-started").exists())
        binding = json.loads((self.root / ".governance/upg.json").read_text())
        self.assertGreater(binding["git_checkpoint"]["watcher"]["lease_until"] - time.time(), 2300)
        self.crash_owned_worker(host)
        deferred = self.recover_inside_session()
        self.assertIn("deferred", deferred["recovery"])
        self.assertEqual(deferred["token"], previous["token"])
        self.assertEqual((self.root / ".governance/orphan-count").read_text(), "1")
        self.assertEqual(self.count(), 1)
        self.write(".governance/orphan-release", "release actual orphan command\n")
        self.wait_for(lambda: (self.root / ".governance/orphan-finished").exists())
        deadline = time.monotonic() + 15
        while True:
            current = self.recover_inside_session()
            if current.get("token") != previous["token"] and current.get("pid"):
                break
            if time.monotonic() > deadline:
                self.fail("native guard did not release after actual validator completion")
            time.sleep(.2)
        self.worker_pid = current["pid"]
        self.assertTrue(current["running"], current)
        self.wait_for(lambda: self.count() == 2)
        self.assertEqual((self.root / ".governance/orphan-count").read_text(), "2")
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"source awaiting original orphan validator\n")
        self.stop_worker()

    def test_os_writer_guard_recovers_after_hard_exit_and_preserves_unknown_legacy_lock(self):
        code = ("import os,sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nimport project_tool\n"
                "@project_tool.serialized\ndef held(root):\n (Path(root)/'.governance/writer-entered').write_text('entered')\n os._exit(23)\n"
                "held(Path.cwd())\n")
        child = subprocess.Popen([sys.executable, "-c", code, str(fixture.CLI.parent)], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 23, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.assertTrue((self.root / ".governance/writer-entered").exists())
        self.cli("ensure", str(self.root))
        legacy = self.root / ".governance/.upg-write-lock"
        legacy.mkdir()
        sentinel = legacy / "unknown-owner"
        sentinel.write_bytes(b"preserve unknown lock\n")
        try:
            refused = self.cli("ensure", str(self.root), expected=(2,))
            self.assertIn(b"project state writer busy", refused.stderr)
            self.assertEqual(sentinel.read_bytes(), b"preserve unknown lock\n")
        finally:
            sentinel.unlink()
            legacy.rmdir()
        empty = self.root / "empty-project"
        empty.mkdir()
        self.cli("ensure", str(empty))
        empty_binding = json.loads((empty / ".governance/upg.json").read_text())
        self.assertEqual(empty_binding["project_origin"], "new")
        self.cli("remove", str(empty), "--yes")
        self.assertTrue((empty / ".governance/.upg-writer.guard").is_file(), "stable guard inode is retained deliberately")

    def test_unique_atomic_crash_residue_never_blocks_or_becomes_canonical_state(self):
        before = (self.root / ".governance/upg.json").read_bytes()
        code = ("import os,sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nimport project_tool\n"
                "actual=project_tool.os.replace\n"
                "def crash(source,target):\n"
                " if Path(target).name=='upg.json':\n  assert '.upg-' in Path(source).name\n  os._exit(29)\n"
                " return actual(source,target)\n"
                "project_tool.os.replace=crash\nproject_tool.ensure(Path.cwd())\n")
        child = subprocess.Popen([sys.executable, "-c", code, str(fixture.CLI.parent)], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 29, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.assertEqual((self.root / ".governance/upg.json").read_bytes(), before)
        residues = list((self.root / ".governance").glob("upg.json.upg-*.tmp"))
        self.assertEqual(len(residues), 1)
        residues[0].write_bytes(b"never adopt this interrupted candidate\n")
        self.cli("ensure", str(self.root))
        current = (self.root / ".governance/upg.json").read_bytes()
        self.assertEqual(json.loads(current)["managed_by"], "universal-project-governance")
        self.assertEqual(residues[0].read_bytes(), b"never adopt this interrupted candidate\n")
        legacy = self.root / ".governance/upg.json.tmp"
        legacy.write_bytes(b"unknown legacy temporary\n")
        try:
            self.cli("ensure", str(self.root), expected=(2,))
            self.assertEqual((self.root / ".governance/upg.json").read_bytes(), current)
            self.assertEqual(legacy.read_bytes(), b"unknown legacy temporary\n")
            self.assertEqual(residues[0].read_bytes(), b"never adopt this interrupted candidate\n")
        finally:
            legacy.unlink()

    def test_remove_holds_project_native_guards_until_ownership_state_is_deleted(self):
        self.configure()
        code = ("import sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\n"
                "import project_tool,process_guard,git_watch,io,contextlib\nactual=project_tool._remove_files\nobserved=[]\n"
                "def unavailable(*args):\n raise OSError(\"injected launch failure\")\n"
                "import session_lifetime\n"
                "git_watch._spawn_supervisor=unavailable\n"
                "with session_lifetime.Session(Path.cwd()) as life:\n"
                " git_watch._bind_session(Path.cwd(),life.token)\n"
                " failed=git_watch.start(Path.cwd())\n"
                " assert failed[\"watcher\"][\"supervisor\"][\"status\"]==\"blocked\"\n"
                " assert not project_tool.status(Path.cwd())[\"ok\"]\n"
                " sys.argv=[\"project_tool.py\",\"git-watch\",str(Path.cwd()),\"--action\",\"status\"]\n"
                " with contextlib.redirect_stdout(io.StringIO()):\n  assert project_tool.main()==1\n"
                " git_watch.stop(Path.cwd())\n assert project_tool.status(Path.cwd())[\"ok\"]\n"
                " git_watch._end_session(Path.cwd(),life.token)\n"
                "def guarded(root,yes):\n"
                " for name in ['.upg-supervisor.guard','.upg-worker.guard','.upg-validation.guard','.upg-checkpoint.guard']:\n"
                "  assert process_guard.acquire(root,name) is None, 'remove released a native ownership guard early'\n"
                " observed.append('native ownership retained')\n return actual(root,yes)\n"
                "project_tool._remove_files=guarded\nproject_tool.remove(Path.cwd(),True)\n"
                "assert observed==['native ownership retained']\n"
                "assert not (Path.cwd()/'.governance/upg.json').exists()\n")
        child = subprocess.Popen([sys.executable, "-c", code, str(fixture.CLI.parent)], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = child.communicate(timeout=15)
        self.assertEqual(child.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.assertFalse((self.root / ".governance/upg.json").exists())

    def test_stop_and_reconfigure_do_not_let_recovery_revive_user_stop(self):
        self.configure()
        self.enable_recovery_fixture()
        self.start_worker()
        self.stop_worker()
        configured = self.configure()["watcher"]
        self.assertFalse(configured["desired_running"])
        self.assertTrue(configured["supervisor"]["enabled"])
        self.write("source.txt", "edit after explicit user stop\n")
        stopped = self.watch("recover")["watcher"]
        self.assertFalse(stopped["running"])
        self.assertFalse(stopped["desired_running"])
        self.assertNotIn("token", stopped)
        time.sleep(1.1)
        self.assertEqual(self.count(), 1)
        self.start_worker()
        self.wait_for(lambda: self.count() == 2)
        self.stop_worker()


if __name__ == "__main__":
    unittest.main()
