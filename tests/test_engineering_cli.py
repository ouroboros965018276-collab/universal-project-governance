"""Prospective CLI project profile: no real subprocess, network or project code."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SUPPORTED = sys.version_info >= (3, 10)
if SUPPORTED:
    from evolution import engineering_broker as engineering, project_executor, tool_broker, tool_codex
    from evolution.tool_broker import canonical, sha


def task():
    return {'id': 'mock-cli-project', 'family': 'mock-only', 'prompt': 'Repair core and remove retired path.',
        'initial_files': {'pkg/__init__.py': '', 'pkg/core.py': 'VALUE = 0\n',
                          'legacy.py': 'VALUE = 0\n', 'README.md': 'current docs\n'},
        'writable_files': ['pkg/core.py', 'legacy.py', 'README.md'],
        'required_read_paths': ['pkg/core.py'],
        'required_tools': ['repo_read', 'repo_patch', 'repo_validate', 'repo_status'],
        'engineering_contract': {'schema_version': 1, 'contract_id': 'mock-cli-suite',
            'trusted_files': {'audit_tests.py': 'import unittest\nclass Case(unittest.TestCase):\n    def test_value(self):\n        self.assertTrue(True)\n'},
            'checks': [{'id': 'unit', 'recipe': 'unittest', 'test_modules': ['audit_tests'],
                        'minimum_tests': 1, 'expected_test_ids': ['audit_tests.Case.test_value']}]}}


def events_for(journal):
    return [{'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'id': 'item_' + str(n), 'status': 'completed',
        'server': 'upg_repo', 'tool': row['tool'], 'arguments': row['arguments'],
        'result': {'content': [{'type': 'text', 'text': canonical(row['result']).decode('utf-8')}],
                   'structured_content': None}, 'error': None}} for n, row in enumerate(journal)]


@unittest.skipUnless(SUPPORTED, 'repository engine requires Python3.10+')
class CliProjectCandidateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='upg-cli-project-pure-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.repo = self.base / 'workspace'
        self.repo.mkdir()
        self.task = task()
        for name, text in self.task['initial_files'].items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode('utf-8'))
        self.executor_calls = 0
        self.checked_ok = True
        self.integrity_ok = True
        self.execution_unknown = False
        self.patches = [mock.patch.object(tool_broker, 'git_command', return_value=
            subprocess.CompletedProcess([], 0, b' M pkg/core.py\n', b'')),
            mock.patch.object(project_executor, 'execute_project', side_effect=self.execute),
            mock.patch.object(project_executor, 'read_project_receipt', side_effect=self.read_receipt)]
        self.patches += [mock.patch.object(subprocess, name, side_effect=AssertionError('actual process forbidden'))
            for name in ('run', 'Popen', 'check_output', 'call', 'check_call')]
        self.patches += [mock.patch.object(socket, name, side_effect=AssertionError('network forbidden'))
            for name in ('socket', 'create_connection')]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.binary = self.base / 'codex.exe'
        self.binary.write_bytes(b'mock-cli-no-execution')
        self.host = self.base / ('codex-code-mode-host.exe' if os.name == 'nt' else 'codex-code-mode-host')
        self.host.write_bytes(b'mock-code-mode-host-no-execution')
        self.git = self.base / 'mock-git.exe'
        self.git.write_bytes(b'mock-git-no-execution')
        self.config = {'binary': str(self.binary), 'code_mode_host_binary': str(self.host),
            'git_binary': str(self.git), 'model': 'explicit-mock-only', 'effort': 'low',
            'artifact_root': str(self.base / 'calls'), 'timeout_seconds': 90,
            'broker_profile_id': 'stdlib-python-project-v1', 'max_tool_calls': 32}
        self.adapter = tool_codex.ToolCodex(self.config)
        self.broker = engineering.create_broker(self.repo, self.task, self.git,
            execution_artifacts=self.base / 'execution', deadline=time.time() + 60)
        self.before = self.broker.snapshot()

    def execute(self, files, contract, directory, remaining_seconds):
        self.executor_calls += 1
        directory.mkdir()
        receipt = {'status': 'EXECUTED', 'unknown': self.execution_unknown, 'backend': engineering.BACKEND_ID,
            'snapshot_sha256': sha(canonical({n: sha(t.encode('utf-8')) for n, t in files.items()})),
            'contract_sha256': sha(canonical(contract)), 'runner_sha256': '1' * 64,
            'input_sha256': '2' * 64, 'output_sha256': '3' * 64, 'image_id': 'sha256:' + '4' * 64,
            'container_removed': True, 'scratch_removed': True, 'mock_checked_ok': self.checked_ok}
        (directory / 'result.json').write_bytes(canonical(receipt))
        return receipt

    def read_receipt(self, files, contract, directory, receipt_sha256=None):
        raw = (directory / 'result.json').read_bytes()
        observed_ok = json.loads(raw).get('mock_checked_ok', self.checked_ok)
        return ({'ok': observed_ok, 'integrity_ok': self.integrity_ok and (receipt_sha256 is None or sha(raw) == receipt_sha256),
            'failures': [] if observed_ok else ['project-check-failed:unit'],
            'checks_passed': int(observed_ok), 'checks_total': 1, 'diagnostics': []},
            json.loads(raw), sha(raw))

    def edit(self, *, delete=False):
        paths = ['pkg/core.py', 'legacy.py'] if delete else ['pkg/core.py']
        read = self.broker.call('repo_read', {'paths': paths})
        operations = [{'path': 'pkg/core.py', 'old_sha256': read['files']['pkg/core.py']['sha256'],
                       'new_text': 'VALUE = 1\n'}]
        if delete:
            operations.append({'path': 'legacy.py', 'old_sha256': read['files']['legacy.py']['sha256'], 'new_text': None})
        result = self.broker.call('repo_patch', {'operations': operations})
        self.assertTrue(result['ok'], result)

    def complete(self, *, delete=False):
        self.edit(delete=delete)
        self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})

    def quality(self, broker=None, events=None, claim='passed'):
        broker = broker or self.broker
        validation, failures, unknown, not_run = engineering.current_validation_from_receipts(broker)
        result = tool_codex._quality(broker, broker.events, events or events_for(broker.events),
            json.dumps({'summary': 'Mock observation only.', 'validation': claim,
                        'helper_gap': 'project_tool unavailable in bounded broker'}), 32,
            supplied_validation=validation, extra_failures=failures, strict_cli_results=True)
        return result, unknown, not_run

    def test_explicit_project_profile_has_distinct_source_bound_identity(self):
        identity = self.adapter.binding()
        self.assertEqual(identity['adapter'], 'codex-exec-required-stdlib-project-mcp-v1')
        self.assertEqual(identity['broker_profile_id'], engineering.PROFILE_ID)
        self.assertEqual(identity['engineering_broker_source_sha256'], sha(Path(engineering.__file__).read_bytes()))
        self.assertEqual(identity['project_executor_source_sha256'], sha(Path(project_executor.__file__).read_bytes()))
        self.assertEqual(identity['tool_schema_sha256'], sha(canonical(engineering.tool_definitions())))
        self.assertFalse(identity['provider_request_cap_attested'])
        self.assertFalse(identity['controlled_cutpoint_supported'])
        self.assertEqual(identity['artifact_root'], self.config['artifact_root'])

    def test_unknown_profile_and_mixed_endpoint_configs_refused(self):
        for value in ('another-profile', 1, False, {}, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool_codex.ToolCodex(dict(self.config, broker_profile_id=value))
        for name in ('auth', 'headers', 'model_provider', 'base_url'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                tool_codex.ToolCodex(dict(self.config, **{name: 'forbidden'}))

    def test_profile_drift_refused_before_model_dispatch(self):
        self.adapter.config['broker_profile_id'] = None
        with self.assertRaisesRegex(ValueError, 'capability changed'):
            self.adapter.binding()

    def test_cli_child_keeps_official_auth_readonly_shell_disabled(self):
        argv = self.adapter._arguments(self.base, self.base / 'spec.json')
        self.assertIn('--ignore-user-config', argv)
        self.assertEqual(argv[argv.index('--sandbox') + 1], 'read-only')
        for item in ('features.shell_tool=false', 'features.unified_exec=false',
                     'mcp_servers.upg_repo.env_vars=[]', 'model_providers.upg_openai_http.requires_openai_auth=true',
                     'model_providers.upg_openai_http.request_max_retries=0',
                     'model_providers.upg_openai_http.stream_max_retries=0'):
            self.assertIn(item, argv)
        self.assertNotIn('repo_finish', ' '.join(argv))
        self.assertFalse(any('API_KEY' in item or 'auth.json' in item for item in argv))

    def test_cli_and_api_instructions_keep_distinct_terminal_protocols(self):
        api = engineering.public_instruction()
        self.assertIn('End with repo_finish alone', api)
        text = self.adapter.public_instruction()
        self.assertNotIn('repo_finish', text)
        self.assertIn('JSON output schema', text)
        self.assertIn('current successful checks', text)
        for instruction in (api, text):
            self.assertIn('initial_paths lists existing files', instruction)
            self.assertIn('exists=false, text=null and sha256=null', instruction)
            self.assertIn('a string replaces the entire file, never a fragment or diff', instruction)

    def test_current_known_pass_is_read_only_no_implicit_validation(self):
        self.complete()
        result, unknown, not_run = self.quality()
        self.assertTrue(result['hard_pass'], result)
        self.assertFalse(unknown)
        self.assertFalse(not_run)
        self.assertEqual(self.executor_calls, 1)

    def test_current_known_failure_is_not_unknown_and_can_be_repaired(self):
        self.checked_ok = False
        self.complete()
        result, unknown, not_run = self.quality(claim='failed')
        self.assertFalse(result['hard_pass'])
        self.assertFalse(unknown)
        self.assertFalse(not_run)
        self.assertIsNone(self.broker.terminal_result)
        self.assertEqual(self.executor_calls, 1)

    def test_missing_validation_is_known_not_run_without_container(self):
        self.edit()
        self.broker.call('repo_status', {})
        result, unknown, not_run = self.quality(claim='failed')
        self.assertFalse(result['hard_pass'])
        self.assertFalse(unknown)
        self.assertTrue(not_run)
        self.assertEqual(self.executor_calls, 0)

    def test_later_edit_makes_verified_old_validation_stale_not_run(self):
        self.complete()
        read = self.broker.call('repo_read', {'paths': ['README.md']})
        self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': read['files']['README.md']['sha256'], 'new_text': 'new docs\n'}]})
        self.broker.call('repo_status', {})
        result, unknown, not_run = self.quality(claim='failed')
        self.assertFalse(result['hard_pass'])
        self.assertFalse(unknown)
        self.assertTrue(not_run)
        self.assertEqual(self.executor_calls, 1)

    def test_tampered_receipt_sets_unknown_without_second_execution(self):
        self.complete()
        self.integrity_ok = False
        result, unknown, not_run = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertTrue(unknown)
        self.assertFalse(not_run)
        self.assertEqual(self.executor_calls, 1)

    def test_deleted_path_restored_only_by_confirmed_journal_and_actual_disk(self):
        self.complete(delete=True)
        old_journal = canonical(self.broker.events)
        before_paths = set(self.base.rglob('*'))
        restored = engineering.read_broker_receipts(self.repo, self.task, self.git,
            events=self.broker.events, execution_artifacts=self.base / 'execution')
        self.assertNotIn('legacy.py', restored.snapshot())
        self.assertEqual(canonical(self.broker.events), old_journal)
        self.assertEqual(set(self.base.rglob('*')), before_paths)
        result, unknown, not_run = self.quality(restored)
        self.assertTrue(result['hard_pass'], result)
        self.assertFalse(unknown)
        self.assertEqual(self.executor_calls, 1)
        with self.assertRaisesRegex(ValueError, 'receipt view cannot'):
            restored.validate()
        with self.assertRaisesRegex(ValueError, 'receipt view cannot'):
            restored.call('repo_status', {})

    def test_deleted_path_without_chain_or_reappearing_on_disk_refused(self):
        self.complete(delete=True)
        def restore(journal):
            return engineering.read_broker_receipts(self.repo, self.task, self.git,
                events=journal, execution_artifacts=self.base / 'execution')
        with self.assertRaises(ValueError):
            restore([])
        (self.repo / 'legacy.py').write_text('unexpected\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            restore(self.broker.events)

    def test_tampered_journal_previous_hash_result_or_order_refused(self):
        self.complete(delete=True)
        variants = []
        bad = copy.deepcopy(self.broker.events)
        bad[1]['arguments']['operations'][0]['old_sha256'] = 'f' * 64
        bad[1]['arguments_sha256'] = sha(canonical(bad[1]['arguments']))
        variants.append(bad)
        bad = copy.deepcopy(self.broker.events)
        bad[0]['result']['files']['legacy.py']['text'] = 'invented old bytes\n'
        bad[0]['result_sha256'] = sha(canonical(bad[0]['result']))
        variants.append(bad)
        bad = copy.deepcopy(self.broker.events)
        bad[1]['result']['files']['legacy.py']['previous_sha256'] = 'e' * 64
        bad[1]['result_sha256'] = sha(canonical(bad[1]['result']))
        variants.append(bad)
        bad = copy.deepcopy(self.broker.events)
        bad.reverse()
        variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad[0]['tool']), self.assertRaises(ValueError):
                engineering.read_broker_receipts(self.repo, self.task, self.git,
                    events=bad, execution_artifacts=self.base / 'execution')

    def test_cli_order_and_result_content_must_match_not_just_argument_counter(self):
        self.complete()
        for mutate in ('reverse', 'result', 'missing-result', 'extra', 'foreign'):
            events = events_for(self.broker.events)
            if mutate == 'reverse': events.reverse()
            elif mutate == 'result': events[0]['item']['result']['content'][0]['text'] = '{}'
            elif mutate == 'missing-result': events[0]['item'].pop('result')
            elif mutate == 'extra': events.append(copy.deepcopy(events[0]))
            else: events[0]['item']['server'] = 'ambient'
            with self.subTest(mutate=mutate):
                result, _, _ = self.quality(events=events)
                self.assertFalse(result['hard_pass'])
                self.assertFalse(result['scope_ok'])

    def test_strict_cli_json_rejects_duplicate_nonfinite_and_ambiguous_status(self):
        for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool_codex._project_cli_json(value)
        self.complete()
        for kind in ('status', 'id', 'error', 'structured', 'duplicate-result-json'):
            events = events_for(self.broker.events)
            first = events[0]['item']
            if kind == 'status': first['status'] = 'failed'
            elif kind == 'id': first['id'] = False
            elif kind == 'error': first['error'] = {'message': 'tool connection failed'}
            elif kind == 'structured': first['result']['structured_content'] = {}
            else: first['result']['content'][0]['text'] = '{"ok":false,"ok":true}'
            with self.subTest(kind=kind):
                result, _, _ = self.quality(events=events)
                self.assertFalse(result['hard_pass'])

    def test_scope_refusal_cannot_be_hidden_by_later_passing_project_checks(self):
        refused = self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/__init__.py', 'old_sha256': sha(b''), 'new_text': 'wrong\n'}]})
        self.assertFalse(refused['ok'])
        self.complete()
        result, _, _ = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertIn('scope-invalid:cli-project-tool-refused', result['failures'])

    def test_registered_large_read_wire_is_not_capped_at_single_file_json_size(self):
        value = {'ok': True, 'files': {'a.txt': {'text': 'a' * 65536, 'sha256': '1' * 64}}}
        raw = canonical(value)
        self.assertGreater(len(raw), 65536)
        self.assertEqual(tool_codex._project_cli_json(raw), value)

    def test_cli_trace_never_calls_api_quality_or_fabricates_api_chain(self):
        self.complete()
        with mock.patch('evolution.provider_tools._api_quality', side_effect=AssertionError('API grader forbidden')):
            result, _, _ = self.quality()
        self.assertTrue(result['hard_pass'], result)
        self.assertNotIn('api_tool_trace', result)

    def bindings(self):
        result = {name: 'mock-' + name for name in ('campaign_id', 'sample_id', 'protocol_sha256',
            'source_sha256', 'runtime_sha256', 'candidate_sha256')}
        result['capability'] = self.adapter.binding()
        return result

    def fake_cli(self, argv, **kwargs):
        if argv[0] == str(self.git):
            return subprocess.CompletedProcess(argv, 0, b' M pkg/core.py\n', b'')
        self.mock_cli_calls = getattr(self, 'mock_cli_calls', 0) + 1
        directory = Path(argv[argv.index('--cd') + 1]).parent
        spec = json.loads((directory / 'broker.spec.json').read_text(encoding='utf-8'))
        self.assertEqual(spec['broker_profile_id'], engineering.PROFILE_ID)
        self.assertEqual(Path(spec['execution_artifacts']), directory / 'execution')
        broker = engineering.create_broker(spec['workspace'], spec['task'], spec['git_binary'],
            audit_file=spec['audit_file'], max_calls=spec['max_tool_calls'], deadline=spec['deadline'],
            execution_artifacts=spec['execution_artifacts'])
        read = broker.call('repo_read', {'paths': ['pkg/core.py', 'legacy.py']})
        broker.call('repo_patch', {'operations': [
            {'path': 'pkg/core.py', 'old_sha256': read['files']['pkg/core.py']['sha256'], 'new_text': 'VALUE = 1\n'},
            {'path': 'legacy.py', 'old_sha256': read['files']['legacy.py']['sha256'], 'new_text': None}]})
        if not getattr(self, 'omit_validation', False):
            broker.call('repo_validate', {})
        broker.call('repo_status', {})
        events = [{'type': 'thread.started', 'thread_id': 'mock-project-thread'}] + events_for(broker.events)
        events += [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps({
            'summary': 'Mock project check only.', 'validation': 'passed' if self.checked_ok and not getattr(self, 'omit_validation', False) else 'failed',
            'helper_gap': 'project_tool unavailable in bounded broker'})}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'output_tokens': 10}}]
        return subprocess.CompletedProcess(argv, 0, b'\n'.join(canonical(e) for e in events), b'')

    def test_whole_mock_cli_turn_preserves_tombstones_cost_receipt_and_cache_without_reexecution(self):
        bindings = self.bindings()
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            result = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            self.assertTrue(result['quality']['hard_pass'], result['quality'])
            self.assertEqual(result['usage']['total_tokens'], 110)
            self.assertEqual(result['receipt']['application_execution'], 'registered-stdlib-project-fixed-container-recipes')
            self.assertFalse(result['receipt']['replayed_from_local_receipt'])
            again = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            self.assertTrue(again['receipt']['replayed_from_local_receipt'])
        self.assertEqual(self.mock_cli_calls, 1)
        self.assertEqual(self.executor_calls, 1)
        self.assertNotIn('api_tool_trace', result)

    def test_whole_mock_cli_missing_validation_is_completed_known_failure_not_execution(self):
        self.omit_validation = True
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            result = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=self.bindings())
        self.assertFalse(result['quality']['hard_pass'])
        self.assertFalse(result['quality']['execution_state_unknown'])
        self.assertIsNone(result['quality']['validation'])
        self.assertEqual(result['quality']['final_execution_not_run_reason'], 'required-current-project-validation-missing')
        self.assertEqual(self.executor_calls, 0)
        self.assertEqual(result['quality']['checks_total'], 1)
        self.assertEqual(self.mock_cli_calls, 1)

    def test_whole_mock_cli_unknown_keeps_known_usage_and_persistent_no_replay_fence(self):
        self.integrity_ok = False
        bindings = self.bindings()
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            with self.assertRaises(tool_codex.ToolCallError) as caught:
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            self.assertEqual(caught.exception.usage['total_tokens'], 110)
            self.assertTrue((self.base / 'calls/UNKNOWN_CALL.json').is_file())
            with self.assertRaises(tool_codex.ToolCallPending):
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
        self.assertEqual(self.mock_cli_calls, 1)
        self.assertEqual(self.executor_calls, 1)

    def test_ambiguous_raw_cli_event_is_unknown_with_known_usage_preserved(self):
        def ambiguous(argv, **kwargs):
            result = self.fake_cli(argv, **kwargs)
            if argv[0] == str(self.binary):
                result.stdout += b'\n{"type":"item.completed","type":"item.completed"}'
            return result
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=ambiguous):
            with self.assertRaises(tool_codex.ToolCallError) as caught:
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=self.bindings())
        self.assertEqual(caught.exception.usage['total_tokens'], 110)
        self.assertTrue((self.base / 'calls/UNKNOWN_CALL.json').is_file())

    def test_cached_execution_raw_drift_is_refused_without_model_or_container_replay(self):
        bindings = self.bindings()
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            result = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            directory = Path(result['receipt']['artifact_directory'])
            (directory / 'execution/validation-001/result.json').write_bytes(b'{}')
            with self.assertRaises(tool_codex.ToolCallPending):
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
        self.assertEqual(self.mock_cli_calls, 1)
        self.assertEqual(self.executor_calls, 1)

    def test_mcp_profile_lists_engineering_schema_without_running_validation(self):
        # Pure stdio in-memory transport, not a spawned MCP process.
        import io
        class Stream:
            def __init__(self, value=b''): self.buffer = io.BytesIO(value)
        spec = {'workspace': str(self.repo), 'task': self.task, 'git_binary': str(self.git),
            'audit_file': str(self.base / 'stdio-audit.jsonl'), 'max_tool_calls': 32,
            'deadline': time.time() + 60, 'execution_artifacts': str(self.base / 'mcp-execution'),
            'broker_profile_id': 'stdlib-python-project-v1'}
        path = self.base / 'mcp-spec.json'
        path.write_bytes(canonical(spec))
        stdin = Stream(canonical({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}) + b'\n')
        stdout = Stream()
        with mock.patch.object(tool_broker.sys, 'stdin', stdin), mock.patch.object(tool_broker.sys, 'stdout', stdout):
            tool_broker.serve(path)
        result = json.loads(stdout.buffer.getvalue())['result']['tools']
        self.assertEqual(result, engineering.tool_definitions())
        self.assertEqual(self.executor_calls, 0)

    def run_mcp_calls(self, calls):
        import io
        class Stream:
            def __init__(self, value=b''): self.buffer = io.BytesIO(value)
        spec = {'workspace': str(self.repo), 'task': self.task, 'git_binary': str(self.git),
            'audit_file': str(self.base / 'stdio-audit.jsonl'), 'max_tool_calls': 32,
            'deadline': time.time() + 60, 'execution_artifacts': str(self.base / 'mcp-execution'),
            'broker_profile_id': 'stdlib-python-project-v1'}
        path = self.base / 'mcp-spec.json'
        path.write_bytes(canonical(spec))
        raw = b'\n'.join(canonical({'jsonrpc': '2.0', 'id': number, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments}}) for number, (name, arguments) in enumerate(calls, 1)) + b'\n'
        stdin, stdout = Stream(raw), Stream()
        with mock.patch.object(tool_broker.sys, 'stdin', stdin), mock.patch.object(tool_broker.sys, 'stdout', stdout):
            tool_broker.serve(path)
        return [json.loads(line) for line in stdout.buffer.getvalue().splitlines()]

    def test_mcp_known_unchanged_fragment_refusal_keeps_registered_correction_available(self):
        original = self.task['initial_files']['pkg/core.py']
        digest = sha(original.encode('utf-8'))
        responses = self.run_mcp_calls([
            ('repo_read', {'paths': ['pkg/core.py']}),
            ('repo_patch', {'operations': [{'path': 'pkg/core.py', 'old_sha256': digest,
                'old_text': 'ABSENT_FRAGMENT', 'new_text': '3'}]}),
            ('repo_read', {'paths': ['pkg/core.py']}),
            ('repo_patch', {'operations': [{'path': 'pkg/core.py', 'old_sha256': digest,
                'old_text': '0', 'new_text': '3'}]}),
            ('repo_status', {})])
        self.assertEqual(len(responses), 5)
        values = [json.loads(row['result']['content'][0]['text']) for row in responses]
        self.assertEqual(values[1], {'ok': False, 'error': 'ValueError: old_text must occur exactly once in the current file'})
        self.assertTrue(responses[1]['result']['isError'])
        self.assertTrue(all(values[n]['ok'] for n in (0, 2, 3, 4)))
        self.assertEqual(values[2]['files']['pkg/core.py']['text'], original)
        journal = [json.loads(line) for line in (self.base / 'stdio-audit.jsonl').read_bytes().splitlines()]
        self.assertEqual([row['sequence'] for row in journal], [1, 2, 3, 4, 5])
        self.assertEqual(journal[1]['state_sha256'], journal[0]['state_sha256'])
        expected = dict(self.task['initial_files'], **{'pkg/core.py': 'VALUE = 3\n'})
        self.assertEqual(engineering.files_from_receipt_journal(self.task, journal), expected)
        self.assertEqual((self.repo / 'pkg/core.py').read_bytes(), b'VALUE = 3\n')
        self.assertEqual(self.executor_calls, 0)

    def test_mcp_closes_broker_after_scope_refusal_without_second_tool_call(self):
        responses = self.run_mcp_calls([
            ('repo_patch', {'operations': [{'path': 'pkg/__init__.py', 'old_sha256': sha(b''), 'new_text': 'wrong\n'}]}),
            ('repo_read', {'paths': ['pkg/core.py']})])
        self.assertEqual(len(responses), 1)
        self.assertTrue(responses[0]['result']['isError'])
        self.assertEqual(self.executor_calls, 0)

    def test_mcp_absent_creatable_read_keeps_next_registered_call_available(self):
        self.task['writable_files'].append('pkg/new.py')
        responses = self.run_mcp_calls([
            ('repo_read', {'paths': ['pkg/core.py', 'pkg/new.py']}),
            ('repo_read', {'paths': ['README.md']})])
        self.assertEqual(len(responses), 2)
        for response in responses:
            self.assertFalse(response['result']['isError'])
        feedback = json.loads(responses[0]['result']['content'][0]['text'])
        self.assertEqual(feedback['files']['pkg/new.py'], {'exists': False, 'text': None, 'sha256': None})
        events = [json.loads(line) for line in (self.base / 'stdio-audit.jsonl').read_bytes().splitlines()]
        self.assertEqual(len(events), 2)
        self.assertEqual(engineering.files_from_receipt_journal(self.task, events), self.task['initial_files'])
        self.assertFalse((self.repo / 'pkg/new.py').exists())
        self.assertEqual(self.executor_calls, 0)

    def test_mcp_optional_fragment_keeps_same_tool_and_replays_complete_bytes(self):
        operation = {'path': 'pkg/core.py', 'old_sha256': sha(b'VALUE = 0\n'), 'old_text': '0', 'new_text': '3'}
        responses = self.run_mcp_calls([
            ('repo_read', {'paths': ['pkg/core.py']}),
            ('repo_patch', {'operations': [operation]}),
            ('repo_read', {'paths': ['pkg/core.py']})])
        self.assertEqual(len(responses), 3)
        self.assertTrue(all(not row['result']['isError'] for row in responses))
        self.assertEqual((self.repo / 'pkg/core.py').read_bytes(), b'VALUE = 3\n')
        events = [json.loads(line) for line in (self.base / 'stdio-audit.jsonl').read_bytes().splitlines()]
        self.assertEqual(events[1]['arguments']['operations'], [operation])
        self.assertEqual(engineering.files_from_receipt_journal(self.task, events)['pkg/core.py'], 'VALUE = 3\n')
        self.assertEqual(self.executor_calls, 0)

    def test_mcp_keeps_known_test_failure_repairable_without_reclassifying_unknown(self):
        self.checked_ok = False
        responses = self.run_mcp_calls([
            ('repo_validate', {}), ('repo_read', {'paths': ['pkg/core.py']})])
        self.assertEqual(len(responses), 2)
        self.assertTrue(responses[0]['result']['isError'])
        self.assertFalse(responses[1]['result']['isError'])
        self.assertEqual(self.executor_calls, 1)

    def install_typed_diagnostics(self):
        diagnostic = {'id': 'unit', 'recipe': 'unittest', 'exit_code': 1,
            'timeout': False, 'truncated': False, 'completed': False,
            'stdout': '', 'stdout_sha256': sha(b''), 'stdout_bytes': 0,
            'stderr': 'failure\n', 'stderr_sha256': sha(b'failure\n'), 'stderr_bytes': 8}
        original = self.read_receipt
        def reader(*args, **kwargs):
            checked, receipt, digest = original(*args, **kwargs)
            checked['diagnostics'] = [] if checked['ok'] else [copy.deepcopy(diagnostic)]
            return checked, receipt, digest
        patch = mock.patch.object(project_executor, 'read_project_receipt', side_effect=reader)
        patch.start()
        self.addCleanup(patch.stop)

    def mutate_record_diagnostic_types(self, event):
        for key in ('timeout', 'truncated', 'completed'):
            event['result']['diagnostics'][0][key] = 0
        event['result_sha256'] = sha(canonical(event['result']))

    def replace_cached_result(self, directory, transform):
        path = directory / 'result.json'
        value = json.loads(path.read_bytes())
        transform(value)
        path.write_bytes(canonical(value) + b'\n')
        path = directory / 'receipt.json'
        receipt = json.loads(path.read_bytes())
        receipt['result_sha256'] = sha(canonical(value))
        path.write_bytes(canonical(receipt) + b'\n')

    def test_gate_integer_deletion_rejected_when_reconstructing_confirmed_journal(self):
        self.complete(delete=True)
        event = next(row for row in self.broker.events if row['tool'] == 'repo_patch')
        event['result']['files']['legacy.py']['deleted'] = 1
        event['result_sha256'] = sha(canonical(event['result']))
        with self.assertRaises(ValueError):
            engineering.files_from_receipt_journal(self.task, self.broker.events)
        self.assertEqual(self.executor_calls, 1)

    def test_gate_integer_deletion_in_stale_history_becomes_unknown(self):
        self.complete(delete=True)
        event = next(row for row in self.broker.events if row['tool'] == 'repo_patch')
        event['result']['files']['legacy.py']['deleted'] = 1
        event['result_sha256'] = sha(canonical(event['result']))
        read = self.broker.call('repo_read', {'paths': ['README.md']})
        self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': read['files']['README.md']['sha256'], 'new_text': 'later docs\n'}]})
        _, _, unknown, not_run = engineering.current_validation_from_receipts(self.broker)
        self.assertTrue(unknown)
        self.assertFalse(not_run)
        self.assertEqual(self.executor_calls, 1)

    def test_gate_integer_deletion_cached_journal_refused_without_replay(self):
        bindings = self.bindings()
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            result = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            directory = Path(result['receipt']['artifact_directory'])
            def change(value):
                event = next(row for row in value['tool_events'] if row['tool'] == 'repo_patch')
                event['result']['files']['legacy.py']['deleted'] = 1
                event['result_sha256'] = sha(canonical(event['result']))
            self.replace_cached_result(directory, change)
            with self.assertRaises(tool_codex.ToolCallPending):
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
        self.assertEqual(self.mock_cli_calls, 1)
        self.assertEqual(self.executor_calls, 1)

    def test_gate_typed_diagnostic_drift_current_is_unknown(self):
        self.install_typed_diagnostics()
        self.checked_ok = False
        self.complete()
        event = next(row for row in self.broker.events if row['tool'] == 'repo_validate')
        self.mutate_record_diagnostic_types(event)
        _, _, unknown, not_run = engineering.current_validation_from_receipts(self.broker)
        self.assertTrue(unknown)
        self.assertFalse(not_run)
        self.assertEqual(self.executor_calls, 1)

    def test_gate_typed_diagnostic_drift_stale_is_unknown(self):
        self.install_typed_diagnostics()
        self.checked_ok = False
        self.complete()
        event = next(row for row in self.broker.events if row['tool'] == 'repo_validate')
        self.mutate_record_diagnostic_types(event)
        read = self.broker.call('repo_read', {'paths': ['README.md']})
        self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': read['files']['README.md']['sha256'], 'new_text': 'later docs\n'}]})
        _, _, unknown, not_run = engineering.current_validation_from_receipts(self.broker)
        self.assertTrue(unknown)
        self.assertFalse(not_run)
        self.assertEqual(self.executor_calls, 1)

    def test_gate_typed_diagnostic_cached_quality_refused_without_replay(self):
        self.install_typed_diagnostics()
        self.checked_ok = False
        bindings = self.bindings()
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            result = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            directory = Path(result['receipt']['artifact_directory'])
            def change(value):
                for key in ('timeout', 'truncated', 'completed'):
                    value['quality']['validation']['diagnostics'][0][key] = 0
            self.replace_cached_result(directory, change)
            with self.assertRaises(tool_codex.ToolCallPending):
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
        self.assertEqual(self.mock_cli_calls, 1)
        self.assertEqual(self.executor_calls, 1)

    def test_gate_historical_severe_validation_cannot_be_compensated_by_later_pass(self):
        self.edit()
        self.checked_ok = False
        self.broker.call('repo_validate', {})
        historical = self.broker.events[-1]
        self.checked_ok = True
        self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})
        original = copy.deepcopy(historical['result'])
        for kind in ('scope', 'protected', 'partial', 'unknown', 'unregistered-failure'):
            historical['result'] = copy.deepcopy(original)
            if kind == 'scope': historical['result']['failures'] = ['scope-invalid:historical-observed-violation']
            elif kind == 'protected': historical['result']['failures'] = ['protected-file-changed:pkg/__init__.py']
            elif kind == 'partial': historical['result']['write_state'] = 'partial'
            elif kind == 'unknown': historical['result']['execution']['unknown'] = True
            else: historical['result']['failures'] = ['unregistered-failure']
            historical['result_sha256'] = sha(canonical(historical['result']))
            with self.subTest(kind=kind):
                result, _, _ = self.quality()
                self.assertFalse(result['hard_pass'], result)
                self.assertFalse(result['scope_ok'], result)
        self.assertEqual(self.executor_calls, 2)

    def test_gate_historical_registered_failure_can_be_repaired_without_implicit_execution(self):
        self.edit()
        self.checked_ok = False
        self.broker.call('repo_validate', {})
        self.checked_ok = True
        self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})
        result, unknown, not_run = self.quality()
        self.assertTrue(result['hard_pass'], result)
        self.assertFalse(unknown)
        self.assertFalse(not_run)
        self.assertEqual(self.executor_calls, 2)

    def test_gate_mcp_closes_after_observed_scope_validation_failure(self):
        original = self.read_receipt
        def reader(*args, **kwargs):
            checked, receipt, digest = original(*args, **kwargs)
            checked.update(ok=False, checks_passed=0, failures=['scope-invalid:observed-snapshot-violation'])
            return checked, receipt, digest
        with mock.patch.object(project_executor, 'read_project_receipt', side_effect=reader):
            responses = self.run_mcp_calls([('repo_validate', {}), ('repo_read', {'paths': ['pkg/core.py']})])
        self.assertEqual(len(responses), 1)
        self.assertEqual(self.executor_calls, 1)

    def fake_cli_with_historical_scope_failure(self, argv, **kwargs):
        result = self.fake_cli(argv, **kwargs)
        if argv[0] != str(self.binary):
            return result
        directory = Path(argv[argv.index('--cd') + 1]).parent
        path = directory / 'broker.jsonl'
        journal = [json.loads(line) for line in path.read_bytes().splitlines()]
        index = next(i for i, row in enumerate(journal) if row['tool'] == 'repo_validate')
        historical = copy.deepcopy(journal[index])
        # An invented second repo_validate cannot reuse a passing receipt.
        # This known scope refusal has no project execution; its noncompensable
        # cache intent is unchanged, while all real validations stay complete.
        historical['tool'] = 'repo_read'
        historical['arguments'] = {'paths': ['not-registered.txt']}
        historical['arguments_sha256'] = sha(canonical(historical['arguments']))
        historical['result'] = {'ok': False, 'error': 'scope-invalid:unregistered-read'}
        historical['result_sha256'] = sha(canonical(historical['result']))
        journal.insert(index, historical)
        for n, row in enumerate(journal, 1): row['sequence'] = n
        path.write_bytes(b''.join(canonical(row) + b'\n' for row in journal))
        original = [json.loads(line) for line in result.stdout.splitlines()]
        events = [original[0]] + events_for(journal) + original[-2:]
        result.stdout = b'\n'.join(canonical(row) for row in events)
        return result

    def test_gate_cached_historical_severe_failure_cannot_be_erased_by_editing_quality(self):
        bindings = self.bindings()
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli_with_historical_scope_failure):
            result = self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
            directory = Path(result['receipt']['artifact_directory'])
            def change(value):
                value['quality'].update(hard_pass=True, task_success=1, scope_ok=True, failures=[])
            self.replace_cached_result(directory, change)
            with self.assertRaises(tool_codex.ToolCallPending):
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)
        self.assertEqual(self.mock_cli_calls, 1)
        self.assertEqual(self.executor_calls, 1)


@unittest.skipUnless(SUPPORTED, 'repository engine requires Python3.10+')
class HistoricalProjectReceiptTests(unittest.TestCase):
    """Real pure receipt reader with synthetic Docker observations, never CPython execution."""
    def setUp(self):
        from test_project_executor import FakeDocker, FILES, CONTRACT
        self.FakeDocker = FakeDocker
        self.source_b = FILES['sample_pkg/core.py']
        self.source_a = self.source_b.replace('sum(values)', 'sum(values) + 1')
        initial = copy.deepcopy(FILES)
        initial['sample_pkg/core.py'] = self.source_b.replace('sum(values)', '0')
        self.task = {'id': 'synthetic-history-repair', 'family': 'pure-receipt-bookkeeping',
            'prompt': 'Repair the registered core with complete historical execution evidence.',
            'initial_files': initial, 'writable_files': ['sample_pkg/core.py'],
            'required_read_paths': ['sample_pkg/core.py'],
            'required_tools': ['repo_read', 'repo_patch', 'repo_validate', 'repo_status'],
            'engineering_contract': copy.deepcopy(CONTRACT)}
        temp = tempfile.TemporaryDirectory(prefix='upg-cli-history-pure-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.binary, self.git = self.base / 'codex.exe', self.base / 'mock-git.exe'
        self.host = self.base / ('codex-code-mode-host.exe' if os.name == 'nt' else 'codex-code-mode-host')
        for path in (self.binary, self.git, self.host): path.write_bytes(b'pure mock executable never started')
        self.config = {'binary': str(self.binary), 'code_mode_host_binary': str(self.host),
            'git_binary': str(self.git), 'model': 'explicit-mock-only', 'effort': 'low',
            'artifact_root': str(self.base / 'calls'), 'timeout_seconds': 180,
            'broker_profile_id': 'stdlib-python-project-v1', 'max_tool_calls': 32}
        self.adapter = tool_codex.ToolCodex(self.config)
        self.bindings = {name: 'mock-' + name for name in ('campaign_id', 'sample_id', 'protocol_sha256',
            'source_sha256', 'runtime_sha256', 'candidate_sha256')}
        self.bindings['capability'] = self.adapter.binding()
        self.execute_calls, self.cli_calls, self.reader_observations = [], 0, []
        execute = project_executor.execute_project
        read = project_executor.read_project_receipt
        def synthetic_execute(files, contract, directory, seconds):
            mode = 'assertion' if not self.execute_calls else None
            self.execute_calls.append({'path': str(directory), 'files': copy.deepcopy(files)})
            fake = self.FakeDocker(mode)
            with mock.patch.object(project_executor, '_capture', fake):
                return execute(files, contract, directory, seconds)
        def observed_reader(files, contract, directory, receipt_sha256=None):
            self.reader_observations.append({'path': str(directory), 'files': copy.deepcopy(files)})
            return read(files, contract, directory, receipt_sha256=receipt_sha256)
        patches = [mock.patch.object(project_executor, 'execute_project', side_effect=synthetic_execute),
            mock.patch.object(project_executor, 'read_project_receipt', side_effect=observed_reader),
            mock.patch.object(tool_broker, 'git_command', return_value=subprocess.CompletedProcess([], 0, b' M sample_pkg/core.py\n', b''))]
        patches += [mock.patch.object(subprocess, key, side_effect=AssertionError('actual process forbidden'))
                    for key in ('run', 'Popen', 'call', 'check_call', 'check_output')]
        patches += [mock.patch.object(socket, key, side_effect=AssertionError('network forbidden'))
                    for key in ('socket', 'create_connection')]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def fake_cli(self, argv, **kwargs):
        if argv[0] == str(self.git):
            return subprocess.CompletedProcess(argv, 0, b' M sample_pkg/core.py\n', b'')
        self.cli_calls += 1
        self.directory = Path(argv[argv.index('--cd') + 1]).parent
        spec = json.loads((self.directory / 'broker.spec.json').read_bytes())
        self.broker = engineering.create_broker(spec['workspace'], spec['task'], spec['git_binary'],
            audit_file=spec['audit_file'], max_calls=spec['max_tool_calls'], deadline=spec['deadline'],
            execution_artifacts=spec['execution_artifacts'])
        for source in (self.source_a, self.source_b):
            observed = self.broker.call('repo_read', {'paths': ['sample_pkg/core.py']})
            patch = self.broker.call('repo_patch', {'operations': [{'path': 'sample_pkg/core.py',
                'old_sha256': observed['files']['sample_pkg/core.py']['sha256'], 'new_text': source}]})
            self.assertTrue(patch['ok'], patch)
            self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})
        events = [{'type': 'thread.started', 'thread_id': 'mock-two-validation-thread'}] + events_for(self.broker.events)
        events += [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps({
            'summary': 'Synthetic command observations with the real pure receipt reader.',
            'validation': 'passed', 'helper_gap': 'project_tool unavailable in bounded broker'})}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 100, 'output_tokens': 10}}]
        return subprocess.CompletedProcess(argv, 0, b'\n'.join(canonical(event) for event in events), b'')

    def run_turn(self):
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            return self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=self.bindings)

    def reuse(self, bindings=None):
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.fake_cli):
            return self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings or self.bindings)

    def assert_known_usage_fenced(self, error, original_receipt, original_result):
        self.assertEqual(error.usage['total_tokens'], 110)
        self.assertIsNotNone(error.provider_receipt)
        self.assertTrue((self.base / 'calls/UNKNOWN_CALL.json').is_file())
        self.assertTrue((self.directory / 'cache-unknown-observation.json').is_file())
        self.assertEqual((self.directory / 'receipt.json').read_bytes(), original_receipt)
        self.assertEqual((self.directory / 'result.json').read_bytes(), original_result)
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)
        with self.assertRaises(tool_codex.ToolCallPending):
            self.reuse(dict(self.bindings, sample_id='another-never-dispatched-sample'))
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)

    def test_history_complete_failure_then_repair_cache_reads_both_original_snapshots(self):
        result = self.run_turn()
        self.assertTrue(result['quality']['hard_pass'], result['quality'])
        records = [row for row in self.broker.events if row['tool'] == 'repo_validate']
        self.assertFalse(records[0]['result']['ok'])
        self.assertTrue(records[1]['result']['ok'])
        self.assertNotEqual(records[0]['state_sha256'], records[1]['state_sha256'])
        self.reader_observations.clear()
        again = self.reuse()
        self.assertTrue(again['quality']['hard_pass'])
        self.assertTrue(again['receipt']['replayed_from_local_receipt'])
        self.assertEqual([Path(item['path']).name for item in self.reader_observations], ['validation-001', 'validation-002'])
        self.assertEqual(self.reader_observations[0]['files']['sample_pkg/core.py'], self.source_a)
        self.assertEqual(self.reader_observations[1]['files']['sample_pkg/core.py'], self.source_b)
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)

    def test_history_missing_old_receipt_fences_cache_and_retains_original_usage(self):
        self.run_turn()
        old_receipt = (self.directory / 'receipt.json').read_bytes()
        old_result = (self.directory / 'result.json').read_bytes()
        (self.directory / 'execution/validation-001/result.json').unlink()
        with self.assertRaises(tool_codex.ToolCallPending) as caught:
            self.reuse()
        self.assert_known_usage_fenced(caught.exception, old_receipt, old_result)

    def test_history_changed_old_stream_fences_cache_and_retains_original_usage(self):
        self.run_turn()
        old_receipt = (self.directory / 'receipt.json').read_bytes()
        old_result = (self.directory / 'result.json').read_bytes()
        path = self.directory / 'execution/validation-001/04-start-attach.stderr.raw'
        path.write_bytes(path.read_bytes() + b'drift\n')
        with self.assertRaises(tool_codex.ToolCallPending) as caught:
            self.reuse()
        self.assert_known_usage_fenced(caught.exception, old_receipt, old_result)

    def test_history_all_eight_fixed_command_streams_are_read_before_success(self):
        self.run_turn()
        root = self.directory / 'execution/validation-001'
        streams = sorted(root.glob('*.stderr.raw'))
        self.assertEqual(len(streams), 8)
        for path in streams:
            original = path.read_bytes()
            path.write_bytes(original + b'drift\n')
            try:
                with self.subTest(stream=path.name):
                    _, _, unknown, not_run = engineering.current_validation_from_receipts(self.broker)
                    self.assertTrue(unknown)
                    self.assertFalse(not_run)
            finally:
                # Mutable unit fixture only, never a registered result round.
                path.write_bytes(original)
        self.assertEqual(len(self.execute_calls), 2)

    def test_history_count_type_or_summary_drift_is_unknown_after_later_pass(self):
        self.run_turn()
        event = next(row for row in self.broker.events if row['tool'] == 'repo_validate')
        original = copy.deepcopy(event['result'])
        for kind in ('count', 'runner', 'cleanup'):
            event['result'] = copy.deepcopy(original)
            if kind == 'count': event['result']['checks_passed'] = float(event['result']['checks_passed'])
            elif kind == 'runner': event['result']['execution']['runner_sha256'] = 'f' * 64
            else: event['result']['execution']['scratch_removed'] = False
            event['result_sha256'] = sha(canonical(event['result']))
            with self.subTest(kind=kind):
                _, _, unknown, not_run = engineering.current_validation_from_receipts(self.broker)
                self.assertTrue(unknown)
                self.assertFalse(not_run)
        self.assertEqual(len(self.execute_calls), 2)

    def test_history_drift_before_initial_quality_is_unknown_with_known_usage(self):
        def changed(argv, **kwargs):
            result = self.fake_cli(argv, **kwargs)
            if argv[0] == str(self.binary):
                path = self.directory / 'execution/validation-001/04-start-attach.stderr.raw'
                path.write_bytes(path.read_bytes() + b'drift\n')
            return result
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=changed):
            with self.assertRaises(tool_codex.ToolCallError) as caught:
                self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=self.bindings)
        self.assertEqual(caught.exception.usage['total_tokens'], 110)
        self.assertTrue((self.base / 'calls/UNKNOWN_CALL.json').is_file())
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)

    def test_history_cache_unknown_io_failure_retains_existing_lock_and_usage(self):
        self.run_turn()
        original_receipt = (self.directory / 'receipt.json').read_bytes()
        original_result = (self.directory / 'result.json').read_bytes()
        (self.directory / 'execution/validation-001/result.json').unlink()
        atomic = tool_codex._atomic
        def denied(path, value):
            if Path(path).name == 'cache-unknown-observation.json':
                raise OSError('synthetic cache observation I/O failure')
            return atomic(path, value)
        with mock.patch.object(tool_codex, '_atomic', side_effect=denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assertEqual(caught.exception.usage['total_tokens'], 110)
        self.assertIn('fence_persistence_error', caught.exception.provider_receipt)
        self.assertTrue((self.base / 'calls/.tool-dispatch.lock').is_file())
        self.assertEqual((self.directory / 'receipt.json').read_bytes(), original_receipt)
        self.assertEqual((self.directory / 'result.json').read_bytes(), original_result)
        with self.assertRaises(tool_codex.ToolCallPending):
            self.reuse(dict(self.bindings, sample_id='another-never-dispatched-sample'))
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)

    def assert_cache_fault_is_fenced(self, error, original_receipt, original_result, *, loaded_usage):
        self.assertIsInstance(error, tool_codex.ToolCallPending)
        if loaded_usage:
            self.assertEqual(error.usage['total_tokens'], 110)
        else:
            self.assertIsNone(error.usage)
        self.assertIsNotNone(error.provider_receipt)
        self.assertEqual(error.provider_receipt['usage'], error.usage)
        self.assertTrue((self.base / 'calls/.tool-dispatch.lock').is_file())
        self.assertEqual((self.directory / 'receipt.json').read_bytes(), original_receipt)
        self.assertEqual((self.directory / 'result.json').read_bytes(), original_result)
        with self.assertRaises(tool_codex.ToolCallPending):
            self.reuse(dict(self.bindings, sample_id='blocked-after-cache-fault'))
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)

    def cache_fault_setup(self):
        self.run_turn()
        original_receipt = (self.directory / 'receipt.json').read_bytes()
        original_result = (self.directory / 'result.json').read_bytes()
        (self.directory / 'execution/validation-001/result.json').unlink()
        return original_receipt, original_result

    def test_cache_boundary_old_unknown_receipt_reread_is_eliminated(self):
        original_receipt, original_result = self.cache_fault_setup()
        target = self.directory / 'receipt.json'
        actual = Path.read_bytes
        calls = []
        def fail_reread(path):
            if path == target:
                calls.append(str(path))
                raise OSError('synthetic read failure while building unknown observation')
            return actual(path)
        with mock.patch.object(Path, 'read_bytes', fail_reread):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assertEqual(calls, [])
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_first_receipt_read_unknown_usage_is_not_zero(self):
        original_receipt, original_result = self.cache_fault_setup()
        target = self.directory / 'receipt.json'
        actual = Path.open
        def denied(path, *args, **kwargs):
            if path == target:
                raise OSError('synthetic primary receipt read failure')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=False)

    def test_cache_boundary_receipt_parse_unknown_usage_is_not_zero(self):
        original_receipt, original_result = self.cache_fault_setup()
        actual = json.loads
        def rejected(raw, *args, **kwargs):
            if isinstance(raw, str) and raw == original_receipt.decode('utf-8'):
                raise json.JSONDecodeError('synthetic receipt parser failure', raw, 0)
            return actual(raw, *args, **kwargs)
        with mock.patch.object(json, 'loads', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=False)

    def test_cache_boundary_receipt_digest_failure_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        actual = tool_codex.sha
        def rejected(raw):
            if raw == original_receipt:
                raise RuntimeError('synthetic receipt digest failure')
            return actual(raw)
        with mock.patch.object(tool_codex, 'sha', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_later_result_read_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        target = self.directory / 'result.json'
        actual = Path.read_text
        def denied(path, *args, **kwargs):
            if path == target:
                raise OSError('synthetic later result read failure')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_artifact_read_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        target = self.directory / 'stdout.raw'
        actual = Path.read_bytes
        def denied(path):
            if path == target:
                raise OSError('synthetic cached artifact read failure')
            return actual(path)
        with mock.patch.object(Path, 'read_bytes', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_observation_serialization_failure_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        actual = tool_codex.canonical
        def rejected(value):
            if isinstance(value, dict) and value.get('status') == 'cached-project-evidence-unknown':
                raise ValueError('synthetic observation serialization failure')
            return actual(value)
        with mock.patch.object(tool_codex, 'canonical', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_observer_construction_failure_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        with mock.patch.object(self.adapter, '_remember_unknown', side_effect=RuntimeError('synthetic observer construction failure')):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_global_fence_open_failure_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        target = self.base / 'calls/UNKNOWN_CALL.json'
        actual = Path.open
        def denied(path, *args, **kwargs):
            if path == target:
                raise OSError('synthetic global fence write failure')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_global_fence_serialization_failure_preserves_loaded_usage(self):
        original_receipt, original_result = self.cache_fault_setup()
        actual = tool_codex.canonical
        def rejected(value):
            if isinstance(value, dict) and value.get('reason') == 'cached-project-evidence-unknown':
                raise ValueError('synthetic global fence serialization failure')
            return actual(value)
        with mock.patch.object(tool_codex, 'canonical', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse()
        self.assert_cache_fault_is_fenced(caught.exception, original_receipt, original_result, loaded_usage=True)

    def test_cache_boundary_success_reuses_one_receipt_read_and_releases_lock(self):
        self.run_turn()
        target = self.directory / 'receipt.json'
        actual_open, actual_bytes = Path.open, Path.read_bytes
        opens = []
        def observed_open(path, *args, **kwargs):
            if path == target:
                opens.append(args[0] if args else kwargs.get('mode', 'r'))
            return actual_open(path, *args, **kwargs)
        def forbidden_reread(path):
            if path == target:
                raise OSError('successful cache must reuse loaded receipt bytes')
            return actual_bytes(path)
        with mock.patch.object(Path, 'open', observed_open), mock.patch.object(Path, 'read_bytes', forbidden_reread):
            result = self.reuse()
        self.assertTrue(result['quality']['hard_pass'])
        self.assertTrue(result['receipt']['replayed_from_local_receipt'])
        self.assertEqual(opens, ['rb'])
        self.assertFalse((self.base / 'calls/.tool-dispatch.lock').exists())
        self.assertEqual(self.cli_calls, 1)
        self.assertEqual(len(self.execute_calls), 2)

    def assert_prior_call_fault(self, error, owner, original_receipt, original_result, requested_bindings,
                               *, loaded_usage, digest_known=True, expected_turns=1, requested_already_exists=False):
        self.assertIsInstance(error, tool_codex.ToolCallPending)
        observation = error.provider_receipt
        self.assertIsNotNone(observation)
        prior = observation['observed_prior_call']
        self.assertIs(error.observed_prior_call, prior)
        self.assertEqual(prior['kind'], 'observed-prior-cli-call-v1')
        self.assertEqual(prior['call_key'], owner.name)
        self.assertEqual(prior['receipt_ref'], 'calls/' + owner.name + '/receipt.json')
        self.assertEqual(prior['accounting_role'], 'reference-to-existing-turn')
        self.assertIs(prior['count_as_new_charge'], False)
        requested_key = sha(canonical({'task': self.task, 'prompt': self.adapter.public_instruction(),
            'bindings': requested_bindings, 'capability': self.adapter.binding()}))
        matched = owner.name == requested_key
        self.assertEqual(prior['matches_requested_cache_key'], matched)
        self.assertEqual(observation['requested_call_key'], requested_key)
        self.assertEqual(observation['requested_dispatch_state'], 'not_started')
        self.assertIs(observation['cache_check_model_invoked'], False)
        if loaded_usage:
            receipt = json.loads(original_receipt)
            self.assertEqual(prior['reported_usage'], receipt['usage'])
            self.assertEqual(prior['harness_request_id'], receipt['harness_request_id'])
            self.assertEqual(observation['harness_request_id'], receipt['harness_request_id'])
            self.assertEqual(observation['original_completed_result_sha256'], receipt['result_sha256'])
            self.assertEqual(error.usage, receipt['usage'] if matched else None)
        else:
            self.assertIsNone(prior['reported_usage'])
            self.assertIsNone(prior['harness_request_id'])
            self.assertIsNone(error.usage)
        self.assertEqual(prior['receipt_sha256'], sha(original_receipt) if loaded_usage and digest_known else None)
        self.assertEqual(observation['original_completed_receipt_sha256'], prior['receipt_sha256'])
        self.assertTrue((self.base / 'calls/.tool-dispatch.lock').is_file())
        self.assertEqual((owner / 'receipt.json').read_bytes(), original_receipt)
        self.assertEqual((owner / 'result.json').read_bytes(), original_result)
        if not matched and not requested_already_exists:
            self.assertFalse((self.base / 'calls/calls' / requested_key).exists())
        self.assertEqual(self.cli_calls, expected_turns)
        self.assertEqual(len(self.execute_calls), 2 * expected_turns)
        with self.assertRaises(tool_codex.ToolCallPending):
            self.reuse(dict(self.bindings, sample_id='blocked-prior-evidence-retry'))
        self.assertEqual(self.cli_calls, expected_turns)

    def prior_fault_setup(self):
        self.run_turn()
        owner = self.directory
        return owner, (owner / 'receipt.json').read_bytes(), (owner / 'result.json').read_bytes(), dict(self.bindings, sample_id='different-unstarted-key')

    def test_prior_call_different_key_result_read_retains_owner_and_reported_usage(self):
        owner, old_receipt, old_result, requested = self.prior_fault_setup()
        actual = Path.read_text
        def denied(path, *args, **kwargs):
            if path == owner / 'result.json': raise OSError('synthetic prior result read failure')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(requested)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, requested, loaded_usage=True)

    def test_prior_call_different_key_result_parse_retains_owner_and_reported_usage(self):
        owner, old_receipt, old_result, requested = self.prior_fault_setup()
        actual = json.loads
        def rejected(raw, *args, **kwargs):
            if isinstance(raw, str) and raw == old_result.decode('utf-8'):
                raise json.JSONDecodeError('synthetic prior result parser failure', raw, 0)
            return actual(raw, *args, **kwargs)
        with mock.patch.object(json, 'loads', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(requested)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, requested, loaded_usage=True)

    def test_prior_call_different_key_digest_failure_retains_unconfirmed_identity_and_usage(self):
        owner, old_receipt, old_result, requested = self.prior_fault_setup()
        actual = tool_codex.sha
        def rejected(raw):
            if raw == old_receipt: raise RuntimeError('synthetic prior digest failure')
            return actual(raw)
        with mock.patch.object(tool_codex, 'sha', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(requested)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, requested, loaded_usage=True, digest_known=False)

    def test_prior_call_different_key_first_read_keeps_usage_unknown_not_zero(self):
        owner, old_receipt, old_result, requested = self.prior_fault_setup()
        actual = Path.open
        def denied(path, *args, **kwargs):
            if path == owner / 'receipt.json': raise OSError('synthetic unread prior receipt')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(requested)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, requested, loaded_usage=False)

    def test_prior_call_different_key_parse_keeps_usage_unknown_not_zero(self):
        owner, old_receipt, old_result, requested = self.prior_fault_setup()
        actual = json.loads
        def rejected(raw, *args, **kwargs):
            if isinstance(raw, str) and raw == old_receipt.decode('utf-8'):
                raise json.JSONDecodeError('synthetic unreadable prior usage', raw, 0)
            return actual(raw, *args, **kwargs)
        with mock.patch.object(json, 'loads', side_effect=rejected):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(requested)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, requested, loaded_usage=False)

    def test_prior_call_same_key_keeps_existing_cache_usage_and_explicit_no_new_charge(self):
        owner, old_receipt, old_result, _ = self.prior_fault_setup()
        (owner / 'execution/validation-001/result.json').unlink()
        with self.assertRaises(tool_codex.ToolCallPending) as caught:
            self.reuse()
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, self.bindings, loaded_usage=True)

    def test_prior_call_different_key_observer_failure_preserves_reference_and_lock(self):
        owner, old_receipt, old_result, requested = self.prior_fault_setup()
        actual = Path.read_text
        def denied(path, *args, **kwargs):
            if path == owner / 'result.json': raise OSError('synthetic prior evidence unknown')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', denied), mock.patch.object(self.adapter, '_remember_unknown', side_effect=RuntimeError('synthetic observation failure')):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(requested)
        self.assertIn('fence_persistence_error', caught.exception.provider_receipt)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, requested, loaded_usage=True)

    def weighted_cli(self, argv, **kwargs):
        result = self.fake_cli(argv, **kwargs)
        if argv[0] == str(self.binary):
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            rows[-1]['usage'] = {'input_tokens': 100 * self.cli_calls, 'output_tokens': 10 * self.cli_calls}
            result.stdout = b'\n'.join(canonical(row) for row in rows)
        return result

    def weighted_turn(self, bindings):
        with mock.patch.object(tool_codex.subprocess, 'run', side_effect=self.weighted_cli):
            return self.adapter.run(self.task, prompt=self.adapter.public_instruction(), bindings=bindings)

    def test_prior_call_multiple_owners_fault_attribution_is_not_requested_cache_usage(self):
        first = self.run_turn()
        first_owner = self.directory
        second_bindings = dict(self.bindings, sample_id='second-completed-key')
        second = self.weighted_turn(second_bindings)
        owner = self.directory
        old_receipt, old_result = (owner / 'receipt.json').read_bytes(), (owner / 'result.json').read_bytes()
        self.assertEqual(first['usage']['total_tokens'], 110)
        self.assertEqual(second['usage']['total_tokens'], 220)
        self.assertNotEqual(first_owner, owner)
        actual = Path.read_text
        def denied(path, *args, **kwargs):
            if path == owner / 'result.json': raise OSError('synthetic second-owner result failure')
            return actual(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', denied):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                self.reuse(self.bindings)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, self.bindings, loaded_usage=True,
                                    expected_turns=2, requested_already_exists=True)
        self.assertEqual(caught.exception.observed_prior_call['reported_usage']['total_tokens'], 220)
        self.assertNotEqual(caught.exception.observed_prior_call['harness_request_id'], first['receipt']['harness_request_id'])

    def test_prior_call_successful_siblings_do_not_replace_requested_cache_or_double_count(self):
        first = self.run_turn()
        second = self.weighted_turn(dict(self.bindings, sample_id='second-completed-key'))
        cached = self.reuse(self.bindings)
        self.assertTrue(cached['receipt']['replayed_from_local_receipt'])
        self.assertEqual(cached['usage']['total_tokens'], 110)
        self.assertEqual(cached['receipt']['harness_request_id'], first['receipt']['harness_request_id'])
        self.assertNotEqual(cached['receipt']['harness_request_id'], second['receipt']['harness_request_id'])
        by_original_turn = {item['receipt']['harness_request_id']: item['usage']['total_tokens'] for item in (first, second, cached)}
        self.assertEqual(len(by_original_turn), 2)
        self.assertEqual(sum(by_original_turn.values()), 330)
        self.assertEqual(self.cli_calls, 2)
        self.assertEqual(len(self.execute_calls), 4)

    def test_prior_call_requested_cache_fault_restores_owner_after_sibling_checks(self):
        first = self.run_turn()
        owner = self.directory
        old_receipt, old_result = (owner / 'receipt.json').read_bytes(), (owner / 'result.json').read_bytes()
        second = self.weighted_turn(dict(self.bindings, sample_id='other-completed-sibling'))
        self.assertEqual(second['usage']['total_tokens'], 220)
        (owner / 'execution/validation-001/result.json').unlink()
        with self.assertRaises(tool_codex.ToolCallPending) as caught:
            self.reuse(self.bindings)
        self.assert_prior_call_fault(caught.exception, owner, old_receipt, old_result, self.bindings,
                                    loaded_usage=True, expected_turns=2, requested_already_exists=True)
        self.assertEqual(caught.exception.observed_prior_call['harness_request_id'], first['receipt']['harness_request_id'])
        self.assertEqual(caught.exception.usage['total_tokens'], 110)

    def test_prior_call_fresh_dispatch_failure_uses_new_turn_not_prior_usage(self):
        first = self.run_turn()
        requested = dict(self.bindings, sample_id='fresh-current-failed-key')
        with mock.patch.object(self.adapter, '_project_quality', side_effect=ValueError('synthetic new-turn grade failure')):
            with self.assertRaises(tool_codex.ToolCallError) as caught:
                self.weighted_turn(requested)
        self.assertEqual(caught.exception.usage['total_tokens'], 220)
        self.assertNotEqual(caught.exception.provider_receipt['harness_request_id'], first['receipt']['harness_request_id'])
        self.assertFalse(hasattr(caught.exception, 'observed_prior_call'))
        self.assertEqual(self.cli_calls, 2)
        self.assertEqual(len(self.execute_calls), 4)


if __name__ == '__main__':
    unittest.main()
