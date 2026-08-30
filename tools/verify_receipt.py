#!/usr/bin/env python3
"""verify_receipt.py — offline verifier for SZL audit receipts.

Usage:
    python3 verify_receipt.py receipts/audit-receipt-2026-08-30.dsse.json keys/szl-audit-ed25519.pub.pem

No network. No SZL code beyond receipt.py. This is the artifact a CISO runs.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import receipt as R


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 64
    env_path, pub_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    env = json.loads(env_path.read_text())
    pk = R.load_public(pub_path.read_text())
    try:
        statement = R.dsse_verify(env, pk)
    except ValueError:
        print("FAIL: signature_invalid")
        return 1
    pred = statement["predicate"]
    print("VERIFY: PASS (offline)")
    print(f"  predicateType: {statement['predicateType']}")
    print(f"  action:        {pred['action']}")
    print(f"  truth_state:   {pred['truth_state']}")
    print(f"  completeness:  {pred['completeness']}")
    print(f"  keyid:         {env['signatures'][0]['keyid']}")
    if pred["completeness"] == "INCOMPLETE":
        print("  note: evidence obligations unmet; this receipt does not assert PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
