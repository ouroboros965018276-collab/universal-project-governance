"""Canonical safeguards for compact expression; no tool or model execution."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()

class DecisionRelevanceGuidanceTests(unittest.TestCase):
    def test_compact_expression_preserves_core_and_unrelated_guidance(self):
        model = json.loads((ROOT / "governance-src/model/governance-model.json").read_bytes())
        core = {k: v for k, v in model.items()
                if k not in ("version", "execution_guidance", "operational_guidance")}
        self.assertEqual(digest(core), "6d515c0a2a61597057a8618d32d805e2ea2b29d894eaa5eed1b0bdadf67b9f94")
        other = [g for g in model["execution_guidance"] if g["id"] != "decision_relevance"]
        self.assertEqual(digest(other), "8e36e60630f7603e5085dc7d8954eaab3096db96a522a5069f328c51bb8c0367")
        self.assertEqual(digest(model["operational_guidance"]),
            "b3cf14c5cc71af7a35ecfb771de7fbb404eaaa9e117da90056d155193c86e835")

if __name__ == "__main__":
    unittest.main()
