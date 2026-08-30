# SZL MASTER PAYLOAD — Codex Build Directive
**Target:** standard GPT-5.6 Codex (NOT Daybreak Blue — Blue is defensive-security scope only)
**Date:** 2026-08-30 · **Source:** 10-round convergence, 3-model audit (Claude Opus 5 / Nemotron 3 Ultra / Kimi K3)
**Prime directive:** Turn the SZL estate from a technically ambitious proof system into a repeatable commercial company. Ship nothing that cannot survive its own receipt.

---

## 1 · The One-Sentence Company

> **IAM says what an identity may access. a11oy proves what an AI agent was authorized to do, what it actually did, and whether the required evidence exists.**

Codex auto-review decides. a11oy proves. The decision does not survive the vendor, the outage, or the auditor.

---

## 2 · Canonical Lexicon (gate-enforced, `lexicon_gate.py`)

| Never say | Say instead | Why |
|---|---|---|
| EU AI Act compliant | Article 12 logging conformance profile | Applicability is customer-specific; overclaim dies in diligence | <!-- lexicon-ok -->
| 26 Spaces | the measured estate (45 as of 2026-08-30) | Stale marketing count; contradiction B-01 | <!-- lexicon-ok -->
| five flagships | flagship capacity 5, attested 0 | Capacity ≠ attainment | <!-- lexicon-ok -->
| production-ready | truth state + named environment + receipt | "Production-ready" is unfalsifiable | <!-- lexicon-ok -->
| enterprise/military-grade | the control + its evidence | Unverifiable adjective | <!-- lexicon-ok -->
| 100% secure / guaranteed | the invariant + enforcement mechanism | Fails any red team | <!-- lexicon-ok -->
| competitor "has no logs" | "not its stated purpose" + citation | Zero-Bandaid Law applies to your own copy | <!-- lexicon-ok -->

---

## 3 · The Locked Wedge

**Governed agent change management** — one workflow, sold Monday:
prod signal → agent investigates → policy eval → human approval → bounded patch → tests → deploy → observation window → signed closure/rollback receipt.

Reversible actions. Technical buyer (VP Eng/Platform + CISO, dual). Measurable value. Abundant evidence inputs. Powerful demo. Natural expansion into security, compliance, model governance.

**Explicit exclusions for v1 (do not build):** MCP servers, agent framework, UI, multi-tenant SaaS, billing, AQL, Sigstore keyless. Scope discipline is the deliverable.

---

## 4 · Moat Inversion (the strategy in one move)

The monitor/control/police lane is capitalized ~10x above you: Zenity $125M Series C, Obsidian $85M Series D @ $1.1B, Hush $30M, WitnessAI $58M, JetStream $34M — most of it landed August 2026. Do not compete on who logs agents.

**Give away the receipt format. Sell the control plane.** Publish `GovernedAction/v1` as an open spec with reference verifiers in Go/Python/TS. Let competitors emit your format. Sell the trust plane, retention architecture, and conformance tooling on top.

Investor frame: *"We are not competing with agent-security platforms. We are becoming the format they all have to emit."*

---

## 5 · Truth States (structural, enforced in code)

`VERIFIED / DEGRADED / UNKNOWN / BLOCKED / UNAVAILABLE`

Laws enforced in `tools/receipt.py` constructors, not prose:
1. Missing required evidence ⇒ `INCOMPLETE`, never PASS.
2. Signature proves integrity + origin, **not** truth of claims.
3. `is_service_account=True` raises — Art.12(3)(d) requires natural persons; structurally unviolatable.
4. Public `VERIFIED` claim with incomplete evidence auto-demotes to `UNKNOWN` (`public_claim_check`).
5. `None` renders as literal `UNKNOWN` in ledgers — absence is an audited state, not a blank.
6. `stage=RUNNING` is never evidence of deployed revision.
7. Local durability ACK only after `flock`+`fsync`; PENDING_SYNC is a visible state.
8. Four side-effect classes never collapse: `READ_ONLY / WRITE_LOCAL / EXTERNAL_EFFECT / IRREVERSIBLE`. IRREVERSIBLE always requires human approval.

---

## 6 · The Demo Is The Product (12-step acceptance test)

Signal → deny unauthorized → sign approved action → tamper one byte → offline verify FAILS → remove evidence → verdict INCOMPLETE → outage → PENDING_SYNC visible → replay (non-mutating) → Article 12 conformance report → 90-second public recording on the homepage.

Exit criterion for design phase: 80%+ partner conversion **and** three use cases that work with zero custom configuration. Seven flagship surfaces are surfaces, not use cases.

---

## 7 · Build Program (what Codex implements)

**Phase 0 — Truth foundation (done, this repo):** ledgers, gates, signed self-audit receipt. `python3 tools/szl_master_bootstrap.py --run`.

**Phase 1 — Core receipt stack:**
- Adopt `in-toto-attestation` from PyPI (CNCF bindings, v0.9.3, ~38K dl/mo). Delete any hand-rolled DSSE after migration; using maintained bindings is the stronger diligence answer.
- `TypedPolicyEngine`: default-DENY, first-match-wins on decision, evidence obligations accumulate across ALL matched rules, most-restrictive side-effect wins.
- `SegmentedFlightRecorder`: magic header, length-prefixed framing, `verify_integrity()` returning gaps + corruptions + sequence range; idempotency-key scan proving no duplicate execution on recovery.
- `OfflineVerifier`: what `tools/verify_receipt.py` already does — signature + completeness + limitations surfacing.
- Receipt `context` must carry `redaction_commitments` (salted hashes, closes the redaction-vs-exculpatory hole) and `rfc3161_token` + `ntp_synced` (closes backdating).
- ~40 contract tests incl. `test_service_account_cannot_claim_human` (verifier rejects `type=human` + `auth_method=api_key`).

**Phase 2 — Proof surface:** governed-receipt-verifier Space wired to verify real signed artifacts; 90s demo video; Article 12 machine-readable YAML profile (6-month retention floor).

**Phase 3 — Revenue surface:** price page (hypotheses allowed: design partner $50–150K, department $75–250K, enterprise $250–750K+; never token-based — the value is control, not tokens), SOC 2 Type I readiness start ($15–40K, 12–16 wks), Model BOM + dataset license register for all 43 models / 36 datasets.

**Capital allocation next 6 months:** 40% customer deployments / 25% core product / 15% security readiness / 10% GTM / 5% standards / 5% model R&D. (Historical split is roughly inverted.)

---

## 8 · CI Gates (exit codes are the Week 1 checklist)

| Gate | Fails when | Exit |
|---|---|---|
| `spaces_gate.py` | untiered Spaces; flagship overflow >5; flagship unattested; public-Docker billing unverified | 2/3 |
| `lexicon_gate.py` | banned phrasing in any .md/.yaml | 5 |
| `release_gate.py` | any of 24 commercial metrics UNKNOWN; any BLOCKER contradiction open | 6 |

First run failing is correct. Current state: spaces 2, lexicon 0, release 6.

---

## 9 · Competitive Map (as of 2026-08-30)

| Player | Capital | Lane | Your answer |
|---|---|---|---|
| Zenity | $125M C (Aug 4) | monitor/control/police agents | don't enter |
| Obsidian | $85M D @ $1.1B (Aug 4) | SaaS + agent attack surface | don't enter |
| WitnessAI | $58M strategic | agent inventory + runtime control | don't enter |
| JetStream | $34M seed (pre-product, 5 names) | MCP sprawl, enforcement | the "second door": team+thesis rounds exist |
| Hush | $30M A | machine identity for agents | adjacent; your IAM boundary line |
| OpenAI Codex auto-review | shipped | pre-execution approval | "decides, doesn't prove" — cite it, sell the gap |

Quarterly moat test: *if Databricks/OpenAI/Microsoft/Salesforce/Palantir copied every visible feature in six months, what remains?* Answer must be: portable cross-provider evidence graph + customer trust data + conformance tooling. Nothing else.

---

## 10 · Series A Reality

- Bar: ~$3.5M ARR (Carta Q1 2026), median post $75–85M, raise $13–15M, story to $500M–1B.
- Solo founders graduate at 12.9% vs 23.7%/29.3% (2/3 founders). Conditional on raising, valuations are indistinguishable ($54.9M vs $53.6M) — the penalty is entirely at the gate. **Fix the denominator, not the numerator.**
- AI/agent security ≈ 25% of all cyber seed deals Q2 2026 — the window is open and closing simultaneously.
- North Star: **verified governed actions per customer per month**, complete evidence coverage, zero unauthorized execution.
- Design partner exit: 80% paid conversion + three zero-config use cases.

---

## 11 · What No Payload Can Do (human-only work)

1. Supply the 24 commercial facts (ARR, co-founder name, cap table, price). Evidence, not generation.
2. Rotate Replit-era credentials; enroll hardware keys before **Sept 1, 2026** Daybreak enforcement.
3. IP-001: counsel review of Bricklayer patent adjacency before runtime-interception code.
4. Paste the 14 ChatGPT share transcripts into `docs/context/chatgpt-shares/` to promote them from UNAVAILABLE.
5. Confirm HF org billing covers the 4 public Docker Spaces (`a11oy`, `killinchu`, `szl-khipu`, `immune`).

---

## 12 · The Lightning Strike (dated, verifiable, press-able)

Publish `GovernedAction/v1` + reference verifier + Article 12 conformance YAML **and** the signed self-audit receipt of your own estate — including the parts that failed. No funded competitor can copy that without first fixing their own house. Sprawl honestly tiered and signed is a moat; sprawl marketed as five flagships is the blocker. <!-- lexicon-ok -->

**Do not become the company that built an extraordinary proof system for a market it has not yet chosen.**
