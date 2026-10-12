"""Prepare only ignored exact-Git inputs. Never dispatch models/public protocols."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
worker = runpy.run_path(str(HERE / "worker.py"))
digest, sha = worker["digest"], worker["sha"]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def prepare(repo, output, artifact_root, binary, git_binary, control_revision, treatment_revision, model_catalog):
    started = time.perf_counter()
    if any(not re.fullmatch('[0-9a-f]{40}',revision) for revision in (control_revision,treatment_revision)):
        raise ValueError("release revisions must be explicit full lowercase Git commit SHAs")
    if any(not Path(path).is_absolute() for path in (repo, output, artifact_root, binary, git_binary, model_catalog)):
        raise ValueError("all registered paths must be explicit absolute paths")
    repo, output, artifact_root, binary = map(lambda p: Path(p).resolve(), (repo, output, artifact_root, binary))
    if (not output.is_relative_to(repo / "eval-workspaces") or not output.name.startswith("rc19-native-paired-")
            or output.exists() or artifact_root.exists() or not binary.is_file()):
        raise ValueError("fresh ignored preparation/artifact directories and registered binary required")
    def git(*args):
        return subprocess.check_output([str(git_binary), "-C", str(repo), *args])
    revisions = {"control": git("rev-parse", control_revision + "^{commit}").decode().strip(),
                 "treatment": git("rev-parse", treatment_revision + "^{commit}").decode().strip()}
    def blob(revision, relative):
        return git("show", revision + ":" + relative)
    def tree(revision, prefix):
        names = git("ls-tree", "-r", "--name-only", revision, "--", prefix).decode().splitlines()
        return {name[len(prefix) + 1:]: blob(revision, name).decode("utf-8") for name in names}
    # The public native API permits an operator-registered grader. Pin the same
    # corrected current grader for both otherwise unchanged release callbacks.
    grader = blob(revisions["treatment"], "evolution/task_benchmark.py")
    tasks = runpy.run_path(str(HERE / "tasks.py"))["make_tasks"]()
    models = ["gpt-6-luna", "gpt-6.1-sol"]
    catalog_bytes=Path(model_catalog).read_bytes();catalog=json.loads(catalog_bytes)
    if Path(catalog["cli_entry"]).resolve()!=binary:
        raise ValueError("catalog did not come from the registered CLI entry")
    catalog_models={item["id"]:item for item in catalog["catalog"]["data"]}
    if any(model not in catalog_models or not any(e["reasoningEffort"]=="low" for e in catalog_models[model]["supportedReasoningEfforts"]) for model in models):
        raise ValueError("selected requested model/low effort not present in frozen catalog")
    order = worker["matched_order"](models, tasks, 19012)
    output.mkdir(parents=True)
    binary_sha = sha(binary.read_bytes())
    transport_path=HERE/"transport.py"
    transport={"path":str(transport_path),"source_sha256":sha(transport_path.read_bytes()),
               "profile":runpy.run_path(str(transport_path))["PROFILE"],
               "scope":"identical child-only HTTP overrides; historical and current callbacks under common transport scaffold"}
    conditions, workers = {}, {}
    for condition, revision in revisions.items():
        source = tree(revision, "governance-src")
        reference_runtime=tree(revision,"universal-project-governance")
        runtime_directory=output/(condition+"-reference-runtime")
        for relative,content in reference_runtime.items():
            path=runtime_directory/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content.encode("utf-8"))
        expected_plans={}
        for task in tasks:
            context=task["plan_context"];context_sha=digest(context)
            if context_sha in expected_plans:continue
            context_path=output/(condition+"-context-"+context_sha+".json");write(context_path,context)
            planned=subprocess.run([sys.executable,"-B",str(runtime_directory/"scripts/plan_governance.py"),"--context",str(context_path),"--json"],
                                   capture_output=True,timeout=30,check=False)
            if planned.returncode:raise ValueError("frozen release reference planner failed before model dispatch")
            expected_plans[context_sha]=json.loads(planned.stdout)
        artifact = {"compiler": blob(revision, "compiler/compile_governance.py").decode("utf-8"),
                    "license": blob(revision, "LICENSE").decode("utf-8")}
        conditions[condition] = {"revision": revision, "source": source, "source_sha256": digest(source),
                                 "execution_artifact": artifact, "execution_artifact_sha256": digest(artifact),
                                 "candidate_id": digest({"release_revision": revision, "source_sha256": digest(source)}),
                                 "expected_skill": reference_runtime["SKILL.md"],
                                 "expected_runtime_hashes":{name:sha(text.encode("utf-8")) for name,text in reference_runtime.items()},
                                 "expected_runtime_sha256":digest({name:sha(text.encode("utf-8")) for name,text in reference_runtime.items()}),
                                 "expected_plans":expected_plans}
        for model in models:
            key = model + ":" + condition
            snapshot = output / (model + "-" + condition)
            files = {name: blob(revision, name) for name in ("evolution/__init__.py", "evolution/contracts.py", "evolution/native_codex.py")}
            files["upg_native_common_grader.py"] = grader
            for name, content in files.items():
                destination = snapshot / name; destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(content)
            config = {"binary": str(binary), "model": model, "effort": "low", "artifact_root": str(artifact_root / model / condition),
                      "timeout_seconds": 180, "grader": "upg_native_common_grader:grade", "cli_version": "0.162.0-alpha.20"}
            config_path = snapshot / "native.config.json"; write(config_path, config)
            capability = {"native_config_sha256": digest(dict(config, binary_sha256=binary_sha)),
                          "grader": {"reference": config["grader"], "source_sha256": sha(grader)},
                          "campaign_id": "upg-rc19-native-independent-a-v1"}
            manifest = {"worker_sha256": sha((HERE / "worker.py").read_bytes()),
                        "transport":transport,
                        "snapshot_directory": str(snapshot), "files": {name: sha(content) for name, content in files.items()},
                        "config_path": str(config_path), "config_sha256": digest(config), "runner_config": capability,
                        "source_sha256": digest(source), "execution_artifact_sha256": digest(artifact),
                        "candidate_id": conditions[condition]["candidate_id"],
                        "task_sha256": {task["id"]: digest(task) for task in tasks},
                        "task_phases": {task["id"]: task["context_phase"] for task in tasks},
                        "task_order": [row["task_id"] for row in order if row["model"] == model and row["condition"] == condition]}
            workers[key] = {"manifest_path": str(snapshot / "worker.manifest.json"), "manifest_core": manifest,
                            "config": config, "condition": condition, "model": model}
    spec = {"schema_version": 1, "protocol_id": "upg-rc19-native-independent-a-v1", "stage": "independent-artifact-estimand-A",
            "status": "PREPARED-NOT-DISPATCH-AUTHORIZED", "seed": 19012, "models": models,
            "tasks": {task["id"]: task for task in tasks}, "task_manifest_sha256": digest({task["id"]: task for task in tasks}),
            "conditions": conditions, "order": order, "order_sha256": digest(order), "workers": workers,
            "transport":transport,
            "budget": {"model_calls": 32, "tokens": 1500000, "wall_seconds": 7200},
            "acceptance": {"primary": "full-public-callback-time-and-quality", "callback_time_ci_upper_exclusive": 1.0,
                           "all_quality_required": True, "all_fresh_calls_required": True},
            "bootstrap": {"method": "paired-joint-family-block-preserving-models-and-cold-repeat", "seed": 19012, "repetitions": 4000},
            "common_grader": {"selection": "operator-selected treatment-release grader, identical in both arms",
                              "revision": revisions["treatment"], "git_path": "evolution/task_benchmark.py", "sha256": sha(grader)},
            "model_catalog": {"path":str(Path(model_catalog).resolve()),"sha256":sha(catalog_bytes),
                              "observed_at_utc":catalog["observed_at_utc"],"selected_models":models,
                              "state":"listed low-effort support; provider access and observed model identity not attested"},
            "harness_files": {str(path): sha(path.read_bytes()) for path in (
                HERE/"worker.py", HERE/"parent.py", HERE/"prepare.py", HERE/"tasks.py", HERE/"transport.py", HERE/"__init__.py",
                HERE.parent/"__init__.py", REPO/"tests/test_native_paired.py", REPO/"docs/evolution/native-paired-campaign.md")},
            "scope": {"provider": "OpenAI", "model_identity": "requested CLI IDs; internal selection unverified", "formal_qualification": "UNASSESSED",
                      "validation": "JSON/Python AST/exact text; no application-code execution", "tool_calls": "forbidden",
                      "B_joint_gate_unchanged": True, "tokens": "all reported, including regressions; A cannot establish joint token benefit",
                      "cache_scope": "first/repeat exact context in persistent arm workers; OS/provider caches uncontrolled", "automatic_resume": False},
            "source_preparation": {"seconds": time.perf_counter() - started, "measurement_end": "before private protocol/derived manifest publication"}}
    spec_sha = digest(spec)
    write(output / "protocol.private.json", spec)
    for entry in workers.values():
        write(Path(entry["manifest_path"]), dict(entry["manifest_core"], protocol_sha256=spec_sha))
    write(output / "preparation.receipt.json", {"protocol_sha256": spec_sha, "total_seconds_before_this_receipt": time.perf_counter() - started,
                                               "models_dispatched": 0, "public_protocol_created": False})
    return {"protocol": str(output / "protocol.private.json"), "protocol_sha256": spec_sha, "models_dispatched": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "output-directory", "artifact-root", "binary", "git-binary", "model-catalog"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--control-revision", default="29cf112b4629d6b90504b079e95a5370c206a4cb")
    parser.add_argument("--treatment-revision", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.repo, args.output_directory, args.artifact_root, args.binary, args.git_binary,
                             args.control_revision, args.treatment_revision,args.model_catalog), indent=2))
