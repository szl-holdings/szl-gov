#!/usr/bin/env python3
"""build_ledgers.py — generate Truth/Claims/Commercial/Contradiction ledgers from the audit snapshot.

Every row carries evidence_ref. Rows without evidence are UNKNOWN, not blank.
Public claims lacking evidence auto-demote (Zero-Bandaid Law, enforced in receipt.py).
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yamlite
from audit_data_builder import build, FLAGSHIP_CAPACITY

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGERS = ROOT / "ledgers"
AUDIT = ROOT / "audit_data"


def main() -> int:
    gh = json.load(open(AUDIT / "gh_repos.json"))
    hf = json.load(open(AUDIT / "hf_org_listing.json"))
    estate = build(gh, hf)
    c = estate["counts"]

    # ---------------- ESTATE INVENTORY (what exists, attested) ----------------
    inventory = {
        "estate": estate["meta"],
        "counts": c,
        "prior_marketed_counts": estate["prior_claims"],
        "tiering_rule": {
            "max_flagship": FLAGSHIP_CAPACITY,
            "definition": "FLAGSHIP = public, current source revision, attested deploy revision, receipt link, conversion event",
            "enforcement": "spaces_gate.py exits non-zero if flagship set exceeds capacity or loses attestation",
        },
        "github_repos": estate["github_repos"],
        "hf_spaces": estate["hf_spaces"],
        "hf_models": estate["hf_models"],
        "hf_datasets": estate["hf_datasets"],
    }

    # ---------------- CLAIMS LEDGER (only what evidence supports) ----------------
    claims = [
        {
            "claim_id": "C-001",
            "claim": "Killinchu public counter-UAS demo is live as a Docker Space",
            "truth_state": "VERIFIED",
            "evidence": ["https://huggingface.co/spaces/SZLHOLDINGS/killinchu"],
            "notes": "Public Docker Space observed 2026-08-30, likes=2. Runtime stage NOT attested.",
        },
        {
            "claim_id": "C-002",
            "claim": "a11oy public governance Space is live",
            "truth_state": "VERIFIED",
            "evidence": ["https://huggingface.co/spaces/SZLHOLDINGS/a11oy"],
            "notes": "Public Docker Space observed. Carries slsa-l1, doctrine-v11, dsse tags.",
        },
        {
            "claim_id": "C-003",
            "claim": "killinchu-osint-corpus is the estate's distribution leader",
            "truth_state": "VERIFIED",
            "evidence": ["https://huggingface.co/datasets/SZLHOLDINGS/killinchu-osint-corpus"],
            "notes": "41,122 downloads, 8 likes. Next nearest dataset is szl-lake at 4,363.",
        },
        {
            "claim_id": "C-004",
            "claim": "SZL-Khipu-1.5B is a publicly downloaded model",
            "truth_state": "VERIFIED",
            "evidence": ["https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B"],
            "notes": "1,102 downloads. GGUF variant 611. ReceiptAgent variant 954.",
        },
        {
            "claim_id": "C-005",
            "claim": "The estate operates 26 Hugging Face Spaces",
            "truth_state": "BLOCKED",
            "evidence": [],
            "notes": "Measured 45 on 2026-08-30. The '26' figure is stale marketing; retire it.",
        },
        {
            "claim_id": "C-006",
            "claim": "The flagship set is currently attested",
            "truth_state": "UNKNOWN",
            "evidence": [],
            "notes": "Flagship admission tests (8 criteria) have not been run per-Space. Capacity is 5; attested count is 0.",
        },
        {
            "claim_id": "C-007",
            "claim": "Receipts are DSSE-signed and offline-verifiable",
            "truth_state": "VERIFIED",
            "evidence": ["tools/receipt.py", "tools/verify_receipt.py", "receipts/audit-receipt-2026-08-30.dsse.json"],
            "notes": "Ed25519 DSSE sign + offline verify demonstrated 2026-08-30; tamper test rejects single byte-flip. Not yet linked from a public Space.",
        },
        {
            "claim_id": "C-008",
            "claim": "a11oy proves what an agent was authorized to do (vs IAM access)",
            "truth_state": "UNKNOWN",
            "evidence": [],
            "notes": "Positioning line, not a shipped integration. No customer audit has consumed a receipt.",
        },
        {
            "claim_id": "C-009",
            "claim": "Model Bill of Materials exists for all models",
            "truth_state": "VERIFIED",
            "evidence": ["ledgers/MODEL_BOM.yaml"],
            "notes": "43/43 license declared (all Apache-2.0); 13/43 base-model lineage declared; 12 third-party Qwen bases flagged.",
        },
        {
            "claim_id": "C-010",
            "claim": "Dataset license register exists",
            "truth_state": "DEGRADED",
            "evidence": ["ledgers/DATASET_LICENSE_REGISTER.yaml"],
            "notes": "28/36 declared. 8 UNKNOWN, all private repos — cards not machine-readable anonymously; owner must declare.",
        },
        {
            "claim_id": "C-011",
            "claim": "Public Spaces are runtime-observed RUNNING",
            "truth_state": "VERIFIED",
            "evidence": ["audit_data/probes/"],
            "notes": "7/7 public Spaces RUNNING with HEAD SHA captured 2026-08-30. Stage is not deployed-revision evidence (B-06).",
        },
    ]

    # ---------------- COMMERCIAL LEDGER (24 rows, all UNKNOWN, all gate the raise) ----------------
    commercial_rows = [
        ("ARR", "Annual recurring revenue, contracted"),
        ("MRR", "Monthly recurring revenue"),
        ("paying_customers", "Count of customers with a signed paid agreement"),
        ("design_partners_signed", "Paid design partners, not free pilots"),
        ("gross_margin_pct", "Revenue minus cost-to-serve, as %"),
        ("net_revenue_retention_pct", "NRR incl. expansion, target >=110"),
        ("cac_payback_months", "Months to recover acquisition cost"),
        ("burn_multiple", "Net burn / net new ARR, target <1.5x"),
        ("runway_months", "Cash / net burn"),
        ("cash_on_hand", "Current liquid balance"),
        ("monthly_burn", "Average net monthly burn"),
        ("published_price", "A price a stranger can read without a call"),
        ("pricing_model", "Per-action? Per-seat? Platform fee? Undecided = UNKNOWN"),
        ("buyer_persona", "Named single buyer with budget line"),
        ("first_wedge", "One workflow with a budget owner"),
        ("co_founder_name", "Second name with ownership, not advisory"),
        ("cap_table_clean", "Delaware C-Corp, no side letters, no dead equity"),
        ("ip_assignments_complete", "Every contributor signed assignment to the company"),
        ("model_bom", "Bill of materials for all 43 models incl. base weights"),
        ("dataset_license_register", "License + provenance for all 36 datasets"),
        ("training_data_rights", "Legal basis for each training corpus"),
        ("soc2_status", "Type I readiness date, or UNKNOWN"),
        ("eu_design_partner", "Named EU partner with Annex III exposure"),
        ("demo_video_90s", "Public 90-second deny/sign/tamper/verify recording"),
        ("outbound_kit", "Design-partner sequences + target archetypes drafted"),
    ]
    # Honest evidence for rows this week's work actually created. The rest stay UNKNOWN.
    EVIDENCE = {
        "published_price": ("Control $75-250K/yr; Assurance/Sovereign $250K+/yr; Verify open — LIVE at a11oy.net/pricing",
                            "https://a11oy.net/pricing/"),
        "pricing_model": ("Annual platform fee by tier (Control/Assurance/Sovereign); design-partner 6-month paid. Never token-priced. Public.",
                          "https://a11oy.net/pricing/"),
        "first_wedge": ("Governed agent change management: signal->investigate->policy->approve->patch->deploy->signed receipt",
                        "SZL_MASTER_PAYLOAD.md#3"),
        "buyer_persona": ("VP Eng/Platform + CISO (dual), regulated AI product teams with EU Annex III exposure",
                          "SZL_MASTER_PAYLOAD.md#3"),
        "demo_video_90s": ("Scripted as 7-step on-page proof; not yet recorded as video",
                           "commercial/index.html#demo"),
        "outbound_kit": ("3-email sequence + LinkedIn note + target archetypes drafted",
                         "outreach/"),
    }
    commercial = {
        "ledger": "COMMERCIAL_LEDGER",
        "rule": "Any UNKNOWN row sets blocks_raise=true. The release gate fails until every row is attested with evidence.",
        "rows": [
            {"metric": k,
             "definition": v,
             "value": EVIDENCE.get(k, (None, None))[0],
             "evidence_ref": EVIDENCE.get(k, (None, None))[1],
             # Hypothesis artifacts address the row but are NOT contracted revenue.
             # They stop blocking once validated by a customer signal; until then keep blocking.
             "blocks_raise": True,
             "evidence_class": "hypothesis_artifact" if k in EVIDENCE else "none"}
            for k, v in commercial_rows
        ],
    }

    # ---------------- CONTRADICTION REGISTER ----------------
    contradictions = [
        {"id": "B-01", "severity": "BLOCKER",
         "statement": "Marketed Space count (26) diverges from measured estate (45)",
         "resolution": "Adopt measured count; tier the estate; cap flagships at 5"},
        {"id": "B-02", "severity": "BLOCKER",
         "statement": "Docker Spaces on free cpu-basic require PRO (July 2026); public Docker flagships must be billing-verified",
         "resolution": "Org is on TEAM plan; confirm billing binding and keep 4 public Docker Spaces green"},
        {"id": "B-03", "severity": "MEDIUM",
         "statement": "HF backlink parser needs literal model IDs in Space files; 10/43 models backlinked",
         "resolution": "Patches staged in patches/ for immune, governed-receipt-verifier, README. Apply with a write-scoped HF token or manually in the Hub UI. 30 of 45 Spaces still need models: lines."},
        {"id": "B-04", "severity": "HIGH",
         "statement": "GM/NRR/CAC/burn multiple uncomputable (pricing hypothesis exists, no contracted revenue)",
         "resolution": "Pricing page + 3 SKUs shipped 2026-08-30 (commercial/index.html). Hypothesis only; validate with first design-partner contract to clear."},
        {"id": "B-05", "severity": "BLOCKER",
         "statement": "Solo founder. Series A graduation 12.9% vs 23.7% (2 founders) / 29.3% (3)",
         "resolution": "Recruit one named co-owner; write them into the deck"},
        {"id": "B-06", "severity": "HIGH",
         "statement": "RUNNING stage is treated as evidence of deployed revision",
         "resolution": "stage is never evidence; require attested deployed revision per flagship"},
        {"id": "B-07", "severity": "HIGH",
         "statement": "50GB Space disk is not persistent; evidence spooled there is not durable",
         "resolution": "Move evidence spool to persistent storage or signed remote sink"},
        {"id": "B-08", "severity": "MEDIUM",
         "statement": "Org card is itself a Space and can drift unnoticed",
         "resolution": "Inventory README as tier ORG_CARD with the same gates"},
        {"id": "B-09", "severity": "BLOCKER",
         "statement": "The receipt-cannot-lie claim has never been adversarially attacked",
         "resolution": "Run Daybreak Blue S2.6: enumerate every path to PASS on tampered bundle"},
        {"id": "B-10", "severity": "BLOCKER",
         "statement": "Replit-era credentials ($20k+ build history) never rotated",
         "resolution": "Rotate all credentials; hardware keys on Daybreak accounts before Sept 1, 2026"},
        {"id": "B-11", "severity": "HIGH",
         "statement": "Redaction before signing could remove exculpatory evidence undetected",
         "resolution": "Salted hash redaction_commitments in receipt context"},
        {"id": "B-12", "severity": "HIGH",
         "statement": "Receipt backdating is possible without trusted timestamp",
         "resolution": "rfc3161_token + ntp_synced:true required in receipt context"},
    ]

    LEDGERS.mkdir(exist_ok=True)
    (LEDGERS / "ESTATE_INVENTORY.yaml").write_text(yamlite.dump(inventory))

    # BOM + license register (diligence deliverables, C-009/C-010 evidence)
    import build_bom
    build_bom.main()
    (LEDGERS / "CLAIMS_LEDGER.yaml").write_text(yamlite.dump({"ledger": "CLAIMS_LEDGER", "claims": claims}))
    (LEDGERS / "COMMERCIAL_LEDGER.yaml").write_text(yamlite.dump(commercial))
    (LEDGERS / "CONTRADICTION_REGISTER.yaml").write_text(yamlite.dump({"contradictions": contradictions}))

    print(f"ledgers written: {c['github_repos']} repos, {c['hf_spaces']} spaces "
          f"({c['hf_spaces_docker']} docker, {c['hf_spaces_public']} public), "
          f"{c['hf_models']} models, {c['hf_datasets']} datasets")
    print(f"flagship capacity {FLAGSHIP_CAPACITY}; advertised flagships {c['advertised_flagships']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
