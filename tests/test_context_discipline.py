"""No-model contracts for canonical guidance, task routing and source-group ablation."""
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


COMPILER = module("context_discipline_compiler", ROOT / "compiler/compile_governance.py")
STATE = module("context_discipline_state", SOURCE / "runtime-scripts/state_tool.py")
with patch.dict(sys.modules, state_tool=STATE):
    PROJECT = module("context_discipline_project", SOURCE / "runtime-scripts/project_tool.py")
with patch.dict(sys.modules, project_tool=PROJECT):
    PLANNER = module("context_discipline_planner", SOURCE / "runtime-scripts/plan_governance.py")


class ContextDisciplineTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((SOURCE / "model/governance-model.json").read_text(encoding="utf-8"))
        self.groups = {item["id"]: item for item in self.model["execution_guidance"]}

    def plan(self, context, model=None):
        return PLANNER.compile_plan(COMPILER.compile_index(SOURCE, model or self.model), context)

    def test_four_guidance_groups_reuse_existing_routing(self):
        self.assertEqual(
            {key: value["policy_ids"] for key, value in self.groups.items()},
            {
                "decision_relevance": ["TRUTH_CURRENT"],
                "complete_change": ["STRUCTURAL_INTEGRATION"],
                "evidence_fidelity": ["EVIDENCE_AFFECTED"],
                "task_scoped_reading": ["EVIDENCE_AFFECTED"],
            },
        )
        self.assertEqual(len(self.model["policies"]), 16)
        self.assertEqual(len(self.model["hot_path"]), 8)
        self.assertEqual(len(self.model["default_rules"]), 3)

    def test_local_code_and_docs_receive_guidance_without_forcing_architecture_work(self):
        for context in ({"operation": "edit", "domains": ["code"]},
                        {"operation": "docs", "domains": ["docs"]}):
            with self.subTest(context=context):
                plan = self.plan(context)
                self.assertEqual(plan["change_mode"], "local")
                self.assertEqual(plan["scope_guard"], "local-only")
                self.assertEqual(set(plan["active_rules"]), set(self.model["default_rules"]))
                closures = "\n".join(plan["required_closures"])
                for group in ("decision_relevance", "evidence_fidelity", "task_scoped_reading"):
                    self.assertEqual(closures.count(self.groups[group]["statement"]), 1)
                self.assertNotIn(self.groups["complete_change"]["statement"], closures)

    def test_nontrivial_and_forced_work_receive_complete_change_with_scope_guard(self):
        contexts = [
            {"operation": "edit", "domains": ["code"], "risk": {"scope": 2, "reversibility": 2}},
            {"operation": "architecture", "domains": ["code"]},
        ]
        for context in contexts:
            with self.subTest(context=context):
                plan = self.plan(context)
                self.assertEqual(plan["change_mode"], "structural")
                self.assertEqual(plan["scope_guard"], "task-bounded-responsible-layer")
                self.assertIn("STRUCTURAL_INTEGRATION", plan["active_rules"])
                closures = "\n".join(plan["required_closures"])
                for group in self.groups.values():
                    self.assertEqual(closures.count(group["statement"]), 1)

    def test_single_canonical_statements_reach_skill_and_target_closures(self):
        skill = COMPILER.render_skill(SOURCE, self.model)
        index = COMPILER.compile_index(SOURCE, self.model)
        template = (SOURCE / "templates/SKILL.template.md").read_text(encoding="utf-8")
        self.assertNotIn("{{", skill)
        self.assertIn("{{EXECUTION_GUIDANCE}}", template)
        for group in self.groups.values():
            self.assertNotIn(group["statement"], template)
            self.assertEqual(skill.count(group["statement"]), 1)
            self.assertIn(group["id"], skill)
            for policy in index["policies"]:
                self.assertEqual(policy["closure"].count(group["statement"]),
                                 int(policy["id"] in group["policy_ids"]))

    def test_each_source_group_can_be_ablated_without_changing_policy_contracts(self):
        context = {"operation": "architecture", "domains": ["code"]}
        full_plan = self.plan(context)
        for removed in self.groups:
            with self.subTest(removed=removed):
                ablated = copy.deepcopy(self.model)
                ablated["execution_guidance"] = [g for g in ablated["execution_guidance"] if g["id"] != removed]
                plan = self.plan(context, ablated)
                skill = COMPILER.render_skill(SOURCE, ablated)
                closures = "\n".join(plan["required_closures"])
                for key in ("active_rules", "risk_level", "change_mode", "scope_guard", "evidence", "report", "handoff"):
                    self.assertEqual(plan[key], full_plan[key])
                for key in ("policies", "hot_path", "default_rules"):
                    self.assertEqual(ablated[key], self.model[key])
                for group_id, group in self.groups.items():
                    self.assertEqual(group["statement"] in skill, group_id != removed)
                    self.assertEqual(group["statement"] in closures, group_id != removed)

    def test_compile_does_not_mutate_canonical_model_or_accumulate_guidance(self):
        original = copy.deepcopy(self.model)
        first = COMPILER.compile_index(SOURCE, self.model)
        second = COMPILER.compile_index(SOURCE, self.model)
        COMPILER.render_skill(SOURCE, self.model)
        self.assertEqual(first, second)
        self.assertEqual(self.model, original)
        for compiled in first["policies"]:
            source = next(p for p in original["policies"] if p["id"] == compiled["id"])
            self.assertTrue(compiled["closure"].startswith(source["closure"]))

    def test_candidates_without_guidance_keep_original_policy_semantics(self):
        legacy = copy.deepcopy(self.model)
        legacy.pop("execution_guidance")
        index = COMPILER.compile_index(SOURCE, legacy)
        self.assertEqual(index["policies"], legacy["policies"])
        skill = COMPILER.render_skill(SOURCE, legacy)
        self.assertNotIn("{{", skill)
        for group in self.groups.values():
            self.assertNotIn(group["statement"], skill)

    def test_invalid_guidance_fails_before_either_rendered_surface(self):
        mutations = {
            "duplicate-group": lambda groups: groups.append(copy.deepcopy(groups[0])),
            "unknown-policy": lambda groups: groups[0].update(policy_ids=["MISSING_POLICY"]),
            "blank-statement": lambda groups: groups[0].update(statement="  "),
        }
        for mutation_name, mutate in mutations.items():
            for surface in (COMPILER.compile_index, COMPILER.render_skill):
                with self.subTest(mutation=mutation_name, surface=surface.__name__):
                    invalid = copy.deepcopy(self.model)
                    mutate(invalid["execution_guidance"])
                    with self.assertRaises(ValueError):
                        surface(SOURCE, invalid)


if __name__ == "__main__":
    unittest.main()
