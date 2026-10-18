"""Pure metadata contracts: no task, result, planner, provider or backend calls."""
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
if sys.version_info >= (3, 10):
    from evolution import engineering_study as study, provider_tools


@unittest.skipIf(sys.version_info < (3, 10), 'optional engineering study requires Python 3.10+')
class EngineeringStudyTests(unittest.TestCase):
    def setUp(self):
        self.full = json.loads((ROOT / 'governance-src/model/governance-model.json').read_bytes())
        self.baseline_delta = json.loads((ROOT / 'tests/fixtures/engineering-study-rc19-model-delta.json').read_bytes())
        self.baseline = copy.deepcopy(self.full)
        for field in self.baseline_delta['full_only_fields']:
            self.baseline.pop(field)
        self.baseline['version'] = self.baseline_delta['baseline_version']
        next(p for p in self.baseline['policies'] if p['id'] == 'EVIDENCE_AFFECTED')['closure'] = (
            self.baseline_delta['baseline_evidence_affected_closure'])
        self.assertEqual(study.digest(self.baseline), self.baseline_delta['baseline_model_sha256'])
        self.configuration = provider_tools.profile_configuration(study.PROFILE_ID)
        self.pins = {name: __import__('hashlib').sha256((ROOT / name).read_bytes()).hexdigest()
                     for name in (study.MODULE, 'evolution/context_campaign.py')}
        models = study.trusted_arm_models(self.full)
        models['full'] = models.pop('full_rc20')
        models.update(rc19=self.baseline, attention=self.baseline)
        bindings = {arm: {'model_sha256': study.digest(model), 'source_sha256': '1' * 64,
                         'runtime_sha256': '2' * 64, 'skill_sha256': '3' * 64}
                    for arm, model in models.items()}
        self.prereg = {'schema': study.SCHEMA, 'study_id': 'synthetic-six-condition-topology',
            'reviewed_model_delta_id': study.MODEL_DELTA_ID,
            'baseline_model_sha256': study.digest(self.baseline), 'full_model_sha256': study.digest(self.full),
            'profile_configuration_sha256': study.CONFIGURATION_SHA256, 'condition_bindings': bindings,
            'source_pins': self.pins, 'families': [
                {'family': 'f_%06d' % (i + 1), 'kind': route[0], 'source_provider': route[1],
                 'receiver_provider': route[2], 'arm_order': list(study.ARMS[i:] + study.ARMS[:i])}
                for i, route in enumerate(study.ROUTES)]}

    def build(self, prereg=None):
        return study.EngineeringStudy(self.prereg if prereg is None else prereg,
            baseline_model=self.baseline, full_model=self.full, configuration=self.configuration,
            consumed_source_pins=self.pins)

    def test_all_six_conditions_derive_exact_routes_counts_caps_and_blind_panels(self):
        topology = self.build()
        self.assertEqual(topology.counts(), {'families': 4, 'single_families': 2,
            'natural_handoff_families': 2, 'paired_blocks': 4, 'workflows': 24,
            'actors': 36, 'API': 30, 'nativeCLI': 6, 'panels': 6, 'roles_per_panel': 6})
        rows, registry = topology.fixed_order()['workflows'], topology.fixed_registry()
        for arm in study.ARMS:
            selected = sorted((r for r in rows if r['arm'] == arm), key=lambda r: r['block_id'])
            self.assertEqual(len(selected), 4)
            self.assertEqual([(r['kind'], r['source_provider'], r['receiver_provider']) for r in selected], list(study.ROUTES))
            self.assertEqual(sum(r['arm'] == arm for r in registry.values()), 6)
        caps = topology.caps()
        self.assertEqual((caps['request_slots'], caps['cli_execution_slots'], caps['tool_slots'], caps['round_seconds_soft']),
                         (720, 6, 1152, 41250))
        self.assertEqual(caps['provider_request_slots'], {'deepseek': 288, 'mimo': 432})
        for row in registry.values():
            self.assertEqual((row['work_seconds'], row['max_tools'], row['cut_policy']), (600, 32, None))
            self.assertEqual(row['max_requests'], 24 if row['surface'] == 'API' else None)
        panels = topology.private_panel_assignment()
        actors = [a for rows in panels['panels'].values() for row in rows for a in row['actor_ids']]
        self.assertEqual(len(actors), 36)
        self.assertEqual(set(actors), set(registry))
        self.assertTrue(panels['lock_all_initials_before_unblind'])
        self.assertTrue(all(sum(len(r['actor_ids']) for r in rows) == 6 for rows in panels['panels'].values()))

    def test_missing_duplicate_unknown_or_observation_dependent_registration_is_rejected(self):
        for kind in ('condition', 'family', 'duplicate-family', 'duplicate-arm', 'route', 'results'):
            with self.subTest(kind=kind):
                p = copy.deepcopy(self.prereg)
                if kind == 'condition': p['condition_bindings'].pop('full')
                elif kind == 'family': p['families'].pop()
                elif kind == 'duplicate-family': p['families'][1]['family'] = p['families'][0]['family']
                elif kind == 'duplicate-arm': p['families'][0]['arm_order'][1] = p['families'][0]['arm_order'][0]
                elif kind == 'route': p['families'][2]['receiver_provider'] = 'openai-native-cli'
                else: p['observed_results'] = {'select_cheapest_arm': True}
                with self.assertRaises(ValueError): self.build(p)

    def test_ablations_only_remove_their_canonical_guidance_and_preserve_all_core(self):
        models = self.build().condition_models()
        for arm, removed in study.ABLATIONS.items():
            expected = copy.deepcopy(self.full)
            expected['execution_guidance'] = [g for g in expected['execution_guidance'] if g['id'] != removed]
            self.assertEqual(models[arm], expected)
            self.assertIn('task_scoped_reading', {g['id'] for g in models[arm]['execution_guidance']})
            self.assertEqual(models[arm]['policies'], self.full['policies'])
        p = copy.deepcopy(self.prereg)
        p['condition_bindings']['minus_complete_change']['model_sha256'] = study.digest(self.baseline)
        with self.assertRaises(ValueError): self.build(p)
        self.full['policies'].pop()
        self.prereg['full_model_sha256'] = study.digest(self.full)
        with self.assertRaises(ValueError): self.build()

    def test_registry_is_exact_by_identity_not_dictionary_insertion_order(self):
        topology = self.build()
        registry, identity = topology.fixed_registry(), topology.registry_identity()
        reordered = dict(reversed(list(registry.items())))
        self.assertEqual(topology.validate_registry(reordered, registry_identity=identity), registry)
        for kind in ('missing', 'provider', 'budget-float', 'identity', 'count-float'):
            with self.subTest(kind=kind):
                changed, bound = copy.deepcopy(registry), copy.deepcopy(identity)
                if kind == 'missing': changed.pop(next(iter(changed)))
                elif kind == 'provider': changed['w001-source']['provider'] = 'mimo'
                elif kind == 'budget-float': changed['w001-source']['work_seconds'] = 600.0
                elif kind == 'identity': bound['source_sha256'] = '9' * 64
                else: bound['expected_actor_count'] = 36.0
                with self.assertRaises(ValueError): topology.validate_registry(changed, registry_identity=bound)
        registry['w001-source']['work_seconds'] = 1
        self.assertEqual(topology.fixed_registry()['w001-source']['work_seconds'], 600)

    def test_real_fixed_rc19_git_model_and_actual_current_full_are_admitted(self):
        # The compact fixture was observed from the exact Git blob. Rebuilding
        # and matching its complete canonical digest checks the real old model,
        # without requiring historical Git objects in a shallow CI checkout.
        self.assertEqual(study.digest(self.baseline), study.BASELINE_MODEL_SHA256)
        self.assertEqual(study.digest(self.full), self.baseline_delta['full_model_sha256'])
        self.assertNotEqual(self.baseline['policies'], self.full['policies'])
        topology = self.build()
        self.assertEqual(topology.condition_models()['rc19'], self.baseline)
        self.assertEqual(topology.condition_models()['full'], self.full)
        self.assertEqual(topology.counts()['actors'], 36)

    def test_reviewed_delta_does_not_allow_other_policy_or_safety_changes(self):
        for field in ('id', 'severity', 'triggers', 'requires', 'conflicts', 'report', 'closure',
                      'hot_path', 'operational_guidance', 'reviewed_model_delta_id'):
            with self.subTest(field=field):
                full, prereg = copy.deepcopy(self.full), copy.deepcopy(self.prereg)
                if field == 'hot_path': full['hot_path'].reverse()
                elif field == 'operational_guidance': full['operational_guidance'].pop()
                elif field == 'reviewed_model_delta_id': prereg[field] = 'optimizer-selected-delta'
                else: full['policies'][0][field] = 'unreviewed-mutation'
                prereg['full_model_sha256'] = study.digest(full)
                with self.assertRaises(ValueError):
                    study.EngineeringStudy(prereg, baseline_model=self.baseline, full_model=full,
                        configuration=self.configuration, consumed_source_pins=self.pins)
        full = copy.deepcopy(self.full)
        next(p for p in full['policies'] if p['id'] == 'EVIDENCE_AFFECTED')['closure'] += ' optimizer change'
        self.prereg['full_model_sha256'] = study.digest(full)
        with self.assertRaises(ValueError):
            study.EngineeringStudy(self.prereg, baseline_model=self.baseline, full_model=full,
                configuration=self.configuration, consumed_source_pins=self.pins)

    def test_family_fixture_metadata_uses_registered_ids_and_complete_stage_sets(self):
        topology = self.build()
        registry = {'families': [{'family': name, 'stages': [
            {'stage': stage, 'public_task': name + '/' + stage + '.json',
             'private_contract': name + '/contract.json', 'reference': name + '/reference.py'}
            for stage in stages]} for name, stages in topology.family_stages().items()]}
        expected = topology.fixture_bindings(registry)
        registry['families'].reverse()
        self.assertEqual(topology.fixture_bindings(registry), expected)
        registry['families'][0]['stages'].pop()
        with self.assertRaises(ValueError): topology.fixture_bindings(registry)
        with self.assertRaises(ValueError): topology.validate_family_stage('f_unknown', 'source')

    def test_configuration_source_identity_and_protocol_order_are_bound(self):
        topology = self.build()
        protocol = {'identity': self.prereg['study_id'], 'counts': topology.counts(),
            'order': topology.fixed_order(), 'actor_registry': topology.fixed_registry(),
            'ledger_registry_identity': topology.registry_identity(), 'round_caps': topology.caps(),
            'profile_configuration_sha256': study.CONFIGURATION_SHA256,
            'study_topology_sha256': topology.preregistration_sha256}
        self.assertEqual(topology.validate_protocol(protocol), protocol)
        protocol['order']['workflows'][0], protocol['order']['workflows'][1] = protocol['order']['workflows'][1], protocol['order']['workflows'][0]
        with self.assertRaises(ValueError): topology.validate_protocol(protocol)
        self.configuration['admission_limits']['max_requests'] = 25
        with self.assertRaises(ValueError): self.build()
        self.configuration = provider_tools.profile_configuration(study.PROFILE_ID)
        self.prereg['source_pins'] = dict(self.pins, **{study.MODULE: '8' * 64})
        with self.assertRaises(ValueError): self.build()

    def test_topology_smoke_has_no_io_dispatch_or_observed_result_input(self):
        original = copy.deepcopy(self.prereg)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('no source/task/result IO')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('no subprocess')), \
             patch.object(socket, 'socket', side_effect=AssertionError('no network')):
            topology = self.build()
            topology.fixed_order(); topology.fixed_registry(); topology.counts()
            topology.caps(); topology.private_panel_assignment()
        self.assertEqual(self.prereg, original)


if __name__ == '__main__':
    unittest.main()
