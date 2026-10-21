"""Native repository discovery retains safety while bounding process launches."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "governance-src/runtime-scripts"))
SPEC = importlib.util.spec_from_file_location("git_repository_metadata_runtime", ROOT / "governance-src/runtime-scripts/git_checkpoint.py")
git_checkpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(git_checkpoint)


@unittest.skipUnless(shutil.which("git"), "real Git executable required")
class GitRepositoryMetadataTests(unittest.TestCase):
    def setUp(self):
        self.parent = (ROOT / "eval-workspaces").resolve()
        self.parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="git-metadata-", dir=self.parent)
        self.workspace = Path(self.temporary.name).resolve()
        self.root = self.workspace / "repository with spaces"
        self.root.mkdir()
        self.addCleanup(self.cleanup)
        self.git("init", "--template=", "--quiet")
        for key, value in [("user.name", "UPG metadata calibration"),
                           ("user.email", "metadata@example.invalid"),
                           ("commit.gpgSign", "false"), ("core.autocrlf", "false"),
                           ("core.hooksPath", str(self.root / ".git/hooks"))]:
            self.git("config", key, value)

    def cleanup(self):
        if self.workspace.parent != self.parent or not self.workspace.name.startswith("git-metadata-"):
            raise AssertionError("refusing cleanup outside owned metadata fixture")
        self.temporary.cleanup()

    def git(self, *args):
        result = subprocess.run([shutil.which("git"), *args], cwd=self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout

    def commit(self):
        (self.root / "source.txt").write_bytes(b"metadata fixture\n")
        self.git("add", "--", "source.txt")
        self.git("commit", "--quiet", "-m", "metadata fixture baseline")

    def test_committed_repository_discovery_bounds_native_launches(self):
        self.commit()
        with patch.object(git_checkpoint, "_git", wraps=git_checkpoint._git) as observed:
            root, directory, branch, head, index = git_checkpoint._repo(self.root)
        self.assertEqual(root, self.root)
        self.assertEqual(directory, self.root / ".git")
        self.assertEqual(index, directory / "index")
        self.assertTrue(branch.startswith("refs/heads/"))
        self.assertEqual(head, self.git("rev-parse", "HEAD").decode().strip())
        # The old discovery needed seven subprocesses before status or a stage.
        self.assertLessEqual(observed.call_count, 5)

    def test_unborn_repository_keeps_unresolved_ref_check_within_budget(self):
        with patch.object(git_checkpoint, "_git", wraps=git_checkpoint._git) as observed:
            root, directory, branch, head, index = git_checkpoint._repo(self.root)
        self.assertEqual(root, self.root)
        self.assertIsNone(head)
        self.assertTrue(branch.startswith("refs/heads/"))
        self.assertFalse(index.exists())
        self.assertLessEqual(observed.call_count, 6)

    def test_linked_worktree_uses_its_real_external_admin_and_index(self):
        self.commit()
        linked = self.workspace / "linked with spaces"
        self.git("worktree", "add", "--quiet", "-b", "metadata-linked", str(linked))
        root, directory, branch, head, index = git_checkpoint._repo(linked)
        self.assertEqual(root, linked)
        self.assertEqual(branch, "refs/heads/metadata-linked")
        self.assertNotEqual(directory, linked / ".git")
        self.assertTrue(directory.is_dir())
        self.assertTrue(index.is_file())
        self.assertEqual(head, self.git("rev-parse", "HEAD").decode().strip())

    def test_split_index_is_still_rejected_without_changing_owner_index(self):
        self.commit()
        self.git("update-index", "--split-index")
        index = self.root / ".git/index"
        before = index.read_bytes()
        with self.assertRaisesRegex(git_checkpoint.CheckpointError, "^split-index-unsupported$"):
            git_checkpoint._repo(self.root)
        self.assertEqual(index.read_bytes(), before)

    def test_wrong_top_level_never_grants_ownership(self):
        self.commit()
        nested = self.root / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(git_checkpoint.CheckpointError, "^project-must-be-git-worktree-root$"):
            git_checkpoint._repo(nested)

    def test_metadata_command_failure_keeps_capture_failed_and_index_unchanged(self):
        self.commit()
        index = self.root / ".git/index"
        before = index.read_bytes()
        original = git_checkpoint._git
        def fail_metadata(root, args, *positional, **kwargs):
            if args[0] == "rev-parse" and "--show-toplevel" in args:
                raise git_checkpoint.CheckpointError("git-rev-parse-failed")
            return original(root, args, *positional, **kwargs)
        with patch.object(git_checkpoint, "_git", side_effect=fail_metadata):
            observed = git_checkpoint.capture(self.root, {"allowed_paths": ["."], "status_paths": []})
        self.assertEqual(observed, {"ok": False, "reason": "git-rev-parse-failed"})
        self.assertEqual(index.read_bytes(), before)

    @unittest.skipIf(os.name == "nt", "Windows filenames cannot contain LF")
    def test_newline_worktree_path_keeps_exact_root_identity(self):
        self.commit()
        linked = self.workspace / "linked\nworktree"
        self.git("worktree", "add", "--quiet", "-b", "metadata-newline", str(linked))
        root, directory, branch, head, index = git_checkpoint._repo(linked)
        self.assertEqual(root, linked)
        self.assertEqual(branch, "refs/heads/metadata-newline")
        self.assertTrue(index.is_file())

    @unittest.skipIf(os.name == "nt", "Windows filenames cannot contain LF")
    def test_newline_external_admin_is_not_misread_as_split_index(self):
        self.commit()
        external = self.workspace / "external\nadmin"
        self.git("init", "--quiet", "--separate-git-dir=" + str(external))
        root, directory, branch, head, index = git_checkpoint._repo(self.root)
        self.assertEqual(root, self.root)
        self.assertEqual(directory, external)
        self.assertTrue(index.is_file())
        self.assertEqual(head, self.git("rev-parse", "HEAD").decode().strip())


if __name__ == "__main__":
    unittest.main()
