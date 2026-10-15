"""Offline behavior checks for the repository-only native API helper.

All HTTP, sockets, Git/subprocess calls and key material are synthetic. Tests
use one local fixture and the public module; no historical workspace is read.
Python 3.8 runtime tests are separate: this repository helper suite skips before
importing repository engine modules on Python versions below 3.10.
"""
from __future__ import annotations

from decimal import Decimal
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
SUPPORTED = sys.version_info >= (3, 10)
if SUPPORTED:
    from evolution import provider_tools as lab
    from evolution import tool_broker
    from evolution.tool_broker import canonical, sha

SECRET = "mock-secret-never-on-disk-38195"
FINAL = {"summary": "Public mock complete", "validation": "passed",
         "helper_gap": "project_tool unavailable in bounded broker"}


def completion(index, calls=None, content=None, usage=True, **extra):
    result = {"id": "mock-response-" + str(index), "model": "mock-observed-model", "object": "chat.completion",
              "choices": [{"finish_reason": "tool_calls" if calls else "stop", "message": {
                  "role": "assistant", "content": content, "reasoning_content": "mock non-private test field", "tool_calls": calls}}]}
    if usage:
        result["usage"] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
                           "prompt_tokens_details": {"cached_tokens": 2}, "completion_tokens_details": {"reasoning_tokens": 0}}
    result.update(extra)
    return result


def call(identifier, tool, arguments):
    return {"id": identifier, "type": "function", "function": {"name": tool, "arguments": json.dumps(arguments)}}


class _ProviderFixture:
    def setUp(self):
        harmless = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        fence = patch.object(tool_broker, "git_command", return_value=harmless)
        self.git_status = fence.start()
        self.addCleanup(fence.stop)
        for name in ("Popen", "run", "check_output", "call", "check_call"):
            fence = patch.object(subprocess, name, side_effect=AssertionError("real CLI forbidden"))
            fence.start()
            self.addCleanup(fence.stop)
        for target, name in ((socket, "socket"), (socket, "create_connection"), (lab.http.client, "HTTPSConnection")):
            fence = patch.object(target, name, side_effect=AssertionError("live network forbidden"))
            fence.start()
            self.addCleanup(fence.stop)
        temporary = tempfile.TemporaryDirectory(prefix="provider-tools-mock-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.workspace = self.base / "repository"
        self.workspace.mkdir()
        self.artifacts = self.base / "evidence"
        self.task = {"id": "public-http-mock", "family": "public-http-mock", "prompt": "将target.txt改为fixed并保留契约。",
                     "initial_files": {"target.txt": "old\n", "contract.json": "{}\n"}, "writable_files": ["target.txt"],
                     "checks": [{"path": "target.txt", "kind": "text", "expected": "fixed\n"}],
                     "required_read_paths": ["target.txt", "contract.json"],
                     "required_tools": ["repo_read", "repo_patch", "repo_validate", "repo_status"]}
        for name, text in self.task["initial_files"].items():
            (self.workspace / name).write_bytes(text.encode("utf-8"))
        self.git = str(self.base / "mock-git-entry")
        self.loaded, self.before, self.after = [], [], []

    def key(self, provider):
        self.loaded.append(provider)
        return SECRET

    def reserve(self, metadata):
        self.before.append(metadata)
        return {"reservation_id": metadata["request_id"]}

    def account(self, metadata):
        self.after.append(metadata)

    def run_actor(self, **kwargs):
        kwargs.setdefault("response_json_mode", False)
        kwargs.setdefault("thinking", "disabled")
        return lab.run_actor(kwargs.pop("provider", "deepseek"), kwargs.pop("model", "mock-requested-model"), self.task,
                             self.workspace, self.artifacts, self.git, kwargs.pop("system_context", "公开合成条件"), self.key,
                             before_request=self.reserve, after_request=self.account, **kwargs)

    def positive(self, provider, payload, key, timeout):
        definitions = {item["function"]["name"]: item["function"] for item in payload["tools"]}
        self.assertEqual(set(definitions), {"repo_read", "repo_search", "repo_patch", "repo_validate", "repo_status", "repo_finish"})
        self.assertEqual(definitions["repo_finish"]["parameters"], lab.FINAL_SCHEMA)
        self.assertNotIn("response_format", payload)
        index = len(self.before)
        self.assertEqual(key, SECRET)
        self.assertTrue((self.artifacts / "requests" / ("%02d.pending.json" % index)).exists())
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("strict", json.dumps(payload["tools"]))
        self.assertEqual(payload["max_tokens" if provider == "deepseek" else "max_completion_tokens"], 4096)
        self.assertLessEqual(timeout, 180)
        if index == 1:
            response = completion(index, [call("read-1", "repo_read", {"paths": ["target.txt", "contract.json"]})])
        elif index == 2:
            previous = json.loads(payload["messages"][-1]["content"])
            response = completion(index, [call("patch-1", "repo_patch", {"operations": [{"path": "target.txt", "old_sha256": previous["files"]["target.txt"]["sha256"], "new_text": "fixed\n"}]})])
            self.assertEqual(payload["messages"][-2]["reasoning_content"], "mock non-private test field")
        elif index == 3:
            response = completion(index, [call("validate-1", "repo_validate", {}), call("status-1", "repo_status", {})])
        else:
            response = completion(index, [call("finish-" + str(index), "repo_finish", {
                "summary": "完整修复；应用测试未运行。", "validation": "passed",
                "helper_gap": "project_tool unavailable in bounded broker"})])
        response["debug"] = {"api_key": SECRET, "echo": SECRET, "authorization": "Bearer " + SECRET}
        return 200, {"x-request-id": "safe-header-" + str(index)}, canonical(response)

    def scripted(self, steps):
        def post(provider, payload, key, timeout):
            index = len(self.before)
            self.assertTrue((self.artifacts / "requests" / ("%02d.pending.json" % index)).exists())
            step = steps[index - 1]
            response = step(payload) if callable(step) else step
            return 200, {}, canonical(response)
        return post

    def feedback(self, payload):
        self.assertEqual(payload["messages"][-1]["role"], "tool")
        return json.loads(payload["messages"][-1]["content"])

    def read(self, index):
        return completion(index, [call("read-" + str(index), "repo_read", {"paths": ["target.txt", "contract.json"]})])

    def patch_from_read(self, index, text):
        def response(payload):
            current = self.feedback(payload)["files"]["target.txt"]["sha256"]
            return completion(index, [call("patch-" + str(index), "repo_patch", {"operations": [
                {"path": "target.txt", "old_sha256": current, "new_text": text}]})])
        return response

    def validate_and_status(self, index):
        return completion(index, [call("validate-" + str(index), "repo_validate", {}),
                                  call("status-" + str(index), "repo_status", {})])

    def final(self, index, **changes):
        return completion(index, [call("finish-" + str(index), "repo_finish", dict(FINAL, **changes))])

    def assert_negative_preserved(self, result, sequence, expected):
        event = result["tool_events"][sequence - 1]
        self.assertEqual(event["result"], expected)
        self.assertEqual(event["result_sha256"], sha(canonical(expected)))
        trace = result["api_tool_trace"][sequence - 1]
        self.assertEqual(trace["broker_event_sha256"], sha(canonical(event)))
        self.assertEqual(trace["result_sha256"], event["result_sha256"])
        disk = [json.loads(line) for line in (self.artifacts / "broker.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(disk[sequence - 1], event)

    def ready(self):
        return [self.read(1), self.patch_from_read(2, "fixed\n"), self.validate_and_status(3)]

    def execute(self, steps):
        with patch.object(lab, "_post", side_effect=self.scripted(steps)) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, len(steps))
        return result

    def semantic_task(self):
        (self.workspace / "target.txt").unlink()
        source = "def transform(value):\n    return value\n"
        (self.workspace / "core.py").write_bytes(source.encode("utf-8"))
        self.task.update(initial_files={"core.py": source, "contract.json": "{}\n"}, writable_files=["core.py"],
            required_read_paths=["core.py", "contract.json"], checks=[{"path": "core.py", "kind": "python_behavior", "expected": None}],
            behavior_contract={"schema_version": 1, "modules": {"core.py": {"required_functions": {
                "transform": {"params": ["value"], "kwonly": [], "defaults": {}, "kwdefaults": {}}}}},
                "protected_files": {"contract.json": sha(b"{}\n")}, "probes": [
                    {"path": "core.py", "function": "transform", "args": [5], "kwargs": {}, "expect": {"return": 10}}]})


@unittest.skipUnless(SUPPORTED, "repository API helper tests require Python 3.10+; runtime 3.8 has separate tests")
class ProviderToolsTests(_ProviderFixture, unittest.TestCase):
    def test_native_api_broker_chain_and_budget_receipts_pass(self):
        with patch.object(lab, "_post", side_effect=self.positive) as post:
            result = self.run_actor()
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assertEqual(result["adapter"], lab.ADAPTER)
        self.assertEqual(post.call_count, 4)
        self.assertEqual(result["usage"]["total_tokens"], 60)
        self.assertEqual(len(result["api_tool_trace"]), 4)
        self.assertEqual(result["final_state_snapshot"]["target.txt"], sha(b"fixed\n"))
        self.assertTrue(all(row["dispatched"] and row["receipt_sha256"] for row in self.after))
        self.assertTrue(all(row["input_utf8_bytes"] > 0 and row["output_cap"] == 4096 for row in self.before))
        self.assertFalse(list(self.artifacts.rglob("*.pending.json")))
        self.assertNotIn("item.completed", json.dumps(result))
        for path in self.artifacts.rglob("*"):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes(), path)
        self.assertNotIn(SECRET, json.dumps(self.before + self.after + [result]))

    def test_mimo_uses_official_completion_limit_and_same_native_contract(self):
        with patch.object(lab, "_post", side_effect=self.positive):
            result = self.run_actor(provider="mimo")
        self.assertTrue(result["quality"]["hard_pass"])
        self.assertEqual(self.loaded, ["mimo"])

    def test_partial_usage_stops_before_tools_and_fences_replay(self):
        response = completion(1, [call("read-1", "repo_read", {"paths": ["target.txt"]})], usage=False)
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
            result = self.run_actor()
            with self.assertRaises(lab.ActorFence):
                self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "unknown-call-blocked")
        self.assertIsNone(result["usage"])
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(result["tool_events"], [])
        self.assertTrue(self.after[0]["unknown"])
        self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
        self.assertEqual(self.loaded, ["deepseek"])

    def test_missing_message_is_unknown_before_pending_release(self):
        response = completion(1)
        del response["choices"][0]["message"]
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))):
            result = self.run_actor()
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(result["known_usage"]["total_tokens"], 15)
        self.assertTrue(self.after[0]["unknown"])
        self.assertTrue((self.artifacts / "requests/01.pending.json").exists())

    def test_redirect_is_not_followed_and_official_auth_stays_in_memory(self):
        response = Mock(status=302)
        response.read.return_value = b'{}'
        response.getheaders.return_value = [("Location", "https://attacker.invalid/")]
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(lab.http.client, "HTTPSConnection", return_value=connection) as constructor:
            result = self.run_actor(provider="mimo")
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(constructor.call_args.args[0], "api.xiaomimimo.com")
        self.assertEqual(connection.request.call_count, 1)
        self.assertEqual(connection.request.call_args.args[:2], ("POST", "/v1/chat/completions"))
        self.assertEqual(connection.request.call_args.kwargs["headers"]["api-key"], SECRET)
        self.assertTrue(result["unknown_usage"])

    def test_transport_exception_does_not_log_credentials_or_retry(self):
        with patch.object(lab, "_post", side_effect=RuntimeError("Bearer " + SECRET)) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertTrue(result["unknown_usage"])
        for path in self.artifacts.rglob("*.json"):
            self.assertNotIn(SECRET, path.read_text(encoding="utf-8"))

    def test_unregistered_path_is_denied_without_mutation(self):
        response = completion(1, [call("escape-1", "repo_read", {"paths": ["../secret.txt"]})])
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertFalse(result["quality"]["scope_ok"])
        self.assertEqual((self.workspace / "target.txt").read_text(), "old\n")
        self.assertEqual(len(result["api_tool_trace"]), 1)

    def test_schema_extra_argument_and_secret_tool_payload_are_rejected(self):
        for args in ({"paths": ["target.txt"], "extra": True}, {"paths": [SECRET]}):
            with self.subTest(arguments=args):
                self.artifacts = self.base / ("rejected-" + str(len(args)) + str(len(args["paths"][0])))
                response = completion(1, [call("invalid-1", "repo_read", args)])
                with patch.object(lab, "_post", return_value=(200, {}, canonical(response))):
                    result = self.run_actor()
                self.assertFalse(result["quality"]["hard_pass"])
                self.assertEqual(result["tool_events"], [])

    def test_escaped_credential_is_rejected_before_broker_or_file_write(self):
        escaped = "".join("\\u%04x" % ord(character) for character in SECRET)
        arguments = '{"operations":[{"path":"target.txt","old_sha256":"' + sha(b"old\n") + '","new_text":"' + escaped + '"}]}'
        self.assertNotIn(SECRET, arguments)
        response = completion(1, [{"id": "escaped-secret", "type": "function", "function": {"name": "repo_patch", "arguments": arguments}}])
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))):
            result = self.run_actor()
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertEqual(result["tool_events"], [])
        self.assertFalse((self.artifacts / "broker.jsonl").exists())
        self.assertEqual((self.workspace / "target.txt").read_bytes(), b"old\n")
        for path in self.artifacts.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(SECRET, text)
            self.assertNotIn(escaped.replace("\\", "\\\\"), text)

    def test_final_serialized_payload_guard_runs_before_every_post(self):
        original_redact = lab._redact
        def unsafe_passthrough(value, secret):
            # Simulate an upstream bug in conversation redaction; send guard
            # must still stop a credential-bearing second request.
            if isinstance(value, str) and value == "inject-credential-next-message":
                return SECRET
            return original_redact(value, secret)
        response = completion(1, [call("read-1", "repo_read", {"paths": ["target.txt", "contract.json"]})])
        response["choices"][0]["message"]["reasoning_content"] = "inject-credential-next-message"
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post, patch.object(lab, "_redact", side_effect=unsafe_passthrough):
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "preparation-failed-not-invoked")
        self.assertEqual(len(self.after), 2)
        self.assertTrue(self.after[-1]["not_invoked"])

    def test_budget_refusal_loads_no_key_and_sends_no_request(self):
        self.reserve = Mock(side_effect=ValueError("budget limit"))
        with patch.object(lab, "_post") as post:
            result = self.run_actor()
        post.assert_not_called()
        self.assertEqual(self.loaded, [])
        self.assertEqual(result["status"], "outer-budget-refused")
        self.assertEqual(result["requests"], 0)

    def test_reservation_time_exhaustion_sends_no_http_and_releases_reservation(self):
        ticks = [0.0]
        def slow_reservation(metadata):
            ticks[0] = .03
            return {"reservation_id": metadata["request_id"]}
        self.reserve = slow_reservation
        with patch.object(lab, "_post") as post, patch.object(lab.time, "perf_counter", side_effect=lambda: ticks[0]):
            result = self.run_actor(timeout_seconds=.02)
        post.assert_not_called()
        self.assertEqual(self.loaded, [])
        self.assertEqual(result["requests"], 0)
        self.assertEqual(result["status"], "wall-budget-exhausted")
        self.assertTrue(self.after[-1]["not_invoked"])

    def test_key_loader_failure_is_definitely_not_dispatched(self):
        self.key = Mock(side_effect=RuntimeError(SECRET))
        with patch.object(lab, "_post") as post:
            result = self.run_actor()
        post.assert_not_called()
        self.assertFalse(result["unknown_usage"])
        self.assertTrue(self.after[0]["not_invoked"])
        self.assertFalse(self.after[0]["dispatched"])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_fresh_takeover_requires_explicit_received_task_from_driver(self):
        (self.workspace / "target.txt").write_bytes(b"partial\n")
        self.task["initial_files"]["target.txt"] = "partial\n"
        with patch.object(lab, "_post", side_effect=self.positive):
            result = self.run_actor()
        self.assertTrue(result["quality"]["hard_pass"])
        self.assertEqual(result["input_task_sha256"], sha(canonical(self.task)))
        self.assertEqual(result["effective_task_sha256"], result["input_task_sha256"])
        self.assertEqual(result["received_state_sha256"], sha(canonical({"target.txt": sha(b"partial\n"), "contract.json": sha(b"{}\n")})))

    def test_changed_input_file_is_not_blessed_during_takeover(self):
        (self.workspace / "contract.json").write_bytes(b'{"changed":true}\n')
        with patch.object(lab, "_post") as post, self.assertRaisesRegex(ValueError, "exact input task"):
            self.run_actor()
        post.assert_not_called()
        self.assertEqual(self.loaded, [])

    def test_preexisting_writable_only_target_is_rejected_before_key_or_log(self):
        self.task["writable_files"].append("created.txt")
        self.task["checks"].append({"path": "created.txt", "kind": "text", "expected": "new target\n"})
        (self.workspace / "created.txt").write_bytes(SECRET.encode("utf-8"))
        with patch.object(lab, "_post") as post, self.assertRaisesRegex(ValueError, "exact input task"):
            self.run_actor()
        post.assert_not_called()
        self.assertEqual(self.loaded, [])
        self.assertFalse((self.artifacts / "broker.jsonl").exists())

    def test_duplicate_response_id_stops_and_preserves_both_reported_charges(self):
        def repeat(provider, payload, key, timeout):
            index = len(self.before)
            response = completion(1, [call("read-" + str(index), "repo_read", {"paths": ["target.txt", "contract.json"]})])
            return 200, {}, canonical(response)
        with patch.object(lab, "_post", side_effect=repeat) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 2)
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(result["known_usage"]["total_tokens"], 30)
        self.assertEqual(len(result["tool_events"]), 1)
        self.assertTrue(self.after[-1]["unknown"])
        self.assertTrue((self.artifacts / "requests/02.pending.json").exists())

    def test_provider_usage_overrun_is_retained_and_stops_before_tools(self):
        response = completion(1, [call("read-1", "repo_read", {"paths": ["target.txt"]})])
        response["usage"].update(completion_tokens=4097, total_tokens=4107)
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "unexpected-overrun-blocked")
        self.assertEqual(result["usage"]["output_tokens"], 4097)
        self.assertTrue(self.after[0]["unexpected_overrun"])
        self.assertEqual(result["tool_events"], [])

    def test_actor_deadline_returns_unknown_without_waiting_for_late_response(self):
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        def slow(*unused):
            entered.set()
            try:
                release.wait(2)
                return 200, {}, canonical(completion(1))
            finally:
                returned.set()
        try:
            with patch.object(lab, "_post", side_effect=slow), patch.object(lab.time, "perf_counter", return_value=0.0):
                result = self.run_actor(timeout_seconds=.04)
            self.assertTrue(entered.is_set())
            self.assertFalse(release.is_set())
        finally:
            release.set()
            self.assertTrue(returned.wait(1))
        self.assertTrue(result["unknown_usage"])
        self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
        self.assertEqual(self.after[0]["transport"], {"phase": "deadline-wait", "exception_class": None,
            "connection_attempted": None, "http_dispatch": "unknown"})

    def test_hard_request_and_tool_caps_are_not_overridable(self):
        with self.assertRaises(ValueError):
            self.run_actor(max_requests=13)
        response = completion(1, [call(str(index), "repo_status", {}) for index in range(33)])
        with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
            result = self.run_actor(max_requests=1)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["tool_events"], [])
        self.assertFalse(result["quality"]["hard_pass"])

    def test_initial_negative_validate_is_feedback_then_complete_repair_passes(self):
        failed = {"ok": False, "suite": "registered-static-contracts-v1", "checks_passed": 0,
                  "checks_total": 1, "failures": ["contract-failed:target.txt:ValueError"]}
        def after_negative(payload):
            self.assertEqual(self.feedback(payload), failed)
            return self.read(2)
        steps = [completion(1, [call("initial-validate", "repo_validate", {})]), after_negative,
                 self.patch_from_read(3, "fixed\n"), self.validate_and_status(4), self.final(5)]
        with patch.object(lab, "_post", side_effect=self.scripted(steps)) as post:
            result = self.run_actor()
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assertEqual(post.call_count, 5)
        self.assertEqual(len(result["tool_events"]), 5)
        self.assert_negative_preserved(result, 1, failed)
        self.assertFalse(result["quality"]["failures"])

    def test_negative_validate_after_edit_allows_another_fresh_repair(self):
        def after_negative(payload):
            feedback = self.feedback(payload)
            self.assertIs(feedback["ok"], False)
            self.assertEqual(feedback["failures"], ["contract-failed:target.txt:ValueError"])
            return self.read(4)
        steps = [self.read(1), self.patch_from_read(2, "partially-fixed\n"),
                 completion(3, [call("intermediate-validate", "repo_validate", {})]), after_negative,
                 self.patch_from_read(5, "fixed\n"), self.validate_and_status(6), self.final(7)]
        with patch.object(lab, "_post", side_effect=self.scripted(steps)):
            result = self.run_actor()
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assertEqual(result["requests"], 7)
        self.assertEqual(result["tool_events"][2]["state_sha256"],
                         sha(canonical({"contract.json": sha(b"{}\n"), "target.txt": sha(b"partially-fixed\n")})))
        self.assert_negative_preserved(result, 3, result["tool_events"][2]["result"])

    def test_wrong_patch_hash_is_returned_then_fresh_read_and_correct_patch_pass(self):
        failed = {"ok": False, "error": "ValueError: patch precondition hash mismatch"}
        wrong = {"operations": [{"path": "target.txt", "old_sha256": "0" * 64, "new_text": "fixed\n"}]}
        def after_stale(payload):
            self.assertEqual(self.feedback(payload), failed)
            self.assertEqual((self.workspace / "target.txt").read_bytes(), b"old\n")
            return self.read(3)
        steps = [self.read(1), completion(2, [call("stale-patch", "repo_patch", wrong)]), after_stale,
                 self.patch_from_read(4, "fixed\n"), self.validate_and_status(5), self.final(6)]
        with patch.object(lab, "_post", side_effect=self.scripted(steps)):
            result = self.run_actor()
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assert_negative_preserved(result, 2, failed)
        self.assertEqual(result["requests"], 6)

    def test_protected_patch_is_still_terminal(self):
        operation = {"path": "contract.json", "old_sha256": sha(b"{}\n"), "new_text": "changed\n"}
        with patch.object(lab, "_post", return_value=(200, {}, canonical(completion(1, [
                call("protected-patch", "repo_patch", {"operations": [operation]})])))) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "tool-contract-failed")
        self.assertIn("protected", result["tool_events"][0]["result"]["error"])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertEqual((self.workspace / "contract.json").read_bytes(), b"{}\n")

    def test_stale_hash_cannot_mask_a_later_protected_or_duplicate_operation(self):
        stale = {"path": "target.txt", "old_sha256": "0" * 64, "new_text": "fixed\n"}
        for position, later in enumerate((dict(stale, path="contract.json"), stale)):
            with self.subTest(later_path=later["path"]):
                self.artifacts = self.base / ("masked-invalid-" + str(position))
                response = completion(1, [call("masked-patch", "repo_patch", {"operations": [stale, later]})])
                with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
                    result = self.run_actor()
                self.assertEqual(post.call_count, 1)
                self.assertEqual(result["status"], "tool-contract-failed")
                self.assertFalse(result["quality"]["hard_pass"])

    def test_validate_protected_failure_is_still_terminal(self):
        def external_protected_drift(provider, payload, key, timeout):
            (self.workspace / "contract.json").write_bytes(b'{"external":true}\n')
            return 200, {}, canonical(completion(1, [call("validate-protected", "repo_validate", {})]))
        with patch.object(lab, "_post", side_effect=external_protected_drift) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "tool-contract-failed")
        self.assertIn("protected-file-changed:contract.json", result["tool_events"][0]["result"]["failures"])
        self.assertFalse(result["quality"]["hard_pass"])

    def test_scope_failure_during_validate_remains_unknown_and_terminal(self):
        def external_scope_drift(provider, payload, key, timeout):
            (self.workspace / "unregistered.txt").write_bytes(b"external drift\n")
            return 200, {}, canonical(completion(1, [call("validate-scope", "repo_validate", {})]))
        with patch.object(lab, "_post", side_effect=external_scope_drift) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 1)
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(result["status"], "unknown-workspace-state-blocked")
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertTrue((self.artifacts / "actor.pending.json").exists())

    def test_only_the_exact_registered_validation_structure_is_recoverable(self):
        valid = {"ok": False, "suite": "registered-static-contracts-v1", "checks_passed": 0,
                 "checks_total": 1, "failures": ["contract-failed:target.txt:ValueError"]}
        event = {"state_sha256": "known-state"}
        self.assertTrue(lab._recoverable_tool_feedback("repo_validate", {}, valid, event, self.task))
        invalid = [dict(valid, checks_passed=False), dict(valid, checks_total=2), dict(valid, suite="unknown"),
                   dict(valid, failures=[]), dict(valid, failures=["scope-invalid:ValueError"]),
                   dict(valid, failures=["protected-file-changed:contract.json"]),
                   dict(valid, failures=["contract-failed:contract.json:ValueError"]),
                   dict(valid, failures=["contract-failed:target.txt:RuntimeError"]),
                   dict(valid, error="unexpected"), dict(valid, write_state="partial-or-unverified")]
        for result in invalid:
            with self.subTest(result=result):
                self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, result, event, self.task))
        self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, valid, {"state_sha256": None}, self.task))

    def test_normal_negative_feedback_cannot_expand_twelve_http_requests(self):
        def always_negative(provider, payload, key, timeout):
            index = len(self.before)
            return 200, {}, canonical(completion(index, [call("validate-" + str(index), "repo_validate", {})]))
        with patch.object(lab, "_post", side_effect=always_negative) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 12)
        self.assertEqual(result["requests"], 12)
        self.assertEqual(len(result["tool_events"]), 12)
        self.assertEqual(result["status"], "request-budget-exhausted")
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertEqual(len(self.after), 12)

    def test_normal_negative_feedback_cannot_expand_thirty_two_tools(self):
        first = completion(1, [call("validate-" + str(index), "repo_validate", {}) for index in range(32)])
        second = completion(2, [call("validate-33", "repo_validate", {})])
        with patch.object(lab, "_post", side_effect=self.scripted([first, second])) as post:
            result = self.run_actor()
        self.assertEqual(post.call_count, 2)
        self.assertEqual(len(result["tool_events"]), 32)
        self.assertEqual(result["max_tools"], 32)
        self.assertEqual(result["status"], "tool-contract-failed")
        self.assertIn("api-tool-rejected:tool-budget-or-shape", result["quality"]["failures"])

    def test_both_profile_parameters_are_required_and_invalid_values_send_nothing(self):
        signature = inspect.signature(lab.run_actor)
        for name in ("response_json_mode", "thinking"):
            self.assertIs(signature.parameters[name].default, inspect.Parameter.empty)
        for profile in ({"response_json_mode": 1, "thinking": "disabled"},
                        {"response_json_mode": False, "thinking": "omitted"}):
            with patch.object(lab, "_post") as post, self.assertRaises(ValueError):
                self.run_actor(**profile)
            post.assert_not_called()
        self.assertEqual(self.loaded, [])

    def test_native_finish_profile_pair_is_frozen_and_alternatives_send_nothing(self):
        # An enabled mode still needs the separately selected explicit profile.
        for json_mode, thinking in ((True, "disabled"), (False, "enabled"), (True, "enabled")):
            with self.subTest(json_mode=json_mode, thinking=thinking):
                with patch.object(lab, "_post") as post, self.assertRaises(ValueError):
                    self.run_actor(response_json_mode=json_mode, thinking=thinking)
                post.assert_not_called()
        self.assertEqual(self.loaded, [])
        with patch.object(lab, "_post", side_effect=self.positive):
            result = self.run_actor(response_json_mode=False, thinking="disabled")
        self.assertTrue(result["quality"]["hard_pass"])
        self.assertIs(result["response_json_mode"], False)

    def test_feedback_does_not_waive_final_artifact_or_claim_contract(self):
        steps = [self.read(1), self.patch_from_read(2, "still-wrong\n"),
                 self.validate_and_status(3), self.final(4)]
        with patch.object(lab, "_post", side_effect=self.scripted(steps)):
            result = self.run_actor()
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertIn("contract-failed:target.txt:ValueError", result["quality"]["failures"])
        self.assertIn("final-validation-claim-invalid", result["quality"]["failures"])

    def test_prior_successful_validate_and_status_cannot_cover_a_later_edit(self):
        def final_later_edit(payload):
            return completion(4, [call("late-edit", "repo_patch", {"operations": [
                {"path": "target.txt", "old_sha256": sha(b"fixed\n"), "new_text": "fixed"}]})])
        steps = [self.read(1), self.patch_from_read(2, "fixed\n"), self.validate_and_status(3),
                 final_later_edit, self.final(5, validation="failed")]
        with patch.object(lab, "_post", side_effect=self.scripted(steps)):
            result = self.run_actor()
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertIn("required-current-real-tool-evidence-missing", result["quality"]["failures"])

    def test_final_transport_receipt_binds_real_response_original_args_and_state(self):
        original = ' {"summary":"公开终态", "validation":"passed", "helper_gap":"project_tool unavailable in bounded broker"} \n'
        report_call = call("terminal-original", "repo_finish", FINAL)
        report_call["function"]["arguments"] = original
        result = self.execute(self.ready() + [completion(4, [report_call])])
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assertEqual(result["final_text"], original)
        self.assertEqual(result["tool_attempts"], 5)
        self.assertEqual(len(result["tool_events"]), 4)
        self.assertEqual(len(result["api_tool_trace"]), 4)
        self.assertNotIn("repo_finish", {item["tool"] for item in result["tool_events"]})
        path = self.artifacts / "report-receipt.json"
        report = json.loads(path.read_bytes())
        self.assertEqual(sha(path.read_bytes()), result["final_report_receipt_sha256"])
        self.assertEqual(report, result["final_report"])
        self.assertEqual(report["arguments_raw"], original)
        self.assertEqual(report["arguments_utf8_sha256"], sha(original.encode("utf-8")))
        self.assertEqual(report["arguments_sha256"], sha(canonical(json.loads(original))))
        self.assertEqual(report["state_sha256"], result["final_state_sha256"])
        self.assertEqual(report["response_artifact_sha256"], sha((self.artifacts / "requests/04.response.json").read_bytes()))
        self.assertEqual(report["request_receipt_sha256"], sha((self.artifacts / "requests/04.receipt.json").read_bytes()))
        self.assertEqual(report["api_response_id"], "mock-response-4")
        self.assertEqual(report["last_broker_chain_sha256"], result["api_tool_trace"][-1]["chain_sha256"])
        self.assertFalse(report["grading_performed_here"])
        self.assertEqual(result["usage"]["total_tokens"], 60)
        self.assertEqual(len(self.after), 4)
        self.assertTrue(all(item["dispatched"] for item in self.after))
        self.assertFalse(list(self.artifacts.rglob("*.pending.json")))

    def test_plain_json_fenced_json_and_textual_tool_mimic_never_become_reports(self):
        texts = [json.dumps(FINAL), "```json\n" + json.dumps(FINAL) + "\n```",
                 json.dumps({"tool_calls": [call("fake", "repo_finish", FINAL)]}), "Finished successfully."]
        for index, text in enumerate(texts):
            with self.subTest(kind=index):
                self.artifacts = self.base / ("text-final-" + str(index))
                self.before, self.after = [], []
                with patch.object(lab, "_post", return_value=(200, {}, canonical(completion(1, content=text)))) as post:
                    result = self.run_actor()
                self.assertEqual(post.call_count, 1)
                self.assertFalse(result["quality"]["hard_pass"])
                self.assertEqual(result["status"], "tool-contract-failed")
                self.assertIsNone(result["final_report"])
                self.assertFalse((self.artifacts / "report-receipt.json").exists())
                self.assertEqual(result["final_text"], "")

    def test_premature_schema_valid_finish_does_not_fabricate_real_tools_or_edit(self):
        result = self.execute([self.final(1)])
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertEqual(result["tool_events"], [])
        self.assertEqual(result["api_tool_trace"], [])
        self.assertEqual(result["tool_attempts"], 1)
        self.assertIsNotNone(result["final_report"])
        self.assertIn("no-actual-repository-edit-by-this-actor", result["quality"]["failures"])
        self.assertIn("required-current-real-tool-evidence-missing", result["quality"]["failures"])

    def test_mixed_finish_batch_is_rejected_before_any_repository_operation(self):
        patch_call = call("mixed-write", "repo_patch", {"operations": [{"path": "target.txt",
            "old_sha256": sha(b"old\n"), "new_text": "fixed\n"}]})
        for index, calls in enumerate(([self.final(1)["choices"][0]["message"]["tool_calls"][0], patch_call],
                                       [patch_call, self.final(1)["choices"][0]["message"]["tool_calls"][0]])):
            self.artifacts = self.base / ("mixed-" + str(index)); self.before, self.after = [], []
            result = self.execute([completion(1, calls)])
            self.assertFalse(result["quality"]["hard_pass"])
            self.assertEqual(result["tool_events"], [])
            self.assertEqual((self.workspace / "target.txt").read_bytes(), b"old\n")
            self.assertIsNone(result["final_report"])
            self.assertIn("api-finish-rejected:mixed-batch", result["quality"]["failures"])

    def test_native_finish_requires_function_unique_id_schema_and_tool_finish_reason(self):
        mutations = [lambda c: c.update(type="text"), lambda c: c.update(id=""),
                     lambda c: c.update(id="  "), lambda c: c.update(id="read-1"),
                     lambda c: c["function"].update(arguments=json.dumps(dict(FINAL, extra=True))),
                     lambda c: c["function"].update(arguments=json.dumps(dict(FINAL, validation=True))),
                     lambda c: c["function"].update(arguments="```json\n" + json.dumps(FINAL) + "\n```"),
                     lambda c: c["function"].update(arguments='{"summary":"x","summary":"y","validation":"passed","helper_gap":"project_tool unavailable in bounded broker"}'),
                     lambda c: c["function"].update(arguments='{"summary":NaN,"validation":"passed","helper_gap":"none"}')]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                (self.workspace / "target.txt").write_bytes(b"old\n")
                self.artifacts = self.base / ("invalid-finish-" + str(index)); self.before, self.after = [], []
                response = self.final(4); mutate(response["choices"][0]["message"]["tool_calls"][0])
                result = self.execute(self.ready() + [response])
                self.assertFalse(result["quality"]["hard_pass"])
                self.assertIsNone(result["final_report"])
                self.assertEqual((self.workspace / "target.txt").read_bytes(), b"fixed\n")
        (self.workspace / "target.txt").write_bytes(b"old\n")
        self.artifacts = self.base / "wrong-reason"; self.before, self.after = [], []
        response = self.final(4); response["choices"][0]["finish_reason"] = "stop"
        result = self.execute(self.ready() + [response])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertIsNone(result["final_report"])

    def test_native_finish_cannot_stand_in_for_missing_initial_contract_read(self):
        read_target_only = completion(1, [call("read-target", "repo_read", {"paths": ["target.txt"]})])
        result = self.execute([read_target_only, self.patch_from_read(2, "fixed\n"), self.validate_and_status(3), self.final(4)])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertTrue(any("contract.json" in failure for failure in result["quality"]["failures"]))

    def test_finish_cannot_change_the_original_helper_gap_enum(self):
        result = self.execute(self.ready() + [self.final(4, helper_gap="none")])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertIsNone(result["final_report"])

    def test_finish_schema_valid_but_wrong_validation_claim_still_fails_original_grader(self):
        result = self.execute(self.ready() + [self.final(4, validation="failed")])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertIsNotNone(result["final_report"])
        self.assertIn("final-validation-claim-invalid", result["quality"]["failures"])

    def test_finish_cannot_hide_protected_drift(self):
        def changed(payload):
            (self.workspace / "contract.json").write_bytes(b'{"external":true}\n')
            return self.final(4)
        result = self.execute(self.ready() + [changed])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertFalse(result["quality"]["scope_ok"])
        self.assertIn("protected-file-changed:contract.json", result["quality"]["failures"])

    def test_finish_is_the_thirty_second_admitted_tool_and_never_the_thirty_third(self):
        for maximum, statuses in ((32, 28), (33, 29)):
            (self.workspace / "target.txt").write_bytes(b"old\n")
            self.artifacts = self.base / ("tool-count-" + str(maximum)); self.before, self.after = [], []
            many = completion(3, [call("validate-ready", "repo_validate", {})]
                              + [call("status-" + str(i), "repo_status", {}) for i in range(statuses)])
            result = self.execute([self.read(1), self.patch_from_read(2, "fixed\n"), many, self.final(4)])
            self.assertEqual(result["tool_attempts"], 32)
            self.assertEqual(result["quality"]["hard_pass"], maximum == 32)
            self.assertEqual(len(result["tool_events"]), maximum - 1 if maximum == 32 else 32)
            if maximum == 33:
                self.assertIsNone(result["final_report"])

    def test_missing_usage_on_finish_remains_unknown_and_known_cost_is_preserved(self):
        response = self.final(4); del response["usage"]
        result = self.execute(self.ready() + [response])
        self.assertTrue(result["unknown_usage"])
        self.assertIsNone(result["usage"])
        self.assertEqual(result["known_usage"]["total_tokens"], 45)
        self.assertIsNone(result["final_report"])
        self.assertIsNone(self.after[-1]["usage"])
        self.assertTrue(self.after[-1]["unknown"])
        self.assertTrue((self.artifacts / "requests/04.pending.json").exists())
        self.assertFalse(result["quality"]["hard_pass"])
        with self.assertRaises(lab.ActorFence):
            self.run_actor()

    def test_finish_consumption_is_accounted_like_every_other_request_without_polishing(self):
        charges = []
        original_account = self.account
        def account(metadata):
            original_account(metadata)
            usage = metadata["usage"]
            # Conservative registered all-miss estimate, not an invoice.
            charges.append((Decimal(usage["input_tokens"]) * Decimal(".30")
                            + Decimal(usage["output_tokens"]) * Decimal("1.20")) / 1_000_000)
        self.account = account
        result = self.execute(self.ready() + [self.final(4)])
        self.assertTrue(result["quality"]["hard_pass"])
        self.assertEqual(sum(charges), Decimal(".000036"))
        self.assertEqual(len(charges), result["requests"])
        self.assertEqual(result["requests"], 4)
        self.assertEqual(self.after[-1]["request_id"], result["final_report"]["request_id"])
        self.assertEqual(self.after[-1]["api_response_id"], result["final_report"]["api_response_id"])

    def test_duplicate_api_response_on_finish_keeps_both_reported_charges(self):
        response = self.final(4); response["id"] = "mock-response-3"
        result = self.execute(self.ready() + [response])
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(result["known_usage"]["total_tokens"], 60)
        self.assertIsNone(result["final_report"])

    def test_report_persistence_failure_keeps_usage_and_unknown_fence(self):
        real_write = lab._write_new
        def failing_write(path, value, secret=""):
            if Path(path).name == "report-receipt.json":
                raise OSError("synthetic report evidence disk failure")
            return real_write(path, value, secret)
        with patch.object(lab, "_write_new", side_effect=failing_write):
            result = self.execute(self.ready() + [self.final(4)])
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(result["known_usage"]["total_tokens"], 60)
        self.assertTrue((self.artifacts / "actor.pending.json").exists())
        self.assertFalse(result["quality"]["hard_pass"])

    def test_escaped_secret_finish_never_reaches_report_receipt_or_broker(self):
        escaped = "".join("\\u%04x" % ord(char) for char in SECRET)
        response = self.final(1)
        response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = (
            '{"summary":"' + escaped + '","validation":"failed","helper_gap":"none"}')
        result = self.execute([response])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertEqual(result["tool_events"], [])
        self.assertIsNone(result["final_report"])
        for path in self.artifacts.rglob("*"):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes())
                self.assertNotIn(escaped.encode(), path.read_bytes())

    def test_input_byte_cap_refuses_before_reservation_key_or_http(self):
        with patch.object(lab, "_post") as post:
            result = lab.run_actor("deepseek", "mock-requested-model", self.task, self.workspace,
                self.artifacts, self.git, "x" * 131073, self.key, response_json_mode=False, thinking="disabled",
                before_request=self.reserve, after_request=self.account)
        self.assertEqual(result["status"], "input-byte-cap-not-invoked")
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.before, [])
        post.assert_not_called()
        self.assertFalse(result["quality"]["hard_pass"])

    def test_state_change_after_report_and_grading_is_never_a_stale_pass(self):
        real_quality = lab._api_quality
        def changed(*args):
            result = real_quality(*args)
            (self.workspace / "target.txt").write_bytes(b"later-edit\n")
            return result
        with patch.object(lab, "_api_quality", side_effect=changed):
            result = self.execute(self.ready() + [self.final(4)])
        self.assertFalse(result["quality"]["hard_pass"])
        self.assertEqual(result["quality"]["task_success"], 0)
        self.assertIn("api-finish-rejected:state-changed-after-report", result["quality"]["failures"])

    def test_usage_normalization_rejects_invalid_counts_and_preserves_cached_subset(self):
        raw = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
               "prompt_tokens_details": {"cached_tokens": 2}, "completion_tokens_details": {"reasoning_tokens": 1}}
        usage = lab._usage(raw)
        self.assertEqual((usage["input_tokens"], usage["output_tokens"], usage["total_tokens"], usage["cached_tokens"]), (10, 5, 15, 2))
        self.assertEqual(lab._totals([usage, usage])["total_tokens"], 30)
        invalid = [dict(raw, total_tokens=14), dict(raw, prompt_tokens=True), dict(raw, completion_tokens=-1),
                   dict(raw, prompt_tokens_details={"cached_tokens": 11}),
                   dict(raw, completion_tokens_details={"reasoning_tokens": 6}),
                   dict(raw, prompt_cache_hit_tokens=3), dict(raw, prompt_tokens_details=[2])]
        for record in invalid:
            with self.subTest(record=record):
                self.assertIsNone(lab._usage(record))
        self.assertIsNone(lab._totals([usage, dict(usage, cached_tokens=None)])["cached_tokens"])
        self.assertEqual(lab._totals([usage, dict(usage, cached_tokens=None)])["total_tokens"], 30)

    def test_usage_details_allow_only_missing_null_or_dict_and_counters_remain_strict(self):
        base = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        for field, counter in (("prompt_tokens_details", "cached_tokens"), ("completion_tokens_details", "reasoning_tokens")):
            for malformed in ([], False, 0, "", [0], "details", True):
                with self.subTest(field=field, malformed=malformed):
                    self.assertIsNone(lab._usage(dict(base, **{field: malformed})))
            for allowed in (None, {}):
                self.assertIsNone(lab._usage(dict(base, **{field: allowed}))[counter])
            for invalid in (True, False, -1, 11, "0"):
                with self.subTest(field=field, invalid=invalid):
                    self.assertIsNone(lab._usage(dict(base, **{field: {counter: invalid}})))
        self.assertIsNone(lab._usage(base)["cached_tokens"])
        self.assertIsNone(lab._usage(base)["reasoning_tokens"])
        # A bool alias must not compare equal to an otherwise valid integer 0.
        self.assertIsNone(lab._usage(dict(base, prompt_cache_hit_tokens=False,
                                         prompt_tokens_details={"cached_tokens": 0})))
        self.assertEqual(lab._usage(dict(base, prompt_cache_hit_tokens=0,
                                        prompt_tokens_details={"cached_tokens": 0}))["cached_tokens"], 0)
        self.assertIsNone(lab._usage(dict(base, prompt_cache_hit_tokens=None))["cached_tokens"])

    def test_invalid_detail_shape_preserves_private_raw_basic_components_and_unknown_fence(self):
        for index, (field, value) in enumerate((("prompt_tokens_details", []), ("completion_tokens_details", False))):
            self.artifacts, self.before, self.after = self.base / ("invalid-details-" + str(index)), [], []
            raw = self.read(1)
            raw["usage"][field] = value
            with patch.object(lab, "_post", return_value=(200, {}, canonical(raw))) as post:
                result = self.run_actor()
            self.assertEqual(post.call_count, 1)
            self.assertTrue(result["unknown_usage"])
            self.assertIsNone(result["known_usage"]["total_tokens"])
            self.assertIsNone(self.after[0]["usage"])
            self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
            actual = json.loads((self.artifacts / "requests/01.response.json").read_bytes())["response"]["usage"]
            self.assertEqual(actual, raw["usage"])
            self.assertEqual((actual["prompt_tokens"], actual["completion_tokens"], actual["total_tokens"]), (10, 5, 15))
            self.assertEqual(result["tool_events"], [])

    def test_connection_only_failures_record_attempt_and_prove_no_http_without_retry(self):
        cases = [(socket.gaierror(11001, SECRET), "gaierror"),
                 (lab.ssl.SSLCertVerificationError(1, "Bearer " + SECRET), "SSLCertVerificationError"),
                 (ConnectionRefusedError(SECRET), "ConnectionRefusedError")]
        for index, (error, category) in enumerate(cases):
            with self.subTest(category=category):
                self.artifacts, self.before, self.after = self.base / ("connect-" + str(index)), [], []
                connection = Mock()
                connection.connect.side_effect = error
                with patch.object(lab.http.client, "HTTPSConnection", return_value=connection) as constructor:
                    result = self.run_actor()
                self.assertEqual(constructor.call_count, 1)
                self.assertEqual(connection.connect.call_count, 1)
                connection.request.assert_not_called()
                connection.close.assert_called_once()
                receipt = self.after[0]
                self.assertEqual(receipt["transport"], {"phase": "connect", "exception_class": category,
                    "connection_attempted": True, "http_dispatch": "not_started"})
                self.assertEqual((receipt["dispatched"], receipt["not_invoked"], receipt["unknown"]), (False, True, False))
                self.assertEqual(result["requests"], 1)  # A bounded transport slot, not a fabricated HTTP dispatch.
                self.assertEqual(result["status"], "transport-failed-not-invoked")
                self.assertFalse(result["quality"]["hard_pass"])
                self.assertIsNone(receipt["usage"])
                self.assertFalse((self.artifacts / "requests/01.pending.json").exists())
                self.assertTrue((self.artifacts / "requests/01.receipt.json").exists())
                self.assertFalse((self.artifacts / "requests/01.response.json").exists())
                for path in self.artifacts.rglob("*.json"):
                    self.assertNotIn(SECRET, path.read_text(encoding="utf-8"))

    def test_entered_request_header_and_body_failures_remain_unknown_even_for_dns_class(self):
        cases = [("request", socket.gaierror(11001, SECRET), "http-request", "gaierror", "may_have_started"),
                 ("request", TimeoutError(SECRET), "http-request", "TimeoutError", "may_have_started"),
                 ("headers", lab.http.client.RemoteDisconnected(SECRET), "response-headers", "RemoteDisconnected", "may_have_started"),
                 ("body", lab.http.client.IncompleteRead(SECRET.encode()), "response-body", "IncompleteRead", "response_received")]
        for index, (where, error, phase, category, dispatch) in enumerate(cases):
            with self.subTest(where=where, category=category):
                self.artifacts, self.before, self.after = self.base / ("sent-" + str(index)), [], []
                response, connection = Mock(status=200), Mock()
                response.getheaders.return_value = []
                response.read.return_value = canonical(completion(1))
                connection.getresponse.return_value = response
                {"request": connection.request, "headers": connection.getresponse, "body": response.read}[where].side_effect = error
                with patch.object(lab.http.client, "HTTPSConnection", return_value=connection) as constructor:
                    result = self.run_actor()
                self.assertEqual(constructor.call_count, 1)
                self.assertEqual(connection.request.call_count, 1)
                self.assertEqual(connection.auto_open, 0)
                self.assertEqual(self.after[0]["transport"], {"phase": phase, "exception_class": category,
                    "connection_attempted": True, "http_dispatch": dispatch})
                self.assertEqual((self.after[0]["dispatched"], self.after[0]["not_invoked"], self.after[0]["unknown"]), (True, False, True))
                self.assertTrue(result["unknown_usage"])
                self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
                for path in self.artifacts.rglob("*.json"):
                    self.assertNotIn(SECRET, path.read_text(encoding="utf-8"))

    def test_worker_deadline_and_completed_connect_deadline_prove_no_http(self):
        with patch.object(lab.time, "perf_counter", side_effect=[0.0, 2.0]), patch.object(lab, "_post") as post:
            with self.assertRaises(lab.TransportFailure) as raised:
                lab._bounded_post("deepseek", {}, SECRET, 1)
        post.assert_not_called()
        self.assertEqual(raised.exception.transport, {"phase": "worker-before-request", "exception_class": "DeadlineBeforeDispatch",
            "connection_attempted": False, "http_dispatch": "not_started"})
        connection = Mock()
        with patch.object(lab.time, "perf_counter", side_effect=[0.0, 2.0]), patch.object(lab.http.client, "HTTPSConnection", return_value=connection):
            with self.assertRaises(lab.TransportFailure) as raised:
                lab._post("deepseek", {}, SECRET, 1)
        self.assertEqual(raised.exception.transport["exception_class"], "DeadlineBeforeDispatch")
        self.assertTrue(raised.exception.transport["connection_attempted"])
        self.assertEqual(raised.exception.transport["http_dispatch"], "not_started")
        connection.request.assert_not_called()
        with patch.object(lab.http.client, "HTTPSConnection", side_effect=OSError(SECRET)):
            with self.assertRaises(lab.TransportFailure) as raised:
                lab._post("deepseek", {}, SECRET, 1)
        self.assertEqual(raised.exception.transport, {"phase": "connection-create", "exception_class": "OSError",
            "connection_attempted": False, "http_dispatch": "not_started"})

    def test_transport_serializes_fixed_classes_and_preserves_response_processing_phase(self):
        dynamic = type("secret_" + SECRET, (Exception,), {})
        with patch.object(lab, "_post", side_effect=dynamic("Bearer " + SECRET)):
            result = self.run_actor()
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(self.after[0]["transport"]["exception_class"], "OtherError")
        self.assertNotIn(SECRET, json.dumps(self.after))
        for index, body in enumerate((b"not JSON", b"\xff")):
            self.artifacts, self.before, self.after = self.base / ("decode-" + str(index)), [], []
            with patch.object(lab, "_post", return_value=(200, {}, body)):
                result = self.run_actor()
            self.assertTrue(result["unknown_usage"])
            self.assertEqual(self.after[0]["transport"]["phase"], "response-decode")
            self.assertIn(self.after[0]["transport"]["exception_class"], {"ValueError", "UnicodeError"})
            self.assertTrue((self.artifacts / "requests/01.response.json").exists())
        self.artifacts, self.before, self.after = self.base / "persist", [], []
        write = lab._write_new
        def failing_write(path, value, secret=""):
            if str(path).endswith("01.response.json"):
                raise OSError("Bearer " + SECRET)
            return write(path, value, secret)
        with patch.object(lab, "_post", return_value=(200, {}, canonical(completion(1)))), patch.object(lab, "_write_new", side_effect=failing_write):
            result = self.run_actor()
        self.assertEqual(self.after[0]["transport"]["phase"], "response-persist")
        self.assertEqual(self.after[0]["transport"]["exception_class"], "OSError")
        self.assertTrue(result["unknown_usage"])
        self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
        self.artifacts, self.before, self.after = self.base / "owner-interrupt", [], []
        with patch.object(lab, "_bounded_post", side_effect=KeyboardInterrupt):
            result = self.run_actor()
        self.assertTrue(result["unknown_usage"])
        self.assertEqual(self.after[0]["error_type"], "KeyboardInterrupt")
        self.assertEqual(self.after[0]["transport"]["exception_class"], "KeyboardInterrupt")
        self.assertEqual(self.after[0]["transport"]["http_dispatch"], "unknown")
        self.assertTrue((self.artifacts / "requests/01.pending.json").exists())

    def test_public_path_manifest_is_identical_for_conditions_and_providers_and_is_not_read_evidence(self):
        self.task["checks"][0]["expected"] = "PRIVATE_EXPECTED_MARKER"
        users = []
        for index, arm in enumerate(("rc19", "attention", "full_rc20", "minus_decision_relevance", "minus_complete_change", "minus_evidence_fidelity")):
            self.artifacts, self.before, self.after = self.base / ("manifest-" + arm), [], []
            def capture(provider, payload, key, timeout):
                users.append(payload["messages"][1]["content"])
                return 200, {}, canonical(self.final(1))
            with patch.object(lab, "_post", side_effect=capture):
                result = self.run_actor(provider="deepseek" if index % 2 else "mimo", system_context=arm, max_requests=1)
            self.assertFalse(result["quality"]["required_tools_ok"])
            self.assertEqual(result["tool_events"], [])
        self.assertTrue(all(user == users[0] for user in users))
        manifest = json.loads(users[0].split("\n")[-1])
        self.assertEqual(manifest, {"initial_paths": ["contract.json", "target.txt"],
            "required_read_paths": ["contract.json", "target.txt"], "writable_files": ["target.txt"]})
        self.assertNotIn("PRIVATE_EXPECTED_MARKER", users[0])
        self.assertNotIn('"checks"', users[0])

    def test_semantic_feedback_repair_and_existing_multi_read_validate_status_batches_pass(self):
        self.semantic_task()
        def read_after_failure(payload):
            feedback = self.feedback(payload)
            self.assertEqual(feedback["diagnostics"], [{"code": "return-mismatch", "path": "core.py"}])
            self.assertEqual((feedback["checks_passed"], feedback["checks_total"]), (0, 1))
            return completion(2, [call("read-contract", "repo_read", {"paths": ["contract.json"]}),
                                  call("read-core", "repo_read", {"paths": ["core.py"]})])
        def repair(payload):
            digest = self.feedback(payload)["files"]["core.py"]["sha256"]
            return completion(3, [call("repair", "repo_patch", {"operations": [{"path": "core.py", "old_sha256": digest,
                "new_text": "def transform(value):\n    result = value * 2\n    return result\n"}]})])
        result = self.execute([completion(1, [call("negative", "repo_validate", {})]), read_after_failure, repair,
            self.validate_and_status(4), self.final(5)])
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assertEqual(result["quality"]["validation"]["diagnostics"], [])
        self.assertEqual(result["requests"], 5)
        self.assertEqual(len(result["tool_events"]), 6)
        self.assertEqual(result["tool_attempts"], 7)
        self.assert_negative_preserved(result, 1, result["tool_events"][0]["result"])
        serialized = json.dumps(result["tool_events"][0]["result"])
        for field in ('"probe"', '"input"', '"expected"', '"source"'):
            self.assertNotIn(field, serialized)

    def test_semantic_feedback_schema_cannot_relax_scope_or_expose_unbounded_payloads(self):
        self.semantic_task()
        valid = {"ok": False, "suite": "registered-static-contracts-v1", "checks_passed": 0, "checks_total": 1,
            "failures": ["contract-failed:core.py:ValueError"], "diagnostics": [{"code": "return-mismatch", "path": "core.py"}]}
        event = {"state_sha256": "known-state"}
        self.assertTrue(lab._recoverable_tool_feedback("repo_validate", {}, valid, event, self.task))
        bad = [[], [{"code": "private-" + SECRET, "path": "core.py"}], [{"code": "return-mismatch", "path": "outside.py"}],
            [{"code": "return-mismatch", "path": "core.py", "probe": 0}], valid["diagnostics"] * 2,
            valid["diagnostics"] * 17, "not-list"]
        for diagnostics in bad[1:]:  # [] is legal for scope-only/no-locatable ordinary feedback.
            with self.subTest(diagnostics=diagnostics):
                self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, dict(valid, diagnostics=diagnostics), event, self.task))
        missing = dict(valid)
        del missing["diagnostics"]
        self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, missing, event, self.task))
        self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, dict(valid, failures=["protected-file-changed:contract.json"]), event, self.task))
        self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, valid, {"state_sha256": None}, self.task))


@unittest.skipUnless(SUPPORTED, "repository API helper tests require Python 3.10+")
class ThinkingProfileTests(_ProviderFixture, unittest.TestCase):
    def enabled(self, provider="deepseek", **kwargs):
        return self.run_actor(provider=provider, model=lab.THINKING_PROFILE_SETTINGS[provider]["model"],
                              profile_id=lab.THINKING_PROFILE, thinking="enabled", **kwargs)

    def test_enabled_profile_preserves_exact_reasoning_and_provider_specific_payload(self):
        for provider in ("deepseek", "mimo"):
            (self.workspace / "target.txt").write_bytes(b"old\n")
            self.artifacts, self.before, self.after = self.base / provider, [], []
            steps = self.ready() + [self.final(4)]
            observed = []
            def post(actual_provider, payload, key, timeout):
                index = len(self.before)
                self.assertEqual(actual_provider, provider)
                self.assertEqual(payload["thinking"], {"type": "enabled"})
                self.assertEqual(payload["max_tokens" if provider == "deepseek" else "max_completion_tokens"], 8192)
                if provider == "deepseek":
                    self.assertEqual(payload["reasoning_effort"], "low")
                else:
                    self.assertNotIn("reasoning_effort", payload)
                self.assertEqual([m["reasoning_content"] for m in payload["messages"] if m["role"] == "assistant"], observed)
                if index == 1:
                    self.assertEqual(observed, [])  # Fresh actor has no predecessor conversation.
                step = steps[index - 1]
                response = step(payload) if callable(step) else step
                reasoning = "opaque synthetic Ω field " + str(index)
                response["choices"][0]["message"]["reasoning_content"] = reasoning
                observed.append(reasoning)
                return 200, {}, canonical(response)
            with patch.object(lab, "_post", side_effect=post):
                result = self.enabled(provider)
            self.assertTrue(result["quality"]["hard_pass"], result["quality"])
            self.assertEqual((result["profile_id"], result["output_cap"]), (lab.THINKING_PROFILE, 8192))
            self.assertTrue(all(row["output_cap"] == 8192 and row["profile_id"] == lab.THINKING_PROFILE for row in self.before + self.after))
            self.assertNotIn("opaque synthetic", json.dumps(result))

    def test_profile_mismatch_is_rejected_before_artifacts_reservation_or_credentials(self):
        for changes in ({"profile_id": "unknown"}, {"thinking": "disabled"},
                        {"response_json_mode": True}, {"model": "another-model"}):
            args = {"model": "deepseek-flash", "profile_id": lab.THINKING_PROFILE,
                    "thinking": "enabled", "response_json_mode": False}
            args.update(changes)
            with patch.object(lab, "_post") as post, self.assertRaises(ValueError):
                self.run_actor(**args)
            post.assert_not_called()
        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
        self.assertFalse(self.artifacts.exists())

    def test_replayed_reasoning_input_cap_stops_before_next_reservation(self):
        def response(provider, payload, key, timeout):
            raw = self.read(len(self.before))
            raw["choices"][0]["message"]["reasoning_content"] = "Ω" * 25000
            return 200, {}, canonical(raw)
        with patch.object(lab, "_post", side_effect=response) as post:
            result = self.enabled()
        self.assertEqual((post.call_count, len(self.before), len(self.after)), (3, 3, 3))
        self.assertEqual(result["status"], "input-byte-cap-not-invoked")
        self.assertEqual(result["known_usage"]["total_tokens"], 45)
        self.assertFalse(result["unknown_usage"])

    def test_unreplayable_reasoning_stops_with_usage_and_never_leaks_or_retries(self):
        for index, reasoning in enumerate((["invalid type"], SECRET, "Bearer opaque-token")):
            self.artifacts, self.before, self.after = self.base / ("unreplayable-" + str(index)), [], []
            response = self.read(1)
            response["choices"][0]["message"]["reasoning_content"] = reasoning
            with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
                result = self.enabled()
            self.assertEqual(post.call_count, 1)
            self.assertTrue(result["unknown_usage"])
            self.assertEqual(result["known_usage"]["total_tokens"], 15)
            self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
            self.assertEqual(result["tool_events"], [])
            for path in self.artifacts.rglob("*"):
                if path.is_file():
                    self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_enabled_completion_cap_is_8192_and_reasoning_subset_is_not_double_counted(self):
        for output, overrun in ((6000, False), (8193, True)):
            self.artifacts, self.before, self.after = self.base / ("usage-" + str(output)), [], []
            response = self.read(1)
            response["usage"].update(completion_tokens=output, total_tokens=10 + output,
                                     completion_tokens_details={"reasoning_tokens": output - 1})
            with patch.object(lab, "_post", return_value=(200, {}, canonical(response))) as post:
                result = self.enabled(max_requests=1)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(result["known_usage"]["total_tokens"], 10 + output)
            self.assertEqual(result["known_usage"]["reasoning_tokens"], output - 1)
            self.assertEqual(result["status"], "unexpected-overrun-blocked" if overrun else "request-budget-exhausted")
            self.assertEqual(self.after[0]["unexpected_overrun"].get("output_tokens") is not None, overrun)
            self.assertEqual(len(result["tool_events"]), 0 if overrun else 1)

    def test_immutable_reservation_identity_is_bound_into_pending_and_outcome(self):
        original = self.reserve
        def reserve(metadata):
            return dict(original(metadata), reservation_receipt_sha256="c" * 64)
        self.reserve = reserve
        def post(provider, payload, key, timeout):
            pending = json.loads((self.artifacts / "requests/01.pending.json").read_bytes())
            self.assertEqual(pending["reservation_receipt_sha256"], "c" * 64)
            self.assertEqual(pending["reservation"]["reservation_receipt_sha256"], "c" * 64)
            return 200, {}, canonical(self.final(1))
        with patch.object(lab, "_post", side_effect=post):
            self.enabled(max_requests=1)
        self.assertEqual(self.after[0]["reservation_receipt_sha256"], "c" * 64)
        self.assertEqual(json.loads((self.artifacts / "requests/01.receipt.json").read_bytes())["reservation_receipt_sha256"], "c" * 64)

    def test_enabled_owner_interrupt_retains_original_reservation_and_never_retries(self):
        with patch.object(lab, "_bounded_post", side_effect=KeyboardInterrupt) as post:
            result = self.enabled()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(self.before[0]["output_cap"], 8192)
        self.assertEqual(self.after[0]["error_type"], "KeyboardInterrupt")
        self.assertTrue(result["unknown_usage"])
        self.assertTrue((self.artifacts / "requests/01.pending.json").exists())

    def test_registered_json_decode_failure_is_ordinary_feedback_then_actual_repair_passes(self):
        self.task["checks"].append({"path": "contract.json", "kind": "json", "expected": {"fixed": True}})
        self.task["writable_files"].append("contract.json")
        self.task["initial_files"]["contract.json"] = "{"
        (self.workspace / "contract.json").write_bytes(b"{")
        def repair(payload):
            self.assertIn("contract-failed:contract.json:JSONDecodeError", self.feedback(payload)["failures"])
            return completion(3, [call("repair", "repo_patch", {"operations": [
                {"path": "target.txt", "old_sha256": sha(b"old\n"), "new_text": "fixed\n"},
                {"path": "contract.json", "old_sha256": sha(b"{"), "new_text": '{"fixed":true}\n'}]})])
        result = self.execute([self.read(1), completion(2, [call("bad-json", "repo_validate", {})]),
                               repair, self.validate_and_status(4), self.final(5)])
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        bad = result["tool_events"][1]["result"]
        forged = dict(bad, failures=["contract-failed:target.txt:JSONDecodeError", "contract-failed:contract.json:ValueError"])
        self.assertFalse(lab._recoverable_tool_feedback("repo_validate", {}, forged,
                                                       {"state_sha256": "known"}, self.task))

    def test_noop_patch_stays_terminal_and_does_not_use_json_recovery(self):
        steps = [self.read(1), self.patch_from_read(2, "old\n")]
        result = self.execute(steps)
        self.assertEqual(result["status"], "tool-contract-failed")
        self.assertEqual(result["tool_events"][-1]["result"]["error"], "ValueError: patch must make a nonempty bounded change")


@unittest.skipUnless(SUPPORTED, "repository API helper tests require Python 3.10+")
class OptInExecutionTests(_ProviderFixture, unittest.TestCase):
    def enabled(self, **kwargs):
        from evolution.isolated_python import EXECUTION_BACKEND
        kwargs.setdefault('execution_backend', EXECUTION_BACKEND)
        return self.run_actor(model='deepseek-flash', thinking='enabled', profile_id=lab.FLASH_THINKING_PROFILE, **kwargs)

    def capture(self, *, rows=None, mode=None, first_rows=None):
        from tests.test_isolated_python import FakeDocker
        fakes = []
        def call(argv, deadline):
            if argv[1:3] == ['image', 'inspect']:
                fakes.append(FakeDocker(first_rows if not fakes and first_rows is not None else rows, mode))
                if mode == 'known-image-failure':
                    return fakes[-1].response(stderr=b'image not available in synthetic fixture', code=1)
            return fakes[-1](argv, deadline)
        return call, fakes

    def core_read(self, index):
        return completion(index, [call('read-' + str(index), 'repo_read', {'paths': ['core.py', 'contract.json']})])

    def core_patch(self, index, previous, text):
        return completion(index, [call('patch-' + str(index), 'repo_patch', {'operations': [
            {'path': 'core.py', 'old_sha256': sha(previous.encode()), 'new_text': text}]})])

    def language_feedback_task(self, public=True):
        self.semantic_task()
        source = 'def transform(value):\n    return isinstance(value, int)\n'
        public_text = canonical({'language': {'version': 'bounded-ast-behavior-v1',
            'builtins': ['len', 'str', 'int', 'bool', 'abs']}}).decode() if public else '{}\n'
        self.task['initial_files'].update({'core.py': source, 'contract.json': public_text})
        self.task['behavior_contract']['protected_files']['contract.json'] = sha(public_text.encode())
        for name, text in self.task['initial_files'].items():
            (self.workspace / name).write_bytes(text.encode())

    def test_public_language_hint_native_view_preserves_negative_evidence_and_grade(self):
        from evolution import isolated_python as isolated
        self.language_feedback_task()
        payloads = []
        scripted = self.scripted([self.core_read(1), completion(2, [call('invalid-call', 'repo_validate', {})]),
            self.final(3, validation='failed')])
        def post(*args):
            payloads.append(json.loads(json.dumps(args[1])))
            return scripted(*args)
        with patch.object(lab, '_bounded_post', side_effect=post), \
                patch.object(isolated, '_capture', side_effect=AssertionError('VM failure cannot execute Docker')):
            result = self.enabled(tool_feedback_policy=lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)
        bad = result['tool_events'][1]['result']
        view = json.loads(payloads[2]['messages'][-1]['content'])
        hint = view.pop('public_language_hint')
        self.assertEqual(view, bad)
        self.assertEqual(hint['builtins'], ['len', 'str', 'int', 'bool', 'abs'])
        self.assertIn('does not identify the rejected callee', hint['calls'])
        self.assertNotIn('isinstance', json.dumps(hint))
        self.assert_negative_preserved(result, 2, bad)
        self.assertEqual(bad['execution']['status'], 'NOT_RUN_VM_FAILED')
        self.assertFalse(result['quality']['hard_pass'])
        self.assertEqual(result['usage']['total_tokens'], 45)
        self.assertTrue(all(row['tool_feedback_policy'] == lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY
            for row in self.before + self.after))
        entry = json.loads((self.artifacts / 'actor.started.json').read_bytes())
        self.assertEqual(entry['tool_feedback_policy'], lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)
        for path in (self.artifacts / 'requests').glob('*.receipt.json'):
            self.assertEqual(json.loads(path.read_bytes())['tool_feedback_policy'], lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)

    def test_public_language_hint_default_keeps_original_tool_message(self):
        self.language_feedback_task()
        steps = [self.core_read(1), completion(2, [call('invalid-call', 'repo_validate', {})]), self.final(3, validation='failed')]
        scripted = self.scripted(steps)
        contents = []
        def post(*args):
            if len(self.before) == 3:
                contents.append(args[1]['messages'][-1]['content'])
            return scripted(*args)
        with patch.object(lab, '_bounded_post', side_effect=post):
            result = self.enabled()
        self.assertEqual(contents, [canonical(result['tool_events'][1]['result']).decode()])
        self.assertNotIn('tool_feedback_policy', result)
        self.assertTrue(all('tool_feedback_policy' not in row for row in self.before + self.after))
        self.assertFalse(result['quality']['hard_pass'])

    def test_public_language_hint_absent_public_language_keeps_raw_feedback(self):
        self.language_feedback_task(public=False)
        scripted = self.scripted([self.core_read(1), completion(2, [call('invalid-call', 'repo_validate', {})]),
            self.final(3, validation='failed')])
        contents = []
        def post(*args):
            if len(self.before) == 3:
                contents.append(args[1]['messages'][-1]['content'])
            return scripted(*args)
        with patch.object(lab, '_bounded_post', side_effect=post):
            result = self.enabled(tool_feedback_policy=lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)
        self.assertEqual(contents, [canonical(result['tool_events'][1]['result']).decode()])
        self.assertFalse(result['quality']['hard_pass'])

    def test_public_language_hint_excludes_unverified_feedback_and_never_reads_probe_values(self):
        self.language_feedback_task()
        steps = [self.core_read(1), completion(2, [call('invalid-call', 'repo_validate', {})]), self.final(3, validation='failed')]
        with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)):
            result = self.enabled()
        event = result['tool_events'][1]
        bad = event['result']
        class UnreadableProbe(dict):
            def __getitem__(self, key):
                raise AssertionError('private probe read')
            def __iter__(self):
                raise AssertionError('private probe iterated')
        self.task['behavior_contract']['probes'] = [UnreadableProbe()]
        public = json.loads(self.task['initial_files']['contract.json'])
        public['language']['hidden_marker'] = 'private-marker-must-not-echo'
        self.task['initial_files']['contract.json'] = json.dumps(public)
        rendered = lab._model_tool_content('repo_validate', {}, bad, event, self.task,
            'docker-cpython-finite-v1', lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)
        self.assertIn('public_language_hint', rendered)
        self.assertNotIn('private-marker', rendered)
        self.assertNotIn('"expect"', rendered)
        variants = [dict(bad, write_state='partial-or-unverified'), dict(bad, failures=['protected-file-changed:contract.json']),
            dict(bad, diagnostics=[{'code': 'unregistered-call', 'path': 'core.py', 'probe': 0}]),
            dict(bad, diagnostics=[{'code': 'return-mismatch', 'path': 'core.py'}])]
        unknown = json.loads(json.dumps(bad))
        unknown['execution']['unknown'] = True
        variants.append(unknown)
        for item in variants:
            self.assertEqual(lab._model_tool_content('repo_validate', {}, item, event, self.task,
                'docker-cpython-finite-v1', lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY), canonical(item).decode())
        for public_text in ('{}', '{"language":{},"language":{}}', '{"language":{"version":"future"}}'):
            self.task['initial_files']['contract.json'] = public_text
            self.assertEqual(lab._model_tool_content('repo_validate', {}, bad, event, self.task,
                'docker-cpython-finite-v1', lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY), canonical(bad).decode())

    def test_public_language_hint_invalid_policy_refuses_before_key_artifacts_or_http(self):
        for value, backend in (('unknown', 'docker-cpython-finite-v1'), ([], 'docker-cpython-finite-v1'),
                (lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY, None)):
            with self.subTest(value=value), patch.object(lab, '_bounded_post') as post, self.assertRaises(ValueError):
                self.enabled(tool_feedback_policy=value, execution_backend=backend)
            post.assert_not_called()
            self.assertFalse(self.artifacts.exists())
            self.assertEqual((self.loaded, self.before, self.after), ([], [], []))


    def test_public_language_hint_namespaced_contract_native_roundtrip(self):
        self.language_feedback_task()
        public_path = 'upg_synthetic_90409_nonce_CONTRACT.json'
        text = self.task['initial_files'].pop('contract.json')
        self.task['initial_files'][public_path] = text
        self.task['required_read_paths'] = ['core.py', public_path]
        protected = self.task['behavior_contract']['protected_files']
        protected[public_path] = protected.pop('contract.json')
        (self.workspace / 'contract.json').unlink()
        (self.workspace / public_path).write_bytes(text.encode())
        scripted = self.scripted([completion(1, [call('namespace-read', 'repo_read', {'paths': ['core.py', public_path]})]),
            completion(2, [call('invalid-call', 'repo_validate', {})]), self.final(3, validation='failed')])
        contents = []
        def post(*args):
            if len(self.before) == 3:
                contents.append(args[1]['messages'][-1]['content'])
            return scripted(*args)
        with patch.object(lab, '_bounded_post', side_effect=post):
            result = self.enabled(tool_feedback_policy=lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)
        self.assertEqual(len(contents), 1)
        view = json.loads(contents[0])
        self.assertIn('public_language_hint', view)
        self.assertEqual(view.pop('public_language_hint')['builtins'], ['len', 'str', 'int', 'bool', 'abs'])
        self.assertEqual(view, result['tool_events'][1]['result'])
        self.assert_negative_preserved(result, 2, view)
        self.assertFalse(result['quality']['hard_pass'])
        self.assertEqual(result['usage']['total_tokens'], 45)

    def test_public_language_hint_multiple_contract_candidates_keep_raw(self):
        self.language_feedback_task()
        with patch.object(lab, '_bounded_post', side_effect=self.scripted([self.core_read(1),
                completion(2, [call('invalid-call', 'repo_validate', {})]), self.final(3, validation='failed')])):
            result = self.enabled()
        event = result['tool_events'][1]
        self.task['initial_files']['upg_synthetic_90409_nonce_CONTRACT.json'] = self.task['initial_files']['contract.json']
        self.assertEqual(lab._model_tool_content('repo_validate', {}, event['result'], event, self.task,
            'docker-cpython-finite-v1', lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY), canonical(event['result']).decode())


    def test_backend_selection_rejects_wrong_mode_or_profile_before_artifacts_key_or_http(self):
        from evolution.isolated_python import EXECUTION_BACKEND
        for backend, profile in ((False, lab.FLASH_THINKING_PROFILE), ('unknown', lab.FLASH_THINKING_PROFILE),
                (EXECUTION_BACKEND, None), (EXECUTION_BACKEND, lab.THINKING_PROFILE)):
            with self.subTest(backend=backend, profile=profile), self.assertRaises(ValueError):
                self.run_actor(model='deepseek-flash', thinking='enabled' if profile else 'disabled',
                    profile_id=profile, execution_backend=backend)
            self.assertFalse(self.artifacts.exists()); self.assertFalse(self.loaded)
            self.assertFalse(self.before); self.assertFalse(self.after)

    def test_document_only_native_flow_is_not_applicable_without_any_container_call(self):
        from evolution import isolated_python as isolated
        steps = self.ready() + [self.final(4)]
        with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)), \
                patch.object(isolated, '_capture', side_effect=AssertionError('no Python checks; no Docker')):
            result = self.enabled()
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        self.assertTrue(result['application_execution'])
        self.assertIn('not whole-application', result['application_execution_scope'])
        self.assertEqual(result['quality']['evidence_execution_backend'], isolated.EXECUTION_BACKEND)
        self.assertEqual(result['quality']['validation']['execution']['status'], 'NOT_APPLICABLE')
        self.assertFalse(result['execution_state_unknown']); self.assertFalse(result['execution_infrastructure_failed'])
        self.assertFalse(result['unknown_usage']); self.assertEqual(result['usage']['total_tokens'], 60)
        self.assertTrue(all(row['execution_backend'] == isolated.EXECUTION_BACKEND for row in self.before + self.after))
        self.assertEqual(list((self.artifacts / 'execution').iterdir()), [])

    def test_native_flow_and_final_quality_use_real_vm_bridge_and_host_assertions(self):
        from evolution import isolated_python as isolated
        self.semantic_task()
        old = self.task['initial_files']['core.py']; correct = 'def transform(value):\n    return value * 2\n'
        steps = [self.core_read(1), self.core_patch(2, old, correct), self.validate_and_status(3), self.final(4)]
        capture, fakes = self.capture(rows=[{'kind': 'return', 'value': 10}])
        payloads = []
        scripted = self.scripted(steps)
        def post(*args):
            payloads.append(json.loads(json.dumps(args[1])))
            return scripted(*args)
        with patch.object(lab, '_bounded_post', side_effect=post), patch.object(isolated, '_capture', side_effect=capture):
            result = self.enabled()
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        self.assertEqual(len(fakes), 2)  # Explicit repo_validate and independent final quality, same live backend.
        self.assertTrue(all(sum(argv[1] == 'create' for argv in fake.calls) == 1 for fake in fakes))
        self.assertEqual(result['quality']['validation']['execution']['status'], 'EXECUTED')
        self.assertFalse(result['execution_state_unknown']); self.assertFalse(result['execution_infrastructure_failed'])
        self.assertTrue(result['final_report_receipt_sha256'])
        tool = next(t['function'] for t in payloads[0]['tools'] if t['function']['name'] == 'repo_validate')
        self.assertIn('isolated CPython', tool['description'])
        self.assertEqual(len(payloads[0]['tools']), 6)
        for event in result['tool_events']:
            if event['tool'] == 'repo_validate':
                summary = event['result']['execution']
                self.assertEqual(set(summary), isolated.EXECUTION_SUMMARY_FIELDS)
                path = self.artifacts / 'execution' / summary['receipt_ref']
                self.assertEqual(sha(path.read_bytes()), summary['receipt_sha256'])
                self.assertFalse(set(summary) & {'results', 'expect', 'probes', 'args', 'kwargs'})
        serialized = json.dumps(payloads)
        self.assertNotIn('"invocations"', serialized); self.assertNotIn('"expect"', serialized)

    def test_vm_fail_is_recoverable_without_execution_then_real_repair_passes(self):
        from evolution import isolated_python as isolated
        self.semantic_task(); old = self.task['initial_files']['core.py']
        steps = [self.core_read(1), completion(2, [call('initial-validate', 'repo_validate', {})]),
            self.core_patch(3, old, 'def transform(value):\n    return value * 2\n'),
            self.validate_and_status(4), self.final(5)]
        capture, fakes = self.capture(rows=[{'kind': 'return', 'value': 10}])
        with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)), patch.object(isolated, '_capture', side_effect=capture):
            result = self.enabled()
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        self.assertEqual(result['tool_events'][1]['result']['execution']['status'], 'NOT_RUN_VM_FAILED')
        self.assertIsNone(result['tool_events'][1]['result']['execution']['receipt_ref'])
        self.assertEqual(len(fakes), 2)
        self.assertEqual(result['usage']['total_tokens'], 75)

    def test_native_finish_cannot_bypass_final_real_backend_host_assertions(self):
        from evolution import isolated_python as isolated
        self.semantic_task(); old = self.task['initial_files']['core.py']
        steps = [self.core_read(1), self.core_patch(2, old, 'def transform(value):\n    return value * 2\n'),
            self.validate_and_status(3), self.final(4)]
        capture, fakes = self.capture(rows=[{'kind': 'return', 'value': 9}], first_rows=[{'kind': 'return', 'value': 10}])
        with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)), patch.object(isolated, '_capture', side_effect=capture):
            result = self.enabled()
        self.assertTrue(result['final_report_receipt_sha256'])
        self.assertTrue(result['tool_events'][2]['result']['ok'])
        self.assertFalse(result['quality']['hard_pass'])
        self.assertFalse(result['quality']['validation']['ok'])
        self.assertEqual(result['quality']['validation']['execution']['status'], 'EXECUTED')
        self.assertEqual(len(fakes), 2)
        self.assertFalse(result['unknown_usage']); self.assertEqual(result['usage']['total_tokens'], 60)
        self.assertFalse(result['execution_state_unknown']); self.assertFalse(result['execution_infrastructure_failed'])

    def test_completed_host_mismatch_can_be_repaired_without_waiving_final_contract(self):
        from evolution import isolated_python as isolated
        self.semantic_task(); old = self.task['initial_files']['core.py']
        correct = 'def transform(value):\n    return value * 2\n'
        steps = [self.core_read(1), self.core_patch(2, old, correct),
            completion(3, [call('first-validation', 'repo_validate', {})]), self.core_read(4),
            self.core_patch(5, correct, 'def transform(value):\n    return value + value\n'),
            self.validate_and_status(6), self.final(7)]
        capture, fakes = self.capture(rows=[{'kind': 'return', 'value': 10}], first_rows=[{'kind': 'return', 'value': 9}])
        with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)), patch.object(isolated, '_capture', side_effect=capture):
            result = self.enabled()
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        failed = result['tool_events'][2]['result']
        self.assertFalse(failed['ok']); self.assertEqual(failed['execution']['status'], 'EXECUTED')
        self.assertTrue(failed['execution']['container_removed']); self.assertFalse(failed['execution']['unknown'])
        self.assertEqual(failed['diagnostics'], [{'code': 'behavior-contract-failed', 'path': 'core.py'}])
        self.assertEqual(len(fakes), 3)

    def test_infrastructure_unknown_stops_without_http_or_container_retry_and_preserves_known_api_cost(self):
        from evolution import isolated_python as isolated
        for mode in ('timeout', 'cleanup-unknown', 'known-image-failure'):
            with self.subTest(mode=mode):
                self.artifacts, self.before, self.after = self.base / ('infra-' + mode), [], []
                (self.workspace / 'target.txt').write_bytes(b'old\n')
                self.semantic_task(); old = self.task['initial_files']['core.py']
                steps = [self.core_read(1), self.core_patch(2, old, 'def transform(value):\n    return value * 2\n'),
                    self.validate_and_status(3)]
                capture, fakes = self.capture(rows=[{'kind': 'return', 'value': 10}], mode=mode)
                with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)) as post, \
                        patch.object(isolated, '_capture', side_effect=capture):
                    result = self.enabled()
                self.assertEqual(post.call_count, 3); self.assertEqual(len(fakes), 1)
                self.assertTrue(result['execution_infrastructure_failed'])
                self.assertEqual(result['execution_state_unknown'], mode != 'known-image-failure', result['quality']['validation']['execution'])
                self.assertFalse(result['unknown_usage']); self.assertEqual(result['usage']['total_tokens'], 45)
                self.assertEqual(result['known_usage']['total_tokens'], 45)
                self.assertTrue(all(row['unknown'] is False for row in self.after))
                self.assertFalse(result['quality']['hard_pass']); self.assertIsNone(result['final_report'])

    def test_execution_summary_rejects_extra_private_fields_bad_cleanup_or_wrong_snapshot(self):
        from evolution import isolated_python as isolated
        self.semantic_task()
        (self.workspace / 'core.py').write_text('def transform(value):\n    return value * 2\n', encoding='utf-8')
        broker = tool_broker.RepoBroker(self.workspace, self.task, self.git,
            execution_backend=isolated.EXECUTION_BACKEND, execution_artifacts=self.base / 'isolated-summary', deadline=lab.time.time() + 30)
        capture, _ = self.capture(rows=[{'kind': 'return', 'value': 10}])
        with patch.object(isolated, '_capture', side_effect=capture):
            result = broker.call('repo_validate', {})
        state = broker.events[-1]['state_sha256']
        self.assertIsNotNone(lab._execution_evidence(result, self.task, state))
        for change in ({'private_probes': [5]}, {'container_removed': False}, {'received_snapshot_sha256': '0' * 64},
                {'unknown': 0}, {'receipt_ref': '../private.json'}, {'platform': 'other'}, {'status': []}):
            altered = json.loads(json.dumps(result)); altered['execution'].update(change)
            self.assertIsNone(lab._execution_evidence(altered, self.task, state), change)

    def test_unknown_api_call_does_not_start_container_during_failure_grading(self):
        from evolution import isolated_python as isolated
        self.semantic_task(); old = self.task['initial_files']['core.py']
        steps = [self.core_read(1), self.core_patch(2, old, 'def transform(value):\n    return value * 2\n')]
        scripted = self.scripted(steps)
        def post(*args):
            if len(self.before) <= 2:
                return scripted(*args)
            raise lab.TransportFailure({'phase': 'deadline-wait', 'exception_class': None,
                'connection_attempted': None, 'http_dispatch': 'unknown'})
        with patch.object(lab, '_bounded_post', side_effect=post) as calls, \
                patch.object(isolated, '_capture', side_effect=AssertionError('no container after API uncertainty')) as capture:
            result = self.enabled()
        self.assertEqual(calls.call_count, 3); capture.assert_not_called()
        self.assertTrue(result['unknown_usage']); self.assertIsNone(result['usage'])
        self.assertEqual(result['known_usage']['total_tokens'], 30)
        self.assertFalse(result['quality']['hard_pass']); self.assertIsNone(result['quality']['validation'])
        self.assertEqual(result['quality']['final_execution_not_run_reason'], 'api-response-or-usage-uncertain')
        self.assertTrue((self.artifacts / 'requests/03.pending.json').exists())

    def test_unrecorded_patch_receipt_stops_before_new_validation_or_http_and_keeps_known_usage(self):
        from evolution import isolated_python as isolated
        self.semantic_task(); old = self.task['initial_files']['core.py']
        correct = 'def transform(value):\n    return value * 2\n'
        steps = [self.core_read(1), self.core_patch(2, old, correct)]
        write = lab._write_new
        def failing_receipt(path, *args, **kwargs):
            if Path(path).parent.name == 'tool-receipts' and Path(path).name == '02.json':
                raise OSError('synthetic tool receipt failure')
            return write(path, *args, **kwargs)
        with patch.object(lab, '_bounded_post', side_effect=self.scripted(steps)) as post, \
                patch.object(lab, '_write_new', side_effect=failing_receipt), \
                patch.object(isolated, '_capture', side_effect=AssertionError('no new validation after unrecorded write')) as capture:
            result = self.enabled()
        self.assertEqual(post.call_count, 2); capture.assert_not_called()
        self.assertEqual((self.workspace / 'core.py').read_text(encoding='utf-8'), correct)
        self.assertTrue(result['execution_state_unknown']); self.assertFalse(result['quality']['hard_pass'])
        self.assertIsNone(result['quality']['validation'])
        self.assertEqual(result['quality']['final_execution_not_run_reason'], 'execution-state-uncertain')
        self.assertFalse(result['unknown_usage']); self.assertEqual(result['usage']['total_tokens'], 30)
        self.assertTrue(all(row['unknown'] is False for row in self.after))
        self.assertFalse(any(event['tool'] == 'repo_validate' for event in result['tool_events']))


@unittest.skipUnless(SUPPORTED, "repository API helper tests require Python 3.10+")
class FlashThinkingProfileTests(_ProviderFixture, unittest.TestCase):
    def enabled(self, provider="deepseek", **kwargs):
        model = lab.FLASH_THINKING_PROFILE_SETTINGS[provider]["model"]
        return self.run_actor(provider=provider, model=model, profile_id=lab.FLASH_THINKING_PROFILE,
                              thinking="enabled", **kwargs)

    def test_none_backend_keeps_all24_pre_backend_request_payload_digests_and_result_fields(self):
        # Public fixture payloads captured before the opt-in backend change.
        # No ignored workspace, archived source or old implementation is loaded.
        expected = {
            ('deepseek', None): ['b6dd8419cb1419933c6acdb32a381335aed6bf64da4231219eea6c7f03c75ea8', 'c3d4f9ac774042d27b962a8c49f1871fa10ff28a7c78e5102c69584e0978e1de', '947701122b9a77deddd9d2b018c68dc638c1d1763eb66130959a0226cf8bb58f', '8cee1c094042c6a1580624d0c518b8d96d6a1879d693c7ef87fe2d50f34e4aa4'],
            ('deepseek', lab.THINKING_PROFILE): ['ae10aac09f252ce81a7a951c10f3fef9e3d43e3b5c9f4da772bdda34fb0038c7', '23c11987baacb3935c2fa1c0342758515dbf73ec5a12e6790775b8ace3d2c5c5', '801c4aed5e48fc6fc6537ff19bce19b3ea5221c8958d86a3d759e09157544e97', 'f5bbe2882c842595b0021470d9854b5e9234b3bd7e53454e0c3c73a56b1511d5'],
            ('mimo', None): ['2815534d970c7a6cc6b5f4de3daa4e952ca8daae7413bb9c3cfba3e624491049', '9e082724248a861477138259f8fdfb93dde4ced9c7133987d1a6e2f50d58aabe', '132d842e33904c7d86e449d22caa35c5d4ca4106a2b47e08a7b940d4aec012b2', '3e73fe1292bf56bbf591a64b9888c67dfbe857baa6e8c16bf2ff5e049bc2a0f6'],
            ('mimo', lab.THINKING_PROFILE): ['cb796da1dcab5cfdaad20298e4a468e8c52d8374770f866ac5b14ca2b012fa30', '6600a41f57c3559a4da10bda0926704c31d106366800b6b121555c613a4cf472', '3daad4ac19982f58de63e2b811b3e695323a611508f1fce1b535b35cddf3d805', '356226eac5a53ab9e21ad0ffc183197e7d6d8c1c90745c43d09c95b2d633d6ed'],
            ('mimo', lab.FLASH_THINKING_PROFILE): ['46f130c59f2f9326d46000e9c5e0ef6388e0b580f5ab2808e9b535260d1aceae', '1f7d5705481c899011b8f245fb9df19a4912c7df92bcd07cf1a711433ca0894f', '2121629c7d87661fac75c5e5e00b509ae9d04ec138cd277defc2a7ca520d25bc', '8ed9dc9a208f4f31d5b8699d8552aa14d1bcd561f98aaaab5a2b57b64d97b3bf']}
        expected[('deepseek', lab.FLASH_THINKING_PROFILE)] = expected[('deepseek', lab.THINKING_PROFILE)]
        for (provider, profile), hashes in expected.items():
            with self.subTest(provider=provider, profile=profile):
                self.artifacts, self.before, self.after = self.base / (provider + '-' + str(profile)), [], []
                (self.workspace / 'target.txt').write_bytes(b'old\n')
                settings = lab.profile_configuration(profile)['providers'][provider] if profile else None
                steps, captured = self.ready() + [self.final(4)], []
                def post(actual, payload, key, timeout):
                    captured.append(sha(canonical(payload)))
                    step = steps[len(self.before) - 1]
                    return 200, {}, canonical(step(payload) if callable(step) else step)
                with patch.object(lab, '_bounded_post', side_effect=post):
                    result = self.run_actor(provider=provider, model=settings['model'] if settings else 'mock-requested-model',
                        thinking='enabled' if profile else 'disabled', profile_id=profile, execution_backend=None)
                self.assertEqual(captured, hashes)
                self.assertTrue(result['quality']['hard_pass'])
                self.assertFalse(result['application_execution'])
                for item in [result, result['quality']] + self.before + self.after:
                    self.assertNotIn('execution_backend', item)
                    self.assertNotIn('execution_state_unknown', item)
                    self.assertNotIn('execution_infrastructure_failed', item)
                    self.assertNotIn('evidence_execution_backend', item)

    def test_explicit_configuration_and_currency_prices_are_independent_copies(self):
        flash = lab.profile_configuration(lab.FLASH_THINKING_PROFILE)
        pro = lab.profile_configuration(lab.THINKING_PROFILE)
        self.assertEqual(flash["providers"]["mimo"], {"model": "mimo-v2.6-flash", "thinking": "enabled",
            "output_cap": 8192, "reasoning_effort": None})
        self.assertEqual(flash["providers"]["deepseek"], pro["providers"]["deepseek"])
        self.assertEqual(flash["prices"]["mimo"], {
            "CNY": {"input_hit": ".02", "input_miss": "1", "output": "2"},
            "USD": {"input_hit": ".0028", "input_miss": ".14", "output": ".28"}})
        self.assertIn("peak-rate estimate", flash["price_evidence"]["basis"])
        self.assertEqual(flash["price_evidence"]["mimo_flash"], "https://mimo.mi.com/models/en-US/mimo-v2.6-flash")
        self.assertEqual(pro["prices"]["mimo"]["CNY"], {"input_hit": ".025", "input_miss": "3", "output": "6"})
        flash["providers"]["mimo"]["model"] = "mutated"
        flash["prices"]["mimo"]["CNY"]["output"] = "0"
        fresh = lab.profile_configuration(lab.FLASH_THINKING_PROFILE)
        self.assertEqual(fresh["providers"]["mimo"]["model"], "mimo-v2.6-flash")
        self.assertEqual(fresh["prices"]["mimo"]["CNY"]["output"], "2")
        self.assertEqual(lab.THINKING_PROFILE_SETTINGS["mimo"]["model"], "mimo-v2.6-pro")
        for invalid in (None, [], "unknown"):
            with self.assertRaises(ValueError):
                lab.profile_configuration(invalid)

    def test_new_profile_exact_payload_and_opaque_reasoning_for_both_providers(self):
        for provider in ("deepseek", "mimo"):
            (self.workspace / "target.txt").write_bytes(b"old\n")
            self.artifacts, self.before, self.after = self.base / ("flash-" + provider), [], []
            steps, observed = self.ready() + [self.final(4)], []
            def post(actual, payload, key, timeout):
                index = len(self.before)
                self.assertEqual(actual, provider)
                expected = {"model", "messages", "tools", "tool_choice", "stream", "thinking",
                    "max_tokens" if provider == "deepseek" else "max_completion_tokens"}
                if provider == "deepseek":
                    expected.add("reasoning_effort")
                    self.assertEqual(payload["reasoning_effort"], "low")
                self.assertEqual(set(payload), expected)
                self.assertEqual(payload["model"], lab.FLASH_THINKING_PROFILE_SETTINGS[provider]["model"])
                self.assertEqual(payload["thinking"], {"type": "enabled"})
                self.assertEqual(payload["max_tokens" if provider == "deepseek" else "max_completion_tokens"], 8192)
                self.assertEqual([m["reasoning_content"] for m in payload["messages"] if m["role"] == "assistant"], observed)
                step = steps[index - 1]
                response = step(payload) if callable(step) else step
                opaque = "opaque Ω Flash field " + str(index)
                response["choices"][0]["message"]["reasoning_content"] = opaque
                observed.append(opaque)
                return 200, {}, canonical(response)
            with patch.object(lab, "_post", side_effect=post):
                result = self.enabled(provider)
            self.assertTrue(result["quality"]["hard_pass"], result["quality"])
            identity = sha(canonical(lab.profile_configuration(lab.FLASH_THINKING_PROFILE)))
            self.assertEqual(result["profile_configuration_sha256"], identity)
            self.assertTrue(all(item["profile_configuration_sha256"] == identity for item in self.before + self.after))
            self.assertTrue(all("deadline_telemetry" in item for item in self.after))
            self.assertNotIn("opaque Ω Flash", json.dumps(result, ensure_ascii=False))

    def test_existing_profiles_keep_wire_fields_and_outcome_metadata_shape(self):
        common = {"request_id", "request_index", "provider", "model_requested", "input_utf8_bytes",
                  "request_payload_sha256", "output_cap", "input_task_sha256", "adapter"}
        outcome = {"dispatched", "not_invoked", "transport", "usage", "unknown", "unexpected_overrun",
                   "response_sha256", "model_reported", "api_response_id", "elapsed_seconds", "error_type", "receipt_sha256"}
        observed_messages, observed_tools = None, None
        for provider in ("deepseek", "mimo"):
            for profile in (None, lab.THINKING_PROFILE):
                self.artifacts, self.before, self.after = self.base / (provider + "-" + str(profile)), [], []
                settings = lab.THINKING_PROFILE_SETTINGS[provider] if profile else None
                model = settings["model"] if settings else "mock-requested-model"
                captured = []
                def post(actual, payload, key, timeout):
                    captured.append(payload)
                    return 200, {}, canonical(self.read(1))
                with patch.object(lab, "_bounded_post", side_effect=post):
                    result = self.run_actor(provider=provider, model=model, profile_id=profile,
                        thinking="enabled" if profile else "disabled", max_requests=1)
                wire = captured[0]
                expected = {"model", "messages", "tools", "tool_choice", "stream", "thinking",
                            "max_tokens" if provider == "deepseek" else "max_completion_tokens"}
                if profile and provider == "deepseek":
                    expected.add("reasoning_effort")
                    self.assertEqual(wire["reasoning_effort"], "low")
                self.assertEqual(set(wire), expected)
                self.assertEqual((wire["model"], wire["thinking"], wire["tool_choice"], wire["stream"]),
                    (model, {"type": "enabled" if profile else "disabled"}, "auto", False))
                self.assertEqual(wire["max_tokens" if provider == "deepseek" else "max_completion_tokens"], 8192 if profile else 4096)
                if observed_messages is None:
                    observed_messages, observed_tools = wire["messages"], wire["tools"]
                self.assertEqual(wire["messages"], observed_messages)
                self.assertEqual(wire["tools"], observed_tools)
                fields = common | ({"profile_id", "thinking", "reasoning_effort_requested"} if profile else set())
                self.assertEqual(set(self.before[0]), fields)
                self.assertEqual(set(self.after[0]), fields | outcome)
                self.assertNotIn("profile_configuration_sha256", result)
                self.assertNotIn("deadline_telemetry_schema", result)

    def test_precise_wait_argument_and_actor_clock_are_persisted_without_extra_payload(self):
        current = [100.0]
        original = self.reserve
        def reserve(metadata):
            current[0] += 2
            return original(metadata)
        self.reserve = reserve
        steps = self.ready() + [self.final(4)]
        actual_timeouts = []
        def post(provider, payload, key, timeout):
            index = len(self.before)
            actual_timeouts.append(timeout)
            current[0] += 3
            step = steps[index - 1]
            return 200, {}, canonical(step(payload) if callable(step) else step)
        with patch.object(lab.time, "perf_counter", side_effect=lambda: current[0]), patch.object(lab, "_bounded_post", side_effect=post):
            result = self.enabled()
        self.assertTrue(result["quality"]["hard_pass"], result["quality"])
        self.assertEqual(actual_timeouts, [178, 173, 168, 163])
        for index, item in enumerate(self.after, 1):
            timing = item["deadline_telemetry"]
            self.assertEqual(timing, {"schema_version": lab.DEADLINE_TELEMETRY_SCHEMA, "actor_timeout_seconds": 180,
                "actor_elapsed_before_bounded_post_seconds": 5 * index - 3,
                "bounded_post_timeout_seconds": actual_timeouts[index - 1],
                "actor_elapsed_after_bounded_post_seconds": 5 * index})
            receipt = json.loads((self.artifacts / ("requests/%02d.receipt.json" % index)).read_bytes())
            self.assertEqual(receipt["deadline_telemetry"], timing)
            pending = json.loads((self.artifacts / ("requests/%02d.response.json" % index)).read_bytes())
            self.assertNotIn("deadline_telemetry", pending["response"])

    def test_timeout_and_owner_interrupt_record_wait_budget_and_never_retry(self):
        for mode in ("timeout", "interrupt"):
            self.artifacts, self.before, self.after = self.base / mode, [], []
            current = [100.0]
            original = _ProviderFixture.reserve.__get__(self)
            def reserve(metadata):
                current[0] += 7
                return original(metadata)
            self.reserve = reserve
            def fail(provider, payload, key, timeout):
                self.assertEqual(timeout, 173)
                current[0] += 173 if mode == "timeout" else 5
                if mode == "interrupt":
                    raise KeyboardInterrupt
                raise lab.TransportFailure({"phase": "deadline-wait", "exception_class": None,
                    "connection_attempted": None, "http_dispatch": "unknown"})
            with patch.object(lab.time, "perf_counter", side_effect=lambda: current[0]), patch.object(lab, "_bounded_post", side_effect=fail) as post:
                result = self.enabled()
            self.assertEqual(post.call_count, 1)
            self.assertTrue(result["unknown_usage"])
            self.assertIsNone(result["usage"])
            self.assertIsNone(result["known_usage"]["total_tokens"])
            timing = self.after[0]["deadline_telemetry"]
            self.assertEqual(timing["bounded_post_timeout_seconds"], 173)
            self.assertEqual(timing["actor_elapsed_before_bounded_post_seconds"], 7)
            self.assertEqual(timing["actor_elapsed_after_bounded_post_seconds"], 180 if mode == "timeout" else 12)
            self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
            self.assertEqual(self.after[0]["transport"]["phase"], "deadline-wait" if mode == "timeout" else "unobserved")
            self.assertFalse((self.artifacts / "requests/02.pending.json").exists())

    def test_empty_or_missing_usage_is_unknown_without_zero_cost_or_tool_execution(self):
        for index, missing in enumerate(("absent", None, {})):
            self.artifacts, self.before, self.after = self.base / ("no-usage-" + str(index)), [], []
            response = self.read(1)
            if missing == "absent":
                del response["usage"]
            else:
                response["usage"] = missing
            with patch.object(lab, "_bounded_post", return_value=(200, {}, canonical(response))) as post:
                result = self.enabled("mimo")
            self.assertEqual(post.call_count, 1)
            self.assertTrue(result["unknown_usage"])
            self.assertIsNone(result["known_usage"]["total_tokens"])
            self.assertIsNone(self.after[0]["usage"])
            self.assertEqual(result["tool_events"], [])
            self.assertTrue((self.artifacts / "requests/01.pending.json").exists())
            self.assertIn("deadline_telemetry", self.after[0])

    def test_flash_mismatch_is_precredential_and_never_falls_back_to_pro(self):
        base = {"provider": "mimo", "model": "mimo-v2.6-flash", "profile_id": lab.FLASH_THINKING_PROFILE,
                "thinking": "enabled", "response_json_mode": False}
        for change in ({"model": "mimo-v2.6-pro"}, {"thinking": "disabled"}, {"response_json_mode": True}, {"profile_id": "unknown"}):
            with patch.object(lab, "_bounded_post") as post, self.assertRaises(ValueError):
                self.run_actor(**dict(base, **change))
            post.assert_not_called()
        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
        self.assertFalse(self.artifacts.exists())

    def test_flash_input_cap_and_reported_overrun_keep_original_safety_limits(self):
        with patch.object(lab, "_bounded_post") as post:
            result = self.enabled(system_context="x" * lab.MAX_INPUT_BYTES)
        post.assert_not_called()
        self.assertEqual(result["status"], "input-byte-cap-not-invoked")
        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
        self.artifacts = self.base / "overrun"
        response = self.read(1)
        response["usage"].update(completion_tokens=8193, total_tokens=8203,
            completion_tokens_details={"reasoning_tokens": 8192})
        with patch.object(lab, "_bounded_post", return_value=(200, {}, canonical(response))) as post:
            result = self.enabled()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "unexpected-overrun-blocked")
        self.assertEqual(result["known_usage"]["total_tokens"], 8203)
        self.assertEqual(result["tool_events"], [])
        self.assertIn("deadline_telemetry", self.after[0])


@unittest.skipUnless(SUPPORTED, "repository engine requires Python 3.10+")
class FlashDisabledConnectTests(_ProviderFixture, unittest.TestCase):
    def disabled(self, provider="deepseek", **kwargs):
        return self.run_actor(provider=provider,
            model=lab.FLASH_DISABLED_PROFILE_SETTINGS[provider]["model"],
            profile_id=lab.FLASH_DISABLED_PROFILE, thinking="disabled", **kwargs)

    def connect_failure(self, *, dispatch="not_started", phase="connect"):
        return lab.TransportFailure({"phase": phase, "exception_class": "TimeoutError",
            "connection_attempted": True, "http_dispatch": dispatch})

    def acknowledge(self, metadata):
        self.after.append(metadata)
        if metadata["not_invoked"]:
            return {"policy": "confirmed-pre-http-connect-once-v1", "connect_retry_authorized": True,
                "prior_request_id": metadata["request_id"], "prior_request_index": metadata["request_index"],
                "request_payload_sha256": metadata["request_payload_sha256"],
                "input_task_sha256": metadata["input_task_sha256"],
                "prior_receipt_sha256": metadata["receipt_sha256"]}

    def test_disabled_wire_and_nullable_reasoning_complete_the_same_task(self):
        for provider in ("deepseek", "mimo"):
            for nullable in (False, True):
                with self.subTest(provider=provider, nullable=nullable):
                    self.artifacts = self.base / (provider + "-nullable-" + str(nullable))
                    self.workspace = self.base / (provider + "-workspace-" + str(nullable))
                    self.workspace.mkdir()
                    for name, text in self.task["initial_files"].items():
                        (self.workspace / name).write_bytes(text.encode("utf-8"))
                    self.before, self.after = [], []
                    steps = self.ready() + [self.final(4)]
                    def post(actual, payload, key, timeout):
                        self.assertEqual(payload["thinking"], {"type": "disabled"})
                        self.assertNotIn("reasoning_effort", payload)
                        self.assertEqual(payload["max_tokens" if actual == "deepseek" else "max_completion_tokens"], 8192)
                        step = steps[len(self.before) - 1]
                        response = step(payload) if callable(step) else step
                        message = response["choices"][0]["message"]
                        if nullable:
                            message["reasoning_content"] = None
                        else:
                            message.pop("reasoning_content")
                        return 200, {}, canonical(response)
                    with patch.object(lab, "_bounded_post", side_effect=post):
                        result = self.disabled(provider, max_requests=4)
                    self.assertEqual(result["status"], "completed")
                    self.assertTrue(result["quality"]["hard_pass"])
                    self.assertEqual(result["quality"]["task_success"], 1)
                    self.assertEqual((self.workspace / "target.txt").read_text(), "fixed\n")

    def test_confirmed_connect_retry_uses_a_new_slot_same_payload_and_remaining_clock(self):
        now, payloads, timeouts = [100.0], [], []
        steps = self.ready() + [self.final(4)]
        self.account = self.acknowledge
        def post(provider, payload, key, timeout):
            payloads.append(canonical(payload)); timeouts.append(timeout)
            if len(payloads) == 1:
                now[0] += 21
                raise self.connect_failure()
            step = steps[len(payloads) - 2]
            return 200, {}, canonical(step(payload) if callable(step) else step)
        with patch.object(lab.time, "perf_counter", side_effect=lambda: now[0]), patch.object(lab, "_bounded_post", side_effect=post):
            result = self.disabled(max_requests=5, connect_retry_policy=lab.CONNECT_RETRY_POLICY)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(payloads[0], payloads[1])
        self.assertEqual(timeouts[:2], [180.0, 159.0])
        self.assertEqual([row["request_index"] for row in self.before], [1, 2, 3, 4, 5])
        self.assertNotEqual(self.before[0]["request_id"], self.before[1]["request_id"])
        self.assertEqual(self.before[1]["retry_of_request_id"], self.before[0]["request_id"])
        self.assertTrue(self.after[0]["not_invoked"])
        self.assertIsNone(self.after[0]["usage"])
        self.assertTrue((self.artifacts / "requests/01.receipt.json").is_file())
        self.assertTrue((self.artifacts / "requests/02.receipt.json").is_file())

    def test_no_outer_acknowledgement_means_no_retry(self):
        with patch.object(lab, "_bounded_post", side_effect=self.connect_failure()) as post:
            result = self.disabled(connect_retry_policy=lab.CONNECT_RETRY_POLICY)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result["status"], "transport-failed-not-invoked")
        self.assertFalse(result["unknown_usage"])

    def test_second_connect_failure_cannot_receive_a_third_attempt(self):
        self.account = self.acknowledge
        with patch.object(lab, "_bounded_post", side_effect=self.connect_failure()) as post:
            result = self.disabled(connect_retry_policy=lab.CONNECT_RETRY_POLICY)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(result["status"], "transport-failed-not-invoked")
        self.assertEqual(len(self.before), 2)

    def test_http_uncertainty_is_never_a_connect_retry(self):
        self.account = self.acknowledge
        with patch.object(lab, "_bounded_post", side_effect=self.connect_failure(dispatch="unknown", phase="http-request")) as post:
            result = self.disabled(connect_retry_policy=lab.CONNECT_RETRY_POLICY)
        self.assertEqual(post.call_count, 1)
        self.assertTrue(result["unknown_usage"])
        self.assertFalse(self.after[0]["not_invoked"])

    def test_old_profile_cannot_enable_the_new_retry_policy(self):
        with self.assertRaises(ValueError):
            self.run_actor(model="deepseek-flash", profile_id=lab.FLASH_THINKING_PROFILE,
                thinking="enabled", connect_retry_policy=lab.CONNECT_RETRY_POLICY)
        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
        self.assertFalse(self.artifacts.exists())


if __name__ == "__main__":
    unittest.main()
