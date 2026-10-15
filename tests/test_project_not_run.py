"""Pure missing-current-validation classification regression."""
import sys,unittest
if sys.version_info < (3,10):
    raise unittest.SkipTest('Project API tests require Python 3.10+ before engine import')
import json
from unittest.mock import patch
import test_engineering_broker as broker_tests
import test_engineering_provider as provider_tests
from evolution import engineering_broker as lab
from evolution.tool_broker import canonical,sha
from test_provider_tools import call,completion


class NotRunBrokerTests(broker_tests.EngineeringBrokerTests):
    def test_not_run_absent_validation_is_known_failure_without_execution(self):
        self.read_and_edit()
        self.broker.call('repo_status',{})
        result=self.quality()
        self.assertFalse(result['hard_pass']);self.assertEqual(result['task_success'],0)
        self.assertIsNone(result['validation'])
        self.assertEqual(result['final_execution_not_run_reason'],'required-current-project-validation-missing')
        self.assertFalse(result['execution_state_unknown']);self.assertEqual(self.executor_calls,0)

    def stale(self):
        self.read_and_edit();self.broker.call('repo_validate',{})
        self.broker.call('repo_read',{'paths':['README.md']})
        self.broker.call('repo_patch',{'operations':[{'path':'README.md',
            'old_sha256':self.before['README.md'],'new_text':'Changed after validated snapshot.\n'}]})
        self.broker.call('repo_status',{})

    def test_not_run_stale_receipt_verified_at_original_snapshot_only(self):
        self.stale()
        seen=[];original=self.read_receipt
        def observe(files,contract,directory,receipt_sha256=None):
            seen.append(dict(files));return original(files,contract,directory,receipt_sha256)
        with patch.object(lab.project_executor,'read_project_receipt',side_effect=observe):result=self.quality()
        self.assertIsNone(result['validation']);self.assertFalse(result['execution_state_unknown'])
        self.assertEqual(result['final_execution_not_run_reason'],'required-current-project-validation-missing')
        self.assertEqual(len(seen),1);self.assertEqual(seen[0]['README.md'],self.task['initial_files']['README.md'])
        self.assertEqual(self.executor_calls,1)

    def test_not_run_stale_missing_raw_or_event_drift_stays_unknown(self):
        self.stale()
        path=self.base/'execution/validation-001/result.json';raw=path.read_bytes();path.unlink()
        result=self.quality();self.assertTrue(result['execution_state_unknown'])
        self.assertNotIn('final_execution_not_run_reason',result)
        path.write_bytes(raw)
        next(event for event in self.broker.events if event['tool']=='repo_patch')['state_sha256']='0'*64
        result=self.quality();self.assertTrue(result['execution_state_unknown']);self.assertEqual(self.executor_calls,1)


class NotRunProviderTests(provider_tests.EngineeringCandidateTests):
    def test_not_run_typed_quality_remains_known_task_failure(self):
        self.module.quality_from_current_receipts.side_effect=None
        self.module.quality_from_current_receipts.return_value={'validation':None,'failures':[],
            'hard_pass':False,'task_success':0,'execution_state_unknown':False,
            'final_execution_not_run_reason':'required-current-project-validation-missing'}
        self.reserve=lambda metadata: (_ for _ in ()).throw(RuntimeError('ordinary refusal'))
        result,count=self.run_steps([self.read(1)])
        self.assertEqual(count,0);self.assertFalse(result['execution_state_unknown'])
        self.assertFalse(result['execution_infrastructure_failed']);self.assertFalse(result['quality']['hard_pass'])
        self.assertEqual(result['quality']['task_success'],0)
        self.module.validate_execution_result.assert_not_called()

    def test_not_run_schema_refusal_has_known_cost_and_no_implicit_execution(self):
        self.module.quality_from_current_receipts.side_effect=None
        self.module.quality_from_current_receipts.return_value={'validation':None,'failures':['required-current-project-validation-missing'],
            'hard_pass':False,'task_success':0,'execution_state_unknown':False,
            'final_execution_not_run_reason':'required-current-project-validation-missing'}
        original=self.reserve
        def bounded(metadata):
            if metadata['request_index']>1:raise RuntimeError('fixed local budget refusal')
            return original(metadata)
        self.reserve=bounded
        invalid=completion(1,[call('bad-schema','repo_read',{'paths':['target.txt'],'undefined_extra':True})])
        result,count=self.run_steps([invalid])
        self.assertEqual(count,1);self.assertEqual(result['schema_rejections'],1)
        self.assertFalse(result['execution_state_unknown']);self.assertFalse(result['unknown_usage'])
        self.assertIsNotNone(result['usage']);self.assertEqual(result['quality']['task_success'],0)
        self.assertEqual(len(self.executions),0);self.module.validate_execution_result.assert_not_called()


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(cls(name) for cls in (NotRunBrokerTests,NotRunProviderTests)
        for name in sorted(n for n in dir(cls) if n.startswith('test_not_run_')))
