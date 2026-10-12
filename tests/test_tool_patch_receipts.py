"""Observed write receipts support references without replacing task validation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evolution.tool_broker import RepoBroker, TOOLS, canonical, git_command, sha, tool_definitions
from evolution.tool_codex import _quality

ROOT = Path(__file__).resolve().parents[1]


class ToolPatchReceiptTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "eval-workspaces"
        directory.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="patch-receipts-", dir=directory)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository"
        self.root.mkdir()
        self.git = Path(shutil.which("git"))
        self.initial = {"a.txt": "old a\r\n", "nested/b.txt": "old b\n", "STATE.json": "{}\n", "clue.txt": "protected clue\n"}
        self.expected = {"a.txt": "new a 漢字\r\n", "nested/b.txt": "new b\n"}
        self.task = {"id": "public-patch-receipt", "family": "public-recovery", "prompt": "Repair sources and cite their current hashes.",
                     "initial_files": self.initial, "writable_files": ["a.txt", "nested/b.txt", "STATE.json", "created.txt"],
                     # Text checks use universal-newline reads; receipts bind raw bytes.
                     "checks": [{"path": name, "kind": "text", "expected": text.replace("\r\n", "\n")} for name, text in self.expected.items()]
                     + [{"path": "created.txt", "kind": "text", "expected": "created\n"},
                        {"path": "STATE.json", "kind": "file_hash_manifest", "expected": {"sources": list(self.expected), "claims": {"recovered": True}}}],
                     "required_read_paths": list(self.initial),
                     "required_tools": ["repo_read", "repo_patch", "repo_validate", "repo_status"]}
        for name, text in self.initial.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        initialized = git_command(self.git, self.root, "init", "--template=", "--quiet")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.broker = RepoBroker(self.root, self.task, self.git)

    def operation(self, name, text):
        path = self.root / name
        return {"path": name, "old_sha256": sha(path.read_bytes()) if path.exists() else None, "new_text": text}

    def apply(self, changes):
        return self.broker.call("repo_patch", {"operations": [self.operation(name, text) for name, text in changes.items()]})

    def quality(self, validation):
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "upg_repo",
                   "tool": row["tool"], "arguments": row["arguments"]}} for row in self.broker.events]
        final = json.dumps({"summary": "Sources and current references repaired.", "validation": validation,
                            "helper_gap": "project_tool unavailable in bounded broker"})
        return _quality(self.broker, self.broker.events, events, final, self.broker.max_calls)

    def test_single_receipt_hashes_actual_utf8_crlf_bytes_and_preserves_old_fields(self):
        result = self.apply({"a.txt": self.expected["a.txt"]})
        raw = (self.root / "a.txt").read_bytes()
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed"], ["a.txt"])
        self.assertEqual(result["files"], {"a.txt": {"sha256": sha(raw), "byte_size": len(raw)}})
        self.assertNotEqual(len(raw), len(self.expected["a.txt"]))
        self.assertNotIn("text", result["files"]["a.txt"])
        self.assertNotIn("checks", result)

    def test_batch_and_created_files_each_have_observed_metadata(self):
        changes = {"nested/b.txt": self.expected["nested/b.txt"], "created.txt": "created\n", "a.txt": self.expected["a.txt"]}
        result = self.apply(changes)
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed"], sorted(changes))
        self.assertEqual(list(result["files"]), sorted(changes))
        for name in changes:
            raw = (self.root / name).read_bytes()
            self.assertEqual(result["files"][name], {"sha256": sha(raw), "byte_size": len(raw)})

    def test_receipt_supports_current_hash_manifest_without_source_reread(self):
        initial_read = self.broker.call("repo_read", {"paths": list(self.initial)})
        self.assertTrue(initial_read["ok"])
        result = self.apply(dict(self.expected, **{"created.txt": "created\n"}))
        manifest = {"source_sha256": {name: result["files"][name]["sha256"] for name in self.expected}, "claims": {"recovered": True}}
        saved = self.broker.call("repo_patch", {"operations": [{"path": "STATE.json", "old_sha256": initial_read["files"]["STATE.json"]["sha256"], "new_text": json.dumps(manifest)}]})
        self.assertTrue(saved["ok"])
        self.assertEqual(self.broker.read_evidence_failures(self.broker.events), [])
        self.assertFalse(self.quality("failed")["required_tools_ok"])
        validation = self.broker.call("repo_validate", {})
        self.assertTrue(validation["ok"], validation)
        self.assertTrue(self.broker.call("repo_status", {})["ok"])
        self.assertEqual(sum(event["tool"] == "repo_read" for event in self.broker.events), 1)
        self.assertTrue(self.quality("passed")["hard_pass"])
        # Even a valid manifest-only edit invalidates prior validate/status evidence.
        self.assertTrue(self.apply({"STATE.json": json.dumps(manifest) + "\n"})["ok"])
        self.assertTrue(self.broker.validate()["ok"])
        self.assertFalse(self.quality("failed")["required_tools_ok"])
        self.assertFalse(self.quality("failed")["hard_pass"])
        self.assertTrue(self.broker.call("repo_validate", {})["ok"])
        self.assertTrue(self.broker.call("repo_status", {})["ok"])
        self.assertTrue(self.quality("passed")["hard_pass"])

    def test_readback_mismatch_fails_without_planned_hash_and_preserves_write_fact(self):
        replace = os.replace
        def corrupt(source, target):
            replace(source, target)
            Path(target).write_bytes(b"unexpected disk bytes\n")
        with patch("evolution.tool_broker.os.replace", side_effect=corrupt):
            result = self.apply({"a.txt": self.expected["a.txt"]})
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"], ["a.txt"])
        self.assertEqual(result["files"], {})
        self.assertEqual(result["write_state"], "partial-or-unverified")
        self.assertIn("readback", result["error"])
        self.assertEqual((self.root / "a.txt").read_bytes(), b"unexpected disk bytes\n")
        event = self.broker.events[-1]
        self.assertEqual(event["result_sha256"], sha(canonical(result)))
        self.assertEqual(event["state_sha256"], sha(canonical(self.broker.snapshot())))

    def test_failed_later_write_retains_partial_batch_without_atomic_claim(self):
        replace = os.replace
        def fail_second(source, target):
            if Path(target).name == "b.txt": raise OSError("simulated second replacement failure")
            return replace(source, target)
        with patch("evolution.tool_broker.os.replace", side_effect=fail_second):
            result = self.apply(self.expected)
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"], ["a.txt"])
        self.assertEqual(result["files"], {})
        self.assertEqual((self.root / "a.txt").read_bytes(), self.expected["a.txt"].encode("utf-8"))
        self.assertEqual((self.root / "nested/b.txt").read_bytes(), self.initial["nested/b.txt"].encode("utf-8"))
        self.assertEqual(result["write_state"], "partial-or-unverified")
        self.assertFalse(list(self.root.rglob("*.tmp")))

    def test_missing_after_replace_is_unverified_not_a_success_receipt(self):
        replace = os.replace
        def remove(source, target):
            replace(source, target)
            Path(target).unlink()
        with patch("evolution.tool_broker.os.replace", side_effect=remove):
            result = self.apply({"a.txt": self.expected["a.txt"]})
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"], ["a.txt"])
        self.assertEqual(result["files"], {})
        self.assertIsNone(self.broker.events[-1]["state_sha256"])

    def test_readback_still_rejects_links_reparse_and_outside_scope(self):
        target = self.root / "a.txt"
        original = Path.lstat
        for override in ({"st_nlink": 2}, {"st_file_attributes": 1024}, {"st_mode": stat.S_IFLNK | 0o777}):
            def lstat(path, *args, **kwargs):
                value = original(path, *args, **kwargs)
                if path == target:
                    values = {key: getattr(value, key) for key in ("st_mode", "st_nlink", "st_size", "st_dev", "st_ino", "st_mtime_ns")}
                    values["st_file_attributes"] = getattr(value, "st_file_attributes", 0)
                    return SimpleNamespace(**dict(values, **override))
                return value
            with self.subTest(override=override), patch.object(Path, "lstat", lstat), self.assertRaisesRegex(ValueError, "hardlinked|symlink/reparse"):
                self.broker._patch_readback("a.txt", self.initial["a.txt"].encode())
        with self.assertRaises(ValueError): self.broker._patch_readback("../outside", b"body")

    def test_hash_receipt_does_not_satisfy_required_initial_reads(self):
        self.assertTrue(self.apply(self.expected)["ok"])
        self.assertTrue(self.broker.call("repo_read", {"paths": list(self.initial)})["ok"])
        self.assertTrue(self.broker.read_evidence_failures(self.broker.events))

    def test_old_hash_and_protected_scope_guards_are_unchanged(self):
        before = self.broker.snapshot()
        for operation in ({"path": "a.txt", "old_sha256": "0" * 64, "new_text": "bad"},
                          {"path": "clue.txt", "old_sha256": sha(self.initial["clue.txt"].encode()), "new_text": "bad"},
                          {"path": "../outside", "old_sha256": None, "new_text": "bad"}):
            self.assertFalse(self.broker.call("repo_patch", {"operations": [operation]})["ok"])
            self.assertEqual(self.broker.snapshot(), before)

    def test_no_new_tool_or_validation_claim_is_added(self):
        self.assertEqual(tuple(item["name"] for item in tool_definitions()), TOOLS)
        result = self.apply(self.expected)
        self.assertEqual(set(result), {"ok", "changed", "files"})
        self.assertFalse(self.broker.validate()["ok"])
        self.assertNotIn("repo_validate", [row["tool"] for row in self.broker.events])


if __name__ == "__main__":
    unittest.main()
