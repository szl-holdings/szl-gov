# x402 v2 unsigned POST method witness

This is a **bounded source-owned Cloudflare challenge check**, implemented in
[Python](../tools/x402_post_method_watch.py), with
[offline regression tests](../tests/test_x402_post_method_watch.py).
It does not authorize payment, verify a client signature, fulfill a model
request, settle USDC, or establish revenue.

## Production observation (November 17, 2026)

At 19:42:33 UTC, an owner-operated, unsigned, intentionally invalid-body
request to each of the following fixed production URLs received HTTP 402 with
one well-formed x402 V2 `PAYMENT-REQUIRED` offer. Both offers matched the
atomic amount, payee, token, network and resource in the contemporaneous
source-owned pricing snapshot:

| Path | HTTP | Observed scope |
| --- | --- | --- |
| `POST https://a-11-oy.com/v1/chat/completions` | 402 | Public POST payment challenge |
| `POST https://inference.a-11-oy.com/v1/completions` | 402 | Public POST payment challenge |

The unsigned observation was performed with the checked-in script using an
invalid body (no model or prompt), no wallet and no settlement attempt. The
sanitized receipt was retained in a private local reports directory.
It is **not** public, signed or independently confirmed.
The gateway's rules may change after the observation; reobserve before making
pricing, deploy, investor or settlement claims.

The catalog records GET-priced source rules; this witness independently tests
POST **on the wire** and uses the GET-priced rule only as the reference for the
same route's payment terms. It does not assert that the provider rule export
was reread, or that origin services accept paid requests.

## Developer procedure

From a clean checkout of `szl-holdings/szl-gov`:

```bash
python -m pytest -q tests/test_x402_post_method_watch.py
python tools/x402_post_method_watch.py --output /tmp/disabled.json
# The second command refuses with exit 2 and makes zero requests.

python tools/x402_post_method_watch.py --execute \
  --catalog pricing/generated/x402-pricing.json \
  --output /secure/local/post-method-witness.json
```

The explicit `--execute` makes **exactly two bounded HTTPS POSTs** to literal
allowlisted resources. The body `{"szl_post_method_probe_invalid":true}` is
intentionally not a valid inference request. Request headers contain no
authorization, cookies, `PAYMENT-SIGNATURE`, `X-PAYMENT` or
`PAYMENT-CONTEXT`; redirects are never followed. Response bodies are never
consumed or retained; raw challenge headers are used only in memory.
Only coarse response verdicts and SHA-256 of the catalog leave the process.

Positive status `POST_CHALLENGES_OBSERVED` (exit 0) requires two 402 responses,
valid base64 JSON, x402 V2, one unambiguous `exact` offer, correct resource,
CAIP-2 network, USDC asset, payee, amount and bounded timeout, plus a catalog
observation no more than seven days old. Any disagreement produces
`FAIL_CLOSED` (exit 2). A Python exception never constitutes a pass.

## Commercial and release admission

This is **not** a funded wallet canary, a facilitator verification, an origin
delivery check, an on-chain settlement, a receipt-chain verification or revenue
analytics. Full admission requires a separately authorized buyer, signed
authorization, successful origin response, independent settlement confirmation,
reconciliation to the payee and an exact payment/request receipt. Zero
verified settlements must remain zero/unknown, never converted from 402 counts.

Cloudflare reference: https://developers.cloudflare.com/monetization-gateway/
x402 protocol: https://developers.cloudflare.com/agents/tools/payments/x402/
Source of truth: [pricing catalog](../pricing/README.md)
