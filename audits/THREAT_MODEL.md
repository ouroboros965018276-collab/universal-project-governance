# Threat Model — Pre-release

Scope: Universal Project Governance Skill and its shipped helper scripts.

## Primary risks

| Risk | Failure mode | Current mitigation | Evidence surface |
|---|---|---|---|
| Unsafe cleanup/deletion | Agent removes an artifact because a shallow search found no references | Evidence-before-claim + safe deletion protocol + consumer/retention checks | `SKILL.md`, maintenance reference, behavior evals |
| Secret exposure by scanner | Helper reads or emits credentials/private keys | No network; secret-like filename/suffix exclusion; symlink avoidance; text/size bounds | unit tests + `tools/security_audit.py` |
| Path escape via symlink | Scanner follows project symlink into external filesystem | Directory/file symlinks skipped | unit tests |
| Command injection | Runtime helper constructs shell command from project data | `subprocess` uses argv arrays; `shell=True` prohibited by static audit | security audit |
| Fabricated completion evidence | Agent claims validation/debt-free/migration completion without proof | Proof-carrying change and closure gates | validation reference + behavior evals |
| Documentation duplication | Skill creates its own docs inside a mature project or another Skill namespace | One-source-of-truth + interoperability ownership rule | interoperability eval |
| Over-triggering | Read-only questions cause invasive governance work | explicit negative activation boundary + 10 negative trigger cases | `SKILL.md` description + trigger set |
| Under-triggering | Project-changing task bypasses governance | explicit positive activation boundary + 10 positive trigger cases | trigger set |
| Prompt/repository injection | Untrusted project text attempts to override higher-priority instructions | conflict priority and project-instruction hierarchy; do not treat arbitrary docs as authority | `SKILL.md` + interoperability reference |
| Supply-chain drift in release tests | Tooling updates invalidate assumptions | pinned `skills-ref==0.1.1`, pinned `skills@1.7.0`, explicit CI versions | GitHub Actions logs |

## Residual risk before stable

The largest intentionally open risk is behavioral: deterministic tests cannot prove every AI host will activate the Skill correctly or follow its gates under pressure. Stable publication therefore remains blocked until trigger and behavior evals are run in fresh real-agent contexts and reviewed for false positives, false negatives, unsafe actions, and unreasonable overhead.
