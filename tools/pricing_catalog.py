#!/usr/bin/env python3
"""pricing_catalog - the canonical per-call (x402) price catalog for the SZL estate.

``pricing/catalog.yaml`` is the single source of truth for every per-call price
the Cloudflare Monetization Gateway charges on the estate's zones. Every other
price list (the x402 manifest, the per-call table on a-11-oy.com/pricing, README
snippets) is generated from it, and the catalog itself is checked against an
exported snapshot of the gateway rules.

Commands (stdlib only, no network):

  check     Compare the catalog with a rules export (the raw dashboard/API export,
            or the redacted copy under pricing/snapshots/), after applying an
            optional change log. Exit 1 on any disagreement.
  generate  Write the derived artifacts under pricing/generated/, or with
            --check fail when the committed ones are stale.
  redact    Replace the estate-probe user-agent exemption list in a raw export
            with a digest placeholder, so the export can be committed without
            publishing a way to skip payment.
  fmt       Rewrite catalog.yaml in canonical yamlite form, or --check it.

Proof boundary: ``check`` proves that the catalog agrees with the exported rules
it is given. It does not prove that the export is current, that the gateway
settles payments, or that any origin serves a paying caller. The rule
expressions are evaluated by a small interpreter that implements only the
operators these rules use; any other construct fails closed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import yamlite  # sibling module; the path is set above

CATALOG = ROOT / "pricing" / "catalog.yaml"
GENERATED = ROOT / "pricing" / "generated"
OUTPUTS = ("x402-pricing.json", "per-call-table.html", "per-call-table.md", "rule-count.md")
MARK_BEGIN = "szl:x402-per-call:begin"
MARK_END = "szl:x402-per-call:end"
PROBE_USER_AGENT = "szl-pricing-catalog-check/1"
MIN_ATOMIC, MAX_ATOMIC = 1_000, 100_000_000  # Monetization Gateway limits ($0.001 .. $100)
RULE_KEYS = frozenset({"id", "description", "enabled", "expression", "price", "address", "scheme"})
HTTP_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
AUDIENCES = frozenset({"everyone", "verified_bots"})
SCHEMES = frozenset({"exact", "upto"})


class CatalogError(ValueError):
    """The catalog, a snapshot or an expression cannot be read safely."""


# ---------------------------------------------------------------------------
# Canonical yamlite reader (the inverse of tools/yamlite.py for the subset the
# catalog uses: block mappings, block sequences, plain and double-quoted
# scalars, ints and booleans). Anything else is refused.
# ---------------------------------------------------------------------------
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def _scalar(token: str, where: str):
    if token == "UNKNOWN":
        return None
    if token in ("true", "false"):
        return token == "true"
    if token == "{}":
        return {}
    if token == "[]":
        return []
    if token.startswith('"'):
        if len(token) < 2 or not token.endswith('"'):
            raise CatalogError(f"{where}: unterminated quoted scalar")
        out, i, body = [], 0, token[1:-1]
        while i < len(body):
            char = body[i]
            if char == "\\":
                if i + 1 >= len(body) or body[i + 1] not in '\\"':
                    raise CatalogError(f"{where}: unsupported escape in quoted scalar")
                out.append(body[i + 1])
                i += 2
                continue
            if char == '"':
                raise CatalogError(f"{where}: unescaped quote in quoted scalar")
            out.append(char)
            i += 1
        return "".join(out)
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if token.startswith(("|", ">", "&", "*", "!", "[", "{", "'")):
        raise CatalogError(f"{where}: unsupported YAML construct {token[:12]!r}")
    return token


def _is_key_line(text: str) -> bool:
    if text.endswith(":") and _KEY.fullmatch(text[:-1]):
        return True
    key, sep, rest = text.partition(": ")
    return bool(sep and rest and _KEY.fullmatch(key))


def _split_key(text: str, where: str):
    if text.endswith(":") and _KEY.fullmatch(text[:-1]):
        return text[:-1], None
    key, sep, rest = text.partition(": ")
    if not sep or not _KEY.fullmatch(key) or not rest:
        raise CatalogError(f"{where}: expected 'key: value', got {text[:40]!r}")
    return key, rest


def _block(rows, i, indent):
    if rows[i][1] == "-" or rows[i][1].startswith("- "):
        return _sequence(rows, i, indent)
    return _mapping(rows, i, indent)


def _mapping(rows, i, indent):
    out = {}
    while i < len(rows) and rows[i][0] == indent and not (rows[i][1] == "-" or rows[i][1].startswith("- ")):
        where = f"line {rows[i][2]}"
        key, rest = _split_key(rows[i][1], where)
        if key in out:
            raise CatalogError(f"{where}: duplicate key {key!r}")
        i += 1
        if rest is None:
            if i >= len(rows) or rows[i][0] <= indent:
                raise CatalogError(f"{where}: key {key!r} has no value")
            out[key], i = _block(rows, i, rows[i][0])
        else:
            out[key] = _scalar(rest, where)
    if i < len(rows) and rows[i][0] > indent:
        raise CatalogError(f"line {rows[i][2]}: unexpected indentation")
    return out, i


def _sequence(rows, i, indent):
    out = []
    while i < len(rows) and rows[i][0] == indent and (rows[i][1] == "-" or rows[i][1].startswith("- ")):
        where = f"line {rows[i][2]}"
        if rows[i][1] == "-":
            i += 1
            if i >= len(rows) or rows[i][0] <= indent:
                raise CatalogError(f"{where}: empty sequence item")
            item, i = _block(rows, i, rows[i][0])
            out.append(item)
            continue
        content = rows[i][1][2:]
        if _is_key_line(content):
            rows[i] = (indent + 2, content, rows[i][2])
            item, i = _mapping(rows, i, indent + 2)
        else:
            item, i = _scalar(content, where), i + 1
        out.append(item)
    if i < len(rows) and rows[i][0] > indent:
        raise CatalogError(f"line {rows[i][2]}: unexpected indentation")
    return out, i


def split_header(text: str):
    """Return (comment header, YAML body). The header is leading '#' lines."""
    lines = text.split("\n")
    n = 0
    while n < len(lines) and (lines[n].startswith("#") or lines[n] == ""):
        n += 1
    return "\n".join(lines[:n]).strip("\n"), "\n".join(lines[n:])


def load_yaml(text: str):
    """Parse canonical yamlite text and require that it re-emits byte-identically."""
    _header, body = split_header(text)
    rows = []
    for number, line in enumerate(body.split("\n"), start=1):
        if line == "":
            continue
        if "\t" in line or line != line.rstrip():
            raise CatalogError(f"line {number}: tabs or trailing spaces are not canonical")
        rows.append((len(line) - len(line.lstrip(" ")), line.lstrip(" "), number))
    if not rows:
        raise CatalogError("empty document")
    data, end = _block(rows, 0, 0)
    if end != len(rows):
        raise CatalogError(f"line {rows[end][2]}: trailing content")
    if yamlite.dump(data) != body:
        raise CatalogError("document is not in canonical yamlite form; run: python tools/pricing_catalog.py fmt")
    return data


def format_catalog(text: str) -> str:
    """Return the canonical form of a catalog text (header comments kept)."""
    header, body = split_header(text)
    rows = [(len(line) - len(line.lstrip(" ")), line.lstrip(" ").rstrip(), number)
            for number, line in enumerate(body.split("\n"), start=1) if line.strip()]
    if not rows:
        raise CatalogError("empty document")
    data, end = _block(rows, 0, 0)
    if end != len(rows):
        raise CatalogError(f"line {rows[end][2]}: trailing content")
    canonical = yamlite.dump(data)
    return (header + "\n\n" + canonical) if header else canonical


# ---------------------------------------------------------------------------
# Rule expressions: tokenizer, parser, evaluator and structural description.
# Only the operators the exported rules use are implemented.
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r'\s*(?:(?P<lp>\()|(?P<rp>\))|(?P<comma>,)|r"(?P<raw>[^"]*)"'
                    r'|"(?P<str>(?:[^"\\]|\\.)*)"|(?P<word>[A-Za-z_][A-Za-z0-9_.]*))')
FIELDS = {"http.request.uri.path": "path", "http.host": "host", "http.user_agent": "user_agent",
          "cf.client.bot": "bot"}
STRING_FIELDS = frozenset({"http.request.uri.path", "http.host", "http.user_agent"})
COMPARISONS = frozenset({"eq", "contains", "wildcard"})


def _tokens(expression: str):
    out, pos = [], 0
    while pos < len(expression):
        if expression[pos:].strip() == "":
            break
        match = _TOKEN.match(expression, pos)
        if not match or match.end() == pos:
            raise CatalogError(f"unsupported expression syntax at {expression[pos:pos + 24]!r}")
        pos = match.end()
        kind = match.lastgroup
        if kind == "str":
            value = re.sub(r"\\(.)", r"\1", match.group("str"))
            out.append(("str", value))
        elif kind == "raw":
            out.append(("str", match.group("raw")))
        elif kind == "word":
            out.append(("word", match.group("word")))
        else:
            out.append((kind, match.group(kind)))
    return out


class _Parser:
    def __init__(self, expression: str):
        self.tokens = _tokens(expression)
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, kind, value=None):
        token = self.peek()
        if token[0] != kind or (value is not None and token[1] != value):
            raise CatalogError(f"expected {value or kind}, found {token[1]!r}")
        self.pos += 1
        return token[1]

    def parse(self):
        node = self.orexpr()
        if self.pos != len(self.tokens):
            raise CatalogError(f"unexpected token {self.peek()[1]!r}")
        return node

    def orexpr(self):
        parts = [self.andexpr()]
        while self.peek() == ("word", "or"):
            self.pos += 1
            parts.append(self.andexpr())
        return parts[0] if len(parts) == 1 else ("or", parts)

    def andexpr(self):
        parts = [self.unary()]
        while self.peek() == ("word", "and"):
            self.pos += 1
            parts.append(self.unary())
        return parts[0] if len(parts) == 1 else ("and", parts)

    def unary(self):
        if self.peek() == ("word", "not"):
            self.pos += 1
            return ("not", self.unary())
        return self.primary()

    def primary(self):
        kind, value = self.peek()
        if kind == "lp":
            self.pos += 1
            node = self.orexpr()
            self.take("rp")
            return node
        if kind != "word":
            raise CatalogError(f"unexpected token {value!r}")
        self.pos += 1
        if value == "starts_with":
            self.take("lp")
            field = self.take("word")
            self.take("comma")
            literal = self.take("str")
            self.take("rp")
            if field not in STRING_FIELDS:
                raise CatalogError(f"unsupported field in starts_with: {field}")
            return ("starts_with", field, literal)
        if value not in FIELDS:
            raise CatalogError(f"unsupported field or function: {value}")
        if value == "cf.client.bot":
            return ("field", value)
        operator = self.take("word")
        if operator not in COMPARISONS:
            raise CatalogError(f"unsupported operator: {operator}")
        return ("cmp", operator, value, self.take("str"))


def parse_expression(expression: str):
    return _Parser(expression).parse()


def _wildcard(pattern: str, value: str) -> bool:
    regex = "".join(".*" if char == "*" else re.escape(char) for char in pattern)
    return re.fullmatch(regex, value, re.IGNORECASE | re.DOTALL) is not None


def evaluate(node, request: dict) -> bool:
    kind = node[0]
    if kind == "or":
        return any(evaluate(part, request) for part in node[1])
    if kind == "and":
        return all(evaluate(part, request) for part in node[1])
    if kind == "not":
        return not evaluate(node[1], request)
    if kind == "field":
        return bool(request[FIELDS[node[1]]])
    if kind == "starts_with":
        return request[FIELDS[node[1]]].startswith(node[2])
    _, operator, field, literal = node
    value = request[FIELDS[field]]
    if operator == "eq":
        return value == literal
    if operator == "contains":
        return literal in value
    return _wildcard(literal, value)


def _conjuncts(node):
    if node[0] == "and":
        return [leaf for part in node[1] for leaf in _conjuncts(part)]
    return [node]


def _disjuncts(node):
    if node[0] == "or":
        return [leaf for part in node[1] for leaf in _disjuncts(part)]
    return [node]


def _is_ua_contains(node) -> bool:
    return node[0] == "cmp" and node[1] == "contains" and node[2] == "http.user_agent"


REDACTED_UA = re.compile(r"szl-redacted:estate-probe-user-agents:n=(\d+):sha256=([0-9a-f]{64})")


def exemption_fingerprint(literals) -> dict:
    """Count and digest of a user-agent exemption list (raw or redacted)."""
    literals = list(literals)
    if len(literals) == 1 and REDACTED_UA.fullmatch(literals[0]):
        match = REDACTED_UA.fullmatch(literals[0])
        return {"count": int(match.group(1)), "sha256": match.group(2)}
    if any(REDACTED_UA.search(literal) for literal in literals):
        raise CatalogError("redaction placeholder mixed with plain user-agent literals")
    unique = sorted(set(literals))
    return {"count": len(unique), "sha256": hashlib.sha256("\n".join(unique).encode("utf-8")).hexdigest()}


def describe(expression: str) -> dict:
    """Structural reading of one rule expression. Unknown shapes fail closed."""
    out = {"host": None, "path_prefixes": [], "path_wildcard": None, "path_excludes": [],
           "audience": "everyone", "exemption": None}
    for part in _conjuncts(parse_expression(expression)):
        disjuncts = _disjuncts(part)
        if part == ("field", "cf.client.bot"):
            out["audience"] = "verified_bots"
        elif part[0] == "cmp" and part[1] == "eq" and part[2] == "http.host" and out["host"] is None:
            out["host"] = part[3]
        elif part[0] == "cmp" and part[1] == "wildcard" and part[2] == "http.request.uri.path" \
                and out["path_wildcard"] is None:
            out["path_wildcard"] = part[3]
        elif all(d[0] == "starts_with" and d[1] == "http.request.uri.path" for d in disjuncts):
            out["path_prefixes"].extend(d[2] for d in disjuncts)
        elif part[0] == "not" and part[1][0] == "starts_with" and part[1][1] == "http.request.uri.path":
            out["path_excludes"].append(part[1][2])
        elif part[0] == "not" and all(_is_ua_contains(d) for d in _disjuncts(part[1])) \
                and out["exemption"] is None:
            out["exemption"] = exemption_fingerprint(d[3] for d in _disjuncts(part[1]))
        else:
            raise CatalogError(f"unsupported rule condition shape: {part!r}"[:200])
    return out


# ---------------------------------------------------------------------------
# Snapshots: redaction, change log, effective rule set.
# ---------------------------------------------------------------------------
_UA_CLAUSE = re.compile(r'not \(http\.user_agent contains "(?:[^"\\]|\\.)*"'
                        r'(?: or http\.user_agent contains "(?:[^"\\]|\\.)*")*\)')


def _abstract_exemptions(node, fingerprints: list):
    """Replace each user-agent exemption clause by a marker, collecting its fingerprint."""
    kind = node[0]
    if kind == "not" and all(_is_ua_contains(d) for d in _disjuncts(node[1])):
        fingerprints.append(exemption_fingerprint(d[3] for d in _disjuncts(node[1])))
        return ("ua-exemption",)
    if kind in ("and", "or"):
        return (kind, [_abstract_exemptions(part, fingerprints) for part in node[1]])
    if kind == "not":
        return ("not", _abstract_exemptions(node[1], fingerprints))
    return node


def redact_expression(expression: str) -> str:
    """Swap each exemption list for a count+digest placeholder; refuse if meaning could change."""
    def replace(match):
        literals = [re.sub(r"\\(.)", r"\1", lit) for lit in
                    re.findall(r'contains "((?:[^"\\]|\\.)*)"', match.group(0))]
        fingerprint = exemption_fingerprint(literals)
        token = f"szl-redacted:estate-probe-user-agents:n={fingerprint['count']}:sha256={fingerprint['sha256']}"
        return f'not (http.user_agent contains "{token}")'

    redacted = _UA_CLAUSE.sub(replace, expression)
    for literal in re.findall(r'http\.user_agent\s+\w+\s+"((?:[^"\\]|\\.)*)"', redacted):
        if not REDACTED_UA.fullmatch(literal):
            raise CatalogError("a user-agent condition was not recognised for redaction; refusing to emit it")
    before, after = [], []
    if _abstract_exemptions(parse_expression(expression), before) != \
            _abstract_exemptions(parse_expression(redacted), after) or before != after:
        raise CatalogError("redaction changed the meaning of a rule")
    return redacted


def redact_snapshot(snapshot: dict) -> dict:
    out = copy.deepcopy(snapshot)
    for entry in out.values():
        for rule in (entry.get("result") or {}).get("rules") or []:
            rule["expression"] = redact_expression(rule["expression"])
    return out


def snapshot_rules(snapshot: dict) -> dict:
    """{zone: [rule, ...]} from an export; a 404/10005 zone has no rules."""
    if not isinstance(snapshot, dict) or not snapshot:
        raise CatalogError("rules snapshot must be a non-empty object keyed by zone")
    zones = {}
    for zone, entry in snapshot.items():
        status = entry.get("status") if isinstance(entry, dict) else None
        if status == 200 and not entry.get("errors"):
            rules = (entry.get("result") or {}).get("rules")
            if not isinstance(rules, list):
                raise CatalogError(f"{zone}: export has no rules list")
            for rule in rules:
                extra = set(rule) - RULE_KEYS
                missing = RULE_KEYS - set(rule)
                if extra or missing:
                    raise CatalogError(f"{zone}/{rule.get('id')}: export fields differ from the catalog model "
                                       f"(extra {sorted(extra)}, missing {sorted(missing)})")
            zones[zone] = copy.deepcopy(rules)
        elif status == 404 and [e.get("code") for e in entry.get("errors") or []] == [10005]:
            zones[zone] = []
        else:
            raise CatalogError(f"{zone}: export failed (status {status}); cannot verify")
    return zones


def apply_changes(zones: dict, changes: list) -> dict:
    """Apply a change log of enable/disable PATCHes in timestamp order."""
    zones = copy.deepcopy(zones)
    for change in sorted(changes, key=lambda c: c["ts"]):
        if change.get("patch_status") != 200 or change.get("patch_errors"):
            raise CatalogError(f"change {change.get('rule')} did not apply (status {change.get('patch_status')})")
        rules = [r for r in zones.get(change["zone"], []) if r["id"] == change["rule"]]
        if len(rules) != 1:
            raise CatalogError(f"change {change['rule']} names a rule absent from {change['zone']}")
        if rules[0]["enabled"] != change["before_enabled"]:
            raise CatalogError(f"change {change['rule']} expected enabled={change['before_enabled']} "
                               "but the snapshot disagrees")
        if rules[0]["description"] != change["description"]:
            raise CatalogError(f"change {change['rule']} description differs from the snapshot")
        rules[0]["enabled"] = change["after_enabled"]
    return zones


# ---------------------------------------------------------------------------
# Catalog validation and the consistency check.
# ---------------------------------------------------------------------------
def load_catalog(path: Path = CATALOG) -> dict:
    catalog = load_yaml(path.read_text(encoding="utf-8"))
    validate_catalog(catalog)
    return catalog


def validate_catalog(c: dict) -> None:
    def need(condition, message):
        if not condition:
            raise CatalogError(message)

    need(c.get("schema") == "szl.pricing-catalog/v1", "schema must be szl.pricing-catalog/v1")
    for key in ("as_of", "sources", "policy", "payment", "contact", "exemptions", "zones", "charged",
                "inactive_rules", "not_offered_yet", "free", "limits", "presentation"):
        need(key in c, f"catalog is missing {key}")
    need(c["payment"].get("atomic_per_usd") == 1_000_000, "atomic_per_usd must be 1000000 (USDC, 6 decimals)")
    for key in ("manifest_url", "as_of_human", "page_intro"):
        need(isinstance(c["presentation"].get(key), str), f"presentation.{key} must be text")
    for name, exemption in c["exemptions"].items():
        need(isinstance(exemption.get("count"), int) and re.fullmatch(r"[0-9a-f]{64}", exemption.get("sha256", "")),
             f"exemption {name} needs count and sha256")
    zones = {z["zone"]: z for z in c["zones"]}
    need(len(zones) == len(c["zones"]), "duplicate zone")
    for zone in c["zones"]:
        need(all(h == zone["zone"] or h.endswith("." + zone["zone"]) for h in zone.get("probe_hosts") or [None]),
             f"{zone['zone']}: probe hosts must be inside the zone")
    for group in c["free"]:
        need(group["probes"] and all(re.fullmatch(r"https://[^/]+/.*", u) for u in group["probes"]),
             f"free surface {group['surface']!r} needs https probe URLs")
    need(all(isinstance(text, str) for text in c["limits"]), "limits must be text")
    ids, rule_ids = set(), set()
    for entry in c["charged"]:
        need(entry["id"] not in ids, f"duplicate entry id {entry['id']}")
        ids.add(entry["id"])
        need(entry["rule_id"] not in rule_ids, f"rule {entry['rule_id']} listed twice")
        rule_ids.add(entry["rule_id"])
        need(entry["zone"] in zones, f"{entry['id']}: unknown zone")
        need(entry["host"] == "*" or entry["host"] == entry["zone"] or entry["host"].endswith("." + entry["zone"]),
             f"{entry['id']}: host outside its zone")
        need(entry["path_prefixes"] and all(p.startswith("/") for p in entry["path_prefixes"]),
             f"{entry['id']}: path prefixes must be absolute")
        need(set(entry["methods"]) <= HTTP_METHODS and entry["methods"], f"{entry['id']}: bad methods")
        need(entry["audience"] in AUDIENCES, f"{entry['id']}: bad audience")
        need(entry["scheme"] in SCHEMES, f"{entry['id']}: bad scheme")
        need(isinstance(entry["amount_atomic"], int) and MIN_ATOMIC <= entry["amount_atomic"] <= MAX_ATOMIC,
             f"{entry['id']}: amount outside the gateway's $0.001-$100 range")
        need(entry["exemption"] in c["exemptions"], f"{entry['id']}: unknown exemption")
    for entry in c["inactive_rules"]:
        need(entry["rule_id"] not in rule_ids, f"rule {entry['rule_id']} listed twice")
        rule_ids.add(entry["rule_id"])
        need(entry["zone"] in zones, f"inactive {entry['rule_id']}: unknown zone")
    inactive = {e["rule_id"] for e in c["inactive_rules"]}
    for entry in c["not_offered_yet"]:
        need(entry["id"] not in ids, f"duplicate entry id {entry['id']}")
        ids.add(entry["id"])
        need(entry["status"] == "not offered yet", f"{entry['id']}: status must be 'not offered yet'")
        need("amount_atomic" not in entry and "price_usd" not in entry, f"{entry['id']}: carries a price")
        need(set(entry["inactive_rule_ids"]) <= inactive, f"{entry['id']}: names a rule not listed as inactive")


def _request(url: str, bot: bool) -> dict:
    match = re.fullmatch(r"https://([^/]+)(/.*)", url)
    if not match:
        raise CatalogError(f"probe URL must be https://host/path: {url}")
    return {"host": match.group(1), "path": match.group(2), "user_agent": PROBE_USER_AGENT, "bot": bot}


def _zone_of(host: str, zones) -> str | None:
    for zone in zones:
        if host == zone or host.endswith("." + zone):
            return zone
    return None


def compare(catalog: dict, zones_rules: dict) -> list[str]:
    """Every disagreement between the catalog and an effective rule set."""
    errors = []
    by_id = {(z, r["id"]): r for z, rules in zones_rules.items() for r in rules}
    listed = {(e["zone"], e["rule_id"]): ("charged", e) for e in catalog["charged"]}
    listed.update({(e["zone"], e["rule_id"]): ("inactive", e) for e in catalog["inactive_rules"]})
    pay_to = catalog["payment"]["pay_to"]

    zones = {z["zone"]: z for z in catalog["zones"]}
    if set(zones) != set(zones_rules):
        errors.append(f"zones differ: catalog {sorted(zones)} vs snapshot {sorted(zones_rules)}")
    for zone, rules in zones_rules.items():
        if zone in zones:
            defined, enabled = len(rules), sum(1 for r in rules if r["enabled"])
            if (zones[zone]["rules_defined"], zones[zone]["rules_enabled"]) != (defined, enabled):
                errors.append(f"{zone}: catalog says {zones[zone]['rules_defined']} defined / "
                              f"{zones[zone]['rules_enabled']} enabled, snapshot has {defined} / {enabled}")
    for key, rule in by_id.items():
        if key not in listed:
            state = "enabled" if rule["enabled"] else "disabled"
            errors.append(f"{key[0]}/{key[1]}: {state} rule {rule['description']!r} is not in the catalog")
    for key, (kind, entry) in listed.items():
        rule = by_id.get(key)
        if rule is None:
            errors.append(f"{key[0]}/{key[1]}: catalog lists a rule the snapshot does not contain")
            continue
        if rule["description"] != entry["rule_description"]:
            errors.append(f"{key[1]}: description {rule['description']!r} != catalog {entry['rule_description']!r}")
        if kind == "inactive":
            if rule["enabled"]:
                errors.append(f"{key[1]}: rule {rule['description']!r} is ENABLED but the catalog lists it as inactive")
            continue
        if not rule["enabled"]:
            errors.append(f"{key[1]}: catalog charges {entry['id']} but the rule is disabled")
        if rule["price"] != str(entry["amount_atomic"]):
            errors.append(f"{key[1]}: price {rule['price']} != catalog {entry['amount_atomic']}")
        if rule["scheme"] != entry["scheme"]:
            errors.append(f"{key[1]}: scheme {rule['scheme']} != catalog {entry['scheme']}")
        if rule["address"] != pay_to:
            errors.append(f"{key[1]}: pays {rule['address']} != catalog pay_to {pay_to}")
        try:
            redacted = redact_expression(rule["expression"])
            shape = describe(redacted)
        except CatalogError as exc:
            errors.append(f"{key[1]}: {exc}")
            continue
        if redacted != entry["expression"]:
            errors.append(f"{key[1]}: expression differs from the catalog")
        expected_host = None if entry["host"] == "*" else entry["host"]
        if shape["host"] != expected_host:
            errors.append(f"{key[1]}: host condition {shape['host']!r} != catalog {entry['host']!r}")
        if shape["path_prefixes"] != entry["path_prefixes"]:
            errors.append(f"{key[1]}: path prefixes {shape['path_prefixes']} != catalog {entry['path_prefixes']}")
        if shape["path_wildcard"] or shape["path_excludes"]:
            errors.append(f"{key[1]}: enabled rule matches a path wildcard/exclusion; the catalog only "
                          "charges enumerated path prefixes")
        if shape["audience"] != entry["audience"]:
            errors.append(f"{key[1]}: audience {shape['audience']} != catalog {entry['audience']}")
        expected = catalog["exemptions"][entry["exemption"]]
        if shape["exemption"] != {"count": expected["count"], "sha256": expected["sha256"]}:
            errors.append(f"{key[1]}: user-agent exemption differs from catalog exemption {entry['exemption']!r}")

    errors.extend(_probe(catalog, zones_rules))
    return errors


def _probe(catalog: dict, zones_rules: dict) -> list[str]:
    """Behavioural cross-check: synthesize requests and evaluate the enabled rules."""
    errors, enabled = [], []
    for zone, rules in zones_rules.items():
        for rule in rules:
            if rule["enabled"]:
                try:
                    enabled.append((zone, rule, parse_expression(rule["expression"])))
                except CatalogError as exc:
                    errors.append(f"{rule['id']}: {exc}")

    def charged_by(url: str, bot: bool):
        request = _request(url, bot)
        zone = _zone_of(request["host"], zones_rules)
        return [rule for z, rule, tree in enabled if z == zone and evaluate(tree, request)]

    probe_hosts = {z["zone"]: z["probe_hosts"] for z in catalog["zones"]}
    for entry in catalog["charged"]:
        hosts = probe_hosts[entry["zone"]] if entry["host"] == "*" else [entry["host"]]
        for host in hosts:
            for prefix in entry["path_prefixes"]:
                url = f"https://{host}{prefix}probe"
                for bot in (True, False):
                    hits = charged_by(url, bot)
                    should_pay = bot or entry["audience"] == "everyone"
                    if len(hits) > 1:
                        errors.append(f"{url} (bot={bot}): {len(hits)} enabled rules match; the price is ambiguous")
                    elif should_pay and not (hits and hits[0]["id"] == entry["rule_id"]):
                        errors.append(f"{url} (bot={bot}): expected rule {entry['rule_id']} to charge it, "
                                      f"got {[h['id'] for h in hits]}")
                    elif not should_pay and hits:
                        errors.append(f"{url} (bot={bot}): catalog says only verified bots pay, "
                                      f"but {[h['id'] for h in hits]} charge it")
        if entry["host"] != "*":
            for host in probe_hosts[entry["zone"]]:
                if host != entry["host"]:
                    for prefix in entry["path_prefixes"]:
                        url = f"https://{host}{prefix}probe"
                        if any(h["id"] == entry["rule_id"] for h in charged_by(url, True)):
                            errors.append(f"{url}: rule {entry['rule_id']} charges a host outside {entry['host']}")
    for group in catalog["free"]:
        for url in group["probes"]:
            for bot in (True, False):
                hits = charged_by(url, bot)
                if hits:
                    errors.append(f"{url} (bot={bot}) must stay free ({group['surface']}), but "
                                  f"{[h['description'] for h in hits]} charge it")
    return errors


def check(catalog: dict, snapshot: dict, changes: list | None) -> list[str]:
    zones = snapshot_rules(snapshot)
    if changes:
        zones = apply_changes(zones, changes)
    return compare(catalog, zones)


# ---------------------------------------------------------------------------
# Generators.
# ---------------------------------------------------------------------------
def usd(atomic: int, per_usd: int) -> str:
    whole, frac = divmod(atomic, per_usd)
    digits = str(frac).rjust(len(str(per_usd)) - 1, "0").rstrip("0")
    return f"{whole}.{digits.ljust(2, '0')}"


def catalog_digest(path: Path = CATALOG) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _host_label(entry: dict) -> str:
    return f"any {entry['zone']} host" if entry["host"] == "*" else entry["host"]


def _who_pays(entry: dict) -> str:
    return "everyone" if entry["audience"] == "everyone" else "Cloudflare-verified bots only"


def build_manifest(c: dict, digest: str) -> dict:
    per_usd = c["payment"]["atomic_per_usd"]
    zones = [{"zone": z["zone"], "rules_defined": z["rules_defined"], "rules_enabled": z["rules_enabled"]}
             for z in c["zones"]]
    return {
        "schema": "szl.x402-pricing/v2",
        "protocol": "x402",
        "x402_version": c["payment"]["x402_version"],
        "as_of": c["as_of"],
        "source": {
            "catalog": c["sources"]["catalog_url"],
            "catalog_sha256": digest,
            "generator": "szl-gov tools/pricing_catalog.py",
            "rules_checked_against": c["sources"]["rules_checked_against"],
        },
        "authority": c["sources"]["authority"],
        "payment": {key: c["payment"][key] for key in ("network", "asset", "asset_name", "atomic_per_usd",
                                                      "pay_to", "max_timeout_seconds")},
        "seller": {"contact": c["contact"]},
        "paid_surfaces": [{
            "id": e["id"],
            "surface": e["surface"],
            "zone": e["zone"],
            "host": e["host"],
            "host_note": ("the rule has no host condition: every proxied hostname in the zone"
                          if e["host"] == "*" else "the rule matches this hostname only"),
            "path_prefixes": e["path_prefixes"],
            "methods": e["methods"],
            "methods_basis": c["sources"]["methods_basis"][e["methods_basis"]],
            "audience": e["audience"],
            "scheme": e["scheme"],
            "amount_atomic": str(e["amount_atomic"]),
            "price_usd": usd(e["amount_atomic"], per_usd),
            "rule_id": e["rule_id"],
            "rule_description": e["rule_description"],
        } for e in c["charged"]],
        "not_offered_yet": [{
            "id": e["id"],
            "surface": e["surface"],
            "path_prefixes": e["path_prefixes"],
            "status": e["status"],
            "note": e["note"],
        } for e in c["not_offered_yet"]],
        "free_surfaces": [{"surface": g["surface"], "examples": g["probes"]} for g in c["free"]],
        "rule_counts": {
            "as_of": c["as_of"],
            "zones": zones,
            "rules_defined": sum(z["rules_defined"] for z in zones),
            "rules_enabled": sum(z["rules_enabled"] for z in zones),
        },
        "limits": c["limits"],
    }


def render_manifest(c: dict, digest: str) -> str:
    return json.dumps(build_manifest(c, digest), indent=2, ensure_ascii=True) + "\n"


def rule_count_sentence(c: dict) -> str:
    total = sum(z["rules_defined"] for z in c["zones"])
    enabled = sum(z["rules_enabled"] for z in c["zones"])
    parts = "; ".join(f"{z['zone']}: {z['rules_enabled']} of {z['rules_defined']}"
                      for z in c["zones"] if z["rules_defined"])
    return f"{enabled} of {total} gateway rules enabled ({parts}), per {c['sources']['rules_checked_against']}."


def _stamp(digest: str) -> str:
    return (f"generated by szl-gov tools/pricing_catalog.py from pricing/catalog.yaml "
            f"sha256={digest}; do not edit by hand")


def render_html(c: dict, digest: str) -> str:
    def e(text: str) -> str:  # text node: quotes need no escaping
        return html.escape(text, quote=False)

    a = html.escape  # attribute value
    per_usd = c["payment"]["atomic_per_usd"]
    rows = []
    for entry in c["charged"]:
        prefixes = "<br>".join(f"<code>{e(p)}</code>" for p in entry["path_prefixes"])
        rows.append(
            f'        <tr data-entry-id="{a(entry["id"])}" data-rule-id="{a(entry["rule_id"])}" '
            f'data-amount-atomic="{entry["amount_atomic"]}">\n'
            f'          <th scope="row">{prefixes} <span class="no">({e(entry["surface"])})</span></th>\n'
            f'          <td data-label="Host">{e(_host_label(entry))}</td>\n'
            f'          <td data-label="Who pays">{e(_who_pays(entry))}</td>\n'
            f'          <td data-label="Price per request">${usd(entry["amount_atomic"], per_usd)} USDC'
            f' ({entry["amount_atomic"]} atomic, {e(entry["scheme"])})</td>\n'
            f'          <td data-label="Status" class="yes">Charged</td>\n'
            "        </tr>")
    for entry in c["not_offered_yet"]:
        prefixes = "<br>".join(f"<code>{e(p)}</code>" for p in entry["path_prefixes"])
        rows.append(
            f'        <tr data-entry-id="{a(entry["id"])}" data-status="not-offered-yet">\n'
            f'          <th scope="row">{prefixes} <span class="no">({e(entry["surface"])})</span></th>\n'
            '          <td data-label="Host">&mdash;</td>\n'
            '          <td data-label="Who pays">&mdash;</td>\n'
            '          <td data-label="Price per request">&mdash;</td>\n'
            '          <td data-label="Status" class="no">Not offered yet</td>\n'
            "        </tr>")
    limits = " ".join(e(text) for text in c["limits"])
    return (
        f"<!-- {MARK_BEGIN} {_stamp(digest)} -->\n"
        '  <section class="compare wrap" id="per-call-prices">\n'
        "    <h2>Per-call API prices (x402)</h2>\n"
        f'    <p class="sub">{e(c["presentation"]["page_intro"])} Prices as of {e(c["presentation"]["as_of_human"])}. '
        'Machine-readable copy: '
        '<a href="/.well-known/x402-pricing.json">/.well-known/x402-pricing.json</a>.</p>\n'
        '    <div class="tablecard">\n'
        '      <div class="tablewrap">\n'
        "      <table>\n"
        "        <thead>\n"
        '          <tr><th scope="col">Path prefix</th><th scope="col">Host</th><th scope="col">Who pays</th>'
        '<th scope="col">Price per request</th><th scope="col">Status</th></tr>\n'
        "        </thead>\n"
        "        <tbody>\n" + "\n".join(rows) + "\n"
        "        </tbody>\n"
        "      </table>\n"
        "      </div>\n"
        "    </div>\n"
        f'    <div class="note"><b>Owner policy ({e(c["policy"]["decided_on"])}).</b> {e(c["policy"]["statement"])} '
        f"<b>Limits.</b> {limits}</div>\n"
        "  </section>\n"
        f"<!-- {MARK_END} -->\n"
    )


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(c: dict, digest: str) -> str:
    per_usd = c["payment"]["atomic_per_usd"]
    lines = [
        f"<!-- {MARK_BEGIN} {_stamp(digest)} -->",
        ("Per-call prices the Cloudflare Monetization Gateway charges, from the canonical catalog "
         f"([szl-gov `pricing/catalog.yaml`]({c['sources']['catalog_url']})), checked against "
         f"{c['sources']['rules_checked_against']}."),
        "",
        "| Path prefix | Host | Who pays | Price per request | Gateway rule |",
        "|---|---|---|---|---|",
    ]
    for entry in c["charged"]:
        prefixes = ", ".join(f"`{p}`" for p in entry["path_prefixes"])
        lines.append(f"| {prefixes} ({_md_cell(entry['surface'])}) | {_md_cell(_host_label(entry))} | {_who_pays(entry)} | "
                     f"${usd(entry['amount_atomic'], per_usd)} USDC ({entry['amount_atomic']} atomic, "
                     f"{entry['scheme']}) | {_md_cell(entry['rule_description'])} |")
    lines += ["", "Not offered yet (no enabled gateway rule, no price): " + "; ".join(
        f"{', '.join(f'`{p}`' for p in e['path_prefixes'])} ({e['surface']})" for e in c["not_offered_yet"]) + ".",
        "", f"Owner policy ({c['policy']['decided_on']}): {c['policy']['statement']}", "",
        f"Machine-readable copy: {c['presentation']['manifest_url']}. {rule_count_sentence(c)}", "",
        "Limits: " + " ".join(c["limits"]),
        f"<!-- {MARK_END} -->", ""]
    return "\n".join(lines)


def render_rule_count(c: dict, digest: str) -> str:
    return f"<!-- {_stamp(digest)} -->\n{rule_count_sentence(c)}\n"


def render_all(c: dict, digest: str) -> dict:
    return {
        "x402-pricing.json": render_manifest(c, digest),
        "per-call-table.html": render_html(c, digest),
        "per-call-table.md": render_markdown(c, digest),
        "rule-count.md": render_rule_count(c, digest),
    }


def replace_marked_region(text: str, fragment: str) -> str:
    """Swap the generated region (markers included) inside a target document."""
    start = text.find(f"<!-- {MARK_BEGIN}")
    end = text.find(f"<!-- {MARK_END} -->")
    if start < 0 or end < start or text.count(f"<!-- {MARK_BEGIN}") != 1:
        raise CatalogError("target must contain exactly one generated region")
    end += len(f"<!-- {MARK_END} -->\n")
    return text[:start] + fragment + text[end:]


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="compare the catalog with a rules export")
    p_check.add_argument("--rules", type=Path, required=True)
    p_check.add_argument("--changes", type=Path)
    p_check.add_argument("--catalog", type=Path, default=CATALOG)
    p_gen = sub.add_parser("generate", help="write or verify pricing/generated/*")
    p_gen.add_argument("--check", action="store_true")
    p_gen.add_argument("--catalog", type=Path, default=CATALOG)
    p_gen.add_argument("--out", type=Path, default=GENERATED)
    p_red = sub.add_parser("redact", help="redact the user-agent exemption list of a raw export")
    p_red.add_argument("source", type=Path)
    p_red.add_argument("-o", "--output", type=Path, required=True)
    p_fmt = sub.add_parser("fmt", help="canonicalize catalog.yaml")
    p_fmt.add_argument("--check", action="store_true")
    p_fmt.add_argument("--catalog", type=Path, default=CATALOG)
    p_sync = sub.add_parser("sync", help="replace the generated region in a target document")
    p_sync.add_argument("target", type=Path)
    p_sync.add_argument("--format", choices=("html", "md"), required=True)
    p_sync.add_argument("--catalog", type=Path, default=CATALOG)
    args = parser.parse_args(argv)

    try:
        if args.command == "fmt":
            text = args.catalog.read_text(encoding="utf-8")
            canonical = format_catalog(text)
            if args.check:
                if canonical != text:
                    print(f"FAIL: {args.catalog} is not canonical; run: python tools/pricing_catalog.py fmt")
                    return 1
                print(f"OK: {args.catalog} is canonical")
                return 0
            args.catalog.write_text(canonical, encoding="utf-8")
            print(f"wrote {args.catalog}")
            return 0
        if args.command == "redact":
            redacted = redact_snapshot(_read_json(args.source))
            args.output.write_text(json.dumps(redacted, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
            print(f"wrote {args.output}")
            return 0
        catalog = load_catalog(args.catalog)
        digest = catalog_digest(args.catalog)
        if args.command == "check":
            changes = _read_json(args.changes) if args.changes else None
            errors = check(catalog, _read_json(args.rules), changes)
            for error in errors:
                print(f"DISAGREE: {error}")
            if errors:
                print(f"FAIL: {len(errors)} disagreement(s) between {args.catalog.name} and {args.rules.name}")
                return 1
            charged = len(catalog["charged"])
            print(f"OK: catalog agrees with {args.rules.name}"
                  f"{' + ' + args.changes.name if args.changes else ''}: {charged} charged rule(s), "
                  f"{len(catalog['inactive_rules'])} inactive, {sum(len(g['probes']) for g in catalog['free'])} "
                  "free probe URL(s) uncharged")
            return 0
        if args.command == "sync":
            fragment = render_all(catalog, digest)["per-call-table." + args.format]
            text = args.target.read_text(encoding="utf-8")
            args.target.write_text(replace_marked_region(text, fragment), encoding="utf-8")
            print(f"synced {args.target}")
            return 0
        outputs = render_all(catalog, digest)
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
            print(f"FAIL: stale generated output(s): {', '.join(stale)}; run: python tools/pricing_catalog.py generate")
            return 1
        print("OK: generated outputs are current" if args.check else f"wrote {len(outputs)} file(s) to {args.out}")
        return 0
    except (CatalogError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
