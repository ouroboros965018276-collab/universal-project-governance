"""Necessary native crash calibration for owned Git index-lock recovery."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "governance-src/runtime-scripts"
sys.path.insert(0, str(RUNTIME))
import git_checkpoint


@unittest.skipUnless(shutil.which("git"), "real Git executable is required")
class GitRecoveryIndexTests(unittest.TestCase):
    def setUp(self):
        self.parent = (ROOT / "eval-workspaces").resolve()
        self.parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="git-recovery-index-", dir=str(self.parent))
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.cleanup)
        self.git("init", "--template=", "--quiet")
        for key, value in (("user.name", "UPG local recovery calibration"),
                           ("user.email", "recovery@example.invalid"),
                           ("commit.gpgSign", "false"), ("core.autocrlf", "false"),
                           ("core.hooksPath", str(self.root / ".git/hooks"))):
            self.git("config", key, value)
        self.write(".gitignore", ".governance/\n")
        self.write("source.txt", "baseline\n")
        self.write("unrelated.txt", "owner baseline\n")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "recovery fixture baseline")
        self.policy = {"enabled": True, "min_interval_seconds": 300,
                       "allowed_paths": ["source.txt"], "status_paths": []}
        self.policy["start"] = {"workflow_id": "native-recovery",
                                "snapshot": git_checkpoint.capture(self.root, self.policy)}
        self.binding = {"git_checkpoint": self.policy}
        self.payload = {"workflow_id": "native-recovery", "status": "complete",
                        "changed_files": ["source.txt"], "validation": ["local native crash calibration"],
                        "integrity": "pass", "task": "recover actual owned index lock"}
        self.state = self.root / ".governance/recovery-binding.json"
        self.state.parent.mkdir(exist_ok=True)
        self.save(self.binding)
        self.write("source.txt", "validated final source\n")
        self.write("unrelated.txt", "owner staged work\n")
        self.git("add", "--", "unrelated.txt")

    def cleanup(self):
        if self.root.parent != self.parent or not self.root.name.startswith("git-recovery-index-"):
            raise AssertionError("refusing cleanup outside owned recovery fixture")
        self.temporary.cleanup()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))

    def git(self, *args):
        result = subprocess.run([shutil.which("git"), *args], cwd=self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def save(self, value):
        self.state.write_bytes(json.dumps(value, sort_keys=True).encode("utf-8"))

    def crash(self, boundary):
        code = """
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import git_checkpoint
root = Path(sys.argv[2])
state = root / ".governance/recovery-binding.json"
binding = json.loads(state.read_text(encoding="utf-8"))
payload = json.loads(sys.argv[4])
boundary = sys.argv[3]
def save(value):
    policy = value["git_checkpoint"]
    if boundary == "receipt" and not policy.get("journal") and policy.get("last_commit"):
        os._exit(43)
    temporary = state.with_name("observed-save.tmp")
    with temporary.open("wb") as stream:
        stream.write(json.dumps(value, sort_keys=True).encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(state))
    if boundary == "intent" and policy.get("journal", {}).get("status") == "prepared":
        assert not (root / ".git/index.lock").exists()
        os._exit(41)
if boundary == "locked":
    def reached_native_lock(*args):
        journal = binding["git_checkpoint"]["journal"]
        source = root / ".git" / journal["artifact_dir"] / journal["lock_source"]
        assert os.path.samefile(str(source), str(root / ".git/index.lock"))
        os._exit(42)
    git_checkpoint._private_admin = reached_native_lock
git_checkpoint.run_checkpoint(root, binding, payload, "crash-stage", save)
raise AssertionError("fixture did not reach requested native crash boundary")
"""
        result = subprocess.run([sys.executable, "-c", code, str(RUNTIME), str(self.root), boundary,
                                 json.dumps(self.payload)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=45)
        expected = {"intent": 41, "locked": 42, "receipt": 43}[boundary]
        self.assertEqual(result.returncode, expected, result.stderr)
        self.binding = json.loads(self.state.read_text(encoding="utf-8"))
        self.policy = self.binding["git_checkpoint"]

    def recover(self):
        return git_checkpoint.run_checkpoint(self.root, self.binding, self.payload, "crash-stage", self.save)

    def assert_one_commit_and_preserved_staging(self):
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"2")
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"validated final source\n")
        self.assertEqual(self.git("show", ":unrelated.txt"), b"owner staged work\n")
        self.assertEqual(self.git("diff", "--cached", "--name-only").strip(), b"unrelated.txt")
        self.assertFalse((self.root / ".git/index.lock").exists())
        self.assertNotIn("journal", self.policy)
        self.assertEqual(self.recover()["status"], "duplicate")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"2")

    def test_journal_precedes_lock_and_identical_foreign_lock_is_never_removed(self):
        self.crash("intent")
        lock = self.root / ".git/index.lock"
        journal = self.policy["journal"]
        source = self.root / ".git" / journal["artifact_dir"] / journal["lock_source"]
        self.assertFalse(lock.exists())
        lock.write_bytes(source.read_bytes())
        foreign = lock.read_bytes()
        self.assertFalse(os.path.samefile(str(lock), str(source)))
        result = self.recover()
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["reason"], "git-index-busy")
        self.assertEqual(lock.read_bytes(), foreign)
        # This exact file was created by this test; removal is not recovery code.
        lock.unlink()
        self.assertEqual(self.recover()["status"], "committed")
        self.assert_one_commit_and_preserved_staging()

    def test_hard_exit_after_atomic_owned_link_recovers_but_legacy_metadata_blocks(self):
        self.crash("locked")
        lock = self.root / ".git/index.lock"
        self.assertTrue(lock.is_file())
        saved = copy.deepcopy(self.policy["journal"])
        self.policy["journal"].pop("lock_protocol")
        self.assertEqual(self.recover()["reason"], "legacy-native-index-lock-requires-inspection")
        self.assertTrue(lock.is_file())
        self.policy["journal"] = saved
        self.assertEqual(self.recover()["status"], "committed")
        self.assert_one_commit_and_preserved_staging()

    def test_hard_exit_after_index_replace_before_receipt_recovers_without_duplicate(self):
        self.crash("receipt")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"2")
        self.assertNotIn("last_commit", self.policy)
        self.assertFalse((self.root / ".git/index.lock").exists())
        self.assertEqual(self.recover()["status"], "committed")
        self.assert_one_commit_and_preserved_staging()


if __name__ == "__main__":
    unittest.main()
