"""Synthetic admission specimens, never evidence of an actual ROOT audit."""
import copy
import tempfile
from pathlib import Path
import unittest

from evolution import actor_checkpoint as a
from evolution.provider_tools import profile_configuration
from evolution.tool_broker import canonical, sha


class ActorCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.run=self.base/'run';self.project=self.run/'workspaces/w001'
        self.art=self.run/'actors/w001-source/artifacts';self.project.mkdir(parents=True)
        (self.project/'.git/refs/heads').mkdir(parents=True)
        (self.project/'.git/HEAD').write_text('ref: refs/heads/main\n',encoding='ascii')
        (self.project/'.git/refs/heads/main').write_text('a'*40+'\n',encoding='ascii')
        self.task={'id':'synthetic-resume','family':'public-control','prompt':'Update the registered value.',
            'initial_files':{'main.py':'value=0\n'},'writable_files':['main.py'],
            'required_tools':['repo_read','repo_patch','repo_validate','repo_status'],
            'engineering_contract':{'schema_version':1,'contract_id':'synthetic-control',
                'trusted_files':{'audit_test.py':'import unittest\nclass Example(unittest.TestCase):\n    def test_example(self): self.assertTrue(True)\n'},
                'checks':[{'id':'unit','recipe':'unittest','test_modules':['audit_test'],'minimum_tests':1,
                    'expected_test_ids':['audit_test.Example.test_example']}]}}
        self.cfg=profile_configuration(a.PROFILE);self.system='synthetic public instruction'
        current={'main.py':'value=1\n'};(self.project/'main.py').write_bytes(current['main.py'].encode())
        state=sha(canonical(a._state(current)));initial=sha(canonical(a._state(self.task['initial_files'])))
        events=[];traces=[];previous=None
        for n,(tool,args,result)in enumerate([
            ('repo_read',{'paths':['main.py']},{'ok':True,'files':{'main.py':{'text':'value=0\n','sha256':sha(b'value=0\n')}}}),
            ('repo_patch',{'operations':[{'path':'main.py','old_sha256':sha(b'value=0\n'),'new_text':'value=1\n'}]},
                {'ok':True,'changed':['main.py'],'files':{'main.py':{'sha256':sha(b'value=1\n'),'byte_size':8}}}),
            ('repo_status',{}, {'ok':True})],1):
            event={'sequence':n,'tool':tool,'arguments':args,'result':result,'arguments_sha256':sha(canonical(args)),
                'result_sha256':sha(canonical(result)),'state_sha256':initial if n==1 else state};events.append(event)
            trace={k:event[k]for k in ('tool','arguments_sha256','result_sha256','state_sha256')}
            trace.update(broker_sequence=n,broker_event_sha256=sha(canonical(event)),previous_chain_sha256=previous,request_index=1)
            trace['chain_sha256']=sha(canonical(trace));previous=trace['chain_sha256'];traces.append(trace)
        self.art.mkdir(parents=True);(self.art/'broker.jsonl').write_bytes(b''.join(canonical(e)+b'\n'for e in events))
        outcomes=[];receipt_refs=[]
        for index in (1,2):
            out={'request_index':index,'provider':'mimo','model_requested':self.cfg['providers']['mimo']['model'],
                'input_task_sha256':sha(canonical(self.task)),'profile_configuration_sha256':sha(canonical(self.cfg)),
                'unknown':False,'retry_of_request_id':None,'dispatched':index==1,'not_invoked':index==2,
                'usage':{'total_tokens':10}if index==1 else None,'response_sha256':'b'*64 if index==1 else None,
                'transport':{'phase':'complete','http_dispatch':'response_received'}if index==1 else
                    {'phase':'connect','http_dispatch':'not_started','exception_class':'TimeoutError'},
                'settlement':{'worker_done':True,'worker_alive_at_return':False,'attempt_dispatch_gate_closed':True,'body_bytes_observed':0}}
            outcomes.append(out);receipt_refs.append(self.write(self.art/'requests'/('%02d.receipt.json'%index),out))
        result={'input_task_sha256':sha(canonical(self.task)),'system_context_sha256':sha(self.system.encode()),
            'profile_configuration_sha256':sha(canonical(self.cfg)),'profile_id':a.PROFILE,'status':'transport-failed-not-invoked',
            'final_report':None,'quality':{'hard_pass':False},'unknown_usage':False,'execution_state_unknown':False,
            'execution_infrastructure_failed':False,'work_deadline_reached':False,'conversation_index':0,'context_checkpoint_receipts':[],
            'schema_rejections':0,'reasoning_continuations':0,'requests':2,'tool_attempts':3,'max_requests':24,'max_tools':32,
            'tool_events':events,'api_tool_trace':traces,'final_state_sha256':state,'received_state_sha256':initial,'wall_seconds':2.,'receipt':{}}
        result_ref=self.write(self.art/'actor.result.json',result);task_ref=self.write(self.run/'actors/w001-source/task.json',self.task)
        git={'ref':'git-baselines/w001/source.json','baseline_commit':'a'*40}
        git['sha256']=self.write(self.run/git['ref'],{'baseline_commit':'a'*40})['sha256']
        record={'actor_id':'w001-source','provider':'mimo','model':self.cfg['providers']['mimo']['model'],
            'task_ref':'actors/w001-source/task.json','task_sha256':task_ref['sha256'],'result_ref':'actors/w001-source/artifacts/actor.result.json',
            'result_sha256':result_ref['sha256'],'artifact_ref':'actors/w001-source/artifacts','workspace_ref':'workspaces/w001',
            'system_context':self.system,'actor_timing':{'started_monotonic':10.},'git_entry':git,'result':copy.deepcopy(result)}
        record['result']['receipt']['result_file_sha256']=result_ref['sha256'];self.record_ref=self.write(self.run/'actor-records/w001-source.json',record)
        inline=self.write(self.run/'actors/w001-source/raw-verification.json',{'verified_final_state_sha256':state,'independent_task_pass':False})
        self.write(self.run/'actors/w001-source/record-publication.json',{'actor_id':'w001-source',
            'actor_record_sha256':self.record_ref['sha256'],'raw_verification_receipt':inline})
        protocol=self.write(self.base/'protocol.json',{'run_root':str(self.run),'configuration_sha256':sha(canonical(self.cfg)),
            'actor_registry':{'w001-source':{'surface':'API','provider':'mimo','model':record['model']}}})
        snapshot=self.write(self.base/'snapshot.json',{'actor_id':'w001-source','files':current,'state_sha256':state})
        closure=self.write(self.base/'owner-exit.json',{'process_exited':True,'worker_alive':False,'observed_exit_monotonic':12.5})
        inputmap=self.write(self.base/'inputs.json',{'raw':{p.relative_to(self.run).as_posix():sha(p.read_bytes())for p in self.art.rglob('*')if p.is_file()}})
        reader=self.base/'independent.py';reader.write_bytes(b'# synthetic audit identity only\n')
        reader_ref={'path':str(reader),'sha256':sha(reader.read_bytes())}
        proof=self.write(self.base/'proof.json',{'schema':'engineering-actor-resume-prefix-proof-v1','status':'VERIFIED_UNFINISHED',
            'actor_id':'w001-source','original_protocol':protocol,'original_record':self.record_ref,'snapshot':snapshot,
            'reader_sha256':reader_ref['sha256'],'raw_integrity':True,'accounting_complete':True,'owned_workers_closed':True,
            'inputs_before_after_exact':True,'eligible_before_dispatch_timeout':True,'independent_task_pass':False,
            'events_sha256':sha(canonical(events)),'traces_sha256':sha(canonical(traces)),'broker_journal_sha256':sha((self.art/'broker.jsonl').read_bytes()),
            'request_receipts':receipt_refs,'original_owner_exit':closure,'active_seconds_debit':2.5,'input_map':inputmap,'git_entry':git})
        observed=self.write(self.base/'observed.json',{'schema':'root-observed-actor-resume-prefix-exit-v1','caller':'ROOT',
            'exit_code':0,'reader_sha256':reader_ref['sha256'],'proof_sha256':proof['sha256'],'source_before_after_exact':True,
            'model_calls':0,'project_executions':0})
        self.value={'schema':a.SCHEMA,'policy_id':a.POLICY_ID,'actor_id':'w001-source','original_protocol':protocol,
            'original_record':self.record_ref,'verified_prefix':proof,'prefix_observed_exit':observed,
            'prefix_reader':reader_ref,'snapshot':snapshot,'active_seconds_debit':2.5}

    @staticmethod
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);data=canonical(value)+b'\n';path.write_bytes(data)
        return {'path':str(path),'sha256':sha(data)}

    def validate(self,value=None,**kwargs):
        return a.validate_resume(self.value if value is None else value,task=self.task,provider='mimo',
            model=self.cfg['providers']['mimo']['model'],system_context=self.system,configuration=self.cfg,root=self.project,**kwargs)

    def test_owned_seed_cumulative_budget_and_scope(self):
        seed=self.validate();self.assertEqual((seed['requests_used'],seed['tools_used'],seed['conversation_index']),(2,3,1))
        self.assertEqual(seed['elapsed_seconds_used'],2.5);self.assertEqual(a.validate_seed(seed,task=self.task,root=self.project)['events'],seed['events'])
        with self.assertRaises(ValueError):a.validate_seed(dict(seed),task=self.task,root=self.project)
        seed['requests_used']=0
        with self.assertRaises(ValueError):a.validate_seed(seed,task=self.task,root=self.project)

    def test_no_budget_reset_bool_or_repeated_recovery(self):
        for debit in (0,True,600,float('inf')):
            value=copy.deepcopy(self.value);value['active_seconds_debit']=debit
            with self.subTest(debit=debit),self.assertRaises(ValueError):self.validate(value)
        value=copy.deepcopy(self.value);value['policy_id']='another-recovery'
        with self.assertRaises(ValueError):self.validate(value)

    def test_current_files_and_git_lineage_are_not_rebaselined(self):
        (self.project/'main.py').write_bytes(b'value=2\n')
        with self.assertRaises(ValueError):self.validate()
        self.validate(require_current_disk=False)
        (self.project/'.git/refs/heads/main').write_text('b'*40+'\n',encoding='ascii')
        with self.assertRaises(ValueError):self.validate(require_current_disk=False)

    def test_original_request_or_journal_mutation_rejected(self):
        path=self.art/'requests/01.receipt.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.validate()
        with self.assertRaises(ValueError):self.validate(dict(self.value,snapshot=dict(self.value['snapshot'],sha256='0'*64)))

    def test_real_validator_seed_reaches_real_live_broker(self):
        from evolution.engineering_broker import create_broker
        seed=self.validate();before=(self.art/'broker.jsonl').read_bytes();directory=self.base/'new-artifacts';directory.mkdir()
        broker=create_broker(self.project,self.task,self.base/'mock-git',audit_file=directory/'broker.jsonl',
            execution_artifacts=directory/'execution',resume_checkpoint=seed)
        self.assertEqual(len(broker.events),3);self.assertFalse(broker._receipt_only)
        self.assertTrue(broker.call('repo_read',{'paths':['main.py']})['ok'])
        self.assertEqual(broker.events[-1]['sequence'],4)
        self.assertEqual((self.art/'broker.jsonl').read_bytes(),before)


if __name__=='__main__':unittest.main()
