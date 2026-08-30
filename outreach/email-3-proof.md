Subject: Signed receipt for our own audit (attached approach)

Hi {first_name},

Last note — I'll show rather than tell.

We ran our full estate audit and signed the result with the same receipt format we'd deploy for you. It says DEGRADED and INCOMPLETE in the honest places. Any CISO can verify it offline:

  curl <receipt url>; curl <pubkey url>
  python3 tools/verify_receipt.py receipt.json pubkey.pem
  # VERIFY: PASS (offline) — or FAIL if a single byte changed

That's the whole product in one command. A record your auditor can check without trusting us.

If governed agent change management is on your 2026 roadmap — and with Annex III logging obligations already in force, it should be — I'd rather earn a design partnership than keep emailing.

a11oy.net/pricing · github.com/szl-holdings/szl-gov

Stephen
