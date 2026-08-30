---
title: Governed Receipt Verifier
emoji: 🧾
colorFrom: indigo
colorTo: gray
sdk: static
pinned: false
license: apache-2.0
models: [SZLHOLDINGS/szl-receipt-attn, SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3]
short_description: Verify a governed receipt offline, in-browser
tags:
  - receipts
  - verification
  - dsse
  - pyodide
  - governance
  - szl-holdings
datasets: [SZLHOLDINGS/szl-lake]
---


<div align="center">
<p>

[![governed](https://img.shields.io/badge/governed-SZL%20Holdings-3af4c8?style=flat-square)](https://huggingface.co/SZLHOLDINGS)
[![Λ](https://img.shields.io/badge/Λ-Conjecture%201%20advisory-d7b96b?style=flat-square)](https://a-11-oy.com)
[![license](https://img.shields.io/badge/license-apache--2.0-7e8aa3?style=flat-square)](https://huggingface.co/spaces/SZLHOLDINGS/governed-receipt-verifier)

</p>
</div>
<!-- SZL-ESTATE-CARD:v2:START -->
<p align="center"><a href="https://a-11-oy.com/"><img src="https://huggingface.co/spaces/SZLHOLDINGS/README/resolve/main/assets/estate-banner-v2.svg" alt="SZL Holdings — governed, receipted, verifiable" width="100%"></a></p>
<p align="center">
  <a href="https://github.com/szl-holdings/.github/tree/main/doctrine"><img src="https://img.shields.io/badge/doctrine-v11%20LOCKED-0B1F3A?style=flat-square" alt="doctrine v11"></a>
  <a href="https://a-11-oy.com/"><img src="https://img.shields.io/badge/evidence%20wall-LIVE%20%C2%B7%20verify%20in%20browser-3AF4C8?style=flat-square" alt="live evidence wall"></a>
  <a href="https://huggingface.co/datasets/SZLHOLDINGS/szl-lake"><img src="https://img.shields.io/badge/szl--lake-offline%20verifiable-C9B787?style=flat-square" alt="szl-lake offline verifiable"></a>
  <a href="https://huggingface.co/spaces/SZLHOLDINGS/holographic"><img src="https://img.shields.io/badge/estate%20map-holographic-5B8DEE?style=flat-square" alt="holographic estate map"></a>
</p>
<p align="center"><sub>Part of the <a href="https://huggingface.co/SZLHOLDINGS">SZL Holdings</a> governed estate — claims are designed to carry checkable receipts. Verification proves integrity &amp; origin, never accuracy or performance.</sub></p>
<!-- SZL-ESTATE-CARD:v2:END -->

# Governed Receipt Verifier

A tiny, **static** Hugging Face Space that verifies a **governed inference
receipt** entirely in your browser. It runs the dependency-free
[`verify.py`](https://github.com/szl-holdings/governed-receipt-spec/blob/main/verify.py)
from the open [`governed-receipt-spec`](https://github.com/szl-holdings/governed-receipt-spec)
via [Pyodide](https://pyodide.org) — no server, no upload, no dependencies.

Built and maintained by [SZL Holdings](https://a-11-oy.com). Apache-2.0.

## What it does

Paste a receipt (a single JSON object, a JSON array, or NDJSON) and it re-checks:

1. **JSON Schema** — the decoded decision object against the spec schema.
2. **Content hash** — recomputes `sha256(DSSE PAE) == _pae_sha256` for signed
   receipts, or `sha256(payload) == payloadSha256` for readiness receipts.
3. **Hash chain** — `prev == previous.digest`, contiguous `seq`, genesis is 64 zeros.
4. **Claim binding** — every clear governance claim must be present with the
   same JSON type and value in the selected sealed payload; ambiguous or
   alternate envelope locations fail closed.
5. **DSSE envelope** — strict Base64, signature-marker consistency, and
   structural well-formedness.

It shows a clear **PASS / FAIL** with per-check reasons. Try the built-in
examples: a valid receipt, a valid 5-receipt chain, and a tampered receipt (which
fails on the content hash).

> **Honest scope.** A receipt is a signed, tamper-evident audit record of what a
> governed runtime *decided* — the "receipt tier" of trust. It is **not** a
> zero-knowledge proof and **not** a proof of computation. Full ECDSA-P256
> signature verification is an upstream `cosign verify-blob --key cosign.pub` step;
> this Space checks structure, content hashes, clear-to-sealed binding, and the
> chain — the relations an outside party can independently reproduce.

## The estate

- **Spec + verifier:** [`szl-holdings/governed-receipt-spec`](https://github.com/szl-holdings/governed-receipt-spec)
- **Benchmark corpus:** [`SZLHOLDINGS/governed-receipts-bench`](https://huggingface.co/datasets/SZLHOLDINGS/governed-receipts-bench)
- **Source receipt datasets:** [`a11oy-verifiable-corpus`](https://huggingface.co/datasets/SZLHOLDINGS/a11oy-verifiable-corpus), [`readiness-runs`](https://huggingface.co/datasets/SZLHOLDINGS/readiness-runs)
- **Console:** [a-11-oy.com](https://a-11-oy.com) · **HF org:** [SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) · **GitHub org:** [szl-holdings](https://github.com/szl-holdings)

---

## SZL Estate

Part of the **SZL Holdings** governed-AI estate — *governed AI you can prove*: every decision carries a signed, checkable receipt.

- **Flagship:** [a11oy command console → a-11-oy.com](https://a-11-oy.com)
- **Orgs:** [GitHub · szl-holdings](https://github.com/szl-holdings) · [Hugging Face · SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS)
- **Related Spaces:** [⚡ energy-attested-runs](https://huggingface.co/spaces/SZLHOLDINGS/energy-attested-runs) · [🧾 guardrail-receipt](https://huggingface.co/spaces/SZLHOLDINGS/guardrail-receipt) · [🧬 immune](https://huggingface.co/spaces/SZLHOLDINGS/immune)

**Status:** responding as of 2026-07-09 (HF Space root probe, this session).

<sub>Doctrine v11 · Λ = Conjecture 1 (advisory — never "green"/theorem; open) · honest by design · public data only.</sub>

---

<div align="center">

**[🛡️ SZLHOLDINGS on Hugging Face →](https://huggingface.co/SZLHOLDINGS)**   ·   **[a-11-oy.com →](https://a-11-oy.com)**   ·   **[Estate hub — live →](https://szlholdings-szl-estate-live.static.hf.space)**

### Governed AI you can prove.

<sub>SLSA: L1 honest · L2 attested · L3 roadmap. Λ = Conjecture 1 (advisory, never a theorem). Trust ceiling 0.97 — never 100%. Labels honest by default: MEASURED / REPORTED / MODELED / HEURISTIC / UNKNOWN / UNAVAILABLE. locked-proven = exactly 8 {F1,F4,F7,F11,F12,F18,F19,F22}.</sub>

</div>
