# RC1 Acceptance Binding — HW-002

**Purpose:** make `tools/verify_receipt.py` the acceptance test for RC1 execution receipts,
so the Beacon hardware and the a11oy software emit **one** predicate rather than two.

Add this as an acceptance clause in §7 (RC1 Functional Requirements) and as a line item
in §17 (EVT Acceptance Test Matrix) of the Beacon RFQ.

## Why this matters commercially

Without this binding, you ship two artifacts and must argue they agree. With it, the
sentence to a buyer becomes:

> The same public verifier your auditor runs against our software also validates the
> receipt our silicon emits. One format, one verifier, no vendor in the loop.

That is not a feature. It is the reason a hardware-enforced boundary is worth paying for:
the proof does not change shape when it crosses from silicon to software.

## Normative requirement (proposed RFQ language)

> **RC1-ACC-1.** Every RC1 execution receipt SHALL be serializable to a
> `https://szl.dev/GovernedAction/v1` predicate wrapped in an in-toto Statement v1
> envelope, DSSE-signed with an Ed25519 key whose private half is generated inside the
> RC1 secure element and never exported.
>
> **RC1-ACC-2.** Acceptance is demonstrated by the SZL reference verifier
> (`tools/verify_receipt.py`) returning `VERIFY: PASS (offline)` on a receipt captured
> from physical hardware, executed on a host with **no network route to SZL or Minewing
> infrastructure**.
>
> **RC1-ACC-3.** The verifier SHALL return failure — not a warning — for each negative
> case in the table below. A build that passes the positive case but fails to fail a
> negative case does NOT pass acceptance.

## Field mapping: RC1 receipt → GovernedAction/v1

| RC1 receipt field (RFQ §7) | GovernedAction/v1 | Notes |
|---|---|---|
| exact command digest | `inputs_digest` | SHA-256 over the authenticated envelope |
| decision | `truth_state` | admitted → `VERIFIED`; refused → `BLOCKED` |
| hardware identity | `actor` + `subject.name` | RC1 device serial, provisioned in secure element |
| time basis | `timestamp` + `context.ntp_synced` | RC1 has no assured RTC while offline — see below |
| firmware measurement/version | `context.firmware_measurement` | SP 800-193 measured boot value |
| output channel | `scope` | which privileged output was energized |
| result | `side_effect_class` | `EXTERNAL_EFFECT` or `IRREVERSIBLE` |
| witness input reading | `evidence[kind=witness_path]` | independently readable, post-action |
| anti-replay counter | `context.monotonic_counter` | from protected NVM |
| policy digest | `policy_ref` | hash of the policy in force at decision time |

## Negative cases the verifier must reject

| # | Physical condition induced on the bench | Required verifier result |
|---|---|---|
| N1 | Flip one byte of the signed receipt | `signature_invalid` |
| N2 | Replay a previously valid envelope | RC1 refuses to energize; receipt `truth_state: BLOCKED` |
| N3 | Present an expired envelope (outside time window) | `BLOCKED`, output never energized |
| N4 | Omit the witness-path reading | `completeness: INCOMPLETE`, never PASS |
| N5 | Sign with a key not provisioned in the secure element | `signature_invalid` |
| N6 | Assert a service-account principal | envelope rejected — `is_service_account` is pinned false |
| N7 | Brownout / watchdog reset mid-action | safe state held; receipt records the abort, not a success |
| N8 | Application processor attempts direct output control, bypassing RC1 | output does NOT energize; **this is the core claim** |

N8 is the acceptance test that decides whether the product is what it says it is. It should
be witnessed and recorded on video during EVT.

## Honest constraint — offline time basis

RC1 cannot establish trusted time while offline. Do **not** claim tamper-proof timestamps
on a disconnected node. The lawful position:

- Record the local monotonic counter and the last known synced time.
- Set `context.ntp_synced: false` when time was not verifiable.
- Attach an RFC 3161 timestamp token **on reconciliation**, when the node regains a link.
- Until then the receipt is `PENDING_SYNC` — a visible state, not a silent assumption.

This mirrors the Flight Recorder rule already in the software: local durability is
acknowledged, remote durability is not asserted.

## Deliverable to request from Minewing

Add to §21: *"A signed sample RC1 execution receipt from physical hardware, plus the
eight negative-case captures, in machine-readable form — verifiable by the customer's
reference verifier with no network access."*

That single deliverable converts the entire RFQ from a description of intent into a
testable contract.
