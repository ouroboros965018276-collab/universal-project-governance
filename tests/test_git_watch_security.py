"""The own-worker launch exception cannot authorize arbitrary process code."""
import ast
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import security_audit as audit

class GitWatchSecurityTests(unittest.TestCase):
    def source(self):
        return (ROOT / "governance-src/runtime-scripts/git_watch.py").read_text(encoding="utf-8")

    def approved(self, source, filename="git_watch.py", function="_spawn_worker"):
        tree = ast.parse(source)
        fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function), None)
        if fn is None:
            return False
        call_name = "lifetime.spawn" if function in {"_spawn_worker", "_spawn_supervisor"} else "subprocess.Popen"
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == call_name]
        self.assertEqual(len(calls), 1)
        return audit.approved_worker_launch(Path(filename), tree, calls[0])

    def test_only_the_reviewed_own_worker_launch_is_approved(self):
        self.assertTrue(self.approved(self.source()))
        self.assertFalse(self.approved(self.source(), "other_helper.py"))

    def test_python_versions_with_or_without_empty_type_parameters_share_identity(self):
        tree = ast.parse(self.source())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_worker")
        call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == "lifetime.spawn")
        fn._fields = tuple(name for name in fn._fields if name != "type_params")
        self.assertTrue(audit.approved_worker_launch(Path("git_watch.py"), tree, call))
        fn._fields += ("type_params",)
        fn.type_params = []
        self.assertTrue(audit.approved_worker_launch(Path("git_watch.py"), tree, call))
        fn.type_params = [ast.Name(id="unexpected_generic_parameter", ctx=ast.Load())]
        self.assertFalse(audit.approved_worker_launch(Path("git_watch.py"), tree, call))

    def test_python38_transparent_index_wrappers_share_reviewed_identity(self):
        source = (ROOT / "governance-src/runtime-scripts/process_guard.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_guarded")
        call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == "subprocess.Popen")
        # _spawn_guarded still has real option subscripts after the worker's
        # native launch moved into the bounded session helper.
        legacy_index_type = type("Index", (ast.AST,), {"_fields": ("value",)})
        for node in list(ast.walk(fn)):
            if isinstance(node, ast.Subscript) and type(node.slice).__name__ != "Index":
                wrapper = legacy_index_type()
                wrapper.value = node.slice
                node.slice = wrapper
        self.assertTrue(audit.approved_worker_launch(Path("process_guard.py"), tree, call))

    def test_replacing_fixed_interpreter_with_arbitrary_command_is_rejected(self):
        source = self.source().replace("argv = [sys.executable,", 'argv = ["untrusted-program",', 1)
        self.assertFalse(self.approved(source))

    def test_guarded_native_launch_is_fixed_to_reviewed_wrapper(self):
        source = (ROOT / "governance-src/runtime-scripts/process_guard.py").read_text(encoding="utf-8")
        self.assertTrue(self.approved(source, "process_guard.py", "_spawn_guarded"))
        self.assertFalse(self.approved(source, "git_watch.py", "_spawn_guarded"))
        changed = source.replace('options["shell"] = False', 'options["shell"] = True', 1)
        self.assertFalse(self.approved(changed, "process_guard.py", "_spawn_guarded"))
        moved = source.replace("def _spawn_guarded(argv, guards, kwargs):", "def unknown_launch(argv, guards, kwargs):", 1)
        self.assertFalse(self.approved(moved, "process_guard.py", "_spawn_guarded"))

    def test_bounded_git_reader_requires_reviewed_fixed_query_caller(self):
        source = (ROOT / "governance-src/runtime-scripts/project_facts.py").read_text(encoding="utf-8")
        self.assertTrue(self.approved(source, "project_facts.py", "_bounded_git_query"))
        self.assertFalse(self.approved(source, "other_helper.py", "_bounded_git_query"))
        for old, new in [('subprocess.Popen(command, **options)', 'subprocess.Popen(command, shell=True, **options)'),
                         ('stream.read(output_limit + 1)', 'stream.read()'),
                         ('prefix + arguments', '["untrusted-program"]'),
                         ('timeout=5, output_limit=limit', 'timeout=None, output_limit=limit'),
                         ('def git_state(root, scope, binary, *, reader=None):',
                          'def unreviewed_caller(root, scope, binary, *, reader=None):')]:
            with self.subTest(mutation=old):
                self.assertIn(old, source)
                changed = source.replace(old, new, 1)
                self.assertFalse(self.approved(changed, "project_facts.py", "_bounded_git_query"))

    def test_portable_ast_preserves_byte_literal_type_and_value(self):
        byte_value = ast.parse("def example(): return b'\\x00'").body[0]
        same_value = ast.parse("def example(): return b'\\0'").body[0]
        string_value = ast.parse("def example(): return '\\x00'").body[0]
        other_byte = ast.parse("def example(): return b'\\x01'").body[0]
        self.assertEqual(audit.worker_launch_digest(byte_value), audit.worker_launch_digest(same_value))
        self.assertNotEqual(audit.worker_launch_digest(byte_value), audit.worker_launch_digest(string_value))
        self.assertNotEqual(audit.worker_launch_digest(byte_value), audit.worker_launch_digest(other_byte))

    def test_session_supervisor_uses_only_the_reviewed_own_script(self):
        source = self.source()
        self.assertTrue(self.approved(source, function="_spawn_supervisor"))
        changed = source.replace('"--supervise", str(root)', '"--unreviewed", str(root)', 1)
        self.assertFalse(self.approved(changed, function="_spawn_supervisor"))
        self.assertFalse(self.approved(source, "other_helper.py", "_spawn_supervisor"))

    def test_session_native_spawn_requires_its_exact_reviewed_containment_handshake(self):
        source = (ROOT / "governance-src/runtime-scripts/session_lifetime.py").read_text(encoding="utf-8")
        self.assertTrue(self.approved(source, "session_lifetime.py", "spawn"))
        self.assertFalse(self.approved(source, "other_helper.py", "spawn"))
        for old, new in [('_argv(argv, internal=True)', '_argv(argv, internal=False)'),
                         ('subprocess.Popen(command, shell=False', 'subprocess.Popen(command, shell=True'),
                         ('options["start_new_session"] = True', 'options["start_new_session"] = False')]:
            with self.subTest(mutation=old):
                self.assertIn(old, source)
                self.assertFalse(self.approved(source.replace(old, new, 1), "session_lifetime.py", "spawn"))

    def test_user_host_launch_cannot_inherit_session_authority_or_use_a_shell(self):
        source = (ROOT / "governance-src/runtime-scripts/session_lifetime.py").read_text(encoding="utf-8")
        self.assertTrue(self.approved(source, "session_lifetime.py", "run_host"))
        self.assertFalse(self.approved(source, "other_helper.py", "run_host"))
        # Pin the delegation as well as direct native options. The helper's
        # environment stripping behavior is calibrated separately below.
        prefix, host = source.split("def run_host(", 1)
        for old, new in [('without_session_environment(options.pop("env", None))', 'dict(options.pop("env", {}))'),
                         ('options["close_fds"] = True', 'options["close_fds"] = False'),
                         ('subprocess.Popen(command, shell=False', 'subprocess.Popen(command, shell=True')]:
            with self.subTest(mutation=old):
                self.assertIn(old, host)
                changed = prefix + "def run_host(" + host.replace(old, new, 1)
                self.assertFalse(self.approved(changed, "session_lifetime.py", "run_host"))

    def test_environment_stripping_removes_only_observer_authority_without_mutating_input(self):
        path = ROOT / "governance-src/runtime-scripts/session_lifetime.py"
        spec = importlib.util.spec_from_file_location("security_session_environment", path)
        lifetime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lifetime)
        original = {lifetime._ENV: "private-observer-capability", "PATH": "ordinary-native-path", "OWNER_SETTING": "preserve"}
        before = dict(original)
        self.assertEqual(lifetime.without_session_environment(original),
                         {"PATH": "ordinary-native-path", "OWNER_SETTING": "preserve"})
        self.assertEqual(original, before)
        with mock.patch.dict(os.environ, original, clear=True):
            self.assertEqual(lifetime.without_session_environment(),
                             {"PATH": "ordinary-native-path", "OWNER_SETTING": "preserve"})
            self.assertEqual(dict(os.environ), before)

    def test_own_worker_cannot_bypass_the_session_lifetime_launcher(self):
        changed = self.source().replace("return lifetime.spawn(argv,", "return subprocess.Popen(argv,", 1)
        tree = ast.parse(changed)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_worker")
        call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == "subprocess.Popen")
        self.assertFalse(audit.approved_worker_launch(Path("git_watch.py"), tree, call))

    def test_moving_process_launch_outside_reviewed_function_is_rejected(self):
        source = self.source().replace("def _spawn_worker(root, token, guard):", "def arbitrary_launcher(root, token, guard):", 1)
        self.assertFalse(self.approved(source))

if __name__ == "__main__":
    unittest.main()
