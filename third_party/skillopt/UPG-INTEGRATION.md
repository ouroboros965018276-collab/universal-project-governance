# Pinned SkillOpt source

Source: <https://github.com/microsoft/SkillOpt>

Commit: `343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c`

The complete upstream `skillopt/` research package, MIT `LICENSE`, original
`pyproject.toml`, and original `README.md` are retained. No upstream source file
has a local modification. `PROVENANCE.json` records a SHA-256 for every retained
upstream file. The source package includes benchmark-specific adapters for
provenance completeness; UPG does not import them or copy their datasets,
checkpoints, plugins, CI configuration, Git metadata, or provider dependencies.
The integration's `.gitattributes` preserves upstream blob bytes across checkout;
the pinned `gradient/reflect.py` contains original CRLF line endings.

UPG's optional Python 3.10+ offline optimizer reuses upstream `types`,
`gradient.reflect`, `gradient.aggregate`, `optimizer.clip`, `optimizer.skill`,
`optimizer.slow_update`, `optimizer.meta_skill`, and `envs.base` directly.
`evolution/skillopt_adapter.py` executes unchanged source in a private module
namespace and supplies the model capability at the `skillopt.model` import
boundary. The upstream provider router is never imported: it would eagerly
load provider SDKs and read credential environment variables. This explicit
dependency injection needs only Python's standard library for offline fixtures.
Importing the optional optimizer does not install packages or access accounts.

The injected callable receives `system`, `user`, `max_completion_tokens`, and
`stage`, and returns `(text, usage_dict_or_None)`. It must perform one attempt
and disable its own provider retries. The UPG wrapper reserves shared budget
for every attempt, including failure and retry, and records unavailable usage
as unknown. Provider/backend errors must report available `usage` on the error
object if an attempt consumed tokens. Provider selection and authorization are
the caller's responsibility.
The wrapper caps requested completion tokens at the remaining measured budget.
Input tokens remain unknown until a backend receipt arrives; this is a measured
token stop threshold, not a guarantee against single-call overshoot. A backend
must enforce its supplied completion cap and any provider-specific total limit.

`SourceBridge` exports only existing policy `statement` and `closure` prose.
It binds patches to the complete original model, unique rule/field identity,
and original field SHA-256, validates unique anchors, then uses upstream edit
application on a private copy. Missing or duplicate `insert_after` anchors
reject the entire patch before any canonical model can change. Protected UPG
hot-path rules, dependency closure, triggers, and thresholds have no write path.
Optimizer-side longitudinal memory is never written into governance policy.

`fixture_backend` is a deterministic synthetic engineering fixture. Its zero
token usage means no provider call happened; `measurement: synthetic` and
`fixture: true` must be retained. These fixtures establish plumbing and safety
behavior, never empirical learning effectiveness or real model cost.
