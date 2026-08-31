# Hardware Track — A11oy Beacon / PHYS-1

**Status:** Rev 0.9 RFQ issued to Minewing (JDM), Attn: Jenny, 2026-08-31. Pre-NDA.
**Scope:** ONE (1) engineering prototype. No production tooling authorized.

## Why this matters strategically

Every competitor in the funded set (Zenity $125M, Obsidian $85M @ $1.1B, WitnessAI $58M,
JetStream $34M, Hush $30M) sells **software** inspection of agent behavior. None of them
can enforce it below the operating system.

**RC1 Receipt Control Coprocessor** is the moat in silicon:

> "The application processor must not have unconditional direct electrical control over
> privileged outputs."

That is the a11oy thesis — control before action, evidence after — implemented as an
electrical boundary rather than a policy. A software control plane can be bypassed by
whoever owns root. A coprocessor that refuses malformed, expired, replayed, or
unauthorized envelopes cannot be argued with.

This is the strongest differentiation the estate has produced, because it is the one
claim a better-capitalized software competitor cannot copy in a sprint.

## The Reality Transaction (product core)

INTENT → EVIDENCE → PROPOSAL → SIMULATION/ASSESSMENT → POLICY → CONSENT → ACTION → WITNESS → RECEIPT

Maps 1:1 onto `GovernedAction/v1`. The hardware emits the same predicate the software
verifier already checks — meaning `tools/verify_receipt.py` is the acceptance test for
RC1 firmware, not a separate deliverable.

## Discipline already correct in the spec

The RFQ is Zero-Bandaid compliant as written, and that should be preserved through revisions:

- §24 explicitly **refuses** a "first" claim pending claim-charted novelty search by counsel
- Feasibility verdict is stated as feasible-with-conditions, not asserted
- Rev A **excludes** life-safety, medical treatment, and autonomous actuation
- AI output must carry visible labels (VERIFIED SOURCE / COMMUNITY REPORT / MACHINE INFERENCE)
- No biometrics, no hidden surveillance mode, data minimization by default
- Machine-readable test records required, "not PDF-only where avoidable"

## OPEN RISK — HW-001 (raised by this review, BLOCKER)

**Pre-NDA disclosure of a novel hardware boundary may create a patentability problem.**

The document is marked "CONFIDENTIAL - PRE-NDA TECHNICAL RFQ" and §25 correctly sequences
"execute mutual NDA" as step 1 — but the RFQ describing the RC1 boundary in enabling detail
has already been prepared for transmission to a third-party manufacturer in a foreign
jurisdiction.

In most first-to-file regimes, disclosure to a third party without a confidentiality
agreement in force can start clocks or create prior art against your own filing. The
marking on the document is not itself an agreement.

**Required order of operations:**
1. Mutual NDA **executed** (signed by both parties) before the RFQ is transmitted.
2. Provisional patent application on the RC1 privileged-output boundary filed **before**
   or concurrently with disclosure — counsel decides.
3. Only then send the enabling detail in §7 and §22.

This connects to IP-001 (Bricklayer patent adjacency) already in the contradiction
register. Same counsel engagement can cover both.

## Prior art the spec already identified

- US20190110172A1 — mesh networks for disaster relief
- US10872153B2 — trusted cyber physical system
- EMBRAVE — TPM-based remote attestation for dynamic IoT
- Nature Electronics 2026 — in-sensor cryptographic signature generation
- IgniRelay — offline signed emergency events, BLE relay, supply matching

The novelty argument must therefore be narrow and specific: not "signed events," not
"offline mesh," but **hardware-enforced separation of AI reasoning from privileged
actuation, with an independently readable witness path**.

## Standards baseline referenced

NISTIR 8259A · NIST SP 800-193 · FCC Part 15 · IEC/UL 62368-1 · IEC 60529 (IP65) ·
IEC 62133-2 · UN 38.3 · LoRaWAN 1.1 · ETSI EN 303 645 · EU CRA · ICRC data protection

## Files

- `BEACON_PHYS1_RFQ_extract.md` — full text + 16 tables extracted from the Rev 0.9 docx
