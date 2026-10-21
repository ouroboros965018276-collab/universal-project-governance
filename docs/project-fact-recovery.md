# Project fact recovery

Use recovery when a maintained task was interrupted, its handoff is missing or
stale, documented behavior contradicts current artifacts, or analysis stops
producing evidence. Ordinary local tasks retain the existing lightweight path.
Recovery does not install tools, execute project programs, search entire trees,
or require a second report directory.

The optional helper writes JSON to stdout only:

```bash
python scripts/state_tool.py recover /project/root --scope src/entry.py --scope config/plugins.json --handoff .governance/handoff.json --git-binary /absolute/path/to/git
```

Use an actually available Python 3.8+ executable. Scope entries are explicit
project-relative files, not globs or directories. Omit unavailable handoff/Git
inputs; their absence remains a gap. A referenced file outside the explicit
scope is not followed. File count, depth and byte limits bound recovery; an
exhausted budget does not establish coverage. Links, reparse points, hard-linked
files, credential paths and VCS internals are rejected as file inputs.

Git inspection uses index/object metadata and local bounded-byte comparison;
it avoids worktree-conversion commands that can launch project clean filters.
Active filtering or normalization rules leave content validity unknown. Git
metadata has its own timeout and bounded stdout/stderr reads, with limits scaled
to the encoded scope paths. The optional handoff has one reserved read attempt
in addition to the 64 scoped files. A file changed after observation becomes
unavailable before evidence inheritance; matching an earlier hash cannot make it
current again. These limits are not an operating-system isolation guarantee.

The returned view distinguishes observed source identity, static declarations,
referenced evidence, hypotheses and contradictions. Python imports and package
entry declarations are clues; they are not a complete dynamic call graph.
Opaque artifacts or behavior mismatches require a task-relevant specialized
method and actual validation, not automatic installation or speculative claims.

Hash matches establish byte identity. They do not establish correct behavior,
coverage, environment compatibility or historical intent. Dynamic evidence also
needs current tested revision, input/configuration/environment references and
coverage; eligibility for review is not a semantic PASS. Preserve unknowns,
original failed evidence and pending retests.

Merge justified decision changes and carried references into the existing
current handoff. Do not copy the entire source/history into another truth store.
Repeated attempts with the same method and unchanged evidence require another
method or a bounded blocker. The helper never reconstructs private reasoning or
invents why a previous actor made a change.

The planner emits optional recovery guidance only for relevant signals, while
the existing policy closure remains authoritative. The helper is compiler-owned;
change `governance-src/` and regenerate the installed bundle.

Tool-task regression fixtures cover stale PASS records and interrupted
consumer migrations with current-hash and positive artifact contracts. Their
mechanical success proves grader behavior, not model efficacy. Independent model
quality, total tokens and complete callback time remain separate release gates.
