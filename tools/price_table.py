#!/usr/bin/env python3
"""price_table — the draft per-1M-token card, and the checks that keep it one source.

``pricing/price-table.yaml`` is the source for the draft inference card (tiers,
per-1M-token rates, the per-call minimum, credit-pack sizes) and for the numbers
``pricing/catalog.yaml`` also states: the pay-to address and every charged
per-call amount. The catalog keeps rule expressions, hosts and paths. This tool
reads both. It does not duplicate those rule fields into the table.

Commands (stdlib only, no network, no Stripe and no Cloudflare calls):

  validate  Reject a price table that is not the draft schema.
  check     Fail when catalog payment terms or charged prices differ from the table.
  generate  Write gateway rule parameters and Stripe lookup keys, or --check them.
  fmt       Rewrite the table in canonical yamlite form, or --check it.

The generated gateway file keeps today's exact per-call floor and also emits the
``upto`` per-token parameters marked not-yet-applied. Nothing here is a write,
and the draft values are not an approval to charge them.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
if __package__:  # installed wheel: sibling modules live inside the szl_gov package
    from . import pricing_catalog as catalog_mod
else:
    import pricing_catalog as catalog_mod

TABLE = ROOT / "pricing" / "price-table.yaml"
GENERATED = ROOT / "pricing" / "generated"
GATEWAY_OUTPUT = "gateway-rule-parameters.json"
STRIPE_OUTPUT = "stripe-lookup-keys.json"
OUTPUTS = (GATEWAY_OUTPUT, STRIPE_OUTPUT)

SCHEMA = "szl.price-table/v1"
GATEWAY_SCHEMA = "szl.gateway-rule-parameters/v1"
STRIPE_SCHEMA = "szl.stripe-lookup-keys/v1"
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
TIER_ID = re.compile(r"[a-z][a-z0-9_]*")
PACK_ID = re.compile(r"[a-z0-9-]+")
ENTRY_ID = re.compile(r"[a-z0-9-]+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
COMPONENTS = ("input_uncached", "input_cached", "output")
ROLES = frozenset({"floor", "other-per-call"})
FORBIDDEN_KEYS = frozenset({
    "secret", "secret_key", "api_key", "password", "stripe_secret_key",
    "stripe_webhook_secret", "webhook_secret", "authorization", "bearer",
    "sk_live", "sk_test", "rk_live", "rk_test",
})
SECRET_VALUE = re.compile(r"(?:^|_)(?:sk|rk)_(?:live|test)_|^whsec_")
TOP_KEYS = frozenset({
    "schema", "status", "approval", "published", "deployed", "values_approved",
    "as_of", "card", "plan", "currency", "atomic_per_usd", "tokens_per_unit",
    "payment", "gateway_bounds", "floor", "minimum_per_call", "upto",
    "off_peak_policy", "cached_input_ratio", "reference_call", "tiers",
    "credit_packs", "catalog_prices",
})
PAYMENT_KEYS = frozenset({"protocol", "network", "asset", "asset_name", "pay_to"})
BOUNDS_KEYS = frozenset({"min_atomic", "max_atomic"})
FLOOR_KEYS = frozenset({
    "applied", "write", "disposition", "scheme", "amount_atomic", "catalog_entry_ids", "note",
})
MINIMUM_KEYS = frozenset({"applied", "amount_atomic", "note"})
UPTO_KEYS = frozenset({
    "applied", "write", "disposition", "scheme", "cap_policy", "gateway_support", "note",
})
OFF_PEAK_KEYS = frozenset({"applied", "status", "numerator", "denominator", "note"})
RATIO_KEYS = frozenset({"numerator", "denominator", "note"})
REFERENCE_KEYS = frozenset({
    "input_uncached_tokens", "input_cached_tokens", "output_tokens", "note",
})
TIER_KEYS = frozenset({
    "id", "name", "model", "offer", "provisional", "context_tokens",
    "input_uncached_atomic_per_million", "input_cached_atomic_per_million",
    "output_atomic_per_million",
})
PACK_KEYS = frozenset({"id", "amount_atomic"})
CATALOG_PRICE_KEYS = frozenset({"id", "amount_atomic", "scheme", "role"})
CATALOG_FIELDS = (
    "rule_id", "rule_description", "zone", "host", "path_prefixes", "methods",
    "audience", "expression",
)
TABLE_FIELDS = ("price", "address", "scheme")


class PriceTableError(ValueError):
    """The price table is unreadable or is not the one draft card."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise PriceTableError(message)


def _int(value, where: str) -> int:
    if type(value) is not int:
        raise PriceTableError(f"{where} must be an integer")
    return value


def _bool(value, where: str) -> bool:
    if type(value) is not bool:
        raise PriceTableError(f"{where} must be a boolean")
    return value


def _text(value, where: str) -> str:
    if type(value) is not str or value == "" or "\n" in value:
        raise PriceTableError(f"{where} must be a single line of text")
    return value


def _keys(obj, allowed: frozenset, where: str) -> None:
    if type(obj) is not dict:
        raise PriceTableError(f"{where} must be a mapping")
    extra = set(obj) - allowed
    missing = allowed - set(obj)
    if extra or missing:
        raise PriceTableError(f"{where} fields differ (extra {sorted(extra)}, missing {sorted(missing)})")


def _reject_secrets(obj, where: str) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS or SECRET_VALUE.search(str(key)):
                raise PriceTableError(f"{where}.{key}: secret-shaped key")
            _reject_secrets(value, f"{where}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _reject_secrets(value, f"{where}[{index}]")
    elif isinstance(obj, str) and SECRET_VALUE.search(obj):
        raise PriceTableError(f"{where}: secret-shaped value")


def _in_gateway_range(atomic: int, bounds: dict, where: str) -> None:
    if not bounds["min_atomic"] <= atomic <= bounds["max_atomic"]:
        raise PriceTableError(
            f"{where} {atomic} is outside the gateway range "
            f"{bounds['min_atomic']}..{bounds['max_atomic']}"
        )


def validate_table(table: dict) -> None:
    """Fail closed unless this is the unapproved draft card."""
    _reject_secrets(table, "price-table")
    _keys(table, TOP_KEYS, "price table")
    _need(table["schema"] == SCHEMA, f"schema must be {SCHEMA}")
    _need(table["status"] == "DRAFT" and table["approval"] == "not-approved",
          "v1 is a draft schema: status must be DRAFT and approval not-approved")
    _need(_bool(table["published"], "published") is False
          and _bool(table["deployed"], "deployed") is False
          and _bool(table["values_approved"], "values_approved") is False,
          "v1 cannot be published, deployed, or marked approved")
    _need(DATE.fullmatch(_text(table["as_of"], "as_of")) is not None, "as_of must be YYYY-MM-DD")
    _text(table["card"], "card")
    _text(table["plan"], "plan")
    _need(table["currency"] == "USD", "currency must be USD")
    _need(_int(table["atomic_per_usd"], "atomic_per_usd") == 1_000_000,
          "atomic_per_usd must be 1000000 (USDC, 6 decimals)")
    _need(_int(table["tokens_per_unit"], "tokens_per_unit") == 1_000_000,
          "tokens_per_unit must be 1000000")

    _keys(table["payment"], PAYMENT_KEYS, "payment")
    pay = table["payment"]
    _need(pay["protocol"] == "x402", "payment.protocol must be x402")
    _need(re.fullmatch(r"eip155:\d+", _text(pay["network"], "payment.network")) is not None,
          "payment.network must look like eip155:<id>")
    _need(ADDRESS.fullmatch(_text(pay["asset"], "payment.asset")) is not None, "payment.asset must be an 0x address")
    _need(ADDRESS.fullmatch(_text(pay["pay_to"], "payment.pay_to")) is not None, "payment.pay_to must be an 0x address")
    _text(pay["asset_name"], "payment.asset_name")

    _keys(table["gateway_bounds"], BOUNDS_KEYS, "gateway_bounds")
    bounds = table["gateway_bounds"]
    _need((_int(bounds["min_atomic"], "gateway min"), _int(bounds["max_atomic"], "gateway max"))
          == (catalog_mod.MIN_ATOMIC, catalog_mod.MAX_ATOMIC),
          "gateway bounds must match the catalog's Monetization Gateway limits")

    _validate_policies(table, bounds)
    _validate_tiers(table, bounds)
    _validate_packs(table)
    _validate_catalog_prices(table, bounds)


def _validate_policies(table: dict, bounds: dict) -> None:
    floor = table["floor"]
    _keys(floor, FLOOR_KEYS, "floor")
    _need(_bool(floor["applied"], "floor.applied") is True, "the live floor must stay applied")
    _need(_bool(floor["write"], "floor.write") is False, "the floor is not a Cloudflare write")
    _need(floor["disposition"] == "keep-live", "floor.disposition must be keep-live")
    _need(floor["scheme"] == "exact", "the live floor scheme must be exact")
    _in_gateway_range(_int(floor["amount_atomic"], "floor.amount_atomic"), bounds, "floor")
    _text(floor["note"], "floor.note")
    ids = floor["catalog_entry_ids"]
    _need(type(ids) is list and ids and len(ids) == len(set(ids)), "floor catalog_entry_ids must be unique")
    for entry_id in ids:
        _need(type(entry_id) is str and ENTRY_ID.fullmatch(entry_id) is not None,
              f"bad floor catalog entry id {entry_id!r}")

    minimum = table["minimum_per_call"]
    _keys(minimum, MINIMUM_KEYS, "minimum_per_call")
    _need(_bool(minimum["applied"], "minimum_per_call.applied") is False,
          "the card minimum is not what the gateway charges today")
    _in_gateway_range(_int(minimum["amount_atomic"], "minimum"), bounds, "minimum")
    _need(minimum["amount_atomic"] <= floor["amount_atomic"],
          "the card minimum must not exceed the live floor")
    _text(minimum["note"], "minimum_per_call.note")

    upto = table["upto"]
    _keys(upto, UPTO_KEYS, "upto")
    _need(_bool(upto["applied"], "upto.applied") is False, "scheme upto must stay not-yet-applied")
    _need(_bool(upto["write"], "upto.write") is False, "scheme upto is not a Cloudflare write")
    _need(upto["disposition"] == "not-yet-applied", "upto.disposition must be not-yet-applied")
    _need(upto["scheme"] == "upto" and upto["scheme"] in catalog_mod.SCHEMES, "upto.scheme must be upto")
    _need(upto["cap_policy"] == "dearest-fill-of-context", "upto.cap_policy is dearest-fill-of-context")
    _need(upto["gateway_support"] == "UNKNOWN", "gateway support for scheme upto must stay UNKNOWN")
    _text(upto["note"], "upto.note")

    policy = table["off_peak_policy"]
    _keys(policy, OFF_PEAK_KEYS, "off_peak_policy")
    _need(_bool(policy["applied"], "off_peak.applied") is False, "off-peak must stay not applied")
    _need(policy["status"] == "not-justified", "off-peak status must be not-justified")
    num, den = _int(policy["numerator"], "off-peak numerator"), _int(policy["denominator"], "off-peak denominator")
    _need(0 < num < den, "off-peak must keep a positive fraction below 1")
    _text(policy["note"], "off_peak_policy.note")

    ratio = table["cached_input_ratio"]
    _keys(ratio, RATIO_KEYS, "cached_input_ratio")
    num, den = _int(ratio["numerator"], "cached numerator"), _int(ratio["denominator"], "cached denominator")
    _need(0 < num < den, "cached-input ratio must be a positive fraction below 1")
    _text(ratio["note"], "cached_input_ratio.note")

    call = table["reference_call"]
    _keys(call, REFERENCE_KEYS, "reference_call")
    for key in ("input_uncached_tokens", "input_cached_tokens", "output_tokens"):
        _need(_int(call[key], key) >= 0, f"{key} must be >= 0")
    _text(call["note"], "reference_call.note")


def _validate_tiers(table: dict, bounds: dict) -> None:
    tiers = table["tiers"]
    _need(type(tiers) is list and tiers, "tiers must be a non-empty list")
    seen = set()
    ratio = table["cached_input_ratio"]
    policy = table["off_peak_policy"]
    for index, tier in enumerate(tiers):
        where = f"tiers[{index}]"
        if type(tier) is not dict:
            raise PriceTableError(f"{where} must be a mapping")
        extra = set(tier) - (TIER_KEYS | {"provisional_reason"})
        missing = TIER_KEYS - set(tier)
        if extra or missing:
            raise PriceTableError(f"{where} fields differ (extra {sorted(extra)}, missing {sorted(missing)})")
        tier_id = _text(tier["id"], f"{where}.id")
        _need(TIER_ID.fullmatch(tier_id) is not None, f"{where}.id must be a lookup-key token")
        _need(tier_id not in seen, f"duplicate tier id {tier_id}")
        seen.add(tier_id)
        _text(tier["name"], f"{where}.name")
        _text(tier["model"], f"{where}.model")
        _need(tier["offer"] == "not-published", f"{where}.offer must be not-published while the card is a draft")
        provisional = _bool(tier["provisional"], f"{where}.provisional")
        if provisional:
            _need("provisional_reason" in tier, f"{where} provisional tier needs provisional_reason")
            _text(tier["provisional_reason"], f"{where}.provisional_reason")
        elif "provisional_reason" in tier:
            raise PriceTableError(f"{where} provisional_reason is only for a provisional tier")
        context = tier["context_tokens"]
        if context is not None:
            _need(_int(context, f"{where}.context_tokens") > 0, f"{where}.context_tokens must be > 0")
        uncached = _int(tier["input_uncached_atomic_per_million"], f"{where}.input")
        cached = _int(tier["input_cached_atomic_per_million"], f"{where}.cached")
        output = _int(tier["output_atomic_per_million"], f"{where}.output")
        _need(uncached > 0 and cached > 0 and output > 0, f"{where} rates must be positive")
        _need(output >= uncached >= cached, f"{where} rates must fall from output to cached input")
        _need(cached * ratio["denominator"] == uncached * ratio["numerator"],
              f"{where} cached rate does not match cached_input_ratio")
        for rate in (uncached, cached, output):
            _in_gateway_range(rate, bounds, f"{where} rate")
            _need(rate * policy["numerator"] % policy["denominator"] == 0,
                  f"{where} off-peak fraction does not land on an atomic unit")


def _validate_packs(table: dict) -> None:
    packs = table["credit_packs"]
    _need(type(packs) is list and packs, "credit_packs must be a non-empty list")
    seen_ids, seen_amounts = set(), set()
    for index, pack in enumerate(packs):
        where = f"credit_packs[{index}]"
        _keys(pack, PACK_KEYS, where)
        pack_id = _text(pack["id"], f"{where}.id")
        _need(PACK_ID.fullmatch(pack_id) is not None, f"{where}.id has unsupported characters")
        amount = _int(pack["amount_atomic"], f"{where}.amount_atomic")
        _need(amount > 0 and amount % table["atomic_per_usd"] == 0,
              f"{where} amount must be a positive whole-dollar atomic amount")
        _need(pack_id not in seen_ids, f"duplicate credit pack id {pack_id}")
        _need(amount not in seen_amounts, f"duplicate credit pack amount {amount}")
        seen_ids.add(pack_id)
        seen_amounts.add(amount)


def _validate_catalog_prices(table: dict, bounds: dict) -> None:
    rows = table["catalog_prices"]
    _need(type(rows) is list and rows, "catalog_prices must be a non-empty list")
    seen = set()
    floor = table["floor"]
    for index, row in enumerate(rows):
        where = f"catalog_prices[{index}]"
        _keys(row, CATALOG_PRICE_KEYS, where)
        entry_id = _text(row["id"], f"{where}.id")
        _need(ENTRY_ID.fullmatch(entry_id) is not None, f"{where}.id has unsupported characters")
        _need(entry_id not in seen, f"duplicate catalog price id {entry_id}")
        seen.add(entry_id)
        amount = _int(row["amount_atomic"], f"{where}.amount_atomic")
        _in_gateway_range(amount, bounds, where)
        _need(row["scheme"] in catalog_mod.SCHEMES, f"{where}.scheme is not a known gateway scheme")
        _need(row["role"] in ROLES, f"{where}.role must be floor or other-per-call")
        if row["role"] == "floor":
            _need(amount == floor["amount_atomic"] and row["scheme"] == floor["scheme"],
                  f"{entry_id}: a floor row must match the floor amount and scheme")
        else:
            _need(row["scheme"] == "exact", f"{entry_id}: non-token per-call prices stay scheme exact")
            _need(amount != floor["amount_atomic"],
                  f"{entry_id}: amount equals the floor but the role is other-per-call")
    floor_rows = [row["id"] for row in rows if row["role"] == "floor"]
    _need(floor_rows == floor["catalog_entry_ids"],
          f"floor catalog_entry_ids {floor['catalog_entry_ids']} != floor rows {floor_rows}")


def load_table(path: Path = TABLE) -> dict:
    table = catalog_mod.load_yaml(path.read_text(encoding="utf-8"))
    validate_table(table)
    return table


def table_digest(path: Path = TABLE) -> str:
    """Same LF-normalized digest the catalog generator uses."""
    return catalog_mod.catalog_digest(path)


def drift(table: dict, catalog: dict) -> list[str]:
    """Disagreements between the price table and the per-call catalog.

    The table owns payment identity and every charged amount. The catalog owns
    the rule shape. A difference in a shared number is drift.
    """
    errors = []
    expected = {
        "protocol": table["payment"]["protocol"],
        "network": table["payment"]["network"],
        "asset": table["payment"]["asset"],
        "asset_name": table["payment"]["asset_name"],
        "pay_to": table["payment"]["pay_to"],
        "atomic_per_usd": table["atomic_per_usd"],
    }
    for key, want in expected.items():
        got = catalog["payment"].get(key)
        if got != want:
            errors.append(f"payment.{key}: catalog {got!r} != price table {want!r}")

    catalog_ids = [entry["id"] for entry in catalog["charged"]]
    table_ids = [row["id"] for row in table["catalog_prices"]]
    if catalog_ids != table_ids:
        errors.append(f"charged ids: catalog {catalog_ids} != price table {table_ids}")
    rows = {row["id"]: row for row in table["catalog_prices"]}
    for entry in catalog["charged"]:
        row = rows.get(entry["id"])
        if row is None:
            continue
        if entry["amount_atomic"] != row["amount_atomic"]:
            errors.append(
                f"charged {entry['id']} amount_atomic: catalog {entry['amount_atomic']} "
                f"!= price table {row['amount_atomic']}"
            )
        if entry["scheme"] != row["scheme"]:
            errors.append(
                f"charged {entry['id']} scheme: catalog {entry['scheme']!r} != price table {row['scheme']!r}"
            )
        if entry["scheme"] == "upto" and table["upto"]["applied"] is False:
            errors.append(f"charged {entry['id']}: catalog scheme is upto but the price table has not applied it")
    return errors


def require_agreement(table: dict, catalog: dict) -> None:
    errors = drift(table, catalog)
    if errors:
        raise PriceTableError("catalog drifted from the price table: " + "; ".join(errors))


def component_atomic(tokens: int, rate: int, unit: int = 1_000_000) -> int:
    """Ceil of tokens * per-million rate / unit, so a fraction never rounds down."""
    if type(tokens) is not int or tokens < 0 or type(rate) is not int or rate < 0 or type(unit) is not int or unit <= 0:
        raise PriceTableError("token count, rate and unit must be non-negative integers")
    if tokens == 0 or rate == 0:
        return 0
    return (tokens * rate + unit - 1) // unit


def off_peak_atomic(rate: int, policy: dict) -> int:
    numerator, denominator = policy["numerator"], policy["denominator"]
    if rate * numerator % denominator != 0:
        raise PriceTableError("off-peak fraction does not land on an atomic unit")
    return rate * numerator // denominator


def rate_atomic(tier: dict, component: str, table: dict, *, off_peak: bool) -> int:
    peak = tier[f"{component}_atomic_per_million"]
    if not off_peak:
        return peak
    return off_peak_atomic(peak, table["off_peak_policy"])


def metered_atomic(tier: dict, table: dict, uncached: int, cached: int, output: int, *, off_peak: bool = False) -> int:
    counts = {"input_uncached": uncached, "input_cached": cached, "output": output}
    unit = table["tokens_per_unit"]
    total = 0
    for component, tokens in counts.items():
        total += component_atomic(tokens, rate_atomic(tier, component, table, off_peak=off_peak), unit)
    return total


def card_settlement_atomic(metered: int, minimum: int) -> int:
    """Card quote: never below the per-call minimum. Not a gateway parameter."""
    if type(metered) is not int or type(minimum) is not int or metered < 0 or minimum < 0:
        raise PriceTableError("settlement inputs must be non-negative integers")
    return max(metered, minimum)


def atomic_to_cents_decimal(atomic: int, atomic_per_usd: int = 1_000_000) -> str:
    """US cents for an atomic USDC amount, as a decimal string. No binary float."""
    if type(atomic) is not int or atomic < 0:
        raise PriceTableError("atomic amount must be a non-negative integer")
    divisor = atomic_per_usd // 100
    whole, frac = divmod(atomic, divisor)
    if frac == 0:
        return str(whole)
    return f"{whole}.{frac:04d}".rstrip("0")


def cents_per_token_decimal(atomic_per_million: int, atomic_per_usd: int = 1_000_000) -> str:
    """US cents for one token, given an atomic price per 1M tokens."""
    if type(atomic_per_million) is not int or atomic_per_million < 0:
        raise PriceTableError("per-million rate must be a non-negative integer")
    # cents/token = (atomic/million / cents-divisor) / 1_000_000
    divisor = (atomic_per_usd // 100) * 1_000_000
    whole, frac = divmod(atomic_per_million, divisor)
    if frac == 0:
        text = str(whole)
    else:
        width = len(str(divisor - 1))
        digits = f"{frac:0{width}d}".rstrip("0")
        text = f"{whole}.{digits}" if whole else f"0.{digits}"
    places = len(text.partition(".")[2])
    if places > 12:
        raise PriceTableError("per-token cents need more than 12 decimal places")
    return text


def _usd(atomic: int, table: dict) -> str:
    return catalog_mod.usd(atomic, table["atomic_per_usd"])


def _rates(tier: dict, table: dict, *, off_peak: bool) -> dict:
    atomic = {component: rate_atomic(tier, component, table, off_peak=off_peak) for component in COMPONENTS}
    return {
        "atomic_per_million": atomic,
        "usd_per_million": {component: _usd(amount, table) for component, amount in atomic.items()},
    }


def authorization_quote(tier: dict, table: dict, *, off_peak: bool) -> dict:
    """One static rule price: the dearest fill of a known context window.

    A gateway rule carries one price. Input and output share the context window,
    and output is the dearer rate, so the cap bills every context token as output.
    Unknown context does not get an invented cap. A cap outside the gateway's
    $0.001-$100 range is not emitted as a price.
    """
    context = tier["context_tokens"]
    rate = rate_atomic(tier, "output", table, off_peak=off_peak)
    floor_atomic = table["floor"]["amount_atomic"]
    quote = {
        "cap_policy": table["upto"]["cap_policy"],
        "context_tokens": context,
        "output_rate_atomic_per_million": rate,
        "live_floor_atomic": floor_atomic,
        "applied": False,
        "price": None,
        "price_atomic": None,
        "price_usd": None,
    }
    if context is None:
        quote["generated"] = False
        quote["reason"] = "context_tokens is UNKNOWN, so no authorization cap is generated"
        return quote
    atomic = component_atomic(context, rate, table["tokens_per_unit"])
    bounds = table["gateway_bounds"]
    if not bounds["min_atomic"] <= atomic <= bounds["max_atomic"]:
        quote["generated"] = False
        quote["reason"] = (
            f"computed cap {atomic} atomic is outside the gateway range "
            f"{bounds['min_atomic']}..{bounds['max_atomic']}"
        )
        return quote
    quote["generated"] = True
    quote["price_atomic"] = atomic
    quote["price"] = str(atomic)
    quote["price_usd"] = _usd(atomic, table)
    quote["reason"] = "every context token billed at the output rate, the dearest fill of the window"
    if atomic < floor_atomic:
        quote["reason"] += ". This cap is below the live exact floor, so it cannot replace that floor"
    return quote


def _rule_parameters(entry: dict, row: dict, table: dict) -> dict:
    return {
        "catalog_id": entry["id"],
        "role": row["role"],
        "surface": entry["surface"],
        "rule_id": entry["rule_id"],
        "rule_description": entry["rule_description"],
        "zone": entry["zone"],
        "host": entry["host"],
        "path_prefixes": list(entry["path_prefixes"]),
        "methods": list(entry["methods"]),
        "audience": entry["audience"],
        "expression": entry["expression"],
        "scheme": row["scheme"],
        "price": str(row["amount_atomic"]),
        "price_usd": _usd(row["amount_atomic"], table),
        "address": table["payment"]["pay_to"],
        "disposition": "keep-live",
        "write": False,
    }


def _examples(table: dict) -> list:
    call = table["reference_call"]
    minimum = table["minimum_per_call"]["amount_atomic"]
    floor = table["floor"]["amount_atomic"]
    specs = (
        ("reference-call", call["input_uncached_tokens"], call["input_cached_tokens"], call["output_tokens"], False),
        ("one-output-token", 0, 0, 1, False),
        ("reference-call-off-peak", call["input_uncached_tokens"], call["input_cached_tokens"],
         call["output_tokens"], True),
    )
    examples = []
    for name, uncached, cached, output, off_peak in specs:
        by_tier = []
        for tier in table["tiers"]:
            metered = metered_atomic(tier, table, uncached, cached, output, off_peak=off_peak)
            settled = card_settlement_atomic(metered, minimum)
            by_tier.append({
                "tier": tier["id"],
                "metered_atomic": metered,
                "metered_usd": _usd(metered, table),
                "card_settlement_atomic": settled,
                "card_settlement_usd": _usd(settled, table),
            })
        examples.append({
            "name": name,
            "label": "DERIVED",
            "off_peak": off_peak,
            "applied": False,
            "input_uncached_tokens": uncached,
            "input_cached_tokens": cached,
            "output_tokens": output,
            "live_floor_exact_atomic": floor,
            "live_floor_applied": True,
            "upto_applied": False,
            "tiers": by_tier,
        })
    return examples


def build_gateway_rules(table: dict, catalog: dict, table_sha: str, catalog_sha: str) -> dict:
    validate_table(table)
    catalog_mod.validate_catalog(catalog)
    require_agreement(table, catalog)
    by_id = {entry["id"]: entry for entry in catalog["charged"]}
    floor_rules, other_rules = [], []
    for row in table["catalog_prices"]:
        shaped = _rule_parameters(by_id[row["id"]], row, table)
        (floor_rules if row["role"] == "floor" else other_rules).append(shaped)
    upto_tiers = []
    for tier in table["tiers"]:
        shaped = {
            "id": tier["id"],
            "name": tier["name"],
            "model": tier["model"],
            "offer": tier["offer"],
            "provisional": tier["provisional"],
            "scheme": "upto",
            "applied": False,
            "disposition": "not-yet-applied",
            "write": False,
            "minimum_atomic": table["minimum_per_call"]["amount_atomic"],
            "minimum_usd": _usd(table["minimum_per_call"]["amount_atomic"], table),
            "rates": _rates(tier, table, off_peak=False),
            "authorization": authorization_quote(tier, table, off_peak=False),
            "off_peak": {
                "status": table["off_peak_policy"]["status"],
                "applied": False,
                "rates": _rates(tier, table, off_peak=True),
                "authorization": authorization_quote(tier, table, off_peak=True),
            },
        }
        if tier["provisional"]:
            shaped["provisional_reason"] = tier["provisional_reason"]
        upto_tiers.append(shaped)
    floor = table["floor"]
    return {
        "schema": GATEWAY_SCHEMA,
        "status": "DRAFT",
        "approval": "not-approved",
        "values_approved": False,
        "write_to_cloudflare": False,
        "read_first": (
            "DRAFT. Do not PATCH Cloudflare. The floor block is today's exact per-call "
            "price and stays in force. The upto block is generated and not-yet-applied. "
            "Gateway support for scheme upto on this route is UNKNOWN."
        ),
        "source": {
            "price_table": "pricing/price-table.yaml",
            "price_table_sha256": table_sha,
            "catalog": "pricing/catalog.yaml",
            "catalog_sha256": catalog_sha,
            "generator": "szl-gov tools/price_table.py",
            "fields_from_price_table": list(TABLE_FIELDS),
            "fields_read_from_catalog": list(CATALOG_FIELDS),
        },
        "payment": {
            "protocol": table["payment"]["protocol"],
            "network": table["payment"]["network"],
            "asset": table["payment"]["asset"],
            "asset_name": table["payment"]["asset_name"],
            "atomic_per_usd": table["atomic_per_usd"],
            "pay_to": table["payment"]["pay_to"],
        },
        "floor": {
            "disposition": floor["disposition"],
            "applied": True,
            "write": False,
            "scheme": floor["scheme"],
            "price": str(floor["amount_atomic"]),
            "price_usd": _usd(floor["amount_atomic"], table),
            "note": floor["note"],
            "rules": floor_rules,
        },
        "other_exact_rules": {
            "disposition": "keep-live",
            "applied": True,
            "write": False,
            "note": (
                "Charged per-call prices that are not the inference floor. Amounts and "
                "pay-to come from the price table. Rule shape is read from the catalog."
            ),
            "rules": other_rules,
        },
        "upto": {
            "disposition": table["upto"]["disposition"],
            "applied": False,
            "write": False,
            "scheme": "upto",
            "gateway_support": "UNKNOWN",
            "replaces_floor_rules": False,
            "floor_catalog_ids": list(floor["catalog_entry_ids"]),
            "minimum_atomic": table["minimum_per_call"]["amount_atomic"],
            "minimum_usd": _usd(table["minimum_per_call"]["amount_atomic"], table),
            "settlement": {
                "report_via": "PAYMENT-SETTLEMENT",
                "gateway_constraint": "0 <= actual_atomic <= authorized price",
                "card_constraint": "actual_atomic >= per-call minimum and actual_atomic <= authorized price",
                "note": (
                    "The gateway documents a settled actual between 0 and the authorized "
                    "price inclusive. The card also applies a per-call minimum, which the "
                    "origin would have to enforce. Scheme support on this route is UNKNOWN. "
                    "Not applied."
                ),
            },
            "tiers": upto_tiers,
        },
        "examples": _examples(table),
    }


def _stripe_metadata(table_sha: str) -> dict:
    return {
        "status": "DRAFT",
        "approval": "not-approved",
        "price_table_schema": SCHEMA,
        "price_table_sha256": table_sha,
        "do_not_create": "true",
    }


def _metered_price(tier: dict, table: dict, component: str, table_sha: str, *, off_peak: bool) -> dict:
    rate = rate_atomic(tier, component, table, off_peak=off_peak)
    middle = f"{tier['id']}_offpeak_{component}" if off_peak else f"{tier['id']}_{component}"
    labels = {"input_uncached": "uncached input", "input_cached": "cached input", "output": "output"}
    peak = "off-peak " if off_peak else ""
    return {
        "lookup_key": f"draft_szl_inference_{middle}_per_1m",
        "create": False,
        "type": "recurring",
        "currency": "usd",
        "product_name": "SZL inference DRAFT",
        "nickname": f"DRAFT {tier['name']} {peak}{labels[component]} per 1M tokens",
        "tier": tier["id"],
        "component": component,
        "off_peak": off_peak,
        "offer": table["off_peak_policy"]["status"] if off_peak else tier["offer"],
        "provisional": tier["provisional"],
        "unit": "1000000_tokens",
        "unit_amount_decimal": atomic_to_cents_decimal(rate, table["atomic_per_usd"]),
        "per_token_unit_amount_decimal": cents_per_token_decimal(rate, table["atomic_per_usd"]),
        "recurring": {"interval": "month", "usage_type": "metered", "interval_count": 1},
        "metadata": _stripe_metadata(table_sha),
    }


def _pack_price(pack: dict, table: dict, table_sha: str) -> dict:
    dollars = pack["amount_atomic"] // table["atomic_per_usd"]
    cents = pack["amount_atomic"] // (table["atomic_per_usd"] // 100)
    return {
        "lookup_key": f"draft_szl_inference_credit_pack_usd_{dollars}",
        "create": False,
        "type": "one_time",
        "currency": "usd",
        "product_name": "SZL inference DRAFT",
        "nickname": f"DRAFT credit pack ${dollars}",
        "pack_id": pack["id"],
        "amount_atomic": pack["amount_atomic"],
        "amount_usd": _usd(pack["amount_atomic"], table),
        "unit_amount": cents,
        "metadata": _stripe_metadata(table_sha),
    }


def build_stripe_lookup_keys(table: dict, table_sha: str) -> dict:
    validate_table(table)
    prices = []
    for off_peak in (False, True):
        for tier in table["tiers"]:
            for component in COMPONENTS:
                prices.append(_metered_price(tier, table, component, table_sha, off_peak=off_peak))
    prices.extend(_pack_price(pack, table, table_sha) for pack in table["credit_packs"])
    keys = [price["lookup_key"] for price in prices]
    if len(keys) != len(set(keys)):
        raise PriceTableError("Stripe lookup keys are not unique")
    return {
        "schema": STRIPE_SCHEMA,
        "status": "DRAFT",
        "approval": "not-approved",
        "values_approved": False,
        "write_to_stripe": False,
        "read_first": (
            "DRAFT lookup keys only. No Stripe price id, product id, secret key or "
            "webhook secret. create is false on every row. Do not create these prices "
            "until the card is approved. Stripe transform_quantity.divide_by rounds to "
            "an integer before pricing, so dividing raw tokens by 1000000 against the "
            "per-1M unit amount would bill a short call as a full million tokens. Use "
            "per_token_unit_amount_decimal, or debit atomic units in the ledger."
        ),
        "source": {
            "price_table": "pricing/price-table.yaml",
            "price_table_sha256": table_sha,
            "generator": "szl-gov tools/price_table.py",
        },
        "prices": prices,
        "not_stripe_prices": [
            {
                "id": "minimum_per_call",
                "amount_atomic": table["minimum_per_call"]["amount_atomic"],
                "amount_usd": _usd(table["minimum_per_call"]["amount_atomic"], table),
                "reason": (
                    "A card charge at the per-call minimum is not a Stripe price. "
                    "Packs or a metered invoice carry it."
                ),
            },
            {
                "id": "live_floor_exact",
                "amount_atomic": table["floor"]["amount_atomic"],
                "amount_usd": _usd(table["floor"]["amount_atomic"], table),
                "reason": "The live x402 floor is a Cloudflare exact rule, not a Stripe price.",
            },
        ],
    }


def render_all(table: dict, catalog: dict, table_sha: str, catalog_sha: str) -> dict:
    return {
        GATEWAY_OUTPUT: json.dumps(
            build_gateway_rules(table, catalog, table_sha, catalog_sha), indent=2, ensure_ascii=True
        ) + "\n",
        STRIPE_OUTPUT: json.dumps(build_stripe_lookup_keys(table, table_sha), indent=2, ensure_ascii=True) + "\n",
    }


def _read_pair(table_path: Path, catalog_path: Path):
    table = load_table(table_path)
    catalog = catalog_mod.load_catalog(catalog_path)
    return table, catalog, table_digest(table_path), catalog_mod.catalog_digest(catalog_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="fail if the catalog disagrees with the price table")
    generate = sub.add_parser("generate", help="write or verify the derived parameter files")
    validate = sub.add_parser("validate", help="validate the draft price table")
    fmt = sub.add_parser("fmt", help="canonicalize the price table")
    for command in (check, generate, validate, fmt):
        command.add_argument("--table", type=Path, default=TABLE)
    for command in (check, generate):
        command.add_argument("--catalog", type=Path, default=catalog_mod.CATALOG)
    generate.add_argument("--check", action="store_true")
    generate.add_argument("--out", type=Path, default=GENERATED)
    fmt.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "fmt":
            text = args.table.read_text(encoding="utf-8")
            canonical = catalog_mod.format_catalog(text)
            if args.check:
                if canonical != text:
                    print(f"FAIL: {args.table} is not canonical; run: python tools/price_table.py fmt")
                    return 1
                print(f"OK: {args.table} is canonical")
                return 0
            args.table.write_text(canonical, encoding="utf-8")
            print(f"wrote {args.table}")
            return 0
        if args.command == "validate":
            load_table(args.table)
            print(f"OK: {args.table} is the draft price table")
            return 0
        table, catalog, table_sha, catalog_sha = _read_pair(args.table, args.catalog)
        errors = drift(table, catalog)
        if args.command == "check" or errors:
            for error in errors:
                print(f"DISAGREE: {error}")
            if errors:
                print(f"FAIL: {len(errors)} disagreement(s) between {args.table.name} and {args.catalog.name}")
                return 1
            if args.command == "check":
                print(f"OK: {args.catalog.name} matches {args.table.name} on payment terms and charged prices")
                return 0
        outputs = render_all(table, catalog, table_sha, catalog_sha)
        stale = []
        for name, body in outputs.items():
            path = args.out / name
            if args.check:
                if not path.is_file() or path.read_text(encoding="utf-8") != body:
                    stale.append(name)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
        if stale:
            print(f"FAIL: stale generated output(s): {', '.join(stale)}; run: python tools/price_table.py generate")
            return 1
        print("OK: generated outputs are current" if args.check else f"wrote {len(outputs)} file(s) to {args.out}")
        return 0
    except (PriceTableError, catalog_mod.CatalogError, KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
