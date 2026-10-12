"""Official Codex exec with one required, bounded repository MCP capability.

No authentication material is read/copied by this adapter. Raw CLI events and
the independent broker journal are retained outside the synthetic repository.
This development profile does not claim container isolation, arbitrary program
execution, provider request IDs, or verified provider-internal model selection.
"""
from __future__ import annotations

from collections import Counter
import copy
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from .tool_broker import RepoBroker, TOOLS, canonical, git_command, sha, tool_definitions, validate_task
from .cli_transport import profile_configuration, profile_overrides

VERSION = "1"
_BROKER = Path(__file__).with_name("tool_broker.py")
_TRANSPORT_PROFILE = Path(__file__).with_name("cli_transport.py")
_CONFIG_KEYS = {"binary", "code_mode_host_binary", "git_binary", "model", "effort", "artifact_root", "timeout_seconds",
                "cli_version", "max_tool_calls"}
_BINDING_KEYS = {"campaign_id", "sample_id", "protocol_sha256", "source_sha256",
                 "runtime_sha256", "candidate_sha256"}
_DISABLED = ("shell_tool", "unified_exec", "apps", "plugins", "remote_plugin", "hooks",
             "multi_agent", "multi_agent_v2", "browser_use", "computer_use", "in_app_browser",
             "image_generation", "view_image", "workspace_dependencies", "skill_search",
             "skill_mcp_dependency_install", "sleep_tool")
FINAL_SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"},
                "validation": {"type": "string", "enum": ["passed", "failed"]},
                "helper_gap": {"type": "string", "enum": ["project_tool unavailable in bounded broker"]}},
                "required": ["summary", "validation", "helper_gap"], "additionalProperties": False}


class ToolCallError(RuntimeError):
    def __init__(self, message, *, usage=None, provider_receipt=None):
        super().__init__(message)
        self.usage, self.provider_receipt = usage, provider_receipt


class ToolCallPending(ToolCallError):
    """Uncertain dispatch is fenced, never automatically replayed."""


def _atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                if os.name != "nt" or getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 5:
                    raise
                time.sleep((.02, .04, .08, .16, .24)[attempt])
    finally:
        if temporary.exists():
            temporary.unlink()


def _events(raw):
    events = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _usage(events):
    turns = [event for event in events if event.get("type") == "turn.completed"]
    if len(turns) != 1 or not isinstance(turns[0].get("usage"), dict):
        return None
    raw = turns[0]["usage"]
    names = ("input_tokens", "output_tokens")
    if any(type(raw.get(key)) is not int or raw[key] < 0 for key in names):
        return None
    result = {key: raw[key] for key in names}
    result.update(total_tokens=sum(result.values()), cost_usd=None,
                  measurement="actual-codex-cli-completed-tool-turn")
    for name, maximum in (("cached_input_tokens", raw["input_tokens"]),
                          ("reasoning_output_tokens", raw["output_tokens"]),
                          ("cache_write_input_tokens", None)):
        value = raw.get(name)
        if value is not None and (type(value) is not int or value < 0 or maximum is not None and value > maximum):
            return None
        result[name] = value
    return result


def _final_text(events):
    messages = [event.get("item", {}).get("text", "") for event in events
                if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message"]
    return messages[-1] if messages else ""


def _audit(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _trace_failures(events, broker_events, max_calls):
    failures, observed = [], []
    for event in events:
        if event.get("type") in {"turn.failed", "error"}:
            failures.append("cli-turn-error")
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        kind = item.get("type")
        if kind == "mcp_tool_call":
            if item.get("server") != "upg_repo" or item.get("tool") not in TOOLS:
                failures.append("nonbroker-tool-event")
            arguments = item.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = None
            if not isinstance(arguments, dict):
                failures.append("missing-cli-tool-arguments")
            observed.append((item.get("tool"), sha(canonical(arguments))))
        elif kind not in {"agent_message", "reasoning", "plan", "todo_list"}:
            failures.append("unregistered-cli-item:" + str(kind))
    if Counter(observed) != Counter((row.get("tool"), row.get("arguments_sha256")) for row in broker_events):
        failures.append("cli-broker-call-journal-mismatch")
    if len(broker_events) > max_calls:
        failures.append("tool-call-budget-exceeded")
    for number, row in enumerate(broker_events, 1):
        if (row.get("sequence") != number or row.get("result_sha256") != sha(canonical(row.get("result")))
                or row.get("arguments_sha256") != sha(canonical(row.get("arguments")))):
            failures.append("invalid-broker-journal")
    return failures


def _quality(broker, broker_events, events, final_text, max_calls):
    validation = broker.validate()
    failures = (list(validation["failures"]) + _trace_failures(events, broker_events, max_calls)
                + broker.read_evidence_failures(broker_events))
    current = sha(canonical(broker.snapshot()))
    success = {row["tool"] for row in broker_events if row.get("result", {}).get("ok") is True}
    required = set(broker.task.get("required_tools", ["repo_read", "repo_patch", "repo_validate", "repo_status"]))
    tools_ok = required <= success
    for tool in ("repo_validate", "repo_status"):
        successful = [row for row in broker_events if row.get("tool") == tool and row.get("result", {}).get("ok") is True]
        if not successful or successful[-1].get("state_sha256") != current:
            tools_ok = False
    if not tools_ok:
        failures.append("required-current-real-tool-evidence-missing")
    initial = {name: sha(text.encode("utf-8")) for name, text in broker.task["initial_files"].items()}
    if broker.snapshot() == initial:
        failures.append("no-actual-repository-edit")
    try:
        final = json.loads(final_text)
        if (not isinstance(final, dict) or set(final) != {"summary", "validation", "helper_gap"}
                or not isinstance(final["summary"], str) or not final["summary"].strip()
                or final["helper_gap"] != "project_tool unavailable in bounded broker"
                or final["validation"] != ("passed" if validation["ok"] and tools_ok else "failed")):
            raise ValueError("final claim does not match independently observed validation")
    except (ValueError, TypeError):
        failures.append("final-validation-claim-invalid")
    scope_ok = not any(item.startswith(("scope-invalid:", "protected-file-changed:", "nonbroker-", "unregistered-cli-"))
                       for item in failures)
    return {"task_success": int(not failures), "hard_pass": not failures, "scope_ok": scope_ok,
            "required_tools_ok": tools_ok, "checks_passed": validation["checks_passed"],
            "checks_total": validation["checks_total"], "failures": failures}


class ToolCodex:
    def __init__(self, config):
        started = time.perf_counter()
        if not isinstance(config, dict) or set(config) - _CONFIG_KEYS:
            raise ValueError("unsupported tool configuration; no credential fields accepted")
        for key in ("binary", "code_mode_host_binary", "git_binary", "model", "effort", "artifact_root", "timeout_seconds"):
            if key not in config:
                raise ValueError("tool configuration requires " + key)
        self.config = dict(config)
        # Both experiment conditions use this fixed child-only transport. Keep
        # endpoint selection and authentication with the installed OpenAI CLI;
        # callers cannot supply provider/credential overrides through config.
        self.config.update(profile_configuration())
        self.binary, self.git = Path(config["binary"]), Path(config["git_binary"])
        self.code_mode_host = Path(config["code_mode_host_binary"])
        self.package_manifest = self.binary.parent.parent / "codex-package.json"
        self.artifacts = Path(config["artifact_root"])
        if not all(path.is_absolute() and path.is_file() for path in (self.binary, self.code_mode_host, self.git)):
            raise ValueError("registered native CLI, Code Mode host and Git must be absolute files")
        host_name = "codex-code-mode-host.exe" if os.name == "nt" else "codex-code-mode-host"
        if self.code_mode_host.name != host_name or self.code_mode_host.resolve().parent != self.binary.resolve().parent:
            raise ValueError("registered Code Mode host must be the native CLI's installed sibling")
        if not self.artifacts.is_absolute():
            raise ValueError("artifact root must be absolute")
        if not isinstance(config["model"], str) or not config["model"].strip():
            raise ValueError("model must be explicitly registered")
        if config["effort"] not in {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}:
            raise ValueError("unsupported explicit effort")
        timeout = config["timeout_seconds"]
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 900:
            raise ValueError("timeout must be finite and in (0,900]")
        calls = config.get("max_tool_calls", 32)
        if type(calls) is not int or not 4 <= calls <= 128:
            raise ValueError("max_tool_calls must be in [4,128]")
        self._frozen = self._identity()
        self.setup_seconds = time.perf_counter() - started

    def _identity(self):
        manifest_hash = None
        if self.package_manifest.exists():
            raw_manifest = self.package_manifest.read_bytes()
            manifest = json.loads(raw_manifest)
            if (manifest.get("layoutVersion") != 1 or not isinstance(manifest.get("entrypoint"), str)
                    or (self.package_manifest.parent / manifest["entrypoint"]).resolve() != self.binary.resolve()):
                raise ValueError("installed package manifest does not identify registered CLI")
            manifest_hash = sha(raw_manifest)
        return {"adapter": "codex-exec-required-bounded-mcp-v2", "config_sha256": sha(canonical(self.config)),
                "model_provider": self.config["model_provider"],
                "model_provider_profile": copy.deepcopy(self.config["model_provider_profile"]),
                "model_provider_profile_sha256": sha(canonical(self.config["model_provider_profile"])),
                "transport_features": copy.deepcopy(self.config["transport_features"]),
                "transport_profile_source_sha256": sha(_TRANSPORT_PROFILE.read_bytes()),
                "transport_overrides_sha256": sha(canonical(profile_overrides())),
                "binary_sha256": sha(self.binary.read_bytes()), "git_sha256": sha(self.git.read_bytes()),
                "code_mode_host_sha256": sha(self.code_mode_host.read_bytes()),
                "package_manifest_sha256": manifest_hash,
                "code_mode_host_process_path_attested": False,
                "adapter_source_sha256": sha(Path(__file__).read_bytes()), "broker_source_sha256": sha(_BROKER.read_bytes()),
                "tool_schema_sha256": sha(canonical(tool_definitions())),
                "host": {"platform": platform.platform(), "python_version": platform.python_version(),
                         "python_binary_sha256": sha(Path(sys.executable).read_bytes())},
                "model_requested": self.config["model"], "effort_requested": self.config["effort"],
                "cli_version_declared": self.config.get("cli_version"), "isolation_attested": False,
                "tool_scope": "registered-text-static-contracts-and-fixed-git-status",
                "tool_transport": "installed-code-mode-v8-required-mcp",
                "preapproved_broker_tools": list(TOOLS),
                "code_mode_configuration_enabled": False}

    def binding(self):
        if (sha(canonical(self.config)) != self._frozen["config_sha256"]
                or sha(Path(__file__).read_bytes()) != self._frozen["adapter_source_sha256"]
                or sha(_BROKER.read_bytes()) != self._frozen["broker_source_sha256"]
                or sha(_TRANSPORT_PROFILE.read_bytes()) != self._frozen["transport_profile_source_sha256"]):
            raise ValueError("tool capability changed after registration")
        return copy.deepcopy(self._frozen)

    def _unknown(self, directory, receipt):
        _atomic(directory / "receipt.json", receipt)
        fence = self.artifacts / "UNKNOWN_CALL.json"
        if not fence.exists():
            with fence.open("xb") as stream:
                stream.write(canonical({"call_key": directory.name,
                                        "harness_request_id": receipt["harness_request_id"],
                                        "reason": receipt["status"]}) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())

    def _remember_unknown(self, directory, receipt):
        try:
            self._unknown(directory, receipt)
        except OSError as error:
            # The incomplete or noncompleted call directory also fences future
            # dispatches. Never discard observed usage because evidence I/O failed.
            receipt["fence_persistence_error"] = type(error).__name__ + ": " + str(error)[:240]

    def _arguments(self, directory, spec_file):
        command = [str(self.binary), "--ask-for-approval", "never", "exec", "--cd", str(directory / "workspace"),
                   "--ephemeral", "--ignore-user-config", "--json", "--sandbox", "read-only",
                   "--model", self.config["model"], "--output-schema", str(directory / "output.schema.json"),
                   "-c", "model_reasoning_effort=" + json.dumps(self.config["effort"]),
                   "-c", 'web_search="disabled"', "-c", "features.skip_host_skill_discovery=true",
                   "-c", "hide_agent_reasoning=true", "-c", "project_doc_max_bytes=0",
                   "-c", "features.code_mode.enabled=false", "-c", "features.code_mode_host=true",
                   "-c", "suppress_unstable_features_warning=true"]
        for value in profile_overrides():
            command.extend(["-c", value])
        for feature in _DISABLED:
            command.extend(["-c", "features." + feature + "=false"])
        mcp = {"command": sys.executable, "args": ["-B", str(_BROKER), str(spec_file)],
               "required": True, "enabled_tools": list(TOOLS), "env_vars": [],
               "env": {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}}
        for key, value in mcp.items():
            # JSON scalars/arrays are TOML-compatible; inline tables need TOML syntax.
            serialized = ('{PYTHONIOENCODING="utf-8",PYTHONDONTWRITEBYTECODE="1"}'
                          if key == "env" else json.dumps(value, ensure_ascii=False))
            command.extend(["-c", "mcp_servers.upg_repo." + key + "=" + serialized])
        # The owner has authorized these exact bounded synthetic-repository
        # capabilities. Keep the global policy and every other server unchanged.
        for tool in TOOLS:
            command.extend(["-c", 'mcp_servers.upg_repo.tools.' + tool + '.approval_mode="approve"'])
        command.append("-")
        return command

    def run(self, task, *, prompt, bindings):
        run_started = time.perf_counter()
        validate_task(task)
        capability = self.binding()
        if (not isinstance(bindings, dict) or bindings.get("capability") != capability
                or any(not isinstance(bindings.get(key), str) or not bindings[key] for key in _BINDING_KEYS)):
            raise ValueError("explicit matching capability and frozen experiment bindings are required")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("owner-compiled prompt is required")
        self.artifacts.mkdir(parents=True, exist_ok=True)
        lock = self.artifacts / ".tool-dispatch.lock"
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise ToolCallPending("tool dispatch active/interrupted; no automatic replay") from error
        result, call_error = None, None
        try:
            os.write(descriptor, canonical({"pid": os.getpid(), "sample_id": bindings["sample_id"]}))
            os.fsync(descriptor)
            result = self._run_locked(task, prompt, bindings, capability, run_started)
        except BaseException as error:
            call_error = error
            raise
        finally:
            try:
                os.close(descriptor)
                lock.unlink()
            except OSError as error:
                # Retained lock stops subsequent dispatch. Do not mask known
                # charges/results with a cleanup exception after the real turn.
                cleanup = type(error).__name__ + ": " + str(error)[:240]
                if result is not None:
                    result["receipt"]["dispatch_lock_cleanup_error"] = cleanup
                elif getattr(call_error, "provider_receipt", None) is not None:
                    call_error.provider_receipt["dispatch_lock_cleanup_error"] = cleanup
        return result

    def _run_locked(self, task, prompt, bindings, capability, run_started):
        if (self.artifacts / "UNKNOWN_CALL.json").exists():
            raise ToolCallPending("unknown tool call needs independent reconciliation")
        frozen = self.artifacts / "CAPABILITY.json"
        if frozen.exists():
            if json.loads(frozen.read_text(encoding="utf-8")) != capability:
                raise ValueError("artifact root bound to another capability")
        else:
            _atomic(frozen, capability)
        calls = self.artifacts / "calls"
        calls.mkdir(exist_ok=True)
        for previous in calls.iterdir():
            if previous.is_dir():
                try:
                    previous_receipt = json.loads((previous / "receipt.json").read_text(encoding="utf-8"))
                    previous_result = json.loads((previous / "result.json").read_text(encoding="utf-8"))
                    if (previous_receipt.get("status") != "completed"
                            or sha(canonical(previous_result)) != previous_receipt.get("result_sha256")):
                        raise ValueError("noncompleted or corrupt result")
                except (OSError, ValueError) as error:
                    raise ToolCallPending("incomplete/noncompleted tool dispatch needs reconciliation") from error
        key = sha(canonical({"task": task, "prompt": prompt, "bindings": bindings, "capability": capability}))
        directory = calls / key
        if directory.exists():
            receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
            result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            for name, expected in receipt["artifact_sha256"].items():
                if sha((directory / name).read_bytes()) != expected:
                    raise ToolCallPending("tool receipt artifact hash mismatch; no replay")
            if sha(canonical(result)) != receipt["result_sha256"]:
                raise ToolCallPending("tool result hash mismatch; no replay")
            try:
                saved_repo = RepoBroker(directory / "workspace", task, self.git,
                                        max_calls=self.config.get("max_tool_calls", 32))
                if sha(canonical(saved_repo.snapshot())) != result["final_files_sha256"]:
                    raise ValueError("repository changed after measured call")
            except (OSError, ValueError) as error:
                raise ToolCallPending("cached repository evidence changed; no replay") from error
            result["receipt"] = dict(receipt, artifact_directory=str(directory),
                                     receipt_sha256=sha((directory / "receipt.json").read_bytes()),
                                     replayed_from_local_receipt=True,
                                     local_reuse_wall_seconds=time.perf_counter() - run_started)
            return result
        directory.mkdir()
        identifier = str(uuid.uuid4())
        pending = {"harness_request_id": identifier, "bindings": bindings, "task_sha256": sha(canonical(task)),
                   "prompt_sha256": sha(prompt.encode("utf-8")), "capability": capability,
                   "dispatch_state": "not_started", "model_invoked": False}
        try:
            _atomic(directory / "pending.json", pending)
            # Keep prep results explicit: these files are outside agent scope.
            workspace = directory / "workspace"
            workspace.mkdir()
            for name, text in task["initial_files"].items():
                path = workspace.joinpath(*name.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))
            initialized = git_command(self.git, workspace, "init", "--template=", "--quiet")
            if initialized.returncode:
                raise ValueError("fixed Git initialization failed")
            spec = {"workspace": str(workspace), "task": task, "git_binary": str(self.git),
                    "audit_file": str(directory / "broker.jsonl"), "max_tool_calls": self.config.get("max_tool_calls", 32),
                    "deadline": time.time() + self.config["timeout_seconds"]}
            _atomic(directory / "broker.spec.json", spec)
            _atomic(directory / "output.schema.json", FINAL_SCHEMA)
            (directory / "prompt.txt").write_bytes(prompt.encode("utf-8"))
            command = self._arguments(directory, directory / "broker.spec.json")
            _atomic(directory / "command.json", command)
            # One full binary/config verification immediately before dispatch.
            if self._identity() != capability:
                raise ValueError("capability changed during preparation")
            prepare_seconds = time.perf_counter() - run_started
            pending.update(dispatch_state="dispatching", model_invoked=None)
            _atomic(directory / "pending.json", pending)
        except Exception as error:
            zero = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                    "measurement": "model-dispatch-not-started", "cost_usd": None}
            receipt = dict(pending, status="preparation-failed", dispatch_state="not_started", model_invoked=False,
                           usage=zero, artifact_directory=str(directory), error_type=type(error).__name__)
            try:
                _atomic(directory / "preparation-failure.json", receipt)
            except OSError as persistence_error:
                receipt["preparation_receipt_error"] = type(persistence_error).__name__
            raise ToolCallPending("tool preparation failed before model dispatch", usage=zero, provider_receipt=receipt) from error
        started = time.perf_counter()
        stdout, stderr, exit_code = b"", b"", None
        try:
            completed = subprocess.run(command, input=prompt.encode("utf-8"), stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, timeout=self.config["timeout_seconds"], check=False)
            stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        except BaseException as error:
            if isinstance(error, subprocess.TimeoutExpired):
                stdout, stderr = error.stdout or b"", error.stderr or b""
            known_usage = _usage(_events(stdout))
            receipt = dict(pending, status=type(error).__name__ + "-dispatch-state-unconfirmed",
                           usage=known_usage, wall_seconds=time.perf_counter() - started, provider_request_id=None,
                           model_observed=None, artifact_sha256={"stdout.raw": sha(stdout), "stderr.raw": sha(stderr)})
            try:
                (directory / "stdout.raw").write_bytes(stdout)
                (directory / "stderr.raw").write_bytes(stderr)
            except OSError as persistence_error:
                receipt["raw_persistence_error"] = type(persistence_error).__name__
            self._remember_unknown(directory, receipt)
            if not isinstance(error, Exception):
                raise
            raise ToolCallError(receipt["status"], usage=known_usage, provider_receipt=receipt) from error
        elapsed = time.perf_counter() - started
        grading_started = time.perf_counter()
        events = _events(stdout)
        usage = _usage(events)
        threads = [event.get("thread_id") for event in events if event.get("type") == "thread.started"]
        try:
            (directory / "stdout.raw").write_bytes(stdout)
            (directory / "stderr.raw").write_bytes(stderr)
        except OSError as error:
            receipt = dict(pending, status="raw-evidence-persistence-failed", usage=usage,
                           wall_seconds=elapsed, provider_request_id=None, model_observed=None)
            self._remember_unknown(directory, receipt)
            raise ToolCallError(receipt["status"], usage=usage, provider_receipt=receipt) from error
        if usage is None or len(threads) != 1 or not isinstance(threads[0], str) or not threads[0]:
            receipt = dict(pending, status="completed-identity-or-usage-unconfirmed", usage=usage,
                           wall_seconds=elapsed, cli_exit_code=exit_code, provider_request_id=None,
                           model_observed=None, artifact_sha256={"stdout.raw": sha(stdout), "stderr.raw": sha(stderr)})
            self._remember_unknown(directory, receipt)
            raise ToolCallError(receipt["status"], usage=usage, provider_receipt=receipt)
        try:
            broker_events = _audit(directory / "broker.jsonl")
            broker = RepoBroker(workspace, task, self.git, max_calls=self.config.get("max_tool_calls", 32))
            final_text = _final_text(events)
            quality = _quality(broker, broker_events, events, final_text, self.config.get("max_tool_calls", 32))
            if exit_code:
                quality["task_success"], quality["hard_pass"] = 0, False
                quality["failures"].append("nonzero-cli-exit")
            final_files = broker.snapshot()
            _atomic(directory / "final-files.json", final_files)
            result = {"status": "completed", "usage": usage, "wall_seconds": elapsed, "quality": quality,
                      "tool_events": broker_events, "final_response_text": final_text, "final_files_sha256": sha(canonical(final_files)),
                      "timing": {"prepare_seconds": prepare_seconds, "cli_seconds": elapsed,
                                 "grading_seconds": time.perf_counter() - grading_started,
                                 "measurement_end": "after-independent-grade-before-evidence-commit",
                                 "capability_setup_seconds_not_in_task_wall": self.setup_seconds}}
            result["wall_seconds"] = time.perf_counter() - run_started
            _atomic(directory / "result.json", result)
            names = ("stdout.raw", "stderr.raw", "broker.jsonl", "broker.spec.json", "output.schema.json",
                     "prompt.txt", "command.json", "pending.json", "final-files.json")
            # A completed no-tool task is known failed evidence, with an empty broker journal.
            if not (directory / "broker.jsonl").exists():
                (directory / "broker.jsonl").write_bytes(b"")
            receipt = dict(pending, status="completed", receipt_type="codex_cli_tool_turn", usage=usage,
                           wall_seconds=result["wall_seconds"], timing=result["timing"], cli_exit_code=exit_code, cli_thread_id=threads[0],
                           provider_request_id=None, model_observed=None, provider_internal_attempts="unknown",
                           argv=command, artifact_sha256={name: sha((directory / name).read_bytes()) for name in names},
                           result_sha256=sha(canonical(result)), isolation_attested=False,
                           dispatch_state="completed", model_invoked=True,
                           application_execution="excluded-static-contracts-only")
            _atomic(directory / "receipt.json", receipt)
        except BaseException as error:
            receipt = dict(pending, status="post-dispatch-evidence-unconfirmed", usage=usage,
                           wall_seconds=elapsed, cli_thread_id=threads[0], provider_request_id=None,
                           model_observed=None, error_type=type(error).__name__)
            self._remember_unknown(directory, receipt)
            if not isinstance(error, Exception):
                raise
            raise ToolCallError(receipt["status"], usage=usage, provider_receipt=receipt) from error
        result["receipt"] = dict(receipt, artifact_directory=str(directory),
                                 receipt_sha256=sha(canonical(receipt) + b"\n"),
                                 replayed_from_local_receipt=False)
        return result
