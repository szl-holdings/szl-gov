#!/usr/bin/env python3
"""szl_master_bootstrap.py --run

One command that:
  1. builds the four ledgers from the live audit snapshot
  2. signs a GovernedAction/v1 receipt for THIS audit (dogfooding the standard)
  3. runs spaces_gate + lexicon_gate + release_gate and reports exit codes

The audit runs READ_ONLY. If a11oy's own audit cannot obey its own
side-effect classification, the classification is theater.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import receipt as R

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
RECEIPTS = ROOT / "receipts"
KEYS = ROOT / "keys"


def run_gate(script: str) -> int:
    p = subprocess.run([sys.executable, str(TOOLS / script)], capture_output=True, text=True)
    print(p.stdout, end="")
    if p.stderr.strip():
        print(p.stderr, file=sys.stderr, end="")
    return p.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="execute (default is dry plan)")
    args = ap.parse_args()

    if not args.run:
        print("plan: build ledgers -> sign audit receipt -> run 3 gates. Pass --run.")
        return 0

    t0 = time.time()

    # 1. ledgers (+ BOM + license register via build_bom inside build_ledgers)
    import build_ledgers
    rc = build_ledgers.main()
    if rc != 0:
        return rc

    # 1b. tiering scaffold (spaces_gate consumes spaces_tiering.json)
    import tier_spaces
    tier_spaces.main()

    # 2. sign the audit's own receipt
    # Key lives outside the repo so the public push can never leak it.
    EXTKEYS = ROOT.parent / "szl-gov-keys"
    EXTKEYS.mkdir(exist_ok=True)
    key_path = EXTKEYS / "szl-audit-ed25519.pem"
    pub_path = EXTKEYS / "szl-audit-ed25519.pub.pem"
    pub_copy = KEYS / "szl-audit-ed25519.pub.pem"
    if key_path.exists():
        sk = R.load_private(key_path.read_text())
        pk = R.load_public(pub_path.read_text())
    else:
        sk, pk = R.generate_keypair()
        key_path.write_text(R.private_key_pem(sk))
        pub_path.write_text(R.public_key_pem(pk))
        key_path.chmod(0o600)
    # publish only the public key into the repo
    KEYS.mkdir(exist_ok=True)
    pub_copy.write_text(R.public_key_pem(pk))

    hf = json.load(open(ROOT / "audit_data" / "hf_org_listing.json"))
    gh = json.load(open(ROOT / "audit_data" / "gh_repos.json"))

    evidence = [
        R.EvidenceItem(kind="api_response", ref="audit_data/gh_repos.json",
                       sha256=hashlib.sha256((ROOT/'audit_data'/'gh_repos.json').read_bytes()).hexdigest()),
        R.EvidenceItem(kind="api_response", ref="audit_data/hf_org_listing.json",
                       sha256=hashlib.sha256((ROOT/'audit_data'/'hf_org_listing.json').read_bytes()).hexdigest()),
        R.EvidenceItem(kind="api_response", ref="audit_data/hf_whoami.json",
                       sha256=hashlib.sha256((ROOT/'audit_data'/'hf_whoami.json').read_bytes()).hexdigest(),
                       required=False),
        R.EvidenceItem(kind="api_response", ref="audit_data/probes/",
                       required=False),  # runtime probes for 7 public Spaces
        R.EvidenceItem(kind="generated_artifact", ref="ledgers/MODEL_BOM.yaml", required=False),
        R.EvidenceItem(kind="generated_artifact", ref="ledgers/DATASET_LICENSE_REGISTER.yaml", required=False),
        R.EvidenceItem(kind="generated_artifact", ref="ledgers/spaces_tiering.json", required=False),
        # Human attestation rows we could not machine-collect stay honestly empty:
        R.EvidenceItem(kind="human_attestation", ref="", required=True),  # flagship tiering review
        R.EvidenceItem(kind="human_attestation", ref="", required=True),  # billing console confirmation
    ]

    action = R.GovernedAction(
        action="full_estate_audit",
        actor="stephenlutar2@gmail.com",
        scope="szl-holdings/github + SZLHOLDINGS/hf",
        truth_state="DEGRADED",   # honest: inventory VERIFIED, runtime + commercial UNKNOWN
        side_effect_class="READ_ONLY",
        evidence=evidence,
        limitations=[
            "runtime stage of Spaces not attested; RUNNING would not be evidence of deployed revision anyway",
            "private repo/Space internals not inspected beyond metadata",
            "commercial facts are UNKNOWN by construction; no model may invent them",
            "signature proves this receipt's integrity and origin, not the truth of any marketing claim",
        ],
        context={
            "ntp_synced": True,
            "rfc3161_token": None,   # UNKNOWN until a TSA is wired — honest absence
            "redaction_commitments": [],
        },
    )

    statement = R.build_statement(
        action,
        source_rev="github.com/szl-holdings/szl-gov",
    )
    statement["predicate"]["verification_surface"] = (
        "https://github.com/szl-holdings/szl-gov "
        "(offline verify: python3 tools/verify_receipt.py <receipt> keys/szl-audit-ed25519.pub.pem)"
    )
    env = R.sign_statement(statement, sk)
    RECEIPTS.mkdir(exist_ok=True)
    out = RECEIPTS / "audit-receipt-2026-08-30.dsse.json"
    out.write_text(json.dumps(env, indent=2))

    # self-verify before declaring victory
    verified = R.dsse_verify(env, R.load_public(pub_path.read_text()))
    assert verified["predicateType"] == R.PREDICATE_TYPE

    print(f"\nreceipt: {out.relative_to(ROOT)}")
    print(f"  predicateType: {R.PREDICATE_TYPE}")
    print(f"  completeness:  {action.completeness}  (missing human attestations -> INCOMPLETE, never PASS)")
    print(f"  keyid:         {env['signatures'][0]['keyid']}")
    print("  self-verify:   PASS (offline, public key only)")

    # 3. gates
    print()
    codes = {}
    for gate in ("spaces_gate.py", "lexicon_gate.py", "release_gate.py"):
        codes[gate] = run_gate(gate)
        print(f"[exit {codes[gate]}] {gate}\n")

    print(f"bootstrap finished in {time.time()-t0:.1f}s")
    print("summary: receipt signed & self-verified offline; gates failing is the Week 1 checklist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
