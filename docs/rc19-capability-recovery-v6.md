# RC19 recovery capability probe v6

The four-call probe completed with **4/4 strict task passes**, **12/12 positive artifact checks**, and **28 actual broker tool calls**. Independent verification passed. The preregistered **net-benefit gate remains FAIL**; this probe supports access and scoped task correctness for these four calls, not a benefit or production qualification claim.

The fixed public development task exercised current-fact recovery in one synthetic task family. Two requested OpenAI models (`gpt-6-sol`, `gpt-6-luna`, low effort) each completed one control/treatment pair. The control used the RC18 baseline; the treatment used the frozen RC19 candidate. Both received the same task, bounded repository tools, static grader, HTTP transport profile and exact tool permissions. Final independent task sets were not used in this probe.

| Requested model | Control tokens | Treatment tokens | Token change | Control callback s | Treatment callback s | Callback change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-6-luna | 118,274 | 101,435 | −14.24% | 29.1691 | 28.2844 | −3.03% |
| gpt-6-sol | 102,588 | 102,120 | −0.46% | 30.5329 | 31.2755 | +2.43% |
| Pooled | 220,862 | 203,555 | −7.84% | 59.7020 | 59.5599 | −0.24% |

All four turns reported **424,417 total tokens**: 420,243 input and 4,174 output. Cached input was 354,560 tokens, included in input. The 51 reasoning tokens were a subset of output and were not added again. These are CLI-reported usage counts; provider billing and internal attempts are unobserved. Callback time totaled 119.2619 s; CLI time totaled 116.0062 s. The collector recorded 120.9370 s against the 900 s budget. Source preparation (3.9603 s, zero model calls) and collector setup (1.5412 s) are separately reported. Caps were four calls and 500,000 reported tokens; this is not a guaranteed provider token pre-cap.

The independent audit recomputed all 36 registered raw artifact hashes, four receipt hashes and four canonical result hashes. It matched the four unique CLI threads and harness requests, exact frozen prompts, argument lists, capability/source/runtime/task bindings, and CLI/broker tool-and-argument multisets. It re-read final repository files and mechanically repeated the JSON/text/AST grading, including required initial clue reads before the first successful patch and current validation/status evidence. No application code or model was executed by the audit. All four calls were fresh; none used a local receipt cache. Retained per-call `pending.json` files are original dispatch evidence: the terminal receipts are completed and the collector pending field is null.

The pooled timing point is too small to establish acceleration, and the Sol callback timing regressed. Each model has only one task in one family. The legacy bootstrap's degenerate intervals are diagnostic, not independent precision; the required joint-family intervals are unavailable and family coverage gates fail. Two models from the same provider do not establish multiple provider families. Formal qualification remains **UNASSESSED**. The hashes bind registered binaries and sources but do not attest the actual host process path or OS isolation. Model identity is requested only; CLI thread IDs are not provider request IDs. Success here does not establish future provider capacity or availability.

The earlier v5 unknown-call fence remains preserved and was not resumed or replayed into this probe. No old result was regraded under a relaxed acceptance rule.

Frozen candidate source: `60c8b0f44d7290f15e92a45de346be1c7d0a0aea`; probe protocol freeze: `1f6840ead95b7453bd15371eb6efd001a65895d8`.

- Canonical private protocol SHA256: `213819b610b2dc44cba6ac6fccc628495cd25a033cf765aa6378616db64986b3`
- Task manifest SHA256: `47cc62df65af2872e0c0b112823212f192f2a497bf7a10a1665d76a073c1d8b5`
- Measured engine SHA256: `3004dd6fb64066f135fbd104e6d56d2d69f14f85e4871e55fa8b57e4cfc1bda6`

The [registered public protocol](../evolution/protocol/rc19-capability-recovery-v6.json) and [independent audit](../audits/rc19-capability-recovery-v6.audit.json) retain the aggregate measurements, gate results, per-call evidence hashes and owner-evidence digests. Absolute host paths, thread/harness IDs, raw event contents, and task/Skill bodies are omitted from the public audit.
