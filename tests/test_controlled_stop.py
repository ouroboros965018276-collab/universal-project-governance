"""Public synthetic controlled-stop seam tests; no model or process dispatch."""
import sys,unittest
if sys.version_info < (3,10):
    raise unittest.SkipTest('Controlled-stop API tests require Python 3.10+ before any engine import')
import copy,json,pathlib
from unittest.mock import Mock,patch
import evolution.provider_tools as api
from test_provider_tools import call,completion
import test_engineering_provider as engineering_tests
from evolution.tool_broker import canonical,sha


class ControlledStopTests(engineering_tests.EngineeringCandidateTests):
    def setUp(self):
        super().setUp()
        self.guard_calls=[]
        self.proposal_change=None
        self.accept_guard=True
        original=self.reserve
        self.reserve_spy=Mock(side_effect=original)
        self.reserve=self.reserve_spy

    def stop_guard(self,metadata):
        self.guard_calls.append(copy.deepcopy(metadata))
        if metadata['request_index']<3:return None
        event=self.brokers[-1][0].events[-1]
        event_raw=(self.artifacts/'broker.jsonl').read_bytes()
        trace_path=self.artifacts/'tool-receipts'/('%02d.json'%event['sequence'])
        trace_raw=trace_path.read_bytes();trace=json.loads(trace_raw)
        request_raw=(self.artifacts/'requests'/('%02d.receipt.json'%trace['request_index'])).read_bytes()
        value={'schema_version':'confirmed-first-patch-tail-local-stop-v1',
            'kind':'controlled-local-stop-authorization','reservation_performed':False,
            **{k:metadata[k] for k in ('adapter','provider','model_requested','profile_id','profile_configuration_sha256',
                'broker_profile_id','execution_backend','input_task_sha256','request_id','request_index','request_payload_sha256')},
            'received_state_sha256':sha(canonical({p:sha(t.encode()) for p,t in self.task['initial_files'].items()})),
            'state_sha256':event['state_sha256'],'last_broker_sequence':event['sequence'],
            'last_broker_event_sha256':sha(canonical(event)),'broker_audit_sha256':sha(event_raw),
            'last_trace_file_sha256':sha(trace_raw),'last_trace_chain_sha256':trace['chain_sha256'],
            'last_request_receipt_sha256':sha(request_raw),
            'last_response_artifact_sha256':trace['response_artifact_sha256'],
            'last_request_index':trace['request_index'],'last_api_response_id':trace['api_response_id'],
            'last_tool_call_id':trace['tool_call_id'],'successful_patch_ordinal':1,
            'source_completion_required':False,'source_graded':False}
        if self.proposal_change:self.proposal_change(value)
        path=self.artifacts/'control/local-stop-authorization.json'
        api._write_new(path,value)
        return api.ControlledLocalStopRequested('control/local-stop-authorization.json',sha(path.read_bytes()))

    def stopped(self,steps=None,**kwargs):
        kwargs.setdefault('controlled_local_stop_guard',self.stop_guard)
        return self.run_steps(steps or [self.read(1),self.patch_from_read(2,'fixed\n')],**kwargs)

    def test_stop_accepts_only_durable_patch_tail_without_reserve_dispatch_or_grade(self):
        self.module.quality_from_current_receipts.side_effect=AssertionError('accepted unfinished source cannot be graded')
        result,count=self.stopped()
        self.assertEqual(count,2)
        self.assertEqual(self.reserve_spy.call_count,2)
        self.assertEqual(len(self.after),2)
        self.assertEqual(result['status'],'controlled-local-stop-unfinished')
        self.assertEqual(result['usage']['total_tokens'],30)
        self.assertFalse(result['unknown_usage'])
        self.assertFalse(result['execution_state_unknown'])
        self.assertIsNone(result['quality']['task_success'])
        self.assertEqual(result['quality']['assessment'],'NOT_GRADED_CONTROLLED_STOP')
        self.assertFalse(result['quality']['hard_pass'])
        self.assertTrue((self.artifacts/'actor.pending.json').exists())
        self.assertFalse((self.artifacts/'requests/03.pending.json').exists())
        accepted=self.artifacts/'control/local-stop.accepted.json'
        self.assertEqual(result['controlled_local_stop']['accepted_receipt_sha256'],sha(accepted.read_bytes()))
        self.assertEqual(result['controlled_local_stop']['state_sha256'],result['final_state_sha256'])
        self.module.quality_from_current_receipts.assert_not_called()

    def test_stop_guard_none_preserves_normal_completed_flow(self):
        result,count=self.run_steps(self.ready()+[self.finish(4)],controlled_local_stop_guard=lambda metadata:None)
        self.assertEqual(count,4);self.assertEqual(result['status'],'completed')
        self.assertTrue(result['quality']['hard_pass']);self.assertIsNone(result['controlled_local_stop'])

    def test_stop_bad_snapshot_proposal_gets_no_bypass_or_new_reservation(self):
        self.proposal_change=lambda value:value.update(state_sha256='0'*64)
        result,count=self.stopped()
        self.assertEqual(count,2);self.assertEqual(self.reserve_spy.call_count,2)
        self.assertIsNone(result['controlled_local_stop'])
        self.assertNotEqual(result['status'],'controlled-local-stop-unfinished')
        self.module.quality_from_current_receipts.assert_called_once()

    def test_stop_non_tail_patch_cannot_be_reinterpreted_as_patch_boundary(self):
        def batch(payload):
            response=self.patch_from_read(2,'fixed\n')(payload)
            response['choices'][0]['message']['tool_calls'].append(call('later-status','repo_status',{}))
            return response
        result,count=self.stopped([self.read(1),batch])
        self.assertEqual(count,2);self.assertIsNone(result['controlled_local_stop'])
        self.assertNotEqual(result['status'],'controlled-local-stop-unfinished')

    def test_stop_no_guard_cannot_activate_controlled_unfinished(self):
        def refuse(metadata):
            if metadata['request_index']==3:raise RuntimeError('ordinary local budget refusal')
            self.before.append(metadata)
            return {'reservation_receipt_sha256':'c'*64}
        self.reserve=refuse
        result,count=self.stopped(controlled_local_stop_guard=None)
        self.assertEqual(count,2);self.assertNotEqual(result['status'],'controlled-local-stop-unfinished')
        self.assertNotIn('controlled_local_stop',result)
        self.module.quality_from_current_receipts.assert_called_once()

    def test_stop_unknown_prior_call_never_reaches_later_guard(self):
        unknown=completion(2,[call('untrusted-patch','repo_patch',{'operations':[]})],usage=False)
        result,count=self.stopped([self.read(1),unknown])
        self.assertEqual(count,2);self.assertEqual(len(self.guard_calls),2)
        self.assertTrue(result['unknown_usage']);self.assertEqual(result['status'],'unknown-call-blocked')
        self.assertIsNone(result['controlled_local_stop'])

    def test_stop_boolean_or_guard_error_is_local_refusal_not_authorization(self):
        for label,guard in (('bool',lambda metadata:True),('error',Mock(side_effect=RuntimeError('synthetic')))):
            self.artifacts=self.base/label
            self.loaded=[];self.before=[];self.after=[]
            result,count=self.stopped(controlled_local_stop_guard=guard)
            self.assertEqual(count,0);self.assertEqual(self.loaded,[])
            self.assertIsNone(result['controlled_local_stop'])
            self.assertNotEqual(result['status'],'controlled-local-stop-unfinished')

    def test_stop_guard_is_rejected_for_legacy_and_finite_profiles_before_key(self):
        for kwargs in ({},{'execution_backend':'docker-cpython-finite-v1','profile_id':api.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE,'model':'deepseek-v4-pro'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.run_actor(controlled_local_stop_guard=lambda metadata:None,**kwargs)
        self.assertEqual(self.loaded,[])

    def test_stop_deleted_native_raw_receipt_gets_no_bypass(self):
        def guard(metadata):
            proposal=self.stop_guard(metadata)
            if proposal is not None:
                (self.artifacts/'tool-receipts/02.json').unlink()
            return proposal
        result,count=self.stopped(controlled_local_stop_guard=guard)
        self.assertEqual(count,2);self.assertIsNone(result['controlled_local_stop'])
        self.assertNotEqual(result['status'],'controlled-local-stop-unfinished')

    def test_stop_second_successful_patch_is_not_registered_cutpoint(self):
        def guard(metadata):
            return self.stop_guard(metadata) if metadata['request_index']==4 else None
        second=completion(3,[call('second-patch','repo_patch',{'operations':[
            {'path':'target.txt','old_sha256':sha(b'fixed\n'),'new_text':'newer\n'}]})])
        result,count=self.stopped([self.read(1),self.patch_from_read(2,'fixed\n'),second],controlled_local_stop_guard=guard)
        self.assertEqual(count,3);self.assertIsNone(result['controlled_local_stop'])
        self.assertNotEqual(result['status'],'controlled-local-stop-unfinished')

    def test_stop_request_identity_mismatch_gets_no_bypass(self):
        self.proposal_change=lambda value:value.update(request_id='different-request')
        result,count=self.stopped()
        self.assertEqual(count,2);self.assertIsNone(result['controlled_local_stop'])

    def test_stop_unknown_execution_never_reaches_later_guard(self):
        self.validation_unknown=True
        guard=Mock(return_value=None)
        result,count=self.stopped(self.ready(),controlled_local_stop_guard=guard)
        self.assertEqual(count,3);self.assertEqual(guard.call_count,3)
        self.assertTrue(result['execution_state_unknown']);self.assertIsNone(result['controlled_local_stop'])

    def test_stop_completed_source_cannot_receive_a_late_stop_proposal(self):
        guard=Mock(side_effect=lambda metadata:None if metadata['request_index']<=4 else self.stop_guard(metadata))
        result,count=self.stopped(self.ready()+[self.finish(4)],controlled_local_stop_guard=guard)
        self.assertEqual(count,4);self.assertEqual(guard.call_count,4)
        self.assertEqual(result['status'],'completed');self.assertIsNone(result['controlled_local_stop'])

    def test_stop_snapshot_drift_after_acceptance_is_unknown_and_ungraded(self):
        original=api._write_new
        def drifting(path,value,secret=''):
            identity=original(path,value,secret)
            if pathlib.Path(path).name=='local-stop.accepted.json':
                (self.workspace/'target.txt').write_bytes(b'drift\n')
            return identity
        with patch.object(api,'_write_new',side_effect=drifting):
            result,count=self.stopped()
        self.assertEqual(count,2);self.assertEqual(result['status'],'execution-state-unknown-blocked')
        self.assertTrue(result['execution_state_unknown'])
        self.assertIsNone(result['quality']['task_success'])
        self.assertEqual(result['quality']['assessment'],'CONTROLLED_STOP_INVALIDATED')
        self.assertTrue((self.artifacts/'actor.pending.json').exists())


def load_tests(loader, tests, pattern):
    # Reuse the existing fixture without rediscovering its inherited 22 cases.
    return unittest.TestSuite(ControlledStopTests(name) for name in sorted(
        name for name in dir(ControlledStopTests) if name.startswith('test_stop_')))
