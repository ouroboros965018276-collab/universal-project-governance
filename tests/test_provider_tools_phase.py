"""New fake transport/broker probes of actual staged run_actor; no project code."""
import copy
import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
if sys.version_info < (3, 10):
    raise unittest.SkipTest('Repository API helper requires Python 3.10+')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from evolution import provider_tools as api
assert Path(api.__file__).resolve() == ROOT / 'evolution/provider_tools.py'

class Broker:

    def __init__(self, root, task, audit_file=None, **unused):
        self.root, self.task, self.audit_file = (Path(root), task, audit_file)
        self.events = []

    def path(self, name):
        return self.root / name

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): api.sha(p.read_bytes()) for p in sorted(self.root.rglob('*')) if p.is_file()}

    def read_evidence_failures(self, events):
        return []

    def call(self, tool, arguments):
        if tool == 'repo_patch':
            self.path('a.txt').write_text('new', encoding='utf-8')
        result = {'ok': tool != 'repo_validate'}
        event = {'sequence': len(self.events) + 1, 'tool': tool, 'arguments': arguments, 'result': result, 'arguments_sha256': api.sha(api.canonical(arguments)), 'result_sha256': api.sha(api.canonical(result)), 'state_sha256': api.sha(api.canonical(self.snapshot()))}
        self.events.append(event)
        with Path(self.audit_file).open('ab') as stream:
            stream.write(api.canonical(event) + b'\n')
        return result

class ProviderPhaseBoundaryTests(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='provider-phase-fake-')
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.project = self.folder / 'fake-files'
        self.project.mkdir()
        (self.project / 'a.txt').write_text('old', encoding='utf-8')
        self.artifacts = self.folder / 'fake-native-artifacts'
        self.task = {'id': 'synthetic-no-project-execution', 'family': 'pure', 'prompt': 'Pure fake only.', 'initial_files': {'a.txt': 'old'}, 'writable_files': ['a.txt'], 'required_read_paths': [], 'required_tools': [], 'engineering_contract': {}}
        self.now = 100.0
        self.before, self.keys, self.after, self.callbacks = ([], [], [], [])
        self.batches = [[('repo_read', {})]]
        self.late, self.after_error = (False, False)
        self.brokers = []

        def create(root, task, git, **kwargs):
            result = Broker(root, task, **kwargs)
            self.brokers.append(result)
            return result
        self.engineering = SimpleNamespace(PROFILE_ID=api.ENGINEERING_PROFILE, BACKEND_ID=api.ENGINEERING_BACKEND, validate_task=lambda task: task, create_broker=create, public_instruction=lambda: 'Synthetic only.', tool_definitions=lambda: [{'name': name, 'description': 'fake', 'inputSchema': {'type': 'object', 'additionalProperties': False}} for name in ('repo_read', 'repo_patch', 'repo_validate', 'repo_status')], validate_execution_result=lambda result, task, state: {'status': 'EXECUTED', 'unknown': False}, quality_from_current_receipts=lambda *args: {'hard_pass': False, 'task_success': 0, 'validation': None, 'failures': [], 'required_tools_ok': False, 'scope_ok': True})

    def pre(self, metadata):
        self.assertEqual(self.keys, [] if not self.before else self.keys)
        self.before.append(copy.deepcopy(metadata))
        return {'reservation_receipt_sha256': 'a' * 64}

    def key(self, provider):
        self.assertTrue(self.before)
        self.keys.append(provider)
        return 'synthetic-sentinel-not-a-credential'

    def post(self, metadata):
        self.after.append(copy.deepcopy(metadata))
        if self.after_error:
            raise OSError('synthetic-after-fault')

    def transport(self, provider, payload, key, work, settlement, capture):
        self.assertEqual(settlement - work, 600)
        batch = self.batches[len(self.after)]
        calls = [{'id': 'r%d-c%d' % (len(self.after) + 1, ordinal), 'type': 'function', 'function': {'name': name, 'arguments': api.canonical(arguments).decode()}} for ordinal, (name, arguments) in enumerate(batch)]
        raw = {'id': 'synthetic-response-%d' % (len(self.after) + 1), 'model': payload['model'], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}, 'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None, 'tool_calls': calls}}]}
        body = api.canonical(raw)
        return {'response': (200, {}, body), 'failure': None, 'settlement': {'policy': api.SETTLEMENT_POLICY, 'max_seconds': 600, 'accounting_only': self.late, 'work_closed': self.late, 'worker_done': True, 'worker_alive_at_return': False, 'attempt_dispatch_gate_closed': True, 'dispatch_started': True, 'body_complete': True, 'capture_failure': None, 'transport_failure': None, 'work_deadline_monotonic': work, 'settlement_deadline_monotonic': settlement}}

    def guard(self, evidence):
        self.callbacks.append(copy.deepcopy(evidence))
        expected = dict(evidence, kind='controlled-phase-stop-authorization')
        identity = api._write_new(self.artifacts / 'control/phase-stop-authorization.json', expected)
        return api.ControlledPhaseStopRequested('control/phase-stop-authorization.json', identity)

    def run_fake(self, policy=None, guard=None, timing=True, maximum=12, profile=None):
        reasoning = profile in api.ENGINEERING_REASONING_PROFILES
        timeout = 600 if reasoning else 180
        kwargs = {'response_json_mode': False, 'thinking': 'enabled' if reasoning else 'disabled', 'before_request': self.pre, 'after_request': self.post, 'profile_id': profile or api.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE, 'execution_backend': api.ENGINEERING_BACKEND, 'broker_profile_id': api.ENGINEERING_PROFILE, 'connect_retry_policy': api.CONNECT_RETRY_POLICY, 'settlement_policy': api.SETTLEMENT_POLICY, 'max_requests': maximum, 'timeout_seconds': timeout}
        if timing:
            kwargs['actor_timing'] = {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': 90.0, 'work_deadline_monotonic': 90.0 + timeout}
        if policy is not None:
            kwargs.update(controlled_phase_stop_policy=policy, controlled_phase_stop_guard=self.guard if guard is None else guard)
        with mock.patch.object(api.importlib, 'import_module', side_effect=lambda name: self.engineering if name == 'evolution.engineering_broker' else (_ for _ in ()).throw(AssertionError(name))), mock.patch.object(api.time, 'perf_counter', side_effect=lambda: self.now), mock.patch.object(api, '_managed_post', side_effect=self.transport), mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('external process forbidden')), mock.patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')):
            return api.run_actor('deepseek', 'deepseek-v4-pro', self.task, self.project, self.artifacts, 'UNUSED-NO-GIT-EXECUTION', 'Synthetic pure context.', self.key, **kwargs)

    def test_zero_tool_cut_before_whole_valid_batch_delivery(self):
        self.batches = [[('repo_patch', {}), ('repo_status', {})]]
        result = self.run_fake('before-first-repository-tool-delivery-v1')
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual(result['requests'], 1)
        self.assertEqual(result['tool_events'], [])
        self.assertEqual((self.project / 'a.txt').read_text(), 'old')
        self.assertEqual(self.callbacks[0]['request_tail_event_count'], 0)
        self.assertEqual(len(self.callbacks[0]['batch']), 2)
        self.assertIsNone(result['quality']['task_success'])
        self.assertTrue((self.artifacts / 'actor.pending.json').exists())

    def test_patch_cut_on_twelfth_request_with_full_known_failed_validation_tail(self):
        self.batches = [[('repo_read', {})] for _ in range(11)] + [[('repo_patch', {}), ('repo_validate', {}), ('repo_status', {})]]
        result = self.run_fake('first-confirmed-repo-patch-request-tail-v1')
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual(result['requests'], 12)
        self.assertEqual([row['tool'] for row in result['api_tool_trace'][-3:]], ['repo_patch', 'repo_validate', 'repo_status'])
        self.assertEqual(self.callbacks[0]['request_tail_event_count'], 3)
        self.assertEqual(self.callbacks[0]['successful_patch_count'], 1)
        self.assertEqual(len(self.after), 12)
        self.assertEqual(result['known_usage']['total_tokens'], 24)

    def test_reasoning_profile_thirteenth_slot_first_patch_stops_at_real_phase_boundary(self):
        self.batches = [[('repo_read', {})] for _ in range(12)] + [[('repo_patch', {}), ('repo_validate', {}), ('repo_status', {})]]
        result = self.run_fake('first-confirmed-repo-patch-request-tail-v1', maximum=24,
            profile=api.ENGINEERING_REASONING_PROFILE)
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual(result['requests'], 13)
        self.assertEqual(result['max_requests'], 24)
        self.assertEqual(result['timeout_seconds'], 600)
        self.assertEqual(result['known_usage']['total_tokens'], 26)
        self.assertEqual(len(self.after), 13)
        self.assertEqual(len(self.callbacks), 1)
        evidence = self.callbacks[0]
        self.assertEqual(evidence['request_metadata']['profile_id'], api.ENGINEERING_REASONING_PROFILE)
        self.assertEqual(evidence['request_metadata']['profile_configuration_sha256'],
            api.sha(api.canonical(api.profile_configuration(api.ENGINEERING_REASONING_PROFILE))))
        self.assertEqual(evidence['api_requests_observed'], 13)
        self.assertEqual(evidence['request_tail_event_count'], 3)
        self.assertEqual(evidence['successful_patch_count'], 1)
        self.assertEqual([row['tool'] for row in result['api_tool_trace'][-3:]],
            ['repo_patch', 'repo_validate', 'repo_status'])
        self.assertIsNone(result['quality']['task_success'])
        self.assertTrue((self.artifacts / 'actor.pending.json').is_file())

    def test_phase_boundary_cannot_borrow_reasoning_limit_from_unbound_profile_or_legacy_metadata(self):
        base = {'profile_id': api.ENGINEERING_REASONING_PROFILE,
            'profile_configuration_sha256': api.sha(api.canonical(api.profile_configuration(api.ENGINEERING_REASONING_PROFILE))),
            'broker_profile_id': api.ENGINEERING_PROFILE, 'execution_backend': api.ENGINEERING_BACKEND,
            'request_index': 13}
        for metadata in (dict(base, profile_configuration_sha256='0' * 64),
                dict(base, broker_profile_id='wrong'), dict(base, execution_backend='wrong'),
                dict(base, profile_id=api.DEEPSEEK_PRO_FLASH_DISABLED_PROFILE)):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                api._phase_cut_evidence('first-confirmed-repo-patch-request-tail-v1',
                    'complete-request-tool-tail', metadata, SimpleNamespace(events=[]), [],
                    [{'function': {'name': 'repo_patch'}}], self.artifacts,
                    {}, '', '', 13)
        self.assertEqual(self.before, [])
        self.assertEqual(self.keys, [])

    def test_reasoning_v2_thirteenth_slot_phase_stop_binds_new_configuration_and_input_cap(self):
        self.batches = [[('repo_read', {})] for _ in range(12)] + [[('repo_patch', {}), ('repo_validate', {}), ('repo_status', {})]]
        result = self.run_fake('first-confirmed-repo-patch-request-tail-v1', maximum=24,
            profile=api.ENGINEERING_REASONING_INPUT_PROFILE)
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual((result['requests'], result['max_requests'], result['timeout_seconds']), (13, 24, 600))
        self.assertEqual(result['max_input_bytes'], 524288)
        self.assertEqual(len(self.after), 13)
        self.assertEqual(len(self.callbacks), 1)
        metadata = self.callbacks[0]['request_metadata']
        self.assertEqual(metadata['profile_configuration_sha256'],
            api.sha(api.canonical(api.profile_configuration(api.ENGINEERING_REASONING_INPUT_PROFILE))))
        self.assertEqual(metadata['max_input_bytes'], 524288)
        self.assertEqual(self.callbacks[0]['request_tail_event_count'], 3)
        self.assertFalse(self.callbacks[0]['next_request_reserved'])
        self.assertFalse(self.callbacks[0]['next_request_dispatched'])
        self.assertIsNone(result['quality']['task_success'])
        for change in ({'max_input_bytes': 131072}, {'profile_configuration_sha256':
                api.sha(api.canonical(api.profile_configuration(api.ENGINEERING_REASONING_PROFILE)))}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                api._phase_cut_evidence('first-confirmed-repo-patch-request-tail-v1',
                    'complete-request-tool-tail', dict(metadata, **change), SimpleNamespace(events=[]), [],
                    [{'function': {'name': 'repo_patch'}}], self.artifacts, {}, '', '', 13)

    def test_schema_invalid_batch_does_not_deliver_or_cut(self):
        self.batches = [[('repo_read', {'extra': 1}), ('repo_patch', {})], [('repo_read', {})]]
        result = self.run_fake('before-first-repository-tool-delivery-v1')
        self.assertEqual(result['requests'], 2)
        self.assertEqual(result['schema_rejections'], 1)
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(self.callbacks), 1)

    def test_after_accounting_fault_fences_phase_tools_and_preserves_known_components(self):
        self.after_error = True
        result = self.run_fake('before-first-repository-tool-delivery-v1')
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'], 2)
        self.assertEqual(self.callbacks, [])
        self.assertEqual(result['tool_events'], [])
        self.assertTrue((self.artifacts / 'requests/01.pending.json').exists())

    def test_accounting_only_late_result_does_not_reach_phase(self):
        self.late = True
        result = self.run_fake('before-first-repository-tool-delivery-v1')
        self.assertEqual(result['status'], 'work-deadline-settled-unfinished')
        self.assertIs(result['quality']['task_success'], False)
        self.assertEqual(self.callbacks, [])
        self.assertEqual(result['tool_events'], [])

    def test_wrong_phase_authorization_is_rejected_before_delivery(self):

        def wrong(evidence):
            changed = dict(evidence, kind='controlled-phase-stop-authorization', phase='complete-request-tool-tail')
            identity = api._write_new(self.artifacts / 'control/phase-stop-authorization.json', changed)
            return api.ControlledPhaseStopRequested('control/phase-stop-authorization.json', identity)
        result = self.run_fake('before-first-repository-tool-delivery-v1', wrong)
        self.assertEqual(result['status'], 'controlled-phase-stop-proposal-refused')
        self.assertIsNone(result['controlled_phase_stop'])
        self.assertEqual(result['tool_events'], [])

    def test_changed_journal_or_state_during_guard_invalidates_cut(self):
        self.batches = [[('repo_patch', {}), ('repo_status', {})]]

        def changed(evidence):
            proposal = self.guard(evidence)
            (self.project / 'a.txt').write_text('tampered', encoding='utf-8')
            return proposal
        result = self.run_fake('first-confirmed-repo-patch-request-tail-v1', changed)
        self.assertEqual(result['status'], 'controlled-phase-stop-proposal-refused')
        self.assertIsNone(result['controlled_phase_stop'])

    def test_external_setup_clock_tightens_native_clock(self):
        result = self.run_fake('before-first-repository-tool-delivery-v1')
        self.assertEqual(result['work_deadline_monotonic'], 270)
        self.assertEqual(self.before[0]['work_deadline_monotonic'], 270)
        self.assertEqual(self.after[0]['settlement']['actor_elapsed_before_transport_seconds'], 10)
        self.assertEqual(result['wall_seconds'], 10)

    def test_invalid_or_exhausted_clock_is_refused_before_reservation_and_key(self):
        cases = [{'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': 101, 'work_deadline_monotonic': 281}, {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': 90, 'work_deadline_monotonic': 271}, {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': True, 'work_deadline_monotonic': 181}, {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': float('nan'), 'work_deadline_monotonic': 280}, {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': -80, 'work_deadline_monotonic': 100}]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises((ValueError, api.DeadlineBeforeDispatch)):
                    api._registered_actor_timing(value, 180, 100)
        self.assertEqual(self.before, [])
        self.assertEqual(self.keys, [])

    def test_registered_clock_preserves_exact_constructed_deadline_across_float_binades(self):
        for boundary in (2.0**16, 2.0**20):
            for budget in (180, 600):
                start = math.nextafter(boundary - budget/2, math.inf)
                deadline = start + budget
                timing = {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': start,
                    'work_deadline_monotonic': deadline}
                with self.subTest(boundary=boundary, budget=budget):
                    self.assertNotEqual(deadline - start, budget)
                    accepted = api._registered_actor_timing(timing, budget, start + 1)
                    self.assertEqual(accepted, timing)
                    self.assertEqual(accepted['work_deadline_monotonic'], deadline)
                    for direction in (math.inf, -math.inf):
                        changed = dict(timing, work_deadline_monotonic=math.nextafter(deadline, direction))
                        with self.assertRaises(ValueError):
                            api._registered_actor_timing(changed, budget, start + 1)
        self.assertEqual(self.before, [])
        self.assertEqual(self.keys, [])

    def test_nonoptin_clock_and_result_surface_remain_unchanged(self):
        self.batches = [[('repo_read', {})]]
        result = self.run_fake(timing=False, maximum=1)
        self.assertNotIn('actor_timing', result)
        self.assertNotIn('controlled_phase_stop', result)
        self.assertEqual(result['work_deadline_monotonic'], 280)
        self.assertEqual(result['requests'], 1)
        self.assertEqual(self.callbacks, [])

    def test_guard_cannot_authorize_after_work_deadline(self):

        def late(evidence):
            proposal = self.guard(evidence)
            self.now = 271
            return proposal
        result = self.run_fake('before-first-repository-tool-delivery-v1', late)
        self.assertIsNone(result['controlled_phase_stop'])
        self.assertIs(result['quality']['task_success'], False)
        self.assertEqual(result['tool_events'], [])

    def test_unknown_dispatch_gate_cannot_authorize_cut(self):
        transport = self.transport

        def unconfirmed(*args):
            result = transport(*args)
            result['settlement']['attempt_dispatch_gate_closed'] = False
            return result
        self.transport = unconfirmed
        result = self.run_fake('before-first-repository-tool-delivery-v1')
        self.assertEqual(result['status'], 'controlled-phase-stop-proposal-refused')
        self.assertIsNone(result['controlled_phase_stop'])
        self.assertEqual(self.callbacks, [])
        self.assertEqual(result['tool_events'], [])

    def test_first_patch_request_allows_multiple_successful_patch_calls(self):
        self.batches = [[('repo_patch', {}), ('repo_patch', {}), ('repo_status', {})]]
        result = self.run_fake('first-confirmed-repo-patch-request-tail-v1')
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual(result['requests'], 1)
        self.assertEqual([row['tool'] for row in result['api_tool_trace']], ['repo_patch', 'repo_patch', 'repo_status'])
        self.assertEqual(self.callbacks[0]['successful_patch_count'], 2)
        self.assertEqual(self.callbacks[0]['request_tail_event_count'], 3)
        self.assertIsNone(result['quality']['task_success'])
        self.assertTrue((self.artifacts / 'actor.pending.json').is_file())

    def test_patch_in_earlier_request_cannot_be_late_cut(self):
        self.batches = [[('repo_patch', {})], [('repo_patch', {}), ('repo_status', {})]]
        original = api._controlled_phase_boundary

        def missed_first(policy, phase, guard, metadata, *args):
            if metadata['request_index'] == 1:
                return None
            return original(policy, phase, guard, metadata, *args)
        with mock.patch.object(api, '_controlled_phase_boundary', side_effect=missed_first):
            result = self.run_fake('first-confirmed-repo-patch-request-tail-v1')
        self.assertEqual(result['requests'], 2)
        self.assertEqual(result['status'], 'controlled-phase-stop-proposal-refused')
        self.assertIsNone(result['controlled_phase_stop'])
        self.assertEqual(self.callbacks, [])
        self.assertFalse((self.artifacts / 'control/phase-stop.accepted.json').exists())
if __name__ == '__main__':
    unittest.main()
