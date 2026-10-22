"""Prepared release registrations against the real native API, without provider calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests import test_native_paired as fixtures
from tests import test_native_paired_wire as wire_fixtures

if fixtures.OFFLINE_SUPPORTED:
    from evolution import native_codex
    from evolution.evaluator import canonical_source


@unittest.skipUnless(fixtures.OFFLINE_SUPPORTED, "native callback experiment requires Python 3.10+")
class NativePairedRegistrationTests(unittest.TestCase):
    setUp = fixtures.NativePairedTests.setUp
    tearDown = fixtures.NativePairedTests.tearDown
    bundle = fixtures.NativePairedTests.bundle
    receipt_fixture = fixtures.NativePairedTests.receipt_fixture

    def current_bundle(self):
        blobs = self.blobs['b' * 40]
        for name in ('evolution/native_codex.py', 'evolution/contracts.py', 'compiler/compile_governance.py', 'LICENSE'):
            blobs[name] = (fixtures.REPO / name).read_bytes()
        for name, content in canonical_source(fixtures.REPO).items():
            blobs['governance-src/' + name] = content.encode('utf-8')
        for path in (fixtures.REPO / 'universal-project-governance').rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                blobs[path.relative_to(fixtures.REPO).as_posix()] = path.read_bytes()
        spec, output = self.bundle()
        entry = next(entry for entry in spec['workers'].values() if entry['condition'] == 'treatment')
        return spec, entry, output

    def command(self, spec, entry):
        condition = spec['conditions'][entry['condition']]
        task = spec['tasks'][entry['manifest_core']['task_order'][0]]
        return {'protocol_sha256': fixtures.digest(spec), 'sample_id': 'synthetic-registration',
                'request': {'source': copy.deepcopy(condition['source']), 'source_sha256': condition['source_sha256'],
                            'execution_artifact': copy.deepcopy(condition['execution_artifact']),
                            'candidate_id': condition['candidate_id'], 'config': entry['manifest_core']['runner_config'],
                            'model': entry['model'], 'task': task}}

    def test_prepared_config_and_capability_execute_current_native_contract_without_provider(self):
        spec, entry, _ = self.current_bundle()
        request = self.command(spec, entry)['request']
        snapshot = entry['manifest_core']['snapshot_directory']
        with patch.dict(sys.modules), patch.object(sys, 'path', [snapshot, *sys.path]):
            sys.modules.pop('upg_native_common_grader', None)
            service = native_codex.NativeCodex(entry['config'])
            self.assertEqual(service.binding(), {k: v for k, v in request['config'].items() if k != 'campaign_id'})
            # Only the provider boundary is synthetic: real compilation, planning,
            # registration admission and the current runner all execute.
            result = {'text': '{}', 'usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
                      'receipt': {}, 'wall_seconds': 0.0}
            with patch.object(service, '_call', return_value=result) as provider:
                self.assertEqual(service.runner(request)['status'], 'completed')
            provider.assert_called_once()
            changed = copy.deepcopy(request)
            changed['execution_artifact']['compiler'] += '\nraise AssertionError("unregistered execution")\n'
            with patch.object(service, '_call', side_effect=AssertionError('provider forbidden')) as provider:
                with self.assertRaisesRegex(ValueError, 'not owner-registered'):
                    service.runner(changed)
            provider.assert_not_called()

    def test_current_worker_verifies_registration_and_rejects_missing_pin_before_ready(self):
        spec, entry, _ = self.current_bundle()
        manifest = Path(entry['manifest_path'])
        command = [sys.executable, '-B', str(fixtures.HERE / 'worker.py'), '--manifest', str(manifest)]
        checked = subprocess.run(command + ['--manifest-sha256', fixtures.sha(manifest.read_bytes())],
                                 capture_output=True, timeout=15)
        self.assertEqual(checked.returncode, 0, checked.stderr.decode(errors='replace'))
        self.assertTrue(json.loads(checked.stdout)['verification_only'])
        config = dict(entry['config'])
        del config['execution_inputs_sha256']
        Path(entry['manifest_core']['config_path']).write_text(json.dumps(config), encoding='utf-8')
        changed = json.loads(manifest.read_bytes())
        changed['config_sha256'] = fixtures.digest(config)
        changed['runner_config'].pop('execution_inputs_sha256')
        manifest.write_text(json.dumps(changed), encoding='utf-8')
        refused = subprocess.run(command + ['--manifest-sha256', fixtures.sha(manifest.read_bytes())],
                                 capture_output=True, timeout=15)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn(b'owner-registered execution inputs', refused.stderr)
        self.assertEqual(refused.stdout, b'')
        self.assertFalse(Path(config['artifact_root']).exists())

    def test_parent_receipt_requires_current_execution_registration(self):
        spec, _, _ = self.current_bundle()
        item = next(item for item in spec['order'] if item['condition'] == 'treatment')
        raw, request, directory = self.receipt_fixture(spec, item)
        self.assertTrue(fixtures.P['verify_receipt'](spec, item, raw, request)['strict_artifact_quality'])
        unregistered = copy.deepcopy(request)
        unregistered['config'].pop('execution_inputs_sha256')
        with self.assertRaisesRegex(ValueError, 'differs from owner registration'):
            fixtures.P['verify_receipt'](spec, item, raw, unregistered)
        changed = copy.deepcopy(raw)
        changed['provider_receipt']['bindings']['capability'].pop('execution_inputs_sha256')
        (directory / 'receipt.json').write_text(json.dumps(changed['provider_receipt']), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            fixtures.P['verify_receipt'](spec, item, changed, request)

    def test_legacy_callback_still_rejects_owner_manifest_source_or_artifact_drift(self):
        for kind in ('source', 'artifact'):
            with self.subTest(kind=kind):
                worker, entry, command, log = wire_fixtures.NativePairedWireTests.worker(self)
                self.assertNotIn('execution_inputs_sha256', entry['config'])
                if kind == 'source':
                    command['request']['source']['runtime-scripts/unregistered.py'] = 'raise AssertionError("candidate")'
                    command['request']['source_sha256'] = fixtures.digest(command['request']['source'])
                else:
                    command['request']['execution_artifact']['compiler'] += '\nraise AssertionError("candidate")'
                try:
                    worker.process.stdin.write((json.dumps(command, ensure_ascii=True) + '\n').encode('ascii'))
                    worker.process.stdin.flush()
                    with self.assertRaisesRegex(RuntimeError, 'without an authoritative result'):
                        worker._receive(15)
                finally:
                    closed = worker.close()
                    worker.process.stdout.close()
                self.assertNotEqual(closed['exit_code'], 0)
                self.assertIn(b'dispatch input differs from frozen worker registration', (log / 'worker.stderr.raw').read_bytes())
                self.assertFalse(Path(entry['config']['artifact_root']).exists())


if __name__ == '__main__':
    unittest.main()
