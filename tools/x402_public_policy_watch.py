#!/usr/bin/env python3
"""Bounded, public, GET-only x402 route-policy witness.

A 402 challenge is NOT payment, settlement, or revenue. No credentials,
payment signatures, POSTs, origin bodies, or redirects are ever consumed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

# Source-owned import also works under Python -I, without trusting CWD.
_CONTRACT = Path(__file__).resolve().with_name("x402_challenge_receipt.py")
_SPEC = importlib.util.spec_from_file_location("_szl_x402_challenge_contract", _CONTRACT)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit("FAIL_CLOSED: SOURCE_CONTRACT_UNAVAILABLE")
witness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(witness)

SCHEMA = "szl.x402-public-policy-witness/v1"
TARGETS = (
    ("product", "https://a-11-oy.com/", "free"),
    ("proof", "https://a11oy.net/", "free"),
    ("inference", "https://inference.a-11-oy.com/v1/completions", "paid"),
    ("chat", "https://a-11-oy.com/v1/chat/", "paid"),
)
MAX_CHALLENGE_HEADER = 16384
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def observe(name, url, policy, *, opener, observed_at, catalog, catalog_sha):
    """One observation of one literal public route. Never return header bytes."""
    row = {"surface": name, "expected": policy, "state": "BLOCKED",
           "http_status": None, "reason": "TRANSPORT_UNAVAILABLE"}
    request = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json", "Cache-Control": "no-store",
                 "User-Agent": "SZL-Public-Policy-Witness/1"},
    )
    response = None
    try:
        try:
            response = opener.open(request, timeout=12)
        except urllib.error.HTTPError as error:
            response = error
        status = getattr(response, "status", None)
        if type(status) is not int:
            status = getattr(response, "code", None)
        if type(status) is not int or not 100 <= status <= 599:
            return row
        row["http_status"] = status
        if response.geturl() != url:
            row["reason"] = "REDIRECT_OR_TARGET_DRIFT"
            return row
        headers = response.headers
        if headers.get("cf-mitigated"):
            row["reason"] = "EDGE_CHALLENGE_UNAVAILABLE"
            return row
        encoded = headers.get("PAYMENT-REQUIRED", "")
        if encoded and (not isinstance(encoded, str) or len(encoded) > MAX_CHALLENGE_HEADER):
            row["reason"] = "CHALLENGE_HEADER_INVALID"
            return row
        if policy == "free":
            if status == 200 and not encoded:
                row["state"], row["reason"] = "PASS", "FREE_HTTP_200"
            else:
                row["reason"] = "FREE_ROUTE_UNAVAILABLE_OR_PAYWALLED"
            return row
        if policy != "paid" or status != 402 or not encoded:
            row["reason"] = "PAID_CHALLENGE_UNAVAILABLE"
            return row
        capture = {"schema": witness.CAPTURE_SCHEMA, "url": url, "method": "GET",
                   "status": status, "payment_required": encoded,
                   "observed_at": observed_at}
        capture_bytes = json.dumps(capture, sort_keys=True,
                                   separators=(",", ":")).encode()
        comparison = witness.make_report([capture], catalog,
                        input_sha256=hashlib.sha256(capture_bytes).hexdigest(),
                        catalog_sha256=catalog_sha)
        proof = comparison["records"][0]
        if proof["status"] == "CHALLENGE_MATCH" and comparison["result"] == "CHALLENGES_MATCH":
            row["state"], row["reason"] = "PASS", "CHALLENGE_CATALOG_MATCH"
            row["rule_id"] = proof["rule_id"]
        else:
            row["reason"] = proof.get("reason", "CHALLENGE_CONTRACT_UNAVAILABLE")
        return row
    except (OSError, ValueError, witness.InvalidEvidence):
        row["reason"] = "CHALLENGE_CONTRACT_UNAVAILABLE" if row["http_status"] == 402 else "TRANSPORT_UNAVAILABLE"
        return row
    finally:
        if response is not None:
            response.close()


def snapshot(*, opener, catalog_bytes: bytes, observed_at: str, source_revision: str):
    catalog_sha = hashlib.sha256(catalog_bytes).hexdigest()
    catalog = witness._json_bytes(catalog_bytes)
    if not isinstance(catalog, dict) or catalog.get("schema") != "szl.x402-pricing/v2":
        raise witness.InvalidEvidence("CATALOG_INVALID")
    if not isinstance(observed_at, str):
        raise witness.InvalidEvidence("TIME_INVALID")
    witness._timestamp(observed_at)
    rows = [
        observe(name, url, policy, opener=opener, observed_at=observed_at,
                catalog=catalog, catalog_sha=catalog_sha)
        for name, url, policy in TARGETS
    ]
    ok = len(rows) == len(TARGETS) and all(row["state"] == "PASS" for row in rows)
    return {
        "schema": SCHEMA, "observed_at": observed_at,
        "source_revision": source_revision if SHA40.fullmatch(source_revision) else "UNOBSERVED_LOCAL",
        "catalog_sha256": catalog_sha,
        "scope": "PUBLIC_UNAUTHENTICATED_GET_CHALLENGES_ONLY",
        "status": "POLICY_CHALLENGES_OBSERVED" if ok else "FAIL_CLOSED",
        "provider_rule_readback": "NOT_PERFORMED",
        "authorization": "UNVERIFIED", "settlement": "UNVERIFIED",
        "revenue": "NO_CLAIM", "wallet_used": False,
        "requests": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("pricing/generated/x402-pricing.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        content = args.catalog.read_bytes()
        result = snapshot(
            opener=urllib.request.build_opener(
                urllib.request.ProxyHandler({}), NoRedirect()),
            catalog_bytes=content,
            observed_at=datetime.now(timezone.utc).isoformat(),
            source_revision=os.getenv("GITHUB_SHA", ""),
        )
        raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
        if args.output.is_symlink():
            raise witness.InvalidEvidence("OUTPUT_SYMLINK")
        witness._atomic_write(args.output, raw)
        print(f"{result['status']}: {sum(x['state']=='PASS' for x in result['requests'])}/{len(TARGETS)}"
              " public policy observations; settlement=UNVERIFIED revenue=NO_CLAIM")
        return 0 if result["status"] == "POLICY_CHALLENGES_OBSERVED" else 2
    except (OSError, witness.InvalidEvidence) as exc:
        code = exc.code if isinstance(exc, witness.InvalidEvidence) else "IO_UNAVAILABLE"
        print("FAIL_CLOSED: " + code + " settlement=UNVERIFIED revenue=NO_CLAIM", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
