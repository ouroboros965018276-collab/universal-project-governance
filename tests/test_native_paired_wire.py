"""Real Python subprocess canaries; synthetic native runner, zero provider calls."""
import copy
import json
import os
from pathlib import Path
import queue
import unittest
from unittest.mock import patch

from tests import test_native_paired as fixtures


@unittest.skipUnless(fixtures.OFFLINE_SUPPORTED, "optional native callback experiment requires Python 3.10+")
class NativePairedWireTests(unittest.TestCase):
    setUp = fixtures.NativePairedTests.setUp
    tearDown = fixtures.NativePairedTests.tearDown
    bundle = fixtures.NativePairedTests.bundle

    def worker(self):
        # These are the only native modules in the prepared synthetic snapshots.
        # A real official CLI invocation cannot execute their synthetic binary.
        native = b'''import hashlib, json, subprocess
def runner(request):
    source = request["source"]
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return {"source": source, "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "execution_artifact": request["execution_artifact"], "marker": "\\u4e2d\\u6587\\U0001f9ed"}
'''
        for blobs in self.blobs.values():
            blobs['evolution/native_codex.py'] = native
            blobs['governance-src/model/governance-model.json'] = '{"说明":"中文治理🧭，é，𠮷"}\n'.encode('utf-8')
            blobs['compiler/compile_governance.py'] = '# 中文编译器🧭\n'.encode('utf-8')
            blobs['LICENSE'] = '许可证：中文🧭\n'.encode('utf-8')
        spec, _ = self.bundle()
        entry = next(iter(spec['workers'].values()))
        task_id = entry['manifest_core']['task_order'][0]
        condition = spec['conditions'][entry['condition']]
        command = {'protocol_sha256': fixtures.digest(spec), 'sample_id': 'synthetic-unicode-canary',
                   'request': {'source': condition['source'], 'source_sha256': condition['source_sha256'],
                               'execution_artifact': condition['execution_artifact'], 'candidate_id': condition['candidate_id'],
                               'config': entry['manifest_core']['runner_config'], 'model': entry['model'],
                               'task': spec['tasks'][task_id]}}
        log = self.root / ('wire-logs-' + str(self.counter))
        # Force the text stream settings that previously misdecoded UTF-8 on
        # Windows. The fixed worker intentionally bypasses both text streams.
        with patch.dict(os.environ, {'PYTHONIOENCODING': 'cp936:surrogateescape', 'PYTHONUTF8': '0'}):
            worker = fixtures.P['ProcessWorker'](entry, fixtures.digest(spec), log)
        return worker, entry, command, log

    def test_real_subprocess_preserves_unicode_source_artifact_and_digest_under_cp936(self):
        worker, entry, command, log = self.worker()
        try:
            result = worker.call(command)
            self.assertEqual(result['type'], 'call_result')
            self.assertEqual(result['result']['source'], command['request']['source'])
            self.assertEqual(result['result']['source_sha256'], command['request']['source_sha256'])
            self.assertEqual(result['result']['execution_artifact'], command['request']['execution_artifact'])
            self.assertEqual(result['result']['marker'], '中文🧭')
            self.assertEqual(result['transport_receipts'], [])
        finally:
            closed = worker.close()
            worker.process.stdout.close()
        self.assertEqual(closed['exit_code'], 0)
        wire = (log / 'worker.stdout.jsonl').read_bytes()
        self.assertTrue(wire.isascii())
        self.assertIn(b'\\u4e2d', wire)
        self.assertFalse(Path(entry['config']['artifact_root']).exists())

    def test_real_subprocess_rejects_invalid_wire_bytes_without_replacement_or_callback(self):
        worker, entry, command, log = self.worker()
        try:
            worker.process.stdin.write(b'{"request":"\xff"}\n')
            worker.process.stdin.flush()
            with self.assertRaisesRegex(RuntimeError, 'without an authoritative result'):
                worker._receive(15)
        finally:
            closed = worker.close()
            worker.process.stdout.close()
        self.assertNotEqual(closed['exit_code'], 0)
        self.assertIn(b'UnicodeDecodeError', (log / 'worker.stderr.raw').read_bytes())
        self.assertEqual(len((log / 'worker.stdout.jsonl').read_bytes().splitlines()), 1)
        self.assertFalse(Path(entry['config']['artifact_root']).exists())

    def test_real_subprocess_rejects_unpaired_source_surrogate_before_native_callback(self):
        worker, entry, command, log = self.worker()
        corrupted = copy.deepcopy(command)
        corrupted['request']['source']['model/governance-model.json'] += '\udc9d'
        try:
            worker.process.stdin.write((json.dumps(corrupted, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii'))
            worker.process.stdin.flush()
            with self.assertRaisesRegex(RuntimeError, 'without an authoritative result'):
                worker._receive(15)
        finally:
            closed = worker.close()
            worker.process.stdout.close()
        self.assertNotEqual(closed['exit_code'], 0)
        self.assertIn(b'UnicodeEncodeError', (log / 'worker.stderr.raw').read_bytes())
        self.assertEqual(len((log / 'worker.stdout.jsonl').read_bytes().splitlines()), 1)
        self.assertFalse(Path(entry['config']['artifact_root']).exists())

    def test_parent_rejects_non_ascii_worker_wire_without_silent_decode(self):
        worker = object.__new__(fixtures.P['ProcessWorker'])
        worker.messages = queue.Queue()
        worker.messages.put(b'{"type":"call_result","value":"\xff"}\n')
        with self.assertRaises(UnicodeDecodeError):
            worker._receive(1)


if __name__ == '__main__':
    unittest.main()
