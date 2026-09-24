import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_data_builder import build


def _minimal_hf(updated_key="updated"):
    return {
        "spaces": [
            {
                "path": "SZLHOLDINGS/example-space",
                "sdk": "static",
                "private": False,
                "likes": "1",
                updated_key: "2026-09-24T10:00:00.000Z",
            }
        ],
        "models": [
            {
                "path": "SZLHOLDINGS/example-model",
                "downloads": "2",
                "likes": "3",
                "task": "text-generation",
                updated_key: "2026-09-24T10:01:00.000Z",
            }
        ],
        "datasets": [
            {
                "path": "SZLHOLDINGS/example-dataset",
                "downloads": "4",
                "private": False,
                updated_key: "2026-09-24T10:02:00.000Z",
            }
        ],
    }


def test_provider_updated_field_is_preserved_in_canonical_snapshot():
    estate = build([], _minimal_hf("updated"))

    assert estate["hf_spaces"][0]["updated_at"] == "2026-09-24T10:00:00.000Z"
    assert estate["hf_models"][0]["updated_at"] == "2026-09-24T10:01:00.000Z"
    assert estate["hf_datasets"][0]["updated_at"] == "2026-09-24T10:02:00.000Z"


def test_updated_at_provider_variant_is_preserved_without_rewriting_time():
    estate = build([], _minimal_hf("updated_at"))

    assert estate["hf_spaces"][0]["updated_at"] == "2026-09-24T10:00:00.000Z"
    assert estate["hf_models"][0]["updated_at"] == "2026-09-24T10:01:00.000Z"
    assert estate["hf_datasets"][0]["updated_at"] == "2026-09-24T10:02:00.000Z"


def test_committed_hf_snapshot_retains_observation_times_end_to_end():
    raw = json.loads((ROOT / "audit_data" / "hf_org_listing.json").read_text())
    estate = build([], raw)

    for source_key, output_key in (
        ("spaces", "hf_spaces"),
        ("models", "hf_models"),
        ("datasets", "hf_datasets"),
    ):
        expected = {row["path"]: row.get("updated") for row in raw[source_key]}
        observed = {row["path"]: row["updated_at"] for row in estate[output_key]}
        assert observed == expected
