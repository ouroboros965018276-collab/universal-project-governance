"""Synthetic callbacks only: no CLI, network, or sealed task-body reads."""
import copy
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
    from evolution import context_campaign as campaign
    from evolution.contracts import digest


@unittest.skipIf(sys.version_info < (3, 10), "optional CLI campaign needs Python 3.10+")
class ContextCampaignTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "eval-workspaces/tmp-context-campaign-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="context-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "run.json"
        self.tasks = {str(i): {"id": str(i), "family": "family-" + str(i), "prompt": "Change a to b.",
            "initial_files": {"data.txt": "a"}, "writable_files": ["data.txt"],
            "checks": [{"path": "data.txt", "kind": "text", "expected": "PRIVATE-EXPECTED-b"}],
            "required_read_paths": ["data.txt"]} for i in range(7)}
        full = json.loads((ROOT / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        models = campaign.trusted_arm_models(full)
        baseline = copy.deepcopy(full)
        baseline.pop("execution_guidance")
        baseline["version"] = "3.0.0-rc.19"
        models.update(rc19=baseline, attention=copy.deepcopy(baseline))
        def plan(model):
            groups = model.get("execution_guidance", [])
            return json.dumps({"active_rules": [policy["id"] for policy in model["policies"]],
                "required_closures": [policy["closure"] + " " + " ".join(group["statement"] for group in groups
                    if policy["id"] in group["policy_ids"]) for policy in model["policies"]]})
        conditions = {arm: {"governance_model": model, "candidate_sha256": digest(model),
            "source_sha256": digest(["source", arm]), "runtime_sha256": digest(["runtime", arm]),
            "skill": "Synthetic Skill " + arm + "\n" + "\n".join(group["statement"]
                for group in model.get("execution_guidance", [])),
            "plan_text": {task: plan(model) for task in self.tasks}}
            for arm, model in models.items()}
        conditions["attention"] = dict(copy.deepcopy(conditions["rc19"]), attention_instruction=campaign.ATTENTION_INSTRUCTION)
        self.configs = {model: {"model": model, "timeout_seconds": 180, "max_tool_calls": 32,
                              "effort": "medium", "artifact_root": self.temporary.name}
                        for model in ("synthetic-sol", "synthetic-luna")}
        self.capabilities = {model: {"config_sha256": digest(config)} for model, config in self.configs.items()}
        self.protocol = {"protocol_id": "synthetic-six-arm", "stage": "independent", "seed": 20014,
            "optimizer_candidate": False, "models": list(self.configs), "task_ids": list(self.tasks),
            "task_manifest_sha256": digest(self.tasks), "baseline_revision": "a" * 40,
            "conditions": conditions, "budget": {"model_calls": 84, "tokens": 10000, "wall_seconds": 7200}}
        self.calls, self.instances, self.clock, self.behavior = [], [], 0.0, None
        outer = self

        class FakeService:
            def __init__(self, config):
                self.config = config
                outer.instances.append(config["model"])

            def binding(self):
                return outer.capabilities[self.config["model"]]

            def run(self, task, *, prompt, bindings):
                checkpoint = json.loads(outer.output.read_text(encoding="utf-8"))
                outer.assertIsNotNone(checkpoint["pending"])
                outer.assertEqual(checkpoint["budget"]["calls"], len(outer.calls) + 1)
                outer.assertNotIn("PRIVATE-EXPECTED", prompt)
                outer.calls.append((task, prompt, bindings))
                full_arm = bindings["sample_id"].endswith(":full_rc20")
                outer.clock += 2 if full_arm else 4
                result = outer.result(bindings, prompt, full_arm)
                return outer.behavior(result) if outer.behavior else result

        self.factory = FakeService
        self.engine = patch.object(campaign, "engine_identity", return_value="b" * 64)
        self.engine.start()
        self.addCleanup(self.engine.stop)
        self.timer = patch.object(campaign.time, "perf_counter", side_effect=lambda: self.clock)
        self.timer.start()
        self.addCleanup(self.timer.stop)

    def result(self, bindings, prompt, full):
        import hashlib
        inputs = 20 if full else 40
        return {"status": "completed", "usage": {"input_tokens": inputs, "output_tokens": 10,
            "total_tokens": inputs + 10, "cached_input_tokens": None, "reasoning_output_tokens": None,
            "measurement": "synthetic-fixture", "fixture": True}, "wall_seconds": 2 if full else 4,
            "timing": {"cli_seconds": 1 if full else 3},
            "quality": {"hard_pass": True, "task_success": 1, "scope_ok": True, "required_tools_ok": True},
            "tool_events": [1, 2, 3, 4], "receipt": {"receipt_sha256": digest(bindings),
            "cli_thread_id": bindings["sample_id"], "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "replayed_from_local_receipt": False}}

    def collect(self):
        return campaign.collect(ROOT, self.protocol, self.tasks, self.configs, self.output,
                                expected_capabilities=self.capabilities, service_factory=self.factory)

    def test_complete_round_uses_one_client_per_model_and_no_dispatch_on_resume(self):
        run = self.collect()
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(self.calls), 84)
        self.assertEqual(len(self.instances), 2)
        self.assertEqual(run["budget"]["calls"], 84)
        self.assertEqual(run["budget"]["total_tokens"], 14 * (5 * 50 + 30))
        self.assertEqual(run["summary"]["net_benefit_gate"], "PASS")
        self.assertEqual(self.collect(), run)
        self.assertEqual(len(self.calls), 84)
        self.assertTrue(all(row["usage"]["cached_tokens"] is None for row in run["observations"]))
        self.assertFalse(run["optimizer_candidate"])
        bound = run["summary"]["finite_scope_quality"]
        self.assertEqual(bound["full_arm_trials"], 14)
        self.assertGreater(bound["zero_failure_one_sided_95_binomial_upper"], .05)
        self.assertEqual(bound["population_noninferiority"], "UNASSESSED")

    def test_fixed_order_has_adjacent_unique_arms_and_williams_position_balance(self):
        sequence = campaign.order(self.protocol["models"], self.protocol["task_ids"])
        self.assertEqual(sequence, campaign.order(self.protocol["models"], self.protocol["task_ids"]))
        self.assertEqual(len(sequence), 84)
        for start in range(0, 84, 6):
            block = sequence[start:start + 6]
            self.assertEqual({row["condition"] for row in block}, set(campaign.ARMS))
            self.assertEqual(len({(row["model"], row["task_id"]) for row in block}), 1)
        for model in self.protocol["models"]:
            for position in range(6):
                counts = [sum(row["model"] == model and row["position"] == position and row["condition"] == arm
                              for row in sequence) for arm in campaign.ARMS]
                self.assertEqual(sorted(counts), [1, 1, 1, 1, 1, 2])

    def test_attention_is_only_the_fixed_instruction_and_ablation_retains_reading(self):
        run = self.collect()
        prompts = {row[2]["sample_id"].split(":")[-1]: row[1] for row in self.calls}
        self.assertEqual(prompts["attention"], prompts["rc19"] + "\n\n" + campaign.ATTENTION_INSTRUCTION)
        for arm in campaign.ABLATIONS:
            groups = self.protocol["conditions"][arm]["governance_model"]["execution_guidance"]
            self.assertIn("task_scoped_reading", {group["id"] for group in groups})
        self.assertEqual(set(run["summary"]["comparisons"]), {"rc19", "attention"})
        self.assertTrue(all(value["diagnostic_only"] and not value["selection_allowed"]
                            for value in run["summary"]["ablation_diagnostics"].values()))

    def test_unknown_usage_stops_entire_round_and_blocks_resume(self):
        self.behavior = lambda result: dict(result, usage=None)
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(run["budget"]["unknown_usage"])
        self.assertIsNotNone(run["pending"])
        with self.assertRaisesRegex(ValueError, "never replay"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_exception_retains_observed_charge_and_interrupt_retains_pending(self):
        class KnownFailure(RuntimeError):
            pass
        def fail(result):
            error = KnownFailure("synthetic persistence fault")
            error.usage, error.provider_receipt = result["usage"], result["receipt"]
            raise error
        self.behavior = fail
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertGreater(run["budget"]["total_tokens"], 0)
        self.assertFalse(run["budget"]["unknown_usage"])
        self.assertEqual(run["budget"]["calls"], 1)

    def test_interrupt_never_replays_an_unfinished_dispatch(self):
        def interrupt(result):
            raise KeyboardInterrupt()
        self.behavior = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.collect()
        checkpoint = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertIsNotNone(checkpoint["pending"])
        self.assertEqual(checkpoint["budget"]["calls"], 1)
        with self.assertRaisesRegex(ValueError, "never replay"):
            self.collect()
        self.assertEqual(len(self.calls), 1)

    def test_replay_is_not_a_free_independent_observation(self):
        def replay(result):
            result["receipt"]["replayed_from_local_receipt"] = True
            return result
        self.behavior = replay
        run = self.collect()
        self.assertEqual(run["status"], "unknown-call-blocked")
        self.assertEqual(run["budget"]["calls"], 0)
        self.assertEqual(run["budget"]["records"], [])
        self.assertFalse(run["observations"][0]["independent_sample"])
        self.assertEqual(len(self.calls), 1)

    def test_known_overrun_retains_the_charge_and_stops_before_next_call(self):
        self.protocol["budget"]["tokens"] = 1
        run = self.collect()
        self.assertEqual(run["status"], "budget-exhausted")
        self.assertGreater(run["budget"]["total_tokens"], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn("tokens", run["actual_budget_overrun"])

    def test_quality_failure_and_incomplete_collection_cannot_expose_comparative_costs(self):
        def fail_quality(result):
            result["quality"]["hard_pass"] = False
            result["quality"]["task_success"] = 0
            return result
        self.behavior = fail_quality
        run = self.collect()
        self.assertEqual(len(self.calls), 84)
        self.assertEqual(run["summary"]["net_benefit_gate"], "FAIL")
        self.assertIsNone(run["summary"]["comparisons"]["rc19"]["metrics"]["total_tokens"])
        run["observations"].pop()
        self.assertFalse(campaign.summarize(run, repetitions=20)["gates"]["complete_six_arm_collection"])
        self.assertEqual(len(self.calls), 84)

    def test_changed_ablation_or_attention_rejected_before_dispatch(self):
        for arm in ("minus_complete_change", "attention"):
            with self.subTest(arm=arm):
                original = copy.deepcopy(self.protocol["conditions"][arm])
                self.protocol["conditions"][arm]["governance_model"]["hot_path"].pop()
                self.protocol["conditions"][arm]["candidate_sha256"] = digest(self.protocol["conditions"][arm]["governance_model"])
                with self.assertRaises(ValueError):
                    self.collect()
                self.protocol["conditions"][arm] = original
                self.assertFalse(self.calls)

    def test_strict_stage_seed_tool_and_caps_rejected_before_dispatch(self):
        mutations = [lambda: self.protocol.update(stage="development"),
                     lambda: self.protocol.update(seed=20015),
                     lambda: self.protocol["budget"].update(model_calls=85),
                     lambda: self.protocol["budget"].update(tokens=10_000_001),
                     lambda: self.configs["synthetic-sol"].update(max_tool_calls=33)]
        original_protocol, original_configs = copy.deepcopy(self.protocol), copy.deepcopy(self.configs)
        for mutate in mutations:
            mutate()
            with self.assertRaises(ValueError):
                self.collect()
            self.protocol, self.configs = copy.deepcopy(original_protocol), copy.deepcopy(original_configs)
            self.assertFalse(self.calls)

    def test_guidance_ablation_must_remove_both_skill_and_plan_leaks(self):
        arm = "minus_complete_change"
        original = copy.deepcopy(self.protocol["conditions"][arm])
        full = self.protocol["conditions"]["full_rc20"]
        for field in ("skill", "plan_text"):
            with self.subTest(field=field):
                self.protocol["conditions"][arm][field] = copy.deepcopy(full[field])
                with self.assertRaisesRegex(ValueError, "leaks or omits guidance"):
                    self.collect()
                self.protocol["conditions"][arm] = copy.deepcopy(original)
                self.assertFalse(self.calls)

    def test_frozen_identity_change_rejected_on_resume(self):
        self.collect()
        self.protocol["conditions"]["full_rc20"]["runtime_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.collect()
        self.assertEqual(len(self.calls), 84)


if __name__ == "__main__":
    unittest.main()
