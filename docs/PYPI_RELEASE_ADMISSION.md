# szl-gov PyPI release admission (source-owned, OIDC only)

**Current disposition (2026-11-17): SOURCE PREPARED, PUBLICATION HOLD.**

The canonical PyPI URL `https://pypi.org/project/szl-gov/` and JSON
endpoint returned HTTP 404 at the latest owner-side inspection. Therefore
**this package has not been verified as published**. The accepted
`szl-holdings` organization on PyPI is not itself proof that this particular
project has a publisher or exists.

## One release path

- Canonical Python source: `szl-holdings/szl-gov` protected `main`.
- Package: `szl-gov`; initial candidate version `0.1.0`; top-level import
  `szl_gov`; source URL bound to the GitHub repository in `pyproject.toml`.
- Only publish a GitHub Release with exact tag `v0.1.0` *after* source CI and
  the owner-controlled PyPI pending publisher are admitted.
- The [workflow](../.github/workflows/publish-pypi.yml) builds both sdist and
  wheel, checks metadata with Twine, enforces tag-to-version exactness, rejects
  duplicate PyPI versions, validates the complete wheel's top-level import in
  an isolated virtualenv, emits a release-gate receipt, and uses only
  **PyPI Trusted Publishing** (GitHub OIDC with limited `id-token: write`).
- The [release gate](../.github/scripts/szl_pypi_release_gate.py) is the
  byte-identical, versioned SZL publisher copied from the source-owned
  `szl-holdings/szl-receipt` lane. It uses no API key.

**No tag or GitHub Release was created while this document was prepared.
No API token or private key was accessed or published.**

## Pre-publication operator admission

1. Confirm PyPI organization `szl-holdings` owns the pending `szl-gov`
   trusted publisher (repository: `szl-holdings/szl-gov`, workflow:
   `publish-pypi.yml`, environment: `pypi`). Configure it on PyPI as a
   **pending publisher** for first upload. Verify the exact owner and package
   name; never infer these from domain ownership or another published package.
2. Configure a protected GitHub `pypi` environment, with protected-main
   admission and owner-reviewed releases; GitHub's environment API returned
   zero configured environments during the 2026-11-17 inspection.
3. Require all source checks to pass and a reproducible release-gate build
   (`python .github/scripts/szl_pypi_release_gate.py --packages
   szl-gov=.:pypi --repo szl-holdings/szl-gov --event push --ref-type
   branch --ref-name main --outdir <operator-local-outdir>`).
4. Publish the exact `v0.1.0` GitHub Release only after steps 1–3. The
   trusted workflow refuses pre-existing versions, metadata ambiguity or
   missing signing/publisher authority. Do not relax the gate.
5. Read back PyPI's project JSON, the sdist and wheel hashes, PEP 740
   provenance, installed import, project owner and GitHub release; record
   `PUBLICATION_VERIFIED` only after all match.

## Scope and claims

A local wheel or successful PR CI is **not a PyPI publication**. Package
publication itself is **not a Hugging Face deployment**, **not Cloudflare
monetization**, and **not academic peer review**. The Python public-policy
and POST-method witnesses report HTTP 402 challenges but neither payments
nor settlements. Hold any investor/publication claim that lacks an exact
public readback.

Upstream canonical publisher: [szl-receipt release workflow](https://github.com/szl-holdings/szl-receipt/blob/main/.github/workflows/publish-pypi.yml).
