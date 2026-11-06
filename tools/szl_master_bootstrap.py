#!/usr/bin/env python3
"""szl_master_bootstrap.py --run

One command that:
  1. builds the four ledgers from the live audit snapshot
  2. signs a GovernedAction/v1 receipt for THIS audit (dogfooding the standard)
  3. runs spaces_gate + lexicon_gate + release_gate and reports exit codes

The audit runs READ_ONLY. If a11oy's own audit cannot obey its own
side-effect classification, the classification is theater.

Signing needs the key holder's private key in ../szl-gov-keys/ (outside the
repo). The key is resolved before anything is written:

  0  ledgers built, receipt signed and self-verified against keys/*.pub.pem
  7  refused: no signing key, or the key is not the published identity
     (keys/szl-audit-ed25519.pub.pem); nothing was written

Key rotation is explicit: --new-key mints a key pair only when no key exists
yet, then replaces the published public key. It never overwrites a key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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
# Key lives outside the repo so the public push can never leak it.
EXTKEYS = ROOT.parent / "szl-gov-keys"
PUBLISHED_PUB = KEYS / "szl-audit-ed25519.pub.pem"
KEY_REFUSED = 7


def signing_key(new_key: bool = False):
    """Return (sk, pk) for the published audit identity, or None to refuse.

    Without the private key this used to mint a fresh key pair, overwrite the
    published public key and re-sign the dated receipt, silently replacing the
    estate's verification identity. Now absence refuses; rotation is opt-in.
    """
    key_path = EXTKEYS / "szl-audit-ed25519.pem"
    if new_key:
        if key_path.exists():
            print(f"REFUSED: {key_path} already exists; --new-key never overwrites a key. "
                  "Move it aside first to rotate deliberately.", file=sys.stderr)
            return None
        sk, pk = R.generate_keypair()
        EXTKEYS.mkdir(exist_ok=True)
        # O_EXCL + 0600 at creation: never overwrites, never briefly world-readable.
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(R.private_key_pem(sk))
        (EXTKEYS / "szl-audit-ed25519.pub.pem").write_text(R.public_key_pem(pk))
        return sk, pk
    if not key_path.exists():
        print(f"REFUSED: no signing key at {key_path}; nothing was written. Third parties verify "
              "with tools/verify_receipt.py and run the gates directly. The key holder restores "
              "the key, or passes --new-key to rotate the published identity on purpose.",
              file=sys.stderr)
        return None
    sk = R.load_private(key_path.read_text())
    pk = sk.public_key()
    if PUBLISHED_PUB.exists() and R.key_id(pk) != R.key_id(R.load_public(PUBLISHED_PUB.read_text())):
        print(f"REFUSED: the key at {key_path} (keyid {R.key_id(pk)}) is not the published identity "
              f"in {PUBLISHED_PUB}; nothing was written.", file=sys.stderr)
        return None
    return sk, pk


def run_gate(script: str) -> int:
    p = subprocess.run([sys.executable, str(TOOLS / script)], capture_output=True, text=True)
    print(p.stdout, end="")
    if p.stderr.strip():
        print(p.stderr, file=sys.stderr, end="")
    return p.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="execute (default is dry plan)")
    ap.add_argument("--new-key", action="store_true",
                    help="rotate: mint a new signing key (only if none exists) and replace the published public key")
    args = ap.parse_args(argv)

    if not args.run:
        print("plan: resolve signing key -> build ledgers -> sign audit receipt -> run 3 gates. Pass --run.")
        return 0

    t0 = time.time()

    # 0. control before action: no key, no writes
    resolved = signing_key(args.new_key)
    if resolved is None:
        return KEY_REFUSED
    sk, pk = resolved

    # 1. ledgers (+ BOM + license register via build_bom inside build_ledgers)
    import build_ledgers
    rc = build_ledgers.main()
    if rc != 0:
        return rc

    # 1b. tiering scaffold (spaces_gate consumes spaces_tiering.json)
    import tier_spaces
    tier_spaces.main()

    # 2. sign the audit's own receipt; publish only the public key into the repo,
    # and only when it is new (first publication or deliberate rotation).
    if args.new_key or not PUBLISHED_PUB.exists():
        KEYS.mkdir(exist_ok=True)
        PUBLISHED_PUB.write_text(R.public_key_pem(pk))

    _ = json.load(open(ROOT / "audit_data" / "hf_org_listing.json"))
    _ = json.load(open(ROOT / "audit_data" / "gh_repos.json"))

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

    # self-verify against the published key file a third party would use
    verified = R.dsse_verify(env, R.load_public(PUBLISHED_PUB.read_text()))
    assert verified["predicateType"] == R.PREDICATE_TYPE

    print(f"\nreceipt: {out.relative_to(ROOT)}")
    print(f"  predicateType: {R.PREDICATE_TYPE}")
    print(f"  completeness:  {action.completeness}  (missing human attestations -> INCOMPLETE, never PASS)")
    print(f"  keyid:         {env['signatures'][0]['keyid']}")
    print(f"  self-verify:   PASS (offline, against {PUBLISHED_PUB.name})")

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
