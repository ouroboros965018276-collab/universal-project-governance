"""Canonical validation continuity regressions, using source rather than a compiled copy."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "governance-src/runtime-scripts/state_tool.py"
SPEC = importlib.util.spec_from_file_location("validation_state_tool", TOOL)
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


def run(run_id="focused", **changes):
    value = {"run_id": run_id, "scope": "focused contract tests", "result": "failed", "tested_revision": "tested-a", "passed": 144, "total": 145}
    value.update(changes)
    return value


def execution(runs=None):
    value = {"updated_at": "2026-10-11T06:00:00Z", "level": "engineering", "task": "validation continuity", "status": "complete", "actions": [], "cleanup": [], "validation": [], "findings": [], "governance_feedback": [], "retain_for_audit": False, "durable_summary_recorded": True}
    if runs is not None:
        value["validation_runs"] = runs
    return value


def handoff(ref=None):
    value = {"updated_at": "2026-10-11T06:00:00Z", "goal": "continue validation", "status": "in_progress", "completed": [], "in_progress": ["retest assertion change"], "decisions": [], "invariants": [], "risks": [], "next_actions": ["run affected tests"], "validation": [], "canonical_sources": []}
    if ref is not None:
        value["validation_ref"] = ref
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def ref(path, root, run_id="focused", **extra):
    value = {"path": path.relative_to(root).as_posix(), "run_id": run_id, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    value.update(extra)
    return value


def compact_records(root):
    """Actual compact candidates; no historical or product acceptance claim."""
    return {
        "execution": write(root / ".governance/execution/latest.json", execution([run(result="passed", passed=145)])),
        "handoff": write(root / ".governance/handoff.json", dict(handoff(), status="ready", in_progress=[], next_actions=[])),
        "feedback": write(root / ".governance/feedback/open.json", {
            "updated_at": "2026-10-11T06:00:00Z", "items": [{
                "id": "resolved", "status": "resolved", "observation": "resolved fixture",
                "evidence": ["synthetic test assertion"], "consequence": "none", "scope": "project"}]}),
    }


def active_task_binding(root, proof, location="result"):
    """Derive the active task state through the real evidence/contract verifier."""
    from task_lifecycle import evaluate
    contract = {"revision": "p1", "scope": ["synthetic compaction fixture"],
                "acceptance": ["current proof"], "constraints": [], "unknowns": [],
                "units": [{"id": "observed", "outcome": "current fixture identity observed",
                           "verification": "check actual file or canonical run", "depends_on": []}]}
    result = {"id": "observed", "status": "pending", "evidence": []}
    progress = {"revision": "p1", "results": [result], "next_action": "continue the synthetic task"}
    if location == "result":
        result.update(proof, status="passed")
    else:
        progress["acceptance"] = [dict(proof, criterion="current proof")]
    outcome = {"status": "partial", "change": {"validation_revision": "tested-a"}, "task_progress": progress}
    active = {"task_contract": contract}
    active["task_state"] = evaluate(root, outcome, active)
    active["last_outcome"] = outcome
    return {"active_workflow": active}


def task_proof(kind, path, root):
    proof = {"evidence": ["Synthetic current file/run observation; no product acceptance claim"]}
    reference = {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if kind == "sources":
        proof[kind] = [dict(reference, executable=path.stat().st_mode & 0o111)]
    elif kind == "current_state":
        proof[kind] = reference
    else:
        proof[kind] = dict(reference, run_id="focused")
    return proof


class ValidationContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime_path = patch.object(sys, "path", [str(TOOL.parent)] + sys.path)
        runtime_path.start()
        cls.addClassCleanup(runtime_path.stop)
        helper_spec = importlib.util.spec_from_file_location("project_facts", TOOL.with_name("project_facts.py"))
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        modules = patch.dict(sys.modules, project_facts=helper)
        modules.start()
        cls.addClassCleanup(modules.stop)

    def test_scopes_keep_their_own_denominators_and_revisions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(Path(directory) / "execution.json", execution([
                run(), run("full", scope="full regression", passed=552, total=623, tested_revision="older-b"),
            ]))
            self.assertEqual(state.validate_file(path, "execution"), [])
            rendered = state.render(path, "execution")
            for text in ["144/145", "552/623", "tested-a", "older-b", "scopes are not added together"]:
                self.assertIn(text, rendered)
            self.assertNotIn("696/768", rendered)
            self.assertNotIn("only one", rendered)

    def test_handoff_uses_existing_external_record_without_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"project_status": "active", "stages": {"contract/test": run()}})
            pointer = "/stages/contract~1test"
            path = write(root / ".governance/handoff.json", handoff(ref(source, root, pointer=pointer)))
            before = source.read_bytes()
            self.assertEqual(state.validate_file(path, "handoff", root), [])
            rendered = state.render(path, "handoff", root)
            self.assertIn("execution_status.json", rendered)
            self.assertIn("144/145", rendered)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse((root / ".governance/execution/latest.json").exists())

    def test_changed_source_is_stale_even_when_run_identity_stays_same(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"validation_runs": [run()]})
            path = write(root / "handoff.json", handoff(ref(source, root)))
            write(source, {"validation_runs": [run(passed=145, result="passed")]})
            errors = state.validate_file(path, "handoff", root)
            self.assertTrue(any("SHA-256 changed" in error for error in errors), errors)
            with self.assertRaisesRegex(ValueError, "stale validation_ref"):
                state.render(path, "handoff", root)

    def test_changed_run_id_is_stale_even_with_current_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"validation_runs": [run("different")]})
            path = write(root / "handoff.json", handoff(ref(source, root)))
            errors = state.validate_file(path, "handoff", root)
            self.assertTrue(any("run_id unavailable" in error for error in errors), errors)

    def test_later_changes_or_new_revision_require_retest_in_rendered_view(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write(Path(directory) / "execution.json", execution([run(result="passed", passed=145, later_changes=["assertion changed after this run"])]))
            rendered = state.render(path, "execution")
            self.assertIn("Historical result:** passed", rendered)
            self.assertIn("Retest:** pending", rendered)
            self.assertIn("assertion changed after this run", rendered)
            write(path, execution([run(result="passed", passed=145)]))
            rendered = state.render(path, "execution", current_revision="changed-b")
            self.assertIn("Tested revision:** tested-a", rendered)
            self.assertIn("Current revision supplied: changed-b", rendered)
            self.assertIn("Retest:** pending", rendered)

    def test_missing_file_and_missing_project_context_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"validation_runs": [run()]})
            path = write(root / "handoff.json", handoff(ref(source, root)))
            self.assertIn("requires --project-root", "; ".join(state.validate_file(path, "handoff")))
            source.unlink()
            self.assertIn("file unavailable", "; ".join(state.validate_file(path, "handoff", root)))

    def test_unsafe_paths_and_malformed_references_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"validation_runs": [run()]})
            reference = ref(source, root)
            for unsafe in ["../execution_status.json", "/execution_status.json", "C:/execution_status.json", "C:execution_status.json", "nested/../execution_status.json", "nested\\execution_status.json", "./execution_status.json", "docs/file.json:stream", "docs//file.json"]:
                with self.subTest(path=unsafe):
                    value = dict(reference, path=unsafe)
                    path = write(root / "handoff.json", handoff(value))
                    self.assertTrue(state.validate_file(path, "handoff", root))
            for change in [{"sha256": "unknown"}, {"run_id": ""}, {"pointer": "not-a-pointer"}, {"unexpected": True}]:
                with self.subTest(change=change):
                    path = write(root / "handoff.json", handoff(dict(reference, **change)))
                    self.assertTrue(state.validate_file(path, "handoff", root))

    def test_pointer_missing_malformed_or_unsupported_record_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"tests": {"focused": {"passed": 144, "total": 145}}})
            for pointer, message in [("/absent", "pointer unavailable"), ("/tests/~2bad", "pointer pattern mismatch"), ("/tests/focused", "unsupported canonical validation record")]:
                with self.subTest(pointer=pointer):
                    path = write(root / "handoff.json", handoff(ref(source, root, pointer=pointer)))
                    self.assertIn(message, "; ".join(state.validate_file(path, "handoff", root)))

    def test_duplicate_runs_and_invalid_counts_do_not_validate(self):
        for runs in [[run(), run()], [run(passed=146)], [run(total=None)], [run(result="passed")], [run(passed=True)], [run(total=-1)], [run()] * 33]:
            with self.subTest(runs=runs):
                self.assertTrue(state.validation_run_errors(runs))
        self.assertEqual(state.validation_run_errors([run(passed=None, total=None, result="unknown")]), [])

    def test_reference_read_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "execution_status.json"
            source.write_bytes(b" " * (4 * 1024 * 1024 + 1))
            path = write(root / "handoff.json", handoff(ref(source, root)))
            self.assertIn("4 MiB read limit", "; ".join(state.validate_file(path, "handoff", root)))

    def test_legacy_string_validation_is_still_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind, value in [("execution", execution()), ("handoff", handoff())]:
                value["validation"] = ["legacy recorded result; scope unknown"]
                path = write(root / (kind + ".json"), value)
                self.assertEqual(state.validate_file(path, kind), [])
                self.assertIn("legacy recorded result", state.render(path, kind))
                self.assertNotIn("Canonical validation runs", state.render(path, kind))

    def test_compaction_preserves_known_referenced_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / ".governance/execution/latest.json", execution([run()]))
            write(root / ".governance/handoff.json", handoff(ref(source, root)))
            self.assertEqual(state.compact(root, True, False), [])
            self.assertTrue(source.exists())
            write(source, execution([run(pending_retest=True)]))
            with self.assertRaisesRegex(ValueError, "stale validation_ref"):
                state.compact(root, True, False)
            self.assertTrue(source.exists())

    def test_compaction_preserves_each_binding_current_state_candidate(self):
        for candidate in ("execution/latest.json", "handoff.json", "feedback/open.json"):
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if candidate == "execution/latest.json":
                    value = execution()
                elif candidate == "handoff.json":
                    value = dict(handoff(), status="ready", in_progress=[], next_actions=[])
                else:
                    value = {"updated_at": "2026-10-11T06:00:00Z", "items": [{
                        "id": "resolved", "status": "resolved", "observation": "resolved fixture",
                        "evidence": ["synthetic test assertion"], "consequence": "none", "scope": "project"}]}
                source = write(root / ".governance" / candidate, value)
                current = {"path": source.relative_to(root).as_posix(),
                           "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                write(root / ".governance/upg.json", {"current_state": current})
                before = source.read_bytes()
                self.assertEqual(state.resolve_current_state(root, current), source.resolve())
                self.assertEqual(state.compact(root, False, True), [])
                self.assertEqual(state.compact(root, True, True), [])
                self.assertEqual(source.read_bytes(), before)

    def test_compaction_rejects_stale_current_state_before_any_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "current.json", {"stage": "first"})
            current = {"path": "current.json", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
            write(root / ".governance/upg.json", {"current_state": current})
            removable = write(root / ".governance/execution/latest.json", execution())
            write(source, {"stage": "later"})
            before = removable.read_bytes()
            with self.assertRaisesRegex(ValueError, "current_state changed"):
                state.compact(root, True, True)
            self.assertEqual(removable.read_bytes(), before)

    def test_compaction_protects_current_active_results_and_acceptance_only(self):
        for location in ("result", "acceptance"):
            for kind in ("sources", "current_state", "validation_ref"):
                candidates = ("execution",) if kind == "validation_ref" else ("execution", "handoff", "feedback")
                for candidate in candidates:
                    with self.subTest(location=location, kind=kind, candidate=candidate), tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        records = compact_records(root)
                        source = records[candidate]
                        binding = active_task_binding(root, task_proof(kind, source, root), location)
                        write(root / ".governance/upg.json", binding)
                        before = source.read_bytes()
                        planned = state.compact(root, False, True)
                        self.assertEqual(len(planned), 2)
                        self.assertEqual(state.compact(root, True, True), planned)
                        self.assertEqual(source.read_bytes(), before)
                        self.assertTrue(all(not path.exists() for name, path in records.items() if name != candidate))

    def test_compaction_rejects_stale_or_unsafe_active_proofs_before_any_cleanup(self):
        for location in ("result", "acceptance"):
            for kind in ("sources", "current_state", "validation_ref"):
                for invalid in ("stale", "unsafe"):
                    with self.subTest(location=location, kind=kind, invalid=invalid), tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        records = compact_records(root)
                        source = records["execution"]
                        binding = active_task_binding(root, task_proof(kind, source, root), location)
                        if invalid == "stale":
                            write(source, dict(execution([run(result="passed", passed=145)]), task="changed after proof"))
                        else:
                            progress = binding["active_workflow"]["last_outcome"]["task_progress"]
                            proof = progress["results"][0] if location == "result" else progress["acceptance"][0]
                            reference = proof[kind][0] if kind == "sources" else proof[kind]
                            reference["path"] = "../outside.json"
                        write(root / ".governance/upg.json", binding)
                        before = {name: path.read_bytes() for name, path in records.items()}
                        with self.assertRaises((OSError, ValueError)):
                            state.compact(root, True, True)
                        self.assertEqual({name: path.read_bytes() for name, path in records.items()}, before)

    def test_compaction_cli_preserves_active_task_proof_without_import_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = compact_records(root)
            source = records["execution"]
            write(root / ".governance/upg.json", active_task_binding(root, task_proof("validation_ref", source, root)))
            before = source.read_bytes()
            result = subprocess.run([sys.executable, "-B", str(TOOL), "compact", str(root), "--apply", "--close-handoff"],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(records["handoff"].exists())
            self.assertFalse(records["feedback"].exists())

    def test_compaction_rejects_current_nonpassed_validation_but_ignores_old_task_proofs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = compact_records(root)
            source = records["execution"]
            binding = active_task_binding(root, task_proof("validation_ref", source, root))
            write(source, execution([run(result="passed", passed=145, pending_retest=True)]))
            result = binding["active_workflow"]["last_outcome"]["task_progress"]["results"][0]
            result["validation_ref"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            write(root / ".governance/upg.json", binding)
            before = {name: path.read_bytes() for name, path in records.items()}
            with self.assertRaisesRegex(ValueError, "currently passed"):
                state.compact(root, True, True)
            self.assertEqual({name: path.read_bytes() for name, path in records.items()}, before)
            # The latest stage has explicitly invalidated this result. Its old
            # proof and earlier completed history must not become retention roots.
            old_outcome = json.loads(json.dumps(binding["active_workflow"]["last_outcome"]))
            result.update(status="unknown", invalidation_reason="canonical run needs retest")
            binding["active_workflow"]["task_state"]["completed"] = {}
            binding["latest_change"] = old_outcome
            write(root / ".governance/upg.json", binding)
            write(root / ".governance/field-reports.json", {"reports": [old_outcome]})
            self.assertEqual(len(state.compact(root, True, True)), 3)
            self.assertTrue(all(not path.exists() for path in records.values()))
            self.assertTrue((root / ".governance/field-reports.json").exists())

    def test_current_state_resolver_preserves_safe_object_and_read_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, value, message in (("current.json", [], "structured JSON object"),
                                              ("large.json", {"value": "x" * (256 * 1024)}, "bounded read limit")):
                source = write(root / relative, value)
                current = {"path": relative, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, message):
                    state.resolve_current_state(root, current)
            for relative in ("../outside.json", ".governance/upg.json", ".governance/field-reports.json"):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    state.resolve_current_state(root, {"path": relative, "sha256": "a" * 64})

    def test_compaction_preserves_reference_through_noncanonical_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ancestor").mkdir()
            alias = root / "ancestor" / ".."
            source = write(root / ".governance/execution/latest.json", execution([run()]))
            reference = ref(source, root)
            write(root / ".governance/handoff.json", handoff(reference))
            before = source.read_bytes()
            self.assertEqual(state.reference_path(reference, alias), source.resolve())
            self.assertEqual(state.compact(alias, False, False), [])
            self.assertEqual(state.compact(alias, True, False), [])
            self.assertEqual(source.read_bytes(), before)
            write(source, execution([run(pending_retest=True)]))
            with self.assertRaisesRegex(ValueError, "stale validation_ref"):
                state.compact(alias, True, False)
            self.assertTrue(source.exists())

    def test_reference_rejects_link_metadata_before_canonicalization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"validation_runs": [run()]})
            reference = ref(source, root)
            before = source.read_bytes()
            original = Path.lstat
            for override in ({"st_file_attributes": 1024}, {"st_nlink": 2}, {"st_mode": stat.S_IFLNK | 0o777}):
                def lstat(path, *args, **kwargs):
                    value = original(path, *args, **kwargs)
                    if path == source:
                        metadata = {"st_mode": value.st_mode, "st_nlink": value.st_nlink,
                                    "st_file_attributes": getattr(value, "st_file_attributes", 0)}
                        return SimpleNamespace(**dict(metadata, **override))
                    return value
                with self.subTest(override=override), patch.object(Path, "lstat", lstat), self.assertRaisesRegex(ValueError, "symlink/reparse|hardlinked"):
                    state.reference_path(reference, root)
            self.assertEqual(source.read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "Windows short-path identity regression")
    def test_compaction_preserves_reference_through_windows_short_root(self):
        import ctypes
        with tempfile.TemporaryDirectory(prefix="validation-continuity-long-name-") as directory:
            root = Path(directory)
            get_short_path = ctypes.windll.kernel32.GetShortPathNameW
            get_short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
            get_short_path.restype = ctypes.c_uint32
            buffer = ctypes.create_unicode_buffer(32768)
            length = get_short_path(str(root), buffer, len(buffer))
            if not length or length >= len(buffer):
                self.skipTest("Windows short-path alias unavailable on this volume")
            alias = Path(buffer.value)
            if alias == alias.resolve():
                self.skipTest("Windows short and canonical paths are identical on this volume")
            source = write(root / ".governance/execution/latest.json", execution([run()]))
            reference = ref(source, root)
            write(root / ".governance/handoff.json", handoff(reference))
            before = source.read_bytes()
            self.assertEqual(state.reference_path(reference, alias), source.resolve())
            self.assertEqual(state.compact(alias, True, False), [])
            self.assertEqual(source.read_bytes(), before)
            write(source, execution([run(pending_retest=True)]))
            with self.assertRaisesRegex(ValueError, "stale validation_ref"):
                state.compact(alias, True, False)
            self.assertTrue(source.exists())

    def test_cli_resolves_reference_only_with_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write(root / "execution_status.json", {"validation_runs": [run()]})
            path = write(root / "handoff.json", handoff(ref(source, root)))
            base = [sys.executable, str(TOOL)]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            rejected = subprocess.run(base + ["validate", str(path)], capture_output=True, text=True, env=env)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn("validation passed", rejected.stdout)
            accepted = subprocess.run(base + ["render", str(path), "--project-root", str(root), "--current-revision", "changed-b"], capture_output=True, text=True, env=env)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertIn("144/145", accepted.stdout)
            self.assertIn("Retest:** pending", accepted.stdout)


if __name__ == "__main__":
    unittest.main()
