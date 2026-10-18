"""Synthetic SSE framing and owned fake HTTPS controls; no paid/network/CLI I/O."""
import copy
import http.client
import json
import sys
import threading
import unittest
from unittest.mock import patch

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Provider helper requires Python 3.10+")

from evolution import chat_sse as sse
from evolution import provider_tools as api
from evolution.tool_broker import canonical, sha
from test_provider_tools import _ProviderFixture, completion, call, SECRET
import test_engineering_provider as engineering_fixture


def event(value, ending=b"\r\n"):
    return b"data: " + (value if isinstance(value, bytes) else canonical(value)) + ending * 2


def chunk(delta=None, finish=None, usage=None, choices=True, created=1):
    return {"id": "synthetic-response", "model": "synthetic-model", "object": "chat.completion.chunk",
            "created": created, "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}] if choices else [],
            "usage": usage}


USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
         "prompt_tokens_details": {"cached_tokens": 2}, "completion_tokens_details": {"reasoning_tokens": 1}}


def wire(native, provider="deepseek"):
    choice = native["choices"][0]
    message = choice["message"]
    parts = [chunk({"role": "assistant", "content": message.get("content"),
                    "reasoning_content": message.get("reasoning_content")})]
    for index, tool in enumerate(message.get("tool_calls") or []):
        name, args = tool["function"]["name"], tool["function"]["arguments"]
        split = max(1, len(args) // 2)
        parts.append(chunk({"tool_calls": [{"index": index, "id": tool["id"], "type": tool["type"],
            "function": {"name": name[:3], "arguments": args[:split]}}]}))
        parts.append(chunk({"tool_calls": [{"index": index,
            "function": {"name": name[3:], "arguments": args[split:]}}]}))
    parts.append(chunk(finish=choice["finish_reason"], usage=native["usage"] if provider == "deepseek" else None))
    if provider == "mimo":
        parts.append(chunk(usage=native["usage"], choices=False))
    for i, part in enumerate(parts):
        part.update(id=native["id"], model=native["model"], created=i + 1)
    return b": keep-alive\r\n\r\n" + b"".join(event(part) for part in parts) + event(b"[DONE]")


class SSEProjectionTests(unittest.TestCase):
    def native(self):
        return completion(1, [call("tool-0", "repo_read", {"paths": ["中文.py"]})], content="你好")

    def test_both_provider_shapes_every_byte_split_and_created_variation(self):
        for provider in ("deepseek", "mimo"):
            raw = wire(self.native(), provider)
            expected = sse.project(raw, body_complete=True)
            self.assertTrue(expected["terminal_complete"])
            self.assertTrue(expected["sse"]["message_valid"])
            self.assertEqual(expected["response"]["choices"][0]["message"], self.native()["choices"][0]["message"])
            for split in range(len(raw) + 1):
                parser = sse.ChatSSE()
                parser.feed(raw[:split]); parser.feed(raw[split:])
                self.assertEqual(parser.report(body_complete=True), expected)

    def test_interleaved_tool_names_and_arguments_keep_indexes(self):
        fields = [
            chunk({"tool_calls": [{"index": 1, "id": "b", "type": "function", "function": {"name": "repo_", "arguments": "{"}},
                                   {"index": 0, "id": "a", "type": "function", "function": {"name": "repo_", "arguments": "{"}}]}),
            chunk({"tool_calls": [{"index": 0, "function": {"name": "read", "arguments": "}"}},
                                   {"index": 1, "function": {"name": "status", "arguments": "}"}}]}),
            chunk(finish="tool_calls", usage=USAGE)]
        result = sse.project(b"".join(event(x) for x in fields) + event(b"[DONE]"), body_complete=True)
        tools = result["response"]["choices"][0]["message"]["tool_calls"]
        self.assertTrue(result["terminal_complete"])
        self.assertEqual([(t["id"], t["function"]) for t in tools], [
            ("a", {"name": "repo_read", "arguments": "{}"}), ("b", {"name": "repo_status", "arguments": "{}"})])

    def test_multiline_data_bom_comments_and_all_line_endings(self):
        data = canonical(chunk(finish="stop", usage=USAGE))
        for ending in (b"\n", b"\r", b"\r\n"):
            raw = b"\xef\xbb\xbf: keep-alive" + ending * 2 + b"data: " + data[:1] + ending + b"data: " + data[1:] + ending * 2 + event(b"[DONE]", ending) + b": trailing"
            parser = sse.ChatSSE()
            for byte in raw:
                parser.feed(bytes([byte]))
            self.assertTrue(parser.report(body_complete=True)["terminal_complete"])

    def test_missing_terminal_interruption_and_observed_usage(self):
        finished = event(chunk(finish="stop", usage=USAGE))
        for raw, eof in ((finished, True), (finished + event(b"[DONE]"), False),
                         (event(chunk()) + event(b"[DONE]"), True)):
            result = sse.project(raw, body_complete=eof)
            self.assertFalse(result["terminal_complete"])
        result = sse.project(finished + b"data: {", body_complete=False)
        self.assertEqual(result["response"]["usage"], USAGE)
        self.assertTrue(result["sse"]["usage_observed"])
        # No dispatch of a usage chunk lacking its blank separator.
        result = sse.project(event(chunk(finish="stop")) + event(chunk(usage=USAGE, choices=False))[:-2], body_complete=True)
        self.assertIsNone(result["response"]["usage"])
        result = sse.project(event(chunk(usage=USAGE)) + event(b"[DONE]"), body_complete=True)
        self.assertFalse(result['terminal_complete'])
        self.assertEqual(result['response']['usage'], USAGE)

    def test_malformed_identity_terminal_json_utf8_and_trailing_data(self):
        good = event(chunk(finish="stop", usage=USAGE))
        bad = [good + event(dict(chunk(choices=False, usage=USAGE), model="different")),
               good + event(chunk(choices=False, usage=USAGE)),
               good + event(b"[DONE]") + event(b"[DONE]"),
               good + event(b"[DONE]") + event(chunk()),
               event(b'{"id":"x","id":"x"}'), event(b"\xff"), b"event: x\n\n"]
        for raw in bad:
            self.assertFalse(sse.project(raw, body_complete=True)["terminal_complete"])

    def test_model_envelope_invalid_keeps_transport_usage(self):
        raw = event(chunk({"role": "user", "content": 7, "reasoning_content": []})) + event(chunk(finish="stop", usage=USAGE)) + event(b"[DONE]")
        result = sse.project(raw, body_complete=True)
        self.assertTrue(result["terminal_complete"])
        self.assertFalse(result["sse"]["message_valid"])
        self.assertEqual(result["response"]["usage"], USAGE)

    def test_nonfinite_json_exponent_is_rejected_without_nonjson_projection(self):
        bad = event(chunk(finish='stop', usage=dict(USAGE, extra=1))).replace(b'"extra":1', b'"extra":1e999')
        result = sse.project(bad + event(b'[DONE]'), body_complete=True)
        self.assertFalse(result['terminal_complete'])
        self.assertEqual(result['error_code'], 'sse-invalid-json')
        self.assertNotIn(b'Infinity', canonical(result['response']))

    def test_each_finite_bound_positive_and_plus_one(self):
        raw = event(chunk(finish="stop", usage=USAGE)) + event(b"[DONE]")
        result = sse.project(raw, body_complete=True)
        projection_bytes = len(canonical(result["response"]))
        event_bytes = len(event(chunk(finish="stop", usage=USAGE)))
        for name, cap in (("max_raw", len(raw)), ("max_event", event_bytes),
                          ("max_blocks", 2), ("max_projection", projection_bytes)):
            parser = sse.ChatSSE(**{name: cap}); parser.feed(raw)
            self.assertTrue(parser.report(body_complete=True)["terminal_complete"], name)
            parser = sse.ChatSSE(**{name: cap - 1}); parser.feed(raw)
            report = parser.report(body_complete=True)
            self.assertFalse(report["terminal_complete"], name)
            if name == "max_projection":
                self.assertLessEqual(len(canonical(report["response"])), cap - 1)
        parser = sse.ChatSSE(max_blocks=2); parser.feed(b": comment\n\n" + raw)
        self.assertEqual(parser.report(body_complete=True)["error_code"], "sse-block-limit")

    def test_exact_http_status_media_charset_and_entity_encoding(self):
        for rows in ([('Content-Type', 'text/event-stream')], [('Content-Type', 'Text/Event-Stream; charset="utf-8"')],
                     [('Content-Type', 'text/event-stream; p="a;b"'), ('Content-Encoding', 'identity')]):
            self.assertTrue(sse.headers_valid(200, rows))
        for status, rows in ((201, [('Content-Type', 'text/event-stream')]), (200, []),
                             (200, [('Content-Type', 'application/json')]),
                             (200, [('Content-Type', 'text/event-stream; charset=latin1')]),
                             (200, [('Content-Type', 'text/event-stream'), ('Content-Encoding', 'gzip')])):
            self.assertFalse(sse.headers_valid(status, rows))


class SSEActorTests(engineering_fixture.EngineeringCandidateTests):
    # The inherited focused engineering controls also guard legacy behavior.

    def fake_https(self, steps, provider="deepseek", transform=None, broken=False, close_failure=False, on_eof=None):
        owner = self
        payloads = []
        class Response:
            status = 200
            def __init__(self, body):
                self.body, self.offset = body, 0
                self.length = len(body) + int(broken)
            def getheaders(self):
                return [('content-type', 'text/event-stream; charset=utf-8')]
            def read1(self, maximum):
                if self.offset == len(self.body):
                    if on_eof:
                        on_eof()
                    if broken:
                        raise http.client.IncompleteRead(b'', 1)
                    return b''
                end = min(len(self.body), self.offset + maximum)
                value = self.body[self.offset:end]
                self.offset = end; self.length -= len(value)
                return value
        class Connection:
            sock = None
            def __init__(self, host, timeout):
                self.timeout = timeout
            def connect(self):
                pass
            def request(self, method, path, body, headers):
                payload = json.loads(body)
                payloads.append(copy.deepcopy(payload))
                owner.assertEqual(headers['Accept'], 'text/event-stream')
                step = steps[len(payloads)-1]
                native = step(payload) if callable(step) else copy.deepcopy(step)
                native['model'] = payload['model']
                self.body = wire(native, provider)
                if transform:
                    self.body = transform(self.body)
            def getresponse(self):
                return Response(self.body)
            def close(self):
                if close_failure:
                    raise OSError('synthetic close failure')
        return patch.object(api.http.client, 'HTTPSConnection', Connection), payloads

    def run_sse(self, steps, provider="deepseek", actor_options=None, **kwargs):
        control, payloads = self.fake_https(steps, provider, **kwargs)
        options = dict(profile_id=api.ENGINEERING_REASONING_SSE_PROFILE, thinking='enabled',
                       settlement_policy=api.SETTLEMENT_POLICY, timeout_seconds=600, max_requests=24)
        options.update(actor_options or {})
        with control:
            result = self.new_actor(provider=provider, model='deepseek-v4-pro' if provider == 'deepseek' else 'mimo-v2.6-pro',
                                    **options)
        return result, payloads

    def test_actual_owned_transport_both_providers_raw_projection_history_and_budget(self):
        for provider in ('deepseek', 'mimo'):
            with self.subTest(provider=provider):
                self.artifacts = self.base/('sse-' + provider)
                (self.workspace/'target.txt').write_bytes(b'old\n')
                self.before, self.after, self.loaded = [], [], []
                self.executions = []
                result, payloads = self.run_sse(self.ready()+[self.finish(4)], provider)
                self.assertEqual(result['status'], 'completed')
                self.assertFalse(result['unknown_usage'])
                self.assertTrue(result['quality']['hard_pass'])
                self.assertEqual(len(payloads), 4)
                for payload in payloads:
                    self.assertTrue(payload['stream'])
                    self.assertEqual(payload.get('stream_options'), {'include_usage': True} if provider == 'deepseek' else None)
                    for message in payload['messages']:
                        if message['role'] == 'assistant':
                            self.assertEqual(message['reasoning_content'], 'mock non-private test field')
                for meta in [result, *self.before, *self.after]:
                    self.assertEqual(meta['transport_profile_id'], sse.TRANSPORT_PROFILE)
                    self.assertEqual(meta['max_input_bytes'], 524288)
                for i in range(1, 5):
                    raw = (self.artifacts/('requests/%02d.transport-sse.bin' % i)).read_bytes()
                    record = json.loads((self.artifacts/('requests/%02d.response.json' % i)).read_bytes())
                    capture = json.loads((self.artifacts/('requests/%02d.transport-sse-body.json' % i)).read_bytes())['capture']
                    self.assertEqual(record['body_sha256'], sha(raw))
                    self.assertEqual(capture['raw_body_sha256'], sha(raw))
                    self.assertEqual(record['response'], sse.project(raw, body_complete=True)['response'])
                    self.assertNotIn('body_utf8', capture)
                    self.assertFalse((self.artifacts/('requests/%02d.pending.json' % i)).exists())

    def test_valid_terminal_bad_argument_json_keeps_known_usage_and_once_policy(self):
        bad = completion(1, [call('bad', 'repo_read', {})])
        bad['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = '{bad'
        result, payloads = self.run_sse([bad, completion(2, [call('bad-2', 'unregistered', {})])])
        self.assertFalse(self.after[0]['unknown'])
        self.assertIsNotNone(self.after[0]['usage'])
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertEqual(result['schema_rejections'], 1)
        self.assertEqual(len(payloads), 2)

    def test_semantic_message_invalid_preserves_billing_without_tool(self):
        native = completion(1, content=7)
        result, payloads = self.run_sse([native])
        self.assertEqual(result['status'], 'tool-contract-failed')
        self.assertFalse(result['unknown_usage'])
        self.assertIsNotNone(self.after[0]['usage'])
        self.assertFalse(self.after[0]['unknown'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)

    def test_extra_tool_fragment_keys_cannot_be_hidden_by_projection(self):
        for level in ('call', 'function'):
            self.artifacts = self.base/('extra-key-' + level)
            self.before, self.after, self.loaded = [], [], []
            def poison(body):
                blocks = body.split(b'\r\n\r\n')
                for index, block in enumerate(blocks):
                    if block.startswith(b'data: {'):
                        value = json.loads(block[6:])
                        tools = value['choices'][0]['delta'].get('tool_calls') if value['choices'] else None
                        if tools:
                            target = tools[0] if level == 'call' else tools[0]['function']
                            target['unexpected'] = 1
                            blocks[index] = b'data: ' + canonical(value)
                            break
                return b'\r\n\r\n'.join(blocks)
            result, payloads = self.run_sse([self.read(1)], transform=poison)
            self.assertEqual(result['status'], 'tool-contract-failed')
            self.assertFalse(result['unknown_usage'])
            self.assertIsNotNone(self.after[0]['usage'])
            self.assertEqual(result['tool_events'], [])
            self.assertEqual(len(payloads), 1)

    def test_split_synthetic_credential_is_rejected_before_raw_persistence(self):
        def split(body):
            blocks, seen = body.split(b'\r\n\r\n'), 0
            cut = len(SECRET)//2
            for index, block in enumerate(blocks):
                if block.startswith(b'data: {') and seen < 2:
                    value = json.loads(block[6:])
                    value['choices'][0]['delta']['reasoning_content'] = SECRET[:cut] if seen == 0 else SECRET[cut:]
                    blocks[index] = b'data: ' + canonical(value)
                    seen += 1
            raw = b'\r\n\r\n'.join(blocks)
            self.assertNotIn(SECRET.encode(), raw)
            return raw
        result, payloads = self.run_sse([self.read(1)], transform=split)
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)
        self.assertFalse((self.artifacts/'requests/01.transport-sse.bin').exists())
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        for path in self.artifacts.rglob('*'):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_interruption_retains_prefix_usage_pending_and_no_retry(self):
        result, payloads = self.run_sse([self.read(1)], broken=True)
        self.assertEqual(result['status'], 'unknown-call-blocked')
        self.assertTrue(result['unknown_usage'])
        self.assertIsNotNone(result['known_usage']['input_tokens'])
        self.assertFalse(self.after[0]['settlement']['body_complete'])
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)
        self.assertTrue(self.after[0]['settlement']['worker_done'])
        self.assertFalse(self.after[0]['settlement']['worker_alive_at_return'])

    def test_missing_done_and_close_failure_are_unknown_with_observed_usage(self):
        for mode in ('done', 'close'):
            self.artifacts = self.base/('unknown-' + mode)
            self.before, self.after = [], []
            result, payloads = self.run_sse([self.read(1)], transform=(lambda body: body[:-len(event(b'[DONE]'))]) if mode == 'done' else None,
                                          close_failure=mode == 'close')
            self.assertTrue(result['unknown_usage'])
            self.assertIsNotNone(result['known_usage']['input_tokens'])
            self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
            self.assertEqual(len(payloads), 1)

    def test_v3_requires_managed_settlement_and_rejects_retry_before_reserve_key(self):
        for opts in ({}, {'settlement_policy': api.SETTLEMENT_POLICY, 'connect_retry_policy': api.CONNECT_RETRY_POLICY}):
            with self.assertRaises(ValueError):
                self.new_actor(profile_id=api.ENGINEERING_REASONING_SSE_PROFILE, thinking='enabled', **opts)
        self.assertEqual(self.before, [])
        self.assertEqual(self.loaded, [])

    def test_v3_config_only_adds_explicit_transport_to_v2(self):
        v2 = api.profile_configuration(api.ENGINEERING_REASONING_INPUT_PROFILE)
        self.assertEqual(sha(canonical(v2)), 'd56ad83d4e7339c59c9f2f782f91241e538af1eddb158fc3f1d5373b53fd5ce3')
        v3 = api.profile_configuration(api.ENGINEERING_REASONING_SSE_PROFILE)
        transport = v3.pop('transport')
        v3['profile_id'] = api.ENGINEERING_REASONING_INPUT_PROFILE
        self.assertEqual(v3, v2)
        self.assertEqual(transport['max_raw_body_bytes'], 8388608)
        self.assertEqual(api.MAX_INPUT_BYTES, 131072)

    def test_real_raw_byte_cap_retains_exact_prefix_and_unknown_reserve(self):
        raw = b':' + b'x' * sse.MAX_RAW_BYTES
        result, payloads = self.run_sse([self.read(1)], transform=lambda unused: raw)
        saved = (self.artifacts/'requests/01.transport-sse.bin').read_bytes()
        self.assertEqual(saved, raw[:sse.MAX_RAW_BYTES])
        self.assertTrue(result['unknown_usage'])
        self.assertEqual(len(payloads), 1)
        self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
        self.assertFalse(self.after[0]['settlement']['body_complete'])

    def test_legacy_oversized_chunk_keeps_original_untouched_capture_buffer(self):
        deadline = api.time.perf_counter()+10
        job = api._ManagedRequest('deepseek', {'stream': False}, '', deadline, deadline)
        job.state['body'].extend(b'old')
        with self.assertRaises(api.ResponseUnknown):
            job.capture_chunk(b'x'*(api.MAX_RESPONSE_BYTES+2))
        self.assertEqual(job.snapshot()['body'], b'old')

    def test_v3_large_request_admitted_and_over_cap_stops_before_key_reserve(self):
        result, payloads = self.run_sse([self.read(1)], actor_options={'system_context': 'x'*140000, 'max_requests': 1})
        self.assertGreater(len(canonical(payloads[0])), 131072)
        self.assertLess(len(canonical(payloads[0])), 524288)
        self.assertFalse(result['unknown_usage'])
        self.artifacts = self.base/'over-input-cap'
        self.before, self.after, self.loaded = [], [], []
        result, payloads = self.run_sse([], actor_options={'system_context': 'x'*524288})
        self.assertEqual(result['status'], 'input-byte-cap-not-invoked')
        self.assertEqual((self.before, self.after, self.loaded, payloads), ([], [], [], []))

    def test_late_terminal_only_accounts_and_never_executes_model_action(self):
        now = [100.0]
        with patch.object(api.time, 'perf_counter', side_effect=lambda: now[0]):
            result, payloads = self.run_sse([self.read(1)], on_eof=lambda: now.__setitem__(0, 701.0))
        self.assertEqual(result['status'], 'work-deadline-settled-unfinished')
        self.assertFalse(result['unknown_usage'])
        self.assertIsNotNone(result['known_usage']['input_tokens'])
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)

    def test_v3_phase_stop_binds_raw_binary_and_rejects_wrong_transport(self):
        import time
        started = time.perf_counter()
        def guard(evidence):
            value = dict(evidence, kind='controlled-phase-stop-authorization')
            ref = 'control/phase-stop-authorization.json'
            identity = api._write_new(self.artifacts/ref, value)
            return api.ControlledPhaseStopRequested(ref, identity)
        result, payloads = self.run_sse([self.read(1)], actor_options={
            'actor_timing': {'schema': api.ACTOR_TIMING_SCHEMA, 'started_monotonic': started,
                             'work_deadline_monotonic': started+600},
            'controlled_phase_stop_policy': 'before-first-repository-tool-delivery-v1',
            'controlled_phase_stop_guard': guard})
        self.assertEqual(result['status'], 'controlled-phase-stop-unfinished')
        self.assertEqual(result['tool_events'], [])
        self.assertEqual(len(payloads), 1)
        metadata = dict(self.before[0], transport_profile_id='wrong')
        with self.assertRaises(ValueError):
            api._phase_cut_evidence('before-first-repository-tool-delivery-v1',
                'validated-batch-before-tool-delivery', metadata, self.brokers[0][0], [],
                [call('x', 'repo_read', {'paths': ['target.txt']})], self.artifacts, {}, '', '', 1)

    def test_owned_worker_short_tail_is_joined_before_model_action(self):
        original = api._ManagedRequest._worker
        jobs = []
        def tail(job):
            jobs.append(job)
            original(job)
            threading.Event().wait(0.01)
        with patch.object(api._ManagedRequest, '_worker', tail):
            result, payloads = self.run_sse([self.read(1)], actor_options={'max_requests': 1})
        self.assertFalse(result['unknown_usage'])
        self.assertFalse(self.after[0]['settlement']['worker_alive_at_return'])
        self.assertTrue(all(not job.thread.is_alive() for job in jobs))
        self.assertEqual(len(result['tool_events']), 1)

    def test_owned_worker_still_alive_is_unknown_and_cannot_execute(self):
        original = api._ManagedRequest._worker
        release, jobs = threading.Event(), []
        def tail(job):
            jobs.append(job)
            original(job)
            release.wait(3)
        try:
            with patch.object(api._ManagedRequest, '_worker', tail):
                result, payloads = self.run_sse([self.read(1)])
            self.assertTrue(result['unknown_usage'])
            self.assertEqual(result['tool_events'], [])
            self.assertTrue(self.after[0]['settlement']['worker_done'])
            self.assertTrue(self.after[0]['settlement']['worker_alive_at_return'])
            self.assertIsNotNone(result['known_usage']['input_tokens'])
            self.assertTrue((self.artifacts/'requests/01.pending.json').exists())
            self.assertEqual(len(payloads), 1)
        finally:
            release.set()
            for job in jobs:
                job.thread.join(1)


if __name__ == '__main__':
    unittest.main()
