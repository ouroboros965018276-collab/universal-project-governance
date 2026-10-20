"""Small native calibrations for crash-safe project process ownership."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "governance-src/runtime-scripts"
SPEC = importlib.util.spec_from_file_location("process_guard_runtime", RUNTIME / "process_guard.py")
process_guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(process_guard)


class ProcessGuardTests(unittest.TestCase):
    def setUp(self):
        self.parent = ROOT / "eval-workspaces"
        self.parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="process-guard-", dir=str(self.parent))
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.root.parent != self.parent.resolve() or not self.root.name.startswith("process-guard-"):
            raise AssertionError("refusing cleanup outside owned process-guard fixture")
        self.temporary.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(value.encode("utf-8"))
        return path

    def wait_for(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.025)
        self.fail("bounded native guard observation timed out")

    def test_exclusive_duplicate_and_release_preserve_same_file(self):
        guard = process_guard.acquire(self.root, ".upg-worker.guard")
        self.assertIsNotNone(guard)
        path = guard.path
        before = path.stat().st_mtime_ns
        try:
            self.assertIsNone(process_guard.acquire(self.root, ".upg-worker.guard"))
            if os.name == "nt":
                self.assertFalse(os.get_handle_inheritable(guard.handle))
                with process_guard.inheritance([guard]) as options:
                    self.assertTrue(os.get_handle_inheritable(guard.handle))
                    self.assertEqual(options["startupinfo"].lpAttributeList["handle_list"], [guard.handle])
                self.assertFalse(os.get_handle_inheritable(guard.handle))
            else:
                with process_guard.inheritance([guard]) as options:
                    self.assertEqual(options["pass_fds"], (guard.handle,))
        finally:
            guard.close()
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_mtime_ns, before)
        with process_guard.acquire(self.root, ".upg-worker.guard") as recovered:
            self.assertEqual(recovered.path, path)

    def test_invalid_names_and_wrong_inherited_file_are_rejected(self):
        for name in ("../other", "guard", ".upg-../worker.guard", ".upg-worker.guard/child"):
            with self.assertRaises(ValueError):
                process_guard.acquire(self.root, name)
        with process_guard.acquire(self.root, ".upg-worker.guard") as guard:
            with process_guard.acquire(self.root, ".upg-writer.guard"):
                with self.assertRaises(ValueError):
                    process_guard.adopt(self.root, ".upg-writer.guard", guard.handle)
        with self.assertRaises(ValueError):
            process_guard.adopt(self.root, ".upg-worker.guard", True)

    def test_parent_hard_exit_keeps_child_guard_until_actual_child_exit(self):
        child_code = """
import os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import process_guard
root = Path(sys.argv[2])
guard = process_guard.adopt(root, ".upg-worker.guard", int(sys.argv[3]))
(root / "child-ready").write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 20
while not (root / "release-child").exists() and time.monotonic() < deadline:
    time.sleep(0.025)
guard.close()
(root / "child-exited").write_text("released", encoding="utf-8")
"""
        parent_code = """
import os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import process_guard
root = Path(sys.argv[2])
guard = process_guard.acquire(root, ".upg-worker.guard")
assert guard is not None
with process_guard.inheritance([guard]) as options:
    child = subprocess.Popen(
        [sys.executable, str(root / "child.py"), sys.argv[1], str(root), str(guard.handle)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
deadline = time.monotonic() + 10
while not (root / "child-ready").exists() and time.monotonic() < deadline:
    time.sleep(0.025)
assert (root / "child-ready").exists()
(root / "parent-ready").write_text("ready", encoding="utf-8")
os._exit(17)
"""
        self.write("child.py", child_code)
        parent = self.write("parent.py", parent_code)
        process = subprocess.Popen([sys.executable, str(parent), str(RUNTIME), str(self.root)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            output, error = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 17, (output, error))
            self.assertTrue((self.root / "parent-ready").is_file())
            self.assertIsNone(process_guard.acquire(self.root, ".upg-worker.guard"))
            # No PID signal or stale-file removal: the real inherited OS handle
            # keeps ownership until the child cooperatively exits.
            self.write("release-child", "release")
            self.wait_for(lambda: (self.root / "child-exited").exists())
            acquired = []
            def available():
                item = process_guard.acquire(self.root, ".upg-worker.guard")
                if item is not None:
                    acquired.append(item)
                    return True
                return False
            self.wait_for(available)
            acquired[0].close()
        finally:
            self.write("release-child", "cleanup")
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            self.wait_for(lambda: (self.root / "child-exited").exists(), timeout=25)

    def test_process_exit_releases_unshared_native_guard_without_lock_cleanup(self):
        code = """
import os, sys
sys.path.insert(0, sys.argv[1])
import process_guard
guard = process_guard.acquire(sys.argv[2], ".upg-checkpoint.guard")
assert guard is not None
os._exit(19)
"""
        result = subprocess.run([sys.executable, "-c", code, str(RUNTIME), str(self.root)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 19, result.stderr)
        self.assertTrue((self.root / ".governance/.upg-checkpoint.guard").exists())
        with process_guard.acquire(self.root, ".upg-checkpoint.guard"):
            pass

    def test_timeout_keeps_actual_native_work_owned_and_refuses_resubmission(self):
        command = """import sys,time
from pathlib import Path
root=Path(sys.argv[1])
(root/'actual-ready').write_text('ready',encoding='utf-8')
deadline=time.monotonic()+15
while not (root/'release-actual').exists() and time.monotonic()<deadline:
 time.sleep(0.025)
"""
        guard = process_guard.acquire(self.root, ".upg-validation.guard")
        try:
            with process_guard.holding(guard):
                with self.assertRaises(subprocess.TimeoutExpired):
                    process_guard.run([sys.executable, "-c", command, str(self.root)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=0.15)
                self.wait_for(lambda: (self.root / "actual-ready").exists())
                self.assertTrue(process_guard.has_pending())
                with self.assertRaises(subprocess.TimeoutExpired):
                    process_guard.run([sys.executable, "-c",
                                       "from pathlib import Path;Path('unexpected-command').touch()"],
                                      cwd=self.root, timeout=1)
                self.assertFalse((self.root / "unexpected-command").exists())
            guard.close()
            self.assertIsNone(process_guard.acquire(self.root, ".upg-validation.guard"))
            self.write("release-actual", "release")
            acquired = []
            def available():
                item = process_guard.acquire(self.root, ".upg-validation.guard")
                if item is not None:
                    acquired.append(item)
                    return True
                return False
            self.wait_for(available)
            acquired[0].close()
        finally:
            self.write("release-actual", "cleanup")
            guard.close()

    def test_native_wrapper_survives_hard_parent_exit_until_command_finishes(self):
        actual = self.write("actual.py", """
import sys,time
from pathlib import Path
root=Path(sys.argv[1])
(root/'native-ready').write_text('ready',encoding='utf-8')
deadline=time.monotonic()+20
while not (root/'release-native').exists() and time.monotonic()<deadline:
 time.sleep(0.025)
""")
        parent = self.write("wrapper-parent.py", """
import os,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import process_guard
root=Path(sys.argv[2])
guard=process_guard.acquire(root,'.upg-worker.guard')
def hard_exit():
 deadline=time.monotonic()+10
 while not (root/'native-ready').exists() and time.monotonic()<deadline:
  time.sleep(0.025)
 assert (root/'native-ready').exists()
 os._exit(37)
threading.Thread(target=hard_exit,daemon=True).start()
with process_guard.holding(guard):
 process_guard.run([sys.executable,str(root/'actual.py'),str(root)],timeout=15)
raise AssertionError('hard parent exit was not observed')
""")
        error_path = self.root / "parent-error.txt"
        with error_path.open("wb") as error:
            process = subprocess.Popen([sys.executable, str(parent), str(RUNTIME), str(self.root)],
                                       stdout=subprocess.DEVNULL, stderr=error)
            try:
                self.assertEqual(process.wait(timeout=15), 37, error_path.read_bytes())
                self.assertIsNone(process_guard.acquire(self.root, ".upg-worker.guard"))
                self.write("release-native", "release")
                acquired = []
                def available():
                    item = process_guard.acquire(self.root, ".upg-worker.guard")
                    if item is not None:
                        acquired.append(item)
                        return True
                    return False
                self.wait_for(available)
                acquired[0].close()
            finally:
                self.write("release-native", "cleanup")
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_wrapper_explicitly_transfers_standard_input_output_and_error(self):
        launcher = Path(sys.executable)
        if os.name == "nt":
            candidate = launcher.with_name("pythonw.exe")
            if candidate.is_file():
                launcher = candidate
        script = self.write("stdio-probe.py", """
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import process_guard
root=Path(sys.argv[2])
guard=process_guard.acquire(root,'.upg-diagnostic.guard')
command="import sys; raw=sys.stdin.buffer.read(); sys.stdout.buffer.write(b'OUT:'+raw); sys.stderr.buffer.write(b'ERR:'+raw)"
with guard,process_guard.holding(guard):
 result=process_guard.run([sys.argv[3],'-c',command],input=b'owned-input',capture_output=True,timeout=10)
(root/'stdio-result.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout.decode('ascii'),'stderr':result.stderr.decode('ascii')}),encoding='utf-8')
""")
        observed = subprocess.run([str(launcher), str(script), str(RUNTIME), str(self.root), sys.executable],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=15)
        self.assertEqual(observed.returncode, 0)
        result = json.loads((self.root / "stdio-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result, {"returncode": 0, "stdout": "OUT:owned-input", "stderr": "ERR:owned-input"})


if __name__ == "__main__":
    unittest.main()
