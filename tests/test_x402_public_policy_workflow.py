"""Review lock for the bounded, public-only scheduled x402 observer."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "x402-public-policy-witness.yml"
SOURCE = ROOT / "tools" / "x402_public_policy_watch.py"


def test_protected_main_read_only_no_credentials_or_payments():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "refs/heads/main" in text
    assert "ref: ${{ github.sha }}" in text
    assert "contents: read" in text
    assert "permissions:" in text
    assert "python -I -B tools/x402_public_policy_watch.py" in text
    assert "GITHUB_SHA: " in text
    assert "if: always()" in text
    assert "if-no-files-found: error" in text
    for forbidden in ("secrets.", "permissions: write-all", "workflow_call:",
                      "pull_request:", "curl ", "wget ", "payment-signature",
                      "PAYMENT-SIGNATURE", "HF_TOKEN", "CLOUDFLARE_API_TOKEN"):
        assert forbidden not in text
    used = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", text)
    assert len(used) == 3
    assert all(re.search(r"@[0-9a-f]{40}$", value) for value in used)


def test_monitor_never_constructs_payment_attempts_or_unscoped_probes():
    text = SOURCE.read_text(encoding="utf-8")
    assert "method=\"GET\"" in text
    assert "NoRedirect" in text
    assert "ProxyHandler({})" in text
    assert "settlement\": \"UNVERIFIED\"" in text
    assert "revenue\": \"NO_CLAIM\"" in text
    assert "provider_rule_readback\": \"NOT_PERFORMED\"" in text
    for forbidden in ("method=\"POST\"", "wallet.sign", "eth_sendRawTransaction",
                      "send_transaction(", "Authorization: Bearer"):
        assert forbidden not in text
