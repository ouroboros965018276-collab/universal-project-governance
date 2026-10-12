# RC19 independent real-tool confirmation v13 — interrupted

The single preregistered additional confirmation round stopped at unknown-call-blocked. Both the original net-benefit gate and additional confirmation gate remain **FAIL**. Of 48 planned dispatches, four completed with strict quality PASS, the fifth has unknown usage, and 43 were never dispatched. This does not establish an independent net benefit; there will be no further confirmation round.

The four completed turns reported **304,324 tokens**: 300,865 input and 3,459 output, including 238,848 cached input tokens. They have four distinct threads, harness requests and completed receipts. The unknown fifth dispatch is distinct and its consumption remains unknown, not zero.

Independent verification passed **675 assertions**, checking that 154 original files remained byte-for-byte unchanged. It reconstructed the frozen Git engine and both runtime identities, checked actual CLI arguments, prompt/result hashes and usage, matched CLI broker calls by tool and argument hash, and inspected actual artifacts without invoking the grader or executing application code. The completed turns contain 21 broker operations, six successful patches and 12 actual-byte file receipts. All 10 positive contract checks and required current-state validation/status evidence are consistent with the stored PASS labels, which were preserved.

The unknown requested Sol control turn emitted nine stdout events, including two completed MCP calls, followed by "Connection failed: error sending request" and turn.failed. Its journal records successful **repo_status and repo_read**, with no patch or validation; initial workspace bytes are unchanged. There is no turn.completed, completed usage or result. The journal, partial artifacts, pending state and unknown-call fence remain intact. The underlying transport cause and provider charge are unestablished; no replay, resume, session recovery interface or fence release occurred.

Only **two of 24 matched pairs**, both requested Luna, completed. These prefix figures are diagnostic:

| Metric | Treatment/control | Original 95% interval |
|---|---:|---:|
| Reported total tokens | 1.008222 | [1.007215, 1.008976] |
| Collector callback time | 1.011675 | [0.898250, 1.157008] |

A separate implementation reproduced the original intervals exactly using seed 19012 and 4,000 repetitions. Complete cross-model coverage is absent; joint-family intervals remain null. All original gates are false. The additional analysis correctly stopped with "partial/unknown collection cannot confirm": **no 99% interval or full 48-receipt check was performed**. Its 0.115962-second analysis time is separate from task timing.

The candidate remains the one fixed before B. Source revision 754bc07a41d89f6c19851c4aa7617f0201feff01, freeze revision d1b1d7f8b7b5461567c8bc90128860b8093369c6, protocol digest f026923ce3392a787df3ff96b6791f911d1a15cd6b370eeeff2a46028becbddf and engine digest bf34e2ecef8e04e6951d28077d3c31a09f1199176598d3e48827856b0bd0f0ae bind this result. Pre-call review covered all 24 plans and the full balanced order. Post-call inspection parsed only the five called specifications. Default official HTTP and zero ordinary retries were retained.

B's 10 completed turns / 730,397 reported tokens plus one unknown remain a separate failed independent result; B and C are not pooled. RC19 cumulative recorded cost is **383 known completed turns / 14,537,062 reported tokens, plus six unknown dispatches: 389 actual CLI dispatches**. A4's pre-CLI reservation is excluded. Same-provider, bounded repository-tool evidence does not establish Stable, general production reliability or complete independent net benefit. These results do not justify merging or local deployment under the evidence gate.

[Public evidence audit](../audits/rc19-tools-independent-v13.audit.json) records original hashes and owner-retained verification receipt digests. No model call, label replacement, candidate edit or original-record modification occurred during this audit.
