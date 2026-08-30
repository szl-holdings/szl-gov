#!/usr/bin/env bash
# apply_backlinks.sh — wires models: front-matter into the 3 backlink-gap Spaces.
#
# The audit token (betterwithage OAuth) is read-scoped, so this runs locally
# with YOUR write token. One command:
#
#   HF_TOKEN=hf_xxx bash patches/apply_backlinks.sh
#
# Zero dependencies beyond curl + python3.
set -euo pipefail
: "${HF_TOKEN:?export HF_TOKEN=hf_... (write-scoped, from https://huggingface.co/settings/tokens)}"
HERE="$(cd "$(dirname "$0")" && pwd)"

declare -A SPACES=(
  [immune]="immune.README.md"
  [governed-receipt-verifier]="governed-receipt-verifier.README.md"
  [README]="README.README.md"
)

for space in "${!SPACES[@]}"; do
  file="${SPACES[$space]}"
  echo "== $space"
  python3 - "$space" "$HERE/$file" <<'PY'
import json, os, subprocess, sys, base64
space, path = sys.argv[1], sys.argv[2]
content = open(path, 'rb').read()
tok = os.environ['HF_TOKEN']
body = {
  "summary": "Add models: front-matter for Hub backlink discovery (szl-gov audit B-03)",
  "files": [{"path": "README.md", "content": base64.b64encode(content).decode(), "encoding": "base64"}],
}
r = subprocess.run([
  "curl", "-s", "-X", "POST",
  f"https://huggingface.co/api/spaces/SZLHOLDINGS/{space}/commit/main",
  "-H", f"Authorization: Bearer {tok}",
  "-H", "Content-Type: application/json",
  "-d", json.dumps(body),
], capture_output=True, text=True)
print(r.stdout[:400])
PY
done

echo "Verify: open each Space page and confirm 'Spaces using this model' appears on the linked model pages."
