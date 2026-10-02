from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "universal-project-governance"
PYTHON = sys.executable


def run(script: str, *args: str, cwd: Path | None = None):
    return subprocess.run(
        [PYTHON, str(SKILL / "scripts" / script), *map(str, args)],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class IntegrityTests(unittest.TestCase):
    def staged_skill(self, root: Path) -> Path:
        dst = root / SKILL.name
        shutil.copytree(SKILL, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        refresh = subprocess.run(
            [PYTHON, str(dst / "scripts" / "refresh_integrity.py"), str(dst), "--confirm-governance-upgrade"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(refresh.returncode, 0, refresh.stdout + refresh.stderr)
        return dst

    def test_integrity_detects_protected_file_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            dst = self.staged_skill(Path(td))
            ok = subprocess.run([PYTHON, str(dst / "scripts" / "validate_integrity.py"), str(dst)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            with (dst / "SKILL.md").open("a", encoding="utf-8") as f:
                f.write("\nunauthorized drift\n")
            bad = subprocess.run([PYTHON, str(dst / "scripts" / "validate_integrity.py"), str(dst)],
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("integrity mismatch: SKILL.md", bad.stderr)

    def test_checksum_refresh_requires_explicit_upgrade_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / SKILL.name
            shutil.copytree(SKILL, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            cp = subprocess.run([PYTHON, str(dst / "scripts" / "refresh_integrity.py"), str(dst)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(cp.returncode, 2)
            self.assertIn("refusing checksum refresh", cp.stderr)


class ReportPolicyTests(unittest.TestCase):
    def classify(self, *args: str):
        cp = run("classify_report.py", *args)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        return json.loads(cp.stdout)

    def test_small_change_has_no_standalone_report(self):
        result = self.classify("--mode", "standard", "--files-changed", "1", "--lines-changed", "8")
        self.assertEqual(result["report_level"], "change-note")
        self.assertFalse(result["standalone_report"])
        self.assertFalse(result["execution_audit"])

    def test_refactor_in_evaluation_mode_generates_engineering_and_execution_audit(self):
        result = self.classify("--mode", "evaluation", "--files-changed", "5", "--lines-changed", "120", "--refactor")
        self.assertEqual(result["report_level"], "engineering")
        self.assertTrue(result["standalone_report"])
        self.assertTrue(result["execution_audit"])

    def test_release_generates_audit(self):
        result = self.classify("--release")
        self.assertEqual(result["report_level"], "audit")
        self.assertTrue(result["standalone_report"])


class HandoffTests(unittest.TestCase):
    def test_blank_template_fails_but_populated_snapshot_passes(self):
        blank = run("validate_handoff.py", str(SKILL / "assets" / "templates" / "HANDOFF.md"))
        self.assertEqual(blank.returncode, 1)

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "HANDOFF.md"
            p.write_text("""# Project Handoff Snapshot
**Last Updated:** 2026-10-02T22:00:00+08:00
## Current Objective
Complete parser migration.
## Current State
New parser is active in staging.
## Completed
- Callers migrated.
## In Progress
- Production rollout.
## Important Decisions
- v2 parser is canonical.
## Do Not Change Without Review
- Public schema.
## Known Risks / Open Questions
- Production rollout not yet observed.
## Validation / Evidence
- Focused tests pass.
## Recommended Next Actions
1. Roll out and verify metrics.
""", encoding="utf-8")
            ok = run("validate_handoff.py", str(p))
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)


class ReportLifecycleTests(unittest.TestCase):
    def test_retention_overflow_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gov = root / ".governance"
            (gov / "execution").mkdir(parents=True)
            (gov / "config.json").write_text('{"mode":"evaluation","execution_retention":2}', encoding="utf-8")
            for i in range(3):
                (gov / "execution" / f"{i}.md").write_text("# audit\n", encoding="utf-8")
            cp = run("validate_reports.py", str(root))
            self.assertEqual(cp.returncode, 1)
            self.assertIn("retention exceeded", cp.stderr)

    def test_evidence_export_excludes_project_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "PROJECT_STATE.md").write_text("# Project State\nSafe summary.\n", encoding="utf-8")
            (root / "secret_source.py").write_text("API_SECRET='do-not-export'\n", encoding="utf-8")
            gov = root / ".governance"
            gov.mkdir()
            (gov / "HANDOFF.md").write_text("# Project Handoff Snapshot\nSummary only.\n", encoding="utf-8")
            cp = run("export_evidence_bundle.py", str(root))
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertIn("PROJECT_STATE.md", cp.stdout)
            self.assertIn("HANDOFF.md", cp.stdout)
            self.assertNotIn("do-not-export", cp.stdout)
            self.assertNotIn("secret_source.py", cp.stdout)


if __name__ == "__main__":
    unittest.main()
