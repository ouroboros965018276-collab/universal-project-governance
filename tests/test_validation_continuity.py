"""Canonical validation continuity regressions, using source rather than a compiled copy."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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


class ValidationContinuityTests(unittest.TestCase):
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
            for pointer, message in [("/absent", "pointer unavailable"), ("/tests/~2bad", "pointer escape"), ("/tests/focused", "unsupported canonical validation record")]:
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
