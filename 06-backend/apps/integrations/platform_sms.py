# ── Trace ──────────────────────────────────────────────
# Change:   CR-198-BRC10 (PO 2026-10-29: "1A 2A 4B 5 US 6A(ONly Stop option is
#           required), start") — text messages through ONE shared platform
#           Twilio account.
# Rules:    BR-INT-084 (platform-held SMS credential and sender) · BR-INT-085
#           (callback signature, per-(message, status) dedupe) · CLAUDE.md
#           hard-won law 3 (fail closed) · law 4 (an existing .env does not get
#           a new setting) · hard rule 1 (no tenant table is touched here)
# Tests:    06-backend/tests/test_cr198_sms_twilio.py
# ───────────────────────────────────────────────────────
"""The platform's Twilio account: what is configured, and who sends for whom.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials, webhook keys).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-29 under the PO ruling of 2026-08-09,
with a row in `12-governance/09-human-review-ledger.md`.

⚠ **THE CREDENTIAL IS A SERVER SECRET AND THIS FILE IS THE ONLY READER OF IT.**
PO 2026-10-29, ruling 4B: *one shared platform Twilio account*, the shape of
email's *"our account - we will provdie servcie to utilities as platform
provider"* (2026-09-17). So the Account SID, the Auth Token and the API key live
in the server's environment (`config/settings/base.py`, `TWILIO_*`) and:

  * are NEVER written to a tenant row — `integration_credential` is RLS FORCED and
    tenant-owned, and a platform secret copied into every utility's store is
    our own secret duplicated N times (`DEF-INT-5636`'s reasoning);
  * are NEVER served — `card_state()` answers booleans, a sender KIND and a masked
    tail, and nothing else; the test asserts no secret byte reaches the wire;
  * are NEVER logged — this module has no logger, and `secrets()` is called at
    the moment of a call and its answer dropped after it.

⚠ **EMPTY MEANS OFF, NEVER "SEND ANYWAY"** (hard-won law 3). `configured()` is
the one question every caller asks; with any piece missing SMS is not
dispatchable, each text rests `queued` with a named reason exactly as it did
before this change, and the card reads *Not set up on this server*.

WHO SENDS FOR WHOM (decision log 2026-10-29, judgment 1)
--------------------------------------------------------
A utility on `TWILIO_SENDER_BY_UTILITY` sends through ITS OWN Messaging Service
(or number) — the SMS equivalent of email's *from the utility*. Every other
utility sends through the platform default. **The map is the SERVER's**: a
Messaging Service SID is not a secret, so a utility that could type one could
type ANOTHER utility's and text that utility's customers from that utility's
number. DevOps sets it beside the 10DLC campaign; nothing a clerk types moves it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.integrations.adapters.base import ConnectionView

PROVIDER_KEY = "sms_twilio"

#: The two ways a text can be addressed FROM. Exactly one goes on a request.
SENDER_SERVICE = "messaging_service"
SENDER_NUMBER = "from_number"

#: Why the platform cannot text, as CODES a screen can translate (rule 33).
PROBLEM_NO_ACCOUNT = "no_account"
PROBLEM_NO_SEND_CREDENTIAL = "no_send_credential"
PROBLEM_NO_SENDER = "no_sender"
PROBLEM_NO_CALLBACK_ADDRESS = "no_callback_address"
PROBLEM_CALLBACKS_UNVERIFIABLE = "callbacks_unverifiable"

#: The paths a callback reaches us at. `{utility}` is the tenant subdomain —
#: the tenant is the PATH (BR-TEN-003). The reply door has no utility, because
#: a shared sender's incoming-message webhook is one URL for every utility.
STATUS_PATH = "/api/{utility}/integrations/platform/sms_twilio/status"
REPLY_PATH = "/api/hooks/twilio/reply"


def _setting(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


@dataclass(frozen=True)
class Sender:
    """One sender: a Messaging Service SID (`MG…`) or an E.164 number."""

    kind: str
    value: str

    @property
    def hint(self) -> str:
        """The last four characters — enough to recognise, never the whole."""
        return f"••••{self.value[-4:]}" if len(self.value) > 4 else "••••"


def _sender_from(raw: str) -> Sender | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.upper().startswith("MG"):
        return Sender(SENDER_SERVICE, text)
    from apps.identity.phones import normalise_phone

    number = normalise_phone(text)
    return Sender(SENDER_NUMBER, number) if number else None


def default_sender() -> Sender | None:
    """The platform's own sender: the Messaging Service when one is set (A2P
    10DLC needs one), else the From number, else None."""
    return _sender_from(_setting("TWILIO_MESSAGING_SERVICE_SID")) or _sender_from(
        _setting("TWILIO_FROM_NUMBER")
    )


def sender_map() -> dict[str, Sender]:
    """`TWILIO_SENDER_BY_UTILITY` parsed: `riverbend:MG…;ottumwa:+1…`.

    A malformed entry is SKIPPED, never guessed at — that utility then sends
    through the platform default, which is a working sender rather than a wrong
    one."""
    found: dict[str, Sender] = {}
    for entry in _setting("TWILIO_SENDER_BY_UTILITY").split(";"):
        if ":" not in entry:
            continue
        utility, raw = entry.split(":", 1)
        sender = _sender_from(raw)
        if utility.strip() and sender is not None:
            found[utility.strip().lower()] = sender
    return found


def sender_for(utility: str | None) -> Sender | None:
    """This utility's sender: its own from the server's map, else the default."""
    own = sender_map().get(str(utility or "").strip().lower())
    return own or default_sender()


def utilities_sending_through(sender_value: str) -> tuple[str | None, ...]:
    """Which utilities a reply addressed to this sender could concern.

    `None` in the answer means *every utility on the platform default* — the
    caller narrows that to the utilities that have texted the number."""
    wanted = (sender_value or "").strip()
    named = tuple(key for key, one in sender_map().items() if one.value == wanted)
    default = default_sender()
    if default is not None and default.value == wanted:
        return (*named, None)
    return named


def sends_with() -> str | None:
    """`api_key` when both API-key halves are set, else `auth_token`, else None."""
    if _setting("TWILIO_API_KEY_SID") and _setting("TWILIO_API_KEY_SECRET"):
        return "api_key"
    if _setting("TWILIO_AUTH_TOKEN"):
        return "auth_token"
    return None


def problems() -> tuple[str, ...]:
    """Every reason the platform cannot fully text, in the order a person fixes
    them. Empty = sending AND verified callbacks both work."""
    found: list[str] = []
    if not _setting("TWILIO_ACCOUNT_SID"):
        found.append(PROBLEM_NO_ACCOUNT)
    if sends_with() is None:
        found.append(PROBLEM_NO_SEND_CREDENTIAL)
    if default_sender() is None and not sender_map():
        found.append(PROBLEM_NO_SENDER)
    if not public_api_base_url():
        found.append(PROBLEM_NO_CALLBACK_ADDRESS)
    if not _setting("TWILIO_AUTH_TOKEN"):
        found.append(PROBLEM_CALLBACKS_UNVERIFIABLE)
    return tuple(found)


def configured(utility: str | None = None) -> bool:
    """CAN a text leave for this utility? Account, a send credential and a
    sender. Callbacks are not required to SEND — without them a text stays
    `sent` and is never marked delivered, which is the honest state."""
    return bool(
        _setting("TWILIO_ACCOUNT_SID")
        and sends_with() is not None
        and sender_for(utility) is not None
    )


def public_api_base_url() -> str:
    return _setting("PUBLIC_API_BASE_URL").rstrip("/")


def status_callback_url(utility: str | None) -> str | None:
    """Where Twilio reports a text's status, or None (then none is asked for)."""
    base = public_api_base_url()
    if not base or not utility or not _setting("TWILIO_AUTH_TOKEN"):
        return None
    return base + STATUS_PATH.format(utility=utility)


def reply_url() -> str | None:
    base = public_api_base_url()
    return base + REPLY_PATH if base else None


def signing_token() -> str | None:
    """The Auth Token Twilio signs callbacks with — for `twilio_signature` only."""
    return _setting("TWILIO_AUTH_TOKEN") or None


def secrets() -> dict[str, str]:
    """The credential, for the length of ONE adapter call. Never stored."""
    return {
        "account_sid": _setting("TWILIO_ACCOUNT_SID"),
        "auth_token": _setting("TWILIO_AUTH_TOKEN"),
        "api_key_sid": _setting("TWILIO_API_KEY_SID"),
        "api_key_secret": _setting("TWILIO_API_KEY_SECRET"),
    }


def view(utility: str | None) -> ConnectionView:
    """The non-secret half an adapter sees: base URL, account, sender, callback."""
    sender = sender_for(utility)
    config: dict[str, Any] = {
        "base_url": _setting("TWILIO_API_BASE_URL") or "https://api.twilio.com",
        "account_sid": _setting("TWILIO_ACCOUNT_SID"),
        "status_callback": status_callback_url(utility),
    }
    if sender is not None:
        config["messaging_service_sid" if sender.kind == SENDER_SERVICE else "from_number"] = (
            sender.value
        )
    return ConnectionView(provider_key=PROVIDER_KEY, environment="production", config=config)


def card_state(utility: str | None) -> dict[str, Any]:
    """What the Twilio card may show. Booleans, codes and a masked tail ONLY."""
    sender = sender_for(utility)
    own = sender_map().get(str(utility or "").strip().lower())
    return {
        "provided_by_platform": True,
        "configured": configured(utility),
        "sender_kind": None if sender is None else sender.kind,
        "sender_hint": None if sender is None else sender.hint,
        "own_sender": own is not None,
        "callbacks": status_callback_url(utility) is not None,
        "problems": list(problems()),
    }


__all__ = [
    "PROVIDER_KEY",
    "SENDER_NUMBER",
    "SENDER_SERVICE",
    "Sender",
    "card_state",
    "configured",
    "default_sender",
    "problems",
    "public_api_base_url",
    "reply_url",
    "secrets",
    "sender_for",
    "sender_map",
    "signing_token",
    "status_callback_url",
    "utilities_sending_through",
    "view",
]
