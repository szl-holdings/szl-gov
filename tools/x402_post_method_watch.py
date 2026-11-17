#!/usr/bin/env python3
"""Explicitly opted-in, unauthenticated POST challenge witness (no wallet).

A 402 is a price request, not a sale. This module cannot sign, pay, settle,
transact or authorize a caller. Both request bodies are intentionally invalid.
It does not follow redirects, consume response bodies, or accept URL inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CONTRACT = Path(__file__).resolve().with_name("x402_challenge_receipt.py")
_SPEC = importlib.util.spec_from_file_location("_szl_x402_post_contract", _CONTRACT)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit("FAIL_CLOSED: SOURCE_CONTRACT_UNAVAILABLE")
witness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(witness)

TARGETS = (
    ("chat", "https://a-11-oy.com/v1/chat/completions"),
    ("inference", "https://inference.a-11-oy.com/v1/completions"),
)
SCHEMA = "szl.x402-post-method-witness/v1"
INVALID_BODY = b'{"szl_post_method_probe_invalid":true}'
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_HEADER = 16384


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _verify_402(header: str, url: str, catalog: dict, observed_at: str) -> str:
    """Validate observed POST terms against the GET-priced public reference.

    The dated catalog records public prices but does not itself establish
    whether POST is charged. A matching *observed* POST 402 establishes that.
    """
    if not isinstance(header, str) or not 0 < len(header) <= MAX_HEADER:
        return "HEADER_MISSING_OR_OVERSIZED"
    try:
        observed = witness._timestamp(observed_at)
        as_of = witness._timestamp(catalog["as_of"])
        if observed < as_of or observed - as_of > timedelta(days=7):
            return "CATALOG_STALE_OR_FUTURE"
        target = witness._request_target(url)
        rule = witness._match_catalog_rule(catalog, target, "GET")
        if rule.get("audience") != "everyone":
            return "AUDIENCE_NEEDS_PROVIDER_PROOF"
        decoded = witness._decode_header(header)
        if not isinstance(decoded, dict) or type(decoded.get("x402Version")) is not int or decoded["x402Version"] != 2:
            return "VERSION_DRIFT"
        if not isinstance(decoded.get("resource"), dict) or decoded["resource"].get("url") != url:
            return "RESOURCE_DRIFT"
        offers = decoded.get("accepts")
        if not isinstance(offers, list) or len(offers) != 1 or not isinstance(offers[0], dict):
            return "OFFERS_AMBIGUOUS"
        offer = offers[0]
        payment = catalog["payment"]
        if offer.get("scheme") != rule["scheme"] or offer.get("network") != payment["network"]:
            return "SCHEME_NETWORK_DRIFT"
        if witness._address(offer.get("asset")) != witness._address(payment["asset"]):
            return "ASSET_DRIFT"
        if witness._address(offer.get("payTo")) != witness._address(payment["pay_to"]):
            return "RECIPIENT_DRIFT"
        if witness._atomic(offer.get("amount")) != witness._atomic(rule["amount_atomic"]):
            return "PRICE_DRIFT"
        timeout = offer.get("maxTimeoutSeconds")
        if type(timeout) is not int or not 1 <= timeout <= 86400:
            return "TIMEOUT_INVALID"
        if not isinstance(offer.get("extra"), dict):
            return "EXTRA_INVALID"
        return "CHALLENGE_CATALOG_MATCH"
    except (witness.InvalidEvidence, KeyError, ValueError, TypeError):
        return "CHALLENGE_INVALID"


def observe(name, url, *, opener, catalog, observed_at):
    row = {"surface": name, "method": "POST", "http_status": None,
           "state": "BLOCKED", "reason": "TRANSPORT_UNAVAILABLE"}
    request = urllib.request.Request(
        url, method="POST", data=INVALID_BODY,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "Cache-Control": "no-store",
                 "User-Agent": "SZL-Unsigned-Post-Method-Witness/1"},
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
        elif response.headers.get("cf-mitigated"):
            row["reason"] = "EDGE_CHALLENGE_UNAVAILABLE"
        elif status != 402:
            row["reason"] = "POST_PAYMENT_CHALLENGE_UNAVAILABLE"
        else:
            row["reason"] = _verify_402(
                response.headers.get("PAYMENT-REQUIRED", ""),
                url, catalog, observed_at)
            if row["reason"] == "CHALLENGE_CATALOG_MATCH":
                row["state"] = "PASS"
        return row
    except (OSError, ValueError, TypeError):
        return row
    finally:
        if response is not None:
            response.close()


def snapshot(*, opener, catalog_bytes: bytes, observed_at: str, source_revision: str):
    catalog = witness._json_bytes(catalog_bytes)
    if not isinstance(catalog, dict) or catalog.get("schema") != "szl.x402-pricing/v2":
        raise witness.InvalidEvidence("CATALOG_INVALID")
    witness._timestamp(observed_at)
    rows = [observe(name, url, opener=opener, catalog=catalog, observed_at=observed_at)
            for name, url in TARGETS]
    return {
        "schema": SCHEMA, "observed_at": observed_at,
        "source_revision": source_revision if SHA40.fullmatch(source_revision) else "UNOBSERVED_LOCAL",
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "scope": "UNSIGNED_INVALID_BODY_POST_CHALLENGES_ONLY",
        "catalog_reference_method": "GET",
        "status": "POST_CHALLENGES_OBSERVED" if all(r["state"] == "PASS" for r in rows) else "FAIL_CLOSED",
        "authorization": "UNVERIFIED", "origin_fulfillment": "UNVERIFIED",
        "settlement": "UNVERIFIED", "revenue": "NO_CLAIM",
        "provider_rule_readback": "NOT_PERFORMED", "wallet_used": False,
        "requests": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("pricing/generated/x402-pricing.json"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true",
                        help="Allow exactly two invalid-body, unsigned production POST requests")
    args = parser.parse_args(argv)
    if not args.execute:
        print("FAIL_CLOSED: EXPLICIT_EXECUTE_REQUIRED; no network request", file=sys.stderr)
        return 2
    try:
        source = args.catalog.read_bytes()
        result = snapshot(
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()),
            catalog_bytes=source,
            observed_at=datetime.now(timezone.utc).isoformat(),
            source_revision=os.getenv("GITHUB_SHA", ""),
        )
        if args.output.is_symlink():
            raise witness.InvalidEvidence("OUTPUT_SYMLINK")
        witness._atomic_write(args.output, (json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
        print(f"{result['status']}: {sum(r['state']=='PASS' for r in result['requests'])}/{len(TARGETS)}"
              " unsigned POST 402 challenges; settlement=UNVERIFIED revenue=NO_CLAIM")
        return 0 if result["status"] == "POST_CHALLENGES_OBSERVED" else 2
    except (OSError, witness.InvalidEvidence) as exc:
        code = exc.code if isinstance(exc, witness.InvalidEvidence) else "IO_UNAVAILABLE"
        print("FAIL_CLOSED: " + code + " settlement=UNVERIFIED revenue=NO_CLAIM", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
