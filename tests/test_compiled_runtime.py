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
from registration_fixture import report_identity

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

if __name__ == "__main__":
    unittest.main()
