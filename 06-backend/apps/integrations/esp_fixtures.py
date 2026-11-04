# ── Trace ──────────────────────────────────────────────
# Story:    `CR-115-BRC05` §7 — the two email service providers. This is the
#           stand-in every proof over them runs against.
# Rules:    CLAUDE.md hard-won law 7 (a check that cannot fail is worse than no
#           check — see WHAT THIS CANNOT PROVE) · BR-INT-019 · BR-INT-038
# Tests:    06-backend/tests/test_cr115_esp_adapters.py
# Impacts:  apps/integrations/adapters/esp_email.py (the `Transport` it serves)
# ───────────────────────────────────────────────────────
"""Hand-shaped SendGrid and Postmark answers. **NOT A RECORDING.**

⚠⚠ **WHAT THIS CANNOT PROVE, SAID FIRST BECAUSE IT IS THE THING A READER MUST
NOT MISS.** Nothing in this build environment has ever reached SendGrid or
Postmark: outbound HTTPS is proxied and refused, the same wall `CR-115-BRC05`
§7.10 records for the City of Ann Arbor (*"`curl` returns code `000`"*). Every
byte below was written by hand from the wire formats in `CR-115-BRC05` §7 — the
Product Owner's own set-up guide — and from nothing else.

**So a green test over this file is evidence about OUR code and about nothing of
either vendor's.** If SendGrid's `202` carries the accepted id under a different
header, or Postmark's server endpoint lives at a different path, every test here
still passes and the product still fails on the first real bill. That is not a
flaw in these fixtures; it is the honest boundary of what can be proved from
here, and `CR-112`'s stand-in carries the identical warning for the identical
reason.

⚠ **THIS FILE IS THE `Transport` SEAM AND NOTHING ELSE.** It answers HTTP, it
decides nothing, and it holds no adapter logic — an adapter proved against a
fixture that reimplements the adapter proves only that somebody wrote the same
thing twice (law 7's *a test that constructs the thing it is testing*).

WHAT IS HERE
------------
  * `sendgrid_transport(...)` and `postmark_transport(...)` — happy paths, with
    the accepted id in the place each vendor really puts it.
  * `refusing_transport(status, body)` — a `4xx` that is an ANSWER, which is
    what a wrong key and an unverified sender both look like.
  * `unreachable_transport()` — a socket that never opens, which is a
    `ProviderTimeout` and NOT an answer (`DEF-INT-5599`'s distinction).
  * `SENDGRID_DOMAINS` — one whitelabel row with its three CNAMEs, two of them
    published and one not, so the PARTIAL state is exercised rather than assumed.
  * `SENDGRID_EVENTS` / `POSTMARK_EVENTS` — one of each event shape the two
    normalisers claim to read.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from apps.integrations.adapters.esp_email import HttpAnswer
from apps.integrations.runtime import ProviderTimeout

#: ⚠ **THE PREFIX AND THE SELECTORS ARE MADE UP AND THAT IS THE POINT OF SAYING
#: SO.** `em7391` and `s1`/`s2` differ per SendGrid ACCOUNT; a real utility's
#: values can only come out of a real answer. If any code path ever composes a
#: host that looks like one of these, it is building a record that will publish
#: cleanly and verify never.
SENDGRID_DOMAINS: list[dict[str, Any]] = [
    {
        "id": 7391,
        "domain": "ottumwawater.gov",
        "subdomain": "em7391",
        "valid": False,
        "dns": {
            "mail_cname": {
                "host": "em7391.ottumwawater.gov",
                "type": "cname",
                "data": "u7391.wl.sendgrid.net",
                "valid": True,
            },
            "dkim1": {
                "host": "s1._domainkey.ottumwawater.gov",
                "type": "cname",
                "data": "s1.domainkey.u7391.wl.sendgrid.net",
                "valid": True,
            },
            "dkim2": {
                "host": "s2._domainkey.ottumwawater.gov",
                "type": "cname",
                "data": "s2.domainkey.u7391.wl.sendgrid.net",
                # ⚠ FALSE ON PURPOSE. Two of three published is the state a
                # utility is ACTUALLY in for most of the one-to-three-week wait,
                # and a fixture where everything is verified cannot tell a
                # working partial-state panel from a broken one.
                "valid": False,
            },
        },
    }
]

SENDGRID_SCOPES: dict[str, Any] = {"scopes": ["mail.send", "sender_verification_eligible"]}
SENDGRID_SCOPES_READ_ONLY: dict[str, Any] = {"scopes": ["templates.read", "stats.read"]}

POSTMARK_SERVER: dict[str, Any] = {"ID": 8281, "Name": "SmartBillHub production", "Color": "blue"}

#: One of every SendGrid event shape `email_sendgrid._EVENTS` claims to read.
SENDGRID_EVENTS: list[dict[str, Any]] = [
    {"event": "delivered", "email": "a@x.example", "tracking_ref": "q-1", "timestamp": 1789000000},
    {"event": "bounce", "type": "bounce", "email": "b@x.example", "tracking_ref": "q-2",
     "reason": "550 5.1.1 unknown user"},
    {"event": "bounce", "type": "blocked", "email": "c@x.example", "tracking_ref": "q-3",
     "reason": "421 4.7.0 try later"},
    {"event": "deferred", "email": "d@x.example", "tracking_ref": "q-4", "response": "mailbox full"},
    {"event": "dropped", "email": "e@x.example", "tracking_ref": "q-5", "reason": "Bounced Address"},
    {"event": "spamreport", "email": "f@x.example", "tracking_ref": "q-6"},
    {"event": "unsubscribe", "email": "g@x.example", "tracking_ref": "q-7"},
    {"event": "processed", "email": "h@x.example", "tracking_ref": "q-8"},
    {"event": "open", "email": "i@x.example", "tracking_ref": "q-9"},
]

#: One of every Postmark event shape `email_postmark._RECORDS` claims to read.
POSTMARK_EVENTS: list[dict[str, Any]] = [
    {"RecordType": "Delivery", "Email": "a@x.example", "Metadata": {"tracking_ref": "q-1"}},
    {"RecordType": "Bounce", "Type": "HardBounce", "Email": "b@x.example",
     "Metadata": {"tracking_ref": "q-2"}, "Description": "The address does not exist"},
    {"RecordType": "Bounce", "Type": "SoftBounce", "Email": "c@x.example",
     "Metadata": {"tracking_ref": "q-3"}, "Description": "Mailbox full"},
    {"RecordType": "Bounce", "Type": "Blocked", "Email": "d@x.example",
     "Metadata": {"tracking_ref": "q-4"}},
    {"RecordType": "Bounce", "Type": "AGreenFieldTypeWeHaveNeverSeen", "Email": "e@x.example",
     "Metadata": {"tracking_ref": "q-5"}},
    {"RecordType": "SpamComplaint", "Email": "f@x.example", "Metadata": {"tracking_ref": "q-6"}},
    {"RecordType": "SubscriptionChange", "SuppressSending": True, "Email": "g@x.example",
     "Metadata": {"tracking_ref": "q-7"}},
    {"RecordType": "SubscriptionChange", "SuppressSending": False, "Email": "h@x.example",
     "Metadata": {"tracking_ref": "q-8"}},
    {"RecordType": "Open", "Email": "i@x.example", "Metadata": {"tracking_ref": "q-9"}},
]


def _answer(status: int, body: Any = None, headers: Mapping[str, str] | None = None) -> HttpAnswer:
    raw = "" if body is None else json.dumps(body)
    return HttpAnswer(status=status, body=body, headers=dict(headers or {}), text=raw)


#: ⚠ **THE TRANSPORTS REFUSE A WRONG CREDENTIAL, AND THAT IS NOT DECORATION.**
#: The conformance kit's sharpest case is *a wrong credential is `ok=False` with
#: their words underneath, and never raises*. A fixture that accepted anything
#: would pass that case by being incapable of the failure it is checking for
#: (hard-won law 7), so these read the header the adapter built and answer `401`
#: when it does not carry the expected value. It is also the only place in this
#: file that proves the adapter put the credential where the manifest says.
SENDGRID_GOOD_KEY = "SG.a-real-looking-key-value"
POSTMARK_GOOD_TOKEN = "0f3a1c88-postmark-server-token"

_REFUSED_SENDGRID = {"errors": [{"message": "The provided authorization grant is invalid"}]}
_REFUSED_POSTMARK = {"ErrorCode": 10, "Message": "No account or server API tokens were supplied"}


def sendgrid_transport(
    *,
    scopes: Any = None,
    domains: Any = None,
    message_id: str = "sg-msg-1",
    good_key: str = SENDGRID_GOOD_KEY,
):
    """A SendGrid that accepts a good key, refuses a bad one, and records both.

    The returned callable carries a `.sent` list of `(method, url, headers,
    body)` so a test can assert the SHAPE we put on the wire — the sandbox flag,
    the tracking reference, the From address — rather than only the outcome.
    """
    sent: list[tuple[str, str, dict[str, str], Any]] = []

    def transport(method, url, headers, body, timeout_s):  # noqa: ANN001, ARG001
        sent.append((method, url, dict(headers), json.loads(body) if body else None))
        if headers.get("Authorization") != f"Bearer {good_key}":
            return _answer(401, _REFUSED_SENDGRID)
        if url.endswith("/v3/mail/send"):
            return _answer(202, None, {"X-Message-Id": message_id})
        if url.endswith("/v3/scopes"):
            return _answer(200, SENDGRID_SCOPES if scopes is None else scopes)
        if url.endswith("/v3/whitelabel/domains"):
            return _answer(200, SENDGRID_DOMAINS if domains is None else domains)
        return _answer(404, {"errors": [{"message": "not found"}]})

    transport.sent = sent  # type: ignore[attr-defined]
    return transport


def postmark_transport(
    *,
    server: Any = None,
    message_id: str = "pm-msg-1",
    error_code: int = 0,
    good_token: str = POSTMARK_GOOD_TOKEN,
):
    """A Postmark that accepts a good token, refuses a bad one, and records both."""
    sent: list[tuple[str, str, dict[str, str], Any]] = []

    def transport(method, url, headers, body, timeout_s):  # noqa: ANN001, ARG001
        sent.append((method, url, dict(headers), json.loads(body) if body else None))
        if headers.get("X-Postmark-Server-Token") != good_token:
            return _answer(401, _REFUSED_POSTMARK)
        if url.endswith("/email"):
            return _answer(
                200,
                {"MessageID": message_id, "ErrorCode": error_code, "Message": "OK"},
            )
        if url.endswith("/v3/server"):
            return _answer(200, POSTMARK_SERVER if server is None else server)
        return _answer(404, {"ErrorCode": 701, "Message": "not found"})

    transport.sent = sent  # type: ignore[attr-defined]
    return transport


def refusing_transport(status: int = 401, body: Any = None):
    """A provider that ANSWERED, unhappily. Never a `ProviderTimeout`.

    ⚠ This is the case `BR-INT-022` is explicit about: a refusal must not count
    towards a breaker built for a provider that is not there.
    """

    def transport(method, url, headers, body_bytes, timeout_s):  # noqa: ANN001, ARG001
        return _answer(status, body if body is not None else {"errors": [{"message": "no"}]})

    return transport


def unreachable_transport():
    """A socket that never opens — `ProviderTimeout`, which is NOT an answer."""

    def transport(method, url, headers, body_bytes, timeout_s):  # noqa: ANN001, ARG001
        raise ProviderTimeout("the service could not be reached: tunnel refused")

    return transport


__all__ = [
    "POSTMARK_EVENTS",
    "POSTMARK_GOOD_TOKEN",
    "POSTMARK_SERVER",
    "SENDGRID_DOMAINS",
    "SENDGRID_EVENTS",
    "SENDGRID_GOOD_KEY",
    "SENDGRID_SCOPES",
    "SENDGRID_SCOPES_READ_ONLY",
    "postmark_transport",
    "refusing_transport",
    "sendgrid_transport",
    "unreachable_transport",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (the two wire specifications) · CR-112's gis_fixtures.py (the precedent, and the warning copied from it)
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_esp_adapters.py
# exceptions: HAND-SHAPED, NOT RECORDED — neither provider is reachable from this environment and the docstring says so first, before anything else a reader might take on trust.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
