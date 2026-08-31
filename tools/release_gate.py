#!/usr/bin/env python3
"""release_gate.py — the raise gate.

Reads COMMERCIAL_LEDGER.yaml + CONTRADICTION_REGISTER.yaml and fails while
any commercial row is UNKNOWN / unattested or any BLOCKER contradiction is open.

Tiny YAML reader scoped to the exact ledgers we emit (no dependency).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGERS = ROOT / "ledgers"


def rows_with_unknown(text: str) -> list[str]:
    """Return metric names whose value rendered as UNKNOWN (None at build)."""
    out = []
    for m in re.finditer(r"- metric: (\S+)[\s\S]*?value: UNKNOWN", text):
        out.append(m.group(1))
    return out


def open_blockers(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"id: ((?:B-\d+|HW-\d+))\n\s+severity: (BLOCKER)", text):
        out.append(m.group(1))
    return out


def main() -> int:
    commercial_path = LEDGERS / "COMMERCIAL_LEDGER.yaml"
    contradictions_path = LEDGERS / "CONTRADICTION_REGISTER.yaml"

    print("== RELEASE GATE ==")
    status = 0

    if not commercial_path.exists():
        print("FAIL: COMMERCIAL_LEDGER.yaml missing — run build_ledgers.py")
        return 6
    text = commercial_path.read_text()
    unknown = rows_with_unknown(text)
    if unknown:
        status = 6
        print(f"FAIL: {len(unknown)} commercial metrics UNKNOWN (each sets blocks_raise=true):")
        for u in unknown:
            print(f"  - {u}")
        print("No model may invent these. They are supplied by evidence: contracts, bank, cap table, counsel.")

    if contradictions_path.exists():
        ctext = contradictions_path.read_text()
        blockers = open_blockers(ctext)
        if blockers:
            status = 6
            print(f"FAIL: {len(blockers)} BLOCKER contradictions open: {', '.join(blockers)}")

    if status == 0:
        print("clean — raise not blocked by truth ledgers")
    else:
        print("\nThis failure is the Week 1 checklist, not a bug.")
    return status


if __name__ == "__main__":
    sys.exit(main())
