"""Network-free contracts for public x402 surface observation."""
from __future__ import annotations

import base64
import json
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

# Match the repository's standalone pytest invocation on Linux runners.
TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import x402_challenge_receipt as witness  # noqa: E402
import x402_public_policy_watch as watch  # noqa: E402

CATALOG = json.loads((Path(__file__).resolve().parents[1] /
    "pricing/generated/x402-pricing.json").read_text(encoding="utf-8"))
CATALOG_BYTES = json.dumps(CATALOG, sort_keys=True).encode()
OBSERVED_AT = (witness._timestamp(CATALOG["as_of"]) + timedelta(days=1)).isoformat()


class Response:
    def __init__(self, url, status, headers=None, observed_url=None):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.observed_url = observed_url or url
        self.closed = False

    def geturl(self):
        return self.observed_url

    def close(self):
        self.closed = True


def challenge(url):
    rule = witness._match_catalog_rule(CATALOG, urlsplit(url), "GET")
    payment = CATALOG["payment"]
    value = {
        "x402Version": 2, "resource": {"url": url},
        "accepts": [{
            "scheme": rule["scheme"], "network": payment["network"],
            "asset": payment["asset"], "payTo": payment["pay_to"],
            "amount": rule["amount_atomic"], "extra": {},
            "maxTimeoutSeconds": payment["max_timeout_seconds"],
        }],
    }
    return base64.b64encode(json.dumps(value).encode()).decode()


def scenarios(changes=None):
    expected = {
        url: Response(url, 200) if scope == "free"
        else Response(url, 402, {"PAYMENT-REQUIRED": challenge(url)})
        for _, url, scope in watch.TARGETS
    }
    expected.update(changes or {})
    return expected


class OfflineTransport:
    def __init__(self, cases):
        self.cases = cases
        self.request_log = []

    def open(self, request, *, timeout):
        assert request.get_method() == "GET"
        assert request.data is None
        assert timeout <= 12
        assert request.full_url in self.cases
        assert "authorization" not in {x.lower() for x in request.headers}
        assert "cookie" not in {x.lower() for x in request.headers}
        assert "payment-signature" not in {x.lower() for x in request.headers}
        self.request_log.append(request.full_url)
        result = self.cases[request.full_url]
        if isinstance(result, Exception):
            raise result
        return result


def run(overrides=None, catalog=CATALOG_BYTES):
    transport = OfflineTransport(scenarios(overrides))
    report = watch.snapshot(opener=transport, catalog_bytes=catalog,
                            observed_at=OBSERVED_AT,
                            source_revision="a" * 40)
    return report, transport


def test_exact_four_surface_positive_has_no_revenue_or_payment_authority():
    report, transport = run()
    assert report["status"] == "POLICY_CHALLENGES_OBSERVED"
    assert len(report["requests"]) == len(watch.TARGETS) == 4
    assert all(item["state"] == "PASS" for item in report["requests"])
    assert report["authorization"] == "UNVERIFIED"
    assert report["settlement"] == "UNVERIFIED"
    assert report["revenue"] == "NO_CLAIM"
    assert report["wallet_used"] is False
    assert transport.request_log == [url for _, url, _ in watch.TARGETS]
    assert "PAYMENT-REQUIRED" not in json.dumps(report)


def test_a_public_proof_paywall_is_not_accepted():
    url = watch.TARGETS[1][1]
    result, _ = run({url: Response(url, 402, {"PAYMENT-REQUIRED": challenge(watch.TARGETS[2][1])})})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][1]["reason"] == "FREE_ROUTE_UNAVAILABLE_OR_PAYWALLED"


def test_paid_route_silent_200_is_a_failure_not_revenue():
    url = watch.TARGETS[2][1]
    result, _ = run({url: Response(url, 200)})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][2]["reason"] == "PAID_CHALLENGE_UNAVAILABLE"


def test_paid_price_mismatch_is_blocked():
    url = watch.TARGETS[2][1]
    encoded = challenge(url)
    blob = json.loads(base64.b64decode(encoded))
    blob["accepts"][0]["amount"] = str(int(blob["accepts"][0]["amount"]) + 1)
    wrong = base64.b64encode(json.dumps(blob).encode()).decode()
    result, _ = run({url: Response(url, 402, {"PAYMENT-REQUIRED": wrong})})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][2]["reason"] == "PRICE_DRIFT"


def test_invalid_base64_is_sanitized():
    url = watch.TARGETS[2][1]
    result, _ = run({url: Response(url, 402, {"PAYMENT-REQUIRED": "SECRET_CANARY!"})})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][2]["reason"] == "HEADER_ENCODING"
    assert "SECRET_CANARY" not in json.dumps(result)


def test_no_redirect_or_credential_influence():
    url = watch.TARGETS[3][1]
    result, _ = run({url: Response(url, 302, {"Location": "https://evil.invalid/path"},
                                   observed_url="https://evil.invalid/path")})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][3]["reason"] == "REDIRECT_OR_TARGET_DRIFT"
    assert "evil.invalid" not in json.dumps(result)


def test_transport_failure_cannot_be_green():
    url = watch.TARGETS[2][1]
    result, _ = run({url: OSError("DO_NOT_LOG_SECRET")})
    assert result["requests"][2]["reason"] == "TRANSPORT_UNAVAILABLE"
    assert "DO_NOT_LOG_SECRET" not in json.dumps(result)


def test_stale_catalog_fails_closed_without_paid_claim():
    old = dict(CATALOG)
    old["as_of"] = "2025-01-01T00:00:00Z"
    result, _ = run(catalog=json.dumps(old).encode())
    assert result["status"] == "FAIL_CLOSED"
    assert all(row["state"] == "BLOCKED" for row in result["requests"] if row["expected"] == "paid")
    assert result["settlement"] == "UNVERIFIED"


def test_edge_challenge_does_not_count_as_free_public():
    url = watch.TARGETS[0][1]
    result, _ = run({url: Response(url, 200, {"cf-mitigated": "challenge"})})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][0]["reason"] == "EDGE_CHALLENGE_UNAVAILABLE"


def test_no_host_or_url_inputs_and_fixed_targets():
    assert set(watch.TARGETS) == {
        ("product", "https://a-11-oy.com/", "free"),
        ("proof", "https://a11oy.net/", "free"),
        ("inference", "https://inference.a-11-oy.com/v1/completions", "paid"),
        ("chat", "https://a-11-oy.com/v1/chat/", "paid"),
    }
