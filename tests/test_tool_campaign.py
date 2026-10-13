"""Collector inference, provenance and interruption tests; no model calls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
if sys.version_info >= (3, 10):
    from evolution import tool_campaign
    from evolution.contracts import digest


@unittest.skipIf(sys.version_info < (3, 10), "optional real-tool campaign requires Python 3.10+")
class CampaignTests(unittest.TestCase):
    def setUp(self):
        temporary_root = ROOT / "eval-workspaces/tmp-tool-campaign-tests"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="campaign-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "run.json"
        self.tasks = {"a": {"id": "a", "family": "json", "prompt": "Synthetic task a", "checks": ["PRIVATE-CHECK"]},
                      "b": {"id": "b", "family": "python", "prompt": "Synthetic task b", "checks": ["PRIVATE-CHECK"]}}
        self.configs = {model: {"model": model} for model in ("synthetic-model-1", "synthetic-model-2")}
        condition = {"skill": "synthetic skill", "plan_text": {key: '{\n "version": "synthetic"\n}\n' for key in self.tasks},
                     "source_sha256": "1" * 64, "runtime_sha256": "2" * 64, "candidate_sha256": "3" * 64}
        self.protocol = {"protocol_id": "synthetic-contract-protocol", "stage": "development", "seed": 19012,
                         "models": list(self.configs), "task_ids": list(self.tasks), "task_manifest_sha256": digest(self.tasks),
                         "baseline_revision": "4" * 40,
                         "conditions": {"control": copy.deepcopy(condition), "treatment": copy.deepcopy(condition)},
                         "budget": {"model_calls": 8, "tokens": 1000, "wall_seconds": 120}}
        self.protocol["conditions"]["treatment"]["source_sha256"] = "5" * 64
        self.calls = []
        self.behavior = None
        outer = self
        class FakeToolCodex:
            def __init__(self, config):
                self.config = config
            def binding(self):
                return {"synthetic_capability": digest(self.config)}
            def run(self, task, *, prompt, bindings):
                checkpoint = json.loads(outer.output.read_text())
                outer.assertIsNotNone(checkpoint["pending"])
                outer.assertEqual(checkpoint["pending"]["sample_id"], bindings["sample_id"])
                outer.assertEqual(checkpoint["pending"]["prompt_sha256"], hashlib.sha256(prompt.encode("utf-8")).hexdigest())
                outer.assertNotIn("PRIVATE-CHECK", prompt)
                outer.calls.append((task, prompt, bindings))
                if outer.behavior:
                    return outer.behavior(task, prompt, bindings)
                result = outer.result(bindings)
                result["receipt"]["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                return result
        self.service_patch = patch("evolution.tool_codex.ToolCodex", FakeToolCodex)
        self.service_patch.start()
        self.addCleanup(self.service_patch.stop)
        self.engine_patch = patch.object(tool_campaign, "engine_identity", return_value="6" * 64)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)

    def result(self, bindings, *, replay=False, quality=True):
        treatment = bindings["source_sha256"] == "5" * 64
        return {"status": "completed", "usage": {"input_tokens": 30 if treatment else 40, "output_tokens": 10,
                                                   "total_tokens": 40 if treatment else 50, "cached_input_tokens": 5,
                                                   "reasoning_output_tokens": 2},
                "wall_seconds": 4 if treatment else 5,
                "timing": {"cli_seconds": 3 if treatment else 4},
                "quality": {"hard_pass": quality, "task_success": int(quality), "scope_ok": True, "required_tools_ok": True},
                "tool_events": [1, 2, 3, 4], "final_response_text": "synthetic final text",
                "receipt": {"receipt_sha256": digest(bindings), "replayed_from_local_receipt": replay,
                            "cli_thread_id": digest(bindings)[:12], "artifact_directory": "synthetic-local-artifact"}}

    def collect(self):
        return tool_campaign.collect(ROOT, self.protocol, self.tasks, self.configs, self.output)

    def no_tool_result(self, bindings, diagnostics, *, tampered=False):
        result = self.result(bindings, quality=False)
        result["tool_events"] = []
        result["quality"]["required_tools_ok"] = False
        result["quality"]["failures"] = ["required-current-real-tool-evidence-missing", "no-actual-repository-edit"]
        directory = Path(self.temporary.name) / digest(bindings)
        directory.mkdir(exist_ok=True)
        events = [{"type": "thread.started", "thread_id": result["receipt"]["cli_thread_id"]}]
        events.extend(diagnostics)
        events.append({"type": "turn.completed", "usage": {"input_tokens": result["usage"]["input_tokens"],
                                                            "output_tokens": result["usage"]["output_tokens"]}})
        payload = ("\n".join(json.dumps(event) for event in events) + "\n").encode("utf-8")
        (directory / "stdout.raw").write_bytes(payload + (b"tampered" if tampered else b""))
        result["receipt"].update(artifact_directory=str(directory),
                                 artifact_sha256={"stdout.raw": hashlib.sha256(payload).hexdigest()})
        return result

    @staticmethod
    def cli_error(message):
        return {"type": "item.completed", "item": {"type": "error", "message": message}}

    @staticmethod
    def mcp_approval_error():
        return {"type": "item.completed", "item": {"id": "synthetic-tool-call", "type": "mcp_tool_call",
                "server": "upg_repo", "tool": "repo_read", "arguments": {"paths": ["normalizer.py"]},
                "result": None, "error": {"message": "MCP tool call requires approval, but approval policy is never"},
                "status": "failed"}}

    def test_prompt_preserves_exact_planner_bytes_and_excludes_private_checks(self):
        plan = '{\n  "key": true\n}\n'
        prompt = tool_campaign.build_prompt("Skill", plan, "task")
        self.assertIn("\n" + plan + "\n</governance_plan>", prompt)
        self.assertIn("project_tool unavailable in bounded broker", prompt)
        self.assertIn("project_tool and persistent governance state are unavailable in this broker", prompt)
        self.assertIn("Do not probe unregistered/hidden paths.", prompt)
        self.assertNotIn("host receipt/project state fallback", prompt)
        for tool in ("repo_read", "repo_patch", "repo_validate", "repo_status"):
            self.assertIn(tool, prompt)
        self.assertNotIn("batch", prompt.lower())

    def test_collection_complete_budget_and_completed_resume_no_dispatch(self):
        run = self.collect()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["budget"]["calls"], 8)
        self.assertEqual(run["budget"]["total_tokens"], 360)
        self.assertEqual(len(run["observations"]), 8)
        self.assertTrue(all(row["usage"]["cached_tokens"] == 5 for row in run["observations"]))
        self.assertEqual(self.collect(), run)
        self.assertEqual(len(self.calls), 8)

    def test_prompt_hash_matches_exact_utf8_adapter_receipt(self):
        run = self.collect()
        for row, (task, prompt, bindings) in zip(run["observations"], self.calls):
            actual = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            self.assertEqual(row["prompt_sha256"], actual)
            self.assertEqual(row["result"]["receipt"]["prompt_sha256"], actual)
            self.assertNotEqual(row["prompt_sha256"], digest(prompt))

    def test_pair_order_deterministic_and_condition_order_balanced_per_model(self):
        run = self.collect()
        self.assertEqual(run["order"], tool_campaign._order(self.protocol["models"], self.protocol["task_ids"], 19012))
        for model in self.protocol["models"]:
            firsts = [row["condition"] for row in run["order"][::2] if row["model"] == model]
            self.assertEqual(sorted(firsts), ["control", "treatment"])
        for left, right in zip(run["order"][::2], run["order"][1::2]):
            self.assertEqual((left["model"], left["task_id"]), (right["model"], right["task_id"]))

    def test_legacy_order_without_stratification_preserves_frozen_bytes(self):
        run = self.collect()
        self.assertNotIn("order_stratification", run)
        # Captured from the pre-stratification implementation, not recomputed
        # from a duplicate of the sorting algorithm.
        self.assertEqual(digest(run["order"]), "5b6a80366adfe38cd28e285b3aae063fd87a0970e2efa49e1f8a2f2bbcbecd12")

    def test_family_order_balances_every_model_family_with_adjacent_unique_pairs(self):
        tasks = {"%s-%s" % (family, number): {"family": family}
                 for family in ("json", "python", "text", "toml", "recovery", "current-truth")
                 for number in range(2)}
        models, ids = self.protocol["models"], list(tasks)
        order = tool_campaign._family_order(models, ids, 19012, tasks)
        self.assertEqual(order, tool_campaign._family_order(models, ids, 19012, tasks))
        self.assertEqual(len(order), 48)
        self.assertEqual([row["sample_index"] for row in order], list(range(48)))
        self.assertEqual([(row["model"], row["task_id"]) for row in order[::2]],
                         [(row["model"], row["task_id"]) for row in tool_campaign._order(models, ids, 19012)[::2]])
        self.assertEqual({(row["model"], row["task_id"], row["condition"]) for row in order},
                         {(model, task, condition) for model in models for task in ids for condition in tool_campaign.CONDITIONS})
        for index, (left, right) in enumerate(zip(order[::2], order[1::2])):
            self.assertEqual((left["model"], left["task_id"], left["pair_index"]),
                             (right["model"], right["task_id"], right["pair_index"]))
            self.assertEqual(left["pair_index"], index)
            self.assertEqual({left["condition"], right["condition"]}, set(tool_campaign.CONDITIONS))
        for model in models:
            firsts = [row for row in order[::2] if row["model"] == model]
            self.assertEqual(sum(row["condition"] == "control" for row in firsts), 6)
            for family in {task["family"] for task in tasks.values()}:
                self.assertEqual(sorted(row["condition"] for row in firsts if tasks[row["task_id"]]["family"] == family),
                                 ["control", "treatment"])

    def test_family_order_seed_randomizes_initial_arm_and_odd_groups_alternate(self):
        tasks = {str(number): {"family": "odd"} for number in range(3)}
        first_arms = set()
        for seed in range(20):
            order = tool_campaign._family_order(["synthetic-model"], list(tasks), seed, tasks)
            firsts = [row["condition"] for row in order[::2]]
            self.assertNotEqual(firsts[0], firsts[1])
            self.assertEqual(firsts[0], firsts[2])
            first_arms.add(firsts[0])
        self.assertEqual(first_arms, set(tool_campaign.CONDITIONS))

    def test_family_order_opt_in_is_preregistered_and_resume_cannot_change_it(self):
        self.tasks["b"]["family"] = self.tasks["a"]["family"]
        self.protocol["task_manifest_sha256"] = digest(self.tasks)
        self.protocol["order_stratification"] = "model-task-family"
        run = self.collect()
        self.assertEqual(run["order_stratification"], "model-task-family")
        self.assertEqual(run["identities"]["protocol_sha256"], digest(self.protocol))
        self.assertEqual(run["order"], tool_campaign._family_order(self.protocol["models"], self.protocol["task_ids"], 19012, self.tasks))
        self.assertEqual(self.collect(), run)
        self.assertEqual(len(self.calls), 8)
        del self.protocol["order_stratification"]
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.collect()
        self.assertEqual(len(self.calls), 8)

    def test_unknown_or_wrong_type_order_stratification_rejected_before_calls(self):
        for value in (None, True, 0, [], {}, "", "model", "task-family"):
            with self.subTest(value=value):
                self.protocol["order_stratification"] = value
                with self.assertRaisesRegex(ValueError, "order_stratification"):
                    self.collect()
                self.assertFalse(self.output.exists())
                self.assertFalse(self.calls)

    def test_family_order_missing_or_invalid_family_rejected_before_calls(self):
        original = copy.deepcopy(self.tasks)
        self.protocol["order_stratification"] = "model-task-family"
        for value in (None, 7, [], "", "  "):
            with self.subTest(value=value):
                self.tasks = copy.deepcopy(original)
                if value is None:
                    del self.tasks["a"]["family"]
                else:
                    self.tasks["a"]["family"] = value
                self.protocol["task_manifest_sha256"] = digest(self.tasks)
                with self.assertRaisesRegex(ValueError, "famil"):
                    self.collect()
                self.assertFalse(self.output.exists())
                self.assertFalse(self.calls)

    def test_family_order_checkpoint_metadata_cannot_lose_opt_in(self):
        self.protocol["order_stratification"] = "model-task-family"
        run = self.collect()
        del run["order_stratification"]
        tool_campaign.save_run(self.output, run)
        with self.assertRaisesRegex(ValueError, "order stratification"):
            self.collect()
        self.assertEqual(len(self.calls), 8)

    def test_private_list_normalizes_to_preregistered_id_map(self):
        self.tasks = list(self.tasks.values())
        self.assertEqual(self.collect()["status"], "completed")

    def test_changed_manifest_config_protocol_capability_or_engine_rejected(self):
        self.collect()
        original = copy.deepcopy(self.protocol)
        self.protocol["seed"] += 1
        with self.assertRaises(ValueError):
            self.collect()
        self.protocol = original
        self.configs[self.protocol["models"][0]]["extra"] = "changed"
        with self.assertRaises(ValueError):
            self.collect()
        self.assertEqual(len(self.calls), 8)

    def test_manifest_mismatch_rejected_before_call(self):
        self.tasks["a"]["prompt"] = "changed"
        with self.assertRaisesRegex(ValueError, "manifest"):
            self.collect()
        self.assertFalse(self.calls)

    def test_preregistered_capabilities_match_without_extra_setup_or_binding(self):
        from evolution.tool_codex import ToolCodex
        expected = {model: {"synthetic_capability": digest(config)} for model, config in self.configs.items()}
        setups, bindings = [], []
        original_init, original_binding = ToolCodex.__init__, ToolCodex.binding
        def initialize(service, config):
            setups.append(config["model"])
            original_init(service, config)
        def binding(service):
            bindings.append(service.config["model"])
            return original_binding(service)
        with patch.object(ToolCodex, "__init__", initialize), patch.object(ToolCodex, "binding", binding):
            run = tool_campaign.collect(ROOT, self.protocol, self.tasks, self.configs, self.output,
                                        expected_capabilities=expected)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["capabilities"], expected)
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(sorted(setups), sorted(self.protocol["models"]))
        self.assertEqual(sorted(bindings), sorted(self.protocol["models"]))

    def test_effort_or_binary_config_change_after_freeze_stops_before_checkpoint(self):
        expected = {model: {"synthetic_capability": digest(config)} for model, config in self.configs.items()}
        original = copy.deepcopy(self.configs)
        for field, changed in (("effort", "high"), ("binary", "different-registered-cli")):
            self.configs = copy.deepcopy(original)
            self.configs[self.protocol["models"][0]][field] = changed
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "preregistered freeze"):
                tool_campaign.collect(ROOT, self.protocol, self.tasks, self.configs, self.output,
                                      expected_capabilities=expected)
            self.assertFalse(self.calls)
            self.assertFalse(self.output.exists())

    def test_actual_binary_or_typed_capability_drift_stops_before_checkpoint(self):
        from evolution.tool_codex import ToolCodex
        expected = {model: {"synthetic_capability": digest(config), "binary_sha256": "a" * 64,
                            "isolation_attested": False} for model, config in self.configs.items()}
        for changed in ({"binary_sha256": "b" * 64}, {"isolation_attested": 0}):
            def binding(service):
                return dict(expected[service.config["model"]], **changed)
            with self.subTest(changed=changed), patch.object(ToolCodex, "binding", binding), self.assertRaisesRegex(ValueError, "preregistered freeze"):
                tool_campaign.collect(ROOT, self.protocol, self.tasks, self.configs, self.output,
                                      expected_capabilities=expected)
            self.assertFalse(self.calls)
            self.assertFalse(self.output.exists())

    def test_abrupt_call_interruption_pending_blocks_restart(self):
        def interrupted(*args):
            raise KeyboardInterrupt
        self.behavior = interrupted
        with self.assertRaises(KeyboardInterrupt):
            self.collect()
        self.behavior = None
        with self.assertRaisesRegex(ValueError, "pending"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_unknown_usage_stops_without_retries(self):
        self.behavior = lambda task, prompt, bindings: dict(self.result(bindings), usage=None)
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertTrue(run["budget"]["unknown_usage"])
        self.assertIsNotNone(run["pending"])
        self.assertEqual(len(self.calls), 1)

    def test_exception_with_known_charge_still_stops_uncertain_dispatch(self):
        class Uncertain(RuntimeError):
            usage = {"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}
            provider_receipt = {"status": "post-dispatch-evidence-unconfirmed"}
        def uncertain(*args):
            raise Uncertain("synthetic uncertainty")
        self.behavior = uncertain
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertEqual(run["budget"]["total_tokens"], 40)
        self.assertEqual(len(self.calls), 1)

    def test_quality_failure_charged_and_cannot_pass(self):
        self.behavior = lambda task, prompt, bindings: self.result(bindings, quality=False)
        run = self.collect()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["budget"]["calls"], 8)
        self.assertFalse(run["summary"]["gates"]["all_task_quality_pass"])
        self.assertEqual(run["summary"]["net_benefit_gate"], "FAIL")

    def test_known_transport_failure_retains_charge_and_stops_without_resume_replay(self):
        message = ("Code Mode is unavailable because code-mode host is disabled. "
                   "Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.")
        diagnostics = [self.cli_error("Under-development features enabled: skip_host_skill_discovery."),
                       self.cli_error(message)]
        self.behavior = lambda task, prompt, bindings: self.no_tool_result(bindings, diagnostics)
        run = self.collect()
        self.assertEqual(run["status"], "blocked_transport")
        self.assertEqual(len(run["observations"]), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(run["budget"]["calls"], 1)
        self.assertEqual(run["budget"]["total_tokens"], run["observations"][0]["usage"]["total_tokens"])
        self.assertFalse(run["budget"]["unknown_usage"])
        self.assertIsNone(run["pending"])
        self.assertTrue(run["new_protocol_required"])
        self.assertEqual(run["transport_failure"]["code"], "code-mode-host-disabled")
        self.assertEqual(run["transport_failure"]["event_line"], 3)
        self.assertEqual(run["transport_failure"]["message"], message)
        self.assertEqual(run["transport_failure"]["stdout_sha256"],
                         run["observations"][0]["result"]["receipt"]["artifact_sha256"]["stdout.raw"])
        self.assertEqual(run["summary"]["net_benefit_gate"], "FAIL")
        self.assertFalse(run["summary"]["gates"]["complete_matched_collection"])
        self.assertFalse(run["summary"]["gates"]["all_task_quality_pass"])
        before = self.output.read_bytes()
        self.assertEqual(self.collect(), run)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(len(self.calls), 1)
        self.protocol["protocol_id"] += "-changed"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_startup_warning_with_no_tools_is_quality_failure_not_transport_stop(self):
        warning = self.cli_error("Under-development features enabled: skip_host_skill_discovery. Under-development features are incomplete.")
        self.behavior = lambda task, prompt, bindings: self.no_tool_result(bindings, [warning])
        run = self.collect()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(run["budget"]["total_tokens"], 360)
        self.assertIsNone(run["summary"]["transport_failure"])
        self.assertFalse(run["summary"]["gates"]["all_task_quality_pass"])

    def test_model_self_report_cannot_trigger_known_transport_guard(self):
        message = "Code Mode is unavailable because code-mode host is disabled."
        diagnostic = {"type": "item.completed", "item": {"type": "agent_message", "text": message}}
        def self_report(task, prompt, bindings):
            result = self.no_tool_result(bindings, [diagnostic])
            result["final_response_text"] = message
            return result
        self.behavior = self_report
        run = self.collect()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(run["summary"]["net_benefit_gate"], "FAIL")

    def test_tool_evidence_prevents_transport_wide_classification(self):
        diagnostic = self.cli_error("Code Mode is unavailable because code-mode host is disabled.")
        def with_tools(task, prompt, bindings):
            result = self.no_tool_result(bindings, [diagnostic])
            result["tool_events"] = [1]
            return result
        self.behavior = with_tools
        run = self.collect()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(self.calls), 8)
        self.assertFalse(run["summary"]["gates"]["all_task_quality_pass"])

    def test_tampered_transport_evidence_retains_known_charge_and_fences_replay(self):
        diagnostic = self.cli_error("Code Mode is unavailable because code-mode host is disabled.")
        self.behavior = lambda task, prompt, bindings: self.no_tool_result(bindings, [diagnostic], tampered=True)
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertEqual(len(run["observations"]), 1)
        self.assertEqual(run["budget"]["calls"], 1)
        self.assertGreater(run["budget"]["total_tokens"], 0)
        self.assertTrue(run["transport_evidence_error"]["known_usage_retained"])
        self.assertEqual(run["pending"]["kind"], "transport-evidence-unconfirmed")
        self.assertNotIn("transport_failure", run)
        with self.assertRaisesRegex(ValueError, "pending"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_missing_transport_artifact_fails_closed_without_replay(self):
        def missing(task, prompt, bindings):
            result = self.result(bindings, quality=False)
            result["tool_events"] = []
            return result
        self.behavior = missing
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertEqual(run["budget"]["calls"], 1)
        self.assertGreater(run["budget"]["total_tokens"], 0)
        self.assertEqual(run["pending"]["kind"], "transport-evidence-unconfirmed")
        with self.assertRaisesRegex(ValueError, "pending"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_known_transport_failure_retains_also_measured_budget_overrun(self):
        diagnostic = self.cli_error("Code Mode is unavailable because code-mode host is disabled.")
        self.protocol["budget"]["tokens"] = 1
        self.behavior = lambda task, prompt, bindings: self.no_tool_result(bindings, [diagnostic])
        run = self.collect()
        self.assertEqual(run["status"], "blocked_transport")
        self.assertIn("tokens", run["actual_budget_overrun"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(run["summary"]["actual_charged_usage"], run["budget"])

    def test_terminal_summary_and_checkpoint_share_advancing_budget_snapshot(self):
        original_budget, original_save = tool_campaign.Budget, tool_campaign.save_run
        for blocked in (False, True):
            with self.subTest(blocked_transport=blocked):
                clock = [100.0]
                class ClockedBudget(original_budget):
                    def __init__(self, **values):
                        super().__init__(**values, _start=clock[0])
                def advancing_save(path, run):
                    original_save(path, run)
                    clock[0] += .25
                self.output = Path(self.temporary.name) / ("blocked.json" if blocked else "completed.json")
                self.calls.clear()
                self.behavior = (lambda task, prompt, bindings: self.no_tool_result(
                    bindings, [self.cli_error("Code Mode is unavailable because code-mode host is disabled.")])) if blocked else None
                with patch.object(tool_campaign, "Budget", ClockedBudget), \
                     patch("evolution.contracts.time.monotonic", side_effect=lambda: clock[0]), \
                     patch.object(tool_campaign, "save_run", side_effect=advancing_save):
                    run = self.collect()
                    expected_calls = 1 if blocked else 8
                    self.assertEqual(run["status"], "blocked_transport" if blocked else "completed")
                    self.assertGreater(run["budget"]["elapsed_seconds"], 0)
                    self.assertEqual(run["summary"]["actual_charged_usage"], run["budget"])
                    persisted = json.loads(self.output.read_text())
                    self.assertEqual(persisted["summary"]["actual_charged_usage"], persisted["budget"])
                    self.assertEqual(persisted["budget"], run["budget"])
                    self.assertEqual(tool_campaign.summarize(run, repetitions=10)["actual_charged_usage"], run["budget"])
                    self.assertEqual(self.collect(), run)
                    self.assertEqual(len(self.calls), expected_calls)

    def test_terminal_summary_time_crossing_retains_charge_and_blocks_benefit(self):
        original_budget, original_summary = tool_campaign.Budget, tool_campaign.summarize
        for blocked in (False, True):
            with self.subTest(blocked_transport=blocked):
                clock = [100.0]
                class ClockedBudget(original_budget):
                    def __init__(self, **values):
                        super().__init__(**values, _start=clock[0])
                def slow_summary(run):
                    summary = original_summary(run)
                    clock[0] = 221.0  # The real clock advances past the 120-second stop threshold.
                    return summary
                self.output = Path(self.temporary.name) / ("blocked-time.json" if blocked else "completed-time.json")
                self.calls.clear()
                self.behavior = (lambda task, prompt, bindings: self.no_tool_result(
                    bindings, [self.cli_error("Code Mode is unavailable because code-mode host is disabled.")])) if blocked else None
                with patch.object(tool_campaign, "Budget", ClockedBudget), \
                     patch("evolution.contracts.time.monotonic", side_effect=lambda: clock[0]), \
                     patch.object(tool_campaign, "summarize", side_effect=slow_summary):
                    run = self.collect()
                    self.assertEqual(run["status"], "blocked_transport" if blocked else "budget-exhausted")
                    self.assertEqual(run["actual_budget_overrun"]["wall_seconds"]["actual"], 121)
                    self.assertEqual(run["budget"]["calls"], 1 if blocked else 8)
                    self.assertEqual(run["budget"]["total_tokens"], sum(row["usage"]["total_tokens"] for row in run["observations"]))
                    self.assertFalse(run["budget"]["unknown_usage"])
                    self.assertIsNone(run["pending"])
                    self.assertEqual(run["summary"]["status"], run["status"])
                    self.assertEqual(run["summary"]["actual_charged_usage"], run["budget"])
                    self.assertFalse(run["summary"]["gates"]["complete_matched_collection"])
                    self.assertEqual(run["summary"]["net_benefit_gate"], "FAIL")
                    persisted = json.loads(self.output.read_text())
                    self.assertEqual(persisted, run)
                    self.assertEqual(self.collect(), run)
                    self.assertEqual(len(self.calls), 1 if blocked else 8)

    def test_registered_failed_mcp_approval_stops_after_known_charge_without_replay(self):
        diagnostic = self.mcp_approval_error()
        self.behavior = lambda task, prompt, bindings: self.no_tool_result(bindings, [diagnostic])
        run = self.collect()
        self.assertEqual(run["status"], "blocked_transport")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(run["budget"]["calls"], 1)
        self.assertEqual(run["budget"]["total_tokens"], run["observations"][0]["usage"]["total_tokens"])
        self.assertIsNone(run["pending"])
        self.assertTrue(run["new_protocol_required"])
        failure = run["transport_failure"]
        self.assertEqual(failure["code"], "registered-mcp-approval-policy-never")
        self.assertEqual(failure["server"], "upg_repo")
        self.assertEqual(failure["tool"], "repo_read")
        self.assertEqual(failure["arguments_sha256"], digest(diagnostic["item"]["arguments"]))
        self.assertEqual(failure["message"], diagnostic["item"]["error"]["message"])
        self.assertNotIn("arguments", failure)
        self.assertEqual(run["summary"]["net_benefit_gate"], "FAIL")
        self.assertFalse(run["summary"]["gates"]["all_task_quality_pass"])
        before = self.output.read_bytes()
        self.assertEqual(self.collect(), run)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(len(self.calls), 1)

    def test_registered_mcp_approval_accepts_each_registered_tool_and_json_object_arguments(self):
        for tool in tool_campaign.TOOLS:
            with self.subTest(tool=tool):
                diagnostic = self.mcp_approval_error()
                diagnostic["item"].update(tool=tool, arguments='{}')
                raw = self.no_tool_result({"source_sha256": "1" * 64, "tool": tool}, [diagnostic])
                failure = tool_campaign._transport_failure(raw)
                self.assertEqual(failure["code"], "registered-mcp-approval-policy-never")
                self.assertEqual(failure["tool"], tool)
                self.assertEqual(failure["arguments_sha256"], digest({}))

    def test_approval_guard_rejects_unregistered_nonfailed_and_argumentless_events(self):
        variants = []
        for field, value in (("server", "unregistered-server"), ("tool", "arbitrary_unregistered_tool"),
                             ("status", "completed"), ("status", "in_progress"), ("arguments", None),
                             ("arguments", []), ("arguments", '{'), ("arguments", '[]'),
                             ("arguments", {"invalid": float("nan")}),
                             ("error", "MCP tool call requires approval, but approval policy is never"),
                             ("error", {"message": "MCP tool call requires approval"})):
            event = self.mcp_approval_error()
            event["item"][field] = value
            variants.append((field + ":" + repr(value), event))
        missing = self.mcp_approval_error()
        missing["item"].pop("arguments")
        variants.append(("missing-arguments", missing))
        started = self.mcp_approval_error()
        started["type"] = "item.started"
        variants.append(("item-started", started))
        unrelated = self.cli_error("MCP tool call requires approval, but approval policy is never")
        variants.append(("unregistered-item-error", unrelated))
        for name, diagnostic in variants:
            with self.subTest(name=name):
                raw = self.no_tool_result({"source_sha256": "1" * 64, "variant": name}, [diagnostic])
                self.assertIsNone(tool_campaign._transport_failure(raw))
        raw = self.no_tool_result({"source_sha256": "1" * 64, "variant": "broker-present"}, [self.mcp_approval_error()])
        raw["tool_events"] = [{"tool": "repo_read"}]
        self.assertIsNone(tool_campaign._transport_failure(raw))

    def test_tampered_mcp_approval_evidence_keeps_charge_and_nonreplay_fence(self):
        self.behavior = lambda task, prompt, bindings: self.no_tool_result(bindings, [self.mcp_approval_error()], tampered=True)
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertEqual(run["budget"]["calls"], 1)
        self.assertGreater(run["budget"]["total_tokens"], 0)
        self.assertEqual(run["pending"]["kind"], "transport-evidence-unconfirmed")
        self.assertNotIn("transport_failure", run)
        with self.assertRaisesRegex(ValueError, "pending"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_local_receipt_reuse_is_not_a_new_sample_or_new_charge(self):
        self.behavior = lambda task, prompt, bindings: self.result(bindings, replay=True)
        run = self.collect()
        self.assertEqual(run["budget"]["calls"], 0)
        self.assertEqual(run["budget"]["total_tokens"], 0)
        self.assertFalse(run["summary"]["gates"]["all_new_model_calls"])

    def test_post_measurement_token_overrun_retains_observation(self):
        self.protocol["budget"]["tokens"] = 1
        run = self.collect()
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertEqual(len(run["observations"]), 1)
        self.assertGreater(run["budget"]["total_tokens"], 1)
        self.assertIn("tokens", run["actual_budget_overrun"])

    def synthetic_summary_run(self, *, regressed_model=None, wall_regression=False):
        rows = []
        for model in self.protocol["models"]:
            for task_id, task in self.tasks.items():
                for condition in tool_campaign.CONDITIONS:
                    bindings = {"source_sha256": "5" * 64 if condition == "treatment" else "1" * 64,
                                "unique": model + task_id + condition}
                    result = self.result(bindings)
                    elapsed = result["wall_seconds"]
                    if condition == "treatment" and model == regressed_model:
                        result["usage"]["total_tokens"] = 60
                    if wall_regression and condition == "treatment":
                        elapsed = 6
                    rows.append({"model": model, "task_id": task_id, "condition": condition, "family": task["family"],
                                 "result": result, "usage": result["usage"], "collector_wall_seconds": elapsed,
                                 "independent_sample": True, "cache_hit": False})
        return {"status": "completed", "stage": "independent", "models_requested": self.protocol["models"],
                "task_ids": self.protocol["task_ids"], "observations": rows}

    def test_paired_block_bootstrap_and_scope_gate(self):
        run = self.synthetic_summary_run()
        summary = tool_campaign.summarize(run, repetitions=100)
        self.assertEqual(summary["net_benefit_gate"], "PASS")
        self.assertAlmostEqual(summary["metrics"]["total_tokens"]["ratio"], .8)
        self.assertEqual(summary["metrics"]["total_tokens"]["paired_model_family_bootstrap_95_interval"], [.8, .8])
        self.assertEqual(summary["formal_qualification"], "UNASSESSED")
        self.assertIn("not multiple provider families", summary["provider_family_scope"])

    def test_new_collection_requires_joint_family_gate_without_protocol_opt_out(self):
        self.protocol["joint_family_intervals_required"] = False
        run = self.collect()
        self.assertIs(run["joint_family_intervals_required"], True)
        self.assertIs(json.loads(self.output.read_text())["joint_family_intervals_required"], True)
        self.assertEqual(run["summary"]["joint_family_bootstrap"]["repetitions"], 4000)
        self.assertEqual(run["summary"]["joint_family_bootstrap"]["seed"], 19012)
        run["joint_family_intervals_required"] = False
        self.output.write_text(json.dumps(run), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "joint-family interval contract"):
            self.collect()
        self.assertEqual(len(self.calls), 8)

    def test_shared_family_correlation_can_fail_joint_ci_despite_stratified_pass(self):
        self.tasks = {str(number): {"id": str(number), "family": "shared-" + str(number)} for number in range(4)}
        self.protocol["task_ids"] = list(self.tasks)
        run = self.synthetic_summary_run()
        for row in run["observations"]:
            value = 100 if row["condition"] == "control" else (120 if row["task_id"] == "3" else 50)
            row["usage"]["total_tokens"] = value
            row["collector_wall_seconds"] = value / 10
        legacy = tool_campaign.summarize(run)
        self.assertEqual(legacy["net_benefit_gate"], "PASS")
        run["joint_family_intervals_required"] = True
        summary = tool_campaign.summarize(run)
        self.assertEqual(summary["metrics"], legacy["metrics"])
        self.assertEqual(summary["per_model"], legacy["per_model"])
        for metric in ("total_tokens", "wall_seconds"):
            self.assertTrue(summary["gates"][metric + "_ci_upper_improves"])
            self.assertFalse(summary["gates"][metric + "_joint_family_ci_upper_improves"])
            self.assertGreaterEqual(summary["joint_family_metrics"][metric]["paired_joint_family_bootstrap_95_interval"][1], 1)
        self.assertEqual(summary["net_benefit_gate"], "FAIL")

    def test_joint_pass_does_not_override_existing_stratified_failure(self):
        run = self.synthetic_summary_run()
        for row in run["observations"]:
            bad = (row["model"] == self.protocol["models"][0]) == (row["task_id"] == "a")
            value = 100 if row["condition"] == "control" else (140 if bad else 10)
            row["usage"]["total_tokens"] = value
            row["collector_wall_seconds"] = value / 10
        run["joint_family_intervals_required"] = True
        summary = tool_campaign.summarize(run)
        self.assertTrue(summary["gates"]["total_tokens_joint_family_ci_upper_improves"])
        self.assertTrue(summary["gates"]["wall_seconds_joint_family_ci_upper_improves"])
        self.assertFalse(summary["gates"]["total_tokens_ci_upper_improves"])
        self.assertEqual(summary["net_benefit_gate"], "FAIL")

    def test_joint_family_coverage_and_disabled_contract_fail_closed(self):
        for mode in ("missing-model-family", "mismatched-pair-family", "disabled"):
            with self.subTest(mode=mode):
                run = self.synthetic_summary_run()
                run["joint_family_intervals_required"] = mode != "disabled"
                if mode == "missing-model-family":
                    for row in run["observations"]:
                        if row["model"] == self.protocol["models"][0]:
                            row["family"] = "one-unshared-family"
                elif mode == "mismatched-pair-family":
                    run["observations"][1]["family"] = "incorrect-label"
                summary = tool_campaign.summarize(run, repetitions=100)
                self.assertFalse(summary["gates"]["joint_family_complete_cross_model_coverage"])
                self.assertIsNone(summary["joint_family_metrics"]["total_tokens"])
                self.assertEqual(summary["net_benefit_gate"], "FAIL")

    def test_legacy_summary_has_exact_unchanged_shape_and_metrics(self):
        run = self.synthetic_summary_run()
        summary = tool_campaign.summarize(run, repetitions=100)
        def metric(control, treatment, interval):
            return {"control_total": control, "treatment_total": treatment, "ratio": treatment / control,
                    "savings_fraction": 1 - treatment / control,
                    "paired_model_family_bootstrap_95_interval": interval}
        metrics = {"total_tokens": metric(200, 160, [.8, .8]), "wall_seconds": metric(20, 16, [.8, .8]),
                   "cli_wall_seconds": metric(16, 12, [.75, .75]), "tool_calls": metric(16, 16, [1, 1])}
        expected = {"status": "completed", "matched_pairs": 4, "expected_pairs": 4, "net_benefit_gate": "PASS",
                    "gates": {key: True for key in ("complete_matched_collection", "all_task_quality_pass", "all_new_model_calls",
                              "unique_raw_call_receipts", "at_least_two_families_per_model", "total_tokens_ci_upper_improves",
                              "total_tokens_every_model_point_improves", "wall_seconds_ci_upper_improves", "wall_seconds_every_model_point_improves")},
                    "transport_failure": None, "new_protocol_required": False, "metrics": metrics,
                    "per_model": {model: {name: dict(value, control_total=value["control_total"] / 2,
                                                     treatment_total=value["treatment_total"] / 2)
                                           for name, value in metrics.items()} for model in run["models_requested"]},
                    "actual_charged_usage": None, "source_preparation": None, "formal_qualification": "UNASSESSED", "stage": "independent",
                    "provider_family_scope": "same-provider requested OpenAI models; not multiple provider families",
                    "execution_scope": "bounded real repository tools and AST/data inspection; no application-code execution",
                    "bootstrap": {"method": "paired-task-family-block-bootstrap-stratified-by-requested-model", "repetitions": 100,
                                  "seed": 19012, "confidence": .95},
                    "budget_limit": "actual reported CLI usage; no guaranteed provider token hard pre-cap"}
        self.assertEqual(summary, expected)

    def test_pooled_improvement_cannot_hide_model_regression(self):
        run = self.synthetic_summary_run(regressed_model=self.protocol["models"][0])
        summary = tool_campaign.summarize(run, repetitions=100)
        self.assertFalse(summary["gates"]["total_tokens_every_model_point_improves"])
        self.assertEqual(summary["net_benefit_gate"], "FAIL")

    def test_end_to_end_time_gate_cannot_hide_non_cli_overhead(self):
        run = self.synthetic_summary_run(wall_regression=True)
        summary = tool_campaign.summarize(run, repetitions=100)
        self.assertLess(summary["metrics"]["cli_wall_seconds"]["ratio"], 1)
        self.assertGreater(summary["metrics"]["wall_seconds"]["ratio"], 1)
        self.assertEqual(summary["net_benefit_gate"], "FAIL")

    def test_cli_timing_is_separate_from_full_adapter_and_collector_endpoint(self):
        raw = {"wall_seconds": 10, "timing": {"cli_seconds": 7}}
        row = {"result": raw, "collector_wall_seconds": 11}
        self.assertEqual(tool_campaign._value(row, "wall_seconds"), 11)
        self.assertEqual(tool_campaign._value(row, "cli_wall_seconds"), 7)
        self.assertEqual(tool_campaign._phase_timings(raw, 11), {
            "collector_total_seconds": 11, "adapter_seconds": 10, "cli_seconds": 7, "non_cli_seconds": 4})
        fallback = {"wall_seconds": 10, "receipt": {"timing": {"cli_seconds": 7}}}
        self.assertEqual(tool_campaign._phase_timings(fallback, 11)["cli_seconds"], 7)
        self.assertIsNone(tool_campaign._phase_timings({"wall_seconds": 10}, 11)["cli_seconds"])

    def test_duplicate_receipts_and_incomplete_pairs_cannot_pass(self):
        run = self.synthetic_summary_run()
        run["observations"][0]["result"]["receipt"]["receipt_sha256"] = run["observations"][1]["result"]["receipt"]["receipt_sha256"]
        summary = tool_campaign.summarize(run, repetitions=50)
        self.assertFalse(summary["gates"]["unique_raw_call_receipts"])
        run["observations"].pop()
        self.assertFalse(tool_campaign.summarize(run, repetitions=50)["gates"]["complete_matched_collection"])


if __name__ == "__main__":
    unittest.main()
