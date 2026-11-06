"""The offline verifier must not report more than it checked.

It used to print "VERIFY: PASS" for any validly signed payload without
checking the statement type, crash on malformed input, and never compare the
evidence digests a receipt records with the evidence files themselves.
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import receipt as R
import verify_receipt

RECEIPT = ROOT / "receipts" / "audit-receipt-2026-08-30.dsse.json"
PUBKEY = ROOT / "keys" / "szl-audit-ed25519.pub.pem"


@pytest.fixture
def signed(tmp_path):
    """A receipt over one evidence file, plus the matching public key, in tmp_path."""
    (tmp_path / "data").mkdir()
    evidence = tmp_path / "data" / "capture.json"
    evidence.write_text('{"rows": 1}\n', encoding="utf-8")
    sk, pk = R.generate_keypair()
    action = R.GovernedAction(
        action="t", actor="qa@szl.dev", scope="test", truth_state="VERIFIED",
        evidence=[R.EvidenceItem(kind="api_response", ref="data/capture.json",
                                 sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())])
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(R.sign_statement(R.build_statement(action, source_rev="t"), sk)))
    key = tmp_path / "key.pub.pem"
    key.write_text(R.public_key_pem(pk))
    return receipt, key, evidence, sk


def _run(*argv):
    return verify_receipt.main([str(a) for a in argv])


def test_signature_only_mode_says_digests_were_not_compared(signed, capsys):
    receipt, key, _, _ = signed
    assert _run(receipt, key) == 0
    assert "digests not compared with files" in capsys.readouterr().out


def test_matching_evidence_passes(signed, capsys):
    receipt, key, _, _ = signed
    assert _run(receipt, key, "--evidence-root", receipt.parent) == 0
    assert "EVIDENCE: PASS (1 of 1" in capsys.readouterr().out


def test_changed_evidence_fails_with_exit_2(signed, capsys):
    receipt, key, evidence, _ = signed
    evidence.write_text('{"rows": 2}\n', encoding="utf-8")
    assert _run(receipt, key, "--evidence-root", receipt.parent) == verify_receipt.EVIDENCE_FAILED
    out = capsys.readouterr().out
    assert "MISMATCH" in out and "EVIDENCE: FAIL" in out


def test_missing_evidence_fails_with_exit_2(signed):
    receipt, key, evidence, _ = signed
    evidence.unlink()
    assert _run(receipt, key, "--evidence-root", receipt.parent) == verify_receipt.EVIDENCE_FAILED


def test_evidence_refs_cannot_escape_the_evidence_root(tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("x", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    predicate = {"evidence": [{"ref": "../secret.txt", "sha256": hashlib.sha256(b"x").hexdigest()}]}
    assert verify_receipt.check_evidence(predicate, root) == [("OUTSIDE_ROOT", "../secret.txt")]


def test_validly_signed_non_governed_action_payload_is_rejected(signed, capsys):
    receipt, key, _, sk = signed
    other = R.dsse_sign({"_type": R.STATEMENT_TYPE, "predicateType": "https://example.test/Other/v1",
                         "predicate": {}}, sk)
    receipt.write_text(json.dumps(other))
    assert _run(receipt, key) == 1
    assert "not a GovernedAction/v1" in capsys.readouterr().out


@pytest.mark.parametrize("text", ["not json", "{}", '{"payload": 5, "payloadType": "x"}'])
def test_malformed_receipt_fails_cleanly(signed, text):
    receipt, key, _, _ = signed
    receipt.write_text(text)
    assert _run(receipt, key) == 1


def test_tampered_payload_fails(signed):
    receipt, key, _, _ = signed
    env = json.loads(receipt.read_text())
    body = bytearray(base64.b64decode(env["payload"]))
    body[-2] ^= 0x01
    env["payload"] = base64.b64encode(bytes(body)).decode()
    receipt.write_text(json.dumps(env))
    assert _run(receipt, key) == 1


def test_usage_error_keeps_exit_64():
    with pytest.raises(SystemExit) as raised:
        verify_receipt.main([])
    assert raised.value.code == verify_receipt.USAGE


def test_committed_receipt_reports_its_evidence_honestly(capsys):
    """Exit 0 only if every digest the committed receipt records matches the checkout."""
    predicate = json.loads(base64.b64decode(json.loads(RECEIPT.read_text())["payload"]))["predicate"]
    expected = {item["ref"]: hashlib.sha256((ROOT / item["ref"]).read_bytes()).hexdigest() == item["sha256"]
                for item in predicate["evidence"] if item.get("sha256")}
    code = _run(RECEIPT, PUBKEY, "--evidence-root", ROOT)
    out = capsys.readouterr().out
    assert code == (0 if all(expected.values()) else verify_receipt.EVIDENCE_FAILED)
    for ref, matches in expected.items():
        assert f"{'MATCH' if matches else 'MISMATCH':<12} {ref}" in out
