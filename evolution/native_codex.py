"""Explicit real-model capability through an already authenticated Codex CLI.

This repository-only adapter never reads authentication files, installs a host,
changes host configuration, or silently selects a model. ``UPG_NATIVE_CONFIG``
must name an owner-supplied JSON configuration. CLI thread receipts are labelled
as such: they are not provider request IDs or independent isolation attestations.
Unknown calls leave a durable fence; restarting an optimizer never replays them.
"""
from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
import hashlib
import importlib
import inspect
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import time
import uuid

from .contracts import canonical_bytes, digest

VERSION = "1"
_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_KEYS = {"binary", "model", "effort", "artifact_root", "timeout_seconds",
                "grader", "cli_version"}


class NativeCallError(RuntimeError):
    def __init__(self, message, *, usage=None, provider_receipt=None):
        super().__init__(message)
        self.usage = usage
        self.provider_receipt = provider_receipt


class NativeCallPending(NativeCallError):
    """A prior call needs independent reconciliation before another dispatch."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical_bytes(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _text_files(root, files):
    if not isinstance(files, dict) or not files:
        raise ValueError("exact UTF-8 source/runtime mapping is required")
    for name, content in files.items():
        if not isinstance(name, str) or not isinstance(content, str):
            raise ValueError("source paths and contents must be strings")
        relative = PurePosixPath(name)
        if (not name or "\\" in name or ":" in name or relative.is_absolute()
                or any(part in {".", "..", ""} for part in name.split("/"))):
            raise ValueError("unsafe source/runtime path")
        destination = root.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content.encode("utf-8"))


def _usage(events):
    completed = [event for event in events if event.get("type") == "turn.completed"]
    if len(completed) != 1 or not isinstance(completed[0].get("usage"), dict):
        return None
    raw = completed[0]["usage"]
    values = [raw.get("input_tokens"), raw.get("output_tokens")]
    if any(type(value) is not int or value < 0 for value in values):
        return None
    result = {"input_tokens": values[0], "output_tokens": values[1],
              "total_tokens": sum(values), "cost_usd": None}
    for target, key in (("cached_tokens", "cached_input_tokens"),
                        ("reasoning_tokens", "reasoning_output_tokens"),
                        ("cache_write_input_tokens", "cache_write_input_tokens")):
        value = raw.get(key)
        result[target] = value if type(value) is int and value >= 0 else None
    if result["cached_tokens"] is not None and result["cached_tokens"] > values[0]:
        return None
    if result["reasoning_tokens"] is not None and result["reasoning_tokens"] > values[1]:
        return None
    result["measurement"] = "actual-codex-cli-turn.completed"
    return result


def _events(stdout):
    events = []
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _bytes(value):
    return value if isinstance(value, bytes) else (value or "").encode("utf-8")


def _grader(spec):
    if not isinstance(spec, str) or spec.count(":") != 1:
        raise ValueError("native config must register a trusted grader module:function")
    module_name, function_name = spec.split(":")
    if not module_name or not function_name or not all(
            part.isidentifier() for part in module_name.split(".") + [function_name]):
        raise ValueError("invalid trusted grader reference")
    function = getattr(importlib.import_module(module_name), function_name)
    if not callable(function):
        raise ValueError("registered grader is not callable")
    file = inspect.getsourcefile(function)
    if not file or not Path(file).is_file():
        raise ValueError("registered grader requires inspectable executable source")
    return function, {"reference": spec, "source_sha256": _sha(Path(file).read_bytes())}


class NativeCodex:
    """One explicit native CLI capability with persistent local call evidence."""

    def __init__(self, config):
        if not isinstance(config, dict) or set(config) - _CONFIG_KEYS:
            raise ValueError("native config contains unsupported fields; no secrets are accepted")
        for name in ("binary", "model", "effort", "artifact_root", "timeout_seconds"):
            if name not in config:
                raise ValueError("native config requires " + name)
        self.config = dict(config)
        self.binary = Path(config["binary"])
        self.artifacts = Path(config["artifact_root"])
        if not self.binary.is_absolute() or not self.binary.is_file():
            raise ValueError("native config binary must be a registered absolute file")
        if not self.artifacts.is_absolute():
            raise ValueError("native artifact_root must be absolute")
        if not isinstance(config["model"], str) or not config["model"].strip():
            raise ValueError("native model must be explicitly registered")
        if config["effort"] not in {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}:
            raise ValueError("unsupported explicit reasoning effort")
        seconds = config["timeout_seconds"]
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 3600:
            raise ValueError("native timeout_seconds must be finite in (0, 3600]")
        if "cli_version" in config and not isinstance(config["cli_version"], str):
            raise ValueError("cli_version must be a declared string")
        self.binary_sha256 = _sha(self.binary.read_bytes())
        self.config_sha256 = digest(dict(config, binary_sha256=self.binary_sha256))
        self._preparation_cache = OrderedDict()
        self._dispatch_blocked = False

    @classmethod
    def from_environment(cls):
        configured = os.environ.get("UPG_NATIVE_CONFIG")
        if not configured or not Path(configured).is_absolute():
            raise ValueError("UPG_NATIVE_CONFIG must explicitly name an absolute JSON config path")
        config = json.loads(Path(configured).read_text(encoding="utf-8"))
        return _configured_client(canonical_bytes(config).decode("utf-8"))

    def _registered_binding(self):
        """Constructor anchor for preparation; dispatch still verifies binary bytes."""
        if digest(dict(self.config, binary_sha256=self.binary_sha256)) != self.config_sha256:
            raise ValueError("native configuration changed after registration")
        unused, grader_identity = _grader(self.config.get("grader"))
        return {"native_config_sha256": self.config_sha256, "grader": grader_identity}

    def binding(self):
        """Read the exact capability identity to preregister in runner_config."""
        binary_sha256 = _sha(self.binary.read_bytes())
        if (binary_sha256 != self.binary_sha256 or
                digest(dict(self.config, binary_sha256=binary_sha256)) != self.config_sha256):
            raise ValueError("native configuration or binary changed after registration")
        return self._registered_binding()

    def _prepare(self, source, artifact, context):
        """Cache only deterministic local preparation, never model observations."""
        # Digests detect changed bytes inside this trusted Python process;
        # process memory and its cache anchors are not an authorization boundary.
        started = time.perf_counter()
        key = digest({"version": 1, "source": source, "artifact": artifact, "context": context,
                      "python": {"executable": sys.executable, "version": sys.version}})
        phases = {"cache_hit": key in self._preparation_cache, "compile_seconds": 0.0,
                  "plan_seconds": 0.0, "cache_verify_seconds": 0.0}
        if key not in self._preparation_cache:
            self.artifacts.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="upg-native-", dir=self.artifacts) as temporary:
                isolated = Path(temporary)
                _text_files(isolated / "governance-src", source)
                runtime = isolated / "universal-project-governance"
                if artifact.get("runtime") is not None:
                    _text_files(runtime, artifact["runtime"])
                else:
                    compiler = isolated / "compiler/compile_governance.py"
                    compiler.parent.mkdir()
                    compiler.write_bytes(artifact["compiler"].encode("utf-8"))
                    (isolated / "LICENSE").write_bytes(artifact["license"].encode("utf-8"))
                    phase_started = time.perf_counter()
                    compiled = subprocess.run([sys.executable, "-B", str(compiler), "--repo", str(isolated),
                                               "--write", "--confirm-generated-runtime-update"],
                                              capture_output=True, timeout=60, check=False)
                    phases["compile_seconds"] = time.perf_counter() - phase_started
                    if compiled.returncode:
                        raise ValueError("exact-source native runtime compilation failed")
                context_path = isolated / "context.json"
                context_path.write_bytes(canonical_bytes(context))
                phase_started = time.perf_counter()
                planned = subprocess.run([sys.executable, "-B", str(runtime / "scripts/plan_governance.py"),
                                          "--context", str(context_path), "--json"],
                                         capture_output=True, timeout=30, check=False)
                phases["plan_seconds"] = time.perf_counter() - phase_started
                if planned.returncode:
                    raise ValueError("exact-source native governance planning failed")
                files = {p.relative_to(runtime).as_posix(): p.read_bytes().decode("utf-8")
                         for p in sorted(runtime.rglob("*")) if p.is_file()}
                payload = {"runtime": files, "plan": json.loads(planned.stdout)}
                blob = canonical_bytes(payload)
            self._preparation_cache[key] = (blob, _sha(blob))
            while len(self._preparation_cache) > 32:
                self._preparation_cache.popitem(last=False)
        phase_started = time.perf_counter()
        blob, expected = self._preparation_cache[key]
        if not isinstance(blob, bytes) or _sha(blob) != expected:
            raise ValueError("native preparation cache artifact hash mismatch")
        prepared = json.loads(blob)
        runtime_identity = digest({name: _sha(text.encode("utf-8")) for name, text in prepared["runtime"].items()})
        self._preparation_cache.move_to_end(key)
        phases["cache_verify_seconds"] = time.perf_counter() - phase_started
        phases["prepare_seconds"] = time.perf_counter() - started
        skill = prepared["runtime"]["SKILL.md"].replace("\r\n", "\n").replace("\r", "\n")
        return skill, prepared["plan"], runtime_identity, phases

    def _unknown(self, directory, receipt):
        # Set this before evidence I/O: a full/unwritable disk must never permit
        # a second launch or erase usage already observed in completed stdout.
        self._dispatch_blocked = True
        receipt["dispatch_evidence_unconfirmed"] = True
        try:
            _atomic(directory / "receipt.json", receipt)
        except OSError as error:
            receipt["receipt_persistence_error"] = type(error).__name__ + ": " + str(error)[:240]
        # The unresolved call blocks the entire configured experiment root,
        # including retries whose prompts or candidate identifiers differ.
        fence = self.artifacts / "UNKNOWN_CALL.json"
        try:
            with fence.open("xb") as stream:
                stream.write(canonical_bytes({"request_id": receipt["harness_request_id"],
                                             "call_key": directory.name,
                                             "reason": receipt["status"]}) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
        except OSError as error:
            receipt["fence_persistence_error"] = type(error).__name__ + ": " + str(error)[:240]

    def _call(self, *, key, prompt, bindings, output_schema=None, local_timings=None):
        if self._dispatch_blocked:
            raise NativeCallPending("native evidence is unresolved in this process; no automatic replay")
        self.artifacts.mkdir(parents=True, exist_ok=True)
        lock = self.artifacts / ".native-dispatch.lock"
        result, call_error = None, None
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise NativeCallPending("native dispatch is active or interrupted; no automatic replay") from error
        try:
            os.write(descriptor, canonical_bytes({"pid": os.getpid(), "key_sha256": digest(key)}))
            os.fsync(descriptor)
            result = self._locked_call(key=key, prompt=prompt, bindings=bindings, output_schema=output_schema,
                                       local_timings=local_timings)
        except BaseException as error:
            call_error = error
            raise
        finally:
            try:
                os.close(descriptor)
                if not self._dispatch_blocked:
                    lock.unlink()
            except OSError as error:
                self._dispatch_blocked = True
                cleanup = type(error).__name__ + ": " + str(error)[:240]
                if result is not None:
                    receipt = dict(result["receipt"], status="dispatch-lock-cleanup-failed",
                                   original_status=result["receipt"]["status"], dispatch_lock_cleanup_error=cleanup)
                    directory = self.artifacts / receipt["raw_artifact_reference"]
                    self._unknown(directory, receipt)
                    raise NativeCallError(receipt["status"], usage=result["usage"],
                                          provider_receipt=receipt) from error
                if getattr(call_error, "provider_receipt", None) is not None:
                    call_error.provider_receipt["dispatch_lock_cleanup_error"] = cleanup
        return result

    def _locked_call(self, *, key, prompt, bindings, output_schema=None, local_timings=None):
        if (self.artifacts / "UNKNOWN_CALL.json").exists():
            raise NativeCallPending("unresolved native call: independently reconcile UNKNOWN_CALL.json before dispatch")
        verify_started = time.perf_counter()
        capability = self.binding()
        capability_verify_seconds = time.perf_counter() - verify_started
        if "capability" in bindings and bindings["capability"] != capability:
            raise ValueError("native capability changed while preparing this call")
        frozen = self.artifacts / "CAPABILITY.json"
        if frozen.exists():
            if json.loads(frozen.read_text(encoding="utf-8")) != capability:
                raise ValueError("native artifact root is frozen to a different capability")
        else:
            _atomic(frozen, capability)
        calls = self.artifacts / "calls"
        calls.mkdir(exist_ok=True)
        directory = calls / digest({"key": key, "config": self.config_sha256,
                                    "prompt": prompt, "schema": output_schema})
        for previous in calls.iterdir():
            if previous.is_dir() and (not (previous / "result.json").is_file()
                                      or not (previous / "receipt.json").is_file()):
                raise NativeCallPending("an interrupted native dispatch needs reconciliation; no automatic replay")
            if previous.is_dir():
                try:
                    prior_receipt = json.loads((previous / "receipt.json").read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    raise NativeCallPending("prior native receipt is unreadable; no automatic replay") from error
                if prior_receipt.get("dispatch_evidence_unconfirmed") is True:
                    raise NativeCallPending("prior native evidence is unresolved; no automatic replay")
        try:
            directory.mkdir()
        except FileExistsError:
            result_file = directory / "result.json"
            receipt_file = directory / "receipt.json"
            if not result_file.is_file() or not receipt_file.is_file():
                raise NativeCallPending("native call has a durable pending fence; no automatic replay")
            receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
            result = json.loads(result_file.read_text(encoding="utf-8"))
            for name in ("stdout", "stderr"):
                raw = directory / (name + ".raw")
                if not raw.is_file() or _sha(raw.read_bytes()) != receipt[name + "_sha256"]:
                    raise NativeCallPending("native receipt artifact hash mismatch; no automatic replay")
            if digest(result) != receipt.get("result_sha256"):
                raise NativeCallPending("native result hash mismatch; no automatic replay")
            if result["status"] != "completed":
                raise NativeCallError("prior native call failed; no automatic retry",
                                      usage=result.get("usage"), provider_receipt=receipt)
            result["receipt"] = dict(receipt, replayed_from_local_receipt=True)
            result["dispatch_timings"] = {"capability_verify_seconds": capability_verify_seconds}
            return result

        request_id = str(uuid.uuid4())
        _atomic(directory / "pending.json", {"harness_request_id": request_id,
                                              "config_sha256": self.config_sha256,
                                              "bindings": bindings, "prompt_sha256": _sha(prompt.encode("utf-8"))})
        (directory / "prompt.txt").write_bytes(prompt.encode("utf-8"))
        arguments = [str(self.binary), "--ask-for-approval", "never", "exec", "--cd", str(directory),
                     "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--json",
                     "--sandbox", "read-only", "--model", self.config["model"],
                     "-c", 'model_reasoning_effort="%s"' % self.config["effort"],
                     "-c", "features.shell_tool=false", "-c", 'web_search="disabled"',
                     "-c", "hide_agent_reasoning=true"]
        if output_schema is not None:
            if not isinstance(output_schema, dict):
                raise ValueError("task output_schema must be an object")
            schema_path = directory / "output.schema.json"
            schema_path.write_bytes(canonical_bytes(output_schema))
            arguments.extend(["--output-schema", str(schema_path)])
        arguments.append("-")
        started = time.perf_counter()
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        stdout, stderr, exit_code, failure = b"", b"", None, None
        dispatch_error = None
        try:
            completed = subprocess.run(arguments, input=prompt.encode("utf-8"),
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=self.config["timeout_seconds"], check=False)
            stdout, stderr, exit_code = _bytes(completed.stdout), _bytes(completed.stderr), completed.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, failure = _bytes(error.stdout), _bytes(error.stderr), "timeout-unknown-provider-state"
            dispatch_error = error
        except BaseException as error:
            failure = type(error).__name__ + "-dispatch-state-unconfirmed"
            dispatch_error = error
            stdout, stderr = _bytes(getattr(error, "stdout", None)), _bytes(getattr(error, "stderr", None))
        elapsed = time.perf_counter() - started
        # Mechanical accounting precedes every post-dispatch evidence write.
        # A unique completed turn is measured usage, never proof of success or
        # completeness of failed/partial provider-side attempts.
        events = _events(stdout)
        usage = _usage(events)
        threads = [event.get("thread_id") for event in events if event.get("type") == "thread.started"]
        messages = [event["item"].get("text", "") for event in events
                    if event.get("type") == "item.completed" and isinstance(event.get("item"), dict)
                    and event["item"].get("type") == "agent_message"]
        tools = [event["item"].get("type") for event in events
                 if event.get("type") == "item.completed" and isinstance(event.get("item"), dict)
                 and event["item"].get("type") in {"command_execution", "mcp_tool_call", "file_change", "web_search"}]
        success = failure is None and exit_code == 0 and usage is not None and len(threads) == 1 and bool(messages) and not tools
        result = {"status": "completed" if success else "failed", "text": messages[-1] if messages else "",
                  "usage": usage, "wall_seconds": elapsed}
        receipt = {"schema_version": 1, "receipt_type": "codex_cli_thread", "adapter_version": VERSION,
                   "harness_request_id": request_id, "cli_thread_id": threads[0] if len(threads) == 1 else None,
                   "provider_request_id": None, "model_requested": self.config["model"], "model_observed": None,
                   "effort": self.config["effort"], "binary_sha256": self.binary_sha256,
                   "cli_version_declared": self.config.get("cli_version"), "config_sha256": self.config_sha256,
                   "started_at": started_at, "wall_seconds": elapsed, "exit_code": exit_code,
                   "status": "completed" if success else failure or "failed-native-response",
                   "usage": usage, "tool_calls": len(tools), "tool_types": tools,
                   "bindings": bindings, "prompt_sha256": _sha(prompt.encode("utf-8")),
                   "stdout_sha256": _sha(stdout), "stderr_sha256": _sha(stderr),
                   "raw_artifact_reference": "calls/" + directory.name,
                   "result_sha256": digest(result), "sandbox": "read-only", "ephemeral": True,
                   "isolation_attested": False, "provider_token_precap_enforced": False,
                   "adapter_retries": 0, "provider_retry_configuration_verified": False,
                   "retry_accounting_limit": "native provider retry configuration is not independently verified; usage is the reported completed turn",
                   "replayed_from_local_receipt": False}
        receipt["local_timings"] = dict(local_timings or {}, cli_seconds=elapsed,
                                        capability_verify_seconds=capability_verify_seconds)
        if dispatch_error is not None:
            receipt["dispatch_error"] = type(dispatch_error).__name__ + ": " + str(dispatch_error)[:240]
        try:
            (directory / "stdout.raw").write_bytes(stdout)
            (directory / "stderr.raw").write_bytes(stderr)
        except OSError as error:
            receipt.update(original_status=receipt["status"], status="raw-evidence-persistence-failed",
                           raw_persistence_error=type(error).__name__ + ": " + str(error)[:240])
            self._unknown(directory, receipt)
            if dispatch_error is not None and not isinstance(dispatch_error, Exception):
                raise dispatch_error
            raise NativeCallError(receipt["status"], usage=usage, provider_receipt=receipt) from error
        if failure is not None or usage is None or len(threads) != 1:
            self._unknown(directory, receipt)
            if dispatch_error is not None and not isinstance(dispatch_error, Exception):
                raise dispatch_error
            raise NativeCallError(receipt["status"], usage=usage, provider_receipt=receipt) from dispatch_error
        try:
            _atomic(directory / "result.json", result)
            _atomic(directory / "receipt.json", receipt)
        except OSError as error:
            receipt.update(original_status=receipt["status"], status="post-dispatch-evidence-unconfirmed",
                           evidence_persistence_error=type(error).__name__ + ": " + str(error)[:240])
            self._unknown(directory, receipt)
            raise NativeCallError(receipt["status"], usage=usage, provider_receipt=receipt) from error
        if not success:
            raise NativeCallError("native response failed or used forbidden tools", usage=usage, provider_receipt=receipt)
        result["receipt"] = receipt
        result["dispatch_timings"] = {"capability_verify_seconds": capability_verify_seconds}
        return result

    def backend(self, *, system, user, max_completion_tokens, stage="optimizer", **unused):
        if not isinstance(system, str) or not isinstance(user, str):
            raise ValueError("native learner requires exact system/user strings")
        if type(max_completion_tokens) is not int or max_completion_tokens <= 0:
            raise ValueError("max_completion_tokens must be positive")
        # The native CLI exposes no per-turn output token hard cap. This requested
        # limit is disclosed as a prompt instruction, never an enforced ceiling.
        prompt = ("Use no tools and do not read or modify files. Return only the exact output required by the following optimizer stage. "
                  "Requested completion budget: %d tokens (instruction only).\n\n" % max_completion_tokens
                  + canonical_bytes({"stage": stage, "system": system, "user": user}).decode("utf-8"))
        capability = self._registered_binding()
        # Separate ablation arms owe the cost of their own learning calls.
        # Interrupted learning is fenced by the controller and this adapter.
        invocation_id = str(uuid.uuid4())
        result = self._call(key={"kind": "learner", "invocation_id": invocation_id, "stage": stage, "system": system, "user": user,
                                 "completion_request": max_completion_tokens, "capability": capability}, prompt=prompt,
                            bindings={"kind": "learner", "invocation_id": invocation_id, "stage": stage, "capability": capability})
        usage = dict(result["usage"], native_receipt=result["receipt"], wall_seconds=result["wall_seconds"])
        return result["text"], usage

    def runner(self, request):
        started = time.perf_counter()
        if not isinstance(request, dict) or not isinstance(request.get("source"), dict):
            raise ValueError("native runner requires exact candidate source")
        registered = request.get("config")
        capability = self._registered_binding()
        if not isinstance(registered, dict) or any(
                registered.get(key) != value for key, value in capability.items()):
            raise ValueError("runner_config must match the frozen native configuration and grader")
        campaign_id = registered.get("campaign_id")
        if campaign_id is not None and (not isinstance(campaign_id, str) or not campaign_id.strip()):
            raise ValueError("native campaign_id must be a nonempty string when supplied")
        source = request["source"]
        source_identity = digest(source)
        if request.get("source_sha256") != source_identity:
            raise ValueError("native source hash does not match exact execution source")
        if request.get("model") not in {None, "unknown", self.config["model"]}:
            raise ValueError("runner model differs from registered native model")
        candidate = request.get("candidate_id")
        if not isinstance(candidate, str) or len(candidate) != 64 or any(x not in "0123456789abcdef" for x in candidate):
            raise ValueError("native runner requires exact candidate SHA-256")
        task = request.get("task")
        if not isinstance(task, dict) or not isinstance(task.get("prompt"), str):
            raise ValueError("native task requires an explicit prompt")
        if not isinstance(task.get("id"), str) or not task["id"].strip():
            raise ValueError("native task requires an explicit sample task id")
        context = task.get("plan_context", task.get("context"))
        if not isinstance(context, dict):
            raise ValueError("native task requires plan_context")
        registered_grader = self.config.get("grader")
        if "grader" in task and task["grader"] != registered_grader:
            raise ValueError("task cannot select an unregistered grader")
        grader, grader_identity = _grader(registered_grader)
        if grader_identity != capability["grader"]:
            raise ValueError("native grader changed while preparing this task")
        artifact = request.get("execution_artifact")
        if not isinstance(artifact, dict) or not isinstance(artifact.get("compiler"), str) or not isinstance(artifact.get("license"), str):
            raise ValueError("native runner requires pinned execution compiler and license")
        skill, plan, runtime_identity, local_timings = self._prepare(source, artifact, context)
        bindings = {"kind": "task", "source_sha256": source_identity, "candidate_id": candidate,
                    "task_sha256": digest(task), "runtime_sha256": runtime_identity,
                    "execution_artifact_sha256": digest(artifact), "grader": grader_identity,
                    "capability": capability, "campaign_id": campaign_id, "sample_id": task["id"]}
        payload = {"governance_skill": skill, "governance_plan": plan, "task": task["prompt"],
                   "task_payload": task.get("payload"), "output_contract": task.get("output_schema")}
        prompt = ("Perform the task using the supplied governance Skill and compiled task plan. All required project files and facts are in the task payload. "
                  "Use no tools, read no other files, and change no external state. Return only the task's requested JSON response.\n\n"
                  + canonical_bytes(payload).decode("utf-8"))
        result = self._call(key={"kind": "task", "cache_key": request.get("cache_key"),
                                 "attempt": request.get("attempt", 0), "bindings": bindings},
                            prompt=prompt, bindings=bindings, output_schema=task.get("output_schema"),
                            local_timings=local_timings)
        try:
            parsed = json.loads(result["text"])
        except json.JSONDecodeError:
            parsed = None
        graded_request = {"task": task, "response_text": result["text"], "response_json": parsed,
                          "plan": plan, "source_sha256": source_identity, "candidate_id": candidate,
                          "usage": result["usage"], "wall_seconds": result["wall_seconds"],
                          "receipt": result["receipt"]}
        grade_started = time.perf_counter()
        try:
            outcome = grader(graded_request)
            if not isinstance(outcome, dict):
                raise ValueError("grader outcome must be an object")
            for field in ("loss", "hard", "soft"):
                value = outcome.get(field)
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("grader must report finite " + field)
            if outcome["hard"] not in (0, 1) or not 0 <= outcome["soft"] <= 1:
                raise ValueError("grader hard/soft scores are outside their contracts")
        except Exception as error:
            raise NativeCallError("trusted grader failed: " + type(error).__name__, usage=result["usage"],
                                  provider_receipt=result["receipt"]) from error
        local_timings.update(grade_seconds=time.perf_counter() - grade_started,
                             cli_seconds=result["wall_seconds"], total_seconds=time.perf_counter() - started,
                             capability_verify_seconds=result.get("dispatch_timings", {}).get("capability_verify_seconds"))
        return {"status": "completed", "usage": result["usage"], "provider_receipt": result["receipt"],
                "outcome": outcome, "native_wall_seconds": result["wall_seconds"],
                "local_timings": local_timings}


@lru_cache(maxsize=4)
def _configured_client(config_json):
    return NativeCodex(json.loads(config_json))


def runner(request):
    """Evaluator callback; capability is explicitly selected by UPG_NATIVE_CONFIG."""
    started = time.perf_counter()
    client = NativeCodex.from_environment()
    setup_seconds = time.perf_counter() - started
    result = client.runner(request)
    result["local_timings"].update(client_setup_seconds=setup_seconds,
                                   total_seconds=time.perf_counter() - started)
    return result


def backend(**request):
    """UPG reflection callback returning the unmodified response and actual usage."""
    return NativeCodex.from_environment().backend(**request)
