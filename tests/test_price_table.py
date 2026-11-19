"""The draft per-1M price table is the source for catalog prices, and the generator stays inside it.

Schema validation refuses anything but the unapproved draft. Drift fails when
catalog.yaml disagrees on pay-to or a charged amount. The generator's gateway
file keeps the exact $0.02 floor and marks scheme upto not-yet-applied. Stripe
output is lookup keys only.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pricing_catalog as pc
import price_table as pt

PAY_TO = "0x7b133ef996852c223379d6d1245430300970291A"
LOOKUP_KEYS = (
    "draft_szl_inference_lite_input_uncached_per_1m",
    "draft_szl_inference_lite_input_cached_per_1m",
    "draft_szl_inference_lite_output_per_1m",
    "draft_szl_inference_standard_input_uncached_per_1m",
    "draft_szl_inference_standard_input_cached_per_1m",
    "draft_szl_inference_standard_output_per_1m",
    "draft_szl_inference_lite_offpeak_input_uncached_per_1m",
    "draft_szl_inference_lite_offpeak_input_cached_per_1m",
    "draft_szl_inference_lite_offpeak_output_per_1m",
    "draft_szl_inference_standard_offpeak_input_uncached_per_1m",
    "draft_szl_inference_standard_offpeak_input_cached_per_1m",
    "draft_szl_inference_standard_offpeak_output_per_1m",
    "draft_szl_inference_credit_pack_usd_10",
    "draft_szl_inference_credit_pack_usd_50",
    "draft_szl_inference_credit_pack_usd_200",
)


@pytest.fixture()
def table():
    return pt.load_table()


@pytest.fixture()
def catalog():
    return pc.load_catalog()


def _scaled(text):
    whole, dot, frac = text.partition(".")
    if not dot:
        return int(whole), 1
    return int(whole + frac), 10 ** len(frac)


def _tier(rules, tier_id):
    return next(tier for tier in rules["upto"]["tiers"] if tier["id"] == tier_id)


def _example(rules, name):
    return next(item for item in rules["examples"] if item["name"] == name)


# --- schema -----------------------------------------------------------------


def test_committed_table_is_canonical_and_draft():
    text = pt.TABLE.read_text(encoding="utf-8")
    assert text.startswith("# DRAFT")
    assert "not approved" in text
    assert "0.30" in text and "3.00" in text and "0.002" in text and "0.02" in text
    assert pc.format_catalog(text) == text
    table = pt.load_table()
    assert table["schema"] == pt.SCHEMA
    assert table["status"] == "DRAFT"
    assert table["approval"] == "not-approved"
    assert table["published"] is False
    assert table["deployed"] is False
    assert table["values_approved"] is False


def test_draft_card_numbers(table):
    lite, standard = table["tiers"]
    assert lite["id"] == "lite"
    assert lite["provisional"] is False
    assert lite["context_tokens"] == 8192
    assert (lite["input_uncached_atomic_per_million"], lite["input_cached_atomic_per_million"],
            lite["output_atomic_per_million"]) == (300_000, 30_000, 3_000_000)
    assert standard["id"] == "standard"
    assert standard["provisional"] is True
    assert standard["context_tokens"] is None
    assert (standard["input_uncached_atomic_per_million"], standard["input_cached_atomic_per_million"],
            standard["output_atomic_per_million"]) == (600_000, 60_000, 6_000_000)
    assert table["minimum_per_call"] == {
        "applied": False, "amount_atomic": 2000,
        "note": table["minimum_per_call"]["note"],
    }
    assert table["floor"]["applied"] is True
    assert table["floor"]["write"] is False
    assert table["floor"]["scheme"] == "exact"
    assert table["floor"]["amount_atomic"] == 20000
    assert table["floor"]["catalog_entry_ids"] == ["chat", "inference-completions-responses"]
    assert table["upto"]["applied"] is False
    assert table["upto"]["disposition"] == "not-yet-applied"
    assert table["upto"]["gateway_support"] == "UNKNOWN"
    assert table["off_peak_policy"]["numerator"] == 60
    assert table["off_peak_policy"]["denominator"] == 100
    assert table["off_peak_policy"]["applied"] is False
    assert table["cached_input_ratio"]["numerator"] == 1
    assert table["cached_input_ratio"]["denominator"] == 10
    assert [pack["amount_atomic"] for pack in table["credit_packs"]] == [10_000_000, 50_000_000, 200_000_000]
    assert table["payment"]["pay_to"] == PAY_TO
    assert table["payment"]["network"] == "eip155:8453"
    assert table["reference_call"]["input_uncached_tokens"] == 2000
    assert table["reference_call"]["input_cached_tokens"] == 2000
    assert table["reference_call"]["output_tokens"] == 500
    assert "http.request" not in pt.TABLE.read_text(encoding="utf-8")


def test_usd_display_of_the_card_rates():
    assert pc.usd(300_000, 1_000_000) == "0.30"
    assert pc.usd(30_000, 1_000_000) == "0.03"
    assert pc.usd(3_000_000, 1_000_000) == "3.00"
    assert pc.usd(600_000, 1_000_000) == "0.60"
    assert pc.usd(60_000, 1_000_000) == "0.06"
    assert pc.usd(6_000_000, 1_000_000) == "6.00"
    assert pc.usd(2000, 1_000_000) == "0.002"
    assert pc.usd(20000, 1_000_000) == "0.02"
    assert pc.usd(2160, 1_000_000) == "0.00216"
    assert pc.usd(4320, 1_000_000) == "0.00432"


@pytest.mark.parametrize("mutate, message", [
    (lambda table: table.__setitem__("published", True), "cannot be published"),
    (lambda table: table.__setitem__("status", "approved"), "DRAFT"),
    (lambda table: table.__setitem__("approval", "approved"), "not-approved"),
    (lambda table: table.__setitem__("values_approved", True), "cannot be published"),
    (lambda table: table.__setitem__("extra", "nope"), "fields differ"),
    (lambda table: table["upto"].__setitem__("applied", True), "not-yet-applied"),
    (lambda table: table["floor"].__setitem__("scheme", "upto"), "exact"),
    (lambda table: table["floor"].__setitem__("applied", False), "must stay applied"),
    (lambda table: table["floor"].__setitem__("write", True), "not a Cloudflare write"),
    (lambda table: table["minimum_per_call"].__setitem__("applied", True), "not what the gateway charges"),
    (lambda table: table["minimum_per_call"].__setitem__("amount_atomic", 30000), "must not exceed"),
    (lambda table: table["off_peak_policy"].__setitem__("applied", True), "must stay not applied"),
    (lambda table: table["off_peak_policy"].__setitem__("status", "live"), "not-justified"),
    (lambda table: table["gateway_bounds"].__setitem__("min_atomic", 2), "gateway bounds"),
    (lambda table: table["payment"].__setitem__("pay_to", "0x123"), "pay_to"),
    (lambda table: table["tiers"][0].__setitem__("input_cached_atomic_per_million", 40000), "cached rate"),
    (lambda table: table["tiers"][0].__setitem__("context_tokens", 0), "context_tokens"),
    (lambda table: table["tiers"][0].__setitem__("offer", "live"), "not-published"),
    (lambda table: table["tiers"].append(copy.deepcopy(table["tiers"][0])), "duplicate tier"),
    (lambda table: table["tiers"][1].__delitem__("provisional_reason"), "provisional_reason"),
    (lambda table: table["credit_packs"][0].__setitem__("amount_atomic", 10_000_001), "whole-dollar"),
    (lambda table: table["catalog_prices"][0].__setitem__("amount_atomic", 21000), "floor row must match"),
    (lambda table: table["catalog_prices"][2].__setitem__("amount_atomic", 20000), "other-per-call"),
    (lambda table: table.__setitem__("tiers", []), "tiers"),
])
def test_schema_rejects(table, mutate, message):
    mutate(table)
    with pytest.raises(pt.PriceTableError, match=message):
        pt.validate_table(table)


def test_schema_rejects_a_secret_shaped_key(table):
    table["stripe_secret_key"] = "sk_" + "test_" + "example"
    with pytest.raises(pt.PriceTableError, match="secret-shaped"):
        pt.validate_table(table)


def test_schema_rejects_a_secret_shaped_value(table):
    table["floor"]["note"] = "whsec_" + "example"
    with pytest.raises(pt.PriceTableError, match="secret-shaped"):
        pt.validate_table(table)


def test_non_canonical_yaml_is_refused(tmp_path):
    path = tmp_path / "table.yaml"
    path.write_text(pt.TABLE.read_text(encoding="utf-8").replace("status: DRAFT", "status:  DRAFT", 1),
                    encoding="utf-8")
    with pytest.raises(pc.CatalogError, match="canonical"):
        pt.load_table(path)


# --- drift: catalog versus the table ----------------------------------------


def test_committed_catalog_matches_the_table(table, catalog):
    assert pt.drift(table, catalog) == []


def test_pay_to_drift(table, catalog):
    catalog["payment"]["pay_to"] = "0x" + "11" * 20
    assert "payment.pay_to" in "\n".join(pt.drift(table, catalog))


def test_network_drift(table, catalog):
    catalog["payment"]["network"] = "eip155:1"
    assert "payment.network" in "\n".join(pt.drift(table, catalog))


def test_floor_amount_drift(table, catalog):
    catalog["charged"][0]["amount_atomic"] = 21000
    text = "\n".join(pt.drift(table, catalog))
    assert "charged chat amount_atomic: catalog 21000 != price table 20000" in text


def test_other_per_call_amount_drift(table, catalog):
    catalog["charged"][2]["amount_atomic"] = 51000
    text = "\n".join(pt.drift(table, catalog))
    assert "a11oy-mesh-frontier amount_atomic: catalog 51000 != price table 50000" in text


def test_added_charged_id_drifts(table, catalog):
    extra = copy.deepcopy(catalog["charged"][0])
    extra["id"] = "extra-surface"
    catalog["charged"].append(extra)
    assert "charged ids" in "\n".join(pt.drift(table, catalog))


def test_scheme_drift_names_upto(table, catalog):
    catalog["charged"][0]["scheme"] = "upto"
    text = "\n".join(pt.drift(table, catalog))
    assert "scheme: catalog 'upto'" in text
    assert "has not applied it" in text


# --- arithmetic --------------------------------------------------------------


def test_component_atomic_ceils_and_rejects_negatives():
    assert pt.component_atomic(1, 300_000) == 1
    assert pt.component_atomic(2000, 300_000) == 600
    assert pt.component_atomic(0, 300_000) == 0
    assert pt.component_atomic(8192, 3_000_000) == 24576
    assert pt.component_atomic(8192, 1_800_000) == 14746
    with pytest.raises(pt.PriceTableError):
        pt.component_atomic(-1, 300_000)


def test_off_peak_is_sixty_percent_of_peak(table):
    policy = table["off_peak_policy"]
    assert [pt.off_peak_atomic(rate, policy) for rate in (300_000, 30_000, 3_000_000)] == [180_000, 18_000, 1_800_000]
    assert [pt.off_peak_atomic(rate, policy) for rate in (600_000, 60_000, 6_000_000)] == [360_000, 36_000, 3_600_000]
    assert pc.usd(180_000, 1_000_000) == "0.18"
    assert pc.usd(18_000, 1_000_000) == "0.018"
    assert pc.usd(1_800_000, 1_000_000) == "1.80"
    assert pc.usd(360_000, 1_000_000) == "0.36"
    assert pc.usd(36_000, 1_000_000) == "0.036"
    assert pc.usd(3_600_000, 1_000_000) == "3.60"


def test_cent_strings_reconstruct_the_atomic_rate():
    rates = (300_000, 30_000, 3_000_000, 600_000, 60_000, 6_000_000,
             180_000, 18_000, 1_800_000, 360_000, 36_000, 3_600_000)
    for rate in rates:
        per_million, per_token = pt.atomic_to_cents_decimal(rate), pt.cents_per_token_decimal(rate)
        million_n, million_d = _scaled(per_million)
        token_n, token_d = _scaled(per_token)
        assert token_n * 1_000_000 * million_d == million_n * token_d
        assert million_n * 10_000 == rate * million_d
    assert pt.atomic_to_cents_decimal(18_000) == "1.8"
    assert pt.cents_per_token_decimal(300_000) == "0.00003"
    assert pt.cents_per_token_decimal(18_000) == "0.0000018"


def test_cap_outside_the_gateway_range_is_not_a_price(table):
    table["tiers"][0]["context_tokens"] = 100_000_000
    quote = pt.authorization_quote(table["tiers"][0], table, off_peak=False)
    assert quote["generated"] is False
    assert quote["price"] is None
    assert "outside the gateway range" in quote["reason"]


# --- generator ---------------------------------------------------------------


def test_gateway_rules_keep_the_floor_and_hold_upto(table, catalog):
    rules = pt.build_gateway_rules(table, catalog, pt.table_digest(), pc.catalog_digest())
    assert rules["schema"] == pt.GATEWAY_SCHEMA
    assert rules["status"] == "DRAFT"
    assert rules["write_to_cloudflare"] is False
    assert rules["values_approved"] is False
    assert rules["floor"]["applied"] is True
    assert rules["floor"]["write"] is False
    assert rules["floor"]["scheme"] == "exact"
    assert rules["floor"]["price"] == "20000"
    assert rules["floor"]["price_usd"] == "0.02"
    assert [rule["catalog_id"] for rule in rules["floor"]["rules"]] == ["chat", "inference-completions-responses"]
    for rule in rules["floor"]["rules"]:
        entry = next(item for item in catalog["charged"] if item["id"] == rule["catalog_id"])
        assert rule["expression"] == entry["expression"]
        assert rule["rule_id"] == entry["rule_id"]
        assert rule["price"] == "20000"
        assert rule["scheme"] == "exact"
        assert rule["address"] == PAY_TO
        assert rule["write"] is False
        assert rule["disposition"] == "keep-live"
    other = rules["other_exact_rules"]["rules"]
    assert [(rule["catalog_id"], rule["price"]) for rule in other] == [
        ("a11oy-mesh-frontier", "50000"), ("a11oy-attest-ledger", "25000")]
    assert rules["upto"]["applied"] is False
    assert rules["upto"]["disposition"] == "not-yet-applied"
    assert rules["upto"]["gateway_support"] == "UNKNOWN"
    assert rules["upto"]["replaces_floor_rules"] is False
    assert rules["upto"]["floor_catalog_ids"] == ["chat", "inference-completions-responses"]
    lite, standard = _tier(rules, "lite"), _tier(rules, "standard")
    assert lite["authorization"]["generated"] is True
    assert lite["authorization"]["price"] == "24576"
    assert lite["authorization"]["price_usd"] == "0.024576"
    assert lite["authorization"]["applied"] is False
    assert lite["authorization"]["price_atomic"] > lite["authorization"]["live_floor_atomic"]
    assert lite["off_peak"]["applied"] is False
    assert lite["off_peak"]["status"] == "not-justified"
    assert lite["off_peak"]["rates"]["usd_per_million"] == {
        "input_uncached": "0.18", "input_cached": "0.018", "output": "1.80"}
    assert lite["off_peak"]["authorization"]["price_atomic"] == 14746
    assert "below the live exact floor" in lite["off_peak"]["authorization"]["reason"]
    assert standard["provisional"] is True
    assert "measured trial" in standard["provisional_reason"]
    assert standard["authorization"]["generated"] is False
    assert standard["authorization"]["price"] is None
    assert "UNKNOWN" in standard["authorization"]["reason"]
    assert standard["off_peak"]["rates"]["usd_per_million"] == {
        "input_uncached": "0.36", "input_cached": "0.036", "output": "3.60"}


def test_examples_match_the_card_reference_call(table, catalog):
    rules = pt.build_gateway_rules(table, catalog, "a" * 64, "b" * 64)
    reference = _example(rules, "reference-call")
    by_tier = {row["tier"]: row for row in reference["tiers"]}
    assert reference["applied"] is False
    assert reference["live_floor_applied"] is True
    assert reference["live_floor_exact_atomic"] == 20000
    assert reference["upto_applied"] is False
    assert by_tier["lite"]["metered_atomic"] == 2160
    assert by_tier["lite"]["metered_usd"] == "0.00216"
    assert by_tier["lite"]["card_settlement_atomic"] == 2160
    assert by_tier["standard"]["metered_atomic"] == 4320
    assert by_tier["standard"]["metered_usd"] == "0.00432"
    one = {row["tier"]: row for row in _example(rules, "one-output-token")["tiers"]}
    assert one["lite"]["metered_atomic"] == 3
    assert one["lite"]["card_settlement_atomic"] == 2000
    assert one["standard"]["metered_atomic"] == 6
    assert one["standard"]["card_settlement_atomic"] == 2000
    off = _example(rules, "reference-call-off-peak")
    off_tiers = {row["tier"]: row for row in off["tiers"]}
    assert off["applied"] is False
    assert off_tiers["lite"]["metered_atomic"] == 1296
    assert off_tiers["lite"]["card_settlement_atomic"] == 2000
    assert off_tiers["standard"]["metered_atomic"] == 2592
    assert off_tiers["standard"]["card_settlement_atomic"] == 2592


def test_generator_refuses_a_drifting_catalog(table, catalog):
    catalog["charged"][0]["amount_atomic"] = 21000
    with pytest.raises(pt.PriceTableError, match="drifted"):
        pt.build_gateway_rules(table, catalog, "a" * 64, "b" * 64)


def test_changed_table_price_is_what_the_generator_emits(table, catalog):
    for row in table["catalog_prices"]:
        if row["id"] == "a11oy-mesh-frontier":
            row["amount_atomic"] = 51000
    for entry in catalog["charged"]:
        if entry["id"] == "a11oy-mesh-frontier":
            entry["amount_atomic"] = 51000
    rules = pt.build_gateway_rules(table, catalog, "a" * 64, "b" * 64)
    mesh = next(rule for rule in rules["other_exact_rules"]["rules"] if rule["catalog_id"] == "a11oy-mesh-frontier")
    assert mesh["price"] == "51000"
    assert pt.drift(table, catalog) == []


def test_stripe_lookup_keys_are_draft_and_keyless(table):
    stripe = pt.build_stripe_lookup_keys(table, pt.table_digest())
    assert stripe["schema"] == pt.STRIPE_SCHEMA
    assert stripe["write_to_stripe"] is False
    assert stripe["values_approved"] is False
    assert [price["lookup_key"] for price in stripe["prices"]] == list(LOOKUP_KEYS)
    assert all(price["create"] is False and price["currency"] == "usd" for price in stripe["prices"])
    by_key = {price["lookup_key"]: price for price in stripe["prices"]}
    assert by_key["draft_szl_inference_lite_input_uncached_per_1m"]["unit_amount_decimal"] == "30"
    assert by_key["draft_szl_inference_lite_input_cached_per_1m"]["unit_amount_decimal"] == "3"
    assert by_key["draft_szl_inference_lite_output_per_1m"]["unit_amount_decimal"] == "300"
    assert by_key["draft_szl_inference_standard_output_per_1m"]["unit_amount_decimal"] == "600"
    assert by_key["draft_szl_inference_lite_offpeak_input_cached_per_1m"]["unit_amount_decimal"] == "1.8"
    assert by_key["draft_szl_inference_lite_offpeak_input_cached_per_1m"]["offer"] == "not-justified"
    assert by_key["draft_szl_inference_standard_input_uncached_per_1m"]["provisional"] is True
    assert by_key["draft_szl_inference_credit_pack_usd_10"]["unit_amount"] == 1000
    assert by_key["draft_szl_inference_credit_pack_usd_50"]["unit_amount"] == 5000
    assert by_key["draft_szl_inference_credit_pack_usd_200"]["unit_amount"] == 20000
    assert by_key["draft_szl_inference_credit_pack_usd_200"]["type"] == "one_time"
    blob = json.dumps(stripe)
    assert "sk_" not in blob and "whsec_" not in blob and "rk_" not in blob
    assert "price_" not in blob.replace("price_table", "")
    not_stripe = {item["id"]: item for item in stripe["not_stripe_prices"]}
    assert not_stripe["minimum_per_call"]["amount_atomic"] == 2000
    assert not_stripe["live_floor_exact"]["amount_atomic"] == 20000
    assert "divide_by" in stripe["read_first"]


def test_generated_files_are_current_and_carry_no_secret(table, catalog):
    rendered = pt.render_all(table, catalog, pt.table_digest(), pc.catalog_digest())
    for name, body in rendered.items():
        assert (pt.GENERATED / name).read_text(encoding="utf-8") == body
        assert "sk_" not in body and "whsec_" not in body
        parsed = json.loads(body)
        assert parsed["status"] == "DRAFT"
        assert parsed["values_approved"] is False


def test_tool_source_does_not_import_a_network_client():
    source = (ROOT / "tools" / "price_table.py").read_text(encoding="utf-8")
    for banned in ("import urllib", "import requests", "import socket", "import http", "stripe."):
        assert banned not in source


# --- CLI ---------------------------------------------------------------------


def test_cli_accepts_the_committed_files():
    assert pt.main(["validate"]) == 0
    assert pt.main(["check"]) == 0
    assert pt.main(["generate", "--check"]) == 0
    assert pt.main(["fmt", "--check"]) == 0


def test_cli_reports_drift_and_unreadable_input(tmp_path, catalog):
    catalog["payment"]["pay_to"] = "0x" + "ab" * 20
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(pc.yamlite.dump(catalog), encoding="utf-8")
    assert pt.main(["check", "--catalog", str(catalog_path)]) == 1
    broken = tmp_path / "broken.yaml"
    broken.write_text(":\n", encoding="utf-8")
    assert pt.main(["validate", "--table", str(broken)]) == 2
    out = tmp_path / "out"
    out.mkdir()
    assert pt.main(["generate", "--check", "--out", str(out)]) == 1
    assert pt.main(["generate", "--out", str(out)]) == 0
    assert pt.main(["generate", "--check", "--out", str(out)]) == 0
