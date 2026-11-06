"""The bootstrap must never replace the published audit identity by accident.

Without the key holder's private key it used to mint a new key pair,
overwrite keys/szl-audit-ed25519.pub.pem and re-sign the dated receipt; the
result no longer verified against the key third parties already hold.
"""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import receipt as R
import szl_master_bootstrap as boot


@pytest.fixture
def layout(tmp_path, monkeypatch):
    keys, ext, receipts = tmp_path / "keys", tmp_path / "szl-gov-keys", tmp_path / "receipts"
    keys.mkdir()
    receipts.mkdir()
    published = keys / "szl-audit-ed25519.pub.pem"
    sk, pk = R.generate_keypair()
    published.write_text(R.public_key_pem(pk))
    monkeypatch.setattr(boot, "KEYS", keys)
    monkeypatch.setattr(boot, "EXTKEYS", ext)
    monkeypatch.setattr(boot, "RECEIPTS", receipts)
    monkeypatch.setattr(boot, "PUBLISHED_PUB", published)
    # Any ledger build before the key check would be a write without control.
    tripwire = types.ModuleType("build_ledgers")
    tripwire.main = lambda: pytest.fail("ledgers were built before the signing key was resolved")
    monkeypatch.setitem(sys.modules, "build_ledgers", tripwire)
    return types.SimpleNamespace(sk=sk, pk=pk, ext=ext, receipts=receipts, published=published,
                                 published_text=published.read_text())


def _install_key(layout, sk):
    layout.ext.mkdir(exist_ok=True)
    (layout.ext / "szl-audit-ed25519.pem").write_text(R.private_key_pem(sk))


def test_missing_key_refuses_before_any_write(layout, capsys):
    assert boot.main(["--run"]) == boot.KEY_REFUSED
    assert "REFUSED: no signing key" in capsys.readouterr().err
    assert not layout.ext.exists()
    assert list(layout.receipts.iterdir()) == []
    assert layout.published.read_text() == layout.published_text


def test_key_that_is_not_the_published_identity_refuses(layout, capsys):
    other, _ = R.generate_keypair()
    _install_key(layout, other)
    assert boot.main(["--run"]) == boot.KEY_REFUSED
    assert "is not the published identity" in capsys.readouterr().err
    assert list(layout.receipts.iterdir()) == []
    assert layout.published.read_text() == layout.published_text


def test_published_identity_key_is_accepted(layout):
    _install_key(layout, layout.sk)
    sk, pk = boot.signing_key()
    assert R.key_id(pk) == R.key_id(layout.pk) == R.key_id(sk.public_key())


def test_new_key_never_overwrites_an_existing_key(layout):
    _install_key(layout, layout.sk)
    key_file = layout.ext / "szl-audit-ed25519.pem"
    before = key_file.read_bytes()
    assert boot.signing_key(new_key=True) is None
    assert key_file.read_bytes() == before


def test_new_key_mints_a_private_key_readable_only_by_its_owner(layout):
    _, pk = boot.signing_key(new_key=True)
    key_file = layout.ext / "szl-audit-ed25519.pem"
    assert key_file.stat().st_mode & 0o777 == 0o600
    assert R.key_id(R.load_private(key_file.read_text()).public_key()) == R.key_id(pk)
