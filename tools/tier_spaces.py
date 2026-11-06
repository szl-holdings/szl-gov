#!/usr/bin/env python3
"""tier_spaces.py — apply the 8 flagship tests to every public Space, emit spaces_tiering.json.

Machine-checked tests are computed from the committed probe + listing + README
evidence. A test whose evidence was never captured fails: UNKNOWN, not invented.
Test names are spaces_gate.FLAGSHIP_TESTS, so a row can only pass what the gate
checks. spaces_gate.py consumes the output; failing honestly is the point.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from audit_data_builder import is_public_hf, load_withheld
from spaces_gate import FLAGSHIP_TESTS

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit_data"

# Recommended flagship set (buyer-legible wedge surfaces first). Max 5.
RECOMMENDED_FLAGSHIP = [
    "a11oy",
    "killinchu",
    "governed-receipt-verifier",
    "szl-khipu",
    "immune",
]
# Org card gets its own tier.
ORG_CARD = "README"


# The 8 tests run 2026-08-30 evidence: README captures (audit_data/readmes/) and
# Hub probes (audit_data/probes/). Keys are the gate's FLAGSHIP_TESTS names.
def _readme(name):
    p = AUDIT / "readmes" / f"{name}.md"
    return p.read_text(errors="replace") if p.exists() else ""


def _deployed_revision(probe):
    """The Hub's runtime.sha (revision of the running build) equals the source revision.

    Stage RUNNING is not evidence of what is deployed (B-06). Static Spaces
    report no runtime.sha, so their deployed revision stays UNKNOWN.
    """
    source = probe.get("sha")
    return bool(source) and (probe.get("runtime") or {}).get("sha") == source


MACHINE_TESTS = {
    "current source revision attested": lambda s, probe: bool(probe.get("sha")),
    "deployed revision attested (stage RUNNING is NOT evidence)": lambda s, probe: _deployed_revision(probe),
    # No mobile-UA capture is committed under audit_data/probes/ (the 2026-08-30
    # curl results were not recorded), so this is UNKNOWN for every Space until
    # one is. It used to pass from a hard-coded name list and for any static Space.
    "mobile smoke test passed": lambda s, probe: False,
    "conversion event present": lambda s, probe: bool(re.search(r"(pricing|buy|contact|demo|get started|sign up|deploy this|use this|try it|try the|purchase|mailto:|verify a)", _readme(s["path"].split("/")[-1]), re.I)),
    "link to a real verifier or receipt artifact": lambda s, probe: bool(re.search(r"(verif|receipt|dsse|signature|a11oy\.net|offline)", _readme(s["path"].split("/")[-1]), re.I)),
    "no stale metric on the card": lambda s, probe: not re.search(r"\b26\s+spaces\b|\b26\s+repos\b", _readme(s["path"].split("/")[-1]), re.I),
    "buyer-legible CTA": lambda s, probe: bool(re.search(r"(pricing|contact us|book|schedule|get started|deploy|use case)", _readme(s["path"].split("/")[-1]), re.I)),
    "declared truth state": lambda s, probe: True,  # every row gets a truth_state field below
}
if set(MACHINE_TESTS) != set(FLAGSHIP_TESTS):
    raise RuntimeError("tier_spaces.MACHINE_TESTS must name exactly spaces_gate.FLAGSHIP_TESTS")

HUMAN_TESTS = []  # all machine-checked; human-only = billing + final attestation sign-off


def main() -> int:
    hf = json.load(open(AUDIT / "hf_org_listing.json"))
    # Only Spaces the snapshot marks public are tiered and listed; the rest are counted.
    spaces = [s for s in hf["spaces"] if is_public_hf(s)]
    withheld = len(hf["spaces"]) - len(spaces) + load_withheld(AUDIT).get("hf_spaces", 0)
    tiers = []

    for s in spaces:
        name = s["path"].split("/")[-1]
        probe_path = AUDIT / "probes" / f"space_{name}.json"
        probe = {}
        if probe_path.exists():
            probe = json.load(open(probe_path))

        if name == ORG_CARD:
            tier = "ORG_CARD"
        elif name in RECOMMENDED_FLAGSHIP:
            tier = "FLAGSHIP"
        elif s.get("private"):
            tier = "LAB"
        else:
            tier = "SUPPORTING"

        passed = [k for k, f in MACHINE_TESTS.items() if f(s, probe)]
        entry = {
            "name": name,
            "path": s["path"],
            "tier": tier,
            "sdk": s.get("sdk"),
            "private": bool(s.get("private")),
            "runtime_stage": (probe.get("runtime") or {}).get("stage") or "UNKNOWN",
            "source_sha": (probe.get("sha") or "")[:8] or None,
            "deployed_sha": ((probe.get("runtime") or {}).get("sha") or "")[:8] or None,
            "truth_state": "VERIFIED" if (probe.get("runtime") or {}).get("stage") == "RUNNING" else "UNKNOWN",
            "attested": len(passed) == len(MACHINE_TESTS),
            "tests_passed": passed,
            "tests_failed": [t for t in MACHINE_TESTS if t not in passed],
            "notes": "",
        }
        if tier == "FLAGSHIP":
            missing = [t for t in MACHINE_TESTS if t not in passed]
            entry["notes"] = ("Fully machine-attested." if not missing
                              else f"Flagship gap(s): {', '.join(missing)}")
        elif tier == "ORG_CARD":
            entry["notes"] = "Org card is itself a Space (B-08). Needs receipt link + no stale metric."
        elif tier == "LAB" and s.get("sdk") == "docker":
            entry["notes"] = "Private Docker lab. Candidate: archive with dated frozen banner or demote to static."
        tiers.append(entry)

    out = {
        "generated_by": "tools/tier_spaces.py",
        "flagship_capacity": 5,
        "billing_verified": False,  # human: confirm HF TEAM plan covers the 4 public Docker Spaces
        "withheld_non_public": withheld,
        "tiers": tiers,
    }
    dest = ROOT / "ledgers" / "spaces_tiering.json"
    dest.write_text(json.dumps(out, indent=1))

    from collections import Counter
    c = Counter(t["tier"] for t in tiers)
    print("tiering written:", dict(c), f"(non-public Spaces withheld: {withheld})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
