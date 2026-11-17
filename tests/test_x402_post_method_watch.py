"""Offline regression tests for the opt-in unsigned POST challenge witness."""
from __future__ import annotations

import base64
import json
import sys
from datetime import timedelta
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import x402_post_method_watch as watch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "pricing/generated/x402-pricing.json").read_text(encoding="utf-8"))
OBSERVED = (watch.witness._timestamp(CATALOG["as_of"]) + timedelta(days=1)).isoformat()


class Response:
    def __init__(self, url, status, headers=None, observed_url=None):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.observed_url = observed_url or url
        self.closed = False

    def geturl(self):
        return self.observed_url

    def read(self, *args, **kwargs):
        raise AssertionError("Production response bodies must never be consumed")

    def close(self):
        self.closed = True


def encoded_challenge(url, *, amount_delta=0, version=2):
    target = watch.witness._request_target(url)
    rule = watch.witness._match_catalog_rule(CATALOG, target, "GET")
    payment = CATALOG["payment"]
    value = {
        "x402Version": version, "resource": {"url": url},
        "accepts": [{
            "scheme": rule["scheme"], "network": payment["network"],
            "asset": payment["asset"], "payTo": payment["pay_to"],
            "amount": str(int(rule["amount_atomic"]) + amount_delta),
            "maxTimeoutSeconds": payment["max_timeout_seconds"],
            "extra": {},
        }],
    }
    return base64.b64encode(json.dumps(value).encode()).decode()


class OfflineTransport:
    def __init__(self, cases):
        self.cases = cases
        self.requests = []

    def open(self, request, *, timeout):
        assert timeout <= 12
        assert request.get_method() == "POST"
        assert request.data == watch.INVALID_BODY
        assert b"model" not in request.data and b"prompt" not in request.data
        assert request.full_url in [url for _, url in watch.TARGETS]
        assert not {
            "authorization", "cookie", "payment-signature", "x-payment",
            "payment-context", "x-payment-verified",
        }.intersection({key.lower() for key in request.headers})
        self.requests.append(request.full_url)
        return self.cases[request.full_url]


def snapshot(changes=None, catalog=CATALOG, when=OBSERVED):
    cases = {
        url: Response(url, 402, {"PAYMENT-REQUIRED": encoded_challenge(url)})
        for _, url in watch.TARGETS
    }
    cases.update(changes or {})
    transport = OfflineTransport(cases)
    report = watch.snapshot(
        opener=transport,
        catalog_bytes=json.dumps(catalog).encode(),
        observed_at=when,
        source_revision="a" * 40,
    )
    return report, transport


def test_two_exact_post_routes_match_reference_catalog_without_revenue_claims():
    result, transport = snapshot()
    assert result["status"] == "POST_CHALLENGES_OBSERVED"
    assert result["catalog_reference_method"] == "GET"
    assert len(result["requests"]) == len(transport.requests) == 2
    assert all(r["state"] == "PASS" and r["http_status"] == 402 for r in result["requests"])
    assert result["settlement"] == result["authorization"] == "UNVERIFIED"
    assert result["origin_fulfillment"] == "UNVERIFIED"
    assert result["revenue"] == "NO_CLAIM" and result["wallet_used"] is False
    assert "PAYMENT-REQUIRED" not in json.dumps(result)


def test_wrong_amount_refuses_post_even_when_status_is_402():
    url = watch.TARGETS[1][1]
    result, _ = snapshot({url: Response(url, 402, {
        "PAYMENT-REQUIRED": encoded_challenge(url, amount_delta=1)
    })})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][1]["reason"] == "PRICE_DRIFT"


def test_unpaid_post_reaching_origin_does_not_count_as_paid():
    url = watch.TARGETS[0][1]
    result, _ = snapshot({url: Response(url, 422)})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][0]["reason"] == "POST_PAYMENT_CHALLENGE_UNAVAILABLE"


def test_bad_base64_never_echoes_private_bytes():
    url = watch.TARGETS[0][1]
    result, _ = snapshot({url: Response(url, 402, {"PAYMENT-REQUIRED": "PRIVATE_TOKEN!"})})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][0]["reason"] == "CHALLENGE_INVALID"
    assert "PRIVATE_TOKEN" not in json.dumps(result)


def test_v1_header_refuses_without_exposing_payload():
    url = watch.TARGETS[0][1]
    result, _ = snapshot({url: Response(url, 402, {
        "PAYMENT-REQUIRED": encoded_challenge(url, version=1)
    })})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][0]["reason"] == "VERSION_DRIFT"


def test_redirect_is_never_followed():
    url = watch.TARGETS[1][1]
    result, _ = snapshot({url: Response(url, 302, observed_url="https://untrusted.invalid/")})
    assert result["status"] == "FAIL_CLOSED"
    assert result["requests"][1]["reason"] == "REDIRECT_OR_TARGET_DRIFT"
    assert "untrusted.invalid" not in json.dumps(result)


def test_catalog_expiration_fails_closed():
    too_old = (watch.witness._timestamp(CATALOG["as_of"]) + timedelta(days=8)).isoformat()
    result, _ = snapshot(when=too_old)
    assert result["status"] == "FAIL_CLOSED"
    assert all(row["reason"] == "CATALOG_STALE_OR_FUTURE" for row in result["requests"])


def test_cli_is_inert_without_explicit_execute(tmp_path, capsys):
    assert watch.main(["--output", str(tmp_path / "not-written.json")]) == 2
    assert not (tmp_path / "not-written.json").exists()
    assert "EXPLICIT_EXECUTE_REQUIRED" in capsys.readouterr().err


def test_exact_fixed_urls_and_no_generic_or_wallet_routes():
    assert watch.TARGETS == (
        ("chat", "https://a-11-oy.com/v1/chat/completions"),
        ("inference", "https://inference.a-11-oy.com/v1/completions"),
    )
