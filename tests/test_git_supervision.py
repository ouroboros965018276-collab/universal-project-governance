"""Two bounded real-process project supervision checks; no host startup APIs."""
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_git_watch as fixture


@unittest.skipUnless(fixture.shutil.which("git"), "real Git executable required")
class GitSupervisionTests(unittest.TestCase):
    # Reuse only disposable fixture helpers; do not inherit the old test matrix.
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

    def state(self):
        # Windows replace can briefly deny a concurrent reader; keep a real
        # persistent permission failure visible instead of masking it.
        deadline = time.monotonic() + 1
        while True:
            try:
                return json.loads((self.root / ".governance/upg.json").read_text(encoding="utf-8"))["git_checkpoint"]["watcher"]
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.02)

    def stop_all(self):
        deadline = time.monotonic() + 30
        while True:
            result = self.watch("stop", expected=(0, 1, 2))
            if not isinstance(result, subprocess.CompletedProcess):
                break
            if b"project state writer busy" not in result.stderr or time.monotonic() > deadline:
                self.fail(result.stderr.decode("utf-8", "replace"))
            time.sleep(.1)
        self.wait_for(lambda: not self.state().get("pid") and not self.state().get("supervisor", {}).get("pid"), timeout=20)
        state = self.state()
        self.assertFalse(state["desired_running"])
        self.assertFalse(state.get("token"))
        self.assertFalse(state.get("supervisor", {}).get("token"))

    def owned_host(self, public_launch):
        # The routine boundary keeps actual worker Popen handles in its owner;
        # the separate public-launch boundary uses the real fresh supervisor.
        mode = "public" if public_launch else "routine"
        script = '''import json,subprocess,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import git_watch
p=Path.cwd()/'.governance'
mode=sys.argv[2]
children=[]
original_worker=git_watch._spawn_worker
original_supervisor=git_watch._spawn_supervisor

def own_worker(*args,**kwargs):
 child=original_worker(*args,**kwargs)
 children.append(child)
 if len(children)==1:
  (p/'first-owned-worker.json').write_text(json.dumps({'pid':child.pid}))
 return child

def own_supervisor(*args,**kwargs):
 child=original_supervisor(*args,**kwargs)
 children.append(child)
 (p/'public-owned-supervisor.json').write_text(json.dumps({'pid':child.pid}))
 return child

def crash_controller():
 while not (p/'finish-owned-host').exists():
  if (p/'crash-first-owned-worker').exists():
   assert children, 'no actual owned worker handle'
   child=children[0]
   if child.poll() is None:
    child.kill()
    child.wait(timeout=10)
   (p/'owned-crash-complete').write_text(json.dumps({'pid':child.pid,'returncode':child.returncode}))
   return
  time.sleep(.03)

if mode=='public':
 git_watch._spawn_supervisor=own_supervisor
 view=git_watch.start(Path.cwd())
 assert len(children)==1 and children[0].pid==view['watcher']['supervisor']['pid']
 (p/'owned-host-ready').write_text(json.dumps(view))
 until=time.monotonic()+150
 while not (p/'finish-owned-host').exists() and time.monotonic()<until:
  time.sleep(.03)
 assert (p/'finish-owned-host').exists(), 'test must normally stop its public supervisor'
else:
 git_watch._spawn_worker=own_worker
 git_watch._set_start_intent(Path.cwd())
 view,token=git_watch._reserve_supervisor(Path.cwd())
 assert token
 thread=threading.Thread(target=crash_controller,daemon=True)
 thread.start()
 (p/'owned-host-ready').write_text(json.dumps(view))
 result=git_watch.supervise(Path.cwd(),token)
 assert result==0
 thread.join(timeout=2)
for child in children:
 child.wait(timeout=15)
assert all(child.returncode is not None for child in children)
(p/'owned-host-children-exited').write_text(json.dumps([{'pid':c.pid,'returncode':c.returncode} for c in children]))
'''
        self.write(".governance/owned-supervision-host.py", script)
        host = subprocess.Popen([sys.executable, str(self.root / ".governance/owned-supervision-host.py"),
                                 str(fixture.CLI.parent), mode], cwd=self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def finish():
            try:
                if host.poll() is None:
                    self.stop_all()
                    self.write(".governance/finish-owned-host", "normal owner cleanup\n")
                output, error = host.communicate(timeout=20)
                self.assertEqual(host.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
            finally:
                self.assertIsNotNone(host.poll(), "owned host must actually exit before fixture deletion")
        self.addCleanup(finish)
        self.wait_for(lambda: (self.root / ".governance/owned-host-ready").exists() or host.poll() is not None, timeout=25)
        if host.poll() is not None:
            output, error = host.communicate()
            self.fail(error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        return host

    def test_production_supervisor_routine_recovers_owned_crash_without_another_activation(self):
        self.configure()
        host = self.owned_host(public_launch=False)
        self.wait_for(lambda: ((self.root / ".governance/first-owned-worker.json").exists()
                              and self.state().get("pid")
                              and self.state().get("supervisor", {}).get("status") == "watching"), timeout=25)
        first = self.state()
        owned = json.loads((self.root / ".governance/first-owned-worker.json").read_text())
        self.assertEqual(first["pid"], owned["pid"])
        self.assertEqual(first["supervisor"]["pid"], host.pid)
        self.assertEqual(first["supervisor"]["status"], "watching")
        self.write(".governance/crash-first-owned-worker", "kill only the captured real child\n")
        self.wait_for(lambda: (self.root / ".governance/owned-crash-complete").exists(), timeout=15)
        exited = json.loads((self.root / ".governance/owned-crash-complete").read_text())
        self.assertEqual(exited["pid"], first["pid"])
        self.assertIsNotNone(exited["returncode"])
        self.write("source.txt", "validated source after supervised crash\n")
        # No recover/start/ensure call occurs between crash and observation.
        self.wait_for(lambda: bool(self.state().get("pid") and self.state().get("token") != first["token"]), timeout=30)
        recovered = self.state()
        self.assertNotEqual(recovered["pid"], first["pid"])
        self.assertEqual(recovered["supervisor"]["pid"], host.pid)
        self.assertEqual(recovered["supervisor"]["token"], first["supervisor"]["token"])
        self.wait_for(lambda: self.count() == 2 and self.state()["status"] in {"idle", "committed"}, timeout=60)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"validated source after supervised crash\n")
        self.assertEqual(self.validator_count(), 1)
        self.watch("tick")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        self.stop_all()
        self.write(".governance/finish-owned-host", "finished bounded calibration\n")
        output, error = host.communicate(timeout=20)
        self.assertEqual(host.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))

    def test_public_start_launches_supervisor_then_stop_and_ensure_leave_all_processes_stopped(self):
        self.configure()
        host = self.owned_host(public_launch=True)
        self.wait_for(lambda: self.state().get("pid") and self.state().get("supervisor", {}).get("pid"), timeout=25)
        started = self.state()
        owned = json.loads((self.root / ".governance/public-owned-supervisor.json").read_text())
        self.assertEqual(started["supervisor"]["pid"], owned["pid"])
        self.assertNotEqual(started["supervisor"]["pid"], host.pid)
        self.assertTrue(started["supervisor"]["enabled"])
        self.stop_all()
        self.write(".governance/finish-owned-host", "ordinary cooperative stop\n")
        output, error = host.communicate(timeout=20)
        self.assertEqual(host.returncode, 0, error.decode("utf-8", "replace") + output.decode("utf-8", "replace"))
        self.assertTrue((self.root / ".governance/owned-host-children-exited").exists())
        self.write("source.txt", "owner edit after explicit stop\n")
        self.cli("ensure", str(self.root))
        time.sleep(1.2)
        stopped = self.state()
        self.assertFalse(stopped["desired_running"])
        self.assertFalse(stopped.get("pid"))
        self.assertFalse(stopped.get("supervisor", {}).get("pid"))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.validator_count(), 0)
        self.assertFalse((fixture.CLI.parent / "git_autostart.py").exists())
        self.cli("git-autostart", str(self.root), "--action", "status", expected=(2,))


if __name__ == "__main__":
    unittest.main()
