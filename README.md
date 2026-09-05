# szl-gov — estate truth layer
<!-- szl:header v1 -->
<!-- badges: add this repo's CI / release / status badges here -->
[![org: szl-holdings](https://img.shields.io/badge/org-szl--holdings-black)](https://github.com/szl-holdings)
[![doctrine](https://img.shields.io/badge/doctrine-control%20before%20action%20%C2%B7%20evidence%20after-blue)](https://a-11-oy.com)

**Control before action. Evidence after.**

Part of the [szl-holdings](https://github.com/szl-holdings) estate ·
Product: [a-11-oy.com](https://a-11-oy.com) ·
Proof: [a11oy.net](https://a11oy.net)
<!-- /szl:header -->

Signed, offline-verifiable audit of the SZL estate, plus the gates that keep it honest.

## Live estate census

The authoritative GitHub inventory is now `tools/audit_github_estate.py`. It enumerates every repository visible to the organization audit credential, walks every exact default-branch tree, records every blob/submodule identity, and fails closed on unreadable or truncated evidence. Control mode audits high-signal files; archive mode byte-verifies exact commit archives and never labels active-only or budget-limited coverage as a full-estate pass.

```bash
ESTATE_GITHUB_TOKEN=... python3 tools/audit_github_estate.py \
  --org szl-holdings \
  --content-mode control \
  --fail-on critical
```

See [`docs/LIVE_ESTATE_FILE_AUDIT.md`](docs/LIVE_ESTATE_FILE_AUDIT.md) for the evidence model, coverage semantics, archive verification, and CI contract.

## Run the signed snapshot toolchain

```bash
python3 tools/szl_master_bootstrap.py --run   # ledgers + signed receipt + all gates
python3 tools/lexicon_gate.py                  # honesty gate (exit 5 = banned phrasing)
python3 tools/spaces_gate.py                   # spaces tiering gate (exit 2/3)
python3 tools/release_gate.py                  # raise gate (exit 6 = UNKNOWN commercial rows)
python3 tools/verify_receipt.py receipts/audit-receipt-2026-08-30.dsse.json keys/szl-audit-ed25519.pub.pem
```

## What's here

| Path | What |
|---|---|
| `tools/audit_github_estate.py` | live token-visible repository/file census, bounded content checks, archive byte verification, and cross-repository duplicate evidence |
| `.github/workflows/live-estate-file-audit.yml` | daily exact control census and weekly full-estate archive attempt with immutable artifacts |
| `tools/receipt.py` | GovernedAction/v1 predicate, in-toto Statement, DSSE Ed25519 sign/verify |
| `tools/build_ledgers.py` | generates the four ledgers from the retained audit snapshot |
| `tools/tier_spaces.py` | applies the 8 flagship tests to all Spaces -> `spaces_tiering.json` |
| `tools/build_bom.py` | Model BOM + Dataset License Register (diligence deliverables) |
| `tools/szl_master_bootstrap.py` | one command: ledgers + self-signed receipt + gates |
| `tools/verify_receipt.py` | offline verifier — the artifact a CISO runs |
| `ledgers/` | retained snapshot ledgers and registers |
| `patches/` | ready-to-apply model-card patches retained from the 2026-08-30 snapshot |
| `receipts/` | DSSE-signed historical audit receipts |
| `SZL_MASTER_PAYLOAD.md` | the Codex build directive |
| `docs/positioning/AUTO_REVIEW_DELTA.md` | Codex auto-review comparison, 12 rows |

## Historical snapshot — 2026-08-30

The retained 2026-08-30 snapshot recorded 100 GitHub repositories (59 active public, 36 archived public, 5 private), 45 Hugging Face Spaces, 43 models, and 36 datasets. Those values are historical evidence, not a current inventory claim. The live controller above supersedes static counts for current-state decisions.

The snapshot gates fail on first run by design. Their exit codes remain the historical Week 1 checklist.

## What changed in the 2026-08-30 v2 snapshot

- All 7 public Spaces probed RUNNING with HEAD SHA (`audit_data/probes/`)
- 45 Spaces tiered: 5 FLAGSHIP (recommended), 38 LAB, 1 SUPPORTING, 1 ORG_CARD
- Model BOM: 43/43 license declared (all Apache-2.0), 13/43 base lineage, 12 third-party Qwen bases
- Dataset license register: 28/36 declared, 8 UNKNOWN (all private — owner must declare)
- Backlink coverage measured at 10/43 models; 3 patches staged, 30 Spaces still need `models:` lines
- Signed receipt v2 includes BOM, license register, tiering as generated-artifact evidence

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

**Key material.** `keys/szl-audit-ed25519.pub.pem` is a **public** verification key,
published so third parties can verify estate audit receipts offline. No private key
material is present in this repository, and none may ever be committed to it.

**Verification boundary.** A signed estate-audit receipt proves integrity and origin
of the audit record — that these values were observed and signed at that time. It does
not prove the estate is secure, compliant, or correct. Λ = Conjecture 1 (advisory).
Absent evidence is reported as UNKNOWN, never converted into a pass.
