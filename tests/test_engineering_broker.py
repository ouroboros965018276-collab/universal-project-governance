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
