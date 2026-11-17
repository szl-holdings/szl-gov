# Public x402 v2 challenge readback — measured GET, not revenue

**Status:** One-shot, credential-free source tool. This contract does not alter
Cloudflare rules, DNS, API origin authentication, price, payee, payment policy,
or production traffic. GitHub szl-holdings/szl-gov is canonical source.

## Developer and investor context

The existing tools/x402_challenge_receipt.py deliberately operates offline,
interpreting a previously collected public PAYMENT-REQUIRED challenge. Its
companion tools/x402_public_probe.py makes one bounded unauthenticated GET
per owner-controlled URL and checks that header using the same fail-closed
comparator. No PAYMENT-SIGNATURE is generated, no wallet or facilitator is
contacted, and no Cloudflare API access is required.

The protocol is x402 v2: the gateway supplies PAYMENT-REQUIRED, a paying
client sends PAYMENT-SIGNATURE, and an origin separately validates the
signed PAYMENT-CONTEXT JWT. A compliant 402 is not an authorization or sale.

References:
- https://developers.cloudflare.com/monetization-gateway/x402/
- https://developers.cloudflare.com/monetization-gateway/configuration/payment-validation/
- https://github.com/x402-foundation/x402/blob/main/specs/transports-v2/http.md

## Reproduce from GitHub source

Python 3.11+ standard library only. Use a fresh private output filename.
The two sample endpoints are GET checks, not actual paid chat requests.

    python tools/x402_public_probe.py \
      --catalog pricing/generated/x402-pricing.json \
      --url https://a-11-oy.com/v1/chat/completions \
      --url https://inference.a-11-oy.com/v1/completions \
      --output /private/observed-20261117T193748Z.json

    python -m pytest -q tests/test_x402_public_probe.py
    python -m pytest -q tests/test_x402_challenge_receipt.py

The tool accepts 1-8 unique HTTPS URLs mapped to everyone-priced GET
routes in the canonical catalog. Unknown or qualified-bot-only paths,
query strings, redirects, duplicate URLs, source-catalog ages greater
than seven days, malformed challenges and price/recipient mismatches
are refused. HTTP 401, 403 or 429 stops subsequent provider GETs in
that run. Every endpoint is fetched at most once.

The exclusive output contains observed status, rule match, catalog
source SHA-256 and a digest of the public challenge header. It never
contains the raw header, signed payload, wallet key, bearer token, or
customer identity. No account settings or routes are changed.

Exit codes: 0 means all sampled GET challenges matched; 2 means a held
or unobserved sample; 3 means invalid input or output precondition.
None of these establishes training, model quality, paid origin serving,
settlement, or release readiness.

## 2026-11-17 sample evidence, not a revenue report

At 19:37:48 UTC two independent public GETs returned HTTP 402 with
PAYMENT-REQUIRED headers matching the November 13 catalog and fixed
20,000 USDC atomic-unit ($0.02) offers on Base. The historical private
readback digest is:

    889a61dfdbdbb450c7a4bf3e949e3fae38c0d4e220713f8d22c102509e037d6d

This is challenge-format observation only. The gateway export did not
establish that POST calls are billable, even though chat endpoints
typically use POST. There is no evidence here of a paid retry, client
signature, origin JWT validation, Coinbase settlement receipt, on-chain
finality, fees/refunds, or recognized revenue.

## Commercial admission gates

1. Obtain a fresh scoped Cloudflare rule readback, including methods,
   audiences, protected routes, payee and current price.
2. Verify the supported gateway/origin integration and the required
   PAYMENT-CONTEXT signature checks without weakening origin security.
3. Perform a separately authorized funded-wallet x402 v2 SDK canary.
4. Independently reconcile network, token asset, payee, amount,
   transaction hash, settlement, finality, fees/refunds and request ID.
5. Only then publish measured revenue and connect developer checkout
   documentation. Keep product sites, proof, health and well-known paths
   free as current owner policy requires.

Investor-safe statement: Source-controlled x402 pricing matched two
public live GET challenges on November 17, 2026. Neither actual
collections nor end-to-end paid origin service was established.
