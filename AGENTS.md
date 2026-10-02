# AGENTS.md

## Repository contract

This repository uses a **compiled governance architecture**.

### Canonical source

Edit governance semantics only under:

```text
governance-src/
```

Do **not** hand-edit:

```text
universal-project-governance/
```

That directory is generated output.

### Required workflow after source changes

```bash
python compiler/compile_governance.py --write --confirm-generated-runtime-update
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_repository.py .
python -m unittest discover -s tests -v
```

Then run the complete CI/release gate before claiming completion.

### Invariants

- one semantic rule, one canonical definition;
- profiles activate policies but never redefine them;
- Policy IR stays declarative and non-executable;
- complexity budgets are release blockers, not suggestions;
- schema-first JSON is canonical for governance state; rendered Markdown is a view;
- generated runtime integrity is tamper-evident, not an access-control claim;
- current-state docs describe the present project; release audits may remain historical/frozen.

If a requested change would weaken these invariants, require explicit owner intent and document the design decision/version impact.
