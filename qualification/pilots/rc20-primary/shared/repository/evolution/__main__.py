"""Offline evolution CLI. No model or credential is selected implicitly."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys


def load_callable(name):
    if name is None:
        return None
    module, separator, function = name.partition(":")
    if not separator or not module or not function.isidentifier():
        raise ValueError("callback must be an explicitly trusted module:function")
    callback = getattr(importlib.import_module(module), function)
    if not callable(callback):
        raise ValueError("configured callback is not callable")
    return callback


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "ablate", "paired"):
        sub = commands.add_parser(name)
        sub.add_argument("--spec", default="evolution/protocol/upg-evolution-v2.json")
        sub.add_argument("--repo", default=".")
        sub.add_argument("--output", default="eval-workspaces/evolution/" + ("run.json" if name == "run" else "matrix"))
        sub.add_argument("--runner", help="trusted module:function returning actual task receipts")
        sub.add_argument("--backend", help="trusted module:function for UPG reflection model calls")
        if name == "run":
            run_parser = sub
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--disable", action="append", default=[], choices=["reflection", "annealing", "de", "curvature"])
    run_parser.add_argument("--ordinary", action="store_true", help="ordinary perturbation control")
    for name in ("inspect", "verify", "propose"):
        sub = commands.add_parser(name)
        sub.add_argument("--run", required=True, help="checkpoint JSON path")
        if name == "propose":
            sub.add_argument("--repo", default=".")
            sub.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in {"run", "ablate", "paired"}:
            from .controller import run_search
            protocol = json.loads(Path(args.spec).read_text(encoding="utf-8"))
            if args.command == "paired":
                from .paired import collect, summarize as summarize_pairs
                result = summarize_pairs(collect(args.repo, protocol, args.output, load_callable(args.runner)))
            elif args.command == "ablate":
                from .ablation import run_matrix
                result = run_matrix(args.repo, protocol, args.output, runner=load_callable(args.runner),
                                    backend=load_callable(args.backend))
            else:
                result = run_search(args.repo, protocol, args.output, runner=load_callable(args.runner),
                                    backend=load_callable(args.backend), resume=args.resume,
                                    disabled=args.disable, ordinary=args.ordinary)
                result = summarize(result)
        else:
            run = json.loads(Path(args.run).read_text(encoding="utf-8"))
            if args.command == "inspect":
                result = summarize(run)
            elif args.command == "verify":
                from .promotion import verify
                result = verify(run)
            else:
                from .promotion import propose
                result = propose(run, Path(args.repo), Path(args.output))
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False))
        if args.command == "verify":
            return 0 if result.get("empirical", {}).get("status") == "PASS" else 1
        if args.command == "propose" and result.get("status") != "PROPOSED":
            return 1
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, KeyError, TypeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


def summarize(run):
    return {key: run.get(key) for key in ("run_id", "stage", "status", "iteration", "best_candidate_id",
                                         "operator_counts", "budget", "empirical_status")} | {
        "candidate_count": len(run.get("candidates", [])), "event_count": len(run.get("events", []))}


if __name__ == "__main__":
    raise SystemExit(main())
