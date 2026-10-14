"""七类公开开发任务的确定性正反评分回归；无模型调用或应用源码执行。"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from evolution.tool_broker import RepoBroker, canonical, git_command, sha, validate_task
from evolution.tool_codex import _quality

FIXTURE = ROOT / "tests/fixtures/context_discipline_cases.json"


class ContextDisciplineAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "eval-workspaces"
        temporary_root.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="rc20-context-acceptance-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.tasks = {task["id"]: task for task in fixture["tasks"]}
        self.cases = {case["task_id"]: case["negative_cases"] for case in fixture["acceptance_cases"]}
        self.git = Path(shutil.which("git"))
        self.serial = 0

    def broker(self, task):
        self.serial += 1
        workspace = self.root / ("workspace-" + str(self.serial))
        workspace.mkdir()
        for name, text in task["initial_files"].items():
            path = workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        result = git_command(self.git, workspace, "init", "--template=", "--quiet")
        self.assertEqual(result.returncode, 0, result.stderr)
        return RepoBroker(workspace, copy.deepcopy(task), self.git)

    def patch(self, broker, files):
        operations = [{"path": name, "old_sha256": sha(broker.path(name).read_bytes()), "new_text": text}
                      for name, text in files.items()]
        self.assertTrue(broker.call("repo_patch", {"operations": operations})["ok"])

    def complete(self, broker, *, read_before=True):
        task = broker.task
        if read_before:
            self.assertTrue(broker.call("repo_read", {"paths": task["required_read_paths"]})["ok"])
        files = {check["path"]: check["expected"] if isinstance(check["expected"], str)
                 else canonical(check["expected"]).decode("utf-8") + "\n"
                 for check in task["checks"] if check["kind"] != "file_hash_manifest"}
        self.patch(broker, files)
        self.assertTrue(broker.call("repo_read", {"paths": task["required_read_paths"]})["ok"])
        for check in task["checks"]:
            if check["kind"] == "file_hash_manifest":
                value = {"source_sha256": {name: sha(broker.path(name).read_bytes()) for name in check["expected"]["sources"]},
                         "claims": copy.deepcopy(check["expected"]["claims"])}
                self.patch(broker, {check["path"]: canonical(value).decode("utf-8") + "\n"})
        self.assertTrue(broker.call("repo_validate", {})["ok"])
        self.assertTrue(broker.call("repo_status", {})["ok"])

    def quality(self, broker):
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "upg_repo",
                   "tool": row["tool"], "arguments": row["arguments"], "status": "completed"}}
                  for row in broker.events]
        final = canonical({"summary": "已完成注册的静态契约；应用测试未运行。", "validation": "passed",
                           "helper_gap": "project_tool unavailable in bounded broker"}).decode("utf-8")
        return _quality(broker, broker.events, events, final, 32)

    def test_seven_public_families_are_valid_development_only(self):
        self.assertEqual(len(self.tasks), 7)
        self.assertEqual(len({task["family"] for task in self.tasks.values()}), 7)
        self.assertEqual(set(self.tasks), set(self.cases))
        self.assertTrue(all("-development-" in identifier for identifier in self.tasks))
        for task in self.tasks.values():
            self.assertIs(validate_task(task), task)
            self.assertEqual(len(self.cases[task["id"]]), 2)
            self.assertIn("tests/contract.json", task["required_read_paths"])
            self.assertNotIn("tests/contract.json", task["writable_files"])

    def test_all_complete_positive_artifacts_and_real_tool_evidence_pass(self):
        for task in self.tasks.values():
            with self.subTest(family=task["family"]):
                broker = self.broker(task)
                self.assertFalse(broker.validate()["ok"])
                self.complete(broker)
                self.assertTrue(self.quality(broker)["hard_pass"])
                for name, original in task["initial_files"].items():
                    if name not in task["writable_files"]:
                        self.assertEqual(broker.path(name).read_bytes(), original.encode("utf-8"))

    def rejected_family(self, family):
        task = next(task for task in self.tasks.values() if task["family"] == family)
        for case in self.cases[task["id"]]:
            with self.subTest(negative=case["name"]):
                broker = self.broker(task)
                self.complete(broker)
                self.patch(broker, case["edits"])
                self.assertFalse(broker.validate()["ok"])

    def test_process_narration_and_missing_document_structure_fail(self):
        self.rejected_family("chinese-documentation")

    def test_wrong_feature_boundary_and_short_stub_fail(self):
        self.rejected_family("single-feature-navigation")

    def test_missing_dynamic_consumer_and_deleted_compatibility_fail(self):
        self.rejected_family("public-api-consumers")

    def test_stale_map_and_unchanged_actual_source_fail(self):
        self.rejected_family("stale-map-source-conflict")

    def test_simplification_without_type_or_error_safety_fails(self):
        self.rejected_family("simplification-preserves-safety")

    def test_lost_numbers_reference_negation_or_unknown_fails(self):
        self.rejected_family("evidence-fidelity")

    def test_handoff_only_fix_or_rewritten_start_and_validation_fails(self):
        self.rejected_family("interrupted-handoff-recovery")

    def test_correct_artifacts_without_before_edit_reads_do_not_pass(self):
        for task in self.tasks.values():
            with self.subTest(family=task["family"]):
                broker = self.broker(task)
                self.complete(broker, read_before=False)
                self.assertTrue(broker.validate()["ok"])
                quality = self.quality(broker)
                self.assertFalse(quality["hard_pass"])
                self.assertTrue(any(reason.startswith("required-recovery-reads-before-edit-missing:") for reason in quality["failures"]))

    def test_current_hashes_are_required_after_interrupted_consumer_repair(self):
        task = next(task for task in self.tasks.values() if task["family"] == "interrupted-handoff-recovery")
        broker = self.broker(task)
        self.complete(broker)
        handoff = json.loads(broker.path("HANDOFF.json").read_text(encoding="utf-8"))
        handoff["source_sha256"]["client.py"] = sha(task["initial_files"]["client.py"].encode("utf-8"))
        self.patch(broker, {"HANDOFF.json": canonical(handoff).decode("utf-8")})
        self.assertFalse(broker.validate()["ok"])

    def test_unrelated_read_remains_observed_cost_not_a_quality_shortcut(self):
        task = next(task for task in self.tasks.values() if task["family"] == "single-feature-navigation")
        broker = self.broker(task)
        result = broker.call("repo_read", {"paths": ["docs/background.md"]})
        self.assertTrue(result["ok"])
        observed = result["files"]["docs/background.md"]
        self.assertEqual(len(observed["text"].encode("utf-8")), len(task["initial_files"]["docs/background.md"].encode("utf-8")))
        self.assertFalse(broker.validate()["ok"])
        self.complete(broker)
        self.assertTrue(self.quality(broker)["hard_pass"])
        self.assertIn("docs/background.md", broker.events[0]["result"]["files"])

    def test_protected_contract_cannot_be_removed_to_get_a_pass(self):
        task = next(iter(self.tasks.values()))
        broker = self.broker(task)
        self.complete(broker)
        broker.path("tests/contract.json").unlink()
        self.assertFalse(broker.validate()["ok"])

    def test_submitted_application_source_is_only_parsed(self):
        task = next(task for task in self.tasks.values() if task["family"] == "single-feature-navigation")
        broker = self.broker(task)
        marker = self.root / "must-not-execute"
        source = "import pathlib\npathlib.Path(" + repr(str(marker)) + ").write_text('executed')\nwhile True: pass\n"
        self.patch(broker, {"src/window.py": source})
        self.assertFalse(broker.validate()["ok"])
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
