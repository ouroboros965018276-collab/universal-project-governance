"""Private native comparison collector; default CLI invocation is verification-only."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import runpy
import subprocess
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"
worker_api = runpy.run_path(str(WORKER))
transport_api=runpy.run_path(str(HERE/"transport.py"))
digest, sha = worker_api["digest"], worker_api["sha"]


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def validate(spec):
    models=spec["models"]
    reserved = {"CON", "PRN", "AUX", "NUL"} | {prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)}
    if (not isinstance(models,list) or len(models)!=2 or any(not isinstance(model,str) or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',model)
            or model.endswith('.') or model.split('.')[0].upper() in reserved for model in models)
            or len(set(models))!=2):
        raise ValueError("models must be exactly two unique safe exact catalog IDs")
    if not isinstance(spec["protocol_id"],str) or not re.fullmatch('[a-z][a-z0-9-]{0,95}',spec["protocol_id"]):
        raise ValueError("an explicit safe protocol id is required")
    if spec["budget"] != {"model_calls": 32, "tokens": 1500000, "wall_seconds": 7200}:
        raise ValueError("native campaign budget differs from the reviewed design")
    if (spec["seed"] != 19012
            or spec["acceptance"] != {"primary": "full-public-callback-time-and-quality", "callback_time_ci_upper_exclusive": 1.0,
                                      "all_quality_required": True, "all_fresh_calls_required": True}):
        raise ValueError("model/order/acceptance differs from the prespecified A estimand")
    tasks = spec["tasks"]
    if digest(tasks) != spec["task_manifest_sha256"] or any(key != task["id"] for key, task in tasks.items()):
        raise ValueError("private task manifest changed")
    order = worker_api["matched_order"](spec["models"], list(tasks.values()), spec["seed"])
    if order != spec["order"] or digest(order) != spec["order_sha256"]:
        raise ValueError("matched context order changed")
    for name, expected in spec["harness_files"].items():
        if sha(Path(name).read_bytes()) != expected: raise ValueError("harness source changed")
    if spec["transport"]["profile"]!=transport_api["PROFILE"] or sha(Path(spec["transport"]["path"]).read_bytes())!=spec["transport"]["source_sha256"]:
        raise ValueError("common child transport differs from registration")
    profile=spec["transport"]["profile_source"];profile_path=transport_api["PROFILE_SOURCE"]
    if (Path(profile["path"]).resolve()!=profile_path or sha(profile_path.read_bytes())!=profile["sha256"]
            or spec["harness_files"].get(str(profile_path))!=profile["sha256"]):
        raise ValueError("common child transport profile differs from registration")
    catalog_bytes=Path(spec["model_catalog"]["path"]).read_bytes()
    if sha(catalog_bytes)!=spec["model_catalog"]["sha256"]:raise ValueError("frozen model catalog changed")
    catalog=json.loads(catalog_bytes);catalog_models={item["id"]:item for item in catalog["catalog"]["data"]}
    if spec["model_catalog"]["selected_models"]!=models:raise ValueError("model catalog selection/order differs from frozen protocol")
    if any(model not in catalog_models or not any(e["reasoningEffort"]=="low" for e in catalog_models[model]["supportedReasoningEfforts"]) for model in spec["models"]):
        raise ValueError("selected model/low not listed")
    for condition in ("control", "treatment"):
        item = spec["conditions"][condition]
        if (digest(item["source"]) != item["source_sha256"] or "runtime" in item["execution_artifact"]
                or digest(item["execution_artifact"]) != item["execution_artifact_sha256"]
                or digest({"release_revision": item["revision"], "source_sha256": item["source_sha256"]}) != item["candidate_id"]):
            raise ValueError("exact release source/compiler/candidate identity changed")
        if (digest(item["expected_runtime_hashes"])!=item["expected_runtime_sha256"]
                or sha(item["expected_skill"].encode("utf-8"))!=item["expected_runtime_hashes"].get("SKILL.md")
                or set(item["expected_plans"])!={digest(task["plan_context"]) for task in tasks.values()}):
            raise ValueError("frozen generated runtime/Skill/context set changed")
    protocol_sha = digest(spec)
    if set(spec["workers"]) != {model + ":" + condition for model in spec["models"] for condition in ("control", "treatment")}:
        raise ValueError("four isolated workers are required")
    graders, artifacts, binaries = set(), set(), {}
    for key, entry in spec["workers"].items():
        manifest = dict(entry["manifest_core"], protocol_sha256=protocol_sha)
        path = Path(entry["manifest_path"])
        if json.loads(path.read_text(encoding="utf-8")) != manifest: raise ValueError("derived worker manifest changed")
        core, config = entry["manifest_core"], entry["config"]
        root = Path(core["snapshot_directory"])
        if set(core["files"]) != {"evolution/__init__.py", "evolution/contracts.py", "evolution/native_codex.py", "upg_native_common_grader.py"}:
            raise ValueError("snapshot dependency set changed")
        for relative, expected in core["files"].items():
            if sha((root / relative).read_bytes()) != expected: raise ValueError("snapshot dependency hash changed")
        if json.loads(Path(core["config_path"]).read_text(encoding="utf-8")) != config or digest(config) != core["config_sha256"]:
            raise ValueError("native config changed")
        condition = spec["conditions"][entry["condition"]]
        if Path(catalog["cli_entry"]).resolve()!=Path(config["binary"]).resolve():raise ValueError("catalog and binary entries differ")
        expected_order = [row["task_id"] for row in order if row["model"] == entry["model"] and row["condition"] == entry["condition"]]
        if (key != entry["model"] + ":" + entry["condition"] or config["model"] != entry["model"] or config["effort"] != "low"
                or config["timeout_seconds"] != 180 or core["task_order"] != expected_order
                or core["task_sha256"] != {tid: digest(task) for tid, task in tasks.items()}
                or core["task_phases"] != {tid: task["context_phase"] for tid, task in tasks.items()}
                or core["source_sha256"] != condition["source_sha256"] or core["candidate_id"] != condition["candidate_id"]
                or core["execution_artifact_sha256"] != condition["execution_artifact_sha256"]
                or core["runner_config"]["campaign_id"] != spec["protocol_id"]):
            raise ValueError("worker input/config/order binding differs")
        if core["transport"]!=spec["transport"]:raise ValueError("worker transport differs between arms")
        if config["binary"] not in binaries: binaries[config["binary"]] = sha(Path(config["binary"]).read_bytes())
        binary_sha = binaries[config["binary"]]
        if (core["runner_config"]["native_config_sha256"] != digest(dict(config, binary_sha256=binary_sha))
                or core["runner_config"]["grader"] != {"reference": "upg_native_common_grader:grade", "source_sha256": core["files"]["upg_native_common_grader.py"]}):
            raise ValueError("registered binary/grader capability changed")
        graders.add(core["files"]["upg_native_common_grader.py"]); artifacts.add(config["artifact_root"])
    if len(graders) != 1 or len(artifacts) != 4: raise ValueError("grader must be identical and artifact roots isolated")
    if (spec["common_grader"]["sha256"] not in graders
            or spec["common_grader"]["revision"] != spec["conditions"]["treatment"]["revision"]):
        raise ValueError("common operator-selected grader provenance differs")
    return protocol_sha


class ProcessWorker:
    def __init__(self, entry, protocol_sha, log_directory):
        started = time.perf_counter(); self.active = False
        log_directory = Path(log_directory); log_directory.mkdir(parents=True, exist_ok=True)
        self.stderr = (log_directory / "worker.stderr.raw").open("ab")
        self.stdout_log = (log_directory / "worker.stdout.jsonl").open("ab")
        manifest = Path(entry["manifest_path"])
        command = [sys.executable, "-B", str(WORKER), "--manifest", str(manifest), "--manifest-sha256", sha(manifest.read_bytes()),
                   "--allow-dispatch-protocol-sha256", protocol_sha]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        self.messages = queue.Queue()
        def read():
            try:
                for line in self.process.stdout:
                    self.stdout_log.write(line); self.stdout_log.flush(); os.fsync(self.stdout_log.fileno())
                    self.messages.put(line)
            except BaseException as error: self.messages.put(error)
            finally: self.messages.put(None)
        self.thread = threading.Thread(target=read, daemon=True); self.thread.start()
        try:
            ready = self._receive(30)
            if (ready.get("type") != "ready" or ready.get("verification_only") is not False or ready.get("protocol_sha256") != protocol_sha
                    or ready.get("manifest_sha256")!=sha(manifest.read_bytes()) or ready.get("model_requested")!=entry["model"]
                    or ready.get("transport_source_sha256")!=entry["manifest_core"]["transport"]["source_sha256"]
                    or ready.get("transport_profile_source_sha256")!=entry["manifest_core"]["transport"]["profile_source"]["sha256"]
                    or ready.get("transport_profile_sha256")!=digest(entry["manifest_core"]["transport"]["profile"])):
                raise ValueError("worker did not attest matching isolated registration")
        except BaseException:
            # No request has been sent. Closing input can safely end this child.
            if self.process.stdin: self.process.stdin.close()
            try: self.process.wait(timeout=10)
            except subprocess.TimeoutExpired: pass
            if self.process.poll() is not None:
                self.thread.join(timeout=1);self.stderr.close();self.stdout_log.close()
            raise
        self.startup_seconds = time.perf_counter() - started
        self.pid = self.process.pid

    def _receive(self, timeout):
        try: line = self.messages.get(timeout=timeout)
        except queue.Empty as error: raise TimeoutError("worker result unavailable; no retry") from error
        if line is None: raise RuntimeError("worker exited without an authoritative result")
        if isinstance(line, BaseException): raise RuntimeError("worker evidence capture failed") from line
        return json.loads(line)

    def call(self, command):
        self.active = True
        self.process.stdin.write((json.dumps(command, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
        self.process.stdin.flush()
        result = self._receive(300)  # 180 CLI + at most 60 compile + 30 plan + bounded evidence slack.
        self.active = False
        return result

    def close(self):
        if self.process.stdin and not self.process.stdin.closed: self.process.stdin.close()
        if self.active:
            return {"pid": self.pid, "state": "pending process left for independent reconciliation; no new input"}
        try: self.process.wait(timeout=10)
        except subprocess.TimeoutExpired: return {"pid": self.pid, "state": "worker shutdown unconfirmed"}
        self.thread.join(timeout=1); self.stderr.close(); self.stdout_log.close()
        return {"pid": self.pid, "state": "exited", "exit_code": self.process.returncode}


def usage(value):
    if (not isinstance(value, dict) or any(type(value.get(key)) is not int or value[key] < 0 for key in ("input_tokens", "output_tokens", "total_tokens"))
            or value["total_tokens"] != value["input_tokens"] + value["output_tokens"]): return None
    return copy.deepcopy(value)


def strict_json(text):
    def pairs(rows):
        answer = {}
        for key, value in rows:
            if key in answer: raise ValueError("duplicate JSON key")
            answer[key] = value
        return answer
    def constant(value): raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def same_json(left, right):
    if type(left) is not type(right): return False
    if isinstance(left, dict): return left.keys() == right.keys() and all(same_json(left[k], right[k]) for k in left)
    if isinstance(left, list): return len(left)==len(right) and all(same_json(a,b) for a,b in zip(left,right))
    if isinstance(left, float) and not math.isfinite(left): return False
    return left == right


def strict_artifact_quality(task, response_text):
    """Independent defense shared by both arms; never execute generated code."""
    try:
        response = strict_json(response_text)
        if (not isinstance(response,dict) or set(response)!={"files","validation"}
                or response["validation"]!="not_run" or not isinstance(response["files"],list)):
            return False
        files = {}
        for item in response["files"]:
            if (not isinstance(item,dict) or set(item)!={"path","content"} or not isinstance(item["path"],str)
                    or not isinstance(item["content"],str) or item["path"] in files): return False
            files[item["path"]]=item["content"]
        if set(files)!={check["path"] for check in task["artifact_checks"]}: return False
        for check in task["artifact_checks"]:
            if check["kind"]=="json" and not same_json(strict_json(files[check["path"]]),strict_json(check["expected"])):
                return False
        return True
    except (ValueError,TypeError,KeyError): return False


def verify_receipt(spec, item, raw, request):
    receipt = raw.get("provider_receipt") or {}
    if receipt.get("replayed_from_local_receipt") is True: raise ValueError("local receipt cannot be a fresh independent call")
    entry = spec["workers"][item["model"] + ":" + item["condition"]]
    reference = receipt.get("raw_artifact_reference", "")
    parts = reference.split("/")
    if len(parts) != 2 or parts[0] != "calls" or len(parts[1]) != 64 or any(c not in "0123456789abcdef" for c in parts[1]):
        raise ValueError("invalid native raw artifact reference")
    directory = Path(entry["config"]["artifact_root"]) / parts[0] / parts[1]
    stored = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
    if stored != receipt: raise ValueError("returned and durable native receipts differ")
    stdout = (directory / "stdout.raw").read_bytes(); stderr = (directory / "stderr.raw").read_bytes()
    persisted_result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if sha(stdout) != receipt["stdout_sha256"] or sha(stderr) != receipt["stderr_sha256"] or digest(persisted_result) != receipt["result_sha256"]:
        raise ValueError("raw CLI/result hash changed")
    if (receipt.get("status") != "completed" or receipt.get("tool_calls") != 0 or receipt.get("model_requested") != item["model"]
            or receipt.get("config_sha256") != request["config"]["native_config_sha256"]
            or receipt.get("usage") != raw.get("usage") or persisted_result.get("usage") != raw.get("usage")
            or receipt.get("sandbox")!="read-only" or receipt.get("ephemeral") is not True
            or receipt.get("provider_request_id") is not None or receipt.get("model_observed") is not None
            or receipt["bindings"].get("capability") != {key:request["config"][key] for key in ("native_config_sha256","grader")}
            or receipt["bindings"].get("grader") != request["config"]["grader"]
            or receipt["bindings"].get("campaign_id") != spec["protocol_id"]
            or receipt["bindings"].get("sample_id") != request["task"]["id"]
            or receipt["bindings"].get("source_sha256") != request["source_sha256"]
            or receipt["bindings"].get("task_sha256") != digest(request["task"])
            or receipt["bindings"].get("execution_artifact_sha256") != digest(request["execution_artifact"])
            or receipt["bindings"].get("runtime_sha256") != spec["conditions"][item["condition"]]["expected_runtime_sha256"]
            or receipt["bindings"].get("candidate_id") != request["candidate_id"]):
        raise ValueError("native identity/source/task/transport binding mismatch")
    events = []
    for line in stdout.decode("utf-8").splitlines():
        try: event = json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(event, dict): events.append(event)
    starts = [event.get("thread_id") for event in events if event.get("type") == "thread.started"]
    turns = [event.get("usage") for event in events if event.get("type") == "turn.completed"]
    if starts != [receipt.get("cli_thread_id")] or not isinstance(starts[0],str) or not starts[0] or len(turns) != 1:
        raise ValueError("actual CLI thread/completed-turn identity missing")
    allowed_events={"thread.started","turn.started","turn.completed","item.started","item.updated","item.completed"}
    allowed_items={"reasoning","agent_message"}
    if any(e.get("type") not in allowed_events or (e.get("type","").startswith("item.")
            and (not isinstance(e.get("item"),dict) or e["item"].get("type") not in allowed_items)) for e in events):
        raise ValueError("actual CLI stream contains an unregistered event or item")
    turn = turns[0]; actual = raw["usage"]
    if any(turn.get(key) != actual.get(key) for key in ("input_tokens", "output_tokens")):
        raise ValueError("usage does not match actual completed CLI turn")
    prompt_bytes = (directory / "prompt.txt").read_bytes()
    if sha(prompt_bytes) != receipt["prompt_sha256"]: raise ValueError("actual prompt hash mismatch")
    payload = json.loads(prompt_bytes.decode("utf-8").split("\n\n", 1)[1])
    task = request["task"]
    if (set(payload) != {"governance_skill", "governance_plan", "task", "task_payload", "output_contract"}
            or payload["task"] != task["prompt"] or payload["task_payload"] != task["payload"]
            or payload["output_contract"] != task["output_schema"]
            or not same_json(payload["governance_plan"],spec["conditions"][item["condition"]]["expected_plans"][digest(task["plan_context"])])
            or payload["governance_skill"] != spec["conditions"][item["condition"]]["expected_skill"].replace("\r\n", "\n").replace("\r", "\n")):
        raise ValueError("provider prompt differs or contains unregistered task material")
    # Regrade actual final CLI output using the same frozen positive common grader.
    messages = [e["item"]["text"] for e in events if e.get("type") == "item.completed" and isinstance(e.get("item"), dict) and e["item"].get("type") == "agent_message"]
    if not messages: raise ValueError("actual final CLI output missing")
    if persisted_result.get("text") != messages[-1]: raise ValueError("persisted final text differs from CLI output")
    try: response = strict_json(messages[-1])
    except ValueError: response = None
    common = runpy.run_path(str(Path(entry["manifest_core"]["snapshot_directory"]) / "upg_native_common_grader.py"))
    independently_graded = common["grade"]({"task": task, "response_text":messages[-1], "response_json": response,
                                           "usage": actual, "wall_seconds": receipt["wall_seconds"]})
    if any(independently_graded.get(key) != (raw.get("outcome") or {}).get(key) for key in ("hard", "soft", "artifact_checks", "scope_ok", "validation_truth_ok")):
        raise ValueError("returned quality differs from independent actual-output grading")
    return {"receipt_sha256": sha((directory / "receipt.json").read_bytes()), "artifact_directory": str(directory),
            "stdout_sha256": receipt["stdout_sha256"], "prompt_sha256": receipt["prompt_sha256"],
            "cli_thread_id": receipt["cli_thread_id"], "independent_grade": independently_graded,
            "strict_artifact_quality":strict_artifact_quality(task,messages[-1])}


def expected_cli_arguments(spec,item,raw):
    entry=spec["workers"][item["model"]+":"+item["condition"]]
    reference=(raw.get("provider_receipt") or {}).get("raw_artifact_reference","").split("/")
    if (len(reference)!=2 or reference[0]!="calls" or len(reference[1])!=64
            or any(c not in "0123456789abcdef" for c in reference[1])):
        raise ValueError("invalid native directory for exact argv verification")
    directory=Path(entry["config"]["artifact_root"])/reference[0]/reference[1]
    arguments=[entry["config"]["binary"],"--ask-for-approval","never","exec","--cd",str(directory),
               "--skip-git-repo-check","--ephemeral","--ignore-user-config","--json","--sandbox","read-only",
               "--model",item["model"],"-c",'model_reasoning_effort="%s"'%entry["config"]["effort"],
               "-c","features.shell_tool=false","-c",'web_search="disabled"',"-c","hide_agent_reasoning=true"]
    if spec["tasks"][item["task_id"]].get("output_schema") is not None:
        arguments.extend(["--output-schema",str(directory/"output.schema.json")])
    return arguments+["-"]


def verify_transport(spec,item,message,raw):
    rows=message.get("transport_receipts")
    if not isinstance(rows,list) or len(rows)!=1:raise ValueError("fresh native call requires exactly one actual child dispatch trace")
    row=rows[0];entry=spec["workers"][item["model"]+":"+item["condition"]]
    sample_id=entry["model"]+":"+entry["condition"]+":"+item["task_id"]
    path=Path(entry["config"]["artifact_root"])/"transport"/(digest({"sample_id":sample_id})+".json")
    if row.get("receipt_path")!=str(path) or json.loads(path.read_text(encoding="utf-8"))!=row:
        raise ValueError("durable child transport receipt differs")
    profile=spec["transport"]["profile"];argv=row.get("argv");receipt=raw.get("provider_receipt") or {}
    tail=[part for value in profile for part in ("-c",value)]+["-"]
    expected_original=expected_cli_arguments(spec,item,raw)
    if (not isinstance(argv,list) or len(argv)<15 or argv[-len(tail):]!=tail
            or argv!=expected_original[:-1]+tail
            or argv[:4]!=[entry["config"]["binary"],"--ask-for-approval","never","exec"]
            or row.get("argv_sha256")!=digest(argv)
            or row.get("original_argv_sha256")!=digest(expected_original)
            or row.get("profile")!=profile or row.get("sample_id")!=sample_id
            or row.get("transport_source_sha256")!=spec["transport"]["source_sha256"]
            or row.get("profile_source_sha256")!=spec["transport"]["profile_source"]["sha256"]
            or row.get("status")!="returned" or row.get("exit_code")!=0 or row.get("automatic_retry") is not False
            or row.get("stdout_sha256")!=receipt.get("stdout_sha256") or row.get("stderr_sha256")!=receipt.get("stderr_sha256")):
        raise ValueError("actual child HTTP argv/output/source binding mismatch")
    for option,value in (("--sandbox","read-only"),("--model",item["model"])):
        if argv.count(option)!=1 or argv[argv.index(option)+1]!=value:raise ValueError("actual child model/sandbox differs")
    if "--ignore-user-config" not in argv or "--ephemeral" not in argv or "--json" not in argv:
        raise ValueError("actual child isolation/JSON options missing")
    if type(row.get("elapsed_seconds")) not in (int,float) or not math.isfinite(row["elapsed_seconds"]) or row["elapsed_seconds"]<0:
        raise ValueError("actual child instrumentation time missing or invalid")
    return {"receipt_path":str(path),"receipt_sha256":sha(path.read_bytes()),"argv_sha256":row["argv_sha256"],
            "profile_sha256":digest(profile),"elapsed_seconds":row["elapsed_seconds"]}


def metric(pairs, name, repetitions=4000, seed=19012):
    if not pairs: return None
    def value(row):
        return (row.get("usage") or {}).get("total_tokens") if name == "total_tokens" else row.get(name)
    if any(type(value(row)) not in (int, float) or not math.isfinite(value(row)) or value(row) < 0 for pair in pairs for row in pair): return None
    control = sum(value(a) for a,b in pairs); treatment = sum(value(b) for a,b in pairs)
    blocks = {}
    for pair in pairs: blocks.setdefault(pair[0]["family"], []).append(pair)
    rng, draws = random.Random(seed), []
    for unused in range(repetitions):
        sample = []
        families = sorted(blocks)
        for unused_family in families: sample.extend(blocks[rng.choice(families)])
        denominator = sum(value(a) for a,b in sample)
        if denominator: draws.append(sum(value(b) for a,b in sample) / denominator)
    draws.sort()
    return {"control_total": control, "treatment_total": treatment, "ratio": treatment/control if control else None,
            "paired_joint_family_block_95_interval": [draws[int(len(draws)*.025)], draws[min(len(draws)-1,int(len(draws)*.975))]] if draws else None}


def summarize(run, repetitions=4000):
    rows = run["observations"]; cells = {(r["model"],r["task_id"],r["condition"]):r for r in rows}
    pairs = [(cells[(m,t,"control")],cells[(m,t,"treatment")]) for m in run["models"] for t in run["task_ids"] if all((m,t,c) in cells for c in ("control","treatment"))]
    metrics = {name:metric(pairs,name,repetitions) for name in ("callback_seconds","cli_seconds","worker_roundtrip_seconds","collector_seconds","total_tokens")}
    quality = bool(rows) and all(r.get("quality_pass") is True for r in rows)
    fresh = bool(rows) and all(r.get("fresh") is True for r in rows)
    receipts = [r.get("evidence",{}).get("receipt_sha256") for r in rows]
    threads = [r.get("evidence",{}).get("cli_thread_id") for r in rows]
    complete = run["status"] == "completed" and len(rows)==32 and len(cells)==32 and len(pairs)==16
    interval = (metrics["callback_seconds"] or {}).get("paired_joint_family_block_95_interval")
    gates = {"complete_matched_collection":complete,"all_quality_pass":quality,"all_fresh_calls":fresh,
             "unique_raw_receipts":bool(receipts) and all(isinstance(x,str) and len(x)==64 for x in receipts) and len(set(receipts))==len(receipts),
             "unique_cli_threads":bool(threads) and all(isinstance(x,str) and bool(x) for x in threads) and len(set(threads))==len(threads),
             "callback_time_ci_upper_improves":interval is not None and interval[1] < 1.0}
    return {"estimand":"A-independent-native-full-callback-time-and-quality","A_time_quality_gate":"PASS" if all(gates.values()) else "FAIL",
            "gates":gates,"metrics":metrics,"paired_tasks":len(pairs),"actual_charged_usage":copy.deepcopy(run["budget"]),
            "per_model":{m:{name:metric([p for p in pairs if p[0]["model"]==m],name,repetitions) for name in metrics} for m in run["models"]},
            "context_strata":{phase:{name:metric([p for p in pairs if p[0]["context_phase"]==phase],name,repetitions) for name in metrics} for phase in ("cold","repeat")},
            "formal_qualification":"UNASSESSED","joint_token_benefit":"NOT CLAIMED; all tokens and regressions reported",
            "B_joint_gate_unchanged":True,"bootstrap":"joint whole family blocks, preserving both requested models and cold/repeat together; four known families only",
            "startup_seconds":run.get("worker_startup_seconds"),"source_preparation":run.get("source_preparation"),
            "campaign_wall_seconds":run["budget"]["elapsed_seconds"],
            "timing_endpoints":{"callback":"public runner entry through return, includes own client constructor/config/prepare/CLI/grade/native receipt persistence",
              "worker_roundtrip":"parent send through worker result reception, includes callback serialization and durable worker stdout capture",
              "collector":"pre-dispatch fence through independently graded observation checkpoint; timing publication excluded",
              "campaign":"before parent registration validation through terminal checkpoint, including worker startup and shutdown; source preparation separate"}}


def collect(spec, output, *, allow_dispatch_protocol_sha256, worker_factory=ProcessWorker, verifier=verify_receipt, transport_verifier=verify_transport):
    started = time.perf_counter(); output=Path(output).resolve(); protocol_sha=validate(spec)
    if allow_dispatch_protocol_sha256 != protocol_sha: raise ValueError("explicit frozen protocol dispatch identity required")
    if output.exists():
        old=json.loads(output.read_text(encoding="utf-8"))
        if old.get("protocol_sha256") != protocol_sha: raise ValueError("existing output belongs to another protocol")
        if old.get("pending") or old.get("status")=="running": raise ValueError("partial native campaign requires independent reconciliation; worker cache cannot resume")
        return old
    if any(Path(entry["config"]["artifact_root"]).exists() for entry in spec["workers"].values()):
        raise ValueError("native experiment roots must be fresh; no observation replay")
    lock=Path(str(output)+".lock");lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open("x",encoding="ascii") as handle: handle.write(uuid.uuid4().hex);handle.flush();os.fsync(handle.fileno())
    run={"schema_version":1,"protocol_sha256":protocol_sha,"protocol_id":spec["protocol_id"],"status":"running","pending":None,
         "models":spec["models"],"task_ids":list(spec["tasks"]),"order":spec["order"],"observations":[],"worker_startup_seconds":{},
         "source_preparation":spec["source_preparation"],"budget":{"calls":0,"total_tokens":0,"unknown_usage":False,"records":[],"elapsed_seconds":0},"scope":spec["scope"]}
    workers={}
    def checkpoint():
        run["budget"]["elapsed_seconds"]=time.perf_counter()-started
        over={key:run["budget"][field] for key,field in (("model_calls","calls"),("tokens","total_tokens"),("wall_seconds","elapsed_seconds")) if run["budget"][field]>spec["budget"][key]}
        if over:
            run["actual_budget_overrun"]=over
            if run["status"]=="completed":run.update(status="budget-exhausted",stop_reason="terminal measurement exceeded stop threshold")
        if "summary" in run:
            run["summary"]["actual_charged_usage"]=copy.deepcopy(run["budget"])
            run["summary"]["campaign_wall_seconds"]=run["budget"]["elapsed_seconds"]
            if run["status"]!="completed":run["summary"]["gates"]["complete_matched_collection"]=False;run["summary"]["A_time_quality_gate"]="FAIL"
        atomic(output,run)
    checkpoint()
    try:
        try:
            for key,entry in spec["workers"].items():
                workers[key]=worker_factory(entry,protocol_sha,output.parent/(output.stem+"-"+key.replace(":","-")))
                run["worker_startup_seconds"][key]=workers[key].startup_seconds
        except Exception as error:
            run.update(status="preparation-failed",stop_reason="before first model dispatch: "+type(error).__name__+": "+str(error))
            checkpoint();run["summary"]=summarize(run);checkpoint();return run
        checkpoint()
        for item in spec["order"]:
            if (run["budget"]["calls"]>=spec["budget"]["model_calls"] or run["budget"]["total_tokens"]>=spec["budget"]["tokens"] or time.perf_counter()-started>=spec["budget"]["wall_seconds"]):
                run.update(status="budget-exhausted",stop_reason="pre-dispatch stop threshold reached");break
            cycle_started=time.perf_counter(); key=item["model"]+":"+item["condition"];entry=spec["workers"][key];condition=spec["conditions"][item["condition"]];task=spec["tasks"][item["task_id"]]
            sample_id=key+":"+item["task_id"]
            request={"source":condition["source"],"source_sha256":condition["source_sha256"],"candidate_id":condition["candidate_id"],"execution_artifact":condition["execution_artifact"],
                     "task":task,"model":item["model"],"config":entry["manifest_core"]["runner_config"],"cache_key":digest({"protocol":protocol_sha,"sample":sample_id}),"attempt":0}
            run["budget"]["calls"]+=1;run["pending"]={"sample_id":sample_id,"request_sha256":digest(request),"observation_index":len(run["observations"])};checkpoint()
            roundtrip_started=time.perf_counter()
            try: message=workers[key].call({"protocol_sha256":protocol_sha,"sample_id":sample_id,"request":request})
            except BaseException as error:
                run.update(status="unknown-call-blocked",stop_reason=type(error).__name__+": "+str(error));run["budget"]["unknown_usage"]=True;checkpoint();break
            roundtrip=time.perf_counter()-roundtrip_started
            raw=message.get("result") or {"status":"failed","usage":message.get("usage"),"provider_receipt":message.get("provider_receipt"),"error":message.get("error")}
            actual=usage(raw.get("usage"));receipt=raw.get("provider_receipt") or {};replayed=receipt.get("replayed_from_local_receipt") is True
            row=dict(item,sample_id=sample_id,family=task["family"],result=raw,usage=actual,callback_seconds=message.get("callback_wall_seconds"),
                     cli_seconds=receipt.get("wall_seconds"),worker_message=copy.deepcopy(message),worker_roundtrip_seconds=roundtrip,collector_seconds=0.0,fresh=False,quality_pass=False)
            run["observations"].append(row)
            run["budget"]["records"].append({"sample_id":sample_id,"usage":actual,"worker_roundtrip_seconds":roundtrip,
                                             "unverified_replay_claim":replayed})
            if actual is None or replayed:run["budget"]["unknown_usage"]=True
            if actual is not None:run["budget"]["total_tokens"]+=actual["total_tokens"]
            if replayed:run["budget"]["accounting_limit"]="unverified replay claim in fresh root; reserved attempt and returned usage retained conservatively, new provider charge unknown"
            if message.get("type")!="call_result" or actual is None or message.get("sample_id")!=sample_id:
                run.update(status="unknown-call-blocked",stop_reason="worker call/error/usage identity unconfirmed; known charges retained");checkpoint();break
            try:
                row["evidence"]=verifier(spec,item,raw,request)
                row["transport_evidence"]=transport_verifier(spec,item,message,raw)
                if raw.get("status")!="completed" or replayed:raise ValueError("native completion not fresh")
                if any(type(row.get(field)) not in (int,float) or not math.isfinite(row[field]) or row[field]<0 for field in ("callback_seconds","cli_seconds")):
                    raise ValueError("actual timing is missing or nonfinite")
                worker_prior=sum(r["model"]==item["model"] and r["condition"]==item["condition"] for r in run["observations"][:-1])
                if message.get("first_public_callback") is not (worker_prior==0) or message.get("context_phase")!=item["context_phase"]:
                    raise ValueError("worker first-call/context marker differs from frozen order")
                if item["condition"]=="treatment" and (raw.get("local_timings") or {}).get("cache_hit") is not (item["context_phase"]=="repeat"):
                    raise ValueError("actual preparation cache state differs from frozen first/repeat schedule")
                row["fresh"]=True
                outcome=raw.get("outcome") or {}
                row["quality_pass"]=(outcome.get("hard")==1 and outcome.get("soft")==1 and outcome.get("scope_ok") is True
                                     and outcome.get("validation_truth_ok") is True and row["evidence"].get("strict_artifact_quality") is True)
            except Exception as error:
                run.update(status="protocol-violation",stop_reason=type(error).__name__+": "+str(error));run["pending"]=None;checkpoint();break
            run["pending"]=None;checkpoint()  # Includes full graded observation evidence persistence.
            row["collector_seconds"]=time.perf_counter()-cycle_started
            checkpoint()  # Timing-publication overhead is outside that explicitly labelled endpoint.
            if run.get("actual_budget_overrun"):
                run.update(status="budget-exhausted",stop_reason="measured call exceeded stop threshold");break
        else:run["status"]="completed"
        checkpoint();run["summary"]=summarize(run);checkpoint()
        return run
    except BaseException as error:
        # Pending was fsynced before any send; interruption never resumes this cache schedule.
        run.update(status="unknown-call-blocked" if run.get("pending") else "collector-interrupted",
                   stop_reason=type(error).__name__+": "+str(error))
        if run.get("pending"):run["budget"]["unknown_usage"]=True
        checkpoint()
        raise
    finally:
        close_states={}
        for key,value in workers.items():
            try:close_states[key]=value.close()
            except BaseException as error:close_states[key]={"state":"cleanup unconfirmed","error":type(error).__name__+": "+str(error)}
        if run.get("status")!="running":
            run["worker_close_states"]=close_states;checkpoint()
        if lock.exists():lock.unlink()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--spec",required=True);parser.add_argument("--output")
    parser.add_argument("--allow-dispatch-protocol-sha256");args=parser.parse_args();spec=json.loads(Path(args.spec).read_text(encoding="utf-8"));identity=validate(spec)
    if args.allow_dispatch_protocol_sha256 is None:print(json.dumps({"verified":True,"protocol_sha256":identity,"model_calls":0}))
    else:
        if not args.output:raise ValueError("dispatch requires an explicit fresh output path")
        result=collect(spec,args.output,allow_dispatch_protocol_sha256=args.allow_dispatch_protocol_sha256)
        print(json.dumps(result.get("summary",{"status":result["status"]}),indent=2))
