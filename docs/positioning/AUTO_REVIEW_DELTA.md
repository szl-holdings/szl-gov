# Codex auto-review vs a11oy — committed comparison

Source: OpenAI Codex auto-review ships as an `[auto_review]` config block
(`enabled`, `reviewer_model`, `block_on_severity`) routing eligible approvals
through a reviewer agent at the sandbox boundary. Defaults: no network,
workspace-write only.

**Discipline (Zero-Bandaid Law applies to our own copy):** we say what is
*not its stated purpose* — never "it has no logs." Auto-review is real and shipped. <!-- lexicon-ok -->

| # | Capability | Codex auto-review | a11oy |
|---|---|---|---|
| 1 | Pre-execution approval of elevated actions | stated purpose | stated purpose |
| 2 | Side-effect classification | yes (sandbox escalation, network, permission, tool calls) | 4 classes, never collapsed |
| 3 | Signed receipt per action | not its stated purpose | DSSE/in-toto, Ed25519 |
| 4 | Offline verification by third party | not its stated purpose | public key only, no vendor call |
| 5 | Evidence-obligation model | not its stated purpose | missing evidence ⇒ INCOMPLETE |
| 6 | Retention tier | not its stated purpose | Article 12 profile, 6-mo floor |
| 7 | Article 12 field set | not its stated purpose | `is_service_account` pinned false |
| 8 | Portability across vendors | no (OpenAI surface) | vendor-neutral predicate |
| 9 | Survives vendor outage | no | signed artifact + offline verify |
| 10 | Auditor-consumable record | not its stated purpose | the product |
| 11 | Tamper evidence | not its stated purpose | byte-flip ⇒ signature_invalid |
| 12 | Redaction with integrity | not its stated purpose | salted hash commitments |

**Deck line:** "Codex auto-review decides. a11oy proves. The decision does not
survive the vendor, the outage, or the auditor."

**Validation to cite:** the largest AI lab independently concluded agents taking
elevated-permission actions need pre-execution review rather than post-hoc logs.
Stop arguing the premise; cite theirs. Sell the gap.
