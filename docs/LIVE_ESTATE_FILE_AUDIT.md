# Live GitHub Estate and File Audit

## Purpose

`tools/audit_github_estate.py` is the estate-wide source census for the GitHub organization. It replaces static repository counts and sampled-file claims with an exact, source-bound observation of every repository visible to the supplied credential and every entry on each default branch.

The controller is read-only. It does not merge pull requests, alter branch protection, modify repositories, rotate credentials, publish provider resources, or change deployment state.

## Evidence model

Every repository record binds:

- repository identity, visibility, lifecycle state, default branch, and observed head;
- exact default-branch tree identity;
- every blob or submodule path, mode, size, classification, and Git object identity;
- explicit recursive-tree truncation recovery rather than accepting a partial GitHub response;
- a content-coverage state that distinguishes metadata-only, bounded control scan, exact archive verification, skipped scope, mismatch, and failure;
- findings with stable fingerprints and no recorded token or secret value.

The JSON receipt is authoritative. The Markdown and CSV files are views over the same observation.

## Audit modes

### `tree`

Inventories every token-visible repository and every exact default-branch blob/submodule. This is a complete metadata and Git-object census when `coverage.tree_inventory_complete` is true.

### `control`

Performs the complete tree census and fetches bounded high-signal source: workflows, dependency manifests and lockfiles, root governance files, Docker/Compose files, infrastructure definitions, policy/configuration files, and deployment controls. Files over the configured text bound remain content-addressed and are explicitly counted as bounded exclusions.

### `archive`

Downloads each exact commit archive in scope. Every regular file is streamed through Git object verification and SHA-256 hashing, including large binaries without loading them into memory. Small UTF-8 files additionally enter the semantic scanners. Git symlinks are verified against their link-target blob bytes. Archive/tree mismatches, hard-link ambiguity, size mismatches, byte mismatches, download failure, and estate-budget exhaustion fail closed.

`coverage.full_estate_archive_complete` is true only when archive mode includes archived repositories and every requested repository completes. Active-only verification is reported separately and is never labelled as full-estate completion.

## Current scanners

The initial contract detects:

- unreadable repositories and unrecoverable truncated trees;
- active repositories missing root README, public license, SECURITY policy, CI, tests, or dependency locks;
- large committed objects requiring explicit LFS/artifact ownership;
- GitHub Actions not pinned to immutable commit/digest identities;
- dangerous `pull_request_target` head-code use, `permissions: write-all`, and network-to-shell pipelines;
- unpinned container base images;
- high-confidence committed credential material, with lower-severity verification findings for credential-shaped values in documentation/tests;
- exact non-generated source/config blobs duplicated across active repositories.

A finding is not proof of exploitability. It is deterministic evidence requiring owner review or remediation.

## Workflow behavior

`.github/workflows/live-estate-file-audit.yml` provides two lanes:

1. **Control census:** pull-request qualification, protected-main execution, and daily execution. Pull requests block only on incomplete coverage so the controller can be introduced without falsely declaring the existing estate clean. Protected-main and scheduled runs also block on critical findings and synchronize one deterministic incident.
2. **Archive census:** weekly and explicit-dispatch exact byte verification with a finite per-repository and estate download budget. Exhausting that budget is an incomplete run, not a pass.

The credential fallback follows the existing SZL organization-controller convention:

`SZL_ORG_ADMIN_TOKEN → ORG_ADMIN_TOKEN → SZL_GITHUB_TOKEN → GH_PAT → github.token`

The receipt always describes **token-visible scope**. Private repositories outside that credential's installation or authorization are not silently claimed as audited.

## No-bandaid boundary

This controller does not add exceptions for a failing repository, does not convert unreadable state to success, does not accept a truncated recursive tree, and does not suppress critical findings to obtain a green operational run. Remediation happens in the owning repository and is re-observed by the next exact census.

## Local verification

```bash
python -m py_compile tools/audit_github_estate.py tests/test_audit_github_estate.py
python -m unittest discover -s tests -p 'test_audit_github_estate.py' -v

ESTATE_GITHUB_TOKEN=... python tools/audit_github_estate.py \
  --org szl-holdings \
  --content-mode control \
  --fail-on critical
```

For exhaustive archive verification:

```bash
ESTATE_GITHUB_TOKEN=... python tools/audit_github_estate.py \
  --org szl-holdings \
  --content-mode archive \
  --include-archived-content \
  --fail-on critical
```
