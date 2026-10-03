"""RC9 engineering regressions. No real Agent execution or qualification result is produced."""
import ast
import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'universal-project-governance/scripts'))
import project_tool
from plan_governance import compile_plan, load_index
from state_tool import validate_node
from qualification.analysis.admission import admit, verify_artifact
from qualification.analysis.gates import critical_safety, deployment_integrity
from qualification.adapters.command_adapter import CommandAdapter
from qualification.lib.core import evaluate_check, materialize_lab, snapshot
from qualification.round_manifest import build_manifest
from tools.qualification_freeze import expected
from registration_fixture import registered_fixture, freeze, change
import test_qualification as legacy

def report(workflow='test-workflow', parent=None):
    metadata = change(); metadata['parent_event_id'] = parent
    return dict(workflow_id=workflow, change=metadata, task='engineering acceptance', status='complete', change_mode='local', scope_guard='local-only', risk_level='low', active_rules=[], changed_files=[], validation=['unit test'], cleanup=[], structural_scope={'canonical_layer':'runtime', 'unrelated_changes':[], 'api_changes':[], 'architecture_changes':[], 'overreach_concern':False}, integrity='pass', handoff='not-required', feedback=[])

def write(path, data):
    pathlib.Path(path).write_bytes((json.dumps(data) + '\n').encode())
    return pathlib.Path(path)

class RC9Tests(unittest.TestCase):
    def test_unknown_project_profile_keeps_universal_scope_and_rules(self):
        base={'operation':'edit','domains':['content'],'profiles':[],'signals':[],'risk':{}}
        known=compile_plan(load_index(),base)
        fallback=compile_plan(load_index(),dict(base,profiles=['future-unlisted-project']))
        self.assertEqual(known['active_rules'],fallback['active_rules'])
        self.assertEqual(known['scope_guard'],fallback['scope_guard'])
        self.assertTrue(any('universal' in x for x in fallback['warnings']))

    def registered(self):
        raw = legacy.QualificationTests()._synthetic_rows(repetitions=1)
        return registered_fixture(raw)

    def admission(self, rows, manifest, fingerprint=None):
        with patch('qualification.analysis.admission.verify_artifact', return_value=[]):
            return admit(rows, fingerprint or freeze()['qualification_fingerprint'], legacy.load_protocol(), manifest)

    def test_admission_requires_manifest_and_correct_fingerprint(self):
        rows, manifest = self.registered()
        self.assertEqual(self.admission(rows, None)['state'], 'FAIL')
        self.assertEqual(self.admission(rows, manifest, 'sha256:'+'0'*64)['state'], 'FAIL')
        rows[0]['fingerprints']['qualification'] = 'sha256:'+'0'*64
        self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')

    def test_admission_rejects_unsandboxed_boolean_lookalike(self):
        for value in [False, 1, 'true']:
            rows, manifest = self.registered(); rows[0]['environment']['sandboxed'] = value
            self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')

    def test_admission_rejects_unregistered_duplicate_and_malformed_trials(self):
        rows, manifest = self.registered()
        self.assertEqual(self.admission(rows + [copy.deepcopy(rows[0])], manifest)['state'], 'FAIL')
        rows[0]['trial_id'] = 'unregistered'
        self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')
        self.assertEqual(self.admission([{}], manifest)['state'], 'FAIL')
        self.assertEqual(self.admission(rows, dict(manifest, trials=['invalid']))['state'], 'FAIL')

    def test_missing_registered_trial_is_more_data(self):
        rows, manifest = self.registered()
        result = self.admission(rows[1:], manifest)
        self.assertEqual(result['state'], 'MORE_DATA')
        self.assertIn(rows[0]['trial_id'], result['missing_trials'])

    def test_admission_binds_fixture_profile_exposure_and_scope(self):
        for field in ['exposure', 'profile', 'scope']:
            rows, manifest = self.registered(); row = next(r for r in rows if r['kind']=='behavioral' and r['arm']=='A2')
            if field == 'exposure': row['safety_exposures'] = []
            if field == 'profile': row['environment']['project_profile'] = 'invented'
            if field == 'scope': row['outcome']['scope_metrics']['overreach_exposure'] = 'invented'
            self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')

    def test_admission_enforces_repetition_and_time(self):
        rows, manifest = self.registered(); rows[0]['repetition'] = 13; manifest['trials'][0]['repetition'] = 13
        self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')
        rows, manifest = self.registered(); rows[0]['completed_at'] = '1999-01-01T00:00:00Z'
        self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')

    def test_source_identity_and_trigger_target_cannot_drift(self):
        rows, manifest = self.registered(); row = next(r for r in rows if r['kind']=='handoff'); row['environment']['source_model_id']='other'
        self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')
        rows, manifest = self.registered(); row = next(r for r in rows if r['kind']=='trigger'); row['outcome']['should_trigger'] = not row['outcome']['should_trigger']
        self.assertEqual(self.admission(rows, manifest)['state'], 'FAIL')

    def test_artifact_bytes_and_trial_identity_are_verified(self):
        with tempfile.TemporaryDirectory() as td:
            path=write(pathlib.Path(td)/'manifest.json', {'trial_id':'t', 'before':{}, 'after':{}, 'execution':{}})
            row={'trial_id':'t', 'evidence':{'artifact_manifest':str(path), 'artifact_manifest_sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()}}
            self.assertEqual(verify_artifact(row), [])
            path.write_bytes(path.read_bytes()+b' ')
            self.assertTrue(verify_artifact(row))
            row['evidence']['artifact_manifest_sha256']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(); row['trial_id']='other'
            self.assertTrue(verify_artifact(row))

    def test_schema_const_time_and_nonfinite_numbers_fail(self):
        self.assertTrue(validate_node(1, {'const':True}))
        self.assertTrue(validate_node(True, {'const':1}))
        self.assertTrue(validate_node(float('nan'), {'type':'number'}))
        for text in ['2026-02-30T12:00:00Z', '2026-10-03T12:00:00', 'yesterday']:
            self.assertTrue(validate_node(text, {'type':'string','format':'date-time'}))
        self.assertEqual(validate_node('2026-10-03T20:00:00+08:00', {'type':'string','format':'date-time'}), [])
        payload=report(); payload['change']['base_revision']='deadbee'
        with self.assertRaises(ValueError): project_tool.validate_report(payload)

    def test_observed_critical_failure_outside_exposure_still_fails(self):
        row={'kind':'behavioral','arm':'A2','environment':{'qualification_set':'locked'}, 'safety_exposures':[], 'outcome':{'critical_failures':['CF01_UNSAFE_DELETION']}}
        result=critical_safety([row], legacy.load_protocol(), legacy.load_thresholds())
        self.assertEqual(result['state'],'FAIL')
        self.assertEqual(result['classes']['CF01_UNSAFE_DELETION']['exposures'],0)

    def test_invalid_single_report_does_not_pass_deployment(self):
        row={'kind':'behavioral','arm':'A2','environment':{'qualification_set':'locked'},'outcome':{'deployment':{'binding_ok':True,'report_count':1,'field_report_recorded':False}},'usage':{'managed_project_files':2}}
        self.assertEqual(deployment_integrity([row],legacy.load_thresholds(),{'state':'PASS','complete_pairs':1})['state'],'FAIL')

    def test_freeze_is_identical_after_repository_relocation(self):
        with tempfile.TemporaryDirectory() as td:
            target=pathlib.Path(td)/'moved'
            shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','.governance','__pycache__','*.pyc','dist'))
            self.assertEqual(expected(ROOT),expected(target))

    def test_all_initial_python_and_json_files_parse(self):
        count=0
        for path in (ROOT/'qualification/fixtures').rglob('*.json'):
            data=json.loads(path.read_text(encoding='utf-8'))
            for lab in data.get('labs',[]):
                for rel,text in lab.get('initial_files',{}).items():
                    if rel.endswith('.py'): ast.parse(text,filename=rel); count+=1
                    if rel.endswith('.json'): json.loads(text); count+=1
        self.assertGreaterEqual(count,19)

    def test_chronology_requires_owner_truth_and_actual_task(self):
        with tempfile.TemporaryDirectory() as td:
            lab=json.loads((ROOT/'qualification/fixtures/holdout/locked/behavioral-labs.json').read_text(encoding='utf-8'))['labs']
            lab=next(x for x in lab if any(c['type']=='chronology' for c in x['checks']))
            before=materialize_lab(lab,td); check=next(c for c in lab['checks'] if c['type']=='chronology')
            path=pathlib.Path(td)/check['path']; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('previous 2026-01-01 deadbee',encoding='utf-8')
            self.assertFalse(evaluate_check(check,td,before,snapshot(td))['pass'])
            exact={'previous_event_id':'owner-import','function':'workflow','before':'step=previous','after':'step=current','rationale':'user-requested workflow update','source':'task and owner notes','prior_occurred_at':None,'prior_commit':None,'validation':'workflow.txt contains step=current'}
            write(path,exact)
            self.assertFalse(evaluate_check(check,td,before,snapshot(td))['pass'])
            (pathlib.Path(td)/'workflow.txt').write_text('step=current\n',encoding='utf-8')
            self.assertTrue(evaluate_check(check,td,before,snapshot(td))['pass'])

    def test_report_retry_conflict_and_crash_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            path=write(pathlib.Path(td)/'report.json',report())
            with patch.object(project_tool,'_reconcile_completion',side_effect=OSError('simulated interruption')):
                with self.assertRaises(OSError): project_tool.record_report(td,path)
            self.assertTrue(project_tool.record_report(td,path)['idempotent'])
            self.assertEqual(project_tool.status(td)['report_count'],1)
            altered=report(); altered['task']='conflict'; write(path,altered)
            with self.assertRaises(ValueError): project_tool.record_report(td,path)

    def test_epoch_rotation_requires_export_and_preserves_sequence_and_parent(self):
        with tempfile.TemporaryDirectory() as td:
            path=write(pathlib.Path(td)/'report.json',report('first'))
            project_tool.record_report(td,path)
            parent=project_tool.status(td)['latest_change']['event_id']
            with self.assertRaises(ValueError): project_tool.purge_reports(td,True)
            project_tool.export_reports(td,pathlib.Path(td)/'export.json'); project_tool.purge_reports(td,True)
            write(path,report('second'))
            with self.assertRaises(ValueError): project_tool.record_report(td,path)
            write(path,report('second',parent)); result=project_tool.record_report(td,path)
            self.assertEqual(result['sequence'],2)
            ledger=json.loads((pathlib.Path(td)/'.governance/field-reports.json').read_text(encoding='utf-8'))
            self.assertEqual(ledger['epoch'],1)
            self.assertEqual(project_tool.status(td)['previous_change']['event_id'],parent)

    def test_old_retry_does_not_rewind_latest_change(self):
        with tempfile.TemporaryDirectory() as td:
            first=write(pathlib.Path(td)/'first.json',report('first')); project_tool.record_report(td,first)
            parent=project_tool.status(td)['latest_change']['event_id']
            second=write(pathlib.Path(td)/'second.json',report('second',parent)); project_tool.record_report(td,second)
            latest=project_tool.status(td)['latest_change']
            project_tool.record_report(td,first)
            self.assertEqual(project_tool.status(td)['latest_change'],latest)

    def test_workflow_start_is_idempotent_and_preserves_origin(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as inputs:
            project_tool.ensure(td)
            self.assertEqual(json.loads((pathlib.Path(td)/'.governance/upg.json').read_text())['project_origin'],'new')
            start={'workflow_id':'one','change':change()}; path=write(pathlib.Path(inputs)/'start.json',start)
            original=project_tool.begin_workflow(td,path)
            self.assertEqual(project_tool.begin_workflow(td,path)['active_workflow'],original['active_workflow'])
            start['workflow_id']='two'; write(path,start)
            with self.assertRaises(ValueError): project_tool.begin_workflow(td,path)

    def test_concurrent_report_retries_record_one_entry(self):
        with tempfile.TemporaryDirectory() as td:
            path=write(pathlib.Path(td)/'report.json',report())
            cmd=[sys.executable,str(ROOT/'universal-project-governance/scripts/project_tool.py'),'report',td,'--input',str(path)]
            children=[subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
            for child in children:
                out,err=child.communicate(timeout=15); self.assertEqual(child.returncode,0,out+err)
            self.assertEqual(project_tool.status(td)['report_count'],1)

    def test_round_plan_is_reproducible_and_does_not_execute_agents(self):
        adapters=[CommandAdapter({'agent':{'family':family,'model_id':'test','scaffold_version':'1'},'host_tool':{'name':'unit','version':'1'},'sandboxed':True,'workspace_isolation':'container','isolation_attestation':{'issuer':'unit','reference':'synthetic only','sha256':'sha256:'+'a'*64}}) for family in ['a','b','c']]
        with patch.object(CommandAdapter,'run',side_effect=AssertionError('must not execute')):
            first=build_manifest('unit-plan',adapters,8,17); second=build_manifest('unit-plan',adapters,8,17)
        self.assertEqual(first,second)
        self.assertEqual(len({x['trial_id'] for x in first['trials']}),len(first['trials']))
        self.assertNotEqual(first['trials'],build_manifest('unit-plan',adapters,8,18)['trials'])
        with self.assertRaises(ValueError): build_manifest('unit-plan',adapters,13,17)

if __name__=='__main__': unittest.main()
