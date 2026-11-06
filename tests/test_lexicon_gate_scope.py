"""The lexicon gate scans the repository's own docs, not a local virtualenv,
and never skips the repository because of where it was cloned."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lexicon_gate

BANNED = "This build is " + "production-ready.\n"  # assembled so this file is not itself a hit


def _gate(root, monkeypatch, capsys):
    monkeypatch.setattr(lexicon_gate, "ROOT", root)
    code = lexicon_gate.main()
    return code, capsys.readouterr().out


def test_local_virtualenv_docs_are_not_estate_claims(tmp_path, monkeypatch, capsys):
    for venv in (".venv", "venv"):
        (tmp_path / venv / "lib").mkdir(parents=True)
        (tmp_path / venv / "lib" / "LICENSE.md").write_text(BANNED, encoding="utf-8")
    (tmp_path / "README.md").write_text("Evidence after.\n", encoding="utf-8")
    assert _gate(tmp_path, monkeypatch, capsys) == (0, "== LEXICON GATE ==\nclean\n")


def test_checkout_under_a_skipped_name_is_still_scanned(tmp_path, monkeypatch, capsys):
    root = tmp_path / "venv" / "audit_data" / "szl-gov"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "claim.md").write_text(BANNED, encoding="utf-8")
    code, out = _gate(root, monkeypatch, capsys)
    assert code == 5
    assert "docs/claim.md:1" in out
