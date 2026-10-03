"""Canonical qualification contracts shared by registration and evidence admission."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("upg_contract_validator", ROOT / "universal-project-governance/scripts/state_tool.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate_node = module.validate_node

def frozen_candidate():
    """Resolve identity and analysis settings together, rejecting live surface drift."""
    from tools.qualification_freeze import expected
    identity = json.loads((ROOT / "qualification/FREEZE.json").read_text(encoding="utf-8"))
    if expected(ROOT) != identity:
        raise ValueError("frozen source/runtime/evaluator drift detected")
    return {
        "identity": identity,
        "protocol": json.loads((ROOT / "qualification/protocol/qualification-v3.json").read_text(encoding="utf-8")),
        "thresholds": json.loads((ROOT / "qualification/protocol/thresholds.json").read_text(encoding="utf-8")),
    }

def configuration_errors(thresholds, protocol, candidate=None):
    """A frozen identity authorizes only its own finite JSON settings."""
    candidate = frozen_candidate() if candidate is None else candidate
    errors = []
    for name, value in [("thresholds", thresholds), ("protocol", protocol)]:
        try:
            canonical = lambda data: json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if canonical(value) != canonical(candidate[name]):
                errors.append(name + " differs from frozen candidate configuration")
        except (ValueError, TypeError):
            errors.append(name + " is not a finite JSON configuration")
    return errors
