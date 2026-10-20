"""Bounded public-session native supervision checks; no host startup APIs."""
import json
import os
import signal
import subprocess
import time
import unittest

import test_git_watch as fixture


@unittest.skipUnless(fixture.shutil.which("git"), "real Git executable required")
class GitSupervisionTests(unittest.TestCase):
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

    def test_public_session_recovers_owned_supervisor_crash_without_another_activation(self):
        self.configure()
        # The fault controller retains the real supervisor Popen created by the
        # unchanged public runtime entry. No PID from a document is signalled.
        script = """import json,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import git_watch
root=Path.cwd()
p=root/'.governance'
children=[]
original=git_watch._spawn_supervisor

def own_supervisor(*args,**kwargs):
 child=original(*args,**kwargs)
 children.append(child)
 (p/'owned-supervisors.json').write_text(json.dumps([c.pid for c in children]))
 return child

def crash():
 deadline=time.monotonic()+90
 while not (p/'crash-owned-supervisor').exists() and time.monotonic()<deadline:
  time.sleep(.03)
 if not (p/'crash-owned-supervisor').exists():
  return
 assert children, 'no actual owned supervisor handle'
 child=children[0]
 child.kill()
 child.wait(timeout=10)
 (p/'owned-crash-complete').write_text(json.dumps({'pid':child.pid,'returncode':child.returncode}))

git_watch._spawn_supervisor=own_supervisor
thread=threading.Thread(target=crash,daemon=True)
thread.start()
result=git_watch.session(root,sys.argv[2:])
thread.join(timeout=2)
assert result['host_returncode']==0,result
for child in children:
 child.wait(timeout=15)
assert all(child.returncode is not None for child in children)
(p/'owned-children-exited').write_text(json.dumps([{'pid':c.pid,'returncode':c.returncode} for c in children]))
"""
        self.write(".governance/owned-session.py", script)
        record = self.start_session(self.root / ".governance/owned-session.py")
        first = self.state()
        self.write(".governance/crash-owned-supervisor", "terminate the captured child handle\n")
        self.wait_for(lambda: (self.root / ".governance/owned-crash-complete").exists(), timeout=15)
        crashed = json.loads((self.root / ".governance/owned-crash-complete").read_text())
        self.assertEqual(crashed["pid"], first["supervisor"]["pid"])
        self.assertIsNotNone(crashed["returncode"])
        # No ensure/recover/start invocation occurs after the captured crash.
        self.wait_for(lambda: bool(self.state().get("supervisor", {}).get("pid")
                                  and self.state()["supervisor"]["token"] != first["supervisor"]["token"]
                                  and self.state()["supervisor"].get("status") == "watching"), timeout=40)
        recovered = self.state()
        self.assertNotEqual(recovered["supervisor"]["pid"], first["supervisor"]["pid"])
        self.assertIsNone(record["process"].poll(), "same foreground session must still own recovery")
        current = [fixture.ProcessObservation(recovered["pid"]), fixture.ProcessObservation(recovered["supervisor"]["pid"])]
        record["observations"].extend(current)
        self.write("source.txt", "validated source after supervised crash\n")
        self.wait_for(lambda: self.count() == 2 and self.state()["status"] in {"idle", "committed"}, timeout=60)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"validated source after supervised crash\n")
        self.assertEqual(self.validator_count(), 1)
        self.watch("tick")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        self.finish_session(record)
        self.assertTrue((self.root / ".governance/owned-children-exited").exists())

    @unittest.skipUnless(os.name == "nt" or (hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal")),
                         "native exact-process worker fault injection requires a Job handle or pidfd")
    def test_public_session_recovers_actual_worker_crash_without_another_activation(self):
        self.configure()
        script = """import json,os,signal,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import git_watch,session_lifetime
root=Path.cwd()
p=root/'.governance'

def crash():
 deadline=time.monotonic()+90
 while not (p/'crash-owned-worker').exists() and time.monotonic()<deadline:
  time.sleep(.03)
 if not (p/'crash-owned-worker').exists():
  return
 life=session_lifetime.current()
 assert life is not None and life.active
 state=json.loads((p/'upg.json').read_text())['git_checkpoint']['watcher']
 assert state['session']['token']==life.token
 pid=state['pid']
 supervisor=life.supervisor
 assert supervisor is not None and supervisor.poll() is None
 if os.name=='nt':
  import ctypes
  from ctypes import wintypes
  k=ctypes.WinDLL('kernel32',use_last_error=True)
  k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
  k.OpenProcess.restype=wintypes.HANDLE
  k.IsProcessInJob.argtypes=[wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.BOOL)]
  k.IsProcessInJob.restype=wintypes.BOOL
  k.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
  k.TerminateProcess.restype=wintypes.BOOL
  k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
  k.WaitForSingleObject.restype=wintypes.DWORD
  k.CloseHandle.argtypes=[wintypes.HANDLE]
  handle=k.OpenProcess(0x100000|0x400|0x1,False,pid)
  assert handle,ctypes.get_last_error()
  try:
   inside=wintypes.BOOL()
   assert k.IsProcessInJob(handle,life.job,ctypes.byref(inside)),ctypes.get_last_error()
   assert inside.value,'captured process is outside our actual observer Job'
   assert k.WaitForSingleObject(handle,0)==258,'worker already exited'
   assert k.TerminateProcess(handle,37),ctypes.get_last_error()
   assert k.WaitForSingleObject(handle,5000)==0,'captured worker handle did not signal exit'
  finally:
   k.CloseHandle(handle)
 else:
  import select
  fd=os.pidfd_open(pid)
  try:
   assert os.getpgid(pid)==supervisor.pid and os.getsid(pid)==supervisor.pid
   signal.pidfd_send_signal(fd,signal.SIGKILL)
   assert select.select([fd],[],[],5)[0],'captured worker pidfd did not signal exit'
  finally:
   os.close(fd)
 (p/'owned-worker-crash-complete').write_text(json.dumps({'pid':pid,'exited':True}))

thread=threading.Thread(target=crash,daemon=True)
thread.start()
result=git_watch.session(root,sys.argv[2:])
thread.join(timeout=2)
assert result['host_returncode']==0,result
"""
        self.write(".governance/owned-worker-session.py", script)
        record = self.start_session(self.root / ".governance/owned-worker-session.py")
        first = self.state()
        self.write(".governance/crash-owned-worker", "signal only a captured and contained native process\n")
        self.wait_for(lambda: (self.root / ".governance/owned-worker-crash-complete").exists(), timeout=20)
        crashed = json.loads((self.root / ".governance/owned-worker-crash-complete").read_text())
        self.assertEqual(crashed["pid"], first["pid"])
        self.assertTrue(crashed["exited"])
        self.wait_for(lambda: self.state().get("pid") and self.state().get("token") != first["token"]
                      and self.state().get("supervisor", {}).get("status") == "watching", timeout=40)
        recovered = self.state()
        self.assertNotEqual(recovered["pid"], first["pid"])
        self.assertEqual(recovered["supervisor"]["pid"], first["supervisor"]["pid"])
        self.assertEqual(recovered["supervisor"]["token"], first["supervisor"]["token"])
        record["observations"].append(fixture.ProcessObservation(recovered["pid"]))
        self.write("source.txt", "validated stage after actual worker crash\n")
        self.wait_for(lambda: self.count() == 2, timeout=60)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"validated stage after actual worker crash\n")
        self.assertEqual(self.validator_count(), 1)
        self.watch("tick")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        self.finish_session(record)

    def test_public_session_stop_and_ensure_leave_observers_stopped_while_host_is_active(self):
        self.configure()
        record = self.start_session()
        started = self.state()
        self.assertTrue(started["supervisor"]["enabled"])
        self.stop_all()
        self.assertIsNone(record["process"].poll(), "explicit stop need not close the editor host")
        self.write("source.txt", "owner edit after explicit stop\n")
        self.cli("ensure", str(self.root))
        time.sleep(1.2)
        stopped = self.state()
        self.assertFalse(stopped["desired_running"])
        self.assertFalse(stopped.get("pid"))
        self.assertFalse(stopped.get("supervisor", {}).get("pid"))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.validator_count(), 0)
        blocked = self.cli("remove", str(self.root), "--yes", expected=(2,))
        self.assertIn(b"native project work remains active", blocked.stderr)
        self.assertTrue((self.root / ".governance/upg.json").is_file())
        self.finish_session(record)
        self.cli("remove", str(self.root), "--yes")
        self.assertFalse((self.root / ".governance/upg.json").exists())
        self.assertFalse((fixture.CLI.parent / "git_autostart.py").exists())
        self.cli("git-autostart", str(self.root), "--action", "status", expected=(2,))


if __name__ == "__main__":
    unittest.main()
