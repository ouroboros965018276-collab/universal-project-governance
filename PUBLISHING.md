# Publishing and Release Gates

The installable Skill is the compiler-generated `universal-project-governance/` directory.

## RC4 source/runtime gate

Before any candidate promotion:

```bash
python compiler/compile_governance.py --check
python tools/governance_lint.py .
python tools/validate_repository.py .
python tools/validate_skill_bundle.py universal-project-governance
python universal-project-governance/scripts/validate_integrity.py universal-project-governance
python -m unittest discover -s tests -v
python tools/package_release.py universal-project-governance --output-dir dist
```

GitHub CI must additionally pass:

- Python 3.8 / 3.11 / 3.13;
- upstream `skills-ref==0.1.1`;
- Skills CLI discovery and clean installation;
- default-branch private-GitHub installation;
- security static audit;
- deterministic release package.

## Complexity gate

The release fails on deterministic governance defects including:

- duplicate/invalid policy IDs;
- missing dependency references;
- dependency cycles;
- orphan policies;
- blocking rules without evidence contracts;
- unknown profile activations;
- conflicts inside a rule closure;
- runtime `SKILL.md` over budget;
- hot path/default rule closure over budget;
- excess runtime Markdown;
- source/runtime compiler drift.

Fuzzy semantic-duplicate signals are advisory only.

## Candidate identity

A candidate is identified by:

1. semantic prerelease version;
2. canonical source state in Git;
3. compiler-generated runtime identity;
4. deterministic release ZIP SHA-256;
5. successful CI for the release-relevant HEAD.

Do not create self-referential audit loops that require a document to contain the run/commit created by editing itself.

## Stable behavioral gate

Stable remains blocked until empirical evaluation demonstrates:

- trigger false-positive/false-negative behavior across supported agents;
- fresh-context with-Skill vs no-Skill/previous-stable comparisons;
- Agent A → Agent B handoff recovery;
- zero critical unsafe-deletion, fabricated-evidence, false-completion, duplicate-truth, or ignored-validation failures;
- acceptable context/token/latency overhead.

Any material behavioral finding creates a new RC and reruns deterministic + empirical gates.

## Public release

Before changing the private repository to Public:

- verify history contains no unrelated private material/secrets;
- confirm branch/repository protection available at publication tier;
- verify README/version/tag/artifact checksum agree;
- perform a clean install from the public repository;
- publish the candidate/stable audit evidence.
