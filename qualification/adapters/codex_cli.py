"""Minimal Codex CLI adapter helpers for isolated development smoke runs."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

if __package__:
    from .diagnostics import redact_text
else:
    from diagnostics import redact_text

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def _host_preferences():
    if sys.platform != "win32":
        return {}
    codex_home = pathlib.Path(os.environ.get("CODEX_HOME") or pathlib.Path.home() / ".codex")
    config_path = codex_home / "config.toml"
    if not config_path.is_file():
        return {}
    if tomllib is None:
        raise RuntimeError("Python 3.11+ or tomli is required to preserve Windows Codex sandbox settings")
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("could not read allowlisted settings from Codex config") from exc
    preferences = {}
    windows = config.get("windows", {})
    sandbox = windows.get("sandbox") if isinstance(windows, dict) else None
    if sandbox in {"elevated", "unelevated"}:
        preferences["windows_sandbox"] = sandbox
    features = config.get("features", {})
    if isinstance(features, dict) and features.get("respect_system_proxy") is True:
        preferences["respect_system_proxy"] = True
    return preferences


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


def _decode_output(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _host_config_args(preferences):
    args = []
    if preferences.get("windows_sandbox"):
        args.extend(["-c", 'windows.sandbox="%s"' % preferences["windows_sandbox"]])
    if preferences.get("respect_system_proxy"):
        args.extend([
            "--enable", "respect_system_proxy",
            "-c", "suppress_unstable_features_warning=true",
        ])
    return args


class PreflightTimeoutError(RuntimeError):
    """Windows sandbox preflight timed out before any Agent invocation."""


def _preflight_windows_sandbox(codex, preferences, output_file=None, timeout_seconds=None):
    if sys.platform != "win32":
        return None
    command = [codex] + _host_config_args(preferences) + ["doctor", "--json"]
    raw_paths = None
    if output_file is not None:
        output_path = pathlib.Path(output_file)
        raw_paths = (
            output_path.with_suffix(".preflight.stdout.raw"),
            output_path.with_suffix(".preflight.stderr.raw"),
        )
    try:
        checked = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30 if timeout_seconds is None else timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if raw_paths:
            _write_raw(raw_paths[0], exc.stdout)
            _write_raw(raw_paths[1], exc.stderr)
        raise PreflightTimeoutError("Codex Windows sandbox preflight timed out") from exc
    stdout = _decode_output(checked.stdout)
    stderr = _decode_output(checked.stderr)
    if raw_paths:
        _write_raw(raw_paths[0], checked.stdout)
        _write_raw(raw_paths[1], checked.stderr)
    try:
        report = json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Codex Windows sandbox preflight returned invalid diagnostics") from exc
    checks = report.get("checks") if isinstance(report, dict) else None
    sandbox = checks.get("sandbox.helpers") if isinstance(checks, dict) else None
    details = sandbox.get("details") if isinstance(sandbox, dict) else None
    if not isinstance(details, dict):
        raise RuntimeError("Codex Windows sandbox preflight omitted sandbox diagnostics")
    provisioning = details.get("sandbox provisioning")
    if checked.returncode != 0 or sandbox.get("status") != "ok" or provisioning != "complete":
        reason = details.get("error code") or sandbox.get("summary") or "sandbox status unavailable"
        raise RuntimeError("Codex Windows sandbox preflight failed: " + str(reason))
    return {
        "backend": details.get("sandbox backend"),
        "provisioning": provisioning,
    }


def _diagnostics(stdout, last_message, return_code, timed_out, stderr=""):
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
            errors.append(redact_text(message)[:300])
    result = {
        "exit_code": return_code,
        "timed_out": timed_out,
        "event_counts": event_counts,
        "errors": errors,
        "last_message_exists": last_message.is_file(),
    }
    if stderr:
        result["stderr_excerpt"] = redact_text(stderr[-1000:])
    if last_message.is_file():
        data = last_message.read_bytes()
        result["last_message_bytes"] = len(data)
        result["last_message_sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    return result


def _write_raw(path, value):
    if value is None:
        data = b""
    else:
        data = value if isinstance(value, bytes) else value.encode("utf-8", errors="replace")
    path = pathlib.Path(path)
    path.write_bytes(data)
    return len(data), hashlib.sha256(data).hexdigest()


def run(workspace, task_file, condition_file, output_file, phase, model_id, skill_path):
    workspace = pathlib.Path(workspace).resolve()
    # On Windows shutil.which("codex") usually finds the npm-generated .CMD
    # shim first. subprocess.run cannot execute that shim directly; its failure
    # looks like a Codex workspace-routing error because the Agent never starts.
    # Prefer the native CLI executable so the measured turn reaches Codex itself.
    host_cli = os.environ.get("CODEX_CLI_PATH")
    if sys.platform == "win32" and host_cli and pathlib.Path(host_cli).is_file():
        codex = host_cli
    else:
        codex = shutil.which("codex.exe") if sys.platform == "win32" else shutil.which("codex")
    if not codex:
        raise RuntimeError("native Codex CLI executable is unavailable on PATH")
    task = pathlib.Path(task_file).read_text(encoding="utf-8")
    condition = pathlib.Path(condition_file).read_text(encoding="utf-8").strip()
    skill = "Use $universal-project-governance for this maintained-project change." if skill_path else "Do not use or install a project governance Skill."
    prompt = "\n\n".join(
        part for part in [skill, condition, "Task:\n" + task, "Evaluation phase: " + phase] if part
    )
    host_preferences = _host_preferences()
    output_path = pathlib.Path(output_file)
    preflight_started = time.monotonic()
    try:
        preflight_timeout = float(os.environ.get("UPG_ADAPTER_PREFLIGHT_TIMEOUT_SECONDS", "30"))
        sandbox_preflight = _preflight_windows_sandbox(codex, host_preferences, output_path, preflight_timeout)
    except (OSError, RuntimeError) as exc:
        reason = redact_text(str(exc))
        elapsed = time.monotonic() - preflight_started
        timed_out = isinstance(exc, PreflightTimeoutError)
        exit_code = 124 if timed_out else 78
        failure_category = "preflight_timed_out" if timed_out else "preflight_failed"
        payload = {
            "usage": {"usage_available": False, "wall_time_seconds": elapsed},
            "events": {
                "exit_code": exit_code,
                "timed_out": timed_out,
                "failure_category": failure_category,
                "timeout_phase": "windows_sandbox_preflight" if timed_out else None,
                "sandbox_preflight": {
                    "status": "timed_out" if timed_out else "failed",
                    "reason": reason,
                    "failure_category": failure_category,
                    "timed_out": timed_out,
                    "model_invoked": False,
                },
            },
            "host_adaptation": host_preferences,
            "sandbox_preflight": {
                "status": "timed_out" if timed_out else "failed",
                "reason": reason,
                "failure_category": failure_category,
                "timed_out": timed_out,
                "model_invoked": False,
            },
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        print("error: " + reason, file=sys.stderr)
        return exit_code
    last_message = pathlib.Path(output_file).with_suffix(".last-message.txt")
    command = [codex]
    command.extend(_host_config_args(host_preferences))
    command.extend([
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
    ])
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=float(os.environ.get("UPG_ADAPTER_TIMEOUT_SECONDS", "870")),
            check=False,
        )
        stdout_raw = completed.stdout
        stderr_raw = completed.stderr
        stdout = _decode_output(stdout_raw)
        stderr = _decode_output(stderr_raw)
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout_raw = exc.stdout
        stderr_raw = exc.stderr
        stdout = _decode_output(stdout_raw)
        stderr = _decode_output(stderr_raw)
        return_code = 124
        timed_out = True
    usage = _usage(stdout)
    usage["wall_time_seconds"] = time.monotonic() - started
    stdout_bytes, stdout_sha = _write_raw(output_path.with_suffix(".stdout.raw"), stdout_raw)
    stderr_bytes, stderr_sha = _write_raw(output_path.with_suffix(".stderr.raw"), stderr_raw)
    events = _diagnostics(stdout, last_message, return_code, timed_out, stderr)
    events["host_adaptation"] = host_preferences
    events["sandbox_preflight"] = sandbox_preflight
    payload = {
        "usage": usage,
        "events": events,
        "host_adaptation": host_preferences,
        "sandbox_preflight": sandbox_preflight,
        "stderr": redact_text(stderr[-8000:]),
        "diagnostics": {
            "stdout_bytes": stdout_bytes,
            "stdout_sha256": "sha256:" + stdout_sha,
            "stderr_bytes": stderr_bytes,
            "stderr_sha256": "sha256:" + stderr_sha,
        },
    }
    output_path.write_text(json.dumps(payload), encoding="utf-8")
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
