"""UPG-native routing preserves local scope and existing reporting contracts."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
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


COMPILER = module("pstack_compiler", ROOT / "compiler/compile_governance.py")
STATE = module("pstack_state", SOURCE / "runtime-scripts/state_tool.py")
GUARD = module("pstack_guard", SOURCE / "runtime-scripts/process_guard.py")
with patch.dict(sys.modules, state_tool=STATE, process_guard=GUARD):
    PROJECT = module("pstack_project", SOURCE / "runtime-scripts/project_tool.py")
with patch.dict(sys.modules, project_tool=PROJECT):
    PLANNER = module("pstack_planner", SOURCE / "runtime-scripts/plan_governance.py")


class PstackWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((SOURCE / "model/governance-model.json").read_text(encoding="utf-8"))
        self.index = COMPILER.compile_index(SOURCE, self.model)

    def test_local_change_retains_lightweight_scope_and_global_completion_review(self):
        for operation, domain in (("edit", "code"), ("docs", "docs")):
            context = {"operation": operation, "domains": [domain]}
            plan = PLANNER.compile_plan(self.index, context)
            self.assertEqual(plan["change_mode"], "local")
            self.assertEqual(plan["report"], "none")
            self.assertFalse(any(c.startswith("Operational engineering_workflow:")
                                 for c in plan["required_closures"]))
        # Global review applies even when no optional operational block is selected.
        guidance = next(g for g in self.model["execution_guidance"] if g["id"] == "evidence_fidelity")
        self.assertEqual(COMPILER.render_skill(SOURCE, self.model).count(guidance["statement"]), 1)
        self.assertIn("completion_review", guidance["statement"])

    def test_engineering_and_audit_select_workflow_once_without_changing_other_plan_contracts(self):
        bare = copy.deepcopy(self.index)
        bare["operational_guidance"] = [g for g in bare["operational_guidance"] if g["id"] != "engineering_workflow"]
        for context in (
            {"operation": "refactor", "domains": ["code"]},
            {"operation": "governance_upgrade", "domains": ["governance"], "explicit_audit": True},
            {"operation": "docs", "domains": ["docs"], "explicit_audit": True},
        ):
            with self.subTest(context=context):
                result = PLANNER.compile_plan(self.index, context)
                previous = PLANNER.compile_plan(bare, context)
                additions = [c for c in result["required_closures"] if c.startswith("Operational engineering_workflow:")]
                self.assertEqual(len(additions), 1)
                self.assertEqual({k: v for k, v in result.items() if k != "required_closures"},
                                 {k: v for k, v in previous.items() if k != "required_closures"})
                self.assertEqual([c for c in result["required_closures"] if c not in additions],
                                 previous["required_closures"])

    def test_unknown_profile_and_reporting_opt_in_do_not_expand_local_design_scope(self):
        result = PLANNER.compile_plan(self.index, {"operation": "docs", "domains": ["docs"],
            "profiles": ["pstack"], "field_test_reporting": True})
        self.assertEqual(result["change_mode"], "local")
        self.assertEqual(result["report"], "none")
        self.assertEqual(result["field_report_obligation"], "required-before-completion")
        self.assertFalse(any(c.startswith("Operational engineering_workflow:") for c in result["required_closures"]))
        self.assertEqual(len(self.index["policies"]), 16)
        self.assertEqual(len(self.index["hot_path"]), 8)
        self.assertEqual(len(self.index["default_rules"]), 3)
        self.assertIs(self.index["project_binding"]["field_test_reporting"], False)
        self.assertEqual(self.index["project_binding"]["managed_files_max"], 2)

    def test_intake_and_advancement_guidance_stays_global_without_heavy_local_routing(self):
        skill = COMPILER.render_skill(SOURCE, self.model)
        guidance = next(item for item in self.model["execution_guidance"] if item["id"] == "complete_change")
        self.assertEqual(skill.count(guidance["statement"]), 1)
        context = {"operation": "edit", "domains": ["code"], "profiles": ["unknown-future-task"]}
        plan = PLANNER.compile_plan(self.index, context)
        self.assertEqual(plan["change_mode"], "local")
        self.assertEqual(plan["report"], "none")
        self.assertFalse(any(item.startswith("Operational tracked_state:") for item in plan["required_closures"]))
        self.assertFalse(any(item.startswith("Operational engineering_workflow:") for item in plan["required_closures"]))
        # A task plan is project execution state; the policy projection never
        # manufactures task acceptance, units, progress or a ready verdict.
        self.assertFalse({"task_contract", "task_progress", "ready"} & set(plan))

    def test_evidence_change_routes_continuity_without_authorizing_structural_scope(self):
        for signal in ("interrupted", "no-progress", "contradiction"):
            with self.subTest(signal=signal):
                plan = PLANNER.compile_plan(self.index, {"operation": "edit", "domains": ["code"], "signals": [signal]})
                self.assertEqual(plan["change_mode"], "local")
                self.assertEqual(plan["handoff"], "required")
                self.assertIn("HANDOFF_CONTINUITY", plan["active_rules"])
                for group in ("tracked_state", "recovery_tools"):
                    self.assertEqual(sum(item.startswith("Operational " + group + ":")
                                         for item in plan["required_closures"]), 1)
                self.assertFalse(any(item.startswith("Operational engineering_workflow:")
                                     for item in plan["required_closures"]))


if __name__ == "__main__":
    unittest.main()
