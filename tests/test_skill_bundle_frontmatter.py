"""The generated bundle accepts a declared string subset, not arbitrary YAML."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "universal-project-governance"
VALIDATOR = ROOT / "tools" / "validate_skill_bundle.py"
SPEC = importlib.util.spec_from_file_location("skill_bundle_validator", VALIDATOR)
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)

BAD_DESCRIPTION = ("Govern maintained-project changes across project types/hosts: "
                   "task-bounded integration, proportional cleanup and evidence.")


def document(description="Safe generated description", compatibility="Python 3.8+ helpers"):
    return ("---\nname: universal-project-governance\ndescription: " + description
            + "\nlicense: Apache-2.0\ncompatibility: " + compatibility
            + '\nmetadata:\n  version: "3.0.0-rc.19"\n---\nBody\n')


class SkillBundleFrontmatterTests(unittest.TestCase):
    def test_real_ci_unquoted_mapping_indicator_is_rejected(self):
        data, errors = BUNDLE.frontmatter(document(BAD_DESCRIPTION))
        self.assertNotIn("description", data)
        self.assertTrue(any("description" in error and "JSON double quotes" in error for error in errors))

    def test_compatibility_and_plain_comment_ambiguity_are_rejected(self):
        for description, compatibility in (("Safe text # hidden suffix", "Python helpers"),
                                            ("Safe text", "Helpers: Python 3.8+"),
                                            ("Safe text", "Python helpers # hidden suffix")):
            with self.subTest(description=description, compatibility=compatibility):
                self.assertTrue(BUNDLE.frontmatter(document(description, compatibility))[1])

    def test_safe_plain_and_json_quoted_special_text_are_preserved(self):
        for plain in ("Safe generated description", "3.0.0-rc.19", "5 step process", "治理与证据"):
            with self.subTest(plain=plain):
                data, errors = BUNDLE.frontmatter(document(plain))
                self.assertEqual(errors, [])
                self.assertEqual(data["description"], plain)
        quoted = BAD_DESCRIPTION + ' Literal #, apostrophe it\'s, quote " and slash \\ stay text.'
        data, errors = BUNDLE.frontmatter(document(json.dumps(quoted), json.dumps("Helpers: Python # literal")))
        self.assertEqual(errors, [])
        self.assertEqual(data["description"], quoted)
        self.assertEqual(data["compatibility"], "Helpers: Python # literal")

    def test_typed_literals_and_unsupported_quotes_require_json_strings(self):
        for value in ("true", "null", "42", "0xFF", ".inf", "2026-10-13", "12:30", "*alias", ",flow",
                      "'simple string'", "'it''s a string'", '"unterminated', '"text" # comment',
                      '"\\ud800"'):
            with self.subTest(value=value):
                data, errors = BUNDLE.frontmatter(document(value))
                self.assertNotIn("description", data)
                self.assertTrue(errors)
        for value in ("true", "42", "it's a string"):
            with self.subTest(quoted=value):
                data, errors = BUNDLE.frontmatter(document(json.dumps(value)))
                self.assertEqual(errors, [])
                self.assertEqual(data["description"], value)

    def test_current_runtime_frontmatter_is_supported(self):
        data, errors = BUNDLE.frontmatter((RUNTIME / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(errors, [])
        self.assertEqual(data["name"], RUNTIME.name)
        self.assertIsInstance(data["description"], str)
        self.assertIsInstance(data["compatibility"], str)

    def test_actual_bundle_cli_rejects_bad_description_and_accepts_quoted_equivalent(self):
        with tempfile.TemporaryDirectory(prefix="skill-frontmatter-") as temporary:
            copy = Path(temporary) / RUNTIME.name
            shutil.copytree(RUNTIME, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            skill = copy / "SKILL.md"
            original = skill.read_text(encoding="utf-8")
            def check(description):
                text = "\n".join("description: " + description if line.startswith("description: ") else line
                                 for line in original.splitlines()) + "\n"
                skill.write_bytes(text.encode("utf-8"))
                return subprocess.run([sys.executable, "-B", str(VALIDATOR), str(copy)], cwd=str(ROOT),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      encoding="utf-8", check=False)
            bad = check(BAD_DESCRIPTION)
            self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
            self.assertIn("invalid frontmatter string description", bad.stderr)
            quoted = check(json.dumps(BAD_DESCRIPTION))
            self.assertEqual(quoted.returncode, 0, quoted.stdout + quoted.stderr)
            plain = check(BAD_DESCRIPTION.replace("hosts: ", "hosts; "))
            self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)


if __name__ == "__main__":
    unittest.main()
