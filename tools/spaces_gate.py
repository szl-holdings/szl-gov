#!/usr/bin/env python3
"""spaces_gate.py — CI gate over the Spaces estate.

Exit codes are the Week 1 checklist. Non-zero IS the correct first result.

  0  estate clean
  2  flagship capacity exceeded or flagship unattested
  3  public docker flagship billing risk unresolved
  4  backlink evidence missing for flagship spaces
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit_data"
FLAGSHIP_CAPACITY = 5

FLAGSHIP_TESTS = [
    "current source revision attested",
    "deployed revision attested (stage RUNNING is NOT evidence)",
    "mobile smoke test passed",
    "conversion event present",
    "declared truth state",
    "link to a real verifier or receipt artifact",
    "no stale metric on the card",
    "buyer-legible CTA",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiering", default=str(ROOT / "ledgers" / "spaces_tiering.json"),
                    help="hand-attested tiering file produced after human review")
    args = ap.parse_args()

    hf = json.load(open(AUDIT / "hf_org_listing.json"))
    spaces = hf["spaces"]
    by_path = {s["path"].split("/")[-1]: s for s in spaces}

    failures, warnings = [], []

    tier_path = pathlib.Path(args.tiering)
    if not tier_path.exists():
        failures.append(
            f"NO_TIERING: {tier_path.name} does not exist. "
            "Every one of the {n} Spaces is currently untiered -> all are BLOCKERS by policy. "
            "Create it by applying the 8 flagship tests in spaces_gate.py.".format(n=len(spaces))
        )
    else:
        tiers = json.load(open(tier_path))
        flagships = [t for t in tiers.get("tiers", []) if t.get("tier") == "FLAGSHIP"]
        if len(flagships) > FLAGSHIP_CAPACITY:
            failures.append(f"FLAGSHIP_OVERFLOW: {len(flagships)} flagships > capacity {FLAGSHIP_CAPACITY}")
        for f in flagships:
            if not f.get("attested"):
                failures.append(f"FLAGSHIP_UNATTESTED: {f.get('name')} missing attestation evidence")
            missing = [t for t in FLAGSHIP_TESTS if t not in f.get("tests_passed", [])]
            if missing:
                failures.append(f"FLAGSHIP_TESTS_INCOMPLETE: {f.get('name')} missing {len(missing)} tests")

    # Public docker = diligence-visible billing risk class
    public_docker = [s for s in spaces if s.get("sdk") == "docker" and not s.get("private")]
    if public_docker:
        warnings.append(
            "PUBLIC_DOCKER: " + ", ".join(s["path"] for s in public_docker)
            + " — confirm org billing covers Docker/Gradio on cpu-basic (July 2026 policy)."
        )

    untiered = len(spaces) if not tier_path.exists() else 0

    print("== SPACES GATE ==")
    print(f"spaces={len(spaces)} public_docker={len(public_docker)} untiered={untiered}")
    for w in warnings:
        print("WARN:", w)
    for f in failures:
        print("FAIL:", f)

    if not tier_path.exists():
        return 2
    if any("PUBLIC_DOCKER" in w for w in warnings) and not json.load(open(tier_path)).get("billing_verified"):
        return 3
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
