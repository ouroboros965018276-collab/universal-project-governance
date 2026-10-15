"""Bounded provider-index compatibility; all external execution is mocked."""
import sys
import unittest
if sys.version_info<(3,10):raise unittest.SkipTest('Engineering API tests require Python3.10+ before evolution import')
import copy,json,os
from unittest.mock import create_autospec,patch
from test_provider_tools import _ProviderFixture,SECRET,call,completion
from evolution import provider_tools as lab,engineering_broker as engineering,project_executor
from evolution.tool_broker import canonical,sha

class EngineeringToolIndexTests(_ProviderFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        (self.workspace/'target.txt').unlink()
        self.task={'id':'public-index-fixture','family':'public-index-fixture','prompt':'Read the registered project and report the known incomplete state.',
            'initial_files':{'pkg.py':'value = 1\n','contract.json':'{}\n','README.md':'Public synthetic fixture.\n'},'writable_files':['pkg.py'],
            'required_read_paths':['pkg.py'],'required_tools':['repo_read','repo_patch','repo_validate','repo_status'],
            'engineering_contract':{'schema_version':1,'contract_id':'public-index-only','trusted_files':{'public_test.py':'import unittest\n'},
                'checks':[{'id':'unit','recipe':'unittest','minimum_tests':1,'test_modules':['public_test'],'expected_test_ids':['public_test.Public.test_value']}]}}
        for name,text in self.task['initial_files'].items():(self.workspace/name).write_bytes(text.encode())
        self.definitions={item['name']:item for item in engineering.tool_definitions()}
        self.definitions[lab.FINISH_TOOL]={'inputSchema':lab.FINAL_SCHEMA}
        for name in('execute_project','validate_with_project_execution','_capture'):
            fence=patch.object(project_executor,name,side_effect=AssertionError('project/Docker execution forbidden'));fence.start();self.addCleanup(fence.stop)

    def item(self,identifier='read-0',path='pkg.py',index='absent'):
        result=call(identifier,'repo_read',{'paths':[path]})
        if index!='absent':result['index']=index
        return result

    def batch(self,items,seen=None):return lab._engineering_batch(items,self.definitions,set()if seen is None else seen,SECRET,self.task)

    def test_indices012_noindex_and_mixed_positions_are_readonly(self):
        batches=[ [self.item('r'+str(i),index=i)for i in range(3)],
            [self.item('r'+str(i))for i in range(3)],
            [self.item('r0',index=0),self.item('r1'),self.item('r2',index=2)],
            [self.item('r0'),self.item('r1',index=1),self.item('r2')] ]
        for items in batches:
            with self.subTest(keys=[sorted(x)for x in items]):
                before=canonical(items);parsed,rejected=self.batch(items)
                self.assertEqual(len(parsed),3);self.assertEqual(rejected,[]);self.assertEqual(canonical(items),before)

    def test_wrong_index_types_values_order_and_duplicates_reject(self):
        batches=[[self.item(index=x)]for x in(True,False,0.0,'0',-1,1,None)]
        batches += [[self.item('r0',index=0),self.item('r1',index=0)], [self.item('r0',index=1),self.item('r1',index=0)], [self.item('r0'),self.item('r1',index=2)]]
        for items in batches:
            with self.subTest(indices=[x.get('index')for x in items]),self.assertRaises(ValueError):self.batch(items)

    def test_unknown_outer_and_function_extra_keys_still_reject(self):
        for index in('absent',0):
            item=self.item(index=index);item['extra']=None
            with self.subTest(where='outer',index=index),self.assertRaises(ValueError):self.batch([item])
            item=self.item(index=index);item['function']['extra']=None
            with self.subTest(where='function',index=index),self.assertRaises(ValueError):self.batch([item])

    def test_duplicate_seen_blank_wrong_ids_and_tool_type_still_reject(self):
        for items,seen in [([self.item('same',index=0),self.item('same',index=1)],set()),([self.item('seen',index=0)],{'seen'}),([self.item(' ',index=0)],set()),([self.item(None,index=0)],set())]:
            with self.subTest(ids=[x['id']for x in items]),self.assertRaises(ValueError):self.batch(items,seen)
        item=self.item(index=0);item['type']='not-function'
        with self.assertRaises(ValueError):self.batch([item])

    def test_unknown_tool_credentials_read_and_protected_write_scope_still_reject(self):
        for mode in('unknown-tool','credential-raw','credential-decoded','read-outside','write-protected','write-outside'):
            item=self.item(index=0)
            if mode=='unknown-tool':item['function']['name']='unregistered'
            elif mode=='credential-raw':item['function']['arguments']=json.dumps({'paths':[SECRET]})
            elif mode=='credential-decoded':item['function']['arguments']='{"paths":["'+''.join('\\u%04x'%ord(c)for c in SECRET)+'"]}'
            elif mode=='read-outside':item['function']['arguments']=json.dumps({'paths':['../outside']})
            else:item=call('write','repo_patch',{'operations':[{'path':'contract.json'if mode=='write-protected'else'../outside','old_sha256':'a'*64,'new_text':'changed'}]});item['index']=0
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.batch([item])

    def test_argument_schema_failure_remains_bounded_not_executed_classification(self):
        item=self.item(index=0);item['function']['arguments']=json.dumps({'paths':['pkg.py'],'undefined':True})
        parsed,rejected=self.batch([item]);self.assertEqual(rejected,['read-0']);self.assertEqual(parsed[0]['tool'],'repo_read')
        item['function']['arguments']='{';self.assertEqual(self.batch([item])[1],['read-0'])

    def produce(self,first,provider='deepseek'):
        payloads=[];counter=[0]
        finish=call('finish','repo_finish',{'summary':'Public synthetic read only; required repair and validation remain incomplete.','validation':'failed','helper_gap':'project_tool unavailable in bounded broker'});finish['index']=0
        def response(provider,payload,key,timeout):
            payloads.append(copy.deepcopy(payload));counter[0]+=1
            body=completion(counter[0],first if counter[0]==1 else[finish]);body['model']='synthetic-observed-model'
            return 200,{},canonical(body)
        post=create_autospec(lab._bounded_post,side_effect=response)
        # Wrap the true class method, never substitute a broker implementation.
        actual=[];real_call=engineering.EngineeringBroker.call
        def observed(broker,name,args):actual.append((type(broker),name,copy.deepcopy(args)));return real_call(broker,name,args)
        root=self.artifacts/provider
        def reserve(metadata):
            value=self.reserve(metadata);folder=root/'fixture-reservations';folder.mkdir(parents=True,exist_ok=True)
            raw=canonical(metadata)+b'\n'
            with(folder/(metadata['request_id']+'.json')).open('xb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            return dict(value,reservation_receipt_sha256=sha(raw))
        def account(metadata):
            self.account(metadata);folder=root/'fixture-accounted';folder.mkdir(parents=True,exist_ok=True)
            with(folder/(metadata['request_id']+'.json')).open('xb')as stream:stream.write(canonical(metadata)+b'\n');stream.flush();os.fsync(stream.fileno())
        with patch.object(lab,'_bounded_post',post),patch.object(lab,'_post',side_effect=AssertionError('HTTP forbidden')),patch.object(engineering.EngineeringBroker,'call',observed):
            result=lab.run_actor(provider,'deepseek-v4-pro'if provider=='deepseek'else'mimo-v2.6-flash',self.task,self.workspace,root,self.git,'Public synthetic fixed context',self.key,
                response_json_mode=False,thinking='disabled',profile_id=lab.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE,execution_backend=engineering.BACKEND_ID,broker_profile_id=engineering.PROFILE_ID,
                connect_retry_policy=None,tool_feedback_policy=None,before_request=reserve,after_request=account)
        return result,payloads,actual,root

    def test_true_engineering_broker_read_then_finish_preserves_raw_index_and_replay(self):
        for provider in('deepseek','mimo'):
            with self.subTest(provider=provider):
                item=self.item(index=0);item['function']['arguments']='{ "paths" : ["pkg.py"] }'
                result,payloads,actual,root=self.produce([item],provider)
                self.assertEqual(result['status'],'completed');self.assertEqual(result['requests'],2)
                self.assertEqual([x[1]for x in actual],['repo_read']);self.assertIs(actual[0][0],engineering.EngineeringBroker)
                self.assertEqual([x['tool']for x in result['tool_events']],['repo_read']);self.assertTrue(result['tool_events'][0]['result']['ok'])
                self.assertFalse(result['execution_state_unknown']);self.assertEqual(result['quality']['task_success'],0)
                self.assertEqual(result['quality']['final_execution_not_run_reason'],'required-current-project-validation-missing')
                first=json.loads((root/'requests/01.response.json').read_bytes())['response']['choices'][0]['message']['tool_calls'][0]
                self.assertEqual(first,item);assistant=next(m for m in payloads[1]['messages']if m['role']=='assistant')
                self.assertEqual(assistant['tool_calls'][0],item)
                receipt=json.loads((root/'requests/01.receipt.json').read_bytes())
                self.assertEqual(receipt['response_sha256'],sha((root/'requests/01.response.json').read_bytes()))
                final=json.loads((root/'requests/02.response.json').read_bytes())['response']['choices'][0]['message']['tool_calls'][0]
                self.assertIs(type(final['index']),int);self.assertEqual(final['index'],0)

    def test_true_broker_batch012_executes_all_three_ordered_reads(self):
        result,_,actual,_=self.produce([self.item('r'+str(i),path,index=i)for i,path in enumerate(('pkg.py','contract.json','README.md'))])
        self.assertEqual(result['status'],'completed');self.assertEqual([x[1]for x in actual],['repo_read']*3)
        self.assertEqual([x['arguments']['paths'][0]for x in result['tool_events']],['pkg.py','contract.json','README.md'])
        self.assertEqual(result['tool_attempts'],4)

    def test_bad_second_ordinal_prevalidates_whole_batch_without_broker_or_feedback(self):
        result,_,actual,_=self.produce([self.item('r0',index=0),self.item('r1',index=0)])
        self.assertEqual(result['status'],'tool-contract-failed');self.assertEqual(result['requests'],1)
        self.assertEqual(actual,[]);self.assertEqual(result['tool_events'],[]);self.assertEqual(result['schema_rejections'],0)

class LegacyIndexPathTests(_ProviderFixture,unittest.TestCase):
    def test_ordinary_profile_keeps_existing_envelope_behavior(self):
        read=call('legacy-read','repo_read',{'paths':['target.txt']});read['index']='legacy-uninterpreted'
        final=call('legacy-finish','repo_finish',{'summary':'Known incomplete public fixture','validation':'failed','helper_gap':'project_tool unavailable in bounded broker'});final['index']=True
        counter=[0]
        def response(provider,payload,key,timeout):
            counter[0]+=1;return 200,{},canonical(completion(counter[0],[read]if counter[0]==1 else[final]))
        with patch.object(lab,'_bounded_post',create_autospec(lab._bounded_post,side_effect=response)),patch.object(lab,'_post',side_effect=AssertionError('HTTP forbidden')):result=self.run_actor()
        self.assertEqual(result['status'],'completed');self.assertEqual([e['tool']for e in result['tool_events']],['repo_read'])
