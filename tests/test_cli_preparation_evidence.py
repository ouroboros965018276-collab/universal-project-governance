"""New preparation evidence tests: synthetic mocks only, never real Git/model."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from evolution import tool_codex
from evolution.tool_broker import canonical, sha
import test_engineering_cli as legacy

ROOT = Path(__file__).resolve().parents[1]


class PreparationEvidenceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'eval-workspaces').mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='v6-preparation-pure-', dir=ROOT / 'eval-workspaces')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.binary, self.git = self.base / 'codex.exe', self.base / 'mock-git.exe'
        self.host = self.base / ('codex-code-mode-host.exe' if os.name == 'nt' else 'codex-code-mode-host')
        for path in (self.binary, self.git, self.host):
            path.write_bytes(b'public mock binary; never execute')
        self.config = {'binary': str(self.binary), 'code_mode_host_binary': str(self.host),
            'git_binary': str(self.git), 'model': 'explicit-mock-only', 'effort': 'low',
            'artifact_root': str(self.base / 'calls'), 'timeout_seconds': 90,
            'broker_profile_id': 'stdlib-python-project-v1', 'max_tool_calls': 4}
        self.adapter = tool_codex.ToolCodex(self.config)
        self.task = legacy.task()
        self.bindings = {key: 'synthetic-' + key for key in ('campaign_id', 'sample_id',
            'protocol_sha256', 'source_sha256', 'runtime_sha256', 'candidate_sha256')}
        self.bindings['capability'] = self.adapter.binding()
        self.mode = 'success'
        self.git_calls = self.model_calls = 0
        self.intent_seen = False
        self.stdout, self.stderr = b'original out\x00\xff\n', b'original err\x00\xfe\n'

    def directory(self):
        return next((Path(self.config['artifact_root']) / 'calls').iterdir())

    def git_dir(self):
        return self.directory() / 'preparation/git-init'

    def fake_run(self, argv, **kwargs):
        if argv[0] == str(self.git):
            self.git_calls += 1
            intent = self.git_dir() / 'intent.json'
            self.intent_seen = intent.is_file()
            if self.intent_seen:
                value = json.loads(intent.read_bytes())
                self.assertEqual(value['planned_argv'], argv)
                self.assertEqual(value['model_dispatch_state'], 'not_started')
                self.assertTrue((Path(self.config['artifact_root']) / '.tool-dispatch.lock').exists())
            if self.mode == 'timeout':
                raise subprocess.TimeoutExpired(argv, 10, output=self.stdout, stderr=self.stderr)
            if self.mode == 'spawn':
                raise OSError('DO-NOT-RECORD-untrusted-exception-secret')
            if self.mode == 'bad-argv':
                return subprocess.CompletedProcess(['unexpected'], 0, self.stdout, self.stderr)
            return subprocess.CompletedProcess(argv, 17 if self.mode == 'nonzero' else 0, self.stdout, self.stderr)
        self.model_calls += 1
        if self.config.get('broker_profile_id') is not None and hasattr(tool_codex, '_preparation_write'):
            receipt = json.loads((self.git_dir() / 'result.json').read_bytes())
            self.assertEqual(receipt['returncode'], 0)
            self.assertEqual(receipt['outcome'], 'completed')
            self.assertTrue((self.git_dir() / 'stdout.raw').is_file())
            self.assertTrue((self.git_dir() / 'stderr.raw').is_file())
        raise RuntimeError('pure model sentinel; never dispatch')

    def invoke(self):
        with mock.patch.object(subprocess, 'run', side_effect=self.fake_run), \
             mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('actual process forbidden')):
            with self.assertRaises(tool_codex.ToolCallError) as caught:
                self.adapter.run(self.task, prompt='Owner synthetic public test only.', bindings=self.bindings)
        return caught.exception

    def assert_fenced_before_model(self, error, reason):
        self.assertEqual(self.model_calls, 0)
        self.assertTrue((Path(self.config['artifact_root']) / '.tool-dispatch.lock').is_file())
        receipt = error.provider_receipt
        self.assertEqual(receipt['dispatch_state'], 'not_started')
        self.assertIs(receipt['model_invoked'], False)
        self.assertEqual(receipt['preparation_reason'], reason)
        self.assertEqual(error.usage['measurement'], 'model-dispatch-not-started')
        self.assertEqual(error.usage['total_tokens'], 0)
        self.assertIsNone(error.usage['cost_usd'])
        self.assertNotIn('DO-NOT-RECORD', canonical(receipt).decode())
        return receipt

    def test_success_persists_original_git_evidence_before_cli_mock(self):
        self.invoke()
        self.assertEqual((self.git_calls, self.model_calls), (1, 1))
        self.assertTrue(self.intent_seen)
        result = json.loads((self.git_dir() / 'result.json').read_bytes())
        self.assertEqual((self.git_dir() / 'stdout.raw').read_bytes(), self.stdout)
        self.assertEqual((self.git_dir() / 'stderr.raw').read_bytes(), self.stderr)
        self.assertEqual(result['stdout']['sha256'], sha(self.stdout))
        self.assertEqual(result['stderr']['sha256'], sha(self.stderr))
        self.assertEqual(result['intent_sha256'], sha((self.git_dir() / 'intent.json').read_bytes()))
        self.assertEqual(result['source_binding']['git_binary_sha256'], self.adapter.binding()['git_sha256'])
        self.assertIsInstance(result['git_wall_seconds'], float)
        self.assertGreaterEqual(result['git_wall_seconds'], 0)
        self.assertNotIn('environment_values', result)

    def test_nonzero_git_preserves_returncode_streams_and_safe_original_cause(self):
        self.mode = 'nonzero'
        error = self.invoke()
        receipt = self.assert_fenced_before_model(error, 'git-init-nonzero')
        result = json.loads((self.git_dir() / 'result.json').read_bytes())
        self.assertEqual(result['returncode'], 17)
        self.assertEqual((self.git_dir() / 'stdout.raw').read_bytes(), self.stdout)
        self.assertEqual((self.git_dir() / 'stderr.raw').read_bytes(), self.stderr)
        self.assertEqual(receipt['safe_error']['class'], 'ValueError')
        self.assertEqual(receipt['safe_error']['message_code'], 'git-init-nonzero')

    def test_timeout_preserves_exact_partial_streams_without_invented_exit_code(self):
        self.mode = 'timeout'
        receipt = self.assert_fenced_before_model(self.invoke(), 'git-init-timeout')
        result = json.loads((self.git_dir() / 'result.json').read_bytes())
        self.assertEqual(result['outcome'], 'timeout')
        self.assertIsNone(result['returncode'])
        self.assertEqual((self.git_dir() / 'stdout.raw').read_bytes(), self.stdout)
        self.assertEqual((self.git_dir() / 'stderr.raw').read_bytes(), self.stderr)
        self.assertEqual(receipt['safe_error']['class'], 'TimeoutExpired')

    def test_spawn_error_withholds_untrusted_text_and_does_not_forge_empty_streams(self):
        self.mode = 'spawn'
        receipt = self.assert_fenced_before_model(self.invoke(), 'git-init-spawn-failed')
        result = json.loads((self.git_dir() / 'result.json').read_bytes())
        self.assertIsNone(result['returncode'])
        self.assertIsNone(result['stdout'])
        self.assertIsNone(result['stderr'])
        self.assertFalse((self.git_dir() / 'stdout.raw').exists())
        self.assertEqual(receipt['safe_error']['class'], 'OSError')

    def test_argv_mismatch_is_unknown_local_observation_without_model(self):
        self.mode = 'bad-argv'
        self.assert_fenced_before_model(self.invoke(), 'git-init-result-invalid')
        result = json.loads((self.git_dir() / 'result.json').read_bytes())
        self.assertIsNone(result['observed_argv'])
        self.assertEqual((self.git_dir() / 'stdout.raw').read_bytes(), self.stdout)

    def fault_writer(self, filename):
        original = getattr(tool_codex, '_preparation_write', None)
        def write(path, raw):
            if Path(path).name == filename:
                raise OSError('DO-NOT-RECORD-write-secret')
            return original(path, raw)
        return mock.patch.object(tool_codex, '_preparation_write', side_effect=write, create=True)

    def test_intent_persistence_failure_stops_before_git_and_model(self):
        with self.fault_writer('intent.json'):
            self.assert_fenced_before_model(self.invoke(), 'preparation-evidence-persistence-failed')
        self.assertEqual(self.git_calls, 0)

    def test_stream_persistence_failure_keeps_known_nonzero_cause_and_lock(self):
        self.mode = 'nonzero'
        with self.fault_writer('stderr.raw'):
            receipt = self.assert_fenced_before_model(self.invoke(), 'preparation-evidence-persistence-failed')
        self.assertEqual(receipt['preparation_observation']['original_error']['message_code'], 'git-init-nonzero')
        self.assertEqual(receipt['preparation_observation']['returncode'], 17)
        self.assertEqual((self.git_dir() / 'stdout.raw').read_bytes(), self.stdout)

    def test_result_persistence_failure_never_reaches_model(self):
        with self.fault_writer('result.json'):
            receipt = self.assert_fenced_before_model(self.invoke(), 'preparation-evidence-persistence-failed')
        self.assertEqual(receipt['preparation_stage'], 'git-result-persistence')
        self.assertEqual((self.git_dir() / 'stdout.raw').read_bytes(), self.stdout)

    def test_intent_fsync_failure_preserves_written_bytes_but_never_invokes_git(self):
        original = getattr(tool_codex, '_preparation_write', None)
        def write(path, raw):
            if Path(path).name == 'intent.json':
                with mock.patch.object(tool_codex.os, 'fsync', side_effect=OSError('DO-NOT-RECORD-fsync-secret')):
                    return original(path, raw)
            return original(path, raw)
        with mock.patch.object(tool_codex, '_preparation_write', side_effect=write, create=True):
            receipt = self.assert_fenced_before_model(self.invoke(), 'preparation-evidence-persistence-failed')
        self.assertEqual(self.git_calls, 0)
        self.assertEqual(receipt['preparation_stage'], 'git-intent-persistence')
        intent = json.loads((self.git_dir() / 'intent.json').read_bytes())
        self.assertEqual(intent['outcome'], 'not_started')
        self.assertIs(intent['model_invoked'], False)

    def test_failure_receipt_serialization_does_not_erase_original_reason_or_lock(self):
        self.mode = 'nonzero'
        original = tool_codex._atomic
        def write(path, value):
            if Path(path).name == 'preparation-failure.json':
                raise TypeError('DO-NOT-RECORD-serialization-secret')
            return original(path, value)
        with mock.patch.object(tool_codex, '_atomic', side_effect=write):
            receipt = self.assert_fenced_before_model(self.invoke(), 'git-init-nonzero')
        self.assertEqual(receipt['preparation_receipt_error'], 'TypeError')
        self.assertEqual(receipt['safe_error']['class'], 'ValueError')

    def test_capability_drift_has_distinct_stage_after_successful_git(self):
        original = self.adapter._identity
        count = 0
        def identity():
            nonlocal count
            count += 1
            result = original()
            if count > 1:
                result['config_sha256'] = 'drift'
            return result
        with mock.patch.object(self.adapter, '_identity', side_effect=identity):
            receipt = self.assert_fenced_before_model(self.invoke(), 'capability-drift')
        self.assertEqual(receipt['preparation_stage'], 'capability-verification')
        self.assertEqual(self.git_calls, 1)

    def test_sensitive_private_stream_is_exact_but_never_in_error_or_provider_prompt(self):
        self.stderr = b'Bearer ' + b'SYNTHETIC_SECRET_TOKEN_1234567890\n'
        receipt = self.assert_fenced_before_model(self.invoke(), 'git-init-sensitive-output')
        self.assertEqual((self.git_dir() / 'stderr.raw').read_bytes(), self.stderr)
        self.assertNotIn('SYNTHETIC_SECRET_TOKEN', canonical(receipt).decode())
        self.assertTrue(json.loads((self.git_dir() / 'result.json').read_bytes())['sensitive_output'])

    def test_ordinary_profile_none_keeps_old_git_path_without_preparation_artifacts(self):
        self.config.pop('broker_profile_id')
        self.adapter = tool_codex.ToolCodex(self.config)
        self.task = {'id': 'ordinary-mock', 'family': 'ordinary', 'prompt': 'public',
            'initial_files': {'README.md': 'old\n'}, 'writable_files': ['README.md'],
            'checks': [{'kind': 'text', 'path': 'README.md', 'expected': 'fixed\n'}]}
        self.bindings['capability'] = self.adapter.binding()
        with mock.patch.object(self.adapter, '_initialize_project_git', side_effect=AssertionError('project helper forbidden'), create=True):
            self.invoke()
        self.assertEqual((self.git_calls, self.model_calls), (1, 1))
        self.assertFalse((self.directory() / 'preparation').exists())

    def test_completed_cache_binds_new_preparation_raw_and_retains_known_usage_on_drift(self):
        fixture = legacy.CliProjectCandidateTests('test_whole_mock_cli_turn_preserves_tombstones_cost_receipt_and_cache_without_reexecution')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with mock.patch.object(subprocess, 'run', side_effect=fixture.fake_cli):
            first = fixture.adapter.run(fixture.task, prompt=fixture.adapter.public_instruction(), bindings=fixture.bindings())
        directory = Path(first['receipt']['artifact_directory'])
        raw = (directory / 'preparation/git-init/stdout.raw')
        self.assertIn('preparation/git-init/stdout.raw', first['receipt']['artifact_sha256'])
        original_receipt = (directory / 'receipt.json').read_bytes()
        raw.write_bytes(raw.read_bytes() + b'drift')
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no replay')):
            with self.assertRaises(tool_codex.ToolCallPending) as caught:
                fixture.adapter.run(fixture.task, prompt=fixture.adapter.public_instruction(), bindings=fixture.bindings())
        self.assertEqual(caught.exception.usage['total_tokens'], 110)
        self.assertTrue((fixture.adapter.artifacts / '.tool-dispatch.lock').is_file())
        self.assertEqual((directory / 'receipt.json').read_bytes(), original_receipt)
        self.assertEqual(fixture.mock_cli_calls, 1)
