"""Minimal Codex CLI adapter helpers for isolated development smoke runs."""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time


def install(workspace, skill_path):
    workspace = pathlib.Path(workspace).resolve()
    source = pathlib.Path(skill_path).resolve()
    validator = source / "scripts/validate_integrity.py"
    if not validator.is_file():
        raise ValueError("Skill integrity validator is missing")
    checked = subprocess.run(
        [sys.executable, str(validator), str(source)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if checked.returncode:
        raise RuntimeError("Skill integrity validation failed: " + checked.stderr[-2000:])
    destination = workspace / ".agents/skills/universal-project-governance"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def _usage(stdout):
    result = {"usage_available": False}
    calls = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") in {"command_execution", "mcp_tool_call", "file_change"}:
                calls += 1
        if event.get("type") == "turn.completed":
            usage = event.get("usage", {})
            input_tokens = usage.get("input_tokens", usage.get("total_input_tokens"))
            output_tokens = usage.get("output_tokens", usage.get("total_output_tokens"))
            if type(input_tokens) is int and type(output_tokens) is int:
                result.update(
                    usage_available=True,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    cached_input_tokens=usage.get("cached_input_tokens"),
                )
    result["tool_calls"] = calls
    return result


def _diagnostics(stdout, last_message, return_code, timed_out):
    event_counts = {}
    errors = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if isinstance(event_type, str):
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        item = event.get("item", {})
        message = event.get("message") if event_type == "error" else item.get("message") if item.get("type") == "error" else None
        if isinstance(message, str) and len(errors) < 5:
            errors.append(message[:300])
    result = {
        "exit_code": return_code,
        "timed_out": timed_out,
        "event_counts": event_counts,
        "errors": errors,
        "last_message_exists": last_message.is_file(),
    }
    if last_message.is_file():
        data = last_message.read_bytes()
        result["last_message_bytes"] = len(data)
        result["last_message_sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    return result


def run(workspace, task_file, condition_file, output_file, phase, model_id, skill_path):
    workspace = pathlib.Path(workspace).resolve()
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Codex CLI is unavailable on PATH")
    task = pathlib.Path(task_file).read_text(encoding="utf-8")
    condition = pathlib.Path(condition_file).read_text(encoding="utf-8").strip()
    skill = "Use $universal-project-governance for this maintained-project change." if skill_path else "Do not use or install a project governance Skill."
    prompt = "\n\n".join(
        part for part in [skill, condition, "Task:\n" + task, "Evaluation phase: " + phase] if part
    )
    last_message = pathlib.Path(output_file).with_suffix(".last-message.txt")
    command = [
        codex,
        "exec",
        "--cd",
        str(workspace),
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--json",
        "--output-last-message",
        str(last_message),
        "--sandbox",
        "workspace-write",
        "--model",
        model_id,
        "-",
    ]
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900,
            check=False,
        )
        stdout = completed.stdout
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        return_code = 124
        timed_out = True
    usage = _usage(stdout)
    usage["wall_time_seconds"] = time.monotonic() - started
    payload = {"usage": usage, "events": _diagnostics(stdout, last_message, return_code, timed_out)}
    pathlib.Path(output_file).write_text(json.dumps(payload), encoding="utf-8")
    if timed_out:
        print("error: Codex CLI exceeded the 900-second task timeout", file=sys.stderr)
    return return_code


def main():
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "install":
            install(sys.argv[2], sys.argv[3])
            return 0
        if len(sys.argv) == 9 and sys.argv[1] == "run":
            return run(*sys.argv[2:])
        raise ValueError("expected install <workspace> <skill-path> or run <workspace> <task> <condition> <output> <phase> <skill-path>")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
