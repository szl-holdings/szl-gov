#!/usr/bin/env python3
"""verify_receipt.py — offline verifier for SZL audit receipts.

Usage:
    python3 verify_receipt.py receipts/audit-receipt-2026-08-30.dsse.json keys/szl-audit-ed25519.pub.pem
    python3 verify_receipt.py RECEIPT PUBKEY --evidence-root .

  0   signature valid; with --evidence-root, every recorded evidence digest
      also matches its file under that directory
  1   signature invalid, unreadable receipt/key, or not a GovernedAction/v1
      in-toto Statement
  2   signature valid, but a hashed evidence file is missing, outside the
      evidence root, or changed since signing
  64  usage error

No network. No SZL code beyond receipt.py. This is the artifact a CISO runs.
The signature covers the receipt, including the evidence digests it records.
Only --evidence-root compares those digests with files on disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import receipt as R

EVIDENCE_FAILED = 2
USAGE = 64


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # keep the documented usage exit code
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(USAGE)


def check_evidence(predicate: dict, root: pathlib.Path) -> list[tuple[str, str]]:
    """(status, ref) for every evidence item that records a sha256 digest."""
    base = root.resolve()
    results = []
    for item in predicate.get("evidence", []):
        if not isinstance(item, dict) or not item.get("sha256"):
            continue
        ref = str(item.get("ref") or "")
        path = (base / ref).resolve()
        if base != path and base not in path.parents:
            results.append(("OUTSIDE_ROOT", ref))
        elif not path.is_file():
            results.append(("MISSING", ref))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            results.append(("MISMATCH", ref))
        else:
            results.append(("MATCH", ref))
    return results


def main(argv=None) -> int:
    ap = _Parser(description="Offline verifier for SZL audit receipts.")
    ap.add_argument("receipt", type=pathlib.Path)
    ap.add_argument("public_key", type=pathlib.Path)
    ap.add_argument("--evidence-root", type=pathlib.Path,
                    help="directory the receipt's evidence refs are relative to (e.g. a checkout)")
    args = ap.parse_args(argv)

    try:
        env = json.loads(args.receipt.read_text())
        pk = R.load_public(args.public_key.read_text())
    except (OSError, ValueError, TypeError) as error:
        print(f"FAIL: cannot read receipt or public key ({type(error).__name__})")
        return 1
    try:
        statement = R.dsse_verify(env, pk)
    except (ValueError, KeyError, TypeError, AttributeError):
        print("FAIL: signature_invalid")
        return 1
    if (not isinstance(statement, dict) or env.get("payloadType") != R.MEDIA_TYPE
            or statement.get("_type") != R.STATEMENT_TYPE
            or statement.get("predicateType") != R.PREDICATE_TYPE
            or not isinstance(statement.get("predicate"), dict)):
        print("FAIL: signed payload is not a GovernedAction/v1 in-toto Statement")
        return 1

    pred = statement["predicate"]
    print("VERIFY: PASS (offline)")
    print(f"  predicateType: {statement['predicateType']}")
    print(f"  action:        {pred.get('action')}")
    print(f"  truth_state:   {pred.get('truth_state')}")
    print(f"  completeness:  {pred.get('completeness')}")
    print(f"  keyid:         {env['signatures'][0].get('keyid')}")
    if pred.get("completeness") != "COMPLETE":
        print("  note: evidence obligations unmet; this receipt does not assert PASS")

    if args.evidence_root is None:
        print("  evidence:      digests not compared with files (pass --evidence-root DIR)")
        return 0
    results = check_evidence(pred, args.evidence_root)
    for status, ref in results:
        print(f"  evidence:      {status:<12} {ref}")
    failed = [ref for status, ref in results if status != "MATCH"]
    if failed:
        print(f"EVIDENCE: FAIL ({len(failed)} of {len(results)} recorded digests do not match "
              f"files under {args.evidence_root}); the signature covers the record, not these files")
        return EVIDENCE_FAILED
    print(f"EVIDENCE: PASS ({len(results)} of {len(results)} recorded digests match files under "
          f"{args.evidence_root})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
