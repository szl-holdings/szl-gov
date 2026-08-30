#!/usr/bin/env python3
"""lexicon_gate.py — the honesty gate.

Scans all markdown and ledger files for claims the estate is not entitled to make.
Non-zero exit is the intended first result. Exit codes ARE the fix list.

  0  lexicon clean
  5  banned phrasing found (compliance overclaim, unverifiable absolute, ...)
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# phrase -> why it's banned + lawful replacement
BANNED = [
    (r"\bEU AI Act compliant\b",
     "Overclaim. Say 'Article 12 logging conformance profile'. Applicability is customer-specific."),
    (r"\bfully compliant\b",
     "Absolute compliance claims are unauditable. Name the specific profile and its scope."),
    (r"\ball 26 spaces\b|\b26 spaces\b",
     "Stale count. Measured estate is 45 as of 2026-08-30. Cite the current inventory."),
    (r"\bfive flagship[s]?\b",
     "Capacity is not attainment. Flagship count is attested evidence, currently 0 of 5."),
    (r"\bproduction[- ]ready\b",
     "Means nothing without a named environment, revision, and receipt. Use truth states."),
    (r"\bmilitary[- ]grade\b|\benterprise[- ]grade\b",
     "Unverifiable adjective. State the control and its evidence instead."),
    (r"\b100% (?:secure|safe|private)\b",
     "Absolute security claims fail any red team. Describe the threat model boundary."),
    (r"\bguarantee[ds]?\b",
     "Nothing is guaranteed. State the invariant and its enforcement mechanism."),
    (r"\bno logs?\b",
     "Unprovable negative about a third party. Say 'not its stated purpose' and cite."),
    (r"\bpioneering\b|\bworld[- ]first\b|\brevolutionary\b",
     "Marketing adjectives with no evidence_ref. Delete or attach evidence."),
]

SCAN_SUFFIXES = {".md", ".yaml", ".yml"}
SKIP_DIRS = {"audit_data", ".git", "node_modules", "__pycache__"}
# Lines that quote a banned phrase in order to forbid it must carry this marker.
# The marker is itself auditable: grep for it to see every sanctioned quotation.
ALLOW_MARKER = "lexicon-ok"


def iter_files():
    for p in ROOT.rglob("*"):
        if p.is_dir() or p.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def main() -> int:
    hits = []
    for p in iter_files():
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        for pattern, reason in BANNED:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                line = text[:m.start()].count("\n") + 1
                if ALLOW_MARKER in lines[line - 1]:
                    continue  # sanctioned quotation, e.g. the lexicon table itself
                hits.append((p.relative_to(ROOT), line, m.group(0), reason))

    print("== LEXICON GATE ==")
    if not hits:
        print("clean")
        return 0
    for path, line, phrase, reason in hits:
        print(f"FAIL: {path}:{line}  '{phrase}'  -> {reason}")
    print(f"{len(hits)} banned phrase(s). Every one must be replaced with a claim that carries evidence.")
    return 5


if __name__ == "__main__":
    sys.exit(main())
