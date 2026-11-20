#!/usr/bin/env python3
"""Fail-closed, read-only x402 v2 challenge-to-catalog comparator.

It cannot authorize a payment, verify a wallet, prove settlement or recognize
revenue. Inputs are operator-supplied offline captures, not provider evidence.
Only catalog-wide, unqualified (audience=everyone) GET rules can yield MATCH;
other audiences remain UNKNOWN without an independent Cloudflare identity
receipt. No HTTP request is ever made by this module.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "szl.x402-challenge-readback/v1"
CAPTURE_SCHEMA = "szl.x402-public-challenge-capture/v1"
MAX_BYTES = 64 * 1024
MAX_CAPTURE_BYTES = 4 * 1024 * 1024
MAX_ROWS = 1000
HEX_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
DIGITS = re.compile(r"(?:0|[1-9][0-9]*)\Z")


class InvalidEvidence(ValueError):
    """Fixed-code diagnostic; untrusted input is not echoed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidEvidence("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _bad_constant(_):
    raise InvalidEvidence("NONFINITE_NUMBER")


def _json_bytes(raw: bytes, *, limit: int = MAX_BYTES):
    if not isinstance(raw, bytes) or len(raw) > limit:
        raise InvalidEvidence("INPUT_SIZE")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_bad_constant)
    except InvalidEvidence:
        raise
    except (UnicodeError, ValueError):
        raise InvalidEvidence("INVALID_JSON") from None


def _timestamp(value: str):
    if not isinstance(value, str) or not value:
        raise InvalidEvidence("TIME_INVALID")
    try:
        value = value[:-1] + "+00:00" if value.endswith("Z") else value
        result = datetime.fromisoformat(value)
    except ValueError:
        raise InvalidEvidence("TIME_INVALID") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvalidEvidence("TIME_INVALID")
    return result.astimezone(timezone.utc)


def _atomic(value):
    if isinstance(value, str) and DIGITS.fullmatch(value) and len(value) <= 24:
        return value
    raise InvalidEvidence("AMOUNT_INVALID")


def _address(value):
    if not isinstance(value, str) or not HEX_ADDRESS.fullmatch(value):
        raise InvalidEvidence("ADDRESS_INVALID")
    return value.lower()


def _decode_header(encoded: str):
    if not isinstance(encoded, str) or not encoded or len(encoded) > MAX_BYTES * 2:
        raise InvalidEvidence("HEADER_INVALID")
    if not encoded.isascii() or not re.fullmatch(r"[A-Za-z0-9+/_=-]+", encoded):
        raise InvalidEvidence("HEADER_ENCODING")
    try:
        normalized = encoded.replace("-", "+").replace("_", "/")
        raw = base64.b64decode(normalized + "=" * (-len(normalized) % 4), validate=True)
    except (ValueError, binascii.Error):
        raise InvalidEvidence("HEADER_ENCODING") from None
    return _json_bytes(raw)


def _request_target(url: str):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) <= 32 for c in url):
        raise InvalidEvidence("REQUEST_URL")
    try:
        value = urlsplit(url)
        port = value.port
    except ValueError:
        raise InvalidEvidence("REQUEST_URL") from None
    if (value.scheme != "https" or not value.hostname or port not in (None, 443)
            or value.username or value.password or value.fragment or value.path.startswith("//")):
        raise InvalidEvidence("REQUEST_URL")
    return value


def _match_catalog_rule(catalog: dict, target, method: str):
    matches = []
    rules = catalog.get("paid_surfaces")
    if not isinstance(rules, list):
        raise InvalidEvidence("CATALOG_INVALID")
    for entry in rules:
        if not isinstance(entry, dict):
            raise InvalidEvidence("CATALOG_INVALID")
        methods = entry.get("methods")
        if not isinstance(methods, list) or any(not isinstance(m, str) for m in methods):
            raise InvalidEvidence("CATALOG_INVALID")
        if method not in methods:
            continue
        host = entry.get("host")
        zone = entry.get("zone")
        if not isinstance(host, str) or not isinstance(zone, str) or not zone:
            raise InvalidEvidence("CATALOG_INVALID")
        if not (target.hostname == zone or target.hostname.endswith("." + zone)):
            continue
        if host != "*" and host != target.hostname:
            continue
        prefixes = entry.get("path_prefixes")
        if not isinstance(prefixes, list):
            raise InvalidEvidence("CATALOG_INVALID")
        if any(isinstance(prefix, str) and target.path.startswith(prefix)
               for prefix in prefixes):
            matches.append(entry)
    if len(matches) != 1:
        raise InvalidEvidence("RULE_UNMATCHED" if not matches else "RULE_AMBIGUOUS")
    return matches[0]


def inspect(capture: dict, catalog: dict):
    """Return a secret-free scope-limited result. Never inspect payment credentials."""
    if not isinstance(capture, dict) or set(capture) != {
        "schema", "url", "method", "status", "payment_required", "observed_at"
    } or capture["schema"] != CAPTURE_SCHEMA:
        raise InvalidEvidence("CAPTURE_SCHEMA")
    if capture["status"] != 402 or type(capture["status"]) is not int:
        raise InvalidEvidence("NOT_A_402")
    if capture["method"] != "GET":
        raise InvalidEvidence("METHOD_UNVERIFIED")
    target = _request_target(capture["url"])
    observed = _timestamp(capture["observed_at"])
    source_at = _timestamp(catalog.get("as_of"))
    if observed < source_at or observed - source_at > timedelta(days=7):
        raise InvalidEvidence("CATALOG_STALE_OR_FUTURE")
    rule = _match_catalog_rule(catalog, target, capture["method"])
    if not isinstance(rule.get("id"), str) or not rule["id"]:
        raise InvalidEvidence("CATALOG_INVALID")
    if rule.get("audience") != "everyone":
        raise InvalidEvidence("AUDIENCE_NEEDS_PROVIDER_PROOF")
    challenge = _decode_header(capture["payment_required"])
    if not isinstance(challenge, dict) or type(challenge.get("x402Version")) is not int or challenge["x402Version"] != 2:
        raise InvalidEvidence("VERSION_DRIFT")
    resource = challenge.get("resource")
    if not isinstance(resource, dict) or resource.get("url") != capture["url"]:
        raise InvalidEvidence("RESOURCE_DRIFT")
    accepts = challenge.get("accepts")
    if not isinstance(accepts, list) or len(accepts) != 1 or not isinstance(accepts[0], dict):
        raise InvalidEvidence("OFFERS_AMBIGUOUS")
    offer = accepts[0]
    payment = catalog.get("payment")
    if not isinstance(payment, dict):
        raise InvalidEvidence("CATALOG_INVALID")
    timeout = offer.get("maxTimeoutSeconds")
    expected_timeout = payment.get("max_timeout_seconds")
    if type(expected_timeout) is not int or not 1 <= expected_timeout <= 86400:
        raise InvalidEvidence("CATALOG_INVALID")
    if type(timeout) is not int or not 1 <= timeout <= 86400:
        raise InvalidEvidence("TIMEOUT_INVALID")
    if timeout != expected_timeout:
        raise InvalidEvidence("TIMEOUT_DRIFT")
    if not isinstance(offer.get("extra"), dict):
        raise InvalidEvidence("EXTRA_INVALID")
    if (offer.get("scheme") != rule.get("scheme") or
            offer.get("network") != payment.get("network")):
        raise InvalidEvidence("SCHEME_NETWORK_DRIFT")
    if _address(offer.get("asset")) != _address(payment.get("asset")):
        raise InvalidEvidence("ASSET_DRIFT")
    if _address(offer.get("payTo")) != _address(payment.get("pay_to")):
        raise InvalidEvidence("RECIPIENT_DRIFT")
    if _atomic(offer.get("amount")) != _atomic(rule.get("amount_atomic")):
        raise InvalidEvidence("PRICE_DRIFT")
    return {
        "status": "CHALLENGE_MATCH",
        "rule_id": rule["id"],
        "method": "GET",
        "hostname": target.hostname,
        "path": target.path,
        "amount_atomic": _atomic(rule["amount_atomic"]),
        "limitations": ["PUBLIC_402_ONLY", "AUTHORIZATION_NOT_OBSERVED",
                        "SETTLEMENT_NOT_VERIFIED", "REVENUE_NOT_ESTABLISHED"],
    }


def make_report(captures: list[dict], catalog: dict, *, input_sha256: str, catalog_sha256: str):
    if not isinstance(catalog, dict) or catalog.get("schema") != "szl.x402-pricing/v2":
        raise InvalidEvidence("CATALOG_INVALID")
    if not isinstance(captures, list) or len(captures) == 0 or len(captures) > MAX_ROWS:
        raise InvalidEvidence("CAPTURE_COUNT")
    results = []
    for index, capture in enumerate(captures):
        try:
            result = inspect(capture, catalog)
        except InvalidEvidence as err:
            result = {"status": "REFUSED", "reason": err.code}
        results.append({"index": index, **result})
    matched = sum(row["status"] == "CHALLENGE_MATCH" for row in results)
    return {
        "schema": SCHEMA, "scope": "OFFLINE_REQUEST_CHALLENGE_COMPARISON_ONLY",
        "input_sha256": input_sha256, "catalog_sha256": catalog_sha256,
        "catalog_as_of": catalog["as_of"],
        "matched_challenges": matched, "refused_captures": len(results) - matched,
        "result": "CHALLENGES_MATCH" if matched == len(results) else "FAIL_CLOSED",
        "settlement_state": "UNVERIFIED", "revenue_state": "NO_CLAIM",
        "records": results,
    }


def _atomic_write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".szl-x402-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        raw_capture = args.captures.read_bytes()
        raw_catalog = args.catalog.read_bytes()
        catalog = _json_bytes(raw_catalog)
        captures = _json_bytes(raw_capture, limit=MAX_CAPTURE_BYTES)
        report = make_report(captures, catalog,
                             input_sha256=hashlib.sha256(raw_capture).hexdigest(),
                             catalog_sha256=hashlib.sha256(raw_catalog).hexdigest())
        _atomic_write(args.output, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        print(f"{report['result']} {report['matched_challenges']}/{len(report['records'])} "
              "settlement=UNVERIFIED revenue=NO_CLAIM")
        return 0 if report["result"] == "CHALLENGES_MATCH" else 2
    except (InvalidEvidence, OSError) as exc:
        code = exc.code if isinstance(exc, InvalidEvidence) else "IO_UNAVAILABLE"
        print("FAIL_CLOSED " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
