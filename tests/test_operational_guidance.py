"""Deterministic operational routing contracts; no ignored study or CLI inputs."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "governance-src"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


COMPILER = module("operational_compiler", ROOT / "compiler/compile_governance.py")
STATE = module("operational_state", SOURCE / "runtime-scripts/state_tool.py")
GUARD = module("operational_guard", SOURCE / "runtime-scripts/process_guard.py")
with patch.dict(sys.modules, state_tool=STATE, process_guard=GUARD):
    PROJECT = module("operational_project", SOURCE / "runtime-scripts/project_tool.py")
with patch.dict(sys.modules, project_tool=PROJECT):
    PLANNER = module("operational_planner", SOURCE / "runtime-scripts/plan_governance.py")


class OperationalGuidanceTests(unittest.TestCase):
    def setUp(self):
        for name in ("Popen", "run", "check_output", "call", "check_call"):
            fence = patch.object(subprocess, name, side_effect=AssertionError("CLI forbidden in routing tests"))
            fence.start()
            self.addCleanup(fence.stop)
        self.model = json.loads((SOURCE / "model/governance-model.json").read_text(encoding="utf-8"))
        self.index = COMPILER.compile_index(SOURCE, self.model)
        self.context = {"operation": "edit", "domains": ["docs"], "signals": [], "profiles": [],
                        "risk": {}, "unfinished": False, "explicit_audit": False,
                        "field_test_reporting": False}

    def plan(self, **changes):
        return PLANNER.compile_plan(self.index, dict(self.context, **changes))

    def count(self, plan, name):
        return sum(item.startswith("Operational " + name + ": ") for item in plan["required_closures"])

    def test_tiny_local_reporting_off_keeps_original_default_obligations(self):
        plan = self.plan()
        self.assertEqual(plan["change_mode"], "local")
        self.assertEqual(plan["report"], "none")
        self.assertEqual(self.count(plan, "tracked_state"), 0)
        self.assertEqual(plan["active_rules"], sorted(self.model["default_rules"]))

    def test_tiny_local_reporting_on_loads_tracked_state_once(self):
        plan = self.plan(field_test_reporting=True)
        self.assertEqual(plan["change_mode"], "local")
        self.assertEqual(plan["report"], "none")
        self.assertEqual(self.count(plan, "tracked_state"), 1)
        self.assertEqual(plan["field_report_obligation"], "required-before-completion")

    def test_existing_enabled_binding_fallback_applies_without_context_override(self):
        index = copy.deepcopy(self.index)
        index["project_binding"]["field_test_reporting"] = True
        context = dict(self.context)
        context.pop("field_test_reporting")
        plan = PLANNER.compile_plan(index, context)
        self.assertEqual(self.count(plan, "tracked_state"), 1)
        self.assertEqual(plan["field_report_obligation"], "required-before-completion")

    def test_tiny_local_explicit_audit_loads_tracked_state_once(self):
        plan = self.plan(explicit_audit=True)
        self.assertEqual(plan["report"], "audit")
        self.assertEqual(self.count(plan, "tracked_state"), 1)

    def test_structural_multiple_policy_and_reporting_matches_do_not_duplicate_blocks(self):
        plan = self.plan(operation="refactor", domains=["code"], signals=["handoff"],
                         unfinished=True, field_test_reporting=True)
        self.assertEqual(plan["change_mode"], "structural")
        self.assertEqual(plan["scope_guard"], "task-bounded-responsible-layer")
        self.assertEqual(self.count(plan, "tracked_state"), 1)
        self.assertEqual(self.count(plan, "recovery_tools"), 1)

    def test_resolved_report_alone_and_all_three_predicates_select_once(self):
        for report in ("engineering", "audit"):
            closures = PLANNER.operational_closures(self.index, set(self.model["default_rules"]), False, report)
            self.assertEqual(sum(c.startswith("Operational tracked_state:") for c in closures), 1)
        closures = PLANNER.operational_closures(self.index, {"STRUCTURAL_INTEGRATION", "HANDOFF_CONTINUITY"}, True, "audit")
        self.assertEqual(sum(c.startswith("Operational tracked_state:") for c in closures), 1)
        self.assertEqual(sum(c.startswith("Operational recovery_tools:") for c in closures), 1)

    def test_invalid_even_unselected_routing_is_rejected_by_both_compile_surfaces_and_planner(self):
        for mutate in (lambda g: g.update(id="INVALID ID"), lambda g: g.update(policy_ids=["UNKNOWN"]),
                       lambda g: g.update(policy_ids=[]),
                       lambda g: g.update(policy_ids=[g["policy_ids"][0]] * 2),
                       lambda g: g.update(on_field_reporting=1), lambda g: g.update(statement=" "),
                       lambda g: g.update(extra=True)):
            invalid = copy.deepcopy(self.model)
            mutate(invalid["operational_guidance"][1])
            for surface in (COMPILER.compile_index, COMPILER.render_skill):
                with self.assertRaises(ValueError):
                    surface(SOURCE, invalid)
            index = copy.deepcopy(self.index)
            index["operational_guidance"] = invalid["operational_guidance"]
            with self.assertRaises(ValueError):
                PLANNER.compile_plan(index, self.context)

    def test_invalid_report_levels_and_duplicate_groups_fail_closed(self):
        for value in (None, "audit", 1, [True], ["unknown"], ["audit", "audit"], [{}]):
            invalid = copy.deepcopy(self.model)
            invalid["operational_guidance"][1]["report_levels"] = value
            with self.assertRaises(ValueError):
                COMPILER.compile_index(SOURCE, invalid)
            index = copy.deepcopy(self.index)
            index["operational_guidance"] = invalid["operational_guidance"]
            with self.assertRaises(ValueError):
                PLANNER.compile_plan(index, self.context)
        for mutation in (lambda groups: groups[1].pop("report_levels"),
                         lambda groups: groups.extend(copy.deepcopy(groups))):
            invalid = copy.deepcopy(self.model)
            mutation(invalid["operational_guidance"])
            with self.assertRaises(ValueError):
                COMPILER.compile_index(SOURCE, invalid)
            index = copy.deepcopy(self.index)
            index["operational_guidance"] = invalid["operational_guidance"]
            with self.assertRaises(ValueError):
                PLANNER.compile_plan(index, self.context)

    def test_schema_and_canonical_router_use_the_same_five_typed_fields(self):
        schema = json.loads((SOURCE / "schemas/governance-model.schema.json").read_text(encoding="utf-8"))
        item = schema["properties"]["operational_guidance"]["items"]
        fields = {"id", "policy_ids", "report_levels", "on_field_reporting", "statement"}
        self.assertEqual(set(item["required"]), fields)
        self.assertEqual(set(item["properties"]), fields)
        self.assertIs(item["additionalProperties"], False)
        self.assertEqual(set(item["properties"]["report_levels"]["items"]["enum"]),
                         {"none", "change-note", "engineering", "audit"})
        self.assertFalse(STATE.validate_node(self.model, schema))

    def test_git_checkpoint_default_schema_is_typed_closed_and_bounded(self):
        schema = json.loads((SOURCE / "schemas/governance-model.schema.json").read_text(encoding="utf-8"))
        checkpoint = schema["properties"]["project_binding"]["properties"]["git_checkpoint"]
        defaults = self.model["project_binding"]["git_checkpoint"]
        self.assertEqual({key: value["default"] for key, value in checkpoint["properties"].items()}, defaults)
        self.assertFalse(STATE.validate_node(defaults, checkpoint))
        for key, value in (("enabled", 1), ("min_interval_seconds", True),
                           ("min_interval_seconds", 0.5), ("min_interval_seconds", -1),
                           ("min_interval_seconds", 86401), ("allowed_paths", "src"),
                           ("allowed_paths", [1]), ("status_paths", [""]),
                           ("status_paths", ["a"] * 1025), ("allowed_paths", ["a" * 1025])):
            with self.subTest(key=key, value_type=type(value).__name__):
                invalid = dict(defaults, **{key: value})
                self.assertTrue(STATE.validate_node(invalid, checkpoint))
        self.assertTrue(STATE.validate_node(dict(defaults, unexpected=True), checkpoint))
        for missing in defaults:
            self.assertTrue(STATE.validate_node({key: value for key, value in defaults.items() if key != missing}, checkpoint))

    def test_source_export_does_not_mutate_or_replace_core_definitions(self):
        original = copy.deepcopy(self.model)
        for key in ("policies", "hot_path", "default_rules", "risk_model", "structural_integration", "project_binding"):
            self.assertEqual(self.index[key], original[key])
        self.assertEqual(len(self.index["policies"]), 16)
        self.assertEqual(len(self.index["hot_path"]), 8)
        self.assertEqual(len(self.index["default_rules"]), 3)
        self.assertEqual(self.index["operational_guidance"], self.model["operational_guidance"])
        self.assertEqual(COMPILER.compile_index(SOURCE, self.model), self.index)
        self.assertEqual(self.model, original)

    def test_operational_projection_changes_no_other_plan_fields_or_base_closures(self):
        bare_index = copy.deepcopy(self.index)
        bare_index.pop("operational_guidance")
        for changes in ({}, {"explicit_audit": True}, {"field_test_reporting": True},
                        {"operation": "refactor", "domains": ["code"]}, {"unfinished": True}):
            context = dict(self.context, **changes)
            plan = PLANNER.compile_plan(self.index, context)
            bare = PLANNER.compile_plan(bare_index, context)
            self.assertEqual({k: v for k, v in plan.items() if k != "required_closures"},
                             {k: v for k, v in bare.items() if k != "required_closures"})
            self.assertEqual([c for c in plan["required_closures"] if not c.startswith("Operational ")],
                             bare["required_closures"])

    def test_legacy_inline_compiled_index_remains_an_exact_closure_source(self):
        index = copy.deepcopy(self.index)
        index.pop("operational_guidance")
        for policy in index["policies"]:
            additions = [g["statement"] for g in self.model["execution_guidance"] if policy["id"] in g["policy_ids"]]
            if additions:
                policy["closure"] += " " + " ".join(additions)
        for changes in ({}, {"explicit_audit": True}, {"operation": "refactor", "domains": ["code"]}):
            plan = PLANNER.compile_plan(index, dict(self.context, **changes))
            policies = {p["id"]: p for p in index["policies"]}
            expected = [rid + ": " + policies[rid]["closure"]
                        for rid in index["presentation"]["policy_order"] if rid in plan["active_rules"]]
            self.assertEqual(plan["required_closures"], expected)

    def test_recovery_preserves_original_continuity_closure_and_adds_each_selected_block(self):
        plan = self.plan(signals=["interrupted"], unfinished=True)
        self.assertEqual(self.count(plan, "tracked_state"), 1)
        self.assertEqual(self.count(plan, "recovery_tools"), 1)
        policy = next(p for p in self.model["policies"] if p["id"] == "HANDOFF_CONTINUITY")
        self.assertIn("HANDOFF_CONTINUITY: " + policy["closure"], plan["required_closures"])

    def test_unknown_profile_cannot_remove_task_obligations(self):
        plain = self.plan()
        unknown = self.plan(profiles=["unknown-review-profile"])
        self.assertEqual({k: v for k, v in plain.items() if k != "warnings"},
                         {k: v for k, v in unknown.items() if k != "warnings"})
        self.assertTrue(unknown["warnings"])

    def test_temporary_source_compilation_is_deterministic_and_keeps_declared_delivery_paths(self):
        with tempfile.TemporaryDirectory(prefix="upg-operational-") as directory:
            repo = Path(directory)
            shutil.copytree(SOURCE, repo / "governance-src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copyfile(ROOT / "LICENSE", repo / "LICENSE")
            outputs = [repo / "first", repo / "second"]
            for output in outputs:
                COMPILER.compile_runtime(repo, output)
            def contents(base):
                return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}
            generated = contents(outputs[0])
            self.assertEqual(generated, contents(outputs[1]))
            expected = {p.relative_to(ROOT / "universal-project-governance").as_posix()
                        for p in (ROOT / "universal-project-governance").rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts}
            self.assertEqual(set(generated), expected)
            self.assertIn("scripts/git_checkpoint.py", generated)
            self.assertIn("scripts/git_watch.py", generated)
            self.assertIn("scripts/process_guard.py", generated)
            self.assertIn("scripts/session_lifetime.py", generated)
            self.assertEqual(generated["scripts/session_lifetime.py"], (SOURCE / "runtime-scripts/session_lifetime.py").read_bytes())
            self.assertEqual(generated["scripts/git_checkpoint.py"], (SOURCE / "runtime-scripts/git_checkpoint.py").read_bytes())
            self.assertIn("scripts/completion_review.py", generated)
            self.assertIn("scripts/task_lifecycle.py", generated)
            self.assertEqual(generated["scripts/task_lifecycle.py"], (SOURCE / "runtime-scripts/task_lifecycle.py").read_bytes())
            self.assertEqual(len(generated), 24)


if __name__ == "__main__":
    unittest.main()
