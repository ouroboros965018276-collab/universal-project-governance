"""Shared deterministic contracts. Search controls never become governance rules."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
import time


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def materialize(candidate):
    """Map normalized theta to an executable, complete presentation permutation.

    Neutral weights preserve alphabetical order. Only the order of already
    required closures/evidence changes; selection and dependency closure do not.
    """
    model = copy.deepcopy(candidate["model"])
    theta = candidate.get("theta", [0.5, 0.5, 0.5])
    if len(theta) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float))
                              or not math.isfinite(x) or not 0 <= x <= 1 for x in theta):
        raise ValueError("theta must contain three finite normalized values")
    weights = [round((x - 0.5) * 8) for x in theta]
    policies = model["policies"]
    ids = [p["id"] for p in policies]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate policy identity")
    def priority(p):
        features = [int(p["severity"] == "blocking"),
                    len(p.get("requires", [])), len(p.get("evidence", []))]
        return (-sum(w * f for w, f in zip(weights, features)), p["id"])
    model["presentation"] = {"policy_order": [p["id"] for p in sorted(policies, key=priority)]}
    return model


def candidate_id(candidate):
    # Collapse plateaus after legalizing/compiling presentation, not float values.
    return digest(materialize(candidate))


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    max_calls: int = 32
    max_total_tokens: int = 100000
    max_seconds: float = 600
    calls: int = 0
    total_tokens: int = 0
    elapsed_seconds: float = 0
    unknown_usage: bool = False
    records: list = field(default_factory=list)
    _start: float = field(default_factory=time.monotonic, repr=False)

    def __post_init__(self):
        for name in ("max_calls", "max_total_tokens", "calls", "total_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(name + " must be a nonnegative integer")
        if type(self.max_seconds) not in (int, float) or not math.isfinite(self.max_seconds) or self.max_seconds <= 0:
            raise ValueError("max_seconds must be finite and positive")
        if type(self.elapsed_seconds) not in (int, float) or not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and nonnegative")
        if type(self.unknown_usage) is not bool or not isinstance(self.records, list):
            raise ValueError("invalid budget checkpoint metadata")
        if not 0 <= self.calls - len(self.records) <= 1:
            raise ValueError("budget call/receipt count mismatch")
        known_tokens = 0
        for index, receipt in enumerate(self.records):
            if not isinstance(receipt, dict) or receipt.get("attempt") != index + 1:
                raise ValueError("invalid budget receipt sequence")
            total = receipt.get("usage", {}).get("total_tokens")
            if total is None:
                if not self.unknown_usage:
                    raise ValueError("unknown usage flag was cleared")
            elif type(total) is not int or total < 0:
                raise ValueError("invalid checkpoint token total")
            else:
                known_tokens += total
        if known_tokens != self.total_tokens:
            raise ValueError("budget token receipt mismatch")

    def reserve(self, estimated_tokens=0):
        if type(estimated_tokens) is not int or estimated_tokens < 0:
            raise ValueError("invalid token reservation")
        if (self.unknown_usage or self.calls >= self.max_calls
                or self.total_tokens >= self.max_total_tokens
                or self.total_tokens + estimated_tokens > self.max_total_tokens
                or self.elapsed_seconds + time.monotonic() - self._start >= self.max_seconds):
            raise BudgetExceeded("offline call/token/time budget exhausted or usage unknown")
        self.calls += 1  # Failed calls and retries are attempts, too.

    def record(self, usage=None, elapsed_seconds=0, error=None):
        if type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("invalid call elapsed time")
        if usage is not None and not isinstance(usage, dict):
            raise ValueError("usage must be a dictionary or unknown")
        if self.calls != len(self.records) + 1:
            raise ValueError("record must match one reserved call")
        usage = usage or {}
        normalized = {}
        aliases = {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens"}
        for key in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens", "total_tokens"):
            value = usage.get(key, usage.get(aliases.get(key, key)))
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError("invalid provider usage: " + key)
            normalized[key] = value
        total = normalized["total_tokens"]
        if total is None:
            self.unknown_usage = True
        else:
            self.total_tokens += total
        self.records.append({"attempt": self.calls, "usage": normalized,
                             "elapsed_seconds": elapsed_seconds, "error": error,
                             "measurement": usage.get("measurement", "provider"),
                             "fixture": usage.get("fixture", False)})

    def state(self):
        return {"max_calls": self.max_calls, "max_total_tokens": self.max_total_tokens,
                "max_seconds": self.max_seconds, "calls": self.calls,
                "total_tokens": self.total_tokens, "unknown_usage": self.unknown_usage,
                "elapsed_seconds": self.elapsed_seconds + time.monotonic() - self._start,
                "records": copy.deepcopy(self.records)}

    @classmethod
    def from_state(cls, state):
        return cls(**copy.deepcopy(state))
