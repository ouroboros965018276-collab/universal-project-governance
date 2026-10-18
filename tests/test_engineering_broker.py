"""Pure broker regressions; every process/network/project execution is mocked."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
SUPPORTED = sys.version_info >= (3, 10)
if SUPPORTED:
    from evolution import engineering_broker as lab
    from evolution import project_executor, tool_broker
    from evolution.tool_broker import canonical, sha


@unittest.skipUnless(SUPPORTED, 'repository engine requires Python3.10+')
class EngineeringBrokerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='upg-engineering-broker-pure-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.workspace = self.base / 'repo'
        self.workspace.mkdir()
        self.task = {'id': 'synthetic-project', 'family': 'public-mock', 'prompt': 'Fix the core and update current docs.',
            'initial_files': {'pkg/__init__.py': '', 'pkg/core.py': 'VALUE = 0\n',
                              'README.md': 'Current old value.\n', 'CONTRACT.json': '{}\n'},
            'writable_files': ['pkg/core.py', 'README.md'],
            'required_read_paths': ['pkg/core.py', 'CONTRACT.json'],
            'required_tools': ['repo_read', 'repo_patch', 'repo_validate', 'repo_status'],
            'engineering_contract': {'schema_version': 1, 'contract_id': 'public-mock-suite',
                'trusted_files': {'audit_tests.py': 'import unittest\nclass Example(unittest.TestCase):\n    def test_bounds(self):\n        self.assertTrue(True)\n'},
                'checks': [{'id': 'unit', 'recipe': 'unittest', 'test_modules': ['audit_tests'],
                            'minimum_tests': 1, 'expected_test_ids': ['audit_tests.Example.test_bounds']}]}}
        for name, text in self.task['initial_files'].items():
            path = self.workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode('utf-8'))
        self.checked_ok = True
        self.integrity_ok = True
        self.executor_calls = 0
        harmless = SimpleNamespace(returncode=0, stdout=b' M pkg/core.py\n', stderr=b'')
        patches = [patch.object(tool_broker, 'git_command', return_value=harmless),
                   patch.object(project_executor, 'execute_project', side_effect=self.execute),
                   patch.object(project_executor, 'read_project_receipt', side_effect=self.read_receipt)]
        patches += [patch.object(subprocess, n, side_effect=AssertionError('real process forbidden'))
                    for n in ('run', 'Popen', 'check_output', 'call', 'check_call')]
        patches += [patch.object(socket, n, side_effect=AssertionError('network forbidden'))
                    for n in ('socket', 'create_connection')]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.broker = lab.create_broker(self.workspace, self.task, self.base / 'mock-git',
            audit_file=self.base / 'broker.jsonl', deadline=time.time() + 60,
            execution_artifacts=self.base / 'execution')
        self.before = self.broker.snapshot()

    def execute(self, files, contract, directory, remaining_seconds):
        self.executor_calls += 1
        self.assertGreater(remaining_seconds, 0)
        directory.mkdir(parents=True)
        receipt = {'status': 'EXECUTED', 'unknown': False, 'backend': lab.BACKEND_ID,
                   'snapshot_sha256': sha(canonical({p: sha(t.encode('utf-8')) for p, t in files.items()})),
                   'contract_sha256': sha(canonical(contract)), 'mock_ordinal': self.executor_calls,
                   'runner_sha256': '1' * 64, 'input_sha256': '2' * 64, 'output_sha256': '3' * 64,
                   'image_id': 'sha256:' + '4' * 64, 'container_removed': True, 'scratch_removed': True}
        (directory / 'result.json').write_bytes(canonical(receipt))
        return receipt

    def read_receipt(self, files, contract, directory, receipt_sha256=None):
        raw = (directory / 'result.json').read_bytes()
        integrity = self.integrity_ok and (receipt_sha256 is None or sha(raw) == receipt_sha256)
        return ({'ok': self.checked_ok, 'integrity_ok': self.integrity_ok,
                 'failures': [] if self.checked_ok else ['registered-test-failed'],
                 'checks_passed': 1 if self.checked_ok else 0, 'checks_total': 1,
                 **({'integrity_ok': integrity} if not integrity else {})},
                json.loads(raw), sha(raw))

    def read_and_edit(self, read=True):
        if read:
            self.assertTrue(self.broker.call('repo_read', {'paths': ['pkg/core.py', 'CONTRACT.json']})['ok'])
        self.assertTrue(self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/core.py', 'old_sha256': self.before['pkg/core.py'], 'new_text': 'VALUE = 1\n'}]})['ok'])

    def quality(self):
        trace, previous = [], None
        for event in self.broker.events:
            row = {'previous_chain_sha256': previous, 'broker_sequence': event['sequence'],
                   'broker_event_sha256': sha(canonical(event)), 'arguments_sha256': event['arguments_sha256'],
                   'result_sha256': event['result_sha256']}
            row['chain_sha256'] = sha(canonical(row))
            previous = row['chain_sha256']
            trace.append(row)
        return lab.quality_from_current_receipts(self.broker, self.before, json.dumps({
            'summary': 'Synthetic bounded project checks.', 'validation': 'passed',
            'helper_gap': 'project_tool unavailable in bounded broker'}), trace, [])

    def test_current_success_has_no_implicit_executor_run(self):
        self.read_and_edit()
        self.assertTrue(self.broker.call('repo_validate', {})['ok'])
        self.broker.call('repo_status', {})
        result = self.quality()
        self.assertTrue(result['hard_pass'], result)
        self.assertEqual(result['evidence_adapter'], lab.ADAPTER)
        self.assertEqual(result['evidence_broker_profile_id'], lab.PROFILE_ID)
        self.assertEqual(self.executor_calls, 1)

    def test_status_readiness_exposes_missing_search_and_allows_in_budget_recovery(self):
        self.task['required_tools'].insert(1, 'repo_search')
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        status = self.broker.call('repo_status', {})
        ready = status['completion_readiness']
        self.assertEqual(ready['missing_successful_required_tools'], ['repo_search'])
        self.assertEqual(ready['current_validation'], 'PASSED')
        self.assertTrue(ready['current_status'])
        self.assertFalse(ready['required_evidence_ready'])
        self.assertFalse(self.quality()['required_tools_ok'])
        self.broker.call('repo_search', {'needle': 'VALUE'})
        status = self.broker.call('repo_status', {})
        self.assertTrue(status['completion_readiness']['required_evidence_ready'])
        self.assertTrue(self.quality()['hard_pass'])
        self.assertEqual(self.executor_calls, 1)

    def test_status_readiness_marks_validation_stale_after_patch_without_executing(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        self.broker.call('repo_read', {'paths': ['README.md']})
        self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': self.before['README.md'], 'new_text': 'Current new value.\n'}]})
        ready = self.broker.call('repo_status', {})['completion_readiness']
        self.assertEqual(ready['missing_successful_required_tools'], [])
        self.assertEqual(ready['current_validation'], 'STALE')
        self.assertTrue(ready['current_status'])
        self.assertFalse(ready['required_evidence_ready'])
        self.assertEqual(ready['snapshot_sha256'], sha(canonical(self.broker.snapshot())))
        self.assertFalse(self.quality()['hard_pass'])
        self.assertEqual(self.executor_calls, 1)

    def test_status_readiness_same_snapshot_passes_and_is_bound_in_journal(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        status = self.broker.call('repo_status', {})
        ready = status['completion_readiness']
        self.assertEqual(ready['current_validation'], 'PASSED')
        self.assertTrue(ready['current_status'])
        self.assertEqual(ready['missing_successful_required_tools'], [])
        self.assertTrue(ready['required_evidence_ready'])
        self.assertEqual(self.broker.events[-1]['result_sha256'], sha(canonical(status)))
        self.assertEqual(lab.completion_readiness_from_receipts(self.broker), ready)
        self.assertTrue(self.quality()['hard_pass'])
        self.assertEqual(self.executor_calls, 1)

    def test_readiness_missing_status_does_not_invent_or_execute_one(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        count = len(self.broker.events)
        ready = lab.completion_readiness_from_receipts(self.broker)
        self.assertEqual(ready['missing_successful_required_tools'], ['repo_status'])
        self.assertEqual(ready['current_validation'], 'PASSED')
        self.assertFalse(ready['current_status'])
        self.assertFalse(ready['required_evidence_ready'])
        self.assertEqual(len(self.broker.events), count)
        self.assertEqual(self.executor_calls, 1)

    def test_readiness_missing_or_tampered_validation_cannot_be_ready(self):
        self.read_and_edit()
        ready = self.broker.call('repo_status', {})['completion_readiness']
        self.assertEqual(ready['current_validation'], 'NOT_RUN')
        self.assertFalse(ready['required_evidence_ready'])
        self.assertEqual(self.executor_calls, 0)
        self.broker.call('repo_validate', {})
        (self.base / 'execution/validation-001/result.json').unlink()
        ready = self.broker.call('repo_status', {})['completion_readiness']
        self.assertEqual(ready['current_validation'], 'UNKNOWN')
        self.assertFalse(ready['required_evidence_ready'])
        self.assertTrue(self.quality()['execution_state_unknown'])
        self.assertEqual(self.executor_calls, 1)

    def test_existing_and_absent_creatable_reads_keep_exact_byte_history(self):
        self.task['writable_files'].append('pkg/new.py')
        result = self.broker.call('repo_read', {'paths': ['pkg/core.py', 'CONTRACT.json', 'pkg/new.py']})
        self.assertEqual(result, {'ok': True, 'files': {
            'pkg/core.py': {'text': 'VALUE = 0\n', 'sha256': self.before['pkg/core.py']},
            'CONTRACT.json': {'text': '{}\n', 'sha256': self.before['CONTRACT.json']},
            'pkg/new.py': {'exists': False, 'text': None, 'sha256': None}}})
        self.assertEqual(len(self.broker.events), 1)
        self.assertFalse((self.workspace / 'pkg/new.py').exists())
        self.assertEqual(self.broker.snapshot(), self.before)
        self.assertEqual(lab.files_from_receipt_journal(self.task, self.broker.events), self.task['initial_files'])
        self.assertEqual(self.broker.read_evidence_failures(self.broker.events), [])
        created = self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/new.py', 'old_sha256': None, 'new_text': 'VALUE = 2\n'}]})
        self.assertTrue(created['ok'], created)
        readback = self.broker.call('repo_read', {'paths': ['pkg/new.py']})
        self.assertEqual(readback['files']['pkg/new.py'], {'text': 'VALUE = 2\n', 'sha256': sha(b'VALUE = 2\n')})
        expected = dict(self.task['initial_files'], **{'pkg/new.py': 'VALUE = 2\n'})
        self.assertEqual(lab.files_from_receipt_journal(self.task, self.broker.events), expected)
        self.assertEqual(self.executor_calls, 0)

    def test_absence_does_not_supply_required_initial_content_or_validation(self):
        self.task['writable_files'].append('pkg/new.py')
        self.assertTrue(self.broker.call('repo_read', {'paths': ['pkg/new.py']})['ok'])
        result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertTrue(any('required-recovery-reads-before-edit-missing' in x for x in result['failures']))
        self.assertIn('required-current-project-validation-missing', result['failures'])
        self.assertEqual(self.executor_calls, 0)

    def test_absence_does_not_hide_unregistered_paths_or_missing_initial_files(self):
        self.task['writable_files'].append('pkg/new.py')
        for path in ('unregistered.py', '../outside.py'):
            with self.subTest(path=path):
                result = self.broker.call('repo_read', {'paths': ['pkg/new.py', path]})
                self.assertFalse(result['ok'])
                self.assertNotIn('files', result)
        (self.workspace / 'CONTRACT.json').unlink()
        result = self.broker.call('repo_read', {'paths': ['pkg/new.py', 'CONTRACT.json']})
        self.assertFalse(result['ok'])
        self.assertNotIn('files', result)
        self.assertEqual(len(self.broker.events), 3)

    def test_directory_or_io_error_cannot_be_reported_as_absence(self):
        self.task['writable_files'].append('pkg/new.py')
        (self.workspace / 'pkg/new.py').mkdir()
        self.assertFalse(self.broker.call('repo_read', {'paths': ['pkg/new.py']})['ok'])
        (self.workspace / 'pkg/new.py').rmdir()
        actual = Path.read_bytes
        def denied(path):
            if path == self.workspace / 'pkg/core.py':
                raise PermissionError('synthetic unreadable existing file')
            return actual(path)
        with patch.object(Path, 'read_bytes', denied):
            result = self.broker.call('repo_read', {'paths': ['pkg/new.py', 'pkg/core.py']})
        self.assertFalse(result['ok'])
        self.assertIn('PermissionError', result['error'])
        self.assertNotIn('files', result)

    def test_absence_receipt_must_match_typed_current_namespace(self):
        self.task['writable_files'].append('pkg/new.py')
        self.broker.call('repo_read', {'paths': ['pkg/new.py']})
        for change in ('false-as-int', 'text', 'hash', 'existing', 'unregistered'):
            with self.subTest(change=change):
                journal = copy.deepcopy(self.broker.events)
                event = journal[0]
                value = event['result']['files']['pkg/new.py']
                if change == 'false-as-int': value['exists'] = 0
                elif change == 'text': value['text'] = ''
                elif change == 'hash': value['sha256'] = sha(b'')
                else:
                    name = 'pkg/core.py' if change == 'existing' else 'unregistered.py'
                    event['arguments']['paths'] = [name]
                    event['result']['files'] = {name: value}
                event['arguments_sha256'] = sha(canonical(event['arguments']))
                event['result_sha256'] = sha(canonical(event['result']))
                with self.assertRaises(ValueError):
                    lab.files_from_receipt_journal(self.task, journal)

    def test_read_change_is_not_silently_reported_as_snapshot_bytes(self):
        actual = Path.read_bytes
        reads = 0
        def changed(path):
            nonlocal reads
            if path == self.workspace / 'pkg/core.py':
                reads += 1
                if reads == 3:  # call snapshot, read snapshot, then actual requested contents.
                    return b'unobserved replacement\n'
            return actual(path)
        with patch.object(Path, 'read_bytes', changed):
            result = self.broker.call('repo_read', {'paths': ['pkg/core.py']})
        self.assertFalse(result['ok'])
        self.assertIn('read bytes differ', result['error'])
        self.assertEqual(self.broker.snapshot(), self.before)

    def test_patch_remains_full_replacement_and_rejects_noop_or_stale_hash(self):
        self.broker.call('repo_read', {'paths': ['pkg/core.py']})
        for old, text in ((self.before['pkg/core.py'], 'VALUE = 0\n'), ('0' * 64, 'VALUE = 1\n')):
            with self.subTest(old=old, text=text):
                result = self.broker.call('repo_patch', {'operations': [
                    {'path': 'pkg/core.py', 'old_sha256': old, 'new_text': text}]})
                self.assertFalse(result['ok'])
                self.assertEqual(self.broker.snapshot(), self.before)
        schema = {item['name']: item for item in lab.tool_definitions()}
        replacement = schema['repo_patch']['inputSchema']['properties']['operations']['items']['properties']['new_text']
        self.assertIn('Complete replacement file contents', replacement['description'])
        self.assertIn('exists=false', schema['repo_read']['description'])

    def test_pure_reader_does_not_accept_forged_noop_or_empty_replacement(self):
        self.broker.call('repo_read', {'paths': ['pkg/core.py']})
        self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/core.py', 'old_sha256': self.before['pkg/core.py'], 'new_text': 'VALUE = 1\n'}]})
        for text in ('VALUE = 0\n', ''):
            with self.subTest(text=text):
                journal = copy.deepcopy(self.broker.events)
                event = journal[-1]
                event['arguments']['operations'][0]['new_text'] = text
                event['result']['files']['pkg/core.py'] = {'sha256': sha(text.encode()), 'byte_size': len(text.encode())}
                event['arguments_sha256'] = sha(canonical(event['arguments']))
                event['result_sha256'] = sha(canonical(event['result']))
                snapshot = dict(self.before, **{'pkg/core.py': sha(text.encode())})
                event['state_sha256'] = sha(canonical(snapshot))
                with self.assertRaises(ValueError):
                    lab.files_from_receipt_journal(self.task, journal)

    def test_explicit_fragment_preserves_unicode_crlf_and_replays_complete_bytes(self):
        self.task['writable_files'].append('pkg/new.py')
        original = 'α\r\nVALUE = 0\r\nΩ\r\n'
        self.assertTrue(self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/new.py', 'old_sha256': None, 'new_text': original}]})['ok'])
        operation = {'path': 'pkg/new.py', 'old_sha256': sha(original.encode()),
                     'old_text': 'VALUE = 0', 'new_text': 'VALUE = 7'}
        result = self.broker.call('repo_patch', {'operations': [operation]})
        expected = 'α\r\nVALUE = 7\r\nΩ\r\n'
        self.assertTrue(result['ok'], result)
        self.assertEqual((self.workspace / 'pkg/new.py').read_bytes(), expected.encode())
        self.assertEqual(result['files']['pkg/new.py'], {'sha256': sha(expected.encode()), 'byte_size': len(expected.encode())})
        self.assertEqual(self.broker.events[-1]['arguments']['operations'], [operation])
        self.assertEqual(lab.files_from_receipt_journal(self.task, self.broker.events),
                         dict(self.task['initial_files'], **{'pkg/new.py': expected}))
        self.assertEqual(self.executor_calls, 0)

    def test_fragment_can_remove_only_the_match_and_old_mode_still_replaces_whole_file(self):
        self.broker.call('repo_read', {'paths': ['README.md']})
        result = self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': self.before['README.md'], 'old_text': 'old ', 'new_text': ''}]})
        self.assertTrue(result['ok'], result)
        self.assertEqual((self.workspace / 'README.md').read_bytes(), b'Current value.\n')
        result = self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': sha(b'Current value.\n'), 'new_text': 'full replacement\n'}]})
        self.assertTrue(result['ok'], result)
        self.assertEqual((self.workspace / 'README.md').read_bytes(), b'full replacement\n')
        self.assertEqual(lab.files_from_receipt_journal(self.task, self.broker.events)['README.md'], 'full replacement\n')

    def test_fragment_refusals_preserve_bytes_and_every_attempt_is_recorded(self):
        self.task['writable_files'].append('pkg/new.py')
        self.broker.call('repo_read', {'paths': ['README.md']})
        base = {'path': 'README.md', 'old_sha256': self.before['README.md'], 'old_text': 'old', 'new_text': 'new'}
        invalid = [dict(base, old_text=value) for value in ('', 'absent', 'r', None, 1)]
        invalid += [dict(base, new_text=None), dict(base, new_text='old'), dict(base, old_sha256='0' * 64),
                    dict(base, old_text=self.task['initial_files']['README.md'], new_text=''),
                    dict(base, path='pkg/new.py', old_sha256=None), dict(base, path='CONTRACT.json')]
        for operation in invalid:
            with self.subTest(operation=operation):
                result = self.broker.call('repo_patch', {'operations': [operation]})
                self.assertFalse(result['ok'])
                self.assertNotIn('write_state', result)
                self.assertEqual(self.broker.snapshot(), self.before)
        self.assertEqual(len(self.broker.events), 1 + len(invalid))
        self.assertEqual(lab.files_from_receipt_journal(self.task, self.broker.events), self.task['initial_files'])

    def test_fragment_overlapping_matches_and_unread_current_sha_are_refused(self):
        operation = {'path': 'pkg/core.py', 'old_sha256': self.before['pkg/core.py'],
                     'old_text': '0', 'new_text': '1'}
        self.assertFalse(self.broker.call('repo_patch', {'operations': [operation]})['ok'])
        self.task['writable_files'].append('pkg/new.py')
        self.assertTrue(self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/new.py', 'old_sha256': None, 'new_text': 'aaa'}]})['ok'])
        result = self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/new.py', 'old_sha256': sha(b'aaa'), 'old_text': 'aa', 'new_text': 'b'}]})
        self.assertFalse(result['ok'])
        self.assertIn('exactly once', result['error'])
        self.assertEqual((self.workspace / 'pkg/new.py').read_bytes(), b'aaa')

    def test_mixed_fragment_batch_preflight_precedes_every_mutation(self):
        self.broker.call('repo_read', {'paths': ['README.md', 'pkg/core.py']})
        removal = {'path': 'README.md', 'old_sha256': self.before['README.md'], 'new_text': None}
        fragment = {'path': 'pkg/core.py', 'old_sha256': self.before['pkg/core.py'], 'old_text': 'missing', 'new_text': '1'}
        self.assertFalse(self.broker.call('repo_patch', {'operations': [removal, fragment]})['ok'])
        self.assertEqual(self.broker.snapshot(), self.before)
        fragment = dict(fragment, old_text='0')  # Keep the rejected journal arguments immutable.
        result = self.broker.call('repo_patch', {'operations': [removal, fragment]})
        self.assertTrue(result['ok'], result)
        restored = lab.files_from_receipt_journal(self.task, self.broker.events)
        self.assertNotIn('README.md', restored)
        self.assertEqual(restored['pkg/core.py'], 'VALUE = 1\n')

    def test_pure_fragment_reader_rejects_semantics_or_complete_readback_drift(self):
        self.broker.call('repo_read', {'paths': ['pkg/core.py']})
        self.broker.call('repo_patch', {'operations': [{'path': 'pkg/core.py',
            'old_sha256': self.before['pkg/core.py'], 'old_text': '0', 'new_text': '1'}]})
        for change in ('match', 'sha', 'fragment-readback', 'null', 'extra'):
            with self.subTest(change=change):
                journal = copy.deepcopy(self.broker.events)
                event = journal[-1]
                operation = event['arguments']['operations'][0]
                if change == 'match': operation['old_text'] = 'missing'
                elif change == 'sha': operation['old_sha256'] = '0' * 64
                elif change == 'null': operation['new_text'] = None
                elif change == 'extra': operation['extra'] = True
                else: event['result']['files']['pkg/core.py'] = {'sha256': sha(b'1'), 'byte_size': 1}
                event['arguments_sha256'] = sha(canonical(event['arguments']))
                event['result_sha256'] = sha(canonical(event['result']))
                with self.assertRaises(ValueError):
                    lab.files_from_receipt_journal(self.task, journal)

    def bounded_batch_broker(self, label):
        root = self.base / label
        root.mkdir()
        task = copy.deepcopy(self.task)
        task['initial_files'] = {'A': 'aa', 'B': 'bbbbbbbb'}
        task['writable_files'] = ['A', 'B']
        task['required_read_paths'] = ['A', 'B']
        for name, text in task['initial_files'].items():
            (root / name).write_bytes(text.encode())
        broker = lab.create_broker(root, task, self.base / 'mock-git', deadline=time.time() + 60)
        self.assertTrue(broker.call('repo_read', {'paths': ['A', 'B']})['ok'])
        return broker, task, root

    def test_no_deletion_batch_uses_final_total_in_either_order_with_fragment_mixtures(self):
        for mode in ('whole', 'grow-fragment', 'shrink-fragment'):
            for order in ('grow-first', 'shrink-first'):
                with self.subTest(mode=mode, order=order), patch.object(lab, 'MAX_TOTAL_BYTES', 10), \
                        patch.object(tool_broker, 'MAX_TOTAL_BYTES', 10):
                    broker, task, root = self.bounded_batch_broker(mode + '-' + order)
                    operations = [{'path': 'A', 'old_sha256': sha(b'aa'), 'new_text': 'aaa'},
                                  {'path': 'B', 'old_sha256': sha(b'bbbbbbbb'), 'new_text': 'b'}]
                    if mode == 'grow-fragment': operations[0]['old_text'] = 'aa'
                    if mode == 'shrink-fragment': operations[1]['old_text'] = 'bbbbbbbb'
                    if order == 'shrink-first': operations.reverse()
                    original, delegated = tool_broker.RepoBroker._execute, []
                    def observed(broker, tool, arguments):
                        if tool == 'repo_patch': delegated.append(copy.deepcopy(arguments['operations']))
                        return original(broker, tool, arguments)
                    with patch.object(tool_broker.RepoBroker, '_execute', observed):
                        result = broker.call('repo_patch', {'operations': operations})
                    self.assertTrue(result['ok'], result)
                    self.assertNotIn('write_state', result)
                    self.assertEqual([len(batch) for batch in delegated], [2])
                    self.assertTrue(all('old_text' not in item for item in delegated[0]))
                    self.assertEqual(result['changed'], ['A', 'B'])
                    self.assertEqual(result['files'], {'A': {'sha256': sha(b'aaa'), 'byte_size': 3},
                                                       'B': {'sha256': sha(b'b'), 'byte_size': 1}})
                    self.assertEqual((root / 'A').read_bytes(), b'aaa')
                    self.assertEqual((root / 'B').read_bytes(), b'b')
                    self.assertEqual(len(broker.events), 2)
                    self.assertEqual(lab.files_from_receipt_journal(task, broker.events), {'A': 'aaa', 'B': 'b'})

    def test_no_deletion_batch_still_rejects_final_overcap_or_late_bad_precondition_before_writes(self):
        for failure in ('final-overcap', 'late-stale-sha', 'late-missing-fragment'):
            with self.subTest(failure=failure), patch.object(lab, 'MAX_TOTAL_BYTES', 10), \
                    patch.object(tool_broker, 'MAX_TOTAL_BYTES', 10):
                broker, task, root = self.bounded_batch_broker(failure)
                operations = [{'path': 'A', 'old_sha256': sha(b'aa'), 'old_text': 'aa', 'new_text': 'aaa'},
                              {'path': 'B', 'old_sha256': sha(b'bbbbbbbb'), 'new_text': 'b'}]
                if failure == 'final-overcap':
                    operations[0]['new_text'] = 'aaaa'
                    operations[1]['new_text'] = 'bbbbbbb'  # Final 11 remains over the unchanged cap 10.
                elif failure == 'late-stale-sha': operations[1]['old_sha256'] = '0' * 64
                else: operations[1]['old_text'] = 'missing'
                result = broker.call('repo_patch', {'operations': operations})
                self.assertFalse(result['ok'])
                self.assertNotIn('write_state', result)
                self.assertNotIn('changed', result)
                self.assertEqual((root / 'A').read_bytes(), b'aa')
                self.assertEqual((root / 'B').read_bytes(), b'bbbbbbbb')
                self.assertEqual(len(broker.events), 2)
                self.assertEqual(lab.files_from_receipt_journal(task, broker.events), task['initial_files'])

    def test_later_doc_edit_invalidates_current_validation(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        self.broker.call('repo_read', {'paths': ['README.md']})
        self.broker.call('repo_patch', {'operations': [{'path': 'README.md',
            'old_sha256': self.before['README.md'], 'new_text': 'Current new value.\n'}]})
        self.broker.call('repo_status', {})
        result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertIn('required-current-project-validation-missing', result['failures'])
        self.assertEqual(self.executor_calls, 1)

    def test_known_test_failure_does_not_become_unknown(self):
        self.read_and_edit()
        self.checked_ok = False
        result = self.broker.call('repo_validate', {})
        self.assertFalse(result['ok'])
        self.assertEqual(result['execution']['status'], 'EXECUTED')
        self.assertFalse(result['execution']['unknown'])
        self.assertIsNone(self.broker.terminal_result)

    def test_bad_receipt_integrity_closes_broker(self):
        self.read_and_edit()
        self.integrity_ok = False
        result = self.broker.call('repo_validate', {})
        self.assertFalse(result['ok'])
        self.assertTrue(result['execution']['unknown'])
        self.assertIsNotNone(self.broker.terminal_result)
        self.broker.call('repo_validate', {})
        self.assertEqual(self.executor_calls, 1)

    def test_protected_external_drift_never_executes(self):
        (self.workspace / 'CONTRACT.json').write_text('{"drift":true}\n', encoding='utf-8')
        result = self.broker.call('repo_validate', {})
        self.assertFalse(result['ok'])
        self.assertTrue(result['execution']['unknown'])
        self.assertEqual(self.executor_calls, 0)

    def test_missing_pre_edit_reads_cannot_be_repaired_by_late_reads(self):
        self.broker.call('repo_read', {'paths': ['pkg/core.py']})
        self.read_and_edit(read=False)
        self.broker.call('repo_read', {'paths': ['pkg/core.py', 'CONTRACT.json']})
        self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})
        result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertTrue(any('required-recovery-reads-before-edit-missing' in x for x in result['failures']))

    def test_protected_patch_is_rejected_without_change(self):
        result = self.broker.call('repo_patch', {'operations': [{'path': 'CONTRACT.json',
            'old_sha256': self.before['CONTRACT.json'], 'new_text': '{"bad":true}\n'}]})
        self.assertFalse(result['ok'])
        self.assertEqual(self.broker.snapshot(), self.before)
        self.assertEqual(self.executor_calls, 0)

    def test_malformed_execution_summary_is_not_a_recoverable_test_failure(self):
        self.read_and_edit()
        result = self.broker.call('repo_validate', {})
        state = sha(canonical(self.broker.snapshot()))
        self.assertIsNotNone(lab.validate_execution_result(result, self.task, state))
        for field, value in [('receipt_sha256', 'z' * 64), ('receipt_ref', '../result.json'),
                             ('observed_wall_seconds', float('nan')), ('received_snapshot_sha256', '0' * 64)]:
            with self.subTest(field=field):
                forged = copy.deepcopy(result)
                forged['execution'][field] = value
                self.assertIsNone(lab.validate_execution_result(forged, self.task, state))

    def test_real_broker_reserves_fresh_execution_parent(self):
        self.assertTrue((self.base / 'execution').is_dir())
        with self.assertRaises(ValueError):
            lab.create_broker(self.workspace, self.task, self.base / 'mock-git',
                deadline=time.time() + 60, execution_artifacts=self.base / 'execution')

    def test_known_hash_without_actual_current_read_cannot_patch(self):
        result = self.broker.call('repo_patch', {'operations': [
            {'path': 'pkg/core.py', 'old_sha256': self.before['pkg/core.py'], 'new_text': 'VALUE = 1\n'}]})
        self.assertFalse(result['ok'])
        self.assertEqual(self.broker.snapshot(), self.before)

    def test_final_receipt_tampering_is_unknown_without_reexecution(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})
        path = self.base / 'execution/validation-001/result.json'
        value = json.loads(path.read_bytes())
        value['mock_ordinal'] = 999
        path.write_bytes(canonical(value))
        result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertTrue(result.get('execution_state_unknown'))
        self.assertEqual(self.executor_calls, 1)

    def test_missing_final_raw_receipt_is_unknown_without_reexecution(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        self.broker.call('repo_status', {})
        (self.base / 'execution/validation-001/result.json').unlink()
        result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertTrue(result.get('execution_state_unknown'))
        self.assertEqual(self.executor_calls, 1)

    def test_current_invalid_summary_is_unknown_not_absent_validation(self):
        self.read_and_edit()
        self.broker.call('repo_validate', {})
        self.broker.events[-1]['result']['execution']['receipt_sha256'] = 'z' * 64
        self.broker.call('repo_status', {})
        result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertTrue(result.get('execution_state_unknown'))
        self.assertEqual(self.executor_calls, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
