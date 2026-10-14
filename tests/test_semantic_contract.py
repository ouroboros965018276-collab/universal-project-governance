"""Independent synthetic tests. No generator, study, network, or filesystem input."""
from copy import deepcopy
import ast
import hashlib
import unittest
from unittest.mock import patch

import sys
if sys.version_info < (3, 10):
    raise unittest.SkipTest("Finite Python behavior profile requires Python 3.10+")

from evolution.semantic_contract import (
    BehaviorContractError, DEFAULT_LIMITS, require_behavior,
    validate_behavior, validate_contract,
)


def signature(*params, kwonly=(), defaults=None, kwdefaults=None):
    return {"params": list(params), "kwonly": list(kwonly),
            "defaults": defaults or {}, "kwdefaults": kwdefaults or {}}


def single(source="def f(x):\n    return x + 1\n", cases=None):
    if cases is None:
        cases = [(0, 1), (8, 9), (-4, -3)]
    return {"m.py": source}, {
        "schema_version": 1,
        "modules": {"m.py": {"required_functions": {"f": signature("x")}}},
        "probes": [{"path": "m.py", "function": "f", "args": [x], "expect": {"return": y}} for x, y in cases],
    }


def routed(consumer="def use(x):\n    answer = canonical(x)\n    return answer\n"):
    files = {
        "core.py": "def fix(x):\n    if x is None:\n        raise ValueError('required')\n    return x.strip().casefold()\n",
        "consumer.py": "from core import fix as canonical\n" + consumer,
        "driver.py": "from consumer import use\ndef run(x):\n    return use(x)\n",
        "README.md": "Synthetic protected reference.\n",
    }
    contract = {"schema_version": 1, "modules": {
        "core.py": {"required_functions": {"fix": signature("x")}},
        "consumer.py": {"required_functions": {"use": signature("x")},
                        "required_imports": {"canonical": {"path": "core.py", "name": "fix"}},
                        "required_calls": {"use": [{"path": "core.py", "function": "fix"}]}},
        "driver.py": {"required_functions": {"run": signature("x")},
                      "required_imports": {"use": {"path": "consumer.py", "name": "use"}},
                      "required_calls": {"run": [{"path": "consumer.py", "function": "use"}]}},
    }, "protected_files": {"README.md": hashlib.sha256(files["README.md"].encode()).hexdigest()},
        "probes": [{"path": "driver.py", "function": "run", "args": [text], "expect": {"return": output}}
                   for text, output in [(" A ", "a"), ("b", "b"), (" Straße ", "strasse"), ("", "")]]}
    contract["probes"].append({"path": "driver.py", "function": "run", "args": [None], "expect": {"raises": "ValueError"}})
    return files, contract


class EquivalentPrograms(unittest.TestCase):
    def assertPass(self, files, contract):
        result = validate_behavior(files, contract)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checks_total"], result["checks_passed"])

    def test_direct_return_and_local_assignment(self):
        for source in ("def f(x):\n    return x + 1\n",
                       "def f(x):\n    adjusted = x + 1\n    answer = adjusted\n    return answer\n"):
            self.assertPass(*single(source))

    def test_synonymous_guard_forms(self):
        for guard in ("if not trusted:\n        return False\n    return 0 <= attempts < LIMIT",
                      "if trusted:\n        accepted = attempts >= 0 and attempts < LIMIT\n        return accepted\n    return False",
                      "return trusted and 0 <= attempts and attempts < LIMIT"):
            files = {"gate.py": "LIMIT = 72\ndef allow(attempts, trusted):\n    " + guard + "\n"}
            c = {"schema_version": 1, "modules": {"gate.py": {"constants": {"LIMIT": 72},
                 "required_functions": {"allow": signature("attempts", "trusted")}}}, "probes": []}
            for attempts in (-1, 0, 1, 71, 72, 400):
                for trusted in (False, True):
                    c["probes"].append({"path": "gate.py", "function": "allow", "args": [attempts, trusted],
                                        "expect": {"return": trusted and 0 <= attempts < 72}})
            self.assertPass(files, c)

    def test_pure_string_methods_and_literals(self):
        source = "def f(x):\n    cleaned = x.strip().lower()\n    return {'label': cleaned.upper(), 'parts': [len(cleaned), str(3), True, None]}\n"
        self.assertPass(*single(source, [(" hi ", {"label": "HI", "parts": [2, "3", True, None]})]))

    def test_typed_kwonly_and_defaults(self):
        files, c = single("OFFSET = 2\ndef f(x=OFFSET, *, prefix='p'):\n    return prefix + str(x)\n", [])
        c["modules"]["m.py"]["required_functions"]["f"] = signature("x", defaults={"x": 2}, kwonly=["prefix"], kwdefaults={"prefix": "p"})
        c["probes"] = [{"path": "m.py", "function": "f", "args": [], "expect": {"return": "p2"}},
                       {"path": "m.py", "function": "f", "args": [4], "kwargs": {"prefix": "n"}, "expect": {"return": "n4"}}]
        self.assertPass(files, c)

    def test_exception_probe_and_short_circuit(self):
        files, c = single("def f(x):\n    if x is None:\n        raise ValueError('missing')\n    return x and 9\n", [(False, False), (True, 9)])
        c["probes"].append({"path": "m.py", "function": "f", "args": [None], "expect": {"raises": "ValueError"}})
        self.assertPass(files, c)

    def test_static_registered_import_chain(self):
        self.assertPass(*routed())

    def test_import_alias_is_not_an_exact_source_spelling_constraint(self):
        files, c = routed()
        files["consumer.py"] = files["consumer.py"].replace("canonical", "renamed_local")
        self.assertPass(files, c)

    def test_required_call_through_returned_container_slot(self):
        self.assertPass(*routed("def use(x):\n    values = ['other', canonical(x)]\n    return values[-1]\n"))

    def test_required_call_as_real_returning_guard(self):
        files, c = routed("def use(x):\n    if canonical(x):\n        return True\n    return False\n")
        for probe in c["probes"][:-1]:
            probe["expect"]["return"] = bool(probe["expect"]["return"])
        self.assertPass(files, c)

    def test_registered_constant_import(self):
        files, c = single("from settings import OFFSET\ndef f(x):\n    return x + OFFSET\n")
        files["settings.py"] = "OFFSET = 1\n"
        c["modules"]["settings.py"] = {"constants": {"OFFSET": 1}}
        self.assertPass(files, c)

    def test_pure_constant_expression_preserves_value(self):
        files, c = single("OFFSET = 4 - 3\ndef f(x):\n    return x + OFFSET\n")
        c["modules"]["m.py"]["constants"] = {"OFFSET": 1}
        self.assertPass(files, c)

    def test_local_if_assignment_and_subscript(self):
        source = "def f(x):\n    if x >= 0:\n        result = {'v': x + 1}\n    else:\n        result = {'v': 0}\n    return result['v']\n"
        self.assertPass(*single(source, [(0, 1), (5, 6), (-4, 0)]))


class AntiMutants(unittest.TestCase):
    def assertRejected(self, files, contract, code=None):
        result = validate_behavior(files, contract)
        self.assertFalse(result["ok"], result)
        if code:
            self.assertIn(code, {f["code"] for f in result["failures"]}, result)

    def test_noop_and_hardcoded_answer(self):
        for source in ("def f(x):\n    return x\n", "def f(x):\n    return 1\n"):
            self.assertRejected(*single(source), "return-mismatch")

    def test_deleted_module_or_driver(self):
        for path in ("core.py", "consumer.py", "driver.py"):
            files, c = routed()
            del files[path]
            self.assertRejected(files, c, "missing-module")

    def test_signature_reordered_or_default_changed(self):
        files, c = single("def f(other):\n    return other + 1\n")
        self.assertRejected(files, c, "signature-mismatch")
        files, c = single("def f(x=3):\n    return x + 1\n")
        self.assertRejected(files, c, "signature-mismatch")

    def test_kwonly_cannot_become_positional(self):
        files, c = single("def f(x, prefix='p'):\n    return x + 1\n")
        c["modules"]["m.py"]["required_functions"]["f"] = signature("x", kwonly=["prefix"], kwdefaults={"prefix": "p"})
        self.assertRejected(files, c, "signature-mismatch")

    def test_deprecated_symbol_cannot_remain(self):
        files, c = single("OLD = 0\ndef f(x):\n    return x + 1\n")
        c["modules"]["m.py"]["forbidden_symbols"] = ["OLD"]
        self.assertRejected(files, c, "forbidden-symbol-present")

    def test_constant_and_protected_bytes(self):
        files, c = single("LIMIT = 71\ndef f(x):\n    return x + 1\n")
        c["modules"]["m.py"]["constants"] = {"LIMIT": 72}
        self.assertRejected(files, c, "constant-mismatch")
        files, c = routed()
        files["README.md"] += "drift"
        self.assertRejected(files, c, "protected-file-mismatch")

    def test_missing_required_import(self):
        files, c = routed()
        files["consumer.py"] = "def use(x):\n    return x.strip().casefold()\n"
        self.assertRejected(files, c, "required-import-mismatch")

    def test_unused_import_duplicate_logic(self):
        files, c = routed("def use(x):\n    if x is None:\n        raise ValueError('required')\n    return x.strip().casefold()\n")
        self.assertRejected(files, c, "required-call-not-in-result")

    def test_call_and_discard_duplicate_logic(self):
        files, c = routed("def use(x):\n    canonical(x)\n    return x.strip().casefold()\n")
        self.assertRejected(files, c, "required-call-not-in-result")

    def test_unselected_container_slot_is_not_dependency(self):
        files, c = routed("def use(x):\n    results = [x.strip().casefold(), canonical(x)]\n    return results[0]\n")
        self.assertRejected(files, c, "required-call-not-in-result")

    def test_dead_if_condition_is_not_dependency(self):
        files, c = routed("def use(x):\n    if canonical(x):\n        unused = 1\n    return x.strip().casefold()\n")
        self.assertRejected(files, c, "required-call-not-in-result")

    def test_guard_weakening_fails_boundaries(self):
        files, c = single("def f(x):\n    return x < 8\n", [(-1, False), (0, True), (7, True), (8, False)])
        self.assertRejected(files, c, "return-mismatch")

    def test_bool_int_output_not_interchangeable(self):
        self.assertRejected(*single("def f(x):\n    return True\n", [(0, 1)]), "return-mismatch")

    def test_wrong_or_missing_expected_exception(self):
        files, c = single("def f(x):\n    return x + 1\n")
        c["probes"][0]["expect"] = {"raises": "ValueError"}
        self.assertRejected(files, c, "return-mismatch")
        files, c = single("def f(x):\n    raise TypeError('wrong')\n")
        c["probes"][0]["expect"] = {"raises": "ValueError"}
        self.assertRejected(files, c, "exception-mismatch")


class UnsupportedAndLimits(unittest.TestCase):
    def assertUnsupported(self, source, code=None, **limits):
        files, c = single(source)
        if limits:
            c["limits"] = limits
        result = validate_behavior(files, c)
        self.assertEqual(result["status"], "UNSUPPORTED", result)
        if code:
            self.assertIn(code, {f["code"] for f in result["failures"]}, result)

    def test_no_host_execution_import_or_dynamic_attribute(self):
        for source in (
            "import os\ndef f(x):\n    return x + 1\n",
            "from os import system\ndef f(x):\n    return x + 1\n",
            "def f(x):\n    return __import__('os')\n",
            "def f(x):\n    return x.__class__\n",
            "def f(x):\n    return x.read()\n",
            "def f(x):\n    if False:\n        open('forbidden')\n    return x + 1\n",
            "def f(x):\n    if False:\n        eval('1')\n    return x + 1\n",
        ):
            with self.subTest(source=source):
                self.assertUnsupported(source)

    def test_unsupported_language_never_passes_even_unreached(self):
        for fragment in ("while False:\n        x = 1", "for item in []:\n        x = item", "x = [i for i in []]",
                         "x = lambda: 1", "try:\n        x = 1\n    except:\n        x = 2", "x += 1", "x = (1, 2)"):
            self.assertUnsupported("def f(x):\n    " + fragment + "\n    return x + 1\n")

    def test_reserved_binding_and_duplicate_parameters(self):
        self.assertUnsupported("def f(x):\n    ValueError = 2\n    return x + 1\n")
        self.assertUnsupported("def f(x, x):\n    return x + 1\n")

    def test_loopless_recursion_bounded(self):
        self.assertUnsupported("def f(x):\n    return f(x)\n", "call-depth-limit", call_depth=4)

    def test_step_expression_ast_source_limits(self):
        self.assertUnsupported("def f(x):\n    y = x + 1\n    return y\n", "step-limit", steps=3)
        self.assertUnsupported("def f(x):\n    return (x + 1) + 0\n", "expression-depth-limit", expression_depth=2)
        self.assertUnsupported("def f(x):\n    return x + 1\n", "ast-node-limit", ast_nodes=3)
        self.assertUnsupported("def f(x):\n    return x + 1\n", "source-size-limit", source_bytes=8)

    def test_output_size_and_integer_limits_before_huge_allocation(self):
        self.assertUnsupported("def f(x):\n    return 'a' * 1000000000\n", "operation-size-limit")
        self.assertUnsupported("def f(x):\n    return 128 * 128\n", "integer-size-limit", integer_bits=8)

    def test_unregistered_python_error_is_not_misreported_as_type_error(self):
        files, c = single("def f(x):\n    return {}['missing']\n")
        for probe in c["probes"]:
            probe["expect"] = {"raises": "TypeError"}
        result = validate_behavior(files, c)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertIn("unsupported-operation-error", {f["code"] for f in result["failures"]})

    def test_exception_and_data_handling_has_no_host_calls(self):
        files, c = single()
        normal_import = __import__
        def stdlib_only(name, *args, **kwargs):
            # ast.walk itself imports collections.deque. This is trusted parser
            # machinery, not a submitted import or module lookup.
            if name != "collections":
                raise AssertionError("unexpected host import")
            return normal_import(name, *args, **kwargs)
        with patch("builtins.open", side_effect=AssertionError("host open")), \
             patch("builtins.eval", side_effect=AssertionError("host eval")), \
             patch("builtins.exec", side_effect=AssertionError("host exec")), \
             patch("builtins.__import__", side_effect=stdlib_only):
            self.assertTrue(validate_behavior(files, c)["ok"])


class ContractSchema(unittest.TestCase):
    def test_schema_does_not_require_initial_behavior(self):
        files, c = single("def f(x):\n    return 0\n")
        self.assertTrue(validate_contract(c)["ok"])
        self.assertFalse(validate_behavior(files, c)["ok"])

    def test_protected_hash_preserves_raw_crlf(self):
        files, c = single()
        files["protected.txt"] = "first\r\nsecond\r\n"
        c["protected_files"] = {"protected.txt": hashlib.sha256(files["protected.txt"].encode()).hexdigest()}
        self.assertTrue(validate_behavior(files, c)["ok"])
        files["protected.txt"] = files["protected.txt"].replace("\r\n", "\n")
        self.assertFalse(validate_behavior(files, c)["ok"])

    def test_only_lower_limits(self):
        _, c = single()
        c["limits"] = {"steps": 50}
        self.assertTrue(validate_contract(c)["ok"])
        c["limits"]["steps"] = DEFAULT_LIMITS["steps"] + 1
        self.assertFalse(validate_contract(c)["ok"])

    def test_paths_references_and_expected_types(self):
        for path in ("../m.py", "/m.py", "C:/m.py", "a\\m.py", "a//m.py", "a/./m.py", "m\x00.py"):
            _, c = single()
            c["modules"] = {path: c["modules"]["m.py"]}
            self.assertFalse(validate_contract(c)["ok"], path)
        _, c = single()
        c["probes"][0]["path"] = "unregistered.py"
        self.assertFalse(validate_contract(c)["ok"])
        _, c = single()
        c["probes"][0]["expect"] = {"return": 1.5}
        self.assertEqual(validate_contract(c)["status"], "UNSUPPORTED")

    def test_value_depth_nodes_and_aggregate_char_limits(self):
        for limits, value, code in (({"value_depth": 2}, [[[1]]], "value-depth-limit"),
                                    ({"value_nodes": 4}, [1, 2, 3, 4], "value-node-limit"),
                                    ({"value_chars": 6}, ["four", "four"], "value-character-limit")):
            _, c = single()
            c["limits"] = limits
            c["probes"][0]["args"] = [value]
            result = validate_contract(c)
            self.assertFalse(result["ok"])
            self.assertIn(code, {f["code"] for f in result["failures"]})

    def test_dictionary_keys_share_value_size_budget(self):
        _, c = single()
        c["limits"] = {"string_chars": 8}
        c["probes"][0]["args"] = [{"long_key_which_is_not_exempt": 1}]
        self.assertFalse(validate_contract(c)["ok"])

    def test_invalid_shapes_fail_closed(self):
        for c in (None, {}, {"schema_version": True}, {"schema_version": 1, "modules": [], "probes": []}):
            self.assertFalse(validate_contract(c)["ok"])
        for key, value in (("limits", []), ("probes", [None]), ("protected_files", {"../x": "0" * 64})):
            _, c = single()
            c[key] = value
            self.assertFalse(validate_contract(c)["ok"])

    def test_import_and_route_references_must_be_registered(self):
        _, c = routed()
        c["modules"]["consumer.py"]["required_calls"]["use"][0]["path"] = "missing.py"
        self.assertFalse(validate_contract(c)["ok"])
        _, c = routed()
        c["modules"]["consumer.py"]["required_imports"]["canonical"]["path"] = "../core.py"
        self.assertFalse(validate_contract(c)["ok"])

    def test_diagnostics_reveal_no_source_expected_or_exception_message(self):
        source = "def f(x):\n    raise ValueError('PRIVATE_BODY_1')\n"
        files, c = single(source, [(1, "PRIVATE_EXPECTED_2")])
        result = repr(validate_behavior(files, c))
        self.assertNotIn("PRIVATE_BODY_1", result)
        self.assertNotIn("PRIVATE_EXPECTED_2", result)
        with self.assertRaisesRegex(BehaviorContractError, "^python-behavior-contract-failed$"):
            require_behavior(files, c)

    def test_no_compile_eval_exec_calls_in_interpreter_ast(self):
        # Inspect only the trusted implementation text, never submitted Python.
        from pathlib import Path
        tree = ast.parse((Path(__file__).resolve().parents[1] / "evolution/semantic_contract.py").read_text(encoding="utf-8"))
        forbidden = {"eval", "exec", "compile", "open", "__import__"}
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in forbidden for n in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
