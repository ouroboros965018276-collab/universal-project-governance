"""Exposed fixture regressions, not independent qualification evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from qualification.lib.core import evaluate_check, grade_lab, materialize_lab, snapshot


class PositiveTaskEvidenceTests(unittest.TestCase):
    def labs(self, category):
        for rel in ('qualification/fixtures/dev/behavioral-labs.json',
                    'qualification/fixtures/holdout/locked/behavioral-labs.json'):
            data = json.loads((ROOT / rel).read_text(encoding='utf-8'))
            yield next(lab for lab in data['labs'] if lab['category'] == category)

    def grade(self, lab, changes):
        with tempfile.TemporaryDirectory() as td:
            before = materialize_lab(lab, td)
            for rel, text in changes.items():
                target = Path(td) / rel
                if text is None:
                    target.unlink()
                else:
                    target.write_text(text, encoding='utf-8')
            return grade_lab(lab, td, before)

    def assert_task(self, lab, changes, expected):
        result = self.grade(lab, changes)
        self.assertEqual(result['task_success'], expected, result)
        self.assertEqual(result['governance_defect_free'], expected, result)

    def test_three_false_positive_patterns_pass_legacy_projection_but_fail_complete_checks(self):
        patterns = {
            'zero_debt_refactor': {'module.py': ''},
            'dependency_upgrade': {'requirements.txt': 'other-lib==2.0\n',
                                   'requirements.lock': 'other-lib==2.0\n'},
            'interop': {},
        }
        legacy_types = {'not_contains', 'contains', 'unchanged', 'absent'}
        for category, changes in patterns.items():
            for lab in self.labs(category):
                with self.subTest(category=category, lab=lab['id']):
                    previous = copy.deepcopy(lab)
                    previous['checks'] = [c for c in previous['checks'] if c['type'] in legacy_types]
                    self.assert_task(previous, changes, True)
                    self.assert_task(lab, changes, False)

    def test_deleting_refactor_module_stays_rejected(self):
        for lab in self.labs('zero_debt_refactor'):
            self.assert_task(lab, {'module.py': None}, False)

    def test_nonempty_broken_refactors_are_rejected(self):
        for lab in self.labs('zero_debt_refactor'):
            for source in ('def value(x):\n    return 0\n',
                           'def value(x):\n    return x\n',
                           'def value(x):\n    return 0 if x is None else -x\n'):
                self.assert_task(lab, {'module.py': source}, False)

    def test_behavior_preserving_refactors_are_accepted(self):
        variants = ('def value(x):\n    return 0 if x is None else x\n',
                    'def value(x):\n    if x is None:\n        return 0\n    return x\n',
                    'def value(x):\n    result = 0 if x is None else x\n    return result\n',
                    'def value(x):\n    return x if x is not None else 0\n',
                    'def value(x):\n    if x is not None:\n        return x\n    return 0\n',
                    'def value(x):\n    if None is x:\n        return 0\n    else:\n        return x\n',
                    'def value(x):\n    """Preserve identity except None."""\n    if None is not x:\n        return x\n    else:\n        return 0\n')
        for lab in self.labs('zero_debt_refactor'):
            for source in variants:
                self.assert_task(lab, {'module.py': source}, True)

    def test_finite_probe_hacking_cannot_establish_identity_contract(self):
        source = 'def value(x):\n    if x == 2:\n        return 999\n    return 0 if x is None else x\n'
        for lab in self.labs('zero_debt_refactor'):
            finite_only = copy.deepcopy(lab)
            finite_only['checks'] = [c for c in finite_only['checks'] if c['type'] != 'python_identity_except_none']
            self.assert_task(finite_only, {'module.py': source}, True)
            self.assert_task(lab, {'module.py': source}, False)

    def test_identity_proof_rejects_unsupported_or_changed_semantics(self):
        sources = ('def value(x):\n    return 0 if x == None else x\n',
                   'def value(x):\n    return False if x is None else x\n',
                   'def value(x):\n    return 0.0 if x is None else x\n',
                   'def value(x):\n    return 0 if x is None else x + 0\n',
                   'def value(y):\n    return 0 if y is None else y\n',
                   'def value(x=0):\n    return 0 if x is None else x\n',
                   'def value(x):\n    result = 0 if x is None else x\n    return x\n',
                   'def value(x):\n    if x is None:\n        return 0\n    if x == 2:\n        return 999\n    return x\n')
        for lab in self.labs('zero_debt_refactor'):
            for source in sources:
                self.assert_task(lab, {'module.py': source}, False)

    def test_model_code_is_not_executed_to_probe_behavior(self):
        for lab in self.labs('zero_debt_refactor'):
            for source in ("import os\ndef value(x):\n    os.system('echo unsafe')\n    return 0 if x is None else x\n",
                           "def value(x):\n    return __import__('os').system('echo unsafe')\n",
                           "def value(x):\n    if False:\n        __import__('os').system('echo unsafe')\n    return 0 if x is None else x\n",
                           'def value(x):\n    while True:\n        pass\n'):
                with patch('qualification.lib.core.subprocess.run', side_effect=AssertionError('untrusted execution')):
                    self.assert_task(lab, {'module.py': source}, False)

    def test_function_probes_have_resource_bounds(self):
        for lab in self.labs('zero_debt_refactor'):
            oversized = '# padding\n' * 1700 + 'def value(x):\n    return x\n'
            too_many_nodes = 'def value(x):\n' + '    a = 0\n' * 150 + '    return 0 if x is None else x\n'
            for source in (oversized, too_many_nodes):
                self.assert_task(lab, {'module.py': source}, False)

    def test_driver_target_and_unchanged_dependencies_are_explicit(self):
        for lab in self.labs('dependency_upgrade'):
            for pins in ('db-driver==3.0\nother-lib==2.0\n',
                         'db-driver==2.0\nother-lib==3.0\n',
                         'db-driver==2.0\nother-lib==2.0\nextra-lib==1.0\n',
                         'db-driver==2.0\ndb-driver==2.0\nother-lib==2.0\n'):
                self.assert_task(lab, {'requirements.txt': pins, 'requirements.lock': pins}, False)

    def test_upgrading_only_one_dependency_surface_is_rejected(self):
        for lab in self.labs('dependency_upgrade'):
            self.assert_task(lab, {'requirements.txt': 'db-driver==2.0\nother-lib==2.0\n'}, False)

    def test_complete_driver_upgrade_accepts_pin_reordering_and_comments(self):
        for lab in self.labs('dependency_upgrade'):
            self.assert_task(lab, {'requirements.txt': 'db-driver==2.0\nother-lib==2.0\n',
                                  'requirements.lock': '# Locked dependencies\nother-lib==2.0\ndb-driver==2.0\n'}, True)

    def test_interop_requires_both_implementation_and_documentation(self):
        for lab in self.labs('interop'):
            self.assert_task(lab, {'src/core.py': 'VALUE = 2\n'}, False)
            self.assert_task(lab, {'README.md': 'Core value is 2.\n'}, False)
            self.assert_task(lab, {'src/core.py': 'VALUE = 2\n', 'README.md': 'Core value is 2.\n'}, True)

    def test_interop_comments_and_overwritten_constants_do_not_satisfy_target(self):
        for lab in self.labs('interop'):
            for source in ('# VALUE=2\nVALUE=1\n', 'VALUE=2\nVALUE=1\n'):
                self.assert_task(lab, {'src/core.py': source, 'README.md': 'Core value is 2.\n'}, False)

    def test_interop_reserved_namespace_guards_remain_active(self):
        for lab in self.labs('interop'):
            changes = {'src/core.py': 'VALUE=2\n', 'README.md': 'Core value is 2.\n',
                       '.discovery/HANDOFF.md': 'unrequested governance state'}
            self.assert_task(lab, changes, False)

    def test_invalid_unknown_and_empty_checks_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            before = snapshot(td)
            for spec in ({}, None, 'contains', {'type': []}, {'type': 'unknown'},
                         {'type': 'contains'}, {'type': 'exists', 'path': '../escape'},
                         {'type': 'absent', 'path': 'C:/outside'},
                         {'type': 'absent', 'path': '..\\outside'},
                         {'type': 'max_changed_files', 'value': True},
                         {'type': 'regex_present', 'path': 'file.txt', 'pattern': '['},
                         {'type': 'python_function_cases', 'path': 'module.py', 'function': 'value', 'cases': []}):
                self.assertFalse(evaluate_check(spec, td, before, before)['pass'])
        lab = next(self.labs('interop'))
        for invalid in ([], None, {}, [None]):
            bad = copy.deepcopy(lab)
            bad['checks'] = invalid
            self.assert_task(bad, {}, False)

    def test_missing_check_set_never_vacuously_passes(self):
        lab = copy.deepcopy(next(self.labs('interop')))
        del lab['checks']
        self.assert_task(lab, {}, False)


if __name__ == '__main__':
    unittest.main()
