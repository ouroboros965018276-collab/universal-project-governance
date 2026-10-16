"""Pure finite-backend admission/host-oracle tests; no Docker or submitted exec."""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

if sys.version_info < (3, 10):
    raise unittest.SkipTest("Finite CPython backend requires Python 3.10+")

from evolution import isolated_python as isolated, semantic_contract as vm
from evolution.tool_broker import RepoBroker, canonical, sha, tool_definitions
from evolution.tool_campaign import build_prompt

ROOT = Path(__file__).resolve().parents[1]
CID = "a" * 64
CORE = "def transform(value):\n    if value is None:\n        raise TypeError\n    if value < 0:\n        raise ValueError\n    return value + 1\n"
CONSUMER = "from core import transform\n\ndef run(value):\n    return transform(value)\n"
ROWS = [{"kind": "return", "value": 7}, {"kind": "return", "value": 3},
        {"kind": "raises", "exception": "ValueError"}, {"kind": "raises", "exception": "TypeError"}]


def task_fixture():
    files = {"core.py": CORE, "consumer.py": CONSUMER, "README.md": "Public facts remain limited.\r\n"}
    signature = {"params": ["value"]}
    contract = {"schema_version": 1, "modules": {
        "core.py": {"required_functions": {"transform": signature}},
        "consumer.py": {"required_functions": {"run": signature},
                        "required_imports": {"transform": {"path": "core.py", "name": "transform"}},
                        "required_calls": {"run": [{"path": "core.py", "function": "transform"}]}},
    }, "protected_files": {"README.md": sha(files["README.md"].encode())}, "probes": [
        {"path": "consumer.py", "function": "run", "args": [6], "expect": {"return": 7}},
        {"path": "consumer.py", "function": "run", "kwargs": {"value": 2}, "expect": {"return": 3}},
        {"path": "consumer.py", "function": "run", "args": [-1], "expect": {"raises": "ValueError"}},
        {"path": "consumer.py", "function": "run", "args": [None], "expect": {"raises": "TypeError"}},
    ]}
    return {"id": "public-isolated-fixture", "family": "public-finite-chain", "prompt": "Repair the registered finite functions.",
            "initial_files": files, "writable_files": ["core.py", "consumer.py"], "behavior_contract": contract,
            "checks": [{"path": p, "kind": "python_behavior", "expected": None} for p in ("core.py", "consumer.py")]}


class FakeDocker:
    """Real host bridge/primitive, only the subprocess capture is replaced."""
    def __init__(self, rows=None, mode=None):
        self.rows, self.mode = deepcopy(ROWS if rows is None else rows), mode
        self.calls, self.removed, self.create, self.runner = [], False, None, None

    def response(self, stdout=b"", stderr=b"", code=0, status="completed"):
        return {"status": status, "exit_code": code, "stdout": stdout, "stderr": stderr,
                "observed_bytes": len(stdout) + len(stderr), "output_complete": status == "completed", "wall_seconds": .001}

    def inspection(self):
        args = self.create
        owner = args[args.index("--name") + 1]
        mounts = []
        for i, arg in enumerate(args):
            if arg == "--mount":
                fields = dict(piece.split("=", 1) if "=" in piece else (piece, True) for piece in args[i + 1].split(","))
                mounts.append({"Type": "bind", "Source": fields["source"], "Destination": fields["target"], "RW": False})
        host = {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False, "Memory": 536870912,
                "MemorySwap": 536870912, "NanoCpus": 1000000000, "PidsLimit": 64, "Init": True,
                "CgroupnsMode": "private", "IpcMode": "private", "CapDrop": ["ALL"], "CapAdd": None,
                "SecurityOpt": ["no-new-privileges=true"], "PidMode": "", "PortBindings": {}, "Devices": [],
                "DeviceRequests": [], "RestartPolicy": {"Name": "no"},
                "Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=32m,uid=65534,gid=65534"}}
        return {"Id": CID, "Name": "/" + owner, "Image": isolated.IMAGE.split("@")[1], "HostConfig": host,
                "Path": "/usr/bin/env", "Args": ["-i", "LC_ALL=C.UTF-8", "/usr/local/bin/python", "-I", "-B", "/runner/runner.py"],
                "Config": {"Image": isolated.IMAGE, "Labels": {"upg.executor.owner": owner}, "User": "65534:65534",
                           "WorkingDir": "/tmp", "Volumes": None,
                           "Env": ["PATH=/usr/local/bin"] + [name + "=" for name in isolated.PROXY_NAMES]},
                "Mounts": mounts, "State": {"Running": False, "ExitCode": 0}}

    def __call__(self, argv, deadline):
        self.calls.append(argv)
        args = argv[1:]
        if args[:2] == ["image", "inspect"]:
            if self.mode == "known-image-failure":
                return self.response(stderr=b"synthetic image unavailable", code=1)
            image = {"Id": isolated.IMAGE.split("@")[1], "Os": "linux", "Architecture": "amd64",
                     "Descriptor": {"digest": isolated.IMAGE.split("@")[1]}, "RepoDigests": ["python@" + isolated.IMAGE.split("@")[1]],
                     "Config": {"Env": ["PATH=/usr/local/bin"]}}
            return self.response(canonical([image]))
        if args[0] == "create":
            self.create = args
            for i, arg in enumerate(args):
                if arg == "--mount" and ",target=/runner," in args[i + 1]:
                    self.runner = Path(args[i + 1].split("source=", 1)[1].split(",target=", 1)[0])
            return self.response((CID + "\n").encode())
        if args[:2] == ["container", "inspect"]:
            if self.removed:
                if self.mode == "cleanup-unknown":
                    return self.response(stderr=b"cannot connect Docker daemon", code=1)
                return self.response(b"[]\n", ("Error response from daemon: No such container: " + CID + "\n").encode(), 1)
            inspected = self.inspection()
            if self.mode == "sensitive-inspect":
                inspected["unneeded_debug"] = "sk-synthetic-inspect-secret-12345"
            return self.response(canonical([inspected]))
        if args[:2] == ["container", "start"]:
            return self.response((CID + "\n").encode())
        if args[:2] == ["container", "wait"]:
            return self.response(code=None, status="timeout") if self.mode == "timeout" else self.response(b"0\n")
        if args[:2] == ["container", "logs"]:
            raw = (self.runner / "input.json").read_bytes()
            inp = json.loads(raw)
            rows = [row | {"id": call["id"]} for row, call in zip(self.rows, inp["invocations"])]
            out = {"schema_version": 1, "snapshot_sha256": inp["snapshot_sha256"], "input_sha256": sha(raw),
                   "runner_sha256": sha((self.runner / "runner.py").read_bytes()), "results": rows}
            return self.response(canonical(out))
        if args[:2] == ["container", "rm"]:
            self.removed = True
            return self.response((CID + "\n").encode())
        raise AssertionError("unregistered synthetic Docker command")


class IsolatedPythonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="isolated-python-pure-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.task = task_fixture()
        self.write_files(self.task["initial_files"])
        self.artifacts = self.base / "execution"

    def write_files(self, files):
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))

    def broker(self, **kwargs):
        return RepoBroker(self.root, self.task, "unused-git", execution_backend=isolated.EXECUTION_BACKEND,
                          execution_artifacts=self.artifacts, deadline=time.time() + 60, **kwargs)

    def validate_fake(self, broker=None, *, rows=None, mode=None):
        fake = FakeDocker(rows, mode)
        with patch.object(isolated, "_capture", fake), patch.object(subprocess, "Popen", side_effect=AssertionError("real process forbidden")):
            result = (self.broker() if broker is None else broker).call("repo_validate", {})
        return result, fake

    def test_import_has_no_process_and_supported_grammar(self):
        with patch.object(subprocess, "Popen", side_effect=AssertionError("import must be inert")):
            spec = importlib.util.spec_from_file_location("inert_isolated", isolated.__file__)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        ast.parse(Path(isolated.__file__).read_text(encoding="utf-8"), feature_version=(3, 10))
        ast.parse(isolated.RUNNER, feature_version=(3, 10))

    def test_default_payload_and_result_are_unchanged(self):
        broker = RepoBroker(self.root, self.task, "unused-git")
        with patch.object(isolated, "execute_batch", side_effect=AssertionError("default must not execute")):
            self.assertEqual(broker.validate(), {"ok": True, "suite": "registered-static-contracts-v1", "checks_passed": 2,
                             "checks_total": 2, "failures": [], "diagnostics": []})
        self.assertEqual(tool_definitions(), tool_definitions(execution_backend=None))
        self.assertEqual(build_prompt("Skill", {}, "task"), build_prompt("Skill", {}, "task", execution_backend=None))

    def test_opt_in_changes_only_validate_capability_and_prompt(self):
        old, new = tool_definitions(), tool_definitions(execution_backend=isolated.EXECUTION_BACKEND)
        self.assertEqual(len(new), 5)
        for before, after in zip(old, new):
            if before["name"] == "repo_validate":
                self.assertEqual({k: v for k, v in before.items() if k != "description"}, {k: v for k, v in after.items() if k != "description"})
                self.assertIn("isolated CPython", after["description"])
            else:
                self.assertEqual(before, after)
        default = build_prompt("Skill", {}, "task", terminal_report="native-tool")
        explicit = build_prompt("Skill", {}, "task", terminal_report="native-tool", execution_backend=isolated.EXECUTION_BACKEND)
        self.assertEqual(default.split("<governance_skill>", 1)[1], explicit.split("<governance_skill>", 1)[1])
        self.assertIn("host exact-type", explicit)
        self.assertNotIn("cannot execute application code", explicit)
        for mode in (False, [], "docker", "", 1):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                tool_definitions(execution_backend=mode)
            with self.subTest(prompt_mode=mode), self.assertRaises(ValueError):
                build_prompt("", {}, "", execution_backend=mode)

    def test_real_broker_bridge_primitive_with_only_capture_mocked(self):
        broker = self.broker()
        with patch.object(vm, "validate_behavior", wraps=vm.validate_behavior) as observed:
            result, fake = self.validate_fake(broker)
        self.assertTrue(result["ok"])
        self.assertEqual(observed.call_count, 1)
        self.assertEqual(result["suite"], isolated.EXECUTION_SUITE)
        execution = result["execution"]
        self.assertEqual(set(execution), isolated.EXECUTION_SUMMARY_FIELDS)
        self.assertEqual(execution["status"], "EXECUTED")
        self.assertFalse(execution["unknown"])
        self.assertTrue(execution["container_removed"])
        self.assertEqual(execution["received_snapshot_sha256"], broker.events[-1]["state_sha256"])
        receipt = self.artifacts / execution["receipt_ref"]
        self.assertEqual(execution["receipt_sha256"], sha(receipt.read_bytes()))
        inp = json.loads((receipt.parent / "input.frozen.json").read_bytes())
        self.assertTrue(all(set(call) == {"id", "path", "function", "args", "kwargs"} for call in inp["invocations"]))
        self.assertNotIn("expect", json.dumps(inp))
        self.assertNotIn("probes", json.dumps(inp))
        self.assertNotIn("results", json.dumps(execution))
        self.assertEqual(sum(argv[1] == "create" for argv in fake.calls), 1)

    def test_vm_failure_never_invokes_primitive_or_creates_validation_receipt(self):
        (self.root / "core.py").write_text("def transform(value):\n    return 999\n", encoding="utf-8")
        broker = self.broker()
        with patch.object(isolated, "execute_batch", side_effect=AssertionError("VMFAIL cannot execute")):
            result = broker.validate()
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution"]["status"], "NOT_RUN_VM_FAILED")
        self.assertFalse(result["execution"]["unknown"])
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertTrue(all(item["code"] in {"return-mismatch", "exception-mismatch"} for item in result["diagnostics"]))

    def test_required_call_result_dependency_gate_is_not_replaced(self):
        (self.root / "consumer.py").write_text("from core import transform\ndef run(value):\n    ignored = transform(value)\n    return value + 1\n", encoding="utf-8")
        broker = self.broker()
        with patch.object(isolated, "execute_batch", side_effect=AssertionError("data-flow failure cannot execute")):
            result = broker.validate()
        self.assertFalse(result["ok"])
        self.assertIn("required-call-not-in-result", {d["code"] for d in result["diagnostics"]})
        self.assertEqual(result["execution"]["status"], "NOT_RUN_VM_FAILED")

    def test_host_same_distinguishes_bool_and_int(self):
        for wanted, actual in ((True, 1), (1, True)):
            with self.subTest(wanted=wanted, actual=actual):
                files = {"core.py": "def transform(value):\n    return " + repr(wanted) + "\n"}
                contract = {"schema_version": 1, "modules": {"core.py": {"required_functions": {"transform": {"params": ["value"]}}}},
                            "probes": [{"path": "core.py", "function": "transform", "args": [0], "expect": {"return": wanted}}]}
                path = self.base / ("bool-case-" + str(type(wanted).__name__))
                with patch.object(isolated, "_capture", FakeDocker([{"kind": "return", "value": actual}])):
                    behavior, execution = isolated.validate_with_execution(files, contract, path, 30)
                self.assertFalse(behavior["ok"])
                self.assertEqual(execution["status"], "EXECUTED")
                self.assertFalse(execution["unknown"])

    def test_known_host_mismatch_keeps_safe_generic_diagnostics(self):
        rows = deepcopy(ROWS)
        rows[2] = {"kind": "raises", "exception": "TypeError"}
        result, _ = self.validate_fake(rows=rows)
        self.assertFalse(result["ok"])
        self.assertEqual(result["checks_passed"], 0)
        self.assertEqual(result["execution"]["status"], "EXECUTED")
        self.assertEqual(result["diagnostics"], [{"code": "behavior-contract-failed", "path": "consumer.py"},
                                                {"code": "behavior-contract-failed", "path": "core.py"}])
        self.assertEqual(result["failures"], ["contract-failed:core.py:ValueError", "contract-failed:consumer.py:ValueError"])

    def test_timeout_or_unconfirmed_cleanup_is_infrastructure_failure_and_no_retry(self):
        for mode in ("timeout", "cleanup-unknown"):
            with self.subTest(mode=mode):
                self.artifacts = self.base / mode
                broker = self.broker()
                result, fake = self.validate_fake(broker, mode=mode)
                self.assertFalse(result["ok"])
                self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")
                self.assertTrue(result["execution"]["unknown"])
                with patch.object(isolated, "execute_batch", side_effect=AssertionError("unknown must not retry")):
                    self.assertEqual(broker.validate(), result)
                self.assertEqual(sum(argv[1] == "create" for argv in fake.calls), 1)

    def test_no_python_is_not_applicable_without_dummy_receipt(self):
        self.task = {"id": "public-doc", "family": "doc", "prompt": "fixed text", "initial_files": {"note.txt": "ready"},
                     "writable_files": ["note.txt"], "checks": [{"path": "note.txt", "kind": "text", "expected": "ready"}]}
        for path in self.root.iterdir():
            path.unlink()
        self.write_files(self.task["initial_files"])
        broker = self.broker()
        with patch.object(isolated, "execute_batch", side_effect=AssertionError("no Python")):
            result = broker.validate()
        self.assertTrue(result["ok"])
        execution = result["execution"]
        self.assertEqual(execution["status"], "NOT_APPLICABLE")
        self.assertEqual(execution["probe_count"], 0)
        for key in ("runner_sha256", "input_sha256", "output_sha256", "receipt_ref", "receipt_sha256", "container_removed"):
            self.assertIsNone(execution[key])
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_new_absolute_outside_artifact_fence_and_deadline_are_required(self):
        for artifacts in (None, "relative", self.root / "bad", self.base, self.base / "missing" / "child"):
            with self.subTest(artifacts=artifacts), self.assertRaises(ValueError):
                RepoBroker(self.root, self.task, "unused", execution_backend=isolated.EXECUTION_BACKEND,
                           execution_artifacts=artifacts, deadline=time.time() + 60)
        for deadline in (None, False, float("nan"), float("inf"), time.time() - 1):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                RepoBroker(self.root, self.task, "unused", execution_backend=isolated.EXECUTION_BACKEND,
                           execution_artifacts=self.artifacts, deadline=deadline)
        self.broker()
        with self.assertRaises(ValueError):
            self.broker()
        with self.assertRaises(ValueError):
            RepoBroker(self.root, self.task, "unused", execution_artifacts=self.base / "orphan")

    def test_validation_directories_and_receipts_are_exclusive(self):
        broker = self.broker()
        first, _ = self.validate_fake(broker)
        receipt = self.artifacts / first["execution"]["receipt_ref"]
        original = receipt.read_bytes()
        second, _ = self.validate_fake(broker)
        self.assertTrue(second["ok"])
        self.assertNotEqual(first["execution"]["receipt_ref"], second["execution"]["receipt_ref"])
        self.assertEqual(receipt.read_bytes(), original)

    def test_existing_validation_directory_is_not_reused(self):
        broker = self.broker()
        target = self.artifacts / "validation-001"
        target.mkdir()
        (target / "sentinel").write_bytes(b"preserve")
        with patch.object(isolated, "_capture", side_effect=AssertionError("existing artifact must not dispatch")):
            result = broker.validate()
        self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")
        self.assertEqual((target / "sentinel").read_bytes(), b"preserve")

    def test_receipt_or_output_tamper_never_passes(self):
        primitive = isolated.execute_batch
        for mode in ("raw-result", "output", "missing-receipt"):
            with self.subTest(mode=mode):
                self.artifacts = self.base / mode
                broker = self.broker()
                def tamper(files, invocations, path, remaining):
                    result = primitive(files, invocations, path, remaining)
                    if mode == "raw-result":
                        (path / "result.json").write_bytes(canonical(result | {"extra": True}))
                    elif mode == "output":
                        (path / "06-logs.stdout.raw").write_bytes(b"{}")
                    else:
                        (path / "result.json").unlink()
                    return result
                with patch.object(isolated, "execute_batch", tamper), patch.object(isolated, "_capture", FakeDocker()):
                    result = broker.validate()
                self.assertFalse(result["ok"])
                self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")
                self.assertTrue(result["execution"]["unknown"])

    def test_result_fsync_crossing_total_cannot_trust_older_disk_executed(self):
        clock = [0.]
        path = self.base / "fsync-boundary"
        def fsync(fd):
            if (path / "result.json").exists():
                clock[0] = 30.001
        with patch.object(isolated.time, "monotonic", lambda: clock[0]), patch.object(isolated.os, "fsync", fsync), patch.object(isolated, "_capture", FakeDocker()):
            behavior, execution = isolated.validate_with_execution(self.task["initial_files"], self.task["behavior_contract"], path, 30)
        raw = (path / "result.json").read_bytes()
        self.assertEqual(json.loads(raw)["status"], "EXECUTED")
        self.assertFalse(behavior["ok"])
        self.assertEqual(execution["status"], "INFRASTRUCTURE_FAILED")
        self.assertTrue(execution["unknown"])
        self.assertEqual(execution["receipt_sha256"], sha(raw))
        self.assertEqual((path / "result.json").read_bytes(), raw)

    def test_snapshot_drift_or_protected_change_blocks_execution_evidence(self):
        broker = self.broker()
        primitive = isolated.execute_batch
        def mutate(files, invocations, path, remaining):
            record = primitive(files, invocations, path, remaining)
            (self.root / "core.py").write_text("changed", encoding="utf-8")
            return record
        with patch.object(isolated, "execute_batch", mutate), patch.object(isolated, "_capture", FakeDocker()):
            result = broker.validate()
        self.assertFalse(result["ok"])
        self.assertTrue(result["execution"]["unknown"])
        self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")

    def test_non_python_check_failure_is_not_misclassified_as_infrastructure(self):
        self.task["initial_files"]["note.txt"] = "pending"
        self.task["writable_files"].insert(0, "note.txt")
        self.task["checks"].insert(0, {"path": "note.txt", "kind": "text", "expected": "ready"})
        self.write_files(self.task["initial_files"])
        result, _ = self.validate_fake()
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution"]["status"], "EXECUTED")
        self.assertFalse(result["execution"]["unknown"])

    def test_protected_bytes_or_vm_source_drift_never_dispatches(self):
        broker = self.broker()
        (self.root / "README.md").write_bytes(b"changed protected facts")
        with patch.object(isolated, "execute_batch", side_effect=AssertionError("protected drift cannot execute")):
            result = broker.validate()
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")
        self.assertTrue(result["execution"]["unknown"])
        self.write_files(self.task["initial_files"])
        self.artifacts = self.base / "vm-drift"
        with patch.object(isolated, "VM_SHA256", "0" * 64), patch.object(isolated, "execute_batch", side_effect=AssertionError("VM identity drift cannot execute")):
            result = self.broker().validate()
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")

    def test_expired_remaining_budget_cannot_start_container(self):
        broker = self.broker()
        broker.deadline = time.time() - 1
        with patch.object(isolated, "_capture", side_effect=AssertionError("expired execution cannot dispatch")):
            result = broker.validate()
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")
        self.assertTrue(result["execution"]["unknown"])

    def test_known_infrastructure_failure_preserves_observed_no_create_certainty(self):
        result, fake = self.validate_fake(mode="known-image-failure")
        execution = result["execution"]
        self.assertFalse(result["ok"])
        self.assertEqual(execution["status"], "INFRASTRUCTURE_FAILED")
        self.assertFalse(execution["unknown"])
        self.assertFalse(execution["container_removed"])
        self.assertFalse(any(argv[1] == "create" for argv in fake.calls))
        raw = (self.artifacts / execution["receipt_ref"]).read_bytes()
        self.assertEqual(execution["receipt_sha256"], sha(raw))
        self.assertFalse(json.loads(raw)["unknown"])

    def test_all_inspect_stdout_stderr_are_raw_hash_bound_including_absence(self):
        result, fake = self.validate_fake()
        self.assertTrue(result["ok"])
        directory = (self.artifacts / result["execution"]["receipt_ref"]).parent
        receipts = list(directory.glob("*.receipt.json"))
        inspected = []
        for path in receipts:
            record = json.loads(path.read_bytes())
            if record["argv"][1:3] != ["container", "inspect"]:
                continue
            inspected.append(path)
            prefix = path.name.removesuffix(".receipt.json")
            for stream in ("stdout", "stderr"):
                raw = (directory / (prefix + "." + stream + ".raw")).read_bytes()
                self.assertEqual(sha(raw), record[stream + "_sha256"])
            if record["exit_code"] == 0:
                parsed = json.loads((directory / (prefix + ".stdout.raw")).read_bytes())
                self.assertEqual(parsed[0]["Id"], CID)
                self.assertEqual(parsed[0]["HostConfig"]["NetworkMode"], "none")
                for phase in ("before", "after"):
                    if prefix.endswith("inspect-" + phase):
                        self.assertEqual(canonical(parsed[0]), (directory / ("verified-container-" + phase + ".json")).read_bytes())
            else:
                self.assertEqual((directory / (prefix + ".stdout.raw")).read_bytes(), b"[]\n")
                self.assertEqual((directory / (prefix + ".stderr.raw")).read_bytes(),
                                 ("Error response from daemon: No such container: " + CID + "\n").encode())
        self.assertEqual(len(inspected), 4)  # before, after, owned-cleanup, exact absence

    def test_sensitive_inspect_is_not_persisted_or_silently_accepted(self):
        result, fake = self.validate_fake(mode="sensitive-inspect")
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution"]["status"], "INFRASTRUCTURE_FAILED")
        self.assertTrue(result["execution"]["unknown"])
        self.assertFalse(any(argv[1:3] == ["container", "start"] for argv in fake.calls))
        for path in self.artifacts.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"sk-synthetic-inspect-secret-12345", path.read_bytes())
        directory = self.artifacts / "validation-001"
        self.assertTrue((directory / "03-inspect-before.receipt.json").is_file())
        self.assertFalse((directory / "03-inspect-before.stdout.raw").exists())


if __name__ == "__main__":
    unittest.main()
