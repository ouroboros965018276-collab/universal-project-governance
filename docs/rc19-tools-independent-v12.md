# RC19 independent real-tool evaluation v12 — interrupted

The preregistered independent evaluation stopped with `unknown-call-blocked`; its net-benefit gate remains **FAIL**. Of 48 planned dispatches, 10 completed with strict quality PASS, the eleventh has unknown usage, and 37 were never dispatched. This is an incomplete independent result, not evidence of a verified net improvement.

The 10 completed turns reported **730,397 tokens**: 723,959 input and 6,438 output, including 595,072 cached input tokens. Their 10 thread IDs, harness requests and receipts are distinct. The unknown dispatch is also distinct; its unreported consumption is not counted as zero.

The independent evidence check passed 1,242 assertions and verified that 228 original files remained byte-for-byte unchanged. It reconstructed the frozen Git engine and both runtime identities, checked actual CLI arguments and prompt/result hashes, matched broker calls by tool and argument hash, and inspected actual final artifacts without invoking the grader or executing application code. The 53 broker events include 12 successful patches with 22 actual-byte file receipts; all 22 positive contract checks and the stored current-state validation/status evidence are consistent. Original quality labels were preserved.

Only **5 of 24 matched pairs** completed. Their figures below are diagnostics for that prefix:

| Metric | Treatment/control | Original 95% interval |
|---|---:|---:|
| Reported total tokens | 0.915881 | [0.810514, 0.995004] |
| Collector callback time | 0.956665 | [0.901840, 1.055930] |

A separate implementation reproduced these intervals exactly with seed 19012 and 4,000 repetitions. Complete cross-model family coverage is absent, so the required joint-family intervals remain `null`. Luna's callback point estimate is above one; completion, quality-for-all-dispatches and time gates also fail. None of these incomplete ratios overrides the registered FAIL.

The unknown requested Sol treatment turn exited with `Connection failed: error sending request`. Its stdout contains only thread/turn start, error and turn failure, with no completed usage, result or broker journal; initial workspace bytes are unchanged. The cause beyond that request-send error and its provider charge are unestablished. A separate read-only investigation confirmed `--ephemeral` and found no exact matching persisted local session file for this thread. No available artifact supplies completed usage. The original pending state and global unknown-call fence remain intact; there was no replay, resume or fence release.

The same frozen candidate, default official HTTP scaffold and zero ordinary request/stream retries were used. Source revision `96728ad0052afcb27129025e95c74187892df8dd`, freeze revision `5d25670eba0ace4d434c6775ec683b2a0dc296d0`, protocol digest `3aac153ae3cad9b4d4136ddbbd099d13a2ad570418c952eb41d73a28d807e6d6` and engine digest `5f835b662cd389ec0142b04c044e62366dc95b852974619d2ceef4846d48b3c0` bind this result. Pre-call review verified the full balanced order and 24 plans. Post-call artifact inspection used only called specifications; uncalled sealed bodies were not read and no task goal is published here.

RC19 cumulative recorded cost is **379 known completed turns / 14,232,738 reported tokens, plus five unknown dispatches: 384 actual CLI dispatches**. A4's pre-CLI reservation is excluded. This is same-provider, bounded repository-tool evidence; formal qualification remains UNASSESSED. There is no Stable, general production, invoice-cost or complete independent net-benefit claim.

[Public evidence audit](../audits/rc19-tools-independent-v12.audit.json) contains the original hashes and owner-retained verifier/statistics receipt digests. No model call, score replacement, candidate edit or original-record modification occurred during this audit.
