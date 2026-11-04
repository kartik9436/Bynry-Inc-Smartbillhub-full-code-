# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) · `CR-115-BRC05` §7 — Postmark, beside
#           SendGrid. Screens: S141 (connect · test) · S142.
# Rules:    BR-INT-003 (the three exits) · BR-INT-019 (`test()` sends one real
#           message) · BR-INT-038 (translation only) · BR-NOT-1032 (PROPOSED —
#           the six normalised outcomes) · BR-NOT-013 (only a feedback webhook
#           may write `delivered`) · B14 rule 33 · CLAUDE.md 🔒 credentials
# Tests:    06-backend/tests/test_cr115_esp_adapters.py · the conformance kit
# Impacts:  apps/integrations/manifests/postmark.py · adapters/__init__.py
# ───────────────────────────────────────────────────────
"""Postmark — what is true of Postmark and of nothing else.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09, with a row in
`12-governance/09-human-review-ledger.md`.

⚠⚠ **POSTMARK'S DOMAIN VERIFICATION CANNOT BE REACHED WITH THE CREDENTIAL THIS
CONNECTOR HOLDS, AND THAT IS A BLOCKER RATHER THAN AN OMISSION —
`DEF-INT-5650`.** Postmark issues two kinds of token and they are not
interchangeable: a **Server token**, which sends mail, and an **Account token**,
which administers the account and is the ONLY thing `/domains` accepts. This
manifest declares `server_token` and nothing else, because a connector holds ONE
credential (`DEF-INT-4118`, reached here from a third direction). So:

  * `send_message` works — server token.
  * `validate_credentials` works — server token.
  * `check_domain_verified` **is not declared on the manifest at all**, this
    class overrides no domain hook, and the base answers *We cannot check this
    domain yet.* if anything ever asks.

⚠ **AND THE ACCOUNT TOKEN IS A PLATFORM CREDENTIAL, WHICH IS A SECOND BLOCKER
BEHIND THE FIRST.** PO ruling of 2026-09-17: *"our account - we will provide
service to utilities as platform provider"*. The account token belongs to US,
not to a utility, and `registry.AUTH_MODES` has no mode for a credential that
belongs to no tenant — `DEF-INT-5636`, deferred on purpose, with
`integration_credential` RLS-FORCED as the reason it cannot simply be stored.
**So Postmark's DNS values are blocked behind a ruling, not behind an
afternoon's work**, and `apps/integrations/sending_domain.py` says so on the
wire instead of serving an empty panel that reads like a bug.

⚠ **WHAT A POSTMARK UTILITY CAN STILL BE HANDED ON DAY ONE IS THE DMARC RECORD**,
because that one is not an ESP's to issue — see `esp_email.dmarc_record`. It is
a third of the long pole and it costs the utility's IT team the same ten
minutes, so it goes out now rather than waiting for the other two.

Everything shared with SendGrid is in `esp_email.py`.

⚠ **NOTHING IN THIS ENVIRONMENT HAS EVER REACHED POSTMARK.** Every shape below
is read off `CR-115-BRC05` §7's written specification, and every test runs
against `esp_fixtures.py`, hand-shaped and saying so. A green run here is
evidence about OUR code.

⚠ **POSTMARK'S FEEDBACK DOOR *CAN* OPEN, AND SENDGRID'S CANNOT.** Postmark
authenticates its webhook with HTTP Basic, the manifest declares it, and
`inbound.verify()` reads it today. What is missing is the PASSWORD: minting one
goes through `machine_auth._partner_manifest`, which refuses any connection
whose manifest is not `they_hold_ours` (`DEF-INT-5634`). So the mapping below
has no caller on this deployment either — for a different reason, one credential
door along, and it is stated rather than implied (hard-won law 2).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.integrations import email_attachments
from apps.integrations.adapters import email_format
from apps.integrations.adapters.esp_email import (
    EspEmailAdapter,
    FeedbackOutcome,
    HttpAnswer,
)

#: Where our own reference rides on a Postmark request, and where it comes back
#: on an event. Postmark calls the bag `Metadata`; the key inside it is ours and
#: is spelled the same as SendGrid's, so one reader can find it either way.
METADATA = "Metadata"
TRACKING_REF = "tracking_ref"

EMAIL_PATH = "/email"
#: ⚠ **THE PATH IS THE PO'S OWN SET-UP GUIDE'S** (`CR-115-BRC05` §7), and it is
#: not checkable from here — the egress proxy refuses Postmark exactly as it
#: refuses the City of Ann Arbor. It is written as one constant so that if the
#: real account answers `404`, the fix is this line and not a search.
SERVER_PATH = "/v3/server"

#: ⚠ **THEIR WORDS → OUR SIX, AND THIS FILE IS THE ONLY PLACE THEIRS EXIST.**
#: `RecordType` is the event; a bounce carries its own `Type` and that is where
#: hard and soft live — the single sharpest difference from SendGrid, which
#: splits the same distinction across two event NAMES.
_RECORDS: dict[str, str | None] = {
    "Delivery": "delivered",
    "SpamComplaint": "complained",
    # A `Bounce` is resolved by its `Type` below and never by this table.
    "Bounce": None,
    # A subscription change is an unsubscribe only when it SUPPRESSES; the same
    # record type carries a re-subscribe, which is not an outcome for a message.
    "SubscriptionChange": None,
    # Opens and clicks are not delivery facts and must not move a queue row.
    "Open": None,
    "Click": None,
}

#: ⚠ **THE TABLE THAT DECIDES WHETHER A REAL CUSTOMER LOSES THEIR BILLS FOR
#: EVER.** A HARD bounce suppresses; a SOFT one must never suppress, and
#: `suppression.suppress()` refuses a soft-bounce suppression BY NAME so a
#: mistake here meets an error rather than a silent success.
#:
#: `Blocked`, `Transient` and `DnsError` are the receiving side having a bad
#: day, not a mailbox that does not exist. `ManuallyDeactivated` is Postmark
#: refusing to send at all, so no mailbox was reached and it is `failed` — the
#: same reasoning SendGrid's `dropped` gets, and for the same reason: suppressing
#: on somebody else's earlier decision is `DEF-NOT-5639` wearing our list's
#: clothes.
_BOUNCE_TYPES: dict[str, str] = {
    "HardBounce": "bounced_hard",
    "BadEmailAddress": "bounced_hard",
    "SoftBounce": "bounced_soft",
    "Transient": "bounced_soft",
    "DnsError": "bounced_soft",
    "Blocked": "bounced_soft",
    "SpamNotification": "complained",
    "SpamComplaint": "complained",
    "Unsubscribe": "unsubscribed",
    "ManuallyDeactivated": "failed",
}

#: ⚠ **AN UNKNOWN BOUNCE TYPE BECOMES `failed`, AND THAT IS A JUDGMENT WE MADE
#: RATHER THAN A RULE WE WERE GIVEN** (decision log, 2026-09-17; hard-won
#: law 13 — a judgment recorded with its reasoning is the deliverable).
#:
#: Postmark documents more than twenty bounce types and adds to them. The
#: truthful word for one we do not recognise is `bounced` — *a bounce of unknown
#: kind* — and `DEF-NOT-5626`'s first judgment call keeps that word lawful while
#: ruling it **may never be written again**, so it is not available to us.
#:
#: Of the six that are, `failed` is the only one that takes no irreversible
#: action: it puts the row on the clerk's attention list (`ATTENTION_STATUSES`),
#: suppresses nothing, and leaves a person to decide. `bounced_hard` would
#: suppress a possibly-live consumer on a word we could not read, and
#: `bounced_soft` would retry into a possibly-dead mailbox for ever. Neither is
#: recoverable by a clerk; this is.
_UNKNOWN_BOUNCE = "failed"


class EmailPostmarkAdapter(EspEmailAdapter):
    """Postmark's five answers. It overrides no domain hook — see the docstring."""

    key = "postmark"

    @property
    def _vendor_name(self) -> str:
        return "Postmark"

    @property
    def _default_base_url(self) -> str:
        return "https://api.postmarkapp.com"

    @property
    def _accepted_status(self) -> int:
        """`200`, where SendGrid answers `202`. ⚠ **ACCEPTED, NOT DELIVERED** —
        the queue row becomes `sent` and only the feedback webhook may ever
        write `delivered`."""
        return 200

    def _auth_headers(self, secrets: Mapping[str, str]) -> dict[str, str]:
        """`X-Postmark-Server-Token` — the manifest's `placement="header"` and
        its declared header name, in the vendor's own spelling."""
        return {"X-Postmark-Server-Token": str(secrets.get("server_token") or "")}

    def _send_request(
        self, conn: Any, one: Mapping[str, Any]
    ) -> tuple[str, str, Mapping[str, Any]]:
        """One message, in Postmark's shape, with OUR reference in `Metadata`.

        ⚠ **NO SANDBOX FLAG, AND THE ABSENCE IS THE DIFFERENCE.** SendGrid
        sandboxes with `mail_settings.sandbox_mode` ON THE REQUEST; Postmark has
        no such field and sandboxes with a SEPARATE SERVER holding a different
        token. A connection is keyed on `(tenant, provider_key, environment)`,
        so a utility's sandbox is simply a second connection carrying the test
        token — the existing model answers it exactly and nothing is needed
        here. Writing a flag anyway would be a field Postmark ignores, which is
        a control wired to nothing.

        ⚠ **`MessageStream` IS SENT FROM CONFIG AND DEFAULTS TO `outbound`.**
        `DEF-INT-5635` records why there is no per-class map: Postmark splits
        TRANSACTIONAL from BULK and our classes split by business area, and no
        value is right for `service_field`.
        """
        config = dict(conn.config or {})
        ref = str(one.get("ref") or "").strip()
        # The template's subject, the rendered text and its escaped HTML
        # alternative. No fallback subject: a missing one is refused before
        # this is reached (`DEF-NOT-10420`).
        content = email_format.compose(
            subject=one.get("subject"),
            body=one.get("body"),
            language=one.get("language"),
            html=one.get("html"),  # CR-199-BRC10 S6 — the branded HTML part
        )
        body: dict[str, Any] = {
            "From": str(config.get("send_from") or "").strip(),
            "To": str(one.get("address") or "").strip(),
            "Subject": content.subject,
            "TextBody": content.text,
            "HtmlBody": content.html,
            "MessageStream": str(config.get("message_stream") or "outbound"),
        }
        # `DEF-NOT-10460` — the stored files the row encloses (an agreement's PDF).
        files = email_attachments.postmark(list(one.get("attachments") or ()))
        if files:
            body["Attachments"] = files
        if ref:
            body[METADATA] = {TRACKING_REF: ref}
        return "POST", self._url(conn, EMAIL_PATH), body

    def _accepted_id(self, answer: HttpAnswer) -> str | None:
        """`MessageID`, in the RESPONSE BODY — where SendGrid uses a header.

        ⚠ Postmark answers `200` with an `ErrorCode` for several REFUSALS as
        well as for a success, so a body with no `MessageID` is not a success
        however happy the status looks (`BR-INT-018`, and the honest opposite of
        wave C's no-count 200 fixture).
        """
        body = answer.body
        if not isinstance(body, Mapping):
            return None
        if int(body.get("ErrorCode") or 0) != 0:
            return None
        found = body.get("MessageID")
        return str(found).strip() or None if found else None

    def _credential_request(self, conn: Any) -> tuple[str, str]:
        return "GET", self._url(conn, SERVER_PATH)

    def _credential_can_send(self, answer: HttpAnswer) -> bool:
        """Postmark has no scopes, so the question is *does this token name a
        real Server* — which is what `GET /v3/server` answers and the whole of
        what it can answer. A token that does not is `401`, handled above."""
        body = answer.body
        return isinstance(body, Mapping) and bool(body.get("ID") or body.get("Name"))

    # ⚠ NO `_domain_request` AND NO `_domain_answer` — see the module docstring
    #   and `DEF-INT-5650`. The base's default refuses in six words rather than
    #   dialling an endpoint this credential cannot open.

    # ── the private normaliser (base.FEEDBACK_NORMALISER_METHOD) ───────────

    def _normalise_feedback(self, event: Mapping[str, Any]) -> FeedbackOutcome | None:
        """ONE Postmark event → one of our six words, or `None`.

        ⚠ **NOTHING OF POSTMARK'S VOCABULARY IS ON THE RETURN VALUE.**
        `SpamComplaint`, `SubscriptionChange` and the twenty-odd bounce types
        are read here and go no further.
        """
        record = str(event.get("RecordType") or "").strip()
        if record not in _RECORDS:
            return None
        status = _RECORDS[record]
        if record == "Bounce":
            status = _BOUNCE_TYPES.get(str(event.get("Type") or "").strip(), _UNKNOWN_BOUNCE)
        elif record == "SubscriptionChange":
            # Only a change that SUPPRESSES is an unsubscribe. A re-subscribe
            # arrives on the same record type and is news about a person, not
            # about this message.
            if not bool(event.get("SuppressSending")):
                return None
            status = "unsubscribed"
        if status is None:
            return None
        return FeedbackOutcome(
            status=status,
            tracking_ref=_tracking_ref(event),
            address=_text(event.get("Email")) or _text(event.get("Recipient")),
            occurred_at=None,  # Postmark sends an ISO stamp; the door owns time
            provider_text=_text(event.get("Description")) or _text(event.get("Details")),
        )


def _tracking_ref(event: Mapping[str, Any]) -> str | None:
    bag = event.get(METADATA)
    if isinstance(bag, Mapping):
        return _text(bag.get(TRACKING_REF))
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["EMAIL_PATH", "METADATA", "SERVER_PATH", "TRACKING_REF", "EmailPostmarkAdapter"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (the Postmark wire specification, PO's own setup guide) · the decision log of 2026-09-17 · US-INT-015 · BR-NOT-1032 (PROPOSED)
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a(backend only) C✔ D=PARTIAL(Postmark is unreachable from this environment; proofs are against esp_fixtures.py, hand-shaped) E=n/a F✔ G✔ H=PENDING(🔒 credentials)
# gates: pytest tests/test_cr115_esp_adapters.py · the conformance kit UNCHANGED · G33 · G84
# exceptions: (1) NO DOMAIN CHECK — `DEF-INT-5650`: `/domains` takes an ACCOUNT token and this connector holds a SERVER token, and the account token is a PLATFORM credential `AUTH_MODES` cannot express (`DEF-INT-5636`). The operation is not declared and the base refuses in words. (2) `_normalise_feedback` HAS NO CALLER on this deployment — the door reads Basic correctly and the password cannot be minted (`DEF-INT-5634`). (3) An unknown bounce type becomes `failed`, which is a judgment recorded in the decision log of 2026-09-17, not a rule we were given.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
