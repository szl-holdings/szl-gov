"""Public-only guard: committed snapshots and generated ledgers list public rows only.

Rows the capture does not mark public are withheld and survive only as
aggregate counts. These tests fail if a raw capture, or a generator that
forgets the filter, would put such a row back into the repository.
"""
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_bom  # noqa: E402
import public_snapshot  # noqa: E402
import tier_spaces  # noqa: E402
from audit_data_builder import build, is_public_hf, is_public_repo, load_withheld  # noqa: E402

AUDIT = ROOT / "audit_data"
LEDGERS = ROOT / "ledgers"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _public_ids():
    gh = _load(AUDIT / "gh_repos.json")
    hf = _load(AUDIT / "hf_org_listing.json")
    return (
        {r["name"] for r in gh if is_public_repo(r)},
        {kind: {r["path"] for r in hf[kind] if is_public_hf(r)} for kind in ("spaces", "models", "datasets")},
    )


def test_committed_github_snapshot_lists_public_repos_only():
    rows = _load(AUDIT / "gh_repos.json")
    assert rows
    assert all(is_public_repo(r) for r in rows)


def test_committed_hub_listing_lists_public_rows_only():
    hf = _load(AUDIT / "hf_org_listing.json")
    for key, rows in hf.items():
        if isinstance(rows, list):
            assert all(is_public_hf(r) for r in rows), key


def test_committed_license_snapshot_is_limited_to_the_public_listing():
    _, public = _public_ids()
    lic = _load(AUDIT / "hf_licenses.json")
    for kind, entries in lic.items():
        assert set(entries) <= public[kind], kind
        assert all(is_public_hf(e) for e in entries.values()), kind


def test_withheld_counts_are_aggregates_only():
    data = _load(AUDIT / "withheld_private_counts.json")
    assert set(data) == {"rule", "generated_by", "counts"}
    assert all(isinstance(v, int) and v >= 0 for v in data["counts"].values())
    assert load_withheld(AUDIT) == data["counts"]


def test_generated_ledgers_name_only_public_rows():
    gh_public, public = _public_ids()
    inventory = (LEDGERS / "ESTATE_INVENTORY.yaml").read_text(encoding="utf-8")
    register = (LEDGERS / "DATASET_LICENSE_REGISTER.yaml").read_text(encoding="utf-8")
    bom = (LEDGERS / "MODEL_BOM.yaml").read_text(encoding="utf-8")
    listed_hub = public["spaces"] | public["models"] | public["datasets"]

    for name, text in (("inventory", inventory), ("register", register), ("bom", bom)):
        assert "private: true" not in text, name
        assert "visibility: PRIVATE" not in text, name

    gh_refs = set(re.findall(r'evidence_ref: "?https://github\.com/szl-holdings/([^"\s]+)', inventory))
    hub_refs = set(re.findall(
        r'evidence_ref: "?https://huggingface\.co/(?:spaces/|datasets/)?(SZLHOLDINGS/[^"\s]+)', inventory))
    assert gh_refs and gh_refs <= gh_public
    assert hub_refs and hub_refs <= listed_hub
    assert set(re.findall(r"- dataset: (\S+)", register)) <= public["datasets"]
    assert set(re.findall(r"- model: (\S+)", bom)) <= public["models"]

    tiering = _load(LEDGERS / "spaces_tiering.json")
    assert all(t["private"] is False for t in tiering["tiers"])
    assert {t["path"] for t in tiering["tiers"]} <= public["spaces"]


def test_builder_lists_public_rows_and_keeps_totals():
    gh = [
        {"name": "open-repo", "visibility": "PUBLIC", "pushedAt": "2026-09-24T00:00:00Z"},
        {"name": "closed-repo", "visibility": "PRIVATE", "pushedAt": "2026-09-24T00:00:00Z"},
        {"name": "unflagged-repo", "pushedAt": "2026-09-24T00:00:00Z"},
    ]
    hf = {
        "spaces": [
            {"path": "ORG/open-space", "sdk": "docker", "private": False},
            {"path": "ORG/closed-space", "sdk": "docker", "private": True},
            {"path": "ORG/string-flag-space", "sdk": "static", "private": "true"},
        ],
        "models": [{"path": "ORG/open-model", "private": False}, {"path": "ORG/unflagged-model"}],
        "datasets": [{"path": "ORG/open-ds", "private": "false"}, {"path": "ORG/closed-ds", "private": True}],
    }

    estate = build(gh, hf, withheld={"github_repos": 2, "hf_datasets": 3})

    assert [r["name"] for r in estate["github_repos"]] == ["open-repo"]
    assert [s["path"] for s in estate["hf_spaces"]] == ["ORG/open-space"]
    assert [m["path"] for m in estate["hf_models"]] == ["ORG/open-model"]
    assert [d["path"] for d in estate["hf_datasets"]] == ["ORG/open-ds"]
    assert estate["hf_datasets"][0]["private"] is False
    assert estate["findings"]["docker_tier_risk"]["public_docker_spaces"] == ["ORG/open-space"]
    counts = estate["counts"]
    assert (counts["github_repos"], counts["hf_spaces"], counts["hf_spaces_docker"]) == (5, 3, 2)
    assert (counts["hf_spaces_public"], counts["hf_models"], counts["hf_datasets"]) == (1, 2, 5)
    assert counts["withheld_non_public"] == {
        "github_repos": 4, "hf_spaces": 2, "hf_spaces_docker": 1, "hf_models": 1, "hf_datasets": 4,
    }
    rendered = json.dumps(estate)
    for hidden in ("closed-repo", "unflagged-repo", "closed-space", "string-flag-space",
                   "unflagged-model", "closed-ds"):
        assert hidden not in rendered


def _raw_capture(tmp_path):
    audit = tmp_path / "audit_data"
    (audit / "readmes").mkdir(parents=True)
    (tmp_path / "ledgers").mkdir()
    listing = {
        "spaces": [
            {"path": "ORG/open-space", "sdk": "static", "private": False},
            {"path": "ORG/closed-space", "sdk": "docker", "private": True},
        ],
        "models": [{"path": "ORG/open-model", "private": False, "downloads": 1}],
        "datasets": [
            {"path": "ORG/open-ds", "private": False},
            {"path": "ORG/closed-ds", "private": True},
        ],
    }
    licenses = {
        "models": {"ORG/open-model": {"license": "apache-2.0", "private": False, "sha": "abc"}},
        "datasets": {
            "ORG/open-ds": {"license": "apache-2.0", "private": False, "sha": "def"},
            "ORG/closed-ds": {"license": None, "private": False, "sha": ""},
        },
    }
    gh = [{"name": "open-repo", "visibility": "PUBLIC"}, {"name": "closed-repo", "visibility": "PRIVATE"}]
    (audit / "hf_org_listing.json").write_text(json.dumps(listing), encoding="utf-8")
    (audit / "hf_licenses.json").write_text(json.dumps(licenses), encoding="utf-8")
    (audit / "gh_repos.json").write_text(json.dumps(gh), encoding="utf-8")
    return audit, listing, licenses, gh


def test_generators_drop_non_public_rows_from_a_raw_capture(tmp_path, monkeypatch):
    audit, _, _, _ = _raw_capture(tmp_path)
    ledgers = tmp_path / "ledgers"
    monkeypatch.setattr(build_bom, "AUDIT", audit)
    monkeypatch.setattr(build_bom, "LEDGERS", ledgers)
    monkeypatch.setattr(tier_spaces, "AUDIT", audit)
    monkeypatch.setattr(tier_spaces, "ROOT", tmp_path)

    assert build_bom.main() == 0
    assert tier_spaces.main() == 0

    register = (ledgers / "DATASET_LICENSE_REGISTER.yaml").read_text(encoding="utf-8")
    tiering = _load(ledgers / "spaces_tiering.json")
    rendered = register + (ledgers / "MODEL_BOM.yaml").read_text(encoding="utf-8") + json.dumps(tiering)
    assert "closed" not in rendered
    assert "withheld_non_public: 1" in register
    assert [t["path"] for t in tiering["tiers"]] == ["ORG/open-space"]
    assert tiering["withheld_non_public"] == 1


def test_public_snapshot_filter_keeps_public_rows_and_counts_the_rest(tmp_path):
    _, listing, licenses, gh = _raw_capture(tmp_path)

    gh_pub, hf_pub, lic_pub, counts = public_snapshot.filter_snapshot(gh, listing, licenses)

    assert [r["name"] for r in gh_pub] == ["open-repo"]
    assert [s["path"] for s in hf_pub["spaces"]] == ["ORG/open-space"]
    assert [d["path"] for d in hf_pub["datasets"]] == ["ORG/open-ds"]
    assert set(lic_pub["datasets"]) == {"ORG/open-ds"}
    assert counts == {"github_repos": 1, "hf_spaces": 1, "hf_spaces_docker": 1, "hf_models": 0, "hf_datasets": 1}
    assert "closed" not in json.dumps([gh_pub, hf_pub, lic_pub])
