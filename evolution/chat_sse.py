"""Bounded official Chat SSE projection. No I/O, tools or billing decisions.

Raw entity bytes remain the evidence. This producer projection is deliberately
not an independent reader, and never parses model tool argument JSON.
"""
from __future__ import annotations

import copy
import json
import math
import re

TRANSPORT_PROFILE = "chat-completions-sse-terminal-usage-v1"
PROJECTION_SCHEMA = "chat-completions-sse-projection-v1"
MAX_RAW_BYTES = 8_388_608
MAX_EVENT_BYTES = 262_144
MAX_BLOCKS = 65_536
MAX_PROJECTION_BYTES = 2_097_152


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError("duplicate-json-key")
        result[key] = value
    return result


def _text(value):
    if type(value) is not str:
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite-json-number")
    return number


def headers_valid(status, headers):
    """HTTP entity is UTF-8 SSE; no implicit compression/decompression."""
    if status != 200:
        return False
    rows = [(k.casefold(), v) for k, v in headers]
    media = [v for k, v in rows if k == "content-type"]
    coding = [v.strip().casefold() for k, v in rows if k == "content-encoding"]
    if len(media) != 1 or len(coding) > 1 or coding and coding != ["identity"]:
        return False
    # Parameters are bounded by the existing header capture limit. Accept the
    # standard token/quoted-string grammar, not an ad-hoc split on semicolons.
    token = r"[!#$%&'*+.^_`|~0-9A-Za-z-]+"
    quoted = r'"(?:[\t !#-\[\]-~]|\\[\t -~])*"'
    match = re.fullmatch(r"\s*text/event-stream\s*((?:;\s*" + token + r"\s*=\s*(?:" + token + "|" + quoted + r")\s*)*)", media[0], re.I)
    if match is None:
        return False
    params = re.findall(r";\s*(" + token + r")\s*=\s*(" + token + "|" + quoted + ")", match[1])
    seen = set()
    for name, value in params:
        name = name.casefold()
        if name in seen:
            return False
        seen.add(name)
        if name == "charset" and value.strip('"').casefold() not in {"utf-8", "utf8"}:
            return False
    return True


class ChatSSE:
    """Incremental byte framing; every buffer has a fixed finite bound."""
    def __init__(self, *, max_raw=MAX_RAW_BYTES, max_event=MAX_EVENT_BYTES,
                 max_blocks=MAX_BLOCKS, max_projection=MAX_PROJECTION_BYTES):
        self.limits = max_raw, max_event, max_blocks, max_projection
        self.raw_bytes = self.block_bytes = self.blocks = self.events = 0
        self.buffer = bytearray()
        self.data = []
        self.block_nonempty = False
        self.first_line = True
        self.done = False
        self.error = None
        self.identifier = self.model = self.finish = self.usage = None
        self.content = self.reasoning = None
        self.tools = {}
        self.message_valid = True

    def _fail(self, code):
        if self.error is None:
            self.error = code

    def feed(self, chunk):
        if type(chunk) is not bytes:
            self._fail("sse-chunk-type")
            return
        maximum = self.limits[0]
        accepted = chunk[:max(0, maximum - self.raw_bytes)]
        self.raw_bytes += len(accepted)
        if self.error is None:
            self.buffer.extend(accepted)
            while self.error is None:
                match = re.search(b"\r\n|\r|\n", self.buffer)
                if match is None or match[0] == b"\r" and match.end() == len(self.buffer):
                    if self.block_bytes + len(self.buffer) > self.limits[1]:
                        self._fail("sse-event-byte-limit")
                    break
                line = bytes(self.buffer[:match.start()])
                count = match.end()
                del self.buffer[:count]
                self._line(line, count)
        if len(accepted) != len(chunk):
            self._fail("sse-raw-byte-limit")

    def _line(self, raw, count):
        self.block_bytes += count
        if self.block_bytes > self.limits[1]:
            self._fail("sse-event-byte-limit")
            return
        try:
            line = raw.decode("utf-8")
        except UnicodeError:
            self._fail("sse-invalid-utf8")
            return
        if self.first_line:
            line = line.removeprefix("\ufeff")
            self.first_line = False
        if not line:
            if self.block_nonempty:
                self.blocks += 1
                if self.blocks > self.limits[2]:
                    self._fail("sse-block-limit")
                elif self.data:
                    self._event("\n".join(self.data))
            self.data = []
            self.block_nonempty = False
            self.block_bytes = 0
            return
        self.block_nonempty = True
        if line.startswith(":"):
            return
        name, separator, value = line.partition(":")
        if name != "data":
            self._fail("sse-unsupported-field")
            return
        if separator and value.startswith(" "):
            value = value[1:]
        self.data.append(value)

    def _event(self, value):
        self.events += 1
        if self.done:
            self._fail("sse-data-after-done")
            return
        if value == "[DONE]":
            self.done = True
            return
        before = copy.deepcopy((self.identifier, self.model, self.finish, self.usage,
                                self.content, self.reasoning, self.tools, self.message_valid))
        try:
            raw = json.loads(value, object_pairs_hook=_pairs,
                             parse_float=_finite_float,
                             parse_constant=lambda unused: (_ for _ in ()).throw(ValueError()))
        except (ValueError, RecursionError):
            self._fail("sse-invalid-json")
            return
        if (type(raw) is not dict or raw.get("object") != "chat.completion.chunk"
                or not _text(raw.get("id")) or not raw["id"]
                or not _text(raw.get("model")) or not raw["model"]
                or type(raw.get("choices")) is not list):
            self._fail("sse-chunk-envelope")
            return
        if self.identifier is None:
            self.identifier, self.model = raw["id"], raw["model"]
        if (self.identifier, self.model) != (raw["id"], raw["model"]):
            self._fail("sse-response-identity")
            return
        choices = raw["choices"]
        if choices:
            if len(choices) != 1 or type(choices[0]) is not dict or type(choices[0].get("index")) is not int or choices[0]["index"] != 0 or self.finish is not None:
                self._fail("sse-choice-terminal")
                return
            choice = choices[0]
            delta = choice.get("delta")
            if type(delta) is not dict:
                self.message_valid = False
            else:
                self._delta(delta)
            finish = choice.get("finish_reason")
            if finish is not None:
                if type(finish) is not str or not finish:
                    self._fail("sse-finish-reason")
                    return
                self.finish = finish
        elif raw.get("usage") is None:
            self._fail("sse-empty-choice-chunk")
            return
        if raw.get("usage") is not None:
            if self.usage is not None or type(raw["usage"]) is not dict:
                self._fail("sse-terminal-usage")
                return
            self.usage = raw["usage"]
            if self.finish is None:
                # A valid observed component is not a complete terminal. Keep
                # it for honest accounting while retaining unknown exposure.
                self._fail("sse-terminal-usage")
        try:
            oversized = len(_canonical(self.response())) > self.limits[3]
        except (UnicodeError, ValueError, RecursionError):
            oversized = True
            self._fail("sse-invalid-json")
        if oversized:
            (self.identifier, self.model, self.finish, self.usage,
             self.content, self.reasoning, self.tools, self.message_valid) = before
            self._fail("sse-projection-byte-limit")

    def _delta(self, delta):
        if "role" in delta and delta["role"] not in (None, "assistant"):
            self.message_valid = False
        for name, attr in (("content", "content"), ("reasoning_content", "reasoning")):
            part = delta.get(name)
            if part is not None:
                if not _text(part):
                    self.message_valid = False
                else:
                    setattr(self, attr, (getattr(self, attr) or "") + part)
        calls = delta.get("tool_calls")
        if calls is None:
            return
        if type(calls) is not list or len(calls) > 32:
            self.message_valid = False
            return
        for call in calls:
            if type(call) is not dict or type(call.get("index")) is not int or not 0 <= call["index"] < 32:
                self.message_valid = False
                continue
            if not set(call) <= {"index", "id", "type", "function"}:
                self.message_valid = False
            target = self.tools.setdefault(call["index"], {"id": None, "type": None, "function": {"name": "", "arguments": ""}})
            for name in ("id", "type"):
                value = call.get(name)
                if value not in (None, ""):
                    if not _text(value) or target[name] not in (None, value):
                        self.message_valid = False
                    else:
                        target[name] = value
            function = call.get("function")
            if function is None:
                continue
            if type(function) is not dict:
                self.message_valid = False
                continue
            if not set(function) <= {"name", "arguments"}:
                self.message_valid = False
            for name in ("name", "arguments"):
                part = function.get(name)
                if part is not None:
                    if not _text(part):
                        self.message_valid = False
                    else:
                        target["function"][name] += part

    def response(self):
        return {"id": self.identifier, "model": self.model, "object": "chat.completion",
                "choices": [{"index": 0, "finish_reason": self.finish, "message": {
                    "role": "assistant", "content": self.content,
                    "reasoning_content": self.reasoning,
                    "tool_calls": [self.tools[i] for i in sorted(self.tools)] or None}}], "usage": self.usage}

    def report(self, *, body_complete):
        # EOF alone does not dispatch an unterminated event. A terminal CR is
        # a full newline, but a data block still needs its blank separator.
        if self.error is None and body_complete and self.buffer.endswith(b"\r"):
            self._line(bytes(self.buffer[:-1]), len(self.buffer))
            self.buffer.clear()
        if self.error is None and body_complete and self.done and not self.data:
            # Trailing comments/whitespace need no dispatched data event.
            tail = bytes(self.buffer)
            if not tail.strip() or tail.startswith(b":"):
                try:
                    tail.decode("utf-8")
                except UnicodeError:
                    self._fail("sse-invalid-utf8")
                if self.block_bytes + len(tail) > self.limits[1]:
                    self._fail("sse-event-byte-limit")
                self.buffer.clear()
                self.block_nonempty = False
        if self.tools and (sorted(self.tools) != list(range(len(self.tools))) or any(
                type(v["id"]) is not str or not v["id"] or v["type"] != "function"
                or not v["function"]["name"] for v in self.tools.values())):
            self.message_valid = False
        if self.error is None and (self.buffer or self.block_nonempty):
            self._fail("sse-undispatched-tail")
        terminal = self.error is None and body_complete and self.done and self.finish is not None and self.usage is not None
        return {"response": self.response(), "sse": {"block_count": self.blocks,
            "data_event_count": self.events, "done": self.done, "finish_reason": self.finish,
            "usage_observed": self.usage is not None, "message_valid": self.message_valid},
            "terminal_complete": terminal, "error_code": self.error or (None if terminal else "sse-incomplete-terminal")}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def project(body, *, body_complete):
    parser = ChatSSE()
    # Same finite read-sized feeds used by the owned HTTPS transport.
    for offset in range(0, len(body), 65536):
        parser.feed(body[offset:offset + 65536])
    return parser.report(body_complete=body_complete)
