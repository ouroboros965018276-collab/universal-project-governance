# RC19 native independent A4 — failure before CLI launch

The first worker failed during dispatch-input validation, before the native runner or official CLI was entered. Independent reconciliation found **zero actual CLI dispatches, zero completed turns and zero task observations**. The A callback-time/quality gate remains **FAIL**; Tool B's joint gate is unchanged and formal qualification remains **UNASSESSED**.

All four retained worker stdout logs contain exactly one matching `ready` registration and no result/error event. The first worker's stderr records `UnicodeEncodeError` at frozen worker line 156 while digesting the registered source; the callback timer begins at line 161 and `native.runner` is called at line 165. The other three stderr logs are empty. All four registered native artifact roots are absent, and all four recorded worker processes were absent when audited. The pending request was independently reconstructed and matches the retained request digest.

The original parent run remains `unknown-call-blocked`: one reserved worker attempt, zero stored reported tokens, unknown usage, no observation and the original pending record. A reserved worker attempt is not an actual CLI dispatch. Independent evidence locates this failure before model invocation; zero stored tokens is not a provider invoice or billing attestation. No pending record, ledger, raw log or fence was cleared, and the failed run was not replayed.

The frozen parent wrote UTF-8 JSON while the frozen worker consumed host-decoded text stdin. An encoding mismatch is consistent with the observed unpaired surrogate U+DC9D. The exact child text encoding was not recorded, so the audit does not assign a particular Windows code page. A corrected wire implementation requires a new source revision and new protocol registration; this A4 record remains failed.

Frozen treatment source: `0bd647a79a7270c674238916217385c4e749a399`; public freeze: `1f8e6d5ab8fc8d4f9bea300c86d898083602ae8d`; private protocol canonical SHA256: `4fe1b0942d0f1b20691b44428055c99615502ec1006585ff9c403f1a960d1fb2`. The audit read the registered Git sources rather than requiring later corrected worktree files to match this historical freeze. It made no model call and executed no application code.

Owner evidence: [independent audit receipt](../audits/rc19-native-independent-a-v4.audit.json). The receipt provides retained log, run and verifier hashes without host paths, process/thread IDs or task/Skill bodies. It supports a local pre-CLI failure diagnosis, not an efficiency or task-quality claim.
