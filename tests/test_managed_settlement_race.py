"""P1 regression from independent review 1ce6bc17; real worker/post, fake HTTPS.

The 24 existing focused methods live unchanged in test_managed_settlement.py.
No actual request, task code, credentials, files or callback is run by workers.
"""
import sys
import unittest
if sys.version_info < (3, 10):
    raise unittest.SkipTest('Managed transport tests require Python 3.10+; no project import attempted')
import json, threading, unittest
from unittest.mock import patch
import evolution.provider_tools as API


class DispatchSnapshotRace(unittest.TestCase):
    def test_commit_winning_after_observer_snapshot_keeps_original_settlement(self):
        clock=[179.0]
        entered,connect_release,sent,reply_release=(threading.Event() for unused in range(4))
        jobs,captures,sends,waits=[],[],[],[]
        main_id=threading.get_ident()
        body=API.canonical({'id':'public-race-response','model':'public-synthetic-model',
            'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'unused late text'}}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
        class Connection:
            sock=None
            def connect(self):
                entered.set()
                if not connect_release.wait(2):raise AssertionError('controlled connect release missing')
            def request(self,*args,**kwargs):sends.append(clock[0]);sent.set()
            def getresponse(self):
                if not reply_release.wait(2):raise AssertionError('controlled response release missing')
                class Response:
                    status=200;offset=0;length=None
                    def getheaders(self):return [('X-Request-ID','public-race-request')]
                    def read1(self,maximum):
                        value=body[self.offset:self.offset+maximum];self.offset+=len(value);return value
                return Response()
            def close(self):pass
        real_snapshot,real_wait=API._ManagedRequest.snapshot,API._ManagedRequest.wait
        first=[True]
        def snapshot(job):
            if threading.get_ident()==main_id and first[0]:
                first[0]=False;jobs.append(job)
                self.assertTrue(entered.wait(1))
                stale=real_snapshot(job)
                self.assertFalse(stale['dispatch_started'])
                connect_release.set();self.assertTrue(sent.wait(1))
                self.assertTrue(real_snapshot(job)['dispatch_started'])
                clock[0]=180.0
                return stale
            return real_snapshot(job)
        def wait(job,seconds,revision):
            waits.append(seconds)
            if real_snapshot(job)['dispatch_started']and clock[0]>=180:
                clock[0]=181.0;reply_release.set()
            real_wait(job,min(.01,max(0,seconds)),revision)
        def capture(kind,value):
            self.assertEqual(threading.get_ident(),main_id)
            captures.append((kind,value))
        try:
            with patch.object(API.time,'perf_counter',side_effect=lambda:clock[0]), \
                 patch.object(API.http.client,'HTTPSConnection',return_value=Connection()), \
                 patch.object(API._ManagedRequest,'snapshot',new=snapshot), \
                 patch.object(API._ManagedRequest,'wait',new=wait), \
                 patch.object(API,'_write_new',side_effect=AssertionError('no worker file writes')):
                observed=API._managed_post('deepseek',{},'public-synthetic-key',180.0,780.0,capture)
                # Clean and prove the response really exists inside the original
                # window even when the v1 observer returned prematurely.
                clock[0]=181.0;reply_release.set();jobs[0].thread.join(2)
                self.assertFalse(jobs[0].thread.is_alive())
                completed=real_snapshot(jobs[0])
                self.assertIsNotNone(completed['response'])
                self.assertEqual(completed['response_completed_monotonic'],181.0)
                self.assertIsNotNone(observed['response'],
                    'Committed attempt was abandoned from stale pre-dispatch state instead of being settled')
                self.assertEqual(observed['response'][2],body)
                self.assertIsNone(observed['failure'])
                self.assertEqual(sends,[179.0])
                self.assertGreaterEqual(len(waits),1)
                self.assertTrue(observed['settlement']['accounting_only'])
                self.assertEqual(observed['settlement']['settlement_deadline_monotonic'],780.0)
                self.assertEqual([kind for kind,value in captures],['headers','body'])
                self.assertEqual(json.loads(observed['response'][2])['usage']['total_tokens'],15)
        finally:
            connect_release.set();reply_release.set()
            for job in jobs:job.thread.join(2)
