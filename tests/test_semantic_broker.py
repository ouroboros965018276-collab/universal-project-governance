"""Real disk/Git integration of finite behavior checks and existing tool receipts."""
from copy import deepcopy
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Finite Python behavior profile requires Python 3.10+")

from evolution import semantic_contract
from evolution.tool_broker import (RepoBroker, SEMANTIC_DIAGNOSTIC_CODES,
                                   SEMANTIC_DIAGNOSTIC_LIMIT, git_command, sha, validate_task)
from evolution.provider_tools import _recoverable_tool_feedback

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    initial = {
        "core.py": "LIMIT = 72\n\ndef accept(attempts, trusted):\n    return True\n",
        "consumer.py": "from core import accept\n\ndef run(n, trusted):\n    return accept(n, trusted)\n",
        "driver.txt": "protected driver contract\r\n",
    }
    signature = lambda *names: {"params": list(names)}
    contract = {"schema_version": 1, "modules": {
        "core.py": {"constants": {"LIMIT": 72},
                    "required_functions": {"accept": signature("attempts", "trusted")}},
        "consumer.py": {"required_functions": {"run": signature("n", "trusted")},
                        "required_imports": {"route": {"path": "core.py", "name": "accept"}},
                        "required_calls": {"run": [{"path": "core.py", "function": "accept"}]}},
    }, "protected_files": {"driver.txt": sha(initial["driver.txt"].encode())},
        "probes": [{"path": "consumer.py", "function": "run", "args": [n, trusted],
                    "expect": {"return": bool(trusted and 0 <= n < 72)}}
                   for n in [-3, 0, 1, 71, 72, 89] for trusted in [False, True]]}
    return {"id": "public-semantic-fixture", "family": "guard-and-consumer",
            "prompt": "Preserve the public API, LIMIT and caller route; accept trusted attempts in [0,72).",
            "initial_files": initial, "writable_files": ["core.py", "consumer.py"],
            "behavior_contract": contract,
            "checks": [{"path": name, "kind": "python_behavior", "expected": None}
                       for name in ["core.py", "consumer.py"]],
            "required_read_paths": list(initial),
            "required_tools": ["repo_read", "repo_patch", "repo_validate", "repo_status"]}


class SemanticBrokerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="semantic-broker-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.task = fixture()
        for name, text in self.task["initial_files"].items():
            (self.root / name).write_bytes(text.encode("utf-8"))
        self.git = shutil.which("git")
        self.assertIsNotNone(self.git)
        result = git_command(self.git, self.root, "init", "--template=", "--quiet")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.broker = RepoBroker(self.root, self.task, self.git)

    def repair(self, *, source=None, caller=None):
        changes = {"core.py": source or "LIMIT = 72\n\ndef accept(attempts, trusted):\n    accepted = trusted and 0 <= attempts < LIMIT\n    return accepted\n"}
        if caller is not None:
            changes["consumer.py"] = caller
        operations = [{"path": name, "old_sha256": sha((self.root / name).read_bytes()), "new_text": text}
                      for name, text in changes.items()]
        return self.broker.call("repo_patch", {"operations": operations})

    def test_schema_registration_accepts_faulty_initial_state_then_equivalent_fix_passes(self):
        self.assertIs(validate_task(self.task), self.task)
        self.assertFalse(self.broker.validate()["ok"])
        self.assertTrue(self.repair()["ok"])
        self.assertTrue(self.broker.validate()["ok"])
        self.assertEqual((self.root / "driver.txt").read_bytes(), b"protected driver contract\r\n")

    def test_diagnostics_do_not_change_existing_success_or_failure_fields(self):
        failed = self.broker.validate()
        self.assertEqual({key: value for key, value in failed.items() if key != "diagnostics"}, {
            "ok": False, "suite": "registered-static-contracts-v1", "checks_passed": 0,
            "checks_total": 2, "failures": ["contract-failed:core.py:ValueError",
                                            "contract-failed:consumer.py:ValueError"]})
        self.assertEqual(failed["diagnostics"], [{"code": "return-mismatch", "path": "consumer.py"}])
        self.assertTrue(self.repair()["ok"])
        self.assertEqual(self.broker.validate(), {"ok": True, "suite": "registered-static-contracts-v1",
                         "checks_passed": 2, "checks_total": 2, "failures": [], "diagnostics": []})

    def test_none_guard_exception_and_unsupported_method_are_distinguishable(self):
        self.task["behavior_contract"]["probes"] = [
            {"path": "core.py", "function": "accept", "args": [None, True],
             "expect": {"return": "UNKNOWN"}}] * 3
        implementations = [
            ("if attempts is None:\n        raise ValueError\n    return 'UNKNOWN'", "exception-mismatch"),
            ("return attempts.strip()", "unsupported-method"),
        ]
        for body, code in implementations:
            with self.subTest(code=code):
                self.assertTrue(self.repair(source="LIMIT = 72\ndef accept(attempts, trusted):\n    " + body + "\n")["ok"])
                result = self.broker.validate()
                self.assertFalse(result["ok"])
                self.assertEqual(result["diagnostics"], [{"code": code, "path": "core.py"}])
                self.assertEqual(result["checks_passed"], 0)
                self.assertEqual(result["failures"], ["contract-failed:core.py:ValueError",
                                                     "contract-failed:consumer.py:ValueError"])

    def test_diagnostics_strip_private_fields_and_unregistered_values(self):
        private = "PRIVATE_INPUT_EXPECTED_SOURCE_FRAGMENT"
        fake = {"ok": False, "status": "FAIL", "failures": [
            {"code": private, "path": "outside/" + private, "probe": 417,
             "input": private, "expected": private, "source": private},
            {"code": "return-mismatch", "path": "consumer.py", "probe": 418,
             "input": private, "expected": private},
        ]}
        with patch.object(semantic_contract, "validate_behavior", return_value=fake):
            result = self.broker.validate()
        self.assertEqual(result["diagnostics"], [
            {"code": "behavior-contract-failed", "path": "consumer.py"},
            {"code": "behavior-contract-failed", "path": "core.py"},
            {"code": "return-mismatch", "path": "consumer.py"},
        ])
        encoded = json.dumps(result)
        for forbidden in [private, "probe", "417", "418", "expected", "input", "source"]:
            self.assertNotIn(forbidden, encoded)
        self.assertTrue(all(set(item) == {"code", "path"} for item in result["diagnostics"]))

    def test_diagnostics_are_deduplicated_sorted_and_bounded(self):
        failures = [{"code": code, "path": path, "probe": index}
                    for index in range(2) for path in ["core.py", "consumer.py", "driver.txt"]
                    for code in SEMANTIC_DIAGNOSTIC_CODES]
        with patch.object(semantic_contract, "validate_behavior",
                          return_value={"ok": False, "status": "FAIL", "failures": failures}):
            result = self.broker.validate()
        pairs = [(item["code"], item["path"]) for item in result["diagnostics"]]
        self.assertEqual(len(pairs), SEMANTIC_DIAGNOSTIC_LIMIT)
        self.assertEqual(pairs, sorted(set(pairs)))
        self.assertTrue(set(path for code, path in pairs) <= {"core.py", "consumer.py", "driver.txt"})

    def test_syntax_and_pathless_resource_failures_only_expose_safe_categories(self):
        self.assertTrue(self.repair(source="LIMIT = 72\ndef accept(attempts, trusted):\n    return (\n")["ok"])
        result = self.broker.validate()
        self.assertEqual(result["diagnostics"], [{"code": "syntax-error", "path": "core.py"}])
        with patch.object(semantic_contract, "validate_behavior", return_value={
                "ok": False, "status": "UNSUPPORTED", "failures": [{"code": "step-limit", "probe": 0}]}):
            result = self.broker.validate()
        self.assertEqual(result["diagnostics"], [{"code": "resource-limit", "path": "consumer.py"},
                                                {"code": "resource-limit", "path": "core.py"}])

    def test_behavior_evaluated_once_for_all_python_paths_on_each_validation(self):
        self.assertTrue(self.repair()["ok"])
        with patch.object(semantic_contract, "validate_behavior", wraps=semantic_contract.validate_behavior) as observed:
            self.assertTrue(self.broker.validate()["ok"])
            self.assertEqual(observed.call_count, 1)
            self.assertTrue(self.broker.validate()["ok"])
            self.assertEqual(observed.call_count, 2)

    def test_alias_rename_and_guard_reorganization_pass(self):
        source = "LIMIT = 72\n\ndef accept(attempts, trusted):\n    if not trusted:\n        return False\n    return attempts >= 0 and attempts < LIMIT\n"
        caller = "from core import accept as canonical\n\ndef run(n, trusted):\n    answer = canonical(n, trusted)\n    return answer\n"
        self.assertTrue(self.repair(source=source, caller=caller)["ok"])
        self.assertTrue(self.broker.validate()["ok"])

    def test_wrong_guard_and_missing_public_function_fail_without_probe_leak(self):
        for body in ["return 0 <= attempts < LIMIT", "return trusted and 0 <= attempts <= LIMIT"]:
            self.assertTrue(self.repair(source="LIMIT = 72\n\ndef accept(attempts, trusted):\n    " + body + "\n")["ok"])
            result = self.broker.validate()
            self.assertFalse(result["ok"])
            self.assertTrue(all(item.endswith(":ValueError") for item in result["failures"]))
            self.assertTrue(_recoverable_tool_feedback("repo_validate", {}, result,
                            {"state_sha256": "observed-state"}, self.task))
            self.assertNotIn("probes", str(result))
        self.repair(source="LIMIT = 72\n")
        result = self.broker.validate()
        self.assertFalse(result["ok"])
        self.assertEqual(result["diagnostics"], [{"code": "required-function-mismatch", "path": "core.py"}])

    def test_consumer_cannot_bypass_canonical_implementation(self):
        caller = "from core import accept\n\ndef run(n, trusted):\n    ignored = accept(n, trusted)\n    return trusted and 0 <= n < 72\n"
        self.assertTrue(self.repair(caller=caller)["ok"])
        self.assertFalse(self.broker.validate()["ok"])

    def test_deleted_module_or_protected_driver_never_passes(self):
        self.assertTrue(self.repair()["ok"])
        for name in ["core.py", "driver.txt"]:
            path = self.root / name
            raw = path.read_bytes()
            path.unlink()
            result = self.broker.validate()
            self.assertFalse(result["ok"])
            self.assertEqual(result["failures"], ["scope-invalid:ValueError"])
            self.assertEqual(result["diagnostics"], [])
            path.write_bytes(raw)
        (self.root / "driver.txt").write_bytes(b"protected driver contract\n")
        result = self.broker.validate()
        self.assertFalse(result["ok"])
        self.assertIn("protected-file-changed:driver.txt", result["failures"])
        self.assertEqual(result["diagnostics"], [{"code": "protected-file-mismatch", "path": "driver.txt"}])

    def test_registration_rejects_unregistered_contract_path_or_duplicate_contract(self):
        mutations = []
        task = deepcopy(self.task)
        task["behavior_contract"]["protected_files"]["outside.txt"] = "a" * 64
        mutations.append(task)
        task = deepcopy(self.task)
        task["checks"][0]["expected"] = task["behavior_contract"]
        mutations.append(task)
        task = deepcopy(self.task)
        task["checks"][0]["path"] = "driver.txt"
        mutations.append(task)
        task = deepcopy(self.task)
        task["behavior_contract"]["limits"] = {"steps": 20001}
        mutations.append(task)
        for task in mutations:
            with self.subTest(task=task["checks"]), self.assertRaises(ValueError):
                validate_task(task)

    def test_unsupported_host_code_fails_without_execution(self):
        source = "import os\nLIMIT = 72\ndef accept(attempts, trusted):\n    os.remove('driver.txt')\n    return True\n"
        self.assertTrue(self.repair(source=source)["ok"])
        result = self.broker.validate()
        self.assertFalse(result["ok"])
        self.assertEqual(result["diagnostics"], [{"code": "unsupported-language", "path": "core.py"}])
        self.assertTrue((self.root / "driver.txt").exists())

    def test_legacy_ast_stays_exact_and_task_without_contract_still_valid(self):
        legacy = deepcopy(self.task)
        legacy.pop("behavior_contract")
        for check in legacy["checks"]:
            check.update(kind="python_ast", expected=self.task["initial_files"][check["path"]])
        self.assertIs(validate_task(legacy), legacy)
        broker = RepoBroker(self.root, legacy, self.git)
        result = broker.validate()
        self.assertTrue(result["ok"])
        self.assertNotIn("diagnostics", result)
        self.repair(source="LIMIT = 72\n\ndef accept(attempts, trusted):\n    result = True\n    return result\n")
        result = broker.validate()
        self.assertFalse(result["ok"])
        self.assertNotIn("diagnostics", result)
        legacy["behavior_contract"] = self.task["behavior_contract"]
        with self.assertRaises(ValueError):
            validate_task(legacy)


if __name__ == "__main__":
    unittest.main()
