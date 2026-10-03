"""Reuse the generated runtime's documented schema subset."""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("upg_contract_validator", ROOT / "universal-project-governance/scripts/state_tool.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate_node = module.validate_node
