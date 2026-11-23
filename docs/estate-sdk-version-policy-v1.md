# Estate SDK version policy, staging-first ladder (gradio)

**Status: PROPOSED DRAFT (PROPOSE_ONLY; authorizes nothing until owner/council ratification).**

Landed as an additive DRAFT document under the W26L landing-triage blocker queue conversion (row G1, landing_priority 11).

## Provenance and landing truth
- Queue record: mesh/2026-11-23/w26l-landing-triage/w26l-blocker-queue.json
- Draft source (PROPOSE_ONLY): mesh/2026-11-23/w26i-g-series-drafts/w26i-g-series-drafts.json
- Blocker clearance: SIGNATURE_MINT cleared 2026-11-23: owner signature mint landed (W26C LEG A complete + W28X corrected-head verified commits; key id 1356467, fp SHA256:/w0Rx9...; going-forward SSH signing live on the owner device)
- Fresh Kimi GO at landing: nonce W26M-G1-145143 (receipt published in wave-logs mesh/2026-11-23/w26m-queue-conversion/)
- Landed 2026-11-23T14:51:46Z. Landed by delegated estate automation under the owner standing green-light directive; NOT independent human review.
- Target adjudication: szl-gov = estate truth layer / standards home; target listed as estate SDK version policy; queue blocker COUNCIL_RATIFICATION executed at landing via the 4 council seats.

## Source citation
W26I G1 draft; observed gradio pins: 6.20.0 szl-science-gate-studio, 6.26.0 szl-constellation production pin (owner landing to move), 6.31.x szl-marketing-1-1 peers, 6.32.x newer staging spaces

## Proposed change
ratify policy then enforce via PRs: pin major.minor.patch, staging-first ladder, never auto-upgrade production

## Proposed estate policy (gradio SDK versioning)
- pin major.minor.patch in every space card
- upgrade ladder: staging first, then quarantine, then production
- never auto-upgrade production spaces
- sdk_version changes beyond patch level are owner-gated
- every upgrade needs a draft PR with changelog digest and smoke receipts
- the szl-constellation production pin (6.26.0) moves only on owner-approved landing; version-split disclosure stays visible until then

## Ratification status
- queue blocker COUNCIL_RATIFICATION: council verdicts recorded at landing time in w26m-council-g1.json (receipts published in wave-logs w26m-queue-conversion)
- enforcement is separate future work per the landing spec; this document is the standard text only

## Acceptance gate
draft authorizes nothing until ratification recorded; enforcement is separate PRs

## Rollback
standard-withdrawal doc only

## Baseline
all space baselines unchanged; production pin 6.26.0 stays; this proposal does not modify it.
