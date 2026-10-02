#!/usr/bin/env python3
"""Classify governance evidence/report level from observable task facts."""
from __future__ import annotations

import argparse
import json


RISK_FLAGS = (
    "refactor", "architecture", "security", "privacy", "migration", "api",
    "schema", "database", "data_integrity", "deployment", "compatibility", "destructive",
)


def classify(args) -> dict:
    strong_risk = any(getattr(args, name) for name in RISK_FLAGS)
    broad = args.files_changed > 10 or args.lines_changed > 300 or args.lines_deleted > 100

    if args.release:
        level = "audit"
    elif args.user_report or strong_risk or broad:
        level = "engineering"
    else:
        level = "change-note"

    standalone = level in {"engineering", "audit"}
    if level == "change-note" and args.mode == "minimal":
        standalone = False
    if level == "change-note" and args.mode == "standard":
        standalone = False

    execution_audit = args.explicit_execution_audit or (
        args.mode == "evaluation" and level in {"engineering", "audit"}
    )
    feedback = args.feedback_event
    handoff = args.handoff

    return {
        "mode": args.mode,
        "report_level": level,
        "standalone_report": standalone,
        "execution_audit": execution_audit,
        "handoff_snapshot": handoff,
        "feedback_record": feedback,
        "reason": {
            "strong_risk": strong_risk,
            "broad_change": broad,
            "release": args.release,
            "user_report": args.user_report,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("minimal", "standard", "evaluation"), default="standard")
    ap.add_argument("--files-changed", type=int, default=1)
    ap.add_argument("--lines-changed", type=int, default=1)
    ap.add_argument("--lines-deleted", type=int, default=0)
    for name in RISK_FLAGS:
        ap.add_argument("--" + name.replace("_", "-"), dest=name, action="store_true")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--user-report", action="store_true")
    ap.add_argument("--explicit-execution-audit", action="store_true")
    ap.add_argument("--feedback-event", action="store_true")
    ap.add_argument("--handoff", action="store_true")
    args = ap.parse_args()
    print(json.dumps(classify(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
