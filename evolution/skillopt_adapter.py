"""Reuse pinned SkillOpt stages with an explicit, budgeted model capability.

The upstream provider router is deliberately replaced at the import boundary:
it eagerly imports provider SDKs and reads credentials. No vendored file is
modified, no public ``skillopt`` package is shadowed, and only the caller's
backend can make a model call. The optimizer needs Python 3.10+; the governance
runtime retains its independent Python 3.8+ support.
"""
from __future__ import annotations

import builtins
import copy
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import threading
import time
import types
from typing import Any, Callable

from .source_bridge import SourceBridge

if sys.version_info < (3, 10):
    raise RuntimeError("The optional offline evolution optimizer requires Python 3.10+")

_VENDOR = Path(__file__).resolve().parents[1] / "third_party" / "skillopt" / "skillopt"
_PRIVATE = "_upg_skillopt_pinned"
_MODULES: dict[str, types.ModuleType] = {}
_EXECUTED: set[str] = set()
_LOAD_LOCK = threading.RLock()
_RUN_LOCK = threading.RLock()
_ACTIVE_CHAT: Callable[..., tuple[str, Any]] | None = None


def _dispatch_chat(**kwargs):
    if _ACTIVE_CHAT is None:
        raise RuntimeError("SkillOpt has no active explicitly supplied model backend")
    return _ACTIVE_CHAT(**kwargs)


def _namespace(name: str) -> types.ModuleType:
    if name in _MODULES:
        return _MODULES[name]
    private_name = _PRIVATE + name[len("skillopt"):]
    module = types.ModuleType(private_name)
    module.__package__ = private_name
    module.__path__ = [str(_VENDOR.joinpath(*name.split(".")[1:]))]
    _MODULES[name] = module
    sys.modules[private_name] = module
    if "." in name:
        parent, attr = name.rsplit(".", 1)
        setattr(_namespace(parent), attr, module)
    return module


def _vendor_import(name, globals=None, locals=None, fromlist=(), level=0):
    if not level and (name == "skillopt" or name.startswith("skillopt.")):
        module = _load(name)
        for item in fromlist or ():
            if item != "*" and not hasattr(module, item):
                _load(name + "." + item)
        return module if fromlist else _namespace("skillopt")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _load(name: str) -> types.ModuleType:
    """Execute unchanged vendored source in a private import namespace."""
    with _LOAD_LOCK:
        module = _namespace(name)
        if name in _EXECUTED:
            return module
        _EXECUTED.add(name)
        if name == "skillopt":
            return module
        if name == "skillopt.model":
            module.chat_optimizer = _dispatch_chat
            return module
        source = _VENDOR.joinpath(*name.split(".")[1:])
        source = source / "__init__.py" if source.is_dir() else source.with_suffix(".py")
        if not source.is_file():
            _EXECUTED.remove(name)
            raise ImportError(f"Unknown pinned SkillOpt module: {name}")
        module.__file__ = str(source)
        module.__builtins__ = dict(vars(builtins), __import__=_vendor_import)
        try:
            exec(compile(source.read_bytes(), str(source), "exec"), module.__dict__)
        except BaseException:
            _EXECUTED.remove(name)
            raise
        return module


def _upstream(name: str) -> types.ModuleType:
    return _load("skillopt." + name)


_types = _upstream("types")
Patch = _types.Patch
Edit = _types.Edit
RolloutResult = _types.RolloutResult
RawPatch = _types.RawPatch
_BaseEnvAdapter = _upstream("envs.base").EnvAdapter


class BudgetedBackend:
    """Single-call backend protocol plus centrally bounded retries.

    The callable must return ``(response_text, usage_dict_or_None)`` and must
    disable provider/SDK retries itself. Every retry reserves the same shared
    budget before dispatch. An error may expose ``usage``; unavailable usage
    is recorded as unknown and the shared Budget decides whether to stop.
    """

    def __init__(self, backend: Callable, budget, max_retries: int = 2):
        if not callable(backend):
            raise TypeError("model_backend must be callable")
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
            raise ValueError("max_retries must be a nonnegative integer")
        self.backend = backend
        self.budget = budget
        self.max_retries = max_retries
        self.terminal_error: BaseException | None = None
        self._lock = threading.Lock()

    def __call__(self, *, system, user, max_completion_tokens=16384, retries=1, stage="optimizer", **kwargs):
        # Upstream stages request retries=3. Never hand those through to a
        # provider: only this wrapper may reserve and dispatch an attempt.
        with self._lock:
            for attempt in range(self.max_retries + 1):
                try:
                    remaining = self.budget.max_total_tokens - self.budget.total_tokens
                    completion_cap = min(max_completion_tokens, max(0, remaining))
                    self.budget.reserve(estimated_tokens=completion_cap)
                except Exception as exc:
                    self.terminal_error = exc
                    raise
                started = time.monotonic()
                try:
                    result = self.backend(system=system, user=user,
                                          max_completion_tokens=completion_cap, stage=stage)
                    if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[0], str):
                        raise TypeError("backend must return (text, usage_dict_or_None)")
                    response, usage = result
                    if usage is not None and not isinstance(usage, dict):
                        raise TypeError("backend usage must be an object or None")
                except Exception as exc:
                    self._record(getattr(exc, "usage", None), time.monotonic() - started, type(exc).__name__)
                    if attempt == self.max_retries:
                        self.terminal_error = exc
                        raise
                else:
                    self._record(usage, time.monotonic() - started)
                    return response, usage
        raise RuntimeError("unreachable retry state")

    def _record(self, usage, elapsed_seconds, error=None):
        try:
            receipt = usage.get("native_receipt") if isinstance(usage, dict) else None
            if isinstance(receipt, dict) and receipt.get("replayed_from_local_receipt") is True:
                self.budget.release_replayed_reservation()
            else:
                self.budget.record(usage, elapsed_seconds=elapsed_seconds, error=error)
        except Exception as exc:
            self.terminal_error = exc
            raise


class SkillOptLearner:
    """Pinned Reflect → Aggregate → Clip → bound canonical-source Patch."""

    def __init__(self, model_backend, budget, bridge: SourceBridge, *,
                 edit_budget: int = 4, minibatch_size: int = 8, seed: int = 0,
                 max_retries: int = 2):
        if not isinstance(edit_budget, int) or isinstance(edit_budget, bool) or edit_budget < 1:
            raise ValueError("edit_budget must be a positive integer")
        if not isinstance(minibatch_size, int) or isinstance(minibatch_size, bool) or minibatch_size < 1:
            raise ValueError("minibatch_size must be a positive integer")
        self.bridge = bridge
        self.budget = budget
        self.backend = BudgetedBackend(model_backend, budget, max_retries)
        self.edit_budget = edit_budget
        self.minibatch_size = minibatch_size
        self.seed = seed
        self.meta_skill_context = ""
        self.slow_update_context = ""
        self.last_trace: dict[str, Any] = {}

    def learn(self, rollouts, context=None):
        """Accept upstream RolloutResult objects or their plain-dict encoding."""
        global _ACTIVE_CHAT
        rows = [_rollout_dict(row) for row in rollouts]
        if not rows:
            return self.bridge.bind_patch(Patch(reasoning="no rollouts"))
        context_text = context if isinstance(context, str) else json.dumps(context or {}, ensure_ascii=True)
        with _RUN_LOCK, tempfile.TemporaryDirectory(prefix="upg-skillopt-") as temp:
            previous = _ACTIVE_CHAT
            _ACTIVE_CHAT = self.backend
            self.backend.terminal_error = None
            try:
                predictions = Path(temp) / "predictions"
                predictions.mkdir()
                safe_rows = []
                for index, row in enumerate(rows):
                    item = copy.deepcopy(row)
                    item["source_rollout_id"] = item["id"]
                    item["id"] = f"rollout-{index:06d}"
                    folder = predictions / item["id"]
                    folder.mkdir()
                    conversation = item.pop("conversation", None)
                    if conversation is None:
                        # This is a factual score/answer observation, explicitly
                        # labelled as such, never a fabricated execution trace.
                        conversation = [{"role": "system", "content":
                            "Evaluation observation; no execution trace was supplied.\n" +
                            json.dumps(row, ensure_ascii=True, sort_keys=True)}]
                    if not isinstance(conversation, list):
                        raise ValueError("rollout conversation must be a list")
                    (folder / "conversation.json").write_text(json.dumps(conversation, ensure_ascii=True), encoding="ascii")
                    safe_rows.append(item)
                view = self.bridge.export_view()
                reflect = _upstream("gradient.reflect")
                raw = []
                # Sequential minibatches keep budget order reproducible; the
                # upstream analyst functions and their prompts are unchanged.
                for source_type in ("failure", "success"):
                    group = [row for row in safe_rows if bool(row["hard"]) == (source_type == "success")]
                    random.Random(self.seed + (source_type == "success")).shuffle(group)
                    analyst = (reflect.run_error_analyst_minibatch if source_type == "failure"
                               else reflect.run_success_analyst_minibatch)
                    for start in range(0, len(group), self.minibatch_size):
                        result = analyst(view, group[start:start + self.minibatch_size], str(predictions),
                                         edit_budget=self.edit_budget,
                                         step_buffer_context=context_text + "\n" + self.slow_update_context,
                                         meta_skill_context=self.meta_skill_context,
                                         skill_aware_reflection=False)
                        self._raise_terminal()
                        if result:
                            raw.append(RawPatch.from_dict(result))
                failures = [row.patch.to_dict() for row in raw if row.source_type == "failure"]
                successes = [row.patch.to_dict() for row in raw if row.source_type == "success"]
                merged = _upstream("gradient.aggregate").merge_patches(
                    view, failures, successes, workers=1, verbose=False,
                    meta_skill_context=self.meta_skill_context)
                self._raise_terminal()
                selected = _upstream("optimizer.clip").rank_and_select(
                    view, merged, self.edit_budget, meta_skill_context=self.meta_skill_context)
                self._raise_terminal()
                patch = self.bridge.bind_patch(selected)
                self.last_trace = {"upstream_commit": "343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c",
                                   "rollouts": len(rows), "raw_patches": len(raw),
                                   "selected_edits": len(patch.edits),
                                   "source_hash": self.bridge.source_hash,
                                   "stages": ["reflect", "aggregate", "clip", "source_bridge"]}
                return patch
            finally:
                _ACTIVE_CHAT = previous

    def _raise_terminal(self):
        # Upstream intentionally catches provider errors. Budget exhaustion
        # must still stop the outer workflow, rather than yield a fake success.
        if self.backend.terminal_error is not None:
            raise self.backend.terminal_error

    def update_memory(self, previous_rollouts, current_rollouts, *, previous_view: str,
                      current_view: str | None = None) -> dict:
        """Reuse upstream longitudinal guidance only as optimizer-side memory.

        This never adds slow-update blocks or meta text to canonical policy.
        The caller supplies paired training observations, never locked holdout.
        """
        global _ACTIVE_CHAT
        before = [_rollout_dict(row) for row in previous_rollouts]
        after = [_rollout_dict(row) for row in current_rollouts]
        before_ids, after_ids = [row["id"] for row in before], [row["id"] for row in after]
        if len(set(before_ids)) != len(before_ids) or len(set(after_ids)) != len(after_ids) or set(before_ids) != set(after_ids):
            raise ValueError("memory updates require identical unique paired rollout IDs")
        slow = _upstream("optimizer.slow_update")
        pairs = slow.build_comparison_pairs(before, after, after)
        with _RUN_LOCK:
            previous = _ACTIVE_CHAT
            _ACTIVE_CHAT = self.backend
            self.backend.terminal_error = None
            try:
                current = current_view or self.bridge.export_view()
                guidance = slow.run_slow_update(current, before, after, after,
                    prev_skill=previous_view, prev_slow_update_content=self.slow_update_context,
                    comparison_pairs=pairs)
                self._raise_terminal()
                memory = _upstream("optimizer.meta_skill").run_meta_skill(
                    previous_view, current, pairs, prev_meta_skill_content=self.meta_skill_context)
                self._raise_terminal()
                if guidance:
                    self.slow_update_context = guidance["slow_update_content"]
                if memory:
                    self.meta_skill_context = memory["meta_skill_content"]
                return {"slow_update": guidance, "meta_skill": memory}
            finally:
                _ACTIVE_CHAT = previous


def _rollout_dict(row) -> dict:
    value = row.to_dict() if hasattr(row, "to_dict") else copy.deepcopy(row)
    if not isinstance(value, dict) or not all(key in value for key in ("id", "hard", "soft")):
        raise ValueError("rollout requires id, hard, and soft")
    for key in ("hard", "soft"):
        if isinstance(value[key], bool) or not isinstance(value[key], (int, float)) or not math.isfinite(value[key]) or not 0 <= value[key] <= 1:
            raise ValueError("rollout scores must be finite numbers in [0, 1]")
    if value["hard"] not in (0, 1):
        raise ValueError("rollout hard score must be 0 or 1")
    if not isinstance(value["id"], str) or not value["id"]:
        raise ValueError("rollout ID must be a nonempty string")
    return value


class UPGEnvAdapter(_BaseEnvAdapter):
    """SkillOpt environment backed by the caller's actual UPG task evaluator."""

    def __init__(self, evaluator: Callable, tasks, bridge: SourceBridge):
        if not callable(evaluator):
            raise TypeError("evaluator must be callable")
        self.evaluator = evaluator
        self.tasks = tuple(copy.deepcopy(list(tasks)))
        self.bridge = bridge

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        rows = list(copy.deepcopy(self.tasks))
        random.Random(seed).shuffle(rows)
        return rows[:batch_size]

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        if split != "train":
            raise ValueError("learning adapter only accepts train; selection/locked holdout stay in the evaluator")
        return self.build_train_env(env_num, seed)

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs):
        model = kwargs.get("model", self.bridge.model)
        if skill_content != SourceBridge(model).export_view():
            raise ValueError("skill view must match the evaluator's canonical model")
        results = []
        for task in env_manager:
            result = _rollout_dict(self.evaluator(copy.deepcopy(task), copy.deepcopy(model)))
            results.append(result)
        return results

    def get_task_types(self):
        return sorted({str(row.get("task_type", "governance")) for row in self.tasks})


def fixture_backend(*, system: str, user: str, max_completion_tokens: int, stage: str):
    """Deterministic synthetic engineering fixture; never learning evidence.

    Zero tokens mean no provider was invoked. ``measurement=synthetic`` must
    survive budget reporting so this cannot be mistaken for provider usage.
    """
    import re

    usage = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0,
             "measurement": "synthetic", "fixture": True}
    match = re.search(r"^## (policies/[^/\n]+/(?:closure|statement)) sha256=([a-f0-9]{64})\n([^\n]+)", user, re.MULTILINE)
    if stage == "analyst" and match:
        path, origin, text = match.groups()
        edits = [{"op": "replace", "target": text, "content": text + " Verify the affected result.",
                  "update_target": path, "update_origin": origin}]
        result = {"patch": {"reasoning": "synthetic engineering fixture", "edits": edits}}
    elif stage == "merge":
        # The production merge stage sees structured upstream analyst output.
        # The fixture deliberately produces one deterministic bounded edit.
        if match:
            path, origin, text = match.groups()
            result = {"reasoning": "synthetic engineering fixture merge", "edits": [
                {"op": "replace", "target": text, "content": text + " Verify the affected result.",
                 "update_target": path, "update_origin": origin}]}
        else:
            result = {"reasoning": "synthetic engineering fixture", "edits": []}
    elif stage == "ranking":
        result = {"selected_indices": [0], "reasoning": "synthetic engineering fixture"}
    elif stage == "slow_update":
        result = {"slow_update_content": "Synthetic fixture: compare paired training observations."}
    elif stage == "meta_skill":
        result = {"meta_skill_content": "Synthetic fixture: preserve hash-bound policy fields."}
    else:
        result = {"patch": {"reasoning": "synthetic engineering fixture", "edits": []}}
    return json.dumps(result, ensure_ascii=True), usage
