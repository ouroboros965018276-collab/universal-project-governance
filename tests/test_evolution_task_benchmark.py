"""Positive grading and adversarial behavior of the real artifact benchmark."""
import unittest
from evolution.task_benchmark import grade, task


class BenchmarkTests(unittest.TestCase):
    def score(self, spec, files, validation="not_run"):
        return grade({"task": spec, "response_json": {"files": [
            {"path": name, "content": value} for name, value in files.items()], "validation": validation},
            "usage": {"total_tokens": 123}, "wall_seconds": 2.0})

    def test_empty_removed_constant_and_correct_module(self):
        spec = task("x", "refactor", {"m.py": "old"}, {"m.py": "def value(x):\n    return 0 if x is None else x\n"},
                    "Preserve function behavior", kinds={"m.py": "python-ast"}, forbidden={"m.py": ["TODO", "workaround"]})
        for files in ({}, {"m.py": ""}, {"m.py": "def value(x): return 0\n"}):
            self.assertEqual(self.score(spec, files)["hard"], 0)
        self.assertEqual(self.score(spec, {"m.py": "def value(x): return 0 if x is None else x"})["hard"], 1)
        self.assertEqual(self.score(spec, {"m.py": "# TODO workaround\ndef value(x): return 0 if x is None else x"})["hard"], 0)

    def test_dependency_deletion_noop_and_scope_fail(self):
        spec = task("y", "dependency", {"requirements.txt": "driver==1.0\nother==2.0\n"},
                    {"requirements.txt": "driver==2.0\nother==2.0\n"}, "Upgrade driver")
        for files in ({"requirements.txt": "other==2.0\n"}, spec["payload"]["initial_files"],
                      {"requirements.txt": "driver==2.0\nother==2.0\n", "extra": ""}):
            self.assertEqual(self.score(spec, files)["hard"], 0)
        result = self.score(spec, {"requirements.txt": "driver==2.0\nother==2.0\n"})
        self.assertEqual(result["hard"], 1)
        self.assertEqual(result["loss"], 323)
        self.assertEqual(self.score(spec, {"requirements.txt": "driver==2.0\nother==2.0\n"}, "passed")["hard"], 0)

    def test_json_formatting_and_absent_positive_checks(self):
        spec = task("z", "interop", {"value.json": '{"v":1}'}, {"value.json": '{"v":2}'}, "Increment", kinds={"value.json": "json"})
        self.assertEqual(self.score(spec, {"value.json": '{ "v" : 2 }'})["hard"], 1)
        self.assertEqual(self.score(spec, {"value.json": '{"v":1}'})["hard"], 0)
        spec["artifact_checks"] = []
        with self.assertRaises(ValueError):
            self.score(spec, {})
