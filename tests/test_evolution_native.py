"""Native adapter contracts; all model streams in these tests are synthetic."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
if sys.version_info >= (3, 10):
    from evolution import native_codex
    from evolution.contracts import digest
    from evolution.evaluator import canonical_source


def grade_task(request):
    correct = request["response_json"] == {"answer": 42}
    return {"hard": int(correct), "soft": float(correct),
            "loss": request["usage"]["total_tokens"] + 100 * request["wall_seconds"],
            "task_description": "synthetic contract task", "predicted_answer": request["response_json"],
            "fail_reason": None if correct else "incorrect response"}


def invalid_grader(request):
    return {"hard": 1, "soft": 1, "loss": float("nan")}


def stream(*, usage=True, tools=False, status=0, duplicate_turn=False):
    events = [{"type": "thread.started", "thread_id": "synthetic-cli-thread"},
              {"type": "turn.started"},
              {"type": "item.completed", "item": {"type": "agent_message", "text": '{"answer":42}'}}]
    if tools:
        events.append({"type": "item.completed", "item": {"type": "command_execution"}})
    if usage:
        event = {"type": "turn.completed", "usage": {"input_tokens": 50, "output_tokens": 7,
                                                       "cached_input_tokens": 20, "reasoning_output_tokens": 2}}
        events.append(event)
        if duplicate_turn:
            events.append(event)
    return subprocess.CompletedProcess([], status, ("\n".join(json.dumps(e) for e in events)).encode(), b"synthetic stderr")


@unittest.skipIf(sys.version_info < (3, 10), "optional native optimizer adapter requires Python 3.10+")
class NativeTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "eval-workspaces/tmp-native-tests"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="native-contract-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binary = self.root / "test-native-binary"
        self.binary.write_bytes(b"synthetic binary fixture; never executed")
        self.config = {"binary": str(self.binary), "model": "synthetic-native-model", "effort": "low",
                       "artifact_root": str(self.root / "artifacts"), "timeout_seconds": 10,
                       "grader": __name__ + ":grade_task"}
        self.service = native_codex.NativeCodex(self.config)

    def call(self, key="first"):
        return self.service._call(key=key, prompt="synthetic prompt", bindings={"kind": "test"})

    def request(self):
        source = canonical_source(ROOT)
        context = json.loads((ROOT / "tests/fixtures/governance_plan_cases.json").read_text(encoding="utf-8"))["cases"][0]["context"]
        return {"source": source, "source_sha256": digest(source), "candidate_id": "1" * 64,
                "model": self.config["model"], "task": {"id": "synthetic", "prompt": "Return JSON answer 42.",
                                                        "plan_context": context},
                "config": dict(self.service.binding(), campaign_id="synthetic-campaign"),
                "cache_key": "synthetic-cache-key", "attempt": 0,
                "execution_artifact": {"compiler": (ROOT / "compiler/compile_governance.py").read_text(encoding="utf-8"),
                                       "license": (ROOT / "LICENSE").read_text(encoding="utf-8")}}

    def native_only(self, value, commands):
        original = subprocess.run
        def dispatch(command, **kwargs):
            commands.append((command, kwargs))
            return value if command[0] == str(self.binary) else original(command, **kwargs)
        return dispatch

    def test_explicit_configuration_and_no_secret_fields(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "UPG_NATIVE_CONFIG"):
            native_codex.runner({})
        for changes in ({"api_key": "forbidden"}, {"binary": "relative"}, {"artifact_root": "relative"},
                        {"timeout_seconds": float("nan")}, {"effort": "invented"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                native_codex.NativeCodex(dict(self.config, **changes))

    def test_actual_stream_usage_and_idempotent_replay(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream()) as invoked:
            first = self.call()
            second = self.call()
        self.assertEqual(invoked.call_count, 1)
        self.assertEqual(first["usage"]["total_tokens"], 57)
        self.assertEqual(first["usage"]["cached_tokens"], 20)
        self.assertIsNone(first["usage"]["cost_usd"])
        self.assertTrue(second["receipt"]["replayed_from_local_receipt"])
        self.assertEqual(first["receipt"]["cli_thread_id"], "synthetic-cli-thread")
        self.assertIsNone(first["receipt"]["provider_request_id"])
        self.assertIsNone(first["receipt"]["model_observed"])
        args = invoked.call_args.args[0]
        self.assertIn("--ephemeral", args)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertIn("features.shell_tool=false", args)
        self.assertIn('web_search="disabled"', args)
        self.assertIn("hide_agent_reasoning=true", args)
        self.assertEqual(first["receipt"]["adapter_retries"], 0)
        self.assertFalse(first["receipt"]["provider_retry_configuration_verified"])
        self.assertEqual(invoked.call_args.kwargs["input"], b"synthetic prompt")

    def test_binding_is_read_only_and_identifies_config_binary_and_grader(self):
        binding = self.service.binding()
        self.assertEqual(binding["native_config_sha256"], self.service.config_sha256)
        self.assertEqual(binding["grader"]["reference"], self.config["grader"])
        self.assertEqual(len(binding["grader"]["source_sha256"]), 64)
        self.assertFalse(self.service.artifacts.exists())
        self.binary.write_bytes(b"changed binary fixture")
        with self.assertRaisesRegex(ValueError, "binary changed"):
            self.service.binding()

    def test_missing_or_changed_frozen_runner_config_never_dispatches(self):
        request = self.request()
        variants = [dict(request, config=None), dict(request, config={}),
                    dict(request, config=dict(request["config"], native_config_sha256="0" * 64)),
                    dict(request, config=dict(request["config"], grader={"reference": "changed:grader"})),
                    dict(request, config=dict(request["config"], campaign_id="")),
                    dict(request, task=dict(request["task"], id=""))]
        for variant in variants:
            with self.subTest(config=variant.get("config")), patch.object(native_codex.subprocess, "run") as invoked:
                with self.assertRaises(ValueError):
                    self.service.runner(variant)
                invoked.assert_not_called()
        self.service = native_codex.NativeCodex(dict(self.config, effort="medium"))
        with patch.object(native_codex.subprocess, "run") as invoked:
            with self.assertRaisesRegex(ValueError, "frozen native"):
                self.service.runner(request)
            invoked.assert_not_called()

    def test_artifact_root_freezes_backend_config_and_grader(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream()) as invoked:
            self.service.backend(system="system", user="first", max_completion_tokens=40)
            changed = native_codex.NativeCodex(dict(self.config, effort="medium"))
            with self.assertRaisesRegex(ValueError, "different capability"):
                changed.backend(system="system", user="second", max_completion_tokens=40)
            grader, identity = native_codex._grader(self.config["grader"])
            identity["source_sha256"] = "0" * 64
            with patch.object(native_codex, "_grader", return_value=(grader, identity)):
                with self.assertRaisesRegex(ValueError, "different capability"):
                    self.service.backend(system="system", user="third", max_completion_tokens=40)
        self.assertEqual(invoked.call_count, 1)

    def test_unknown_usage_halts_other_keys_without_replay(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream(usage=False)) as invoked:
            with self.assertRaises(native_codex.NativeCallError):
                self.call()
            with self.assertRaises(native_codex.NativeCallPending):
                self.call("different")
        self.assertEqual(invoked.call_count, 1)
        self.assertTrue((self.service.artifacts / "UNKNOWN_CALL.json").is_file())

    def test_timeout_partial_raw_bytes_and_unknown_fence(self):
        error = subprocess.TimeoutExpired("synthetic", 10, output=b'{"type":"turn.started"}\n', stderr=b"partial")
        with patch.object(native_codex.subprocess, "run", side_effect=error):
            with self.assertRaises(native_codex.NativeCallError) as failure:
                self.call()
        self.assertIsNone(failure.exception.usage)
        raw = list((self.service.artifacts / "calls").glob("*/stderr.raw"))[0]
        self.assertEqual(raw.read_bytes(), b"partial")

    def test_abrupt_interruption_is_fenced(self):
        with patch.object(native_codex.subprocess, "run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.call()
        with self.assertRaises(native_codex.NativeCallPending):
            self.call("other")

    def test_crashed_pending_call_blocks_new_key(self):
        previous = self.service.artifacts / "calls/unfinished"
        previous.mkdir(parents=True)
        (previous / "pending.json").write_text("{}")
        with patch.object(native_codex.subprocess, "run") as invoked:
            with self.assertRaises(native_codex.NativeCallPending):
                self.call("new")
        invoked.assert_not_called()

    def test_known_failure_retains_charge_and_does_not_retry(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream(status=1)) as invoked:
            for unused in range(2):
                with self.assertRaises(native_codex.NativeCallError) as failure:
                    self.call()
                self.assertEqual(failure.exception.usage["total_tokens"], 57)
        self.assertEqual(invoked.call_count, 1)

    def test_forbidden_tools_are_charged_and_rejected(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream(tools=True)):
            with self.assertRaises(native_codex.NativeCallError) as failure:
                self.call()
        self.assertEqual(failure.exception.usage["total_tokens"], 57)
        self.assertEqual(failure.exception.provider_receipt["tool_calls"], 1)

    def test_tampered_replay_artifact_never_dispatches(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream()):
            self.call()
        raw = list((self.service.artifacts / "calls").glob("*/stdout.raw"))[0]
        raw.write_bytes(b"tampered")
        with patch.object(native_codex.subprocess, "run") as invoked:
            with self.assertRaises(native_codex.NativeCallPending):
                self.call()
        invoked.assert_not_called()

    def test_duplicate_usage_turns_are_unknown(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream(duplicate_turn=True)):
            with self.assertRaises(native_codex.NativeCallError) as failure:
                self.call()
        self.assertIsNone(failure.exception.usage)

    def test_backend_preserves_raw_stage_response_and_usage(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream()) as invoked:
            text, usage = self.service.backend(system="system", user="user", max_completion_tokens=40, stage="reflect")
        self.assertEqual(text, '{"answer":42}')
        self.assertEqual(usage["total_tokens"], 57)
        self.assertEqual(usage["native_receipt"]["bindings"]["stage"], "reflect")
        self.assertIn(b'"stage":"reflect"', invoked.call_args.kwargs["input"])

    def test_equal_learning_prompts_in_separate_arms_are_new_calls(self):
        with patch.object(native_codex.subprocess, "run", return_value=stream()) as invoked:
            first = self.service.backend(system="system", user="user", max_completion_tokens=40, stage="clip")
            second = self.service.backend(system="system", user="user", max_completion_tokens=40, stage="clip")
        self.assertEqual(invoked.call_count, 2)
        self.assertNotEqual(first[1]["native_receipt"]["bindings"]["invocation_id"],
                            second[1]["native_receipt"]["bindings"]["invocation_id"])

    def test_runner_compiles_exact_candidate_source_and_supplies_plan(self):
        request = self.request()
        request["source"]["templates/SKILL.template.md"] += "\nEXACT-CANDIDATE-MARKER\n"
        request["source_sha256"] = digest(request["source"])
        commands = []
        with patch.object(native_codex.subprocess, "run", side_effect=self.native_only(stream(), commands)):
            result = self.service.runner(request)
        self.assertEqual(result["outcome"]["hard"], 1)
        self.assertEqual(result["usage"]["total_tokens"], 57)
        prompt = next(kwargs["input"] for command, kwargs in commands if command[0] == str(self.binary))
        self.assertIn(b"EXACT-CANDIDATE-MARKER", prompt)
        self.assertIn(b"governance_plan", prompt)
        self.assertEqual(result["provider_receipt"]["bindings"]["source_sha256"], request["source_sha256"])

    def test_campaign_and_sample_ids_dispatch_independent_calls(self):
        request = self.request()
        another_sample = copy.deepcopy(request)
        another_sample["task"]["id"] = "synthetic-independent-repeat"
        another_campaign = copy.deepcopy(request)
        another_campaign["config"]["campaign_id"] = "second-campaign"
        commands = []
        with patch.object(native_codex.subprocess, "run", side_effect=self.native_only(stream(), commands)):
            first = self.service.runner(request)
            replay = self.service.runner(request)
            second = self.service.runner(another_sample)
            third = self.service.runner(another_campaign)
        self.assertEqual(sum(command[0] == str(self.binary) for command, unused in commands), 3)
        self.assertTrue(replay["provider_receipt"]["replayed_from_local_receipt"])
        request_ids = {row["provider_receipt"]["harness_request_id"] for row in (first, second, third)}
        self.assertEqual(len(request_ids), 3)
        self.assertEqual(second["provider_receipt"]["bindings"]["sample_id"], another_sample["task"]["id"])
        self.assertEqual(third["provider_receipt"]["bindings"]["campaign_id"], "second-campaign")

    def test_historical_runtime_is_used_exactly_without_recompilation(self):
        request = self.request()
        request["execution_artifact"]["compiler"] = "raise AssertionError('historical compiler must not run')"
        request["execution_artifact"]["runtime"] = {
            p.relative_to(ROOT / "universal-project-governance").as_posix(): p.read_text(encoding="utf-8")
            for p in (ROOT / "universal-project-governance").rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}}
        request["execution_artifact"]["runtime"]["SKILL.md"] = "EXACT-HISTORICAL-SKILL"
        commands = []
        with patch.object(native_codex.subprocess, "run", side_effect=self.native_only(stream(), commands)):
            self.service.runner(request)
        self.assertFalse(any("--write" in command for command, unused in commands))
        prompt = next(kwargs["input"] for command, kwargs in commands if command[0] == str(self.binary))
        self.assertIn(b"EXACT-HISTORICAL-SKILL", prompt)

    def test_invalid_source_hash_and_unregistered_grader_do_not_dispatch(self):
        request = self.request()
        for variant in (dict(request, source_sha256="0" * 64),
                        dict(request, task=dict(request["task"], grader="other:grader"))):
            with patch.object(native_codex.subprocess, "run") as invoked:
                with self.assertRaises(ValueError):
                    self.service.runner(variant)
            invoked.assert_not_called()

    def test_invalid_grader_does_not_lose_real_charge(self):
        self.service = native_codex.NativeCodex(dict(self.config, grader=__name__ + ":invalid_grader"))
        commands = []
        with patch.object(native_codex.subprocess, "run", side_effect=self.native_only(stream(), commands)):
            with self.assertRaises(native_codex.NativeCallError) as failure:
                self.service.runner(self.request())
        self.assertEqual(failure.exception.usage["total_tokens"], 57)
        self.assertEqual(failure.exception.provider_receipt["receipt_type"], "codex_cli_thread")

    def test_source_path_escape_is_rejected_before_execution(self):
        with self.assertRaises(ValueError):
            native_codex._text_files(self.root / "source", {"../escape": "forbidden"})
        self.assertFalse((self.root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
