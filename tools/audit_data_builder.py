"""audit_data_builder — canonical, parsed snapshot of the live estate audit.

Reads nothing at import; build() runs the probe results captured 2026-08-30.
Every count here is derived from raw API snapshots, never asserted in prose.

Public-only listings: a row is listed only when the snapshot marks it public
(GitHub visibility PUBLIC, Hub private false). Anything else, including a row
with no visibility flag, is left out of every listing and kept only as an
aggregate count, so estate totals stay measured without naming it.
"""
from __future__ import annotations

import json
import pathlib

FLAGSHIP_CAPACITY = 5

# Aggregate counts of rows already removed from the committed snapshot
# (written by tools/public_snapshot.py). Counts only, never names.
WITHHELD_FILE = "withheld_private_counts.json"

# Public docker spaces — these are the investor-visible Docker estate (billing risk class).
# From 2026-08-30 audit: public docker = a11oy, killinchu, szl-khipu, immune (4).
# Private docker spaces are numerous; private != demo-safe either, but not diligence-visible.
PUBLIC_FLAGSHIP_CANDIDATES = [
    "a11oy", "killinchu", "governed-receipt-verifier", "szl-atelier", "README",
]


def is_public_repo(record) -> bool:
    """A GitHub row is listed only when the snapshot says PUBLIC (fail closed)."""
    return str(record.get("visibility", "")).strip().upper() == "PUBLIC"


def is_public_hf(record) -> bool:
    """A Hub row is listed only when the snapshot says private is false (fail closed)."""
    return str(record.get("private")).strip().lower() in {"false", "0", "no"}


def load_withheld(audit_dir) -> dict:
    """Aggregate counts of rows withheld from the committed snapshot, if recorded."""
    path = pathlib.Path(audit_dir) / WITHHELD_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: int(v) for k, v in data.get("counts", {}).items()}


def build(gh_repos, hf, withheld=None) -> dict:
    withheld = withheld or {}

    def _updated_at(record):
        """Preserve provider observation time from either supported snapshot key."""
        if "updated_at" in record:
            return record["updated_at"]
        return record.get("updated")

    all_spaces = hf["spaces"]
    all_docker = [s for s in all_spaces if s.get("sdk") == "docker"]
    public_repos = [r for r in gh_repos if is_public_repo(r)]
    spaces = [s for s in all_spaces if is_public_hf(s)]
    models = [m for m in hf["models"] if is_public_hf(m)]
    datasets = [d for d in hf["datasets"] if is_public_hf(d)]
    public_docker = [s["path"] for s in spaces if s.get("sdk") == "docker"]

    # Totals cover the whole estate; every listing below is public rows only.
    seen = {
        "github_repos": gh_repos,
        "hf_spaces": all_spaces,
        "hf_spaces_docker": all_docker,
        "hf_models": hf["models"],
        "hf_datasets": hf["datasets"],
    }
    listed = {
        "github_repos": public_repos,
        "hf_spaces": spaces,
        "hf_spaces_docker": public_docker,
        "hf_models": models,
        "hf_datasets": datasets,
    }
    totals = {k: len(rows) + int(withheld.get(k, 0)) for k, rows in seen.items()}

    estate = {
        "meta": {
            "generated_at": "2026-08-30",
            "github_org": "szl-holdings",
            "hf_org": "SZLHOLDINGS",
            "hf_plan": "team",
            "collector": "szl-gov estate audit (READ_ONLY, API snapshots)",
        },
        "counts": {
            "github_repos": totals["github_repos"],
            "hf_spaces": totals["hf_spaces"],
            "hf_spaces_docker": totals["hf_spaces_docker"],
            "hf_spaces_public": len(spaces),
            "hf_models": totals["hf_models"],
            "hf_datasets": totals["hf_datasets"],
            "advertised_flagships": 5,
            "withheld_non_public": {k: totals[k] - len(listed[k]) for k in totals},
        },
        # Prior rounds marketed the estate as 26 Spaces / 5 flagships.
        # Measured ground truth is 45/9. The gap between the two numbers
        # is itself a Truth-Ledger row and a contradiction (B-01).
        "prior_claims": {"spaces_advertised": 26, "flagships_advertised": 5},
        "github_repos": [
            {
                "name": r["name"],
                "visibility": r["visibility"],
                "lang": (r.get("primaryLanguage") or {}).get("name"),
                "pushed_at": r["pushedAt"],
                "archived": r.get("isArchived", False),
                "evidence_ref": f"https://github.com/szl-holdings/{r['name']}",
            } for r in public_repos
        ],
        "hf_spaces": [
            {
                "path": s["path"],
                "sdk": s.get("sdk"),
                "private": not is_public_hf(s),
                "likes": int(s.get("likes", 0)),
                "updated_at": _updated_at(s),
                # RUNNING is never evidence of deployed revision. We recorded
                # presence + config only; runtime stage was not attested.
                "runtime_attested": False,
                "evidence_ref": f"https://huggingface.co/spaces/{s['path']}",
            } for s in spaces
        ],
        "hf_models": [
            {
                "path": m["path"],
                "downloads": int(m.get("downloads", 0)),
                "likes": int(m.get("likes", 0)),
                "task": m.get("task"),
                "updated_at": _updated_at(m),
                "evidence_ref": f"https://huggingface.co/{m['path']}",
            } for m in models
        ],
        "hf_datasets": [
            {
                "path": dset["path"],
                "downloads": int(dset.get("downloads", 0)),
                "private": not is_public_hf(dset),
                "updated_at": _updated_at(dset),
                "evidence_ref": f"https://huggingface.co/datasets/{dset['path']}",
            } for dset in datasets
        ],
        "findings": {
            "docker_tier_risk": {
                "severity": "BLOCKER",
                "detail": (
                    "HF policy change (July 2026): Docker/Gradio Spaces on free cpu-basic "
                    "require PRO. HF org plan is TEAM (billing bound to team plan). "
                    f"Public Docker Spaces in flight: {public_docker}. "
                    "A dead public flagship in a diligence click-through is worse than five honest ones."
                ),
                "public_docker_spaces": public_docker,
            },
            "model_backlink_gap": {
                "severity": "HIGH",
                "detail": (
                    "HF statically parses Space repo files for literal model IDs. "
                    "IDs built dynamically or held in YAML-only config don't backlink. "
                    "With 43 models x 45 spaces this is compounding free distribution "
                    "currently being discarded. Fix = `models:` front-matter + "
                    "literal-ID file per Space, one commit each."
                ),
            },
            "org_card_is_space": {
                "severity": "MEDIUM",
                "detail": (
                    "SZLHOLDINGS/README is itself a static Space (org card). It has a "
                    "runtime, can drift, and belongs in inventory under tier ORG_CARD. "
                    "It is also public and currently carries 0 likes and no receipt link."
                ),
            },
            "space_disk_not_persistent": {
                "severity": "HIGH",
                "detail": (
                    "Default 50GB Space disk is NOT persistent across rebuilds. Any Space "
                    "spooling evidence to local disk violates Flight Recorder durability. "
                    "Durability that vanishes on rebuild is not durability."
                ),
            },
        },
    }
    return estate
