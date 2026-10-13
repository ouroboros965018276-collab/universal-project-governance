# RC19 v10 completed tool development collection

The independent evidence audit passed. All 32 fresh CLI turns completed, with **2,571,232 reported tokens, zero unknown-usage calls and zero replay**. The unchanged net-benefit gate is **FAIL**: token usage decreased within this round, while callback time did not improve and one control task failed the strict quality contract.

The experiment contains 16 matched pairs: eight known development tasks from six known families, requested on `gpt-6-sol` and `gpt-6-luna` at low effort. Treatment passed 16/16; control passed 15/16. Luna's control on `dev-recovery-29` retains `contract-failed:STATE.json:ValueError` and `required-current-real-tool-evidence-missing`. The latter requires successful validation/status evidence for the final state; merely calling a failed validation is insufficient. The failed task and its costs remain in every aggregate.

| Quantity | Control | Treatment | Treatment/control | Original 95% interval | Joint-family 95% interval |
| --- | ---: | ---: | ---: | --- | --- |
| Reported tokens | 1,321,555 | 1,249,677 | 0.945611 | [0.893102, 0.998322] | [0.886292, 0.998763] |
| Callback seconds | 304.836563 | 306.735582 | 1.006230 | [0.953278, 1.079772] | [0.963515, 1.072918] |
| CLI seconds | 291.324824 | 292.921408 | 1.005480 | [0.947416, 1.082029] | Not registered |
| Broker operations | 91 | 87 | 0.956044 | [0.900990, 1.041667] | Not registered |

Tokens decreased 5.4389%; callback time increased 0.6230%. Sol's token/time ratios are 0.929021/1.005285, and Luna's are 0.961823/1.007254. Both token point estimates improve; both time point estimates regress. The original and joint-family token upper bounds fall below 1, but neither time interval does. The all-task-quality and time gates therefore remain false. Frozen summary recomputation and a separate implementation of both bootstrap methods reproduce the registered seed 19012, 4,000-repetition intervals exactly. These are development diagnostics after repeated tuning, rather than independent final efficacy evidence.

The audit matched 32 unique CLI threads, harness requests and raw receipts; completed usage; exact command/prompt/task/capability/source bindings; and all protected final bytes. The 178 broker operations comprise 59 reads, 47 patches, 33 validations and 39 fixed Git status calls. All 77 successful patch file receipts match actual bytes. Static inspection of declared positive predicates matches 71/72 final contracts, consistent with the retained control failure. The audit invoked no task grader and changed no score. A total of 3,610 evidence assertions passed, with 551 original files hash-identical before and after verification.

Measured source is Git `2179d02549323ed905ab920b06374ff3088a11c9`, frozen publicly at `ff30c8a8f93b6bc12214bd5c73a875efb44b28c1`. The private protocol digest is `890320f029cf289baf6a5d445a4730c54aefb8cc7770e4fd80ae4ab81cac613a`; engine digest is `85310f62c7e1b1ad23e0421def8b3ee214709d30d5444711a532afd8bb842190`. All 62 frozen engine files match Git. Treatment Skill size is 8,180 UTF-8 bytes versus the exact RC18 baseline's 7,940. Both arms use the same default HTTP profile and bounded broker, without the diagnostic proxy overrides. The unused v9 remains at zero calls.

The campaign budget was 32 calls, 5,000,000 reported tokens and 7,200 seconds; measured elapsed time was 614.844000 seconds. Shared source/Skill/plan preparation took 6.902805 seconds separately. Callback timing includes adapter preparation, CLI, static grading and evidence persistence; shared source preparation and adapter constructor setup are outside that estimand. Preparation costs were not added retrospectively to change the registered outcome.

Across retained RC19 rounds, the independently reconciled total is **353 completed turns, 12,028,747 known reported tokens and four unknown-usage dispatches: 357 actual CLI dispatches**. This includes the failed startup diagnostic's completed usage. A4's pre-CLI worker reservation contributes zero actual CLI calls. Earlier unknown fences, raw failures and labels remain preserved.

Reported usage includes cached input; invoices, failed-partial billing, internal attempts, provider request IDs and internal model identity are unobserved. Two requested OpenAI models remain one provider family. The scope is bounded real repository tools and static AST/data/text contracts, with no arbitrary application execution or OS isolation claim. No sealed B task was read or called during this audit. No acceleration, general production maturity, algorithm causal contribution, net benefit or Stable qualification is established.

The sanitized evidence is [rc19-tools-development-v10.audit.json](../audits/rc19-tools-development-v10.audit.json). The owner retains the ignored independent verifier and full audit receipt; receipt SHA-256 is `eb1a70415d9623d46fe85d0050d59ff85993a0d20f6e6069f91d11451acde4ef`. Separate statistics receipt SHA-256 is `155ffdff55f590c64b5aad8fa2ad5c0f433cea4d62348d8ffa3dfa59a551156f`. This audit made zero model/CLI inference calls and preserved all original evidence.
