"""Small, deterministic real-task benchmark; never formal qualification.

Models propose JSON file artifacts without executing generated code. Required
artifacts are compared as JSON, Python AST, or exact text. A removed dependency,
empty module, no-op repair, unrequested edit, or fabricated validation fails.
The frozen task declares its checks before any model dispatch.
"""
from __future__ import annotations

import ast
import json
import math


def _equal(actual, expected, kind):
    if len(actual.encode("utf-8")) > 16384:
        return False
    if kind == "python-ast":
        try:
            tree = ast.parse(actual)
            if sum(1 for _ in ast.walk(tree)) > 256:
                return False
            return ast.dump(tree, include_attributes=False) == ast.dump(
                ast.parse(expected), include_attributes=False)
        except (SyntaxError, TypeError, ValueError):
            return False
    if kind == "json":
        try:
            return json.loads(actual) == json.loads(expected)
        except (json.JSONDecodeError, TypeError):
            return False
    return actual == expected


def grade(request):
    task, response = request["task"], request.get("response_json")
    checks = task.get("artifact_checks", [])
    if not checks:
        raise ValueError("task has no positive artifact checks")
    valid = (isinstance(response, dict) and set(response) == {"files", "validation"}
             and isinstance(response["files"], list) and response["validation"] == "not_run")
    files = {}
    if valid:
        for row in response["files"]:
            if (not isinstance(row, dict) or set(row) != {"path", "content"}
                    or not isinstance(row["path"], str) or not isinstance(row["content"], str)
                    or row["path"] in files):
                valid = False
                break
            files[row["path"]] = row["content"]
    # The task explicitly requires complete final contents of this file set.
    results = {check["path"]: bool(valid and check["path"] in files and
               _equal(files[check["path"]], check["expected"], check.get("kind", "text")) and
               all(text not in files[check["path"]] for text in check.get("forbidden_text", [])))
               for check in checks}
    scope = set(files) == {check["path"] for check in checks}
    hard = int(valid and scope and all(results.values()))
    tokens, seconds = request["usage"].get("total_tokens"), request.get("wall_seconds")
    if type(tokens) is not int or tokens < 0 or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("actual token/time usage is required")
    return {"hard": hard, "soft": float(hard), "critical_failures": 0,
            "core_requirement_failures": int(not hard),
            "loss": tokens + 100 * seconds, "artifact_checks": results, "scope_ok": scope,
            "validation_truth_ok": bool(valid), "task_description": task["prompt"],
            "predicted_answer": response, "fail_reason": None if hard else "positive-artifact-or-truth-check-failed"}


OUTPUT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"files": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"]}}, "validation": {"type": "string", "enum": ["not_run"]}},
    "required": ["files", "validation"]}


def task(identity, family, initial, expected, instruction, *, kinds=None, forbidden=None, unfinished=False):
    """Task factory for an operator-frozen development campaign, not hidden data."""
    kinds = kinds or {}
    forbidden = forbidden or {}
    return {"id": identity, "family": family,
            "plan_context": {"operation": "edit", "domains": ["code"],
                             "signals": ["handoff"] if unfinished else [],
                             "profiles": ["software"], "risk": {}, "unfinished": unfinished},
            "payload": {"initial_files": initial},
            "prompt": instruction + " Return complete final contents of every supplied file, preserve unrelated content, and return no extra files. "
                      "No tests or commands can be executed in this artifact-only task: report validation as not_run. Output the requested JSON only.",
            "output_schema": OUTPUT_SCHEMA,
            "artifact_checks": [{"path": name, "expected": content, "kind": kinds.get(name, "text"),
                                 "forbidden_text": forbidden.get(name, [])}
                                for name, content in expected.items()]}
