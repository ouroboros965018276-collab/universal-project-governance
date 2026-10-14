"""本地导航目标、锚点和路径边界回归；不执行链接到的应用代码。"""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.validate_navigation import validate


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_root = ROOT / "eval-workspaces/tmp-navigation-tests"
        self.temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="navigation-", dir=self.temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def check(self, text):
        self.write("entry.md", text)
        return validate(self.root, ["entry.md"])

    def test_current_entry_links(self):
        self.assertEqual(validate(ROOT), [])

    def test_nested_document_resolves_from_its_own_directory(self):
        self.write("src/core.py", "raise RuntimeError('must not execute')\n")
        self.write("docs/entry.md", "[源码](../src/core.py)\n")
        self.assertEqual(validate(self.root, ["docs/entry.md"]), [])

    def test_deleted_target_fails_with_source_line(self):
        self.assertIn("entry.md:2", self.check("# 入口\n[失效](missing.py)\n")[0])

    def test_renamed_heading_fails(self):
        self.write("guide.md", "# 现有标题\n")
        self.assertIn("标题锚点不存在", self.check("[过期](guide.md#旧标题)")[0])

    def test_unicode_duplicate_and_inline_code_headings(self):
        self.write("guide.md", "# 中文 API `name`\n# 中文 API `name`\n")
        self.assertEqual(self.check("[一](guide.md#中文-api-name) [二](guide.md#中文-api-name-1)"), [])

    def test_fenced_and_inline_examples_are_ignored(self):
        self.assertEqual(self.check("```md\n[示例](missing.md)\n```\n`[示例](missing.md)`\n"), [])

    def test_code_formatted_link_label_still_checks_target(self):
        self.assertTrue(self.check("[`missing.py`](missing.py)"))

    def test_fake_fenced_heading_is_not_an_anchor(self):
        self.write("guide.md", "```md\n# 假标题\n```\n")
        self.assertTrue(self.check("[失效](guide.md#假标题)"))

    def test_reference_and_parenthesized_space_targets(self):
        self.write("a(b).md", "# 目标\n")
        self.write("有 空格.md", "# 目标\n")
        self.assertEqual(self.check("[一](a(b).md#目标) [二](<有 空格.md#目标>) [三][ref]\n\n[ref]: a(b).md#目标\n"), [])

    def test_directory_link_is_allowed_but_directory_anchor_is_not(self):
        (self.root / "docs").mkdir()
        self.assertEqual(self.check("[目录](docs/)"), [])
        self.assertTrue(self.check("[目录](docs/#标题)"))

    def test_outside_absolute_and_encoded_paths_fail(self):
        for destination in ("../outside.md", "%2e%2e/outside.md", "/absolute.md", "C:/absolute.md", "a%5cb.md", "file:///tmp/file.md", "javascript:alert(1)", ".GIT/config"):
            with self.subTest(destination=destination):
                error = self.check("[不安全](%s)" % destination)[0]
                self.assertTrue("路径不安全" in error or "路径超出项目范围" in error, error)

    def test_symlink_outside_root_fails_before_target_read(self):
        with tempfile.TemporaryDirectory(prefix="outside-", dir=self.temporary_root) as outside:
            target = Path(outside) / "outside.md"
            target.write_text("# 外部\n", encoding="utf-8")
            try:
                (self.root / "link.md").symlink_to(target)
            except OSError as error:
                self.skipTest("当前入口不能创建符号链接：%s" % error)
            self.assertIn("路径超出项目范围", self.check("[不安全](link.md#外部)")[0])

    def test_external_links_are_not_fetched(self):
        self.assertEqual(self.check("[网页](https://example.invalid/no-page) [邮件](mailto:example@example.invalid)"), [])


if __name__ == "__main__":
    unittest.main()
