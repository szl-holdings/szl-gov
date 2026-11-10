# Gateway rule snapshots

| File | What it is |
|---|---|
| `monetization-rules-2026-11-06.redacted.json` | Cloudflare Monetization Gateway rules API export for the zones a-11-oy.com (15 rules), a11oy.net (2 rules) and szlholdings.com (no rules: the API answered 404, code 10005 "payment rule not found"), taken by the estate coordinator on 2026-11-06 (file written 16:26 UTC). |
| `monetization-changes-2026-11-06.json` | The coordinator's change log: three rules disabled between 16:27:21 and 16:27:25 UTC, each PATCH answered 200, each with its rollback request. Byte-identical to the coordinator's record. |

## Redaction

Every rule skips requests whose User-Agent contains one of the estate's own probe
names. A user-agent match can be spoofed, so publishing the list would publish a
way to skip payment. `tools/pricing_catalog.py redact` replaced each list with
one placeholder carrying the list's size and SHA-256 digest
(`szl-redacted:estate-probe-user-agents:n=6:sha256=85403a2e…`). It refuses to
write a file if any user-agent condition is left unrecognised, or if the
redacted expression would parse to a different rule. No other byte of the export
was changed: ids, descriptions, prices, addresses, schemes and enabled flags are
as exported.

`check` accepts either form. Against the unredacted export it computes the same
digest itself, so the catalog can be checked against a fresh dashboard export
without redacting it first.
