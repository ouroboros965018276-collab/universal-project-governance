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
        other = json.loads(json.dumps([g for g in model["execution_guidance"] if g["id"] != "decision_relevance"]))
        historical = json.loads((ROOT / "tests/fixtures/engineering-study-rc19-model-delta.json").read_bytes())
        reviewed = next(g for g in other if g["id"] == "evidence_fidelity")
        # RC20.9 reviews only this guidance delta; every unrelated group retains
        # its original identity. Historical study buffers remain historical.
        reviewed["statement"] = historical["full_evidence_fidelity_statement"]
        complete = next(g for g in other if g["id"] == "complete_change")
        task_prefix = (
            "Before changes, frame the user's outcome, scope/retained contracts, observable acceptance, "
            "current facts and material unknowns; choose the next proportionate check. Local low-risk "
            "work may be one short unit. Advance through verifiable units; check actual results before "
            "dependents and revise affected remaining work when evidence changes, preserving intent "
            "and original start facts. ")
        # RC20.10 adds this reviewed task-start/progress prefix. Assert its exact
        # identity and the untouched historical tail before normalizing it.
        self.assertEqual(complete["statement"], task_prefix + historical["full_complete_change_statement"])
        complete["statement"] = historical["full_complete_change_statement"]
        self.assertEqual(digest(other), "8e36e60630f7603e5085dc7d8954eaab3096db96a522a5069f328c51bb8c0367")
        old_git = ("Git checkpoints follow meaningful verified stages, risk or handoff boundaries under project/user policy; "
                   "group related edits, inspect the diff, skip unchanged/duplicate status-only commits; "
                   "never commit per tool call or push without authorization.")
        helper_git = 'Git: git-configure explicitly enables scope/bootstrap; begin/finish save verified stages with cooldown/dedup and completion or explicit handoff/risk flush. Hosts without lifecycle: configure local validator argv, then use foreground git-watch session: --host codex-cli runs the existing official CLI without a daemon; --host stdin binds to an owned project-only channel until EOF; --command requires a host that waits for the actual project session. The observer saves stable validated changes and yields to active work only while that session lives. Host exit or session-owner crash terminates its observer subtree; active sessions recover supervisor and worker exits. Without a reliable host-session end signal, use finite checkpoints/ticks; never infer parent PID or detach. No OS startup, host configuration injection or session-external residency; explicit stop stays stopped within the session. Respect disabled/scope/dirty-index guards; report blocked/unavailable; no implicit push.'
        operational = [dict(group) for group in model["operational_guidance"] if group["id"] != "engineering_workflow"]
        tracked = next(group for group in operational if group["id"] == "tracked_state")
        old_tracked_prefix = "Non-trivial/cross-session: stable workflow ID; minimal project_tool begin checkpoint if available. "
        task_tracked_prefix = (
            "Non-trivial/cross-session: stable workflow ID; project_tool begin with a bounded task_contract: "
            "scope, acceptance, constraints, unknowns and independently verifiable units with dependencies; "
            "change.function remains the original goal. One unit suffices when appropriate; unresolved "
            "questions can start with investigation. Track current results/next action through task_progress "
            "in existing partial/blocked/complete outcomes; passed units need current source or canonical "
            "validation evidence, and dependents require passed prerequisites. Explicitly invalidate stale "
            "results; replan affected remaining units with a new revision and evidence-based reason, "
            "preserving completed-unit definitions and original scope/acceptance. New tracked completion "
            "requires task acceptance, all current required units and evidence_fidelity. Old active "
            "workflows/history remain factual; do not backfill plans. Direct reports without an active "
            "workflow are observations, never proof of governed task execution. ")
        self.assertTrue(tracked["statement"].startswith(task_tracked_prefix))
        tracked["statement"] = old_tracked_prefix + tracked["statement"][len(task_tracked_prefix):]
        self.assertEqual(tracked["statement"].count(helper_git), 1)
        # Normalize only the reviewed executable-Git route; unrelated workflow
        # text and every other group still use the original frozen digest.
        tracked["statement"] = tracked["statement"].replace(helper_git, old_git)
        self.assertEqual(digest(operational),
            "45d6df5e0e0f91de53b0906f6769fdd25bccde35822b1f426040e0980e5e094b")

if __name__ == "__main__":
    unittest.main()
