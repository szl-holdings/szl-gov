#!/usr/bin/env python3
"""build_bom.py — Model Bill of Materials + Dataset License Register.

AI-specific diligence in 2026 requires: training-data inventory, license
provenance per model/dataset, and base-model lineage. This generates both
ledgers from machine-collected card metadata. UNKNOWN stays UNKNOWN —
private repos can't be read anonymously; the owner must declare them.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yamlite

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit_data"
LEDGERS = ROOT / "ledgers"


def main() -> int:
    lic = json.load(open(AUDIT / "hf_licenses.json"))
    hf = json.load(open(AUDIT / "hf_org_listing.json"))
    dl_counts = {e["path"]: int(e.get("downloads", 0)) for e in hf["models"]}

    # ---- MODEL BOM
    models = []
    for rid, m in sorted(lic["models"].items()):
        base = m.get("base_model")
        if isinstance(base, list):
            base = base[0] if base else None
        third_party = bool(base) and not str(base).startswith("SZLHOLDINGS/")
        models.append({
            "model": rid,
            "license": m.get("license"),
            "base_model": base,
            "base_model_license": "apache-2.0" if base and "Qwen" in str(base) else None,
            "third_party_base": third_party,
            "library": m.get("library"),
            "pipeline_tag": m.get("pipeline_tag"),
            "sha12": m.get("sha"),
            "downloads": dl_counts.get(rid, 0),
            "provenance_status": "DECLARED" if m.get("license") and base else
                                 "LICENSE_ONLY" if m.get("license") else "UNKNOWN",
        })

    bom = {
        "ledger": "MODEL_BOM",
        "rule": "Every model needs license + base_model + training-data basis before diligence. UNKNOWN blocks the raise.",
        "summary": {
            "total": len(models),
            "license_declared": sum(1 for m in models if m["license"]),
            "base_declared": sum(1 for m in models if m["base_model"]),
            "third_party_bases": sum(1 for m in models if m["third_party_base"]),
        },
        "models": models,
    }

    # ---- DATASET LICENSE REGISTER
    datasets = []
    ds_priv = {e["path"]: e.get("private") for e in hf["datasets"]}
    for rid, m in sorted(lic["datasets"].items()):
        private = bool(ds_priv.get(rid))
        datasets.append({
            "dataset": rid,
            "license": m.get("license"),
            "private": private,
            "sha12": m.get("sha"),
            "provenance_status": "DECLARED" if m.get("license") else
                                 "UNKNOWN_PRIVATE" if private else "UNKNOWN",
            "note": "private repo — card not machine-readable anonymously; owner must declare" if private and not m.get("license") else "",
        })

    register = {
        "ledger": "DATASET_LICENSE_REGISTER",
        "rule": "Every public dataset needs a declared license + training-data rights basis. UNKNOWN_PRIVATE requires owner declaration.",
        "summary": {
            "total": len(datasets),
            "declared": sum(1 for d in datasets if d["license"]),
            "unknown": sum(1 for d in datasets if not d["license"]),
        },
        "datasets": datasets,
    }

    (LEDGERS / "MODEL_BOM.yaml").write_text(yamlite.dump(bom))
    (LEDGERS / "DATASET_LICENSE_REGISTER.yaml").write_text(yamlite.dump(register))
    print(f"MODEL_BOM: {bom['summary']}")
    print(f"DATASET_LICENSE_REGISTER: {register['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
