"""Bounded registered-file removal; process/network/execution mocked by fixture."""
from __future__ import annotations
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

if sys.version_info < (3, 10):
    raise unittest.SkipTest('repository engine requires Python3.10+')
import test_engineering_broker as fixture
from evolution import engineering_broker as lab, tool_broker
from evolution.tool_broker import canonical, sha


class RemovalTests(fixture.EngineeringBrokerTests):
    def removal(self, path='README.md', old=None):
        return {'path': path, 'old_sha256': self.before[path] if old is None else old, 'new_text': None}

    def read(self, *paths):
        self.assertTrue(self.broker.call('repo_read', {'paths': list(paths)})['ok'])

    def test_read_bound_removal_has_absence_receipt(self):
        self.read('README.md')
        result = self.broker.call('repo_patch', {'operations': [self.removal()]})
        self.assertTrue(result['ok'], result)
        self.assertFalse((self.workspace/'README.md').exists())
        self.assertNotIn('README.md', self.broker.snapshot())
        self.assertEqual(result['files']['README.md'], {'sha256': None, 'deleted': True,
            'previous_sha256': self.before['README.md']})
        self.assertEqual(self.executor_calls, 0)

    def test_unread_existing_file_cannot_be_removed(self):
        result = self.broker.call('repo_patch', {'operations': [self.removal()]})
        self.assertFalse(result['ok'])
        self.assertEqual(self.before, self.broker.snapshot())

    def test_protected_file_and_stale_sha_cannot_be_removed(self):
        self.read('CONTRACT.json', 'README.md')
        for operation in (self.removal('CONTRACT.json'), self.removal(old='0'*64)):
            result = self.broker.call('repo_patch', {'operations': [operation]})
            self.assertFalse(result['ok'])
            self.assertEqual(self.before, self.broker.snapshot())

    def test_mixed_replacement_and_removal_is_one_verified_event(self):
        self.read('pkg/core.py', 'CONTRACT.json', 'README.md')
        result = self.broker.call('repo_patch', {'operations': [self.removal(),
            {'path':'pkg/core.py','old_sha256':self.before['pkg/core.py'],'new_text':'VALUE = 2\n'}]})
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['changed'], ['README.md', 'pkg/core.py'])
        self.assertEqual(self.broker.events[-1]['state_sha256'], sha(canonical(self.broker.snapshot())))

    def test_whole_batch_preflight_refuses_bad_later_operation_before_removal(self):
        self.read('README.md', 'pkg/core.py')
        result = self.broker.call('repo_patch', {'operations': [self.removal(),
            {'path':'pkg/core.py','old_sha256':'0'*64,'new_text':'VALUE = 2\n'}]})
        self.assertFalse(result['ok'])
        self.assertEqual(self.before, self.broker.snapshot())
        self.assertNotIn('write_state', result)

    def test_missing_target_and_duplicate_batch_are_refused(self):
        self.read('README.md')
        duplicate = self.broker.call('repo_patch', {'operations': [self.removal(), self.removal()]})
        self.assertFalse(duplicate['ok'])
        self.assertEqual(self.before, self.broker.snapshot())
        self.assertTrue(self.broker.call('repo_patch', {'operations': [self.removal()]})['ok'])
        again = self.broker.call('repo_patch', {'operations': [{'path':'README.md','old_sha256':None,'new_text':None}]})
        self.assertFalse(again['ok'])

    def test_unlink_failure_preserves_uncertain_mutation_fence(self):
        self.read('README.md')
        with patch.object(Path, 'unlink', side_effect=OSError('synthetic unlink failure')):
            result = self.broker.call('repo_patch', {'operations': [self.removal()]})
        self.assertFalse(result['ok'])
        self.assertEqual(result['write_state'], 'partial-or-unverified')
        self.assertTrue((self.workspace/'README.md').exists())

    def test_failed_write_after_removal_retains_partial_state(self):
        self.read('README.md', 'pkg/core.py')
        original = tool_broker.RepoBroker._execute
        def fail_write(broker, tool, arguments):
            if tool == 'repo_patch':
                return {'ok':False, 'changed':[], 'write_state':'partial-or-unverified'}
            return original(broker, tool, arguments)
        with patch.object(tool_broker.RepoBroker, '_execute', fail_write):
            result = self.broker.call('repo_patch', {'operations': [self.removal(),
                {'path':'pkg/core.py','old_sha256':self.before['pkg/core.py'],'new_text':'VALUE = 3\n'}]})
        self.assertFalse(result['ok'])
        self.assertEqual(result['write_state'], 'partial-or-unverified')
        self.assertEqual(result['changed'], ['README.md'])
        self.assertFalse((self.workspace/'README.md').exists())
        self.assertEqual(self.broker.snapshot()['pkg/core.py'], self.before['pkg/core.py'])

    def test_default_wire_stays_string_only(self):
        original = next(x for x in tool_broker.tool_definitions() if x['name']=='repo_patch')
        project = next(x for x in lab.tool_definitions() if x['name']=='repo_patch')
        def value(definition):
            return definition['inputSchema']['properties']['operations']['items']['properties']['new_text']['type']
        self.assertEqual(value(original), 'string')
        self.assertEqual(value(project), ['string', 'null'])
        self.assertEqual(value(next(x for x in tool_broker.tool_definitions() if x['name']=='repo_patch')), 'string')

    def test_unregistered_external_deletion_remains_unknown_snapshot(self):
        (self.workspace/'README.md').unlink()
        with self.assertRaises(ValueError):
            self.broker.snapshot()

    def test_removed_path_cannot_reappear_without_verified_write(self):
        self.read('README.md')
        self.assertTrue(self.broker.call('repo_patch', {'operations':[self.removal()]})['ok'])
        (self.workspace/'README.md').write_text('Unrecorded reappearance.\n',encoding='utf-8')
        with self.assertRaises(ValueError):
            self.broker.snapshot()

    def test_explicit_recreate_clears_only_confirmed_removal(self):
        self.read('README.md')
        self.assertTrue(self.broker.call('repo_patch', {'operations':[self.removal()]})['ok'])
        result = self.broker.call('repo_patch', {'operations':[
            {'path':'README.md','old_sha256':None,'new_text':'Explicit new content.\n'}]})
        self.assertTrue(result['ok'], result)
        self.assertIn('README.md', self.broker.snapshot())
        self.assertNotIn('README.md', self.broker._confirmed_removed_paths)

    def test_stale_validation_reconstructs_original_removed_state(self):
        self.read('pkg/core.py', 'CONTRACT.json', 'README.md')
        self.assertTrue(self.broker.call('repo_patch', {'operations':[self.removal()]})['ok'])
        self.assertTrue(self.broker.call('repo_validate', {})['ok'])
        self.assertTrue(self.broker.call('repo_patch', {'operations':[
            {'path':'pkg/core.py','old_sha256':self.before['pkg/core.py'],'new_text':'VALUE = 4\n'}]})['ok'])
        captured = []
        original = lab.project_executor.read_project_receipt
        def read(files, *args, **kwargs):
            captured.append(copy.deepcopy(files))
            return original(files, *args, **kwargs)
        with patch.object(lab.project_executor, 'read_project_receipt', side_effect=read):
            result = self.quality()
        self.assertFalse(result['hard_pass'])
        self.assertFalse(result['execution_state_unknown'])
        self.assertIsNone(result['validation'])
        self.assertNotIn('README.md', captured[0])
        self.assertEqual(captured[0]['pkg/core.py'], 'VALUE = 0\n')
        self.assertEqual(self.executor_calls, 1)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(RemovalTests(name) for name in sorted(RemovalTests.__dict__)
                              if name.startswith('test_'))
