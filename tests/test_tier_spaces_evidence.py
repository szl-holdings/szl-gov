"""Tier rows may only pass a flagship test on committed evidence the gate accepts.

The generator once named its deployment test differently from the gate,
passed it on stage RUNNING (which B-06 says is not evidence), and passed the
mobile test from a hard-coded name list. Two flagships were written as
"Fully machine-attested" while the gate, the README and claim C-006 said 0.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import spaces_gate
import tier_spaces

DEPLOYED = "deployed revision attested (stage RUNNING is NOT evidence)"
MOBILE = "mobile smoke test passed"
SPACE = {"path": "ORG/example", "sdk": "docker", "private": False}


def _passes(test, probe):
    return tier_spaces.MACHINE_TESTS[test](SPACE, probe)


def test_generator_tests_are_exactly_the_gate_tests():
    assert set(tier_spaces.MACHINE_TESTS) == set(spaces_gate.FLAGSHIP_TESTS)


def test_running_stage_is_not_deployed_revision_evidence():
    assert not _passes(DEPLOYED, {"sha": "abc", "runtime": {"stage": "RUNNING"}})
    assert not _passes(DEPLOYED, {"sha": "abc", "runtime": {"stage": "RUNNING", "sha": "def"}})
    assert not _passes(DEPLOYED, {"runtime": {"stage": "RUNNING", "sha": None}})
    assert _passes(DEPLOYED, {"sha": "abc", "runtime": {"stage": "BUILDING", "sha": "abc"}})


def test_mobile_smoke_test_never_passes_without_captured_evidence():
    for probe in ({}, {"sdk": "static"}, {"sha": "abc", "runtime": {"stage": "RUNNING", "sha": "abc"}}):
        assert not _passes(MOBILE, probe)


def test_committed_tiering_agrees_with_the_gate_row_by_row():
    tiering = json.loads((ROOT / "ledgers" / "spaces_tiering.json").read_text(encoding="utf-8"))
    for row in tiering["tiers"]:
        missing = [t for t in spaces_gate.FLAGSHIP_TESTS if t not in row["tests_passed"]]
        assert sorted(missing) == sorted(row["tests_failed"]), row["name"]
        assert row["attested"] is (not missing), row["name"]
        if row["deployed_sha"] is None:
            assert DEPLOYED in row["tests_failed"], row["name"]
