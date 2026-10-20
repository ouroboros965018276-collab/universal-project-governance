"""Synthetic clocks/HTTPS only. No provider, task code, process or vault calls."""
import sys, unittest
if sys.version_info < (3, 10):
    raise unittest.SkipTest('Provider helper requires Python 3.10+')
import copy, json, pathlib, tempfile, threading
from unittest.mock import patch
import evolution.provider_tools as lab
import test_engineering_provider as engineering_tests
from test_provider_tools import _ProviderFixture, SECRET, call, completion
from evolution.tool_broker import canonical


class FakeHTTPS:
    def __init__(self, body, clock, *, late=False, close_error=False, partial=False, headers=None, late_at=181, missing_bytes=0):
        self.body, self.clock, self.late = body, clock, late
        self.close_error, self.partial = close_error, partial
        self.sent, self.connections, self.owner_threads = [], [], []
        self.headers = headers or [('X-Request-ID', 'synthetic-provider-id')]
        self.late_at, self.missing_bytes = late_at, missing_bytes
    def factory(self, host, timeout):
        owner = self
        class Connection:
            sock = None
            auto_open = 1
            def connect(self): pass
            def request(self, method, path, body, headers):
                owner.sent.append(json.loads(body))
            def getresponse(self):
                number = len(owner.sent)
                data = owner.body(number, owner.sent[-1]) if callable(owner.body) else owner.body
                class Response:
                    status = 200
                    reads = 0
                    offset = 0
                    length = len(data)+owner.missing_bytes if owner.missing_bytes else None
                    def getheaders(self): return owner.headers
                    def read1(self, maximum):
                        self.reads += 1
                        if self.reads == 1:
                            late = owner.late(number) if callable(owner.late) else owner.late
                            owner.clock[0] = float(owner.late_at) if late else float(number)
                        if owner.partial:
                            if self.reads == 1: return b'{"partial":'
                            raise TimeoutError('synthetic incomplete body')
                        chunk = data[self.offset:self.offset+maximum]
                        self.offset += len(chunk)
                        if self.length is not None: self.length -= len(chunk)
                        return chunk
                return Response()
            def close(self):
                if owner.close_error: raise OSError('synthetic close failure')
        value = Connection()
        self.connections.append(value)
        return value


class ManagedTransportTests(unittest.TestCase):
    def test_cancelled_dns_worker_cannot_dispatch_or_write_after_return(self):
        entered, release = threading.Event(), threading.Event()
        sent = []
        class Connection:
            sock = None
            def connect(self): entered.set(); release.wait(2)
            def request(self, *args, **kwargs): sent.append(True)
            def close(self): pass
        with patch.object(lab.http.client, 'HTTPSConnection', return_value=Connection()), \
             patch.object(lab, '_write_new', side_effect=AssertionError('worker cannot write')):
            job = lab._ManagedRequest('deepseek', {}, SECRET, lab.time.perf_counter()+1, lab.time.perf_counter()+601)
            job.start()
            self.assertTrue(entered.wait(1))
            self.assertTrue(job.cancel_before_dispatch())
            # The terminal observer has returned while DNS/connect is still blocked.
            release.set(); job.thread.join(2)
            self.assertFalse(job.thread.is_alive())
            self.assertEqual(sent, [])
            self.assertFalse(job.snapshot()['dispatch_started'])

    def test_cutoff_closes_gate_even_without_an_observer_cancellation(self):
        with patch.object(lab.time, 'perf_counter', return_value=2):
            job = lab._ManagedRequest('deepseek', {}, SECRET, 1, 601)
            self.assertFalse(job.begin_dispatch())
            self.assertTrue(job.snapshot()['dispatch_closed'])

    def test_early_headers_and_complete_body_are_only_captured_by_main(self):
        current, captured, owner = [0.0], [], threading.get_ident()
        fake = FakeHTTPS(canonical(completion(1)), current, late=True)
        def capture(kind, value):
            self.assertEqual(threading.get_ident(), owner)
            captured.append((kind, copy.deepcopy(value)))
        with patch.object(lab.time, 'perf_counter', side_effect=lambda: current[0]), \
             patch.object(lab.http.client, 'HTTPSConnection', side_effect=fake.factory):
            result = lab._managed_post('deepseek', {}, SECRET, 180, 780, capture)
        self.assertEqual([x[0] for x in captured], ['headers', 'body'])
        self.assertTrue(result['settlement']['accounting_only'])
        self.assertTrue(result['settlement']['worker_done'])
        self.assertEqual(result['response'][2], canonical(completion(1)))
        self.assertEqual(len(fake.sent), 1)

    def test_complete_response_survives_close_error(self):
        current = [0.0]
        fake = FakeHTTPS(canonical(completion(1)), current, late=True, close_error=True)
        with patch.object(lab.time, 'perf_counter', side_effect=lambda: current[0]), \
             patch.object(lab.http.client, 'HTTPSConnection', side_effect=fake.factory):
            result = lab._managed_post('deepseek', {}, SECRET, 180, 780, lambda *args: None)
        self.assertEqual(result['response'][2], canonical(completion(1)))
        self.assertEqual(result['failure']['phase'], 'connection-close')
        self.assertEqual(result['failure']['exception_class'], 'OSError')

    def test_partial_response_is_not_promoted_to_complete(self):
        current, captured = [0.0], []
        fake = FakeHTTPS(b'ignored', current, late=True, partial=True)
        with patch.object(lab.time, 'perf_counter', side_effect=lambda: current[0]), \
             patch.object(lab.http.client, 'HTTPSConnection', side_effect=fake.factory):
            result = lab._managed_post('deepseek', {}, SECRET, 180, 780, lambda *x: captured.append(x))
        self.assertIsNone(result['response'])
        self.assertEqual(result['failure']['phase'], 'response-body')
        self.assertFalse(captured[-1][1]['body_complete'])
        self.assertEqual(captured[-1][1]['body_bytes'], len(b'{"partial":'))

    def test_hung_dispatched_worker_cannot_capture_after_settlement_terminal(self):
        entered, release, jobs = threading.Event(), threading.Event(), []
        clock, captures, sent = [0.0], [], []
        class Connection:
            sock = None
            def connect(self): pass
            def request(self, *args, **kwargs): sent.append(True)
            def getresponse(self):
                entered.set(); release.wait(2)
                class Response:
                    status = 200
                    def getheaders(self): return []
                    def read1(self, maximum): return b''
                return Response()
            def close(self): pass
        def wait(job, seconds, revision):
            jobs[:] = [job]
            if job.snapshot()['dispatch_started']:
                self.assertTrue(entered.wait(1)); clock[0] = 780
            else:
                with job.condition: job.condition.wait(.001)
        try:
            with patch.object(lab.time, 'perf_counter', side_effect=lambda: clock[0]), \
                 patch.object(lab.http.client, 'HTTPSConnection', return_value=Connection()), \
                 patch.object(lab._ManagedRequest, 'wait', new=wait), \
                 patch.object(lab, '_write_new', side_effect=AssertionError('no worker writes')):
                result = lab._managed_post('deepseek', {}, SECRET, 180, 780, lambda *x: captures.append(x))
                observed = list(captures)
                self.assertTrue(result['settlement']['settlement_limit_reached'])
                self.assertFalse(result['settlement']['worker_done'])
                self.assertIsNone(result['response'])
                self.assertEqual(result['failure']['http_dispatch'], 'may_have_started')
                release.set(); jobs[0].thread.join(2)
                self.assertEqual(captures, observed)
                self.assertEqual(sent, [True])
        finally: release.set()

    def test_bounded_headers_and_body_never_promote_oversize_response(self):
        for mode in ('headers', 'body'):
            with self.subTest(mode=mode):
                clock, captures = [0.0], []
                fake = FakeHTTPS(b'x'*(lab.MAX_RESPONSE_BYTES+1), clock, late=True,
                    headers=[('X-Large', 'x'*(lab.MAX_CAPTURE_HEADER_BYTES+1))] if mode=='headers' else None)
                with patch.object(lab.time, 'perf_counter', side_effect=lambda: clock[0]), \
                     patch.object(lab.http.client, 'HTTPSConnection', side_effect=fake.factory):
                    result = lab._managed_post('deepseek', {}, SECRET, 180, 780, lambda *x: captures.append(x))
                self.assertIsNone(result['response'])
                self.assertIsNotNone(result['failure'])
                if mode=='body':
                    self.assertEqual(captures[-1][1]['body_bytes'], lab.MAX_RESPONSE_BYTES+1)
                    self.assertFalse(captures[-1][1]['body_complete'])


class SettlementActorTests(engineering_tests.EngineeringCandidateTests):
    setUp = engineering_tests.EngineeringCandidateTests.setUp
    new_actor = engineering_tests.EngineeringCandidateTests.new_actor
    finish = engineering_tests.EngineeringCandidateTests.finish

    def run_https(self, fake, **options):
        with patch.object(lab.time, 'perf_counter', side_effect=lambda: fake.clock[0]), \
             patch.object(lab.http.client, 'HTTPSConnection', side_effect=fake.factory):
            return self.new_actor(settlement_policy=lab.SETTLEMENT_POLICY, **options)

    def test_late_finish_has_one_accounting_callback_and_no_task_success(self):
        fake = FakeHTTPS(canonical(self.finish(1)), [0.0], late=True)
        result = self.run_https(fake)
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(len(self.before), 1)
        self.assertEqual(len(self.after), 1)
        self.assertEqual(result['status'], 'work-deadline-settled-unfinished')
        self.assertFalse(result['quality']['task_success'])
        self.assertFalse(result['unknown_usage'])
        self.assertGreater(result['known_usage']['total_tokens'], 0)
        self.assertEqual(result['tool_events'], [])
        self.assertIsNone(result['final_report'])
        self.assertEqual(result['final_text'], '')
        self.assertEqual(self.after[0]['settlement_policy'], lab.SETTLEMENT_POLICY)
        self.assertEqual(self.after[0]['settlement_max_seconds'], 600)
        self.assertEqual(self.after[0]['settlement']['accounting_only'], True)
        native = self.artifacts/'requests/01.receipt.json'
        self.assertEqual(self.after[0]['receipt_sha256'], lab.sha(native.read_bytes()))
        self.assertFalse((self.artifacts/'requests/01.pending.json').exists())
        self.assertTrue((self.artifacts/'actor.pending.json').exists())

    def test_late_patch_is_never_executed(self):
        response = completion(1, [call('late-patch', 'repo_patch', {'operations': [
            {'path': 'target.txt', 'old_sha256': lab.sha(b'old\n'), 'new_text': 'late mutation\n'}]})])
        result = self.run_https(FakeHTTPS(canonical(response), [0.0], late=True))
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(result['tool_attempts'], 0)
        self.assertFalse(result['quality']['hard_pass'])

    def test_partial_response_retains_request_and_actor_pending(self):
        result = self.run_https(FakeHTTPS(b'ignored', [0.0], late=True, partial=True))
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(len(self.after), 1)
        self.assertTrue(self.after[0]['unknown'])
        self.assertIsNone(self.after[0]['usage'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertTrue((self.artifacts/'actor.pending.json').exists())
        self.assertEqual(result['tool_events'], [])

    def test_close_failure_keeps_known_usage_and_unknown_fence(self):
        result = self.run_https(FakeHTTPS(canonical(self.finish(1)), [0.0], late=True, close_error=True))
        self.assertTrue(result['unknown_usage'])
        self.assertGreater(result['known_usage']['total_tokens'], 0)
        self.assertGreater(self.after[0]['usage']['total_tokens'], 0)
        self.assertTrue(self.after[0]['unknown'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertFalse(result['quality']['task_success'])

    def test_headers_persistence_failure_never_admits_late_tools(self):
        original = lab._write_new
        def write(path, *args, **kwargs):
            if str(path).endswith('.transport-headers.json'): raise OSError('synthetic persist failure')
            return original(path, *args, **kwargs)
        with patch.object(lab, '_write_new', side_effect=write):
            result = self.run_https(FakeHTTPS(canonical(self.finish(1)), [0.0], late=True))
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(len(self.after), 1)
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertEqual(result['tool_events'], [])

    def test_ontime_chain_still_uses_original_request_and_tool_caps(self):
        steps = self.ready()+[self.finish(4)]
        def body(index, payload):
            value = steps[index-1]
            return canonical(value(payload) if callable(value) else value)
        fake = FakeHTTPS(body, [0.0])
        result = self.run_https(fake)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(result['quality']['hard_pass'])
        self.assertEqual(len(fake.sent), 4)
        self.assertEqual(len(self.after), 4)
        self.assertEqual(result['tool_attempts'], 5)
        self.assertTrue(all(x['settlement']['accounting_only'] is False for x in self.after))

    def test_policy_refuses_default_profile_before_key_or_reservation(self):
        with self.assertRaises(ValueError):
            self.run_actor(settlement_policy=lab.SETTLEMENT_POLICY)
        self.assertEqual(self.before, [])
        self.assertEqual(self.loaded, [])

    def test_after_request_crossing_work_deadline_cannot_execute_first_tool(self):
        fake = FakeHTTPS(canonical(self.read(1)), [0.0])
        original = self.account
        def account(value):
            original(value); fake.clock[0] = 180
        self.account = account
        result = self.run_https(fake)
        self.assertTrue(result['work_deadline_reached'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(len(self.after), 1)
        self.assertFalse(result['quality']['task_success'])

    def test_midbatch_work_cutoff_permanently_blocks_second_tool(self):
        fake = FakeHTTPS(canonical(completion(1, [
            call('read-first', 'repo_read', {'paths':['target.txt','contract.json']}),
            call('patch-late', 'repo_patch', {'operations':[{'path':'target.txt',
                'old_sha256':lab.sha(b'old\n'),'new_text':'forbidden late write\n'}]})])), [0.0])
        create = self.module.create_broker.side_effect
        def wrapped(*args, **kwargs):
            broker = create(*args, **kwargs)
            original = broker.call
            def invoke(name, arguments):
                value = original(name, arguments)
                fake.clock[0] = 180
                return value
            broker.call = invoke
            return broker
        self.module.create_broker.side_effect = wrapped
        result = self.run_https(fake)
        self.assertEqual([x['tool'] for x in result['tool_events']], ['repo_read'])
        self.assertEqual((self.workspace/'target.txt').read_bytes(), b'old\n')
        self.assertFalse(result['quality']['task_success'])

    def test_prior_validation_pass_does_not_bless_late_finish(self):
        steps = self.ready()+[self.finish(4)]
        def body(index, payload):
            value = steps[index-1]
            return canonical(value(payload) if callable(value) else value)
        result = self.run_https(FakeHTTPS(body, [0.0], late=lambda n:n==4))
        self.assertEqual(len(self.executions), 1)
        self.assertTrue(result['quality']['validation']['ok'])
        self.assertFalse(result['quality']['task_success'])
        self.assertFalse(result['quality']['hard_pass'])
        self.assertIsNone(result['final_report'])
        self.assertEqual(len(self.after), 4)

    def test_response_persistence_failure_preserves_known_components_and_fence(self):
        original = lab._write_new
        def write(path, *args, **kwargs):
            if str(path).endswith('01.response.json'): raise OSError('synthetic response persist failure')
            return original(path, *args, **kwargs)
        with patch.object(lab, '_write_new', side_effect=write):
            result = self.run_https(FakeHTTPS(canonical(self.finish(1)), [0.0], late=True))
        self.assertTrue(result['unknown_usage'])
        self.assertGreater(result['known_usage']['total_tokens'], 0)
        self.assertEqual(result['known_usage']['total_tokens'], self.after[0]['usage']['total_tokens'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertEqual(len(self.after), 1)

    def test_accounting_failure_never_repeats_callback_or_releases_request(self):
        def account(value):
            self.after.append(value)
            raise OSError('synthetic ledger publish failure')
        self.account = account
        result = self.run_https(FakeHTTPS(canonical(self.finish(1)), [0.0], late=True))
        self.assertEqual(len(self.after), 1)
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(result['known_usage']['total_tokens'], self.after[0]['usage']['total_tokens'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())

    def test_capture_receipts_bound_to_reservation_and_secret_redacted(self):
        value = self.finish(1)
        value['debug'] = {'secret_echo':SECRET}
        result = self.run_https(FakeHTTPS(canonical(value), [0.0], late=True,
            headers=[('X-Request-ID', SECRET)]))
        self.assertFalse(result['unknown_usage'])
        self.assertEqual(len(self.after), 1)
        for item in self.after[0]['settlement']['capture_receipts']:
            path = self.artifacts/item['receipt_ref']
            raw = path.read_bytes()
            self.assertNotIn(SECRET.encode(), raw)
            self.assertEqual(lab.sha(raw), item['receipt_sha256'])
            record = json.loads(raw)
            self.assertEqual(record['request_id'], self.after[0]['request_id'])
            self.assertEqual(record['reservation_receipt_sha256'], 'c'*64)
            self.assertEqual(record['settlement_deadline_monotonic']-record['work_deadline_monotonic'], 600)

    def test_json_prefix_with_missing_content_length_bytes_remains_unknown(self):
        result = self.run_https(FakeHTTPS(canonical(self.finish(1)), [0.0], late=True, missing_bytes=10))
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(self.after[0]['transport']['exception_class'], 'IncompleteRead')
        self.assertIsNone(self.after[0]['usage'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertEqual(result['tool_events'], [])

    def test_body_after_absolute_settlement_limit_is_not_accounted_or_used(self):
        fake = FakeHTTPS(canonical(self.finish(1)), [0.0], late=True, late_at=781)
        result = self.run_https(fake)
        self.assertTrue(result['unknown_usage'])
        self.assertTrue(result['settlement']['settlement_limit_reached'])
        self.assertFalse(result['settlement']['body_complete'])
        self.assertIsNone(self.after[0]['usage'])
        self.assertEqual(len(fake.sent), 1)
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())

    def test_opt_in_does_not_create_a_thirteenth_request_or_extra_slot(self):
        fake = FakeHTTPS(lambda n,p:canonical(self.read(n)), [0.0])
        result = self.run_https(fake)
        self.assertEqual(len(fake.sent), 12)
        self.assertEqual(len(self.before), 12)
        self.assertEqual(len(self.after), 12)
        self.assertEqual(result['requests'], 12)
        self.assertEqual(result['status'], 'request-budget-exhausted')
        self.assertFalse(result['quality']['task_success'])

    def test_finish_schema_crossing_deadline_never_publishes_report(self):
        fake = FakeHTTPS(canonical(self.finish(1)), [0.0])
        original = lab._schema
        def schema(value, definition, depth=0):
            ok = original(value, definition, depth)
            if isinstance(value, dict) and value.get('summary')=='Public synthetic completion':
                fake.clock[0] = 180
            return ok
        with patch.object(lab, '_schema', side_effect=schema):
            result = self.run_https(fake)
        self.assertIsNone(result['final_report'])
        self.assertFalse((self.artifacts/'report-receipt.json').exists())
        self.assertFalse(result['quality']['task_success'])
        self.assertEqual(len(self.after), 1)




def load_tests(loader, tests, pattern):
    # Discover only this module's new cases, not inherited fixture cases.
    return unittest.TestSuite(cls(name) for cls in (ManagedTransportTests,SettlementActorTests,)
        for name in sorted(cls.__dict__) if name.startswith('test_'))

if __name__ == '__main__': unittest.main()
