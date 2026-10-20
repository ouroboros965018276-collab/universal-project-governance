"""Necessary native-process recovery checks; no scheduled task or paid calls."""
import json
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

    def enable_recovery_fixture(self):
        # Exercise project-session recovery intent without host startup tasks.
        path = self.root / ".governance/upg.json"
        binding = json.loads(path.read_text())
        binding["git_checkpoint"]["watcher"]["supervisor"] = {"enabled": True, "fixture": True}
        self.write(".governance/upg.json", json.dumps(binding))

    def owned_worker_host(self):
        self.write(".governance/owned-host.py", "import json,sys,time\nfrom pathlib import Path\n"
                   "sys.path.insert(0,sys.argv[1])\nimport git_watch\n"
                   "p=Path.cwd()/'.governance'\noriginal=git_watch._spawn_worker\nchildren=[]\n"
                   "def owned(*args):\n child=original(*args)\n children.append(child)\n return child\n"
                   "git_watch._spawn_worker=owned\ngit_watch._set_start_intent(Path.cwd())\nview=git_watch._launch(Path.cwd())\n"
                   "assert len(children)==1 and view['watcher']['running']\n"
                   "(p/'owned-worker-ready').write_text(json.dumps(view))\n"
                   "deadline=time.monotonic()+45\n"
                   "while not (p/'kill-owned-worker').exists() and time.monotonic()<deadline:\n time.sleep(.05)\n"
                   "assert (p/'kill-owned-worker').exists(), 'test did not request its owned crash'\n"
                   "children[0].kill()\nchildren[0].wait(timeout=10)\n"
                   "assert children[0].returncode is not None\n"
                   "(p/'owned-worker-exited').write_text(str(children[0].returncode))\n")
        host = subprocess.Popen([sys.executable, str(self.root / ".governance/owned-host.py"), str(fixture.CLI.parent)],
                                cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.stop_worker)
        def finish_host():
            if host.poll() is None:
                self.write(".governance/kill-owned-worker", "end owned fixture\n")
            output, error = host.communicate(timeout=15)
            self.assertEqual(host.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.addCleanup(finish_host)
        self.wait_for(lambda: (self.root / ".governance/owned-worker-ready").exists(), timeout=15)
        view = json.loads((self.root / ".governance/owned-worker-ready").read_text())["watcher"]
        self.worker_pid = view["pid"]
        return host, view

    def crash_owned_worker(self, host):
        # The separate parent owns a real Popen handle and kills only its exact
        # child. No process is selected or signalled using metadata's bare PID.
        self.write(".governance/kill-owned-worker", "controlled native crash\n")
        self.wait_for(lambda: (self.root / ".governance/owned-worker-exited").exists(), timeout=10)
        output, error = host.communicate(timeout=5)
        self.assertEqual(host.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.worker_pid = None

    def test_native_crash_recovers_original_scope_and_deduplicates(self):
        configured = self.configure()["watcher"]
        self.enable_recovery_fixture()
        host, previous = self.owned_worker_host()
        self.crash_owned_worker(host)
        self.write("source.txt", "source after actual worker crash\n")
        recovered = self.watch("recover")["watcher"]
        self.assertTrue(recovered["running"], recovered)
        self.assertNotEqual(recovered["token"], previous["token"])
        self.assertEqual(recovered["generation"], configured["generation"])
        self.worker_pid = recovered["pid"]
        self.wait_for(lambda: self.count() == 2)
        again = self.watch("recover")["watcher"]
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
        deferred = self.watch("recover")["watcher"]
        self.assertIn("deferred", deferred["recovery"])
        self.assertEqual(deferred["token"], previous["token"])
        self.assertEqual((self.root / ".governance/orphan-count").read_text(), "1")
        self.assertEqual(self.count(), 1)
        self.write(".governance/orphan-release", "release actual orphan command\n")
        self.wait_for(lambda: (self.root / ".governance/orphan-finished").exists())
        deadline = time.monotonic() + 15
        while True:
            current = self.watch("recover")["watcher"]
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
                "git_watch._spawn_supervisor=unavailable\nfailed=git_watch.start(Path.cwd())\n"
                "assert failed[\"watcher\"][\"supervisor\"][\"status\"]==\"blocked\"\n"
                "assert not project_tool.status(Path.cwd())[\"ok\"]\n"
                "sys.argv=[\"project_tool.py\",\"git-watch\",str(Path.cwd()),\"--action\",\"status\"]\n"
                "with contextlib.redirect_stdout(io.StringIO()):\n assert project_tool.main()==1\n"
                "git_watch.stop(Path.cwd())\nassert project_tool.status(Path.cwd())[\"ok\"]\n"
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
