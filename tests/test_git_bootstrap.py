"""Necessary real-Git calibration for explicit initialization and root commits."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("git_bootstrap_runtime", ROOT / "governance-src/runtime-scripts/git_checkpoint.py")
git_checkpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(git_checkpoint)


@unittest.skipUnless(shutil.which("git"), "real Git executable required")
class GitBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.parent = (ROOT / "eval-workspaces").resolve()
        self.parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="git-bootstrap-", dir=self.parent)
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.cleanup)
        self.policy = {"enabled": True, "bootstrap": True, "allowed_paths": ["source.txt"],
                       "status_paths": [], "min_interval_seconds": 300}
        self.binding = {"git_checkpoint": self.policy}
        self.write("source.txt", "initial owner source\n")

    def cleanup(self):
        if Path(self.temporary.name).resolve() != self.root or self.root.parent != self.parent:
            raise AssertionError("refusing cleanup outside owned bootstrap fixture")
        self.temporary.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def git(self, *args, root=None, ok=True):
        process = subprocess.run([shutil.which("git"), *args], cwd=root or self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ok:
            self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
        return process.stdout

    def identity(self):
        for key, value in [("user.name", "UPG local bootstrap calibration"),
                           ("user.email", "bootstrap-calibration@example.invalid"),
                           ("core.autocrlf", "false"), ("commit.gpgSign", "false"),
                           ("core.hooksPath", str(self.root / ".git/hooks"))]:
            self.git("config", key, value)

    def begin(self, bootstrap=False):
        snapshot = (git_checkpoint.bootstrap if bootstrap else git_checkpoint.capture)(self.root, self.policy)
        self.assertTrue(snapshot.get("ok"), snapshot)
        self.policy["start"] = {"workflow_id": "initial-adoption", "snapshot": snapshot}
        return snapshot

    def checkpoint(self, event="first-observed-stage", **kwargs):
        payload = {"workflow_id": "initial-adoption", "status": "complete", "changed_files": ["source.txt"],
                   "validation": ["observed necessary local Git calibration"], "integrity": "pass",
                   "task": "explicit initial source adoption", "handoff": "not-required"}
        def save(binding):
            self.write(".governance/bootstrap-receipt.json", json.dumps(binding, sort_keys=True))
        return git_checkpoint.run_checkpoint(self.root, self.binding, payload, event, save, **kwargs)

    def test_explicit_no_repository_initializes_commits_latest_source_and_deduplicates(self):
        snapshot = self.begin(bootstrap=True)
        self.assertTrue(snapshot["initialized"])
        self.assertIsNone(snapshot["head"])
        self.assertTrue((self.root / ".git").is_dir())
        self.identity()
        self.write("source.txt", "normal edited source after initial adoption\n")
        result = self.checkpoint()
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"normal edited source after initial adoption\n")
        head = self.git("rev-parse", "HEAD")
        retry = self.checkpoint()
        self.assertEqual(retry["status"], "duplicate", retry)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")

    def test_deleted_initial_branch_does_not_authorize_another_root_commit(self):
        self.begin(bootstrap=True)
        self.identity()
        self.assertEqual(self.checkpoint()["status"], "committed")
        previous = self.git("rev-parse", "HEAD").decode().strip()
        branch = self.git("symbolic-ref", "HEAD").decode().strip()
        self.git("update-ref", "-d", branch, previous)
        self.write("source.txt", "later source after owner deleted branch\n")
        result = self.checkpoint(event="must-not-create-another-root")
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.git("rev-parse", "--verify", "HEAD", ok=False), b"")
        self.assertEqual(self.git("show", previous + ":source.txt"), b"initial owner source\n")

    def test_validated_source_hash_cannot_authorize_later_bytes_before_helper_capture(self):
        self.begin(bootstrap=True)
        self.identity()
        validated = git_checkpoint._sources(self.root, ["source.txt"])
        self.write("source.txt", "later unvalidated source bytes\n")
        result = self.checkpoint(validated_sources=validated)
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.git("rev-parse", "--verify", "HEAD", ok=False), b"")
        current = git_checkpoint._sources(self.root, ["source.txt"])
        result = self.checkpoint(validated_sources=current)
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"later unvalidated source bytes\n")

    def test_large_untracked_neighborhood_outside_scope_does_not_block_initial_commit(self):
        for number in range(257):
            self.write("outside/file-%03d.txt" % number, "outside scoped adoption\n")
        snapshot = self.begin(bootstrap=True)
        self.assertIsNone(snapshot["head"])
        self.identity()
        result = self.checkpoint()
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.git("ls-tree", "--name-only", "HEAD").strip(), b"source.txt")
        self.assertEqual(len(list((self.root / "outside").iterdir())), 257)
        self.assertEqual(self.git("ls-files", "--", "outside"), b"")

    def test_initialization_requires_explicit_authorization(self):
        for mutation in ({"bootstrap": False}, {"enabled": False}, {"allowed_paths": []}):
            with self.subTest(mutation=mutation):
                policy = dict(self.policy, **mutation)
                result = git_checkpoint.bootstrap(self.root, policy)
                self.assertFalse(result.get("ok"), result)
                self.assertFalse((self.root / ".git").exists())

    def test_existing_unborn_repository_and_missing_index_are_supported(self):
        self.git("init", "--template=", "--quiet")
        self.identity()
        self.assertFalse((self.root / ".git/index").exists())
        snapshot = self.begin(bootstrap=True)
        self.assertFalse(snapshot["initialized"])
        self.assertIsNone(snapshot["head"])
        result = self.checkpoint()
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")
        self.assertEqual(self.git("ls-files", "--stage").count(b"source.txt"), 1)

    def test_child_project_is_initialized_without_mutating_parent_head_index_or_config(self):
        self.git("init", "--template=", "--quiet")
        self.identity()
        self.git("add", "--", "source.txt")
        self.git("commit", "--quiet", "-m", "parent fixture baseline")
        self.write("parent-staged.txt", "parent owner staged work\n")
        self.git("add", "--", "parent-staged.txt")
        observed = (self.git("rev-parse", "HEAD"), (self.root / ".git/index").read_bytes(),
                    (self.root / ".git/config").read_bytes())
        child = self.root / "nested"
        child.mkdir()
        (child / "source.txt").write_bytes(b"child source\n")
        snapshot = git_checkpoint.bootstrap(child, self.policy)
        self.assertTrue(snapshot.get("ok"), snapshot)
        self.assertTrue(snapshot["parent_isolated"], snapshot)
        self.assertTrue((child / ".git").is_dir())
        self.assertEqual((self.git("rev-parse", "HEAD"), (self.root / ".git/index").read_bytes(),
                          (self.root / ".git/config").read_bytes()), observed)
        self.assertEqual(self.git("show", ":parent-staged.txt"), b"parent owner staged work\n")
        self.assertEqual(self.git("rev-parse", "--show-toplevel", root=child).decode().strip().replace("\\", "/"), child.as_posix())

    def test_initial_commit_preserves_unrelated_staged_entries(self):
        self.git("init", "--template=", "--quiet")
        self.identity()
        self.write("unrelated.txt", "owner staging before first commit\n")
        self.git("add", "--", "unrelated.txt")
        staged = self.git("show", ":unrelated.txt")
        self.begin()
        result = self.checkpoint()
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.git("show", ":unrelated.txt"), staged)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"unrelated.txt\n")
        self.assertEqual(self.git("ls-tree", "--name-only", "HEAD").strip(), b"source.txt")

    def test_selected_staged_initial_source_blocks_without_losing_owner_index(self):
        self.git("init", "--template=", "--quiet")
        self.identity()
        self.git("add", "--", "source.txt")
        self.write("source.txt", "owner staged part plus later unstaged source\n")
        self.begin()
        before = self.git("ls-files", "--stage", "-z")
        result = self.checkpoint()
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.git("ls-files", "--stage", "-z"), before)
        self.assertEqual(self.git("show", ":source.txt"), b"initial owner source\n")
        self.assertEqual(self.git("rev-parse", "--verify", "HEAD", ok=False), b"")

    def test_missing_identity_and_rejecting_hook_are_reported_and_recover_without_duplicate(self):
        self.begin(bootstrap=True)
        self.identity()
        self.git("config", "user.name", "")
        self.git("config", "user.email", "")
        # Empty explicit local identity overrides inherited global configuration;
        # no author is supplied by the tool and no host configuration is edited.
        import os
        environment = {k: v for k, v in os.environ.items() if k not in {
            "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"}}
        with patch.dict(os.environ, environment, clear=True):
            rejected = self.checkpoint()
        self.assertEqual(rejected["status"], "blocked", rejected)
        self.assertEqual(self.git("rev-parse", "--verify", "HEAD", ok=False), b"")
        self.identity()
        hook = self.root / ".git/hooks/pre-commit"
        hook.parent.mkdir(exist_ok=True)
        hook.write_bytes(b"#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        rejected = self.checkpoint()
        self.assertEqual(rejected["status"], "blocked", rejected)
        self.assertEqual(self.git("rev-parse", "--verify", "HEAD", ok=False), b"")
        hook.unlink()
        recovered = self.checkpoint()
        self.assertEqual(recovered["status"], "committed", recovered)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")
        self.assertEqual(self.checkpoint()["status"], "duplicate")


if __name__ == "__main__":
    unittest.main()
