"""Prepared private worker, not a registered protocol or an approved dispatch.

Default invocation verifies pinned files and exits without a model call. Actual
dispatch additionally requires an exact protocol-SHA argument and JSONL calls
from a separately frozen, durable, serial parent collector. No host config or
authentication files are read, copied or changed by this harness.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import random
import runpy
import sys
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8"))


def matched_order(models, tasks, seed=19012):
    """Four preparation misses before four reuses, balanced inside each model."""
    if len(models) != 2 or len(set(models)) != 2 or len(tasks) != 8:
        raise ValueError("this prepared design requires two models and eight tasks")
    groups = {}
    ids = set()
    for task in tasks:
        if task["id"] in ids or task["context_phase"] not in {"cold", "repeat"}:
            raise ValueError("duplicate task or invalid context phase")
        ids.add(task["id"])
        group = groups.setdefault(task["context_group"], {})
        if task["context_phase"] in group:
            raise ValueError("duplicate task in context phase")
        group[task["context_phase"]] = task
    if len(groups) != 4 or any(set(group) != {"cold", "repeat"} for group in groups.values()):
        raise ValueError("four context groups each require one cold and one repeat task")
    if len({digest(group["cold"]["plan_context"]) for group in groups.values()}) != 4:
        raise ValueError("first-stage contexts must be distinct")
    for group in groups.values():
        if group["cold"]["plan_context"] != group["repeat"]["plan_context"]:
            raise ValueError("repeat task must preserve the exact context")
        for key in ("payload", "artifact_checks"):
            if group["cold"][key] == group["repeat"][key]:
                raise ValueError("repeat requires a fresh artifact fixture and positive target")
    rng, order = random.Random(seed), []
    for phase in ("cold", "repeat"):
        pairs = [(model, name) for model in models for name in sorted(groups)]
        rng.shuffle(pairs)
        first, seen = {model: rng.randrange(2) for model in models}, dict.fromkeys(models, 0)
        for model, name in pairs:
            start = (first[model] + seen[model]) % 2
            seen[model] += 1
            conditions = ("control", "treatment") if start == 0 else ("treatment", "control")
            for condition in conditions:
                order.append({"model": model, "task_id": groups[name][phase]["id"],
                              "context_group": name, "context_phase": phase,
                              "condition": condition, "sample_index": len(order)})
    return order


def emit(value):
    sys.stdout.buffer.write((json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii"))
    sys.stdout.buffer.flush()


def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--allow-dispatch-protocol-sha256")
    args = parser.parse_args()
    raw_manifest = Path(args.manifest).read_bytes()
    if sha(raw_manifest) != args.manifest_sha256:
        raise ValueError("worker manifest changed")
    manifest = json.loads(raw_manifest)
    if sha(Path(__file__).read_bytes()) != manifest["worker_sha256"]:
        raise ValueError("worker source changed after registration")
    snapshot = Path(manifest["snapshot_directory"])
    if not snapshot.is_absolute():
        raise ValueError("snapshot directory must be absolute")
    required = {"evolution/__init__.py", "evolution/contracts.py", "evolution/native_codex.py",
                "upg_native_common_grader.py"}
    if set(manifest["files"]) != required:
        raise ValueError("exact minimal isolated dependency set is required")
    for relative, expected in manifest["files"].items():
        if sha((snapshot / relative).read_bytes()) != expected:
            raise ValueError("snapshot dependency changed: " + relative)
    config_path = Path(manifest["config_path"])
    if not config_path.is_absolute():
        raise ValueError("explicit absolute config path is required")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if digest(config) != manifest["config_sha256"]:
        raise ValueError("configuration differs from registration")
    if (set(config) - {"binary", "model", "effort", "artifact_root", "timeout_seconds", "grader", "cli_version"}
            or config.get("grader") != "upg_native_common_grader:grade"):
        raise ValueError("only the pinned common grader and native config fields are supported")
    if any(name == "evolution" or name.startswith("evolution.") for name in sys.modules):
        raise ValueError("worker was contaminated by another engine namespace")
    sys.path.insert(0, str(snapshot))
    native = importlib.import_module("evolution.native_codex")
    contracts = importlib.import_module("evolution.contracts")
    common = importlib.import_module("upg_native_common_grader")
    if any(Path(module.__file__).resolve() != (snapshot / relative).resolve() for module, relative in (
            (native, "evolution/native_codex.py"), (contracts, "evolution/contracts.py"),
            (common, "upg_native_common_grader.py"))):
        raise ValueError("engine/grader import escaped its pinned snapshot")
    transport_path=Path(manifest["transport"]["path"])
    if not transport_path.is_absolute() or sha(transport_path.read_bytes())!=manifest["transport"]["source_sha256"]:
        raise ValueError("common transport instrumentation source changed")
    profile=manifest["transport"]["profile_source"]
    profile_path=Path(profile["path"])
    if (not profile_path.is_absolute() or profile_path.resolve()!=transport_path.resolve().parents[2]/"cli_transport.py"
            or sha(profile_path.read_bytes())!=profile["sha256"]):
        raise ValueError("common transport profile source changed")
    transport=runpy.run_path(str(transport_path))
    # Installation itself performs no config/auth read, client construction or CLI call.
    transport_state=transport["install"](native,config,manifest["transport"]) if dispatch_allowed(args,manifest) else None
    # Importing modules does not construct a client or warm the public LRU cache.
    os.environ["UPG_NATIVE_CONFIG"] = str(config_path)
    dispatch = args.allow_dispatch_protocol_sha256
    if dispatch is not None and dispatch != manifest["protocol_sha256"]:
        raise ValueError("dispatch protocol is not the registered manifest")
    emit({"type": "ready", "verification_only": dispatch is None,
          "protocol_sha256": manifest["protocol_sha256"], "model_requested": config["model"],
          "manifest_sha256": args.manifest_sha256,
          "transport_source_sha256":manifest["transport"]["source_sha256"],
          "transport_profile_source_sha256":profile["sha256"],
          "transport_profile_sha256":digest(manifest["transport"]["profile"]),
          "worker_ready_seconds": time.perf_counter() - started,
          "measurement": "worker initialization only; parent separately measures process startup"})
    if dispatch is None:
        return 0
    expected_order = manifest["task_order"]
    if len(expected_order) != 8 or len(set(expected_order)) != 8:
        raise ValueError("worker requires its frozen eight-task order")
    # Read the same strict ASCII JSONL wire the parent writes; never let the
    # host text decoder introduce surrogate escapes into registered sources.
    for index, line in enumerate(sys.stdin.buffer):
        command = json.loads(line.decode("ascii"))
        request = command["request"]
        task = request["task"]
        if (index >= len(expected_order) or command.get("protocol_sha256") != dispatch
                or task["id"] != expected_order[index]
                or digest(task) != manifest["task_sha256"][task["id"]]
                or request["config"] != manifest["runner_config"]
                or request["model"] != config["model"]
                or request["source_sha256"] != manifest["source_sha256"]
                or digest(request["source"]) != manifest["source_sha256"]
                or request["candidate_id"] != manifest["candidate_id"]
                or digest(request["execution_artifact"]) != manifest["execution_artifact_sha256"]
                or "runtime" in request["execution_artifact"]):
            raise ValueError("dispatch input differs from frozen worker registration")
        callback_started = time.perf_counter()
        transport_state["sample_id"]=command["sample_id"]
        transport_start=len(transport_state["records"])
        try:
            result = native.runner(request)  # Exact public release callback, never a preconstructed client.
        except BaseException as error:
            emit({"type": "call_error", "sample_id": command["sample_id"],
                  "error_type": type(error).__name__, "error": str(error),
                  "usage": getattr(error, "usage", None),
                  "provider_receipt": getattr(error, "provider_receipt", None),
                  "transport_receipts":transport_state["records"][transport_start:],
                  "callback_wall_seconds": time.perf_counter() - callback_started,
                  "automatic_retry": False})
            return 70
        emit({"type": "call_result", "sample_id": command["sample_id"], "result": result,
              "transport_receipts":transport_state["records"][transport_start:],
              "callback_wall_seconds": time.perf_counter() - callback_started,
              "first_public_callback": index == 0, "context_phase": manifest["task_phases"][task["id"]],
              "measurement_end": "after-public-callback-return-before-worker-JSON-publication"})
    return 0


def dispatch_allowed(args,manifest):
    value=args.allow_dispatch_protocol_sha256
    if value is not None and value!=manifest["protocol_sha256"]:raise ValueError("dispatch protocol is not the registered manifest")
    return value is not None


if __name__ == "__main__":
    raise SystemExit(main())
