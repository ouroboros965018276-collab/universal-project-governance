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
                "cli_version", "max_tool_calls", "broker_profile_id"}
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



class _PreparationStageError(RuntimeError):
    """Safe owner-only observation; never converts a preparation error to dispatch."""
    def __init__(self, observation, original):
        super().__init__(observation['reason'])
        self.observation = observation
        self.original = original


def _preparation_error(error, reason):
    # Unknown exception strings/args may contain credentials. Never format them.
    known = {'OSError', 'PermissionError', 'FileNotFoundError', 'FileExistsError',
             'TimeoutError', 'ValueError', 'TypeError', 'RuntimeError', 'AssertionError',
             'UnicodeError', 'UnicodeDecodeError', 'UnicodeEncodeError', 'RecursionError',
             'KeyboardInterrupt', 'SystemExit', 'TimeoutExpired'}
    name = type(error).__name__
    result = {'class': name if name in known else 'Exception', 'message_code': reason,
              'message': 'untrusted exception text withheld'}
    for key in ('errno', 'winerror'):
        value = getattr(error, key, None)
        if type(value) is int:
            result[key] = value
    return result


def _preparation_write(path, raw):
    # Fresh paths only. Never replace or clean partial evidence after a failure.
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


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


def _audit(path, *, strict_project=False):
    if not path.exists():
        return []
    parse = _project_cli_json if strict_project else json.loads
    return [parse(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _select_prior_call_context(context, directory, requested_key, observation=None):
    """Attribute checked prior evidence without creating a new charge record."""
    if observation is None:
        prior = {'kind': 'observed-prior-cli-call-v1', 'call_key': directory.name,
            'receipt_ref': 'calls/' + directory.name + '/receipt.json',
            'receipt_sha256': None, 'harness_request_id': None, 'reported_usage': None,
            'matches_requested_cache_key': directory.name == requested_key,
            'accounting_role': 'reference-to-existing-turn', 'count_as_new_charge': False}
        observation = {'status': 'cached-project-evidence-unknown', 'harness_request_id': None,
            'usage': None, 'cache_check_model_invoked': False, 'cache_check_replayed': False,
            'requested_call_key': requested_key, 'requested_dispatch_state': 'not_started',
            'original_completed_receipt_sha256': None, 'original_completed_result_sha256': None,
            'observed_prior_call': prior}
    context.update(active=True, directory=directory, observation=observation)
    context['pending'].usage = observation['usage']
    context['pending'].provider_receipt = observation
    context['pending'].observed_prior_call = observation['observed_prior_call']
    return observation


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


def _project_cli_json(raw):
    """Reuse strict parsing, with a wire bound allowing escaped registered files."""
    from .project_executor import strict_json
    from .tool_broker import MAX_TOTAL_BYTES, _bounded
    if not isinstance(raw, (str, bytes)) or len(raw.encode('utf-8') if isinstance(raw, str) else raw) > 8 * MAX_TOTAL_BYTES:
        raise ValueError('CLI project event exceeds wire bound')
    return _bounded(strict_json(raw))


def _project_cli_events(raw):
    result = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        value = _project_cli_json(line)
        if type(value) is not dict:
            raise ValueError('CLI project event is not an object')
        result.append(value)
    return result


def _project_cli_trace_failures(events, journal, task):
    """Strict CLI-native MCP evidence, not a fabricated API response chain.

    This explicit prospective profile admits only the locally registered JSON
    event envelope. Unknown/absent result shapes fail; real CLI compatibility
    still requires a separate registered first observation.
    """
    observed, failures, seen_ids = [], [], set()
    for event in events:
        if event.get('type') != 'item.completed' or event.get('item', {}).get('type') != 'mcp_tool_call':
            continue
        item = event['item']
        arguments = item.get('arguments')
        if type(arguments) is str:
            try:
                arguments = _project_cli_json(arguments)
            except (ValueError, RecursionError):
                arguments = None
        result = item.get('result')
        identifier = item.get('id')
        if (set(item) != {'id', 'type', 'server', 'tool', 'arguments', 'result', 'error', 'status'}
                or type(identifier) is not str or not identifier or identifier in seen_ids
                or item.get('status') != 'completed'
                or item.get('server') != 'upg_repo' or item.get('tool') not in TOOLS
                or type(arguments) is not dict or item.get('error') is not None
                or type(result) is not dict or set(result) != {'content', 'structured_content'}
                or result.get('structured_content') is not None
                or type(result.get('content')) is not list or len(result['content']) != 1
                or type(result['content'][0]) is not dict
                or set(result['content'][0]) != {'type', 'text'}
                or result['content'][0]['type'] != 'text'
                or type(result['content'][0]['text']) is not str):
            failures.append('scope-invalid:cli-project-mcp-result-unconfirmed')
            continue
        seen_ids.add(identifier)
        try:
            value = _project_cli_json(result['content'][0]['text'])
            if type(value) is not dict:
                raise ValueError('MCP result is not an object')
        except (ValueError, RecursionError):
            failures.append('scope-invalid:cli-project-mcp-result-unconfirmed')
            continue
        observed.append((item['tool'], sha(canonical(arguments)), sha(canonical(value))))
    expected = [(row.get('tool'), row.get('arguments_sha256'), row.get('result_sha256')) for row in journal]
    if observed != expected:
        failures.append('scope-invalid:cli-project-ordered-results-journal-mismatch')
    from .engineering_broker import validate_execution_result, recoverable_project_test_failure
    for row in journal:
        result = row.get('result', {})
        project_validation = row.get('tool') == 'repo_validate' and row.get('arguments') == {}
        if project_validation:
            checked = validate_execution_result(result, task, row.get('state_sha256'))
            if (checked is None or checked['status'] != 'EXECUTED' or checked['unknown'] is not False
                    or result.get('write_state') is not None):
                failures.append('scope-invalid:cli-project-execution-unknown-or-unconfirmed')
        if result.get('ok') is not True:
            if not project_validation or not recoverable_project_test_failure(result, task, row.get('state_sha256')):
                failures.append('scope-invalid:cli-project-tool-refused')
                failures.extend(value for value in result.get('failures', []) if type(value) is str)
        elif result.get('write_state') is not None or result.get('failures'):
            failures.append('scope-invalid:cli-project-inconsistent-success')
            failures.extend(value for value in result.get('failures', []) if type(value) is str)
    return failures


def _quality(broker, broker_events, events, final_text, max_calls, *, supplied_validation=None,
             extra_failures=(), strict_cli_results=False):
    validation = broker.validate() if supplied_validation is None else supplied_validation
    failures = (list(validation["failures"]) + _trace_failures(events, broker_events, max_calls)
                + broker.read_evidence_failures(broker_events) + list(extra_failures))
    if strict_cli_results:
        failures.extend(_project_cli_trace_failures(events, broker_events, broker.task))
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
            "required_tools_ok": tools_ok, "checks_passed": validation.get("checks_passed", 0),
            "checks_total": validation.get("checks_total", len(broker.task.get('engineering_contract', {}).get('checks', []))),
            "failures": failures}


class ToolCodex:
    def __init__(self, config):
        started = time.perf_counter()
        if not isinstance(config, dict) or set(config) - _CONFIG_KEYS:
            raise ValueError("unsupported tool configuration; no credential fields accepted")
        for key in ("binary", "code_mode_host_binary", "git_binary", "model", "effort", "artifact_root", "timeout_seconds"):
            if key not in config:
                raise ValueError("tool configuration requires " + key)
        profile = config.get("broker_profile_id")
        if profile is not None and (type(profile) is not str or profile != "stdlib-python-project-v1"):
            raise ValueError("unknown explicit broker profile")
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
        identity = {"adapter": "codex-exec-required-bounded-mcp-v2", "config_sha256": sha(canonical(self.config)),
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
        if self.config.get("broker_profile_id") is not None:
            from . import engineering_broker as engineering
            from . import project_executor
            from . import isolated_python
            from tools import validate_navigation
            identity.update(adapter="codex-exec-required-stdlib-project-mcp-v1",
                broker_profile_id=engineering.PROFILE_ID,
                execution_backend=engineering.BACKEND_ID,
                engineering_broker_source_sha256=sha(Path(engineering.__file__).read_bytes()),
                project_executor_source_sha256=sha(Path(project_executor.__file__).read_bytes()),
                isolated_executor_source_sha256=sha(Path(isolated_python.__file__).read_bytes()),
                navigation_source_sha256=sha(Path(validate_navigation.__file__).read_bytes()),
                project_runner_sha256=sha(project_executor.CHECKER.encode('utf-8')),
                tool_schema_sha256=sha(canonical(engineering.tool_definitions())),
                final_schema_sha256=sha(canonical(FINAL_SCHEMA)),
                artifact_root=str(self.artifacts),
                tool_scope="registered-stdlib-project-fixed-container-recipes",
                application_isolation_scope="fixed-project-recipe-container-only",
                provider_request_cap_attested=False, controlled_cutpoint_supported=False,
                final_report_protocol="cli-json-output-schema-v1",
                preparation_evidence_schema="project-git-init-preparation-v1")
        return identity

    def binding(self):
        if (sha(canonical(self.config)) != self._frozen["config_sha256"]
                or sha(Path(__file__).read_bytes()) != self._frozen["adapter_source_sha256"]
                or sha(_BROKER.read_bytes()) != self._frozen["broker_source_sha256"]
                or sha(_TRANSPORT_PROFILE.read_bytes()) != self._frozen["transport_profile_source_sha256"]):
            raise ValueError("tool capability changed after registration")
        if self.config.get("broker_profile_id") is not None and self._identity() != self._frozen:
            raise ValueError("project tool capability changed after registration")
        return copy.deepcopy(self._frozen)

    def _task_validate(self, task):
        if self.config.get("broker_profile_id") is None:
            return validate_task(task)
        from .engineering_broker import validate_task as validate_project
        return validate_project(task)

    def public_instruction(self):
        if self.config.get("broker_profile_id") is None:
            raise ValueError("public project instruction requires an explicit project profile")
        from .engineering_broker import cli_public_instruction
        return cli_public_instruction()

    def _read_broker(self, directory, task, journal):
        if self.config.get("broker_profile_id") is None:
            return RepoBroker(directory / "workspace", task, self.git,
                              max_calls=self.config.get("max_tool_calls", 32))
        from .engineering_broker import read_broker_receipts
        return read_broker_receipts(directory / "workspace", task, self.git,
            events=journal, execution_artifacts=directory / "execution",
            max_calls=self.config.get("max_tool_calls", 32))

    def _project_quality(self, broker, journal, events, final_text):
        from .engineering_broker import current_validation_from_receipts, BACKEND_ID
        validation, failures, execution_unknown, not_run = current_validation_from_receipts(broker)
        quality = _quality(broker, journal, events, final_text,
            self.config.get("max_tool_calls", 32), supplied_validation=validation,
            extra_failures=failures, strict_cli_results=True)
        quality.update(validation=None if not_run else validation,
            evidence_adapter="codex-exec-required-stdlib-project-mcp-v1",
            evidence_broker_profile_id=self.config["broker_profile_id"],
            evidence_execution_backend=BACKEND_ID, execution_state_unknown=execution_unknown)
        if not_run:
            quality['final_execution_not_run_reason'] = 'required-current-project-validation-missing'
        return quality

    def _unknown(self, directory, receipt, *, cache_observation=False):
        _atomic(directory / ("cache-unknown-observation.json" if cache_observation else "receipt.json"), receipt)
        fence = self.artifacts / "UNKNOWN_CALL.json"
        if not fence.exists():
            with fence.open("xb") as stream:
                stream.write(canonical({"call_key": directory.name,
                                        "harness_request_id": receipt["harness_request_id"],
                                        "reason": receipt["status"]}) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())

    def _remember_unknown(self, directory, receipt, *, cache_observation=False):
        try:
            if cache_observation:
                self._unknown(directory, receipt, cache_observation=True)
            else:
                self._unknown(directory, receipt)
        except OSError as error:
            # The incomplete or noncompleted call directory also fences future
            # dispatches. Never discard observed usage because evidence I/O failed.
            receipt["fence_persistence_error"] = type(error).__name__ + ": " + str(error)[:240]

    def _initialize_project_git(self, directory, workspace, pending):
        """One fixed Git init, with private evidence committed before any model call."""
        from .tool_broker import clean_git_environment
        expected = [str(self.git), '--no-optional-locks', '-c', 'core.fsmonitor=false',
                    '-c', 'core.hooksPath=/dev/null', '-c', 'core.autocrlf=false',
                    'init', '--template=', '--quiet']
        target = directory / 'preparation' / 'git-init'
        started = time.perf_counter()
        observation = {'schema_version': 1, 'kind': 'project-git-init-preparation-v1',
            'stage': 'git-intent-persistence', 'reason': 'preparation-evidence-persistence-failed',
            'outcome': 'not_started', 'harness_request_id': pending['harness_request_id'],
            'model_dispatch_state': 'not_started', 'model_invoked': False,
            'planned_argv': expected, 'observed_argv': None, 'cwd': str(workspace),
            'environment_key_names': sorted(clean_git_environment()),
            'source_binding': {'capability_sha256': sha(canonical(pending['capability'])),
                'adapter_source_sha256': pending['capability']['adapter_source_sha256'],
                'broker_source_sha256': pending['capability']['broker_source_sha256'],
                'git_binary_sha256': pending['capability']['git_sha256'],
                'python_binary_sha256': pending['capability']['host']['python_binary_sha256']},
            'started_unix_seconds': time.time(), 'git_wall_seconds': None,
            'returncode': None, 'stdout': None, 'stderr': None, 'sensitive_output': None}
        original, failure_reason = None, 'git-init-spawn-failed'
        try:
            target.mkdir(parents=True)
            intent_raw = canonical(observation) + b'\n'
            _preparation_write(target / 'intent.json', intent_raw)
            observation['intent_sha256'] = sha(intent_raw)
            observation['stage'], observation['reason'] = 'git-invocation', 'git-init-spawn-failed'
            invoked = time.perf_counter()
            stdout, stderr = None, None
            try:
                initialized = git_command(self.git, workspace, 'init', '--template=', '--quiet')
                observation['observed_argv'] = initialized.args if initialized.args == expected else None
                stdout = initialized.stdout if type(initialized.stdout) is bytes else None
                stderr = initialized.stderr if type(initialized.stderr) is bytes else None
                if type(initialized.returncode) is int:
                    observation['returncode'] = initialized.returncode
                if (initialized.args != expected or type(initialized.returncode) is not int
                        or type(initialized.stdout) is not bytes or type(initialized.stderr) is not bytes):
                    observation['reason'] = 'git-init-result-invalid'
                    raise ValueError('fixed Git result schema mismatch')
                observation.update(outcome='completed', returncode=initialized.returncode)
                stdout, stderr = initialized.stdout, initialized.stderr
                observation['reason'] = 'git-init-completed' if initialized.returncode == 0 else 'git-init-nonzero'
                if initialized.returncode:
                    original = ValueError('fixed Git initialization failed')
            except subprocess.TimeoutExpired as error:
                original = error
                observation.update(outcome='timeout', reason='git-init-timeout')
                observation['observed_argv'] = error.cmd if error.cmd == expected else None
                stdout = error.stdout if type(error.stdout) is bytes else None
                stderr = error.stderr if type(error.stderr) is bytes else None
            except BaseException as error:
                original = error
                observation['outcome'] = 'spawn-or-observation-error'
            observation['git_wall_seconds'] = time.perf_counter() - invoked
            failure_reason = observation['reason']
            from .isolated_python import SECRET
            observation['sensitive_output'] = any(SECRET.search(raw) is not None for raw in (stdout, stderr) if raw is not None)
            for name, raw in (('stdout', stdout), ('stderr', stderr)):
                if raw is not None:
                    observation[name] = {'ref': name + '.raw', 'sha256': sha(raw), 'bytes': len(raw)}
                    observation['stage'] = 'git-' + name + '-persistence'
                    observation['reason'] = 'preparation-evidence-persistence-failed'
                    _preparation_write(target / (name + '.raw'), raw)
            observation['reason'] = failure_reason
            if observation['sensitive_output']:
                observation['reason'] = 'git-init-sensitive-output'
                original = original or ValueError('private Git output rejected')
            if original is not None:
                observation['error'] = _preparation_error(original, observation['reason'])
            observation['stage'] = 'git-result-persistence'
            result_raw = canonical(dict(observation, stage='git-completed',
                                       preparation_wall_seconds=time.perf_counter() - started)) + b'\n'
            _preparation_write(target / 'result.json', result_raw)
            if original is not None:
                observation['stage'] = 'git-completed'
                raise _PreparationStageError(observation, original) from original
            return {'kind': observation['kind'], 'receipt_ref': 'preparation/git-init/result.json',
                    'receipt_sha256': sha(result_raw), 'intent_sha256': observation['intent_sha256']}
        except _PreparationStageError:
            raise
        except BaseException as error:
            # The first cause/observed process state survives a later persistence failure.
            observation['reason'] = 'preparation-evidence-persistence-failed'
            observation['persistence_error'] = _preparation_error(error, observation['reason'])
            if original is not None:
                observation['original_error'] = _preparation_error(original, failure_reason)
            raise _PreparationStageError(observation, original or error) from error

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
        self._task_validate(task)
        capability = self.binding()
        if (not isinstance(bindings, dict) or bindings.get("capability") != capability
                or any(not isinstance(bindings.get(key), str) or not bindings[key] for key in _BINDING_KEYS)):
            raise ValueError("explicit matching capability and frozen experiment bindings are required")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("owner-compiled prompt is required")
        self.artifacts.mkdir(parents=True, exist_ok=True)
        project_profile = self.config.get('broker_profile_id') is not None
        # Project dispatch is released only after a fully confirmed return.
        # The existing fsynced lock remains the fallback for every uncertain
        # cache check, including failures while constructing an observation.
        release_lock = not project_profile
        cache_context = None
        if project_profile:
            observation = {'status': 'cached-project-evidence-unknown', 'harness_request_id': None,
                'usage': None, 'cache_check_model_invoked': False, 'cache_check_replayed': False,
                'original_completed_receipt_sha256': None, 'original_completed_result_sha256': None}
            cache_context = {'active': False, 'directory': None, 'observation': observation,
                'pending': ToolCallPending('cached project evidence unknown; no replay', provider_receipt=observation)}
        lock = self.artifacts / ".tool-dispatch.lock"
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise ToolCallPending("tool dispatch active/interrupted; no automatic replay") from error
        result, call_error = None, None
        try:
            os.write(descriptor, canonical({"pid": os.getpid(), "sample_id": bindings["sample_id"]}))
            os.fsync(descriptor)
            if project_profile:
                result = self._run_locked(task, prompt, bindings, capability, run_started, cache_context=cache_context)
            else:
                result = self._run_locked(task, prompt, bindings, capability, run_started)
            release_lock = True
        except BaseException as error:
            call_error = error
            if cache_context is not None and cache_context['active']:
                # Known usage and the pending exception already exist before
                # any cache hash, grade or evidence persistence can fail.
                observation = cache_context['observation']
                pending = cache_context['pending']
                call_error = pending
                pending.retain_dispatch_lock = True
                try:
                    observation['error_type'] = type(error).__name__
                    self._remember_unknown(cache_context['directory'], observation, cache_observation=True)
                except BaseException as persistence_error:
                    observation['fence_persistence_error'] = type(persistence_error).__name__
                raise pending from error
            raise
        finally:
            try:
                os.close(descriptor)
                if release_lock and not getattr(call_error, 'retain_dispatch_lock', False):
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

    def _run_locked(self, task, prompt, bindings, capability, run_started, *, cache_context=None):
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
        key = (sha(canonical({"task": task, "prompt": prompt, "bindings": bindings, "capability": capability}))
               if cache_context is not None else None)
        loaded_cache = None
        for previous in calls.iterdir():
            if previous.is_dir():
                if cache_context is not None:
                    # Do not carry an already checked sibling's accounting
                    # context into another call's still-unread evidence.
                    cache_context['active'] = False
                    cache_context['pending'].usage = None
                try:
                    if (previous / 'cache-unknown-observation.json').exists():
                        raise ValueError('cached project evidence has an unresolved unknown observation')
                    if cache_context is not None:
                        # One exact binary read; keep its identity for both
                        # successful reuse and an unknown observation.
                        observation = _select_prior_call_context(cache_context, previous, key)
                        with (previous / 'receipt.json').open('rb') as stream:
                            previous_receipt_raw = stream.read()
                        previous_receipt = json.loads(previous_receipt_raw.decode('utf-8'))
                        prior = observation['observed_prior_call']
                        prior['reported_usage'] = previous_receipt.get('usage')
                        prior['harness_request_id'] = previous_receipt.get('harness_request_id')
                        # Existing cache reuse exposes that same turn's usage.
                        # A different requested key has no new provider turn.
                        if prior['matches_requested_cache_key']:
                            cache_context['pending'].usage = prior['reported_usage']
                            observation['usage'] = prior['reported_usage']
                        observation['harness_request_id'] = prior['harness_request_id']
                        observation['original_completed_result_sha256'] = previous_receipt.get('result_sha256')
                        prior['receipt_sha256'] = sha(previous_receipt_raw)
                        observation['original_completed_receipt_sha256'] = prior['receipt_sha256']
                    else:
                        previous_receipt = json.loads((previous / "receipt.json").read_text(encoding="utf-8"))
                    previous_result = json.loads((previous / "result.json").read_text(encoding="utf-8"))
                    if (previous_receipt.get("status") != "completed"
                            or sha(canonical(previous_result)) != previous_receipt.get("result_sha256")):
                        raise ValueError("noncompleted or corrupt result")
                    if cache_context is not None and previous.name == key:
                        loaded_cache = (previous_receipt, previous_result,
                                        observation['original_completed_receipt_sha256'], observation)
                    if cache_context is not None:
                        cache_context['active'] = False
                        cache_context['pending'].usage = None
                except (OSError, ValueError) as error:
                    raise ToolCallPending("incomplete/noncompleted tool dispatch needs reconciliation") from error
        if cache_context is None:
            key = sha(canonical({"task": task, "prompt": prompt, "bindings": bindings, "capability": capability}))
        directory = calls / key
        if directory.exists():
            if cache_context is not None:
                if loaded_cache is None:
                    raise ValueError('cached call identity was not confirmed')
                receipt, result, receipt_sha256, observation = loaded_cache
                _select_prior_call_context(cache_context, directory, key, observation)
            else:
                receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
                result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            for name, expected in receipt["artifact_sha256"].items():
                if sha((directory / name).read_bytes()) != expected:
                    raise ToolCallPending("tool receipt artifact hash mismatch; no replay")
            if sha(canonical(result)) != receipt["result_sha256"]:
                raise ToolCallPending("tool result hash mismatch; no replay")
            try:
                saved_repo = self._read_broker(directory, task, result["tool_events"])
                if sha(canonical(saved_repo.snapshot())) != result["final_files_sha256"]:
                    raise ValueError("repository changed after measured call")
                if self.config.get("broker_profile_id") is not None:
                    journal = _audit(directory / 'broker.jsonl', strict_project=True)
                    events = _project_cli_events((directory / 'stdout.raw').read_bytes())
                    final_text = _final_text(events)
                    if canonical(journal) != canonical(result['tool_events']) or final_text != result['final_response_text']:
                        raise ValueError('cached CLI journal or terminal report differs')
                    quality = self._project_quality(saved_repo, journal, events, final_text)
                    if receipt['cli_exit_code']:
                        quality['task_success'], quality['hard_pass'] = 0, False
                        quality['failures'].append('nonzero-cli-exit')
                    if quality['execution_state_unknown'] or canonical(quality) != canonical(result['quality']):
                        raise ValueError('cached project execution or quality evidence differs')
            except (OSError, ValueError, TypeError, KeyError, UnicodeError, AttributeError, RecursionError) as error:
                if self.config.get('broker_profile_id') is not None:
                    raise
                raise ToolCallPending("cached repository evidence changed; no replay") from error
            result["receipt"] = dict(receipt, artifact_directory=str(directory),
                                     receipt_sha256=(receipt_sha256 if cache_context is not None else
                                                     sha((directory / "receipt.json").read_bytes())),
                                     replayed_from_local_receipt=True,
                                     local_reuse_wall_seconds=time.perf_counter() - run_started)
            return result
        if cache_context is not None:
            # Previous turns are references, never fees for a fresh dispatch.
            cache_context['active'] = False
            cache_context['pending'].usage = None
        directory.mkdir()
        identifier = str(uuid.uuid4())
        pending = {"harness_request_id": identifier, "bindings": bindings, "task_sha256": sha(canonical(task)),
                   "prompt_sha256": sha(prompt.encode("utf-8")), "capability": capability,
                   "dispatch_state": "not_started", "model_invoked": False}
        preparation_stage, preparation_reason = 'workspace-preparation', 'preparation-step-failed'
        try:
            _atomic(directory / "pending.json", pending)
            # Keep prep results explicit: these files are outside agent scope.
            workspace = directory / "workspace"
            workspace.mkdir()
            for name, text in task["initial_files"].items():
                path = workspace.joinpath(*name.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))
            if self.config.get('broker_profile_id') is not None:
                preparation_stage, preparation_reason = 'git-source-binding', 'preparation-observation-construction-failed'
                pending['preparation_evidence'] = self._initialize_project_git(directory, workspace, pending)
            else:
                initialized = git_command(self.git, workspace, "init", "--template=", "--quiet")
                if initialized.returncode:
                    raise ValueError("fixed Git initialization failed")
            spec = {"workspace": str(workspace), "task": task, "git_binary": str(self.git),
                    "audit_file": str(directory / "broker.jsonl"), "max_tool_calls": self.config.get("max_tool_calls", 32),
                    "deadline": time.time() + self.config["timeout_seconds"]}
            if self.config.get("broker_profile_id") is not None:
                spec.update(broker_profile_id=self.config["broker_profile_id"],
                            execution_artifacts=str(directory / "execution"))
            preparation_stage, preparation_reason = 'broker-evidence-persistence', 'preparation-evidence-persistence-failed'
            _atomic(directory / "broker.spec.json", spec)
            _atomic(directory / "output.schema.json", FINAL_SCHEMA)
            (directory / "prompt.txt").write_bytes(prompt.encode("utf-8"))
            command = self._arguments(directory, directory / "broker.spec.json")
            _atomic(directory / "command.json", command)
            # One full binary/config verification immediately before dispatch.
            preparation_stage, preparation_reason = 'capability-verification', 'capability-verification-failed'
            if self._identity() != capability:
                preparation_reason = 'capability-drift'
                raise ValueError("capability changed during preparation")
            prepare_seconds = time.perf_counter() - run_started
            preparation_stage, preparation_reason = 'dispatch-intent-persistence', 'preparation-evidence-persistence-failed'
            pending.update(dispatch_state="dispatching", model_invoked=None)
            _atomic(directory / "pending.json", pending)
        except Exception as error:
            zero = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                    "measurement": "model-dispatch-not-started", "cost_usd": None}
            receipt = dict(pending, status="preparation-failed", dispatch_state="not_started", model_invoked=False,
                           usage=zero, artifact_directory=str(directory), error_type=type(error).__name__)
            if self.config.get('broker_profile_id') is not None:
                if isinstance(error, _PreparationStageError):
                    receipt['preparation_observation'] = error.observation
                    preparation_stage, preparation_reason = error.observation['stage'], error.observation['reason']
                    original = error.original
                else:
                    original = error
                receipt.update(preparation_stage=preparation_stage, preparation_reason=preparation_reason,
                               safe_error=_preparation_error(original, preparation_reason))
            try:
                _atomic(directory / "preparation-failure.json", receipt)
            except Exception as persistence_error:
                if self.config.get('broker_profile_id') is None and not isinstance(persistence_error, OSError):
                    raise
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
            if self.config.get("broker_profile_id") is not None:
                events = _project_cli_events(stdout)
            broker_events = _audit(directory / "broker.jsonl", strict_project=self.config.get("broker_profile_id") is not None)
            broker = self._read_broker(directory, task, broker_events)
            final_text = _final_text(events)
            if self.config.get("broker_profile_id") is None:
                quality = _quality(broker, broker_events, events, final_text, self.config.get("max_tool_calls", 32))
            else:
                quality = self._project_quality(broker, broker_events, events, final_text)
                if quality['execution_state_unknown']:
                    receipt = dict(pending, status="project-execution-receipt-unknown", usage=usage,
                        wall_seconds=time.perf_counter() - run_started, cli_thread_id=threads[0],
                        provider_request_id=None, model_observed=None, quality=quality)
                    self._remember_unknown(directory, receipt)
                    raise ToolCallError(receipt["status"], usage=usage, provider_receipt=receipt)
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
            if self.config.get('broker_profile_id') is not None:
                names += tuple('preparation/git-init/' + name for name in ('intent.json', 'stdout.raw', 'stderr.raw', 'result.json'))
            # A completed no-tool task is known failed evidence, with an empty broker journal.
            if not (directory / "broker.jsonl").exists():
                (directory / "broker.jsonl").write_bytes(b"")
            receipt = dict(pending, status="completed", receipt_type="codex_cli_tool_turn", usage=usage,
                           wall_seconds=result["wall_seconds"], timing=result["timing"], cli_exit_code=exit_code, cli_thread_id=threads[0],
                           provider_request_id=None, model_observed=None, provider_internal_attempts="unknown",
                           argv=command, artifact_sha256={name: sha((directory / name).read_bytes()) for name in names},
                           result_sha256=sha(canonical(result)), isolation_attested=False,
                           dispatch_state="completed", model_invoked=True,
                           application_execution=("registered-stdlib-project-fixed-container-recipes"
                               if self.config.get("broker_profile_id") is not None else "excluded-static-contracts-only"))
            _atomic(directory / "receipt.json", receipt)
        except ToolCallError:
            raise
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
