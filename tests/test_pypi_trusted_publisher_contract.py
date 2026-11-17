"""Supply-chain/registry admission for the source-owned initial PyPI release."""
from __future__ import annotations

import hashlib
import re
import runpy
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/publish-pypi.yml"
GATE = ROOT / ".github/scripts/szl_pypi_release_gate.py"
CANONICAL_GATE_SHA256 = "6a8e0846b73c917f422f155fa28b10abefb277f44d15b5e757e4f4780be735ad"


def test_canonical_gate_is_byte_identical_to_estate_owned_gate():
    assert GATE.is_file()
    assert hashlib.sha256(GATE.read_bytes()).hexdigest() == CANONICAL_GATE_SHA256
    source = GATE.read_text(encoding="utf-8")
    assert "PRIVATE_CLASSIFIER" in source
    assert "pypi_versions" in source
    assert "tag_expect_single" in source
    assert "shutil.copy2" in source
    assert "declared = release_cfg.get" in source


def test_release_has_one_owned_package_and_exclusive_oidc_publisher():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'SZL_PACKAGES: "szl-gov=.:pypi"' in text
    assert "release:\n    types: [published]" in text
    assert "pull_request:" in text and "push:" in text
    assert "if: github.event_name == 'release'" in text
    assert "environment:\n      name: pypi" in text
    assert "id-token: write" in text
    assert "skip-existing: false" in text
    assert "verify-metadata: true" in text
    assert "attestations: true" in text
    assert "pypa/gh-action-pypi-publish@" in text
    assert "password:" not in text.lower()
    assert "pypi_token" not in text.lower()
    assert "twine upload" not in text.lower()
    assert "workflow_dispatch:" not in text


def test_every_workflow_action_is_sha_pinned():
    raw = WORKFLOW.read_text(encoding="utf-8")
    refs = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", raw, re.M)
    assert len(refs) >= 5
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", ref) for ref in refs)


def test_pypi_project_metadata_is_bound_to_org():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        metadata = tomllib.load(stream)
    project = metadata["project"]
    assert project["name"] == "szl-gov"
    assert project["version"] == "0.1.0"
    assert project["urls"]["Repository"] == "https://github.com/szl-holdings/szl-gov"
    assert metadata["tool"]["szl"]["release"]["import_names"] == ["szl_gov"]


def test_canonical_release_package_config_is_exact():
    gateway = runpy.run_path(str(GATE))
    assert gateway["parse_packages"]("szl-gov=.:pypi") == [
        {"name": "szl-gov", "dir": ".", "environment": "pypi"}
    ]
