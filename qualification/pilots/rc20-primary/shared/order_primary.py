"""Pure fixed-size workflow ordering; no fixture generation, IO or launch."""
import copy
import random
import re

ARMS = ('rc19', 'attention', 'full')
PROVIDERS = ('deepseek', 'mimo')
MODELS = {'deepseek': 'deepseek-v4-pro', 'mimo': 'mimo-v2.6-flash'}
REVERSE = {'deepseek': 'mimo', 'mimo': 'deepseek'}
CUT_POLICIES = ('before-first-repository-tool-delivery-v1', 'first-confirmed-repo-patch-request-tail-v1')
COUNTS = {'blocks': 18, 'workflows': 54, 'actors': 66, 'families': 9, 'single_families': 7, 'controlled_families': 2}
ROLE_FIELDS = frozenset(('provider', 'model', 'work_seconds', 'max_requests', 'max_tools',
    'minimum_dispatch_window_seconds', 'workflow_id', 'role', 'arm', 'case_id', 'block_id', 'cut_policy'))


def make_order(case_headers, seed):
    """Preserve C11's provider/arm insertion order and Random(seed).shuffle."""
    if (type(seed) is not int or type(case_headers) is not list or len(case_headers) != 9
            or any(type(row) is not dict or set(row) != {'case_id', 'cut_policy'}
                   or type(row['case_id']) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', row['case_id']) is None
                   or row['cut_policy'] not in (None,) + CUT_POLICIES for row in case_headers)
            or len({row['case_id'] for row in case_headers}) != 9
            or [sum(row['cut_policy'] == policy for row in case_headers) for policy in (None,) + CUT_POLICIES] != [7, 1, 1]):
        raise ValueError('exact nine-family/seven-single/two-controlled registration required')
    rows = []
    block_index = 0
    for case in case_headers:
        for provider in PROVIDERS:
            block_index += 1
            for arm in ARMS:
                rows.append(dict(copy.deepcopy(case), arm=arm, block_id='b%02d' % block_index,
                    source_provider=provider, receiver_provider=REVERSE[provider] if case['cut_policy'] else None))
    random.Random(seed).shuffle(rows)
    for index, row in enumerate(rows, 1):
        identifier = 'w%03d' % index
        row.update(workflow_id=identifier, source_actor_id=identifier + '-source',
                   receiver_actor_id=identifier + '-receiver' if row['receiver_provider'] else None)
    if len(rows) != 54 or sum(1 + bool(row['receiver_actor_id']) for row in rows) != 66:
        raise AssertionError('fixed primary denominator changed')
    return {'schema_version': 'primary-managed-workflow-order-v1', 'seed': seed, 'workflows': rows}


def actor_registry(order):
    """Immutable actor identities/budgets derive only from the frozen order."""
    if type(order) is not dict or set(order) != {'schema_version', 'seed', 'workflows'}:
        raise ValueError('order schema')
    if order['schema_version'] != 'primary-managed-workflow-order-v1' or type(order['workflows']) is not list or len(order['workflows']) != 54:
        raise ValueError('order identity/count')
    actors = {}
    for row in order['workflows']:
        for role in ('source', 'receiver'):
            actor_id, provider = row[role + '_actor_id'], row[role + '_provider']
            if role == 'receiver' and actor_id is None:
                if provider is not None:
                    raise ValueError('unregistered receiver provider')
                continue
            if actor_id in actors or provider not in PROVIDERS:
                raise ValueError('actor identity/provider')
            actors[actor_id] = {'provider': provider, 'model': MODELS[provider], 'work_seconds': 180,
                'max_requests': 12, 'max_tools': 32, 'minimum_dispatch_window_seconds': 15,
                'workflow_id': row['workflow_id'], 'role': role, 'arm': row['arm'], 'case_id': row['case_id'],
                'block_id': row['block_id'], 'cut_policy': row['cut_policy'] if role == 'source' else None}
            if set(actors[actor_id]) != ROLE_FIELDS:
                raise AssertionError('actor registry fields differ')
    if len(actors) != 66:
        raise ValueError('registered actor count')
    return actors
