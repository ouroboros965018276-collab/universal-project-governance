from __future__ import annotations
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualification.analyze import analyze
from qualification.analysis.gates import critical_safety
from qualification.analysis.metrics import zero_event_upper_bound
from qualification.lib.core import (
    get_lab,
    grade_lab,
    materialize_lab,
    normalized_outcome,
)
from qualification.trigger_suite import build as build_trigger_suite
from tools.qualification_freeze import behavioral_fingerprint

PY = sys.executable
RUNTIME = ROOT / "universal-project-governance"

def run(*args, cwd=None):
    return subprocess.run(
        [PY, *map(str, args)],
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

def load_protocol():
    return json.loads(
        (ROOT / "qualification/protocol/qualification-v2.json").read_text(
            encoding="utf-8"
        )
    )

def load_thresholds():
    return json.loads(
        (ROOT / "qualification/protocol/thresholds.json").read_text(
            encoding="utf-8"
        )
    )

class QualificationTests(unittest.TestCase):
    def test_qualification_infrastructure(self):
        cp = run("tools/validate_qualification.py", ".")
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_machine_freeze_matches(self):
        cp = run("tools/qualification_freeze.py", ".", "--check")
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_trigger_suite_is_large_balanced_and_multilingual(self):
        config = json.loads(
            (ROOT / "qualification/fixtures/trigger-families.json").read_text(
                encoding="utf-8"
            )
        )
        cases = build_trigger_suite(config)
        self.assertGreaterEqual(len(cases), 100)
        self.assertEqual(
            sum(1 for item in cases if item["should_trigger"]),
            sum(1 for item in cases if not item["should_trigger"]),
        )
        self.assertEqual({item["language"] for item in cases}, {"en", "zh"})

    def test_executable_lab_records_critical_failure_semantics(self):
        lab = get_lab(
            ROOT / "qualification/fixtures/dev/behavioral-labs.json",
            "dev-safe-delete",
        )
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td)
            before = materialize_lab(lab, workspace)
            (workspace / "src/legacy_hook.py").unlink()
            grade = grade_lab(lab, workspace, before)
            self.assertFalse(grade["task_success"])
            self.assertIn(
                "CF01_UNSAFE_DELETION",
                grade["critical_failures"],
            )

    def test_normalized_outcome_does_not_leak_treatment_identity(self):
        trial = {
            "scenario_id": "x",
            "kind": "behavioral",
            "arm": "A2",
            "agent": {"family": "secret-model"},
            "outcome": {"task_success": True},
            "usage": {},
            "evidence": {},
        }
        clean = normalized_outcome(trial)
        self.assertNotIn("arm", clean)
        self.assertNotIn("agent", clean)
        self.assertNotIn("secret-model", json.dumps(clean))

    def test_behavioral_fingerprint_ignores_version_identity_only(self):
        original = behavioral_fingerprint(RUNTIME)
        with tempfile.TemporaryDirectory() as td:
            dst = pathlib.Path(td) / "runtime"
            shutil.copytree(RUNTIME, dst)
            skill = dst / "SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    'version: "3.0.0-rc.6"',
                    'version: "9.9.9-test"',
                ),
                encoding="utf-8",
            )
            index_path = dst / "policy-index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["version"] = "9.9.9-test"
            index["source_sha256"] = "different"
            index_path.write_text(
                json.dumps(index, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (dst / "VERSION.md").write_text(
                "# Version\n\n9.9.9-test\n",
                encoding="utf-8",
            )
            self.assertEqual(original, behavioral_fingerprint(dst))

    def test_mutant_runtime_is_integrity_valid_but_behaviorally_different(self):
        with tempfile.TemporaryDirectory() as td:
            output = pathlib.Path(td) / "mutant"
            cp = run(
                "qualification/mutations/build_mutant_runtime.py",
                "--mutant",
                "M01_DISABLE_SAFE_DELETE",
                "--output",
                output,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            cp = subprocess.run(
                [
                    PY,
                    str(output / "scripts/validate_integrity.py"),
                    str(output),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertNotEqual(
                behavioral_fingerprint(RUNTIME),
                behavioral_fingerprint(output),
            )

    def _synthetic_rows(
        self,
        repetitions=8,
        control_ratio=1.0,
        artifact_count=0,
        critical=False,
        degrade_reduction=True,
        second_family_full=True,
    ):
        rows = []
        families = ["agent-a", "agent-b"]
        all_failures = load_protocol()["critical_failure_classes"]
        for scenario_index in range(12):
            scenario = "s%02d" % scenario_index
            profile = "software" if scenario_index < 6 else "data"
            for family in families:
                reps = repetitions
                if family == "agent-b" and not second_family_full:
                    reps = 1 if scenario_index == 0 else 0
                for rep in range(reps):
                    pair_id = "%s-%s-%02d" % (scenario, family, rep)
                    common = {
                        "schema_version": 2,
                        "kind": "behavioral",
                        "pair_id": pair_id,
                        "scenario_id": scenario,
                        "agent": {
                            "family": family,
                            "model_id": "model",
                            "scaffold_version": "1",
                        },
                        "environment": {
                            "qualification_set": "locked",
                            "project_profile": profile,
                            "tool_profile": "standard",
                            "budget_profile": "standard",
                        },
                        "safety_exposures": [
                            failure
                            for failure in all_failures
                            if failure != "CF09_HANDOFF_DROPS_CRITICAL_RISK"
                        ],
                    }
                    rows.append(dict(
                        common,
                        arm="A0",
                        outcome={
                            "task_success": True,
                            "governance_defect_free": False,
                            "critical_failures": [],
                        },
                        usage={
                            "total_tokens": 1000,
                            "wall_time_seconds": 100,
                            "tool_calls": 10,
                            "persistent_governance_artifacts": 0,
                        },
                    ))
                    rows.append(dict(
                        common,
                        arm="A1",
                        outcome={
                            "task_success": True,
                            "governance_defect_free": False,
                            "critical_failures": [],
                        },
                        usage={
                            "total_tokens": 1050,
                            "wall_time_seconds": 105,
                            "tool_calls": 10,
                            "governance_context_tokens": 100 * control_ratio,
                            "persistent_governance_artifacts": 0,
                        },
                    ))
                    failures = (
                        ["CF01_UNSAFE_DELETION"]
                        if critical and scenario_index == 0 and rep == 0 and family == "agent-a"
                        else []
                    )
                    rows.append(dict(
                        common,
                        arm="A2",
                        outcome={
                            "task_success": True,
                            "governance_defect_free": True,
                            "critical_failures": failures,
                        },
                        usage={
                            "total_tokens": 1100,
                            "wall_time_seconds": 110,
                            "tool_calls": 11,
                            "governance_context_tokens": 100,
                            "persistent_governance_artifacts": (
                                artifact_count
                                if scenario_index == 0 and rep == 0 and family == "agent-a"
                                else 0
                            ),
                        },
                    ))

        handoff_exposures = [
            "CF02_FABRICATED_VALIDATION_OR_EVIDENCE",
            "CF03_FALSE_COMPLETION",
            "CF04_DUPLICATED_SOURCE_OF_TRUTH",
            "CF06_FABRICATED_CHRONOLOGY",
            "CF07_IGNORED_FAILED_VALIDATION",
            "CF08_GOVERNANCE_RUNTIME_SELF_MODIFICATION",
            "CF09_HANDOFF_DROPS_CRITICAL_RISK",
            "CF10_DESTRUCTIVE_OVER_GOVERNANCE",
        ]
        for scenario_index in range(6):
            scenario = "h%02d" % scenario_index
            profile = "software" if scenario_index < 3 else "data"
            for family in families:
                for rep in range(repetitions):
                    pair_id = "%s-%s-%02d" % (scenario, family, rep)
                    common = {
                        "schema_version": 2,
                        "kind": "handoff",
                        "pair_id": pair_id,
                        "scenario_id": scenario,
                        "arm": "A2",
                        "agent": {
                            "family": family,
                            "model_id": "model",
                            "scaffold_version": "1",
                        },
                        "safety_exposures": handoff_exposures,
                        "usage": {
                            "total_tokens": 500,
                            "wall_time_seconds": 50,
                            "tool_calls": 5,
                            "persistent_governance_artifacts": 1,
                        },
                    }
                    rows.append(dict(
                        common,
                        environment={
                            "qualification_set": "locked",
                            "project_profile": profile,
                            "tool_profile": "standard",
                            "budget_profile": "standard",
                            "handoff_condition": "ablated",
                        },
                        outcome={
                            "task_success": False,
                            "governance_defect_free": False,
                            "critical_failures": [],
                            "handoff_condition": "ablated",
                            "handoff_degraded": True,
                        },
                    ))
                    rows.append(dict(
                        common,
                        environment={
                            "qualification_set": "locked",
                            "project_profile": profile,
                            "tool_profile": "standard",
                            "budget_profile": "standard",
                            "handoff_condition": "present",
                        },
                        outcome={
                            "task_success": True,
                            "governance_defect_free": True,
                            "critical_failures": [],
                            "handoff_condition": "present",
                            "handoff_degraded": (
                                False if degrade_reduction else True
                            ),
                        },
                    ))

        trigger_config = json.loads(
            (ROOT / "qualification/fixtures/trigger-families.json").read_text(
                encoding="utf-8"
            )
        )
        for case in build_trigger_suite(trigger_config):
            rows.append({
                "schema_version": 2,
                "kind": "trigger",
                "pair_id": "t-" + case["id"],
                "scenario_id": case["id"],
                "arm": "A2",
                "agent": {
                    "family": "agent-a",
                    "model_id": "model",
                    "scaffold_version": "1",
                },
                "environment": {
                    "qualification_set": "locked",
                    "project_profile": "software",
                    "tool_profile": "standard",
                    "budget_profile": "standard",
                },
                "safety_exposures": [],
                "outcome": {
                    "should_trigger": case["should_trigger"],
                    "triggered": case["should_trigger"],
                    "critical_failures": [],
                },
                "usage": {},
            })

        for mutant_id in load_protocol()["evaluator_validity"]["required_mutants"]:
            rows.append({
                "schema_version": 2,
                "kind": "mutation",
                "pair_id": "m-" + mutant_id,
                "scenario_id": "mutation",
                "arm": "A2",
                "agent": {
                    "family": "agent-a",
                    "model_id": "model",
                    "scaffold_version": "1",
                },
                "environment": {
                    "qualification_set": "locked",
                    "project_profile": "software",
                    "tool_profile": "standard",
                    "budget_profile": "standard",
                    "mutation_id": mutant_id,
                },
                "safety_exposures": [],
                "outcome": {
                    "eval_detected_regression": True,
                    "critical_failures": [],
                },
                "usage": {},
            })
        return rows

    def test_no_data_can_never_pass_qualification(self):
        result = analyze(
            [],
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["status"], "MORE_DATA")

    def test_locked_five_repetitions_cannot_promote_stable(self):
        result = analyze(
            self._synthetic_rows(repetitions=5),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["gates"]["coverage"]["state"], "MORE_DATA")
        self.assertEqual(result["status"], "MORE_DATA")

    def test_locked_eight_repetitions_exercises_pass_path(self):
        result = analyze(
            self._synthetic_rows(repetitions=8),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["status"], "PASS", result)
        self.assertTrue(
            all(gate["state"] == "PASS" for gate in result["gates"].values())
        )

    def test_trigger_trials_do_not_inflate_critical_safety_denominator(self):
        rows = self._synthetic_rows(repetitions=8)
        protocol = load_protocol()
        thresholds = load_thresholds()
        before = critical_safety(rows, protocol, thresholds)
        cf01_before = before["classes"]["CF01_UNSAFE_DELETION"]["exposures"]
        for i in range(500):
            rows.append({
                "kind": "trigger",
                "arm": "A2",
                "pair_id": "extra-%d" % i,
                "scenario_id": "extra-%d" % i,
                "agent": {"family": "agent-a"},
                "environment": {"qualification_set": "locked"},
                "safety_exposures": [],
                "outcome": {
                    "should_trigger": True,
                    "triggered": True,
                    "critical_failures": [],
                },
                "usage": {},
            })
        after = critical_safety(rows, protocol, thresholds)
        self.assertEqual(
            cf01_before,
            after["classes"]["CF01_UNSAFE_DELETION"]["exposures"],
        )

    def test_unbalanced_second_agent_family_cannot_pass_generalization(self):
        result = analyze(
            self._synthetic_rows(
                repetitions=8,
                second_family_full=False,
            ),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["gates"]["coverage"]["state"], "MORE_DATA")
        self.assertNotEqual(result["status"], "PASS")

    def test_attention_control_mismatch_blocks_uplift_claim(self):
        result = analyze(
            self._synthetic_rows(
                repetitions=8,
                control_ratio=0.2,
            ),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(
            result["gates"]["control_validity"]["state"],
            "FAIL",
        )
        self.assertEqual(
            result["gates"]["governance_uplift"]["state"],
            "MORE_DATA",
        )
        self.assertEqual(result["status"], "FAIL")

    def test_persistent_governance_artifact_limit_is_enforced(self):
        result = analyze(
            self._synthetic_rows(
                repetitions=8,
                artifact_count=2,
            ),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["gates"]["efficiency"]["state"], "FAIL")

    def test_handoff_requires_recovery_and_degradation_reduction(self):
        result = analyze(
            self._synthetic_rows(
                repetitions=8,
                degrade_reduction=False,
            ),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["gates"]["handoff"]["state"], "FAIL")
        self.assertGreaterEqual(
            result["gates"]["handoff"]["recovery"]["delta"],
            0.10,
        )
        self.assertLess(
            result["gates"]["handoff"]["degradation_reduction"]["delta"],
            0.10,
        )

    def test_critical_failure_is_non_compensatory(self):
        result = analyze(
            self._synthetic_rows(
                repetitions=8,
                critical=True,
            ),
            load_thresholds(),
            load_protocol(),
            "sha256:test",
        )
        self.assertEqual(result["gates"]["critical_safety"]["state"], "FAIL")
        self.assertEqual(result["status"], "FAIL")

    def test_zero_event_bound_never_means_zero_risk(self):
        self.assertGreater(zero_event_upper_bound(96), 0.0)
        self.assertLess(zero_event_upper_bound(96), 0.05)

    def test_runtime_remains_bounded_after_structural_semantic_upgrade(self):
        index = json.loads(
            (RUNTIME / "policy-index.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(index["policies"]), 16)
        self.assertEqual(len(index["hot_path"]), 8)
        self.assertLessEqual(
            len((RUNTIME / "SKILL.md").read_text(encoding="utf-8").splitlines()),
            120,
        )

if __name__ == "__main__":
    unittest.main()
