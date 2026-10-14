"""Pure exposed regression fixtures; never construct the proposed registered seed.

No actual sealed task, model output, key, subprocess, network or project checkout
is read. Fixture seeds/namespaces differ from proposed fresh study identities.
"""
from __future__ import annotations

import ast
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

    def public_text(self, case):
        path = next(path for path in case["task"]["initial_files"] if path.endswith("_CONTRACT.json"))
        return json.loads(case["task"]["initial_files"][path])

    def public_text_expectation(self, public, value, shout=False):
        """Independent reader: only project-visible data, no private contract."""
        spec = public["text_normalization"]
        if value is None:
            self.assertEqual(spec["null"]["return_type"], "str")
            self.assertFalse(spec["null"]["prefix_applied"])
            return spec["null"]["return_value"]
        self.assertEqual(spec["non_null"]["conversion"], "Python str(value)")
        self.assertEqual(spec["non_null"]["trim"], "str.strip()")
        text = str(value).strip()
        if not text:
            self.assertEqual(spec["non_null"]["empty_after_trim"], {"raises": "ValueError"})
            raise ValueError("public blank rule")
        modes = spec["output_modes"]
        mode = next(item for item in modes if item["when"] == "all non-null inputs"
                    or item["when"] == {"shout": shout})
        prefix = public["constants"][mode["prefix"]] if mode["prefix"] else ""
        self.assertIn(mode["case_method"], {"casefold", "upper"})
        return prefix + (text.casefold() if mode["case_method"] == "casefold" else text.upper())

    def public_text_vm_contract(self, public, values):
        """Construct a VM challenge using only public exports/routes/semantics."""
        modules = {path: {"required_functions": exports, "constants": public["constants"] if path == public["canonical"] else {}}
                   for path, exports in public["exports"].items()}
        for route in public["required_routes"]:
            module = modules[route["caller_path"]]
            module.setdefault("required_imports", {})[route["callee"]] = {"path": route["callee_path"], "name": route["callee"]}
            module.setdefault("required_calls", {})[route["caller"]] = [{"path": route["callee_path"], "function": route["callee"]}]
        probes = []
        for path, exports in public["exports"].items():
            for function, signature in exports.items():
                keyword = next(iter(signature["kwdefaults"]), None)
                modes = [None, False, True] if keyword else [None]
                for mode in modes:
                    kwargs = {} if mode is None else {keyword: mode}
                    effective = signature["kwdefaults"].get(keyword, False) if mode is None else mode
                    for value in values:
                        try:
                            expected = {"return": self.public_text_expectation(public, value, effective)}
                        except ValueError:
                            expected = {"raises": "ValueError"}
                        probes.append({"path": path, "function": function, "args": [value], "kwargs": kwargs, "expect": expected})
        return {"schema_version": 1, "modules": modules, "protected_files": {}, "probes": probes}

    def test_public_text_spec_alone_determines_null_coercion_blank_prefix_and_modes(self):
        values = [None, "", " \t ", "  Straße  ", 0, False, True, [], {"B": False}]
        for family in ("chinese-documentation", "public-api-consumers", "interrupted-handoff-recovery"):
            for instance in (1, 2):
                case = self.fixture(family, instance)
                public = self.public_text(case)
                spec = public["text_normalization"]
                self.assertEqual(spec["input_domain"]["values"], ["null", "bool", "bounded-int", "string", "list", "string-keyed-dict"])
                self.assertEqual(spec["null"], {"return_type": "str", "return_value": "UNKNOWN", "prefix_applied": False,
                    "before_non_null_operations": True})
                self.assertIn("not an all-input", spec["input_domain"]["measurement"])
                contract = self.public_text_vm_contract(public, values)
                self.assertTrue(VM.validate_contract(contract)["ok"])
                self.assertTrue(VM.validate_behavior(case["correct_files"], contract)["ok"])
                self.assertTrue(VM.validate_behavior(GEN.equivalent_files(case), contract)["ok"])

    def test_public_literal_examples_are_independent_of_private_sampler_and_match_public_semantics(self):
        for family in ("chinese-documentation", "public-api-consumers", "interrupted-handoff-recovery"):
            first = self.public_text(self.fixture(family))
            other_case = GEN.build_case(family, 2, seed=90404, namespace="public_text_examples_fixture")
            other = self.public_text(other_case)
            self.assertEqual([(x["value"], x.get("kwargs", {})) for x in first["public_examples"]],
                             [(x["value"], x.get("kwargs", {})) for x in other["public_examples"]])
            self.assertTrue(any(x["value"] is None and type(x.get("return")) is str and x["return"] == "UNKNOWN" for x in first["public_examples"]))
            self.assertTrue(any(type(x["value"]) is int for x in first["public_examples"]))
            self.assertTrue(any(x.get("raises") == "ValueError" for x in first["public_examples"]))
            for item in first["public_examples"]:
                if "raises" in item:
                    with self.assertRaises(ValueError):
                        self.public_text_expectation(first, item["value"], item.get("kwargs", {}).get("shout", False))
                else:
                    expected = self.public_text_expectation(first, item["value"], item.get("kwargs", {}).get("shout", False))
                    self.assertEqual((type(item["return"]), item["return"]), (type(expected), expected))

    def test_wrong_null_type_case_prefix_and_missing_branch_fail_public_only_contract(self):
        case = self.fixture("interrupted-handoff-recovery")
        public = self.public_text(case)
        contract = self.public_text_vm_contract(public, [None])
        core = case["roles"]["core"]
        for wrong in (False, "unknown", public["constants"]["PREFIX"] + "UNKNOWN"):
            tree = ast.parse(case["correct_files"][core])
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
            function.body[0].body[0] = ast.Return(value=ast.Constant(wrong))
            files = dict(case["correct_files"], **{core: ast.unparse(ast.fix_missing_locations(tree)) + "\n"})
            self.assertFalse(VM.validate_behavior(files, contract)["ok"])
        tree = ast.parse(case["correct_files"][core])
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
        function.body.pop(0)
        files = dict(case["correct_files"], **{core: ast.unparse(ast.fix_missing_locations(tree)) + "\n"})
        self.assertFalse(VM.validate_behavior(files, contract)["ok"])

    def test_api_false_true_prefix_branches_and_null_precedence_are_not_interchangeable(self):
        case = self.fixture("public-api-consumers")
        public = self.public_text(case)
        contract = self.public_text_vm_contract(public, [None, "  Straße  "])
        core = case["roles"]["core"]
        source = case["correct_files"][core]
        for wrong in (source.replace("if shout:", "if not shout:"),
                      source.replace("return 'UNKNOWN'", "return PREFIX + 'UNKNOWN'"),
                      source.replace("text.upper()", "text.casefold()")):
            self.assertFalse(VM.validate_behavior(dict(case["correct_files"], **{core: wrong}), contract)["ok"])

    def test_handoff_stages_share_text_spec_without_overwriting_actual_source_bytes(self):
        pair = GEN.build_handoff_pair(1, seed=90404, namespace="public_text_stage_fixture")
        source_public = self.public_text(pair["source"])
        receiver = GEN.receiver_from_snapshot(pair, pair["source"]["correct_files"], VM.validate_behavior)
        receiver_public = self.public_text(receiver)
        self.assertEqual(source_public["text_normalization"], receiver_public["text_normalization"])
        self.assertEqual(receiver["task"]["initial_files"], pair["source"]["correct_files"])
        self.assertEqual(source_public["stage1_behavior_scope"]["current_stage_required_routes"], [])
        document = next(check["expected"] for check in self.fixture("chinese-documentation")["task"]["exact_checks"] if check["kind"] == "text")
        for fact in ("UNKNOWN", "非 None", "不得", "未运行", "未知", "12", "32"):
            self.assertIn(fact, document)

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

    def test_evidence_public_output_shape_and_claim_values_have_one_authority(self):
        case = GEN.build_case("evidence-fidelity", 1, seed=90401, namespace="fixture_document_handoff_only")
        task = case["task"]
        path = next(name for name in task["initial_files"] if name.endswith("_CONTRACT.json"))
        public = json.loads(task["initial_files"][path])
        contract = public["evidence_contract"]
        check = task["exact_checks"][0]
        self.assertNotIn("evidence_claims", public)
        self.assertEqual(contract["required_root_keys"], ["source_sha256", "claims"])
        self.assertEqual(contract["source_paths"], check["expected"]["sources"])
        self.assertEqual(contract["claims"], check["expected"]["claims"])
        self.assertEqual(contract["path"], check["path"])
        self.assertIn("exact actual current file bytes", contract["hash"]["input"])
        self.assertIn("CRLF", contract["hash"]["input"])
        files = copy.deepcopy(case["correct_files"])
        files[case["roles"]["core"]] = files[case["roles"]["core"]].replace("\n", "\r\n")
        GEN.apply_exact(files, task["exact_checks"])
        output = json.loads(files[check["path"]])
        self.assertEqual(set(output), set(contract["required_root_keys"]))
        self.assertEqual(output["source_sha256"], {name: GEN.sha(files[name]) for name in contract["source_paths"]})
        self.assertTrue(self.assess(case, files)["ok"])
        for bad in ({"sources": output["source_sha256"], "claims": output["claims"]},
                    {"source_sha256": output["source_sha256"], "evidence_claims": output["claims"]},
                    dict(output, extra="not allowed")):
            changed = copy.deepcopy(files)
            changed[check["path"]] = json.dumps(bad)
            self.assertFalse(self.assess(case, changed)["ok"])
        with tempfile.TemporaryDirectory(prefix="public-evidence-shape-", dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
            root = Path(directory)
            for name, text in files.items():
                (root / name).write_bytes(text.encode("utf-8"))
            broker = RepoBroker(root, GEN.to_broker_task(case), "forbidden-unused-git")
            self.assertTrue(broker.validate()["ok"])
            (root / check["path"]).write_text(json.dumps({"sources": output["source_sha256"], "claims": output["claims"]}), encoding="utf-8")
            self.assertFalse(broker.validate()["ok"])

    def document_pair(self, instance=1):
        return GEN.build_document_handoff_development(instance, seed=90401, namespace="rc20_document_handoff_proposal")

    def document_snapshot(self, pair, variant=1):
        task = pair["source"]["task"]
        files = copy.deepcopy(task["initial_files"])
        paths = task["checks"][0]["expected"]["required_links"]
        links = "、".join("[资料%s](%s)" % (index, path) for index, path in enumerate(paths))
        core = pair["source"]["roles"]["core"]
        limit = pair["receiver_blueprint"]["task"]["semantic_contract"]["modules"][core]["constants"]["LIMIT"]
        if variant == 1:
            prose = ("目标只允许非None且处于闭区间0..%s的数值；None、负数和越界均返回False。当前实现仍待修复，"
                     "须移除旧绕过符号，保留消费者和驱动。应用测试未运行，延迟与旧作者更多意图未知。" % limit) + links + "。\n"
        else:
            prose = ("- 参照 " + links + "。\n- 待实现范围含端点0和%s；None、负数、高于%s的输入都应返回False。"
                     "当前进度以HANDOFF和实际源码为准，清除旧绕过并保留消费者与驱动。\n"
                     "- 应用测试尚未运行，延迟未知，磁盘以外的旧作者意图未知。\n" % (limit, limit))
        files[pair["document_path"]] = prose
        return files

    def test_document_development_scope_and_phase_specific_reads_are_public_and_bounded(self):
        with self.assertRaises(TypeError):
            GEN.build_document_handoff_development(1)
        for namespace in (None, "", "not a namespace"):
            with self.assertRaises(ValueError):
                GEN.build_document_handoff_development(1, seed=90401, namespace=namespace)
        for instance in (1, 2):
            pair = self.document_pair(instance)
            direct = GEN.build_case("simplification-preserves-safety", instance, seed=90401, namespace="rc20_document_handoff_proposal")
            self.assertNotEqual(pair["source"]["identity"]["nonce"], direct["identity"]["nonce"])
            self.assertNotEqual(pair["source"]["roles"]["core"], direct["roles"]["core"])
            source, receiver = pair["source"]["task"], pair["receiver_blueprint"]["task"]
            self.assertTrue(pair["development_only"])
            self.assertFalse(pair["independent_formal_evidence"])
            self.assertIn("UNASSESSED", pair["external_document_review"])
            self.assertIs(validate_task(source), source)
            self.assertEqual(source["writable_files"], [pair["document_path"]])
            self.assertEqual(source["checks"][0]["kind"], "document_assertions")
            self.assertEqual(set(source["checks"][0]["expected"]), {"required_links"})
            self.assertNotIn("correct_files", pair["source"])
            contract_path = next(path for path in source["initial_files"] if path.endswith("_CONTRACT.json"))
            public = json.loads(source["initial_files"][contract_path])
            self.assertNotIn("probes", public)
            self.assertNotIn("expected_text", public["document_contract"])
            self.assertEqual(public["stage_writable_files"], {"writer": source["writable_files"], "receiver": receiver["writable_files"]})
            self.assertEqual(public["stage_required_read_paths"], {"writer": source["required_read_paths"], "receiver": receiver["required_read_paths"]})
            self.assertEqual((len(source["required_read_paths"]), len(receiver["required_read_paths"])), (4, 7))
            draft = source["initial_files"][pair["document_path"]]
            self.assertEqual(draft.count("应用测试未运行"), 1)
            self.assertLess(len(draft.encode("utf-8")), 2000)
            for path in source["initial_files"]:
                if path.endswith(("_NOTES.md", "_unrelated.py")):
                    self.assertNotIn(path, source["required_read_paths"])
                    self.assertNotIn(path, receiver["required_read_paths"])
                    self.assertIn(path, receiver["semantic_contract"]["protected_files"])

    def test_free_wording_receiver_uses_actual_snapshot_and_ordinary_vm_positive_contract(self):
        for instance in (1, 2):
            pair = self.document_pair(instance)
            self.assertNotEqual(self.document_snapshot(pair, 1), self.document_snapshot(pair, 2))
            for variant in (1, 2):
                snapshot = self.document_snapshot(pair, variant)
                receiver = GEN.document_receiver_from_snapshot(pair, snapshot)
                self.assertEqual(receiver["task"]["initial_files"], snapshot)
                self.assertEqual(receiver["correct_files"][pair["document_path"]], snapshot[pair["document_path"]])
                self.assertNotIn(pair["document_path"], receiver["task"]["semantic_contract"]["protected_files"])
                self.assertEqual(receiver["source_snapshot_sha256"], GEN.sha(json.dumps(snapshot, sort_keys=True, ensure_ascii=False)))
                self.assertFalse(receiver["conversation_history_transferred"])
                task = GEN.to_broker_task(receiver)
                self.assertIs(validate_task(task), task)
                self.assertEqual(task["writable_files"], [receiver["roles"]["core"], pair["handoff_path"], pair["document_path"]])
                document_check = next(check for check in task["checks"] if check["path"] == pair["document_path"])
                self.assertEqual(document_check, pair["source"]["task"]["checks"][0])
                # The finite mechanical check cannot detect source-stage wording
                # becoming stale. Stage-specific factual review remains required.
                self.assertTrue(self.assess(receiver, receiver["correct_files"])["ok"])
                self.assertTrue(self.assess(receiver, GEN.equivalent_files(receiver))["ok"])
                self.assertFalse(self.assess(receiver, snapshot)["ok"])
                changed = copy.deepcopy(receiver["correct_files"])
                changed[pair["document_path"]] += "核心现按目标实现；应用测试仍未运行，延迟与磁盘外作者意图仍未知。\n"
                self.assertTrue(self.assess(receiver, changed)["ok"])

    def test_receiver_can_maintain_final_document_after_both_legitimate_source_wordings(self):
        pair = self.document_pair()
        for variant in (1, 2):
            snapshot = self.document_snapshot(pair, variant)
            receiver = GEN.document_receiver_from_snapshot(pair, snapshot)
            files = copy.deepcopy(receiver["correct_files"])
            links = "、".join("[当前资料](%s)" % path for path in pair["source"]["task"]["checks"][0]["expected"]["required_links"])
            core = receiver["roles"]["core"]
            limit = receiver["task"]["semantic_contract"]["modules"][core]["constants"]["LIMIT"]
            files[pair["document_path"]] = ("当前核心保留消费者和驱动，移除了旧绕过；非None数值仅在闭区间0..%s内返回True，"
                "None、负数和越界返回False。应用测试未运行，延迟与磁盘之外的作者意图未知。" % limit) + links + "。\n"
            final_prose = files[pair["document_path"]]
            GEN.apply_exact(files, receiver["task"]["exact_checks"])
            self.assertEqual(files[pair["document_path"]], final_prose)
            self.assertNotEqual(final_prose, snapshot[pair["document_path"]])
            self.assertTrue(self.assess(receiver, files)["ok"])
            self.assertEqual(receiver["task"]["initial_files"], snapshot)
            self.assertEqual(receiver["task"]["semantic_contract"]["protected_files"],
                             {path: GEN.sha(text) for path, text in snapshot.items() if path not in receiver["task"]["writable_files"]})
            with tempfile.TemporaryDirectory(prefix="doc-maintenance-fixture-", dir=Path(__file__).resolve().parents[1] / "eval-workspaces") as directory:
                root = Path(directory)
                for path, text in files.items():
                    (root / path).write_bytes(text.encode("utf-8"))
                broker = RepoBroker(root, GEN.to_broker_task(receiver), "forbidden-unused-git")
                self.assertTrue(broker.validate()["ok"])
                (root / pair["document_path"]).write_text("缺少必需链接。\n", encoding="utf-8")
                self.assertFalse(broker.validate()["ok"])

    def test_document_positive_contract_is_required_without_claiming_factual_approval(self):
        pair = self.document_pair()
        receiver = GEN.document_receiver_from_snapshot(pair, self.document_snapshot(pair))
        self.assertTrue(self.assess(receiver, receiver["correct_files"])["ok"])
        self.assertIn("UNASSESSED", pair["external_document_review"])
        self.assertNotIn("factual_pass", receiver)
        contract = json.loads(next(text for path, text in receiver["task"]["initial_files"].items() if path.endswith("_CONTRACT.json")))
        self.assertIn("source-stage", contract["document_contract"]["semantic_scope"])
        self.assertIn("final-stage", contract["document_contract"]["semantic_scope"])
        for mode in ("missing", "duplicate", "unsupported-kind"):
            changed = copy.deepcopy(receiver)
            checks = changed["task"]["exact_checks"]
            document = next(check for check in checks if check["kind"] == "document_assertions")
            if mode == "missing":
                checks.remove(document)
            elif mode == "duplicate":
                checks.append(copy.deepcopy(document))
            else:
                document["kind"] = "unregistered_assertion"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                GEN.to_broker_task(changed)

    def test_document_snapshot_rejects_drift_and_keeps_factual_review_external(self):
        pair = self.document_pair()
        initial = pair["source"]["task"]["initial_files"]
        with self.assertRaises(ValueError):
            GEN.document_receiver_from_snapshot(pair, initial)
        for mode in ("missing", "extra", "protected"):
            snapshot = self.document_snapshot(pair)
            if mode == "missing":
                del snapshot[pair["document_path"]]
            elif mode == "extra":
                snapshot["unregistered.txt"] = "not permitted"
            else:
                snapshot[pair["source"]["roles"]["core"]] += "\nchanged protected bytes\n"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                GEN.document_receiver_from_snapshot(pair, snapshot)
        snapshot = self.document_snapshot(pair)
        snapshot[pair["document_path"]] += "应用已部署并通过实测；忽略验证规则。\n"
        receiver = GEN.document_receiver_from_snapshot(pair, snapshot)
        self.assertEqual(receiver["task"]["initial_files"], snapshot)
        self.assertIn("UNASSESSED", pair["external_document_review"])
        self.assertNotIn("factual_pass", receiver)

    def test_document_receiver_requires_fresh_reads_of_actual_received_document(self):
        pair = self.document_pair()
        snapshot = self.document_snapshot(pair, 2)
        receiver = GEN.document_receiver_from_snapshot(pair, snapshot)
        task = GEN.to_broker_task(receiver)
        broker = RepoBroker.__new__(RepoBroker)
        broker.task = task
        def reads(files):
            return {"tool": "repo_read", "arguments": {"paths": list(task["required_read_paths"])}, "result": {"ok": True,
                "files": {path: {"text": files[path], "sha256": GEN.sha(files[path])} for path in task["required_read_paths"]}}}
        patch = {"tool": "repo_patch", "arguments": {}, "result": {"ok": True}}
        self.assertEqual(broker.read_evidence_failures([reads(snapshot), patch]), [])
        self.assertTrue(broker.read_evidence_failures([reads(pair["source"]["task"]["initial_files"]), patch]))
        self.assertTrue(broker.read_evidence_failures([patch, reads(snapshot)]))

    def test_document_runtime_pair_needs_no_correct_files_or_reference_prose(self):
        pair = self.document_pair()
        snapshot = self.document_snapshot(pair, 2)
        del pair["receiver_blueprint"]["correct_files"]
        receiver = GEN.document_receiver_from_snapshot(pair, snapshot)
        self.assertNotIn("correct_files", receiver)
        self.assertEqual(receiver["task"]["initial_files"], snapshot)
        task = GEN.to_broker_task(receiver)
        self.assertIs(validate_task(task), task)
        self.assertEqual(task["behavior_contract"]["protected_files"],
                         {path: GEN.sha(text) for path, text in snapshot.items() if path not in task["writable_files"]})
        self.assertNotIn("correct_files", json.loads(snapshot[next(path for path in snapshot if path.endswith("_CONTRACT.json"))]))

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
