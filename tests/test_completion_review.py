"""Final-state completion review gates; synthetic and local Git evidence only."""
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

from registration_fixture import change, reviewed_report
from test_completion_outcomes import report, write

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "governance-src/runtime-scripts"))
SPEC = importlib.util.spec_from_file_location("review_project_tool", ROOT / "governance-src/runtime-scripts/project_tool.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)
import completion_review
import git_checkpoint


class CompletionReviewTests(unittest.TestCase):
    def setUp(self):
        runtime_index = json.loads((ROOT / "universal-project-governance/policy-index.json").read_text(encoding="utf-8"))
        self.index_patch = patch.object(tool, "index", return_value=runtime_index)
        self.index_patch.start()
        self.addCleanup(self.index_patch.stop)
        temporary = tempfile.TemporaryDirectory(prefix="completion-review-", dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def begin(self, reporting=False):
        tool.ensure(self.root, field_test_reporting=reporting)
        start = dict(workflow_id="reviewed-task", change=change())
        tool.begin_workflow(self.root, write(self.root / ".governance/start.json", start))
        return start

    def payload(self, start, paths=("runtime.py",)):
        value = report(start)
        value["changed_files"] = list(paths)
        return reviewed_report(value, self.root)

    def finish(self, value, direct=False):
        path = write(self.root / ".governance/finish.json", value)
        return (tool.record_report if direct else tool.finish_workflow)(self.root, path)

    def durable(self):
        return {path.name: path.read_bytes() for path in (self.root / ".governance").glob("*.json")
                if path.name not in {"start.json", "finish.json"}}

    def test_missing_receipt_rejected_before_durable_write_in_both_modes(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting):
                start = self.begin(reporting)
                value = self.payload(start)
                value.pop("completion_review")
                before = self.durable()
                with self.assertRaisesRegex(ValueError, "requires completion_review"):
                    self.finish(value)
                self.assertEqual(self.durable(), before)
                self.assertIsNotNone(tool.status(self.root)["active_workflow"])

    def test_review_and_audit_must_pass_without_unresolved_findings(self):
        start = self.begin()
        for name in ("review", "audit"):
            for field, bad in (("status", "failed"), ("status", "pending"), ("findings", ["unresolved defect"])):
                value = self.payload(start)
                value["completion_review"][name][field] = bad
                before = self.durable()
                with self.subTest(name=name, field=field, bad=bad), self.assertRaisesRegex(ValueError, "passed review and audit"):
                    self.finish(value)
                self.assertEqual(self.durable(), before)

    def test_narrative_evidence_is_bounded_and_cannot_be_empty_or_secret(self):
        start = self.begin()
        for evidence in ([], [" "], ["x" * 1001], ["api_key=" + "a" * 20]):
            value = self.payload(start)
            value["completion_review"]["audit"]["evidence"] = evidence
            before = self.durable()
            with self.subTest(evidence_length=len(str(evidence))), self.assertRaises(ValueError):
                self.finish(value)
            self.assertEqual(self.durable(), before)

    def test_changed_files_coverage_and_duplicate_paths_are_exact(self):
        start = self.begin()
        value = self.payload(start)
        for paths in ([], ["other.py"], ["runtime.py", "runtime.py"]):
            bad = copy.deepcopy(value)
            bad["changed_files"] = paths
            with self.subTest(paths=paths), self.assertRaisesRegex(ValueError, "exactly|duplicate"):
                self.finish(bad)
        value["completion_review"]["files"].append(copy.deepcopy(value["completion_review"]["files"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.finish(value)

    def test_current_bytes_and_executable_mode_are_required(self):
        start = self.begin()
        source = self.root / "runtime.py"
        source.write_bytes(b"value = 1\n")
        value = self.payload(start)
        source.write_bytes(b"value = 2\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.finish(value)
        value = self.payload(start)
        value["completion_review"]["files"][0]["executable"] = 73 if source.stat().st_mode & 0o111 == 0 else 0
        with self.assertRaisesRegex(ValueError, "stale"):
            self.finish(value)

    def test_deleted_files_are_reviewed_and_recreation_invalidates_receipt(self):
        source = self.root / "runtime.py"
        source.write_bytes(b"retired implementation\n")
        start = self.begin()
        source.unlink()
        value = self.payload(start)
        self.assertIsNone(value["completion_review"]["files"][0]["sha256"])
        source.write_bytes(b"unexpected recreation\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.finish(value)
        source.unlink()
        self.finish(value)
        self.assertIsNone(tool.status(self.root)["active_workflow"])

    def test_safe_paths_and_tool_bookkeeping_cannot_be_reviewed(self):
        start = self.begin()
        for relative in ("../outside.py", "C:/outside.py", "sub\\file.py", ".git/config", ".governance/upg.json"):
            value = self.payload(start, ())
            value["changed_files"] = [relative]
            value["completion_review"]["files"] = [dict(path=relative, sha256=None, executable=0)]
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.finish(value)

    def test_direct_report_cannot_bypass_gate_without_active_workflow(self):
        tool.ensure(self.root, field_test_reporting=True)
        start = dict(workflow_id="direct-observation", change=change())
        value = self.payload(start)
        value.pop("completion_review")
        with self.assertRaisesRegex(ValueError, "requires completion_review"):
            self.finish(value, direct=True)
        self.assertEqual(tool.status(self.root)["report_count"], 0)
        value = self.payload(start)
        self.finish(value, direct=True)
        self.assertEqual(tool.status(self.root)["report_count"], 1)

    def test_reporting_off_retains_compact_receipt_without_new_ledger(self):
        start = self.begin()
        value = self.payload(start)
        self.finish(value)
        state = tool.status(self.root)
        self.assertEqual(state["latest_change"]["completion_review"], value["completion_review"])
        self.assertFalse((self.root / ".governance/field-reports.json").exists())
        self.assertTrue(self.finish(value)["idempotent"])

    def test_partial_and_blocked_do_not_require_or_claim_final_review(self):
        start = self.begin()
        for status in ("partial", "blocked"):
            value = report(start, status)
            value["checkpoint_id"] = status + "-stage"
            self.finish(value)
            self.assertEqual(tool.status(self.root)["active_workflow"]["last_outcome"]["status"], status)
        self.assertIsNone(tool.status(self.root)["latest_change"])

    def test_pending_ledger_drift_recovers_through_explicit_fresh_review(self):
        start = self.begin(True)
        source = self.root / "runtime.py"
        source.write_bytes(b"reviewed\n")
        value = self.payload(start)
        with patch.object(tool, "_reconcile_completion", side_effect=OSError("synthetic crash")):
            with self.assertRaises(OSError):
                self.finish(value)
        source.write_bytes(b"later change\n")
        recovered = self.finish(value)
        self.assertFalse(recovered["completed"])
        state = tool.status(self.root)
        self.assertFalse(state["ok"])
        self.assertEqual(state["reason"], "completion-review-pending")
        self.assertIsNone(state["active_workflow"])
        self.assertEqual(state["completion_review_pending"]["paths"], ["runtime.py"])
        fresh = dict(workflow_id="fresh-review", change=change())
        fresh["change"]["parent_event_id"] = state["latest_change"]["event_id"]
        tool.begin_workflow(self.root, write(self.root / ".governance/fresh-start.json", fresh))
        with self.assertRaisesRegex(ValueError, "pending recovery scope"):
            self.finish(self.payload(fresh, ()))
        self.finish(self.payload(fresh))
        final = tool.status(self.root)
        self.assertTrue(final["ok"])
        self.assertIsNone(final["completion_review_pending"])
        self.assertIsNone(final["active_workflow"])
        ledger = tool.load_json(self.root / ".governance/field-reports.json")
        self.assertEqual(len(ledger["reports"]), 2)
        self.assertEqual(ledger["reports"][0]["completion_review"], value["completion_review"])
        self.assertTrue(self.finish(value)["idempotent"])
        self.assertEqual(tool.status(self.root)["latest_change"], final["latest_change"])

    def test_legacy_completed_receipt_is_readable_and_exact_retry_stays_historical(self):
        for reporting in (False, True):
            with self.subTest(reporting=reporting):
                start = self.begin(reporting)
                value = self.payload(start)
                self.finish(value)
                legacy = copy.deepcopy(value)
                legacy.pop("completion_review")
                binding_path = self.root / ".governance/upg.json"
                binding = tool.load_json(binding_path)
                binding["latest_change"].pop("completion_review")
                binding["latest_change"]["payload_sha256"] = tool._completion_payload_sha256(legacy)
                tool.write_json_atomic(binding_path, binding)
                if reporting:
                    ledger_path = self.root / ".governance/field-reports.json"
                    ledger = tool.load_json(ledger_path)
                    ledger["reports"][0].pop("completion_review")
                    tool.write_json_atomic(ledger_path, ledger)
                (self.root / "runtime.py").write_bytes(b"later unrelated bytes\n")
                self.assertTrue(self.finish(legacy)["idempotent"])
                self.assertIsNone(tool.status(self.root)["active_workflow"])
                (self.root / "runtime.py").unlink()
                # Each subcase gets a fresh independent binding.
                shutil.rmtree(self.root / ".governance")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def git_repo(self):
        for args in (("init", "--template=", "--quiet"), ("config", "user.name", "UPG fixture"),
                     ("config", "user.email", "fixture@example.invalid"), ("config", "core.autocrlf", "false"),
                     ("config", "commit.gpgSign", "false")):
            self.git(*args)
        (self.root / ".gitignore").write_bytes(b".governance/\n")
        (self.root / "runtime.py").write_bytes(b"initial\n")
        (self.root / "other.py").write_bytes(b"other initial\n")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "baseline")

    def git(self, *args):
        result = subprocess.run([shutil.which("git"), *args], cwd=self.root, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout

    def git_begin(self, reporting=False):
        tool.ensure(self.root, field_test_reporting=reporting)
        tool.configure_git(self.root, True, ["."], [], 300)
        return self.begin(reporting)

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_git_omission_covers_untracked_deleted_and_committed_changes(self):
        self.git_repo()
        start = self.git_begin(True)
        (self.root / "runtime.py").write_bytes(b"current\n")
        (self.root / "other.py").unlink()
        (self.root / "new.py").write_bytes(b"new\n")
        for omitted in ("other.py", "new.py"):
            all_paths = ["runtime.py", "other.py", "new.py"]
            before = self.durable()
            with self.subTest(omitted=omitted), self.assertRaisesRegex(ValueError, "omits observed Git changes"):
                self.finish(self.payload(start, [path for path in all_paths if path != omitted]))
            self.assertEqual(self.durable(), before)
        self.git("add", "new.py")
        self.git("commit", "--quiet", "-m", "external stage")
        with self.assertRaisesRegex(ValueError, "omits observed Git changes"):
            self.finish(self.payload(start, ["runtime.py", "other.py"]))

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_unchanged_preexisting_dirty_path_is_exempt_but_later_changes_are_not(self):
        self.git_repo()
        other = self.root / "other.py"
        other.write_bytes(b"preexisting owner edit\n")
        start = self.git_begin()
        (self.root / "runtime.py").write_bytes(b"current\n")
        value = self.payload(start)
        other.write_bytes(b"later owner edit\n")
        with self.assertRaisesRegex(ValueError, "omits observed Git changes"):
            self.finish(value)
        other.write_bytes(b"preexisting owner edit\n")
        result = self.finish(value)
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        self.assertEqual(other.read_bytes(), b"preexisting owner edit\n")
        self.assertEqual(self.git("status", "--porcelain").decode().strip(), "M other.py")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_drift_after_outcome_publication_cannot_be_committed(self):
        self.git_repo()
        start = self.git_begin()
        source = self.root / "runtime.py"
        source.write_bytes(b"reviewed\n")
        value = self.payload(start)
        original = git_checkpoint.run_checkpoint
        def concurrent_change(*args, **kwargs):
            source.write_bytes(b"unreviewed concurrent edit\n")
            return original(*args, **kwargs)
        with patch.object(git_checkpoint, "run_checkpoint", side_effect=concurrent_change):
            result = self.finish(value)
        self.assertEqual(result["git_checkpoint"]["status"], "blocked", result)
        self.assertEqual(result["git_checkpoint"]["reason"], "validated-source-drift")
        self.assertFalse(tool.status(self.root)["ok"])
        self.assertEqual(tool.status(self.root)["reason"], "completion-review-pending")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")
        self.assertFalse(result["completed"])
        self.complete_recovery()
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"2")

    def complete_recovery(self):
        state = tool.status(self.root)
        fresh = dict(workflow_id="fresh-reviewed-recovery", change=change())
        fresh["change"]["parent_event_id"] = state["latest_change"]["event_id"]
        tool.begin_workflow(self.root, write(self.root / ".governance/recovery-start.json", fresh))
        result = self.finish(self.payload(fresh, state["completion_review_pending"]["paths"]))
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        self.assertTrue(tool.status(self.root)["ok"])
        self.assertIsNone(tool.status(self.root)["completion_review_pending"])

    def test_config_and_sensitive_file_hashes_are_allowed_without_exporting_content(self):
        start = self.begin()
        (self.root / ".codex").mkdir()
        (self.root / ".codex/config.toml").write_bytes(b"task configuration\n")
        (self.root / ".env").write_bytes(b"private source contents\n")
        value = self.payload(start, [".codex/config.toml", ".env"])
        self.finish(value)
        self.assertNotIn("private source contents", json.dumps(tool.status(self.root)))

    def test_bookkeeping_case_aliases_are_rejected(self):
        start = self.begin()
        value = self.payload(start, ())
        value["changed_files"] = [".Governance/Upg.json"]
        value["completion_review"]["files"] = [dict(path=".Governance/Upg.json", sha256=None, executable=0)]
        with self.assertRaisesRegex(ValueError, "tool-owned"):
            self.finish(value)

    def test_capture_cli_outputs_only_file_facts_and_rejects_unsafe_scope(self):
        (self.root / "runtime.py").write_bytes(b"observed bytes\n")
        helper = ROOT / "governance-src/runtime-scripts/completion_review.py"
        command = [sys.executable, "-B", str(helper), str(self.root), "--path", "runtime.py", "--path", "deleted.py"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(result.stdout)
        self.assertEqual(set(facts), {"files"})
        self.assertEqual([entry["path"] for entry in facts["files"]], ["runtime.py", "deleted.py"])
        self.assertIsNone(facts["files"][1]["sha256"])
        invalid = subprocess.run(command + ["--path", "../outside.py"], capture_output=True, text=True, check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(invalid.stdout, "")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_git_lifecycle_inputs_do_not_require_impossible_self_hashes(self):
        self.git_repo()
        (self.root / ".gitignore").write_bytes(b"# governance deliberately not ignored\n")
        self.git("add", ".gitignore")
        self.git("commit", "--quiet", "-m", "include all governance infrastructure")
        start = self.git_begin()
        (self.root / "runtime.py").write_bytes(b"reviewed\n")
        result = self.finish(self.payload(start))
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        self.assertTrue((self.root / ".governance/finish.json").exists())

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_staged_change_restored_in_worktree_cannot_be_omitted(self):
        self.git_repo()
        start = self.git_begin()
        other = self.root / "other.py"
        original = other.read_bytes()
        other.write_bytes(b"unreviewed staged source\n")
        self.git("add", "other.py")
        other.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "omits observed Git changes"):
            self.finish(self.payload(start, ()))
        self.assertIsNotNone(tool.status(self.root)["active_workflow"])

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_legacy_dirty_baseline_keeps_owner_edits_and_declared_scope_compatible(self):
        self.git_repo()
        other = self.root / "other.py"
        other.write_bytes(b"owner edit before upgrade\n")
        start = self.git_begin()
        binding_path = self.root / ".governance/upg.json"
        binding = tool.load_json(binding_path)
        binding["active_workflow"].pop("completion_baseline")
        tool.write_json_atomic(binding_path, binding)
        (self.root / "runtime.py").write_bytes(b"reviewed upgrade change\n")
        result = self.finish(self.payload(start))
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        self.assertEqual(other.read_bytes(), b"owner edit before upgrade\n")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_prior_owned_partial_commit_and_current_changes_finish_together(self):
        self.git_repo()
        start = self.git_begin()
        (self.root / "runtime.py").write_bytes(b"first owned stage\n")
        stage = report(start, "partial")
        stage["checkpoint_id"] = "first-stage"
        result = self.finish(stage)
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        (self.root / "other.py").write_bytes(b"final owned stage\n")
        result = self.finish(self.payload(start, ["runtime.py", "other.py"]))
        self.assertEqual(result["git_checkpoint"]["status"], "committed", result)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"3")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_git_ledger_drift_recovery_carries_only_original_owned_scope(self):
        self.git_repo()
        owner = self.root / "other.py"
        owner.write_bytes(b"unrelated owner edit\n")
        start = self.git_begin(True)
        source = self.root / "runtime.py"
        source.write_bytes(b"original reviewed bytes\n")
        value = self.payload(start)
        with patch.object(tool, "_reconcile_completion", side_effect=OSError("synthetic crash")):
            with self.assertRaises(OSError):
                self.finish(value)
        source.write_bytes(b"later bytes requiring review\n")
        result = self.finish(value)
        self.assertFalse(result["completed"])
        self.assertEqual(result["completion_review_pending"]["git_owned_paths"], ["runtime.py"])
        self.complete_recovery()
        self.assertEqual(owner.read_bytes(), b"unrelated owner edit\n")
        self.assertEqual(self.git("status", "--porcelain").decode().strip(), "M other.py")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_dirty_index_change_cannot_gain_unchanged_worktree_exemption(self):
        self.git_repo()
        other = self.root / "other.py"
        other.write_bytes(b"owner working tree\n")
        start = self.git_begin()
        other.write_bytes(b"new staged bytes\n")
        self.git("add", "other.py")
        other.write_bytes(b"owner working tree\n")
        with self.assertRaisesRegex(ValueError, "omits observed Git changes"):
            self.finish(self.payload(start, ()))

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_recovery_does_not_adopt_owner_changes_after_switching_branches(self):
        self.git_repo()
        self.git("branch", "other-owner-branch")
        start = self.git_begin(True)
        source = self.root / "runtime.py"
        source.write_bytes(b"reviewed branch A implementation\n")
        original = self.payload(start)
        with patch.object(tool, "_reconcile_completion", side_effect=OSError("synthetic crash")):
            with self.assertRaises(OSError):
                self.finish(original)
        self.git("switch", "--quiet", "other-owner-branch")
        source.write_bytes(b"unrelated owner changes on branch B\n")
        recovered = self.finish(original)
        self.assertFalse(recovered["completed"])
        state = tool.status(self.root)
        fresh = dict(workflow_id="branch-b-fresh-review", change=change())
        fresh["change"]["parent_event_id"] = state["latest_change"]["event_id"]
        tool.begin_workflow(self.root, write(self.root / ".governance/branch-b-start.json", fresh))
        result = self.finish(self.payload(fresh))
        self.assertEqual(result["git_checkpoint"]["status"], "blocked", result)
        self.assertEqual(result["git_checkpoint"]["reason"], "preexisting-dirty-path")
        self.assertEqual(source.read_bytes(), b"unrelated owner changes on branch B\n")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")

    def prepare_owned_recovery(self):
        start = self.git_begin(True)
        source = self.root / "runtime.py"
        source.write_bytes(b"reviewed implementation\n")
        original = self.payload(start)
        with patch.object(tool, "_reconcile_completion", side_effect=OSError("synthetic crash")):
            with self.assertRaises(OSError):
                self.finish(original)
        source.write_bytes(b"later bytes requiring fresh review\n")
        self.finish(original)
        return source

    def assert_recovery_does_not_transfer(self):
        state = tool.status(self.root)
        fresh = dict(workflow_id="identity-guarded-fresh-review", change=change())
        fresh["change"]["parent_event_id"] = state["latest_change"]["event_id"]
        tool.begin_workflow(self.root, write(self.root / ".governance/guarded-start.json", fresh))
        self.assertFalse(tool.status(self.root)["git_checkpoint"].get("pending_paths"))
        result = self.finish(self.payload(fresh))
        self.assertEqual(result["git_checkpoint"]["status"], "blocked", result)
        self.assertEqual(result["git_checkpoint"]["reason"], "preexisting-dirty-path")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_recovery_identity_is_rechecked_after_marker_before_begin(self):
        self.git_repo()
        self.git("branch", "other-owner-branch")
        source = self.prepare_owned_recovery()
        marker = tool.status(self.root)["completion_review_pending"]
        self.assertIn("git_identity", marker)
        self.assertEqual(marker["git_owned_paths"], ["runtime.py"])
        self.git("switch", "--quiet", "other-owner-branch")
        source.write_bytes(b"branch B owner bytes\n")
        self.assert_recovery_does_not_transfer()
        self.assertEqual(source.read_bytes(), b"branch B owner bytes\n")
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_recovery_does_not_transfer_ownership_after_unproven_head_change(self):
        self.git_repo()
        self.prepare_owned_recovery()
        (self.root / "other.py").write_bytes(b"external owner's committed update\n")
        self.git("add", "other.py")
        self.git("commit", "--quiet", "-m", "external owner head")
        self.assert_recovery_does_not_transfer()
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"2")

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_legacy_recovery_marker_without_git_identity_cannot_adopt_dirty_files(self):
        self.git_repo()
        self.prepare_owned_recovery()
        binding_path = self.root / ".governance/upg.json"
        binding = tool.load_json(binding_path)
        binding["completion_review_pending"].pop("git_identity")
        tool.write_json_atomic(binding_path, binding)
        self.assert_recovery_does_not_transfer()

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_recovery_identity_change_during_begin_does_not_transfer_ownership(self):
        self.git_repo()
        self.git("branch", "other-owner-branch")
        self.prepare_owned_recovery()
        state = tool.status(self.root)
        fresh = dict(workflow_id="concurrent-branch-review", change=change())
        fresh["change"]["parent_event_id"] = state["latest_change"]["event_id"]
        observed = git_checkpoint.capture
        switched = False
        def switch_before_capture(root, policy):
            nonlocal switched
            if not switched:
                self.git("switch", "--quiet", "other-owner-branch")
                switched = True
            return observed(root, policy)
        with patch.object(git_checkpoint, "capture", side_effect=switch_before_capture):
            with self.assertRaisesRegex(ValueError, "Git identity changed"):
                tool.begin_workflow(self.root, write(self.root / ".governance/concurrent-start.json", fresh))
        after = tool.status(self.root)
        self.assertIsNone(after["active_workflow"])
        self.assertEqual(after["completion_review_pending"], state["completion_review_pending"])
        self.assertFalse(after["git_checkpoint"].get("pending_paths"))

    @unittest.skipUnless(shutil.which("git"), "local Git required")
    def test_stale_ledger_does_not_strand_existing_native_partial_journal(self):
        self.git_repo()
        start = self.git_begin(True)
        source = self.root / "runtime.py"
        source.write_bytes(b"partial journal bytes\n")
        hook = self.root / ".git/hooks/pre-commit"
        hook.parent.mkdir(exist_ok=True)
        hook.write_bytes(b"#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        partial = report(start, "partial")
        partial["checkpoint_id"] = "native-stage"
        result = self.finish(partial)
        self.assertEqual(result["git_checkpoint"]["status"], "blocked", result)
        journal = copy.deepcopy(tool.status(self.root)["git_checkpoint"]["journal"])
        source.write_bytes(b"final reviewed bytes\n")
        complete = self.payload(start)
        with patch.object(tool, "_reconcile_completion", side_effect=OSError("synthetic crash")):
            with self.assertRaises(OSError):
                self.finish(complete)
        source.write_bytes(b"later unreviewed bytes\n")
        with self.assertRaisesRegex(ValueError, "recover its original stage first"):
            self.finish(complete)
        state = tool.status(self.root)
        self.assertIsNotNone(state["active_workflow"])
        self.assertIsNone(state["completion_review_pending"])
        self.assertEqual(state["git_checkpoint"]["journal"], journal)
        source.write_bytes(b"partial journal bytes\n")
        hook.unlink()
        self.assertEqual(self.finish(partial)["git_checkpoint"]["status"], "committed")
        source.write_bytes(b"final reviewed bytes\n")
        self.assertEqual(self.finish(complete)["git_checkpoint"]["status"], "committed")
        self.assertTrue(tool.status(self.root)["ok"])
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"3")


if __name__ == "__main__":
    unittest.main()
