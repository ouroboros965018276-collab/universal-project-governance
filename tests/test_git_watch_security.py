"""The own-worker launch exception cannot authorize arbitrary process code."""
import ast
from pathlib import Path
import sys
import unittest

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
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == "subprocess.Popen"]
        self.assertEqual(len(calls), 1)
        return audit.approved_worker_launch(Path(filename), tree, calls[0])

    def test_only_the_reviewed_own_worker_launch_is_approved(self):
        self.assertTrue(self.approved(self.source()))
        self.assertFalse(self.approved(self.source(), "other_helper.py"))

    def test_python_versions_with_or_without_empty_type_parameters_share_identity(self):
        tree = ast.parse(self.source())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_worker")
        call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == "subprocess.Popen")
        fn._fields = tuple(name for name in fn._fields if name != "type_params")
        self.assertTrue(audit.approved_worker_launch(Path("git_watch.py"), tree, call))
        fn._fields += ("type_params",)
        fn.type_params = []
        self.assertTrue(audit.approved_worker_launch(Path("git_watch.py"), tree, call))
        fn.type_params = [ast.Name(id="unexpected_generic_parameter", ctx=ast.Load())]
        self.assertFalse(audit.approved_worker_launch(Path("git_watch.py"), tree, call))

    def test_python38_transparent_index_wrappers_share_reviewed_identity(self):
        tree = ast.parse(self.source())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_worker")
        call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and audit.dotted(n.func) == "subprocess.Popen")
        # New Python aliases ast.Index to its value; construct the actual old
        # labelled shape to exercise portable identity on every CI interpreter.
        legacy_index_type = type("Index", (ast.AST,), {"_fields": ("value",)})
        for node in list(ast.walk(fn)):
            if isinstance(node, ast.Subscript) and type(node.slice).__name__ != "Index":
                wrapper = legacy_index_type()
                wrapper.value = node.slice
                node.slice = wrapper
        self.assertTrue(audit.approved_worker_launch(Path("git_watch.py"), tree, call))

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

    def test_session_supervisor_uses_only_the_reviewed_own_script(self):
        source = self.source()
        self.assertTrue(self.approved(source, function="_spawn_supervisor"))
        changed = source.replace('"--supervise", str(root)', '"--unreviewed", str(root)', 1)
        self.assertFalse(self.approved(changed, function="_spawn_supervisor"))
        self.assertFalse(self.approved(source, "other_helper.py", "_spawn_supervisor"))

    def test_moving_process_launch_outside_reviewed_function_is_rejected(self):
        source = self.source().replace("def _spawn_worker(root, token, guard):", "def arbitrary_launcher(root, token, guard):", 1)
        self.assertFalse(self.approved(source))

if __name__ == "__main__":
    unittest.main()
