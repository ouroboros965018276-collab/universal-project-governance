"""RC9 engineering regressions. No real Agent execution or qualification result is produced."""
import ast
import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'universal-project-governance/scripts'))
# The suite must not mutate the tree it validates: importing the generated runtime scripts
# in-process would otherwise write scripts/__pycache__ into release source, and later runs
# would fail the packaging and mutant-manifest checks on that residue.
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import project_tool
from plan_governance import compile_plan, load_index
from state_tool import validate_node
from qualification.analysis.admission import admit, verify_artifact
from qualification.analysis.gates import critical_safety, deployment_integrity
from qualification.adapters.command_adapter import CommandAdapter
from qualification.adapters.codex_cli import install as install_codex_skill
from qualification.lib.core import evaluate_check, grade_lab, materialize_lab, snapshot
from qualification.round_manifest import build_manifest
from qualification.dev_smoke import build_manifest as build_dev_smoke_manifest, rejects_development_before_inference
from tools.qualification_freeze import expected
from registration_fixture import registered_fixture, freeze, change
import test_qualification as legacy
from qualification.analyze import analyze as release_analyze
from qualification.lib.contracts import configuration_errors
from qualification.lib.execution import registration
from qualification.run_trial import prepare_a2_reporting
from types import SimpleNamespace

def report(workflow='test-workflow', parent=None):
    metadata = change(); metadata['parent_event_id'] = parent
    return dict(workflow_id=workflow, change=metadata, task='engineering acceptance', status='complete', change_mode='local', scope_guard='local-only', risk_level='low', active_rules=[], changed_files=[], validation=['unit test'], cleanup=[], structural_scope={'canonical_layer':'runtime', 'unrelated_changes':[], 'api_changes':[], 'architecture_changes':[], 'overreach_concern':False}, integrity='pass', handoff='not-required', feedback=[])

def write(path, data):
    pathlib.Path(path).write_bytes((json.dumps(data) + '\n').encode())
    return pathlib.Path(path)

class RC9Tests(unittest.TestCase):
    def enable_reporting(self, project):
        project_tool.ensure(project, field_test_reporting=True)

    def test_multilingual_trigger_cli_handles_cp1252_stdout(self):
        env=dict(os.environ,PYTHONIOENCODING='cp1252',PYTHONDONTWRITEBYTECODE='1')
        cp=subprocess.run([sys.executable,'qualification/trigger_suite.py'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(cp.returncode,0,cp.stderr.decode('ascii',errors='replace'))
        cp.stdout.decode('ascii')
        data=json.loads(cp.stdout.decode('ascii'))
        self.assertTrue(any(any(ord(c)>127 for c in case['query']) for case in data['cases']))
        with tempfile.TemporaryDirectory() as td:
            path=write(pathlib.Path(td)/'context.json',{'operation':'edit','domains':['content'],'profiles':['未知项目']})
            cp=subprocess.run([sys.executable,str(ROOT/'universal-project-governance/scripts/plan_governance.py'),'--context',str(path),'--json'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(cp.returncode,0,cp.stderr.decode('ascii',errors='replace'))
            self.assertTrue(any('未知项目' in item for item in json.loads(cp.stdout.decode('ascii'))['warnings']))

    def test_a2_qualification_workspace_explicitly_opts_into_reporting(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td) / 'workspace'
            workspace.mkdir()
            prepare_a2_reporting(workspace, ROOT / 'universal-project-governance')
            state = project_tool.status(workspace)
            self.assertTrue(state['ok'])
            self.assertTrue(state['field_test_reporting'])
            self.assertEqual(state['report_count'], 0)

    def test_codex_adapter_installs_only_an_integrity_checked_skill_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td) / 'workspace'
            workspace.mkdir()
            install_codex_skill(workspace, ROOT / 'universal-project-governance')
            installed = workspace / '.agents/skills/universal-project-governance'
            self.assertTrue((installed / 'SKILL.md').is_file())
            cp = subprocess.run(
                [sys.executable, str(installed / 'scripts/validate_integrity.py'), str(installed)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_adapter_skill_setup_is_outside_measured_agent_changes(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = pathlib.Path(td) / 'workspace'
            workspace.mkdir()
            lab = {
                'initial_files': {'README.md': 'Installtion instructions.\n'},
                'checks': [
                    {'type': 'contains', 'path': 'README.md', 'text': 'Installation'},
                    {'type': 'max_changed_files', 'value': 1},
                ],
                'scope_contract': {'allowed_change_globs': ['README.md']},
            }
            materialize_lab(lab, workspace)
            install = "from pathlib import Path; p=Path(r'{workspace}')/'.agents'/'installed'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(str(int(p.read_text() if p.exists() else '0')+1))"
            adapter = CommandAdapter({
                'skill_install_command': [sys.executable, '-c', install],
                'command': [sys.executable, '-c', 'pass'],
            })
            adapter.prepare_skill(workspace, 'test task', '', ROOT / 'universal-project-governance')
            before = snapshot(workspace)
            (workspace / 'README.md').write_text('Installation instructions.\n', encoding='utf-8')
            adapter.run(
                workspace, 'test task', '', skill_path=ROOT / 'universal-project-governance',
                skill_prepared=True,
            )
            self.assertEqual((workspace / '.agents/installed').read_text(), '1')
            result = grade_lab(lab, workspace, before)
            self.assertTrue(result['task_success'])
            self.assertEqual(result['changed_files'], ['README.md'])

    def test_codex_cli_adapter_ignores_user_mcp_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            task = pathlib.Path(td) / 'task.txt'
            condition = pathlib.Path(td) / 'condition.md'
            output = pathlib.Path(td) / 'adapter-output.json'
            task.write_text('bounded task', encoding='utf-8')
            condition.write_text('', encoding='utf-8')
            with patch('qualification.adapters.codex_cli.sys.platform', 'linux'), patch(
                'qualification.adapters.codex_cli.shutil.which', return_value='codex'
            ), patch(
                'qualification.adapters.codex_cli.subprocess.run',
                return_value=subprocess.CompletedProcess([], 0, '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n', 'diagnostic stderr'),
            ) as run:
                from qualification.adapters.codex_cli import run as run_codex
                self.assertEqual(run_codex(td, task, condition, output, 'single', 'gpt-5.5', ROOT / 'universal-project-governance'), 0)
                command = run.call_args.args[0]
                self.assertIn('--ignore-user-config', command)
                result = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(result['usage']['total_tokens'], 12)
                self.assertEqual(result['events']['event_counts']['turn.completed'], 1)
                self.assertEqual(result['stderr'], 'diagnostic stderr')

    def test_windows_codex_adapter_reapplies_only_allowlisted_host_preferences(self):
        with tempfile.TemporaryDirectory() as td:
            home = pathlib.Path(td)
            (home / 'config.toml').write_text(
                'approval_policy = "never"\n'
                '[windows]\nsandbox = "elevated"\n'
                '[features]\nrespect_system_proxy = true\n'
                '[mcp_servers.untrusted]\ncommand = "must-not-load"\n',
                encoding='utf-8',
            )
            task = home / 'task.txt'
            condition = home / 'condition.md'
            output = home / 'adapter-output.json'
            task.write_text('bounded task', encoding='utf-8')
            condition.write_text('', encoding='utf-8')
            with patch('qualification.adapters.codex_cli.sys.platform', 'win32'), patch.dict(
                os.environ, {'CODEX_HOME': td, 'CODEX_CLI_PATH': ''}, clear=False
            ), patch(
                'qualification.adapters.codex_cli.tomllib',
                SimpleNamespace(loads=lambda _: {
                    'windows': {'sandbox': 'elevated'},
                    'features': {'respect_system_proxy': True},
                }),
            ), patch('qualification.adapters.codex_cli.shutil.which', return_value='codex.exe'), patch(
                'qualification.adapters.codex_cli.subprocess.run',
                return_value=subprocess.CompletedProcess([], 0, '{"type":"turn.completed"}\n', ''),
            ) as run:
                from qualification.adapters.codex_cli import run as run_codex
                self.assertEqual(run_codex(td, task, condition, output, 'single', 'gpt-5.5', None), 0)
                command = run.call_args.args[0]
                self.assertEqual(command[:8], [
                    'codex.exe', '-c', 'windows.sandbox="elevated"',
                    '--enable', 'respect_system_proxy', '-c', 'suppress_unstable_features_warning=true', 'exec',
                ])
                self.assertNotIn('--ask-for-approval', command)
                self.assertIn('--ignore-user-config', command)
                self.assertIn('--sandbox', command)
                self.assertEqual(command[command.index('--sandbox') + 1], 'workspace-write')
                result = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(result['host_adaptation'], {
                    'windows_sandbox': 'elevated',
                    'respect_system_proxy': True,
                })

    def test_command_adapter_does_not_forward_undeclared_host_environment(self):
        adapter = CommandAdapter({'environment_passthrough': ['CODEX_HOME', 'HTTPS_PROXY']})
        with patch.dict(os.environ, {
            'CODEX_HOME': 'C:/codex-home', 'HTTPS_PROXY': 'http://proxy.invalid:8080',
            'CODEX_THREAD_ID': 'outer-thread', 'CODEX_SHELL': 'outer-shell',
        }, clear=True):
            env = adapter._environment()
        self.assertEqual(env['CODEX_HOME'], 'C:/codex-home')
        self.assertEqual(env['HTTPS_PROXY'], 'http://proxy.invalid:8080')
        self.assertNotIn('CODEX_THREAD_ID', env)
        self.assertNotIn('CODEX_SHELL', env)

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
            return admit(rows, fingerprint or freeze()['qualification_fingerprint'], legacy.load_protocol(full_inference=True), manifest, thresholds=legacy.load_thresholds())

    def test_admission_requires_manifest_and_correct_fingerprint(self):
        rows, manifest = self.registered()
        self.assertEqual(self.admission(rows, None)['state'], 'FAIL')
        formal=legacy.load_protocol(full_inference=True); thresholds=legacy.load_thresholds()
        self.assertEqual(configuration_errors(thresholds,formal),[])
        relaxed=copy.deepcopy(thresholds); relaxed['core_task_non_inferiority']['margin_absolute']=-1.0
        result=release_analyze(rows,relaxed,formal,freeze()['qualification_fingerprint'],manifest)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(any('thresholds' in x for x in result['gates']['evidence_admission']['errors']))
        self.assertTrue(configuration_errors(thresholds,legacy.load_protocol()))
        self.assertEqual(self.admission(rows, manifest, 'sha256:'+'0'*64)['state'], 'FAIL')
        with patch('tools.qualification_freeze.expected',return_value={}):
            self.assertEqual(self.admission(rows,manifest)['state'],'FAIL')
            self.assertEqual(release_analyze([], thresholds, formal, freeze()['qualification_fingerprint'])['status'], 'FAIL')
            with self.assertRaises(ValueError):
                build_manifest('drifted', [], 8, 1729)
            with tempfile.TemporaryDirectory() as td:
                path=write(pathlib.Path(td)/'round.json',manifest)
                args=SimpleNamespace(locked_holdout=True,round_manifest=str(path),trial_id='unexecuted')
                with self.assertRaises(ValueError):
                    registration(args, None, 'behavioral', 'unused', 'A2')
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

    def test_trial_schema_represents_unisolated_development_without_relaxing_locked_admission(self):
        rows, manifest = self.registered()
        row = copy.deepcopy(rows[0])
        row['environment'].update(
            qualification_set='dev',
            sandboxed=False,
            workspace_isolation='process',
            isolation_attestation=None,
        )
        schema = json.loads((ROOT/'qualification/protocol/schemas/trial.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(validate_node(row, schema), [])
        result = self.admission([row], manifest)
        self.assertEqual(result['state'], 'FAIL')
        self.assertTrue(any('development evidence cannot promote release' in item for item in result['errors']))

    def test_locked_admission_checks_actual_isolation_even_with_valid_schema(self):
        rows, manifest = self.registered()
        row = copy.deepcopy(rows[0])
        row['environment'].update(sandboxed=False, workspace_isolation='process', isolation_attestation=None)
        result = self.admission([row], manifest)
        self.assertEqual(result['state'], 'FAIL')
        self.assertTrue(any('strong workspace isolation' in item for item in result['errors']))
        self.assertTrue(any('operator isolation attestation' in item for item in result['errors']))

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
            self.enable_reporting(td)
            path=write(pathlib.Path(td)/'report.json',report())
            with patch.object(project_tool,'_reconcile_completion',side_effect=OSError('simulated interruption')):
                with self.assertRaises(OSError): project_tool.record_report(td,path)
            self.assertTrue(project_tool.record_report(td,path)['idempotent'])
            self.assertEqual(project_tool.status(td)['report_count'],1)
            altered=report(); altered['task']='conflict'; write(path,altered)
            with self.assertRaises(ValueError): project_tool.record_report(td,path)

    def test_epoch_rotation_requires_export_and_preserves_sequence_and_parent(self):
        with tempfile.TemporaryDirectory() as td:
            self.enable_reporting(td)
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
            self.enable_reporting(td)
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
            self.enable_reporting(td)
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

    def test_development_smoke_registration_binds_agent_and_trial_identity(self):
        adapter = CommandAdapter({
            'id': 'dev-adapter',
            'agent': {'family': 'codex', 'model_id': 'configured', 'scaffold_version': 'test'},
            'host_tool': {'name': 'codex', 'version': 'test'},
            'capabilities': ['skill_injection'],
            'sandboxed': False,
            'workspace_isolation': 'process',
            'command': ['unused'],
        })
        manifest = build_dev_smoke_manifest(adapter, 'dev-small-typo', 'dev-smoke-test')
        with tempfile.TemporaryDirectory() as td:
            manifest_path = write(pathlib.Path(td) / 'registration.json', manifest)
            args = SimpleNamespace(
                locked_holdout=False,
                round_manifest=str(manifest_path),
                trial_id=manifest['trials'][0]['trial_id'],
                pair_id=manifest['trials'][0]['pair_id'],
                output=str(pathlib.Path(td) / 'trial.json'),
            )
            registered = registration(args, adapter, 'behavioral', 'dev-small-typo', 'A2')
            self.assertEqual(registered['trial_id'], args.trial_id)
            args.pair_id = 'different-pair'
            with self.assertRaisesRegex(ValueError, 'pair_id'):
                registration(args, adapter, 'behavioral', 'dev-small-typo', 'A2')

    def test_development_smoke_requires_release_rejection_before_inference(self):
        early = {
            'status': 'FAIL',
            'gates': {'evidence_admission': {'errors': ['row 0: development evidence cannot promote release']}},
            'notes': ['Evidence rejected before inference.'],
            'effects': {},
        }
        late = dict(early, notes=['Inference completed.'], effects={'governance_uplift': {'state': 'FAIL'}})
        self.assertTrue(rejects_development_before_inference(early))
        self.assertFalse(rejects_development_before_inference(late))

    def test_adapter_runtime_identity_includes_declared_helper_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            helper = pathlib.Path(td) / 'adapter-helper.py'
            helper.write_text('VALUE = 1\n', encoding='utf-8')
            config = {
                'agent': {'family': 'codex', 'model_id': 'configured', 'scaffold_version': 'test'},
                'host_tool': {'name': 'codex', 'version': 'test'},
                'adapter_runtime_files': [str(helper)],
            }
            adapter = CommandAdapter(config)
            first = adapter.identity()['adapter_runtime_sha256']
            helper.write_text('VALUE = 2\n', encoding='utf-8')
            second = adapter.identity()['adapter_runtime_sha256']
            self.assertNotEqual(first, second)

if __name__=='__main__': unittest.main()
