"""Public synthetic engineering API tests; no live providers, processes or containers."""
import sys
import unittest

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Engineering API tests require Python 3.10+; no evolution import attempted")

import copy
import hashlib
import json
import pathlib
import types
from unittest.mock import Mock, patch

from test_provider_tools import _ProviderFixture, call, completion
import evolution.provider_tools as lab
from evolution.tool_broker import RepoBroker, canonical, sha, tool_definitions, validate_task

# Observed original baseline source, not a second implementation.
DEFAULT_WIRE_BASELINE_SOURCE_SHA256 = '0ceb714e31d2f8ff833bf2906cedea20b4cd3e02b0d83a0044c1052ea2ffd01a'
DEFAULT_WIRE_PAYLOAD_SHA256 = ('d73c24a6d9075b10873a9b67b7bee689a844fbbfe2255bd11de2ed89490057af', '09f202412caa6324514c771aff8fe96fcf434e7cdd0f2313b87c6103a1f5bdd2', 'b8584d858705b2e00f1bd6512c928f9bf9de4cc7d7ea7aa735e4026b90aba3fd', '39934e373733f737ba03fcb63a0d787d3332cac1b57c979b22f33fc99734b937')

PROFILE = 'stdlib-python-project-v1'
BACKEND = 'docker-cpython-project-v1'
ADAPTER = 'official-chat-api-registered-project-v1'


class EngineeringCandidateTests(_ProviderFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.executions = []
        self.brokers = []
        self.validation_unknown = False
        self.validation_failed = False
        self.deny_patch = False
        self.tamper_state = False
        owner = self

        class MockEngineeringBroker(RepoBroker):
            def call(self, name, args):
                result = super().call(name, args)
                if owner.tamper_state:
                    self.events[-1]['state_sha256'] = None
                return result

            def validate(self):
                owner.executions.append(sha(canonical(self.snapshot())))
                ok = not owner.validation_failed
                return {'ok': ok, 'suite': 'registered-python-project-checks-v1',
                        'checks_passed': int(ok), 'checks_total': 1,
                        'failures': [] if ok else ['registered-test-failed'],
                        'execution': {'status': 'EXECUTED', 'unknown': owner.validation_unknown,
                                      'received_snapshot_sha256': sha(canonical(self.snapshot()))}}

            def _execute(self, name, args):
                if name == 'repo_patch' and owner.deny_patch:
                    return {'ok': False, 'error': 'registered scope denied'}
                return super()._execute(name, args)

        def create(root, task, git_binary, *, audit_file=None, max_calls=32,
                   deadline=None, execution_artifacts=None):
            broker = MockEngineeringBroker(root, task, git_binary,
                         audit_file=audit_file, max_calls=max_calls, deadline=deadline)
            self.brokers.append((broker, execution_artifacts))
            return broker

        def execution(result, task, state):
            record = result.get('execution') if isinstance(result, dict) else None
            if (not isinstance(record, dict) or record.get('received_snapshot_sha256') != state
                    or type(record.get('unknown')) is not bool):
                return None
            return copy.deepcopy(record)

        def quality(broker, before, final_text, native_trace, extra_failures):
            # A test stub, not engineering source: prove API delegates pure grading.
            self.assertEqual(len(self.executions), len([e for e in broker.events if e['tool'] == 'repo_validate']))
            current = sha(canonical(broker.snapshot()))
            valid = [e for e in broker.events if e['tool'] == 'repo_validate' and e['state_sha256'] == current]
            good = bool(valid) and valid[-1]['result']['ok'] and not extra_failures
            return {'hard_pass': bool(good), 'task_success': int(bool(good)),
                    'required_tools_ok': bool(valid), 'scope_ok': True,
                    'failures': list(extra_failures),
                    'validation': valid[-1]['result'] if valid else None,
                    'evidence_adapter': ADAPTER}

        self.module = types.ModuleType('evolution.engineering_broker')
        self.module.PROFILE_ID, self.module.BACKEND_ID = PROFILE, BACKEND
        self.module.validate_task = Mock(side_effect=validate_task)
        self.module.create_broker = Mock(side_effect=create)
        self.module.tool_definitions = Mock(side_effect=tool_definitions)
        self.module.public_instruction = Mock(return_value='Synthetic engineering instruction. required_read_paths alone are mandatory. project_tool unavailable.')
        self.module.validate_execution_result = Mock(side_effect=execution)
        self.module.quality_from_current_receipts = Mock(side_effect=quality)
        module_patch = patch.dict(sys.modules, {'evolution.engineering_broker': self.module})
        module_patch.start()
        self.addCleanup(module_patch.stop)

    def new_actor(self, **kwargs):
        kwargs.setdefault('broker_profile_id', PROFILE)
        kwargs.setdefault('execution_backend', BACKEND)
        kwargs.setdefault('profile_id', lab.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE)
        kwargs.setdefault('model', 'deepseek-v4-pro')
        original = self.reserve
        def durable(metadata):
            value = original(metadata)
            return dict(value, reservation_receipt_sha256='c' * 64)
        self.reserve = durable
        try:
            with patch.dict(sys.modules, {'evolution.engineering_broker': self.module}):
                return self.run_actor(**kwargs)
        finally:
            self.reserve = original

    def finish(self, index):
        return completion(index, [call('finish-'+str(index), 'repo_finish',
            {'summary': 'Public synthetic completion', 'validation': 'passed',
             'helper_gap': 'project_tool unavailable in bounded broker'})])

    def run_steps(self, steps, **kwargs):
        with patch.object(lab, '_post', side_effect=self.scripted(steps)) as post:
            result = self.new_actor(**kwargs)
        return result, post.call_count

    def test_profile_delegates_and_never_implicitly_executes_at_finish(self):
        result, count = self.run_steps(self.ready()+[self.finish(4)])
        self.assertEqual(count, 4)
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(len(self.executions), 1)
        self.assertEqual(self.module.quality_from_current_receipts.call_count, 1)
        self.assertIsNone(self.brokers[0][1])
        self.assertIsNotNone(self.brokers[1][1])
        for item in (result, result['receipt'], result['final_report'], *self.before, *self.after, *result['api_tool_trace']):
            self.assertEqual(item['adapter'], ADAPTER)
            self.assertEqual(item['broker_profile_id'], PROFILE)
            self.assertEqual(item['execution_backend'], BACKEND)
        request = json.loads((self.artifacts/'requests/01.pending.json').read_text()) if (self.artifacts/'requests/01.pending.json').exists() else json.loads((self.artifacts/'requests/01.receipt.json').read_text())
        self.assertEqual(request['reservation_receipt_sha256'], 'c'*64)

    def test_schema_rejection_prevalidates_entire_batch_then_bounded_correction(self):
        invalid = self.patch_from_read(2, 'fixed\n')
        def batch(payload):
            response = invalid(payload)
            args = json.loads(response['choices'][0]['message']['tool_calls'][0]['function']['arguments'])
            args['operations'][0]['path_placeholder'] = 'extra'
            response['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = json.dumps(args)
            response['choices'][0]['message']['tool_calls'].append(call('validate-not-run','repo_validate',{}))
            return response
        correction = completion(3, [call('corrected-patch','repo_patch',{'operations':[
            {'path':'target.txt','old_sha256':sha(b'old\n'),'new_text':'fixed\n'}]})])
        result, count = self.run_steps([self.read(1),batch,correction,self.validate_and_status(4),self.finish(5)])
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(count, 5)
        self.assertEqual([e['tool'] for e in result['tool_events']], ['repo_read','repo_patch','repo_validate','repo_status'])
        self.assertEqual(len(self.executions), 1)
        self.assertEqual(result['schema_rejections'], 1)
        record=json.loads((self.artifacts/'schema-rejections/02.json').read_bytes())
        self.assertEqual(record['status'],'NOT_EXECUTED_SCHEMA_REJECTED')
        self.assertIs(record['batch_executed'],False)
        self.assertEqual(record['state_sha256'], result['tool_events'][0]['state_sha256'])

    def test_second_schema_rejection_is_terminal_without_budget_reset(self):
        bad = lambda index: completion(index,[call('bad-'+str(index),'repo_read',{'paths':['target.txt'],'extra':1})])
        result,count=self.run_steps([bad(1),bad(2)])
        self.assertEqual(count,2)
        self.assertEqual(result['status'],'tool-contract-failed')
        self.assertEqual(result['schema_rejections'],2)
        self.assertEqual(result['tool_events'],[])
        self.assertEqual(result['tool_attempts'],2)

    def test_scope_denial_is_terminal_without_schema_feedback(self):
        self.deny_patch=True
        result,count=self.run_steps([self.read(1),self.patch_from_read(2,'fixed\n')])
        self.assertEqual(count,2)
        self.assertEqual(result['status'],'tool-contract-failed')
        self.assertEqual(result['schema_rejections'],0)
        self.assertEqual(len(self.executions),0)

    def test_unknown_execution_stops_and_never_runs_final_validation(self):
        self.validation_unknown=True
        result,count=self.run_steps(self.ready())
        self.assertEqual(count,3)
        self.assertEqual(len(self.executions),1)
        self.assertTrue(result['execution_state_unknown'])
        self.assertFalse(result['quality']['hard_pass'])
        self.assertEqual(result['usage']['total_tokens'],45)

    def test_unknown_execution_preserves_actor_pending_fence(self):
        self.validation_unknown=True
        result,count=self.run_steps(self.ready())
        self.assertEqual(count,3)
        self.assertTrue((self.artifacts/'actor.pending.json').is_file())

    def test_schema_failure_cannot_hide_protected_path_later_in_batch(self):
        batch=completion(1,[call('bad-schema','repo_read',{'paths':['target.txt'],'extra':1}),
            call('protected-write','repo_patch',{'operations':[
                {'path':'contract.json','old_sha256':sha(b'{}\n'),'new_text':'changed\n'}]})])
        result,count=self.run_steps([batch])
        self.assertEqual(count,1)
        self.assertEqual(result['status'],'tool-contract-failed')
        self.assertEqual(result['schema_rejections'],0)
        self.assertEqual(result['tool_events'],[])

    def test_late_bad_schema_keeps_earlier_valid_patch_unexecuted(self):
        batch=completion(1,[call('valid-write','repo_patch',{'operations':[
            {'path':'target.txt','old_sha256':sha(b'old\n'),'new_text':'fixed\n'}]}),
            call('invalid-later','repo_status',{'extra':1})])
        result,count=self.run_steps([batch],max_requests=1)
        self.assertEqual(count,1)
        self.assertEqual((self.workspace/'target.txt').read_bytes(),b'old\n')
        self.assertEqual(result['tool_events'],[])
        self.assertEqual(result['schema_rejections'],1)

    def test_unverified_event_snapshot_is_terminal_before_next_request(self):
        self.tamper_state=True
        result,count=self.run_steps([self.read(1)])
        self.assertEqual(count,1)
        self.assertTrue(result['execution_state_unknown'])
        self.assertEqual(result['status'],'execution-state-unknown-blocked')
        self.assertEqual(len(self.executions),0)

    def test_schema_rejection_receipt_failure_cannot_continue(self):
        original=lab._write_new
        def reject(path,value,secret=''):
            if pathlib.Path(path).parent.name=='schema-rejections':
                raise OSError('synthetic receipt failure')
            return original(path,value,secret)
        bad=completion(1,[call('bad','repo_read',{'paths':['target.txt'],'extra':1})])
        with patch.object(lab,'_write_new',side_effect=reject):
            result,count=self.run_steps([bad])
        self.assertEqual(count,1)
        self.assertTrue(result['execution_state_unknown'])
        self.assertEqual(result['tool_events'],[])
        self.assertEqual(result['known_usage']['total_tokens'],15)

    def test_rejected_call_identity_cannot_be_replayed_as_corrected(self):
        bad=completion(1,[call('same-id','repo_read',{'paths':['target.txt'],'extra':1})])
        reused=completion(2,[call('same-id','repo_read',{'paths':['target.txt']})])
        result,count=self.run_steps([bad,reused])
        self.assertEqual(count,2)
        self.assertEqual(result['status'],'tool-contract-failed')
        self.assertEqual(result['schema_rejections'],1)
        self.assertEqual(result['tool_events'],[])

    def test_default_api_wire_is_byte_identical_to_baseline(self):
        # Fixed observed baseline payload hashes; no baseline implementation import.
        self.before,self.after,self.loaded=[],[],[]
        (self.workspace/'target.txt').write_bytes(b'old\n')
        self.artifacts=self.base/'default-wire-0'
        observed=[]
        def post(provider,payload,key,timeout):
            raw=json.dumps(copy.deepcopy(payload),ensure_ascii=False,sort_keys=True,
                           separators=(',',':'),allow_nan=False).encode('utf-8')
            observed.append(hashlib.sha256(raw).hexdigest())
            return self.positive(provider,payload,key,timeout)
        with patch.object(lab,'_post',side_effect=post):
            result=lab.run_actor('deepseek','mock-requested-model',self.task,self.workspace,
                self.artifacts,self.git,'public',self.key,response_json_mode=False,thinking='disabled',
                before_request=self.reserve,after_request=self.account)
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(observed,list(DEFAULT_WIRE_PAYLOAD_SHA256))

    def test_mimo_flash_uses_same_fixed_profile_and_provider_wire(self):
        payloads=[]
        scripted=self.scripted(self.ready()+[self.finish(4)])
        def post(provider,payload,key,timeout):
            self.assertEqual(provider,'mimo')
            payloads.append(copy.deepcopy(payload))
            return scripted(provider,payload,key,timeout)
        with patch.object(lab,'_post',side_effect=post):
            result=self.new_actor(provider='mimo',model='mimo-v2.6-flash')
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(result['adapter'],ADAPTER)
        for payload in payloads:
            self.assertEqual(payload['model'],'mimo-v2.6-flash')
            self.assertEqual(payload['thinking'],{'type':'disabled'})
            self.assertEqual(payload['max_completion_tokens'],8192)
            self.assertNotIn('max_tokens',payload)
        raw=json.loads((self.artifacts/'requests/01.response.json').read_bytes())
        self.assertEqual(raw['adapter'],ADAPTER)
        self.assertEqual(raw['broker_profile_id'],PROFILE)
        self.assertEqual(raw['execution_backend'],BACKEND)

    def test_existing_quality_pure_branch_accepts_identity_bound_native_chain(self):
        def pure(broker,before,final_text,native_trace,extra_failures):
            validation=[e for e in broker.events if e['tool']=='repo_validate'][-1]['result']
            return lab._api_quality(broker,before,final_text,native_trace,extra_failures,
                                    execution_backend=BACKEND,failed_execution=validation)
        self.module.quality_from_current_receipts.side_effect=pure
        result,count=self.run_steps(self.ready()+[self.finish(4)])
        self.assertEqual(count,4)
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(len(self.executions),1)

    def test_partial_write_is_terminal_and_preserves_known_usage(self):
        original=self.module.create_broker.side_effect
        def create(*args,**kwargs):
            broker=original(*args,**kwargs)
            execute=broker._execute
            def partial(name,arguments):
                if name=='repo_patch':
                    return {'ok':False,'write_state':'partial-or-unverified','changed':[],
                            'files':{},'error':'synthetic uncertain write'}
                return execute(name,arguments)
            broker._execute=partial
            return broker
        self.module.create_broker.side_effect=create
        result,count=self.run_steps([self.read(1),self.patch_from_read(2,'fixed\n')])
        self.assertEqual(count,2)
        self.assertEqual(result['status'],'unknown-tool-write-blocked')
        self.assertTrue(result['execution_state_unknown'])
        self.assertFalse(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'],30)
        self.assertTrue((self.artifacts/'actor.pending.json').is_file())

    def test_final_receipt_recheck_unknown_promotes_status_and_preserves_fence(self):
        original=self.module.quality_from_current_receipts.side_effect
        def invalid(*args):
            result=original(*args)
            result.update(execution_state_unknown=True,hard_pass=False,task_success=0)
            result['failures'].append('scope-invalid:project-execution-receipt-missing')
            return result
        self.module.quality_from_current_receipts.side_effect=invalid
        result,count=self.run_steps(self.ready()+[self.finish(4)])
        self.assertEqual(count,4)
        self.assertEqual(result['status'],'execution-state-unknown-blocked')
        self.assertTrue(result['execution_state_unknown'])
        self.assertFalse(result['unknown_usage'])
        self.assertEqual(result['usage']['total_tokens'],60)
        self.assertTrue((self.artifacts/'actor.pending.json').is_file())
        self.assertEqual(len(self.executions),1)

    def test_final_receipt_recheck_infra_failure_is_terminal_without_reexecution(self):
        original=self.module.quality_from_current_receipts.side_effect
        def invalid(*args):
            result=original(*args)
            result.update(execution_infrastructure_failed=True,hard_pass=False,task_success=0)
            result['failures'].append('scope-invalid:project-execution-receipt-invalid')
            return result
        self.module.quality_from_current_receipts.side_effect=invalid
        result,count=self.run_steps(self.ready()+[self.finish(4)])
        self.assertEqual(count,4)
        self.assertEqual(result['status'],'execution-infrastructure-blocked')
        self.assertTrue(result['execution_infrastructure_failed'])
        self.assertFalse(result['execution_state_unknown'])
        self.assertTrue((self.artifacts/'actor.pending.json').is_file())
        self.assertEqual(len(self.executions),1)

    def test_known_failed_test_can_be_repaired_within_original_budget(self):
        self.validation_failed=True
        def repair(payload):
            self.assertEqual(self.feedback(payload)['execution']['status'],'EXECUTED')
            self.validation_failed=False
            return self.validate_and_status(4)
        result,count=self.run_steps([self.read(1),self.patch_from_read(2,'fixed\n'),
            completion(3,[call('known-failure','repo_validate',{})]),repair,self.finish(5)])
        self.assertEqual(count,5)
        self.assertEqual(len(self.executions),2)
        self.assertTrue(result['quality']['hard_pass'])
        self.assertFalse(result['execution_state_unknown'])

    def test_fixed_model_profile_and_feedback_policy_reject_before_key(self):
        for change in ({'model':'deepseek-flash'},{'profile_id':lab.FLASH_DISABLED_PROFILE},
                       {'execution_backend':'docker-cpython-finite-v1'},
                       {'tool_feedback_policy':lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.new_actor(**change)
        self.assertEqual(self.loaded,[])
        self.assertEqual(self.before,[])

    def test_callbacks_and_durable_receipt_are_required_before_http(self):
        with patch.object(lab,'_post',side_effect=AssertionError('HTTP forbidden')):
            with self.assertRaises(ValueError):
                lab.run_actor('deepseek','deepseek-v4-pro',self.task,self.workspace,self.artifacts,
                    self.git,'public',self.key,response_json_mode=False,thinking='disabled',
                    profile_id=lab.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE,
                    broker_profile_id=PROFILE,execution_backend=BACKEND)
        self.assertEqual(self.loaded,[])

    def test_missing_reservation_identity_is_refused_without_key_or_http(self):
        self.reserve=lambda metadata: {'reservation_id':metadata['request_id']}
        with patch.dict(sys.modules,{'evolution.engineering_broker':self.module}),patch.object(lab,'_post',side_effect=AssertionError('HTTP forbidden')):
            result=self.run_actor(model='deepseek-v4-pro',profile_id=lab.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE,
                broker_profile_id=PROFILE,execution_backend=BACKEND)
        self.assertEqual(result['status'],'outer-budget-refused')
        self.assertEqual(self.loaded,[])

    def test_legacy_defaults_do_not_load_engineering_module(self):
        with patch.object(lab,'_post',side_effect=self.positive):
            result=self.run_actor()
        self.assertEqual(result['adapter'],lab.ADAPTER)
        self.assertNotIn('broker_profile_id',result)
        self.module.create_broker.assert_not_called()
