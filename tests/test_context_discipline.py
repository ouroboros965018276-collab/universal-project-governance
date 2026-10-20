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

    def test_local_code_and_docs_keep_global_guidance_without_forcing_architecture_work(self):
        for context in ({"operation": "edit", "domains": ["code"]},
                        {"operation": "docs", "domains": ["docs"]}):
            with self.subTest(context=context):
                plan = self.plan(context)
                self.assertEqual(plan["change_mode"], "local")
                self.assertEqual(plan["scope_guard"], "local-only")
                self.assertEqual(set(plan["active_rules"]), set(self.model["default_rules"]))
                closures = "\n".join(plan["required_closures"])
                skill = COMPILER.render_skill(SOURCE, self.model)
                for group in self.groups.values():
                    self.assertEqual(skill.count(group["statement"]), 1)
                    self.assertNotIn(group["statement"], closures)
                self.assertFalse(any(c.startswith("Operational ") for c in plan["required_closures"]))

    def test_nontrivial_and_forced_work_keep_base_closures_and_scope_guard(self):
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
                    self.assertNotIn(group["statement"], closures)
                self.assertEqual(sum(c.startswith("Operational tracked_state: ")
                                     for c in plan["required_closures"]), 1)

    def test_missing_or_empty_risk_is_provisional_without_escalating_local_work(self):
        context = {"operation": "edit", "domains": ["code"]}
        zeros = dict.fromkeys(self.model["risk_model"]["dimensions"], 0)
        assessed = self.plan(dict(context, risk=zeros))
        for supplied in (context, dict(context, risk={})):
            with self.subTest(context=supplied):
                plan = self.plan(supplied)
                self.assertEqual({key: value for key, value in plan.items() if key != "warnings"},
                                 {key: value for key, value in assessed.items() if key != "warnings"})
                self.assertEqual(plan["risk_score"], 0)
                self.assertEqual(plan["change_mode"], "local")
                self.assertEqual(plan["report"], "none")
                self.assertEqual(len(plan["warnings"]), 1)
                self.assertIn("risk unassessed", plan["warnings"][0])
                self.assertIn("provisional", plan["warnings"][0])
                self.assertIn(", ".join(sorted(zeros)), plan["warnings"][0])

    def test_fully_assessed_zero_risk_remains_confirmed_trivial_without_warning(self):
        zeros = dict.fromkeys(self.model["risk_model"]["dimensions"], 0)
        plan = self.plan({"operation": "edit", "domains": ["code"], "risk": zeros})
        self.assertEqual((plan["risk_level"], plan["risk_score"]), ("trivial", 0))
        self.assertEqual(plan["active_rules"], sorted(self.model["default_rules"]))
        self.assertEqual(plan["warnings"], [])

    def test_partial_risk_preserves_known_score_and_closures_but_warns_missing_facts(self):
        for known, expected_score in (({"scope": 0}, 0), ({"scope": 2}, 2),
                                      ({"scope": 2, "reversibility": 2}, 4)):
            with self.subTest(known=known):
                complete = dict.fromkeys(self.model["risk_model"]["dimensions"], 0)
                complete.update(known)
                context = {"operation": "edit", "domains": ["code"]}
                partial = self.plan(dict(context, risk=known))
                assessed = self.plan(dict(context, risk=complete))
                self.assertEqual({key: value for key, value in partial.items() if key != "warnings"},
                                 {key: value for key, value in assessed.items() if key != "warnings"})
                self.assertEqual(partial["risk_score"], expected_score)
                self.assertEqual(len(partial["warnings"]), 1)
                self.assertIn("risk partially assessed", partial["warnings"][0])
                missing = sorted(set(complete) - set(known))
                self.assertIn(", ".join(missing), partial["warnings"][0])

    def test_global_guidance_reaches_skill_once_and_preserves_all_base_policy_definitions(self):
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
                self.assertNotIn(group["statement"], policy["closure"])
        self.assertEqual(index["policies"], self.model["policies"])
        self.assertEqual(index["operational_guidance"], self.model["operational_guidance"])

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
                self.assertEqual(plan, full_plan)
                for key in ("policies", "hot_path", "default_rules"):
                    self.assertEqual(ablated[key], self.model[key])
                for group_id, group in self.groups.items():
                    self.assertEqual(group["statement"] in skill, group_id != removed)
                    self.assertNotIn(group["statement"], closures)

    def test_compile_does_not_mutate_canonical_model_or_accumulate_guidance(self):
        original = copy.deepcopy(self.model)
        first = COMPILER.compile_index(SOURCE, self.model)
        second = COMPILER.compile_index(SOURCE, self.model)
        COMPILER.render_skill(SOURCE, self.model)
        self.assertEqual(first, second)
        self.assertEqual(self.model, original)
        for compiled in first["policies"]:
            source = next(p for p in original["policies"] if p["id"] == compiled["id"])
            self.assertEqual(compiled, source)

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
