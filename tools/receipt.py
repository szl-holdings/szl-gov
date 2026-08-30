"""receipt — GovernedAction/v1 predicate + in-toto Statement v1 envelope + DSSE sign/verify.

Uses only `cryptography` (Ed25519). Do NOT hand-roll this again —
production v1 should adopt the maintained `in-toto-attestation` PyPI bindings
(CNCF-governed). This module exists so the estate can sign receipts TODAY
with one dependency and a fully testable code path.

Truth states (structural, not decorative):
  VERIFIED / DEGRADED / UNKNOWN / BLOCKED / UNAVAILABLE

Laws enforced here:
  - missing evidence => INCOMPLETE, never PASS
  - signature proves integrity + origin, NOT truth of claims
  - is_service_account is structurally pinned False at the schema level
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

PREDICATE_TYPE = "https://szl.dev/GovernedAction/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
MEDIA_TYPE = "application/vnd.in-toto+json"

TRUTH_STATES = ("VERIFIED", "DEGRADED", "UNKNOWN", "BLOCKED", "UNAVAILABLE")
SIDE_EFFECT_CLASSES = ("READ_ONLY", "WRITE_LOCAL", "EXTERNAL_EFFECT", "IRREVERSIBLE")


# ---------------------------------------------------------------- keys

def generate_keypair():
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    return sk, pk


def public_key_pem(pk: Ed25519PublicKey) -> str:
    return pk.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def private_key_pem(sk: Ed25519PrivateKey) -> str:
    return sk.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def load_private(pem: str) -> Ed25519PrivateKey:
    return serialization.load_pem_private_key(pem.encode(), password=None)


def load_public(pem: str) -> Ed25519PublicKey:
    return serialization.load_pem_public_key(pem.encode())


def key_id(pk: Ed25519PublicKey) -> str:
    raw = pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------- DSSE (spec-exact PAE)

def _pae(payload_type: bytes, payload: bytes) -> bytes:
    # Pre-Authentication Encoding per DSSE spec: prevents signature confusion.
    # "DSSEv1" SP <len(type)> SP <type> SP <len(payload)> SP <payload>
    return (
        b"DSSEv1"
        + b" " + str(len(payload_type)).encode()
        + b" " + payload_type
        + b" " + str(len(payload)).encode()
        + b" " + payload
    )


def dsse_sign(payload: dict, sk: Ed25519PrivateKey, ptype: str = MEDIA_TYPE) -> dict:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = sk.sign(_pae(ptype.encode(), body))
    pk = sk.public_key()
    return {
        "payloadType": ptype,
        "payload": base64.b64encode(body).decode(),
        "signatures": [{"keyid": key_id(pk), "sig": base64.b64encode(sig).decode()}],
    }


def dsse_verify(env: dict, pk: Ed25519PublicKey) -> dict:
    body = base64.b64decode(env["payload"])
    ok = False
    for s in env.get("signatures", []):
        try:
            pk.verify(base64.b64decode(s["sig"]), _pae(env["payloadType"].encode(), body))
            ok = True
        except Exception:
            pass
    if not ok:
        raise ValueError("signature_invalid")
    return json.loads(body)


# ---------------------------------------------------------------- predicate

@dataclass
class EvidenceItem:
    kind: str                     # e.g. api_response | cli_output | screenshot | human_attestation
    ref: str                      # path or URL where the evidence lives
    sha256: str | None = None     # content hash when the evidence is a file
    required: bool = True         # if True and ref is empty -> completeness INCOMPLETE


@dataclass
class GovernedAction:
    action: str
    actor: str
    scope: str
    truth_state: str
    side_effect_class: str = "READ_ONLY"
    evidence: list = field(default_factory=list)     # list[EvidenceItem|dict]
    limitations: list = field(default_factory=list)  # explicit non-claims
    context: dict = field(default_factory=dict)      # redaction_commitments, ntp_synced, rfc3161_token ...
    is_service_account: bool = False                 # Art.12(3)(d): human principal, structurally pinned

    def __post_init__(self):
        if self.is_service_account:
            raise ValueError(
                "is_service_account=True is structurally forbidden: "
                "EU AI Act Art.12(3)(d) requires natural persons in the verification loop."
            )
        if self.truth_state not in TRUTH_STATES:
            raise ValueError(f"unknown truth_state {self.truth_state!r}; lawful states: {TRUTH_STATES}")
        if self.side_effect_class not in SIDE_EFFECT_CLASSES:
            raise ValueError(f"unknown side_effect_class {self.side_effect_class!r}")
        self.evidence = [e if isinstance(e, EvidenceItem) else EvidenceItem(**e) for e in self.evidence]

    @property
    def completeness(self) -> str:
        """Missing required evidence => INCOMPLETE, never PASS."""
        for e in self.evidence:
            if e.required and not e.ref:
                return "INCOMPLETE"
        return "COMPLETE" if self.evidence else "INCOMPLETE"

    def public_claim_check(self) -> None:
        """Zero-Bandaid Law: a public VERIFIED claim with complete-missing evidence demotes to UNKNOWN."""
        if self.truth_state == "VERIFIED" and self.completeness == "INCOMPLETE":
            object.__setattr__(self, "truth_state", "UNKNOWN")

    def to_dict(self) -> dict:
        self.public_claim_check()
        d = asdict(self)
        d["evidence"] = [asdict(e) for e in self.evidence]
        d["completeness"] = self.completeness
        d["_schema"] = PREDICATE_TYPE
        return d


def build_statement(action: GovernedAction, source_rev: str, tool_version: str = "0.1.0") -> dict:
    """Wrap the predicate in an in-toto Statement v1 envelope."""
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{
            "name": f"szl-audit/{action.scope}",
            "digest": {"sha256": hashlib.sha256(
                json.dumps(action.to_dict(), sort_keys=True).encode()
            ).hexdigest()},
        }],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            **action.to_dict(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": str(uuid.uuid4()),
            "source_revision": source_rev,
            "tool": {"name": "szl-gov", "version": tool_version},
        },
    }


def sign_statement(statement: dict, sk: Ed25519PrivateKey) -> dict:
    return dsse_sign(statement, sk)
