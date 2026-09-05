# SPDX-License-Identifier: Apache-2.0
"""Offline adversarial tests for the live GitHub estate/file census."""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "audit_github_estate.py"
SPEC = importlib.util.spec_from_file_location("audit_github_estate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def blob_entry(path: str, content: bytes, *, mode: str = "100644") -> dict[str, Any]:
    return {
        "path": path,
        "type": "blob",
        "mode": mode,
        "sha": MODULE.git_blob_sha(content),
        "size": len(content),
    }


class EstateClient:
    def __init__(
        self,
        repositories: list[dict[str, Any]],
        trees: dict[str, list[dict[str, Any]]],
        blobs: dict[str, bytes],
    ) -> None:
        self.repositories = repositories
        self.trees = trees
        self.blobs = blobs
        self.blob_requests: list[str] = []

    def paginated(self, endpoint: str):
        self.endpoint = endpoint
        yield from self.repositories

    def json(self, endpoint: str):
        if "/branches/" in endpoint:
            repository = endpoint.split("/repos/", 1)[1].split("/branches/", 1)[0]
            return {
                "commit": {
                    "sha": f"head-{repository.split('/')[-1]}",
                    "commit": {"tree": {"sha": f"tree-{repository.split('/')[-1]}"}},
                }
            }
        if "/git/trees/" in endpoint:
            repository = endpoint.split("/repos/", 1)[1].split("/git/trees/", 1)[0]
            return {"tree": self.trees[repository], "truncated": False}
        if "/git/blobs/" in endpoint:
            sha = endpoint.rsplit("/", 1)[1]
            self.blob_requests.append(sha)
            content = self.blobs[sha]
            return {
                "size": len(content),
                "encoding": "base64",
                "content": base64.b64encode(content).decode("ascii"),
            }
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    def blob_text(self, repository: str, sha: str, *, max_bytes: int):
        del repository
        self.blob_requests.append(sha)
        content = self.blobs[sha]
        return None if len(content) > max_bytes else content


class TruncatedTreeClient:
    def json(self, endpoint: str):
        if "/branches/" in endpoint:
            return {
                "commit": {
                    "sha": "head",
                    "commit": {"tree": {"sha": "root"}},
                }
            }
        if endpoint.endswith("/git/trees/root?recursive=1"):
            return {"tree": [], "truncated": True}
        if endpoint.endswith("/git/trees/root"):
            return {
                "tree": [
                    {"path": "README.md", "type": "blob", "mode": "100644", "sha": "a", "size": 3},
                    {"path": "src", "type": "tree", "mode": "040000", "sha": "child"},
                ]
            }
        if endpoint.endswith("/git/trees/child"):
            return {
                "tree": [
                    {"path": "main.py", "type": "blob", "mode": "100644", "sha": "b", "size": 8}
                ]
            }
        raise AssertionError(endpoint)


class ArchiveClient:
    def __init__(self, files: dict[str, bytes], symlinks: dict[str, str] | None = None) -> None:
        self.files = files
        self.symlinks = symlinks or {}

    def download_archive(
        self,
        repository: str,
        revision: str,
        destination: Path,
        *,
        max_bytes: int,
    ) -> int:
        del repository, revision, max_bytes
        with tarfile.open(destination, "w:gz") as archive:
            for path, content in self.files.items():
                info = tarfile.TarInfo(f"owner-repo-deadbeef/{path}")
                info.size = len(content)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(content))
            for path, target in self.symlinks.items():
                info = tarfile.TarInfo(f"owner-repo-deadbeef/{path}")
                info.type = tarfile.SYMTYPE
                info.linkname = target
                info.mode = 0o777
                archive.addfile(info)
        return destination.stat().st_size


class AuditGitHubEstateTests(unittest.TestCase):
    def test_control_run_addresses_every_file_and_labels_bounded_scan(self) -> None:
        content = {
            "README.md": b"# Product\n",
            "LICENSE": b"Apache License 2.0\n",
            "SECURITY.md": b"# Security\n",
            "app.py": b"print('ok')\n",
            "tests/test_app.py": b"def test_ok(): assert True\n",
            "package.json": b'{"name":"demo"}\n',
            "package-lock.json": b'{"lockfileVersion":3}\n',
            ".github/workflows/ci.yml": (
                b"name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
                b"    steps:\n      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n"
            ),
            "config/large.json": b"x" * 1024,
        }
        tree = [blob_entry(path, value) for path, value in content.items()]
        blobs = {entry["sha"]: content[entry["path"]] for entry in tree}
        client = EstateClient(
            [
                {
                    "full_name": "szl-holdings/demo",
                    "name": "demo",
                    "visibility": "public",
                    "private": False,
                    "archived": False,
                    "disabled": False,
                    "fork": False,
                    "default_branch": "main",
                    "size": 1,
                    "language": "Python",
                    "topics": [],
                }
            ],
            {"szl-holdings/demo": tree},
            blobs,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = MODULE.run(
                [
                    "--content-mode",
                    "control",
                    "--max-text-bytes",
                    "512",
                    "--workers",
                    "1",
                    "--fail-on",
                    "none",
                    "--output-json",
                    str(root / "audit.json"),
                    "--output-md",
                    str(root / "audit.md"),
                    "--output-csv",
                    str(root / "audit.csv"),
                ],
                client=client,
            )
            payload = json.loads((root / "audit.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(payload["coverage"]["repositories_discovered"], 1)
        self.assertEqual(payload["coverage"]["files_inventory_total"], len(content))
        self.assertTrue(payload["coverage"]["tree_inventory_complete"])
        self.assertTrue(payload["coverage"]["every_file_content_addressed"])
        self.assertTrue(payload["coverage"]["requested_audit_complete"])
        self.assertEqual(payload["repositories"][0]["content_status"], "CONTROL_BOUNDED_COMPLETE")
        self.assertEqual(payload["repositories"][0]["content_files_skipped_size"], 1)
        self.assertIn("CONTENT006", payload["finding_counts"]["by_rule"])
        large = next(item for item in payload["files"] if item["path"] == "config/large.json")
        self.assertFalse(large["content_fetched"])
        self.assertTrue(large["git_object_sha"])

    def test_unreadable_active_repository_fails_incomplete(self) -> None:
        class Client:
            def paginated(self, endpoint: str):
                del endpoint
                yield {
                    "full_name": "szl-holdings/unreadable",
                    "name": "unreadable",
                    "visibility": "private",
                    "private": True,
                    "archived": False,
                    "disabled": False,
                    "fork": False,
                    "default_branch": "main",
                    "size": 0,
                    "topics": [],
                }

            def json(self, endpoint: str):
                raise MODULE.AuditError(f"blocked {endpoint}")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = MODULE.run(
                [
                    "--content-mode",
                    "tree",
                    "--workers",
                    "1",
                    "--fail-on",
                    "incomplete",
                    "--output-json",
                    str(root / "audit.json"),
                    "--output-md",
                    str(root / "audit.md"),
                    "--output-csv",
                    str(root / "audit.csv"),
                ],
                client=Client(),
            )
            payload = json.loads((root / "audit.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(payload["state"], "INCOMPLETE")
        self.assertFalse(payload["coverage"]["requested_audit_complete"])
        self.assertIn("szl-holdings/unreadable", payload["coverage"]["active_repository_inventory_incomplete"])
        self.assertEqual(payload["finding_counts"]["by_rule"]["ESTATE001"], 1)

    def test_truncated_recursive_tree_is_walked_without_silent_loss(self) -> None:
        repository = {
            "repository": "szl-holdings/truncated",
            "name": "truncated",
            "private": False,
            "archived": False,
            "disabled": False,
            "fork": False,
            "default_branch": "main",
            "size_kib": 0,
        }
        record, files, findings = MODULE.inventory_repository(TruncatedTreeClient(), repository)
        self.assertTrue(record["inventory_complete"])
        self.assertTrue(record["tree_truncated"])
        self.assertTrue(record["tree_fallback_walked"])
        self.assertEqual([item["path"] for item in files], ["README.md", "src/main.py"])
        self.assertNotIn("ESTATE001", {item.rule_id for item in findings})

    def test_security_scanners_detect_unsafe_workflow_container_and_secret_contexts(self) -> None:
        workflow = """
name: unsafe
on:
  pull_request_target:
permissions: write-all
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: 'actions/checkout@v4'
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - run: curl https://example.invalid/install.sh | bash
"""
        rules = {item.rule_id for item in MODULE.scan_text_content("o/r", ".github/workflows/unsafe.yml", workflow)}
        self.assertTrue({"GHA001", "GHA002", "GHA003", "GHA004"} <= rules)
        docker_rules = {
            item.rule_id
            for item in MODULE.scan_text_content("o/r", "Dockerfile", "FROM python:3.12\n")
        }
        self.assertIn("CONTAINER001", docker_rules)
        token = "ghp_" + "A" * 40
        source_finding = MODULE.scan_text_content("o/r", "src/config.py", f'TOKEN = "{token}"\n')[0]
        doc_finding = MODULE.scan_text_content("o/r", "docs/example.md", token + "\n")[0]
        self.assertEqual((source_finding.rule_id, source_finding.severity), ("SECRET001", "critical"))
        self.assertEqual((doc_finding.rule_id, doc_finding.severity), ("SECRET002", "medium"))

    def test_archive_mode_byte_verifies_regular_files_and_git_symlinks(self) -> None:
        regular = b"alpha\n"
        symlink_target = "a.txt"
        raw = [
            blob_entry("a.txt", regular),
            blob_entry("link.txt", symlink_target.encode("utf-8"), mode="120000"),
        ]
        files = [MODULE.normalize_tree_entry("o/r", entry) for entry in raw]
        record = {
            "repository": "o/r",
            "head_sha": "deadbeef",
            "archived": False,
            "inventory_complete": True,
        }
        findings, used = MODULE.scan_archive(
            ArchiveClient({"a.txt": regular}, {"link.txt": symlink_target}),
            record,
            files,
            max_text_bytes=1024,
            max_archive_bytes=1024 * 1024,
        )
        self.assertGreater(used, 0)
        self.assertEqual(record["content_status"], "ARCHIVE_COMPLETE")
        self.assertEqual(record["archive_unverified_file_count"], 0)
        self.assertTrue(all(item["byte_verified"] for item in files))
        self.assertNotIn("CONTENT007", {item.rule_id for item in findings})

    def test_duplicate_source_blob_is_reported_across_active_repositories(self) -> None:
        content = b"def shared():\n    return 'same'\n" * 50
        sha = MODULE.git_blob_sha(content)
        files = [
            {
                "repository": "o/a",
                "path": "src/shared.py",
                "entry_type": "blob",
                "git_object_sha": sha,
                "size": len(content),
                "classification": "source_or_config",
            },
            {
                "repository": "o/b",
                "path": "lib/shared.py",
                "entry_type": "blob",
                "git_object_sha": sha,
                "size": len(content),
                "classification": "source_or_config",
            },
        ]
        findings = MODULE.duplicate_blob_findings(
            [{"repository": "o/a", "archived": False}, {"repository": "o/b", "archived": False}],
            files,
        )
        self.assertEqual(len(findings), 2)
        self.assertEqual({item.rule_id for item in findings}, {"DRIFT001"})

    def test_archive_scope_is_not_overclaimed_when_archived_repos_are_metadata_only(self) -> None:
        repositories = [
            {
                "repository": "o/active",
                "inventory_complete": True,
                "head_sha": "a",
                "archived": False,
                "disabled": False,
                "private": False,
                "fork": False,
                "total_blob_bytes": 1,
                "content_status": "ARCHIVE_COMPLETE",
            },
            {
                "repository": "o/archive",
                "inventory_complete": True,
                "head_sha": "b",
                "archived": True,
                "disabled": False,
                "private": False,
                "fork": False,
                "total_blob_bytes": 1,
                "content_status": "ARCHIVED_METADATA_ONLY",
            },
        ]
        files = {
            "o/active": [
                {
                    "repository": "o/active",
                    "path": "a",
                    "entry_type": "blob",
                    "git_object_sha": "x",
                    "byte_verified": True,
                    "content_fetched": True,
                    "content_scanned": True,
                }
            ],
            "o/archive": [
                {
                    "repository": "o/archive",
                    "path": "b",
                    "entry_type": "blob",
                    "git_object_sha": "y",
                    "byte_verified": False,
                    "content_fetched": False,
                    "content_scanned": False,
                }
            ],
        }
        payload = MODULE.build_summary(
            "o",
            repositories,
            files,
            [],
            content_mode="archive",
            observed_at="2026-09-05T00:00:00Z",
            include_archived_content=False,
        )
        self.assertTrue(payload["coverage"]["requested_audit_complete"])
        self.assertTrue(payload["coverage"]["archive_byte_verification_complete"])
        self.assertFalse(payload["coverage"]["full_estate_archive_complete"])
        self.assertEqual(payload["coverage"]["content_scope"], "active_repositories")


if __name__ == "__main__":
    unittest.main(verbosity=2)
