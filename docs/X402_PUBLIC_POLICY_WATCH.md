# SZL x402 public route policy witness — read-only

**Owner:** `szl-holdings/szl-gov`. **Source truth:** `pricing/catalog.yaml` and
the generated `pricing/generated/x402-pricing.json` snapshot; current
Cloudflare provider rules require **separate authenticated readback**. The
observation tool is `tools/x402_public_policy_watch.py`.

## Measured scope

A bounded daily GitHub Actions run performs **exactly four literal public GETs**:
the public product root, the public proof root, inference completions, and chat.
It never follows redirects, sends a wallet signature, submits a POST, logs
authorization data, reads a response body, or retries blindly. The output
includes only sanitized HTTP status, fixed verdict codes, source revision,
catalog SHA-256, and observed timestamp. The raw `PAYMENT-REQUIRED` header
is processed only in memory.

For public roots, only HTTP 200 with **no payment challenge** is accepted. For
paid routes, only HTTP 402 with an x402 v2 challenge matching the catalog's
specified network, asset, recipient, atomic price, scheme, target resource
and timeout is accepted. Only `audience: everyone` routes qualify; provider
classification of verified bots requires authenticated provider evidence.
The source catalog must be no more than seven days older than the observed
challenge. Missing, moved, malformed, paywalled, stale, or ambiguous responses
fail closed.

A matching header does **not** show a payer, valid signature, actual
authorization, response to a paid retry, USDC settlement, refund, fees,
or net revenue. The output **always** contains:

```json
{
  "authorization": "UNVERIFIED",
  "settlement": "UNVERIFIED",
  "revenue": "NO_CLAIM",
  "provider_rule_readback": "NOT_PERFORMED",
  "wallet_used": false
}
```

The GitHub Action uses `contents: read`, pins its actions by exact SHA,
runs from protected main, and stores a bounded, sanitized readback artifact.
A report status of `POLICY_CHALLENGES_OBSERVED` is **not** production
admission. It is a dated public-route observation, not the current authenticated
Cloudflare configuration. An absent source receipt, current manifest,
independent wallet-funded settlement and on-chain readback stay separate holds.

## Run

From a reviewed repository checkout:

```bash
python tools/x402_public_policy_watch.py \
  --catalog pricing/generated/x402-pricing.json \
  --output /secure/path/x402-public-policy-witness.json

python -m pytest tests/test_x402_challenge_receipt.py \
  tests/test_x402_public_policy_watch.py -q
```

Never commit raw network challenge headers, customer queries, provider
tokens, wallet material, or raw payment responses. The public monitor uses
no such values. No recurring payment can be triggered by this workflow.

## Limits and repair sequence

If the monitor finds a 402 on a free route, do **not** amend the catalog to
make it appear correct. Review exact Cloudflare rule expressions and
target-zone readback, establish owner approval, make a bounded change, and
independently verify served behavior. If a paid-route challenge differs,
compare immutable price source against a fresh authenticated provider export.
If the snapshot is stale, regenerate it through its existing owner process
instead of relaxing the seven-day gate.

After public-scope parity, validate a **separate** controlled x402 v2
signed client retry, exact settlement receipt, chain readback, refunds/fees,
and net reconciliation. A 402 response cannot ever count as `$ revenue`.
