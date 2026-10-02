# Pre-release Audit — 2.0.0-rc.2

Audit date: 2026-10-02  
Status: **PRE-RELEASE ENGINEERING GATES PASS — NOT STABLE. Real-agent behavioral gates remain release-blocking.**

## Candidate identity

- Skill: `universal-project-governance`
- Version: `2.0.0-rc.2`
- Release class: pre-release candidate, not stable
- Repository: `ouroboros965018276-collab/universal-project-governance`
- Repository lineage: created empty for this project; no unrelated legacy-repository Git history inherited
- Installable package: `universal-project-governance-v2.0.0-rc.2.zip`
- Canonical package SHA-256: `13e9b7c643533aa337d416f1f041b981428138ecb290c0df0765de7bc18dddf5`
- CI provenance rule: the latest successful `validate-pre-release` run for the current release-relevant HEAD is authoritative; GitHub preserves the exact commit/run linkage independently of this prose
- Baseline input: user-supplied `2.0.0-rc.1` archive, audited and reorganized/hardened rather than uploaded unchanged

## Engineering and installation evidence

| Gate | Result | Evidence |
|---|---|---|
| Skill bundle validation | **PASS** | `SKILL.md` 200 lines; 0 bundled warnings |
| Repository release invariants | **PASS** | exactly 1 source Skill; version/eval/license invariants satisfied |
| Security static audit | **PASS** | no governed network imports, `shell=True`, dangerous dynamic execution, symlink-following, or secret-like token patterns |
| Self-governance validation | **PASS** | 3 repository governance artifacts; 0 warnings |
| Official Agent Skills reference validator | **PASS** | `skills-ref==0.1.1`; explicit “Upstream Agent Skills validation passed.” |
| Python 3.8 runtime | **PASS** | 11/11 tests + inspector + deterministic packager |
| Python 3.11 runtime | **PASS** | 11/11 tests + inspector + deterministic packager |
| Python 3.13 runtime | **PASS** | 11/11 tests + inspector + deterministic packager |
| Skills CLI local discovery | **PASS** | pinned `skills@1.7.0` found the single Skill |
| Skills CLI clean local Codex install | **PASS** | installed `universal-project-governance`; repo-only tests/evals excluded |
| Skills CLI private-GitHub install | **PASS** | cloned this private repository and installed the named Skill successfully |
| Deterministic release package | **PASS** | Python 3.8 / 3.11 / 3.13 produced identical SHA-256 |
| Current GitHub Actions workflow | **PASS** | latest pre-release workflow for the audited release-relevant HEAD must be green before promotion |

## Reproducible package identity

The installable Skill archive is:

`universal-project-governance-v2.0.0-rc.2.zip`

SHA-256:

`13e9b7c643533aa337d416f1f041b981428138ecb290c0df0765de7bc18dddf5`

The same digest was produced independently on Python 3.8, 3.11, and 3.13. This establishes byte-for-byte reproducibility for the candidate package across the tested runtimes.

## Baseline-to-RC2 comparison

The user-supplied RC1 archive was revalidated locally before comparison: bundle validation passed, all 7 RC1 helper tests passed, and its deterministic package SHA-256 was `6dc9827ceddece9525be3845e95236cc815050e08bc49f938294833c0e34a074`.

RC2 preserves the original governance concept and the detailed reference/asset semantics while hardening the engineering boundary:

- `SKILL.md` remains 200 lines and keeps the same one-Skill/five-closure design; version metadata advances to RC2.
- Detailed reference files and bootstrap assets retain their canonical content identity from RC1.
- repository-only tests/evals/packaging/security tooling moved outside the installed Skill, reducing consumer payload and avoiding development machinery in user projects.
- runtime helpers were hardened, including symlink-safe reference scanning.
- repository validation, threat modeling, security checks, multi-runtime tests, and real Skills CLI installation were added.

## Drift detected and closed during audit

An earlier pre-release run produced a package digest different from the expected audited source. The discrepancy was not accepted. Blob-level comparison isolated it to a non-functional explanatory comment omitted during repository transfer; executable logic was unchanged.

The source was reconciled and the complete pipeline rerun. The candidate package digest above is the byte identity used for RC2 evidence.

## Runtime/helper safety findings

The shipped helper surface is intentionally narrow:

- no network dependency;
- target-project inspection is read-only unless an explicit scanner output path is supplied;
- content scanners skip symlinked files/directories;
- secret-like file names and private-key formats are conservatively excluded;
- common VCS/vendor/build/cache directories are excluded;
- reference/duplicate/TODO/churn findings are signals, not automatic deletion authority;
- subprocess Git use is argv-based rather than `shell=True`;
- untouched governance templates fail validation instead of producing a false success.

The repository-level threat model is recorded in `audits/THREAT_MODEL.md`.

## Distribution-boundary finding

Repository engineering assets are intentionally outside the installable Skill. The installed target contains the Skill contract, references, bootstrap assets, runtime helpers, and license; it does **not** copy repository-only `tests/`, `evals/`, `audits/`, or CI machinery into consumer projects.

This reduces installation noise and context footprint without weakening the governance contract.

## Stable-release blockers still open

The following are evidence deliberately required before stable publication:

1. Trigger behavior must be measured using `evals/trigger_set.json` in real compatible agent environments, with repeated runs and review of false-positive/false-negative activation.
2. All behavior cases in `evals/evals.json` must be run from fresh contexts with the Skill and against a no-Skill or previous-stable baseline.
3. Critical governance failures must be zero: unsafe deletion, fabricated evidence/chronology, false completion or debt-free claims, duplicate truth, namespace collision, or ignored validation failure.
4. Token/context/latency overhead must be reviewed so the Skill does not impose disproportionate ceremony.
5. Any behavioral finding must be fixed in a new RC and the complete deterministic + behavioral gate rerun.

## Audit conclusion

`2.0.0-rc.2` is **engineering-valid and installation-valid as a private pre-release candidate** on the tested GitHub/Python/Skills-CLI matrix, provided the current release-relevant HEAD has a successful `validate-pre-release` run.

It is **not yet justified as a stable public release**, because deterministic validation cannot prove cross-model activation quality or real-agent behavioral effectiveness. Stable promotion remains blocked until those empirical gates are completed with evidence.
