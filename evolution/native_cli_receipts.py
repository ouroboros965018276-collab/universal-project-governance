"""Pure native receipt classification; never execute current or historical work."""
import copy
import hashlib
import json
import math


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _state_digest(files):
    hashes = {name: hashlib.sha256(text.encode("utf-8")).hexdigest()
              for name, text in files.items()}
    return hashlib.sha256(_canonical(hashes)).hexdigest()


def replay_current_validation(task, journal, *, receipt_file_states, verify_validation):
    """Verify every occurred execution, then classify the final replay snapshot.

    The existing independent execution reader is supplied as verify_validation.
    Its errors propagate: unknown/missing receipts or cleanup never become a
    known task failure. Missing or stale final validation is a known NOT_RUN,
    with a non-None sentinel suitable for the existing pure quality projection.
    """
    files = copy.deepcopy(task["initial_files"])
    validation, validation_state, count = None, None, 0
    for event, files in receipt_file_states(task, journal):
        wall = event["wall_seconds"]
        if type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0:
            raise ValueError("native-tool-time")
        if event["tool"] == "repo_validate":
            count += 1
            result = event["result"]
            if (result.get("execution", {}).get("receipt_ref") !=
                    "validation-%03d/result.json" % count):
                raise ValueError("native-historical-execution-ordinal")
            verify_validation(result, task, files)
            validation, validation_state = result, event["state_sha256"]
    current = _state_digest(files)
    if journal and journal[-1]["state_sha256"] != current:
        raise ValueError("native-final-journal-state")
    not_run = validation_state != current
    reason = "required-current-project-validation-missing"
    return {
        "files": files,
        "supplied_validation": ({"ok": False, "failures": [reason]}
                                if not_run else validation),
        "extra_failures": [reason] if not_run else [],
        "not_run": not_run,
        "current_snapshot_validation": "NOT_RUN" if not_run else "EXECUTED",
        "all_occurred_execution_receipts_verified": True,
        "occurred_execution_receipt_count": count,
    }
