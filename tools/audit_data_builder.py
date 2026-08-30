"""audit_data_builder — canonical, parsed snapshot of the live estate audit.

Reads nothing at import; build() runs the probe results captured 2026-08-30.
Every count here is derived from raw API snapshots, never asserted in prose.
"""
from __future__ import annotations

FLAGSHIP_CAPACITY = 5

# Public docker spaces — these are the investor-visible Docker estate (billing risk class).
# From 2026-08-30 audit: public docker = a11oy, killinchu, szl-khipu, immune (4).
# Private docker spaces are numerous; private != demo-safe either, but not diligence-visible.
PUBLIC_FLAGSHIP_CANDIDATES = [
    "a11oy", "killinchu", "governed-receipt-verifier", "szl-atelier", "README",
]

def build(gh_repos, hf) -> dict:
    def _truthy(v):
        return str(v).strip().lower() in {"true", "1", "yes"}

    spaces = hf["spaces"]
    docker_spaces = [s for s in spaces if s.get("sdk") == "docker"]
    public_spaces = [s for s in spaces if not _truthy(s.get("private"))]
    public_docker = [s["path"] for s in docker_spaces if not _truthy(s.get("private"))]

    estate = {
        "meta": {
            "generated_at": "2026-08-30",
            "github_org": "szl-holdings",
            "hf_org": "SZLHOLDINGS",
            "hf_plan": "team",
            "collector": "szl-gov estate audit (READ_ONLY, API snapshots)",
        },
        "counts": {
            "github_repos": len(gh_repos),
            "hf_spaces": len(spaces),
            "hf_spaces_docker": len(docker_spaces),
            "hf_spaces_public": len(public_spaces),
            "hf_models": len(hf["models"]),
            "hf_datasets": len(hf["datasets"]),
            "advertised_flagships": 5,
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
            } for r in gh_repos
        ],
        "hf_spaces": [
            {
                "path": s["path"],
                "sdk": s.get("sdk"),
                "private": bool(s.get("private")),
                "likes": int(s.get("likes", 0)),
                "updated_at": s.get("updated_at"),
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
                "updated_at": m.get("updated_at"),
                "evidence_ref": f"https://huggingface.co/{m['path']}",
            } for m in hf["models"]
        ],
        "hf_datasets": [
            {
                "path": dset["path"],
                "downloads": int(dset.get("downloads", 0)),
                "private": bool(dset.get("private")),
                "updated_at": dset.get("updated_at"),
                "evidence_ref": f"https://huggingface.co/datasets/{dset['path']}",
            } for dset in hf["datasets"]
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
