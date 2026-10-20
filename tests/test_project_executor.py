"""Candidate pure/mock tests: no Docker, model, native CLI or submitted Python."""
import ast
import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import sys

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Registered project backend requires Python 3.10+")

from evolution import isolated_python as legacy, project_executor as project

HERE = Path(__file__).resolve().parent


class InitialContractTests(unittest.TestCase):
    def test_new_backend_is_explicit(self):
        self.assertEqual(project.EXECUTION_BACKEND, "docker-cpython-project-v1")
        self.assertEqual(project.EXECUTION_SUITE, "registered-python-project-checks-v1")

    def test_legacy_entry_bytes_unchanged(self):
        self.assertEqual(hashlib.sha256(Path(legacy.__file__).read_bytes()).hexdigest(),
                         "2fc136ffa4bb1ca0a99615c12278df36452257d093d8ec2aa9035a3dd4bf1c8d")


CID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
FILES = {"sample_pkg/__init__.py": "", "sample_pkg/core.py": "from pathlib import Path\ndef total(values):\n    return sum(values)\n",
         "sample_pkg/__main__.py": "from .core import total\nprint(total([2, 3]))\n", "assets/input.txt": "2\n3\n"}
TEST_ID = "registered_tests.TestProject.test_total"
CONTRACT = {"schema_version": 1, "contract_id": "sample-project-v1",
            "trusted_files": {"registered_tests.py": "import unittest\nfrom sample_pkg.core import total\nclass TestProject(unittest.TestCase):\n    def test_total(self):\n        self.assertEqual(total([2, 3]), 5)\n"},
            "checks": [{"id": "unit", "recipe": "unittest", "test_modules": ["registered_tests"], "minimum_tests": 1, "expected_test_ids": [TEST_ID]},
                       {"id": "imports", "recipe": "import", "modules": ["sample_pkg", "sample_pkg.core"]},
                       {"id": "files-cli", "recipe": "module", "module": "sample_pkg.__main__", "args": ["input.txt", "output.txt"],
                        "stdin": "", "input_files": {"input.txt": "2\n3\n"}, "expected_exit": 0, "expected_stdout": "5\n", "expected_stderr": "",
                        "expected_files": {"output.txt": "5\n"}}]}


class FakeDocker:
    """Synthetic observations only; does not execute the project or trusted code."""
    def __init__(self, mode=None):
        self.mode, self.calls, self.create, self.root, self.removed = mode, [], None, None, False
        self.deadlines = []

    def response(self, stdout=b"", stderr=b"", code=0, status="completed"):
        return {"status": status, "exit_code": code, "stdout": stdout, "stderr": stderr,
                "observed_bytes": len(stdout) + len(stderr), "output_complete": status == "completed", "wall_seconds": .001}

    def inspection(self):
        owner = self.create[self.create.index("--name") + 1]
        mounts = []
        for i, arg in enumerate(self.create):
            if arg == "--mount":
                values = dict(p.split("=", 1) if "=" in p else (p, True) for p in self.create[i + 1].split(","))
                mounts.append({"Type": "bind", "Source": values["source"], "Destination": values["target"], "RW": False})
        host = {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False, "Memory": 536870912,
                "MemorySwap": 536870912, "NanoCpus": 1000000000, "PidsLimit": 64, "Init": True,
                "CgroupnsMode": "private", "IpcMode": "private", "CapDrop": ["ALL"], "CapAdd": None,
                "SecurityOpt": ["no-new-privileges=true"], "PidMode": "", "PortBindings": {}, "Devices": [],
                "DeviceRequests": [], "RestartPolicy": {"Name": "no"},
                "Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=32m,uid=65534,gid=65534"}}
        item = {"Id": CID, "Name": "/" + owner, "Image": IMAGE_ID, "HostConfig": host,
                "Path": "/usr/bin/env", "Args": ["-i", "LC_ALL=C.UTF-8", project.PYTHON, "-I", "-B", "/runner/runner.py"],
                "Config": {"Image": project.IMAGE, "Labels": {"upg.executor.owner": owner}, "User": "65534:65534",
                           "WorkingDir": "/tmp", "Volumes": None,
                           "Env": ["PATH=/usr/local/bin"] + [p + "=" for p in project.PROXY_NAMES]},
                "Mounts": mounts, "State": {"Running": False, "ExitCode": 0}}
        if self.mode == "isolation":item["HostConfig"]["NetworkMode"] = "bridge"
        if self.mode == "owner":item["Config"]["Labels"] = {}
        if self.mode == "mount":item["Mounts"][0]["RW"] = True
        if self.mode == "env":item["Config"]["Env"].append("UNREGISTERED_TOKEN=synthetic")
        return item

    def rows(self, inp):
        rows = []
        for check in inp["checks"]:
            if check["recipe"] == "unittest":
                outcome = {"recipe": "unittest", "completed": True, "tests_run": 1, "skipped": 0, "failures": 0, "errors": 0,
                           "expected_failures": 0, "unexpected_successes": 0, "successful": True,
                           "test_ids": [TEST_ID], "executed_test_ids": [TEST_ID]}
                stdout, stderr = b"", b"test_total ... ok\nRan 1 test\nOK\n"
                if self.mode == "assertion":outcome.update(failures=1, successful=False)
                if self.mode == "zero":outcome.update(tests_run=0, test_ids=[], executed_test_ids=[])
                if self.mode == "duplicate":outcome.update(tests_run=2, test_ids=[TEST_ID, TEST_ID], executed_test_ids=[TEST_ID, TEST_ID])
                if self.mode == "dummy":outcome.update(test_ids=["registered_tests.TestProject.test_dummy"], executed_test_ids=["registered_tests.TestProject.test_dummy"])
                if self.mode == "skip":outcome["skipped"] = 1
                if self.mode == "expected-failure":outcome["expected_failures"] = 1
                if self.mode == "unexpected-success":outcome["unexpected_successes"] = 1
                if self.mode == "fakepass":outcome.update(tests_run=0, test_ids=[], executed_test_ids=[]);stdout = b"PASS\n"
            elif check["recipe"] == "import":
                outcome = {"recipe": "import", "completed": True, "modules": {m: "/src/" + inp["source_module_files"][m] for m in check["modules"]}}
                stdout, stderr = b"", b""
            else:
                outcome = {"recipe": "module", "completed": True}
                stdout, stderr = b"5\n", b""
                if self.mode == "wrong-output":stdout = b"PASS\n"
            streams = {}
            for key, raw in (("stdout", stdout), ("stderr", stderr)):
                streams.update({key + "_base64": base64.b64encode(raw).decode(), key + "_sha256": project.sha(raw), key + "_bytes": len(raw)})
            row = {"id": check["id"], "recipe": check["recipe"], "snapshot_sha256": inp["snapshot_sha256"],
                   "argv": [project.PYTHON, "-I", "-B", "/runner/checker.py", check["id"]], "cwd": "/tmp/work/" + check["id"],
                   "env_sha256": project.sha(project.canonical(project.PROCESS_ENV)), "exit_code": 0, "timeout": False, "truncated": False,
                   "observed_bytes": len(stdout) + len(stderr), "outcome": outcome, "output_files": {}, **streams}
            if check["recipe"] == "module":row["output_files"] = {"output.txt": {"sha256": project.sha(b"5\n"), "bytes": 2}}
            if self.mode == "stream-hash":row["stdout_sha256"] = "0" * 64
            if self.mode == "child-timeout":row.update(timeout=True, exit_code=None, outcome=None)
            if self.mode == "child-truncated":row.update(truncated=True, exit_code=None, outcome=None)
            rows.append(row)
        return rows

    def __call__(self, argv, deadline):
        self.calls.append(argv)
        self.deadlines.append(deadline)
        args = argv[1:]
        if args[:2] == ["image", "inspect"]:
            if self.mode == "image-error":return self.response(stderr=b"synthetic image unavailable", code=1)
            digest = project.IMAGE.split("@")[1]
            image = {"Id": IMAGE_ID, "Os": "linux", "Architecture": "amd64", "Descriptor": {"digest": digest},
                     "RepoDigests": ["python@" + digest], "Config": {"Env": ["PATH=/usr/local/bin"]}}
            if self.mode == "image-digest":image["Descriptor"]["digest"] = "sha256:" + "0" * 64
            return self.response(project.canonical([image]))
        if args[0] == "create":
            self.create = args
            for i, arg in enumerate(args):
                if arg == "--mount" and ",target=/runner," in args[i + 1]:
                    self.root = Path(args[i + 1].split("source=", 1)[1].split(",target=", 1)[0]).parent
            if self.mode == "create-timeout":return self.response(status="timeout", code=None)
            if self.mode == "create-id":return self.response(b"unconfirmed\n")
            return self.response((CID + "\n").encode())
        if args[:2] == ["container", "inspect"]:
            if self.removed:
                if self.mode == "cleanup":return self.response(stderr=b"unknown daemon", code=1)
                return self.response(b"[]\n", ("Error response from daemon: No such container: " + CID + "\n").encode(), 1)
            return self.response(project.canonical([self.inspection()]))
        if args[:3] == ["container", "start", "--attach"]:
            if self.mode == "attach-timeout":return self.response(status="timeout", code=None)
            if self.mode == "attach-output-limit":return self.response(status="output-limit", code=None)
            raw = (self.root / "runner" / "input.json").read_bytes()
            inp = project.strict_json(raw)
            payload = {"schema_version": 1, "snapshot_sha256": inp["snapshot_sha256"], "contract_sha256": inp["contract_sha256"],
                       "input_sha256": project.sha(raw), "runner_sha256": project.sha((self.root / "runner" / "runner.py").read_bytes()),
                       "checks": self.rows(inp)}
            if self.mode == "snapshot":payload["snapshot_sha256"] = "0" * 64
            if self.mode == "fake-raw-output":return self.response(b"PASS\n")
            return self.response(project.canonical(payload) + b"\n")
        if args[:2] == ["container", "rm"]:
            self.removed = True
            return self.response((CID + "\n").encode())
        raise AssertionError("unregistered synthetic Docker command")


class ProjectExecutorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rc20-project-pure-", dir=HERE)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.artifacts = self.base / "execution"

    def execute(self, mode=None, files=None, contract=None):
        fake = FakeDocker(mode)
        with patch.object(project, "_capture", fake), patch.object(subprocess, "Popen", side_effect=AssertionError("real process forbidden")), patch.object(legacy, "_profile", side_effect=AssertionError("VM forbidden")):
            receipt = project.execute_project(FILES if files is None else files, CONTRACT if contract is None else contract, self.artifacts, 60)
        return receipt, fake

    def test_import_and_full_python_are_inert(self):
        with patch.object(subprocess, "Popen", side_effect=AssertionError("import process forbidden")):
            new_spec = importlib.util.spec_from_file_location("candidate_inert", Path(project.__file__))
            module = importlib.util.module_from_spec(new_spec);new_spec.loader.exec_module(module)
        for source in (Path(project.__file__).read_text(), project.CHECKER, project.RUNNER):ast.parse(source, feature_version=(3, 10))
        self.assertNotIn("candidate_inert", __import__("sys").modules)

    def test_contract_detached_and_exact(self):
        normalized = project.validate_contract(CONTRACT)
        self.assertEqual(normalized, CONTRACT)
        self.assertIsNot(normalized, CONTRACT)
        normalized["checks"][0]["minimum_tests"] = 2
        self.assertEqual(CONTRACT["checks"][0]["minimum_tests"], 1)

    def test_known_complete_success_and_stderr_allowed(self):
        receipt, fake = self.execute()
        self.assertEqual(receipt["status"], "EXECUTED", receipt)
        outcome, saved, digest = project.read_project_receipt(FILES, CONTRACT, self.artifacts)
        self.assertTrue(outcome["ok"], outcome)
        self.assertTrue(outcome["integrity_ok"])
        self.assertEqual(saved, receipt)
        self.assertEqual(digest, project.sha((self.artifacts / "result.json").read_bytes()))
        self.assertTrue(receipt["container_removed"] and receipt["scratch_removed"])
        self.assertEqual(sum("create" in call for call in fake.calls), 1)
        self.assertEqual(sum("--attach" in call for call in fake.calls), 1)
        self.assertEqual(receipt["checks"][0]["stderr_bytes"], len(b"test_total ... ok\nRan 1 test\nOK\n"))

    def test_known_test_failures_are_distinct_from_integrity_unknown(self):
        for mode in ("assertion", "zero", "duplicate", "dummy", "skip", "expected-failure", "unexpected-success", "fakepass", "wrong-output", "child-timeout", "child-truncated"):
            with self.subTest(mode=mode):
                self.artifacts = self.base / mode
                receipt, _ = self.execute(mode)
                self.assertEqual(receipt["status"], "EXECUTED", receipt)
                result, _, _ = project.read_project_receipt(FILES, CONTRACT, self.artifacts)
                self.assertTrue(result["integrity_ok"], result)
                self.assertFalse(result["ok"], result)

    def test_unknown_lifecycle_result_integrity_and_cleanup_never_replay(self):
        for mode in ("isolation", "owner", "mount", "env", "create-timeout", "create-id", "attach-timeout", "attach-output-limit", "snapshot", "stream-hash", "cleanup", "fake-raw-output"):
            with self.subTest(mode=mode):
                self.artifacts = self.base / mode
                receipt, fake = self.execute(mode)
                self.assertEqual(receipt["status"], "TERMINAL_UNKNOWN", receipt)
                self.assertTrue(receipt["unknown"])
                self.assertFalse(project.validate_receipt(FILES, CONTRACT, receipt)["integrity_ok"])
                self.assertLessEqual(sum("create" in c for c in fake.calls), 1)
                with self.assertRaises(ValueError):project.execute_project(FILES, CONTRACT, self.artifacts, 60)

    def test_pinned_image_failure_has_no_create(self):
        for mode in ("image-error", "image-digest"):
            with self.subTest(mode=mode):
                self.artifacts = self.base / mode
                receipt, fake = self.execute(mode)
                self.assertNotEqual(receipt["status"], "EXECUTED")
                self.assertFalse(receipt["unknown"])
                self.assertEqual(len(fake.calls), 1)

    def test_current_snapshot_contract_and_receipt_binding(self):
        receipt, _ = self.execute()
        changed = dict(FILES);changed["assets/input.txt"] += "stale\n"
        self.assertFalse(project.validate_receipt(changed, CONTRACT, receipt)["integrity_ok"])
        changed_contract = deepcopy(CONTRACT);changed_contract["checks"][-1]["expected_stdout"] = "wrong\n"
        self.assertFalse(project.validate_receipt(FILES, changed_contract, receipt)["integrity_ok"])
        for field, value in (("owner", "different"), ("container_id", "0"), ("container_removed", False), ("scratch_removed", False), ("runner_sha256", "0" * 64), ("input_sha256", "0" * 64), ("output_sha256", "0" * 64), ("command_receipts", [])):
            with self.subTest(field=field):
                mutated = deepcopy(receipt);mutated[field] = value
                self.assertFalse(project.validate_receipt(FILES, CONTRACT, mutated)["integrity_ok"])

    def test_receipt_read_checks_all_raw_bytes(self):
        self.execute()
        path = self.artifacts / "03-inspect-before.stdout.raw"
        path.write_bytes(b"tampered")
        with self.assertRaises(ValueError):project.read_project_receipt(FILES, CONTRACT, self.artifacts)

    def test_valid_json_with_wrong_top_level_shapes_never_escapes_as_attribute_error(self):
        for filename in ("result.json", "output.received.json", "input.frozen.json", "contract.frozen.json", "snapshot.received.json", "03-inspect-before.start.json"):
            for raw in (b"[]", b"1", b"null", b'"text"'):
                with self.subTest(filename=filename, raw=raw):
                    self.artifacts = self.base / (filename.replace(".", "-") + "-" + project.sha(raw)[:8])
                    self.execute()
                    (self.artifacts / filename).write_bytes(raw)
                    with self.assertRaises(ValueError):project.read_project_receipt(FILES, CONTRACT, self.artifacts)

    def test_create_flag_mutation_and_observation_schema_are_integrity_failures(self):
        receipt, _ = self.execute()
        mutated = deepcopy(receipt)
        args = mutated["command_receipts"][1]["argv"]
        args[args.index("--network") + 1] = "bridge"
        self.assertFalse(project.validate_receipt(FILES, CONTRACT, mutated)["integrity_ok"])
        for value in (True, None, [], "1"):
            mutated = deepcopy(receipt);mutated["schema_version"] = value
            self.assertFalse(project.validate_receipt(FILES, CONTRACT, mutated)["integrity_ok"])
        self.assertFalse(project.validate_receipt(FILES, {"checks": None}, receipt)["integrity_ok"])

    def test_final_fsync_crossing_total_is_unknown_despite_older_disk_executed(self):
        clock = [0.]
        fake = FakeDocker()
        def fsync(_):
            if (self.artifacts / "result.json").exists():clock[0] = 30.001
        with patch.object(project.time, "monotonic", lambda: clock[0]), patch.object(project.os, "fsync", fsync), patch.object(project, "_capture", fake), patch.object(subprocess, "Popen", side_effect=AssertionError("no process")):
            behavior, summary = project.validate_with_project_execution(FILES, CONTRACT, self.artifacts, 30)
        self.assertEqual(project.strict_json((self.artifacts / "result.json").read_bytes())["status"], "EXECUTED")
        self.assertFalse(behavior["ok"])
        self.assertFalse(behavior["integrity_ok"])
        self.assertEqual(summary["status"], "TERMINAL_UNKNOWN")
        self.assertTrue(summary["unknown"])
        self.assertEqual(fake.deadlines[:5], [22.] * 5)
        self.assertEqual(fake.deadlines[5:], [30.] * 3)

    def test_full_python_source_admitted_without_finite_vm(self):
        files = deepcopy(FILES)
        files["sample_pkg/core.py"] = "from dataclasses import dataclass\nfrom pathlib import Path\n@dataclass\nclass Record:\n    value: int\ndef total(values):\n    return sum(v for v in values if isinstance(v, int))\n"
        self.assertTrue(project._prepare(files, CONTRACT)["files_sha256"])

    def test_final_scoring_does_not_run(self):
        self.execute()
        with patch.object(project, "_capture", side_effect=AssertionError("final score must never execute")), patch.object(project, "execute_project", side_effect=AssertionError("no reexecution")):
            result, _, _ = project.read_project_receipt(FILES, CONTRACT, self.artifacts)
        self.assertTrue(result["ok"])

    def test_forbidden_paths_source_and_contract_shapes(self):
        for path in ("../escape.py", "/absolute.py", "a\\b.py", "C:/x.py", "a/../x.py", "a//x.py", "CON.py", "a./b.py", "x/" + "a" * 65):
            with self.subTest(path=path), self.assertRaises(ValueError):project._prepare({path: "x=1\n"}, CONTRACT)
        for files in ({"A.py": "x=1", "a.py": "x=2"}, {"a": "x", "a/x.py": "x=1"}, {"empty.py": "\"doc\"\npass\n"}, {"blank.py": "def f():\n    ...\n"}, {"huge.py": "x" * (project.MAX_FILE_BYTES + 1)}):
            with self.subTest(files=list(files)), self.assertRaises(ValueError):project._prepare(files, CONTRACT)
        for modification in (lambda c:c["checks"][0].update(minimum_tests=0), lambda c:c["checks"][0].update(expected_test_ids=[]), lambda c:c["checks"][0].update(expected_test_ids=[TEST_ID, TEST_ID]), lambda c:c["checks"][-1].update(argv=["sh"]), lambda c:c["checks"][-1].update(env={"TOKEN":"synthetic"}), lambda c:c["checks"][-1].update(recipe="shell"), lambda c:c.update(trusted_files={"sample_pkg/tests.py":"pass"})):
            contract = deepcopy(CONTRACT);modification(contract)
            with self.assertRaises((ValueError, TypeError)):project.validate_contract(contract)

    def test_secret_like_source_or_trusted_argument_never_dispatches(self):
        for kind in ("source", "argument"):
            files, contract = deepcopy(FILES), deepcopy(CONTRACT)
            if kind == "source":files["assets/input.txt"] = "sk-synthetic-credential-123456789"
            else:contract["checks"][-1]["args"] = ["sk-synthetic-credential-123456789"]
            self.artifacts = self.base / kind
            receipt, fake = self.execute(files=files, contract=contract)
            self.assertFalse(fake.calls)
            self.assertTrue(receipt["unknown"])

    def test_container_has_only_fixed_env_argv_and_ro_mounts(self):
        receipt, fake = self.execute()
        create = fake.create
        self.assertEqual([create[i + 1] for i, a in enumerate(create) if a == "--env"], [p + "=" for p in project.PROXY_NAMES])
        self.assertEqual(len([a for a in create if a == "--mount"]), 3)
        self.assertIn("never", create)
        inp = project.strict_json((self.artifacts / "input.frozen.json").read_bytes())
        self.assertNotIn("expected_stdout", inp["checks"][-1])
        self.assertNotIn("expected_exit", inp["checks"][-1])
        self.assertNotIn("expected_files", inp["checks"][-1])
        self.assertEqual(set(project.PROCESS_ENV), {"LC_ALL"})

    def test_total_budget_rejects_nonfinite_and_reserved_fence(self):
        for seconds in (0, -1, float("nan"), float("inf"), True, "60"):
            with self.assertRaises(ValueError):project.execute_project(FILES, CONTRACT, self.artifacts, seconds)
        self.assertFalse(self.artifacts.exists())
        receipt, _ = self.execute(files={"../bad": "x"})
        self.assertTrue(receipt["unknown"])
        self.assertTrue((self.artifacts / "result.json").exists())
        with self.assertRaises(ValueError):project.execute_project(FILES, CONTRACT, self.artifacts, 60)

    def test_symlink_or_reparse_parent_is_not_followed(self):
        self.base.joinpath("ordinary").write_bytes(b"x")
        original = Path.lstat
        def synthetic(path):
            info = original(path)
            if path == self.base:
                class Reparse:
                    st_mode = info.st_mode
                    st_file_attributes = 1024
                return Reparse()
            return info
        with patch.object(Path, "lstat", synthetic), self.assertRaises(ValueError):project._safe_new_root(self.artifacts)

    def public_facts(self, *, contract=None, current=None):
        registered = CONTRACT if contract is None else contract
        with patch.object(project, "_read_project_receipt", wraps=project._read_project_receipt) as reader:
            checked, receipt, digest, summary = project.read_project_receipt(
                FILES, registered, self.artifacts, include_public_summary=True)
        self.assertEqual(reader.call_count, 1)
        return project.public_validation_facts(summary, tuple(row["recipe"] for row in registered["checks"]),
            current_snapshot_sha256=receipt["snapshot_sha256"] if current is None else current), summary

    def test_public_validation_separates_checks_from_test_executions_without_leaks(self):
        contract = deepcopy(CONTRACT)
        contract["checks"].insert(1, dict(contract["checks"][0], id="another-unit-recipe"))
        self.execute(contract=contract)
        facts, summary = self.public_facts(contract=contract)
        self.assertEqual(facts["checks"], {"registered": 4, "passed": 4, "failed": 0, "timed_out": 0, "truncated": 0})
        # The same registered test executed by two recipes is two executions,
        # not four checks or two distinct test cases.
        self.assertEqual(facts["unittest"]["counts"]["tests_run"], 2)
        self.assertEqual(facts["current_validation"], "PASSED")
        self.assertEqual(facts["execution"], {"status": "EXECUTED", "unknown": False,
                         "container_removed": True, "scratch_removed": True})
        encoded = project.canonical(facts).decode()
        for secret in (TEST_ID, "another-unit-recipe", "registered_tests", "sample_pkg", "test_ids",
                       "stdout", "stderr", "diagnostics", "expected_stdout", "expected_files"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(len(project.read_project_receipt(FILES, contract, self.artifacts)), 3)

    def test_public_validation_preserves_all_failed_unittest_counts(self):
        original = FakeDocker.rows
        def failing_rows(fake, inp):
            rows = original(fake, inp)
            rows[0]["outcome"].update(tests_run=7, failures=2, errors=1, skipped=1,
                                      expected_failures=1, unexpected_successes=1, successful=False)
            return rows
        with patch.object(FakeDocker, "rows", failing_rows):
            self.execute()
        facts, _ = self.public_facts()
        self.assertEqual(facts["current_validation"], "FAILED")
        self.assertEqual(facts["checks"]["failed"], 1)
        self.assertEqual(facts["unittest"]["counts"], {"tests_run": 7, "failures": 2, "errors": 1,
                         "skipped": 1, "expected_failures": 1, "unexpected_successes": 1})

    def test_public_validation_stale_keeps_historical_counts(self):
        self.execute()
        facts, _ = self.public_facts(current="0" * 64)
        self.assertEqual(facts["current_validation"], "STALE")
        self.assertEqual(facts["observed_validation"], "PASSED")
        self.assertEqual(facts["unittest"]["counts"]["tests_run"], 1)

    def test_public_validation_incomplete_outcome_never_becomes_zero_tests(self):
        self.execute("child-timeout")
        facts, _ = self.public_facts()
        self.assertEqual(facts["current_validation"], "FAILED")
        self.assertEqual(facts["checks"]["timed_out"], 3)
        self.assertEqual(facts["unittest"]["status"], "INCOMPLETE")
        self.assertIsNone(facts["unittest"]["counts"])
        self.assertIsNone(facts["unittest"]["known_counts"])
        self.assertEqual(facts["unittest"]["completed_recipe_count"], 0)

    def test_public_validation_unknown_cleanup_does_not_claim_known_results(self):
        self.execute("cleanup")
        facts, summary = self.public_facts()
        self.assertIs(summary, project.ValidationUnavailable.UNKNOWN)
        self.assertEqual(facts["current_validation"], "UNKNOWN")
        self.assertTrue(facts["execution"]["unknown"])
        self.assertIsNone(facts["execution"]["container_removed"])
        self.assertIsNone(facts["execution"]["scratch_removed"])
        self.assertIsNone(facts["checks"]["passed"])
        self.assertIsNone(facts["unittest"]["counts"])

    def test_public_validation_partial_recipe_coverage_preserves_known_failure_subtotal(self):
        contract = deepcopy(CONTRACT)
        contract["checks"].insert(1, dict(contract["checks"][0], id="another-unit-recipe"))
        original = FakeDocker.rows
        def partial_rows(fake, inp):
            rows = original(fake, inp)
            rows[0]["outcome"].update(failures=1, successful=False)
            rows[1].update(timeout=True, exit_code=None, outcome=None)
            return rows
        with patch.object(FakeDocker, "rows", partial_rows):
            self.execute(contract=contract)
        facts, _ = self.public_facts(contract=contract)
        self.assertEqual(facts["unittest"]["status"], "INCOMPLETE")
        self.assertIsNone(facts["unittest"]["counts"])
        self.assertEqual(facts["unittest"]["known_counts"]["tests_run"], 1)
        self.assertEqual(facts["unittest"]["known_counts"]["failures"], 1)
        self.assertEqual(facts["unittest"]["completed_recipe_count"], 1)

    def test_public_validation_truncated_or_timed_out_rows_cannot_claim_complete_counts(self):
        original = FakeDocker.rows
        for flag in ("timeout", "truncated"):
            self.artifacts = self.base / flag
            def incomplete_rows(fake, inp):
                rows = original(fake, inp)
                rows[0][flag] = True  # Even a complete-looking outcome is insufficient.
                return rows
            with patch.object(FakeDocker, "rows", incomplete_rows):
                self.execute()
            facts, _ = self.public_facts()
            self.assertEqual(facts["unittest"]["status"], "INCOMPLETE")
            self.assertIsNone(facts["unittest"]["counts"])
            self.assertIsNone(facts["unittest"]["known_counts"])

    def test_public_validation_explicit_not_run_differs_from_unknown(self):
        recipes = ("unittest", "module")
        absent = project.public_validation_facts(project.ValidationUnavailable.NOT_RUN, recipes,
                                                 current_snapshot_sha256="0" * 64)
        unknown = project.public_validation_facts(project.ValidationUnavailable.UNKNOWN, recipes,
                                                  current_snapshot_sha256="0" * 64)
        self.assertEqual(absent["current_validation"], "NOT_RUN")
        self.assertFalse(absent["execution"]["unknown"])
        self.assertEqual(unknown["current_validation"], "UNKNOWN")
        self.assertIsNone(absent["unittest"]["counts"])
        no_unit = project.public_validation_facts(project.ValidationUnavailable.UNKNOWN, ("module",),
                                                  current_snapshot_sha256="0" * 64)
        self.assertEqual(no_unit["unittest"]["status"], "NOT_RUN")
        self.assertIsNone(no_unit["unittest"]["counts"])

    def test_public_validation_rejects_producer_dicts_recipe_drift_and_false_types(self):
        self.execute()
        facts, summary = self.public_facts()
        for supplied in ({"ok": True, "tests_run": 999}, bytes(summary), None, True):
            with self.subTest(supplied=type(supplied)), self.assertRaises(ValueError):
                project.public_validation_facts(supplied, ("unittest", "import", "module"), current_snapshot_sha256="0" * 64)
        for recipes in (("unittest",), ("unittest", "module", "import"), ["unittest", "import", "module"], ("private-test-id",)):
            with self.subTest(recipes=recipes), self.assertRaises(ValueError):
                project.public_validation_facts(summary, recipes, current_snapshot_sha256="0" * 64)
        for snapshot in (True, None, "current"):
            with self.assertRaises(ValueError):
                project.public_validation_facts(summary, ("unittest", "import", "module"), current_snapshot_sha256=snapshot)
        with self.assertRaises(ValueError):
            project.read_project_receipt(FILES, CONTRACT, self.artifacts, include_public_summary=1)

    def test_public_validation_original_stream_tamper_rejected_before_projection(self):
        self.execute()
        (self.artifacts / "04-start-attach.stdout.raw").write_bytes(b"producer says all tests passed\n")
        with self.assertRaises(ValueError):
            project.read_project_receipt(FILES, CONTRACT, self.artifacts, include_public_summary=True)


if __name__ == "__main__":
    unittest.main()
