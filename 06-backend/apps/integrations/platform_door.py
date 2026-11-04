# ── Trace ──────────────────────────────────────────────
# Change:   CR-198-BRC10 (PO 2026-10-29) — the two doors Twilio calls us at:
#           a text's delivery status, and a customer's reply (STOP only).
# Rules:    BR-INT-085 (X-Twilio-Signature checked against the address WE
#           published; a wrong one is 401 and NOTHING is saved; a status is
#           saved once per (message, status)) · BR-INT-086 (STOP) · BR-INT-021
#           (authenticate before the body is trusted) · BR-TEN-003 (the tenant
#           is the path) · CLAUDE.md hard rule 1 · hard rule 6 · hard-won law 3
# Tests:    06-backend/tests/test_cr198_sms_twilio.py
# ───────────────────────────────────────────────────────
"""Twilio's callbacks: verify, then land through notifications — and stop.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: webhook keys, idempotency keys).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-29 under the PO ruling of
2026-08-09, with a row in `12-governance/09-human-review-ledger.md`.

⚠ **WHY THIS IS NOT `inbound.receive()`.** The generic door identifies a caller
by the blind index of a credential a UTILITY's connection holds
(`serve.resolve_caller`). A platform-held account has no such row in any tenant
— its token is a server secret — so the generic door would refuse every Twilio
call for ever (law 7's *incapable of passing*). These two doors verify against
the PLATFORM's Auth Token instead, and keep everything else the generic door
promises: authenticate before anything is trusted, the same five-word refusal,
nothing saved on a refusal, saved once on a repeat.

THE SIGNATURE (Twilio's own scheme)
-----------------------------------
    X-Twilio-Signature = base64( HMAC-SHA1( AuthToken,
                             URL + name1 + value1 + name2 + value2 + … ) )

with the POST fields sorted by name. **URL is the address WE published** —
`PUBLIC_API_BASE_URL` + the request's own path and query — and NEVER one
rebuilt from the `Host` header, so a caller (or a proxy) that changes `Host`
cannot make a forged call verify, and a call signed for another address fails.

WHAT WOULD MAKE THIS PASS WRONGLY (law 7) — each refused, each tested:
  1. a missing signature header compared as empty == empty → refused first;
  2. a missing Auth Token read as *no check needed* → refused (law 3);
  3. a missing `PUBLIC_API_BASE_URL` — no published address to check against →
     refused; with it unset no StatusCallback was ever asked for anyway;
  4. `==` instead of `hmac.compare_digest` → constant-time only;
  5. the body read before the check → the form is parsed for the digest only
     (a fixed grammar — `name=value&…`), nothing is LOOKED UP until it passes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl

from apps.integrations import platform_sms
from apps.integrations.adapters import sms_twilio
from apps.integrations.seams import notifications as notifications_seam
from apps.integrations.seams import tenancy as tenancy_seam
from core import tenancy as core_tenancy

SIGNATURE_HEADER = "HTTP_X_TWILIO_SIGNATURE"
PROVIDER_KEY = platform_sms.PROVIDER_KEY


class Refused(Exception):
    """The ONE refusal: wrong or missing signature, unconfigured platform.
    The view answers it with the five words and the declared 401."""


@dataclass(frozen=True)
class DoorAnswer:
    outcome: str  # "ok" · "ignored" · "duplicate"
    detail: dict[str, Any] = field(default_factory=dict)


def expected_signature(token: str, url: str, pairs: Sequence[tuple[str, str]]) -> str:
    """Twilio's digest: URL + every (name, value) sorted by name, HMAC-SHA1."""
    data = url + "".join(name + value for name, value in sorted(pairs))
    digest = hmac.new(token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def published_url(full_path: str) -> str | None:
    """The address WE published for this path, or None (then refuse)."""
    base = platform_sms.public_api_base_url()
    return (base + full_path) if base else None


def verify(*, headers: Mapping[str, Any], full_path: str, raw_body: bytes) -> list[tuple[str, str]]:
    """The form's (name, value) pairs when the signature verifies; else raises.

    Raises `Refused` for every failure — no token, no published address, no
    header, a header that does not match — and never says which."""
    token = platform_sms.signing_token()
    url = published_url(full_path)
    presented = str(headers.get(SIGNATURE_HEADER) or "").strip()
    if not token or not url or not presented:
        raise Refused()
    try:
        pairs = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError as bad:
        raise Refused() from bad
    expected = expected_signature(token, url, pairs)
    if not hmac.compare_digest(expected.encode("ascii"), presented.encode("ascii", "replace")):
        raise Refused()
    return pairs


def _last(pairs: Sequence[tuple[str, str]], name: str) -> str:
    found = ""
    for key, value in pairs:
        if key == name:
            found = value
    return found.strip()


def status(
    *, headers: Mapping[str, Any], full_path: str, raw_body: bytes, received_at: datetime
) -> DoorAnswer:
    """A status callback for THIS utility's text (the tenant is the path and
    the middleware has set it). Verify → map → land once."""
    if core_tenancy.current_tenant_id() is None:
        raise Refused()
    pairs = verify(headers=headers, full_path=full_path, raw_body=raw_body)
    sid = _last(pairs, "MessageSid") or _last(pairs, "SmsSid")
    their_status = (_last(pairs, "MessageStatus") or _last(pairs, "SmsStatus")).lower()
    outcome = sms_twilio.map_status(their_status)
    if not sid or outcome is None:
        return DoorAnswer("ignored", {"status": their_status or None})
    error_code = _last(pairs, "ErrorCode") or None
    error_text = _last(pairs, "ErrorMessage") or None
    landed = notifications_seam.record_text_status(
        provider=PROVIDER_KEY,
        reference=sid,
        outcome=outcome,
        provider_status=their_status,
        error_code=error_code,
        provider_text=(f"{error_code}: {error_text}" if error_code and error_text else error_text),
        received_at=received_at,
    )
    if landed is None:  # pragma: no cover — notifications publishes it
        raise Refused()
    return DoorAnswer("ok" if landed.get("landed") else "duplicate", landed)


def _candidate_utilities(sender: str) -> tuple[str, ...]:
    """The utilities a reply to this sender could concern: those mapped to it,
    plus — when it is the platform default — every live utility with no sender
    of its own. Never a utility on a DIFFERENT sender."""
    through = platform_sms.utilities_sending_through(sender)
    named = tuple(one for one in through if one)
    if None not in through:
        return named
    mapped = set(platform_sms.sender_map())
    rest = tuple(one for one in tenancy_seam.live_utilities() if one.lower() not in mapped)
    return named + rest


def reply(
    *, headers: Mapping[str, Any], full_path: str, raw_body: bytes, received_at: datetime
) -> DoorAnswer:
    """A customer's incoming text. Only STOP is acted on (PO 2026-10-29).

    Applied, inside EACH concerned utility's own tenant context, for exactly
    the utilities that send through the sender it was addressed to AND have
    texted this number (decision log 2026-10-29, judgment 2)."""
    pairs = verify(headers=headers, full_path=full_path, raw_body=raw_body)
    if not sms_twilio.is_stop(_last(pairs, "Body"), _last(pairs, "OptOutType")):
        # START, HELP and every other reply: not built (PO: STOP only). Twilio's
        # Advanced Opt-Out answers START/HELP at the carrier.
        return DoorAnswer("ignored")
    sid = _last(pairs, "MessageSid") or _last(pairs, "SmsSid")
    number = _last(pairs, "From")
    sender = _last(pairs, "MessagingServiceSid") or _last(pairs, "To")
    if not sid or not number or not sender:
        return DoorAnswer("ignored")
    applied: list[dict[str, Any]] = []
    for utility in _candidate_utilities(sender):
        tenant_id = tenancy_seam.tenant_for(utility)
        if tenant_id is None:
            continue
        with core_tenancy.tenant_context(tenant_id):
            if not notifications_seam.has_texted(number):
                continue
            landed = notifications_seam.record_text_stop(
                provider=PROVIDER_KEY,
                reference=sid,
                from_number=number,
                received_at=received_at,
            )
        if landed is not None:
            applied.append(landed)
    if applied and not any(one.get("landed") for one in applied):
        return DoorAnswer("duplicate", {"utilities": len(applied)})
    return DoorAnswer("ok", {"utilities": len(applied)})


__all__ = [
    "DoorAnswer",
    "Refused",
    "expected_signature",
    "published_url",
    "reply",
    "status",
    "verify",
]
