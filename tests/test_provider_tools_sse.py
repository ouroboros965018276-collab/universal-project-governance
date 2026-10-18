"""Synthetic SSE framing and owned fake HTTPS controls; no paid/network/CLI I/O."""
import copy
import http.client
import json
import sys
import threading
import unittest
from unittest.mock import patch

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Provider helper requires Python 3.10+")

from evolution import chat_sse as sse
from evolution import provider_tools as api
from evolution.tool_broker import canonical, sha
from test_provider_tools import _ProviderFixture, completion, call, SECRET
import test_engineering_provider as engineering_fixture


def event(value, ending=b"\r\n"):
    return b"data: " + (value if isinstance(value, bytes) else canonical(value)) + ending * 2


def chunk(delta=None, finish=None, usage=None, choices=True, created=1):
    return {"id": "synthetic-response", "model": "synthetic-model", "object": "chat.completion.chunk",
            "created": created, "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}] if choices else [],
            "usage": usage}


USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
         "prompt_tokens_details": {"cached_tokens": 2}, "completion_tokens_details": {"reasoning_tokens": 1}}


def wire(native, provider="deepseek"):
    choice = native["choices"][0]
    message = choice["message"]
    parts = [chunk({"role": "assistant", "content": message.get("content"),
                    "reasoning_content": message.get("reasoning_content")})]
    for index, tool in enumerate(message.get("tool_calls") or []):
        name, args = tool["function"]["name"], tool["function"]["arguments"]
        split = max(1, len(args) // 2)
        parts.append(chunk({"tool_calls": [{"index": index, "id": tool["id"], "type": tool["type"],
            "function": {"name": name[:3], "arguments": args[:split]}}]}))
        parts.append(chunk({"tool_calls": [{"index": index,
            "function": {"name": name[3:], "arguments": args[split:]}}]}))
    parts.append(chunk(finish=choice["finish_reason"], usage=native["usage"] if provider == "deepseek" else None))
    if provider == "mimo":
        parts.append(chunk(usage=native["usage"], choices=False))
    for i, part in enumerate(parts):
        part.update(id=native["id"], model=native["model"], created=i + 1)
    return b": keep-alive\r\n\r\n" + b"".join(event(part) for part in parts) + event(b"[DONE]")


def nullable_role_wire(body):
    """Fresh official-shaped MiMo placeholders; never reads a real response."""
    rebuilt, first = [], True
    for block in body.split(b'\r\n\r\n'):
        if not block.startswith(b'data: {'):
            rebuilt.append(block)
            continue
        value = json.loads(block[6:])
        if value['choices']:
            delta = value['choices'][0]['delta']
            if first:
                first = False
                original = dict(delta)
                value['choices'][0]['delta'] = {'role': 'assistant', 'content': '',
                    'reasoning_content': None, 'tool_calls': None}
                rebuilt.append(b'data: '+canonical(value))
                for field, text in (('reasoning_content', original.get('reasoning_content')),
                                    ('content', original.get('content') or 'public synthetic content')):
                    extra = copy.deepcopy(value)
                    extra['choices'][0]['delta'] = {'role': None, 'content': None,
                        'reasoning_content': None, 'tool_calls': None, field: text}
                    rebuilt.append(b'data: '+canonical(extra))
                continue
            delta['role'] = None
            for key in ('content', 'reasoning_content', 'tool_calls'):
                delta.setdefault(key, None)
        rebuilt.append(b'data: '+canonical(value))
    return b'\r\n\r\n'.join(rebuilt)


class SSEProjectionTests(unittest.TestCase):
    def native(self):
        return completion(1, [call("tool-0", "repo_read", {"paths": ["中文.py"]})], content="你好")

    def test_both_provider_shapes_every_byte_split_and_created_variation(self):
        for provider in ("deepseek", "mimo"):
            raw = wire(self.native(), provider)
            expected = sse.project(raw, body_complete=True)
            self.assertTrue(expected["terminal_complete"])
            self.assertTrue(expected["sse"]["message_valid"])
            self.assertEqual(expected["response"]["choices"][0]["message"], self.native()["choices"][0]["message"])
            for split in range(len(raw) + 1):
                parser = sse.ChatSSE()
                parser.feed(raw[:split]); parser.feed(raw[split:])
                self.assertEqual(parser.report(body_complete=True), expected)

    def test_official_mimo_nullable_role_reasoning_content_tools_and_finish(self):
        native = self.native()
        raw = nullable_role_wire(wire(native, 'mimo'))
        self.assertIn(b'"role":null', raw)
        result = sse.project(raw, body_complete=True)
        self.assertTrue(result['terminal_complete'])
        self.assertTrue(result['sse']['message_valid'])
        self.assertEqual(result['response']['choices'][0]['message'], native['choices'][0]['message'])
        for wrong_role in ('user', 7):
            invalid = event(chunk({'role': wrong_role}, finish='stop', usage=USAGE))+event(b'[DONE]')
            rejected = sse.project(invalid, body_complete=True)
            self.assertTrue(rejected['terminal_complete'])
            self.assertFalse(rejected['sse']['message_valid'])
            self.assertEqual(rejected['response']['usage'], USAGE)

    def test_interleaved_tool_names_and_arguments_keep_indexes(self):
        fields = [
            chunk({"tool_calls": [{"index": 1, "id": "b", "type": "function", "function": {"name": "repo_", "arguments": "{"}},
                                   {"index": 0, "id": "a", "type": "function", "function": {"name": "repo_", "arguments": "{"}}]}),
            chunk({"tool_calls": [{"index": 0, "function": {"name": "read", "arguments": "}"}},
                                   {"index": 1, "function": {"name": "status", "arguments": "}"}}]}),
            chunk(finish="tool_calls", usage=USAGE)]
        result = sse.project(b"".join(event(x) for x in fields) + event(b"[DONE]"), body_complete=True)
        tools = result["response"]["choices"][0]["message"]["tool_calls"]
        self.assertTrue(result["terminal_complete"])
        self.assertEqual([(t["id"], t["function"]) for t in tools], [
            ("a", {"name": "repo_read", "arguments": "{}"}), ("b", {"name": "repo_status", "arguments": "{}"})])

    def test_multiline_data_bom_comments_and_all_line_endings(self):
        data = canonical(chunk(finish="stop", usage=USAGE))
        for ending in (b"\n", b"\r", b"\r\n"):
            raw = b"\xef\xbb\xbf: keep-alive" + ending * 2 + b"data: " + data[:1] + ending + b"data: " + data[1:] + ending * 2 + event(b"[DONE]", ending) + b": trailing"
            parser = sse.ChatSSE()
            for byte in raw:
                parser.feed(bytes([byte]))
            self.assertTrue(parser.report(body_complete=True)["terminal_complete"])

    def test_missing_terminal_interruption_and_observed_usage(self):
        finished = event(chunk(finish="stop", usage=USAGE))
        for raw, eof in ((finished, True), (finished + event(b"[DONE]"), False),
                         (event(chunk()) + event(b"[DONE]"), True)):
            result = sse.project(raw, body_complete=eof)
            self.assertFalse(result["terminal_complete"])
        result = sse.project(finished + b"data: {", body_complete=False)
        self.assertEqual(result["response"]["usage"], USAGE)
        self.assertTrue(result["sse"]["usage_observed"])
        # No dispatch of a usage chunk lacking its blank separator.
        result = sse.project(event(chunk(finish="stop")) + event(chunk(usage=USAGE, choices=False))[:-2], body_complete=True)
        self.assertIsNone(result["response"]["usage"])
        result = sse.project(event(chunk(usage=USAGE)) + event(b"[DONE]"), body_complete=True)
        self.assertFalse(result['terminal_complete'])
        self.assertEqual(result['response']['usage'], USAGE)

    def test_malformed_identity_terminal_json_utf8_and_trailing_data(self):
        good = event(chunk(finish="stop", usage=USAGE))
        bad = [good + event(dict(chunk(choices=False, usage=USAGE), model="different")),
               good + event(chunk(choices=False, usage=USAGE)),
               good + event(b"[DONE]") + event(b"[DONE]"),
               good + event(b"[DONE]") + event(chunk()),
               event(b'{"id":"x","id":"x"}'), event(b"\xff"), b"event: x\n\n"]
        for raw in bad:
            self.assertFalse(sse.project(raw, body_complete=True)["terminal_complete"])

    def test_model_envelope_invalid_keeps_transport_usage(self):
        raw = event(chunk({"role": "user", "content": 7, "reasoning_content": []})) + event(chunk(finish="stop", usage=USAGE)) + event(b"[DONE]")
        result = sse.project(raw, body_complete=True)
        self.assertTrue(result["terminal_complete"])
        self.assertFalse(result["sse"]["message_valid"])
        self.assertEqual(result["response"]["usage"], USAGE)

    def test_nonfinite_json_exponent_is_rejected_without_nonjson_projection(self):
        bad = event(chunk(finish='stop', usage=dict(USAGE, extra=1))).replace(b'"extra":1', b'"extra":1e999')
        result = sse.project(bad + event(b'[DONE]'), body_complete=True)
        self.assertFalse(result['terminal_complete'])
        self.assertEqual(result['error_code'], 'sse-invalid-json')
        self.assertNotIn(b'Infinity', canonical(result['response']))

    def test_each_finite_bound_positive_and_plus_one(self):
        raw = event(chunk(finish="stop", usage=USAGE)) + event(b"[DONE]")
        result = sse.project(raw, body_complete=True)
        projection_bytes = len(canonical(result["response"]))
        event_bytes = len(event(chunk(finish="stop", usage=USAGE)))
        for name, cap in (("max_raw", len(raw)), ("max_event", event_bytes),
                          ("max_blocks", 2), ("max_projection", projection_bytes)):
            parser = sse.ChatSSE(**{name: cap}); parser.feed(raw)
            self.assertTrue(parser.report(body_complete=True)["terminal_complete"], name)
            parser = sse.ChatSSE(**{name: cap - 1}); parser.feed(raw)
            report = parser.report(body_complete=True)
            self.assertFalse(report["terminal_complete"], name)
            if name == "max_projection":
                self.assertLessEqual(len(canonical(report["response"])), cap - 1)
        parser = sse.ChatSSE(max_blocks=2); parser.feed(b": comment\n\n" + raw)
        self.assertEqual(parser.report(body_complete=True)["error_code"], "sse-block-limit")

    def test_exact_http_status_media_charset_and_entity_encoding(self):
        for rows in ([('Content-Type', 'text/event-stream')], [('Content-Type', 'Text/Event-Stream; charset="utf-8"')],
                     [('Content-Type', 'text/event-stream; p="a;b"'), ('Content-Encoding', 'identity')]):
            self.assertTrue(sse.headers_valid(200, rows))
        for status, rows in ((201, [('Content-Type', 'text/event-stream')]), (200, []),
                             (200, [('Content-Type', 'application/json')]),
                             (200, [('Content-Type', 'text/event-stream; charset=latin1')]),
                             (200, [('Content-Type', 'text/event-stream'), ('Content-Encoding', 'gzip')])):
            self.assertFalse(sse.headers_valid(status, rows))


class SSEActorTests(engineering_fixture.EngineeringCandidateTests):
    # The inherited focused engineering controls also guard legacy behavior.

    def test_checkpoint_profile_is_explicit_and_preserves_capacity_configuration(self):
        prior = api.profile_configuration(api.ENGINEERING_ULTRASPEED_CAPACITY_SSE_PROFILE)
        self.assertEqual(sha(canonical(prior)), '6a3b378982dd17b11e9dc5daa3204f36df8d35087993ffccbe8c0b99f5f029c7')
        expected = copy.deepcopy(prior)
        expected.update(profile_id=api.ENGINEERING_CHECKPOINT_SSE_PROFILE,
                        context_checkpoint=copy.deepcopy(api.context_checkpoint.POLICY))
        self.assertEqual(api.profile_configuration(api.ENGINEERING_CHECKPOINT_SSE_PROFILE), expected)
        self.assertEqual(expected['context_checkpoint']['trigger_bytes'], 262144)
        self.assertEqual(expected['context_checkpoint']['max_checkpoints'], 1)
        self.assertEqual(expected['admission_limits']['max_input_bytes'], 524288)
        self.assertNotIn('context_checkpoint', prior)

    def test_checkpoint_two_conversations_keep_actor_budget_evidence_and_id_namespaces(self):
        for provider in ('deepseek', 'mimo'):
            with self.subTest(provider=provider):
                self.artifacts = self.base/('checkpoint-' + provider)
                self.before, self.after, self.loaded, self.executions = [], [], [], []
                (self.workspace/'target.txt').write_bytes(b'old\n')
                first = completion(1, [call('reused', 'repo_read', {'paths': ['target.txt', 'contract.json']})])
                second = completion(2, [call('patch', 'repo_patch', {'operations': [
                    {'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}]})])
                for step in (first, second): step['choices'][0]['message']['reasoning_content'] = 'synthetic reasoning ' * 7000
                third = completion(3, [call('reused', 'repo_validate', {}), call('status', 'repo_status', {})])
                result, payloads = self.run_sse([first, second, third, self.finish(4)], provider,
                    model='deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro-ultraspeed',
                    actor_options={'profile_id': api.ENGINEERING_CHECKPOINT_SSE_PROFILE})
                self.assertEqual(result['status'], 'completed', result['quality'])
                self.assertIs(result['quality']['hard_pass'], True, result['quality'])
                for proof in (result, result['quality']):
                    if 'independent_task_pass' in proof:
                        self.assertIs(proof['independent_task_pass'], True)
                self.assertEqual((result['requests'], result['tool_attempts'], result['conversation_index']), (4, 5, 1))
                self.assertEqual(len(result['context_checkpoint_receipts']), 1)
                self.assertEqual([m['conversation_index'] for m in self.before], [0, 0, 1, 1])
                self.assertEqual(len(payloads[2]['messages']), 3)
                self.assertEqual(payloads[2]['messages'][:2], payloads[0]['messages'])
                self.assertEqual([m['role'] for m in payloads[2]['messages']], ['system', 'user', 'user'])
                self.assertNotIn('synthetic reasoning', payloads[2]['messages'][-1]['content'])
                self.assertEqual(result['api_tool_trace'][0]['tool_call_id'], result['api_tool_trace'][2]['tool_call_id'])
                self.assertEqual([t['conversation_index'] for t in result['api_tool_trace']], [0, 0, 1, 1])
                ref = result['context_checkpoint_receipts'][0]
                raw = (self.artifacts/ref['ref']).read_bytes(); checkpoint = json.loads(raw)
                self.assertEqual(sha(raw), ref['sha256'])
                self.assertEqual(checkpoint['previous_request_receipt_sha256'], self.after[1]['receipt_sha256'])
                self.assertEqual(checkpoint['previous_broker_chain_sha256'], result['api_tool_trace'][1]['chain_sha256'])
                self.assertEqual(checkpoint['bootstrap_payload_sha256'], sha(canonical(payloads[2])))
                self.assertEqual(checkpoint['facts']['budgets']['requests_used'], 2)
                self.assertEqual(checkpoint['facts']['budgets']['tool_attempts_used'], 2)
                self.assertEqual(checkpoint['facts']['budgets']['work_deadline_monotonic'], result['work_deadline_monotonic'])
                self.assertTrue(all(m['work_deadline_monotonic'] == result['work_deadline_monotonic'] for m in self.before))
                self.assertEqual(len({id(b) for b, _ in self.brokers[-2:]}), 2) # admission view + one executing broker
                self.assertEqual(len(self.loaded), 1)
                self.assertEqual(len(self.after), 4)
                self.assertTrue(all((self.artifacts/'requests'/('%02d.response.json'%i)).exists() for i in range(1, 5)))
                self.assertFalse(list(self.artifacts.rglob('*.pending.json')))
                bad = copy.deepcopy(result['api_tool_trace'][:2]); bad[0]['chain_sha256'] = '0'*64
                with self.assertRaises(ValueError):
                    api.context_checkpoint.facts(self.task, {p: sha(t.encode()) for p, t in self.task['initial_files'].items()},
                        checkpoint['facts']['current_files'], result['tool_events'][:2], bad, checkpoint['facts']['budgets'])

    def test_resume_checkpoint_continues_counters_namespace_and_actual_model_finish(self):
        # Explicit caller seam: independent validator and real broker integrity
        # are tested separately; this control never attests a real prefix.
        from evolution import actor_checkpoint
        factory = self.module.create_broker.side_effect
        for provider in ('deepseek', 'mimo'):
            with self.subTest(provider=provider):
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.before, self.after, self.loaded, self.executions = [], [], [], []
                self.artifacts = self.base/('resume-prefix-'+provider)
                model = 'deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro-ultraspeed'
                prefix, old_payloads = self.run_sse(self.ready()[:2], provider, model=model,
                    actor_options={'profile_id':api.ENGINEERING_CHECKPOINT_SSE_PROFILE}, connect_failure_at=3)
                self.assertEqual((prefix['status'],prefix['requests'],prefix['tool_attempts']),('transport-failed-not-invoked',3,2))
                self.assertIsNone(prefix['final_report'])
                old = self.artifacts
                inventory = {p.relative_to(old).as_posix():sha(p.read_bytes())for p in old.rglob('*')if p.is_file()}
                outcomes = [json.loads((old/'requests'/('%02d.receipt.json'%i)).read_bytes())for i in range(1,4)]
                seed = dict(policy_id=actor_checkpoint.POLICY_ID,checkpoint_sha256='a'*64,source_actor_id='synthetic-source',
                    original_artifact_root=str(old),original_task_sha256=sha(canonical(self.task)),
                    original_received_state={n:sha(t.encode())for n,t in self.task['initial_files'].items()},
                    current_files={n:(self.workspace/n).read_text()for n in self.task['initial_files']},
                    events=copy.deepcopy(prefix['tool_events']),traces=copy.deepcopy(prefix['api_tool_trace']),
                    requests_used=3,tools_used=2,elapsed_seconds_used=10,schema_rejections_used=0,
                    reasoning_continuations_used=0,connect_retries_used=0,conversation_index=1,checkpoint_count=1,
                    previous_broker_chain_sha256=prefix['api_tool_trace'][-1]['chain_sha256'],
                    previous_request_receipt_sha256=sha((old/'requests/03.receipt.json').read_bytes()),
                    prior_request_receipts=[{'path':str(old/'requests'/('%02d.receipt.json'%i)),
                        'sha256':sha((old/'requests'/('%02d.receipt.json'%i)).read_bytes())}for i in range(1,4)],
                    prior_outcomes=outcomes,independently_verified_prefix={'path':'SYNTHETIC_CALLER_SEAM','sha256':'b'*64})
                def restored(root,task,git,*,resume_checkpoint=None,**kwargs):
                    broker=factory(root,task,git,**kwargs)
                    if resume_checkpoint is not None:broker.events=copy.deepcopy(resume_checkpoint['events'])
                    return broker
                self.module.create_broker.side_effect=restored
                self.artifacts=self.base/('resumed-'+provider);self.before,self.after,self.loaded=[],[],[]
                work=completion(4,[call('read-1','repo_validate',{}),call('fresh-status','repo_status',{})])
                now=api.time.perf_counter();clock={'schema':'collector-first-setup-absolute-work-deadline-v1',
                    'started_monotonic':now,'work_deadline_monotonic':now+600}
                try:
                    with patch.object(actor_checkpoint,'validate_resume',return_value=seed):
                        result,payloads=self.run_sse([work,self.finish(5)],provider,model=model,
                            actor_options={'profile_id':api.ENGINEERING_CHECKPOINT_SSE_PROFILE,'resume_checkpoint':{'synthetic':True},'actor_timing':clock})
                finally:self.module.create_broker.side_effect=factory
                self.assertEqual(result['status'],'completed',result['quality'])
                self.assertIs(result['quality']['hard_pass'],True)
                self.assertEqual((result['requests'],result['segment_requests'],result['tool_attempts'],result['conversation_index']),(5,2,5,1))
                self.assertEqual([v['request_index']for v in self.before],[4,5])
                self.assertEqual(len(payloads),2)
                self.assertEqual(len(payloads[0]['messages']),3)
                self.assertEqual(payloads[0]['messages'][:2],old_payloads[0]['messages'][:2])
                self.assertNotIn('mock non-private test field',payloads[0]['messages'][-1]['content'])
                transition=json.loads((self.artifacts/'context-checkpoints/resume-01.json').read_bytes())
                self.assertEqual(transition['facts']['budgets']['requests_used'],3)
                self.assertEqual(transition['facts']['budgets']['tool_attempts_used'],2)
                self.assertEqual(transition['effective_work_deadline_monotonic'],result['actor_timing']['work_deadline_monotonic']-10)
                self.assertEqual([t['conversation_index']for t in result['api_tool_trace']],[0,0,1,1])
                self.assertEqual(result['api_tool_trace'][2]['previous_chain_sha256'],seed['previous_broker_chain_sha256'])
                self.assertEqual(result['known_usage']['total_tokens'],sum(r['usage']['total_tokens']for r in outcomes if r['usage'])+sum(r['usage']['total_tokens']for r in self.after))
                self.assertEqual({p.relative_to(old).as_posix():sha(p.read_bytes())for p in old.rglob('*')if p.is_file()},inventory)
                self.assertEqual(len(self.executions),1)

    def test_resume_checkpoint_rejection_never_reserves_loads_key_or_dispatches(self):
        from evolution import actor_checkpoint
        now=api.time.perf_counter();clock={'schema':'collector-first-setup-absolute-work-deadline-v1','started_monotonic':now,'work_deadline_monotonic':now+600}
        with patch.object(actor_checkpoint,'validate_resume',side_effect=ValueError('unverified synthetic prefix')) as validate:
            with self.assertRaises(ValueError):
                self.run_sse([],actor_options={'profile_id':api.ENGINEERING_CHECKPOINT_SSE_PROFILE,'resume_checkpoint':{'unverified':True},'actor_timing':clock})
        validate.assert_called_once()
        self.assertEqual((self.before,self.loaded,self.executions),([],[],[]))
        self.assertFalse(self.artifacts.exists())

    def test_checkpoint_once_and_bootstrap_bounds_do_not_add_dispatches(self):
        for mode in ('once-hard-cap', 'bootstrap-too-large', 'known-failure-facts'):
            with self.subTest(mode=mode):
                self.artifacts = self.base/mode; self.before, self.after, self.loaded, self.executions = [], [], [], []
                steps = [completion(i, [call('status-'+str(i), 'repo_status', {})]) for i in range(1, 7)]
                for step in steps: step['choices'][0]['message']['reasoning_content'] = 'r'*150000
                options = {'profile_id': api.ENGINEERING_CHECKPOINT_SSE_PROFILE}
                if mode == 'bootstrap-too-large': options['system_context'] = 'public synthetic context '*12000
                if mode == 'known-failure-facts':
                    self.validation_failed = True
                    self.git_status.return_value.stdout = b' M target.txt\n'
                    diagnostics = [{'check': 'public-synthetic', 'stdout': 'expected failure detail', 'stderr': 'public failure'}]
                    steps = [self.read(1), self.validate_and_status(2), completion(3, [call('finish', 'repo_finish',
                        {'summary': 'Known unfinished public fixture', 'validation': 'failed',
                         'helper_gap': 'project_tool unavailable in bounded broker'})])]
                    for step in steps[:2]: step['choices'][0]['message']['reasoning_content'] = 'r'*150000
                    observed = steps[1]
                    def retain_failure(payload):
                        broker = self.brokers[-1][0]; original = broker.validate
                        def validate():
                            value = original(); value['diagnostics'] = copy.deepcopy(diagnostics)
                            value['execution'].update(receipt_ref='validation-001/result.json', receipt_sha256='a'*64,
                                                      container_removed=True, scratch_removed=True)
                            return value
                        broker.validate = validate
                        return observed
                    steps[1] = retain_failure
                result, payloads = self.run_sse(steps, actor_options=options)
                if mode == 'known-failure-facts':
                    self.assertEqual((result['status'], result['requests'], len(self.executions)), ('completed', 3, 1))
                    self.assertFalse(result['quality']['hard_pass'])
                    facts = json.loads((self.artifacts/'context-checkpoints/01.json').read_bytes())['facts']
                    self.assertEqual(facts['latest_validation']['diagnostics'], diagnostics)
                    self.assertEqual(facts['latest_validation']['receipt_ref'], 'validation-001/result.json')
                    self.assertEqual(facts['latest_validation']['receipt_sha256'], 'a'*64)
                    self.assertTrue(facts['latest_validation']['container_removed'])
                    self.assertTrue(facts['latest_validation']['scratch_removed'])
                    self.assertIn('latest-validation-known-fail', facts['risks'])
                    self.assertEqual(facts['latest_status']['stdout'], ' M target.txt\n')
                    self.assertIsNone(facts['latest_status']['stderr']) # The broker reports a hash, not this body.
                    self.assertFalse(result['unknown_usage'])
                    continue
                self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
                self.assertFalse(result['unknown_usage'])
                self.assertEqual(len(result['context_checkpoint_receipts']), int(mode == 'once-hard-cap'))
                self.assertEqual(result['requests'], 6 if mode == 'once-hard-cap' else 1)
                self.assertEqual(len(payloads), result['requests'])
                self.assertTrue(all(len(canonical(p)) <= 524288 for p in payloads))
                self.assertEqual(result['known_usage']['total_tokens'], result['requests']*15)
                self.assertFalse(list(self.artifacts.rglob('*.pending.json')))

    def test_checkpoint_never_refreshes_unknown_contract_or_partial_write(self):
        for mode in ('unknown', 'contract', 'partial-write', 'length', 'same-conversation-duplicate', 'late'):
            with self.subTest(mode=mode):
                self.artifacts = self.base/('checkpoint-refuse-' + mode)
                self.before, self.after, self.loaded, self.executions = [], [], [], []
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.patch_fault = None
                first = self.read(1); first['choices'][0]['message']['reasoning_content'] = 'r'*150000
                second = completion(2, [call('patch', 'repo_patch', {'operations': [
                    {'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}]})])
                second['choices'][0]['message']['reasoning_content'] = 'r'*150000
                if mode == 'unknown': second['usage'].pop('total_tokens')
                elif mode == 'contract': second['choices'][0]['message']['tool_calls'][0]['function']['name'] = 'unregistered'
                elif mode == 'length': second['choices'][0]['finish_reason'] = 'length'
                elif mode == 'same-conversation-duplicate': second['choices'][0]['message']['tool_calls'][0]['id'] = 'read-1'
                elif mode == 'partial-write':
                    self.enable_real_patch()
                    self.patch_fault = lambda broker, arguments: {'ok': False, 'changed': [], 'files': {},
                        'write_state': 'partial-or-unverified', 'error': 'synthetic partial write'}
                if mode == 'late':
                    now = [100.0]
                    with patch.object(api.time, 'perf_counter', side_effect=lambda: now[0]):
                        result, payloads = self.run_sse([first], on_eof=lambda: now.__setitem__(0, 701.0),
                            actor_options={'profile_id': api.ENGINEERING_CHECKPOINT_SSE_PROFILE})
                else:
                    result, payloads = self.run_sse([first, second], actor_options={'profile_id': api.ENGINEERING_CHECKPOINT_SSE_PROFILE})
                self.assertEqual(len(payloads), 1 if mode == 'late' else 2)
                self.assertNotEqual(result['status'], 'completed')
                self.assertEqual(result['context_checkpoint_receipts'], [])
                self.assertFalse((self.artifacts/'context-checkpoints').exists())
                self.assertEqual(result['conversation_index'], 0)
                self.assertFalse(result['quality']['hard_pass'])
                self.assertEqual(result['unknown_usage'], mode == 'unknown')

    def fake_https(self, steps, provider="deepseek", transform=None, broken=False, close_failure=False, on_eof=None,
                   response_status=200, response_headers=None, connect_failure_at=None):
        owner = self
        payloads = []
        connections = 0
        class Response:
            status = response_status
            def __init__(self, body):
                self.body, self.offset = body, 0
                self.length = len(body) + int(broken)
            def getheaders(self):
                return response_headers if response_headers is not None else [('content-type', 'text/event-stream; charset=utf-8')]
            def read1(self, maximum):
                if self.offset == len(self.body):
                    if on_eof:
                        on_eof()
                    if broken:
                        raise http.client.IncompleteRead(b'', 1)
                    return b''
                end = min(len(self.body), self.offset + maximum)
                value = self.body[self.offset:end]
                self.offset = end; self.length -= len(value)
                return value
        class Connection:
            sock = None
            def __init__(self, host, timeout):
                self.timeout = timeout
            def connect(self):
                nonlocal connections
                connections += 1
                if connections == connect_failure_at:
                    raise TimeoutError('synthetic confirmed pre-dispatch timeout')
            def request(self, method, path, body, headers):
                payload = json.loads(body)
                payloads.append(copy.deepcopy(payload))
                owner.assertEqual(headers['Accept'], 'text/event-stream')
                step = steps[len(payloads)-1]
                native = step(payload) if callable(step) else copy.deepcopy(step)
                native['model'] = payload['model']
                self.body = wire(native, provider)
                if transform:
                    self.body = transform(self.body)
            def getresponse(self):
                return Response(self.body)
            def close(self):
                if close_failure:
                    raise OSError('synthetic close failure')
        return patch.object(api.http.client, 'HTTPSConnection', Connection), payloads

    def run_sse(self, steps, provider="deepseek", actor_options=None, model=None, **kwargs):
        control, payloads = self.fake_https(steps, provider, **kwargs)
        options = dict(profile_id=api.ENGINEERING_REASONING_SSE_PROFILE, thinking='enabled',
                       settlement_policy=api.SETTLEMENT_POLICY, timeout_seconds=600, max_requests=24)
        options.update(actor_options or {})
        with control:
            result = self.new_actor(provider=provider, model=model or ('deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro'),
                                    **options)
        return result, payloads

    def test_actual_owned_transport_both_providers_raw_projection_history_and_budget(self):
        for provider in ('deepseek', 'mimo'):
            with self.subTest(provider=provider):
                self.artifacts = self.base/('sse-' + provider)
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.before, self.after, self.loaded = [], [], []
                self.executions = []
                result, payloads = self.run_sse(self.ready()+[self.finish(4)], provider)
                self.assertEqual(result['status'], 'completed')
                self.assertFalse(result['unknown_usage'])
                self.assertTrue(result['quality']['hard_pass'])
                self.assertEqual(len(payloads), 4)
                for payload in payloads:
                    self.assertTrue(payload['stream'])
                    self.assertEqual(payload.get('stream_options'), {'include_usage': True} if provider == 'deepseek' else None)
                    for message in payload['messages']:
                        if message['role'] == 'assistant':
                            self.assertEqual(message['reasoning_content'], 'mock non-private test field')
                for meta in [result, *self.before, *self.after]:
                    self.assertEqual(meta['transport_profile_id'], sse.TRANSPORT_PROFILE)
                    self.assertEqual(meta['max_input_bytes'], 524288)
                for i in range(1, 5):
                    raw = (self.artifacts/('requests/%02d.transport-sse.bin' % i)).read_bytes()
                    record = json.loads((self.artifacts/('requests/%02d.response.json' % i)).read_bytes())
                    capture = json.loads((self.artifacts/('requests/%02d.transport-sse-body.json' % i)).read_bytes())['capture']
                    self.assertEqual(record['body_sha256'], sha(raw))
                    self.assertEqual(capture['raw_body_sha256'], sha(raw))
                    self.assertEqual(record['response'], sse.project(raw, body_complete=True)['response'])
                    self.assertNotIn('body_utf8', capture)
                    self.assertFalse((self.artifacts/('requests/%02d.pending.json' % i)).exists())

    def test_valid_terminal_bad_argument_json_keeps_known_usage_and_once_policy(self):
        bad = completion(1, [call('bad', 'repo_read', {})])
        bad['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = '{bad'
        result, payloads = self.run_sse([bad, completion(2, [call('bad-2', 'unregistered', {})])])
        self.assertFalse(self.after[0]['unknown'])
        self.assertIsNotNone(self.after[0]['usage'])
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertEqual(result['schema_rejections'], 1)
        self.assertEqual(len(payloads), 2)

    def test_semantic_message_invalid_preserves_billing_without_tool(self):
        native = completion(1, content=7)
        result, payloads = self.run_sse([native])
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertFalse(result['unknown_usage'])
        self.assertIsNotNone(self.after[0]['usage'])
        self.assertFalse(self.after[0]['unknown'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)

    def test_extra_tool_fragment_keys_cannot_be_hidden_by_projection(self):
        for level in ('call', 'function'):
            self.artifacts = self.base/('extra-key-' + level)
            self.before, self.after, self.loaded = [], [], []
            def poison(body):
                blocks = body.split(b'\r\n\r\n')
                for index, block in enumerate(blocks):
                    if block.startswith(b'data: {'):
                        value = json.loads(block[6:])
                        tools = value['choices'][0]['delta'].get('tool_calls') if value['choices'] else None
                        if tools:
                            target = tools[0] if level == 'call' else tools[0]['function']
                            target['unexpected'] = 1
                            blocks[index] = b'data: ' + canonical(value)
                            break
                return b'\r\n\r\n'.join(blocks)
            result, payloads = self.run_sse([self.read(1)], transform=poison)
            self.assertEqual(result['status'], 'tool-contract-failed')
            self.assertFalse(result['unknown_usage'])
            self.assertIsNotNone(self.after[0]['usage'])
            self.assertEqual(result['tool_events'], [])
            self.assertEqual(len(payloads), 1)

    def test_split_synthetic_credential_is_rejected_before_raw_persistence(self):
        def split(body):
            blocks, seen = body.split(b'\r\n\r\n'), 0
            cut = len(SECRET)//2
            for index, block in enumerate(blocks):
                if block.startswith(b'data: {') and seen < 2:
                    value = json.loads(block[6:])
                    value['choices'][0]['delta']['reasoning_content'] = SECRET[:cut] if seen == 0 else SECRET[cut:]
                    blocks[index] = b'data: ' + canonical(value)
                    seen += 1
            raw = b'\r\n\r\n'.join(blocks)
            self.assertNotIn(SECRET.encode(), raw)
            return raw
        result, payloads = self.run_sse([self.read(1)], transform=split)
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)
        self.assertFalse((self.artifacts/'requests/01.transport-sse.bin').exists())
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        for path in self.artifacts.rglob('*'):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_interruption_retains_prefix_usage_pending_and_no_retry(self):
        result, payloads = self.run_sse([self.read(1)], broken=True)
        self.assertEqual(result['status'], 'unknown-call-blocked')
        self.assertTrue(result['unknown_usage'])
        self.assertIsNotNone(result['known_usage']['input_tokens'])
        self.assertFalse(self.after[0]['settlement']['body_complete'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)
        self.assertTrue(self.after[0]['settlement']['worker_done'])
        self.assertFalse(self.after[0]['settlement']['worker_alive_at_return'])

    def test_settled_length_is_unfinished_without_executing_truncated_tools_or_terminal(self):
        for provider in ('deepseek', 'mimo'):
            for kind in ('empty', 'partial-tool', 'complete-tool', 'partial-finish', 'complete-finish'):
                with self.subTest(provider=provider, kind=kind):
                    self.artifacts = self.base/('length-'+provider+'-'+kind)
                    self.before, self.after, self.loaded = [], [], []
                    native = (completion(1) if kind == 'empty' else self.finish(1)
                              if kind.endswith('finish') else self.read(1))
                    native['choices'][0]['finish_reason'] = 'length'
                    if kind.startswith('partial'):
                        native['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = '{"incomplete":'
                    result, payloads = self.run_sse([native], provider)
                    self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
                    self.assertEqual(result['status'], 'output-limit-unfinished')
                    self.assertEqual(result['refusal_reason'], 'provider-finish-reason-length')
                    self.assertFalse(result['unknown_usage'])
                    self.assertEqual(result['usage']['total_tokens'], 15)
                    self.assertEqual(self.after[0]['usage']['total_tokens'], 15)
                    self.assertIsNone(self.after[0]['error_type'])
                    self.assertTrue(self.after[0]['settlement']['worker_done'])
                    self.assertFalse(self.after[0]['settlement']['worker_alive_at_return'])
                    self.assertFalse(result['quality']['hard_pass'])
                    self.assertEqual(result['tool_events'], [])
                    self.assertIsNone(result['final_report'])
                    self.assertFalse((self.artifacts/'requests/01.pending.json').exists())
                    self.assertFalse((self.artifacts/'actor.pending.json').exists())
                    rejected = ('api-finish-rejected:required-native-terminal-call' if kind == 'empty'
                                else 'api-tool-rejected:finish-reason')
                    self.assertIn(rejected, result['quality']['failures'])

    def test_length_diagnosis_does_not_override_unknown_or_late_settlement(self):
        for mode in ('unknown', 'late'):
            with self.subTest(mode=mode):
                self.artifacts = self.base/('length-fence-'+mode)
                self.before, self.after, self.loaded = [], [], []
                native = completion(1)
                native['choices'][0]['finish_reason'] = 'length'
                now = [100.0]
                with patch.object(api.time, 'perf_counter', side_effect=lambda: now[0]):
                    result, payloads = self.run_sse([native], broken=mode == 'unknown',
                        on_eof=(lambda: now.__setitem__(0, 701.0)) if mode == 'late' else None,
                        actor_options={'reasoning_continuation_policy': api.REASONING_CONTINUATION_POLICY})
                self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
                self.assertEqual(result['status'], 'unknown-call-blocked' if mode == 'unknown'
                                 else 'work-deadline-settled-unfinished')
                self.assertIsNone(result['refusal_reason'])
                self.assertEqual(result['unknown_usage'], mode == 'unknown')
                self.assertEqual(result['known_usage']['total_tokens'], 15)
                self.assertEqual(result['reasoning_continuations'], 0)
                self.assertEqual(result['tool_events'], [])
                self.assertIsNone(result['final_report'])
                self.assertEqual((self.artifacts/'requests/01.pending.json').exists(), mode == 'unknown')

    def test_complete_http_json_rejection_preserves_reason_and_unknown_accounting(self):
        rejection = {'error': {'code': '402', 'type': 'insufficient_balance',
                               'message': 'Insufficient account balance'}}
        for provider in ('deepseek', 'mimo'):
            with self.subTest(provider=provider):
                self.artifacts = self.base/('http-rejection-' + provider)
                self.before, self.after, self.loaded = [], [], []
                result, payloads = self.run_sse([self.read(1)], provider,
                    model='deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro-ultraspeed',
                    actor_options={'profile_id': api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE},
                    response_status=402, response_headers=[('Content-Type', 'application/json')],
                    transform=lambda unused: canonical(rejection))
                response = json.loads((self.artifacts/'requests/01.response.json').read_bytes())
                receipt = json.loads((self.artifacts/'requests/01.receipt.json').read_bytes())
                expected = dict(rejection['error'], phase='provider-rejection', http_status=402)
                self.assertEqual(response['provider_rejection'], expected)
                self.assertEqual(receipt['provider_rejection'], expected)
                self.assertEqual(self.after[0]['provider_rejection'], expected)
                self.assertEqual(receipt['transport']['phase'], 'provider-rejection')
                self.assertEqual(receipt['error_type'], 'ProviderRejected')
                self.assertEqual(receipt['transport']['http_dispatch'], 'response_received')
                self.assertTrue(receipt['settlement']['body_complete'])
                self.assertIsNone(receipt['settlement']['transport_failure'])
                self.assertIsNone(receipt['usage'])
                self.assertIsNone(result['usage'])
                self.assertTrue(all(value is None for value in result['known_usage'].values()))
                self.assertTrue(result['unknown_usage'])
                self.assertEqual(result['status'], 'unknown-call-blocked')
                self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
                self.assertEqual(result['tool_events'], [])
                self.assertIsNone(result['final_report'])
                self.assertTrue((self.artifacts/'actor.pending.json').exists())
                self.assertTrue((self.artifacts/'requests/01.pending.json').exists())

    def test_partial_or_unrecognized_http_error_never_becomes_zero_usage(self):
        body = canonical({'error': {'code': '402', 'type': 'insufficient_balance', 'message': 'balance'}})
        for name, raw, status, media, broken in (
                ('interrupted', body, 402, 'application/json', True),
                ('truncated-json', body[:-1], 402, 'application/json', False),
                ('unknown-media', body, 402, 'text/plain', False),
                ('not-http-rejection', body, 200, 'application/json', False)):
            with self.subTest(name=name):
                self.artifacts = self.base/('unknown-http-' + name)
                self.before, self.after, self.loaded = [], [], []
                result, payloads = self.run_sse([self.read(1)], response_status=status,
                    response_headers=[('content-type', media)], broken=broken,
                    transform=lambda unused, raw=raw: raw)
                receipt = json.loads((self.artifacts/'requests/01.receipt.json').read_bytes())
                self.assertNotIn('provider_rejection', receipt)
                self.assertIsNone(receipt['usage'])
                self.assertIsNone(result['usage'])
                self.assertTrue(all(value is None for value in result['known_usage'].values()))
                self.assertTrue(result['unknown_usage'])
                self.assertEqual(result['status'], 'unknown-call-blocked')
                self.assertEqual(len(payloads), 1)
                self.assertEqual(result['tool_events'], [])
                self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
                if broken:
                    self.assertFalse(receipt['settlement']['body_complete'])
                    self.assertEqual(receipt['settlement']['transport_failure']['exception_class'], 'IncompleteRead')

    def test_http_rejection_diagnostic_redacts_before_utf8_cap_and_whitelists_fields(self):
        # The credential begins just before the cap: truncating first would leak its prefix.
        message = 'x'*1018 + SECRET + '\nBearer synthetic-authorization-token ' + '中'*600
        body = canonical({'error': {'code': '402', 'type': 'insufficient_balance', 'message': message,
                                    'request': {'authorization': SECRET}}})
        diagnostic = api._provider_rejection(402, [('Content-Type', 'application/json; charset="UTF-8"')],
            body, complete=True, secret=SECRET)
        self.assertEqual(set(diagnostic), {'phase', 'http_status', 'code', 'type', 'message'})
        self.assertLessEqual(len(diagnostic['message'].encode('utf-8')), 1024)
        self.assertNotIn(SECRET, canonical(diagnostic).decode())
        self.assertNotIn(SECRET[:6], diagnostic['message'])
        full = api._provider_rejection(402, [('Content-Type', 'application/json')],
            canonical({'error': {'message': '\nBearer synthetic-authorization-token ' + SECRET + '中'*600}}),
            complete=True, secret=SECRET)
        self.assertNotIn('synthetic-authorization-token', full['message'])
        self.assertNotIn('\n', full['message'])
        self.assertNotIn(SECRET, full['message'])
        full['message'].encode('utf-8')

    def test_http_rejection_diagnostic_rejects_malformed_or_unconfirmed_json(self):
        headers = [('Content-Type', 'application/json')]
        for body in (b'{"error":{"code":"402","code":"other"}}', b'{"error":{"message":"\xff"}}',
                     b'{"error":{"message":"x"}}' + b' '*16384,
                     b'{"error":{"message":NaN}}', b'{"error":{"message":{"nested":"value"}}}'):
            with self.subTest(body=body[:60]):
                self.assertIsNone(api._provider_rejection(402, headers, body, complete=True))
        good = canonical({'error': {'code': '402', 'message': 'balance'}})
        self.assertIsNone(api._provider_rejection(402, headers, good, complete=False))
        self.assertIsNone(api._provider_rejection(402, headers + [('Content-Encoding', 'gzip')], good, complete=True))
        self.assertIsNone(api._provider_rejection(402, [('Content-Type', 'application/json; charset=latin1')], good, complete=True))

    def test_missing_done_and_close_failure_are_unknown_with_observed_usage(self):
        for mode in ('done', 'close'):
            self.artifacts = self.base/('unknown-' + mode)
            self.before, self.after = [], []
            result, payloads = self.run_sse([self.read(1)], transform=(lambda body: body[:-len(event(b'[DONE]'))]) if mode == 'done' else None,
                                          close_failure=mode == 'close')
            self.assertTrue(result['unknown_usage'])
            self.assertIsNotNone(result['known_usage']['input_tokens'])
            self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
            self.assertEqual(len(payloads), 1)

    def test_v3_requires_managed_settlement_and_rejects_retry_before_reserve_key(self):
        for opts in ({}, {'settlement_policy': api.SETTLEMENT_POLICY, 'connect_retry_policy': api.CONNECT_RETRY_POLICY}):
            with self.assertRaises(ValueError):
                self.new_actor(profile_id=api.ENGINEERING_REASONING_SSE_PROFILE, thinking='enabled', **opts)
        self.assertEqual(self.before, [])
        self.assertEqual(self.loaded, [])

    def test_v3_config_only_adds_explicit_transport_to_v2(self):
        v2 = api.profile_configuration(api.ENGINEERING_REASONING_INPUT_PROFILE)
        self.assertEqual(sha(canonical(v2)), 'd56ad83d4e7339c59c9f2f782f91241e538af1eddb158fc3f1d5373b53fd5ce3')
        v3 = api.profile_configuration(api.ENGINEERING_REASONING_SSE_PROFILE)
        transport = v3.pop('transport')
        v3['profile_id'] = api.ENGINEERING_REASONING_INPUT_PROFILE
        self.assertEqual(v3, v2)
        self.assertEqual(transport['max_raw_body_bytes'], 8388608)
        self.assertEqual(api.MAX_INPUT_BYTES, 131072)

    def test_ultraspeed_strict_configuration_preserves_old_identity_and_bounds(self):
        self.assertEqual(sha(canonical(api.profile_configuration(api.ENGINEERING_HYBRID_SSE_PROFILE))),
                         '46637727f794a961b18190bcd008f2e7149f323d50d2c9d4dfed2aa9afebef36')
        prior = api.profile_configuration(api.ENGINEERING_REASONING_SSE_PROFILE)
        configuration = api.profile_configuration(api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE)
        self.assertEqual(configuration['profile_id'], 'thinking-enabled-engineering-ultraspeed-strict-16384-sse-v1')
        expected = copy.deepcopy(prior['providers'])
        expected['deepseek']['strict_tools'] = False
        expected['mimo'].update(model='mimo-v2.6-pro-ultraspeed', strict_tools=True)
        self.assertEqual(configuration['providers'], expected)
        self.assertIs(configuration['providers']['deepseek']['strict_tools'], False)
        self.assertIs(configuration['providers']['mimo']['strict_tools'], True)
        self.assertEqual(configuration['prices'], dict(prior['prices'],
            mimo={'USD': {'input_hit': '.036', 'input_miss': '4.35', 'output': '8.7'}}))
        self.assertEqual(configuration['price_evidence']['mimo'],
                         'https://mimo.mi.com/models/en-US/mimo-v2.6-pro-ultraspeed')
        self.assertEqual(configuration['price_evidence']['mimo_price_reviewed_on'], '2026-10-18')
        self.assertNotIn('mimo_pro', configuration['price_evidence'])
        self.assertEqual(configuration['transport'], prior['transport'])
        self.assertEqual(configuration['admission_limits'], {'max_requests': 24, 'timeout_seconds': 600,
            'max_tools': 32, 'max_input_bytes': 524288})
        self.assertEqual(configuration['price_evidence']['deepseek'], prior['price_evidence']['deepseek'])
        original = copy.deepcopy(configuration)
        configuration['providers']['mimo']['strict_tools'] = False
        configuration['prices']['mimo']['USD']['output'] = '0'
        configuration['transport']['providers']['mimo']['stream'] = False
        self.assertEqual(api.profile_configuration(api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE), original)

    def test_ultraspeed_capacity_preserves_prior_identities_and_fixed_bounds(self):
        legacy = {
            api.THINKING_PROFILE: '4f4307e6e479eeb852a4d1a7bb358a7e64917467cae0fa11fe4063db1d47d1df',
            api.FLASH_THINKING_PROFILE: 'f5ae975f21072974c9da04da33e8081a2e2fc44be6769c2cbe8c36e82d58081b',
            api.FLASH_DISABLED_PROFILE: 'a11dd520a6f62837f3bfab36468653c418d0caf80c7f0d658b5231429633919e',
            api.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE: 'db21a61c86bb3398f9b9568cdb290482407115dfc1ac0be3c21b8fb62ac8ced6',
            api.ENGINEERING_REASONING_PROFILE: '03de3880a6d3e6114a5321687722e987c39419db55cc7855e2d4e833d009d5df',
            api.ENGINEERING_REASONING_INPUT_PROFILE: 'd56ad83d4e7339c59c9f2f782f91241e538af1eddb158fc3f1d5373b53fd5ce3',
            api.ENGINEERING_REASONING_SSE_PROFILE: '2ab5077064140b8a909534f6da85af18b985c6c01e64ec5c7596e4e9cd95b63b',
            api.ENGINEERING_HYBRID_SSE_PROFILE: '46637727f794a961b18190bcd008f2e7149f323d50d2c9d4dfed2aa9afebef36',
            api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE: '1cb672988abb0ac11a5af1b54f319b261c90774de8435acc61cd67dfbc5d7f79'}
        expected = api.profile_configuration(api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE)
        expected['profile_id'] = 'thinking-enabled-engineering-ultraspeed-strict-dslow32768-mimo65536-sse-v1'
        expected['providers']['deepseek'].update(output_cap=32768, reasoning_effort='low')
        expected['providers']['mimo']['output_cap'] = 65536
        configuration = api.profile_configuration(api.ENGINEERING_ULTRASPEED_CAPACITY_SSE_PROFILE)
        self.assertEqual(configuration, expected)
        self.assertEqual(configuration['admission_limits'], {'max_requests': 24, 'timeout_seconds': 600,
            'max_tools': 32, 'max_input_bytes': 524288})
        configuration['providers']['deepseek']['reasoning_effort'] = 'max'
        configuration['providers']['mimo']['output_cap'] = 131072
        self.assertEqual(api.profile_configuration(api.ENGINEERING_ULTRASPEED_CAPACITY_SSE_PROFILE), expected)
        self.assertEqual({p: sha(canonical(api.profile_configuration(p))) for p in legacy}, legacy)

    def test_ultraspeed_capacity_owned_wire_and_receipts_bind_each_provider(self):
        self.enable_real_patch()
        profile = api.ENGINEERING_ULTRASPEED_CAPACITY_SSE_PROFILE
        configuration = api.profile_configuration(profile)
        parameters = {item['name']: item['inputSchema']
                      for item in engineering_fixture.real_engineering.tool_definitions()}
        parameters[api.FINISH_TOOL] = api.FINAL_SCHEMA
        for provider, cap, effort in (('deepseek', 32768, 'low'), ('mimo', 65536, None)):
            with self.subTest(provider=provider):
                self.artifacts = self.base/('capacity-wire-' + provider)
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.before, self.after, self.loaded, self.executions = [], [], [], []
                result, payloads = self.run_sse(self.ready()+[self.finish(4)], provider,
                    model=configuration['providers'][provider]['model'], actor_options={'profile_id': profile})
                self.assertEqual((result['status'], result['requests'], result['tool_attempts']), ('completed', 4, 5))
                self.assertTrue(result['quality']['hard_pass'])
                for payload in payloads:
                    self.assertEqual(payload['thinking'], {'type': 'enabled'})
                    self.assertEqual(payload['max_tokens' if provider == 'deepseek' else 'max_completion_tokens'], cap)
                    self.assertNotIn('max_completion_tokens' if provider == 'deepseek' else 'max_tokens', payload)
                    self.assertNotIn('strict', payload)
                    self.assertEqual(payload.get('reasoning_effort'), effort)
                    if provider == 'mimo':
                        self.assertNotIn('reasoning_effort', payload)
                    self.assertEqual({tool['function']['name']: tool['function']['parameters']
                                      for tool in payload['tools']}, parameters)
                    self.assertEqual(len(payload['tools']), 6)
                    for tool in payload['tools']:
                        if provider == 'mimo':
                            self.assertIs(tool['function']['strict'], True)
                        else:
                            self.assertNotIn('strict', tool['function'])
                for metadata in (result, *self.before, *self.after):
                    self.assertEqual((metadata['profile_id'], metadata['output_cap'], metadata['reasoning_effort_requested']),
                                     (profile, cap, effort))
                    self.assertEqual(metadata['profile_configuration_sha256'], sha(canonical(configuration)))
                    self.assertEqual(metadata['max_input_bytes'], 524288)
                    self.assertIsNone(metadata['connect_retry_policy'])
                self.assertEqual((result['max_requests'], result['max_tools'], result['timeout_seconds'],
                                  result['settlement_max_seconds']), (24, 32, 600, 600))

    def test_ultraspeed_capacity_does_not_relax_admission_or_provider_overrun(self):
        profile = api.ENGINEERING_ULTRASPEED_CAPACITY_SSE_PROFILE
        for provider, model, cap in (('deepseek', 'deepseek-v4-pro', 32768),
                                     ('mimo', 'mimo-v2.6-pro-ultraspeed', 65536)):
            for change in ({'max_requests': 25}, {'timeout_seconds': 601}, {'thinking': 'disabled'},
                           {'settlement_policy': None}, {'connect_retry_policy': api.CONNECT_RETRY_POLICY}):
                options = dict(provider=provider, model=model, thinking='enabled', profile_id=profile,
                    settlement_policy=api.SETTLEMENT_POLICY, max_requests=24, timeout_seconds=600)
                options.update(change)
                with self.subTest(provider=provider, change=change), self.assertRaises(ValueError):
                    self.new_actor(**options)
            self.assertEqual((self.before, self.after, self.loaded), ([], [], []))
            self.artifacts = self.base/('capacity-input-' + provider)
            result, payloads = self.run_sse([], provider, model=model,
                actor_options={'profile_id': profile, 'system_context': 'x'*524288})
            self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
            self.assertEqual((self.before, self.after, self.loaded, payloads), ([], [], [], []))
            for reported in (cap, cap+1):
                self.artifacts = self.base/('capacity-overrun-' + provider + '-' + str(reported))
                native = self.read(1)
                native['usage'].update(completion_tokens=reported, total_tokens=reported+10)
                result, payloads = self.run_sse([native], provider, model=model,
                    actor_options={'profile_id': profile, 'max_requests': 1})
                self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
                self.assertFalse(result['unknown_usage'])
                self.assertFalse(result['quality']['hard_pass'])
                if reported == cap:
                    self.assertEqual(result['status'], 'request-budget-exhausted')
                    self.assertEqual(len(result['tool_events']), 1)
                else:
                    self.assertEqual(result['status'], 'unexpected-overrun-blocked')
                    self.assertIn('unexpected-provider-usage-overrun', result['quality']['failures'])
                    self.assertEqual(result['tool_events'], [])
                self.before, self.after, self.loaded = [], [], []

    def test_ultraspeed_strict_owned_wire_changes_only_mimo_model_and_function_flag(self):
        self.enable_real_patch()  # Original engineering schemas and patches; execution remains the fixture stub.
        reasoning = 'opaque synthetic enabled reasoning\n' + '\u4e2d\u6587/\\"\n' * 1000 + 'tail'
        configuration = api.profile_configuration(api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE)
        parameters = {item['name']: item['inputSchema']
                      for item in engineering_fixture.real_engineering.tool_definitions()}
        parameters[api.FINISH_TOOL] = api.FINAL_SCHEMA
        operation = parameters['repo_patch']['properties']['operations']['items']
        self.assertNotIn('old_text', operation['required'])
        self.assertEqual(operation['properties']['old_text']['type'], 'string')
        for provider in ('deepseek', 'mimo'):
            observed = []
            prior_model = 'deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro'
            for label, profile, model in (
                    ('prior', api.ENGINEERING_REASONING_SSE_PROFILE, prior_model),
                    ('strict', api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE,
                     configuration['providers'][provider]['model'])):
                with self.subTest(provider=provider, profile=profile):
                    self.artifacts = self.base/('ultraspeed-wire-' + provider + '-' + label)
                    (self.workspace/'target.txt').write_bytes(b'old\n')
                    self.before, self.after, self.loaded, self.executions = [], [], [], []
                    def opaque(step):
                        def reply(payload):
                            native = step(payload) if callable(step) else copy.deepcopy(step)
                            native['choices'][0]['message']['reasoning_content'] = reasoning
                            return native
                        return reply
                    result, payloads = self.run_sse([opaque(step) for step in self.ready()+[self.finish(4)]],
                        provider, model=model, actor_options={'profile_id': profile, 'thinking': 'enabled'})
                    self.assertEqual((result['status'], result['requests'], result['tool_attempts'], len(self.executions)),
                                     ('completed', 4, 5, 1))
                    self.assertTrue(result['quality']['hard_pass'])
                    self.assertEqual(result['known_usage']['total_tokens'], 60)
                    self.assertEqual((len(self.before), len(self.after), self.loaded), (4, 4, [provider]))
                    for index, payload in enumerate(payloads, 1):
                        self.assertNotIn('strict', payload)
                        self.assertEqual(payload['thinking'], {'type': 'enabled'})
                        self.assertEqual(payload.get('reasoning_effort'), 'high' if provider == 'deepseek' else None)
                        if provider == 'mimo':
                            self.assertNotIn('reasoning_effort', payload)
                        self.assertEqual({tool['function']['name']: tool['function']['parameters']
                                          for tool in payload['tools']}, parameters)
                        self.assertEqual(len(payload['tools']), 6)
                        for tool in payload['tools']:
                            if label == 'strict' and provider == 'mimo':
                                self.assertIs(tool['function']['strict'], True)
                            else:
                                self.assertNotIn('strict', tool['function'])
                        self.assertEqual([m['reasoning_content'] for m in payload['messages'] if m['role'] == 'assistant'],
                                         [reasoning]*(index-1))
                        self.assertEqual(self.before[index-1]['request_payload_sha256'], sha(canonical(payload)))
                        record = json.loads((self.artifacts/('requests/%02d.response.json' % index)).read_bytes())
                        self.assertEqual(record['response']['choices'][0]['message']['reasoning_content'], reasoning)
                        self.assertFalse((self.artifacts/('requests/%02d.pending.json' % index)).exists())
                    for metadata in [result, *self.before, *self.after]:
                        self.assertEqual(metadata['model_requested'], model)
                        self.assertEqual(metadata['profile_configuration_sha256'], sha(canonical(api.profile_configuration(profile))))
                        self.assertEqual(metadata['thinking'], 'enabled')
                        self.assertEqual(metadata['max_input_bytes'], 524288)
                        self.assertEqual(metadata['transport_profile_id'], sse.TRANSPORT_PROFILE)
                        self.assertIsNone(metadata['connect_retry_policy'])
                    self.assertEqual((result['max_requests'], result['max_tools'], result['output_cap'],
                        result['timeout_seconds'], result['settlement_max_seconds']), (24, 32, 16384, 600, 600))
                    observed.append(copy.deepcopy(payloads))
            restored = observed[1]
            for payload in restored:
                payload['model'] = prior_model
                for tool in payload['tools']:
                    tool['function'].pop('strict', None)
            self.assertEqual(canonical(restored), canonical(observed[0]))

    def test_ultraspeed_strict_mismatches_refuse_before_reservation_or_credentials(self):
        for provider, model in (('deepseek', 'deepseek-v4-pro'), ('mimo', 'mimo-v2.6-pro-ultraspeed')):
            for change in ({'model': 'mimo-v2.6-pro'}, {'model': 'mimo-v2.6-flash'}, {'thinking': 'disabled'},
                           {'response_json_mode': True}, {'max_requests': 25}, {'timeout_seconds': 601},
                           {'settlement_policy': None}, {'connect_retry_policy': api.CONNECT_RETRY_POLICY},
                           {'broker_profile_id': None}, {'execution_backend': 'docker-cpython-finite-v1'}):
                options = dict(provider=provider, model=model, thinking='enabled',
                    profile_id=api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE,
                    settlement_policy=api.SETTLEMENT_POLICY, max_requests=24, timeout_seconds=600)
                options.update(change)
                with self.subTest(provider=provider, change=change), self.assertRaises(ValueError):
                    self.new_actor(**options)
        self.assertEqual((self.before, self.after, self.loaded), ([], [], []))
        self.module.create_broker.assert_not_called()

    def test_ultraspeed_strict_does_not_normalize_missing_path_or_optional_old_text(self):
        self.enable_real_patch()
        for label, invalid, missing, optional in (
                ('path', {'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}, ['/operations/0/path'], {}),
                ('null-fragment', {'path': 'target.txt', 'old_sha256': sha(b'old\n'),
                                   'new_text': 'fixed\n', 'old_text': None}, [], {'old_text': 'old\n'})):
            with self.subTest(case=label):
                self.artifacts = self.base/('ultraspeed-schema-' + label)
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.before, self.after, self.loaded, self.executions = [], [], [], []
                rejected = completion(2, [call('bad-patch', 'repo_patch', {'operations': [invalid]}),
                    call('not-admitted-validation', 'repo_validate', {})])
                def corrected(payload):
                    feedback = [json.loads(message['content']) for message in payload['messages'][-2:]]
                    self.assertEqual(feedback[0]['missing_required'], missing)
                    self.assertEqual(feedback[0]['inputSchema'],
                        next(item['inputSchema'] for item in engineering_fixture.real_engineering.tool_definitions()
                             if item['name'] == 'repo_patch'))
                    self.assertTrue(all(item['batch_executed'] is False for item in feedback))
                    self.assertEqual(feedback[0]['remaining_schema_corrections'], 0)
                    self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')
                    self.assertEqual(self.executions, [])
                    return self.project_patch(3, [dict(path='target.txt', old_sha256=sha(b'old\n'),
                        new_text='fixed\n', **optional)])
                result, payloads = self.run_sse([self.read(1), rejected, corrected,
                    self.validate_and_status(4), self.finish(5)], 'mimo', model='mimo-v2.6-pro-ultraspeed',
                    actor_options={'profile_id': api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE})
                self.assertEqual((len(payloads), result['schema_rejections']), (5, 1))
                self.assertTrue(result['quality']['hard_pass'])
                self.assertEqual([entry['tool'] for entry in result['tool_events']],
                                 ['repo_read', 'repo_patch', 'repo_validate', 'repo_status'])

    def test_ultraspeed_strict_retains_original_input_and_slot_admission(self):
        options = {'profile_id': api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE,
                   'system_context': 'x'*140000, 'max_requests': 1}
        result, payloads = self.run_sse([self.read(1)], 'mimo', model='mimo-v2.6-pro-ultraspeed', actor_options=options)
        self.assertEqual((result['requests'], len(self.after), len(result['tool_events'])), (1, 1, 1))
        self.assertGreater(len(canonical(payloads[0])), 131072)
        self.assertLess(len(canonical(payloads[0])), 524288)
        self.artifacts = self.base/'ultraspeed-over-input'
        self.before, self.after, self.loaded = [], [], []
        options['system_context'] = 'x'*524288
        result, payloads = self.run_sse([], 'mimo', model='mimo-v2.6-pro-ultraspeed', actor_options=options)
        self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
        self.assertEqual((self.before, self.after, self.loaded, payloads), ([], [], [], []))

    def test_ultraspeed_strict_unknown_and_late_finish_only_account_without_action(self):
        options = {'profile_id': api.ENGINEERING_ULTRASPEED_STRICT_SSE_PROFILE}
        result, payloads = self.run_sse([self.read(1)], 'mimo', model='mimo-v2.6-pro-ultraspeed',
            broken=True, actor_options=options)
        self.assertEqual(result['status'], 'unknown-call-blocked')
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'], 15)
        self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
        self.assertEqual(result['tool_events'], [])
        self.assertTrue((self.artifacts/'actor.pending.json').exists())
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.artifacts = self.base/'ultraspeed-late'
        self.before, self.after, self.loaded = [], [], []
        now = [100.0]
        with patch.object(api.time, 'perf_counter', side_effect=lambda: now[0]):
            result, payloads = self.run_sse([self.finish(1)], 'mimo', model='mimo-v2.6-pro-ultraspeed',
                on_eof=lambda: now.__setitem__(0, 701.0), actor_options=options)
        self.assertEqual(result['status'], 'work-deadline-settled-unfinished')
        self.assertFalse(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'], 15)
        self.assertEqual((len(payloads), len(self.after)), (1, 1))
        self.assertTrue(self.after[0]['settlement']['accounting_only'])
        self.assertFalse(result['quality']['hard_pass'])
        self.assertIsNone(result['final_report'])
        self.assertEqual(result['tool_events'], [])

    def test_hybrid_config_changes_only_identity_and_mimo_mode_preserving_legacy_bytes(self):
        legacy = {
            api.THINKING_PROFILE: '4f4307e6e479eeb852a4d1a7bb358a7e64917467cae0fa11fe4063db1d47d1df',
            api.FLASH_THINKING_PROFILE: 'f5ae975f21072974c9da04da33e8081a2e2fc44be6769c2cbe8c36e82d58081b',
            api.FLASH_DISABLED_PROFILE: 'a11dd520a6f62837f3bfab36468653c418d0caf80c7f0d658b5231429633919e',
            api.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE: 'db21a61c86bb3398f9b9568cdb290482407115dfc1ac0be3c21b8fb62ac8ced6',
            api.ENGINEERING_REASONING_PROFILE: '03de3880a6d3e6114a5321687722e987c39419db55cc7855e2d4e833d009d5df',
            api.ENGINEERING_REASONING_INPUT_PROFILE: 'd56ad83d4e7339c59c9f2f782f91241e538af1eddb158fc3f1d5373b53fd5ce3',
            api.ENGINEERING_REASONING_SSE_PROFILE: '2ab5077064140b8a909534f6da85af18b985c6c01e64ec5c7596e4e9cd95b63b',
        }
        self.assertEqual(api.ENGINEERING_REASONING_PROFILES, (api.ENGINEERING_REASONING_PROFILE,
            api.ENGINEERING_REASONING_INPUT_PROFILE, api.ENGINEERING_REASONING_SSE_PROFILE))
        expected = api.profile_configuration(api.ENGINEERING_REASONING_SSE_PROFILE)
        expected['profile_id'] = 'thinking-hybrid-engineering-pro-16384-sse-v1'
        expected['providers']['mimo']['thinking'] = 'disabled'
        hybrid = api.profile_configuration(api.ENGINEERING_HYBRID_SSE_PROFILE)
        self.assertEqual(hybrid, expected)
        self.assertNotIn(sha(canonical(hybrid)), legacy.values())
        hybrid['providers']['deepseek']['reasoning_effort'] = 'low'
        hybrid['providers']['mimo']['thinking'] = 'enabled'
        hybrid['transport']['providers']['mimo']['stream'] = False
        self.assertEqual(api.profile_configuration(api.ENGINEERING_HYBRID_SSE_PROFILE), expected)
        self.assertEqual({p: sha(canonical(api.profile_configuration(p))) for p in legacy}, legacy)

    def test_hybrid_actual_wire_binds_modes_and_preserves_full_returned_history(self):
        # Returned opaque text is never stripped, including a synthetic field
        # returned despite disabled mode. This asserts replay, not server mode.
        reasoning = 'full synthetic opaque field\n' + '\u4e2d\u6587/\\"\n' * 1000 + 'tail'
        identity = sha(canonical(api.profile_configuration(api.ENGINEERING_HYBRID_SSE_PROFILE)))
        for provider, mode in (('deepseek', 'enabled'), ('mimo', 'disabled')):
            with self.subTest(provider=provider):
                self.artifacts = self.base/('hybrid-' + provider)
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.before, self.after, self.loaded, self.executions = [], [], [], []
                def opaque(step):
                    def reply(payload):
                        native = step(payload) if callable(step) else copy.deepcopy(step)
                        native['choices'][0]['message']['reasoning_content'] = reasoning
                        return native
                    return reply
                result, payloads = self.run_sse([opaque(step) for step in self.ready()+[self.finish(4)]],
                    provider, actor_options={'profile_id': api.ENGINEERING_HYBRID_SSE_PROFILE, 'thinking': mode})
                self.assertEqual(result['status'], 'completed')
                self.assertTrue(result['quality']['hard_pass'])
                self.assertFalse(result['unknown_usage'])
                self.assertEqual((result['requests'], result['tool_attempts'], len(self.executions)), (4, 5, 1))
                self.assertEqual(result['known_usage']['total_tokens'], 60)
                self.assertEqual((len(self.before), len(self.after)), (4, 4))
                self.assertEqual(self.loaded, [provider])  # Synthetic fixture loader, cached once per actor.
                for i, payload in enumerate(payloads, 1):
                    self.assertEqual(payload['thinking'], {'type': mode})
                    self.assertEqual(payload['model'], 'deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro')
                    self.assertTrue(payload['stream'])
                    self.assertEqual(payload['max_tokens' if provider == 'deepseek' else 'max_completion_tokens'], 16384)
                    self.assertEqual(payload.get('reasoning_effort'), 'high' if provider == 'deepseek' else None)
                    self.assertEqual(payload.get('stream_options'), {'include_usage': True} if provider == 'deepseek' else None)
                    if provider == 'mimo':
                        self.assertNotIn('reasoning_effort', payload)
                    self.assertEqual(self.before[i-1]['request_payload_sha256'], sha(canonical(payload)))
                    self.assertEqual([m['reasoning_content'] for m in payload['messages'] if m['role'] == 'assistant'],
                                     [reasoning]*(i-1))
                    raw = (self.artifacts/('requests/%02d.transport-sse.bin' % i)).read_bytes()
                    record = json.loads((self.artifacts/('requests/%02d.response.json' % i)).read_bytes())
                    self.assertEqual(record['body_sha256'], sha(raw))
                    self.assertEqual(record['response'], sse.project(raw, body_complete=True)['response'])
                    self.assertEqual(record['response']['choices'][0]['message']['reasoning_content'], reasoning)
                    self.assertFalse((self.artifacts/('requests/%02d.pending.json' % i)).exists())
                for metadata in [result, *self.before, *self.after]:
                    self.assertEqual(metadata['profile_id'], api.ENGINEERING_HYBRID_SSE_PROFILE)
                    self.assertEqual(metadata['profile_configuration_sha256'], identity)
                    self.assertEqual(metadata['thinking'], mode)
                    self.assertEqual(metadata['reasoning_effort_requested'], 'high' if provider == 'deepseek' else None)
                    self.assertEqual(metadata['max_input_bytes'], 524288)
                    self.assertEqual(metadata['transport_profile_id'], sse.TRANSPORT_PROFILE)
                    self.assertIsNone(metadata['connect_retry_policy'])
                self.assertEqual((result['max_requests'], result['max_tools'], result['timeout_seconds'],
                                  result['settlement_max_seconds'], result['schema_correction_limit']), (24, 32, 600, 600, 1))
                self.assertTrue(all(item['settlement']['worker_done'] for item in self.after))

    def test_hybrid_rejects_mismatched_settings_limits_and_retry_before_reserve_or_key(self):
        changes = ({'thinking': 'enabled'}, {'model': 'mimo-v2.6-flash'},
                   {'response_json_mode': True}, {'max_requests': 25}, {'timeout_seconds': 601},
                   {'settlement_policy': None}, {'connect_retry_policy': api.CONNECT_RETRY_POLICY},
                   {'broker_profile_id': None}, {'execution_backend': 'docker-cpython-finite-v1'})
        for change in changes:
            options = dict(provider='mimo', model='mimo-v2.6-pro', thinking='disabled',
                profile_id=api.ENGINEERING_HYBRID_SSE_PROFILE, settlement_policy=api.SETTLEMENT_POLICY,
                max_requests=24, timeout_seconds=600)
            options.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.new_actor(**options)
        self.assertEqual((self.before, self.after, self.loaded), ([], [], []))
        self.module.create_broker.assert_not_called()

    def test_hybrid_retains_large_input_admission_and_original_slot_bound(self):
        options = {'profile_id': api.ENGINEERING_HYBRID_SSE_PROFILE, 'thinking': 'disabled',
                   'system_context': 'x'*140000, 'max_requests': 1}
        result, payloads = self.run_sse([self.read(1)], 'mimo', actor_options=options)
        self.assertEqual(result['requests'], 1)
        self.assertEqual(len(result['tool_events']), 1)
        self.assertEqual(len(self.after), 1)
        self.assertGreater(len(canonical(payloads[0])), 131072)
        self.assertLess(len(canonical(payloads[0])), 524288)
        self.assertFalse(result['quality']['hard_pass'])
        self.artifacts = self.base/'hybrid-over-input'
        self.before, self.after, self.loaded = [], [], []
        options['system_context'] = 'x'*524288
        result, payloads = self.run_sse([], 'mimo', actor_options=options)
        self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
        self.assertEqual((self.before, self.after, self.loaded, payloads), ([], [], [], []))

    def test_hybrid_native_terminal_and_tool_budget_are_unchanged(self):
        cases = (
            ('plain-finish', completion(1, content='Task complete'), 'api-finish-rejected:required-native-terminal-call'),
            ('tool-budget', completion(1, [call('read-'+str(i), 'repo_read', {'paths': ['target.txt']})
                                          for i in range(33)]), 'api-tool-rejected:invalid-assistant-envelope'),
        )
        for label, native, failure in cases:
            with self.subTest(case=label):
                self.artifacts = self.base/('hybrid-' + label)
                self.before, self.after, self.loaded = [], [], []
                native['choices'][0]['message']['reasoning_content'] = None
                result, payloads = self.run_sse([native], 'mimo', actor_options={
                    'profile_id': api.ENGINEERING_HYBRID_SSE_PROFILE, 'thinking': 'disabled'})
                self.assertEqual(result['status'], 'tool-contract-failed')
                self.assertIn(failure, result['quality']['failures'])
                self.assertFalse(result['unknown_usage'])
                self.assertEqual((len(payloads), len(self.after)), (1, 1))
                self.assertEqual(result['tool_events'], [])
                self.assertIsNone(result['final_report'])

    def test_hybrid_unknown_stream_accounts_observed_usage_without_retry_or_action(self):
        result, payloads = self.run_sse([self.read(1)], 'mimo', broken=True,
            actor_options={'profile_id': api.ENGINEERING_HYBRID_SSE_PROFILE, 'thinking': 'disabled'})
        self.assertEqual(result['status'], 'unknown-call-blocked')
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'], 15)
        self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
        self.assertEqual(result['tool_events'], [])
        self.assertTrue((self.artifacts/'actor.pending.json').exists())
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())

    def test_hybrid_late_finish_only_accounts_without_accepting_terminal_report(self):
        now = [100.0]
        with patch.object(api.time, 'perf_counter', side_effect=lambda: now[0]):
            result, payloads = self.run_sse([self.finish(1)], 'mimo', on_eof=lambda: now.__setitem__(0, 701.0),
                actor_options={'profile_id': api.ENGINEERING_HYBRID_SSE_PROFILE, 'thinking': 'disabled'})
        self.assertEqual(result['status'], 'work-deadline-settled-unfinished')
        self.assertFalse(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'], 15)
        self.assertFalse(result['quality']['hard_pass'])
        self.assertIsNone(result['final_report'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual((len(payloads), len(self.after)), (1, 1))
        self.assertTrue(self.after[0]['settlement']['accounting_only'])

    def test_hybrid_phase_stop_reconstructs_sse_and_binds_new_configuration(self):
        started = api.time.perf_counter()
        def guard(evidence):
            identity = api._write_new(self.artifacts/'control/phase-stop-authorization.json',
                dict(evidence, kind='controlled-phase-stop-authorization'))
            return api.ControlledPhaseStopRequested('control/phase-stop-authorization.json', identity)
        result, payloads = self.run_sse([self.read(1)], 'mimo', actor_options={
            'profile_id': api.ENGINEERING_HYBRID_SSE_PROFILE, 'thinking': 'disabled',
            'actor_timing': {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': started,
                             'work_deadline_monotonic': started+600},
            'controlled_phase_stop_policy': 'before-first-repository-tool-delivery-v1',
            'controlled_phase_stop_guard': guard})
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual((len(payloads), len(self.after)), (1, 1))
        self.assertEqual(result['tool_events'], [])
        self.assertFalse(result['quality']['hard_pass'])
        for change in ({'profile_configuration_sha256': sha(canonical(api.profile_configuration(api.ENGINEERING_REASONING_SSE_PROFILE)))},
                       {'transport_profile_id': 'wrong'}, {'max_input_bytes': 131072}):
            metadata = dict(self.before[0], **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                api._phase_cut_evidence('before-first-repository-tool-delivery-v1',
                    'validated-batch-before-tool-delivery', metadata, self.brokers[0][0], [],
                    [call('x', 'repo_read', {'paths': ['target.txt']})], self.artifacts, {}, '', '', 1)

    def test_real_raw_byte_cap_retains_exact_prefix_and_unknown_reserve(self):
        raw = b':' + b'x' * sse.MAX_RAW_BYTES
        result, payloads = self.run_sse([self.read(1)], transform=lambda unused: raw)
        saved = (self.artifacts/'requests/01.transport-sse.bin').read_bytes()
        self.assertEqual(saved, raw[:sse.MAX_RAW_BYTES])
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(len(payloads), 1)
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertFalse(self.after[0]['settlement']['body_complete'])

    def test_legacy_oversized_chunk_keeps_original_untouched_capture_buffer(self):
        deadline = api.time.perf_counter()+10
        job = api._ManagedRequest('deepseek', {'stream': False}, '', deadline, deadline)
        job.state['body'].extend(b'old')
        with self.assertRaises(api.ResponseUnknown):
            job.capture_chunk(b'x'*(api.MAX_RESPONSE_BYTES+2))
        self.assertEqual(job.snapshot()['body'], b'old')

    def test_managed_polling_omits_body_and_freezes_only_once(self):
        copies = []
        class CountedBody(bytearray):
            def __bytes__(self):
                copies.append(len(self))
                return memoryview(self).tobytes()
        deadline = api.time.perf_counter()+10
        job = api._ManagedRequest('deepseek', {'stream': True}, '', deadline, deadline)
        job.state['body'] = CountedBody(b'x'*524288)
        for unused in range(8):
            self.assertNotIn('body', job.snapshot(include_body=False))
        self.assertEqual(copies, [])
        final = job.snapshot()
        self.assertEqual(copies, [524288])
        self.assertEqual((final['body_bytes_observed'], final['body_sha256']), (524288, sha(final['body'])))
        original, observations = api._ManagedRequest.snapshot, []
        def snapshot(request, **options):
            observations.append(options.get('include_body', True))
            return original(request, **options)
        with patch.object(api._ManagedRequest, 'snapshot', snapshot):
            result, payloads = self.run_sse([self.read(1)], actor_options={'max_requests': 1})
        self.assertEqual(observations.count(True), 1)
        self.assertGreaterEqual(observations.count(False), 1)
        self.assertEqual((len(payloads), len(result['tool_events'])), (1, 1))
        self.assertFalse(result['unknown_usage'])

    def test_main_poll_memory_error_closes_dispatch_gate_without_claiming_worker_exit(self):
        entered, release, jobs, dispatched = threading.Event(), threading.Event(), [], []
        original = api._ManagedRequest.snapshot
        def post(provider, payload, key, timeout, *, _managed):
            _managed.observe('connect', True, 'not_started')
            entered.set()
            release.wait(4)
            if _managed.begin_dispatch():
                dispatched.append(True)
        def snapshot(job, **options):
            if not options.get('include_body', True):
                jobs.append(job)
                self.assertTrue(entered.wait(1))
                raise MemoryError('synthetic main observation allocation')
            return original(job, **options)
        now = api.time.perf_counter()
        try:
            with patch.object(api, '_post', post), patch.object(api._ManagedRequest, 'snapshot', snapshot):
                managed = api._managed_post('deepseek', {'stream': True}, '', now+5, now+10,
                                           lambda kind, value: None)
            settlement = managed['settlement']
            self.assertEqual(managed['failure']['exception_class'], 'MemoryError')
            self.assertTrue(settlement['attempt_dispatch_gate_closed'])
            self.assertFalse(settlement['dispatch_started'])
            self.assertFalse(settlement['worker_done'])
            self.assertTrue(settlement['worker_alive_at_return'])
            self.assertFalse(settlement['body_complete'])
            self.assertEqual(dispatched, [])
        finally:
            release.set()
            for job in jobs:
                job.thread.join(1)
        self.assertEqual(dispatched, [])
        self.assertTrue(all(not job.thread.is_alive() for job in jobs))

    def test_final_body_memory_error_keeps_actual_prefix_metadata_and_pending(self):
        original, jobs = api._ManagedRequest.__init__, []
        class UnfreezableBody(bytearray):
            def __bytes__(self):
                raise MemoryError('synthetic body allocation')
        def init(job, *args, **kwargs):
            original(job, *args, **kwargs)
            job.state['body'] = UnfreezableBody()
            jobs.append(job)
        with patch.object(api._ManagedRequest, '__init__', init):
            result, payloads = self.run_sse([self.read(1)])
        outcome = self.after[0]
        settlement = outcome['settlement']
        self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
        self.assertTrue(result['unknown_usage'])
        self.assertIsNone(outcome['usage'])
        self.assertEqual(outcome['transport']['exception_class'], 'MemoryError')
        self.assertTrue(settlement['worker_done'])
        self.assertFalse(settlement['worker_alive_at_return'])
        self.assertTrue(settlement['body_complete'])
        self.assertEqual(settlement['body_bytes_observed'], len(jobs[0].state['body']))
        self.assertGreater(settlement['body_bytes_observed'], 0)
        self.assertEqual(settlement['body_sha256'], sha(jobs[0].state['body']))
        self.assertEqual(result['tool_events'], [])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertFalse((self.artifacts/'requests/01.transport-sse.bin').exists())
        self.assertFalse((self.artifacts/'requests/01.response.json').exists())

    def test_main_capture_memory_error_retains_unknown_and_actual_worker_lifetime(self):
        original_worker, original_write = api._ManagedRequest._worker, api._write_new
        for stage, alive in (('headers', False), ('projection', False), ('projection', True)):
            with self.subTest(stage=stage, worker_alive=alive):
                self.artifacts = self.base/('memory-'+stage+'-'+str(alive))
                self.before, self.after, self.loaded = [], [], []
                release, jobs = threading.Event(), []
                def worker(job):
                    jobs.append(job)
                    original_worker(job)
                    if alive:
                        release.wait(4)
                def write(path, *args, **kwargs):
                    if stage == 'headers' and path.name == '01.transport-headers.json':
                        raise MemoryError('synthetic capture allocation')
                    return original_write(path, *args, **kwargs)
                try:
                    with patch.object(api._ManagedRequest, '_worker', worker), patch.object(api, '_write_new', write), \
                            patch.object(sse, 'project', side_effect=MemoryError('synthetic projection allocation')) as project:
                        result, payloads = self.run_sse([self.read(1)])
                    outcome = self.after[0]
                    settlement = outcome['settlement']
                    self.assertEqual((len(payloads), len(self.before), len(self.after)), (1, 1, 1))
                    self.assertEqual(project.call_count, int(stage == 'projection'))
                    self.assertTrue(result['unknown_usage'])
                    self.assertIsNone(outcome['usage'])
                    self.assertEqual(outcome['transport']['exception_class'], 'MemoryError')
                    self.assertTrue(settlement['worker_done'])
                    self.assertEqual(settlement['worker_alive_at_return'], alive)
                    self.assertTrue(settlement['attempt_dispatch_gate_closed'])
                    self.assertTrue(settlement['dispatch_started'])
                    self.assertTrue(settlement['body_complete'])
                    self.assertGreater(settlement['body_bytes_observed'], 0)
                    self.assertEqual(settlement['capture_failure']['exception_class'], 'MemoryError')
                    self.assertEqual(result['tool_events'], [])
                    self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
                    self.assertFalse((self.artifacts/'requests/01.response.json').exists())
                finally:
                    release.set()
                    for job in jobs:
                        job.thread.join(1)

    def test_v3_large_request_admitted_and_over_cap_stops_before_key_reserve(self):
        result, payloads = self.run_sse([self.read(1)], actor_options={'system_context': 'x'*140000, 'max_requests': 1})
        self.assertGreater(len(canonical(payloads[0])), 131072)
        self.assertLess(len(canonical(payloads[0])), 524288)
        self.assertFalse(result['unknown_usage'])
        self.artifacts = self.base/'over-input-cap'
        self.before, self.after, self.loaded = [], [], []
        result, payloads = self.run_sse([], actor_options={'system_context': 'x'*524288})
        self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
        self.assertEqual((self.before, self.after, self.loaded, payloads), ([], [], [], []))

    def test_late_terminal_only_accounts_and_never_executes_model_action(self):
        now = [100.0]
        with patch.object(api.time, 'perf_counter', side_effect=lambda: now[0]):
            result, payloads = self.run_sse([self.read(1)], on_eof=lambda: now.__setitem__(0, 701.0))
        self.assertEqual(result['status'], 'work-deadline-settled-unfinished')
        self.assertFalse(result['unknown_usage'])
        self.assertIsNotNone(result['known_usage']['input_tokens'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)

    def test_v3_phase_stop_binds_raw_binary_and_rejects_wrong_transport(self):
        import time
        started = time.perf_counter()
        def guard(evidence):
            value = dict(evidence, kind='controlled-phase-stop-authorization')
            ref = 'control/phase-stop-authorization.json'
            identity = api._write_new(self.artifacts/ref, value)
            return api.ControlledPhaseStopRequested(ref, identity)
        result, payloads = self.run_sse([self.read(1)], actor_options={
            'actor_timing': {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': started,
                             'work_deadline_monotonic': started+600},
            'controlled_phase_stop_policy': 'before-first-repository-tool-delivery-v1',
            'controlled_phase_stop_guard': guard})
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)
        metadata = dict(self.before[0], transport_profile_id='wrong')
        with self.assertRaises(ValueError):
            api._phase_cut_evidence('before-first-repository-tool-delivery-v1',
                'validated-batch-before-tool-delivery', metadata, self.brokers[0][0], [],
                [call('x', 'repo_read', {'paths': ['target.txt']})], self.artifacts, {}, '', '', 1)

    def test_owned_worker_short_tail_is_joined_before_model_action(self):
        original = api._ManagedRequest._worker
        jobs = []
        def tail(job):
            jobs.append(job)
            original(job)
            threading.Event().wait(0.01)
        with patch.object(api._ManagedRequest, '_worker', tail):
            result, payloads = self.run_sse([self.read(1)], actor_options={'max_requests': 1})
        self.assertFalse(result['unknown_usage'])
        self.assertFalse(self.after[0]['settlement']['worker_alive_at_return'])
        self.assertTrue(all(not job.thread.is_alive() for job in jobs))
        self.assertEqual(len(result['tool_events']), 1)

    def test_owned_worker_still_alive_is_unknown_and_cannot_execute(self):
        original = api._ManagedRequest._worker
        release, jobs = threading.Event(), []
        def tail(job):
            jobs.append(job)
            original(job)
            release.wait(3)
        try:
            with patch.object(api._ManagedRequest, '_worker', tail):
                result, payloads = self.run_sse([self.read(1)])
            self.assertTrue(result['unknown_usage'])
            self.assertEqual(result['tool_events'], [])
            self.assertTrue(self.after[0]['settlement']['worker_done'])
            self.assertTrue(self.after[0]['settlement']['worker_alive_at_return'])
            self.assertIsNotNone(result['known_usage']['input_tokens'])
            self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
            self.assertEqual(len(payloads), 1)
        finally:
            release.set()
            for job in jobs:
                job.thread.join(1)


if __name__ == '__main__':
    unittest.main()
