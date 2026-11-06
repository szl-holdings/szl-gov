"""pricing/catalog.yaml must agree with the exported gateway rules and generate every price list.

The committed rules export (pricing/snapshots/) is the 2026-11-06 Monetization
Gateway export with the estate-probe user-agent list redacted; the change log is
the coordinator's record of the three rules disabled at 16:27 UTC. Every mutation
test below changes one fact in a copy of that export and requires the check to
name the disagreement.
"""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pricing_catalog as pc

SNAPSHOTS = ROOT / "pricing" / "snapshots"
RULES = SNAPSHOTS / "monetization-rules-2026-11-06.redacted.json"
CHANGES = SNAPSHOTS / "monetization-changes-2026-11-06.json"
CHAT = "41cee0f88822411baf864bb54e8b4727"
INFERENCE = "6babfd10032746f7863cda066d95125d"
MESH = "94dc6d8169a84173bf0005bea66e50eb"
CATCH_ALL = "5303c2e182cd4d8daf974838f0b14f86"


@pytest.fixture()
def catalog():
    return pc.load_catalog()


@pytest.fixture()
def snapshot():
    return json.loads(RULES.read_text(encoding="utf-8"))


@pytest.fixture()
def changes():
    return json.loads(CHANGES.read_text(encoding="utf-8"))


def rule(snapshot, rule_id, zone="a-11-oy.com"):
    return next(r for r in snapshot[zone]["result"]["rules"] if r["id"] == rule_id)


def joined(errors):
    assert errors, "the check reported no disagreement"
    return "\n".join(errors)


# --- the committed catalog -------------------------------------------------

def test_catalog_is_canonical_yamlite():
    text = pc.CATALOG.read_text(encoding="utf-8")
    assert pc.format_catalog(text) == text
    assert pc.load_yaml(text)["schema"] == "szl.pricing-catalog/v1"


def test_catalog_agrees_with_the_committed_rules_export(catalog, snapshot, changes):
    assert pc.check(catalog, snapshot, changes) == []


def test_catalog_counts_match_the_export(catalog, snapshot, changes):
    zones = pc.apply_changes(pc.snapshot_rules(snapshot), changes)
    assert {z: len(r) for z, r in zones.items()} == {"a-11-oy.com": 15, "a11oy.net": 2, "szlholdings.com": 0}
    assert {z: sum(x["enabled"] for x in r) for z, r in zones.items()} == {
        "a-11-oy.com": 4, "a11oy.net": 0, "szlholdings.com": 0}
    assert [e["amount_atomic"] for e in catalog["charged"]] == [20000, 20000, 50000, 25000]


def test_generated_outputs_are_current(catalog):
    digest = pc.catalog_digest()
    for name, body in pc.render_all(catalog, digest).items():
        assert (pc.GENERATED / name).read_text(encoding="utf-8") == body, f"{name} is stale"


def test_readme_snippet_is_current():
    readme = (ROOT / "pricing" / "README.md").read_text(encoding="utf-8")
    snippet = (pc.GENERATED / "per-call-table.md").read_text(encoding="utf-8")
    assert pc.replace_marked_region(readme, snippet) == readme


def test_manifest_states_only_what_the_rules_charge(catalog):
    manifest = json.loads((pc.GENERATED / "x402-pricing.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "szl.x402-pricing/v2"
    assert "honesty_note" not in manifest  # the old manifest claimed to mirror rules it did not
    assert manifest["source"]["catalog_sha256"] == pc.catalog_digest()
    paid = {s["rule_id"]: s for s in manifest["paid_surfaces"]}
    assert set(paid) == {e["rule_id"] for e in catalog["charged"]}
    for entry in catalog["charged"]:
        assert paid[entry["rule_id"]]["amount_atomic"] == str(entry["amount_atomic"])
    assert {s["price_usd"] for s in paid.values()} == {"0.02", "0.05", "0.025"}
    assert all("price_usd" not in s and "amount_atomic" not in s for s in manifest["not_offered_yet"])
    assert manifest["rule_counts"]["rules_defined"] == 17
    assert manifest["rule_counts"]["rules_enabled"] == 4
    free = [url for group in manifest["free_surfaces"] for url in group["examples"]]
    assert "https://a-11-oy.com/.well-known/x402-pricing.json" in free
    assert "user_agent" not in json.dumps(manifest)


def test_committed_export_carries_no_plain_user_agent_list(snapshot):
    for zone in snapshot.values():
        for r in (zone.get("result") or {}).get("rules") or []:
            shape = pc.describe(r["expression"])
            assert shape["exemption"] == {"count": 6, "sha256": pc.load_catalog()["exemptions"][
                "estate-probe-user-agents"]["sha256"]}
            assert pc.redact_expression(r["expression"]) == r["expression"]  # already redacted


# --- every kind of drift is reported ----------------------------------------

def test_without_the_change_log_the_catch_alls_are_reported(catalog, snapshot):
    text = joined(pc.check(catalog, snapshot, None))
    assert f"{CATCH_ALL}: rule 'Verified bot traffic (x402) - non-API (competitive)' is ENABLED" in text
    assert "https://a-11-oy.com/.well-known/x402-pricing.json (bot=True) must stay free" in text
    assert "https://a11oy.net/ (bot=True) must stay free" in text
    assert "price is ambiguous" in text  # verified bots matched the catch-all and /v1/chat/


def test_price_drift(catalog, snapshot, changes):
    rule(snapshot, CHAT)["price"] = "30000"
    assert f"{CHAT}: price 30000 != catalog 20000" in joined(pc.check(catalog, snapshot, changes))


def test_new_rule(catalog, snapshot, changes):
    extra = copy.deepcopy(rule(snapshot, CHAT))
    extra.update(id="0" * 32, description="New paid path", expression=extra["expression"].replace(
        "/v1/chat/", "/v1/embeddings"))
    snapshot["a-11-oy.com"]["result"]["rules"].append(extra)
    text = joined(pc.check(catalog, snapshot, changes))
    assert "enabled rule 'New paid path' is not in the catalog" in text
    assert "15 defined / 4 enabled, snapshot has 16 / 5" in text


def test_disabled_charged_rule(catalog, snapshot, changes):
    rule(snapshot, CHAT)["enabled"] = False
    text = joined(pc.check(catalog, snapshot, changes))
    assert "catalog charges chat but the rule is disabled" in text
    assert "expected rule 41cee0f88822411baf864bb54e8b4727 to charge it" in text


def test_description_drift(catalog, snapshot, changes):
    rule(snapshot, MESH)["description"] = "Premium API mesh/frontier"
    assert "description 'Premium API mesh/frontier' != catalog" in joined(pc.check(catalog, snapshot, changes))


def test_host_condition_drift(catalog, snapshot, changes):
    r = rule(snapshot, INFERENCE)
    r["expression"] = r["expression"].replace('"inference.a-11-oy.com"', '"api.a-11-oy.com"')
    text = joined(pc.check(catalog, snapshot, changes))
    assert "host condition 'api.a-11-oy.com' != catalog 'inference.a-11-oy.com'" in text
    assert "charges a host outside inference.a-11-oy.com" in text


def test_audience_drift(catalog, snapshot, changes):
    r = rule(snapshot, MESH)
    r["expression"] = r["expression"].replace(" and cf.client.bot", "")
    text = joined(pc.check(catalog, snapshot, changes))
    assert "audience everyone != catalog verified_bots" in text
    assert "catalog says only verified bots pay" in text


def test_path_prefix_drift(catalog, snapshot, changes):
    r = rule(snapshot, CHAT)
    r["expression"] = r["expression"].replace('"/v1/chat/"', '"/v1/chat"')
    assert "path prefixes ['/v1/chat'] != catalog ['/v1/chat/']" in joined(pc.check(catalog, snapshot, changes))


def test_pay_to_drift(catalog, snapshot, changes):
    rule(snapshot, CHAT)["address"] = "0x" + "1" * 40
    assert "!= catalog pay_to" in joined(pc.check(catalog, snapshot, changes))


def test_exemption_list_change(catalog, snapshot, changes):
    r = rule(snapshot, CHAT)
    raw = r["expression"].split(" and not (")[0] + \
        ' and not (http.user_agent contains "synthetic-probe-a" or http.user_agent contains "synthetic-probe-b"))'
    r["expression"] = raw
    assert "user-agent exemption differs" in joined(pc.check(catalog, snapshot, changes))


def test_re_enabled_catch_all_is_reported(catalog, snapshot, changes):
    changes = [c for c in changes if c["rule"] != CATCH_ALL]
    assert "is ENABLED but the catalog lists it as inactive" in joined(pc.check(catalog, snapshot, changes))


def test_a_host_wide_wildcard_rule_cannot_be_catalogued_as_charged(catalog, snapshot, changes):
    changes = [c for c in changes if c["rule"] != CATCH_ALL]  # keep the catch-all enabled
    catch_all = rule(snapshot, CATCH_ALL)
    catalog["inactive_rules"] = [e for e in catalog["inactive_rules"] if e["rule_id"] != CATCH_ALL]
    catalog["charged"].append({**catalog["charged"][0], "id": "catch-all", "rule_id": CATCH_ALL,
                               "rule_description": catch_all["description"], "path_prefixes": ["/"],
                               "audience": "verified_bots", "amount_atomic": 100000,
                               "expression": catch_all["expression"]})
    catalog["zones"][0]["rules_enabled"] = 5
    errors = pc.compare(catalog, pc.apply_changes(pc.snapshot_rules(snapshot), changes))
    assert "the catalog only charges enumerated path prefixes" in joined(errors)


def test_unknown_export_field_fails_closed(catalog, snapshot, changes):
    rule(snapshot, CHAT)["methods"] = ["POST"]
    with pytest.raises(pc.CatalogError, match="export fields differ from the catalog model"):
        pc.check(catalog, snapshot, changes)


def test_change_log_must_match_the_export(catalog, snapshot, changes):
    changes[0]["before_enabled"] = False
    with pytest.raises(pc.CatalogError, match="but the snapshot disagrees"):
        pc.check(catalog, snapshot, changes)


def test_failed_zone_export_fails_closed(catalog, snapshot, changes):
    snapshot["a11oy.net"] = {"status": 403, "result": None, "errors": [{"code": 10000}]}
    with pytest.raises(pc.CatalogError, match="a11oy.net: export failed"):
        pc.check(catalog, snapshot, changes)


# --- redaction ---------------------------------------------------------------

SYNTHETIC = ('(starts_with(http.request.uri.path, "/v1/x/") and not (http.user_agent contains "probe-one" '
             'or http.user_agent contains "probe-two"))')


def test_redaction_removes_the_list_and_keeps_the_meaning():
    redacted = pc.redact_expression(SYNTHETIC)
    assert "probe-one" not in redacted and "probe-two" not in redacted
    assert pc.describe(redacted) == pc.describe(SYNTHETIC)
    assert pc.redact_expression(redacted) == redacted
    for path in ("/v1/x/a", "/v1/y"):
        request = {"host": "a-11-oy.com", "path": path, "user_agent": "Mozilla/5.0", "bot": False}
        assert pc.evaluate(pc.parse_expression(redacted), request) == \
            pc.evaluate(pc.parse_expression(SYNTHETIC), request)


def test_redaction_refuses_an_unrecognised_user_agent_condition():
    with pytest.raises(pc.CatalogError):
        pc.redact_expression('(http.user_agent eq "probe-one")')


def test_redact_cli_writes_a_checkable_export(tmp_path, snapshot):
    raw = copy.deepcopy(snapshot)
    rule(raw, CHAT)["expression"] = SYNTHETIC
    source, output = tmp_path / "raw.json", tmp_path / "redacted.json"
    source.write_text(json.dumps(raw), encoding="utf-8")
    assert pc.main(["redact", str(source), "-o", str(output)]) == 0
    assert "probe-one" not in output.read_text(encoding="utf-8")


# --- expression semantics ----------------------------------------------------

def request(path="/", host="a-11-oy.com", bot=False, user_agent="Mozilla/5.0"):
    return {"host": host, "path": path, "user_agent": user_agent, "bot": bot}


@pytest.mark.parametrize("expression, req, expected", [
    ('http.request.uri.path wildcard r"/*"', request("/anything"), True),
    ('http.request.uri.path wildcard r"/API/*"', request("/api/x"), True),  # wildcard is case-insensitive
    ('starts_with(http.request.uri.path, "/API/")', request("/api/x"), False),  # starts_with is not
    ('http.host eq "inference.a-11-oy.com"', request(host="inference.a-11-oy.com"), True),
    ('http.host eq "inference.a-11-oy.com"', request(host="api.a-11-oy.com"), False),
    ('http.user_agent contains "probe"', request(user_agent="x-probe-y"), True),
    ('cf.client.bot', request(bot=True), True),
    ('not cf.client.bot', request(bot=True), False),
    ('cf.client.bot or cf.client.bot and not cf.client.bot', request(bot=True), True),  # and binds tighter
    ('(cf.client.bot or cf.client.bot) and not cf.client.bot', request(bot=True), False),
])
def test_evaluator(expression, req, expected):
    assert pc.evaluate(pc.parse_expression(expression), req) is expected


@pytest.mark.parametrize("expression", [
    'http.request.uri.path matches "^/v1"',
    'ip.src in {192.0.2.1}',
    'cf.client.bot && http.host eq "a"',
    'lower(http.host) eq "a"',
    'starts_with(http.request.uri.path, "/a"',
])
def test_parser_fails_closed(expression):
    with pytest.raises(pc.CatalogError):
        pc.parse_expression(expression)


def test_describe_rejects_unmodelled_conditions():
    with pytest.raises(pc.CatalogError, match="unsupported rule condition shape"):
        pc.describe('(starts_with(http.request.uri.path, "/a") and http.user_agent eq "x")')


# --- yamlite reader -------------------------------------------------------------

@pytest.mark.parametrize("text, message", [
    ("a: 1\na: 2\n", "duplicate key"),
    ("a:\n\tb: 1\n", "tabs"),
    ("a: &anchor 1\n", "unsupported YAML construct"),
    ("a: 'single'\n", "unsupported YAML construct"),
    ('a: "bad \\n escape"\n', "unsupported escape"),
    ("a:   1\n", "not in canonical yamlite form"),
    ("a: x  \n", "trailing spaces"),
])
def test_yaml_reader_refuses_non_canonical_input(text, message):
    with pytest.raises(pc.CatalogError, match=message):
        pc.load_yaml(text)


def test_yaml_reader_round_trips_yamlite_output():
    data = {"k": "v", "n": 3, "flag": False, "missing": None, "quoted": "a: b",
            "items": [{"id": "x", "tags": ["one", "two"]}, "plain"], "nested": {"deeper": {"x": "/p/"}}}
    assert pc.load_yaml(pc.yamlite.dump(data)) == data


# --- generators ----------------------------------------------------------------

@pytest.mark.parametrize("atomic, text", [
    (1000, "0.001"), (10000, "0.01"), (20000, "0.02"), (25000, "0.025"), (100000, "0.10"),
    (1000000, "1.00"), (123456789, "123.456789")])
def test_usd(atomic, text):
    assert pc.usd(atomic, 1_000_000) == text


def test_marked_region_replacement():
    fragment = f"<!-- {pc.MARK_BEGIN} new -->\nNEW\n<!-- {pc.MARK_END} -->\n"
    page = f"head\n<!-- {pc.MARK_BEGIN} old -->\nOLD\n<!-- {pc.MARK_END} -->\ntail\n"
    assert pc.replace_marked_region(page, fragment) == "head\n" + fragment + "tail\n"
    with pytest.raises(pc.CatalogError):
        pc.replace_marked_region("no markers\n", fragment)
    with pytest.raises(pc.CatalogError):
        pc.replace_marked_region(page + page, fragment)


def test_cli_exit_codes(tmp_path, snapshot):
    assert pc.main(["check", "--rules", str(RULES), "--changes", str(CHANGES)]) == 0
    assert pc.main(["generate", "--check"]) == 0
    assert pc.main(["fmt", "--check"]) == 0
    drifted = tmp_path / "drifted.json"
    rule(snapshot, CHAT)["price"] = "1000000"
    drifted.write_text(json.dumps(snapshot), encoding="utf-8")
    assert pc.main(["check", "--rules", str(drifted), "--changes", str(CHANGES)]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert pc.main(["check", "--rules", str(broken)]) == 2
