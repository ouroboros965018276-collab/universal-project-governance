"""Additional registered v2 boundaries; original24 methods/assertions unchanged."""
import sys
import unittest
if sys.version_info < (3, 10):
    raise unittest.SkipTest('Managed transport tests require Python 3.10+; no project import attempted')
import json,threading,unittest
from unittest.mock import patch
import evolution.provider_tools as API
import test_managed_settlement as prior


class SettlementBoundaryCases(unittest.TestCase):
    def test_headers_body_and_eof_last_tick_have_one_absolute_limit(self):
        body=API.canonical({'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
        for phase in ('headers','body','eof'):
            for tick in (779.999,780.0,780.001):
                with self.subTest(phase=phase,tick=tick):
                    clock,captures=[0.0],[]
                    class Connection:
                        sock=None
                        def connect(self):pass
                        def request(self,*args,**kwargs):pass
                        def getresponse(self):
                            class Response:
                                status=200;length=None;offset=0
                                def getheaders(self):
                                    clock[0]=tick if phase=='headers'else 1.0
                                    return [('X-Request-ID','public-last-tick')]
                                def read1(self,maximum):
                                    if not self.offset:
                                        clock[0]=tick if phase in ('headers','body')else 181.0
                                        self.offset=len(body);return body
                                    clock[0]=tick;return b''
                            return Response()
                        def close(self):pass
                    real_start=API._ManagedRequest.start
                    def start(job):
                        real_start(job);job.thread.join(2)
                        self.assertFalse(job.thread.is_alive())
                    with patch.object(API.time,'perf_counter',side_effect=lambda:clock[0]), \
                         patch.object(API.http.client,'HTTPSConnection',return_value=Connection()), \
                         patch.object(API._ManagedRequest,'start',new=start):
                        result=API._managed_post('deepseek',{},'public-synthetic-key',180,780,lambda *x:captures.append(x))
                    self.assertEqual(result['settlement']['settlement_deadline_monotonic'],780)
                    self.assertTrue(result['settlement']['accounting_only'])
                    if tick<=780:
                        self.assertEqual(result['response'][2],body)
                        self.assertIsNone(result['failure'])
                        self.assertTrue(captures[-1][1]['body_complete'])
                    else:
                        self.assertIsNone(result['response'])
                        self.assertEqual(result['failure']['exception_class'],'TimeoutError')
                        self.assertFalse(result['settlement']['body_complete'])

    def test_header_capture_crossing_work_cutoff_keeps_committed_attempt(self):
        clock=[0.0];release=threading.Event();captures=[];sent=[]
        body=API.canonical({'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
        class Connection:
            sock=None
            def connect(self):pass
            def request(self,*args,**kwargs):sent.append(True)
            def getresponse(self):
                class Response:
                    status=200;length=None;offset=0
                    def getheaders(self):return [('X-Request-ID','public-capture-cross')]
                    def read1(self,maximum):
                        if not release.wait(2):raise AssertionError('capture release missing')
                        clock[0]=181.0
                        chunk=body[self.offset:self.offset+maximum];self.offset+=len(chunk);return chunk
                return Response()
            def close(self):pass
        def capture(kind,value):
            captures.append((kind,value))
            if kind=='headers':clock[0]=180.0;release.set()
        try:
            with patch.object(API.time,'perf_counter',side_effect=lambda:clock[0]), \
                 patch.object(API.http.client,'HTTPSConnection',return_value=Connection()):
                result=API._managed_post('deepseek',{},'public-synthetic-key',180,780,capture)
            self.assertEqual(result['response'][2],body)
            self.assertIsNone(result['failure'])
            self.assertEqual(sent,[True])
            self.assertEqual([x[0]for x in captures],['headers','body'])
            self.assertTrue(result['settlement']['accounting_only'])
        finally:release.set()

    def test_complete_body_with_close_still_hung_preserves_known_facts_and_fence(self):
        clock=[0.0];entered,release=threading.Event(),threading.Event();jobs=[];captures=[]
        body=API.canonical({'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
        class Connection:
            sock=None
            def connect(self):pass
            def request(self,*args,**kwargs):pass
            def getresponse(self):
                class Response:
                    status=200;length=None;offset=0
                    def getheaders(self):return [('X-Request-ID','public-close-hang')]
                    def read1(self,maximum):
                        clock[0]=181.0
                        value=body[self.offset:self.offset+maximum];self.offset+=len(value);return value
                return Response()
            def close(self):entered.set();release.wait(2)
        def wait(job,seconds,revision):
            jobs[:]=[job]
            if job.snapshot()['response']is not None:
                self.assertTrue(entered.wait(1));clock[0]=780.0
            else:
                with job.condition:job.condition.wait(.001)
        try:
            with patch.object(API.time,'perf_counter',side_effect=lambda:clock[0]), \
                 patch.object(API.http.client,'HTTPSConnection',return_value=Connection()), \
                 patch.object(API._ManagedRequest,'wait',new=wait), \
                 patch.object(API,'_write_new',side_effect=AssertionError('worker cannot persist')):
                result=API._managed_post('deepseek',{},'public-synthetic-key',180,780,lambda *x:captures.append(x))
                self.assertEqual(result['response'][2],body)
                self.assertEqual(API._usage(json.loads(body)['usage'])['total_tokens'],15)
                self.assertEqual(result['failure']['phase'],'connection-close')
                self.assertFalse(result['settlement']['worker_done'])
                self.assertTrue(result['settlement']['worker_alive_at_return'])
                count=len(captures);release.set();jobs[0].thread.join(2)
                self.assertFalse(jobs[0].thread.is_alive())
                self.assertEqual(len(captures),count)
        finally:release.set()


class ActorPersistenceBoundaryCases(prior.SettlementActorTests):
    def test_response_parse_crossing_work_cutoff_never_consumes_message(self):
        fake=prior.FakeHTTPS(API.canonical(self.finish(1)),[0.0])
        original=API._native_response_json
        def parse_response(body):
            result=original(body)
            if b'mock-response-1'in body:fake.clock[0]=181.0
            return result
        with patch.object(API,'_native_response_json',side_effect=parse_response) as parse:
            result=self.run_https(fake)
        self.assertEqual(parse.call_count,1)
        self.assertEqual(result['status'],'work-deadline-settled-unfinished')
        self.assertFalse(result['quality']['task_success'])
        self.assertIsNone(result['final_report'])
        self.assertEqual(len(self.after),1)
        self.assertTrue(self.after[0]['settlement']['work_closed'])

    def test_response_write_crossing_cutoff_keeps_usage_once_and_no_finish(self):
        fake=prior.FakeHTTPS(API.canonical(self.finish(1)),[0.0]);original=API._write_new
        def write(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if str(path).endswith('01.response.json'):fake.clock[0]=181.0
            return value
        with patch.object(API,'_write_new',side_effect=write):result=self.run_https(fake)
        self.assertEqual(result['status'],'work-deadline-settled-unfinished')
        self.assertFalse(result['quality']['task_success'])
        self.assertEqual(result['known_usage']['total_tokens'],self.after[0]['usage']['total_tokens'])
        self.assertIsNone(result['final_report'])
        self.assertEqual(len(self.after),1)

    def test_native_outcome_write_crossing_cutoff_does_not_rewrite_prior_observation(self):
        fake=prior.FakeHTTPS(API.canonical(self.finish(1)),[0.0]);original=API._write_new
        def write(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if str(path).endswith('01.receipt.json'):fake.clock[0]=181.0
            return value
        with patch.object(API,'_write_new',side_effect=write):result=self.run_https(fake)
        self.assertFalse(self.after[0]['settlement']['work_closed'])
        self.assertTrue(result['work_deadline_reached'])
        self.assertFalse(result['quality']['task_success'])
        self.assertIsNone(result['final_report'])
        raw=(self.artifacts/'requests/01.receipt.json').read_bytes()
        self.assertEqual(API.sha(raw),self.after[0]['receipt_sha256'])
        self.assertEqual(len(self.after),1)

    def test_ontime_report_publication_overrun_is_preserved_but_never_success(self):
        steps=self.ready()+[self.finish(4)]
        def body(n,p):
            value=steps[n-1];return API.canonical(value(p)if callable(value)else value)
        fake=prior.FakeHTTPS(body,[0.0]);original=API._write_new
        def write(path,*args,**kwargs):
            report=str(path).endswith('report-receipt.json')
            if report:fake.clock[0]=179.0
            value=original(path,*args,**kwargs)
            if report:fake.clock[0]=181.0
            return value
        with patch.object(API,'_write_new',side_effect=write):result=self.run_https(fake)
        self.assertTrue((self.artifacts/'report-receipt.json').exists())
        self.assertEqual(result['status'],'work-deadline-settled-unfinished')
        self.assertFalse(result['quality']['hard_pass'])
        self.assertFalse(result['quality']['task_success'])
        self.assertTrue((self.artifacts/'actor.pending.json').exists())
        self.assertEqual(len(self.after),4)
        self.assertGreaterEqual(result['wall_seconds'],181.0)

    def test_callback_published_then_raised_is_not_repeated_or_released(self):
        def account(value):
            self.after.append(value)
            API._write_new(self.base/'synthetic-ledger-publish.json',value)
            raise OSError('synthetic error after durable ledger publication')
        self.account=account
        result=self.run_https(prior.FakeHTTPS(API.canonical(self.finish(1)),[0.0],late=True))
        self.assertTrue((self.base/'synthetic-ledger-publish.json').exists())
        self.assertEqual(len(self.after),1)
        self.assertTrue(result['unknown_usage'])
        self.assertGreater(result['known_usage']['total_tokens'],0)
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertTrue((self.artifacts/'actor.pending.json').exists())


def load_tests(loader, tests, pattern):
    # Discover only this module's new cases, not inherited fixture cases.
    return unittest.TestSuite(cls(name) for cls in (SettlementBoundaryCases,ActorPersistenceBoundaryCases,)
        for name in sorted(cls.__dict__) if name.startswith('test_'))
