# x402 v2 challenge witness (offline, fail-closed)

This is a **wire-format and catalog consistency check**, not a buyer, payment facilitator, origin authorizer, settlement verifier, or revenue dashboard. It makes **zero HTTP requests** and never handles a wallet or payment signature. The canonical source for this tool is `tools/x402_challenge_receipt.py` in `szl-gov`; the canonical price snapshot is `pricing/generated/x402-pricing.json`, derived from `pricing/catalog.yaml` and only as current as its Cloudflare readback.

## Input

Provide a JSON array of bounded **operator-redacted** captures. Each record has exactly:

```json
{
  "schema": "szl.x402-public-challenge-capture/v1",
  "url": "https://inference.a-11-oy.com/v1/completions",
  "method": "GET",
  "status": 402,
  "payment_required": "<base64-encoded public PAYMENT-REQUIRED header>",
  "observed_at": "2026-11-17T04:30:00Z"
}
```

Never include `PAYMENT-SIGNATURE`, `PAYMENT-CONTEXT`, session cookies, customer identifiers, wallet private keys, or origin secrets. Do not put query-string secrets in `url`; the report avoids echoing them, but raw captures are still sensitive and should not be committed. The witness hashes the full raw capture file and the source price snapshot, without returning raw headers.

## Execute locally

```bash
python3 tools/x402_challenge_receipt.py \
  --captures /secure/path/redacted-challenges.json \
  --catalog pricing/generated/x402-pricing.json \
  --output /secure/path/challenge-readback.json

python3 -m pytest tests/test_x402_challenge_receipt.py -q
```

The output is deterministic: `CHALLENGES_MATCH` (exit 0) only means **one or more observed 402 headers conform to the dated price catalog**, including x402 version, HTTPS resource, exact one-offer scheme, CAIP-2 network, USDC contract, wallet, and atomic amount. Unknown, conflicting, expired-catalog, off-zone, malformed, and privileged-audience cases return `FAIL_CLOSED` (exit 2). The comparator checks only catalog routes with `audience: everyone` and method `GET`; `verified_bots` cannot be inferred from a client-supplied flag. The source catalog is considered stale when the capture is more than seven days after the catalog's `as_of` time. No evidence is manufactured when a route does not match.

## Explicit nonclaims

- **A 402 is not a payment.** It establishes neither a signed authorization nor a successful settlement.
- A `PAYMENT-RESPONSE` string, screenshot, wallet view, gateway challenge, or synthetic fixture does not independently verify USDC transfer or customer revenue.
- This script does **not** decode, request, construct, log, or verify client payment signatures.
- The tool prints `settlement_state: UNVERIFIED` and `revenue_state: NO_CLAIM` unconditionally, even on successful challenge matching.
- A consistent historical price snapshot does not prove current Cloudflare rules or production runtime are identical to the snapshot.
- This is a local software validation receipt, not an independently attested network observation.

## Full settlement admission (separate workstream)

A legitimate funded x402 v2 client must retry using an official SDK and its own wallet; Cloudflare must verify and settle. A separate independently authenticated gateway/on-chain receipt, including network, USDC contract, receiver, transaction hash, status, amount, fees, refunds, timestamp and request correlation, is needed before producing any revenue or successful-settlement metric. The current Worker at `a11oy/ops/revenue-tracker-worker` records **requests**, not settlements. Never substitute its `x402_revenue` request counter for revenue.

Primary references: [Cloudflare x402 protocol](https://developers.cloudflare.com/monetization-gateway/x402/), [x402 v2 protocol](https://github.com/x402-foundation/x402/blob/main/specs/x402-specification-v2.md), [SZL pricing contract](../pricing/README.md).
