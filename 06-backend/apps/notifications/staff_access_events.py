# ── Trace ──────────────────────────────────────────────
# Change:   CR-188-BRC10 — PO 2026-10-22, decision log *"Staff invitation
#           email: a one-time sign-in link, not a password; six answers"*.
# Rules:    BR-IDN-021 (SUPERSEDED for invitations and resets, 2026-10-22) ·
#           BR-NOT-005 (queue only — nothing here sends) · BR-NOT-021 ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           rule 7 (audited by the queue write) · hard-won law 3
# Tests:    06-backend/tests/test_cr188_staff_invite_email.py
# Impacts:  apps/identity/seams/notifications_seam.py (the ONLY caller —
#           identity resolves this module BY NAME and never imports it) ·
#           catalogs.py (`staff_user_invite`, `staff_password_reset_link`) ·
#           seed_templates.py (their bodies) · rule_catalog.py (two events)
# ───────────────────────────────────────────────────────
"""The two emails a member of staff gets about their own sign-in.

*Create user* → **Staff User Invitation & Welcome** (`staff_user_invite`).
*Reset temp password* / *Resend invitation* → **Password reset link**
(`staff_password_reset_link`). Both carry a ONE-TIME SIGN-IN LINK and never a
password — PO 2026-10-22, answer 1, verbatim: *"email a one-time sign-in link
instead, no password."* The template classes have no password token at all, so
`rendering.validate_body` refuses a body that tries to add one.

────────────────────────────────────────────────────────────────────────────
WHY THIS ASKS *CAN EMAIL LEAVE?* BEFORE IT QUEUES, WHEN OTHER WRITERS DO NOT
────────────────────────────────────────────────────────────────────────────
A bill queued while email is off rests `queued` and goes out the day email is
switched on — late, but still true. **A sign-in link does not survive that
wait:** it expires in seven days and is voided by the next one, so a row
released a fortnight later would deliver a dead link. And the admin standing at
*Create user* needs the answer NOW, because the PO's rule is that the person can
still be onboarded by hand (*"we will keep exsisting functionality as it is"*):
*"Invitation not emailed — no email provider is connected"* tells them to share
the on-screen password instead.

So `email_reachability` is asked first, through `provider_seam.channel_route` —
the dispatcher's own verdict, not a copy of it — and nothing is queued when the
answer is no. `None` from the provider read is *cannot answer*, never *not
connected*, and the two travel as different reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.notifications import (
    catalogs,
    dispatch_config,
    models,
    provider_seam,
    rendering,
    services,
    tenancy_seam,
)

#: `models.SOURCE_TYPES`' kind for these two emails. NOT `portal` (that is the
#: CUSTOMER's credential) and NOT `account` (which carries the PRINT floor and
#: would post a sign-in link by letter). No postal surface exists for a member
#: of staff, so it is in the floor test's `NO_POSTAL_SURFACE_KINDS`.
SOURCE_STAFF_ACCESS = "staff_access"

KIND_INVITE = "invite"
KIND_RESET = "reset"

TEMPLATE_INVITE = "staff_user_invite"
TEMPLATE_RESET = "staff_password_reset_link"
EVENT_INVITE = "staff_user_invited"
EVENT_RESET = "staff_password_reset"

TEMPLATE_FOR = {KIND_INVITE: TEMPLATE_INVITE, KIND_RESET: TEMPLATE_RESET}
EVENT_FOR = {KIND_INVITE: EVENT_INVITE, KIND_RESET: EVENT_RESET}

STATUS_QUEUED = "queued"
STATUS_NOT_SENT = "not_sent"

#: Why an email was not queued. CODES, never prose — the screen words them.
REASON_EMAIL_OFF = "email_sending_off"
REASON_PROVIDER_NOT_CONNECTED = provider_seam.ROUTE_PROVIDER_NOT_CONNECTED
REASON_PROVIDER_UNKNOWN = provider_seam.ROUTE_PROVIDER_STATUS_UNKNOWN
REASON_SWITCHED_OFF = "switched_off_in_settings"
REASON_QUEUE_REFUSED = "queue_refused"
REASON_TEMPLATE_MISSING = "template_missing"


@dataclass(frozen=True)
class StaffAccessMessage:
    """What one call left in the queue, or why it left nothing."""

    status: str
    reason: str | None = None
    message_id: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def email_reachability() -> str | None:
    """`None` when an email queued now would leave this deployment; else WHY not.

    The dispatcher's verdict (`provider_seam.channel_route`) with the tenant's
    own activation flag, exactly as `dispatcher._dispatch_channel` asks it.
    """
    settings = dispatch_config.dispatch_settings()
    route = provider_seam.channel_route(
        models.CHANNEL_EMAIL, active=settings.channel_is_active(models.CHANNEL_EMAIL)
    )
    if route.dispatchable:
        return None
    code = (route.problem or {}).get("code")
    if code == provider_seam.ROUTE_CHANNEL_DEFERRED:
        return REASON_EMAIL_OFF
    if code == provider_seam.ROUTE_PROVIDER_NOT_CONNECTED:
        return REASON_PROVIDER_NOT_CONNECTED
    return REASON_PROVIDER_UNKNOWN


def format_link_date(moment: Any) -> str:
    """When the link stops working, in the utility's own zone and Regional date
    format (`rendering.format_date`, the one formatter a document uses)."""
    try:
        zone = tenancy_seam.tenant_timezone()
        local = moment.astimezone(zone)
    except Exception:  # noqa: BLE001 — no zone set: the UTC date is still a true date
        local = moment
    formats, _problems = tenancy_seam.regional_formats()
    return rendering.format_date(local, formats.get("date_format"))


def queue_staff_access_email(
    *,
    kind: str,
    link_id: Any,
    email: str,
    staff_name: str,
    username: str,
    utility_name: str,
    sign_in_link: str,
    link_expires_on: str,
    actor: Any = None,
) -> StaffAccessMessage:
    """ONE email row for ONE issued sign-in link. Queue only (BR-NOT-005).

    `link_id` is the `password_links` row — the source id — so a resend is a NEW
    row (a new link) and a replay of the same link finds its own (rule 6).
    """
    template = TEMPLATE_FOR[kind]
    if catalogs.catalog_for(template) is None:  # pragma: no cover - defensive
        return StaffAccessMessage(status=STATUS_NOT_SENT, reason=REASON_QUEUE_REFUSED)
    unreachable = email_reachability()
    if unreachable is not None:
        return StaffAccessMessage(status=STATUS_NOT_SENT, reason=unreachable)
    # A tenant provisioned before CR-188 may not hold the body yet; plant it
    # (insert-missing, audited) rather than queue a row pinned to nothing.
    from apps.notifications import seed_templates

    seed_templates.ensure_seeded(template, actor=actor)
    write = services.queue_document(
        source_type=SOURCE_STAFF_ACCESS,
        source_id=link_id,
        channels=(models.CHANNEL_EMAIL,),
        template=services.TemplatePin(code=template),
        account_id=None,  # a member of staff belongs to no customer account
        recipients=(
            services.Recipient(
                channel=models.CHANNEL_EMAIL,
                address=email,
                snapshot={"name": staff_name},
            ),
        ),
        render_context={
            "staff_name": staff_name or email,
            "utility_name": utility_name,
            "username": username,
            "sign_in_link": sign_in_link,
            "link_expires_on": link_expires_on,
        },
        actor=actor,
        job="identity.staff_access",
        # BR-NOT-006 (amended 2026-09-23): the UTILITY's Regional language; the
        # variant ladder falls back to `default` where none is published.
        language=tenancy_seam.tenant_default_language(),
        event_key=EVENT_FOR[kind],
    )
    message = write.messages[0] if write.messages else None
    if message is None:
        return StaffAccessMessage(
            status=STATUS_NOT_SENT, reason=REASON_SWITCHED_OFF, problems=tuple(write.problems)
        )
    if any(p.get("code") == services.QUEUE_PIN_UNRESOLVED for p in write.problems):
        # PO 2026-10-22, *"don't do any hardcoding"*: the words come only from
        # the Settings template, so a row with nothing to render is NOT SENT.
        return StaffAccessMessage(
            status=STATUS_NOT_SENT,
            reason=REASON_TEMPLATE_MISSING,
            message_id=str(message.id),
            problems=tuple(write.problems),
        )
    return StaffAccessMessage(
        status=STATUS_QUEUED, message_id=str(message.id), problems=tuple(write.problems)
    )


__all__ = [
    "EVENT_INVITE",
    "EVENT_RESET",
    "SOURCE_STAFF_ACCESS",
    "TEMPLATE_INVITE",
    "TEMPLATE_RESET",
    "StaffAccessMessage",
    "email_reachability",
    "format_link_date",
    "queue_staff_access_email",
]
