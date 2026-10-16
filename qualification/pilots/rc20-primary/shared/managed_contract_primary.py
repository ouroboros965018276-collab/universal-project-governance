"""Source-only finite-map contract shared by fixed primary and prospective calibration owners.

Registration and finalization values remain prospective until their external
protocol/order/fixture/analysis hashes are frozen. This module grants no launch.
"""
import copy
from decimal import Decimal
import hashlib
import json
import math
import re

POLICY = 'work-deadline-accounting-only-settlement-600s-v1'
ADAPTER = 'official-chat-api-registered-project-settlement-v1'
TIMING_SCHEMA = 'collector-first-setup-absolute-work-deadline-v1'
ROLE_FIELDS = frozenset(('provider', 'model', 'work_seconds', 'max_requests', 'max_tools',
    'minimum_dispatch_window_seconds', 'workflow_id', 'role', 'arm', 'case_id', 'block_id', 'cut_policy'))
MODELS = {'deepseek': 'deepseek-v4-pro', 'mimo': 'mimo-v2.6-flash'}
CUT_POLICIES = ('before-first-repository-tool-delivery-v1', 'first-confirmed-repo-patch-request-tail-v1')
FINALIZATION_POLICY = {'schema': 'primary-finalization-observation-v1',
    'workflow_publication_observation_seconds': 60, 'round_publication_observation_seconds': 120,
    'extends_actor_work_deadline': False, 'permits_new_dispatch': False}
REGISTRATION_FIELDS = frozenset(('protocol_sha256', 'order_sha256', 'fixture_binding_sha256', 'analysis_registration_sha256'))
SETTLEMENT_KEYS = set('policy max_seconds accounting_only work_closed attempt_dispatch_gate_closed dispatch_started worker_done worker_alive_at_return last_observed_phase body_complete body_bytes_observed body_sha256 work_deadline_monotonic settlement_deadline_monotonic headers_observed_monotonic body_last_observed_monotonic response_completed_monotonic capture_failure transport_failure settlement_limit_reached capture_receipts work_budget_seconds total_observation_budget_seconds actor_elapsed_before_transport_seconds actor_elapsed_after_transport_seconds actor_elapsed_before_account_seconds'.split())

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def number(value):
    return type(value) in (int, float) and math.isfinite(value)

def valid_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None

def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite JSON number')
    value = json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=pairs, parse_constant=nonfinite)
    if type(value) is not dict:
        raise ValueError('JSON object required')
    return value

def validate_registry(registry, *, registry_identity):
    """One complete finite map, bound to an external generator and exact count.

    Primary owner must separately rebuild the fixed 66-role topology from its
    frozen order. A separate four-role owner binds its own entire fixed map.
    Neither caller can append roles or mutate the registered budgets in place.
    """
    if (type(registry_identity) is not dict
            or set(registry_identity) != {'source_sha256', 'actor_registry_sha256', 'expected_actor_count'}
            or not valid_sha(registry_identity['source_sha256'])
            or not valid_sha(registry_identity['actor_registry_sha256'])
            or type(registry_identity['expected_actor_count']) is not int
            or not 1 <= registry_identity['expected_actor_count'] <= 66
            or type(registry) is not dict or len(registry) != registry_identity['expected_actor_count']
            or sha(canonical(registry)) != registry_identity['actor_registry_sha256']):
        raise ValueError('fixed finite actor registry identity/count differs or UNBOUND')
    roles = set()
    for actor_id, row in registry.items():
        if (type(actor_id) is not str or re.fullmatch('w[0-9]{3}-(source|receiver)', actor_id) is None
                or type(row) is not dict or set(row) != ROLE_FIELDS
                or row['provider'] not in MODELS or row['model'] != MODELS[row['provider']]
                or any(type(row[name]) is not int or row[name] != value for name, value in
                       (('work_seconds', 180), ('max_requests', 12), ('max_tools', 32), ('minimum_dispatch_window_seconds', 15)))
                or type(row['workflow_id']) is not str or re.fullmatch('w[0-9]{3}', row['workflow_id']) is None
                or row['role'] not in ('source', 'receiver') or actor_id != row['workflow_id'] + '-' + row['role']
                or row['arm'] not in ('rc19', 'attention', 'full')
                or type(row['case_id']) is not str or re.fullmatch('[A-Za-z0-9_-]{1,64}', row['case_id']) is None
                or type(row['block_id']) is not str or re.fullmatch('b[0-9]{2}', row['block_id']) is None
                or row['cut_policy'] not in (None,) + CUT_POLICIES
                or row['role'] == 'receiver' and row['cut_policy'] is not None
                or (row['workflow_id'], row['role']) in roles):
            raise ValueError('fixed actor registration schema/budget differs')
        roles.add((row['workflow_id'], row['role']))
    return copy.deepcopy(registry)

def derive_caps(actor_registry, configuration, *, registry_identity, finalization_policy):
    """Conservative prospective envelopes; no usage, refund or invoice claim."""
    registry = validate_registry(actor_registry, registry_identity=registry_identity)
    if canonical(finalization_policy) != canonical(FINALIZATION_POLICY):
        raise ValueError('explicit proposed finalization observation policy required')
    workflows = {}
    slots = {provider: 0 for provider in MODELS}
    for row in registry.values():
        workflows[row['workflow_id']] = workflows.get(row['workflow_id'], 0) + row['work_seconds'] + 600
        slots[row['provider']] += row['max_requests']
    workflow_caps = {key: value + finalization_policy['workflow_publication_observation_seconds']
                     for key, value in sorted(workflows.items())}
    caps = {'actors': len(registry), 'workflows': len(workflows), 'blocks': len({row['block_id'] for row in registry.values()}),
        'request_slots': sum(slots.values()), 'known_reported_tokens_soft': sum(slots.values()) * (131072 + 8192),
        'round_seconds_soft': sum(workflow_caps.values()) + finalization_policy['round_publication_observation_seconds'],
        'workflow_seconds_soft': workflow_caps, 'provider_request_slots': slots,
        'finalization_policy': copy.deepcopy(finalization_policy), 'ordinary_failure_stop_limit': None,
        'actor_registry_sha256': sha(canonical(registry)), 'registry_identity': copy.deepcopy(registry_identity), 'configuration_sha256': sha(canonical(configuration)),
        'kind': 'prospective-reservation-envelope-not-actual-usage-or-invoice'}
    for provider, count in slots.items():
        for currency, prices in configuration['prices'][provider].items():
            amount = count * (Decimal(131072) * Decimal(prices['input_miss']) + Decimal(8192) * Decimal(prices['output'])) / 1_000_000
            caps[provider + '_' + currency] = str(amount)
    return caps

def managed_deadline_valid(metadata, *, actor_id, actor_registry):
    """Typed deadline arithmetic by actor identity; not an independent clock."""
    budget = actor_registry.get(actor_id)
    s = metadata.get('settlement')
    if (budget is None or budget['provider'] != metadata.get('provider') or budget['work_seconds'] != 180
            or type(s) is not dict or set(s) != SETTLEMENT_KEYS
            or metadata.get('adapter') != ADAPTER or metadata.get('settlement_policy') != POLICY
            or type(metadata.get('settlement_max_seconds')) is not int or metadata['settlement_max_seconds'] != 600
            or s['policy'] != POLICY or type(s['max_seconds']) is not int or s['max_seconds'] != 600
            or not all(type(s[k]) is bool for k in ('accounting_only', 'work_closed', 'attempt_dispatch_gate_closed', 'dispatch_started', 'worker_done', 'worker_alive_at_return', 'body_complete', 'settlement_limit_reached'))
            or s['accounting_only'] is not s['work_closed']
            or type(s['body_bytes_observed']) is not int or not 0 <= s['body_bytes_observed'] <= 2097153
            or not number(s['work_budget_seconds']) or s['work_budget_seconds'] != 180
            or not number(s['total_observation_budget_seconds']) or s['total_observation_budget_seconds'] != 780):
        return False
    w, t = s['work_deadline_monotonic'], s['settlement_deadline_monotonic']
    if (not all(number(x) for x in (w, t)) or t - w != 600
            or metadata.get('work_deadline_monotonic') != w or metadata.get('settlement_deadline_monotonic') != t):
        return False
    elapsed = [s[k] for k in ('actor_elapsed_before_transport_seconds', 'actor_elapsed_after_transport_seconds', 'actor_elapsed_before_account_seconds')]
    if not all(number(x) and x >= 0 for x in elapsed) or elapsed != sorted(elapsed):
        return False
    if s['work_closed'] and elapsed[-1] < 180 or not s['work_closed'] and elapsed[1] >= 180:
        return False
    for key in ('headers_observed_monotonic', 'body_last_observed_monotonic', 'response_completed_monotonic'):
        if s[key] is not None and (not number(s[key]) or s[key] > t):
            return False
    refs = s['capture_receipts']
    if type(refs) is not list or len(refs) > 2:
        return False
    kinds = []
    for ref in refs:
        if (type(ref) is not dict or set(ref) != {'kind', 'receipt_ref', 'receipt_sha256'} or not valid_sha(ref['receipt_sha256'])
                or type(metadata.get('request_index')) is not int
                or ref['receipt_ref'] != 'requests/%02d.transport-%s.json' % (metadata['request_index'], ref['kind'])):
            return False
        kinds.append(ref['kind'])
    return kinds in ([], ['headers'], ['body'], ['headers', 'body'])
