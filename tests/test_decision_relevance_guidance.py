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
        self.assertEqual(core["project_binding"]["git_checkpoint"], {'enabled': False, 'min_interval_seconds': 300, 'allowed_paths': [], 'status_paths': [], 'bootstrap': True, 'watcher': {'configuration': {'enabled': False, 'poll_seconds': 5, 'quiet_seconds': 15, 'validators': []}, 'supervisor': {'enabled': False}}})
        # RC20.2 adds this explicit optional capability; all earlier core fields
        # retain their original digest instead of silently refreshing it.
        core["project_binding"] = {key: value for key, value in core["project_binding"].items()
                                   if key != "git_checkpoint"}
        self.assertEqual(digest(core), "6d515c0a2a61597057a8618d32d805e2ea2b29d894eaa5eed1b0bdadf67b9f94")
        other = [g for g in model["execution_guidance"] if g["id"] != "decision_relevance"]
        self.assertEqual(digest(other), "8e36e60630f7603e5085dc7d8954eaab3096db96a522a5069f328c51bb8c0367")
        old_git = ("Git checkpoints follow meaningful verified stages, risk or handoff boundaries under project/user policy; "
                   "group related edits, inspect the diff, skip unchanged/duplicate status-only commits; "
                   "never commit per tool call or push without authorization.")
        helper_git = 'Git: git-configure explicitly enables scope/bootstrap; begin/finish save verified stages with cooldown/dedup and completion or explicit handoff/risk flush. Hosts without lifecycle: configure local validator argv, then use foreground git-watch session: --host codex-cli runs the existing official CLI without a daemon; --host stdin binds to an owned project-only channel until EOF; --command requires a host that waits for the actual project session. The observer saves stable validated changes and yields to active work only while that session lives. Host exit or session-owner crash terminates its observer subtree; active sessions recover supervisor and worker exits. Without a reliable host-session end signal, use finite checkpoints/ticks; never infer parent PID or detach. No OS startup, host configuration injection or session-external residency; explicit stop stays stopped within the session. Respect disabled/scope/dirty-index guards; report blocked/unavailable; no implicit push.'
        operational = [dict(group) for group in model["operational_guidance"]]
        tracked = next(group for group in operational if group["id"] == "tracked_state")
        self.assertEqual(tracked["statement"].count(helper_git), 1)
        # Normalize only the reviewed executable-Git route; unrelated workflow
        # text and every other group still use the original frozen digest.
        tracked["statement"] = tracked["statement"].replace(helper_git, old_git)
        self.assertEqual(digest(operational),
            "45d6df5e0e0f91de53b0906f6769fdd25bccde35822b1f426040e0980e5e094b")

if __name__ == "__main__":
    unittest.main()
