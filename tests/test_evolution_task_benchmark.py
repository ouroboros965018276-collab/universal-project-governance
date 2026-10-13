"""Positive grading and adversarial behavior of the real artifact benchmark."""
import json
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

    def test_json_types_duplicate_keys_and_nonfinite_values_fail(self):
        spec = task("typed", "config", {"value.json": "old"},
                    {"value.json": '{"enabled":true,"count":1,"ratio":1.0}'},
                    "Preserve exact JSON types", kinds={"value.json": "json"})
        correct = '{"ratio":1.0,"count":1,"enabled":true}'
        self.assertEqual(self.score(spec, {"value.json": correct})["hard"], 1)
        for text in ('{"enabled":1,"count":1,"ratio":1.0}',
                     '{"enabled":true,"count":true,"ratio":1.0}',
                     '{"enabled":true,"count":1.0,"ratio":1.0}',
                     '{"enabled":true,"count":1,"ratio":1}',
                     '{"enabled":false,"enabled":true,"count":1,"ratio":1.0}',
                     '{"enabled":true,"count":1,"ratio":NaN}',
                     '{"enabled":true,"count":1,"ratio":Infinity}'):
            with self.subTest(text=text):
                self.assertEqual(self.score(spec, {"value.json": text})["hard"], 0)

    def test_raw_response_duplicate_keys_or_disagreement_cannot_be_lost_by_parser(self):
        spec = task("raw", "config", {"value.json": "old"}, {"value.json": '{"v":2}'},
                    "Increment", kinds={"value.json": "json"})
        response = {"files": [{"path": "value.json", "content": '{"v":2}'}], "validation": "not_run"}
        request = {"task": spec, "response_json": response,
                   "usage": {"total_tokens": 123}, "wall_seconds": 2.0}
        self.assertEqual(grade(dict(request, response_text=json.dumps(response)))["hard"], 1)
        for raw in ('{"validation":"passed","files":' + json.dumps(response["files"]) + ',"validation":"not_run"}',
                    '{"files":[{"path":"extra","path":"value.json","content":"{\\"v\\":2}"}],"validation":"not_run"}',
                    json.dumps(dict(response, validation="passed")), '{"files":NaN,"validation":"not_run"}'):
            with self.subTest(raw=raw):
                self.assertEqual(grade(dict(request, response_text=raw))["hard"], 0)
