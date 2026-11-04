# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) · `CR-115-BRC05` §7 — SendGrid, the bulk
#           sender. Screens: S141 (connect · test) · S142 (the sentence, their
#           words, and the sending-domain panel another lane draws).
# Rules:    BR-INT-003 (the three exits) · BR-INT-019 (`test()` sends one real
#           message) · BR-INT-038 (translation only) · BR-NOT-1032 (PROPOSED —
#           the six normalised outcomes) · BR-NOT-013 (only a feedback webhook
#           may write `delivered`) · B14 rule 33 · CLAUDE.md 🔒 credentials
# Tests:    06-backend/tests/test_cr115_esp_adapters.py · the conformance kit
# Impacts:  apps/integrations/manifests/sendgrid.py (the manifest it serves) ·
#           apps/integrations/adapters/__init__.py (the line that binds it)
# ───────────────────────────────────────────────────────
"""SendGrid — what is true of SendGrid and of nothing else.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09, with a row in
`12-governance/09-human-review-ledger.md`.

Everything shared with Postmark is in `esp_email.py`. This file answers the
seven provider questions and holds the two translation tables that must never
leak: their event words, and their DNS answer.

⚠ **THE KEY NEEDS TWO SCOPES AND THE ACCOUNT WAS SET UP WITH ONE.** The decision
log of 2026-09-17 records the key as *"Restricted Access → Mail Send → Full
Access, as asked"*. That is `mail.send`, which is everything `send_message` and
`validate_credentials` need — and `check_domain_verified` calls
`GET /v3/whitelabel/domains`, which SendGrid gates behind **`whitelabel.read`**.
A key without it answers `403`, which this adapter translates faithfully into
*The service refused the key.* with SendGrid's own words underneath. **That is a
five-minute change on SendGrid's own screen and no change here** — recorded in
`DEF-INT-5649` so it is counted rather than trusted to this paragraph
(hard rule 4's lesson: a finding recorded only in the file you happen to be in
is a finding nobody can count).

⚠ **NOTHING IN THIS ENVIRONMENT HAS EVER REACHED SENDGRID.** Outbound HTTPS is
proxied and refused. Every shape below is read off `CR-115-BRC05` §7's written
specification, and every test runs against `esp_fixtures.py`, which is
hand-shaped and says so in its own docstring. A green run here is evidence about
OUR code and about nothing of SendGrid's.

⚠ **THE FEEDBACK DOOR STAYS SHUT AND THIS FILE DOES NOT OPEN IT.**
`DEF-INT-5630` is OPEN: SendGrid's Event Webhook signs its body and
`registry.SIGNATURE_ALGORITHMS` is `("hmac_sha256",)`, symmetric only. So
`sendgrid`'s manifest declares NO inbound verification, the door answers `None`
and refuses, and `_normalise_feedback` below has no caller on this deployment.
**It is built anyway and that is deliberate**: the mapping is the half that
takes judgment, it is testable without a door, and building it the day the door
opens is how a hard/soft distinction gets guessed at under time pressure. Its
absence of a caller is stated here rather than implied (hard-won law 2).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations import email_attachments
from apps.integrations.adapters import email_format
from apps.integrations.adapters.esp_email import (
    PURPOSE_DKIM,
    PURPOSE_RETURN_PATH,
    DnsRecord,
    DomainAnswer,
    EspEmailAdapter,
    HttpAnswer,
    FeedbackOutcome,
    state_from,
)

#: Where our own reference rides on a SendGrid request, and where it comes back
#: in an event. ONE name, because a send that writes `tracking_ref` and a
#: webhook that reads `trackingRef` is a feedback path that silently matches
#: nothing — and matching nothing looks exactly like a provider that is quiet.
TRACKING_REF = "tracking_ref"

MAIL_SEND_PATH = "/v3/mail/send"
SCOPES_PATH = "/v3/scopes"
WHITELABEL_PATH = "/v3/whitelabel/domains"

#: The scope a key must hold or nothing this connector exists for can happen.
MAIL_SEND_SCOPE = "mail.send"

#: ⚠ **THEIR WORDS → OUR SIX, AND THIS TABLE IS THE ONLY PLACE THEIRS EXIST.**
#: `notifications.models.PROVIDER_OUTCOME_STATUSES` is the contract; nothing
#: outside this file ever sees `spamreport` or `dropped` (`BR-INT-004`).
#:
#: ⚠ **THE HARD/SOFT SPLIT IS THE ONE THAT DECIDES WHETHER A REAL CUSTOMER
#: LOSES THEIR BILLS FOR EVER**, and SendGrid splits it across two EVENT NAMES
#: where Postmark carries it as a type on one event:
#:
#:   * `bounce` — the mailbox refused it. HARD. Suppresses.
#:   * `deferred` — the receiving server asked us to come back later. SOFT, and
#:     `BR-NOT-005`'s retry ×3 with backoff is already the product's answer to
#:     it. **It must NEVER suppress**, and `suppression.suppress()` refuses a
#:     soft-bounce suppression BY NAME so a mistake here meets an error rather
#:     than a silent success.
#:   * `dropped` — SendGrid declined to send it at all, usually because the
#:     address is on THEIR suppression list from an earlier bounce. We never
#:     reached a mailbox, so it is `failed` and not a bounce: calling it
#:     `bounced_hard` would suppress an address on the strength of a decision
#:     somebody else made, which is `DEF-NOT-5639`'s shared-list problem
#:     wearing our own suppression list's clothes.
#:   * `processed` — accepted into their queue. **Not an outcome at all**: the
#:     row is already `sent` and re-writing it would be a status that goes
#:     backwards. Mapped to `None` on purpose rather than left out, so a reader
#:     can see it was considered.
_EVENTS: dict[str, str | None] = {
    "delivered": "delivered",
    "bounce": "bounced_hard",
    "deferred": "bounced_soft",
    "dropped": "failed",
    "spamreport": "complained",
    "unsubscribe": "unsubscribed",
    "group_unsubscribe": "unsubscribed",
    "processed": None,
}

#: ⚠ **A `bounce` EVENT CARRIES ITS OWN `type`, AND WHERE IT SAYS `blocked` THE
#: MAILBOX DID NOT REFUSE US — A REPUTATION FILTER DID.** That is temporary and
#: retryable, so it is a SOFT bounce however it arrived. Reading the event name
#: alone would suppress a live customer over one greylisting.
_BOUNCE_TYPES: dict[str, str] = {
    "bounce": "bounced_hard",
    "blocked": "bounced_soft",
}


class EmailSendgridAdapter(EspEmailAdapter):
    """SendGrid's seven answers, and the two tables above."""

    key = "sendgrid"

    # ── the seven ──────────────────────────────────────────────────────────

    @property
    def _vendor_name(self) -> str:
        return "SendGrid"

    @property
    def _default_base_url(self) -> str:
        return "https://api.sendgrid.com"

    @property
    def _accepted_status(self) -> int:
        """`202 Accepted`. ⚠ **ACCEPTED, NOT DELIVERED** — the queue row becomes
        `sent` and only the feedback webhook may ever write `delivered`."""
        return 202

    def _auth_headers(self, secrets: Mapping[str, str]) -> dict[str, str]:
        """`Authorization: Bearer <api key>` — the manifest's `placement="bearer"`.

        The plaintext exists here, as a local name, for the length of one call.
        It is never returned, never logged (this module has no logger), never
        interpolated into a sentence and never on the `ConnectionView`.
        """
        return {"Authorization": f"Bearer {secrets.get('api_key') or ''}"}

    def _send_request(
        self, conn: Any, one: Mapping[str, Any]
    ) -> tuple[str, str, Mapping[str, Any]]:
        """One message, in SendGrid's v3 shape, with OUR reference on it.

        ⚠ **`custom_args.tracking_ref` IS HOW A BOUNCE FINDS ITS QUEUE ROW.**
        SendGrid hands custom args back on every event for the message, so we
        never have to store their `X-Message-Id` anywhere — which matters,
        because `ItemResult` has nowhere to put one and widening it for this
        would be a schema change to hold a value we do not need.

        ⚠ **SANDBOX IS A FLAG ON THE REQUEST HERE AND A DIFFERENT SERVER AT
        POSTMARK** — the sharpest operational difference between the two. The
        connection already carries `environment`, so this reads it rather than
        asking a sixth question in the modal. A sandbox request is validated
        and NOT delivered, which is exactly what a sandbox connection should do
        when somebody presses *Test*.
        """
        config = dict(conn.config or {})
        ref = str(one.get("ref") or "").strip()
        # The template's subject and both parts — `text/plain` FIRST, which
        # SendGrid requires when both are given. No fallback subject: a missing
        # one is refused before this is reached (`DEF-NOT-10420`).
        content = email_format.compose(
            subject=one.get("subject"),
            body=one.get("body"),
            language=one.get("language"),
            html=one.get("html"),  # CR-199-BRC10 S6 — the branded HTML part
        )
        personalisation: dict[str, Any] = {
            "to": [{"email": str(one.get("address") or "").strip()}]
        }
        if ref:
            personalisation["custom_args"] = {TRACKING_REF: ref}
        body: dict[str, Any] = {
            "personalizations": [personalisation],
            "from": {"email": str(config.get("send_from") or "").strip()},
            "subject": content.subject,
            "content": [
                {"type": "text/plain", "value": content.text},
                {"type": "text/html", "value": content.html},
            ],
        }
        # `DEF-NOT-10460` — the stored files the row encloses (an agreement's PDF).
        files = email_attachments.sendgrid(list(one.get("attachments") or ()))
        if files:
            body["attachments"] = files
        if str(conn.environment or "").lower() == "sandbox":
            body["mail_settings"] = {"sandbox_mode": {"enable": True}}
        return "POST", self._url(conn, MAIL_SEND_PATH), body

    def _accepted_id(self, answer: HttpAnswer) -> str | None:
        """`X-Message-Id`, a RESPONSE HEADER — SendGrid's `202` body is empty.

        ⚠ **A `202` WITH NO HEADER IS NOT A SUCCESS.** `BR-INT-018`: an outcome
        is `succeeded` only when the far end SAID what it accepted. This is the
        honest opposite of wave C's no-count 200 fixture, and it is the reason
        `_accepted()` asks for both the status and this.
        """
        return answer.header("X-Message-Id")

    def _credential_request(self, conn: Any) -> tuple[str, str]:
        return "GET", self._url(conn, SCOPES_PATH)

    def _credential_can_send(self, answer: HttpAnswer) -> bool:
        """The key is only any good to us if `mail.send` is on it.

        ⚠ **A `200` FROM `/v3/scopes` PROVES THE KEY EXISTS AND NOTHING ELSE.**
        A read-only key answers `200` with a list that does not contain
        `mail.send`, and treating that as a pass is a credential check that
        cannot fail the way production fails — `BR-INT-019`'s own warning, one
        operation along.
        """
        body = answer.body
        scopes = body.get("scopes") if isinstance(body, Mapping) else body
        if not isinstance(scopes, Sequence) or isinstance(scopes, (str, bytes)):
            return False
        return MAIL_SEND_SCOPE in {str(one) for one in scopes}

    def _domain_request(self, conn: Any, domain: str) -> tuple[str, str]:
        """⚠ Needs `whitelabel.read` on the key as well as `mail.send` — see the
        module docstring and `DEF-INT-5649`. A key without it answers `403`,
        which reaches a clerk as *The service refused the key.*"""
        return "GET", self._url(conn, WHITELABEL_PATH)

    def _domain_answer(self, answer: HttpAnswer, domain: str) -> DomainAnswer:
        """Their three CNAMEs, **read out of their answer and never composed**.

        ⚠ **THE `em1234` PREFIX AND THE DKIM SELECTORS ARE PER ACCOUNT.** They
        are in `dns.mail_cname.host`, `dns.dkim1.host` and `dns.dkim2.host` and
        there is no way to derive them. A composed value publishes cleanly,
        verifies never, and costs the utility's one-to-three-week cycle twice —
        which is why `DnsRecord.source` exists and why every record built here
        carries `provider`.
        """
        wanted = (domain or "").strip().lower().strip(".")
        rows = answer.body if isinstance(answer.body, Sequence) else []
        chosen: Mapping[str, Any] | None = None
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("domain") or "").strip().lower().strip(".") == wanted:
                chosen = row
                break
        if chosen is None:
            # ⚠ NOT AN ERROR. A domain nobody has added to SendGrid yet is the
            # ordinary state of a utility on day one, and it is what the panel
            # needs to say in order to ask for it.
            return DomainAnswer(domain=wanted, state="not_found", records=())
        records = tuple(_records_from(chosen, wanted))
        return DomainAnswer(domain=wanted, state=state_from(records), records=records)

    # ── the private normaliser (base.FEEDBACK_NORMALISER_METHOD) ───────────

    def _normalise_feedback(self, event: Mapping[str, Any]) -> FeedbackOutcome | None:
        """ONE SendGrid event → one of our six words, or `None`.

        `None` means *this event is not an outcome* — `processed`, an `open`, a
        `click`. Returning a status for one of those would move a queue row on
        news that is not about delivery at all.

        ⚠ **NOTHING OF SENDGRID'S VOCABULARY IS ON THE RETURN VALUE.** Their
        event name is read here and goes no further; `FeedbackOutcome` carries
        our word, our reference, the address and their free-text diagnostic.
        """
        name = str(event.get("event") or "").strip().lower()
        if name not in _EVENTS:
            return None
        status = _EVENTS[name]
        if status is None:
            return None
        if name == "bounce":
            status = _BOUNCE_TYPES.get(str(event.get("type") or "").strip().lower(), status)
        occurred = event.get("timestamp")
        return FeedbackOutcome(
            status=status,
            tracking_ref=_text(event.get(TRACKING_REF)),
            address=_text(event.get("email")),
            occurred_at=int(occurred) if isinstance(occurred, (int, float)) else None,
            provider_text=_text(event.get("reason")) or _text(event.get("response")),
        )


def _records_from(row: Mapping[str, Any], domain: str) -> list[DnsRecord]:
    """The three CNAMEs, each with SendGrid's own per-record `valid` verdict.

    ⚠ **`valid` IS THEIRS AND IS COPIED, NEVER INFERRED.** SendGrid re-checks
    DNS when asked and says which of the three it can see; that is the only
    honest source for *has the IT team published this one yet*, and it is the
    single question the whole one-to-three-week wait turns on.
    """
    dns = row.get("dns")
    if not isinstance(dns, Mapping):
        return []
    purposes = {
        "mail_cname": PURPOSE_RETURN_PATH,
        "dkim1": PURPOSE_DKIM,
        "dkim2": PURPOSE_DKIM,
    }
    found: list[DnsRecord] = []
    for name, purpose in purposes.items():
        entry = dns.get(name)
        if not isinstance(entry, Mapping):
            continue
        host = _text(entry.get("host"))
        value = _text(entry.get("data"))
        if not host or not value:
            continue
        found.append(
            DnsRecord(
                purpose=purpose,
                type=str(entry.get("type") or "cname").upper(),
                host=host,
                value=value,
                verified=bool(entry.get("valid")) if entry.get("valid") is not None else None,
            )
        )
    return found


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["MAIL_SEND_SCOPE", "TRACKING_REF", "EmailSendgridAdapter"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (the SendGrid wire specification, PO's own setup guide) · the decision log of 2026-09-17 · US-INT-015 · BR-NOT-1032 (PROPOSED)
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a(backend only) C✔ D=PARTIAL(SendGrid is unreachable from this environment; proofs are against esp_fixtures.py, hand-shaped) E=n/a F✔ G✔ H=PENDING(🔒 credentials)
# gates: pytest tests/test_cr115_esp_adapters.py · the conformance kit UNCHANGED · G33 · G84
# exceptions: (1) `_normalise_feedback` HAS NO CALLER on this deployment — `DEF-INT-5630` keeps SendGrid's inbound door shut and the manifest declares no verification. Stated, not implied (law 2). (2) `check_domain_verified` needs `whitelabel.read` on the key, which the account was not set up with — `DEF-INT-5649`, a change on SendGrid's own screen and not here.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
