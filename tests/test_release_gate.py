import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import release_gate


def complete_commercial():
    # Synthetic readiness only: never write the repository's actual ledger.
    return ((ROOT / "ledgers/COMMERCIAL_LEDGER.yaml").read_text(encoding="utf-8")
            .replace("value: UNKNOWN", "value: 1")
            .replace("evidence_ref: UNKNOWN", 'evidence_ref: "fixture://evidence"')
            .replace("blocks_raise: true", "blocks_raise: false"))


def run_gate(tmp_path, monkeypatch, commercial=None, contradictions="contradictions: []\n"):
    monkeypatch.setattr(release_gate, "LEDGERS", tmp_path)
    if commercial is not None:
        (tmp_path / "COMMERCIAL_LEDGER.yaml").write_text(commercial, encoding="utf-8")
    if contradictions is not None:
        (tmp_path / "CONTRADICTION_REGISTER.yaml").write_text(contradictions, encoding="utf-8")
    return release_gate.main()


def test_complete_synthetic_ledgers_can_pass(tmp_path, monkeypatch):
    assert run_gate(tmp_path, monkeypatch, complete_commercial()) == 0


@pytest.mark.parametrize("missing", ["commercial", "contradictions"])
def test_each_ledger_is_required(tmp_path, monkeypatch, missing):
    assert run_gate(tmp_path, monkeypatch,
                    None if missing == "commercial" else complete_commercial(),
                    None if missing == "contradictions" else "contradictions: []\n") == 6


@pytest.mark.parametrize("invalid", ["", "# unavailable\n", "garbage\n", "rows: []\n"])
@pytest.mark.parametrize("ledger", ["commercial", "contradictions"])
def test_empty_or_malformed_ledgers_never_report_ready(tmp_path, monkeypatch, capsys, invalid, ledger):
    commercial = invalid if ledger == "commercial" else complete_commercial()
    contradictions = invalid if ledger == "contradictions" else "contradictions: []\n"
    assert run_gate(tmp_path, monkeypatch, commercial, contradictions) == 6
    assert "clean —" not in capsys.readouterr().out


@pytest.mark.parametrize("old,new", [
    ("blocks_raise: false", "blocks_raise: true"),
    ("blocks_raise: false", 'blocks_raise: "false"'),
    ('evidence_ref: "fixture://evidence"', "evidence_ref: UNKNOWN"),
    ('evidence_ref: "fixture://evidence"', 'evidence_ref: ""'),
    ("value: 1", 'value: "UNKNOWN"'),
    ("value: 1", 'value: ""'),
    ("value: 1", "value: null"),
    ("    blocks_raise: false\n", ""),
])
def test_explicit_blocks_and_unattested_values_prevent_release(tmp_path, monkeypatch, old, new):
    assert run_gate(tmp_path, monkeypatch, complete_commercial().replace(old, new, 1)) == 6


def test_missing_metric_does_not_turn_omitted_evidence_into_ready(tmp_path, monkeypatch):
    text = complete_commercial()
    start, stop = text.index("  - metric: ARR\n"), text.index("  - metric: MRR\n")
    assert run_gate(tmp_path, monkeypatch, text[:start] + text[stop:]) == 6


def test_duplicate_metric_is_rejected(tmp_path, monkeypatch):
    text = complete_commercial().replace("metric: MRR", "metric: ARR", 1)
    assert run_gate(tmp_path, monkeypatch, text) == 6


def test_duplicate_key_cannot_override_a_blocker(tmp_path, monkeypatch):
    text = complete_commercial().replace("blocks_raise: false", "blocks_raise: true\n    blocks_raise: false", 1)
    assert run_gate(tmp_path, monkeypatch, text) == 6


def test_blocker_matching_does_not_depend_on_key_order_or_id_prefix(tmp_path, monkeypatch):
    contradictions = ('contradictions:\n  - severity: "BLOCKER"\n    id: NEW-1\n'
                      '    statement: unresolved evidence\n    resolution: obtain evidence\n')
    assert run_gate(tmp_path, monkeypatch, complete_commercial(), contradictions) == 6


def test_resolved_contradictions_can_pass(tmp_path, monkeypatch):
    contradictions = ('contradictions:\n  - id: B-1\n    severity: RESOLVED\n'
                      '    statement: former issue\n    resolution: fixture evidence\n')
    assert run_gate(tmp_path, monkeypatch, complete_commercial(), contradictions) == 0


def test_current_repository_ledgers_remain_blocked(tmp_path, monkeypatch):
    commercial = (ROOT / "ledgers/COMMERCIAL_LEDGER.yaml").read_text(encoding="utf-8")
    contradictions = (ROOT / "ledgers/CONTRADICTION_REGISTER.yaml").read_text(encoding="utf-8")
    assert run_gate(tmp_path, monkeypatch, commercial, contradictions) == 6


@pytest.mark.parametrize("text", [
    "contradictions: []\ncontradictions: []\n",
    "contradictions: []\n  - id: B-1\n",
    "contradictions:\n  - id: B-1\n    severity: RESOLVED\n",
    "contradictions: &alias []\n",
])
def test_ambiguous_or_incomplete_register_is_rejected(tmp_path, monkeypatch, text):
    assert run_gate(tmp_path, monkeypatch, complete_commercial(), text) == 6


def test_invalid_utf8_ledger_returns_blocked(tmp_path, monkeypatch):
    (tmp_path / "COMMERCIAL_LEDGER.yaml").write_bytes(b"\xff")
    assert run_gate(tmp_path, monkeypatch) == 6


def test_oversized_read_is_bounded_and_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(release_gate, "MAX_LEDGER_BYTES", 32)
    assert run_gate(tmp_path, monkeypatch, complete_commercial()) == 6


def test_builder_exports_complete_unique_metric_set():
    from build_ledgers import COMMERCIAL_ROWS
    names = [name for name, _ in COMMERCIAL_ROWS]
    assert len(names) == len(set(names)) == 25
    # The generated format and gate agree without a second handwritten allowlist.
    assert release_gate.rows_with_unknown(complete_commercial()) == []
