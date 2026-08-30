# SZL Outbound Kit — Design Partner Motion

**Goal:** 2 paid design partners in 90 days. Bar: 80% conversion of engaged partners.
**Wedge:** Governed agent change management — one workflow, signal → signed receipt.
**Buyer:** VP Eng/Platform + CISO (dual persona). EU Annex III exposure = urgency.

## Why the timing is now (from 2026-08 market data)

- **EU AI Act Annex III high-risk obligations: enforcement began 2 August 2026.** Deployers must keep automated logs ≥6 months and implement real human oversight. The deadline already passed — enterprises are buying *now*, not evaluating. ([Cloud Security Alliance](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-high-risk-compliance-deadline-20/))
- **Gartner: 40% of enterprise apps will embed task-specific agents by end of 2026, up from <5% in 2025.** New budget line opening.
- **6–10% of security budgets** now explicitly allocated to agent/AI security. ([VentureBeat](https://venturebeat.com/resources/agentic-security-enterprises-enforce-agent-permissions-two-thirds-of-the-time-and-isolate-high-risk-agents-less-than-one-in-five))
- **54% of enterprises have already had an AI-agent incident.** ([VentureBeat](https://venturebeat.com/ai/the-agent-security-gap-54-of-enterprises-have-already-had-an-ai-agent-incident-and-most-still-let-agents-share-credentials))
- **AI Governance Officer comp now $180K–$273K** — they're hiring the buyer you're selling to.

## Target archetypes (not invented names — real buyer profiles)

Prioritize companies that: (a) deploy agents into production workflows, (b) have EU exposure → Annex III, (c) already budget for AI security, (d) sell to regulated customers so *their* receipts become a sales asset.

| Archetype | Why they buy | Trigger to reference |
|---|---|---|
| Financial services deploying agentic underwriting/claims | Annex III credit/insurance = high-risk; FRIA required | "Dec 2027 is closer than it looks; logs + oversight must be operational, not policy" |
| HR-tech / recruiting platforms | Annex III(4) employment = high-risk | Candidate-screening AI must be logged + human-overseen |
| DevOps/platform eng teams running coding agents in prod | The wedge exactly — agent change management | "Codex auto-review decides; you need to *prove* what it did" |
| Critical-infrastructure / energy operators | Annex III critical infra; own-metal/air-gap fit | Sovereign tier — offline, air-gapped receipts |
| Mid-market SaaS selling into regulated EU | Need Art.12-shaped logs to close their own deals | "Your receipts become your sales asset" |

## The one-sentence opener

> IAM says what an identity may access. We prove what your AI agent was authorized to do, what it actually did, and whether the required evidence exists — signed, offline-verifiable, portable across your vendors.

## Proof points to lead with (all real, all public)

1. **We audit ourselves with the same product** — signed estate receipt, honestly INCOMPLETE: github.com/szl-holdings/szl-gov
2. **Offline verification works** — `python3 tools/verify_receipt.py <receipt> <pubkey>`, no network, no vendor call
3. **15/15 contract tests** — tamper, signature-confusion, service-account-spoof all rejected in CI
4. **Our own release pipeline refused an unverified publish** — overclaim guard gated our own pricing page before it went live
5. **Pricing is public** — a11oy.net/pricing

## Sequences

See `email-1-cold.md`, `email-2-followup.md`, `email-3-proof.md`, `linkedin-note.md`.

## Anti-patterns (do NOT send)

- Never ask "would you use a governed inference platform?" — invites polite fiction
- Never lead with "AI governance platform" — too broad, you'll be lumped with OneTrust
- Never claim "EU AI Act compliant" — say "Article 12 logging conformance profile" <!-- lexicon-ok -->
- Never say a competitor "has no logs" — say "not its stated purpose" <!-- lexicon-ok -->
