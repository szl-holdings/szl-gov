# szl-gov — estate truth layer
<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256; Orbit v2 icon. -->
<p>
  <a href="https://github.com/szl-holdings">
    <img src="https://raw.githubusercontent.com/szl-holdings/szl-brand/4309f6fce89179331b0b3ed8c99494e76c5be256/kit/logos/orbit-v2/suite/szl-icon-32.svg" alt="SZL Holdings — Orbit v2" width="32" height="32" />
  </a>
</p>

**Control before action. Evidence after.**

[Product](https://a-11-oy.com) · [Proof](https://a11oy.net) · [GitHub organization](https://github.com/szl-holdings)
<!-- /szl:header -->

Signed, offline-verifiable audit of the SZL estate, plus the gates that keep it honest.

szl-gov holds a dated, public-only snapshot of the `szl-holdings` GitHub organization and the
`SZLHOLDINGS` Hugging Face organization (captured 2026-08-30), the ledgers generated from it
(inventory, claims, commercial, contradictions, model BOM, dataset licenses, Space tiering), a
DSSE/Ed25519-signed `GovernedAction/v1` receipt for that audit with an offline verifier, and three
gates whose non-zero exit codes are the open checklist. Pure Python, one runtime dependency
(`cryptography`, pinned identically in `requirements.txt` and `pyproject.toml`).

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
```

CI runs Python 3.11 and 3.12; the suites also pass on 3.13.

## Run it

```bash
python3 tools/verify_receipt.py receipts/audit-receipt-2026-08-30.dsse.json keys/szl-audit-ed25519.pub.pem
python3 tools/verify_receipt.py receipts/audit-receipt-2026-08-30.dsse.json keys/szl-audit-ed25519.pub.pem --evidence-root .
python3 tools/lexicon_gate.py                  # honesty gate (exit 5 = banned phrasing)
python3 tools/spaces_gate.py                   # spaces tiering gate (exit 2/3)
python3 tools/release_gate.py                  # raise gate (exit 6 = blocked/unattested/invalid ledgers)
python3 tools/build_ledgers.py && python3 tools/tier_spaces.py   # rebuild the ledgers from the snapshot
```

Today these exit 0, 2, 0, 3, 6 and 0. Rebuilt ledgers are byte-identical to the committed ones
(`tests/test_ledgers_reproducible.py`).

Per-call (x402) prices live in one place, [`pricing/catalog.yaml`](pricing/README.md). Both of
these exit 0 today; the first fails on any disagreement with the exported gateway rules:

```bash
python3 tools/pricing_catalog.py check --rules pricing/snapshots/monetization-rules-2026-11-12.redacted.json
python3 tools/pricing_catalog.py generate --check   # manifest, /pricing table, README snippets
```

The verifier exits 0 when the signature is valid, 1 when it is not (or the payload is not a
`GovernedAction/v1` in-toto Statement), and, with `--evidence-root`, 2 when a recorded evidence
digest does not match its file. It exits 2 on this checkout: the receipt records sha256 digests for
`audit_data/gh_repos.json` and `audit_data/hf_org_listing.json` as originally captured, and [#16](https://github.com/szl-holdings/szl-gov/pull/16)
later rewrote both to public rows only. The signature is intact; the evidence binding needs a
receipt re-signed by the key holder over the current files.

```bash
python3 tools/szl_master_bootstrap.py --run    # key holder only: ledgers + signed receipt + all gates
```

The bootstrap signs with the private key in `../szl-gov-keys/` (outside the repo) whose public half
is `keys/szl-audit-ed25519.pub.pem`. Without that key, or with a different one, it refuses with
exit 7 and writes nothing. `--new-key` rotates the published identity on purpose, and only when no
key exists there yet.

Space readiness requires one recognized tier decision for every public Space
in the captured inventory, bound by its full `path`. Missing, duplicate,
unknown, or malformed tier rows block readiness (exit 2). Non-public rows are
withheld and counted; flagship attestation and Docker billing checks still apply.

The flagship tests use committed evidence only. The deployment test passes when the Hub-reported
`runtime.sha` equals the source revision; stage RUNNING is not evidence. The mobile smoke test is
UNKNOWN for every Space because no mobile-UA capture was committed. 0 of 5 flagships pass all 8.

## Test

```bash
pytest -q tests                  # 91 tests (CI: base-python-ci)
python3 tools/test_receipt.py    # 15 receipt contract tests (CI: Repository truth checks)
```

## What's here

| Path | What |
|---|---|
| `tools/receipt.py` | GovernedAction/v1 predicate, in-toto Statement, DSSE Ed25519 sign/verify |
| `tools/build_ledgers.py` | generates the four ledgers from the audit snapshot |
| `tools/tier_spaces.py` | applies the 8 flagship tests to every public Space (7 in the snapshot) -> `spaces_tiering.json` |
| `tools/build_bom.py` | Model BOM + Dataset License Register (diligence deliverables) |
| `tools/lexicon_gate.py`, `tools/spaces_gate.py`, `tools/release_gate.py` | the three gates (exit codes above) |
| `tools/szl_master_bootstrap.py` | key holder's one command: ledgers + signed receipt + gates |
| `tools/verify_receipt.py` | offline verifier — the artifact a CISO runs; `--evidence-root` also checks evidence digests |
| `tools/public_snapshot.py` | reduces a fresh API capture to public rows before commit; other rows are kept only as counts in `audit_data/withheld_private_counts.json` |
| `audit_data/` | the 2026-08-30 snapshot: public-only API captures, README captures and Hub probes for the 7 public Spaces |
| `ledgers/` | ESTATE_INVENTORY / CLAIMS / COMMERCIAL (25 metrics, all blocking the raise; 19 UNKNOWN) / CONTRADICTION_REGISTER / MODEL_BOM / DATASET_LICENSE_REGISTER / spaces_tiering.json |
| `patches/` | proposed `models:` front-matter READMEs for 3 backlink-gap Spaces, written against the 2026-08-30 READMEs. Stale: some Spaces they link no longer exist; regenerate before applying (needs a write-scoped HF token) |
| `receipts/` | DSSE-signed receipt for this audit, completeness INCOMPLETE (honest) |
| `pricing/catalog.yaml` | the canonical per-call (x402) price catalog: every price the Cloudflare Monetization Gateway charges, checked against an exported rules snapshot (`pricing/snapshots/`); see [pricing/README.md](pricing/README.md) |
| `tools/pricing_catalog.py` | `check` the catalog against a rules export, `generate` the x402 manifest, the a-11-oy.com/pricing per-call table and README snippets (`pricing/generated/`), `redact` an export before commit |
| `commercial/index.html` | the 2026-08-30 hypothesis pricing page; that list was withdrawn from a11oy.net on 2026-09-27 ([a11oy-net#231](https://github.com/szl-holdings/a11oy-net/pull/231)) and is kept here as history |
| `docs/ARTICLE_12_CONFORMANCE.yaml` | machine-readable Article 12 logging conformance profile (a profile, not a compliance claim) |
| `SZL_MASTER_PAYLOAD.md` | the Codex build directive |
| `docs/positioning/AUTO_REVIEW_DELTA.md` | Codex auto-review comparison, 12 rows |

## Ground truth (2026-08-30 snapshot)

98 GitHub repos (59 active public · 34 archived public · 5 private, counted only) · 45 HF Spaces (28 Docker, 7 public) · 43 models · 36 datasets — the counts in `ledgers/ESTATE_INVENTORY.yaml`.
A same-day GitHub API census quoted here earlier counted 100 repos (36 archived public); its capture is not committed, so the ledgers keep 98.
Marketed count was 26 Spaces — stale (B-01). Flagship capacity 5, attested 0. <!-- lexicon-ok -->

Listings in `audit_data/` and `ledgers/` name public repos, Spaces, models and datasets only. The totals above still include non-public rows, as aggregate counts.

The snapshot is dated and the estate has changed since. Refreshing it means re-collecting, running
`tools/public_snapshot.py`, rebuilding the ledgers and re-signing the receipt.

Gates fail on first run by design. The exit codes are the Week 1 checklist.

The release gate requires both truth ledgers in the flat YAML format emitted by
`build_ledgers.py`/`yamlite.py`; unsupported syntax, missing or duplicate fields,
missing metrics, and ledgers over 1 MiB are refusals. It checks the builder's full
commercial metric set, honors `blocks_raise`, and requires populated values and
evidence references. An explicit `contradictions: []` is allowed; an absent or
empty register is not. These are local ledger consistency checks, not independent
authentication of the referenced evidence or approval to release.

## What changed 2026-08-30 v2

- All 7 public Spaces probed RUNNING with HEAD SHA (`audit_data/probes/`)
- 45 Spaces tiered: 5 FLAGSHIP (recommended), 38 LAB, 1 SUPPORTING, 1 ORG_CARD (since [#16](https://github.com/szl-holdings/szl-gov/pull/16) the committed tiering lists only the 7 public Spaces — 5 FLAGSHIP, 1 SUPPORTING, 1 ORG_CARD — and counts the other 38)
- Model BOM: 43/43 license declared (all Apache-2.0), 13/43 base lineage, 12 third-party Qwen bases
- Dataset license register: 28/36 declared, 8 UNKNOWN (all private — owner must declare)
- Backlink coverage measured on the Hub at 10/43 models; 3 patches staged, 30 Spaces still need `models:` lines (not reproducible from the public-only snapshot, whose 7 public Space probes declare 12 of the 43 models)
- Signed receipt v2 includes BOM, license register, tiering as generated_artifact evidence

## What changed 2026-11-06

- `forbidden-domain` CI now really scans: its ripgrep call was missing on the runner, and `|| true` reported every run clean
- `spaces_tiering.json` no longer marks Spaces attested on stage RUNNING or on an unrecorded mobile check (was: 2 "Fully machine-attested")
- the bootstrap refuses instead of minting a new signing key; the verifier checks statement type and, on request, evidence digests
- the commercial ledger records the 2026-08-30 price list as withdrawn instead of live

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

**Key material.** `keys/szl-audit-ed25519.pub.pem` is a **public** verification key,
published so third parties can verify estate audit receipts offline. No private key
material is present in this repository, and none may ever be committed to it.

**Verification boundary.** A signed estate-audit receipt proves integrity and origin
of the audit record — that these values were observed and signed at that time. It does
not prove the estate is secure, compliant, or correct. `--evidence-root` shows whether the
files in a checkout still match the digests the receipt recorded; a match does not make
that evidence true. Λ = Conjecture 1 (advisory).
Absent evidence is reported as UNKNOWN, never converted into a pass.

Estate on Hugging Face: models, datasets and Spaces are published under the [SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) org.
