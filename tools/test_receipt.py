#!/usr/bin/env python3
"""test_receipt.py — contract tests for the receipt stack.

Runs under plain python3 (no pytest required) OR pytest. Every test maps to an
attack or invariant from the 10-round thread. A PASS here is proof, not prose.

  python3 tools/test_receipt.py        # standalone
  pytest   tools/test_receipt.py       # if pytest available
"""
from __future__ import annotations

import base64
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import receipt as R

PASS, FAIL = 0, 1
_results = []


def check(name, fn):
    global PASS
    try:
        fn()
        _results.append((PASS, name))
    except Exception as e:
        _results.append((FAIL, f"{name}: {type(e).__name__} {e}"))


# ---------------------------------------------------------------- helpers

def _action(**kw):
    base = dict(action="t", actor="qa@szl.dev", scope="test",
                truth_state="VERIFIED",
                evidence=[R.EvidenceItem(kind="api_response", ref="x", required=True)])
    base.update(kw)
    return R.GovernedAction(**base)


def _signed(action=None):
    sk, pk = R.generate_keypair()
    a = action or _action()
    stmt = R.build_statement(a, source_rev="test")
    return R.sign_statement(stmt, sk), pk, a


# ---------------------------------------------------------------- tests

def t_sign_verify_roundtrip():
    env, pk, a = _signed()
    out = R.dsse_verify(env, pk)
    assert out["predicateType"] == R.PREDICATE_TYPE

def t_tamper_byte_flip_rejected():
    env, pk, a = _signed()
    body = bytearray(base64.b64decode(env["payload"]))
    body[10] ^= 0x01
    env["payload"] = base64.b64encode(bytes(body)).decode()
    try:
        R.dsse_verify(env, pk)
        raise AssertionError("tampered payload was accepted")
    except ValueError:
        pass

def t_wrong_key_rejected():
    env, pk, a = _signed()
    _, pk2 = R.generate_keypair()
    try:
        R.dsse_verify(env, pk2)
        raise AssertionError("wrong key verified")
    except ValueError:
        pass

def t_wrong_payload_type_rejected():
    # signature-confusion attack: re-present the body under a different payloadType
    env, pk, a = _signed()
    env2 = dict(env, payloadType="text/plain")
    try:
        R.dsse_verify(env2, pk)
        raise AssertionError("payload-type confusion accepted")
    except ValueError:
        pass

def t_missing_evidence_is_INCOMPLETE_not_PASS():
    a = _action(evidence=[R.EvidenceItem(kind="human_attestation", ref="", required=True)])
    assert a.completeness == "INCOMPLETE"

def t_empty_evidence_is_INCOMPLETE():
    a = _action(evidence=[])
    assert a.completeness == "INCOMPLETE"

def t_public_claim_without_evidence_demotes_to_UNKNOWN():
    a = _action(truth_state="VERIFIED",
                evidence=[R.EvidenceItem(kind="human_attestation", ref="", required=True)])
    a.public_claim_check()
    assert a.truth_state == "UNKNOWN", f"demotion failed, got {a.truth_state}"

def t_service_account_structurally_forbidden():
    try:
        _action(is_service_account=True)
        raise AssertionError("is_service_account=True did not raise")
    except ValueError:
        pass

def t_service_account_claim_cannot_enter_a_signed_receipt():
    # The Art.12 attack: present a machine action as a human one. Enforced:
    # the schema refuses is_service_account=True, and a signed receipt cannot
    # be edited afterwards to claim it or a different actor.
    # NOT enforced (open gap): the predicate records no auth method, so an
    # API-key actor presenting a human-looking identity is not detected here.
    # (This test used to assert a tautology on keys nothing sets.)
    import dataclasses
    names = {f.name for f in dataclasses.fields(R.GovernedAction)}
    claimed = {k: v for k, v in _action().to_dict().items() if k in names}
    claimed["is_service_account"] = True
    try:
        R.GovernedAction(**claimed)
        raise AssertionError("predicate claiming is_service_account=True was accepted")
    except ValueError:
        pass
    env, pk, _ = _signed()
    statement = json.loads(base64.b64decode(env["payload"]))
    for name, value in (("is_service_account", True), ("actor", "svc-deploy@internal")):
        forged = json.loads(json.dumps(statement))
        forged["predicate"][name] = value
        body = json.dumps(forged, sort_keys=True, separators=(",", ":")).encode()
        try:
            R.dsse_verify(dict(env, payload=base64.b64encode(body).decode()), pk)
            raise AssertionError(f"receipt edited to claim {name}={value!r} still verified")
        except ValueError:
            pass

def t_invalid_truth_state_rejected():
    try:
        _action(truth_state="PASS")
        raise AssertionError("non-canon truth state accepted")
    except ValueError:
        pass

def t_invalid_side_effect_rejected():
    try:
        _action(side_effect_class="Y O L O")
        raise AssertionError("non-canon side effect accepted")
    except ValueError:
        pass

def t_none_renders_UNKNOWN():
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import yamlite
    assert yamlite.scalar(None) == "UNKNOWN"
    assert "value: UNKNOWN" in yamlite.dump({"value": None})

def t_optional_evidence_absent_keeps_COMPLETE():
    a = _action(evidence=[R.EvidenceItem(kind="api_response", ref="x", required=True),
                          R.EvidenceItem(kind="screenshot", ref="", required=False)])
    assert a.completeness == "COMPLETE"

def t_receipt_file_verifies_offline():
    root = pathlib.Path(__file__).resolve().parent.parent
    env = json.loads((root / "receipts" / "audit-receipt-2026-08-30.dsse.json").read_text())
    pk = R.load_public((root / "keys" / "szl-audit-ed25519.pub.pem").read_text())
    out = R.dsse_verify(env, pk)
    assert out["predicate"]["action"] == "full_estate_audit"
    assert out["predicate"]["completeness"] == "INCOMPLETE"  # honest non-PASS

def t_self_audit_receipt_is_DEGRADED_not_VERIFIED():
    root = pathlib.Path(__file__).resolve().parent.parent
    env = json.loads((root / "receipts" / "audit-receipt-2026-08-30.dsse.json").read_text())
    pk = R.load_public((root / "keys" / "szl-audit-ed25519.pub.pem").read_text())
    pred = R.dsse_verify(env, pk)["predicate"]
    assert pred["truth_state"] == "DEGRADED"
    assert len(pred["limitations"]) >= 4


ALL = [v for k, v in sorted(globals().items()) if k.startswith("t_")]


def main():
    for fn in ALL:
        check(fn.__name__, fn)
    fails = [r for r in _results if r[0] == FAIL]
    for ok, name in _results:
        print(("PASS" if ok == PASS else "FAIL"), name)
    print(f"\n{len(_results) - len(fails)}/{len(_results)} contract tests passing")
    return 0 if not fails else 1


# pytest shim: expose as test_ functions
for _fn in ALL:
    globals()["test_" + _fn.__name__[2:]] = _fn

if __name__ == "__main__":
    raise SystemExit(main())
