"""UTF-8 BOM from Windows writers must not change JSON helper semantics."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "universal-project-governance"


class WindowsJsonInputs(unittest.TestCase):
    def test_planner_context_bom_is_equivalent_and_invalid_json_stays_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            context = Path(temporary) / "context.json"
            value = {"operation": "edit", "domains": ["code"], "signals": [], "profiles": [], "risk": {}}
            command = [sys.executable, str(RUNTIME / "scripts/plan_governance.py"), "--context", str(context), "--json"]
            context.write_text(json.dumps(value), encoding="utf-8")
            plain = subprocess.run(command, capture_output=True)
            context.write_text(json.dumps(value), encoding="utf-8-sig")
            bom = subprocess.run(command, capture_output=True)
            self.assertEqual(plain.returncode, 0)
            self.assertEqual(bom.returncode, 0, bom.stderr)
            self.assertEqual(json.loads(plain.stdout), json.loads(bom.stdout))
            context.write_text('{"operation":', encoding="utf-8-sig")
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_state_and_project_json_loaders_accept_bom(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text('{"说明":"真实输入"}', encoding="utf-8-sig")
            code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                    "from pathlib import Path; import state_tool,project_tool; "
                    "a=state_tool.load(Path(sys.argv[2])); b=project_tool.load_json(sys.argv[2]); "
                    "assert a==b=={'说明':'真实输入'}")
            result = subprocess.run([sys.executable, "-c", code, str(RUNTIME / "scripts"), str(path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
