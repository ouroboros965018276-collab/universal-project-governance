from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from registration_fixture import change as fixture_change, report_identity

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable
RUNTIME = ROOT / "universal-project-governance"
UPG_SPEC = importlib.util.spec_from_file_location("upg_cli", ROOT / "upg.py")
UPG = importlib.util.module_from_spec(UPG_SPEC)
UPG_SPEC.loader.exec_module(UPG)

# The suite must not mutate the tree it validates: without this, importing the generated
# runtime scripts writes scripts/__pycache__ into release source, which then fails the
# packaging and mutant-manifest checks of the *next* run.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

def run(*args, cwd=None):
    return subprocess.run(
        [PY, *map(str, args)],
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

class CompiledRuntimeTests(unittest.TestCase):
    def test_top_level_installer_prefers_codex_project_target_over_old_skill_copies(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            stale = project / ".a-old-skills" / "universal-project-governance"
            installed = project / ".agents" / "skills" / "universal-project-governance"
            stale.mkdir(parents=True)
            installed.mkdir(parents=True)
            (stale / "SKILL.md").write_text("stale copy\n", encoding="utf-8")
            (installed / "SKILL.md").write_text("current Codex install\n", encoding="utf-8")

            self.assertEqual(UPG.find_installed(project), installed)

    def test_top_level_installer_does_not_treat_old_copy_as_codex_install(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            stale = project / ".a-old-skills" / "universal-project-governance"
            stale.mkdir(parents=True)
            (stale / "SKILL.md").write_text("stale copy\n", encoding="utf-8")

            self.assertIsNone(UPG.find_installed(project, "codex"))

    def test_top_level_installer_keeps_unique_non_codex_copy_compatible(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            installed = project / ".claude" / "skills" / "universal-project-governance"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("single copy\n", encoding="utf-8")

            self.assertEqual(UPG.find_installed(project, "claude"), installed)

    def test_top_level_installer_fails_closed_on_ambiguous_non_codex_copies(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            first = project / ".claude" / "skills" / "universal-project-governance"
            second = project / ".agents" / "skills" / "universal-project-governance"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            (first / "SKILL.md").write_text("first\n", encoding="utf-8")
            (second / "SKILL.md").write_text("second\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "multiple installed UPG copies"):
                UPG.find_installed(project, "claude")

    def test_top_level_installer_decodes_utf8_cli_output_on_windows(self):
        with tempfile.TemporaryDirectory() as td:
            cp = UPG.run(
                [PY, "-c", "import sys; sys.stdout.buffer.write(bytes.fromhex('e29c93'))"],
                pathlib.Path(td),
            )
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertEqual(cp.stdout, "✓")

    def test_top_level_installer_forwards_explicit_reporting_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            commands = []

            def fake_run(command, cwd):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(UPG.shutil, "which", return_value="npx"), patch.object(
                UPG, "run", side_effect=fake_run
            ), patch.object(UPG, "find_installed", return_value=RUNTIME):
                self.assertEqual(
                    UPG.install(td, "codex", str(ROOT), field_test_reporting=True),
                    0,
                )

            binding_command = next(command for command in commands if "project_tool.py" in command[1])
            self.assertIn("install", binding_command)
            self.assertIn("--field-test-reporting", binding_command)

    def test_compiler_drift_check(self):
        cp = run("compiler/compile_governance.py", "--check")
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_governance_lint_and_budget(self):
        cp = run("tools/governance_lint.py", ".")
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertLessEqual(
            len((RUNTIME / "SKILL.md").read_text(encoding="utf-8").splitlines()),
            120,
        )
        self.assertFalse((RUNTIME / "references").exists())
        self.assertFalse((RUNTIME / "assets").exists())

    def test_runtime_integrity(self):
        cp = run(RUNTIME / "scripts/validate_integrity.py", RUNTIME)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_integrity_detects_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            dst = pathlib.Path(td) / RUNTIME.name
            shutil.copytree(RUNTIME, dst)
            p = dst / "SKILL.md"
            p.write_text(
                p.read_text(encoding="utf-8") + "\nmutated\n",
                encoding="utf-8",
            )
            cp = subprocess.run(
                [PY, str(dst / "scripts/validate_integrity.py"), str(dst)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("integrity mismatch", cp.stderr)

    def test_compiler_write_requires_confirmation(self):
        cp = run("compiler/compile_governance.py", "--write")
        self.assertEqual(cp.returncode, 2)

    def test_plan_cases(self):
        data = json.loads(
            (ROOT / "tests/fixtures/governance_plan_cases.json").read_text(
                encoding="utf-8"
            )
        )
        for case in data["cases"]:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as td:
                ctx = pathlib.Path(td) / "context.json"
                ctx.write_text(json.dumps(case["context"]), encoding="utf-8")
                cp = subprocess.run(
                    [
                        PY,
                        str(RUNTIME / "scripts/plan_governance.py"),
                        "--context",
                        str(ctx),
                        "--json",
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
                plan = json.loads(cp.stdout)
                expected = case["expect"]
                for key in ("risk_level", "change_mode", "scope_guard", "report", "handoff"):
                    if key in expected:
                        self.assertEqual(plan[key], expected[key])
                self.assertEqual(plan["field_report_obligation"], "not-required")
                for rule_id in expected.get("contains", []):
                    self.assertIn(rule_id, plan["active_rules"])
                if "max_rules" in expected:
                    self.assertLessEqual(
                        len(plan["active_rules"]),
                        expected["max_rules"],
                    )

    def test_medium_risk_edit_defaults_to_structural_mode(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = pathlib.Path(td) / "context.json"
            ctx.write_text(
                json.dumps({
                    "operation": "edit",
                    "domains": ["code"],
                    "risk": {"scope": 2, "unknowns": 2},
                }),
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    PY,
                    str(RUNTIME / "scripts/plan_governance.py"),
                    "--context",
                    str(ctx),
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            plan = json.loads(cp.stdout)
            self.assertEqual(plan["change_mode"], "structural")
            self.assertEqual(plan["scope_guard"], "task-bounded-responsible-layer")
            self.assertIn("STRUCTURAL_INTEGRATION", plan["active_rules"])

    def test_project_binding_controls_planner_report_obligation(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            planner = RUNTIME / "scripts/plan_governance.py"
            context = pathlib.Path(td) / "context.json"
            context.write_text(json.dumps({"operation": "edit", "domains": ["code"]}), encoding="utf-8")

            cp = run(tool, "install", project)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            cp = run(planner, "--project-root", project, "--context", context, "--json")
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(json.loads(cp.stdout)["field_report_obligation"], "not-required")

            cp = run(tool, "ensure", project, "--field-test-reporting")
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            cp = run(planner, "--project-root", project, "--context", context, "--json")
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(json.loads(cp.stdout)["field_report_obligation"], "required-before-completion")

            cp = run(tool, "ensure", project)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertTrue(binding["field_test_reporting"])
            self.assertEqual(len(json.loads((project / ".governance/field-reports.json").read_text(encoding="utf-8"))["reports"]), 0)

    def test_unknown_risk_dimension_fails_with_allowed_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = pathlib.Path(td) / "context.json"
            ctx.write_text(
                json.dumps({
                    "operation": "edit",
                    "domains": ["code"],
                    "risk": {"data_impact": 1},
                }),
                encoding="utf-8",
            )
            cp = subprocess.run(
                [
                    PY,
                    str(RUNTIME / "scripts/plan_governance.py"),
                    "--context",
                    str(ctx),
                    "--json",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 2)
            self.assertIn("unknown risk dimension: data_impact", cp.stderr)
            self.assertIn("external_consumers", cp.stderr)

    def test_task_context_schema_risk_dimensions_match_model(self):
        schema = json.loads(
            (RUNTIME / "schemas/task-context.schema.json").read_text(encoding="utf-8")
        )
        index = json.loads((RUNTIME / "policy-index.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(schema["properties"]["risk"]["properties"]),
            set(index["risk_model"]["dimensions"]),
        )
        self.assertFalse(schema["properties"]["risk"]["additionalProperties"])

    def test_project_binding_report_export_and_safe_remove(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run(
                [PY, str(tool), "install", str(project), "--field-test-reporting"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue((project / ".governance/upg.json").is_file())
            self.assertTrue((project / ".governance/field-reports.json").is_file())
            binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertEqual(binding["schema_version"], 2)
            self.assertEqual(binding["adoption_mode"], "in-place")
            self.assertEqual(binding["continuity_mode"], "handoff-or-reconstruct")
            self.assertEqual(binding["capability_handshake"], "observe-before-assume")
            self.assertTrue(binding["field_test_reporting"])

            report = {
                "task": "Fix bounded defect",
                "status": "complete",
                "change_mode": "structural",
                "scope_guard": "task-bounded-responsible-layer",
                "risk_level": "medium",
                "active_rules": ["STRUCTURAL_INTEGRATION"],
                "changed_files": ["module.py"],
                "validation": ["unit tests pass"],
                "cleanup": ["obsolete shim removed"],
                "structural_scope": {
                    "canonical_layer": "module.py",
                    "unrelated_changes": [],
                    "api_changes": [],
                    "architecture_changes": [],
                    "overreach_concern": False,
                },
                "integrity": "pass",
                "handoff": "not-required",
                "feedback": [],
            }
            input_path = project / "report-input.json"
            input_path.write_text(json.dumps(report_identity(report)), encoding="utf-8")
            cp = subprocess.run(
                [PY, str(tool), "report", str(project), "--input", str(input_path)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            ledger = json.loads((project / ".governance/field-reports.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger["reports"]), 1)
            self.assertEqual(ledger["reports"][0]["sequence"], 1)

            binding_path = project / ".governance/upg.json"
            ledger_path = project / ".governance/field-reports.json"
            binding_before = binding_path.read_bytes()
            ledger_before = ledger_path.read_bytes()
            cp = subprocess.run(
                [PY, str(tool), "remove", str(project), "--yes"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("export and purge", cp.stderr)
            self.assertEqual(binding_path.read_bytes(), binding_before)
            self.assertEqual(ledger_path.read_bytes(), ledger_before)

            export_path = project / "field-test-export.json"
            cp = subprocess.run(
                [PY, str(tool), "export", str(project), "--output", str(export_path)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            exported = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(len(exported["reports"]), 1)

            cp = subprocess.run(
                [PY, str(tool), "purge-reports", str(project), "--yes"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(json.loads(ledger_path.read_text(encoding="utf-8"))["reports"], [])

            keep = project / ".governance/keep.json"
            keep.write_text('{"project_owned":true}\n', encoding="utf-8")
            cp = subprocess.run(
                [PY, str(tool), "remove", str(project), "--yes"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertFalse((project / ".governance/upg.json").exists())
            self.assertFalse((project / ".governance/field-reports.json").exists())
            self.assertTrue(keep.is_file())

    def test_existing_project_is_adopted_in_place_without_rewriting_content(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "legacy"
            project.mkdir()
            existing = project / "legacy-notes.txt"
            existing.write_text("pre-UPG project truth\n", encoding="utf-8")
            before = existing.read_bytes()
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run(
                [PY, str(tool), "install", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(existing.read_bytes(), before)
            binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertEqual(binding["project_origin"], "existing")
            self.assertEqual(binding["adoption_mode"], "in-place")
            self.assertFalse(binding["field_test_reporting"])
            self.assertFalse((project / ".governance/field-reports.json").exists())

    def test_rc7_binding_upgrades_without_losing_report_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            governance = project / ".governance"
            governance.mkdir()
            (governance / "upg.json").write_text(json.dumps({
                "schema_version": 1,
                "managed_by": "universal-project-governance",
                "runtime_version": "3.0.0-rc.7",
                "field_test_reporting": True,
                "managed_files": [".governance/upg.json", ".governance/field-reports.json"],
                "field_report_file": ".governance/field-reports.json",
                "max_reports": 200,
            }), encoding="utf-8")
            (governance / "field-reports.json").write_text(json.dumps({
                "schema_version": 1,
                "runtime_version": "3.0.0-rc.7",
                "reports": [{"sequence": 1, "task": "preserve-me"}],
            }), encoding="utf-8")
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run(
                [PY, str(tool), "ensure", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            binding = json.loads((governance / "upg.json").read_text(encoding="utf-8"))
            ledger = json.loads((governance / "field-reports.json").read_text(encoding="utf-8"))
            self.assertEqual(binding["schema_version"], 2)
            self.assertEqual(ledger["reports"][0]["task"], "preserve-me")

    def test_field_reporting_is_opt_in_per_project_and_existing_setting_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run(
                [PY, str(tool), "install", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue((project / ".governance/upg.json").is_file())
            self.assertFalse((project / ".governance/field-reports.json").exists())
            binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertEqual(binding["managed_files"], [".governance/upg.json"])
            self.assertFalse(binding["field_test_reporting"])
            cp = subprocess.run(
                [PY, str(tool), "status", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertFalse(json.loads(cp.stdout)["field_test_reporting"])

            bad = project / "report.json"
            bad.write_text("{}", encoding="utf-8")
            cp = subprocess.run(
                [PY, str(tool), "report", str(project), "--input", str(bad)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("disabled", cp.stderr)
            self.assertFalse((project / ".governance/field-reports.json").exists())

            cp = subprocess.run(
                [PY, str(tool), "install", str(project), "--field-test-reporting"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            enabled = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertTrue(enabled["field_test_reporting"])
            self.assertTrue((project / ".governance/field-reports.json").is_file())
            cp = subprocess.run(
                [PY, str(tool), "status", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads(cp.stdout)["field_test_reporting"])
            self.assertEqual(json.loads(cp.stdout)["report_count"], 0)

            cp = subprocess.run(
                [PY, str(tool), "ensure", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))["field_test_reporting"])

    def test_disabled_reporting_does_not_purge_unowned_ledger_path(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            installed = subprocess.run(
                [PY, str(tool), "install", str(project)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            ledger = project / ".governance/field-reports.json"
            ledger.write_text('{"owner":"project"}\n', encoding="utf-8")
            before = ledger.read_bytes()
            purged = subprocess.run(
                [PY, str(tool), "purge-reports", str(project), "--yes"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(purged.returncode, 0)
            self.assertIn("not owned", purged.stderr)
            self.assertEqual(ledger.read_bytes(), before)

    def test_field_report_contract_rejects_incomplete_report(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run([PY, str(tool), "install", str(project), "--field-test-reporting"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            bad = project / "bad.json"
            bad.write_text('{"task":"missing contract"}\n', encoding="utf-8")
            cp = subprocess.run(
                [PY, str(tool), "report", str(project), "--input", str(bad)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            ledger = json.loads((project / ".governance/field-reports.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["reports"], [])

    def test_field_report_rejects_credential_material(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run(
                [PY, str(tool), "install", str(project), "--field-test-reporting"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            report = {
                "task": "inspect " + ("-----BEGIN " + "PRIVATE KEY-----"),
                "status": "complete",
                "change_mode": "local",
                "scope_guard": "local-only",
                "risk_level": "low",
                "active_rules": [],
                "changed_files": [],
                "validation": [],
                "cleanup": [],
                "structural_scope": {
                    "canonical_layer": "none",
                    "unrelated_changes": [],
                    "api_changes": [],
                    "architecture_changes": [],
                    "overreach_concern": False,
                },
                "integrity": "pass",
                "handoff": "not-required",
                "feedback": [],
            }
            payload = project / "credential-report.json"
            payload.write_text(json.dumps(report_identity(report)), encoding="utf-8")
            cp = subprocess.run(
                [PY, str(tool), "report", str(project), "--input", str(payload)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("credential or secret material", cp.stderr)

    def test_field_report_rejects_bearer_jwt_and_database_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td)
            tool = RUNTIME / "scripts/project_tool.py"
            cp = subprocess.run([PY, str(tool), "install", str(project), "--field-test-reporting"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            base = {
                "task": "safe summary", "status": "complete", "change_mode": "local",
                "scope_guard": "local-only", "risk_level": "low", "active_rules": [],
                "changed_files": [], "validation": [], "cleanup": [],
                "structural_scope": {"canonical_layer": "none", "unrelated_changes": [], "api_changes": [], "architecture_changes": [], "overreach_concern": False},
                "integrity": "pass", "handoff": "not-required", "feedback": [],
            }
            secrets = [
                "Bearer " + "abcdefghijklmnopqrstuvwxyz012345",
                "eyJabcdefghijk.abcdefghijklmnop.abcdefghijklmnop",
                "postgres://alice:supersecret@db.internal/app",
                "api_key=abcdefghijklmnop",
            ]
            for i, value in enumerate(secrets):
                report = dict(base)
                report["task"] = value
                payload = project / ("secret-%d.json" % i)
                payload.write_text(json.dumps(report_identity(report)), encoding="utf-8")
                cp = subprocess.run([PY, str(tool), "report", str(project), "--input", str(payload)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                self.assertNotEqual(cp.returncode, 0, value)

    def test_handoff_schema_validate_and_render(self):
        sample = {
            "updated_at": "2026-10-03T14:17:00+08:00",
            "goal": "Continue migration",
            "status": "in_progress",
            "completed": ["new endpoint"],
            "in_progress": ["consumer cutover"],
            "decisions": ["v2 canonical"],
            "invariants": ["no dual truth"],
            "risks": ["legacy client"],
            "next_actions": ["migrate client"],
            "validation": ["contract tests"],
            "canonical_sources": ["PROJECT_STATE.md"],
        }
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "handoff.json"
            p.write_text(json.dumps(sample), encoding="utf-8")
            cp = subprocess.run(
                [
                    PY,
                    str(RUNTIME / "scripts/state_tool.py"),
                    "validate",
                    str(p),
                    "--schema",
                    "handoff",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_compaction_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            directory = root / ".governance/execution"
            directory.mkdir(parents=True)
            payload = {
                "updated_at": "2026-10-03T14:17:00+08:00",
                "level": "engineering",
                "task": "x",
                "status": "complete",
                "actions": [],
                "cleanup": [],
                "validation": [],
                "findings": [],
                "governance_feedback": [],
                "retain_for_audit": False,
                "durable_summary_recorded": True,
            }
            p = directory / "latest.json"
            p.write_text(json.dumps(payload), encoding="utf-8")
            cp = subprocess.run(
                [
                    PY,
                    str(RUNTIME / "scripts/state_tool.py"),
                    "compact",
                    str(root),
                    "--apply",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertFalse(p.exists())

    def test_feedback_compaction_keeps_only_open(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            directory = root / ".governance/feedback"
            directory.mkdir(parents=True)
            payload = {
                "updated_at": "2026-10-03T14:17:00+08:00",
                "items": [
                    {
                        "id": "a",
                        "status": "resolved",
                        "observation": "x",
                        "evidence": [],
                        "consequence": "x",
                        "scope": "skill",
                    },
                    {
                        "id": "b",
                        "status": "open",
                        "observation": "y",
                        "evidence": ["z"],
                        "consequence": "y",
                        "scope": "project",
                    },
                ],
            }
            p = directory / "open.json"
            p.write_text(json.dumps(payload), encoding="utf-8")
            cp = subprocess.run(
                [
                    PY,
                    str(RUNTIME / "scripts/state_tool.py"),
                    "compact",
                    str(root),
                    "--apply",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            left = json.loads(p.read_text(encoding="utf-8"))["items"]
            self.assertEqual([item["id"] for item in left], ["b"])

    def test_evidence_export_excludes_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            governance = root / ".governance"
            governance.mkdir()
            (governance / "handoff.json").write_text(
                json.dumps({"x": 1}),
                encoding="utf-8",
            )
            (root / "secret.txt").write_text(
                "never export",
                encoding="utf-8",
            )
            output = root / "bundle.json"
            cp = subprocess.run(
                [
                    PY,
                    str(RUNTIME / "scripts/state_tool.py"),
                    "export",
                    str(root),
                    "--output",
                    str(output),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertIn("handoff.json", text)
            self.assertNotIn("never export", text)

    def test_linter_detects_cycle(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            shutil.copytree(ROOT / "governance-src", tmp / "governance-src")
            model_path = tmp / "governance-src/model/governance-model.json"
            model = json.loads(model_path.read_text(encoding="utf-8"))
            by_id = {p["id"]: p for p in model["policies"]}
            by_id["CLEANUP_OBSOLETE"]["requires"] = ["EVIDENCE_AFFECTED"]
            by_id["EVIDENCE_AFFECTED"]["requires"] = ["CLEANUP_OBSOLETE"]
            model_path.write_text(json.dumps(model), encoding="utf-8")
            cp = subprocess.run(
                [PY, str(ROOT / "tools/governance_lint.py"), str(tmp)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("G007", cp.stderr)

    def test_deterministic_package(self):
        with tempfile.TemporaryDirectory() as td:
            first = pathlib.Path(td) / "first"
            second = pathlib.Path(td) / "second"
            cp1 = run(
                "tools/package_release.py",
                "universal-project-governance",
                "--output-dir",
                first,
            )
            cp2 = run(
                "tools/package_release.py",
                "universal-project-governance",
                "--output-dir",
                second,
            )
            self.assertEqual(cp1.returncode, 0, cp1.stdout + cp1.stderr)
            self.assertEqual(cp2.returncode, 0, cp2.stdout + cp2.stderr)
            z1 = next(first.glob("*.zip"))
            z2 = next(second.glob("*.zip"))
            self.assertEqual(
                hashlib.sha256(z1.read_bytes()).hexdigest(),
                hashlib.sha256(z2.read_bytes()).hexdigest(),
            )

    def test_local_bytecode_residue_does_not_fail_the_bundle_check(self):
        with tempfile.TemporaryDirectory() as td:
            copy = pathlib.Path(td) / RUNTIME.name
            shutil.copytree(
                RUNTIME,
                copy,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
            cache = copy / "scripts" / "__pycache__"
            cache.mkdir()
            (cache / "state_tool.cpython-312.pyc").write_bytes(b"residue")
            cp = run("tools/validate_skill_bundle.py", str(copy))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("local bytecode residue present", cp.stdout)
            (copy / "scripts" / "stray.pyc").write_bytes(b"stray")
            cp = run("tools/validate_skill_bundle.py", str(copy))
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("generated artifact bundled", cp.stderr)

    def _workflow_report(self, workflow_id, status="complete", parent_event_id=None, task="Bounded test change"):
        report = {
            "task": task,
            "status": status,
            "change_mode": "local",
            "scope_guard": "local-only",
            "risk_level": "low",
            "active_rules": [],
            "changed_files": ["module.py"],
            "validation": ["unit checks pass"],
            "cleanup": [],
            "structural_scope": {
                "canonical_layer": "module.py",
                "unrelated_changes": [],
                "api_changes": [],
                "architecture_changes": [],
                "overreach_concern": False,
            },
            "integrity": "pass",
            "handoff": "not-required",
            "feedback": [],
            "workflow_id": workflow_id,
            "change": fixture_change(),
        }
        report["change"]["parent_event_id"] = parent_event_id
        return report

    def test_default_workflow_finish_is_idempotent_and_continues_into_opt_in_sequence(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            cp = run(tool, "install", project)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            binding_path = project / ".governance/upg.json"

            begin_a = {"workflow_id": "workflow-a", "change": fixture_change()}
            begin_path = project / "begin-a.json"
            begin_path.write_text(json.dumps(begin_a), encoding="utf-8")
            cp = run(tool, "begin", project, "--input", begin_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

            report_a = self._workflow_report("workflow-a")
            report_path = project / "finish-a.json"
            report_path.write_text(json.dumps(report_a), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", report_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(json.loads(cp.stdout)["sequence"], 1)
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            self.assertNotIn("active_workflow", binding)
            self.assertEqual(binding["latest_change"]["sequence"], 1)
            self.assertFalse((project / ".governance/field-reports.json").exists())

            cp = run(tool, "finish", project, "--input", report_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads(cp.stdout)["idempotent"])
            conflict = dict(report_a, task="conflicting retry")
            conflict_path = project / "finish-conflict.json"
            conflict_path.write_text(json.dumps(conflict), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", conflict_path)
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("conflicting", cp.stderr)

            cp = run(tool, "ensure", project, "--field-test-reporting")
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            ledger_path = project / ".governance/field-reports.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(ledger["next_sequence"], 2)

            wrong_parent = {"workflow_id": "workflow-b", "change": fixture_change()}
            wrong_parent["change"]["parent_event_id"] = "incorrect-parent"
            wrong_path = project / "begin-b-wrong.json"
            wrong_path.write_text(json.dumps(wrong_parent), encoding="utf-8")
            cp = run(tool, "begin", project, "--input", wrong_path)
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("latest completed event", cp.stderr)

            begin_b = {"workflow_id": "workflow-b", "change": fixture_change()}
            begin_b["change"]["parent_event_id"] = binding["latest_change"]["event_id"]
            begin_b_path = project / "begin-b.json"
            begin_b_path.write_text(json.dumps(begin_b), encoding="utf-8")
            cp = run(tool, "begin", project, "--input", begin_b_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            report_b = self._workflow_report("workflow-b", parent_event_id=begin_b["change"]["parent_event_id"])
            report_b_path = project / "finish-b.json"
            report_b_path.write_text(json.dumps(report_b), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", report_b_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(json.loads(cp.stdout)["sequence"], 2)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual([row["sequence"] for row in ledger["reports"]], [2])
            self.assertEqual(json.loads(binding_path.read_text(encoding="utf-8"))["latest_change"]["sequence"], 2)

            cp = run(tool, "finish", project, "--input", report_b_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads(cp.stdout)["idempotent"])
            self.assertEqual(len(json.loads(ledger_path.read_text(encoding="utf-8"))["reports"]), 1)

    def test_opt_in_partial_report_keeps_active_workflow_for_completion_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            cp = run(tool, "install", project, "--field-test-reporting")
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            start = {"workflow_id": "workflow-partial", "change": fixture_change()}
            start_path = project / "begin.json"
            start_path.write_text(json.dumps(start), encoding="utf-8")
            cp = run(tool, "begin", project, "--input", start_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

            partial = self._workflow_report("workflow-partial", status="partial")
            partial_path = project / "partial.json"
            partial_path.write_text(json.dumps(partial), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", partial_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("active_workflow", json.loads((project / ".governance/upg.json").read_text(encoding="utf-8")))
            cp = run(tool, "begin", project, "--input", start_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads(cp.stdout)["idempotent"])

            complete = self._workflow_report("workflow-partial")
            complete_path = project / "complete.json"
            complete_path.write_text(json.dumps(complete), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", complete_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertNotIn("active_workflow", binding)
            ledger = json.loads((project / ".governance/field-reports.json").read_text(encoding="utf-8"))
            self.assertEqual([row["status"] for row in ledger["reports"]], ["partial", "complete"])

    def test_default_partial_workflow_keeps_active_checkpoint_until_recovered(self):
        with tempfile.TemporaryDirectory() as td:
            project = pathlib.Path(td) / "project"
            project.mkdir()
            tool = RUNTIME / "scripts/project_tool.py"
            cp = run(tool, "install", project)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            start = {"workflow_id": "workflow-default-partial", "change": fixture_change()}
            start_path = project / "begin.json"
            start_path.write_text(json.dumps(start), encoding="utf-8")
            cp = run(tool, "begin", project, "--input", start_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

            partial_path = project / "partial.json"
            partial_path.write_text(json.dumps(self._workflow_report("workflow-default-partial", status="partial")), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", partial_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            partial_binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertIn("active_workflow", partial_binding)
            self.assertFalse(partial_binding["field_test_reporting"])
            self.assertFalse((project / ".governance/field-reports.json").exists())

            cp = run(tool, "begin", project, "--input", start_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads(cp.stdout)["idempotent"])
            complete_path = project / "complete.json"
            complete_path.write_text(json.dumps(self._workflow_report("workflow-default-partial")), encoding="utf-8")
            cp = run(tool, "finish", project, "--input", complete_path)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            binding = json.loads((project / ".governance/upg.json").read_text(encoding="utf-8"))
            self.assertNotIn("active_workflow", binding)
            self.assertEqual(binding["latest_change"]["sequence"], 1)
            self.assertFalse((project / ".governance/field-reports.json").exists())

    def test_reporting_opt_in_validation_failure_does_not_mutate_binding_or_create_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            tool = RUNTIME / "scripts/project_tool.py"
            for field, value in [("sequence", -1), ("epoch", -1)]:
                with self.subTest(field=field):
                    project = pathlib.Path(td) / field
                    project.mkdir()
                    cp = run(tool, "install", project)
                    self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
                    binding_path = project / ".governance/upg.json"
                    binding = json.loads(binding_path.read_text(encoding="utf-8"))
                    binding["latest_change"] = {"sequence": value, "epoch": 0 if field == "sequence" else value}
                    binding_path.write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")
                    before = binding_path.read_bytes()

                    cp = run(tool, "ensure", project, "--field-test-reporting")
                    self.assertNotEqual(cp.returncode, 0)
                    self.assertIn("invalid", cp.stderr)
                    self.assertEqual(binding_path.read_bytes(), before)
                    self.assertFalse((project / ".governance/field-reports.json").exists())

                    cp = run(tool, "status", project)
                    self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
                    self.assertTrue(json.loads(cp.stdout)["ok"])
                    self.assertFalse(json.loads(cp.stdout)["field_test_reporting"])

    def test_planner_validates_full_context_schema_and_keeps_unknown_profile_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            context_path = pathlib.Path(td) / "context.json"
            planner = RUNTIME / "scripts/plan_governance.py"
            invalid = [
                {"operation": "edit", "domains": ["code"], "signals": [None]},
                {"operation": "edit", "domains": ["code"], "profiles": [1]},
                {"operation": "edit", "domains": ["code"], "unfinished": 1},
                {"operation": "edit", "domains": ["code"], "explicit_audit": "yes"},
                {"operation": "edit", "domains": ["code"], "field_test_reporting": 0},
                {"operation": "edit", "domains": ["code"], "project_type": ""},
                {"operation": "edit", "domains": ["code"], "agent_mode": 3},
                {"operation": "edit", "domains": ["code"], "capabilities": [""]},
                {"operation": "edit", "domains": ["code"], "risk": []},
                {"operation": "edit", "domains": ["code"], "unexpected": True},
                [],
            ]
            for case in invalid:
                with self.subTest(context=case):
                    context_path.write_text(json.dumps(case), encoding="utf-8")
                    cp = run(planner, "--context", context_path, "--json")
                    self.assertNotEqual(cp.returncode, 0, cp.stdout + cp.stderr)

            context_path.write_text(json.dumps({"operation": "edit", "domains": ["code"], "profiles": ["not-a-known-profile"]}), encoding="utf-8")
            cp = run(planner, "--context", context_path, "--json")
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("unknown optional profiles", json.loads(cp.stdout)["warnings"][0])

            context_path.write_text(json.dumps({"operation": "edit", "domains": ["code"], "risk": {"unmodeled": 1}}), encoding="utf-8")
            cp = run(planner, "--context", context_path, "--json")
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("unknown risk dimension: unmodeled", cp.stderr)


if __name__ == "__main__":
    unittest.main()
