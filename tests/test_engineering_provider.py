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
from evolution import engineering_broker as real_engineering
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
        self.real_patch = False
        self.patch_fault = None
        self.fail_next_snapshot = False
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

        class RealPatchBroker(real_engineering.EngineeringBroker):
            # Keep execution/grading synthetic while exercising real project
            # reads, patch preflight, writes, snapshots and journal receipts.
            _validate_task = staticmethod(validate_task)
            validate = MockEngineeringBroker.validate

            def snapshot(self):
                if owner.fail_next_snapshot:
                    owner.fail_next_snapshot = False
                    raise ValueError('synthetic unverifiable pre-patch snapshot')
                return super().snapshot()

            def _execute(self, name, args):
                if name == 'repo_patch' and owner.patch_fault:
                    return owner.patch_fault(self, args)
                return super()._execute(name, args)

        def create(root, task, git_binary, *, audit_file=None, max_calls=32,
                   deadline=None, execution_artifacts=None):
            broker_type = RealPatchBroker if self.real_patch else MockEngineeringBroker
            broker = broker_type(root, task, git_binary,
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
        self.module.recoverable_project_patch_refusal = real_engineering.recoverable_project_patch_refusal
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

    def test_reasoning_profile_configuration_is_explicit_independent_and_legacy_configs_unchanged(self):
        original = (lab.THINKING_PROFILE, lab.FLASH_THINKING_PROFILE,
            lab.FLASH_DISABLED_PROFILE, lab.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE)
        # Exact earlier identities are already pinned in provider tests; these
        # direct copies additionally ensure no shared nested settings/rates.
        before = {name: canonical(lab.profile_configuration(name)) for name in original}
        config = lab.profile_configuration(lab.ENGINEERING_REASONING_PROFILE)
        self.assertEqual(config['providers'], {
            'deepseek': {'model': 'deepseek-v4-pro', 'thinking': 'enabled', 'output_cap': 16384, 'reasoning_effort': 'high'},
            'mimo': {'model': 'mimo-v2.6-pro', 'thinking': 'enabled', 'output_cap': 16384, 'reasoning_effort': None}})
        self.assertEqual(config['admission_limits'], {'max_requests': 24, 'timeout_seconds': 600, 'max_tools': 32})
        self.assertEqual(config['prices']['deepseek'], lab.profile_configuration(lab.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE)['prices']['deepseek'])
        self.assertEqual(config['prices']['mimo'], lab.profile_configuration(lab.THINKING_PROFILE)['prices']['mimo'])
        config['providers']['mimo']['model'] = 'mutated'
        config['prices']['deepseek']['USD']['output'] = '0'
        config['admission_limits']['max_requests'] = 999
        fresh = lab.profile_configuration(lab.ENGINEERING_REASONING_PROFILE)
        self.assertEqual(fresh['providers']['mimo']['model'], 'mimo-v2.6-pro')
        self.assertEqual(fresh['admission_limits']['max_requests'], 24)
        self.assertEqual({name: canonical(lab.profile_configuration(name)) for name in original}, before)

    def test_reasoning_profile_uses_native_tools_opaque_history_and_hash_bound_budget(self):
        for provider in ('deepseek', 'mimo'):
            with self.subTest(provider=provider):
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.artifacts = self.base/('reasoning-' + provider)
                self.loaded, self.before, self.after = [], [], []
                self.executions, self.brokers = [], []
                identity = sha(canonical(lab.profile_configuration(lab.ENGINEERING_REASONING_PROFILE)))
                steps = self.ready()+[self.finish(4)]
                def post(actual, payload, key, timeout):
                    self.assertEqual(actual, provider)
                    self.assertEqual(payload['model'], 'deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro')
                    self.assertEqual(payload['thinking'], {'type': 'enabled'})
                    self.assertEqual(payload['max_tokens' if provider == 'deepseek' else 'max_completion_tokens'], 16384)
                    self.assertEqual(payload['tool_choice'], 'auto')
                    self.assertNotIn('temperature', payload)
                    self.assertNotIn('top_p', payload)
                    self.assertNotIn('response_format', payload)
                    if provider == 'deepseek':
                        self.assertEqual(payload['reasoning_effort'], 'high')
                    else:
                        self.assertNotIn('reasoning_effort', payload)
                    for message in payload['messages']:
                        if message['role'] == 'assistant':
                            self.assertEqual(message['reasoning_content'], 'mock non-private test field')
                    pending = json.loads((self.artifacts/'requests'/('%02d.pending.json' % len(self.before))).read_bytes())
                    self.assertEqual(pending['profile_configuration_sha256'], identity)
                    step = steps[len(self.before)-1]
                    return 200, {}, canonical(step(payload) if callable(step) else step)
                with patch.object(lab, '_bounded_post', side_effect=post):
                    result = self.new_actor(provider=provider,
                        model='deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro',
                        profile_id=lab.ENGINEERING_REASONING_PROFILE, thinking='enabled',
                        max_requests=24, timeout_seconds=600)
                self.assertTrue(result['quality']['hard_pass'], result)
                self.assertEqual(result['max_requests'], 24)
                self.assertEqual(result['timeout_seconds'], 600)
                self.assertEqual(result['max_tools'], 32)
                self.assertEqual(result['requests'], 4)
                self.assertEqual(result['schema_rejections'], 0)
                for item in [result] + self.before + self.after:
                    self.assertEqual(item['profile_configuration_sha256'], identity)
                    self.assertEqual(item['profile_id'], lab.ENGINEERING_REASONING_PROFILE)
                    self.assertEqual(item['thinking'], 'enabled')
                    self.assertEqual(item['output_cap'], 16384)
                    self.assertIsNone(item['connect_retry_policy'])
                for item in self.after:
                    self.assertEqual(item['deadline_telemetry']['actor_timeout_seconds'], 600)

    def test_reasoning_v2_configuration_adds_only_explicit_request_body_bound(self):
        original = lab.profile_configuration(lab.ENGINEERING_REASONING_PROFILE)
        self.assertEqual(sha(canonical(original)), '03de3880a6d3e6114a5321687722e987c39419db55cc7855e2d4e833d009d5df')
        config = lab.profile_configuration(lab.ENGINEERING_REASONING_INPUT_PROFILE)
        expected = copy.deepcopy(original)
        expected['profile_id'] = 'thinking-enabled-engineering-pro-16384-v2'
        expected['admission_limits']['max_input_bytes'] = 524288
        self.assertEqual(config, expected)
        self.assertEqual(lab.MAX_INPUT_BYTES, 131072)
        config['admission_limits']['max_input_bytes'] = 1
        self.assertEqual(lab.profile_configuration(lab.ENGINEERING_REASONING_INPUT_PROFILE), expected)
        self.assertEqual(lab.profile_configuration(lab.ENGINEERING_REASONING_PROFILE), original)

    def test_reasoning_v2_replays_large_native_history_without_changing_v1_request_cap(self):
        for provider in ('deepseek', 'mimo'):
            for profile in (lab.ENGINEERING_REASONING_PROFILE, lab.ENGINEERING_REASONING_INPUT_PROFILE):
                with self.subTest(provider=provider, profile=profile):
                    (self.workspace/'target.txt').write_bytes(b'old\n')
                    self.artifacts = self.base/(provider + '-' + profile)
                    self.loaded, self.before, self.after = [], [], []
                    self.executions, self.brokers = [], []
                    steps = self.ready()+[self.finish(4)]
                    payloads = []
                    def post(actual, payload, key, timeout):
                        payloads.append(copy.deepcopy(payload))
                        index = len(self.before)
                        step = steps[index-1]
                        response = step(payload) if callable(step) else copy.deepcopy(step)
                        if index <= 2:
                            response['choices'][0]['message']['reasoning_content'] = 'r' * 90000
                        return 200, {}, canonical(response)
                    with patch.object(lab, '_bounded_post', side_effect=post):
                        result = self.new_actor(provider=provider,
                            model=lab.ENGINEERING_REASONING_PROFILE_SETTINGS[provider]['model'],
                            profile_id=profile, thinking='enabled', max_requests=24, timeout_seconds=600)
                    if profile == lab.ENGINEERING_REASONING_PROFILE:
                        self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
                        self.assertEqual(result['requests'], 2)
                        self.assertNotIn('max_input_bytes', result)
                        self.assertTrue(all('max_input_bytes' not in item for item in self.before+self.after))
                        continue
                    self.assertTrue(result['quality']['hard_pass'], result['quality'])
                    self.assertEqual(result['requests'], 4)
                    self.assertGreater(len(canonical(payloads[2])), 131072)
                    self.assertEqual([message['reasoning_content'] for message in payloads[2]['messages']
                        if message['role'] == 'assistant'], ['r' * 90000, 'r' * 90000])
                    identity = sha(canonical(lab.profile_configuration(profile)))
                    for item in [result]+self.before+self.after:
                        self.assertEqual(item['max_input_bytes'], 524288)
                        self.assertEqual(item['profile_configuration_sha256'], identity)
                    for metadata, payload in zip(self.before, payloads):
                        self.assertEqual(metadata['input_utf8_bytes'], len(canonical(payload)))
                        self.assertEqual(metadata['request_payload_sha256'], sha(canonical(payload)))
                    saved = json.loads((self.artifacts/'requests/01.response.json').read_bytes())
                    self.assertEqual(saved['response']['choices'][0]['message']['reasoning_content'], 'r' * 90000)

    def test_reasoning_v2_exact_request_byte_boundary_precedes_reservation_and_credentials(self):
        for provider in ('deepseek', 'mimo'):
            baseline_bytes = None
            for case in ('baseline', 'exact', 'excess'):
                with self.subTest(provider=provider, case=case):
                    self.artifacts = self.base/(provider + '-boundary-' + case)
                    self.loaded, self.before, self.after = [], [], []
                    payloads = []
                    def post(actual, payload, key, timeout):
                        payloads.append(canonical(payload))
                        return 200, {}, canonical(completion(1))
                    size = 0 if case == 'baseline' else 524288 - baseline_bytes + (case == 'excess')
                    with patch.object(lab, '_bounded_post', side_effect=post) as dispatch:
                        result = self.new_actor(provider=provider,
                            model=lab.ENGINEERING_REASONING_PROFILE_SETTINGS[provider]['model'],
                            profile_id=lab.ENGINEERING_REASONING_INPUT_PROFILE, thinking='enabled',
                            system_context='x' * size)
                    if case == 'excess':
                        dispatch.assert_not_called()
                        self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
                        self.assertEqual(result['requests'], 0)
                        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
                        self.assertFalse((self.artifacts/'requests').exists())
                        self.assertFalse((self.artifacts/'actor.started.json').exists())
                    else:
                        self.assertEqual(dispatch.call_count, 1)
                        self.assertEqual(result['requests'], 1)
                        if case == 'baseline':
                            baseline_bytes = len(payloads[0])
                        else:
                            self.assertEqual(len(payloads[0]), 524288)
                            self.assertEqual(self.before[0]['input_utf8_bytes'], 524288)

    def test_reasoning_profile_can_spend_the_thirteenth_slot_without_changing_tool_bound(self):
        steps = [self.read(index) for index in range(1, 11)] + [self.patch_from_read(11, 'fixed\n'),
            self.validate_and_status(12), self.finish(13)]
        result, count = self.run_steps(steps, profile_id=lab.ENGINEERING_REASONING_PROFILE,
            thinking='enabled', max_requests=24, timeout_seconds=600)
        self.assertEqual(count, 13)
        self.assertEqual(result['requests'], 13)
        self.assertEqual(result['max_tools'], 32)
        self.assertTrue(result['quality']['hard_pass'])

    def test_reasoning_actor_retains_large_native_response_and_known_primary_usage_with_unknown_detail(self):
        steps = self.ready()+[self.finish(4)]
        observed_bodies = []
        def post(provider, payload, key, timeout):
            index = len(self.before)
            step = steps[index-1]
            response = step(payload) if callable(step) else step
            if index == 1:
                response['choices'][0]['message']['reasoning_content'] = 'x' * 70000
                response['usage']['completion_tokens_details']['reasoning_tokens'] = 6
            else:
                self.assertEqual(payload['messages'][2]['reasoning_content'], 'x' * 70000)
            body = canonical(response)
            observed_bodies.append(body)
            return 200, {}, body
        with patch.object(lab, '_bounded_post', side_effect=post):
            result = self.new_actor(profile_id=lab.ENGINEERING_REASONING_PROFILE,
                thinking='enabled', max_requests=24, timeout_seconds=600)
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        self.assertFalse(result['unknown_usage'])
        self.assertEqual(result['usage']['total_tokens'], 60)
        self.assertIsNone(result['usage']['reasoning_tokens'])
        self.assertEqual(self.after[0]['usage']['total_tokens'], 15)
        self.assertIsNone(self.after[0]['usage']['reasoning_tokens'])
        saved = json.loads((self.artifacts/'requests/01.response.json').read_bytes())
        self.assertGreater(saved['body_bytes'], 65536)
        self.assertEqual(saved['body_bytes'], len(observed_bodies[0]))
        self.assertEqual(saved['body_sha256'], sha(observed_bodies[0]))
        self.assertEqual(saved['response']['usage']['completion_tokens_details']['reasoning_tokens'], 6)
        self.assertFalse((self.artifacts/'requests/01.pending.json').exists())

    def truncated_reasoning(self, index, **message_changes):
        response = completion(index)
        response['choices'][0]['finish_reason'] = 'length'
        response['choices'][0]['message']['reasoning_content'] = 'opaque synthetic unfinished analysis'
        response['choices'][0]['message'].update(message_changes)
        return response

    def test_opt_in_empty_reasoning_truncation_continues_once_through_native_tools_and_finish(self):
        initial = self.truncated_reasoning(1)
        steps = [initial, self.read(2), self.patch_from_read(3, 'fixed\n'),
            self.validate_and_status(4), self.finish(5)]
        def post(provider, payload, key, timeout):
            index = len(self.before)
            if index == 2:
                self.assertEqual(payload['messages'][-2], initial['choices'][0]['message'])
                self.assertEqual(payload['messages'][-1], {'role': 'user', 'content': lab.REASONING_CONTINUATION_FEEDBACK})
                self.assertEqual(self.brokers[-1][0].events, [])
            step = steps[index-1]
            return 200, {}, canonical(step(payload) if callable(step) else step)
        with patch.object(lab, '_bounded_post', side_effect=post):
            result = self.new_actor(profile_id=lab.ENGINEERING_REASONING_PROFILE, thinking='enabled',
                reasoning_continuation_policy=lab.REASONING_CONTINUATION_POLICY,
                max_requests=24, timeout_seconds=600)
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        self.assertEqual(result['requests'], 5)
        self.assertEqual(result['reasoning_continuations'], 1)
        self.assertEqual(result['usage']['total_tokens'], 75)
        self.assertEqual([event['tool'] for event in result['tool_events']],
            ['repo_read', 'repo_patch', 'repo_validate', 'repo_status'])
        self.assertEqual(result['api_tool_trace'][0]['request_index'], 2)
        for item in [result] + self.before + self.after:
            self.assertEqual(item['reasoning_continuation_policy'], lab.REASONING_CONTINUATION_POLICY)
        saved = json.loads((self.artifacts/'requests/01.response.json').read_bytes())
        self.assertEqual(saved['response'], initial)

    def test_continuation_does_not_repeat_add_slots_or_accept_other_missing_finishes(self):
        cases = [([self.truncated_reasoning(1), self.truncated_reasoning(2)], 24, 2, 1),
            ([self.truncated_reasoning(1)], 1, 1, 0),
            ([completion(1)], 24, 1, 0),
            ([self.truncated_reasoning(1, content='I finished the task.')], 24, 1, 0),
            ([self.truncated_reasoning(1, reasoning_content='')], 24, 1, 0)]
        partial = self.read(1)
        partial['choices'][0]['finish_reason'] = 'length'
        cases.append(([partial], 24, 1, 0))
        for ordinal, (steps, maximum, expected_requests, continuations) in enumerate(cases):
            with self.subTest(ordinal=ordinal):
                self.artifacts = self.base/('continuation-stop-'+str(ordinal))
                self.loaded, self.before, self.after = [], [], []
                result, count = self.run_steps(steps, profile_id=lab.ENGINEERING_REASONING_PROFILE,
                    thinking='enabled', reasoning_continuation_policy=lab.REASONING_CONTINUATION_POLICY,
                    max_requests=maximum, timeout_seconds=600)
                self.assertEqual(count, expected_requests)
                self.assertEqual(result['requests'], expected_requests)
                self.assertEqual(result['reasoning_continuations'], continuations)
                length = steps[-1]['choices'][0]['finish_reason'] == 'length'
                self.assertEqual(result['status'], 'output-limit-unfinished' if length else 'tool-contract-failed')
                self.assertEqual(result['refusal_reason'], 'provider-finish-reason-length' if length else None)
                self.assertEqual(result['tool_events'], [])
                self.assertIsNone(result['final_report'])
                self.assertFalse(result['quality']['hard_pass'])

    def test_continuation_never_retries_unknown_or_late_responses_and_default_remains_terminal(self):
        for ordinal, mode in enumerate(('unknown', 'late', 'default')):
            self.artifacts = self.base/('continuation-fence-'+mode)
            self.loaded, self.before, self.after = [], [], []
            now = [100.0]
            def post(provider, payload, key, timeout):
                response = self.truncated_reasoning(1)
                if mode == 'unknown':
                    response.pop('usage')
                elif mode == 'late':
                    now[0] += 601
                return 200, {}, canonical(response)
            kwargs = {'profile_id': lab.ENGINEERING_REASONING_PROFILE, 'thinking': 'enabled',
                'max_requests': 24, 'timeout_seconds': 600}
            if mode != 'default':
                kwargs['reasoning_continuation_policy'] = lab.REASONING_CONTINUATION_POLICY
            with self.subTest(mode=mode), patch.object(lab.time, 'perf_counter', side_effect=lambda: now[0]), \
                    patch.object(lab, '_bounded_post', side_effect=post) as dispatch:
                result = self.new_actor(**kwargs)
            self.assertEqual(dispatch.call_count, 1)
            self.assertEqual(result['requests'], 1)
            self.assertEqual(result['tool_events'], [])
            self.assertIsNone(result['final_report'])
            if mode == 'default':
                self.assertNotIn('reasoning_continuations', result)
                self.assertNotIn('reasoning_continuation_policy', result)
                self.assertNotIn('reasoning_continuation_policy', self.before[0])
            else:
                self.assertEqual(result['reasoning_continuations'], 0)
            self.assertEqual(result['unknown_usage'], mode == 'unknown')

    def test_continuation_policy_requires_exact_new_profile_before_credentials_or_artifacts(self):
        for changes in ({}, {'profile_id': lab.THINKING_PROFILE},
                {'profile_id': lab.ENGINEERING_REASONING_PROFILE, 'thinking': 'enabled',
                    'reasoning_continuation_policy': 'unknown'}):
            kwargs = {'reasoning_continuation_policy': lab.REASONING_CONTINUATION_POLICY}
            kwargs.update(changes)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.new_actor(**kwargs)
        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
        self.assertFalse(self.artifacts.exists())

    def test_reasoning_profile_does_not_raise_default_limits_or_admit_other_backends(self):
        valid = {'profile_id': lab.ENGINEERING_REASONING_PROFILE, 'thinking': 'enabled'}
        cases = [dict(valid, max_requests=25), dict(valid, max_requests=True),
            dict(valid, timeout_seconds=601), dict(valid, timeout_seconds=float('nan')),
            dict(valid, timeout_seconds=float('inf')), dict(valid, thinking='disabled'),
            dict(valid, model='deepseek-flash'), dict(valid, broker_profile_id=None),
            dict(valid, execution_backend='docker-cpython-finite-v1'),
            {'max_requests': 13}, {'timeout_seconds': 181},
            dict(valid, tool_feedback_policy=lab.PUBLIC_LANGUAGE_FEEDBACK_POLICY)]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), patch.object(lab, '_post') as post, self.assertRaises(ValueError):
                self.new_actor(**kwargs)
            post.assert_not_called()
        self.assertEqual((self.loaded, self.before, self.after), ([], [], []))
        self.assertFalse(self.artifacts.exists())
        result, count = self.run_steps(self.ready()+[self.finish(4)], **valid)
        self.assertEqual(result['max_requests'], 12)
        self.assertEqual(result['timeout_seconds'], 180)
        self.assertEqual(count, 4)

    def test_reasoning_connect_retry_requires_durable_ack_and_uses_same_payload_within_budget(self):
        payloads = []
        steps = self.ready()+[self.finish(5)]
        def acknowledge(metadata):
            self.after.append(metadata)
            return {'policy': lab.CONNECT_RETRY_POLICY, 'connect_retry_authorized': True,
                'prior_request_id': metadata['request_id'], 'prior_request_index': metadata['request_index'],
                'request_payload_sha256': metadata['request_payload_sha256'],
                'input_task_sha256': metadata['input_task_sha256'],
                'prior_receipt_sha256': metadata['receipt_sha256']}
        self.account = acknowledge
        def post(provider, payload, key, timeout):
            payloads.append(canonical(payload))
            index = len(self.before)
            if index == 1:
                raise lab.TransportFailure({'phase': 'connect', 'exception_class': 'TimeoutError',
                    'connection_attempted': True, 'http_dispatch': 'not_started'})
            step = steps[index-2]
            return 200, {}, canonical(step(payload) if callable(step) else step)
        with patch.object(lab, '_bounded_post', side_effect=post):
            result = self.new_actor(profile_id=lab.ENGINEERING_REASONING_PROFILE, thinking='enabled',
                max_requests=24, timeout_seconds=600, connect_retry_policy=lab.CONNECT_RETRY_POLICY)
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(result['requests'], 5)
        self.assertEqual(payloads[0], payloads[1])
        self.assertNotEqual(self.before[0]['request_id'], self.before[1]['request_id'])
        self.assertEqual(self.before[1]['retry_of_request_id'], self.before[0]['request_id'])
        self.assertTrue(self.after[0]['not_invoked'])
        self.assertFalse(self.after[0]['unknown'])
        self.assertEqual(result['usage']['total_tokens'], 60)
        self.assertEqual(result['max_requests'], 24)
        self.assertEqual(result['timeout_seconds'], 600)

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

    def test_missing_patch_path_feedback_identifies_field_before_valid_correction(self):
        observed = []
        invalid = completion(2, [call('missing-path', 'repo_patch', {'operations': [
            {'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}]}),
            call('validation-not-admitted', 'repo_validate', {})])
        def corrected(payload):
            feedback = [json.loads(message['content']) for message in payload['messages'][-2:]]
            observed.append((feedback, (self.workspace/'target.txt').read_bytes(), list(self.executions),
                             [event['tool'] for event in self.brokers[-1][0].events]))
            return completion(3, [call('corrected-path', 'repo_patch', {'operations': [
                {'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}]})])
        result, count = self.run_steps([self.read(1), invalid, corrected,
                                       self.validate_and_status(4), self.finish(5)])
        self.assertEqual(count, 5)
        feedback, contents, executions, events = observed[0]
        self.assertEqual(feedback[0]['missing_required'], ['/operations/0/path'])
        self.assertEqual(feedback[1]['missing_required'], [])
        self.assertEqual(feedback[0]['inputSchema'], tool_definitions()[2]['inputSchema'])
        self.assertTrue(all(item['batch_executed'] is False for item in feedback))
        self.assertEqual(feedback[0]['remaining_schema_corrections'], 0)
        self.assertEqual((contents, executions, events), (b'old\n', [], ['repo_read']))
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(result['schema_rejections'], 1)
        self.assertEqual([event['tool'] for event in result['tool_events']],
                         ['repo_read', 'repo_patch', 'repo_validate', 'repo_status'])

    def test_repeated_missing_patch_path_still_exhausts_one_correction(self):
        observed = []
        def invalid(index):
            return completion(index, [call('missing-path-'+str(index), 'repo_patch', {'operations': [
                {'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}]})])
        def repeated(payload):
            observed.append(json.loads(payload['messages'][-1]['content']))
            return invalid(2)
        result, count = self.run_steps([invalid(1), repeated])
        self.assertEqual((count, result['schema_rejections'], result['tool_attempts']), (2, 2, 2))
        self.assertEqual(observed[0]['missing_required'], ['/operations/0/path'])
        self.assertEqual(observed[0]['remaining_schema_corrections'], 0)
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertIn('api-tool-rejected:schema-correction-budget', result['quality']['failures'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(self.executions, [])
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')
        record = json.loads((self.artifacts/'schema-rejections/02.json').read_bytes())
        self.assertFalse(record['correction_permitted'])

    def test_required_field_feedback_indexes_operations_without_submitted_values(self):
        observed = []
        submitted = 'submitted-private-value'
        bad = completion(1, [call('missing-fields', 'repo_patch', {'operations': [
            {'old_sha256': submitted, 'new_text': submitted, submitted: submitted},
            {'path': 'target.txt', 'new_text': submitted}, {}]})])
        def inspect(payload):
            observed.append(json.loads(payload['messages'][-1]['content']))
            return self.finish(2)
        result, count = self.run_steps([bad, inspect])
        self.assertEqual(count, 2)
        feedback = observed[0]
        self.assertEqual(feedback['missing_required'], ['/operations/0/path',
            '/operations/1/old_sha256', '/operations/2/path',
            '/operations/2/old_sha256', '/operations/2/new_text'])
        self.assertNotIn(submitted, json.dumps(feedback))
        self.assertEqual(feedback['inputSchema'], tool_definitions()[2]['inputSchema'])
        self.assertEqual(result['tool_events'], [])

    def test_required_diagnostics_are_bounded_and_do_not_judge_validity(self):
        schema = real_engineering.tool_definitions()[2]['inputSchema']
        valid = {'operations': [{'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}]}
        self.assertTrue(lab._schema(valid, schema))
        self.assertEqual(lab._missing_required_pointers(valid, schema), [])
        for invalid in ({'operations': 'submitted-private-value'}, dict(valid, extra='submitted-private-value'),
                        {'operations': [dict(valid['operations'][0], new_text=42)]}):
            self.assertFalse(lab._schema(invalid, schema))
            self.assertEqual(lab._missing_required_pointers(invalid, schema), [])
        many = lab._missing_required_pointers({'operations': [{} for unused in range(20)]}, schema)
        self.assertEqual(len(many), 16)
        self.assertEqual(many[:3], ['/operations/0/path', '/operations/0/old_sha256', '/operations/0/new_text'])
        self.assertEqual(many[-1], '/operations/5/path')
        nested, value = {'type': 'object', 'required': ['leaf'], 'properties': {'leaf': {'type': 'string'}}}, {}
        for unused in range(40):
            nested = {'type': 'object', 'properties': {'child': nested}}
            value = {'child': value}
        self.assertEqual(lab._missing_required_pointers(value, nested), [])
        escaped = {'type': 'object', 'properties': {'a/b~c': {'type': 'string'}}, 'required': ['a/b~c']}
        self.assertEqual(lab._missing_required_pointers({}, escaped), ['/a~1b~0c'])
        class CountedArray(list):
            visited = 0
            def __iter__(self):
                for item in super().__iter__():
                    self.visited += 1
                    yield item
        wide = CountedArray([valid['operations'][0]] * 10000)
        self.assertEqual(lab._missing_required_pointers({'operations': wide}, schema), [])
        self.assertLessEqual(wide.visited, 256)

    def test_other_schema_rejections_keep_full_schema_with_empty_required_diagnostics(self):
        observed = []
        malformed = call('malformed-json', 'repo_read', {})
        malformed['function']['arguments'] = '{'
        calls = [call('wrong-type', 'repo_patch', {'operations': [
            {'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 42}]}),
            call('extra-field', 'repo_status', {'submitted-private-name': 'submitted-private-value'}),
            call('wrong-array-type', 'repo_patch', {'operations': 'submitted-private-value'}), malformed]
        def inspect(payload):
            observed.extend(json.loads(message['content']) for message in payload['messages'][-len(calls):])
            return self.finish(2)
        result, count = self.run_steps([completion(1, calls), inspect])
        self.assertEqual(count, 2)
        self.assertEqual(len(observed), len(calls))
        schemas = {item['name']: item['inputSchema'] for item in tool_definitions()}
        for feedback, item in zip(observed, calls):
            self.assertEqual(feedback['missing_required'], [])
            self.assertEqual(feedback['inputSchema'], schemas[item['function']['name']])
            self.assertNotIn('submitted-private-', json.dumps(feedback))
        self.assertEqual(result['tool_events'], [])

    def test_engineering_patch_contract_explicitly_requires_each_operation_fields(self):
        for instruction in (real_engineering.public_instruction(), real_engineering.cli_public_instruction(),
                            real_engineering.tool_definitions()[2]['description']):
            self.assertIn('Each repo_patch operation requires path, old_sha256 and new_text', instruction)
            self.assertIn('no implicit current file', instruction)

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

    def project_patch(self, index, operations):
        return completion(index, [call('patch-'+str(index), 'repo_patch', {'operations': operations})])

    def enable_real_patch(self):
        self.real_patch = True
        self.module.tool_definitions.side_effect = real_engineering.tool_definitions

    def test_real_preflight_rejections_are_original_feedback_then_provider_repairs(self):
        self.enable_real_patch()
        operation = {'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n'}
        bad_operations = [
            [dict(operation, old_sha256='0'*64)],
            [operation, operation],
            [dict(operation, new_text='old\n')],
            [dict(operation, old_text='absent')],
        ]
        errors = ['patch precondition hash mismatch', 'patch path is protected or duplicated',
                  'patch must make a nonempty bounded change', 'old_text must occur exactly once in the current file']
        steps = [self.read(1)]
        for index, operations in enumerate(bad_operations, 2):
            def reject(payload, index=index, operations=operations):
                if index > 2:
                    self.assertEqual(self.feedback(payload), {'ok': False, 'error': 'ValueError: '+errors[index-3]})
                self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')
                return self.project_patch(index, operations)
            steps.append(reject)
        def repair(payload):
            self.assertEqual(self.feedback(payload), {'ok': False, 'error': 'ValueError: '+errors[-1]})
            return self.project_patch(6, [operation])
        result, count = self.run_steps(steps + [repair, self.validate_and_status(7), self.finish(8)])
        self.assertEqual(count, 8)
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'fixed\n')
        events = result['tool_events']
        for event, error in zip(events[1:5], errors):
            self.assertEqual(event['result'], {'ok': False, 'error': 'ValueError: '+error})
            self.assertEqual(event['state_sha256'], events[0]['state_sha256'])
        self.assertEqual(len(result['api_tool_trace']), len(events))
        self.assertEqual(real_engineering.files_from_receipt_journal(self.task, events),
                         {'target.txt': 'fixed\n', 'contract.json': '{}\n'})

    def test_safe_preflight_feedback_cannot_extend_request_budget(self):
        self.enable_real_patch()
        bad = {'path': 'target.txt', 'old_sha256': '0'*64, 'new_text': 'fixed\n'}
        result, count = self.run_steps([self.read(1), self.project_patch(2, [bad])], max_requests=2)
        self.assertEqual(count, 2)
        self.assertFalse(result['quality']['hard_pass'])
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')
        self.assertEqual(len(result['tool_events']), 2)

    def test_partial_write_shape_cannot_be_safe_preflight_feedback(self):
        self.enable_real_patch()
        self.patch_fault = lambda broker, args: {'ok': False,
            'error': 'ValueError: patch precondition hash mismatch', 'changed': [],
            'files': {}, 'write_state': 'partial-or-unverified'}
        result, count = self.run_steps([self.read(1), self.patch_from_read(2, 'fixed\n')])
        self.assertEqual(count, 2)
        self.assertEqual(result['status'], 'unknown-tool-write-blocked')
        self.assertTrue(result['execution_state_unknown'])

    def test_failed_prepatch_snapshot_marks_unknown_without_calling_patch(self):
        self.enable_real_patch()
        def fail_snapshot(payload):
            self.fail_next_snapshot = True
            return self.project_patch(2, [{'path': 'target.txt', 'old_sha256': '0'*64, 'new_text': 'fixed\n'}])
        result, count = self.run_steps([self.read(1), fail_snapshot])
        self.assertEqual(count, 2)
        self.assertEqual(result['status'], 'execution-state-unknown-blocked')
        self.assertTrue(result['execution_state_unknown'])
        self.assertEqual([e['tool'] for e in result['tool_events']], ['repo_read'])
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')

    def test_state_change_with_known_preflight_error_is_terminal(self):
        self.enable_real_patch()
        def drift(broker, args):
            (self.workspace/'target.txt').write_bytes(b'drift\n')
            return {'ok': False, 'error': 'ValueError: patch precondition hash mismatch'}
        self.patch_fault = drift
        result, count = self.run_steps([self.read(1), self.patch_from_read(2, 'fixed\n')])
        self.assertEqual(count, 2)
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertFalse(result['quality']['hard_pass'])

    def test_duplicate_error_cannot_hide_later_protected_or_unregistered_path(self):
        error = {'ok': False, 'error': 'ValueError: patch path is protected or duplicated'}
        for path in ('contract.json', 'unregistered.txt'):
            args = {'operations': [{'path': 'target.txt'}, {'path': 'target.txt'}, {'path': path}]}
            event = {'state_sha256': 'a'*64, 'arguments_sha256': sha(canonical(args)),
                     'result_sha256': sha(canonical(error))}
            self.assertFalse(lab._recoverable_engineering_patch('repo_patch', args, error, event,
                self.task, 'a'*64, 'a'*64))

    def test_real_protected_batch_is_terminal_before_any_patch(self):
        self.enable_real_patch()
        operation = {'path': 'target.txt', 'old_sha256': '0'*64, 'new_text': 'fixed\n'}
        protected = {'path': 'contract.json', 'old_sha256': sha(b'{}\n'), 'new_text': 'changed\n'}
        result, count = self.run_steps([self.read(1), self.project_patch(2, [operation, protected])])
        self.assertEqual(count, 2)
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertEqual([e['tool'] for e in result['tool_events']], ['repo_read'])
        self.assertEqual((self.workspace/'contract.json').read_bytes(), b'{}\n')

    def test_known_error_requires_verified_both_snapshots_and_receipts(self):
        args = {'operations': [{'path': 'target.txt'}]}
        result = {'ok': False, 'error': 'ValueError: patch precondition hash mismatch'}
        event = {'state_sha256': 'a'*64, 'arguments_sha256': sha(canonical(args)),
                 'result_sha256': sha(canonical(result))}
        for before, after in ((None, 'a'*64), ('a'*64, None), ('b'*64, 'a'*64)):
            self.assertFalse(lab._recoverable_engineering_patch('repo_patch', args, result,
                event, self.task, before, after))
        for field in ('state_sha256', 'arguments_sha256', 'result_sha256'):
            self.assertFalse(lab._recoverable_engineering_patch('repo_patch', args, result,
                dict(event, **{field: None}), self.task, 'a'*64, 'a'*64))

    def test_old_text_null_is_rejected_without_silent_normalization(self):
        self.enable_real_patch()
        operation = {'path': 'target.txt', 'old_sha256': sha(b'old\n'), 'new_text': 'fixed\n', 'old_text': None}
        result, count = self.run_steps([self.read(1), self.project_patch(2, [operation])], max_requests=2)
        self.assertEqual(count, 2)
        self.assertEqual(result['schema_rejections'], 1)
        self.assertEqual([e['tool'] for e in result['tool_events']], ['repo_read'])
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')

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
