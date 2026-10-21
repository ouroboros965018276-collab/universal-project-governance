"""Offline OCR-report regressions; synthetic evidence, no model or container calls."""
import copy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evolution import __main__ as cli, actor_checkpoint, chat_sse, contracts, controller
from evolution import evaluator, native_codex, promotion, semantic_contract, task_benchmark
from evolution.context_checkpoint import bootstrap, FACTS_SCHEMA, WORKING_SET_FACTS_SCHEMA
from evolution.search import ChaoticAnnealing
from evolution.search._numeric import reflect, json_state, tuple_state
from evolution.source_bridge import SourceBridge, SourceBridgeError

ROOT = Path(__file__).resolve().parents[1]


def model():
    return {'policies': [{'id': 'A', 'severity': 'blocking', 'requires': [], 'evidence': [],
                          'statement': 'Observe', 'closure': 'aaa'}]}


class OCREvolutionRegressions(unittest.TestCase):
    def test_callback_missing_attribute_and_nonobject_checkpoint_are_input_errors(self):
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            cli.load_callable('json:missing_callback')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'run.json'; path.write_text('[]')
            with patch('sys.stderr', io.StringIO()):
                self.assertEqual(cli.main(['inspect', '--run', str(path)]), 2)

    def test_candidate_shapes_and_checkpoint_usage_fail_uniformly(self):
        for theta in (None, 7, '', {}):
            with self.subTest(theta=theta), self.assertRaises(ValueError):
                contracts.materialize({'model': model(), 'theta': theta})
        for candidate in (None, {}, {'model': {}}, {'model': {'policies': [None]}}):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                contracts.materialize(candidate)
        with self.assertRaises(ValueError):
            contracts.Budget(calls=1, records=[{'attempt': 1, 'usage': None}])

    def test_unhealthy_control_is_not_a_quality_floor(self):
        row={'task_id':'t', 'status':'completed', 'outcome':{'hard':1,'soft':.4,'loss':1}}
        control={'task_id':'t', 'status':'failed', 'outcome':{'hard':0,'soft':0,'loss':0}}
        self.assertIsNone(controller.task_loss([row], [control]))

    def test_source_patch_overlap_ranking_and_header_injection(self):
        bridge=SourceBridge(model())
        with self.assertRaisesRegex(SourceBridgeError, 'exactly once'):
            bridge.bind_patch({'edits':[{'op':'replace','target':'aa','content':'b',
                                         'update_target':'policies/A/closure'}]})
        for details in ([], '', 0, False):
            with self.subTest(details=details), self.assertRaises(SourceBridgeError):
                bridge.bind_patch({'edits':[], 'ranking_details':details})
        value=model();value['policies'][0]['id']='A\n## injected'
        with self.assertRaises(SourceBridgeError): SourceBridge(value)

    def test_checkpoint_schema_selection_is_bidirectional(self):
        for include, schema in ((False,WORKING_SET_FACTS_SCHEMA),(True,FACTS_SCHEMA)):
            with self.assertRaises(ValueError):bootstrap([], {'schema':schema},include_working_set=include)

    def test_numeric_checkpoint_validation_and_nested_rng_state(self):
        for value in (math.inf,-math.inf,math.nan):
            with self.assertRaises(ValueError):reflect(value)
        self.assertEqual(reflect(10**400),0)
        self.assertEqual(tuple_state(json.loads(json.dumps(json_state({'a': (1,(2,3))})))), {'a':(1,(2,3))})
        annealing=ChaoticAnnealing(1,3);annealing.propose([.5]*3)
        state=annealing.state();state['last_temperature'] /= 2
        with self.assertRaises(ValueError):ChaoticAnnealing.from_state(state)
        for state in (None,[],{}, {'algorithm':'chaotic-annealing-v1'}):
            with self.assertRaises(ValueError):ChaoticAnnealing.from_state(state)

    def test_evaluation_cache_binds_retries_and_requires_object_receipts(self):
        candidate={'model':model()};cache={};calls=[]
        def runner(request):
            calls.append(request)
            return {'status':'failed','usage':{'total_tokens':1},'provider_receipt':'invalid'}
        kwargs={'runner_identity':{'id':'fixture','version':'1'},'source':{},'cache':cache}
        first=evaluator.evaluate(candidate,{'id':'t'},runner,retries=0,**kwargs)
        second=evaluator.evaluate(candidate,{'id':'t'},runner,retries=1,**kwargs)
        self.assertEqual(len(calls),3)
        self.assertNotEqual(first['cache_key'],second['cache_key'])
        self.assertFalse(first['empirical_eligible'])

    def test_evidence_root_and_optimizer_identity_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'base';base.mkdir();outside=Path(tmp)/'outside.json';outside.write_text('{}')
            ref={'path':str(outside),'sha256':promotion.hashlib.sha256(outside.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(promotion.EvidenceError,'escapes'):
                promotion._artifact(ref,base)
        frozen={'kind':'independent-holdout-freeze','independent_actor':'reviewer'}
        raw=contracts.canonical_bytes(frozen)
        manifest={'freeze':{'git_revision':'a'*40,'path':'freeze.json','sha256':promotion.hashlib.sha256(raw).hexdigest()}}
        with patch.object(promotion,'_git',side_effect=[b'',raw]):
            with self.assertRaisesRegex(promotion.EvidenceError,'independent'):
                promotion._freeze(manifest,ROOT)

    def test_unregistered_executable_input_and_invalid_schema_do_not_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'binary';binary.write_bytes(b'fixture')
            service=native_codex.NativeCodex({'binary':str(binary),'artifact_root':str(Path(tmp)/'artifacts'),
                'model':'fixture','effort':'low','timeout_seconds':1,'grader':'evolution.task_benchmark:grade'})
            with patch.object(native_codex.subprocess,'run') as dispatch:
                with self.assertRaisesRegex(ValueError,'owner-registered'):
                    service._prepare({}, {'compiler':'raise RuntimeError','license':'fixture'}, {})
                with self.assertRaisesRegex(ValueError,'output_schema'):
                    service._call(key='fixture',prompt='fixture',bindings={},output_schema=[])
                dispatch.assert_not_called()
            self.assertFalse((service.artifacts/'calls').exists())

    def test_checkpoint_needs_an_external_anchor_before_opening_references(self):
        with patch.object(actor_checkpoint,'_ref',side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError,'caller-owned trust anchor'):
                actor_checkpoint.validate_resume({},task={},provider='fixture',model='fixture',
                    system_context='',configuration={},root=ROOT)

    def test_benchmark_preserves_decimal_values_and_rejects_impossible_tasks(self):
        self.assertFalse(task_benchmark._equal('{"x":1.0000000000000001}','{"x":1.0}','json'))
        self.assertTrue(task_benchmark._equal('{"x":1.00}','{"x":1.0}','json'))
        for kwargs in ({'kinds':{'a':'typo'}},{'forbidden':{'a':'bare-string'}},{'kinds':{'other':'text'}}):
            with self.assertRaises(ValueError):task_benchmark.task('t','f',{'a':'x'},{'a':'x'},'fixture',**kwargs)
        with self.assertRaises(ValueError):task_benchmark.task('t','f',{'a':'x'},{},'fixture')
        task=task_benchmark.task('t','f',{'a':'x'},{'a':'x'},'fixture')
        response={'files':[{'path':'a','content':'x'},{'path':'a','content':'x'}],'validation':'not_run'}
        result=task_benchmark.grade({'task':task,'response_json':response,'usage':{'total_tokens':1},'wall_seconds':0})
        self.assertFalse(result['scope_ok'])

    def test_sse_delta_processing_does_not_materialize_accumulated_strings(self):
        parser=chat_sse.ChatSSE(); original=chat_sse._canonical; largest=[]
        def measured(value):
            if isinstance(value,dict):
                content=value.get('choices',[{}])[0].get('message',{}).get('content')
                largest.append(len(content or ''))
            return original(value)
        with patch.object(chat_sse,'_canonical',side_effect=measured):
            for _ in range(1000):
                parser._event(json.dumps({'object':'chat.completion.chunk','id':'r','model':'m',
                    'choices':[{'index':0,'delta':{'content':'x'},'finish_reason':None}]}))
        self.assertEqual(parser.response()['choices'][0]['message']['content'],'x'*1000)
        self.assertEqual(max(largest),0)

    def test_semantic_primitive_and_guard_exceptions_keep_call_provenance(self):
        for body, error in [('return int(g() + "x")','TypeError'),
                            ('if g():\n        x = int("x")\n    return 0','ValueError')]:
            files={'m.py':'def g():\n    return 1\ndef f():\n    '+body+'\n'}
            contract={'schema_version':1,'modules':{'m.py':{'required_functions':{'f':{},'g':{}},
                'required_calls':{'f':[{'path':'m.py','function':'g'}]}}},
                'probes':[{'path':'m.py','function':'f','expect':{'raises':error}}]}
            result=semantic_contract.validate_behavior(files,contract)
            self.assertTrue(result['ok'],result)

    def test_semantic_keywords_forbidden_attributes_and_module_errors(self):
        contract={'schema_version':1,'modules':{'m.py':{'required_functions':{'f':{'params':['x']}},
            'forbidden_symbols':['strip']}},'probes':[{'path':'m.py','function':'f','args':['x'],'expect':{'return':'x'}}]}
        result=semantic_contract.validate_behavior({'m.py':'def f(x):\n    return x.strip()\n'},contract)
        self.assertEqual(result['failures'][0]['code'],'forbidden-symbol-present')
        bad=copy.deepcopy(contract);bad['modules']['m.py']['required_functions']={'class':{}}
        self.assertFalse(semantic_contract.validate_contract(bad)["ok"])
        result=semantic_contract.validate_behavior({'m.py':'X = "x" + 1\ndef f(x):\n    return x\n'},contract)
        self.assertEqual(result['failures'][0],{'code':'module-evaluation-error','path':'m.py'})


if __name__=='__main__':unittest.main()
