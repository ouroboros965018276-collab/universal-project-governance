"""Create a preregistered plan only; never execute an Agent."""
import argparse
import hashlib
import json
import pathlib
import random
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qualification.adapters.command_adapter import CommandAdapter
from qualification.trigger_suite import build

def build_manifest(round_id, adapters, repetitions, seed):
    protocol = json.loads((ROOT / "qualification/protocol/qualification-v3.json").read_text(encoding="utf-8"))
    freeze = json.loads((ROOT / "qualification/FREEZE.json").read_text(encoding="utf-8"))
    if not round_id or not protocol["sampling"]["locked_repetitions_per_cell_min"] <= repetitions <= protocol["sampling"]["locked_repetitions_per_cell_max"]:
        raise ValueError("round ID and preregistered repetition range required")
    families = [a.config.get("agent", {}).get("family") for a in adapters]
    if len(set(families)) != len(families) or len(families) < protocol["sampling"]["minimum_agent_families"]:
        raise ValueError("at least three distinct declared families required")
    for adapter in adapters: adapter.require_locked_holdout()
    behavioral = json.loads((ROOT / "qualification/fixtures/holdout/locked/behavioral-labs.json").read_text(encoding="utf-8"))["labs"]
    handoff = json.loads((ROOT / "qualification/fixtures/holdout/locked/handoff-labs.json").read_text(encoding="utf-8"))["labs"]
    rng = random.Random(seed); trials = []
    def add(adapter, lab, rep, kind, arm, condition=None):
        identity = adapter.identity(); family = adapter.config["agent"]["family"]
        pair = "%s:%s:%s:%d:%s" % (round_id, kind, lab["id"], rep, family)
        tid = str(uuid.uuid5(uuid.NAMESPACE_URL, pair + ":" + arm + ":" + str(condition)))
        slot = dict(identity, trial_id=tid, round_id=round_id, kind=kind, scenario_id=lab["id"], arm=arm, pair_id=pair, repetition=rep, agent=adapter.config["agent"], isolation_attestation=adapter.config["isolation_attestation"], tool_profile=adapter.config.get("tool_profile"), budget_profile=adapter.config.get("budget_profile"))
        if condition:
            slot["handoff_condition"] = condition
            slot["source_isolation_attestation"] = adapter.config["isolation_attestation"]
            slot.update({"source_" + k: v for k, v in identity.items() if k != "adapter_id"})
            slot.update(source_agent_family=family, source_model_id=adapter.config["agent"]["model_id"], source_scaffold_version=adapter.config["agent"]["scaffold_version"])
        trials.append(slot)
    # Repetitions interleave families/scenarios; arms/conditions randomize inside matched blocks.
    for rep in range(1, repetitions + 1):
        blocks = [(a, lab) for a in adapters for lab in behavioral]; rng.shuffle(blocks)
        for adapter, lab in blocks:
            arms = ["A0", "A1", "A2"]; rng.shuffle(arms)
            for arm in arms: add(adapter, lab, rep, "behavioral", arm)
        blocks = [(a, lab) for a in adapters for lab in handoff]; rng.shuffle(blocks)
        for adapter, lab in blocks:
            conditions = ["present", "ablated"]; rng.shuffle(conditions)
            for condition in conditions: add(adapter, lab, rep, "handoff", "A2", condition)
    for case in build(json.loads((ROOT / "qualification/fixtures/trigger-families.json").read_text(encoding="utf-8"))):
        add(adapters[0], case, 1, "trigger", "A2")
    for mutant in protocol["evaluator_validity"]["required_mutants"]:
        lab = behavioral[0]; add(adapters[0], lab, 1, "mutation", "A2")
        trials[-1]["mutation_id"] = mutant
        trials[-1]["pair_id"] += ":" + mutant
        trials[-1]["trial_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, trials[-1]["pair_id"]))
    for order, slot in enumerate(trials): slot["order"] = order
    return {"schema_version": 1, "round_id": round_id, "qualification_fingerprint": freeze["qualification_fingerprint"], "protocol_revision": protocol["protocol_revision"], "randomization_seed": seed, "order_method": "blocked-temporally-interleaved", "trials": trials}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--round-id", required=True); parser.add_argument("--adapters", nargs="+", required=True); parser.add_argument("--repetitions", type=int, default=8); parser.add_argument("--seed", type=int, required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args(); output = pathlib.Path(args.output)
    if output.exists(): raise ValueError("registered round already exists")
    data = build_manifest(args.round_id, [CommandAdapter.from_path(p) for p in args.adapters], args.repetitions, args.seed)
    output.write_bytes((json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print("Round registered; no Agent executed.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
