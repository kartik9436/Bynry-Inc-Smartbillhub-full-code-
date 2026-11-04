# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.14`
#          (*"BI tier 2 — scheduled delivery"*), brief p015 and §7.8 p088–p089,
#          read as IMAGES per B14 rule 42.
# Rules:   **RULED, brief p090 decisions register, FINAL**: *"A scheduled file
#          may leave the product — Yes; admin-set destinations, encrypted in
#          transit, every delivery logged."* · **PO ruling 2026-08-30**,
#          verbatim: *"dont expire it in minutes - exprise it in 3 or 4
#          hours"* (`apps/tenancy/document_storage.py`, the FOUR HOURS this
#          module reuses rather than choosing a number of its own) ·
#          CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (every money
#          action writes `audit_log`) · hard-won law 3 (defaults fail closed) ·
#          law 7 (a check that cannot fail is not a check)
# Tests:   06-backend/tests/test_cr142_p4_14_signed_delivery.py
# Impacts: apps/reports/destinations.py (its caller) · apps/reports/api.py
#          (the one unauthenticated route that accepts one of these)
# ───────────────────────────────────────────────────────
"""A BEARER TOKEN FOR ONE REPORT FILE, FOR FOUR HOURS, AND NOTHING ELSE.

WHAT THIS IS FOR, IN THE BRIEF'S OWN WORDS
──────────────────────────────────────────
§7.8 tier 2, p088: *"Scheduled delivery — the scheduler already writes a file;
send it to SFTP or a signed URL on a timer. … Rides on schedules. A BI tool
that cannot call an API on a timer can still collect a file."* The collector is
a MACHINE with no browser and no session, so the address it is handed has to
carry its own authority. That is what a signed link is, and naming it plainly
is the point: **it is a credential in a URL.**

════════════════════════════════════════════════════════════════════════════
THE FOUR HOURS ARE NOT THIS LANE'S NUMBER
════════════════════════════════════════════════════════════════════════════
⚠ **A LINK LIFETIME IS A SECURITY PARAMETER AND A LANE MAY NOT CHOOSE ONE.**
It did not have to: the PO already ruled this exact question on 2026-08-30, for
the document store, in the words *"dont expire it in minutes - exprise it in 3
or 4 hours"*, and `apps/tenancy/document_storage.url_ttl_seconds()` is that
ruling in code — four hours, a CAP rather than a clamp, refusing by name if an
operator lengthens it. This module CALLS that function rather than declaring a
constant beside it, so a future re-sign moves both at once and there is no
second number free to disagree with the first (hard-won law 5's shape for a
figure instead of a file). Applying a ruled figure to a second kind of
temporary link is not a new decision; inventing a fifth hour would have been.

⚠ **WHAT WAS *NOT* RULED IS RECORDED AND STUBBED, NOT GUESSED** — the SFTP
transport's host-key trust policy. See `destinations.py` and `OQ-REP-7040`.

════════════════════════════════════════════════════════════════════════════
WHAT A TOKEN PERMITS — THE WHOLE LIST, AND IT IS SHORT
════════════════════════════════════════════════════════════════════════════
  · ONE job's artifact. The job id is INSIDE the signed payload, so a holder
    cannot move the token to another file: changing the id changes the
    signature.
  · ONE tenant. The tenant id is in the payload AND re-checked against the
    job's own row at redemption, so a token minted for Brazos Bend cannot read
    Lone Star Ridge's file even if the two job ids were somehow confused.
  · FOR FOUR HOURS. `exp` is in the payload and compared against the clock at
    redemption.
  · READ. There is no verb in the payload because there is only one: this
    token can be exchanged for bytes and for nothing else. No token minted here
    can write, list, delete, or name a second file.
It carries NO session, NO role and NO user. A holder is not signed in as
anybody — which is exactly why the object it names is one file and the window
is four hours.

════════════════════════════════════════════════════════════════════════════
WHY HMAC AND NOT A RANDOM ROW IN A TABLE
════════════════════════════════════════════════════════════════════════════
A stored random token is the other honest design and it was considered. HMAC
wins here for one reason: **the artifact is swept on a retention timer**
(`BR-REP-018`, three days by default and tenant-configurable since `P4.6`), so
a token table would outlive the files it names and need its own sweep — a
second expiry rule free to disagree with the first. A self-describing token
needs no row, expires by arithmetic, and is revoked wholesale by rotating the
key.

⚠ **THE KEY IS DERIVED FROM `SECRET_KEY` WITH ITS OWN INFO STRING, WHICH IS
DOMAIN SEPARATION AND NOT DECORATION.** Signing with the raw `SECRET_KEY` would
mean a token minted here and a token minted by any other feature that ever
signs with it are verifiable by each other's code — so a bug in one becomes a
forgery in the other. `_key()` mixes a constant naming THIS purpose, so a
signature from this module verifies nowhere else.

⚠ **THE COMPARISON IS CONSTANT-TIME (`hmac.compare_digest`).** A `==` over a
signature leaks it one byte at a time to anybody who can measure a response,
and the failure is invisible in every test: both forms refuse a wrong token and
only one of them refuses it safely. `service_accounts.py` says the same thing
about its own token and for the same reason.

⚠ **AND THE GUARDS BELOW WERE PROVED RED BEFORE THEY WERE TRUSTED GREEN** —
`tests/test_cr142_p4_14_signed_delivery.py` mints a valid token and then
tampers with each field in turn, because a verifier that accepts everything
passes exactly the same "it works" check as one that is correct (law 7).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from django.conf import settings

from core import errors

#: Domain separation — see the module docstring. Changing this string
#: invalidates every token in flight, which is the intended emergency lever.
KEY_INFO = b"smartbillhub/reports/scheduled-delivery/v1"

#: Recognisable as OURS and as THIS kind of credential if one turns up in a log
#: or a BI tool's config — the same courtesy `service_accounts.TOKEN_PREFIX`
#: extends, and for the same reason: a secret nobody can identify is a secret
#: nobody can revoke.
TOKEN_PREFIX = "sbhrd1"


def _key() -> bytes:
    """The signing key for THIS purpose, derived from the deployment secret."""
    secret = getattr(settings, "SECRET_KEY", "") or ""
    if not secret:
        # Hard-won law 3 — the unsafe option must be the one you type. An empty
        # secret would produce a perfectly valid-looking signature that every
        # deployment in the world could forge.
        raise RuntimeError(
            "SECRET_KEY is empty; a scheduled-delivery link cannot be signed"
        )
    return hmac.new(secret.encode("utf-8"), KEY_INFO, hashlib.sha256).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def ttl_seconds() -> int:
    """FOUR HOURS — the PO's 2026-08-30 ruling, read from where it lives.

    ⚠ **CALLED, NOT COPIED.** See the module docstring: a constant here would
    be a second copy of a ruled figure, free to drift from the first.
    """
    from apps.tenancy import document_storage

    return document_storage.url_ttl_seconds()


def mint(*, tenant_id: Any, job_id: Any, now: datetime) -> tuple[str, datetime]:
    """A token for ONE tenant's ONE job, expiring `ttl_seconds()` from `now`.

    Answers `(token, expires_at)`. `now` is a PARAMETER and never a clock read
    in here (`BR-TEN-043`) — the caller is the delivery sweep, which holds the
    beat's own moment, and a test can therefore state the hour.
    """
    expires_at = datetime.fromtimestamp(now.timestamp() + ttl_seconds(), tz=UTC)
    payload = {
        "v": 1,
        "t": str(tenant_id),
        "j": str(job_id),
        "exp": int(expires_at.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64(hmac.new(_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{TOKEN_PREFIX}.{body}.{signature}", expires_at


def verify(token: str, *, now: datetime) -> dict[str, Any]:
    """`token` → `{"tenant_id", "job_id"}`, or a refusal.

    ⚠ **ONE REFUSAL FOR EVERY NO, AND THAT IS DELIBERATE** — the posture
    `tenancy.api.export_file` already takes for its five noes. A malformed
    token, a forged signature, an expired one and a well-formed one for a job
    that is gone all answer identically, because distinguishing them tells a
    holder which half of their guess was right.

    ⚠ **THE SIGNATURE IS CHECKED BEFORE THE PAYLOAD IS PARSED AS ANYTHING BUT
    BYTES.** Reading `exp` out of an unverified body and trusting it is how a
    verifier ends up honouring an attacker's expiry.
    """
    refusal = errors.NotFoundError()
    try:
        prefix, body, signature = token.split(".")
    except (AttributeError, ValueError):
        raise refusal from None
    if prefix != TOKEN_PREFIX:
        raise refusal

    expected = _b64(hmac.new(_key(), body.encode("ascii"), hashlib.sha256).digest())
    # Constant-time. See the module docstring.
    if not hmac.compare_digest(expected, signature):
        raise refusal

    try:
        payload = json.loads(_unb64(body))
    except Exception:  # noqa: BLE001 — every malformed body is the same no
        raise refusal from None
    if payload.get("v") != 1:
        raise refusal
    if int(payload.get("exp", 0)) <= int(now.timestamp()):
        raise refusal
    return {"tenant_id": payload["t"], "job_id": payload["j"]}


# gates: pytest tests/test_cr142_p4_14_signed_delivery.py
# exceptions: the SFTP transport is NOT signed here and is not built — its
#   host-key trust policy is `OQ-REP-7040`, OPEN, and `destinations.py` stubs
#   it with that id rather than choosing one (prime directive).
# status: VERIFIED-UNRATIFIED
