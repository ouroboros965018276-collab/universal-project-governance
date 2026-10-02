from __future__ import annotations
import json,pathlib,shutil,subprocess,sys,tempfile,unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from qualification.lib.core import get_lab,materialize_lab,grade_lab,normalized_outcome
from qualification.trigger_suite import build as build_trigger_suite
from qualification.analysis.metrics import zero_event_upper_bound
from qualification.analyze import analyze
from tools.qualification_freeze import behavioral_fingerprint

PY=sys.executable
RUNTIME=ROOT/"universal-project-governance"

def run(*args,cwd=None):
    return subprocess.run([PY,*map(str,args)],cwd=str(cwd or ROOT),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

class RC5QualificationTests(unittest.TestCase):
    def test_rc4_to_rc5_behavior_semantics_frozen(self):
        cp=run("tools/validate_freeze_delta.py")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertIn("behavioral freeze passed",cp.stdout)

    def test_qualification_infrastructure(self):
        cp=run("tools/validate_qualification.py",".")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)

    def test_machine_freeze_matches(self):
        cp=run("tools/qualification_freeze.py",".","--check")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)

    def test_trigger_suite_is_large_balanced_and_multilingual(self):
        cfg=json.loads((ROOT/"qualification/fixtures/trigger-families.json").read_text(encoding="utf-8"))
        cases=build_trigger_suite(cfg)
        self.assertGreaterEqual(len(cases),100)
        self.assertEqual(sum(1 for x in cases if x["should_trigger"]),sum(1 for x in cases if not x["should_trigger"]))
        self.assertEqual({x["language"] for x in cases},{"en","zh"})

    def test_executable_lab_grades_repository_state(self):
        lab=get_lab(ROOT/"qualification/fixtures/dev/behavioral-labs.json","dev-small-typo")
        with tempfile.TemporaryDirectory() as td:
            ws=pathlib.Path(td); before=materialize_lab(lab,ws)
            (ws/"README.md").write_text("Installation instructions are below.\n",encoding="utf-8")
            grade=grade_lab(lab,ws,before)
            self.assertTrue(grade["task_success"],grade)

    def test_safe_delete_lab_rejects_unsafe_removal(self):
        lab=get_lab(ROOT/"qualification/fixtures/dev/behavioral-labs.json","dev-safe-delete")
        with tempfile.TemporaryDirectory() as td:
            ws=pathlib.Path(td); before=materialize_lab(lab,ws)
            (ws/"src/legacy_hook.py").unlink()
            grade=grade_lab(lab,ws,before)
            self.assertFalse(grade["task_success"])

    def test_normalized_outcome_does_not_leak_treatment_identity(self):
        trial={"scenario_id":"x","kind":"behavioral","arm":"A2","agent":{"family":"secret-model"},"outcome":{"task_success":True},"usage":{},"evidence":{}}
        clean=normalized_outcome(trial)
        self.assertNotIn("arm",clean); self.assertNotIn("agent",clean)
        self.assertNotIn("secret-model",json.dumps(clean))

    def test_behavioral_fingerprint_ignores_version_only_changes(self):
        original=behavioral_fingerprint(RUNTIME)
        with tempfile.TemporaryDirectory() as td:
            dst=pathlib.Path(td)/"runtime"; shutil.copytree(RUNTIME,dst)
            p=dst/"SKILL.md"; p.write_text(p.read_text(encoding="utf-8").replace('version: "2.0.0-rc.5"','version: "9.9.9-test"'),encoding="utf-8")
            idx=dst/"policy-index.json"; obj=json.loads(idx.read_text(encoding="utf-8")); obj["version"]="9.9.9-test"; obj["source_sha256"]="different"; idx.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")
            (dst/"VERSION.md").write_text("# Version\n\n9.9.9-test\n",encoding="utf-8")
            self.assertEqual(original,behavioral_fingerprint(dst))

    def test_mutant_runtime_is_integrity_valid_but_behaviorally_different(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)/"mutant"
            cp=run("qualification/mutations/build_mutant_runtime.py","--mutant","M01_DISABLE_SAFE_DELETE","--output",out)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            cp=subprocess.run([PY,str(out/"scripts/validate_integrity.py"),str(out)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            self.assertNotEqual(behavioral_fingerprint(RUNTIME),behavioral_fingerprint(out))

    def _synthetic_rows(self,critical=False):
        rows=[]
        for i in range(60):
            pair="b%03d"%i; fam="agent-a" if i%2==0 else "agent-b"; profile="software" if i%2==0 else "data"
            common={"kind":"behavioral","pair_id":pair,"scenario_id":"s","agent":{"family":fam},"environment":{"project_profile":profile}}
            rows.append(dict(common,arm="A0",outcome={"task_success":True,"governance_defect_free":False,"critical_failures":[]},usage={"total_tokens":1000,"wall_time_seconds":100,"tool_calls":10}))
            rows.append(dict(common,arm="A1",outcome={"task_success":True,"governance_defect_free":False,"critical_failures":[]},usage={"total_tokens":1050,"wall_time_seconds":105,"tool_calls":10}))
            cfs=["CF01_UNSAFE_DELETION"] if critical and i==0 else []
            rows.append(dict(common,arm="A2",outcome={"task_success":True,"governance_defect_free":True,"critical_failures":cfs},usage={"total_tokens":1100,"wall_time_seconds":110,"tool_calls":11}))
        for i in range(8):
            pair="h%02d"%i
            common={"kind":"handoff","pair_id":pair,"scenario_id":"h","arm":"A2","agent":{"family":"agent-a"},"environment":{"project_profile":"software"},"usage":{"total_tokens":500,"wall_time_seconds":50,"tool_calls":5}}
            rows.append(dict(common,outcome={"task_success":False,"governance_defect_free":False,"critical_failures":[],"handoff_condition":"ablated"}))
            rows.append(dict(common,outcome={"task_success":True,"governance_defect_free":True,"critical_failures":[],"handoff_condition":"present"}))
        cfg=json.loads((ROOT/"qualification/fixtures/trigger-families.json").read_text(encoding="utf-8"))
        for case in build_trigger_suite(cfg):
            rows.append({"kind":"trigger","pair_id":"t-"+case["id"],"scenario_id":case["id"],"arm":"A2","agent":{"family":"agent-a"},"environment":{"project_profile":"software"},"outcome":{"should_trigger":case["should_trigger"],"triggered":case["should_trigger"],"critical_failures":[]},"usage":{"total_tokens":1,"wall_time_seconds":1,"tool_calls":1}})
        for i,mid in enumerate(["M01_DISABLE_SAFE_DELETE","M02_WEAKEN_TRUTH_CURRENT","M03_FORCE_REPORT_SPAM","M04_DISABLE_HANDOFF","M05_WEAKEN_MIGRATION_CUTOVER"]):
            rows.append({"kind":"mutation","pair_id":"m%d"%i,"scenario_id":"m","arm":"A2","agent":{"family":"agent-b"},"environment":{"project_profile":"data","mutation_id":mid},"outcome":{"eval_detected_regression":True,"critical_failures":[]},"usage":{"total_tokens":1,"wall_time_seconds":1,"tool_calls":1}})
        return rows

    def test_no_data_can_never_pass_qualification(self):
        th=json.loads((ROOT/"qualification/protocol/thresholds.json").read_text())
        protocol=json.loads((ROOT/"qualification/protocol/qualification-v1.json").read_text())
        result=analyze([],th,protocol,"sha256:test")
        self.assertEqual(result["status"],"MORE_DATA")

    def test_strong_synthetic_evidence_exercises_pass_path(self):
        th=json.loads((ROOT/"qualification/protocol/thresholds.json").read_text())
        protocol=json.loads((ROOT/"qualification/protocol/qualification-v1.json").read_text())
        result=analyze(self._synthetic_rows(),th,protocol,"sha256:test")
        self.assertEqual(result["status"],"PASS",result)
        self.assertTrue(all(x["state"]=="PASS" for x in result["gates"].values()))

    def test_critical_failure_is_non_compensatory(self):
        th=json.loads((ROOT/"qualification/protocol/thresholds.json").read_text())
        protocol=json.loads((ROOT/"qualification/protocol/qualification-v1.json").read_text())
        result=analyze(self._synthetic_rows(critical=True),th,protocol,"sha256:test")
        self.assertEqual(result["status"],"FAIL")
        self.assertEqual(result["gates"]["critical_failure"]["state"],"FAIL")

    def test_zero_failure_claim_has_nonzero_upper_bound(self):
        self.assertGreater(zero_event_upper_bound(180),0.0)
        self.assertLess(zero_event_upper_bound(180),0.02)

    def test_rc5_runtime_did_not_grow(self):
        lines=len((RUNTIME/"SKILL.md").read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(lines,90)
        idx=json.loads((RUNTIME/"policy-index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(idx["policies"]),15)
        self.assertEqual(len(idx["hot_path"]),7)

if __name__=="__main__":
    unittest.main()
