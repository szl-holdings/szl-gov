"""Committed ledgers are exactly what the generators produce from the committed snapshot.

CI rebuilds the ledgers before running the gates, so a hand edit to a
generated file would be invisible there. This catches it.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_bom
import build_ledgers
import tier_spaces

GENERATED = (
    "ESTATE_INVENTORY.yaml",
    "CLAIMS_LEDGER.yaml",
    "COMMERCIAL_LEDGER.yaml",
    "CONTRADICTION_REGISTER.yaml",
    "MODEL_BOM.yaml",
    "DATASET_LICENSE_REGISTER.yaml",
    "spaces_tiering.json",
)


def test_committed_ledgers_match_a_fresh_build(tmp_path, monkeypatch, capsys):
    out = tmp_path / "ledgers"
    monkeypatch.setattr(build_ledgers, "LEDGERS", out)
    monkeypatch.setattr(build_bom, "LEDGERS", out)
    monkeypatch.setattr(tier_spaces, "ROOT", tmp_path)

    assert build_ledgers.main() == 0
    assert tier_spaces.main() == 0
    capsys.readouterr()

    for name in GENERATED:
        fresh = (out / name).read_bytes()
        committed = (ROOT / "ledgers" / name).read_bytes()
        assert fresh == committed, f"ledgers/{name} differs from tools output; regenerate, do not hand-edit"
