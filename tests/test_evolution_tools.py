"""Offline adversarial checks for the bounded genuine-tool CLI profile."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid

from evolution.tool_broker import RepoBroker, canonical, normalize, relative, sha, validate_task
from evolution.tool_codex import ToolCodex, ToolCallError, ToolCallPending, _quality, _trace_failures, _usage

ROOT = Path(__file__).resolve().parents[1]


def task():
    return {"id": "offline-public-regression", "family": "public-text-test", "prompt": "Repair the registered public fixture.",
            "initial_files": {"README.md": "old\n", "tests/contract.txt": "immutable test contract\n"},
            "writable_files": ["README.md"],
            "checks": [{"path": "README.md", "kind": "text", "expected": "fixed\n"}],
            "required_tools": ["repo_read", "repo_patch", "repo_validate", "repo_status"]}


class BoundedToolsTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "eval-workspaces"
        temporary_root.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="rc19-tools-unit-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git = Path(shutil.which("git"))
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.task = task()
        for name, text in self.task["initial_files"].items():
            path = self.workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
        self.broker = RepoBroker(self.workspace, self.task, self.git)

    def test_batch_read_and_hash_conditioned_patch(self):
        files = self.broker.call("repo_read", {"paths": list(self.task["initial_files"])})["files"]
        self.assertEqual(len(files), 2)
        self.assertFalse(self.broker.call("repo_patch", {"operations": [{"path": "README.md", "old_sha256": "wrong", "new_text": "fixed\n"}]})["ok"])
        result = self.broker.call("repo_patch", {"operations": [{"path": "README.md", "old_sha256": files["README.md"]["sha256"], "new_text": "fixed\n"}]})
        self.assertTrue(result["ok"])
        self.assertTrue(self.broker.call("repo_validate", {})["ok"])

    def test_empty_implementation_deleted_tests_and_noop_fail(self):
        self.assertFalse(self.broker.validate()["ok"])
        (self.workspace / "README.md").write_bytes(b"")
        self.assertFalse(self.broker.validate()["ok"])
        (self.workspace / "README.md").write_bytes(b"fixed\n")
        (self.workspace / "tests/contract.txt").unlink()
        self.assertFalse(self.broker.validate()["ok"])

    def test_protected_file_and_outside_paths_denied(self):
        for name in ("../secret", "C:/secret", "data/../../secret", ".git/config", "README.md.", "NUL.txt", "folder\\file"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative(name)
        for name in ("tests/contract.txt", "unknown.txt"):
            self.assertFalse(self.broker.call("repo_patch", {"operations": [{"path": name, "old_sha256": None, "new_text": "bad"}]})["ok"])
        (self.workspace / "tests/contract.txt").write_text("tampered", encoding="utf-8")
        self.assertIn("protected-file-changed:tests/contract.txt", self.broker.validate()["failures"])

    def test_symlink_hardlink_and_reparse_rejected(self):
        original = self.workspace / "README.md"
        outside = self.root / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        original.unlink()
        try:
            original.symlink_to(outside)
        except OSError:
            # Windows symlink creation may be unavailable without developer mode.
            with mock.patch("evolution.tool_broker.Path.lstat") as fake:
                fake.return_value = mock.Mock(st_mode=0o100644, st_file_attributes=1024)
                with self.assertRaisesRegex(ValueError, "reparse"):
                    self.broker.path("README.md")
        else:
            with self.assertRaisesRegex(ValueError, "symlink|reparse"):
                self.broker.path("README.md")
            original.unlink()
        if not original.exists():
            try:
                os.link(outside, original)
            except OSError:
                original.write_bytes(b"old\n")
                original_stat = Path.stat
                def linked_stat(path, *args, **kwargs):
                    info = original_stat(path, *args, **kwargs)
                    if path == original:
                        fields = list(info)
                        fields[3] = 2
                        return os.stat_result(fields)
                    return info
                with mock.patch("evolution.tool_broker.Path.stat", linked_stat):
                    with self.assertRaisesRegex(ValueError, "hardlinked"):
                        self.broker.snapshot()
            else:
                with self.assertRaisesRegex(ValueError, "hardlinked"):
                    self.broker.snapshot()

    def test_static_parsers_never_execute_source(self):
        marker = self.root / "must-not-exist"
        source = "import pathlib\npathlib.Path(" + repr(str(marker)) + ").write_text('executed')\nwhile True: pass\n"
        self.assertIsInstance(normalize("python_ast", source), str)
        self.assertFalse(marker.exists())
        with self.assertRaises(ValueError):
            normalize("json", '{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            normalize("json", '{"a":NaN}')
        self.assertNotEqual(canonical(normalize("json", '{"a":true}')), canonical({"a": 1}))

    def test_invalid_or_unscored_task_fails_closed(self):
        for change in ({"checks": []}, {"checks": [{"path": "README.md", "kind": "unknown", "expected": "fixed"}]},
                       {"writable_files": ["README.md", "unscored.txt"]}, {"required_tools": ["repo_read"]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_task(dict(self.task, **change))

    def test_call_budget_denies_extra_execution(self):
        limited = RepoBroker(self.workspace, self.task, self.git, max_calls=4)
        for unused in range(4):
            self.assertTrue(limited.call("repo_read", {"paths": ["README.md"]})["ok"])
        self.assertFalse(limited.call("repo_read", {"paths": ["README.md"]})["ok"])
        for unused in range(1000):
            limited.call("repo_read", {"paths": ["README.md"]})
        self.assertEqual(len(limited.events), 5)

    def test_real_stdio_protocol_and_bounded_excess_stream(self):
        spec = {"workspace": str(self.workspace), "task": self.task, "git_binary": str(self.git),
                "audit_file": str(self.root / "stdio.jsonl"), "max_tool_calls": 4, "deadline": 99999999999}
        spec_file = self.root / "spec.json"
        spec_file.write_bytes(canonical(spec))
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}]
        requests += [{"jsonrpc": "2.0", "id": number, "method": "tools/call", "params": {
            "name": "repo_read", "arguments": {"paths": ["README.md"]}}} for number in range(3, 103)]
        result = subprocess.run([sys.executable, "-B", str(ROOT / "evolution/tool_broker.py"), str(spec_file)],
                                input=b"\n".join(canonical(row) for row in requests) + b"\n",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "upg-bounded-repository")
        self.assertEqual(len(responses[1]["result"]["tools"]), 5)
        self.assertEqual(len(responses), 7)
        self.assertTrue(responses[-1]["result"]["isError"])
        self.assertEqual(len((self.root / "stdio.jsonl").read_bytes().splitlines()), 5)

    def test_stdio_rejects_oversize_input_without_full_line_allocation(self):
        spec = {"workspace": str(self.workspace), "task": self.task, "git_binary": str(self.git),
                "audit_file": str(self.root / "oversize.jsonl"), "max_tool_calls": 4, "deadline": 99999999999}
        spec_file = self.root / "oversize-spec.json"
        spec_file.write_bytes(canonical(spec))
        result = subprocess.run([sys.executable, "-B", str(ROOT / "evolution/tool_broker.py"), str(spec_file)],
                                input=b"x" * (1048576 + 100) + b"\n", stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=10, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"MCP message exceeds size limit", result.stderr)
        self.assertFalse((self.root / "oversize.jsonl").exists())

    def test_cli_arguments_bind_journal_and_parallel_completion_order(self):
        self.broker.call("repo_read", {"paths": ["README.md"]})
        self.broker.call("repo_search", {"needle": "old"})
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "upg_repo",
                   "tool": row["tool"], "arguments": row["arguments"]}} for row in reversed(self.broker.events)]
        self.assertEqual(_trace_failures(events, self.broker.events, 32), [])
        events[0]["item"]["arguments"] = {"needle": "tampered"}
        self.assertIn("cli-broker-call-journal-mismatch", _trace_failures(events, self.broker.events, 32))

    def test_stale_suite_or_claim_cannot_pass(self):
        self.broker.call("repo_read", {"paths": ["README.md"]})
        self.broker.call("repo_patch", {"operations": [{"path": "README.md", "old_sha256": sha(b"old\n"), "new_text": "fixed\n"}]})
        self.broker.call("repo_validate", {})
        # Simulate real status evidence without spawning for this isolated unit.
        with mock.patch("evolution.tool_broker.git_command", return_value=subprocess.CompletedProcess([], 0, b"?? README.md\n", b"")):
            self.broker.call("repo_status", {})
        events = [{"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "upg_repo", "tool": row["tool"], "arguments": row["arguments"]}}
                  for row in self.broker.events]
        final = json.dumps({"summary": "Static contract repaired.", "validation": "passed", "helper_gap": "project_tool unavailable in bounded broker"})
        self.assertEqual(_quality(self.broker, self.broker.events, events, final, 32)["task_success"], 1)
        self.assertEqual(_quality(self.broker, self.broker.events, events, final.replace('"passed"', '"failed"'), 32)["task_success"], 0)
        (self.workspace / "README.md").write_text("broken again", encoding="utf-8")
        self.assertEqual(_quality(self.broker, self.broker.events, events, final, 32)["task_success"], 0)


class ToolAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rc19-adapter-unit-", dir=ROOT / "eval-workspaces")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = self.root / "fake-codex.exe"
        self.binary.write_bytes(b"registered offline mock CLI")
        self.config = {"binary": str(self.binary), "git_binary": shutil.which("git"), "model": "explicit-mock-model",
                       "effort": "low", "artifact_root": str(self.root / "calls-root"), "timeout_seconds": 180,
                       "cli_version": "mock-only", "max_tool_calls": 32}
        self.adapter = ToolCodex(self.config)
        self.bindings = {key: "explicit-" + key for key in ("campaign_id", "sample_id", "protocol_sha256",
                         "source_sha256", "runtime_sha256", "candidate_sha256")}
        self.bindings["capability"] = self.adapter.binding()
        self.actual_run = subprocess.run
        self.cli_calls = 0

    def fake_run(self, arguments, **kwargs):
        if arguments[0] != str(self.binary):
            return self.actual_run(arguments, **kwargs)
        self.cli_calls += 1
        workspace = Path(arguments[arguments.index("--cd") + 1])
        directory = workspace.parent
        spec = json.loads((directory / "broker.spec.json").read_text(encoding="utf-8"))
        broker = RepoBroker(workspace, spec["task"], spec["git_binary"], audit_file=spec["audit_file"])
        read = broker.call("repo_read", {"paths": list(spec["task"]["initial_files"])})
        broker.call("repo_patch", {"operations": [{"path": "README.md", "old_sha256": read["files"]["README.md"]["sha256"], "new_text": "fixed\n"}]})
        broker.call("repo_validate", {})
        broker.call("repo_status", {})
        events = [{"type": "thread.started", "thread_id": str(uuid.uuid4())}]
        events.extend({"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "upg_repo", "tool": row["tool"], "arguments": row["arguments"]}}
                      for row in broker.events)
        events.append({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps({
            "summary": "Static contract repaired.", "validation": "passed", "helper_gap": "project_tool unavailable in bounded broker"})}})
        events.append({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 10,
                       "cached_input_tokens": 20, "reasoning_output_tokens": 2}})
        return subprocess.CompletedProcess(arguments, 0, b"\n".join(canonical(event) for event in events), b"")

    def test_configuration_disables_unrelated_tools_and_requires_broker(self):
        arguments = self.adapter._arguments(self.root, self.root / "spec.json")
        self.assertIn("--ignore-user-config", arguments)
        self.assertEqual(arguments[arguments.index("--sandbox") + 1], "read-only")
        for config in ("features.shell_tool=false", "features.plugins=false", "features.hooks=false",
                       "features.apps=false", "features.multi_agent=false", 'web_search="disabled"',
                       "mcp_servers.upg_repo.required=true"):
            self.assertIn(config, arguments)

    def test_actual_tools_usage_receipt_and_same_sample_reuse(self):
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run):
            result = self.adapter.run(task(), prompt="fixed public fixture prompt", bindings=self.bindings)
            repeated = self.adapter.run(task(), prompt="fixed public fixture prompt", bindings=self.bindings)
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(result["quality"]["task_success"], 1)
        self.assertEqual(result["usage"]["total_tokens"], 110)
        self.assertEqual(result["usage"]["cached_input_tokens"], 20)
        self.assertEqual(len(result["tool_events"]), 4)
        self.assertTrue(repeated["receipt"]["replayed_from_local_receipt"])
        self.assertIsNone(result["receipt"]["provider_request_id"])
        self.assertIsNone(result["receipt"]["model_observed"])
        self.assertGreaterEqual(result["wall_seconds"], result["timing"]["cli_seconds"])
        self.assertFalse((self.root / "calls-root/UNKNOWN_CALL.json").exists())

    def test_distinct_sample_and_task_dispatch_fresh_turns(self):
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run):
            first = self.adapter.run(task(), prompt="fixed prompt", bindings=self.bindings)
            second = self.adapter.run(dict(task(), id="another-public-instance"), prompt="fixed prompt",
                                      bindings=dict(self.bindings, sample_id="new-independent-sample"))
        self.assertEqual(self.cli_calls, 2)
        self.assertNotEqual(first["receipt"]["cli_thread_id"], second["receipt"]["cli_thread_id"])

    def test_unknown_usage_and_timeout_fence_other_samples(self):
        for mode in ("missing", "duplicate", "timeout"):
            with self.subTest(mode=mode):
                config = dict(self.config, artifact_root=str(self.root / mode))
                adapter = ToolCodex(config)
                bindings = dict(self.bindings, capability=adapter.binding())
                def broken(arguments, **kwargs):
                    if arguments[0] != str(self.binary):
                        return self.actual_run(arguments, **kwargs)
                    if mode == "timeout":
                        raise subprocess.TimeoutExpired(arguments, 180, output=b"partial", stderr=b"timeout")
                    events = [{"type": "thread.started", "thread_id": "mock-thread"}]
                    if mode == "duplicate":
                        events += [{"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}] * 2
                    return subprocess.CompletedProcess(arguments, 0, b"\n".join(canonical(e) for e in events), b"")
                with mock.patch("evolution.tool_codex.subprocess.run", side_effect=broken):
                    with self.assertRaises(ToolCallError):
                        adapter.run(task(), prompt="public fixture", bindings=bindings)
                    with self.assertRaises(ToolCallPending):
                        adapter.run(task(), prompt="other fixture", bindings=dict(bindings, sample_id="other"))
                self.assertTrue((Path(config["artifact_root"]) / "UNKNOWN_CALL.json").exists())

    def test_usage_rejects_negative_bool_and_inconsistent_cached_tokens(self):
        for raw in ({"input_tokens": -1, "output_tokens": 1}, {"input_tokens": True, "output_tokens": 1},
                    {"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 2}):
            self.assertIsNone(_usage([{"type": "turn.completed", "usage": raw}]))

    def test_configuration_drift_rejected_before_model_dispatch(self):
        self.binary.write_bytes(b"changed registered binary")
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run):
            with self.assertRaises(ToolCallPending) as captured:
                self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
        self.assertEqual(self.cli_calls, 0)
        self.assertEqual(captured.exception.usage["total_tokens"], 0)
        self.assertFalse(captured.exception.provider_receipt["model_invoked"])
        pending = next((self.root / "calls-root/calls").glob("*/pending.json"))
        self.assertFalse(json.loads(pending.read_text(encoding="utf-8"))["model_invoked"])

    def test_known_usage_survives_grade_and_unknown_receipt_io_failure(self):
        from evolution import tool_codex
        actual_atomic = tool_codex._atomic
        def denied(path, value):
            if Path(path).name == "final-files.json":
                raise PermissionError("simulated grading evidence replacement denial")
            return actual_atomic(path, value)
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run), \
                mock.patch("evolution.tool_codex._atomic", side_effect=denied), \
                mock.patch.object(self.adapter, "_unknown", side_effect=PermissionError("simulated fence failure")):
            with self.assertRaises(ToolCallError) as captured:
                self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
        self.assertEqual(captured.exception.usage["total_tokens"], 110)
        self.assertIn("fence_persistence_error", captured.exception.provider_receipt)
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run):
            with self.assertRaises(ToolCallPending):
                self.adapter.run(task(), prompt="new sample", bindings=dict(self.bindings, sample_id="new"))
        self.assertEqual(self.cli_calls, 1)

    def test_known_usage_survives_raw_output_write_failure(self):
        original_write = Path.write_bytes
        def denied(path, data):
            if path.name == "stdout.raw":
                raise PermissionError("simulated raw output write denial")
            return original_write(path, data)
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run), \
                mock.patch("evolution.tool_codex.Path.write_bytes", denied):
            with self.assertRaises(ToolCallError) as captured:
                self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
        self.assertEqual(captured.exception.usage["total_tokens"], 110)
        self.assertEqual(captured.exception.provider_receipt["status"], "raw-evidence-persistence-failed")

    def test_known_completed_result_survives_lock_cleanup_denial(self):
        original_unlink = Path.unlink
        def denied(path, *args, **kwargs):
            if path.name == ".tool-dispatch.lock":
                raise PermissionError("simulated lock cleanup denial")
            return original_unlink(path, *args, **kwargs)
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run), \
                mock.patch("evolution.tool_codex.Path.unlink", denied):
            result = self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
        self.assertEqual(result["usage"]["total_tokens"], 110)
        self.assertEqual(result["quality"]["task_success"], 1)
        self.assertIn("dispatch_lock_cleanup_error", result["receipt"])
        with self.assertRaises(ToolCallPending):
            self.adapter.run(task(), prompt="new fixture", bindings=dict(self.bindings, sample_id="new"))
        self.assertEqual(self.cli_calls, 1)

    def test_unrelated_tool_event_fails_even_with_forged_passed_summary(self):
        def extra(arguments, **kwargs):
            result = self.fake_run(arguments, **kwargs)
            if arguments[0] == str(self.binary):
                result.stdout += b"\n" + canonical({"type": "item.completed", "item": {"type": "command_execution", "command": "bad"}})
            return result
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=extra):
            result = self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
        self.assertEqual(result["quality"]["task_success"], 0)
        self.assertFalse(result["quality"]["scope_ok"])

    def test_receipt_and_workspace_tampering_block_reuse(self):
        with mock.patch("evolution.tool_codex.subprocess.run", side_effect=self.fake_run):
            result = self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
            directory = Path(result["receipt"]["artifact_directory"])
            (directory / "workspace/README.md").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ToolCallPending):
                self.adapter.run(task(), prompt="public fixture", bindings=self.bindings)
        self.assertEqual(self.cli_calls, 1)


if __name__ == "__main__":
    unittest.main()
