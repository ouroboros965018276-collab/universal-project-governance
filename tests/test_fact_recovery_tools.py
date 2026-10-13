"""Public regression tasks for bounded current-fact recovery, never holdout data."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from evolution.tool_broker import RepoBroker, canonical, git_command, sha, validate_task
from evolution.tool_codex import _quality

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/fact_recovery_tasks.json"


class FactRecoveryToolsTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "eval-workspaces"
        temporary_root.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="fact-recovery-unit-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tasks = json.loads(FIXTURE.read_text(encoding="utf-8"))["tasks"]
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
        return RepoBroker(workspace, task, self.git)

    def patch(self, broker, files):
        operations = [{"path": name, "old_sha256": sha(broker.path(name).read_bytes()), "new_text": text}
                      for name, text in files.items()]
        self.assertTrue(broker.call("repo_patch", {"operations": operations})["ok"])

    def manifest(self, broker):
        check = next(item for item in broker.task["checks"] if item["kind"] == "file_hash_manifest")
        return {"source_sha256": {name: sha(broker.path(name).read_bytes()) for name in check["expected"]["sources"]},
                "claims": copy.deepcopy(check["expected"]["claims"])}

    def correct(self, broker, *, read_before=True):
        if read_before:
            self.assertTrue(broker.call("repo_read", {"paths": broker.task["required_read_paths"]})["ok"])
        files = {}
        for check in broker.task["checks"]:
            if check["kind"] == "file_hash_manifest":
                continue
            value = check["expected"]
            files[check["path"]] = value if isinstance(value, str) else canonical(value).decode("utf-8") + "\n"
        self.patch(broker, files)
        # Actual whole-file reads expose new hashes without arbitrary code execution.
        self.assertTrue(broker.call("repo_read", {"paths": broker.task["required_read_paths"]})["ok"])
        self.patch(broker, {"STATE.json": canonical(self.manifest(broker)).decode("utf-8") + "\n"})
        self.assertTrue(broker.call("repo_validate", {})["ok"])
        self.assertTrue(broker.call("repo_status", {})["ok"])

    def quality(self, broker):
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "upg_repo",
                   "tool": row["tool"], "arguments": row["arguments"], "status": "completed"}}
                  for row in broker.events]
        final = canonical({"summary": "Updated the registered current artifacts; application tests were not run.",
                           "validation": "passed", "helper_gap": "project_tool unavailable in bounded broker"}).decode()
        return _quality(broker, broker.events, events, final, 32)

    def test_four_public_instances_two_families_have_positive_current_fact_contracts(self):
        self.assertEqual(len(self.tasks), 4)
        self.assertEqual({task["family"] for task in self.tasks}, {"recovery", "current-truth"})
        for task in self.tasks:
            self.assertIs(validate_task(task), task)
            self.assertIn("STATE.json", task["initial_files"])
            self.assertIn("STATE.json", task["writable_files"])
            self.assertFalse(any("handoff" in path.lower() for path in task["initial_files"]))
            self.assertIn("tests/contract.json", task["required_read_paths"])
            self.assertNotIn("evidence/previous.json", task["writable_files"])
            prior = json.loads(task["initial_files"]["evidence/previous.json"])
            for name, old_sha in prior["source_sha256"].items():
                self.assertNotEqual(old_sha, sha(task["initial_files"][name].encode()))

    def test_actual_reads_edits_current_hashes_and_static_checks_pass_all_instances(self):
        for task in self.tasks:
            with self.subTest(task=task["id"]):
                broker = self.broker(task)
                self.assertFalse(broker.validate()["ok"])
                self.correct(broker)
                self.assertTrue(self.quality(broker)["hard_pass"])
                self.assertEqual(broker.read_evidence_failures(broker.events), [])
                for name, original in task["initial_files"].items():
                    if name not in task["writable_files"]:
                        self.assertEqual(broker.path(name).read_bytes(), original.encode())

    def test_complete_looking_old_pass_and_report_only_do_not_validate_current_behavior(self):
        for task in self.tasks:
            broker = self.broker(task)
            self.assertEqual(json.loads(task["initial_files"]["evidence/previous.json"])["status"], "PASS")
            self.patch(broker, {"STATE.json": canonical(self.manifest(broker)).decode()})
            self.assertFalse(broker.validate()["ok"])

    def test_correct_code_with_old_source_or_test_hash_still_fails(self):
        for task in self.tasks:
            for changed_path in (task["required_read_paths"][0], "tests/contract.json"):
                with self.subTest(task=task["id"], stale=changed_path):
                    broker = self.broker(task)
                    self.correct(broker)
                    manifest = self.manifest(broker)
                    manifest["source_sha256"][changed_path] = json.loads(task["initial_files"]["evidence/previous.json"])["source_sha256"][changed_path]
                    self.patch(broker, {"STATE.json": canonical(manifest).decode()})
                    self.assertFalse(broker.validate()["ok"])

    def test_self_reported_current_hashes_cannot_hide_empty_or_stub_implementation(self):
        task = next(task for task in self.tasks if task["family"] == "recovery")
        for source in ("", "def canonicalize(value):\n    return 999\n", "def normalize(value):\n    pass\n"):
            with self.subTest(source=source):
                broker = self.broker(task)
                self.correct(broker)
                broker.path("entry.py").write_bytes(source.encode())
                broker.path("STATE.json").write_bytes(canonical(self.manifest(broker)))
                self.assertFalse(broker.validate()["ok"])

    def test_dynamic_consumer_or_protected_contract_deletion_fails(self):
        task = next(task for task in self.tasks if task["family"] == "recovery")
        for name in ("plugins.json", "tests/contract.json", "entry.py"):
            broker = self.broker(task)
            self.correct(broker)
            broker.path(name).unlink()
            self.assertFalse(broker.validate()["ok"])
        broker = self.broker(task)
        self.correct(broker)
        broker.path("plugins.json").write_bytes(b'{"pipeline":{"handler":"entry:canonicalize"}}')
        broker.path("STATE.json").write_bytes(canonical(self.manifest(broker)))
        self.assertFalse(broker.validate()["ok"])

    def test_stale_claims_or_new_hashes_without_necessary_artifacts_fail(self):
        task = self.tasks[0]
        broker = self.broker(task)
        self.correct(broker)
        value = self.manifest(broker)
        value["claims"]["prior_validation"] = "validated"
        broker.path("STATE.json").write_bytes(canonical(value))
        self.assertFalse(broker.validate()["ok"])
        broker.path("STATE.json").write_bytes(canonical({"source_sha256": self.manifest(broker)["source_sha256"]}))
        self.assertFalse(broker.validate()["ok"])

    def test_only_later_reads_or_status_metadata_do_not_satisfy_before_edit_evidence(self):
        broker = self.broker(self.tasks[0])
        self.assertTrue(broker.call("repo_status", {})["ok"])
        self.correct(broker, read_before=False)
        self.assertTrue(broker.validate()["ok"])
        quality = self.quality(broker)
        self.assertFalse(quality["hard_pass"])
        self.assertTrue(any(reason.startswith("required-recovery-reads-before-edit-missing:") for reason in quality["failures"]))

    def test_partial_wrong_hash_and_failed_reads_cannot_forge_full_clue_coverage(self):
        broker = self.broker(self.tasks[0])
        name = broker.task["required_read_paths"][0]
        original = broker.task["initial_files"][name]
        for result in ({"ok": False}, {"ok": True, "files": {name: {"text": original, "sha256": "0" * 64}}},
                       {"ok": True, "files": {name: {"text": original[:1], "sha256": sha(original[:1].encode())}}}):
            events = [{"tool": "repo_read", "arguments": {"paths": broker.task["required_read_paths"]}, "result": result}]
            self.assertTrue(broker.read_evidence_failures(events))
        self.assertTrue(broker.call("repo_read", {"paths": [name]})["ok"])
        self.assertTrue(broker.read_evidence_failures(broker.events))
        for other in broker.task["required_read_paths"][1:]:
            self.assertTrue(broker.call("repo_read", {"paths": [other]})["ok"])
        self.assertEqual(broker.read_evidence_failures(broker.events), [])

    def test_rejected_patch_does_not_prevent_later_safe_fact_reads(self):
        broker = self.broker(self.tasks[0])
        self.assertFalse(broker.call("repo_patch", {"operations": [{"path": "README.md", "old_sha256": "wrong", "new_text": "wrong"}]})["ok"])
        self.correct(broker)
        self.assertEqual(broker.read_evidence_failures(broker.events), [])
        self.assertTrue(self.quality(broker)["hard_pass"])

    def test_manifest_rejects_duplicate_nonfinite_and_wrong_typed_hashes(self):
        task = self.tasks[0]
        for text in ('{"source_sha256":{},"source_sha256":{},"claims":{}}', '{"source_sha256":NaN,"claims":{}}'):
            broker = self.broker(task)
            self.correct(broker)
            broker.path("STATE.json").write_bytes(text.encode())
            self.assertFalse(broker.validate()["ok"])
        broker = self.broker(task)
        self.correct(broker)
        value = self.manifest(broker)
        value["source_sha256"]["settings.json"] = True
        broker.path("STATE.json").write_bytes(canonical(value))
        self.assertFalse(broker.validate()["ok"])

    def test_bad_manifest_sources_and_read_contracts_reject_before_dispatch(self):
        for sources in ([], ["STATE.json"], ["../outside"], ["settings.json"] * 2, [None]):
            task = copy.deepcopy(self.tasks[0])
            task["checks"][-1]["expected"]["sources"] = sources
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                validate_task(task)
        for reads in ([], ["STATE.json"] * 2, ["../outside"], [None], "settings.json"):
            task = dict(self.tasks[0], required_read_paths=reads)
            with self.subTest(reads=reads), self.assertRaises(ValueError):
                validate_task(task)

    def test_submitted_python_is_parsed_never_executed(self):
        task = next(task for task in self.tasks if task["family"] == "recovery")
        broker = self.broker(task)
        marker = self.root / "must-not-exist"
        broker.path("entry.py").write_text("import pathlib\npathlib.Path(" + repr(str(marker)) + ").write_text('executed')\nwhile True: pass\n", encoding="utf-8")
        self.assertFalse(broker.validate()["ok"])
        self.assertFalse(marker.exists())

    def test_old_tasks_without_new_contract_keep_their_existing_read_rule(self):
        task = copy.deepcopy(self.tasks[0])
        del task["required_read_paths"]
        broker = self.broker(task)
        self.assertEqual(broker.read_evidence_failures([]), [])


if __name__ == "__main__":
    unittest.main()
