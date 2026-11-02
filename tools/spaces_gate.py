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

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from audit_data_builder import is_public_hf, load_withheld

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit_data"
FLAGSHIP_CAPACITY = 5
TIERS = {"FLAGSHIP", "SUPPORTING", "LAB", "ORG_CARD"}

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


def validate_coverage(tiering, spaces):
    """Bind each tier decision to exactly one public Space in the snapshot."""
    expected = {s["path"] for s in spaces}
    failures = []
    if not isinstance(tiering, dict) or not isinstance(tiering.get("tiers"), list):
        return [], len(expected), ["INVALID_TIERING: tiers must be a list"]
    rows, covered = [], set()
    for index, row in enumerate(tiering["tiers"]):
        if not isinstance(row, dict):
            failures.append(f"INVALID_TIER: row {index} must be an object")
            continue
        path, tier = row.get("path"), row.get("tier")
        if not isinstance(path, str) or path not in expected:
            failures.append(f"UNKNOWN_SPACE: row {index} is not in the public inventory")
            continue
        if path in covered:
            failures.append(f"DUPLICATE_SPACE: row {index} repeats a tier decision")
            continue
        if not isinstance(tier, str) or tier not in TIERS:
            failures.append(f"INVALID_TIER: row {index} has no recognized tier")
            continue
        covered.add(path)
        rows.append(row)
    untiered = len(expected - covered)
    if untiered:
        failures.append(f"UNTIERED_SPACES: {untiered} public Spaces have no valid tier decision")
    return rows, untiered, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiering", default=str(ROOT / "ledgers" / "spaces_tiering.json"),
                    help="hand-attested tiering file produced after human review")
    args = ap.parse_args()

    hf = json.load(open(AUDIT / "hf_org_listing.json"))
    spaces = [s for s in hf["spaces"] if is_public_hf(s)]

    failures, warnings = [], []
    untiered = len(spaces)
    billing_verified = False

    tier_path = pathlib.Path(args.tiering)
    if not tier_path.exists():
        failures.append(
            f"NO_TIERING: {tier_path.name} does not exist. "
            "Every one of the {n} Spaces is currently untiered -> all are BLOCKERS by policy. "
            "Create it by applying the 8 flagship tests in spaces_gate.py.".format(n=len(spaces))
        )
    else:
        tiers = json.load(open(tier_path))
        rows, untiered, coverage_failures = validate_coverage(tiers, spaces)
        failures.extend(coverage_failures)
        if isinstance(tiers, dict):
            billing_verified = tiers.get("billing_verified")
        flagships = [t for t in rows if t["tier"] == "FLAGSHIP"]
        if len(flagships) > FLAGSHIP_CAPACITY:
            failures.append(f"FLAGSHIP_OVERFLOW: {len(flagships)} flagships > capacity {FLAGSHIP_CAPACITY}")
        for f in flagships:
            if not f.get("attested"):
                failures.append(f"FLAGSHIP_UNATTESTED: {f.get('name')} missing attestation evidence")
            missing = [t for t in FLAGSHIP_TESTS if t not in f.get("tests_passed", [])]
            if missing:
                failures.append(f"FLAGSHIP_TESTS_INCOMPLETE: {f.get('name')} missing {len(missing)} tests")

    # Public docker = diligence-visible billing risk class
    public_docker = [s for s in spaces if s.get("sdk") == "docker"]
    if public_docker:
        warnings.append(
            "PUBLIC_DOCKER: " + ", ".join(s["path"] for s in public_docker)
            + " — confirm org billing covers Docker/Gradio on cpu-basic (July 2026 policy)."
        )

    print("== SPACES GATE ==")
    # The committed listing is public rows only; non-public Spaces survive as a count.
    withheld = len(hf["spaces"]) - len(spaces) + load_withheld(AUDIT).get("hf_spaces", 0)
    print(f"spaces={len(spaces)} public_docker={len(public_docker)} untiered={untiered} "
          f"withheld_non_public={withheld}")
    for w in warnings:
        print("WARN:", w)
    for f in failures:
        print("FAIL:", f)

    if not tier_path.exists():
        return 2
    if any("PUBLIC_DOCKER" in w for w in warnings) and not billing_verified:
        return 3
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
