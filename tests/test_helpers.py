from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "universal-project-governance"
PYTHON = sys.executable


def run_python(path: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(path), *map(str, args)],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def skill_script(name: str, *args: str, cwd: Path | None = None):
    return run_python(SKILL / "scripts" / name, *args, cwd=cwd)


def tool(name: str, *args: str, cwd: Path | None = None):
    return run_python(REPO / "tools" / name, *args, cwd=cwd)


class InspectorTests(unittest.TestCase):
    def test_scanner_reports_truncation_and_skips_symlink_and_secret(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            (root / "a.txt").write_text("TODO local\n", encoding="utf-8")
            (root / "b.txt").write_text("same\n", encoding="utf-8")
            (root / "c.txt").write_text("same\n", encoding="utf-8")
            (root / ".env").write_text("TODO SECRET=1\n", encoding="utf-8")
            (root / "prod-secrets.yaml").write_text("TODO should-not-read\n", encoding="utf-8")
            external = Path(outside) / "external.txt"
            external.write_text("TODO outside\n", encoding="utf-8")
            try:
                (root / "linked.txt").symlink_to(external)
            except OSError:
                pass

            cp = skill_script("inspect_project.py", str(root), "--markers", "--duplicates", "--max-files", "2")
            self.assertEqual(cp.returncode, 0, cp.stderr)
            report = json.loads(cp.stdout)
            self.assertTrue(report["signals"]["scan_truncated"])
            self.assertEqual(report["signals"]["file_count_scanned"], 2)
            self.assertLessEqual(report.get("marker_counts", {}).get("TODO", 0), 1)

    def test_scanner_duplicate_detection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "z.txt").write_text("same\n", encoding="utf-8")
            (root / "a.txt").write_text("same\n", encoding="utf-8")
            cp1 = skill_script("inspect_project.py", str(root), "--duplicates")
            cp2 = skill_script("inspect_project.py", str(root), "--duplicates")
            self.assertEqual(cp1.returncode, 0, cp1.stderr)
            self.assertEqual(cp1.stdout, cp2.stdout)
            report = json.loads(cp1.stdout)
            self.assertEqual(report["exact_duplicate_groups"], [["a.txt", "z.txt"]])
            self.assertFalse(report["signals"]["scan_truncated"])


@unittest.skipUnless(shutil.which("git"), "git is required")
class ChangedReferenceTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)

    def test_renamed_path_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            (root / "old.txt").write_text("hello\n", encoding="utf-8")
            (root / "README.md").write_text("See old.txt\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True)
            subprocess.run(["git", "-C", str(root), "mv", "old.txt", "new.txt"], check=True)
            cp = skill_script("check_changed_refs.py", str(root))
            self.assertEqual(cp.returncode, 1)
            self.assertIn("old.txt", cp.stdout)
            self.assertIn("README.md", cp.stdout)

    def test_reference_scanner_does_not_follow_symlinked_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root = Path(td)
            self._init_repo(root)
            (root / "old.txt").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True)
            external = Path(outside) / "outside.md"
            external.write_text("old.txt\n", encoding="utf-8")
            try:
                (root / "linked.md").symlink_to(external)
            except OSError:
                self.skipTest("symlink creation unavailable")
            subprocess.run(["git", "-C", str(root), "rm", "old.txt"], check=True, stdout=subprocess.DEVNULL)
            cp = skill_script("check_changed_refs.py", str(root))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertNotIn("linked.md", cp.stdout)


class GovernanceValidatorTests(unittest.TestCase):
    def test_untouched_templates_do_not_false_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("PROJECT_STATE.md", "MODULE_MAP.md", "EXCEPTIONS.md", "DECISIONS.md"):
                shutil.copy2(SKILL / "assets" / name, root / name)
            cp = skill_script("validate_project_governance.py", str(root))
            self.assertEqual(cp.returncode, 1)
            self.assertTrue("template" in (cp.stdout + cp.stderr).lower() or "empty" in (cp.stdout + cp.stderr).lower())

    def test_repository_self_governance_passes(self) -> None:
        cp = skill_script("validate_project_governance.py", str(REPO))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("passed", cp.stdout.lower())


class RepositoryAndBundleTests(unittest.TestCase):
    def test_skill_bundle_validator_passes(self) -> None:
        cp = tool("validate_skill_bundle.py", str(SKILL))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("Skill bundle check passed", cp.stdout)

    def test_repository_validator_passes(self) -> None:
        cp = tool("validate_repository.py", str(REPO))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("Repository check passed", cp.stdout)

    def test_security_audit_passes(self) -> None:
        cp = tool("security_audit.py", str(REPO))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("Security audit passed", cp.stdout)

    def test_license_copies_match(self) -> None:
        self.assertEqual((REPO / "LICENSE").read_bytes(), (SKILL / "LICENSE").read_bytes())

    def test_deterministic_packager_contains_only_skill_surface(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out1 = Path(td) / "one"
            out2 = Path(td) / "two"
            cp1 = tool("package_release.py", str(SKILL), "--output-dir", str(out1))
            cp2 = tool("package_release.py", str(SKILL), "--output-dir", str(out2))
            self.assertEqual(cp1.returncode, 0, cp1.stdout + cp1.stderr)
            self.assertEqual(cp2.returncode, 0, cp2.stdout + cp2.stderr)
            z1 = next(out1.glob("*.zip"))
            z2 = next(out2.glob("*.zip"))
            self.assertEqual(hashlib.sha256(z1.read_bytes()).hexdigest(), hashlib.sha256(z2.read_bytes()).hexdigest())
            with zipfile.ZipFile(z1) as zf:
                names = zf.namelist()
            self.assertTrue(names)
            prefix = SKILL.name + "/"
            self.assertTrue(all(name.startswith(prefix) for name in names))
            self.assertIn(prefix + "SKILL.md", names)
            self.assertNotIn(prefix + ".github/workflows/validate.yml", names)
            self.assertFalse(any("/tests/" in name or "/evals/" in name or "/audits/" in name for name in names))


if __name__ == "__main__":
    unittest.main()
