"""Native failed-tool interoperability: pure receipts, no real CLI/project."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

if sys.version_info < (3, 10):
    raise unittest.SkipTest('repository engine requires Python3.10+')

from evolution import tool_codex, engineering_broker as engineering
from evolution.tool_broker import canonical, sha
import test_engineering_cli as legacy


class NativeFailedValidationTests(unittest.TestCase):
    def setUp(self):
        platform_stub = mock.patch.object(tool_codex.platform, 'platform',
            return_value='synthetic-cli-projection-platform-v1')
        self.addCleanup(platform_stub.stop)
        platform_stub.start()
        self.fixture = legacy.CliProjectCandidateTests(
            'test_whole_mock_cli_turn_preserves_tombstones_cost_receipt_and_cache_without_reexecution')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def turn(self, *, checked_ok=False, mutate=None):
        f = self.fixture
        f.checked_ok = checked_ok
        def fake(argv, **kwargs):
            observed = f.fake_cli(argv, **kwargs)
            if argv[0] == str(f.git):
                return observed
            events = [json.loads(line) for line in observed.stdout.splitlines()]
            for event in events:
                item = event.get('item', {})
                if item.get('type') == 'mcp_tool_call' and item.get('tool') == 'repo_validate':
                    item['status'] = 'failed'
            if mutate is not None:
                mutate(events)
            return subprocess.CompletedProcess(observed.args, observed.returncode,
                b'\n'.join(canonical(event) for event in events), observed.stderr)
        with mock.patch.object(subprocess, 'run', side_effect=fake):
            result = f.adapter.run(f.task, prompt=f.adapter.public_instruction(), bindings=f.bindings())
        directory = Path(result['receipt']['artifact_directory'])
        events = [json.loads(line) for line in (directory / 'stdout.raw').read_bytes().splitlines()]
        return result, directory, events

    def test_failed_known_validation_keeps_scope_but_never_success(self):
        result, _, _ = self.turn()
        self.assertTrue(result['quality']['scope_ok'], result['quality']['failures'])
        self.assertIs(result['quality']['hard_pass'], False)
        self.assertEqual(result['quality']['task_success'], 0)
        self.assertFalse(result['quality']['execution_state_unknown'])
        self.assertIn('project-check-failed:unit', result['quality']['failures'])
        self.assertEqual(result['usage']['total_tokens'], 110)

    def test_failed_status_cannot_label_a_successful_validation(self):
        result, _, _ = self.turn(checked_ok=True)
        self.assertFalse(result['quality']['scope_ok'])
        self.assertFalse(result['quality']['hard_pass'])
        self.assertEqual(result['quality']['task_success'], 0)

    def test_other_failed_tools_are_refused(self):
        result, _, events = self.turn()
        journal = result['tool_events']
        for tool in ('repo_read', 'repo_patch', 'repo_status'):
            changed = copy.deepcopy(events)
            for event in changed:
                item = event.get('item', {})
                if item.get('type') == 'mcp_tool_call' and item.get('tool') == tool:
                    item['status'] = 'failed'
            with self.subTest(tool=tool):
                failures = tool_codex._project_cli_trace_failures(changed, journal, self.fixture.task)
                self.assertIn('scope-invalid:cli-project-mcp-result-unconfirmed', failures)

    def test_failed_envelope_errors_and_wrong_ordinal_are_refused(self):
        result, _, events = self.turn()
        for mode in ('error', 'approval', 'extra-item', 'structured', 'arguments', 'duplicate-body', 'wrong-ordinal'):
            changed = copy.deepcopy(events)
            item = next(event['item'] for event in changed if event.get('item', {}).get('tool') == 'repo_validate')
            if mode == 'error': item['error'] = 'synthetic-refusal'
            elif mode == 'approval': item['status'] = 'needs_approval'
            elif mode == 'extra-item': item['unknown_extra'] = True
            elif mode == 'structured': item['result']['structured_content'] = {}
            elif mode == 'arguments': item['arguments'] = {'extra': True}
            elif mode == 'duplicate-body': item['result']['content'][0]['text'] = '{"ok":false,"ok":false}'
            else:
                native = [i for i, event in enumerate(changed) if event.get('item', {}).get('type') == 'mcp_tool_call']
                changed[native[1]], changed[native[2]] = changed[native[2]], changed[native[1]]
            with self.subTest(mode=mode):
                self.assertTrue(tool_codex._project_cli_trace_failures(changed, result['tool_events'], self.fixture.task))

    def test_same_ordinal_matching_hashes_still_require_canonical_known_failure(self):
        result, _, events = self.turn()
        for mode in ('unknown', 'infrastructure', 'protected', 'partial', 'missing-ref', 'wrong-state', 'duplicate-failure', 'no-failure', 'ok-true'):
            journal, native = copy.deepcopy(result['tool_events']), copy.deepcopy(events)
            row = journal[2]
            value = row['result']
            if mode == 'unknown': value['execution']['unknown'] = True
            elif mode == 'infrastructure': value['execution']['status'] = 'INFRASTRUCTURE_FAILED'
            elif mode == 'protected': value['failures'] = ['protected-file-changed:pkg/core.py']
            elif mode == 'partial': value['write_state'] = 'partial-or-unverified'
            elif mode == 'missing-ref': value['execution']['receipt_ref'] = None
            elif mode == 'wrong-state': value['execution']['received_snapshot_sha256'] = '0' * 64
            elif mode == 'duplicate-failure': value['failures'] *= 2
            elif mode == 'no-failure': value['failures'] = []
            else: value['ok'] = True
            row['result_sha256'] = sha(canonical(value))
            item = next(event['item'] for event in native if event.get('item', {}).get('tool') == 'repo_validate')
            item['result']['content'][0]['text'] = canonical(value).decode()
            with self.subTest(mode=mode):
                self.assertFalse(engineering.recoverable_project_test_failure(value, self.fixture.task, row['state_sha256']))
                self.assertIn('scope-invalid:cli-project-mcp-result-unconfirmed',
                    tool_codex._project_cli_trace_failures(native, journal, self.fixture.task))

    def test_failed_result_hash_or_arguments_hash_cannot_bind_other_payload(self):
        result, _, events = self.turn()
        for key in ('arguments_sha256', 'result_sha256'):
            journal = copy.deepcopy(result['tool_events'])
            journal[2][key] = '0' * 64
            with self.subTest(key=key):
                self.assertTrue(tool_codex._project_cli_trace_failures(events, journal, self.fixture.task))

    def test_unsafe_or_changed_diagnostics_fail_receipt_history_not_a_local_rule(self):
        result, directory, events = self.turn()
        journal = copy.deepcopy(result['tool_events'])
        journal[2]['result']['diagnostics'] = [{'stderr': 'Bearer ' + 'SYNTHETIC_' + 'SECRET_' + 'TOKEN_1234567890'}]
        journal[2]['result_sha256'] = sha(canonical(journal[2]['result']))
        item = next(event['item'] for event in events if event.get('item', {}).get('tool') == 'repo_validate')
        item['result']['content'][0]['text'] = canonical(journal[2]['result']).decode()
        # Reuse the canonical summary predicate; complete source receipt-history
        # verification is still mandatory and refuses any changed diagnostics.
        broker = self.fixture.adapter._read_broker(directory, self.fixture.task, journal)
        quality = self.fixture.adapter._project_quality(broker, journal, events, result['final_response_text'])
        self.assertTrue(quality['execution_state_unknown'])
        self.assertFalse(quality['scope_ok'])
        self.assertEqual(quality['task_success'], 0)

    def test_missing_original_receipt_remains_unknown_and_cannot_become_success(self):
        result, directory, events = self.turn()
        path = directory / 'execution/validation-001/result.json'
        path.unlink()  # Only this newly generated private synthetic fixture.
        broker = self.fixture.adapter._read_broker(directory, self.fixture.task, result['tool_events'])
        quality = self.fixture.adapter._project_quality(broker, result['tool_events'], events, result['final_response_text'])
        self.assertTrue(quality['execution_state_unknown'])
        self.assertFalse(quality['scope_ok'])
        self.assertFalse(quality['hard_pass'])

    def test_late_known_pass_does_not_erase_earlier_unknown_history(self):
        result, directory, events = self.turn()
        journal = copy.deepcopy(result['tool_events'])
        previous = journal[2]
        later = copy.deepcopy(previous)
        later['sequence'] = 4
        later['result'].update(ok=True, checks_passed=1, failures=[], diagnostics=[])
        later_path = directory / 'execution/validation-002'
        later_path.mkdir()
        original = json.loads((directory / 'execution/validation-001/result.json').read_bytes())
        original['mock_checked_ok'] = True
        raw = canonical(original)
        (later_path / 'result.json').write_bytes(raw)
        later['result']['execution'].update(receipt_ref='validation-002/result.json', receipt_sha256=sha(raw))
        later['result_sha256'] = sha(canonical(later['result']))
        journal.insert(3, later)
        journal[-1]['sequence'] = 5
        (directory / 'execution/validation-001/result.json').unlink()
        native = legacy.events_for(journal)
        native[2]['item']['status'] = 'failed'
        broker = self.fixture.adapter._read_broker(directory, self.fixture.task, journal)
        quality = self.fixture.adapter._project_quality(broker, journal, native, result['final_response_text'])
        self.assertTrue(quality['execution_state_unknown'])
        self.assertFalse(quality['scope_ok'])
        self.assertEqual(quality['task_success'], 0)


class NativeFixtureBootstrapTests(unittest.TestCase):
    """Exercise only fixture lifecycle; nested projection bodies are suppressed."""
    @staticmethod
    def child():
        name = 'test_failed_known_validation_keeps_scope_but_never_success'
        child = NativeFailedValidationTests(name)
        setattr(child, name, lambda: None)
        return child

    @staticmethod
    def globals_snapshot():
        return [(owner, name, getattr(owner, name)) for owner, names in (
            (subprocess, ('run', 'Popen', 'check_output', 'call', 'check_call')),
            (legacy.socket, ('socket', 'create_connection')),
            (legacy.tool_broker, ('git_command',)),
            (legacy.project_executor, ('execute_project', 'read_project_receipt')))
            for name in names]

    def test_cold_platform_probe_is_stubbed_without_any_process_attempt(self):
        child = self.child()
        original_platform = tool_codex.platform.platform
        globals_before = self.globals_snapshot()
        def cold_platform_probe():
            return subprocess.check_output(['synthetic-platform-probe-never-execute']).decode()
        with mock.patch.object(tool_codex.platform, 'platform', side_effect=cold_platform_probe) as probe:
            observed = unittest.TestResult()
            try:
                child.run(observed)
                succeeded, probe_calls = observed.wasSuccessful(), probe.call_count
                leaked = [name for owner, name, value in globals_before if getattr(owner, name) is not value]
            finally:
                # A baseline RED must not contaminate its outer test process.
                if hasattr(child, 'fixture'):
                    child.fixture.doCleanups()
            self.assertTrue(succeeded, 'nested bootstrap must complete without cold platform subprocess')
            self.assertEqual(probe_calls, 0)
            self.assertEqual(leaked, [])
        self.assertIs(tool_codex.platform.platform, original_platform)

    def test_partial_fixture_setup_failure_restores_all_global_mocks(self):
        child = self.child()
        original_platform = tool_codex.platform.platform
        globals_before = self.globals_snapshot()
        with mock.patch.object(tool_codex, 'ToolCodex', side_effect=RuntimeError('synthetic-bootstrap-constructor-failure')):
            observed = unittest.TestResult()
            try:
                child.run(observed)
                leaked = [name for owner, name, value in globals_before if getattr(owner, name) is not value]
                platform_restored = tool_codex.platform.platform is original_platform
            finally:
                # Compensate only after observing the old fixture's leak.
                if hasattr(child, 'fixture'):
                    child.fixture.doCleanups()
        self.assertEqual(len(observed.errors), 1)
        self.assertIn('synthetic-bootstrap-constructor-failure', observed.errors[0][1])
        self.assertEqual(observed.failures, [])
        self.assertEqual(leaked, [])
        self.assertTrue(platform_restored)
