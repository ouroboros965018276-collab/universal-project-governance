"""Real Git commits through the public governance lifecycle; no provider calls."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_completion_outcomes import write, report, change
from registration_fixture import reviewed_report, task_contract

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "universal-project-governance"
sys.path.insert(0, str(RUNTIME / "scripts"))
SPEC = importlib.util.spec_from_file_location("git_lifecycle_runtime", RUNTIME / "scripts/project_tool.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


@unittest.skipUnless(shutil.which("git"), "real Git executable required")
class GitLifecycleTests(unittest.TestCase):
    def repo(self):
        parent = (ROOT / "eval-workspaces").resolve()
        parent.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="git-lifecycle-", dir=parent)
        root = Path(temporary.name).resolve()
        self.assertEqual(root.parent, parent)
        def cleanup():
            if Path(temporary.name).resolve() != root or root.parent != parent:
                raise AssertionError("refusing cleanup outside owned lifecycle fixture")
            temporary.cleanup()
        self.addCleanup(cleanup)
        for args in [("init", "--template=", "--quiet"),
                     ("config", "user.name", "UPG local lifecycle calibration"),
                     ("config", "user.email", "local-lifecycle@example.invalid"),
                     ("config", "core.autocrlf", "false"),
                     ("config", "commit.gpgSign", "false")]:
            self.git(root, *args)
        (root / ".gitignore").write_bytes(b".governance/\n")
        (root / "runtime.py").write_bytes(b"value = 1\n")
        self.git(root, "add", "--all")
        self.git(root, "commit", "--quiet", "-m", "lifecycle baseline")
        return root

    def git(self, root, *args):
        result = subprocess.run([shutil.which("git"), *args], cwd=root,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout

    def begin(self, root, reporting):
        tool.ensure(root, field_test_reporting=reporting)
        tool.configure_git(root, True, ["."], [], 300)
        start = {"workflow_id": "automatic-lifecycle", "change": change(), "task_contract": task_contract()}
        tool.begin_workflow(root, write(root / ".governance/start.json", start))
        return start

    def finish(self, root, payload):
        return tool.finish_workflow(root, write(root / ".governance/finish.json", reviewed_report(payload, root)))

    def test_finish_automatically_commits_and_exact_retry_does_not_duplicate_in_both_modes(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting):
                root = self.repo()
                start = self.begin(root, reporting)
                (root / "runtime.py").write_bytes(b"value = 2\n")
                outcome = report(start, root=root)
                outcome["changed_files"] = ["runtime.py"]
                result = self.finish(root, outcome)
                self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
                self.assertEqual(self.git(root, "rev-list", "--count", "HEAD").strip(), b"2")
                retry = self.finish(root, outcome)
                self.assertEqual(retry["git_checkpoint"]["status"], "duplicate", retry)
                self.assertEqual(self.git(root, "rev-list", "--count", "HEAD").strip(), b"2")
                state = tool.status(root)
                self.assertTrue(state["ok"], state)
                self.assertIsNone(state["active_workflow"])
                if reporting:
                    self.assertEqual(state["report_count"], 1)

    def test_failed_git_commit_is_visible_and_same_finished_report_recovers(self):
        root = self.repo()
        start = self.begin(root, True)
        hook = root / ".git/hooks/pre-commit"
        hook.parent.mkdir(exist_ok=True)
        hook.write_bytes(b"#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        (root / "runtime.py").write_bytes(b"value = 3\n")
        outcome = report(start, root=root)
        outcome["changed_files"] = ["runtime.py"]
        result = self.finish(root, outcome)
        self.assertEqual(result["git_checkpoint"]["status"], "blocked", result)
        state = tool.status(root)
        self.assertFalse(state["ok"])
        self.assertEqual(state["reason"], "git-checkpoint-pending")
        self.assertEqual(state["report_count"], 1)
        self.assertEqual(self.git(root, "rev-list", "--count", "HEAD").strip(), b"1")
        next_start = {"workflow_id": "unrelated-next-workflow", "change": change(), "task_contract": task_contract()}
        next_start["change"]["parent_event_id"] = state["latest_change"]["event_id"]
        with self.assertRaisesRegex(ValueError, "pending Git checkpoint"):
            tool.begin_workflow(root, write(root / ".governance/next-start.json", next_start))
        hook.unlink()
        result = self.finish(root, outcome)
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        self.assertTrue(tool.status(root)["ok"])
        self.assertEqual(tool.status(root)["report_count"], 1)
        self.assertEqual(self.git(root, "rev-list", "--count", "HEAD").strip(), b"2")

    def test_default_off_and_invalid_scope_do_not_grant_commit_permission(self):
        root = self.repo()
        tool.ensure(root)
        before = tool.status(root)["git_checkpoint"]
        self.assertFalse(before["enabled"])
        for scope in [[], ["../outside"], ["/absolute"], ["C:/other"], [".git/config"]]:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                tool.configure_git(root, True, scope)
            self.assertEqual(tool.status(root)["git_checkpoint"], before)
        self.assertEqual(self.git(root, "rev-list", "--count", "HEAD").strip(), b"1")

    def test_deferred_scope_is_immutable_and_disable_explicitly_retires_scheduling(self):
        root = self.repo()
        start = self.begin(root, True)
        (root / "runtime.py").write_bytes(b"value = 2\n")
        first = report(start, "partial", root=root)
        first["checkpoint_id"] = "first-verified-stage"
        self.assertEqual(self.finish(root, first)["git_checkpoint"]["status"], "committed")
        (root / "runtime.py").write_bytes(b"value = 3\n")
        second = report(start, "partial", root=root)
        second["checkpoint_id"] = "second-verified-stage"
        self.assertEqual(self.finish(root, second)["git_checkpoint"]["status"], "deferred")
        before = tool.status(root)["git_checkpoint"]
        self.assertTrue(before["deferred_events"])
        for allowed, status in [(["README.md"], None), (None, ["runtime.py"])]:
            with self.assertRaisesRegex(ValueError, "pending Git paths"):
                tool.configure_git(root, True, allowed_paths=allowed, status_paths=status)
            self.assertEqual(tool.status(root)["git_checkpoint"], before)
        disabled = tool.configure_git(root, False)["git_checkpoint"]
        self.assertEqual(disabled["result"]["uncommitted_paths"], ["runtime.py"])
        self.assertNotIn("deferred_events", disabled)
        self.assertNotIn("pending_workflow_id", disabled)
        self.assertEqual((root / "runtime.py").read_bytes(), b"value = 3\n")
        self.assertEqual(self.git(root, "rev-list", "--count", "HEAD").strip(), b"2")


if __name__ == "__main__":
    unittest.main()
