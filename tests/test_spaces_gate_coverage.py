"""A tiering file must account for the public inventory exactly once."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import spaces_gate


PUBLIC_SPACES = [
    {"path": "ORG/one", "sdk": "static", "private": False},
    {"path": "ORG/two", "sdk": "static", "private": False},
]
ROWS = [
    {"path": "ORG/one", "name": "one", "tier": "SUPPORTING"},
    {"path": "ORG/two", "name": "two", "tier": "ORG_CARD"},
]


def run_gate(tmp_path, monkeypatch, tiering, spaces=None):
    audit = tmp_path / "audit_data"
    audit.mkdir()
    (audit / "hf_org_listing.json").write_text(json.dumps({
        "spaces": PUBLIC_SPACES if spaces is None else spaces,
    }), encoding="utf-8")
    path = tmp_path / "tiering.json"
    path.write_text(json.dumps(tiering), encoding="utf-8")
    monkeypatch.setattr(spaces_gate, "AUDIT", audit)
    monkeypatch.setattr(sys, "argv", ["spaces_gate.py", "--tiering", str(path)])
    return spaces_gate.main()


@pytest.mark.parametrize("tiering", [
    {},
    {"tiers": []},
    {"tiers": ROWS[:1]},
    {"tiers": [ROWS[0], ROWS[0]]},
    {"tiers": [*ROWS, ROWS[0]]},
    {"tiers": [*ROWS, {"path": "ORG/unknown", "tier": "SUPPORTING"}]},
    {"tiers": [ROWS[0], {"path": "ORG/two"}]},
    {"tiers": [ROWS[0], {"path": "ORG/two", "tier": "TYPO"}]},
    {"tiers": [ROWS[0], {"path": [], "tier": "SUPPORTING"}]},
    {"tiers": [ROWS[0], None]},
    {"tiers": None},
    [],
])
def test_incomplete_or_invalid_tiering_blocks_readiness(tmp_path, monkeypatch, tiering):
    if isinstance(tiering, dict):
        tiering = {**tiering, "billing_verified": True}
    assert run_gate(tmp_path, monkeypatch, tiering) == 2


def test_complete_public_inventory_is_admissible(tmp_path, monkeypatch, capsys):
    assert run_gate(tmp_path, monkeypatch, {"tiers": ROWS}) == 0
    assert "untiered=0" in capsys.readouterr().out


def test_omitted_inventory_is_reported_as_untiered(tmp_path, monkeypatch, capsys):
    assert run_gate(tmp_path, monkeypatch, {"tiers": ROWS[:1]}) == 2
    assert "untiered=1" in capsys.readouterr().out


def test_non_public_spaces_are_withheld_not_required_or_named(tmp_path, monkeypatch, capsys):
    spaces = [*PUBLIC_SPACES,
              {"path": "ORG/private-secret", "sdk": "docker", "private": True},
              {"path": "ORG/unknown-secret", "sdk": "docker"}]
    assert run_gate(tmp_path, monkeypatch, {"tiers": ROWS}, spaces) == 0
    output = capsys.readouterr().out
    assert "withheld_non_public=2" in output
    assert "secret" not in output


def test_complete_tiering_still_requires_docker_billing(tmp_path, monkeypatch):
    spaces = copy.deepcopy(PUBLIC_SPACES)
    spaces[0]["sdk"] = "docker"
    assert run_gate(tmp_path, monkeypatch, {"tiers": ROWS}, spaces) == 3


def test_complete_tiering_preserves_flagship_attestation_gate(tmp_path, monkeypatch):
    rows = copy.deepcopy(ROWS)
    rows[0]["tier"] = "FLAGSHIP"
    assert run_gate(tmp_path, monkeypatch, {"tiers": rows}) == 2
