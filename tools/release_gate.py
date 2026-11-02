#!/usr/bin/env python3
"""release_gate.py — the raise gate.

Reads COMMERCIAL_LEDGER.yaml + CONTRADICTION_REGISTER.yaml and fails while
any commercial row is UNKNOWN / unattested or any BLOCKER contradiction is open.

Tiny YAML reader scoped to the exact ledgers we emit (no dependency).
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys

from build_ledgers import COMMERCIAL_ROWS

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGERS = ROOT / "ledgers"
MAX_LEDGER_BYTES = 1024 * 1024
COMMERCIAL_FIELDS = {"metric", "definition", "value", "evidence_ref", "blocks_raise", "evidence_class"}
CONTRADICTION_FIELDS = {"id", "severity", "statement", "resolution"}


def scalar(text):
    """Read scalar values from yamlite's emitted, deliberately small YAML subset."""
    if text.startswith('"'):
        value = json.loads(text)
        if not isinstance(value, str):
            raise ValueError("quoted scalar must be text")
        return value
    if text in {"true", "false", "null"}:
        return json.loads(text)
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", text):
        value = json.loads(text)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite ledger number")
        return value
    if not text or text != text.strip() or any(c in text for c in ":#{}[],&*?|<>=%@`\"'"):
        raise ValueError("unsupported ledger scalar")
    return text


def ledger_rows(text, section):
    """Parse only the flat row format written by build_ledgers/yamlite.

    Unsupported YAML syntax, duplicate fields, and malformed indentation are
    refusals, never an empty result. This is not a general-purpose YAML loader.
    """
    headers, rows, current, started, empty = {}, [], None, False, False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            match = re.fullmatch(r"([a-z_]+):(.*)", line)
            if not match or started:
                raise ValueError("invalid ledger header")
            key, raw = match.groups()
            if key in headers:
                raise ValueError("duplicate ledger header")
            if key == section:
                if raw not in {"", " []"}:
                    raise ValueError("ledger rows must be a list")
                started, empty = True, raw == " []"
                headers[key] = True
            else:
                if not raw.startswith(" "):
                    raise ValueError("invalid ledger header value")
                headers[key] = scalar(raw[1:])
            continue
        if not started or empty:
            raise ValueError("row outside ledger list")
        first = re.fullmatch(r"  - ([a-z_]+): (.+)", line)
        more = re.fullmatch(r"    ([a-z_]+): (.+)", line)
        if first:
            current = {}
            rows.append(current)
            match = first
        elif more and current is not None:
            match = more
        else:
            raise ValueError("invalid ledger row")
        key, raw = match.groups()
        if key in current:
            raise ValueError("duplicate ledger field")
        current[key] = scalar(raw)
    expected = {"ledger", "rule", "rows"} if section == "rows" else {"contradictions"}
    if set(headers) != expected:
        raise ValueError("missing or unexpected ledger header")
    if section == "rows" and (headers["ledger"] != "COMMERCIAL_LEDGER" or not present(headers["rule"])):
        raise ValueError("wrong commercial ledger")
    if not rows and not empty:
        raise ValueError("missing ledger rows")
    fields = COMMERCIAL_FIELDS if section == "rows" else CONTRADICTION_FIELDS
    if any(set(row) != fields for row in rows):
        raise ValueError("missing or unexpected ledger field")
    return rows


def present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().upper() not in {"UNKNOWN", "NULL", "UNAVAILABLE", "~"}
    return True


def rows_with_unknown(text: str) -> list[str]:
    """Return blocked/unattested metrics; require the builder's complete metric set."""
    rows = ledger_rows(text, "rows")
    metrics = [row["metric"] for row in rows]
    if (not all(isinstance(metric, str) for metric in metrics)
            or len(set(metrics)) != len(metrics)
            or set(metrics) != {metric for metric, _ in COMMERCIAL_ROWS}):
        raise ValueError("commercial metric set is incomplete or duplicated")
    if any(type(row["blocks_raise"]) is not bool for row in rows):
        raise ValueError("blocks_raise must be a boolean")
    return [row["metric"] for row in rows if row["blocks_raise"] or not present(row["value"])
            or not isinstance(row["evidence_ref"], str) or not present(row["evidence_ref"])]


def open_blockers(text: str) -> list[str]:
    rows = ledger_rows(text, "contradictions")
    ids = [row["id"] for row in rows]
    if (not all(isinstance(identifier, str) and present(identifier) for identifier in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("invalid or duplicate contradiction id")
    if any(row["severity"] not in {"BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "RESOLVED"}
           for row in rows):
        raise ValueError("invalid contradiction severity")
    return [row["id"] for row in rows if row["severity"] == "BLOCKER"]


def read_ledger(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_LEDGER_BYTES + 1)
    if len(data) > MAX_LEDGER_BYTES:
        raise ValueError("ledger exceeds byte limit")
    return data.decode("utf-8")


def main() -> int:
    commercial_path = LEDGERS / "COMMERCIAL_LEDGER.yaml"
    contradictions_path = LEDGERS / "CONTRADICTION_REGISTER.yaml"

    print("== RELEASE GATE ==")
    status = 0

    try:
        unknown = rows_with_unknown(read_ledger(commercial_path))
        blockers = open_blockers(read_ledger(contradictions_path))
    except (OSError, ValueError) as error:
        print(f"FAIL: required truth ledger unavailable or invalid ({type(error).__name__})")
        return 6
    if unknown:
        status = 6
        print(f"FAIL: {len(unknown)} commercial metrics blocked or unattested:")
        for u in unknown:
            print(f"  - {u}")
        print("No model may invent these. They are supplied by evidence: contracts, bank, cap table, counsel.")

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
