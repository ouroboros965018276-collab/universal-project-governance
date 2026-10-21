"""Report-derived boundary regressions; local fixtures only, no provider calls."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from registration_fixture import change as fixture_change

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "governance-src"

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

STATE = module("ocr_state", SOURCE / "runtime-scripts/state_tool.py")
GUARDS = module("ocr_guards", SOURCE / "runtime-scripts/process_guard.py")
LIFETIME = module("ocr_lifetime", SOURCE / "runtime-scripts/session_lifetime.py")
FACTS = module("ocr_facts", SOURCE / "runtime-scripts/project_facts.py")
with patch.dict(sys.modules, state_tool=STATE, process_guard=GUARDS):
    PROJECT = module("ocr_project", SOURCE / "runtime-scripts/project_tool.py")
with patch.dict(sys.modules, project_tool=PROJECT):
    PLAN = module("ocr_plan", SOURCE / "runtime-scripts/plan_governance.py")
COMPILER = module("ocr_compiler", ROOT / "compiler/compile_governance.py")
INTEGRITY = module("ocr_integrity", SOURCE / "runtime-scripts/validate_integrity.py")

def schema(name):
    return json.loads((SOURCE / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8"))

class OcrRuntimeRegressions(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "eval-workspaces"
        parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="ocr-runtime-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        modules = patch.dict(sys.modules, state_tool=STATE, project_facts=FACTS,
                             process_guard=GUARDS, session_lifetime=LIFETIME)
        modules.start(); self.addCleanup(modules.stop)

    def test_null_still_obeys_enum(self):
        self.assertTrue(STATE.validate_node(None, {"type": ["string", "null"], "enum": ["a"]}))
        self.assertEqual(STATE.validate_node(None, {"type": ["string", "null"], "enum": ["a", None]}), [])

    def test_applicators_and_property_names_are_enforced(self):
        contract = {"type": "object", "propertyNames": {"pattern": "^[A-Z]+$"}, "allOf": [
            {"if": {"required": ["FLAG"]}, "then": {"required": ["VALUE"]}}]}
        self.assertTrue(STATE.validate_node({"FLAG": True}, contract))
        self.assertTrue(STATE.validate_node({"lower": 1}, contract))
        self.assertEqual(STATE.validate_node({"FLAG": True, "VALUE": 1}, contract), [])

    def test_passed_run_requires_both_non_null_counts(self):
        base = {"run_id": "unit", "scope": "focused", "result": "passed", "tested_revision": "current"}
        for counts in ({}, {"passed": None, "total": None}, {"total": 4}, {"passed": 3, "total": 4}):
            with self.subTest(counts=counts):
                self.assertTrue(STATE.validation_run_errors([dict(base, **counts)]))
        self.assertEqual(STATE.validation_run_errors([dict(base, passed=4, total=4)]), [])

    def test_audit_rejects_unknown_gate_fields_and_invalid_digest(self):
        contract = schema("audit")
        self.assertTrue(STATE.validate_node("abc", contract["properties"]["artifact_sha256"]))
        self.assertTrue(STATE.validate_node({"name": "gate", "result": "pass", "evidance": "typo"}, contract["properties"]["gates"]["items"]))

    def test_model_rejects_malformed_and_unknown_nested_configuration(self):
        model = json.loads((SOURCE / "model/governance-model.json").read_text(encoding="utf-8"))
        self.assertEqual(STATE.validate_node(model, schema("governance-model")), [])
        for path, value in ((["risk_model"], None), (["complexity_budget", "hot_path_max"], -1),
                            (["policies", 0, "triggers"], None), (["project_binding", "max_reports"], -1),
                            (["hot_path", 0, "statement"], ""), (["defualt_rules"], [])):
            candidate = copy.deepcopy(model); target = candidate
            for key in path[:-1]: target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path): self.assertTrue(STATE.validate_node(candidate, schema("governance-model")))

    def test_plan_conditional_contracts(self):
        contract = schema("governance-plan")
        # Validate producer output before mutating independent contract fields.
        index = COMPILER.compile_index(SOURCE, json.loads((SOURCE / "model/governance-model.json").read_text()))
        plan = PLAN.compile_plan(index, {"operation": "edit", "domains": ["code"]})
        self.assertEqual(STATE.validate_node(plan, contract), [])
        for updates in ({"risk_score": -1}, {"risk_score": 100},
                        {"change_mode": "structural", "scope_guard": "local-only"},
                        {"field_report_obligation": "required-before-completion", "field_report_file": None}):
            with self.subTest(updates=updates): self.assertTrue(STATE.validate_node(dict(plan, **updates), contract))

    def test_field_change_parity_and_sha256_git_revisions(self):
        contract = schema("field-report")["properties"]
        start = {key: value for key, value in contract["start_change"].items() if key != "description"}
        self.assertEqual(contract["change"], start)
        revision = contract["change"]["properties"]["base_revision"]
        self.assertEqual(STATE.validate_node("a" * 64, revision), [])
        self.assertTrue(STATE.validate_node("a" * 63, revision))

    def test_json_pointer_escapes_are_checked_by_schema(self):
        pointer = schema("handoff")["properties"]["validation_ref"]["properties"]["pointer"]
        for valid in ("", "/a~0b/~1c", "/"):
            self.assertEqual(STATE.validate_node(valid, pointer), [])
        self.assertTrue(STATE.validate_node("/a~2b", pointer))

    def test_handoff_status_binds_digest(self):
        contract = schema("handoff")["properties"]["recovery"]["properties"]["source_state"]["properties"]["files"]["items"]
        self.assertTrue(STATE.validate_node({"path": "a", "status": "observed", "sha256": None}, contract))
        self.assertTrue(STATE.validate_node({"path": "a", "status": "unavailable", "sha256": "a" * 64}, contract))

    def test_report_non_objects_raise_controlled_errors(self):
        for value in (None, [], "text", 5, [["a", "b"]]):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "must be an object"):
                PROJECT.validate_report(value)

    def test_binding_transient_shapes_and_v1_git_policy_are_checked(self):
        index = COMPILER.compile_index(SOURCE, json.loads((SOURCE / "model/governance-model.json").read_text()))
        with patch.object(PROJECT, "index", return_value=index):
            value = PROJECT.expected_binding()
            for key in ("active_workflow", "latest_change", "previous_change", "current_state"):
                self.assertIn(key + " must be an object", PROJECT.validate_binding(dict(value, **{key: "bad"})))
            for transient in ({"active_workflow": {"last_outcome": "bad"}},
                              {"active_workflow": {"last_outcome": {"sequence": "3"}}},
                              {"active_workflow": {"outcome_receipts": {"partial": "bad"}}},
                              {"latest_change": {"sequence": "3"}}):
                with self.subTest(transient=transient):
                    self.assertTrue(PROJECT.validate_binding(dict(value, **transient)))
            old = dict(value, schema_version=1, git_checkpoint="bad")
            gov = self.root / ".governance"; gov.mkdir()
            (gov / "upg.json").write_text(json.dumps(old), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "git_checkpoint must be an object"):
                PROJECT.ensure(self.root)
            self.assertEqual(json.loads((gov / "upg.json").read_text()), old)

    def test_legacy_lock_is_rechecked_after_native_guard_acquisition(self):
        gov = self.root / ".governance"; gov.mkdir()
        acquired = Mock()
        def acquire(*unused):
            (gov / ".upg-write-lock").mkdir(exist_ok=True)
            return acquired
        @PROJECT.serialized
        def mutate(project): raise AssertionError("must not enter while legacy lock exists")
        with patch.object(GUARDS, "acquire", side_effect=acquire), patch.object(PROJECT.time, "sleep"):
            with self.assertRaisesRegex(ValueError, "writer busy"): mutate(self.root)
        acquired.close.assert_called_once()

    def test_report_completion_uses_git_finish_path(self):
        binding = {"git_checkpoint": {"enabled": True}}
        with patch.object(PROJECT, "ensure", return_value={"field_test_reporting": True}), \
             patch.object(PROJECT, "_read_report", return_value={"status": "complete"}), \
             patch.object(PROJECT, "config", return_value={"binding_file": ".governance/upg.json"}), \
             patch.object(PROJECT, "load_json", return_value=binding), \
             patch.object(PROJECT, "finish_workflow", return_value={"git_checkpoint": "ran"}) as finish:
            self.assertEqual(PROJECT.record_report(self.root, "report.json"), {"git_checkpoint": "ran"})
        finish.assert_called_once_with(self.root, "report.json")

    def test_failed_git_baseline_is_not_persisted_as_workflow_start(self):
        index = COMPILER.compile_index(SOURCE, json.loads((SOURCE / "model/governance-model.json").read_text()))
        with patch.object(PROJECT, "index", return_value=index): binding = PROJECT.expected_binding()
        binding["git_checkpoint"].update(enabled=True, allowed_paths=["."])
        payload = {"workflow_id": "baseline-failure", "change": fixture_change()}
        helper = SimpleNamespace(bootstrap=Mock(return_value={"ok": True}), capture=Mock(return_value={"ok": False, "reason": "capture failed"}))
        with patch.object(PROJECT, "index", return_value=index), patch.object(PROJECT, "ensure"), \
             patch.object(PROJECT, "load_json", side_effect=[payload, schema("field-report"), binding]), \
             patch.object(PROJECT, "write_json_atomic") as write, patch.dict(sys.modules, git_checkpoint=helper):
            with self.assertRaisesRegex(ValueError, "cannot capture project Git baseline"):
                PROJECT.begin_workflow(self.root, "start.json")
        write.assert_not_called()

    def test_guard_wrapper_preserves_string_argv_and_windows_flags(self):
        guard = GUARDS.Guard(self.root / ".governance/.upg-test.guard", 123)
        with patch.object(GUARDS, "inheritance") as inherited, patch.object(GUARDS.subprocess, "Popen") as popen, \
             patch.object(LIFETIME, "active", return_value=False):
            inherited.return_value.__enter__.return_value = {}
            GUARDS._spawn_guarded("literal-program", [guard], {})
            self.assertEqual(popen.call_args.args[0][-1], "literal-program")
            if os.name == "nt":
                GUARDS._spawn_guarded(["program"], [guard], {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP})
                self.assertEqual(popen.call_args.kwargs["creationflags"], subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)

    @unittest.skipUnless(os.name == "nt", "Windows UNC path normalization")
    def test_guard_unc_handle_path_matches_ordinary_unc_path(self):
        def final_path(handle, buffer, size, flags):
            buffer.value = "\\\\?\\UNC\\server\\share\\guard"
            return len(buffer.value)
        with patch.object(GUARDS._KERNEL, "GetFinalPathNameByHandleW", side_effect=final_path):
            self.assertEqual(GUARDS._windows_path(123), os.path.normcase("\\\\server\\share\\guard"))

    @unittest.skipIf(os.name == "nt", "POSIX directory-descriptor nofollow semantics")
    def test_posix_guard_directory_swap_cannot_redirect_guard_creation(self):
        gov = self.root / ".governance"; gov.mkdir()
        outside = self.root / "other"; outside.mkdir()
        original = GUARDS._is_reparse
        def swap(path):
            if path.name == ".upg-test.guard":
                gov.rename(self.root / "original-governance")
                gov.symlink_to(outside, target_is_directory=True)
                return False
            return original(path)
        with patch.object(GUARDS, "_is_reparse", side_effect=swap), self.assertRaises(OSError):
            GUARDS.acquire(self.root, ".upg-test.guard")
        self.assertFalse((outside / ".upg-test.guard").exists())

    def test_guard_duplicate_handles_rejected_before_adoption(self):
        specs = [{"root": str(self.root), "name": ".upg-test.guard", "handle": 123}] * 2
        with patch.object(LIFETIME, "join_from_environment"), patch.object(GUARDS, "adopt") as adopt:
            with self.assertRaisesRegex(ValueError, "distinct"):
                GUARDS._hold_command(["--hold", json.dumps(specs), "--", "program"])
        adopt.assert_not_called()

    def test_guard_tracks_non_timeout_communication_failure(self):
        guard = GUARDS.Guard(self.root / ".governance/.upg-test.guard", 123)
        process = Mock(); process.communicate.side_effect = KeyboardInterrupt
        with GUARDS.holding(guard), patch.object(GUARDS, "_spawn_guarded", return_value=process), \
             patch.object(GUARDS.threading, "Thread"):
            with self.assertRaises(KeyboardInterrupt): GUARDS.run(["program"])
            self.assertIn(process, GUARDS._PENDING)
        GUARDS._PENDING.pop(process, None)

    @unittest.skipUnless(os.name == "nt", "native Windows handle ownership")
    def test_failed_pipe_adoption_closes_native_handle(self):
        with patch.object(LIFETIME._KERNEL, "GetFileType", return_value=3), \
             patch.object(LIFETIME.os, "set_handle_inheritable"), \
             patch.object(LIFETIME.msvcrt, "open_osfhandle", side_effect=OSError("convert")), \
             patch.object(LIFETIME._KERNEL, "CloseHandle") as close:
            with self.assertRaises(OSError): LIFETIME._adopt_pipe(123)
        close.assert_called_once_with(123)

    def test_failed_watcher_start_does_not_publish_current(self):
        spec = {"root": str(self.root), "token": "a" * 32, "read": 123, "group": None, "gate": None}
        if os.name != "nt": spec["group"] = os.getpgrp()
        with patch.object(LIFETIME, "_CURRENT", None), patch.dict(os.environ, {LIFETIME._ENV: json.dumps(spec)}), \
             patch.object(LIFETIME, "_adopt_pipe", return_value=123), \
             patch.object(LIFETIME.os, "close") as close, \
             patch.object(LIFETIME.threading.Thread, "start", side_effect=RuntimeError("start")):
            with self.assertRaises(RuntimeError): LIFETIME.join_from_environment()
            self.assertIsNone(LIFETIME.current())
        close.assert_called_once_with(123)

    def test_session_close_attempts_all_handles_and_clears_current(self):
        session = LIFETIME.Session(self.root); session.read_fd = 11; session.write_fd = 12
        with patch.object(LIFETIME, "_CURRENT", session), \
             patch.object(LIFETIME.os, "close", side_effect=[OSError("write close"), None]) as close:
            with self.assertRaisesRegex(OSError, "write close"): session.close()
            self.assertIsNone(LIFETIME.current())
            self.assertIsNone(session.read_fd); self.assertIsNone(session.write_fd)
        self.assertEqual(close.call_count, 2)

    def test_read_budget_reserves_one_handoff_attempt(self):
        for i in range(64): (self.root / (str(i) + ".txt")).write_text("x")
        (self.root / "handoff.json").write_text("{}")
        result = FACTS.recover(self.root, [str(i) + ".txt" for i in range(64)], handoff="handoff.json")
        self.assertEqual(sum(row["status"] == "observed" for row in result["recovery"]["source_state"]["files"]), 64)
        self.assertEqual(result["coverage"]["read_attempts"], 65)

    def test_secret_names_are_excluded(self):
        for name in (".git-credentials", "id_ed25519", "private.pem", ".gnupg/key", ".pgpass", "pip.conf", ".yarnrc.yml", ".htpasswd"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "credential"):
                FACTS.safe_path(self.root, name)

    def test_raced_file_is_downgraded_before_reference_inheritance(self):
        (self.root / "main.py").write_text("pass\n")
        def raced(root, scope, binary, *, reader):
            reader.raced_paths.add("main.py")
            return {"available": False, "root": None, "revision": None, "branch": None, "changed_paths": [], "coverage": "explicit-scope-only"}, []
        with patch.object(FACTS, "git_state", side_effect=raced): result = FACTS.recover(self.root, ["main.py"])
        row = result["recovery"]["source_state"]["files"][0]
        self.assertEqual(row["status"], "unavailable"); self.assertIsNone(row["sha256"])
        self.assertEqual(result["recovery"]["static_observations"], [])
        self.assertIn("cannot be inherited", " ".join(result["recovery"]["gaps"]))

    def test_bounded_git_query_rejects_oversized_stream(self):
        with self.assertRaisesRegex(ValueError, "bounded output"):
            FACTS._bounded_git_query([sys.executable, "-c", "import sys;sys.stdout.write('x'*100000)"],
                                     output_limit=1024, timeout=5, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_duplicate_policies_and_profile_ids_rejected(self):
        model = json.loads((SOURCE / "model/governance-model.json").read_text())
        broken = copy.deepcopy(model); broken["policies"].append(copy.deepcopy(broken["policies"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate policy"):
            COMPILER.compile_index(SOURCE, broken)
        index = COMPILER.compile_index(SOURCE, model)
        index["policies"].append(copy.deepcopy(index["policies"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate policy"):
            PLAN.compile_plan(index, {"operation": "edit", "domains": ["code"]})
        profiles = self.root / "profiles"; profiles.mkdir()
        for name in ("a", "b"): (profiles / (name + ".json")).write_text('{"id":"same"}')
        with self.assertRaisesRegex(ValueError, "duplicate profile"):
            COMPILER.compile_index(self.root, model)

    def test_failed_compile_preserves_existing_runtime(self):
        repo = self.root / "repo"; repo.mkdir()
        shutil.copytree(SOURCE, repo / "governance-src")
        shutil.copyfile(ROOT / "LICENSE", repo / "LICENSE")
        output = repo / "runtime"; output.mkdir(); (output / "sentinel").write_text("previous runtime")
        (repo / "governance-src/schemas/handoff.schema.json").unlink()
        with self.assertRaises(OSError): COMPILER.compile_runtime(repo, output)
        self.assertEqual((output / "sentinel").read_text(), "previous runtime")
        self.assertEqual(sorted(p.name for p in repo.iterdir()), ["LICENSE", "governance-src", "runtime"])

    def test_planner_context_flags_cannot_be_silently_ignored(self):
        context = self.root / "context.json"; context.write_text('{"operation":"edit","domains":["code"]}')
        args = argparse.Namespace(context=str(context), operation="edit", domain=[], signal=[], profile=[], risk=[], unfinished=False, audit=False)
        with self.assertRaisesRegex(ValueError, "cannot be combined"): PLAN.normalize_context(args)

    def test_integrity_read_error_is_controlled(self):
        manifest = self.root / "integrity"; manifest.mkdir()
        (manifest / "manifest.json").write_text('{"files":{}}')
        with patch.object(sys, "argv", ["integrity", str(self.root)]), \
             patch.object(INTEGRITY, "eligible", side_effect=PermissionError("denied")):
            self.assertEqual(INTEGRITY.main(), 2)

if __name__ == "__main__": unittest.main()
