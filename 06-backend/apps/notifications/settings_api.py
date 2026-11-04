# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (Settings → Notifications: the dispatch CONFIG half —
#           batch size, quiet hours, the two channel flags, served and
#           editable) · US-NOT-005 (the merge-variable catalogs, per template
#           class) · US-NOT-006 (the version lifecycle and what is PUBLISHED) ·
#           US-NOT-010 (the tone→tier mapping: which letter a tone actually
#           selects, with the tenant's own day numbers) · US-NOT-016 (custom
#           fields as template variables — the catalogue half)
#           Screens: S8 (Settings → Notifications)
# Rules:    BR-TEN-041 #8 (Settings → Notifications IS the dispatch home) ·
#           BR-NOT-005 (the queue; the dispatcher is the ONLY sender and no
#           synchronous send endpoint may exist) · BR-NOT-009 (quiet hours) ·
#           BR-NOT-010 (v1 channels: print live · email W6 · SMS v1.1) ·
#           BR-NOT-001 (category variants + a MANDATORY default fallback) ·
#           BR-NOT-006 (type × category × language; missing variant → the
#           tenant default, NEVER a blank) · BR-NOT-008 (a regulated ladder step
#           ALWAYS renders the disconnect class, whatever tone was picked) ·
#           BR-PAY-035 (three tones and no fourth) · BR-REP-016 (ladder day
#           numbers are TENANT CONFIG, never constants) · BR-BIL-027 (System
#           Admin publishes) · BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) ·
#           BR-TEN-016 (a settings edit is audited before→after) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (audited)
# Tests:    06-backend/tests/test_us_not_004_settings_api.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json (BE-11 TC05 diffs the snapshot) ·
#           07-frontend/src/features/notifications/SettingsNotificationsTab.tsx
# ───────────────────────────────────────────────────────
"""The S8 Notifications tab's CONFIG half: the queue's settings, its letters.

THIN by law (B8 / LAW 0): parse → call a service or a selector → serialize. No
ORM, no clock, no send. `apps/notifications/api.py` is the DELIVERY half (the
queue, the re-queues, the resend, the notice record); this file is everything a
System Admin CONFIGURES about that queue, and the two are separate because the
first decides what happened to a message and the second decides what the next
one will look like.

╔══════════════════════════════════════════════════════════════════════════╗
║  EVERYTHING HERE CONFIGURES A QUEUE. NOTHING HERE IMPLIES A SEND.        ║
╚══════════════════════════════════════════════════════════════════════════╝
PO re-confirmed 2026-08-16, verbatim: *"I already confirm it before it Queue
them"*. R2 has **no dispatcher run and no provider integration on any channel**
— a bill or a notice is composed, QUEUED and visible, and nothing leaves the
building. US-NOT-002 (the dispatcher) and US-NOT-003 (the provider seam) are
OUT OF THIS RELEASE BY DECISION.

So the two channel FLAGS below are exactly what BR-NOT-010 says they are —
*"whether this platform would make provider calls on that channel at all"* —
and the read says so on the wire. ⚠ **AMENDED 2026-10-22 (`DEF-NOT-10533`):**
the paragraph above describes R2 and stopped being true when the dispatcher
and the Custom SMTP adapter went live. The wire no longer carries
`dispatch_runs_in_this_release` / `no_dispatcher_reason`; it carries
`channel_lines` — one line per channel from its live state — so a switch that
reads ON is always read beside what that channel is actually doing.

────────────────────────────────────────────────────────────────────────────
THE FOUR ROUTES, AND WHAT A PERSON CAN NOW DO
────────────────────────────────────────────────────────────────────────────
    GET   /notification-settings   the dispatch configuration a tenant HAS,
                                   with what the release will and will not do
    PATCH /notification-settings   change it — System Admin, audited, atomic
    GET   /notification-templates  WHICH BODY a customer's document renders
                                   from, per class: the published version, its
                                   pin count, the merge variables it may use,
                                   and — for a class with no catalogue — the
                                   REASON no body can be written for it yet
    GET   /notice-tones            WHICH LETTER a tone actually selects, and on
                                   which of the tenant's own day numbers

THE THREE THINGS THAT ARE DELIBERATELY NOT HERE
    · **No template DESIGNER, and no body editor.** The PO CUT S91–S96 from R2
      on 2026-08-16: *"why cant we give 5 differnt tempaltes to start with and
      ask user to choose anyone; we will ahve 1 default tempalte allways"*.
      `template_service` still holds the full draft→publish→archive lifecycle;
      what is SERVED here is the read, because a designer is the thing the
      ruling removed and a chooser needs a library to choose from (see the next
      paragraph — this deployment has none, and the read says so).
    · **No send, no test-send, no preview-with-real-data.** A11 Addendum r2 §4:
      *"no synchronous send endpoint anywhere (queue only, BR-NOT-005)"*.
    · **No tone EDITOR.** BR-PAY-035's mapping is a RULE, not configuration:
      three tones, no fourth, and *"free-text tones do not exist"*.

⚠ **WHAT THE TEMPLATE READ SAYS, AND WHY IT IS TWO ANSWERS AND NOT ONE.**

Until 2026-08-16 nothing anywhere created a notification template: provisioning
seeded the chart of accounts, the number series, the holidays and billing's
fallback bill template, and no seeder, migration or route had ever written a
`notification_templates` row. So `template_service.resolve` correctly refused
for every class on every tenant, every disconnect notice and every dunning
letter was REFUSED rather than queued, and until this route landed **no human
could see that**. DEF-123's shape one module along, filed as **DEF-163**.

**IT IS NOW SEEDED, AND ONLY PARTLY** (`apps/notifications/seed_templates.py`).
Provisioning plants the classes a signed spec writes IN FULL — `dunning` and
`receipt`, quoted verbatim from A13 — and leaves every other class ABSENT WITH
ITS REASON, because a body is what a customer reads and inventing a 10-day
regulated disconnection notice or a 48-hour certified letter would put words in
a utility's mouth. So each row answers two different questions and a screen must
not collapse them:

  · `published` — is there a body for this class ON THIS TENANT, and if not,
    the resolver's own sentence in `published_unavailable`. A tenant provisioned
    before 2026-08-16 answers null for EVERYTHING until an operator runs
    `manage.py seed_demo --tenant <subdomain>` (hard-won law 4, data form).
  · `body_unavailable` — is there a body for this class ON THIS PLATFORM AT ALL,
    and if not, WHY and under which open question (OQ-243 the disconnect notice ·
    OQ-244 the payment-plan agreement · OQ-206/OQ-207 the email, SMS, contract
    and plan-notice catalogues). This one is the same on every tenant and no
    repair run changes it — only a ruling does.

*"Nobody has written this letter yet"* and *"this utility has not been given the
letter"* are different problems with different fixes, and a card showing one
blank cell for both sends a person to the wrong place.
"""

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import catalogs, dispatch_config, notices, provider_seam, rights_footer
from apps.notifications import models as notification_models
from apps.notifications import seed_templates, sender_config, template_service, tenancy_seam
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant

# ⚠ `NO_DISPATCHER_REASON` IS GONE (`DEF-NOT-10533`, PO 2026-10-22, *"Each
# channel tells the clerk the truth about itself, in one short line"*). It read
# *"Nothing is sent in this release, on any channel, printing included …"* —
# true on 2026-08-16 and false from the day the Custom SMTP adapter and the
# dispatcher went live, because a constant describing the state of a release
# is a claim nothing re-checks (hard-won law 1). `channel_lines` below replaces
# it: one line per channel, computed from that channel's live state.


def _retired_sender_fields_refused(payload: dict[str, Any]) -> None:
    """Refuse, BY NAME, a write to a mail-server field (`DEF-NOT-10534`).

    PO 2026-10-22: *"We have to move everything in connector not any other
    place"*. The five fields are Connectors' now; a write naming any of them is
    refused before anything else is read, and each one is named in the field
    list so the caller learns which.
    """
    retired = sorted(set(payload) & set(sender_config.RETIRED_FIELDS))
    if retired:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.sender.movedToConnectors",
            params={"fields": retired, "where": "connectors"},
            field_errors=[
                {
                    "field": name,
                    "code": errors.VAL_FORMAT,
                    "message_key": "notifications.sender.movedToConnectors",
                }
                for name in retired
            ],
        )


def _actor(request: Any) -> Any:
    """The B12 §6a actor shape — id from the session user, ROLE server-attached
    by the identity layer (BE-04) and never client input. `update_dispatch_settings`
    enforces BR-TEN-041 on `actor.role`, so a bare Django user would hand it an
    object with no role and be refused for the wrong reason."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="notifications.payload_not_object"
        )
    return data


def _time_field(payload: dict[str, Any], name: str) -> Any:
    """A quiet-hours boundary as `datetime.time`, from `HH:MM`.

    BR-NOT-009's window is WALL-CLOCK TENANT time and is stored as two times;
    turning them into "may this row go out now?" needs the tenant's zone and is
    the dispatcher's job (which does not run in this release at all).
    """
    from datetime import time as time_cls

    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.dispatch.timeRequired",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        parts = [int(piece) for piece in raw.split(":")[:2]]
        return time_cls(parts[0], parts[1])
    except (ValueError, IndexError) as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.dispatch.timeFormat",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _refused(detail: str, br_ref: str) -> errors.BizError:
    """A service-layer refusal as the ONE catalog exception G9 allows.

    `DispatchConfigRefused` is deliberately not a catalog exception — the
    service is called by jobs as well as by requests and a catalog code carries
    an HTTP status — so the translation belongs here, the only layer that knows
    what HTTP is. The refusal's own sentence travels in `params.detail`.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key="notifications.dispatch.refused",
        params={"detail": detail},
    )


# ── US-NOT-004 · the dispatch configuration ────────────────────────────────
@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])  # read: any role; the WRITE is Admin-only
def notification_settings(request: Any) -> Response:
    """`GET|PATCH /notification-settings` — S8's dispatch config card.

    The service has been complete, role-gated and audited since 2026-08-15 and
    had no route, so the four values the dispatcher obeys could not be seen or
    changed by anybody. The S8 tab's own header said so in as many words.

    **The role gate is the SERVICE's** (`@require_role(SYSTEM_ADMIN)`), and this
    layer does not re-implement it: US-NOT-004 TC-5 is a Billing Clerk's
    batch-size edit being SERVER-rejected, and a permission class here that
    happened to disagree with the service would be two gates for one rule.
    """
    require_tenant(request)
    if request.method == "PATCH":
        payload = _payload(request)
        _retired_sender_fields_refused(payload)
        changes: dict[str, Any] = {}
        if "dispatch_batch_size" in payload:
            changes["dispatch_batch_size"] = payload["dispatch_batch_size"]
        for field in ("quiet_hours_start", "quiet_hours_end"):
            if field in payload:
                changes[field] = _time_field(payload, field)
        for field in (
            "email_dispatch_active",
            "sms_dispatch_active",
            # CR-009 C-13 (BR-NOT-022) — the four A15 send-time elections.
            *dispatch_config.ELECTION_FIELDS,
        ):
            if field in payload:
                changes[field] = payload[field]
        unknown = sorted(set(payload) - set(dispatch_config.EDITABLE_FIELDS))
        if unknown:
            raise _refused(
                f"{', '.join(unknown)} is not a dispatch setting. The editable set is "
                f"{', '.join(dispatch_config.EDITABLE_FIELDS)} (US-NOT-004 §5).",
                "BR-TEN-041",
            )
        try:
            dispatch_config.update_dispatch_settings(actor=_actor(request), **changes)
        except dispatch_config.DispatchConfigRefused as refusal:
            raise _refused(str(refusal), "BR-NOT-009") from refusal
    return Response(_settings_dict())


def _settings_dict() -> dict[str, Any]:
    """This tenant's configuration, plus what the RELEASE does with it.

    The second half is not decoration. `email_dispatch_active: true` on a
    deployment with no dispatcher is a true fact about a stored flag and a false
    impression about the product, and the difference is the whole posture the
    delivery dashboard already keeps.
    """
    settings = dispatch_config.dispatch_settings()
    return {
        "dispatch_batch_size": settings.dispatch_batch_size,
        "quiet_hours_start": settings.quiet_hours_start.isoformat(timespec="minutes"),
        "quiet_hours_end": settings.quiet_hours_end.isoformat(timespec="minutes"),
        "email_dispatch_active": settings.email_dispatch_active,
        "sms_dispatch_active": settings.sms_dispatch_active,
        # ── CR-009 C-13 (BR-NOT-022, OQ-205 CLOSED): the four A15 elections,
        # DEFAULT ON, each beside the honest state of its CONSUMER — hard-won
        # law 2 as data, so the screen can say "this switch is read by X" or
        # "nothing reads this yet" instead of implying either.
        "receipt_on_record_payment": settings.receipt_on_record_payment,
        "credit_notice_email": settings.credit_notice_email,
        "bookkeeper_copies": settings.bookkeeper_copies,
        "lockbox_receipts": settings.lockbox_receipts,
        "election_consumers": {
            "receipt_on_record_payment": {
                "wired": True,
                "detail": (
                    # Provenance for support: read at record time by
                    # `apps/payments/receipts.py`; the document is BR-PAY-024's
                    # RCT print document.
                    # `DEF-NOT-10537`: the sentence went on *"nothing leaves
                    # the building until sending is switched on"* — false once
                    # email sends; each channel's truth is `channel_lines`.
                    "This switch is live. With it on, recording a payment puts "
                    "the customer's receipt in the outbound queue."
                ),
            },
            "credit_notice_email": {
                "wired": False,
                "detail": (
                    # Provenance for support: the credit-issue path does not
                    # queue `email_credit_issued` yet. Reported rather than
                    # implied (hard-won law 2).
                    "Your choice is saved, but nothing reads it yet — issuing a "
                    "credit does not send anything today. It will take effect "
                    "when that part of the product is switched on."
                ),
            },
            "bookkeeper_copies": {
                "wired": False,
                "detail": (
                    # Provenance for support: BR-LED-020's bookkeeper
                    # reconcile / QB-sync copies have no writer yet.
                    "Your choice is saved, but nothing reads it yet — no "
                    "bookkeeper copies are produced today. It will take effect "
                    "when that part of the product is switched on."
                ),
            },
            "lockbox_receipts": {
                "wired": False,
                "detail": (
                    # Provenance for support: US-PAY-025's lockbox half is not
                    # built, so the import queues no receipts.
                    "Your choice is saved, but nothing reads it yet — importing "
                    "a lockbox file does not send receipts today. It will take "
                    "effect when that part of the product is switched on."
                ),
            },
        },
        # BR-BIL-036 — print is the FLOOR and has no column to switch off.
        "print_dispatch_active": True,
        "print_cannot_be_switched_off": "BR-BIL-036",
        # PO 2026-10-22 — one true line per channel, from its live state
        # (`DEF-NOT-10533`). Replaces `dispatch_runs_in_this_release` and
        # `no_dispatcher_reason`, which said nothing is sent while email was.
        "channel_lines": channel_lines(settings),
        "editable_fields": list(dispatch_config.EDITABLE_FIELDS),
    }


#: The states a channel's one line can name. The screen holds a catalogue key
#: per state (`notifications.channels.line.<state>`) and nothing else, so the
#: server is the ONE opinion about what a channel is doing (B14 rule 33: a fact
#: is six words at most, plus the host).
LINE_OFF = "off"
LINE_SENDING = "sending"
LINE_NOT_WORKING = "notWorking"
LINE_NO_MAIL_SERVER = "noMailServer"
LINE_NO_TEXT_PROVIDER = "noTextProvider"
LINE_WAITING_TEXT_PROVIDER = "waitingTextProvider"
LINE_WAITING_PRINT_VENDOR = "waitingPrintVendor"

#: Integrations' word for a connection whose last test failed.
_STATUS_NOT_WORKING = "not_working"


def _line(channel: str, state: str, provider: str | None = None, host: str | None = None) -> dict:
    return {"channel": channel, "state": state, "provider": provider, "host": host}


def channel_lines(settings: Any) -> list[dict[str, Any]]:
    """One true line per channel, from that channel's LIVE state.

    PO 2026-10-22, verbatim: *"A. Each channel tells the clerk the truth about
    itself, in one short line."* The three worked lines are the ruling's own:
    Email *"Sending through Custom SMTP (smtp.office365.com)"*, Text message
    *"Not switched on"*, Printed letter *"Waiting for a print vendor"*.

    Each state is read from the same two places the dispatcher reads — the
    tenant's switch (`dispatch_config`) and the connector
    (`provider_seam.provider_status`, the dispatcher's own test of whether a
    batch could leave). A connector that cannot be read is NOT reported as
    *not connected* (`provider_seam`'s rule): the line then names no provider
    and says the channel is waiting, which is the side of the truth that sends
    a clerk to look rather than telling them all is well.
    """
    lines: list[dict[str, Any]] = []

    email = sender_config.sender_route()
    if not settings.email_dispatch_active:
        lines.append(_line(notification_models.CHANNEL_EMAIL, LINE_OFF))
    elif email.get("active"):
        state = LINE_NOT_WORKING if email.get("status") == _STATUS_NOT_WORKING else LINE_SENDING
        lines.append(
            _line(
                notification_models.CHANNEL_EMAIL,
                state,
                email.get("provider_name"),
                email.get("host"),
            )
        )
    else:
        lines.append(_line(notification_models.CHANNEL_EMAIL, LINE_NO_MAIL_SERVER))

    sms = provider_seam.provider_status(notification_models.CHANNEL_SMS) or {}
    if not settings.sms_dispatch_active:
        lines.append(_line(notification_models.CHANNEL_SMS, LINE_OFF))
    elif sms.get("connected"):
        state = LINE_NOT_WORKING if sms.get("status") == _STATUS_NOT_WORKING else LINE_SENDING
        lines.append(_line(notification_models.CHANNEL_SMS, state, sms.get("provider_name")))
    elif sms.get("connectable"):
        lines.append(_line(notification_models.CHANNEL_SMS, LINE_NO_TEXT_PROVIDER))
    else:
        lines.append(_line(notification_models.CHANNEL_SMS, LINE_WAITING_TEXT_PROVIDER))

    # BR-BIL-036: print has no switch — the floor is enforced by the queue, so
    # the line says what happens to the LETTER, never whether it may be off.
    printing = provider_seam.provider_status(notification_models.CHANNEL_PRINT) or {}
    if printing.get("connected"):
        state = (
            LINE_NOT_WORKING if printing.get("status") == _STATUS_NOT_WORKING else LINE_SENDING
        )
        lines.append(
            _line(notification_models.CHANNEL_PRINT, state, printing.get("provider_name"))
        )
    else:
        lines.append(_line(notification_models.CHANNEL_PRINT, LINE_WAITING_PRINT_VENDOR))
    return lines


def channel_line(channel: str) -> dict[str, Any] | None:
    """`channel_lines` for ONE channel, read from this tenant's live settings.

    Served on both *Send test* results (`DEF-NOT-10537`) so the sentence under
    the button is the Channel status card's own line, never a second opinion.
    `None` for a channel with no line (in-app, the portal): this product
    delivers those itself and the screen says so without a line.
    """
    settings = dispatch_config.dispatch_settings()
    for line in channel_lines(settings):
        if line["channel"] == channel:
            return line
    return None


# ── CR-009 C-12 · the tenant EMAIL SENDER config (BR-NOT-023) ──────────────
@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])  # read: any role; the WRITE is Admin-only
def notification_sender(request: Any) -> Response:
    """`GET|PATCH /notification-sender` — the mail server, READ from Connectors.

    PO 2026-10-22 (`DEF-NOT-10534`): *"We have to move everything in connector
    not any other place"*. The Notifications *Email sender (SMTP)* form is gone
    and this route is now a read of the Custom SMTP connector — host, sender,
    state — which Configure → Notifications shows with a link to Connectors.

    ⚠ PATCH STAYS MOUNTED SO IT CAN REFUSE. A write naming a mail-server field
    is refused BY NAME (*"Set this on Connectors."*); any other field is
    unknown and refused as before. Nothing on this route writes.
    """
    require_tenant(request)
    if request.method == "PATCH":
        payload = _payload(request)
        _retired_sender_fields_refused(payload)
        if payload:
            raise _refused(
                f"{', '.join(sorted(payload))} is not a sender setting. The mail server "
                "is set on Connectors.",
                "BR-NOT-023",
            )
        raise _refused("no sender setting was named, so there is nothing to save.", "BR-NOT-023")
    return Response(_sender_dict())


def _sender_dict() -> dict[str, Any]:
    """The connector's own answer, and nothing typed on this module's row.

    `connection` is `None` when integrations could not answer — a screen must
    never render that as *not connected* (`provider_seam`'s rule).
    """
    return {
        "sender_route": sender_config.sender_route(),
        "connection": sender_config.sender_status(),
        # Where the mail server is set — the Custom SMTP card on Connectors.
        "connectors_provider_key": "email_smtp",
        "retired_fields": list(sender_config.RETIRED_FIELDS),
        "editable_fields": list(sender_config.EDITABLE_FIELDS),
    }


# ── BR-NOT-015 · the disconnection notice's rights footer ─────────────────
@api_view(["GET", "PATCH"])
@permission_classes([AnyTenantRole])  # read: any role; the WRITE is Admin-only
def disconnect_rights_footer(request: Any) -> Response:
    """`GET|PATCH /disconnect-rights-footer` — the five rights clauses.

    **The whole card in one round trip**: the five clauses in printing order,
    each with its heading, its purpose, its current text, whether it is switched
    on, whether the text is still ours, and what ours says — plus the two
    sentences that mark a default AS a default (BR-NOT-015 (a)).

    ⚠ **THE ROLE GATE IS THE SERVICE's** (`@require_role(SYSTEM_ADMIN)` on
    `rights_footer.update_clauses`) and this layer does not re-implement it, for
    US-NOT-004's reason: a permission class here that happened to disagree with
    the service would be two gates for one rule, and the one that mattered would
    be whichever a caller reached first.

    PATCH body: `{"clauses": {"weather_suppression": {"enabled": false},
    "dispute_rights": {"text": "…"}}}`. `"text": null` restores the platform
    default for that clause. Only what is named is changed.
    """
    require_tenant(request)
    if request.method == "PATCH":
        payload = _payload(request)
        clauses = payload.get("clauses")
        if not isinstance(clauses, dict):
            raise _refused(
                'send the clauses you are changing under a "clauses" object — for example '
                '{"clauses": {"weather_suppression": {"enabled": false}}}. Only what you '
                "name is changed; the rest keep whatever they hold.",
                "BR-NOT-015",
            )
        try:
            rights_footer.update_clauses(actor=_actor(request), **clauses)
        except rights_footer.RightsFooterRefused as refusal:
            raise _refused(str(refusal), "BR-NOT-015") from refusal
    return Response(_rights_footer_dict(request))


def _rights_footer_dict(request: Any) -> dict[str, Any]:
    """The card's payload — clauses, the marking, and where they print.

    Every sentence a screen shows is served from here rather than composed in
    the client, the posture this module already keeps: a screen that worded the
    "this is a default" notice itself would drift from the rule the moment
    BR-NOT-015 changed, which is hard-won law 1 in a component.
    """
    clauses = rights_footer.effective_clauses()
    can_edit = getattr(request, "tenant_role", None) == "system_admin"
    return {
        "clauses": [
            {
                "code": clause.code,
                "title": clause.title,
                "purpose": clause.purpose,
                "text": clause.text,
                "enabled": clause.enabled,
                # BR-NOT-015 (a), as a VALUE. A screen must be able to mark a
                # platform default as one without inferring it from a string
                # comparison it would have to keep in step with this file.
                "is_default": clause.is_default,
                "default_text": clause.default_text,
                "source_label": (
                    rights_footer.PLATFORM_DEFAULT_LABEL
                    if clause.is_default
                    else rights_footer.TENANT_WORDING_LABEL
                ),
            }
            for clause in clauses
        ],
        # ⚠ THE SENTENCE CR-007 FORBADE SOFTENING. Served, always, whether or not
        # anything has been overridden — it is the standing statement that the
        # platform wrote these words and warrants them to nobody.
        "platform_default_notice": rights_footer.PLATFORM_DEFAULT_NOTICE,
        "tenant_wording_notice": rights_footer.TENANT_WORDING_NOTICE,
        # Where the footer actually prints, by class code, so the card can say it
        # rather than a person having to know. BR-NOT-014's three tiers and
        # nothing else — the SMS supplement carries no footer (A19 rule 3).
        "prints_on": [
            {"code": code, "name": catalogs.LISTINGS[code].name}
            for code in rights_footer.TIER_CLASSES
            if code in catalogs.LISTINGS
        ],
        # The tokens a clause may use, and the reason the set is what it is. The
        # editor offers exactly these, so a clause cannot be typed that the save
        # will refuse.
        "merge_fields": sorted(f"{{{token}}}" for token in rights_footer.allowed_tokens()),
        "merge_fields_reason": (
            "One footer prints on all three disconnection notices, and each of those "
            "carries its own merge fields (BR-NOT-014). A clause may only use a field ALL "
            "THREE have. {utility_logo} is excluded because nothing fills it — it would "
            "print a blank in the middle of a statement of your customer's rights."
        ),
        "can_edit": can_edit,
        "cannot_edit_reason": (
            None
            if can_edit
            else (
                "Only a System Admin can change these clauses. They are the text telling "
                "a customer their legal rights before their service is cut off, so the "
                "edit is restricted and every change is recorded (BR-NOT-015)."
            )
        ),
    }


# ── US-NOT-005 / US-NOT-006 / US-NOT-016 · which body a document renders from ─
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def notification_templates(request: Any) -> Response:
    """`GET /notification-templates` — the letters this utility can produce.

    One row per template class this module owns, each answering the only
    question that matters before a notice is generated: **is there a published
    body, and if not, what happens instead?**

    Four things travel per class and each is a rule rather than a display
    choice:

    * `published` — the version `template_service.resolve` would pin, resolved
      through BR-BIL-025's own order for the tenant-default variant. `null`
      means nothing renders and the notice HOLDS (field map N-1: *"dispatch
      holds safely on missing published template; content never invented"*).
    * `variables` — US-NOT-005's merge-variable catalogue, which is a WHITELIST:
      a token outside it is refused at save rather than rendered empty. Serving
      it is what lets a person see what a letter of this kind may say.
    * `custom_field_variables` — US-NOT-016's half. Custom fields resolve as
      `{{entity.custom.key}}` from the STAMPED SNAPSHOT and never from live
      master data (BR-NOT-012), which is why the shape is served rather than a
      list of this tenant's current fields: a list read live here would be the
      very lookup that rule forbids.
    * `catalog_unavailable` — for the seventeen classes A19 ratifies and gives
      no tokens (OQ-206, OQ-207), the REASON, verbatim. An empty catalogue and
      an unspecified one are different facts and are spelled differently.
    * `body_unavailable` — **DEF-163's half.** Why this PLATFORM has no body for
      the class, naming the open question that would settle it. Null for the
      classes provisioning plants. See the module docstring: this is a different
      question from `published`, and a screen that shows one cell for both sends
      a person to the wrong fix.

    ⚠ **`writable` IS FALSE ON EVERY ROW AND THAT IS THE PO's RULING, NOT A
    GAP.** S91–S96 were CUT from R2 on 2026-08-16; there is no designer and this
    endpoint is a READ. Bodies are platform-authored and seeded.
    """
    require_tenant(request)
    rows: list[dict[str, Any]] = []
    for code, klass in sorted(catalogs.CATALOGS.items()):
        if code in template_service.BILLING_OWNED_CLASSES:
            # B2 r10 #4: bills and statements pin `bill_templates`, a different
            # registry with its own chooser (S8 → Bill layout, US-BIL-021).
            # Listing them here would offer one document two homes.
            continue
        rows.append(_template_row(code, klass))
    for code, reason in sorted(catalogs.CLASSES_WITHOUT_CATALOG.items()):
        if code in template_service.BILLING_OWNED_CLASSES:
            continue
        rows.append(
            {
                "code": code,
                "group": None,
                "channel": None,
                "published": None,
                "published_unavailable": "no_token_catalogue",
                "variables": [],
                "custom_field_variables": [],
                "mandatory_content": [],
                "catalog_unavailable": reason,
                # The same sentence, on the field a screen reads for "why is
                # there no body" — so one cell answers for every class rather
                # than only for the catalogued ones.
                "body_unavailable": seed_templates.absent_reason(code) or reason,
                "writable": False,
            }
        )
    seeded = [entry.code for entry in seed_templates.SEEDABLE]
    return Response(
        {
            "results": rows,
            # The ruling that removed the designer, carried so a screen states
            # it rather than a lane remembering it.
            "designer_cut_in_r2": True,
            "designer_cut_reason": (
                "the S91-S96 template designer was CUT from R2 by the PO on 2026-08-16 "
                '("why cant we give 5 differnt tempaltes to start with and ask user to '
                'choose anyone; we will ahve 1 default tempalte allways"). Bodies are '
                "platform-authored; a tenant chooses, and never draws a layout."
            ),
            # DEF-163, as data. `platform_seeded_classes` is what provisioning
            # plants; the difference between that and `results` is what nobody
            # has written yet, and every one of those rows says which open
            # question would settle it.
            "platform_seeded_classes": seeded,
            "classes_without_a_body": sum(1 for row in rows if row["body_unavailable"]),
            "seeder": "apps.notifications.services.seed_notice_templates",
        }
    )


def _template_row(code: str, klass: catalogs.TemplateClass) -> dict[str, Any]:
    """One class: what it may say, and what it says TODAY (which is nothing).

    `resolve` is asked for the tenant-default variant — the one BR-NOT-001 makes
    MANDATORY — because that is the variant every other resolution falls back
    to. Its refusal is caught and reported as the row's own reason: a screen
    that let a `TemplateRefused` reach the error handler would darken the whole
    card over one class having no body.
    """
    published: dict[str, Any] | None = None
    unavailable: str | None = None
    try:
        resolved = template_service.resolve(code=code)
    except template_service.TemplateRefused as refusal:
        unavailable = str(refusal)
    else:
        published = {
            "template_id": str(resolved.template_id),
            "version": resolved.version,
            "category": resolved.category,
            "language": resolved.language,
            "resolved_via": resolved.via,
            "fell_back": resolved.fell_back,
        }
    return {
        "code": code,
        "group": klass.group,
        "channel": klass.channel,
        "published": published,
        "published_unavailable": unavailable,
        "variables": sorted(klass.tokens),
        # US-NOT-016 — the SHAPE, never a live list (BR-NOT-012).
        "custom_field_variables": [
            "{{account.custom.<key>}}",
            "{{premises.custom.<key>}}",
            "{{unit.custom.<key>}}",
        ],
        "mandatory_content": list(klass.mandatory_content),
        "catalog_unavailable": None,
        # DEF-163 — the PLATFORM's answer, which no repair run changes. A
        # catalogued class can still have no body: `disconnect_notice` has every
        # token A19 §2 writes and three tier bodies with one slot to put them in
        # (OQ-243), and `contract_payment_plan` has a schedule table no token
        # can express (OQ-244).
        "body_unavailable": seed_templates.absent_reason(code),
        "writable": False,
    }


# ── US-NOT-010 · which letter a tone actually selects ──────────────────────
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def notice_tones(request: Any) -> Response:
    """`GET /notice-tones` — BR-PAY-035's mapping, made visible.

    `notices.TONE_TO_STEP` is the whole of it and there is no other copy. Until
    this route landed **no surface anywhere showed a clerk which letter a tone
    selects**, and the consequence is not cosmetic: BR-NOT-008 says *"regulated
    ladder steps ALWAYS render the disconnect-notice template class regardless
    of the tone picked in the reminder modal"*, so choosing **Firm** in a
    reminder modal does not send a firmer reminder — it sends the REGULATED
    10-day disconnect notice, with its cut date and its statutory footer.
    Choosing **Final** sends the 48-hour certified letter, at real postage.

    The day numbers come from the TENANT's ladder configuration (BR-REP-016 —
    *"always tenant config, never constants"*) and this route REFUSES to invent
    them: when the settings family cannot be read, `stage_days` is reported as
    unavailable with its reason and the tones still render, because which CLASS
    a tone selects is a rule and does not depend on any day number.
    """
    require_tenant(request)
    stage_days: list[int] | None = None
    stage_days_unavailable: str | None = None
    try:
        stage_days = list(notices.stage_days())
    except tenancy_seam.CollectionsConfigUnavailable as refusal:
        stage_days_unavailable = str(refusal)

    tones = []
    for tone, step in notices.TONE_TO_STEP.items():
        regulated = step is not None
        tones.append(
            {
                "tone": tone,
                "step": step,
                # BR-NOT-008 — the CLASS, which is the half that surprises
                # people. ⚠ AMENDED 2026-08-17: this said `CLASS_DISCONNECT` for
                # every regulated tone, which was the SUPERSEDED single class and
                # therefore the wrong answer for both of them. BR-NOT-014 gives
                # each tier its own class and `notices.TIER_TO_CLASS` is the one
                # map — so "Firm" now correctly reports the 10-day class and
                # "Final" the 48-hour certified one, which is precisely the
                # difference this field exists to make visible.
                "template_class": (
                    notices.TIER_TO_CLASS[step] if regulated else notices.CLASS_DUNNING
                ),
                "regulated": regulated,
                # BR-CUS-039 — the final tier is certified mail, which costs
                # real postage and is a legal record.
                "certified_mail": step == notices.TIER_FINAL_48_HOUR,
            }
        )
    return Response(
        {
            "tones": tones,
            "stage_days": stage_days,
            "stage_days_unavailable": stage_days_unavailable,
            "tiers": list(notices.DISCONNECT_TIERS),
            # BR-PAY-035, as data: three tones and no fourth.
            "free_text_tones_exist": False,
            # PO 2026-08-16 — generating a notice QUEUES it. Nothing sends.
            "generation_queues_only": True,
        }
    )


urlpatterns = [
    path("notification-settings", notification_settings),
    path("notification-sender", notification_sender),  # CR-009 C-12
    path("disconnect-rights-footer", disconnect_rights_footer),
    path("notification-templates", notification_templates),
    path("notice-tones", notice_tones),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@3c1f8ab (ships with apps/notifications/dispatch_config.py — the same four sources: EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 03-field-map.md §1 · T7-16/T7-17; co-packets US-NOT-005/006/010/016 from EP-NOT-02-templates-rendering.md and EP-NOT-03-notices-contracts.md)
# generated: 2026-08-16 by story-coder (surface-debt tails lane — the S8 Notifications CONFIG half)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every one of the three paths answered
#         django.urls.exceptions.Resolver404 before `config/urls.py` named this
#         module, and the tone read was run against a stubbed `TONE_TO_STEP`
#         mapping `firm` to the dunning class to prove the BR-NOT-008 assertion
#         bites; verbatim transcripts in the lane report
# exceptions: (1) NO SEND, NO TEST-SEND, NO DESIGNER, NO TONE EDITOR — each for
#         its own ruled reason, all four named in the module docstring.
#         (2) THE TEMPLATE READ IS A READ. `template_service` holds a complete
#         draft→publish→archive lifecycle and none of it is mounted: with no
#         library planted (DEF-163) there is nothing for a tenant to choose
#         between, and a publish route over an empty registry is a control that
#         can only ever refuse.
#         (3) `custom_field_variables` is a SHAPE, not this tenant's field list.
#         BR-NOT-012 resolves custom fields from the stamped snapshot and never
#         from live master data; serving the live list here would be exactly the
#         lookup that rule forbids, one layer up.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
