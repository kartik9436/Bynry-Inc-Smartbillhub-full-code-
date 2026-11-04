# ── Trace ──────────────────────────────────────────────
# Change:   DEF-BIL-10531 lane BILL-LINK (decision log 2026-10-22, *"The bill
#           email's PDF link: how lane BILL-LINK builds it"*, judgment 1)
# Rules:    the click-to-accept agreement link's token (`customers/agreements.py`,
#           CR-190-BRC10) — lifted here so the bill link reuses it rather than
#           writing a second token scheme
# Tests:    06-backend/tests/test_def_bil_10531_bill_link.py ·
#           06-backend/tests/test_cr190_agreements.py
# ───────────────────────────────────────────────────────
"""ONE secret-link token scheme for every emailed link that opens without a sign-in.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the token's size, its digest and the
constant-time compare are the whole security of a page nobody signs in to.
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.

* `mint()` — 256 random bits, URL-safe (`identity.NativeToken`'s size).
* `digest()` — SHA-256 hex. Only the digest is stored: the token is 256 random
  bits, so a plain digest is the right hash and a dump of the table opens nothing.
* `matches()` — constant-time compare of a stored digest with a presented token.
* `plausible()` — refuses an empty or absurdly long presentation before any read.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

#: 256 random bits, URL-safe.
TOKEN_BYTES = 32
#: Nothing longer than this is a token this scheme minted.
MAX_PRESENTED_LENGTH = 128


def mint() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def digest(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def plausible(token: object) -> bool:
    text = str(token or "")
    return bool(text) and len(text) <= MAX_PRESENTED_LENGTH


def matches(stored_digest: str, token: str) -> bool:
    return hmac.compare_digest(str(stored_digest), digest(token))
