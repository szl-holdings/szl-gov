"""Credential-free public x402 probe contract tests. No network or payments."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import x402_public_probe as probe

NOW = datetime(2026, 11, 17, 19, 37, tzinfo=timezone.utc)
URL = "https://inference.a-11-oy.com/v1/completions"
SECOND = "https://a-11-oy.com/v1/chat/completions"
PAYOUT = "0x7b133ef996852c223379d6d1245430300970291A"
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def catalog():
    return {
        "schema": "szl.x402-pricing/v2",
        "x402_version": 2,
        "as_of": "2026-11-13T22:49:00Z",
        "payment": {"network": "eip155:8453", "asset": ASSET, "pay_to": PAYOUT},
        "paid_surfaces": [
            {
                "id": "chat",
                "host": "*",
                "zone": "a-11-oy.com",
                "path_prefixes": ["/v1/chat/"],
                "methods": ["GET"],
                "scheme": "exact",
                "audience": "everyone",
                "amount_atomic": "20000",
            },
            {
                "id": "completions",
                "host": "inference.a-11-oy.com",
                "zone": "a-11-oy.com",
                "path_prefixes": ["/v1/completions"],
                "methods": ["GET"],
                "scheme": "exact",
                "audience": "everyone",
                "amount_atomic": "20000",
            },
        ],
    }


def encoded_header(url, amount="20000"):
    payload = {
        "x402Version": 2,
        "resource": {"url": url},
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "asset": ASSET,
                "payTo": PAYOUT,
                "amount": amount,
                "maxTimeoutSeconds": 3600,
                "extra": {},
            }
        ],
    }
    return base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()


class Response(io.BytesIO):
    def __init__(self, code, headers):
        super().__init__(b"")
        self.status = code
        self.headers = headers


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "timeout": timeout,
                "authorization": request.get_header("Authorization"),
                "payment": request.get_header("PAYMENT-SIGNATURE"),
            }
        )
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ProbeTests(unittest.TestCase):
    def test_two_realistic_matching_402_are_not_revenue(self):
        opener = FakeOpener(
            [
                urllib.error.HTTPError(
                    URL, 402, "pay", {"PAYMENT-REQUIRED": encoded_header(URL)}, None
                ),
                urllib.error.HTTPError(
                    SECOND,
                    402,
                    "pay",
                    {"PAYMENT-REQUIRED": encoded_header(SECOND)},
                    None,
                ),
            ]
        )
        result = probe.observe(catalog(), [URL, SECOND], opener=opener, now=NOW)
        self.assertEqual(result["result"], "CHALLENGES_MATCH")
        self.assertEqual(result["matched_count"], 2)
        self.assertFalse(result["revenue_verified"])
        self.assertFalse(result["settlement_verified"])
        self.assertFalse(result["post_billing_verified"])
        self.assertFalse(result["origin_jwt_verified"])
        self.assertTrue(all(r["status"] == "CHALLENGE_MATCH" for r in result["rows"]))
        self.assertTrue(
            all(
                c["method"] == "GET"
                and c["authorization"] is None
                and c["payment"] is None
                for c in opener.calls
            )
        )
        self.assertNotIn(encoded_header(URL), json.dumps(result))

    def test_wrong_amount_never_mints_a_match(self):
        o = FakeOpener(
            [
                urllib.error.HTTPError(
                    URL,
                    402,
                    "pay",
                    {"PAYMENT-REQUIRED": encoded_header(URL, amount="5")},
                    None,
                )
            ]
        )
        result = probe.observe(catalog(), [URL], opener=o, now=NOW)
        self.assertEqual(result["result"], "HOLD")
        self.assertEqual(result["rows"][0]["reason"], "PRICE_DRIFT")

    def test_missing_header_rejected(self):
        o = FakeOpener([urllib.error.HTTPError(URL, 402, "pay", {}, None)])
        result = probe.observe(catalog(), [URL], opener=o, now=NOW)
        self.assertEqual(result["rows"][0]["reason"], "PAYMENT_REQUIRED_HEADER_MISSING")

    def test_401_403_429_stops_remaining_provider_requests(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                o = FakeOpener(
                    [urllib.error.HTTPError(URL, status, "denied", {}, None)]
                )
                result = probe.observe(catalog(), [URL, SECOND], opener=o, now=NOW)
                self.assertEqual(len(o.calls), 1)
                self.assertTrue(result["provider_lane_stopped"])
                self.assertEqual(result["rows"][0]["reason"], f"HTTP_{status}_STOP")
                self.assertEqual(result["rows"][1]["reason"], "PROVIDER_LANE_STOPPED")

    def test_redirects_not_followed(self):
        self.assertIsNone(
            probe.NoRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://example.invalid"
            )
        )
        o = FakeOpener(
            [
                urllib.error.HTTPError(
                    URL, 302, "Found", {"Location": "https://example.invalid"}, None
                )
            ]
        )
        result = probe.observe(catalog(), [URL], opener=o, now=NOW)
        self.assertEqual(result["rows"][0]["reason"], "NOT_402")

    def test_public_200_never_counts_as_a_challenge(self):
        o = FakeOpener([Response(200, {})])
        result = probe.observe(catalog(), [URL], opener=o, now=NOW)
        self.assertEqual(result["matched_count"], 0)

    def test_stale_future_catalog_refused_before_network(self):
        o = FakeOpener([])
        for when in (NOW + timedelta(days=12), NOW - timedelta(days=5)):
            with self.subTest(when=when):
                with self.assertRaises(probe.InputHold):
                    probe.observe(catalog(), [URL], opener=o, now=when)
        self.assertEqual(o.calls, [])

    def test_no_unknown_url_query_or_duplicate_request_before_network(self):
        o = FakeOpener([])
        for urls in (
            [URL + "?api_key=oops"],
            ["https://example.org/v1/completions"],
            ["http://inference.a-11-oy.com/v1/completions"],
            [URL, URL],
            [],
        ):
            with self.subTest(urls=urls):
                with self.assertRaises(probe.InputHold):
                    probe.observe(catalog(), urls, opener=o, now=NOW)
        self.assertEqual(o.calls, [])

    def test_verified_bots_rule_needs_provider_evidence(self):
        c = catalog()
        c["paid_surfaces"][1]["audience"] = "verified_bots"
        o = FakeOpener([])
        with self.assertRaisesRegex(
            probe.InputHold, "AUDIENCE_NEEDS_PROVIDER_EVIDENCE"
        ):
            probe.observe(c, [URL], opener=o, now=NOW)
        self.assertFalse(o.calls)

    def test_unavailable_transport_is_not_a_success(self):
        o = FakeOpener([urllib.error.URLError("offline")])
        result = probe.observe(catalog(), [URL], opener=o, now=NOW)
        self.assertEqual(result["result"], "HOLD")
        self.assertEqual(result["rows"][0]["reason"], "TRANSPORT_URLError")

    def test_output_exclusive_and_not_claiming_payment(self):
        result = probe.observe(
            catalog(),
            [URL],
            opener=FakeOpener(
                [
                    urllib.error.HTTPError(
                        URL, 402, "pay", {"PAYMENT-REQUIRED": encoded_header(URL)}, None
                    )
                ]
            ),
            now=NOW,
        )
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "observation.json"
            digest = probe.write_exclusive(out, result)
            self.assertEqual(len(digest), 64)
            obj = json.loads(out.read_bytes())
            self.assertEqual(obj["result"], "CHALLENGES_MATCH")
            self.assertFalse(obj["revenue_verified"])
            with self.assertRaises(FileExistsError):
                probe.write_exclusive(out, result)


if __name__ == "__main__":
    unittest.main()
