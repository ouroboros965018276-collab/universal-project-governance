"""Pure prospective engineering-study topology, not a collector or admission grant.

Callers authenticate the supplied model/configuration buffers and source map
with their existing pinned-source loader. No tasks, results, files, processes,
providers, planners or execution backends are opened by this module.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re

from .context_campaign import ABLATIONS, ATTENTION_INSTRUCTION, trusted_arm_models

SCHEMA = 'real-engineering-six-condition-preregistration-v1'
MODULE = 'evolution/engineering_study.py'
ARMS = ('rc19', 'attention', 'full', *ABLATIONS)
PROFILE_ID = 'thinking-enabled-engineering-ultraspeed-strict-dslow32768-mimo65536-checkpoint-once-sse-v1'
CONFIGURATION_SHA256 = '0d204c60bf968839d183954286e871aba0b168ed1b144a6cf1dae219e082af56'
DUAL_API_ROUTE_PROFILE = 'dual-api-natural-cross-provider-v1'
DUAL_API_PROFILE_ID = 'thinking-enabled-engineering-ultraspeed-strict-dslow32768-mimo65536-checkpoint-working-set-once-sse-v1'
DUAL_API_CONFIGURATION_SHA256 = 'ecb06a3c5f8ecb5c8799b586e548f252dda71f699b6f07a83c7e44eb213c5ca1'
DUAL_API_GLOBAL_REQUEST_SLOTS = 720
DUAL_API_GLOBAL_ROUND_SECONDS = 41250
MODEL_DELTA_ID = 'rc19-bd4-to-rc20-reviewed-evidence-closure-compact-expression-v1'
BASELINE_MODEL_SHA256 = '44e7d9fdf648e35d834e3835ea8e06a734a5aed50eb3e701c2f86c2717e17a7d'
BASELINE_EVIDENCE_CLOSURE_SHA256 = '4d97faefd8df3aa5c9ab13d6efef346afa6c9ffa5e1208f0319eb97da5b279f1'
FULL_EVIDENCE_CLOSURE_SHA256 = '2d4847a72a0565a5b4607fec745e617ec199bba7451d8274da1eecb3f9823512'
OPERATIONAL_GUIDANCE_SHA256 = 'b3cf14c5cc71af7a35ecfb771de7fbb404eaaa9e117da90056d155193c86e835'
MODELS = {'deepseek': 'deepseek-v4-pro', 'mimo': 'mimo-v2.6-pro-ultraspeed',
          'openai-native-cli': 'gpt-6-luna'}
ROUTES = (('single', 'deepseek', None), ('single', 'mimo', None),
          ('natural-handoff', 'deepseek', 'mimo'),
          ('natural-handoff', 'mimo', 'openai-native-cli'))
DUAL_API_ROUTES = (('single', 'deepseek', None), ('single', 'mimo', None),
                   ('natural-handoff', 'deepseek', 'mimo'),
                   ('natural-handoff', 'mimo', 'deepseek'))
ENVELOPE = {'work_seconds': 600, 'max_api_requests': 24, 'max_api_input_bytes': 524288,
            'max_tools': 32, 'minimum_dispatch_window_seconds': 15,
            'max_native_executions': 1, 'api_settlement_seconds': 600,
            'native_cleanup_seconds': 15}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _require(value, message):
    if not value:
        raise ValueError(message)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _path(value):
    _require(type(value) is str and value and not any(c in value for c in ('\\', ':', '\x00', '\r', '\n'))
             and all(part not in ('', '.', '..') for part in value.split('/'))
             and value.split('/')[0].casefold() != '.git',
             'exact relative source path required')
    return value


class EngineeringStudy:
    """One fixed preregistration supplies every topology-dependent projection.

    Source pins are compared as complete maps, not trusted as evidence that a
    caller actually read those bytes. Existing source admission remains required.
    Model/Skill/runtime rendering and independent execution/quality proofs also
    remain outside this topology validator.
    """

    def __init__(self, preregistration, *, baseline_model, full_model, configuration,
                 consumed_source_pins):
        p = copy.deepcopy(preregistration)
        dual_api = type(p) is dict and 'route_profile' in p
        fields = {'schema', 'study_id', 'baseline_model_sha256',
                 'full_model_sha256', 'profile_configuration_sha256', 'condition_bindings',
                 'families', 'source_pins', 'reviewed_model_delta_id'}
        _require(type(p) is dict and set(p) == fields | ({'route_profile'} if dual_api else set()) and p['schema'] == SCHEMA
                 and p['reviewed_model_delta_id'] == MODEL_DELTA_ID,
                 'exact prospective study preregistration required')
        _require(not dual_api or p['route_profile'] == DUAL_API_ROUTE_PROFILE,
                 'unknown explicit engineering route profile')
        routes = DUAL_API_ROUTES if dual_api else ROUTES
        profile_id = DUAL_API_PROFILE_ID if dual_api else PROFILE_ID
        configuration_sha256 = DUAL_API_CONFIGURATION_SHA256 if dual_api else CONFIGURATION_SHA256
        _require(type(p['study_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}', p['study_id']),
                 'explicit study identity required')
        pins = p['source_pins']
        _require(type(pins) is dict and {MODULE, 'evolution/context_campaign.py'} <= set(pins)
                 and all(_path(name) and _sha(value) for name, value in pins.items())
                 and canonical(pins) == canonical(consumed_source_pins),
                 'complete consumed source pins differ')
        _require(type(configuration) is dict and configuration.get('profile_id') == profile_id
                 and digest(configuration) == p['profile_configuration_sha256'] == configuration_sha256,
                 'fixed reviewed engineering configuration differs')
        _require(type(baseline_model) is dict and type(full_model) is dict
                 and digest(baseline_model) == p['baseline_model_sha256'] == BASELINE_MODEL_SHA256
                 and digest(full_model) == p['full_model_sha256']
                 and baseline_model.get('version') == '3.0.0-rc.19'
                 and full_model.get('version') == '3.0.0-rc.20'
                 and not baseline_model.get('execution_guidance'), 'fixed RC19/full model identities differ')
        baseline_core, full_core = copy.deepcopy(baseline_model), copy.deepcopy(full_model)
        for model in (baseline_core, full_core):
            model.pop('version', None)
            model.pop('execution_guidance', None)
        # Only the independently reviewed, fixed RC19 -> current RC20 delta is
        # normalized. All other top-level and policy fields remain exact.
        _require('operational_guidance' not in baseline_core
                 and digest(full_core.get('operational_guidance')) == OPERATIONAL_GUIDANCE_SHA256,
                 'reviewed operational-guidance addition differs')
        full_core.pop('operational_guidance')
        old_policy = [p for p in baseline_core.get('policies', []) if p.get('id') == 'EVIDENCE_AFFECTED']
        new_policy = [p for p in full_core.get('policies', []) if p.get('id') == 'EVIDENCE_AFFECTED']
        _require(len(old_policy) == len(new_policy) == 1
                 and digest(old_policy[0].get('closure')) == BASELINE_EVIDENCE_CLOSURE_SHA256
                 and digest(new_policy[0].get('closure')) == FULL_EVIDENCE_CLOSURE_SHA256,
                 'reviewed EVIDENCE_AFFECTED closure upgrade differs')
        old_policy[0]['closure'] = new_policy[0]['closure']
        _require(canonical(baseline_core) == canonical(full_core)
                 and len(baseline_core.get('policies', [])) == 16
                 and len(baseline_core.get('hot_path', [])) == 8,
                 'unreviewed RC19 core policy, safety or other model change')
        expected = trusted_arm_models(full_model)
        models = {'rc19': copy.deepcopy(baseline_model), 'attention': copy.deepcopy(baseline_model),
                  'full': expected.pop('full_rc20'), **expected}
        bindings = p['condition_bindings']
        _require(type(bindings) is dict and set(bindings) == set(ARMS), 'all six conditions required')
        for arm, binding in bindings.items():
            _require(type(binding) is dict and set(binding) == {'model_sha256', 'source_sha256',
                     'runtime_sha256', 'skill_sha256'} and all(_sha(v) for v in binding.values())
                     and binding['model_sha256'] == digest(models[arm]),
                     'condition model/source/runtime/Skill identity differs: ' + arm)
        _require(bindings['attention'] == bindings['rc19'],
                 'attention may only append the canonical attention instruction to the RC19 entry')
        families = p['families']
        _require(type(families) is list and len(families) == len(routes), 'four independent families required')
        names = set()
        for family, route in zip(families, routes):
            _require(type(family) is dict and set(family) == {'family', 'kind', 'source_provider',
                     'receiver_provider', 'arm_order'}, 'exact family route/order fields required')
            name = family['family']
            _require(type(name) is str and re.fullmatch('f_[a-z0-9]{6,24}', name) and name not in names,
                     'distinct opaque family identities required')
            names.add(name)
            _require(tuple(family[k] for k in ('kind', 'source_provider', 'receiver_provider')) == route,
                     'fixed registered DS/MiMo single and bidirectional API handoff routes required' if dual_api else
                     'fixed DS/MiMo single and DS-to-MiMo/MiMo-to-native routes required')
            arms = family['arm_order']
            _require(type(arms) is list and len(arms) == len(ARMS)
                     and all(type(arm) is str for arm in arms) and set(arms) == set(ARMS),
                     'each family needs one preregistered permutation of all six conditions')
        self._preregistration, self._models = p, models
        self._routes, self._configuration_sha256 = routes, configuration_sha256

    @property
    def preregistration_sha256(self):
        return digest(self._preregistration)

    def condition_models(self):
        return copy.deepcopy(self._models)

    def family_stages(self):
        return {f['family']: ('single',) if f['kind'] == 'single' else ('source', 'receiver')
                for f in self._preregistration['families']}

    def validate_family_stage(self, family, stage):
        _require(family in self.family_stages() and stage in self.family_stages()[family],
                 'preregistered family/stage identity required')

    def fixed_order(self):
        rows = []
        for wave in range(len(ARMS)):
            for index, family in enumerate(self._preregistration['families'], 1):
                workflow = 'w%03d' % (len(rows) + 1)
                receiver = family['receiver_provider']
                rows.append({'workflow_id': workflow, 'block_id': 'b%02d' % index,
                    'case_id': family['family'], 'kind': family['kind'], 'arm': family['arm_order'][wave],
                    'source_actor_id': workflow + '-source',
                    'receiver_actor_id': workflow + '-receiver' if receiver else None,
                    'source_provider': family['source_provider'], 'receiver_provider': receiver,
                    'source_fixture_stage': 'source' if receiver else 'single',
                    'receiver_fixture_stage': 'receiver' if receiver else None, 'cut_policy': None})
        return {'schema': 'real-engineering-six-condition-order-v1', 'workflows': rows,
                'uses_observed_results': False, 'natural_completion_only': True}

    def fixed_registry(self):
        result = {}
        for row in self.fixed_order()['workflows']:
            for role in ('source', 'receiver'):
                provider = row[role + '_provider']
                if provider is None:
                    continue
                native = provider == 'openai-native-cli'
                result[row[role + '_actor_id']] = {'provider': provider, 'model': MODELS[provider],
                    'work_seconds': ENVELOPE['work_seconds'], 'max_requests': None if native else ENVELOPE['max_api_requests'],
                    'max_tools': ENVELOPE['max_tools'], 'minimum_dispatch_window_seconds': ENVELOPE['minimum_dispatch_window_seconds'],
                    **{key: row[key] for key in ('workflow_id', 'arm', 'case_id', 'block_id', 'cut_policy')},
                    'role': role, 'surface': 'nativeCLI' if native else 'API', 'max_native_executions': 1 if native else 0}
        return result

    def counts(self):
        registry = self.fixed_registry()
        return {'families': len(self._routes), 'single_families': sum(r[0] == 'single' for r in self._routes),
                'natural_handoff_families': sum(r[0] == 'natural-handoff' for r in self._routes),
                'paired_blocks': len(self._routes), 'workflows': len(self.fixed_order()['workflows']),
                'actors': len(registry), 'API': sum(r['surface'] == 'API' for r in registry.values()),
                'nativeCLI': sum(r['surface'] == 'nativeCLI' for r in registry.values()),
                'panels': len(ARMS), 'roles_per_panel': len(registry) // len(ARMS)}

    def registry_identity(self):
        return {'source_sha256': self._preregistration['source_pins'][MODULE],
                'actor_registry_sha256': digest(self.fixed_registry()), 'expected_actor_count': self.counts()['actors']}

    def validate_registry(self, registry, *, registry_identity):
        _require(canonical(registry) == canonical(self.fixed_registry())
                 and canonical(registry_identity) == canonical(self.registry_identity()),
                 'complete registered actor identities/routes/budgets differ')
        return copy.deepcopy(registry)

    def caps(self):
        registry = self.fixed_registry()
        workflow_caps, slots = {}, {'deepseek': 0, 'mimo': 0}
        for row in registry.values():
            native = row['surface'] == 'nativeCLI'
            seconds = row['work_seconds'] + (ENVELOPE['native_cleanup_seconds'] if native else ENVELOPE['api_settlement_seconds'])
            workflow_caps[row['workflow_id']] = workflow_caps.get(row['workflow_id'], 60) + seconds
            if not native:
                slots[row['provider']] += row['max_requests']
        caps = {'actors': len(registry), 'workflows': len(workflow_caps), 'blocks': len(self._routes),
                'request_slots': sum(slots.values()), 'provider_request_slots': slots,
                'cli_execution_slots': sum(r['max_native_executions'] for r in registry.values()),
                'tool_slots': sum(r['max_tools'] for r in registry.values()),
                'max_input_bytes': ENVELOPE['max_api_input_bytes'], 'workflow_seconds_soft': workflow_caps,
                'round_seconds_soft': sum(workflow_caps.values()) + 120,
                'kind': 'prospective-reservation-envelope-not-actual-usage-or-invoice'}
        if 'route_profile' in self._preregistration:
            # Individual/provider ceilings remain unchanged; the shared study
            # budget does not promise that all actor maxima can be consumed.
            caps.update(request_slots=DUAL_API_GLOBAL_REQUEST_SLOTS,
                        round_seconds_soft=DUAL_API_GLOBAL_ROUND_SECONDS,
                        kind='shared-global-hard-ceilings-not-simultaneous-per-actor-budget-grants')
        return caps

    def private_panel_assignment(self):
        rows, panels = self.fixed_order()['workflows'], {}
        for wave in range(len(ARMS)):
            selection = []
            for row in rows[wave * len(self._routes):(wave + 1) * len(self._routes)]:
                actors = [row['source_actor_id']]
                if row['receiver_actor_id']:
                    actors.append(row['receiver_actor_id'])
                selection.append({'family': row['case_id'], 'workflow_id': row['workflow_id'], 'actor_ids': actors})
            panels['panel-%d' % (wave + 1)] = selection
        return {'schema': 'real-engineering-six-panel-owner-assignment-v1', 'panels': panels,
                'assignment_uses_results': False, 'lock_all_initials_before_unblind': True,
                'planned_role_denominator': len(self.fixed_registry())}

    def fixture_bindings(self, registry):
        """Metadata seam for the existing field adapter; never reads a fixture."""
        _require(type(registry) is dict and type(registry.get('families')) is list,
                 'private registry metadata required')
        result = {}
        for family in registry['families']:
            name = family['family']
            _require(name in self.family_stages() and name not in result, 'exact unique family identity required')
            stages = {}
            for row in family['stages']:
                stage = row['stage']
                self.validate_family_stage(name, stage)
                _require(stage not in stages, 'duplicate fixture stage')
                for key in ('public_task', 'private_contract', 'reference'):
                    _path(row[key])
                stages[stage] = {'public_task_path': row['public_task'], 'private_contract_path': row['private_contract']}
            _require(set(stages) == set(self.family_stages()[name]), 'complete family stages required')
            result[name] = stages
        _require(set(result) == set(self.family_stages()), 'complete preregistered family identities required')
        return result

    def validate_protocol(self, protocol):
        """Topology seam only; existing source, grant, ledger and RAW gates remain."""
        expected = {'identity': self._preregistration['study_id'], 'counts': self.counts(),
                    'order': self.fixed_order(), 'actor_registry': self.fixed_registry(),
                    'ledger_registry_identity': self.registry_identity(),
                    'profile_configuration_sha256': self._configuration_sha256,
                    'study_topology_sha256': self.preregistration_sha256}
        if 'route_profile' in self._preregistration:
            expected.update(route_profile=DUAL_API_ROUTE_PROFILE, profile_id=DUAL_API_PROFILE_ID,
                            configuration_sha256=self._configuration_sha256)
        else:
            _require(type(protocol) is dict and 'route_profile' not in protocol,
                     'explicit route profile requires its own preregistration')
        _require(type(protocol) is dict and all(canonical(protocol.get(k)) == canonical(v) for k, v in expected.items()),
                 'protocol topology/identity differs from preregistration')
        caps = protocol.get('round_caps')
        _require(type(caps) is dict and all(canonical(caps.get(k)) == canonical(v) for k, v in self.caps().items()),
                 'protocol finite reservation caps differ')
        return copy.deepcopy(protocol)
