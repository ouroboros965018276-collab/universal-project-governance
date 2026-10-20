"""Real local Git calibration for bounded stage commits; no model/API calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "governance-src/runtime-scripts"))
import git_checkpoint


@unittest.skipUnless(shutil.which("git"), "real Git executable is required")
class GitCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.workspace_parent = (ROOT / "eval-workspaces").resolve()
        self.workspace_parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="git-checkpoint-unit-", dir=self.workspace_parent)
        self.root = Path(self.temporary.name).resolve()
        self.assertEqual(self.root.parent, self.workspace_parent)
        self.addCleanup(self.cleanup_workspace)
        self.git("init", "--template=", "--quiet")
        self.git("config", "user.name", "UPG local calibration")
        self.git("config", "user.email", "local-calibration@example.invalid")
        self.git("config", "commit.gpgSign", "false")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "core.hooksPath", str(self.root / ".git/hooks"))
        self.write(".gitignore", ".governance/\nignored/\n")
        self.write("source.txt", "original\n")
        self.write("unrelated.txt", "original unrelated\n")
        self.write("PROJECT_STATE.md", "initial state\n")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "fixture baseline")
        self.policy = {"enabled": True, "min_interval_seconds": 300,
                       "allowed_paths": ["."], "status_paths": ["PROJECT_STATE.md"]}
        self.binding = {"git_checkpoint": self.policy}
        self.saved = []
        self.begin()

    def cleanup_workspace(self):
        # TemporaryDirectory recursively deletes only this verified child.
        resolved = Path(self.temporary.name).resolve()
        if resolved.parent != self.workspace_parent or not resolved.name.startswith("git-checkpoint-unit-"):
            raise AssertionError("refusing cleanup outside the owned calibration directory")
        self.temporary.cleanup()

    def git(self, *arguments, ok=True):
        result = subprocess.run([shutil.which("git"), *arguments], cwd=self.root,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def begin(self, workflow="wf"):
        snapshot = git_checkpoint.capture(self.root, self.policy)
        self.assertTrue(snapshot["ok"], snapshot)
        self.policy["start"] = {"workflow_id": workflow, "snapshot": snapshot}

    def save(self, binding):
        self.saved.append(copy.deepcopy(binding))
        self.write(".governance/checkpoint-fixture.json", json.dumps(binding, sort_keys=True))

    def payload(self, paths=("source.txt",), *, status="complete", checkpoint="stage-1", handoff="not-required", git_boundary=None, workflow="wf"):
        result = {"workflow_id": workflow, "status": status, "changed_files": list(paths),
                  "validation": ["observed local fixture validation"], "integrity": "pass",
                  "handoff": handoff, "task": "bounded local Git calibration"}
        if status != "complete":
            result["checkpoint_id"] = checkpoint
        if git_boundary is not None:
            result["git_boundary"] = git_boundary
        return result

    def checkpoint(self, paths=("source.txt",), *, event="event-1", save=None, **kwargs):
        return git_checkpoint.run_checkpoint(self.root, self.binding, self.payload(paths, **kwargs),
                                             event, save or self.save)

    def head(self):
        return self.git("rev-parse", "HEAD").decode().strip()

    def count(self):
        return int(self.git("rev-list", "--count", "HEAD"))

    def changed_in_head(self):
        return set(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "HEAD").decode().split("\0")) - {""}

    def index_entries(self):
        return self.git("ls-files", "--stage", "-z")

    def test_effective_change_commits_once_and_repeated_event_does_not_commit_again(self):
        self.write("source.txt", "verified stage\n")
        result = self.checkpoint()
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.changed_in_head(), {"source.txt"})
        original_head = self.head()
        repeated = self.checkpoint()
        self.assertIn(repeated["status"], {"duplicate", "unchanged"}, repeated)
        self.assertEqual(self.head(), original_head)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")
        self.assertEqual(self.git("diff", "--name-only"), b"")

    def test_no_change_and_status_only_changes_do_not_generate_commits(self):
        before = self.head()
        result = self.checkpoint()
        self.assertEqual(result["status"], "unchanged", result)
        self.write("PROJECT_STATE.md", "status text refreshed\n")
        result = self.checkpoint(("PROJECT_STATE.md",), event="status-refresh")
        self.assertEqual(result["status"], "unchanged", result)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.count(), 1)
        self.assertEqual((self.root / "PROJECT_STATE.md").read_bytes(), b"status text refreshed\n")

    def test_initial_unchanged_event_cannot_commit_later_unvalidated_bytes(self):
        original_head = self.head()
        initial = self.checkpoint(event="unchanged-completion")
        self.assertEqual(initial["status"], "unchanged", initial)
        self.assertEqual(self.head(), original_head)
        self.assertEqual(self.count(), 1)
        self.binding = json.loads((self.root / ".governance/checkpoint-fixture.json").read_text(encoding="utf-8"))
        self.policy = self.binding["git_checkpoint"]
        self.write("source.txt", "later unvalidated bytes after unchanged completion\n")
        retried = self.checkpoint(event="unchanged-completion")
        self.assertEqual(retried["status"], "unchanged", retried)
        self.assertEqual(self.head(), original_head)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.git("show", ":source.txt"), b"original\n")
        self.assertEqual((self.root / "source.txt").read_bytes(), b"later unvalidated bytes after unchanged completion\n")

    def test_unrelated_staged_and_untracked_changes_are_preserved(self):
        self.write("unrelated.txt", "user staged work\n")
        self.git("add", "--", "unrelated.txt")
        staged_before = self.git("show", ":unrelated.txt")
        self.write("unrelated-untracked.txt", "unrelated untracked\n")
        self.write("ignored/cache.txt", "ignored cache\n")
        self.write("source.txt", "verified stage\n")
        result = self.checkpoint()
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.changed_in_head(), {"source.txt"})
        self.assertEqual(self.git("show", ":unrelated.txt"), staged_before)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"unrelated.txt\n")
        self.assertEqual(self.git("show", "HEAD:unrelated.txt"), b"original unrelated\n")
        self.assertEqual((self.root / "unrelated-untracked.txt").read_bytes(), b"unrelated untracked\n")
        self.assertEqual((self.root / "ignored/cache.txt").read_bytes(), b"ignored cache\n")

    def test_selected_partial_staging_blocks_without_losing_index_or_worktree(self):
        self.write("source.txt", "user staged portion\n")
        self.git("add", "--", "source.txt")
        self.write("source.txt", "user staged portion plus unstaged work\n")
        before_head, before_index = self.head(), self.index_entries()
        result = self.checkpoint()
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before_head)
        self.assertEqual(self.index_entries(), before_index)
        self.assertEqual((self.root / "source.txt").read_bytes(), b"user staged portion plus unstaged work\n")

    def test_preexisting_dirty_selected_path_is_not_claimed_by_new_workflow(self):
        self.write("source.txt", "preexisting user edit\n")
        self.begin()
        before = self.head()
        self.write("source.txt", "preexisting user edit with later contribution\n")
        result = self.checkpoint()
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.git("show", ":source.txt"), b"original\n")

    def test_new_deleted_and_literal_special_paths_are_committed_within_scope(self):
        special = "new space 中文 [glob].txt"
        self.write(special, "new scoped source\n")
        (self.root / "source.txt").unlink()
        self.write("outside.txt", "must remain untracked\n")
        result = self.checkpoint((special, "source.txt"))
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.changed_in_head(), {special, "source.txt"})
        self.assertEqual(self.git("show", "HEAD:" + special), b"new scoped source\n")
        self.assertEqual(self.git("ls-files", "--", "outside.txt"), b"")
        self.assertFalse((self.root / "source.txt").exists())

    def test_sensitive_and_ignored_selected_files_never_enter_commit(self):
        self.write(".env", "PRIVATE_TOKEN=local synthetic credential fixture\n")
        self.write("ignored/cache.txt", "ignored data\n")
        before = self.head()
        for path in (".env", "ignored/cache.txt"):
            with self.subTest(path=path):
                result = self.checkpoint((path,), event="excluded-" + path)
                self.assertIn(result["status"], {"blocked", "unchanged"}, result)
                self.assertEqual(self.head(), before)
                self.assertEqual(self.git("ls-files", "--", path), b"")

    def test_recent_partial_stage_defers_and_completion_flushes_pending_change(self):
        self.write("source.txt", "first verified stage\n")
        first = self.checkpoint(status="partial", checkpoint="one", event="stage-one")
        self.assertEqual(first["status"], "committed", first)
        self.write("source.txt", "second verified stage\n")
        second = self.checkpoint(status="partial", checkpoint="two", event="stage-two")
        self.assertEqual(second["status"], "deferred", second)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"first verified stage\n")
        final = self.checkpoint((), event="workflow-complete")
        self.assertEqual(final["status"], "committed", final)
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"second verified stage\n")

    def test_pending_changes_from_another_workflow_do_not_grant_dirty_path_ownership(self):
        self.write("source.txt", "first workflow committed stage\n")
        self.assertEqual(self.checkpoint(status="partial", checkpoint="one", event="first")["status"], "committed")
        self.write("source.txt", "first workflow pending work\n")
        deferred = self.checkpoint(status="partial", checkpoint="two", event="deferred")
        self.assertEqual(deferred["status"], "deferred", deferred)
        before_head, before_index = self.head(), self.index_entries()
        self.begin("wf-b")
        result = self.checkpoint(workflow="wf-b", event="new-workflow-completion")
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before_head)
        self.assertEqual(self.index_entries(), before_index)
        self.assertEqual((self.root / "source.txt").read_bytes(), b"first workflow pending work\n")

    def test_deferred_event_cannot_reuse_validation_after_selected_bytes_change(self):
        self.write("source.txt", "first committed stage\n")
        self.assertEqual(self.checkpoint(status="partial", checkpoint="one", event="first")["status"], "committed")
        self.write("source.txt", "validated deferred bytes X\n")
        deferred = self.checkpoint(status="partial", checkpoint="two", event="deferred")
        self.assertEqual(deferred["status"], "deferred", deferred)
        self.write("source.txt", "later unvalidated bytes Y\n")
        self.policy["last_commit"]["recorded_at"] = 0
        before = self.head()
        stale_retry = self.checkpoint(status="partial", checkpoint="two", event="deferred")
        self.assertEqual(stale_retry["status"], "blocked", stale_retry)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.count(), 2)
        fresh = self.checkpoint(status="partial", checkpoint="three", event="fresh-stage")
        self.assertEqual(fresh["status"], "committed", fresh)
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"later unvalidated bytes Y\n")

    def test_reverted_deferred_change_clears_pending_state_without_extra_commit(self):
        self.write("source.txt", "first verified committed stage\n")
        self.assertEqual(self.checkpoint(status="partial", checkpoint="one", event="first")["status"], "committed")
        self.write("source.txt", "deferred work later reverted\n")
        deferred = self.checkpoint(status="partial", checkpoint="two", event="deferred-reverted")
        self.assertEqual(deferred["status"], "deferred", deferred)
        self.assertTrue(any(entry.get("workflow_id") == "wf" for entry in self.policy.get("deferred_events", {}).values()))
        committed = self.head()
        self.write("source.txt", self.git("show", "HEAD:source.txt").decode("utf-8"))
        completed = self.checkpoint((), event="workflow-complete")
        self.assertEqual(completed["status"], "unchanged", completed)
        self.assertEqual(self.head(), committed)
        self.assertEqual(self.count(), 2)
        self.assertFalse(self.policy.get("pending_paths"))
        self.assertFalse(any(entry.get("workflow_id") == "wf" for entry in self.policy.get("deferred_events", {}).values()))
        durable = json.loads((self.root / ".governance/checkpoint-fixture.json").read_text(encoding="utf-8"))["git_checkpoint"]
        self.assertFalse(durable.get("pending_paths"))
        self.assertFalse(any(entry.get("workflow_id") == "wf" for entry in durable.get("deferred_events", {}).values()))
        retried = self.checkpoint(status="partial", checkpoint="two", event="deferred-reverted")
        self.assertEqual(retried["status"], "unchanged", retried)
        self.assertEqual(self.head(), committed)
        self.assertEqual(self.count(), 2)
        self.write("source.txt", "new unvalidated work after completed no-op\n")
        stale_retry = self.checkpoint(status="partial", checkpoint="two", event="deferred-reverted")
        self.assertEqual(stale_retry["status"], "unchanged", stale_retry)
        self.assertEqual(self.head(), committed)
        self.assertEqual(self.count(), 2)
        self.assertEqual((self.root / "source.txt").read_bytes(), b"new unvalidated work after completed no-op\n")

    def test_handoff_boundary_flushes_inside_cadence_window(self):
        self.write("source.txt", "first verified stage\n")
        self.assertEqual(self.checkpoint(status="partial", event="first")["status"], "committed")
        self.write("source.txt", "handoff verified stage\n")
        result = self.checkpoint(status="partial", checkpoint="handoff", event="handoff", handoff="updated", git_boundary="handoff")
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.count(), 3)

    def test_updating_handoff_document_alone_does_not_bypass_partial_stage_cadence(self):
        self.write("source.txt", "first verified stage\n")
        first = self.checkpoint(status="partial", checkpoint="one", event="first", handoff="updated")
        self.assertEqual(first["status"], "committed", first)
        self.write("source.txt", "second verified stage\n")
        second = self.checkpoint(status="partial", checkpoint="two", event="second", handoff="updated")
        self.assertEqual(second["status"], "deferred", second)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"first verified stage\n")

    def test_failed_validation_blocks_a_commit(self):
        self.write("source.txt", "not verified\n")
        payload = self.payload()
        payload["integrity"] = "fail"
        before = self.head()
        result = git_checkpoint.run_checkpoint(self.root, self.binding, payload, "invalid-stage", self.save)
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")

    def test_project_subdirectory_cannot_adopt_parent_repository_for_commits(self):
        child = self.root / "nested-project-without-git"
        child.mkdir()
        snapshot = git_checkpoint.capture(child, self.policy)
        self.assertFalse(snapshot["ok"], snapshot)
        self.assertEqual(self.count(), 1)
        self.assertFalse((child / ".git").exists())

    def test_disabled_policy_leaves_git_and_binding_unchanged(self):
        self.write("source.txt", "authorized project work without commit opt-in\n")
        self.policy["enabled"] = False
        before_head, before_index = self.head(), self.index_entries()
        before_binding = copy.deepcopy(self.binding)
        result = self.checkpoint()
        self.assertEqual(result["status"], "disabled", result)
        self.assertEqual(self.head(), before_head)
        self.assertEqual(self.index_entries(), before_index)
        self.assertEqual(self.binding, before_binding)
        self.assertEqual(self.saved, [])

    def test_linked_worktree_git_file_uses_its_own_head_and_index(self):
        original_root = self.root
        original_head = self.head()
        linked = (original_root / "linked-worktree").resolve()
        self.assertEqual(linked.parent, original_root)
        self.git("worktree", "add", "--quiet", "-b", "calibration-linked", str(linked), "HEAD")
        self.assertTrue((linked / ".git").is_file())
        self.root = linked
        try:
            self.begin()
            self.write("source.txt", "verified linked worktree stage\n")
            result = self.checkpoint()
            self.assertEqual(result["status"], "committed", result)
            self.assertEqual(self.count(), 2)
            self.assertEqual(self.git("show", "HEAD:source.txt"), b"verified linked worktree stage\n")
            self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")
        finally:
            self.root = original_root
        self.assertEqual(self.head(), original_head)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.git("show", ":source.txt"), b"original\n")

    def test_head_moved_after_baseline_does_not_silently_commit_to_new_parent(self):
        self.write("unrelated.txt", "external commit\n")
        self.git("add", "--", "unrelated.txt")
        self.git("commit", "--quiet", "-m", "external concurrent stage")
        before = self.head()
        self.write("source.txt", "verified against old parent\n")
        result = self.checkpoint()
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before)

    def test_concurrent_branch_publication_is_not_overwritten_by_prepared_stage(self):
        parent = self.head()
        branch = self.git("symbolic-ref", "HEAD").decode().strip()

        def git_input(arguments, raw):
            process = subprocess.run([shutil.which("git"), *arguments], cwd=self.root, input=raw,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
            return process.stdout.strip()

        unrelated_blob = git_input(["hash-object", "-w", "--stdin"], b"concurrent unrelated committed work\n")
        entries = self.git("ls-tree", "-z", "HEAD").split(b"\0")
        concurrent_entries = [b"100644 blob " + unrelated_blob + b"\tunrelated.txt"
                              if entry.endswith(b"\tunrelated.txt") else entry for entry in entries if entry]
        concurrent_tree = git_input(["mktree", "-z"], b"\0".join(concurrent_entries) + b"\0").decode()
        concurrent_commit = self.git("commit-tree", concurrent_tree, "-p", parent, "-m", "concurrent owner commit").decode().strip()
        artifact = self.root / ".governance/concurrent-index"
        artifact.parent.mkdir(exist_ok=True)
        real_git = git_checkpoint._git
        real_git(self.root, ["read-tree", concurrent_tree], index=artifact)
        concurrent_index = artifact.read_bytes()
        real_index = Path(self.git("rev-parse", "--git-path", "index").decode().strip())
        if not real_index.is_absolute():
            real_index = self.root / real_index
        self.write("source.txt", "prepared verified source stage\n")
        injected = {"seen": False}

        def publish_other_owner_before_compare_and_swap(root, arguments, *args, **kwargs):
            if arguments[:2] == ["update-ref", branch] and not injected["seen"]:
                injected["seen"] = True
                self.git("update-ref", branch, concurrent_commit, parent)
                # Model an owner which publishes its prepared index alongside
                # its ref. Every tree and index was built by real Git above.
                real_index.write_bytes(concurrent_index)
            return real_git(root, arguments, *args, **kwargs)

        git_checkpoint._git = publish_other_owner_before_compare_and_swap
        try:
            result = self.checkpoint()
        finally:
            git_checkpoint._git = real_git
        self.assertTrue(injected["seen"], "fixture must advance the actual branch before publication")
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), concurrent_commit)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("show", "HEAD:unrelated.txt"), b"concurrent unrelated committed work\n")
        self.assertEqual(self.git("show", "HEAD:source.txt"), b"original\n")
        self.assertEqual(real_index.read_bytes(), concurrent_index)
        self.assertEqual(self.git("show", ":unrelated.txt"), b"concurrent unrelated committed work\n")
        self.assertEqual((self.root / "source.txt").read_bytes(), b"prepared verified source stage\n")

    def test_rejecting_hook_preserves_head_index_and_worktree(self):
        hook = self.root / ".git/hooks/pre-commit"
        hook.parent.mkdir(exist_ok=True)
        hook.write_bytes(b"#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.write("unrelated.txt", "user staged work\n")
        self.git("add", "--", "unrelated.txt")
        self.write("source.txt", "verified stage\n")
        before_head, before_index = self.head(), self.index_entries()
        result = self.checkpoint()
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before_head)
        self.assertEqual(self.index_entries(), before_index)
        self.assertEqual((self.root / "source.txt").read_bytes(), b"verified stage\n")
        hook.unlink()
        retried = self.checkpoint()
        self.assertEqual(retried["status"], "committed", retried)
        self.assertEqual(self.count(), 2)

    def test_selected_file_changed_after_preparation_is_not_committed_as_verified(self):
        self.write("source.txt", "verified stage\n")
        before_head, before_index = self.head(), self.index_entries()
        changed = {"seen": False}

        def save_and_change_file(binding):
            self.save(binding)
            if binding["git_checkpoint"].get("journal", {}).get("status") == "prepared" and not changed["seen"]:
                changed["seen"] = True
                self.write("source.txt", "concurrent unverified edit\n")

        result = self.checkpoint(save=save_and_change_file)
        self.assertTrue(changed["seen"], "fixture must change the real file after preparation")
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(self.head(), before_head)
        self.assertEqual(self.index_entries(), before_index)
        self.assertEqual((self.root / "source.txt").read_bytes(), b"concurrent unverified edit\n")

    def test_native_index_lock_refuses_concurrent_staging_and_preserves_user_work(self):
        self.write("source.txt", "verified stage\n")
        changed = {"seen": False, "returncode": None, "stderr": b""}

        def save_and_stage_unrelated(binding):
            self.save(binding)
            if binding["git_checkpoint"].get("journal", {}).get("status") == "prepared" and not changed["seen"]:
                changed["seen"] = True
                self.write("unrelated.txt", "concurrent staged user edit\n")
                process = subprocess.run([shutil.which("git"), "add", "--", "unrelated.txt"],
                                         cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                changed["returncode"], changed["stderr"] = process.returncode, process.stderr

        result = self.checkpoint(save=save_and_stage_unrelated)
        self.assertTrue(changed["seen"], "fixture must attempt real staging after preparation")
        self.assertNotEqual(changed["returncode"], 0)
        self.assertIn(b"index.lock", changed["stderr"])
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(self.changed_in_head(), {"source.txt"})
        self.assertEqual(self.git("show", ":unrelated.txt"), b"original unrelated\n")
        self.assertEqual((self.root / "unrelated.txt").read_bytes(), b"concurrent staged user edit\n")

    def test_commit_success_before_receipt_failure_is_recovered_without_duplicate(self):
        self.write("source.txt", "verified stage\n")
        initial_count = self.count()
        crash = {"seen": False}

        def save_then_interrupt(binding):
            if self.count() > initial_count and not crash["seen"]:
                crash["seen"] = True
                raise RuntimeError("controlled receipt interruption after real commit")
            self.save(binding)

        try:
            self.checkpoint(save=save_then_interrupt)
        except RuntimeError as error:
            self.assertIn("controlled receipt interruption", str(error))
        self.assertTrue(crash["seen"], "fixture must interrupt after an observed real commit")
        self.assertEqual(self.count(), 2)
        self.binding = json.loads((self.root / ".governance/checkpoint-fixture.json").read_text(encoding="utf-8"))
        self.policy = self.binding["git_checkpoint"]
        after = self.head()
        retried = self.checkpoint()
        self.assertIn(retried["status"], {"committed", "duplicate", "unchanged"}, retried)
        self.assertEqual(self.head(), after)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")

    def test_real_commit_with_lost_command_response_is_proven_and_not_repeated(self):
        self.write("source.txt", "verified stage despite lost response\n")
        branch = self.git("symbolic-ref", "HEAD").decode().strip()
        real_git = git_checkpoint._git
        real_commits = []

        def real_git_with_lost_commit_response(root, arguments, *args, **kwargs):
            process = real_git(root, arguments, *args, **kwargs)
            if arguments[:2] == ["update-ref", branch]:
                self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
                real_commits.append(self.head())
                raise git_checkpoint.CheckpointError("git-command-timeout")
            return process

        # Every Git call runs the real executable. Only the already-published
        # successful stage's return is lost at the response boundary.
        git_checkpoint._git = real_git_with_lost_commit_response
        try:
            result = self.checkpoint()
        finally:
            git_checkpoint._git = real_git
        self.assertEqual(result["status"], "committed", result)
        self.assertEqual(len(real_commits), 1)
        self.assertEqual(self.count(), 2)
        committed = self.head()
        self.assertEqual(self.git("show", ":source.txt"), b"verified stage despite lost response\n")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")
        self.assertEqual(self.git("diff", "--name-only"), b"")
        retried = self.checkpoint()
        self.assertEqual(retried["status"], "duplicate", retried)
        self.assertEqual(self.head(), committed)
        self.assertEqual(self.count(), 2)

    def test_persisted_uncertainty_after_real_commit_recovers_by_git_proof(self):
        self.write("source.txt", "verified stage awaiting recovery proof\n")
        interrupted = {"seen": False}

        def persist_uncertainty_after_commit(binding):
            journal = binding["git_checkpoint"].get("journal", {})
            if journal.get("status") == "committed" and not interrupted["seen"]:
                interrupted["seen"] = True
                journal["status"] = "uncertain"
                self.save(binding)
                raise RuntimeError("controlled restart with uncertain persisted commit")
            self.save(binding)

        with self.assertRaisesRegex(RuntimeError, "uncertain persisted commit"):
            self.checkpoint(save=persist_uncertainty_after_commit)
        self.assertTrue(interrupted["seen"])
        self.assertEqual(self.count(), 2)
        committed = self.head()
        self.binding = json.loads((self.root / ".governance/checkpoint-fixture.json").read_text(encoding="utf-8"))
        self.policy = self.binding["git_checkpoint"]
        self.assertEqual(self.policy["journal"]["status"], "uncertain")
        self.assertEqual(self.git("show", ":source.txt"), b"original\n")
        recovered = self.checkpoint()
        self.assertEqual(recovered["status"], "committed", recovered)
        self.assertEqual(recovered["commit"], committed)
        self.assertEqual(self.head(), committed)
        self.assertEqual(self.count(), 2)
        self.assertNotIn("journal", self.policy)
        self.assertEqual(self.git("show", ":source.txt"), b"verified stage awaiting recovery proof\n")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")
        retried = self.checkpoint()
        self.assertEqual(retried["status"], "duplicate", retried)
        self.assertEqual(self.head(), committed)
        self.assertEqual(self.count(), 2)


if __name__ == "__main__":
    unittest.main()
