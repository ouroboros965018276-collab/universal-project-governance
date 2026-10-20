"""Inert immutable finite-map ledger derived from reviewed API4 primitives.

No historical ledger is imported, patched, resumed or read. All caps are
prospective conservative envelopes, not used fees, refunds or invoices.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from managed_contract_primary import (POLICY, ADAPTER, TIMING_SCHEMA, REGISTRATION_FIELDS,
    validate_registry, derive_caps, strict_json, number, managed_deadline_valid as deadline_valid)

PROFILE_ID = 'thinking-disabled-deepseek-pro-mimo-flash-8192-v1'
EXECUTION_BACKEND = "docker-cpython-project-v1"
BROKER_PROFILE_ID = "stdlib-python-project-v1"
CONFIGURATION_SHA256 = 'db21a61c86bb3398f9b9568cdb290482407115dfc1ac0be3c21b8fb62ac8ced6'
DISABLED_PROFILE_ID = 'thinking-disabled-deepseek-pro-mimo-flash-8192-v1'
DISABLED_CONFIGURATION_SHA256 = 'db21a61c86bb3398f9b9568cdb290482407115dfc1ac0be3c21b8fb62ac8ced6'
CONNECT_RETRY_POLICY = "confirmed-pre-http-connect-once-v1"
TOOL_FEEDBACK_POLICY = None

BOUND_FIELDS = ("provider", "model_requested", "profile_id", "thinking", "reasoning_effort_requested",
                "request_index", "input_utf8_bytes", "output_cap", "request_payload_sha256", "input_task_sha256", "adapter", "profile_configuration_sha256", "execution_backend", "tool_feedback_policy", "broker_profile_id", "connect_retry_policy", "retry_of_request_id", "settlement_policy", "settlement_max_seconds", "work_deadline_monotonic", "settlement_deadline_monotonic")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def immutable(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(data)


def connect_retry_eligible(metadata, *, actor_id, actor_registry):
    # Independent ledger enforcement: no adapter predicate import.
    value = metadata.get("transport")
    return (isinstance(value, dict)
        and set(value) == {"phase", "exception_class", "connection_attempted", "http_dispatch"}
        and value["phase"] == "connect" and value["connection_attempted"] is True
        and value["http_dispatch"] == "not_started"
        and value["exception_class"] in {"TimeoutError", "gaierror", "ConnectionRefusedError", "ConnectionResetError"}
        and metadata.get("error_type") == "ResponseUnknown"
        and metadata.get("not_invoked") is True and metadata.get("dispatched") is False
        and metadata.get("unknown") is False and metadata.get("unexpected_overrun") == {}
        and "usage" in metadata and metadata["usage"] is None
        and all(name in metadata and metadata[name] is None
            for name in ("api_response_id", "response_sha256", "model_reported"))
        and valid_sha(metadata.get("receipt_sha256")) and deadline_valid(metadata, actor_id=actor_id, actor_registry=actor_registry))


def native_outcome_receipt_matches(run_root, actor, metadata):
    """A retry permit binds existing native bytes, never just a callback claim."""
    if (type(actor) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", actor) is None
            or type(metadata.get("request_index")) is not int or not 1 <= metadata["request_index"] <= 12
            or not valid_sha(metadata.get("receipt_sha256"))):
        return False
    path = Path(run_root) / "actors" / actor / "artifacts" / "requests" / ("%02d.receipt.json" % metadata["request_index"])
    try:
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 1024 or not path.is_file():
            return False
        raw = path.read_bytes()
    except OSError:
        return False
    expected = {key: value for key, value in metadata.items() if key != "receipt_sha256"}
    return sha(raw) == metadata["receipt_sha256"] and raw == canonical(expected) + b"\n"




class StudyStop(RuntimeError):
    pass


class Ledger:
    def __init__(self, path, *, configuration, actor_registry, registry_identity, registration_binding, caps,
                 finalization_policy, clock=time.perf_counter, started_monotonic,
                 profile_id=PROFILE_ID, connect_retry_policy=None, tool_feedback_policy=None):
        if (profile_id != PROFILE_ID or type(configuration) is not dict
                or sha(canonical(configuration)) != CONFIGURATION_SHA256
                or configuration.get('profile_id') != profile_id):
            raise ValueError('explicit reviewed fixed Pro/Flash configuration required')
        registry = validate_registry(actor_registry, registry_identity=registry_identity)
        if (type(registration_binding) is not dict or set(registration_binding) != REGISTRATION_FIELDS
                or not all(valid_sha(v) for v in registration_binding.values())):
            raise ValueError('UNBOUND or invalid primary registration; no ledger admission')
        expected_caps = derive_caps(registry, configuration, registry_identity=registry_identity, finalization_policy=finalization_policy)
        if canonical(caps) != canonical(expected_caps):
            raise ValueError('caps must derive from the entire fixed finite registry and explicit finalization policy')
        if type(connect_retry_policy) is not str or connect_retry_policy != CONNECT_RETRY_POLICY:
            raise ValueError('explicit confirmed-pre-HTTP-connect-once policy required')
        if tool_feedback_policy is not None:
            raise ValueError('legacy finite-language feedback forbidden')
        observed = clock()
        if not number(started_monotonic) or not number(observed) or started_monotonic > observed:
            raise ValueError('round first-setup clock required')
        self.tool_feedback_policy = tool_feedback_policy
        self._persistence_fault = None
        self._after_baseline = None
        self._failure_observation_attempted = False
        self._key_permit = None
        self.profile_id, self.configuration_sha256 = profile_id, CONFIGURATION_SHA256
        self.connect_retry_policy = connect_retry_policy
        self.bound_fields = tuple(name for name in BOUND_FIELDS if name != 'tool_feedback_policy')
        self.configuration = copy.deepcopy(configuration)
        self.models = {provider: value['model'] for provider, value in configuration['providers'].items()}
        self.prices = copy.deepcopy(configuration['prices'])
        self.actor_registry = registry
        self.registry_identity = copy.deepcopy(registry_identity)
        self.registration_binding = copy.deepcopy(registration_binding)
        self.path, self.clock, self.started = Path(path), clock, started_monotonic
        self.caps = copy.deepcopy(expected_caps)
        if self.path.exists():
            raise StudyStop('existing ledger is never reset or resumed')
        self.state = {'status': 'running', 'known_reported_tokens': 0, 'request_slots': 0,
            'dispatched_requests': 0, 'pending': {}, 'requests': [], 'api_response_ids': [],
            'profile_id': self.profile_id, 'profile_configuration_sha256': self.configuration_sha256,
            'execution_backend': EXECUTION_BACKEND, 'prices': copy.deepcopy(self.prices),
            'price_evidence': copy.deepcopy(configuration['price_evidence']),
            'actor_registry': copy.deepcopy(registry), 'registry_identity': copy.deepcopy(registry_identity),
            'registration_binding': copy.deepcopy(registration_binding),
            'actor_clocks': {}, 'current_actor': None,
            'accounts': {provider: {currency: {'committed_estimate': '0', 'reserved_estimate': '0',
                'cap': self.caps[provider + '_' + currency]} for currency in currencies}
                for provider, currencies in self.prices.items()},
            'limits': {'actors': self.caps['actors'], 'workflows': self.caps['workflows'], 'blocks': self.caps['blocks'],
                'http_attempts': self.caps['request_slots'],
                'requests_per_actor': 12, 'output_per_request': 8192, 'serialized_input_utf8_bytes_per_request': 131072,
                'tools_per_actor': 32, 'actor_work_and_dispatch_budgets': copy.deepcopy(registry),
                'settlement_tail_seconds': 600, 'theoretical_request_slots': self.caps['request_slots'],
                'workflow_seconds_soft': copy.deepcopy(self.caps['workflow_seconds_soft']),
                'finalization_policy': copy.deepcopy(finalization_policy),
                'reported_tokens_soft_stop': self.caps['known_reported_tokens_soft'],
                'round_seconds_soft_stop': self.caps['round_seconds_soft'], 'ordinary_failure_stop_limit': None},
            'connect_retry_policy': connect_retry_policy, 'invoice_or_hard_provider_billing_cap': False,
            'registration_is_not_launch_authorization': True,
            'currency_alternatives_are_not_summed': True,
            'unmeasured_usage_is_unknown_not_zero': True}
        self.publish()

    def start_actor(self, actor_id, timing):
        """Persist the caller's first-setup clock, never a fresh per-request clock."""
        if self._persistence_fault is not None:
            raise StudyStop('accounting-persistence-unknown-global-stop')
        observed = self.clock()
        if (self.state['status'] != 'running' or self.state['pending'] or actor_id not in self.actor_registry
                or actor_id in self.state['actor_clocks'] or type(timing) is not dict
                or set(timing) != {'schema', 'started_monotonic', 'work_deadline_monotonic'}
                or timing['schema'] != TIMING_SCHEMA or not number(observed)
                or not all(number(timing[k]) for k in ('started_monotonic', 'work_deadline_monotonic'))
                or not self.started <= timing['started_monotonic'] <= observed < timing['work_deadline_monotonic']
                or timing['work_deadline_monotonic'] - timing['started_monotonic'] != 180):
            raise StudyStop('invalid-or-reopened-actor-first-setup-clock')
        if observed - self.started >= self.caps['round_seconds_soft']:
            self.stop('development-budget-stop-before-actor-setup')
            raise StudyStop(self.state['status'])
        self._key_permit = None
        self.state['actor_clocks'][actor_id] = copy.deepcopy(timing)
        self.state['current_actor'] = actor_id
        self.publish()
        return copy.deepcopy(timing)

    def guarded_key(self, actor_id, loader):
        """Return API7's provider-only callback; no key is loaded at construction."""
        if not callable(loader) or actor_id not in self.actor_registry:
            raise ValueError('registered lazy key callback required')
        def key(provider):
            permit = self._key_permit
            if (self._persistence_fault is not None or self.path.with_name('ledger.failure.json').exists()
                    or self.state['status'] != 'running' or permit is None
                    or permit['actor_id'] != actor_id or permit['provider'] != provider
                    or self.clock() >= self.state['actor_clocks'][actor_id]['work_deadline_monotonic']):
                raise StudyStop('key requires current durable reservation within original actor clock')
            durable = strict_json(self.path.read_bytes())
            if canonical(durable) != canonical(self.state) or durable['status'] != 'running' or len(durable['pending']) != 1:
                raise StudyStop('key durable ledger differs')
            identifier, row = next(iter(durable['pending'].items()))
            if (identifier != permit['request_id'] or row['actor_id'] != actor_id or row['provider'] != provider
                    or provider != self.actor_registry[actor_id]['provider'] or row['status'] != 'reserved-before-send'
                    or row['reservation_receipt_sha256'] != permit['reservation_receipt_sha256']):
                raise StudyStop('key reservation actor/provider/request differs')
            receipt_path = self.path.parent / row['reservation_receipt_path']
            raw = receipt_path.read_bytes()
            saved = strict_json(raw)
            expected = {name: value for name, value in row.items()
                        if name not in ('reservation_receipt_sha256', 'reservation_receipt_path')}
            if (sha(raw) != row['reservation_receipt_sha256']
                    or any(saved.get(name) != value for name, value in expected.items())
                    or saved.get('kind') != 'immutable-pre-dispatch-reservation-v1'):
                raise StudyStop('key immutable reservation differs')
            self._key_permit = None  # One attempt, even if the external lazy loader fails.
            return loader(provider)
        return key

    def publish(self):
        if self._persistence_fault is not None:
            raise StudyStop('accounting-persistence-unknown-global-stop')
        try:
            self.state["elapsed_seconds"] = self.clock() - self.started
            save_run(self.path, self.state)
        except BaseException as error:
            self._persistence_fault = {'exception_class': type(error).__name__,
                'attempted_state_sha256': sha(canonical(self.state)),
                'phase': 'after-request-commit' if self._after_baseline is not None else 'ledger-publication'}
            if self._after_baseline is None:
                self.state.update(status='accounting-persistence-unknown-global-stop', stop_reason='accounting-persistence-unknown-global-stop')
                self._emit_failure_observation()
            raise

    def _emit_failure_observation(self):
        # A distinct observation is not a second write/retry of the uncertain
        # ledger commit. Never overwrite either original ledger or this fence.
        if self._failure_observation_attempted:
            return
        self._failure_observation_attempted = True
        observation = {'kind':'ledger-persistence-unknown-v1', 'unknown_commit':True,
            'first_error':copy.deepcopy(self._persistence_fault), 'retained_state':copy.deepcopy(self.state),
            'scope':'observed usage once plus original reserved exposure; not invoice or a confirmed commit'}
        self.failure_observation = copy.deepcopy(observation)
        try:
            self.failure_observation_sha256 = immutable(self.path.with_name('ledger.failure.json'), observation)
        except BaseException as error:
            self.failure_observation_error = type(error).__name__
            try:
                sys.stderr.write(json.dumps({'ledger_failure_observation_unpublished':type(error).__name__,
                    'first_error':self._persistence_fault['exception_class']},sort_keys=True)+'\n');sys.stderr.flush()
            except BaseException:
                pass

    def stop(self, reason):
        if self._persistence_fault is not None:
            return False
        self.state.update(status=reason, stop_reason=reason)
        self.publish()

    def refresh_tail(self):
        if self._persistence_fault is not None:
            return False  # No generic tail may retry an uncertain business write.
        self.publish()
        exceeded = {}
        if self.state["elapsed_seconds"] > self.caps["round_seconds_soft"]:
            exceeded["round_seconds"] = self.state["elapsed_seconds"]
        if self.state["known_reported_tokens"] > self.caps["known_reported_tokens_soft"]:
            exceeded["known_reported_tokens"] = self.state["known_reported_tokens"]
        if self.state["request_slots"] > self.caps["request_slots"]:
            exceeded["request_slots"] = self.state["request_slots"]
        if exceeded:
            self.state["development_actual_overrun"] = exceeded
            if self.state["status"] in {"running", "completed"}:
                self.state.update(status="development-late-overrun-global-stop", stop_reason="development-late-overrun-global-stop")
            self.publish()

    def estimate(self, provider, inputs, outputs):
        return {currency: (Decimal(inputs) * Decimal(row["input_miss"]) + Decimal(outputs) * Decimal(row["output"])) / 1_000_000
                for currency, row in self.prices[provider].items()}

    def before(self, actor, provider, model, metadata):
        if self._persistence_fault is not None:
            raise StudyStop('accounting-persistence-unknown-global-stop')
        if self.state["status"] != "running":
            raise StudyStop(self.state["status"])
        if (self.clock() - self.started >= self.caps["round_seconds_soft"]
                or self.state["known_reported_tokens"] >= self.caps["known_reported_tokens_soft"]
                or self.state["request_slots"] >= self.caps["request_slots"]):
            self.stop("development-budget-stop-before-send")
            raise StudyStop(self.state["status"])
        identifier, inputs = metadata.get("request_id"), metadata.get("input_utf8_bytes")
        requests = [row for row in self.state["requests"] if row["actor_id"] == actor]
        budget=self.actor_registry.get(actor)
        timing=self.state["actor_clocks"].get(actor)
        if (budget is None or timing is None or self.state['current_actor'] != actor or budget['provider']!=provider
                or metadata.get('work_deadline_monotonic') != timing['work_deadline_monotonic']
                or timing['work_deadline_monotonic'] - self.clock() < budget['minimum_dispatch_window_seconds']
                or metadata.get('settlement_policy')!=POLICY
                or type(metadata.get('settlement_max_seconds'))is not int or metadata['settlement_max_seconds']!=600
                or not all(type(metadata.get(k))in(int,float) and __import__('math').isfinite(metadata[k])for k in('work_deadline_monotonic','settlement_deadline_monotonic'))
                or metadata['settlement_deadline_monotonic']-metadata['work_deadline_monotonic']!=600
                or self.clock()>=metadata['work_deadline_monotonic']):
            self.stop('invalid-registered-managed-actor-binding')
            raise StudyStop(self.state['status'])
        if (not set(self.bound_fields) <= set(metadata) or provider not in self.models or model != self.models[provider] or metadata.get("provider") != provider
                or metadata.get("model_requested") != model or not isinstance(actor, str) or not actor
                or not isinstance(identifier, str) or not identifier or len(identifier) > 128
                or type(inputs) is not int or not 0 < inputs <= 131072
                or metadata.get("profile_id") != self.profile_id or metadata.get("profile_configuration_sha256") != self.configuration_sha256
                or metadata.get("execution_backend") != EXECUTION_BACKEND
                or metadata.get("tool_feedback_policy") != self.tool_feedback_policy
                or metadata.get("thinking") != ("disabled" if self.profile_id == DISABLED_PROFILE_ID else "enabled")
                or metadata.get("reasoning_effort_requested") is not None
                or type(metadata.get("output_cap")) is not int or metadata["output_cap"] != 8192
                or type(metadata.get("request_index")) is not int or metadata["request_index"] != len(requests) + 1
                or not valid_sha(metadata.get("request_payload_sha256")) or not valid_sha(metadata.get("input_task_sha256"))
                or metadata.get("adapter") != ADAPTER
                or metadata.get("broker_profile_id") != BROKER_PROFILE_ID
                or metadata.get("connect_retry_policy") != self.connect_retry_policy
                or self.state["pending"] or any(row["request_id"] == identifier for row in self.state["requests"])):
            self.stop("invalid-request-reservation")
            raise StudyStop(self.state["status"])
        if self.profile_id == DISABLED_PROFILE_ID:
            previous = requests[-1] if requests else None
            authorization = previous.get("connect_retry_authorization") if previous else None
            parent = metadata.get("retry_of_request_id")
            expected_authorization = ({"policy": CONNECT_RETRY_POLICY, "connect_retry_authorized": True,
                "prior_request_id": previous["request_id"], "prior_request_index": previous["request_index"],
                "request_payload_sha256": previous["request_payload_sha256"],
                "input_task_sha256": previous["input_task_sha256"],
                "prior_receipt_sha256": previous.get("receipt", {}).get("receipt_sha256")} if previous else None)
            if authorization is not None and (canonical(authorization) != canonical(expected_authorization)
                    or not connect_retry_eligible(previous.get("receipt", {}), actor_id=actor, actor_registry=self.actor_registry)
                    or not native_outcome_receipt_matches(self.path.parent, actor, previous.get("receipt", {}))):
                self.stop("invalid-connect-retry-original-proof")
                raise StudyStop(self.state["status"])
            if (metadata.get("connect_retry_policy") != self.connect_retry_policy
                    or (authorization is None and parent is not None)
                    or (authorization is not None and (parent != previous["request_id"]
                        or previous.get("retry_consumed_by") is not None
                        or metadata["request_payload_sha256"] != previous["request_payload_sha256"]
                        or metadata["input_task_sha256"] != previous["input_task_sha256"]))):
                self.stop("invalid-connect-retry-binding")
                raise StudyStop(self.state["status"])
        if len(requests) >= budget["max_requests"] or len({row["actor_id"] for row in self.state["requests"]} | {actor}) > self.caps["actors"]:
            self.stop("actor-request-cap-before-send")
            raise StudyStop(self.state["status"])
        amounts = self.estimate(provider, inputs, 8192)
        for currency, amount in amounts.items():
            account = self.state["accounts"][provider][currency]
            if Decimal(account["committed_estimate"]) + Decimal(account["reserved_estimate"]) + amount > Decimal(account["cap"]):
                self.stop("monetary-reservation-cap-before-send")
                raise StudyStop(self.state["status"])
        record = {"actor_id": actor, "request_id": identifier,
                  **{name: copy.deepcopy(metadata[name]) for name in self.bound_fields},
                  "reservation": {currency: str(value) for currency, value in amounts.items()}, "status": "reserved-before-send"}
        self.state["pending"][identifier] = copy.deepcopy(record)
        self.state["requests"].append(record)
        self.state["request_slots"] += 1
        if self.profile_id == DISABLED_PROFILE_ID and metadata.get("retry_of_request_id") is not None:
            previous["retry_consumed_by"] = identifier
        for currency, amount in amounts.items():
            account = self.state["accounts"][provider][currency]
            account["reserved_estimate"] = str(Decimal(account["reserved_estimate"]) + amount)
        self.publish()
        receipt = dict(copy.deepcopy(record), kind="immutable-pre-dispatch-reservation-v1",
                       ledger_pending_sha256=sha(self.path.read_bytes()), created_at_utc=datetime.now(timezone.utc).isoformat())
        path = self.path.parent / "reservations" / (sha(identifier.encode("utf-8")) + ".json")
        try:
            identity = immutable(path, receipt)
        except BaseException:
            self.stop("reservation-evidence-failed-before-send")
            raise
        record.update(reservation_receipt_sha256=identity, reservation_receipt_path=path.relative_to(self.path.parent).as_posix())
        self.state["pending"][identifier] = copy.deepcopy(record)
        self.publish()
        ledger_raw = self.path.read_bytes()
        durable = strict_json(ledger_raw)
        if canonical(durable) != canonical(self.state):
            self.stop('reservation-durable-readback-differs')
            raise StudyStop(self.state['status'])
        self._key_permit = {'actor_id': actor, 'provider': provider, 'request_id': identifier,
                            'reservation_receipt_sha256': identity}
        return dict(copy.deepcopy(record), ledger_sha256=sha(ledger_raw))

    def after(self, actor, provider, model, metadata):
        self._key_permit = None
        if self._persistence_fault is not None:
            raise StudyStop('accounting-persistence-unknown-global-stop')
        baseline = copy.deepcopy(self.state)
        self.state = copy.deepcopy(baseline)
        self._after_baseline = baseline
        try:
            return self._after_reconcile(actor, provider, model, metadata)
        except BaseException as error:
            if self._persistence_fault is None and (not isinstance(error, StudyStop) or self.state['status']=='running'):
                self._persistence_fault = {'exception_class':type(error).__name__, 'phase':'after-request-reconciliation-error',
                    'attempted_state_sha256':sha(canonical(self.state))}
            if self._persistence_fault is not None:
                working = self.state
                retained = copy.deepcopy(baseline)
                # Preserve every actually observed basic usage component once,
                # while restoring original conservative pending/reserved exposure.
                retained['known_reported_tokens'] = working['known_reported_tokens']
                retained['dispatched_requests'] = working['dispatched_requests']
                retained['elapsed_seconds'] = working.get('elapsed_seconds', baseline.get('elapsed_seconds'))
                for name,currencies in retained['accounts'].items():
                    for currency,account in currencies.items():
                        account['committed_estimate'] = working['accounts'][name][currency]['committed_estimate']
                identifier = metadata.get('request_id')
                original = next((row for row in retained['requests'] if row['request_id']==identifier), None)
                observed = next((row for row in working['requests'] if row['request_id']==identifier), None)
                if original is not None and observed is not None:
                    original.update(copy.deepcopy(observed))
                    original.pop('connect_retry_authorization',None)
                    original.update(status='unknown-reservation-retained',
                        exposure_limit='known reported estimate plus original reserved exposure; overlap is not an invoice')
                retained.update(status='accounting-persistence-unknown-global-stop', stop_reason='accounting-persistence-unknown-global-stop',
                    accounting_commit_failure=copy.deepcopy(self._persistence_fault))
                self.state = retained
                self._emit_failure_observation()
            raise  # First publication/validation exception is never replaced.
        finally:
            self._after_baseline = None

    def _after_reconcile(self, actor, provider, model, metadata):
        if self.state["status"] != "running":
            raise StudyStop(self.state["status"])
        identifier = metadata.get("request_id")
        record = self.state["pending"].get(identifier)
        if not record or record["actor_id"] != actor or provider != record["provider"] or model != record["model_requested"]:
            self.stop("unknown-request-reconciliation")
            raise StudyStop(self.state["status"])
        row = next(row for row in self.state["requests"] if row["request_id"] == identifier)
        row["receipt"] = copy.deepcopy(metadata)
        row["transport"] = copy.deepcopy(metadata.get("transport"))
        path = self.path.parent / record["reservation_receipt_path"]
        try:
            immutable_ok = path.is_file() and sha(path.read_bytes()) == record["reservation_receipt_sha256"]
        except OSError:
            immutable_ok = False  # Account observed usage before retaining exposure.
        binding_ok = (metadata.get("tool_feedback_policy") == self.tool_feedback_policy
                       and all(metadata.get(name) == record[name] for name in self.bound_fields)
                      and metadata.get("reservation_receipt_sha256") == record["reservation_receipt_sha256"] and immutable_ok)
        binding_ok = binding_ok and native_outcome_receipt_matches(self.path.parent, actor, metadata)
        transport = metadata.get("transport") or {}
        proven_not_sent = (binding_ok and metadata.get("not_invoked") is True and metadata.get("dispatched") is False
            and metadata.get("unknown") is False and transport.get("http_dispatch") == "not_started"
            and 'usage' in metadata and metadata['usage'] is None
            and all(metadata.get(name) is None for name in ('api_response_id', 'response_sha256', 'model_reported'))
            and type(transport.get("connection_attempted")) is bool
            and transport.get("phase") in {"preparation", "worker-before-request", "payload-serialize", "connection-create", "connect"})
        if proven_not_sent:
            self.release(provider, record)
            self.state["pending"].pop(identifier)
            row["status"] = "confirmed-not-invoked-before-send"
            actor_requests = [item for item in self.state["requests"] if item["actor_id"] == actor]
            if (self.connect_retry_policy == CONNECT_RETRY_POLICY and connect_retry_eligible(metadata, actor_id=actor, actor_registry=self.actor_registry)
                    and not any(item.get("connect_retry_authorization") for item in actor_requests)
                    and len(actor_requests) < self.actor_registry[actor]["max_requests"] and self.state["request_slots"] < self.caps["request_slots"]
                    and self.clock() - self.started < self.caps["round_seconds_soft"]
                    and self.state["known_reported_tokens"] < self.caps["known_reported_tokens_soft"]
                    and metadata["settlement"]["actor_elapsed_before_account_seconds"] < self.actor_registry[actor]["work_seconds"]):
                authorization = {"policy": CONNECT_RETRY_POLICY, "connect_retry_authorized": True,
                    "prior_request_id": identifier, "prior_request_index": record["request_index"],
                    "request_payload_sha256": record["request_payload_sha256"],
                    "input_task_sha256": record["input_task_sha256"], "prior_receipt_sha256": metadata["receipt_sha256"]}
                row["connect_retry_authorization"] = authorization
                self.publish()
                return copy.deepcopy(authorization)
            self.stop("preparation-failed-before-send")
            return
        if metadata.get("dispatched") is True:
            self.state["dispatched_requests"] += 1
        usage, response_id = metadata.get("usage"), metadata.get("api_response_id")
        known = (isinstance(usage, dict) and all(type(usage.get(name)) is int and usage[name] >= 0
                for name in ("input_tokens", "output_tokens", "total_tokens"))
                and usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"])
        optional_valid = known and all(usage.get(name) is None or type(usage[name]) is int and 0 <= usage[name] <= usage[maximum]
            for name, maximum in (('cached_tokens', 'input_tokens'), ('reasoning_tokens', 'output_tokens')))
        if not deadline_valid(metadata, actor_id=actor, actor_registry=self.actor_registry):
            row['unverified_deadline_telemetry'] = True
        overrun, amounts = False, None
        if known and not row.get("known_usage_accounted"):
            amounts = self.estimate(provider, usage["input_tokens"], usage["output_tokens"])
            for currency, amount in amounts.items():
                account = self.state["accounts"][provider][currency]
                account["committed_estimate"] = str(Decimal(account["committed_estimate"]) + amount)
                overrun = overrun or amount > Decimal(record["reservation"][currency]) or Decimal(account["committed_estimate"]) > Decimal(account["cap"])
            self.state["known_reported_tokens"] += usage["total_tokens"]
            overrun = overrun or usage["input_tokens"] > record["input_utf8_bytes"] or usage["output_tokens"] > 8192
            row.update(known_usage_accounted=True, reported_estimate={currency: str(value) for currency, value in amounts.items()}, reported_usage_over_reservation=overrun)
            if not optional_valid:
                row['unverified_optional_metrics'] = True
                row['usage_accounting_scope'] = 'valid reported basic components only; optional metrics are not normalized valid usage'
        if (not binding_ok or metadata.get("unknown") is not False or not known or not optional_valid or not deadline_valid(metadata, actor_id=actor, actor_registry=self.actor_registry) or metadata.get("dispatched") is not True
                or metadata.get("not_invoked") is not False or not valid_sha(metadata.get("receipt_sha256"))
                or not valid_sha(metadata.get("response_sha256")) or not isinstance(response_id, str)
                or not response_id or response_id in self.state["api_response_ids"]):
            row.update(status="unknown-reservation-retained", exposure_limit="known reported estimate plus original reserved exposure; overlap is not an invoice")
            self.stop("unknown-call-global-stop")
            raise StudyStop(self.state["status"])
        self.release(provider, record)
        self.state["pending"].pop(identifier)
        self.state["api_response_ids"].append(response_id)
        row["status"] = "reported-usage-estimate-committed"
        if overrun or self.state["known_reported_tokens"] > self.caps["known_reported_tokens_soft"] or self.clock() - self.started > self.caps["round_seconds_soft"]:
            self.stop("known-charge-overrun-global-stop")
            raise StudyStop(self.state["status"])
        self.publish()

    def release(self, provider, record):
        for currency, amount in record["reservation"].items():
            account = self.state["accounts"][provider][currency]
            account["reserved_estimate"] = str(Decimal(account["reserved_estimate"]) - Decimal(amount))


def _replace_checkpoint(temporary, path):
    """Retry only bounded Windows replacement denials over unchanged bytes."""
    delays = (0.02, 0.04, 0.08, 0.16, 0.24)
    for attempt in range(len(delays) + 1):
        try:
            temporary.replace(path)
        except PermissionError as error:
            if (sys.platform != "win32" or getattr(error, "winerror", None) not in {5, 32, 33}
                    or attempt == len(delays)):
                raise
            time.sleep(delays[attempt])
        else:
            return

def save_run(path, run):
    """Atomic same-volume checkpoints; a failed replace preserves last state."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(run, stream, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        import os
        os.fsync(stream.fileno())
    _replace_checkpoint(temporary, path)
