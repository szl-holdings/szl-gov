"""Offline negative controls for x402 catalog challenge matching (no external calls)."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import x402_challenge_receipt as mod

URL = "https://inference.a-11-oy.com/v1/completions"
PAY_TO = "0x7b133ef996852c223379d6d1245430300970291A"
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def catalog():
    return {"schema": "szl.x402-pricing/v2", "as_of": "2026-11-13T22:49:00Z",
            "payment": {"network": "eip155:8453", "asset": ASSET, "pay_to": PAY_TO},
            "paid_surfaces": [{"id": "completions", "host": "inference.a-11-oy.com",
                               "zone": "a-11-oy.com", "path_prefixes": ["/v1/completions"],
                               "methods": ["GET"], "scheme": "exact", "audience": "everyone",
                               "amount_atomic": "20000"}]}


def challenge():
    return {"x402Version": 2, "resource": {"url": URL}, "accepts": [{
        "scheme": "exact", "network": "eip155:8453", "asset": ASSET,
        "payTo": PAY_TO, "amount": "20000", "maxTimeoutSeconds": 3600, "extra": {}}]}


def capture(payload=None):
    header = base64.b64encode(json.dumps(
        payload or challenge(), separators=(",", ":")).encode()).decode()
    return {"schema": mod.CAPTURE_SCHEMA, "url": URL, "method": "GET",
            "status": 402, "payment_required": header,
            "observed_at": "2026-11-17T04:30:00Z"}


def check(value, cat=None):
    raw = json.dumps(value, sort_keys=True).encode()
    return mod.make_report([value], cat or catalog(),
                           input_sha256=hashlib.sha256(raw).hexdigest(),
                           catalog_sha256="0" * 64)


def test_valid_challenge_proves_header_compliance_only():
    report = check(capture())
    assert report["result"] == "CHALLENGES_MATCH"
    assert report["matched_challenges"] == 1
    assert report["settlement_state"] == "UNVERIFIED"
    assert report["revenue_state"] == "NO_CLAIM"
    assert report["records"][0]["amount_atomic"] == "20000"
    assert "payment_required" not in json.dumps(report)


def test_forged_settlement_header_never_establishes_revenue():
    row = capture()
    row["payment_response"] = base64.b64encode(b'{"success":true}').decode()
    report = check(row)
    assert report["result"] == "FAIL_CLOSED"
    assert report["records"][0]["reason"] == "CAPTURE_SCHEMA"
    assert report["revenue_state"] == "NO_CLAIM"


def test_malformed_base64_and_duplicate_keys_refused():
    row = capture()
    row["payment_required"] = "not base64!"
    assert check(row)["records"][0]["reason"] == "HEADER_ENCODING"
    row["payment_required"] = base64.b64encode(
        b'{"x402Version":2,"x402Version":2}').decode()
    assert check(row)["records"][0]["reason"] == "DUPLICATE_JSON_KEY"


def test_nonfinite_and_noninteger_version_refused():
    for version in (True, "2", 3):
        item = challenge()
        item["x402Version"] = version
        assert check(capture(item))["records"][0]["reason"] == "VERSION_DRIFT"
    row = capture()
    row["payment_required"] = base64.b64encode(
        b'{"x402Version":NaN}').decode()
    assert check(row)["records"][0]["reason"] == "NONFINITE_NUMBER"


def test_wallet_asset_amount_network_scheme_and_resource_drifts():
    for key, replacement, expected in [
        ("payTo", "0x" + "1" * 40, "RECIPIENT_DRIFT"),
        ("asset", "0x" + "2" * 40, "ASSET_DRIFT"),
        ("amount", "20001", "PRICE_DRIFT"),
        ("network", "eip155:1", "SCHEME_NETWORK_DRIFT"),
        ("scheme", "upto", "SCHEME_NETWORK_DRIFT"),
    ]:
        item = challenge()
        item["accepts"][0][key] = replacement
        assert check(capture(item))["records"][0]["reason"] == expected
    item = challenge()
    item["resource"]["url"] = "https://inference.a-11-oy.com/other"
    assert check(capture(item))["records"][0]["reason"] == "RESOURCE_DRIFT"


def test_ambiguous_offers_and_invalid_atomic_types_refused():
    item = challenge()
    item["accepts"].append(copy.deepcopy(item["accepts"][0]))
    assert check(capture(item))["records"][0]["reason"] == "OFFERS_AMBIGUOUS"
    for invalid in (-1, True, 20000, 2e4, "020000", "2.0"):
        item = challenge()
        item["accepts"][0]["amount"] = invalid
        assert check(capture(item))["records"][0]["reason"] == "AMOUNT_INVALID"


def test_post_and_unmatched_route_do_not_prove_paid_behavior():
    row = capture()
    row["method"] = "POST"
    assert check(row)["records"][0]["reason"] == "METHOD_UNVERIFIED"
    row = capture()
    row["url"] = "https://a-11-oy.com/"
    assert check(row)["records"][0]["reason"] == "RULE_UNMATCHED"


def test_verified_bot_needs_independent_provider_proof():
    rules = catalog()
    rules["paid_surfaces"][0]["audience"] = "verified_bots"
    assert check(capture(), rules)["records"][0]["reason"] == "AUDIENCE_NEEDS_PROVIDER_PROOF"


def test_stale_and_future_catalog_are_not_current_evidence():
    rules = catalog()
    rules["as_of"] = "2026-10-15T00:00:00Z"
    assert check(capture(), rules)["records"][0]["reason"] == "CATALOG_STALE_OR_FUTURE"
    rules = catalog()
    rules["as_of"] = "2026-11-18T00:00:00Z"
    assert check(capture(), rules)["records"][0]["reason"] == "CATALOG_STALE_OR_FUTURE"


def test_duplicate_routes_fail_instead_of_guessing_priority():
    rules = catalog()
    rules["paid_surfaces"].append(copy.deepcopy(rules["paid_surfaces"][0]))
    assert check(capture(), rules)["records"][0]["reason"] == "RULE_AMBIGUOUS"


def test_sensitive_query_is_not_reflected_in_report():
    row = capture()
    row["url"] = URL + "?api_key=SECRET_CANARY"
    assert "SECRET_CANARY" not in json.dumps(check(row))


def test_input_byte_bound():
    import pytest
    with pytest.raises(mod.InvalidEvidence):
        mod._json_bytes(b"x" * (mod.MAX_BYTES + 1))


def test_cli_redacts_and_failure_returns_nonzero(tmp_path):
    captures = tmp_path / "captures.json"
    rules = tmp_path / "catalog.json"
    output = tmp_path / "report.json"
    captures.write_text(json.dumps([capture()]), encoding="utf-8")
    rules.write_text(json.dumps(catalog()), encoding="utf-8")
    assert mod.main(["--captures", str(captures), "--catalog", str(rules),
                     "--output", str(output)]) == 0
    assert json.loads(output.read_text())["revenue_state"] == "NO_CLAIM"
    captures.write_text(json.dumps([{"foo": "SECRET_CANARY"}]), encoding="utf-8")
    assert mod.main(["--captures", str(captures), "--catalog", str(rules),
                     "--output", str(output)]) == 2
    assert "SECRET_CANARY" not in output.read_text()


def test_required_timeout_and_extra():
    for value in (None, -1, 0, True, "3600", 86401):
        item = challenge()
        item["accepts"][0]["maxTimeoutSeconds"] = value
        assert check(capture(item))["records"][0]["reason"] == "TIMEOUT_INVALID"
    item = challenge()
    item["accepts"][0].pop("extra")
    assert check(capture(item))["records"][0]["reason"] == "EXTRA_INVALID"


def test_zone_wildcard_does_not_match_foreign_host():
    rules = catalog()
    rules["paid_surfaces"][0]["host"] = "*"
    row = capture()
    row["url"] = "https://evil.example.invalid/v1/completions"
    assert check(row, rules)["records"][0]["reason"] == "RULE_UNMATCHED"
