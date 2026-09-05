#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Live, fail-closed GitHub estate and file census for SZL Holdings.

The controller inventories every repository visible to the supplied GitHub token and
every entry on each default branch.  It records exact Git blob identities, performs
bounded source/content checks, detects cross-repository duplication, and emits a
secret-free JSON receipt plus Markdown and CSV views.

The default ``tree`` mode is a complete metadata census. ``control`` additionally
reads every high-signal control/configuration file. ``archive`` downloads an exact
commit tarball for each eligible repository and scans every regular file whose
content fits the configured bound. Any unreadable repository, truncated tree that
cannot be walked, archive mismatch, or content budget exhaustion is represented as
an explicit incomplete state; it is never silently counted as passing.
"""
from __future__ import annotations

import argparse
import base64
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

API_ROOT = "https://api.github.com"
USER_AGENT = "szl-gov-live-estate-file-audit/1.0"
SCHEMA = "szl.github-estate-file-audit/v1"

TEXT_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cfg",
        ".conf",
        ".cpp",
        ".cs",
        ".css",
        ".csv",
        ".dockerfile",
        ".env",
        ".go",
        ".graphql",
        ".h",
        ".hpp",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsonl",
        ".jsx",
        ".kt",
        ".kts",
        ".lock",
        ".lua",
        ".md",
        ".mjs",
        ".mts",
        ".properties",
        ".proto",
        ".ps1",
        ".py",
        ".rb",
        ".rego",
        ".rs",
        ".rst",
        ".scala",
        ".scss",
        ".sh",
        ".sql",
        ".svg",
        ".tf",
        ".tfvars",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".vue",
        ".xml",
        ".yaml",
        ".yml",
        ".zig",
    }
)

CONTROL_BASENAMES = frozenset(
    {
        ".dockerignore",
        ".env",
        ".gitattributes",
        ".gitignore",
        ".npmrc",
        ".pre-commit-config.yaml",
        ".pre-commit-config.yml",
        "Cargo.lock",
        "Cargo.toml",
        "CODEOWNERS",
        "CONTRIBUTING.md",
        "Dockerfile",
        "Gemfile",
        "Gemfile.lock",
        "LICENSE",
        "Makefile",
        "NOTICE",
        "Pipfile",
        "Pipfile.lock",
        "README.md",
        "SECURITY.md",
        "Taskfile.yml",
        "bun.lock",
        "bun.lockb",
        "compose.yaml",
        "compose.yml",
        "deno.json",
        "deno.lock",
        "go.mod",
        "go.sum",
        "package-lock.json",
        "package.json",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
        "yarn.lock",
    }
)

DEPENDENCY_MANIFESTS = frozenset(
    {
        "Cargo.toml",
        "Gemfile",
        "Pipfile",
        "go.mod",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
    }
)

LOCKFILES = frozenset(
    {
        "Cargo.lock",
        "Gemfile.lock",
        "Pipfile.lock",
        "bun.lock",
        "bun.lockb",
        "deno.lock",
        "go.sum",
        "package-lock.json",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
    }
)

COMMON_DUPLICATE_BASENAMES = frozenset(
    {
        ".gitignore",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "NOTICE",
        "README.md",
        "SECURITY.md",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    }
)

GENERATED_SEGMENTS = frozenset(
    {
        ".next",
        ".venv",
        "build",
        "coverage",
        "dist",
        "generated",
        "node_modules",
        "target",
        "vendor",
        "vendored",
    }
)

SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,255}|github_pat_[A-Za-z0-9_]{50,255})\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe-live-key", re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b")),
)

PLACEHOLDER_WORDS = frozenset(
    {
        "example",
        "fake",
        "placeholder",
        "redacted",
        "sample",
        "test-token",
        "your-token",
        "***",
        "<token>",
        "${",
        "{{",
    }
)

ACTION_USE_RE = re.compile(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)")
DOCKER_FROM_RE = re.compile(r"(?mi)^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)")
CURL_PIPE_RE = re.compile(r"(?i)(?:curl|wget)[^\n|]{0,400}\|\s*(?:sudo\s+)?(?:bash|sh)\b")


class AuditError(RuntimeError):
    """Base class for deterministic audit failures."""


class GitHubApiError(AuditError):
    """A redacted GitHub API error."""

    def __init__(self, status: int, endpoint: str, message: str = "") -> None:
        self.status = status
        self.endpoint = endpoint
        super().__init__(f"GitHub API HTTP {status} for {endpoint}: {message[:240]}")


@dataclasses.dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    rule_id: str
    repository: str
    path: str | None
    line: int | None
    message: str
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class GitHubClient:
    """Small dependency-free GitHub REST client with bounded retries."""

    def __init__(
        self,
        token: str,
        *,
        api_root: str = API_ROOT,
        timeout: float = 45.0,
        retries: int = 4,
        sleep: Any = time.sleep,
    ) -> None:
        if not token:
            raise AuditError("GITHUB_TOKEN/ESTATE_GITHUB_TOKEN is required")
        self._token = token
        self.api_root = api_root.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.sleep = sleep

    def _url(self, endpoint: str) -> str:
        if endpoint.startswith("https://"):
            return endpoint
        return self.api_root + "/" + endpoint.lstrip("/")

    def _request(self, endpoint: str, *, accept: str = "application/vnd.github+json"):
        url = self._url(endpoint)
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self._token}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        return urllib.request.Request(url, headers=headers, method="GET")

    def open(self, endpoint: str, *, accept: str = "application/vnd.github+json"):
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                return urllib.request.urlopen(
                    self._request(endpoint, accept=accept), timeout=self.timeout
                )
            except urllib.error.HTTPError as exc:
                last = exc
                transient = exc.code in {429, 500, 502, 503, 504}
                rate_limited = exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0"
                if attempt < self.retries and (transient or rate_limited):
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        delay = min(float(retry_after), 30.0)
                    elif rate_limited and exc.headers.get("X-RateLimit-Reset", "").isdigit():
                        delay = min(
                            max(float(exc.headers["X-RateLimit-Reset"]) - time.time(), 1.0),
                            30.0,
                        )
                    else:
                        delay = min(2.0 ** (attempt - 1), 10.0)
                    self.sleep(delay)
                    continue
                try:
                    payload = exc.read(2048).decode("utf-8", errors="replace")
                    message = json.loads(payload).get("message", payload)
                except Exception:
                    message = str(exc.reason or "request failed")
                raise GitHubApiError(exc.code, endpoint, str(message)) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
                if attempt < self.retries:
                    self.sleep(min(2.0 ** (attempt - 1), 10.0))
                    continue
                raise AuditError(
                    f"GitHub transport failed for {endpoint}: {type(exc).__name__}"
                ) from None
        raise AuditError(f"GitHub request failed for {endpoint}: {type(last).__name__}")

    def json(self, endpoint: str) -> Any:
        with self.open(endpoint) as response:
            return json.loads(response.read().decode("utf-8"))

    def paginated(self, endpoint: str) -> Iterator[Any]:
        page = 1
        joiner = "&" if "?" in endpoint else "?"
        while True:
            items = self.json(f"{endpoint}{joiner}per_page=100&page={page}")
            if not isinstance(items, list):
                raise AuditError(f"expected list response from {endpoint}")
            yield from items
            if len(items) < 100:
                return
            page += 1

    def blob_text(self, repository: str, sha: str, *, max_bytes: int) -> bytes | None:
        payload = self.json(f"/repos/{repository}/git/blobs/{sha}")
        if not isinstance(payload, Mapping):
            raise AuditError(f"invalid blob response for {repository}@{sha}")
        size = int(payload.get("size") or 0)
        if size > max_bytes:
            return None
        if payload.get("encoding") != "base64":
            raise AuditError(f"unsupported blob encoding for {repository}@{sha}")
        return base64.b64decode(str(payload.get("content") or ""), validate=False)

    def download_archive(
        self,
        repository: str,
        revision: str,
        destination: Path,
        *,
        max_bytes: int,
    ) -> int:
        endpoint = f"/repos/{repository}/tarball/{urllib.parse.quote(revision, safe='')}"
        written = 0
        with self.open(endpoint, accept="application/vnd.github+json") as response:
            length = response.headers.get("Content-Length", "")
            if length.isdigit() and int(length) > max_bytes:
                raise AuditError(
                    f"archive exceeds per-repository byte bound for {repository}"
                )
            with destination.open("wb") as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise AuditError(
                            f"archive exceeded per-repository byte bound for {repository}"
                        )
                    stream.write(chunk)
        return written


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def fingerprint(*parts: object) -> str:
    joined = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


def finding(
    severity: str,
    rule_id: str,
    repository: str,
    message: str,
    *,
    path: str | None = None,
    line: int | None = None,
) -> Finding:
    return Finding(
        severity=severity,
        rule_id=rule_id,
        repository=repository,
        path=path,
        line=line,
        message=message,
        fingerprint=fingerprint(rule_id, repository, path or "", line or 0, message),
    )


def path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in Path(path).parts)


def is_generated_or_vendor(path: str) -> bool:
    return bool(set(path_parts(path)) & GENERATED_SEGMENTS)


def is_workflow(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith(".github/workflows/") and lowered.endswith((".yml", ".yaml"))


def is_container_file(path: str) -> bool:
    name = Path(path).name.lower()
    return name == "dockerfile" or name.startswith("dockerfile.") or path.lower().endswith(
        ("compose.yml", "compose.yaml")
    )


def is_infrastructure(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".tf", ".tfvars")) or any(
        segment in path_parts(path)
        for segment in ("helm", "infra", "infrastructure", "k8s", "kubernetes", "terraform")
    )


def is_test(path: str) -> bool:
    lowered = path.lower()
    return (
        "/tests/" in f"/{lowered}"
        or "/test/" in f"/{lowered}"
        or Path(lowered).name.startswith("test_")
        or lowered.endswith((".test.js", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".spec.tsx"))
    )


def is_doc(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".md", ".rst")) or lowered.startswith(("docs/", "documentation/"))


def is_text_candidate(path: str) -> bool:
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    return suffix in TEXT_SUFFIXES or name in CONTROL_BASENAMES or is_workflow(path)


def is_control_candidate(path: str) -> bool:
    name = Path(path).name
    lowered = path.lower()
    return (
        name in CONTROL_BASENAMES
        or is_workflow(path)
        or is_container_file(path)
        or is_infrastructure(path)
        or lowered.startswith(("config/", ".github/", "policies/", "policy/", "deploy/"))
        or lowered.endswith((".rego", ".lock", ".toml", ".yaml", ".yml", ".json"))
    )


def classify_path(path: str, entry_type: str, size: int) -> str:
    if entry_type == "commit":
        return "submodule"
    if is_generated_or_vendor(path):
        return "generated_or_vendor"
    if is_workflow(path):
        return "workflow"
    if is_container_file(path):
        return "container"
    if is_infrastructure(path):
        return "infrastructure"
    if is_test(path):
        return "test"
    if is_doc(path):
        return "documentation"
    if Path(path).name in DEPENDENCY_MANIFESTS:
        return "dependency_manifest"
    if Path(path).name in LOCKFILES:
        return "lockfile"
    if is_text_candidate(path):
        return "source_or_config"
    if size >= 10 * 1024 * 1024:
        return "large_binary_or_asset"
    return "asset_or_binary"


def normalize_tree_entry(repository: str, entry: Mapping[str, Any]) -> dict[str, Any]:
    path = str(entry.get("path") or "")
    entry_type = str(entry.get("type") or "unknown")
    size = int(entry.get("size") or 0)
    return {
        "repository": repository,
        "path": path,
        "entry_type": entry_type,
        "mode": str(entry.get("mode") or ""),
        "git_object_sha": str(entry.get("sha") or ""),
        "size": size,
        "classification": classify_path(path, entry_type, size),
        "content_fetched": False,
        "content_scanned": False,
        "byte_verified": False,
        "content_sha256": None,
        "binary": None,
        "lfs_pointer": False,
    }


def list_repositories(client: GitHubClient, org: str) -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    for raw in client.paginated(f"/orgs/{org}/repos?type=all&sort=full_name&direction=asc"):
        if not isinstance(raw, Mapping):
            continue
        repositories.append(
            {
                "repository": str(raw.get("full_name") or ""),
                "name": str(raw.get("name") or ""),
                "visibility": str(raw.get("visibility") or ("private" if raw.get("private") else "public")),
                "private": bool(raw.get("private")),
                "archived": bool(raw.get("archived")),
                "disabled": bool(raw.get("disabled")),
                "fork": bool(raw.get("fork")),
                "default_branch": raw.get("default_branch"),
                "size_kib": int(raw.get("size") or 0),
                "language": raw.get("language"),
                "topics": sorted(str(item) for item in (raw.get("topics") or [])),
                "updated_at": raw.get("updated_at"),
                "pushed_at": raw.get("pushed_at"),
                "homepage": raw.get("homepage"),
                "description": raw.get("description"),
            }
        )
    repositories.sort(key=lambda item: item["repository"].casefold())
    return repositories


def _walk_tree(client: GitHubClient, repository: str, tree_sha: str) -> list[dict[str, Any]]:
    stack: list[tuple[str, str]] = [("", tree_sha)]
    seen_trees: set[str] = set()
    entries: list[dict[str, Any]] = []
    while stack:
        prefix, current_sha = stack.pop()
        if current_sha in seen_trees:
            continue
        seen_trees.add(current_sha)
        payload = client.json(f"/repos/{repository}/git/trees/{current_sha}")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("tree"), list):
            raise AuditError(f"invalid tree response for {repository}@{current_sha}")
        for raw in payload["tree"]:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("path") or "")
            full_path = f"{prefix}/{name}" if prefix else name
            item = dict(raw)
            item["path"] = full_path
            if raw.get("type") == "tree":
                stack.append((full_path, str(raw.get("sha") or "")))
            else:
                entries.append(item)
    return entries


def inventory_repository(
    client: GitHubClient, repository: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Finding]]:
    record = dict(repository)
    repo_name = str(record["repository"])
    findings: list[Finding] = []
    default_branch = record.get("default_branch")
    record.update(
        {
            "head_sha": None,
            "tree_sha": None,
            "tree_truncated": False,
            "tree_fallback_walked": False,
            "inventory_complete": False,
            "content_status": "NOT_REQUESTED",
            "file_count": 0,
            "blob_count": 0,
            "submodule_count": 0,
            "total_blob_bytes": 0,
            "counts_by_classification": {},
            "error": None,
        }
    )
    if not default_branch:
        record["inventory_complete"] = True
        record["content_status"] = "EMPTY_OR_BRANCHLESS"
        return record, [], findings
    try:
        branch = client.json(
            f"/repos/{repo_name}/branches/{urllib.parse.quote(str(default_branch), safe='')}"
        )
        commit = branch.get("commit") if isinstance(branch, Mapping) else None
        record["head_sha"] = str((commit or {}).get("sha") or "") or None
        tree_sha = str((((commit or {}).get("commit") or {}).get("tree") or {}).get("sha") or "")
        if not tree_sha:
            commit_payload = client.json(f"/repos/{repo_name}/commits/{record['head_sha']}")
            tree_sha = str(((commit_payload.get("commit") or {}).get("tree") or {}).get("sha") or "")
        if not tree_sha:
            raise AuditError(f"default branch tree SHA unavailable for {repo_name}")
        record["tree_sha"] = tree_sha
        payload = client.json(f"/repos/{repo_name}/git/trees/{tree_sha}?recursive=1")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("tree"), list):
            raise AuditError(f"invalid recursive tree response for {repo_name}")
        record["tree_truncated"] = bool(payload.get("truncated"))
        raw_entries = payload["tree"]
        if record["tree_truncated"]:
            raw_entries = _walk_tree(client, repo_name, tree_sha)
            record["tree_fallback_walked"] = True
        files = [
            normalize_tree_entry(repo_name, entry)
            for entry in raw_entries
            if isinstance(entry, Mapping) and entry.get("type") in {"blob", "commit"}
        ]
        files.sort(key=lambda item: item["path"].casefold())
        record["file_count"] = len(files)
        record["blob_count"] = sum(item["entry_type"] == "blob" for item in files)
        record["submodule_count"] = sum(item["entry_type"] == "commit" for item in files)
        record["total_blob_bytes"] = sum(
            item["size"] for item in files if item["entry_type"] == "blob"
        )
        record["counts_by_classification"] = dict(
            sorted(Counter(item["classification"] for item in files).items())
        )
        record["inventory_complete"] = True
        _repository_structure_findings(record, files, findings)
        return record, files, findings
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        severity = "medium" if record.get("archived") else "critical"
        findings.append(
            finding(
                severity,
                "ESTATE001",
                repo_name,
                "default-branch file inventory could not be completed",
            )
        )
        return record, [], findings


def _repository_structure_findings(
    record: Mapping[str, Any], files: Sequence[Mapping[str, Any]], findings: list[Finding]
) -> None:
    repository = str(record["repository"])
    paths = {str(item["path"]) for item in files}
    paths_casefold = {path.casefold() for path in paths}
    basenames = {Path(path).name for path in paths}
    classifications = Counter(str(item["classification"]) for item in files)
    active = not record.get("archived") and not record.get("disabled")
    public = not record.get("private")
    has_code = bool(
        classifications["source_or_config"]
        or classifications["test"]
        or classifications["container"]
        or classifications["infrastructure"]
        or classifications["dependency_manifest"]
    )
    if active and "readme.md" not in paths_casefold:
        findings.append(finding("medium", "GOV001", repository, "active repository has no root README.md"))
    root_license = any(
        "/" not in path and Path(path).name.casefold().startswith("license")
        for path in paths
    )
    if active and public and not root_license:
        findings.append(
            finding("medium", "GOV002", repository, "active public repository has no root license file")
        )
    if active and public and not ({"security.md", ".github/security.md"} & paths_casefold):
        findings.append(
            finding("low", "GOV003", repository, "active public repository has no root or .github/SECURITY.md")
        )
    if active and has_code and classifications["workflow"] == 0:
        findings.append(
            finding("high", "CI001", repository, "active code repository has no GitHub Actions workflow")
        )
    if active and has_code and classifications["test"] == 0:
        findings.append(
            finding("medium", "CI002", repository, "active code repository exposes no test file in its default branch")
        )
    manifests = basenames & DEPENDENCY_MANIFESTS
    lockfiles = basenames & LOCKFILES
    if active and manifests and not lockfiles:
        findings.append(
            finding(
                "medium",
                "SUPPLY001",
                repository,
                "dependency manifest is present without a recognized lockfile",
            )
        )
    if record.get("fork") and active:
        findings.append(
            finding("info", "ESTATE002", repository, "active repository is a fork; ownership and sync policy should be explicit")
        )
    for item in files:
        size = int(item.get("size") or 0)
        if size >= 100 * 1024 * 1024:
            findings.append(
                finding(
                    "high",
                    "FILE001",
                    repository,
                    f"committed object is {size} bytes; verify Git LFS or artifact storage ownership",
                    path=str(item["path"]),
                )
            )
        elif size >= 25 * 1024 * 1024:
            findings.append(
                finding(
                    "medium",
                    "FILE001",
                    repository,
                    f"large committed object is {size} bytes",
                    path=str(item["path"]),
                )
            )


def decode_text(content: bytes) -> tuple[str | None, bool]:
    if b"\x00" in content[:8192]:
        return None, True
    try:
        return content.decode("utf-8"), False
    except UnicodeDecodeError:
        try:
            return content.decode("utf-8", errors="replace"), True
        except Exception:
            return None, True


def _secret_line_is_placeholder(line: str, path: str) -> bool:
    del path
    lowered = line.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def git_blob_sha(content: bytes) -> str:
    """Return Git's SHA-1 object identity for one blob payload."""
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()  # noqa: S324 - Git object identity


def scan_text_content(
    repository: str,
    path: str,
    text: str,
) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    if is_workflow(path):
        for match in ACTION_USE_RE.finditer(text):
            target = match.group(1).strip("\"'")
            if target.startswith("./"):
                continue
            if target.startswith("docker://"):
                if "@sha256:" not in target:
                    line = text.count("\n", 0, match.start()) + 1
                    findings.append(
                        finding(
                            "high",
                            "GHA001",
                            repository,
                            "container action is not pinned by sha256 digest",
                            path=path,
                            line=line,
                        )
                    )
                continue
            if "@" not in target or not re.search(r"@[0-9a-fA-F]{40}$", target):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    finding(
                        "high",
                        "GHA001",
                        repository,
                        "third-party GitHub Action is not pinned to a 40-character commit SHA",
                        path=path,
                        line=line,
                    )
                )
        if re.search(r"(?m)^\s*pull_request_target\s*:", text):
            if re.search(r"github\.event\.pull_request\.head\.(?:sha|ref)", text):
                findings.append(
                    finding(
                        "critical",
                        "GHA002",
                        repository,
                        "pull_request_target workflow references pull-request head code",
                        path=path,
                    )
                )
        if re.search(r"(?m)^\s*permissions\s*:\s*write-all\s*$", text):
            findings.append(
                finding(
                    "high",
                    "GHA003",
                    repository,
                    "workflow grants write-all permissions",
                    path=path,
                )
            )
        for match in CURL_PIPE_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                finding(
                    "high",
                    "GHA004",
                    repository,
                    "workflow pipes network content directly into a shell",
                    path=path,
                    line=line,
                )
            )
    if is_container_file(path):
        for match in DOCKER_FROM_RE.finditer(text):
            image = match.group(1)
            if image.lower() == "scratch" or "@sha256:" in image:
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                finding(
                    "high",
                    "CONTAINER001",
                    repository,
                    "container base image is not pinned to a sha256 digest",
                    path=path,
                    line=line,
                )
            )
    for line_number, line in enumerate(lines, start=1):
        if _secret_line_is_placeholder(line, path):
            continue
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                lower_risk_context = is_doc(path) or is_test(path) or "fixture" in path.lower()
                findings.append(
                    finding(
                        "medium" if lower_risk_context else "critical",
                        "SECRET002" if lower_risk_context else "SECRET001",
                        repository,
                        (
                            f"credential-shaped {name} pattern appears in documentation/test content; "
                            "verify that it is synthetic; value omitted"
                            if lower_risk_context
                            else f"high-confidence committed {name} pattern detected; value omitted"
                        ),
                        path=path,
                        line=line_number,
                    )
                )
    return findings


def apply_content(
    repository: str,
    file_record: dict[str, Any],
    content: bytes,
    *,
    max_text_bytes: int,
) -> list[Finding]:
    findings: list[Finding] = []
    file_record["content_fetched"] = True
    file_record["content_sha256"] = hashlib.sha256(content).hexdigest()
    expected_git_sha = str(file_record.get("git_object_sha") or "")
    observed_git_sha = git_blob_sha(content)
    file_record["byte_verified"] = bool(expected_git_sha and observed_git_sha == expected_git_sha)
    if expected_git_sha and observed_git_sha != expected_git_sha:
        findings.append(
            finding(
                "critical",
                "CONTENT007",
                repository,
                "fetched bytes do not match the exact Git blob identity",
                path=str(file_record["path"]),
            )
        )
    file_record["lfs_pointer"] = content.startswith(
        b"version https://git-lfs.github.com/spec/v1"
    )
    if len(content) > max_text_bytes:
        file_record["binary"] = None
        file_record["content_scanned"] = False
        return findings
    text, binary = decode_text(content)
    file_record["binary"] = binary
    if text is None or binary:
        file_record["content_scanned"] = False
        return findings
    file_record["content_scanned"] = True
    findings.extend(scan_text_content(repository, str(file_record["path"]), text))
    return findings


def scan_control_blobs(
    client: GitHubClient,
    record: dict[str, Any],
    files: list[dict[str, Any]],
    *,
    max_text_bytes: int,
) -> list[Finding]:
    findings: list[Finding] = []
    repository = str(record["repository"])
    attempted = 0
    fetched = 0
    rule_scanned = 0
    skipped_size = 0
    errors: list[str] = []
    for item in files:
        if item["entry_type"] != "blob" or not is_control_candidate(str(item["path"])):
            continue
        attempted += 1
        if int(item.get("size") or 0) > max_text_bytes:
            skipped_size += 1
            continue
        try:
            content = client.blob_text(
                repository, str(item["git_object_sha"]), max_bytes=max_text_bytes
            )
            if content is None:
                skipped_size += 1
                continue
            findings.extend(
                apply_content(repository, item, content, max_text_bytes=max_text_bytes)
            )
            fetched += 1
            rule_scanned += int(bool(item.get("content_scanned")))
        except Exception as exc:
            errors.append(f"{item['path']}: {type(exc).__name__}")
    if errors:
        record["content_status"] = "CONTROL_PARTIAL"
    elif skipped_size:
        record["content_status"] = "CONTROL_BOUNDED_COMPLETE"
    else:
        record["content_status"] = "CONTROL_COMPLETE"
    record["content_files_attempted"] = attempted
    record["content_files_fetched"] = fetched
    record["content_files_scanned"] = rule_scanned
    record["content_files_skipped_size"] = skipped_size
    record["content_errors"] = errors[:50]
    if skipped_size:
        findings.append(
            finding(
                "medium",
                "CONTENT006",
                repository,
                f"{skipped_size} high-signal file(s) exceeded the configured text-rule bound; exact Git blob identities remain recorded",
            )
        )
    if errors:
        findings.append(
            finding(
                "high" if not record.get("archived") else "medium",
                "CONTENT001",
                repository,
                f"{len(errors)} high-signal file(s) could not be content-audited",
            )
        )
    return findings


def _strip_archive_root(name: str) -> str:
    name = name.lstrip("./")
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else ""


def scan_archive(
    client: GitHubClient,
    record: dict[str, Any],
    files: list[dict[str, Any]],
    *,
    max_text_bytes: int,
    max_archive_bytes: int,
) -> tuple[list[Finding], int]:
    repository = str(record["repository"])
    findings: list[Finding] = []
    by_path = {str(item["path"]): item for item in files if item["entry_type"] == "blob"}
    observed_paths: set[str] = set()
    unexpected = 0
    unverified = 0
    scanned = 0
    with tempfile.TemporaryDirectory(prefix="szl-estate-") as directory:
        archive_path = Path(directory) / "repository.tar.gz"
        archive_bytes = client.download_archive(
            repository,
            str(record["head_sha"]),
            archive_path,
            max_bytes=max_archive_bytes,
        )
        with tarfile.open(archive_path, mode="r:*") as archive:
            for member in archive:
                if not (member.isfile() or member.issym() or member.islnk()):
                    continue
                path = _strip_archive_root(member.name)
                if not path:
                    continue
                observed_paths.add(path)
                item = by_path.get(path)
                if item is None:
                    unexpected += 1
                    findings.append(
                        finding(
                            "high",
                            "CONTENT002",
                            repository,
                            "archive contains a file absent from the exact Git tree",
                            path=path,
                        )
                    )
                    continue

                if member.issym():
                    content = member.linkname.encode("utf-8", errors="surrogateescape")
                    findings.extend(
                        apply_content(
                            repository,
                            item,
                            content,
                            max_text_bytes=max_text_bytes,
                        )
                    )
                    scanned += int(bool(item.get("content_scanned")))
                    unverified += int(not bool(item.get("byte_verified")))
                    continue

                if member.islnk():
                    unverified += 1
                    findings.append(
                        finding(
                            "high",
                            "CONTENT008",
                            repository,
                            "commit archive used a hard-link entry that could not be independently bound to its Git blob",
                            path=path,
                        )
                    )
                    continue

                expected_size = int(item.get("size") or 0)
                if member.size != expected_size:
                    findings.append(
                        finding(
                            "critical",
                            "CONTENT009",
                            repository,
                            f"archive member size {member.size} does not match Git tree size {expected_size}",
                            path=path,
                        )
                    )
                extracted = archive.extractfile(member)
                if extracted is None:
                    unverified += 1
                    findings.append(
                        finding(
                            "high",
                            "CONTENT010",
                            repository,
                            "archive member could not be read for byte verification",
                            path=path,
                        )
                    )
                    continue

                sha1 = hashlib.sha1()  # noqa: S324 - Git object identity
                sha1.update(f"blob {member.size}\0".encode("ascii"))
                sha256 = hashlib.sha256()
                content_buffer = bytearray() if member.size <= max_text_bytes else None
                actual_size = 0
                while True:
                    chunk = extracted.read(1024 * 1024)
                    if not chunk:
                        break
                    actual_size += len(chunk)
                    sha1.update(chunk)
                    sha256.update(chunk)
                    if content_buffer is not None:
                        content_buffer.extend(chunk)
                item["content_fetched"] = True
                item["content_sha256"] = sha256.hexdigest()
                item["byte_verified"] = sha1.hexdigest() == str(item.get("git_object_sha") or "")
                if actual_size != member.size:
                    item["byte_verified"] = False
                    findings.append(
                        finding(
                            "critical",
                            "CONTENT011",
                            repository,
                            f"archive stream yielded {actual_size} bytes but header declared {member.size}",
                            path=path,
                        )
                    )
                if not item["byte_verified"]:
                    unverified += 1
                    findings.append(
                        finding(
                            "critical",
                            "CONTENT007",
                            repository,
                            "archive bytes do not match the exact Git blob identity",
                            path=path,
                        )
                    )
                if content_buffer is not None:
                    # apply_content also sets text/binary classification and executes
                    # bounded semantic checks. The repeated hashes are intentional:
                    # this small-file path shares the exact blob-verification contract
                    # with control-mode reads.
                    findings.extend(
                        apply_content(
                            repository,
                            item,
                            bytes(content_buffer),
                            max_text_bytes=max_text_bytes,
                        )
                    )
                    scanned += int(bool(item.get("content_scanned")))
                else:
                    item["binary"] = None
                    item["content_scanned"] = False

        missing = sorted(set(by_path) - observed_paths)
        for path in missing[:200]:
            findings.append(
                finding(
                    "high",
                    "CONTENT003",
                    repository,
                    "exact Git-tree file is absent from the downloaded commit archive",
                    path=path,
                )
            )
        record["archive_bytes"] = archive_bytes
        record["archive_files_observed"] = len(observed_paths)
        record["archive_missing_file_count"] = len(missing)
        record["archive_unexpected_file_count"] = unexpected
        record["archive_unverified_file_count"] = unverified
        record["content_files_fetched"] = sum(bool(item.get("content_fetched")) for item in files)
        record["content_files_scanned"] = scanned
        record["content_files_skipped_size"] = sum(
            item["entry_type"] == "blob"
            and bool(item.get("content_fetched"))
            and not bool(item.get("content_scanned"))
            and int(item.get("size") or 0) > max_text_bytes
            for item in files
        )
        record["content_status"] = (
            "ARCHIVE_COMPLETE"
            if not missing and not unexpected and not unverified
            else "ARCHIVE_MISMATCH"
        )
        return findings, archive_bytes


def content_audit(
    client: GitHubClient,
    repositories: list[dict[str, Any]],
    files_by_repo: dict[str, list[dict[str, Any]]],
    *,
    mode: str,
    max_text_bytes: int,
    max_archive_bytes: int,
    max_total_archive_bytes: int,
    include_archived_content: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    total_archive_bytes = 0
    for record in repositories:
        repository = str(record["repository"])
        files = files_by_repo.get(repository, [])
        if not record.get("inventory_complete") or not record.get("head_sha"):
            continue
        if record.get("archived") and not include_archived_content:
            record["content_status"] = "ARCHIVED_METADATA_ONLY"
            continue
        if mode == "tree":
            record["content_status"] = "TREE_METADATA_ONLY"
            continue
        if mode == "control":
            findings.extend(
                scan_control_blobs(
                    client, record, files, max_text_bytes=max_text_bytes
                )
            )
            continue
        estimate = max(int(record.get("size_kib") or 0) * 1024, 1)
        if total_archive_bytes + estimate > max_total_archive_bytes:
            record["content_status"] = "ARCHIVE_SKIPPED_TOTAL_BUDGET"
            findings.append(
                finding(
                    "high",
                    "CONTENT004",
                    repository,
                    "full-content archive audit skipped because the estate byte budget was exhausted",
                )
            )
            continue
        try:
            repo_findings, used = scan_archive(
                client,
                record,
                files,
                max_text_bytes=max_text_bytes,
                max_archive_bytes=max_archive_bytes,
            )
            findings.extend(repo_findings)
            total_archive_bytes += used
        except Exception as exc:
            record["content_status"] = "ARCHIVE_FAILED"
            record["content_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            findings.append(
                finding(
                    "high" if not record.get("archived") else "medium",
                    "CONTENT005",
                    repository,
                    "full-content archive audit failed; repository remains explicitly incomplete",
                )
            )
    return findings


def duplicate_blob_findings(
    repositories: Sequence[Mapping[str, Any]], files: Iterable[Mapping[str, Any]]
) -> list[Finding]:
    archived = {str(item["repository"]): bool(item.get("archived")) for item in repositories}
    groups: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for item in files:
        if item.get("entry_type") != "blob":
            continue
        size = int(item.get("size") or 0)
        path = str(item.get("path") or "")
        if size < 1024 or Path(path).name in COMMON_DUPLICATE_BASENAMES:
            continue
        if item.get("classification") in {"documentation", "lockfile", "generated_or_vendor"}:
            continue
        sha = str(item.get("git_object_sha") or "")
        if sha:
            groups[(sha, size)].append(item)
    findings: list[Finding] = []
    for (sha, size), members in sorted(groups.items()):
        active_repositories = sorted(
            {str(item["repository"]) for item in members if not archived.get(str(item["repository"]), False)}
        )
        if len(active_repositories) < 2:
            continue
        sample = ", ".join(
            f"{item['repository']}:{item['path']}" for item in sorted(
                members, key=lambda value: (str(value["repository"]), str(value["path"]))
            )[:6]
        )
        for repository in active_repositories:
            findings.append(
                finding(
                    "medium",
                    "DRIFT001",
                    repository,
                    f"exact {size}-byte source/config blob is duplicated across active repositories ({sha[:12]}): {sample}",
                )
            )
    return findings


def build_summary(
    org: str,
    repositories: list[dict[str, Any]],
    files_by_repo: Mapping[str, Sequence[Mapping[str, Any]]],
    findings: Sequence[Finding],
    *,
    content_mode: str,
    observed_at: str,
    include_archived_content: bool,
) -> dict[str, Any]:
    all_files = [item for repository in repositories for item in files_by_repo.get(repository["repository"], [])]
    severity_counts = Counter(item.severity for item in findings)
    rule_counts = Counter(item.rule_id for item in findings)
    complete_inventory = all(item.get("inventory_complete") for item in repositories)
    active_incomplete = [
        item["repository"]
        for item in repositories
        if not item.get("archived") and not item.get("inventory_complete")
    ]
    content_scope_records = [
        item
        for item in repositories
        if item.get("inventory_complete")
        and item.get("head_sha")
        and (include_archived_content or not item.get("archived"))
    ]
    archive_incomplete_states = {
        "ARCHIVE_FAILED",
        "ARCHIVE_MISMATCH",
        "ARCHIVE_SKIPPED_TOTAL_BUDGET",
    }
    control_incomplete_states = {"CONTROL_PARTIAL"}
    content_incomplete_states = (
        archive_incomplete_states
        if content_mode == "archive"
        else control_incomplete_states
        if content_mode == "control"
        else set()
    )
    content_incomplete = [
        item["repository"]
        for item in content_scope_records
        if item.get("content_status") in content_incomplete_states
    ]
    expected_statuses = (
        {"ARCHIVE_COMPLETE"}
        if content_mode == "archive"
        else {"CONTROL_COMPLETE", "CONTROL_BOUNDED_COMPLETE"}
        if content_mode == "control"
        else {"TREE_METADATA_ONLY"}
    )
    requested_content_scope_complete = all(
        item.get("content_status") in expected_statuses for item in content_scope_records
    )
    requested_audit_complete = complete_inventory and requested_content_scope_complete
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "organization": org,
        "observed_at": observed_at,
        "content_mode": content_mode,
        "authority": {
            "github_reads_only": True,
            "repository_writes": False,
            "provider_writes": False,
            "secret_values_recorded": False,
        },
        "coverage": {
            "repositories_discovered": len(repositories),
            "repositories_inventory_complete": sum(bool(item.get("inventory_complete")) for item in repositories),
            "active_repository_inventory_incomplete": active_incomplete,
            "tree_inventory_complete": complete_inventory,
            "files_inventory_total": len(all_files),
            "git_blob_entries": sum(item.get("entry_type") == "blob" for item in all_files),
            "submodule_entries": sum(item.get("entry_type") == "commit" for item in all_files),
            "every_file_content_addressed": all(
                bool(item.get("git_object_sha")) for item in all_files
            ),
            "content_scope": "all_repositories" if include_archived_content else "active_repositories",
            "content_files_fetched": sum(bool(item.get("content_fetched")) for item in all_files),
            "content_files_scanned": sum(bool(item.get("content_scanned")) for item in all_files),
            "byte_verified_files": sum(bool(item.get("byte_verified")) for item in all_files),
            "content_incomplete_repositories": content_incomplete,
            "requested_content_scope_complete": requested_content_scope_complete,
            "requested_audit_complete": requested_audit_complete,
            "archive_byte_verification_complete": (
                content_mode == "archive"
                and requested_content_scope_complete
                and all(
                    item.get("entry_type") != "blob" or bool(item.get("byte_verified"))
                    for record in content_scope_records
                    for item in files_by_repo.get(record["repository"], [])
                )
            ),
            "full_estate_archive_complete": (
                content_mode == "archive"
                and include_archived_content
                and requested_audit_complete
            ),
        },
        "estate": {
            "public_repositories": sum(not item.get("private") for item in repositories),
            "private_repositories": sum(bool(item.get("private")) for item in repositories),
            "archived_repositories": sum(bool(item.get("archived")) for item in repositories),
            "active_repositories": sum(not item.get("archived") and not item.get("disabled") for item in repositories),
            "forks": sum(bool(item.get("fork")) for item in repositories),
            "default_branch_blob_bytes": sum(int(item.get("total_blob_bytes") or 0) for item in repositories),
        },
        "finding_counts": {
            "by_severity": {level: severity_counts.get(level, 0) for level in SEVERITY_RANK},
            "by_rule": dict(sorted(rule_counts.items())),
            "total": len(findings),
        },
        "repositories": repositories,
        "files": all_files,
        "findings": [item.as_dict() for item in sorted_findings(findings)],
    }
    payload["state"] = (
        "INCOMPLETE"
        if not requested_audit_complete
        else "CRITICAL"
        if severity_counts["critical"]
        else "FINDINGS"
        if findings
        else "CLEAR"
    )
    payload["receipt_scope"] = "canonical JSON payload excluding receipt_sha256"
    payload["receipt_sha256"] = hashlib.sha256(canonical_json(payload)).hexdigest()
    return payload


def sorted_findings(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (
            -SEVERITY_RANK.get(item.severity, 0),
            item.rule_id,
            item.repository.casefold(),
            (item.path or "").casefold(),
            item.line or 0,
            item.fingerprint,
        ),
    )


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, files: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "repository",
        "path",
        "entry_type",
        "mode",
        "git_object_sha",
        "size",
        "classification",
        "content_fetched",
        "content_scanned",
        "byte_verified",
        "content_sha256",
        "binary",
        "lfs_pointer",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for item in files:
            writer.writerow(item)


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    coverage = payload["coverage"]
    estate = payload["estate"]
    counts = payload["finding_counts"]["by_severity"]
    lines = [
        "# Live GitHub estate and file audit",
        "",
        f"- Organization: `{payload['organization']}`",
        f"- Observed: `{payload['observed_at']}`",
        f"- State: **{payload['state']}**",
        f"- Receipt: `{payload['receipt_sha256']}`",
        f"- Content mode: `{payload['content_mode']}`",
        "",
        "## Coverage",
        "",
        f"- Repositories: **{coverage['repositories_inventory_complete']} / {coverage['repositories_discovered']}** exact default-branch inventories",
        f"- Files and submodules: **{coverage['files_inventory_total']}**",
        f"- Every file content-addressed by exact Git object: **{coverage['every_file_content_addressed']}**",
        f"- Content-fetched files: **{coverage['content_files_fetched']}**",
        f"- Text-rule scanned files: **{coverage['content_files_scanned']}**",
        f"- Byte-verified files: **{coverage['byte_verified_files']}**",
        f"- Tree inventory complete: **{coverage['tree_inventory_complete']}**",
        f"- Requested audit complete: **{coverage['requested_audit_complete']}**",
        f"- Full-estate archive complete: **{coverage['full_estate_archive_complete']}**",
        f"- Active / archived / private: **{estate['active_repositories']} / {estate['archived_repositories']} / {estate['private_repositories']}**",
        "",
        "## Findings",
        "",
        f"- Critical: **{counts['critical']}**",
        f"- High: **{counts['high']}**",
        f"- Medium: **{counts['medium']}**",
        f"- Low: **{counts['low']}**",
        f"- Informational: **{counts['info']}**",
        "",
        "| Severity | Rule | Repository | Path | Finding |",
        "|---|---|---|---|---|",
    ]
    for item in payload["findings"][:250]:
        message = str(item["message"]).replace("|", "\\|")
        location = str(item.get("path") or "—").replace("|", "\\|")
        if item.get("line"):
            location += f":{item['line']}"
        lines.append(
            f"| {item['severity'].upper()} | `{item['rule_id']}` | `{item['repository']}` | `{location}` | {message} |"
        )
    if len(payload["findings"]) > 250:
        lines.extend(["", f"_Table truncated; JSON receipt contains all {len(payload['findings'])} findings._"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This controller performs GitHub reads only. It never writes a repository, changes provider state, or records token/secret values. A successful run proves the reported observation and coverage—not that every finding has been remediated.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def should_fail(payload: Mapping[str, Any], threshold: str) -> bool:
    if threshold == "none":
        return False
    if not bool(payload["coverage"]["requested_audit_complete"]):
        return True
    if threshold == "incomplete":
        return False
    required = SEVERITY_RANK[threshold]
    return any(
        SEVERITY_RANK.get(item["severity"], 0) >= required
        for item in payload["findings"]
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", default="szl-holdings")
    parser.add_argument("--output-json", type=Path, default=Path("reports/live-estate-file-audit.json"))
    parser.add_argument("--output-md", type=Path, default=Path("reports/live-estate-file-audit.md"))
    parser.add_argument("--output-csv", type=Path, default=Path("reports/live-estate-file-inventory.csv"))
    parser.add_argument("--content-mode", choices=("tree", "control", "archive"), default="control")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-text-bytes", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--max-archive-bytes", type=int, default=750 * 1024 * 1024)
    parser.add_argument("--max-total-archive-bytes", type=int, default=8 * 1024 * 1024 * 1024)
    parser.add_argument("--include-archived-content", action="store_true")
    parser.add_argument("--repository-limit", type=int)
    parser.add_argument("--fail-on", choices=("none", "incomplete", "critical", "high", "medium", "low"), default="critical")
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None, *, client: GitHubClient | None = None) -> int:
    args = parse_args(argv)
    token = os.environ.get("ESTATE_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    active_client = client or GitHubClient(token)
    observed_at = utc_now()
    repositories = list_repositories(active_client, args.org)
    if args.repository_limit is not None:
        repositories = repositories[: max(args.repository_limit, 0)]
    if not repositories:
        raise AuditError(f"no repositories were visible for organization {args.org}")

    records_by_name: dict[str, dict[str, Any]] = {}
    files_by_repo: dict[str, list[dict[str, Any]]] = {}
    findings: list[Finding] = []
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(inventory_repository, active_client, repository): repository["repository"]
            for repository in repositories
        }
        for future in as_completed(futures):
            record, files, repo_findings = future.result()
            with lock:
                records_by_name[str(record["repository"])] = record
                files_by_repo[str(record["repository"])] = files
                findings.extend(repo_findings)

    records = [records_by_name[item["repository"]] for item in repositories]
    findings.extend(
        content_audit(
            active_client,
            records,
            files_by_repo,
            mode=args.content_mode,
            max_text_bytes=args.max_text_bytes,
            max_archive_bytes=args.max_archive_bytes,
            max_total_archive_bytes=args.max_total_archive_bytes,
            include_archived_content=args.include_archived_content,
        )
    )
    all_files = [item for record in records for item in files_by_repo.get(record["repository"], [])]
    findings.extend(duplicate_blob_findings(records, all_files))
    payload = build_summary(
        args.org,
        records,
        files_by_repo,
        findings,
        content_mode=args.content_mode,
        observed_at=observed_at,
        include_archived_content=args.include_archived_content,
    )
    write_json(args.output_json, payload)
    write_markdown(args.output_md, payload)
    write_csv(args.output_csv, payload["files"])
    print(
        json.dumps(
            {
                "state": payload["state"],
                "repositories": payload["coverage"]["repositories_discovered"],
                "files": payload["coverage"]["files_inventory_total"],
                "findings": payload["finding_counts"]["total"],
                "receipt_sha256": payload["receipt_sha256"],
            },
            sort_keys=True,
        )
    )
    return 1 if should_fail(payload, args.fail_on) else 0


def main() -> int:
    try:
        return run()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
