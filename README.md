# szl-gov — estate truth layer

Signed, offline-verifiable audit of the SZL estate, plus the gates that keep it honest.

## Run it

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
| `tools/receipt.py` | GovernedAction/v1 predicate, in-toto Statement, DSSE Ed25519 sign/verify |
| `tools/build_ledgers.py` | generates the four ledgers from the audit snapshot |
| `tools/tier_spaces.py` | applies the 8 flagship tests to all Spaces -> `spaces_tiering.json` |
| `tools/build_bom.py` | Model BOM + Dataset License Register (diligence deliverables) |
| `tools/szl_master_bootstrap.py` | one command: ledgers + self-signed receipt + gates |
| `tools/verify_receipt.py` | offline verifier — the artifact a CISO runs |
| `ledgers/` | ESTATE_INVENTORY / CLAIMS / COMMERCIAL (24 UNKNOWN rows) / CONTRADICTION_REGISTER / MODEL_BOM / DATASET_LICENSE_REGISTER / spaces_tiering.json |
| `patches/` | Ready-to-apply `models:` front-matter READMEs for the 3 backlink-gap Spaces (needs write-scoped HF token) |
| `receipts/` | DSSE-signed receipt for this audit, completeness INCOMPLETE (honest) |
| `SZL_MASTER_PAYLOAD.md` | the Codex build directive |
| `docs/positioning/AUTO_REVIEW_DELTA.md` | Codex auto-review comparison, 12 rows |

## Ground truth (2026-08-30)

98 GitHub repos · 45 HF Spaces (28 Docker, 7 public) · 43 models · 36 datasets.
Marketed count was 26 Spaces — stale (B-01). Flagship capacity 5, attested 0. <!-- lexicon-ok -->

Gates fail on first run by design. The exit codes are the Week 1 checklist.

## What changed 2026-08-30 v2

- All 7 public Spaces probed RUNNING with HEAD SHA (`audit_data/probes/`)
- 45 Spaces tiered: 5 FLAGSHIP (recommended), 38 LAB, 1 SUPPORTING, 1 ORG_CARD
- Model BOM: 43/43 license declared (all Apache-2.0), 13/43 base lineage, 12 third-party Qwen bases
- Dataset license register: 28/36 declared, 8 UNKNOWN (all private — owner must declare)
- Backlink coverage measured at 10/43 models; 3 patches staged, 30 Spaces still need `models:` lines
- Signed receipt v2 includes BOM, license register, tiering as generated_artifact evidence

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

**Key material.** `keys/szl-audit-ed25519.pub.pem` is a **public** verification key,
published so third parties can verify estate audit receipts offline. No private key
material is present in this repository, and none may ever be committed to it.

**Verification boundary.** A signed estate-audit receipt proves integrity and origin
of the audit record — that these values were observed and signed at that time. It does
not prove the estate is secure, compliant, or correct. Λ = Conjecture 1 (advisory).
Absent evidence is reported as UNKNOWN, never converted into a pass.
