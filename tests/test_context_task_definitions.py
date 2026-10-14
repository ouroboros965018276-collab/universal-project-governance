"""Pure exposed regression fixtures; never construct the proposed registered seed.

No actual sealed task, model output, key, subprocess, network or project checkout
is read. Fixture seeds/namespaces differ from proposed fresh study identities.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Finite Python behavior profile requires Python 3.10+")

from evolution.experiments import context_tasks as GEN
from evolution import semantic_contract as VM
from evolution.tool_broker import MAX_FILE_BYTES, RepoBroker, validate_task


class SemanticTaskFixtures(unittest.TestCase):
    def setUp(self):
        for module, name in [(socket, "socket"), (socket, "create_connection")] + [
                (subprocess, name) for name in ("Popen", "run", "check_output", "check_call", "call")]:
            fence = patch.object(module, name, side_effect=AssertionError("network/CLI forbidden"))
            fence.start()
            self.addCleanup(fence.stop)

    def fixture(self, family, instance=1):
        return GEN.build_case(family, instance, seed=90137, namespace="fixture_semantic_only")

    def assess(self, case, files):
        return GEN.assess_case(case, files, VM.validate_behavior)

    def test_registration_is_metadata_only_fixed_fourteen_and_no_selection(self):
        with patch.object(GEN, "build_case", side_effect=AssertionError("must not construct registered instances")):
            metadata = GEN.registration_plan()
        self.assertEqual(metadata["seed"], 20023)
        self.assertEqual(len(metadata["order"]), 14)
        self.assertEqual(metadata["order"], [{"family": family, "instance": instance} for family in GEN.FAMILIES for instance in (1, 2)])
        self.assertFalse(metadata["measurement"]["new_distribution_claim"])
        self.assertFalse(metadata["measurement"]["whole_python_equivalence_claim"])
        self.assertEqual(metadata["measurement"]["qualification"], "UNASSESSED")

    def test_all_fourteen_reference_implementations_pass(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                with self.subTest(family=family, instance=instance):
                    case = self.fixture(family, instance)
                    outcome = self.assess(case, case["correct_files"])
                    self.assertTrue(outcome["ok"], outcome)

    def test_all_fixture_and_handoff_roles_register_with_canonical_broker(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                case = self.fixture(family, instance)
                task = GEN.to_broker_task(case)
                self.assertIs(validate_task(task), task)
        for instance in (1, 2):
            pair = GEN.build_handoff_pair(instance, seed=90138, namespace="fixture_broker_chain")
            source = GEN.to_broker_task(pair["source"])
            self.assertIs(validate_task(source), source)
            receiver = GEN.receiver_from_snapshot(pair, pair["source"]["correct_files"], VM.validate_behavior)
            task = GEN.to_broker_task(receiver)
            self.assertIs(validate_task(task), task)

    def test_equivalent_local_return_and_reorganized_if_implementations_pass(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                with self.subTest(family=family, instance=instance):
                    case = self.fixture(family, instance)
                    alternate = GEN.equivalent_files(case)
                    self.assertNotEqual(alternate[case["roles"]["core"]], case["correct_files"][case["roles"]["core"]])
                    outcome = self.assess(case, alternate)
                    self.assertTrue(outcome["ok"], outcome)

    def test_original_noop_delete_module_delete_driver_unsafe_and_public_hardcode_fail(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                case = self.fixture(family, instance)
                for mutant in ("old-noop", "delete-module", "delete-driver", "unsafe", "hardcode-public-examples"):
                    with self.subTest(family=family, instance=instance, mutant=mutant):
                        self.assertFalse(self.assess(case, GEN.mutant_files(case, mutant))["ok"])

    def test_bypassing_canonical_consumer_or_discarding_its_result_fails(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                case = self.fixture(family, instance)
                for mutant in ("bypass-canonical-consumer", "call-and-discard-canonical"):
                    with self.subTest(family=family, instance=instance, mutant=mutant):
                        outcome = self.assess(case, GEN.mutant_files(case, mutant))
                        self.assertFalse(outcome["ok"])
                        # API consumers are writable, so this case must fail the
                        # semantic route itself rather than protected-byte scope.
                        if family == "public-api-consumers":
                            self.assertTrue(any("route" in item["code"] or "call" in item["code"] for item in outcome["behavior"]["failures"]), outcome)

    def test_instances_are_disjoint_new_paths_functions_and_contracts(self):
        cases = [self.fixture(family, instance) for family in GEN.FAMILIES for instance in (1, 2)]
        self.assertEqual(len({case["identity"]["nonce"] for case in cases}), 14)
        self.assertEqual(len({case["task"]["id"] for case in cases}), 14)
        self.assertEqual(len({case["roles"]["core"] for case in cases}), 14)
        self.assertEqual(len({case["roles"]["function"] for case in cases}), 14)
        self.assertEqual(len({json.dumps(case["task"]["semantic_contract"], sort_keys=True) for case in cases}), 14)
        other = GEN.build_case(GEN.FAMILIES[0], 1, seed=90138, namespace="fixture_other_only")
        self.assertNotEqual(other["identity"]["nonce"], cases[0]["identity"]["nonce"])

    def test_private_probes_are_not_project_visible_examples_and_include_errors(self):
        for family in GEN.FAMILIES:
            case = self.fixture(family)
            visible_path = next(path for path in case["task"]["initial_files"] if path.endswith("_CONTRACT.json"))
            visible = json.loads(case["task"]["initial_files"][visible_path])
            self.assertNotIn("probes", visible)
            self.assertEqual(visible["language"]["builtins"], ["len", "str", "int", "bool", "abs"])
            self.assertEqual(visible["language"]["limits"], VM.DEFAULT_LIMITS)
            self.assertIn("min/max builtins", visible["language"]["unsupported"])
            self.assertEqual(visible["writable_files"], case["task"]["writable_files"])
            self.assertEqual(visible["exports"][case["roles"]["core"]], case["task"]["semantic_contract"]["modules"][case["roles"]["core"]]["required_functions"])
            self.assertEqual(len(visible["required_routes"]), 2)
            self.assertLess(len(visible["public_examples"]), len(case["task"]["semantic_contract"]["probes"]))
            private_values = [item["args"][0] for item in case["task"]["semantic_contract"]["probes"] if item["path"] == case["roles"]["core"]]
            self.assertTrue(any(value not in [item["value"] for item in visible["public_examples"]] for value in private_values))
            if family != "simplification-preserves-safety":
                self.assertTrue(any(item["expect"].get("raises") == "ValueError" for item in case["task"]["semantic_contract"]["probes"]))

    def test_navigation_has_existing_index_long_irrelevant_reference_and_protected_scope(self):
        case = self.fixture("single-feature-navigation")
        files, task = case["task"]["initial_files"], case["task"]
        notes = next(path for path in files if path.endswith("_NOTES.md"))
        self.assertGreater(len(files[notes]), 16_000)
        self.assertIn(notes, files["MODULE_MAP.md"])
        self.assertNotIn(notes, task["required_read_paths"])
        self.assertIn(notes, task["semantic_contract"]["protected_files"])
        self.assertEqual(task["writable_files"], [case["roles"]["core"]])

    def test_public_interface_requires_consumer_driver_and_keyword_forwarding(self):
        case = self.fixture("public-api-consumers")
        self.assertEqual(set(case["task"]["writable_files"]), {case["roles"]["core"], case["roles"]["consumer"], case["roles"]["driver"]})
        for path in (case["roles"]["consumer"], case["roles"]["driver"]):
            functions = case["task"]["semantic_contract"]["modules"][path]["required_functions"]
            self.assertEqual(next(iter(functions.values()))["kwdefaults"], {"loud": True})
            changed = copy.deepcopy(case["correct_files"])
            changed[path] = case["task"]["initial_files"][path]
            self.assertFalse(self.assess(case, changed)["ok"])

    def test_stale_index_is_corrected_using_existing_source_without_reviving_old_symbol(self):
        case = self.fixture("stale-map-source-conflict")
        visible_path = next(path for path in case["task"]["initial_files"] if path.endswith("_CONTRACT.json"))
        visible = json.loads(case["task"]["initial_files"][visible_path])
        self.assertEqual(visible["module_map_contract"]["expected_text"], case["correct_files"]["MODULE_MAP.md"])
        self.assertIn("exact UTF-8", visible["module_map_contract"]["comparison"])
        self.assertIn("retired_", case["task"]["initial_files"]["MODULE_MAP.md"])
        self.assertIn(case["roles"]["function"], case["task"]["initial_files"][case["roles"]["core"]])
        self.assertNotIn("retired_", case["correct_files"]["MODULE_MAP.md"])
        changed = copy.deepcopy(case["correct_files"])
        changed["MODULE_MAP.md"] = case["task"]["initial_files"]["MODULE_MAP.md"]
        self.assertFalse(self.assess(case, changed)["ok"])
        old_symbol = case["task"]["semantic_contract"]["modules"][case["roles"]["core"]]["forbidden_symbols"][0]
        for path in (case["roles"]["core"], case["roles"]["consumer"]):
            changed = copy.deepcopy(case["correct_files"])
            changed[path] += "\ndef %s(value):\n    return value\n" % old_symbol
            self.assertFalse(self.assess(case, changed)["ok"])

    def test_cleanup_keeps_negative_unknown_and_bounds_and_removes_old_symbols(self):
        case = self.fixture("simplification-preserves-safety")
        module = case["task"]["semantic_contract"]["modules"][case["roles"]["core"]]
        self.assertEqual(len(module["forbidden_symbols"]), 2)
        values = [probe["args"][0] for probe in case["task"]["semantic_contract"]["probes"] if probe["path"] == case["roles"]["core"]]
        self.assertIn(None, values)
        self.assertIn(-1, values)
        self.assertIn(module["constants"]["LIMIT"] + 1, values)
        mutated = copy.deepcopy(case["correct_files"])
        mutated[case["roles"]["core"]] += "\nLEGACY_BYPASS = False\n"
        self.assertFalse(self.assess(case, mutated)["ok"])

    def test_chinese_documentation_cannot_erase_negation_numbers_or_unknown(self):
        case = self.fixture("chinese-documentation")
        path = next(check["path"] for check in case["task"]["exact_checks"])
        for old, new in (("不得", "可以"), ("12", "0"), ("延迟未知", "延迟 1ms")):
            changed = copy.deepcopy(case["correct_files"])
            changed[path] = changed[path].replace(old, new)
            self.assertFalse(self.assess(case, changed)["ok"])

    def test_evidence_current_hashes_allow_equivalent_source_but_fabricated_claims_fail(self):
        case = self.fixture("evidence-fidelity")
        path = next(check["path"] for check in case["task"]["exact_checks"])
        alternate = GEN.equivalent_files(case)
        self.assertTrue(self.assess(case, alternate)["ok"])
        self.assertNotEqual(json.loads(alternate[path])["source_sha256"], json.loads(case["correct_files"][path])["source_sha256"])
        for key, value in (("application_executed", True), ("latency_ms", 1), ("runtime_tests_run", 3), ("historical_success", "passed")):
            changed = copy.deepcopy(case["correct_files"])
            evidence = json.loads(changed[path])
            evidence["claims"][key] = value
            changed[path] = json.dumps(evidence)
            self.assertFalse(self.assess(case, changed)["ok"])

    def test_every_writable_path_has_a_positive_exact_or_behavior_contract(self):
        for family in GEN.FAMILIES:
            case = self.fixture(family)
            task = case["task"]
            covered = set(task["semantic_contract"]["modules"]) | {check["path"] for check in task["exact_checks"]}
            self.assertTrue(set(task["writable_files"]) <= covered)
            self.assertEqual(set(task["initial_files"]) - set(task["writable_files"]), set(task["semantic_contract"]["protected_files"]))

    def test_broker_adapter_keeps_one_contract_and_one_positive_check_per_writable(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                case = self.fixture(family, instance)
                original = copy.deepcopy(case)
                task = GEN.to_broker_task(case)
                self.assertEqual(case, original)
                self.assertEqual(task["behavior_contract"], case["task"]["semantic_contract"])
                self.assertNotIn("semantic_contract", task)
                self.assertNotIn("exact_checks", task)
                self.assertEqual([check["path"] for check in task["checks"]], task["writable_files"])
                for check in task["checks"]:
                    if check["path"].endswith(".py"):
                        self.assertEqual(check, {"path": check["path"], "kind": "python_behavior", "expected": None})
                    else:
                        self.assertIn(check["kind"], {"text", "json", "file_hash_manifest"})

    def test_contract_registration_accepts_initial_bad_source_without_grading_it(self):
        for family in GEN.FAMILIES:
            task = GEN.to_broker_task(self.fixture(family))
            registration = VM.validate_contract(task["behavior_contract"])
            self.assertTrue(registration["ok"], registration)
            self.assertEqual(registration["status"], "PASS")
            self.assertFalse(VM.validate_behavior(task["initial_files"], task["behavior_contract"])["ok"])

    def test_broker_adapter_rejects_namespace_escape_and_uncovered_writables(self):
        for mode in ("module", "probe", "protected", "check-module", "missing-exact", "manifest"):
            case = self.fixture("evidence-fidelity" if mode == "manifest" else "chinese-documentation")
            contract = case["task"]["semantic_contract"]
            if mode == "module":
                contract["modules"]["unregistered.py"] = copy.deepcopy(contract["modules"][case["roles"]["core"]])
            elif mode == "probe":
                contract["probes"][0]["path"] = "unregistered.py"
            elif mode == "protected":
                contract["protected_files"]["unregistered.txt"] = "0" * 64
            elif mode == "check-module":
                del contract["modules"][case["roles"]["core"]]
                contract["probes"] = [item for item in contract["probes"] if item["path"] != case["roles"]["core"]]
            elif mode == "missing-exact":
                case["task"]["exact_checks"] = []
            else:
                case["task"]["exact_checks"][0]["expected"]["sources"].append("unregistered.txt")
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                GEN.to_broker_task(case)

    def test_unregistered_file_added_or_protected_changed_fails(self):
        case = self.fixture("single-feature-navigation")
        for mode in ("extra", "protected"):
            files = copy.deepcopy(case["correct_files"])
            if mode == "extra":
                files["unexpected.py"] = "def bypass(value):\n    return value\n"
            else:
                path = next(iter(case["task"]["semantic_contract"]["protected_files"]))
                files[path] += "\nchanged\n"
            self.assertFalse(self.assess(case, files)["ok"])

    def test_handoff_source_and_actual_snapshot_receiver_support_equivalent_completed_core(self):
        for instance in (1, 2):
            pair = GEN.build_handoff_pair(instance, seed=90137, namespace="fixture_handoff_only")
            direct = GEN.build_case("interrupted-handoff-recovery", instance, seed=90137, namespace="fixture_handoff_only")
            self.assertNotEqual(pair["source"]["identity"]["nonce"], direct["identity"]["nonce"])
            source = pair["source"]
            actual_snapshot = GEN.equivalent_files(source)
            self.assertTrue(self.assess(source, actual_snapshot)["ok"])
            receiver = GEN.receiver_from_snapshot(pair, actual_snapshot, VM.validate_behavior)
            self.assertEqual(receiver["task"]["initial_files"], actual_snapshot)
            core = source["roles"]["core"]
            self.assertEqual(receiver["task"]["semantic_contract"]["protected_files"][core], GEN.sha(actual_snapshot[core]))
            self.assertEqual(receiver["correct_files"][core], actual_snapshot[core])
            self.assertFalse(receiver["conversation_history_transferred"])
            self.assertTrue(self.assess(receiver, receiver["correct_files"])["ok"])

    def test_handoff_rejects_source_noop_and_missing_project_state(self):
        pair = GEN.build_handoff_pair(1, seed=90137, namespace="fixture_handoff_only")
        for mode in ("noop", "missing-state"):
            snapshot = copy.deepcopy(pair["source"]["task"]["initial_files"] if mode == "noop" else pair["source"]["correct_files"])
            if mode == "missing-state":
                del snapshot[pair["handoff_path"]]
            with self.assertRaises(ValueError):
                GEN.receiver_from_snapshot(pair, snapshot, VM.validate_behavior)

    def test_development_identity_is_explicit_without_reusing_historical_registration(self):
        self.assertEqual((GEN.SEED, GEN.NAMESPACE), (20023, "rc20_semantic_fresh_v1"))
        self.assertEqual((GEN.DEVELOPMENT_SEED, GEN.DEVELOPMENT_NAMESPACE),
                         (90139, "rc20_tools_development_v3"))
        self.assertNotEqual(GEN.DEVELOPMENT_NAMESPACE, GEN.NAMESPACE)
        case = GEN.build_case("chinese-documentation", 1, seed=GEN.DEVELOPMENT_SEED,
                              namespace=GEN.DEVELOPMENT_NAMESPACE)
        self.assertEqual(case["identity"]["seed"], 90139)
        self.assertEqual(case["measurement"]["qualification"], "UNASSESSED")
        self.assertFalse(case["measurement"]["new_distribution_claim"])
        self.assertFalse(case["measurement"]["whole_python_equivalence_claim"])

    def test_handoff_required_reads_are_the_six_public_clues_not_unrelated_content(self):
        for instance in (1, 2):
            pair = GEN.build_handoff_pair(instance, seed=GEN.DEVELOPMENT_SEED,
                                          namespace=GEN.DEVELOPMENT_NAMESPACE)
            source = pair["source"]
            receiver = GEN.receiver_from_snapshot(pair, GEN.equivalent_files(source), VM.validate_behavior)
            for case in (source, receiver):
                task, roles = case["task"], case["roles"]
                contract_path = next(path for path in task["initial_files"] if path.endswith("_CONTRACT.json"))
                expected = {"MODULE_MAP.md", contract_path, pair["handoff_path"],
                            roles["core"], roles["consumer"], roles["driver"]}
                self.assertEqual(len(task["required_read_paths"]), 6)
                self.assertEqual(set(task["required_read_paths"]), expected)
                visible = json.loads(task["initial_files"][contract_path])
                self.assertEqual(visible["required_read_paths"], task["required_read_paths"])
                irrelevant = [path for path in task["initial_files"] if path.endswith(("_NOTES.md", "_unrelated.py"))]
                self.assertEqual(len(irrelevant), 2)
                self.assertGreater(sum(len(task["initial_files"][path].encode()) for path in irrelevant), 16000)
                self.assertTrue(set(irrelevant).isdisjoint(expected))
                self.assertTrue(set(irrelevant) <= set(task["semantic_contract"]["protected_files"]))
                self.assertEqual(set(task["semantic_contract"]["protected_files"]),
                                 set(task["initial_files"]) - set(task["writable_files"]))
                self.assertTrue(self.assess(case, case["correct_files"])["ok"])

    def test_every_affected_artifact_is_required_without_unrelated_document_reads(self):
        for family in GEN.FAMILIES:
            for instance in (1, 2):
                case = GEN.build_case(family, instance, seed=GEN.DEVELOPMENT_SEED,
                                      namespace=GEN.DEVELOPMENT_NAMESPACE)
                task = GEN.to_broker_task(case)
                required = task["required_read_paths"]
                contract_path = next(path for path in task["initial_files"] if path.endswith("_CONTRACT.json"))
                self.assertEqual(json.loads(task["initial_files"][contract_path])["required_read_paths"], required)
                self.assertEqual(len(required), len(set(required)))
                self.assertTrue(set(task["writable_files"]) <= set(required))
                for path in task["initial_files"]:
                    if path.endswith(("_NOTES.md", "_unrelated.py")) or (path.endswith("_README.md") and path not in task["writable_files"]):
                        self.assertNotIn(path, required)
                if family in {"chinese-documentation", "evidence-fidelity"}:
                    artifact = case["task"]["exact_checks"][0]["path"]
                    broker = RepoBroker.__new__(RepoBroker)
                    broker.task = task
                    def read_event(paths):
                        return {"tool": "repo_read", "arguments": {"paths": paths}, "result": {"ok": True,
                            "files": {path: {"text": task["initial_files"][path], "sha256": GEN.sha(task["initial_files"][path])} for path in paths}}}
                    patch = {"tool": "repo_patch", "arguments": {}, "result": {"ok": True}}
                    self.assertEqual(broker.read_evidence_failures([read_event(required), patch]), [])
                    self.assertTrue(broker.read_evidence_failures([read_event([path for path in required if path != artifact]), patch]))

    def test_omitting_irrelevant_reads_does_not_waive_real_initial_clue_evidence(self):
        pair = GEN.build_handoff_pair(1, seed=GEN.DEVELOPMENT_SEED, namespace=GEN.DEVELOPMENT_NAMESPACE)
        for case in (pair["source"], GEN.receiver_from_snapshot(pair, pair["source"]["correct_files"], VM.validate_behavior)):
            task = GEN.to_broker_task(case)
            broker = RepoBroker.__new__(RepoBroker)
            broker.task = task
            def read_event(paths):
                return {"tool": "repo_read", "arguments": {"paths": paths}, "result": {"ok": True,
                    "files": {path: {"text": task["initial_files"][path], "sha256": GEN.sha(task["initial_files"][path])} for path in paths}}}
            required = task["required_read_paths"]
            patch = {"tool": "repo_patch", "arguments": {}, "result": {"ok": True}}
            self.assertEqual(broker.read_evidence_failures([read_event(required), patch]), [])
            core = case["roles"]["core"]
            missing = [path for path in required if path != core]
            irrelevant = [path for path in task["initial_files"] if path.endswith(("_NOTES.md", "_unrelated.py"))]
            self.assertTrue(broker.read_evidence_failures([read_event(missing + irrelevant), patch]))
            self.assertTrue(broker.read_evidence_failures([read_event(missing), patch, read_event([core])]))

    def test_handoff_stage_write_scopes_share_the_same_protected_public_contract(self):
        for instance in (1, 2):
            pair = GEN.build_handoff_pair(instance, seed=GEN.DEVELOPMENT_SEED,
                                          namespace=GEN.DEVELOPMENT_NAMESPACE)
            source = pair["source"]
            receiver = GEN.receiver_from_snapshot(pair, GEN.equivalent_files(source), VM.validate_behavior)
            path = next(name for name in source["task"]["initial_files"] if name.endswith("_CONTRACT.json"))
            raw = source["task"]["initial_files"][path]
            visible = json.loads(raw)
            self.assertNotIn("writable_files", visible)
            self.assertEqual(visible["stage_writable_files"], {
                "source": source["task"]["writable_files"], "receiver": receiver["task"]["writable_files"]})
            self.assertEqual(visible["stage_writable_files"]["source"], [source["roles"]["core"], pair["handoff_path"]])
            self.assertEqual(visible["stage_writable_files"]["receiver"], [source["roles"]["consumer"], pair["handoff_path"]])
            self.assertEqual(receiver["task"]["writable_files"], pair["receiver_blueprint"]["task"]["writable_files"])
            for case in (source, receiver):
                self.assertEqual(case["task"]["initial_files"][path], raw)
                self.assertEqual(case["task"]["semantic_contract"]["protected_files"][path], GEN.sha(raw))
                self.assertTrue(self.assess(case, case["correct_files"])["ok"])

    def test_handoff_duplicate_json_key_rejected_by_pure_admission_and_real_broker(self):
        pair = GEN.build_handoff_pair(1, seed=GEN.DEVELOPMENT_SEED, namespace=GEN.DEVELOPMENT_NAMESPACE)
        case = pair["source"]
        files = copy.deepcopy(case["correct_files"])
        files[pair["handoff_path"]] = '{"project_status":"wrong",' + files[pair["handoff_path"]].lstrip()[1:]
        self.assertFalse(self.assess(case, files)["ok"])
        with self.assertRaises(ValueError):
            GEN.receiver_from_snapshot(pair, files, VM.validate_behavior)
        with tempfile.TemporaryDirectory(prefix="duplicate-json-fixture-",
                dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
            root = Path(directory)
            for name, text in files.items():
                (root / name).write_bytes(text.encode("utf-8"))
            self.assertFalse(RepoBroker(root, GEN.to_broker_task(case), "forbidden-unused-git").validate()["ok"])

    def test_evidence_boolean_cannot_be_replaced_with_integer_in_either_grader(self):
        case = GEN.build_case("evidence-fidelity", 1, seed=GEN.DEVELOPMENT_SEED,
                              namespace=GEN.DEVELOPMENT_NAMESPACE)
        files = copy.deepcopy(case["correct_files"])
        path = next(check["path"] for check in case["task"]["exact_checks"] if check["kind"] == "file_hash_manifest")
        evidence = json.loads(files[path])
        self.assertIs(evidence["claims"]["application_executed"], False)
        evidence["claims"]["application_executed"] = 0
        files[path] = json.dumps(evidence)
        self.assertFalse(self.assess(case, files)["ok"])
        with tempfile.TemporaryDirectory(prefix="typed-json-fixture-",
                dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
            root = Path(directory)
            for name, text in files.items():
                (root / name).write_bytes(text.encode("utf-8"))
            self.assertFalse(RepoBroker(root, GEN.to_broker_task(case), "forbidden-unused-git").validate()["ok"])

    def test_exact_raw_byte_cap_is_checked_before_universal_newlines(self):
        pair = GEN.build_handoff_pair(1, seed=GEN.DEVELOPMENT_SEED, namespace=GEN.DEVELOPMENT_NAMESPACE)
        source = pair["source"]
        source_files = copy.deepcopy(source["correct_files"])
        source_files[pair["handoff_path"]] += "\r\n" * 33000
        document = GEN.build_case("chinese-documentation", 1, seed=GEN.DEVELOPMENT_SEED,
                                  namespace=GEN.DEVELOPMENT_NAMESPACE)
        check = document["task"]["exact_checks"][0]
        check["expected"] = "\n" * 33000 + "x\n"
        document_files = copy.deepcopy(document["correct_files"])
        document_files[check["path"]] = check["expected"].replace("\n", "\r\n")
        for case, files, path in ((source, source_files, pair["handoff_path"]),
                                  (document, document_files, check["path"])):
            with self.subTest(kind=case["task"]["exact_checks"][0]["kind"]):
                self.assertGreater(len(files[path].encode("utf-8")), MAX_FILE_BYTES)
                self.assertLess(len(files[path].replace("\r\n", "\n").encode("utf-8")), MAX_FILE_BYTES)
                self.assertFalse(self.assess(case, files)["ok"])
                with tempfile.TemporaryDirectory(prefix="raw-byte-cap-fixture-",
                        dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
                    root = Path(directory)
                    for name, text in files.items():
                        (root / name).write_bytes(text.encode("utf-8"))
                    with self.assertRaises(ValueError):
                        RepoBroker(root, GEN.to_broker_task(case), "forbidden-unused-git")

    def test_each_exact_kind_accepts_the_raw_byte_limit_and_rejects_one_more(self):
        pair = GEN.build_handoff_pair(1, seed=GEN.DEVELOPMENT_SEED, namespace=GEN.DEVELOPMENT_NAMESPACE)
        document = GEN.build_case("chinese-documentation", 1, seed=GEN.DEVELOPMENT_SEED,
                                  namespace=GEN.DEVELOPMENT_NAMESPACE)
        document["task"]["exact_checks"][0]["expected"] = "x" * (MAX_FILE_BYTES - 1) + "\n"
        document["correct_files"][document["task"]["exact_checks"][0]["path"]] = document["task"]["exact_checks"][0]["expected"]
        evidence = GEN.build_case("evidence-fidelity", 1, seed=GEN.DEVELOPMENT_SEED,
                                 namespace=GEN.DEVELOPMENT_NAMESPACE)
        for case in (pair["source"], document, evidence):
            check = case["task"]["exact_checks"][0]
            path = check["path"]
            files = copy.deepcopy(case["correct_files"])
            files[path] += " " * (MAX_FILE_BYTES - len(files[path].encode("utf-8")))
            for oversized in (False, True):
                with self.subTest(kind=check["kind"], oversized=oversized):
                    current = copy.deepcopy(files)
                    current[path] += " " if oversized else ""
                    self.assertEqual(len(current[path].encode("utf-8")), MAX_FILE_BYTES + int(oversized))
                    self.assertEqual(self.assess(case, current)["ok"], not oversized)
                    with tempfile.TemporaryDirectory(prefix="exact-limit-fixture-",
                            dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
                        root = Path(directory)
                        for name, text in current.items():
                            (root / name).write_bytes(text.encode("utf-8"))
                        if oversized:
                            with self.assertRaises(ValueError):
                                RepoBroker(root, GEN.to_broker_task(case), "forbidden-unused-git")
                        else:
                            self.assertTrue(RepoBroker(root, GEN.to_broker_task(case), "forbidden-unused-git").validate()["ok"])

    def test_handoff_unread_protected_bytes_still_fail_in_both_stages(self):
        pair = GEN.build_handoff_pair(1, seed=GEN.DEVELOPMENT_SEED, namespace=GEN.DEVELOPMENT_NAMESPACE)
        source = pair["source"]
        receiver = GEN.receiver_from_snapshot(pair, source["correct_files"], VM.validate_behavior)
        for case in (source, receiver):
            for suffix in ("_NOTES.md", "_unrelated.py"):
                changed = copy.deepcopy(case["correct_files"])
                path = next(path for path in changed if path.endswith(suffix))
                self.assertNotIn(path, case["task"]["required_read_paths"])
                changed[path] += "\nchanged protected bytes\n"
                self.assertFalse(self.assess(case, changed)["ok"])

    def test_documentation_fixed_comparison_is_public_and_does_not_claim_general_quality(self):
        case = GEN.build_case("chinese-documentation", 1, seed=GEN.DEVELOPMENT_SEED,
                              namespace=GEN.DEVELOPMENT_NAMESPACE)
        task = case["task"]
        path = next(name for name in task["initial_files"] if name.endswith("_CONTRACT.json"))
        visible = json.loads(task["initial_files"][path])
        contract = visible["documentation_contract"]
        check = next(check for check in task["exact_checks"] if check["kind"] == "text")
        self.assertEqual((contract["path"], contract["expected_text"]), (check["path"], check["expected"]))
        self.assertEqual(contract["comparison"], {"kind": "text", "encoding": "utf-8", "newlines": "universal-to-LF",
            "whitespace": "exact", "terminal_newline": "required", "paraphrases_accepted": False,
            "alternative_markdown_accepted": False})
        self.assertIn("不是任意等价中文改写", contract["measurement_scope"])
        self.assertEqual(visible["required_read_paths"], task["required_read_paths"])
        for mutation in (lambda text: text.replace("只读取", "仅阅读"), lambda text: text.replace("# 当前契约", "#  当前契约"),
                         lambda text: text.rstrip("\n")):
            changed = copy.deepcopy(case["correct_files"])
            changed[check["path"]] = mutation(changed[check["path"]])
            self.assertFalse(self.assess(case, changed)["ok"])

    def test_documentation_newline_contract_agrees_with_real_static_broker(self):
        case = GEN.build_case("chinese-documentation", 1, seed=GEN.DEVELOPMENT_SEED,
                              namespace=GEN.DEVELOPMENT_NAMESPACE)
        task = GEN.to_broker_task(case)
        path = next(check["path"] for check in task["checks"] if check["kind"] == "text")
        for newline in ("\n", "\r\n", "\r"):
            with self.subTest(newline=repr(newline)), tempfile.TemporaryDirectory(prefix="doc-contract-fixture-",
                    dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
                files = copy.deepcopy(case["correct_files"])
                files[path] = files[path].replace("\n", newline)
                self.assertTrue(self.assess(case, files)["ok"])
                root = Path(directory)
                for name, text in files.items():
                    (root / name).write_bytes(text.encode("utf-8"))
                self.assertTrue(RepoBroker(root, task, "forbidden-unused-git").validate()["ok"])

    def test_generator_import_has_no_io_or_model_cli_entry(self):
        source = Path(GEN.__file__).read_text(encoding="utf-8")
        tree = __import__("ast").parse(source)
        calls = [node for node in tree.body if isinstance(node, __import__("ast").Expr) and isinstance(node.value, __import__("ast").Call)]
        self.assertFalse(calls)
        self.assertFalse(any(isinstance(node, (__import__("ast").Import, __import__("ast").ImportFrom)) and
            any(alias.name.split(".")[0] in {"socket", "subprocess", "http", "requests", "os"} for alias in node.names) for node in tree.body))


if __name__ == "__main__":
    unittest.main()
