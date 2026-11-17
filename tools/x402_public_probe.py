#!/usr/bin/env python3
"""Bounded public GET x402 challenge readback; never a buyer or settlement probe.

One run, 1-8 prevalidated HTTPS URLs, no wallet, signature, credentials,
redirect follow, POST, side effects or retries. Receipts are append-only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

import x402_challenge_receipt as contract

SCHEMA = "szl.x402-live-public-challenge/v1"
MAX_URLS = 8
MAX_HEADER_CHARS = 131_072
ACCESS_STOP_CODES = frozenset((401, 403, 429))


class InputHold(ValueError):
    """A stable refusal code, never provider content."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def utc_now():
    return datetime.now(timezone.utc)


def validate_scope(catalog, urls, now):
    """Validate every requested URL and catalog freshness before any GET."""
    if not isinstance(catalog, dict) or catalog.get("schema") != "szl.x402-pricing/v2":
        raise InputHold("CATALOG_SCHEMA")
    if type(catalog.get("x402_version")) is not int or catalog["x402_version"] != 2:
        raise InputHold("CATALOG_VERSION")
    try:
        catalog_time = contract._timestamp(catalog["as_of"])
    except (KeyError, contract.InvalidEvidence):
        raise InputHold("CATALOG_TIME") from None
    if now.tzinfo is None or now.utcoffset() is None:
        raise InputHold("CLOCK_UNOBSERVED")
    now = now.astimezone(timezone.utc)
    if now < catalog_time or now - catalog_time > timedelta(days=7):
        raise InputHold("CATALOG_STALE_OR_FUTURE")
    if not isinstance(urls, list) or not 1 <= len(urls) <= MAX_URLS:
        raise InputHold("URL_COUNT")
    if any(not isinstance(url, str) for url in urls):
        raise InputHold("URL_INVALID")
    if len(set(urls)) != len(urls):
        raise InputHold("DUPLICATE_URL")
    for url in urls:
        try:
            target = contract._request_target(url)
            if target.query or target.fragment:
                raise InputHold("QUERY_OR_FRAGMENT_DISALLOWED")
            rule = contract._match_catalog_rule(catalog, target, "GET")
            if rule.get("audience") != "everyone":
                raise InputHold("AUDIENCE_NEEDS_PROVIDER_EVIDENCE")
            if target.geturl() != url:
                raise InputHold("NONCANONICAL_URL")
        except contract.InvalidEvidence as exc:
            raise InputHold(exc.code) from None


def _response_code_and_header(opener, url):
    """One GET, bounded header only. Never read response bodies or follow redirects."""
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "SZL-x402-contract-readback/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with opener.open(req, timeout=12) as response:
            code, headers = response.status, response.headers
    except urllib.error.HTTPError as exc:
        code, headers = exc.code, exc.headers
    if type(code) is not int:
        return None, None
    header = headers.get("PAYMENT-REQUIRED") if headers else None
    if header is not None and (
        not isinstance(header, str) or len(header) > MAX_HEADER_CHARS
    ):
        return code, "HEADER_OVER_BUDGET"
    return code, header


def observe(catalog, urls, *, opener=None, now=None):
    """Return a privacy-safe report; a challenge is not a sale or qualification."""
    now = utc_now() if now is None else now
    validate_scope(catalog, urls, now)
    if opener is None:
        opener = urllib.request.build_opener(NoRedirect())
    rows = []
    stopped = False
    for url in urls:
        row = {"url": url, "method": "GET", "status": "UNOBSERVED"}
        if stopped:
            row["reason"] = "PROVIDER_LANE_STOPPED"
            rows.append(row)
            continue
        try:
            code, header = _response_code_and_header(opener, url)
            row["http_code"] = code
            if code in ACCESS_STOP_CODES:
                stopped = True
                row["reason"] = "HTTP_" + str(code) + "_STOP"
            elif code != 402:
                row["reason"] = "NOT_402"
            elif header == "HEADER_OVER_BUDGET":
                row["reason"] = "HEADER_BYTE_BUDGET"
            elif not header:
                row["reason"] = "PAYMENT_REQUIRED_HEADER_MISSING"
            else:
                row["payment_required_sha256"] = hashlib.sha256(
                    header.encode("ascii", errors="strict")
                ).hexdigest()
                capture = {
                    "schema": contract.CAPTURE_SCHEMA,
                    "url": url,
                    "method": "GET",
                    "status": 402,
                    "payment_required": header,
                    "observed_at": now.isoformat(),
                }
                try:
                    detail = contract.inspect(capture, catalog)
                    row["status"] = "CHALLENGE_MATCH"
                    row["rule_id"] = detail["rule_id"]
                    row["amount_atomic"] = detail["amount_atomic"]
                except contract.InvalidEvidence as exc:
                    row["reason"] = exc.code
        except (UnicodeError, ValueError):
            row["reason"] = "HEADER_ENCODING_INVALID"
        except Exception as exc:
            # Never serialize provider error strings, URLs or headers.
            row["reason"] = "TRANSPORT_" + type(exc).__name__
        rows.append(row)
    matched = sum(r["status"] == "CHALLENGE_MATCH" for r in rows)
    return {
        "schema": SCHEMA,
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "catalog_as_of": catalog["as_of"],
        "scope": "PUBLIC_GET_CHALLENGE_ONLY",
        "methods_checked": ["GET"],
        "requested_count": len(urls),
        "matched_count": matched,
        "provider_lane_stopped": stopped,
        "result": "CHALLENGES_MATCH" if matched == len(urls) else "HOLD",
        "rows": rows,
        "signed_authorization_observed": False,
        "settlement_verified": False,
        "revenue_verified": False,
        "post_billing_verified": False,
        "origin_jwt_verified": False,
        "origin_serving_verified": False,
        "live_gateway_rule_export_verified": False,
        "model_quality_verified": False,
        "provider_mutations": 0,
        "wallet_operations": 0,
        "publications": 0,
        "limitations": [
            "GET alone does not prove POST billing or paid origin behavior",
            "Challenge matching does not verify client authorization or settlement",
            "A historical catalog cannot attest to current dashboard rules",
        ],
    }


def write_exclusive(path, result):
    """No overwrite, no implicit output directory creation or signer claim."""
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise InputHold("OUTPUT_DIRECTORY_UNAVAILABLE")
    raw = (
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--url", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        with Path(args.catalog).open("rb") as stream:
            catalog_bytes = stream.read(contract.MAX_BYTES + 1)
        catalog = contract._json_bytes(catalog_bytes)
        result = observe(catalog, args.url)
        result["catalog_sha256"] = hashlib.sha256(catalog_bytes).hexdigest()
        digest = write_exclusive(args.output, result)
    except (InputHold, contract.InvalidEvidence, OSError, ValueError) as exc:
        code = exc.args[0] if isinstance(exc, InputHold) else type(exc).__name__
        print(json.dumps({"result": "HOLD", "reason": code}))
        return 3
    print(
        json.dumps(
            {
                "result": result["result"],
                "matched": result["matched_count"],
                "requested": result["requested_count"],
                "provider_lane_stopped": result["provider_lane_stopped"],
                "output_sha256": digest,
                "settlement_verified": False,
                "revenue_verified": False,
            },
            sort_keys=True,
        )
    )
    return 0 if result["result"] == "CHALLENGES_MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
