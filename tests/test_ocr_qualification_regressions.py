"""Offline regressions for reviewed live qualification findings; no model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.adapters.diagnostics import redact_public, redact_text
from qualification.adapters.command_adapter import CommandAdapter
from qualification.adapters import codex_cli
from qualification.analysis.admission import verify_artifact
from qualification.analysis.coverage import behavioral_coverage, handoff_coverage
from qualification.analysis.gates import core_task, critical_safety
from qualification.analysis.metrics import mcnemar_exact_p, paired_binary, hierarchical_bootstrap_delta
from qualification.lib.core import project_integration_status
from qualification.lib.execution import persist_evidence
from qualification.mutations.apply_policy_mutant import apply_mutant
from qualification.mutations.build_mutant_runtime import build_runtime


class OCRQualificationRegressions(unittest.TestCase):
    def test_structured_secret_values_keys_bytes_and_containers(self):
        value={"password":"x","OPENAI_API_KEY":"abc","nested":(b"DB_PASSWORD=short",),"/home/user/private":"ok"}
        rendered=json.dumps(redact_public(value))
        for secret in ('"x"','"abc"','short','/home/user/private'):
            self.assertNotIn(secret,rendered)
        for value in ('"password": "short"',"DB_PASSWORD=x","OPENAI_API_KEY=abc"):
            self.assertIn("REDACTED",redact_text(value))
        for key in ("Authorization","Proxy-Authorization","Cookie","Set-Cookie","token","client_secret","apiKey","accessToken"):
            self.assertEqual(redact_public({key:"private value"})[key],"[REDACTED_SECRET]")
        self.assertIn("permission denied",redact_text("read /home/a/file: permission denied"))

    def test_blind_pair_direct_script_and_private_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            for side,success in (("left",True),("right",False)):
                (base/(side+".json")).write_text(json.dumps({"scenario_id":"s","kind":"behavioral","outcome":{"task_success":success}}),encoding="utf-8")
            cp=subprocess.run([sys.executable,str(ROOT/"qualification/graders/blind_pair.py"),str(base/"left.json"),str(base/"right.json"),"--seed","s","--output",str(base/"blind.json"),"--mapping-output",str(base/"private.json")],cwd=td,capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stderr)
            mapping=json.loads((base/"private.json").read_text())
            blind=json.loads((base/"blind.json").read_text())
            self.assertEqual(set(mapping.values())-{"left","right",1,"s"},set())
            self.assertNotIn("seed",blind)
            self.assertEqual(blind["candidates"]["X"]["outcome"]["task_success"],mapping["X"]=="left")

    def test_mutant_rejects_source_overlap_and_preserves_output_on_failure(self):
        mutant={"id":"bad","operation":"remove_policy","target":"absent"}
        for output in (ROOT,ROOT.parent,ROOT/"universal-project-governance",ROOT/"universal-project-governance/sub"):
            with self.assertRaises(ValueError): build_runtime(ROOT/"universal-project-governance",output,mutant)
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); source=base/"source"; source.mkdir(); (source/"policy-index.json").write_text('{"policies":[]}')
            output=base/"output"; output.mkdir(); (output/"preserved").write_bytes(b"original")
            with self.assertRaises(ValueError): build_runtime(source,output,mutant)
            self.assertEqual((output/"preserved").read_bytes(),b"original")
            self.assertFalse(list(base.glob("*.building-*")))

    def test_mutant_rejects_noop_and_scrubs_references(self):
        original={"policies":[{"id":"p"},{"id":"q","requires":["p"],"conflicts_with":["p"]}],"default_rules":["p"],"operational_guidance":[{"policy_ids":["p"]}],"profiles":{"a":{"activates":["p"]}},"presentation":{"policy_order":["p"]}}
        mutated=apply_mutant(original,{"operation":"remove_policy","target":"p"})
        self.assertNotIn('"p"',json.dumps(mutated))
        self.assertEqual(original["policies"][0]["id"],"p")
        with self.assertRaises(ValueError): apply_mutant(original,{"operation":"remove_requirement","target":"q","value":"absent"})

    def test_command_usage_invalid_json_shape_and_utf8_still_returns_evidence(self):
        for payload in ("[]","{broken"):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td); (root/"usage.json").write_text(payload)
                adapter=CommandAdapter({"timeout_seconds":3,"usage_file":"usage.json","command":[sys.executable,"-c","import sys;sys.stdout.buffer.write(bytes([255]))"]})
                result=adapter.run(root,"task","")
                self.assertEqual(result["exit_code"],0)
                self.assertTrue(result["events"]["usage_file_invalid"])
                self.assertIn("stdout_sha256",result["evidence"])

    def test_adapter_paths_and_runtime_identity_cannot_collide(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); (base/"command_adapter.py").write_bytes(b"different")
            adapter=CommandAdapter({"adapter_runtime_files":["command_adapter.py"]},base)
            first=adapter.identity()["adapter_runtime_sha256"]
            (base/"command_adapter.py").write_bytes(b"changed")
            self.assertNotEqual(first,adapter.identity()["adapter_runtime_sha256"])
            for raw in ("../secret","C:/secret","/secret"):
                with self.assertRaises(ValueError): adapter._contained_file(base,raw)

    def test_jsonl_adapter_ignores_nonobject_events(self):
        text='null\n[]\n{"type":"item.completed","item":null}\n{"type":"turn.completed","usage":null}\n'
        self.assertFalse(codex_cli._usage(text)["usage_available"])
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(codex_cli._diagnostics(text,Path(td)/"last",0,False)["errors"],[])

    def test_preflight_timeout_not_masked_by_diagnostic_io_failure(self):
        with patch.object(codex_cli.sys,"platform","win32"),patch.object(codex_cli.subprocess,"run",side_effect=subprocess.TimeoutExpired(["cli"],1)),patch.object(codex_cli,"_write_raw",side_effect=OSError("disk full")):
            with self.assertRaises(codex_cli.PreflightTimeoutError): codex_cli._preflight_windows_sandbox("cli",{},"output.json",1)

    def test_evidence_path_shape_and_collection_failure_leave_no_claim(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); workspace=root/"workspace"; workspace.mkdir(); (workspace/"large").write_bytes(b"x"*1000001)
            args=SimpleNamespace(output=str(root/"trial.json"))
            with self.assertRaises(ValueError): persist_evidence(args,"../escape",workspace)
            with self.assertRaises(ValueError): persist_evidence(args,"trial",workspace)
            self.assertFalse((root/"artifacts/trial").exists())
            (workspace/"large").unlink()
            evidence=persist_evidence(args,"trial",workspace)
            self.assertTrue(Path(evidence["artifact_manifest"]).is_file())

    def test_malformed_binding_and_artifact_are_failed_checks(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); governance=root/".governance"; governance.mkdir(); (governance/"upg.json").write_text('[]')
            self.assertEqual(project_integration_status(root)["managed_project_files"],1)
            (governance/"field-reports.json").write_text('{}')
            self.assertFalse(project_integration_status(root)["binding_ok"])
            path=root/"artifact.json"; data=b"[]"; path.write_bytes(data)
            row={"trial_id":"t","evidence":{"artifact_manifest":str(path),"artifact_manifest_sha256":"sha256:"+hashlib.sha256(data).hexdigest()}}
            self.assertTrue(verify_artifact(row))

    def test_large_mcnemar_and_invalid_pairs(self):
        self.assertGreater(mcnemar_exact_p(512,512),0.99)
        row={"arm":"A0","outcome":{"task_success":True}}
        with self.assertRaisesRegex(ValueError,"duplicate"): paired_binary([row,row],"A0","A2","task_success")
        with self.assertRaisesRegex(ValueError,"boolean"): paired_binary([row,{"arm":"A2","outcome":{"task_success":"false"}}],"A0","A2","task_success")

    def test_bootstrap_point_estimate_uses_same_hierarchy_as_resampling(self):
        observations=[{"agent_family":"a","scenario_id":"one","pair_id":str(i),"delta":1} for i in range(20)]+[{"agent_family":"b","scenario_id":"two","pair_id":"x","delta":-1}]
        self.assertEqual(hierarchical_bootstrap_delta(observations,reps=100)["mean_delta"],0)

    def test_zero_pair_gate_and_ablated_handoff_failure_do_not_pass(self):
        protocol=json.loads((ROOT/"qualification/protocol/qualification-v3.json").read_text(encoding="utf-8"))
        thresholds=json.loads((ROOT/"qualification/protocol/thresholds.json").read_text(encoding="utf-8"))
        self.assertEqual(core_task([],protocol,thresholds,{"state":"PASS"})["state"],"MORE_DATA")
        failure=protocol["critical_failure_classes"][0]
        row={"arm":"A2","kind":"handoff","environment":{"qualification_set":"locked","handoff_condition":"ablated"},"outcome":{"critical_failures":[failure]}}
        self.assertEqual(critical_safety([row],protocol,thresholds)["state"],"FAIL")

    def test_coverage_null_environment_and_missing_scenario_do_not_crash(self):
        protocol=json.loads((ROOT/"qualification/protocol/qualification-v3.json").read_text(encoding="utf-8"))
        for function in (behavioral_coverage,handoff_coverage):
            self.assertEqual(function([{"environment":None}],protocol)["state"],"MORE_DATA")
        row={"kind":"handoff","arm":"A2","environment":{"qualification_set":"locked"},"agent":{},"outcome":{}}
        self.assertEqual(handoff_coverage([row],protocol)["state"],"FAIL")

    def test_result_schema_embeds_current_trial_contract_without_resource_marker(self):
        schemas=ROOT/"qualification/protocol/schemas"
        trial=json.loads((schemas/"trial.schema.json").read_text(encoding="utf-8")); trial.pop("$schema")
        result=json.loads((schemas/"result.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(result["properties"]["trials"]["items"],trial)
        self.assertEqual(result["properties"]["trials"]["minItems"],1)


if __name__=="__main__": unittest.main()
