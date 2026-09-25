#!/usr/bin/env python3
"""public_snapshot.py — reduce a fresh API capture to rows that may be published.

Run after collecting audit_data/gh_repos.json, hf_org_listing.json and
hf_licenses.json, and before committing them. A row stays only when the
capture marks it public (GitHub visibility PUBLIC, Hub private false). Every
other row is removed, and only its aggregate count is written to
audit_data/withheld_private_counts.json so estate totals stay measured.

Running it on a snapshot that is already public-only changes nothing. If a
fresh capture has no non-public rows at all, delete the counts file by hand.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from audit_data_builder import WITHHELD_FILE, is_public_hf, is_public_repo

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit_data"


def filter_snapshot(gh_repos, hf, lic):
    """Return (gh, hf, lic) limited to public rows, plus counts of what was removed."""
    gh_public = [r for r in gh_repos if is_public_repo(r)]
    hf_public = {
        key: [r for r in rows if is_public_hf(r)] if isinstance(rows, list) else rows
        for key, rows in hf.items()
    }
    lic_public = {}
    for kind, entries in lic.items():
        listed = {r["path"] for r in hf_public.get(kind, [])}
        lic_public[kind] = {rid: e for rid, e in entries.items() if rid in listed and is_public_hf(e)}

    spaces = hf.get("spaces", [])
    counts = {
        "github_repos": len(gh_repos) - len(gh_public),
        "hf_spaces": len(spaces) - len(hf_public.get("spaces", [])),
        "hf_spaces_docker": sum(1 for s in spaces if s.get("sdk") == "docker" and not is_public_hf(s)),
        "hf_models": len(hf.get("models", [])) - len(hf_public.get("models", [])),
        "hf_datasets": len(hf.get("datasets", [])) - len(hf_public.get("datasets", [])),
    }
    return gh_public, hf_public, lic_public, counts


def main() -> int:
    gh_path = AUDIT / "gh_repos.json"
    hf_path = AUDIT / "hf_org_listing.json"
    lic_path = AUDIT / "hf_licenses.json"
    gh = json.loads(gh_path.read_text(encoding="utf-8"))
    hf = json.loads(hf_path.read_text(encoding="utf-8"))
    lic = json.loads(lic_path.read_text(encoding="utf-8"))

    gh_pub, hf_pub, lic_pub, counts = filter_snapshot(gh, hf, lic)
    lic_removed = sum(len(v) for v in lic.values()) - sum(len(v) for v in lic_pub.values())
    if not any(counts.values()) and not lic_removed:
        print("snapshot already public-only; nothing changed")
        return 0

    # Byte formats match the collectors: `gh --json` (compact) and the Hub listing (indent=1).
    gh_path.write_text(json.dumps(gh_pub, ensure_ascii=False, separators=(",", ":")) + "\n",
                       encoding="utf-8", newline="\n")
    hf_path.write_text(json.dumps(hf_pub, indent=1), encoding="utf-8", newline="\n")
    lic_path.write_text(json.dumps(lic_pub, indent=1), encoding="utf-8", newline="\n")
    if any(counts.values()):
        withheld = {
            "rule": ("Rows the capture did not mark public are not published. Only these "
                     "aggregate counts are kept so estate totals stay measured."),
            "generated_by": "tools/public_snapshot.py",
            "counts": counts,
        }
        (AUDIT / WITHHELD_FILE).write_text(json.dumps(withheld, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    print(f"withheld (counts only): {counts}; license rows removed: {lic_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
