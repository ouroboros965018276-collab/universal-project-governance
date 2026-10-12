"""No-model tests: synthetic Git snapshots, workers and positive receipts only."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
HERE=REPO/"evolution/experiments/native_paired"
TESTROOT=REPO/"eval-workspaces"
TESTROOT.mkdir(exist_ok=True)
P=runpy.run_path(str(HERE/'parent.py'))
PREP=runpy.run_path(str(HERE/'prepare.py'))
W=runpy.run_path(str(HERE/'worker.py'))
T=runpy.run_path(str(HERE/'transport.py'))
sha,digest=P['sha'],P['digest']
GRADER=b'''def grade(request):
    return {"loss":1.0,"hard":1,"soft":1.0,"artifact_checks":[],"scope_ok":True,"validation_truth_ok":True}
'''


class NativePairedTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='rc19-native-paired-test-',dir=TESTROOT)
        self.root=Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(TESTROOT.resolve()))
        self.root.joinpath('binary.exe').write_bytes(b'synthetic-no-model-binary')
        self.root.joinpath('git.exe').write_bytes(b'synthetic-no-git-binary')
        self.root.joinpath('catalog.json').write_text(json.dumps({'cli_entry':str(self.root/'binary.exe'),'observed_at_utc':'synthetic-no-model',
             'catalog':{'data':[{'id':model,'supportedReasoningEfforts':[{'reasoningEffort':'low'}]} for model in ('gpt-6-luna','gpt-6.1-sol')]}}),encoding='utf-8')
        self.blobs={}
        for rev in ('a'*40,'b'*40):
            self.blobs[rev]={
              'evolution/__init__.py':b'', 'evolution/contracts.py':b'# synthetic contracts\n',
              'evolution/native_codex.py':b'def runner(request):\n    raise AssertionError("business callback forbidden in verification-only test")\n',
              'evolution/task_benchmark.py':GRADER,
              'compiler/compile_governance.py':b'# exact synthetic compiler\n','LICENSE':b'synthetic license\n',
              'governance-src/model/governance-model.json':b'{"synthetic":true}\n',
              'universal-project-governance/scripts/plan_governance.py':b'# synthetic reference planner\n',
              'universal-project-governance/SKILL.md':b'synthetic frozen skill\n'}
        def git(command):
            args=command[3:]
            if args[0]=='rev-parse':return (args[1].split('^')[0]+'\n').encode()
            if args[0]=='show':
                rev,name=args[1].split(':',1);return self.blobs[rev][name]
            if args[0]=='ls-tree':
                rev,prefix=args[3],args[5]
                return ('\n'.join(sorted(n for n in self.blobs[rev] if n.startswith(prefix+'/')))+'\n').encode()
            raise AssertionError(command)
        self.git=git
        self.counter=0

    def tearDown(self):
        self.assertTrue(Path(self.temporary.name).resolve().is_relative_to(TESTROOT.resolve()))
        self.temporary.cleanup()

    def bundle(self):
        self.counter+=1
        output=self.root/('eval-workspaces/rc19-native-paired-bundle-'+str(self.counter))
        def plan(*args,**kwargs):return subprocess.CompletedProcess(args,0,b'{"synthetic_plan":true}',b'')
        with patch.object(PREP['subprocess'],'check_output',side_effect=self.git),patch.object(PREP['subprocess'],'run',side_effect=plan):
            info=PREP['prepare'](self.root,output,self.root/('artifacts-'+str(self.counter)),self.root/'binary.exe',self.root/'git.exe','a'*40,'b'*40,self.root/'catalog.json')
        spec=json.loads(Path(info['protocol']).read_text(encoding='utf-8'))
        self.assertEqual(info['models_dispatched'],0)
        return spec,self.root/('run-'+str(self.counter)+'.json')

    def factory(self,output,behavior=None,close_error=False):
        test=self; instances={}; calls=[]
        class Fake:
            def __init__(self,entry,protocol,log):
                self.entry=entry;self.startup_seconds=.05;self.seen=0;instances[entry['model']+':'+entry['condition']]=self
            def call(self,command):
                # Enforce that the durable parent pending fence exists BEFORE dispatch.
                pending=json.loads(output.read_text(encoding='utf-8'))['pending']
                test.assertEqual(pending['request_sha256'],digest(command['request']))
                calls.append(command);self.seen+=1
                if behavior:
                    special=behavior(self,command,len(calls))
                    if special is not None:return special
                return test.message(self,command)
            def close(self):
                if close_error:raise OSError('synthetic cleanup failure')
                return {'state':'synthetic exited'}
        return Fake,instances,calls

    def message(self,worker,command):
        request=command['request'];task=request['task'];condition=worker.entry['condition']
        return {'type':'call_result','sample_id':command['sample_id'],'callback_wall_seconds':2.0 if condition=='control' else 1.0,
                'first_public_callback':worker.seen==1,'context_phase':task['context_phase'],
                'result':{'status':'completed','usage':{'input_tokens':100,'output_tokens':5,'total_tokens':105},
                  'provider_receipt':{'wall_seconds':.5,'replayed_from_local_receipt':False},
                  'outcome':{'hard':1,'soft':1.0,'scope_ok':True,'validation_truth_ok':True},
                  'local_timings':{'cache_hit':task['context_phase']=='repeat'}}}

    def verifier(self,spec,item,raw,request):
        identity=digest({'model':item['model'],'condition':item['condition'],'task':item['task_id']})
        return {'receipt_sha256':identity,'cli_thread_id':'synthetic-'+identity,'strict_artifact_quality':True}

    def collect(self,spec,output,factory):
        return P['collect'](spec,output,allow_dispatch_protocol_sha256=digest(spec),worker_factory=factory,verifier=self.verifier,
                            transport_verifier=lambda *args:{'measurement':'synthetic no model transport'})

    def test_order_four_misses_four_reuses_balanced_and_fresh(self):
        tasks=W['matched_order'].__globals__ # Imports do not execute a callback.
        self.assertIsInstance(tasks,dict)
        spec,output=self.bundle();order=spec['order']
        self.assertEqual([x['context_phase'] for x in order],['cold']*16+['repeat']*16)
        for phase in ('cold','repeat'):
            for model in spec['models']:
                first=[x['condition'] for x in order[::2] if x['model']==model and x['context_phase']==phase]
                self.assertEqual(first.count('control'),2);self.assertEqual(first.count('treatment'),2)
        changed=copy.deepcopy(list(spec['tasks'].values()));changed[4]['payload']=changed[0]['payload']
        with self.assertRaises(ValueError):W['matched_order'](spec['models'],changed)

    def test_all_known_results_charge_full_order_and_terminal_no_replay(self):
        spec,output=self.bundle();factory,instances,calls=self.factory(output,close_error=True)
        run=self.collect(spec,output,factory)
        self.assertEqual(run['status'],'completed');self.assertEqual(len(calls),32)
        self.assertEqual([v.seen for v in instances.values()],[8]*4)
        self.assertEqual(run['budget']['total_tokens'],3360)
        self.assertEqual(run['summary']['A_time_quality_gate'],'PASS')
        self.assertEqual(run['summary']['metrics']['total_tokens']['ratio'],1.0)
        self.assertEqual(run['summary']['actual_charged_usage'],run['budget'])
        self.assertEqual(run['summary']['campaign_wall_seconds'],run['budget']['elapsed_seconds'])
        self.assertTrue(all(v['state']=='cleanup unconfirmed' for v in run['worker_close_states'].values()))
        self.assertEqual(self.collect(spec,output,lambda *a: self.fail('terminal replay started worker')),run)

    def test_unknown_error_retains_known_charge_pending_and_no_restart(self):
        spec,output=self.bundle()
        def behavior(worker,command,index):
            if index==2:return {'type':'call_error','sample_id':command['sample_id'],'callback_wall_seconds':1.0,
                                'usage':{'input_tokens':7,'output_tokens':2,'total_tokens':9},'error':'unknown after paid turn'}
        factory,instances,calls=self.factory(output,behavior)
        run=self.collect(spec,output,factory)
        self.assertEqual(run['status'],'unknown-call-blocked');self.assertEqual(len(calls),2)
        self.assertEqual(run['budget']['total_tokens'],114);self.assertIsNotNone(run['pending'])
        self.assertEqual(run['summary']['A_time_quality_gate'],'FAIL')
        with self.assertRaisesRegex(ValueError,'independent reconciliation'):
            self.collect(spec,output,lambda *a:self.fail('uncertain replay started worker'))

    def test_interruption_before_return_is_durably_fenced(self):
        for exception in (TimeoutError,KeyboardInterrupt):
            spec,output=self.bundle()
            def behavior(worker,command,index):raise exception('synthetic worker loss')
            factory,instances,calls=self.factory(output,behavior)
            run=self.collect(spec,output,factory)
            self.assertEqual(run['status'],'unknown-call-blocked');self.assertTrue(run['budget']['unknown_usage'])
            self.assertEqual(run['budget']['calls'],1);self.assertIsNotNone(run['pending'])
            with self.assertRaises(ValueError):self.collect(spec,output,factory)

    def test_warm_cache_mismatch_keeps_paid_result_and_stops(self):
        spec,output=self.bundle()
        def behavior(worker,command,index):
            if worker.entry['condition']=='treatment' and command['request']['task']['context_phase']=='repeat':
                message=self.message(worker,command);message['result']['local_timings']['cache_hit']=False;return message
        factory,instances,calls=self.factory(output,behavior);run=self.collect(spec,output,factory)
        self.assertEqual(run['status'],'protocol-violation');self.assertGreater(len(calls),16);self.assertLess(len(calls),20)
        self.assertEqual(run['budget']['total_tokens'],105*len(calls));self.assertIsNone(run['pending'])
        self.assertFalse(run['observations'][-1]['fresh'])

    def test_quality_failure_does_not_drop_cost_or_stop_collection(self):
        spec,output=self.bundle()
        def behavior(worker,command,index):
            if index==1:
                message=self.message(worker,command);message['result']['outcome']['hard']=0;return message
        factory,instances,calls=self.factory(output,behavior);run=self.collect(spec,output,factory)
        self.assertEqual(run['status'],'completed');self.assertEqual(len(calls),32)
        self.assertEqual(run['budget']['total_tokens'],3360);self.assertEqual(run['summary']['A_time_quality_gate'],'FAIL')

    def test_unverified_local_replay_cannot_hide_reserved_cost_or_count_fresh(self):
        spec,output=self.bundle()
        def behavior(worker,command,index):
            message=self.message(worker,command);message['result']['provider_receipt']['replayed_from_local_receipt']=True;return message
        factory,instances,calls=self.factory(output,behavior);run=self.collect(spec,output,factory)
        self.assertEqual(run['status'],'protocol-violation');self.assertEqual(run['budget']['calls'],1)
        self.assertEqual(run['budget']['total_tokens'],105);self.assertEqual(len(calls),1)
        self.assertTrue(run['budget']['unknown_usage']);self.assertIn('new provider charge unknown',run['budget']['accounting_limit'])

    def test_snapshot_tamper_and_relative_path_rejected_before_dispatch(self):
        spec,output=self.bundle();entry=next(iter(spec['workers'].values()))
        Path(entry['manifest_core']['snapshot_directory'],'evolution/native_codex.py').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'snapshot dependency hash changed'):
            self.collect(spec,output,lambda *a:self.fail('tamper dispatched'))
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError,'absolute'):
            PREP['prepare'](self.root,'relative',self.root/'artifacts',self.root/'binary.exe',self.root/'git.exe','a'*40,'b'*40,self.root/'catalog.json')

    def test_preparation_failure_is_zero_dispatch_terminal(self):
        spec,output=self.bundle()
        def failure(*args):raise OSError('synthetic no model startup failure')
        run=self.collect(spec,output,failure)
        self.assertEqual(run['status'],'preparation-failed');self.assertEqual(run['budget']['calls'],0)
        self.assertEqual(run['budget']['total_tokens'],0);self.assertFalse(run['budget']['unknown_usage'])

    def test_default_worker_verifies_without_business_callback_or_artifact_write(self):
        spec,output=self.bundle();entry=next(iter(spec['workers'].values()));manifest=Path(entry['manifest_path'])
        result=subprocess.run([sys.executable,'-B',str(HERE/'worker.py'),'--manifest',str(manifest),
                               '--manifest-sha256',sha(manifest.read_bytes())],capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr.decode());ready=json.loads(result.stdout)
        self.assertTrue(ready['verification_only']);self.assertFalse(Path(entry['config']['artifact_root']).exists())
        manifest.write_bytes(manifest.read_bytes()+b' ')
        changed=subprocess.run([sys.executable,'-B',str(HERE/'worker.py'),'--manifest',str(manifest),
                               '--manifest-sha256',ready['manifest_sha256']],capture_output=True,timeout=15)
        self.assertNotEqual(changed.returncode,0);self.assertIn(b'worker manifest changed',changed.stderr)

    def test_strict_json_envelope_types_duplicates_and_nonfinite(self):
        task={'artifact_checks':[{'path':'x.json','kind':'json','expected':'{"enabled":true,"number":1}'}]}
        def good(content):return json.dumps({'files':[{'path':'x.json','content':content}],'validation':'not_run'})
        self.assertTrue(P['strict_artifact_quality'](task,good('{"enabled":true,"number":1}')))
        for content in ('{"enabled":1,"number":1}','{"enabled":true,"number":1.0}',
                        '{"enabled":false,"enabled":true,"number":1}','{"enabled":true,"number":NaN}'):
            self.assertFalse(P['strict_artifact_quality'](task,good(content)))
        for text in (good('{"enabled":true,"number":1}').replace('"not_run"','"passed"'),
                     '{"files":[],"files":[],"validation":"not_run"}',
                     '{"files":[],"validation":"not_run","extra":true}'):
            self.assertFalse(P['strict_artifact_quality'](task,text))

    def receipt_fixture(self,spec,item,response_text=None,extra_events=None):
        entry=spec['workers'][item['model']+':'+item['condition']];condition=spec['conditions'][item['condition']]
        task=spec['tasks'][item['task_id']]
        request={'source_sha256':condition['source_sha256'],'candidate_id':condition['candidate_id'],
                 'task':task,'execution_artifact':condition['execution_artifact'],'config':entry['manifest_core']['runner_config']}
        response_text=response_text or json.dumps({'files':[{'path':c['path'],'content':c['expected']} for c in task['artifact_checks']],
                                                   'validation':'not_run'})
        actual={'input_tokens':100,'output_tokens':5,'total_tokens':105}
        events=[{'type':'thread.started','thread_id':'synthetic-real-format-thread'},
                {'type':'turn.started'},*list(extra_events or []),
                {'type':'item.completed','item':{'type':'agent_message','text':response_text}},
                {'type':'turn.completed','usage':actual}]
        stdout=('\n'.join(json.dumps(e) for e in events)+'\n').encode()
        payload={'governance_skill':condition['expected_skill'],
                 'governance_plan':condition['expected_plans'][digest(task['plan_context'])],
                 'task':task['prompt'],'task_payload':task['payload'],'output_contract':task['output_schema']}
        prompt=('synthetic bounded task\n\n'+json.dumps(payload)).encode()
        persisted={'status':'completed','text':response_text,'usage':actual,'wall_seconds':.5}
        receipt={'status':'completed','tool_calls':0,'model_requested':item['model'],'provider_request_id':None,'model_observed':None,
                 'config_sha256':request['config']['native_config_sha256'],'sandbox':'read-only','ephemeral':True,'wall_seconds':.5,
                 'usage':actual,'cli_thread_id':'synthetic-real-format-thread','replayed_from_local_receipt':False,
                 'bindings':{'capability':{k:request['config'][k] for k in ('native_config_sha256','grader')},
                    'grader':request['config']['grader'],'campaign_id':spec['protocol_id'],'sample_id':task['id'],
                    'source_sha256':condition['source_sha256'],'task_sha256':digest(task),
                    'candidate_id':condition['candidate_id'],'execution_artifact_sha256':digest(condition['execution_artifact']),
                    'runtime_sha256':condition['expected_runtime_sha256']},
                 'stdout_sha256':sha(stdout),'stderr_sha256':sha(b''),'prompt_sha256':sha(prompt),
                 'result_sha256':digest(persisted),'raw_artifact_reference':'calls/'+'d'*64}
        directory=Path(entry['config']['artifact_root'])/'calls'/('d'*64);directory.mkdir(parents=True)
        for name,body in (('stdout.raw',stdout),('stderr.raw',b''),('prompt.txt',prompt)):(directory/name).write_bytes(body)
        for name,body in (('result.json',persisted),('receipt.json',receipt)):(directory/name).write_text(json.dumps(body),encoding='utf-8')
        raw={'status':'completed','usage':actual,'provider_receipt':receipt,
             'outcome':{'loss':1.0,'hard':1,'soft':1.0,'artifact_checks':[],'scope_ok':True,'validation_truth_ok':True}}
        return raw,request,directory

    def test_durable_receipt_hash_thread_usage_runtime_plan_and_output(self):
        spec,output=self.bundle();item=spec['order'][0];raw,request,directory=self.receipt_fixture(spec,item)
        evidence=P['verify_receipt'](spec,item,raw,request)
        self.assertTrue(evidence['strict_artifact_quality']);self.assertEqual(evidence['cli_thread_id'],'synthetic-real-format-thread')
        changed=copy.deepcopy(raw);changed['provider_receipt']['bindings']['runtime_sha256']='f'*64
        (directory/'receipt.json').write_text(json.dumps(changed['provider_receipt']),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'binding mismatch'):P['verify_receipt'](spec,item,changed,request)
        (directory/'receipt.json').write_text(json.dumps(raw['provider_receipt']),encoding='utf-8')
        (directory/'stdout.raw').write_bytes((directory/'stdout.raw').read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'hash changed'):P['verify_receipt'](spec,item,raw,request)

    def test_durable_receipt_rejects_unknown_tools_and_incorrect_plan(self):
        spec,output=self.bundle();item=spec['order'][0]
        raw,request,directory=self.receipt_fixture(spec,item,extra_events=[{'type':'item.started','item':{'type':'code_mode'}}])
        with self.assertRaisesRegex(ValueError,'unregistered event'):P['verify_receipt'](spec,item,raw,request)
        spec,output=self.bundle();item=spec['order'][0];raw,request,directory=self.receipt_fixture(spec,item)
        prompt=(directory/'prompt.txt').read_bytes();payload=json.loads(prompt.split(b'\n\n',1)[1]);payload['governance_plan']={'wrong':True}
        newprompt=b'synthetic bounded task\n\n'+json.dumps(payload).encode();(directory/'prompt.txt').write_bytes(newprompt)
        raw['provider_receipt']['prompt_sha256']=sha(newprompt)
        (directory/'receipt.json').write_text(json.dumps(raw['provider_receipt']),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'prompt differs'):P['verify_receipt'](spec,item,raw,request)

    def test_terminal_clock_snapshot_crossing_budget_is_preserved(self):
        spec,output=self.bundle();factory,instances,calls=self.factory(output)
        clock={'time':0.0,'terminal':False}
        def now():
            clock['time']+=.001
            return clock['time']+(7201 if clock['terminal'] else 0)
        actual_summarize=P['collect'].__globals__['summarize']
        def terminal_summary(run):
            value=actual_summarize(run,30);clock['terminal']=True;return value
        with patch.object(P['time'],'perf_counter',side_effect=now),patch.dict(P['collect'].__globals__,summarize=terminal_summary):
            run=self.collect(spec,output,factory)
        self.assertEqual(len(calls),32);self.assertEqual(run['budget']['total_tokens'],3360)
        self.assertEqual(run['status'],'budget-exhausted');self.assertGreater(run['actual_budget_overrun']['wall_seconds'],7200)
        self.assertEqual(run['summary']['actual_charged_usage'],run['budget'])
        self.assertEqual(run['summary']['campaign_wall_seconds'],run['budget']['elapsed_seconds'])
        self.assertEqual(run['summary']['A_time_quality_gate'],'FAIL')

    def test_unknown_paired_usage_metric_is_null_not_invented(self):
        pair=({'model':'a','family':'f','usage':{'total_tokens':2}}, {'model':'a','family':'f','usage':None})
        self.assertIsNone(P['metric']([pair],'total_tokens',20))

    def test_joint_family_bootstrap_preserves_cross_model_correlations(self):
        pairs=[]
        for model in ('a','b'):
            for family in ('first','second'):
                treatment=2.0 if (model=='a')==(family=='first') else .5
                pairs.append(({'model':model,'family':family,'callback_seconds':1.0},
                              {'model':model,'family':family,'callback_seconds':treatment}))
        measured=P['metric'](pairs,'callback_seconds',400)
        self.assertEqual(measured['ratio'],1.25)
        self.assertEqual(measured['paired_joint_family_block_95_interval'],[1.25,1.25])

    def test_common_http_profile_changes_only_exact_cli_exec_and_retains_io(self):
        spec,output=self.bundle();entry=next(iter(spec['workers'].values()));seen=[]
        def original(argv,*args,**kwargs):
            seen.append((argv,args,kwargs));return subprocess.CompletedProcess(argv,0,b'actual-stdout',b'actual-stderr')
        native=types.SimpleNamespace(subprocess=types.SimpleNamespace(run=original))
        state=T['install'](native,entry['config'],spec['transport'])
        compiler=[sys.executable,'-B','exact-compiler.py','--write'];result=native.subprocess.run(compiler,input=b'original bytes')
        self.assertIs(seen[0][0],compiler);self.assertEqual(len(state['records']),0)
        state['sample_id']='synthetic call'
        cli=[entry['config']['binary'],'--ask-for-approval','never','exec','--sandbox','read-only','-']
        result=native.subprocess.run(cli,input=b'exact-model-prompt',timeout=180)
        expected=cli[:-1]+[x for value in T['PROFILE'] for x in ('-c',value)]+['-']
        self.assertEqual(seen[1][0],expected);self.assertEqual(seen[1][2],{'input':b'exact-model-prompt','timeout':180})
        self.assertEqual(result.stdout,b'actual-stdout');self.assertEqual(result.stderr,b'actual-stderr')
        row=state['records'][0];self.assertEqual(row['stdout_sha256'],sha(result.stdout));self.assertEqual(row['status'],'returned')
        self.assertEqual(json.loads(Path(row['receipt_path']).read_text()),row)
        with self.assertRaisesRegex(ValueError,'no replay'):native.subprocess.run(cli)
        state['sample_id']='conflicting profile'
        with self.assertRaisesRegex(ValueError,'unreviewed provider'):
            native.subprocess.run(cli[:-1]+['-c','model_provider="other"','-'])
        self.assertEqual(len(seen),2)

    def test_http_timeout_has_one_durable_unknown_trace_no_retry(self):
        spec,output=self.bundle();entry=next(iter(spec['workers'].values()));seen=[]
        def original(argv,*args,**kwargs):seen.append(argv);raise subprocess.TimeoutExpired(argv,180,output=b'partial')
        native=types.SimpleNamespace(subprocess=types.SimpleNamespace(run=original));state=T['install'](native,entry['config'],spec['transport'])
        state['sample_id']='synthetic timeout'
        with self.assertRaises(subprocess.TimeoutExpired):
            native.subprocess.run([entry['config']['binary'],'--ask-for-approval','never','exec','-'])
        self.assertEqual(len(seen),1);row=state['records'][0]
        self.assertEqual(row['status'],'unknown');self.assertFalse(row['automatic_retry'])
        self.assertEqual(json.loads(Path(row['receipt_path']).read_text()),row)

    def test_http_postcall_evidence_failure_preserves_actual_result_for_native_usage(self):
        spec,output=self.bundle();entry=next(iter(spec['workers'].values()));seen=[]
        def original(argv,*args,**kwargs):seen.append(argv);return subprocess.CompletedProcess(argv,0,b'paid result',b'')
        native=types.SimpleNamespace(subprocess=types.SimpleNamespace(run=original));state=T['install'](native,entry['config'],spec['transport'])
        state['sample_id']='synthetic postcall write failure';original_atomic=T['install'].__globals__['atomic'];writes=[]
        def fail_second(path,value):
            writes.append(value['status'])
            if len(writes)>1:raise OSError('synthetic evidence publication failure')
            return original_atomic(path,value)
        with patch.dict(T['install'].__globals__,atomic=fail_second):
            result=native.subprocess.run([entry['config']['binary'],'--ask-for-approval','never','exec','-'])
        self.assertEqual(result.stdout,b'paid result');self.assertEqual(len(seen),1)
        self.assertIn('evidence_error',state['records'][0])
        self.assertEqual(json.loads(Path(state['records'][0]['receipt_path']).read_text())['status'],'pending')

    def test_parent_verifies_actual_http_argv_and_raw_output_binding(self):
        spec,output=self.bundle();item=spec['order'][0];raw,request,directory=self.receipt_fixture(spec,item)
        entry=spec['workers'][item['model']+':'+item['condition']]
        def original(argv,*args,**kwargs):return subprocess.CompletedProcess(argv,0,(directory/'stdout.raw').read_bytes(),(directory/'stderr.raw').read_bytes())
        native=types.SimpleNamespace(subprocess=types.SimpleNamespace(run=original));state=T['install'](native,entry['config'],spec['transport'])
        state['sample_id']=item['model']+':'+item['condition']+':'+item['task_id']
        argv=P['expected_cli_arguments'](spec,item,raw)
        native.subprocess.run(argv)
        message={'transport_receipts':state['records']}
        checked=P['verify_transport'](spec,item,message,raw)
        self.assertEqual(checked['argv_sha256'],state['records'][0]['argv_sha256'])
        # Self-consistent hashes cannot authorize extra permission/config flags.
        changed=copy.deepcopy(message);row=changed['transport_receipts'][0]
        original=P['expected_cli_arguments'](spec,item,raw)
        malicious=original[:-1]+['-c','features.shell_tool=true','-']
        row['argv']=malicious[:-1]+[part for value in T['PROFILE'] for part in ('-c',value)]+['-']
        row['original_argv_sha256']=digest(malicious);row['argv_sha256']=digest(row['argv'])
        Path(row['receipt_path']).write_text(json.dumps(row),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'binding mismatch'):P['verify_transport'](spec,item,changed,raw)
        changed=copy.deepcopy(message);changed['transport_receipts'][0]['stdout_sha256']='f'*64
        Path(changed['transport_receipts'][0]['receipt_path']).write_text(json.dumps(changed['transport_receipts'][0]),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'binding mismatch'):P['verify_transport'](spec,item,changed,raw)

    def test_invalid_transport_trace_stops_after_retaining_known_charge(self):
        spec,output=self.bundle();factory,instances,calls=self.factory(output)
        def invalid(*args):raise ValueError('synthetic transport evidence mismatch')
        run=P['collect'](spec,output,allow_dispatch_protocol_sha256=digest(spec),worker_factory=factory,
                         verifier=self.verifier,transport_verifier=invalid)
        self.assertEqual(run['status'],'protocol-violation');self.assertEqual(len(calls),1)
        self.assertEqual(run['budget']['calls'],1);self.assertEqual(run['budget']['total_tokens'],105)
        self.assertFalse(run['observations'][0]['fresh'])


if __name__=='__main__':unittest.main(verbosity=2)
