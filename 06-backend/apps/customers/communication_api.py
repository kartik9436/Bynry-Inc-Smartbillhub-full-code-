# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave K — `ACC-S16`, the communication section.
#           Step 1 lane 2 finding F11: *"There is no way to write to the
#           customer from this screen. Seven icons and six buttons and not one
#           sends a word."* Drawing `R6`, pages 186–188.
# Story:    US-CUS-008 (S21 detail header + action rails) · screen S21.
# Rules:    BR-NOT-005 (queue rows only — NOTHING is ever sent from a screen) ·
#           BR-NOT-013 (delivery is out of this release on post, email and SMS
#           alike; `delivered` and `bounced` can never be written here) ·
#           BR-PAY-035 (a reminder's tone IS a dunning tier; free-text tones do
#           not exist) · BR-NOT-008 (a regulated step renders the disconnect
#           class whatever tone was picked) · BR-BIL-036 (an account with no
#           address on a channel is NORMAL — the absence is stated) ·
#           BR-SHL-025 (a control with no path is refused WITH ITS REASON) ·
#           B1/B2 §2 (customers must not write notifications' tables — this
#           asks through `notifications_seam`) · CLAUDE.md hard rule 1 (tenant
#           scoping) · rule 6 (idempotency) · rule 7 (every money action audits
#           — this one is not a money action and the queue audits its own row).
# Tests:    06-backend/tests/test_cr094_k_account_communication.py
# Impacts:  07-frontend/src/features/customers/AccountCommunicationDialog.tsx ·
#           config/urls.py (this module's `urlpatterns` is included there) ·
#           apps/notifications/customer_events.queue_account_message.
# ───────────────────────────────────────────────────────
"""Writing to a customer from their account — and NOTHING here sends a word.

╔══════════════════════════════════════════════════════════════════════════╗
║  `ACC-S16`, the blueprint's own commitment card:                         ║
║  *"A clerk can write to the customer from the account, and see what has  ║
║   already been sent."*                                                    ║
╚══════════════════════════════════════════════════════════════════════════╝

WHY THIS IS ITS OWN FILE AND NOT SIX MORE LINES IN `api.py`
────────────────────────────────────────────────────────────────────────────
`apps/customers/api.py` is 1,500 routes of shared surface that three lanes were
editing on the afternoon this landed. `service_request_api.py` and
`transfer_disconnect_api.py` are the precedent: a module may export its own
`urlpatterns` and `config/urls.py` includes them. That keeps a wave's endpoints
out of a file every other wave is also holding — CLAUDE.md law 11's mechanism
five (a pathspec commit publishes a neighbour's uncommitted work) avoided by
construction rather than by care.

THE HISTORY VIEW IS NOT HERE, AND THAT IS THE POINT
────────────────────────────────────────────────────────────────────────────
*"What has already gone out"* is served ENTIRELY by `GET /outbound` with
`f.account_id` — notifications' own S8 queue list, which already carries the
capability row's search, its filters, its ratified *failed and bounced first*
sort and server pagination, and whose `Resend` and `Requeue` are real
endpoints. The drawing says so itself: *"The outbound queue, its search and
filters, its failed and bounced first sort, and Resend and Requeue are all
served today."* **So this file adds ZERO read endpoints for it.** A second list
over the same table would be the duplicate code the PO's standing instruction
forbids, and it would be the one that drifts.

WHAT THE COMPOSE VIEW MAY HONESTLY SAY
────────────────────────────────────────────────────────────────────────────
⚠ **`BR-NOT-013`, CONFIRMED BY THE PO ON 2026-08-15:** *"DELIVERY IS OUT OF
THIS RELEASE … No provider adapter exists or is coming on ANY channel, print
included."* Measured rather than trusted: `provider_seam` resolves the vendor
adapter as `apps.integrations.services.dispatch_outbound_batch`, and that
function exists nowhere in `apps/integrations` — its eleven occurrences in this
repo are all tests monkeypatching it into place.

⚠ **AMENDED 2026-10-22 (`DEF-NOT-10537`): THE TWO PARAGRAPHS ABOVE ARE THE
2026-08-15 WORLD.** The Custom SMTP adapter is live, so an email row on a
utility with a working connector IS sent; post and text still rest `queued`.
Nothing below had to change, because none of it assumed either answer:

A dialog that told a clerk their customer had been emailed when the row will
only rest `queued` would be wrong, which is worse than no dialog at all. `GET`
therefore serves `channels[].delivers` from the same `channel_route` the
dispatcher branches on, and the screen states it. The portal is the one channel that reaches a customer
today (`BR-NOT-1031`), and it says so for the same reason.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core import errors
from core.permissions import AdminOrClerk, AnyTenantRole
from core.tenancy import require_tenant

from apps.customers import notifications_seam, seams, selectors

#: The channels the dialog offers, in the drawing's own order — email, text
#: message, post — with the portal last because it is the newest and, on this
#: deployment, the only one that arrives.
OFFERED_CHANNELS: tuple[str, ...] = ("email", "sms", "pdf_print", "portal")

#: `BR-SHL-025` codes, never prose: the screen resolves its own sentence in the
#: clerk's language and a message key cannot be translated from a paragraph.
KIND_REFUSED = "message_kind_not_composed_here"
NO_CHANNEL_TICKED = "message_no_channel"
BODY_EMPTY = "message_body_empty"
BAD_MESSAGE_ID = "message_id_not_a_uuid"

#: `BR-PAY-035` fixes a reminder's tone to a dunning tier and `BR-NOT-008` fixes
#: the disconnect class, so neither is composed here; a bill copy and a balance
#: statement each already have a writer. Named as CODES so the screen shows the
#: clerk where to go instead of a dead control (`BR-SHL-025`).
BR_REF_KIND = "BR-PAY-035 · BR-NOT-008"


def _actor(request: Any) -> Any:
    return getattr(request, "user", None)


def _payload(request: Any) -> dict[str, Any]:
    data = getattr(request, "data", None)
    return dict(data) if isinstance(data, dict) else {}


def _business_date(payload: dict[str, Any]) -> date:
    """`BR-TEN-043` — the business date is an INPUT and never a clock read.

    The dialog's *Queue it · Now* sends today as the utility sees it; *On a date
    I choose* sends that date. An absent value is refused rather than defaulted,
    because a default here is a wall clock wearing a parameter's clothes.
    """
    raw = payload.get("on_date")
    if not raw:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-TEN-043",
            message_key="customers.account.communication.error.noDate",
            detail="the date this message is queued on is the caller's, never this "
            "server's clock. The dialog sends the utility's own today for *Now*.",
        )
    try:
        return date.fromisoformat(str(raw))
    except ValueError as bad:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-TEN-043",
            message_key="customers.account.communication.error.badDate",
            detail=f"{raw!r} is not a date.",
        ) from bad


@api_view(["GET", "POST"])
@permission_classes([AnyTenantRole])  # the POST re-checks; an Executive may READ
def account_communication(request: Any, account_id: str) -> Response:
    """`GET|POST /accounts/{id}/communication` — the dialog, and its one commit.

    **GET** answers everything the compose view needs and nothing it does not:
    who the message would go to per channel, whether that channel actually
    delivers on this deployment, and which kinds may be composed here at all.

    **POST** queues it. The response says `queued`, never `sent` — there is no
    word in this module's vocabulary for a thing that left the building, because
    nothing does.
    """
    require_tenant(request)
    if request.method == "POST":
        if not AdminOrClerk().has_permission(request, None):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-IDN-009")
        return _queue(request, account_id)
    return Response(_form(account_id))


def _form(account_id: str) -> dict[str, Any]:
    """WHO it would go to, WHETHER that route delivers, and WHAT may be written.

    ⚠ **A CHANNEL WITH NOTHING ON FILE IS SERVED AND NOT DROPPED**, which is the
    drawing's own instruction: *"A channel with nothing on file is shown and
    cannot be ticked, so a clerk can see what is missing rather than wonder why
    an option vanished."* `BR-BIL-036` is the rule underneath — an account with
    no email address is NORMAL — and the absence arrives as a REASON rather than
    as a blank.
    """
    account = selectors.account_detail(account_id)
    recipients = selectors.delivery_recipients_for_account(account_id, OFFERED_CHANNELS)
    #: The UTILITY's default language — the FALLBACK — and the account's own,
    #: asked first (PO option B, 2026-10-29). Read once, so the field the
    #: dialog shows and the wording it offers cannot disagree.
    utility = seams.tenant_default_language()
    stated = selectors.account_preferred_language(account_id)
    language = stated or utility
    reach = {row["channel"]: row for row in notifications_seam.channel_reachability(OFFERED_CHANNELS)}
    channels: list[dict[str, Any]] = []
    for channel in OFFERED_CHANNELS:
        entry = recipients.get(channel) or {}
        route = reach.get(channel) or {}
        channels.append(
            {
                "channel": channel,
                "address": entry.get("address"),
                #: Exactly one of `address` and `unavailable_reason` is set —
                #: the same either/or `outbound_messages` makes structural.
                "unavailable_reason": entry.get("unavailable_reason"),
                "on_file": bool(entry.get("address")),
                #: ⚠ **THE HONEST HALF.** False means a row queued here rests
                #: `queued` and is not sent (`BR-NOT-013`). It is served, not
                #: inferred on the screen, so one answer governs the dialog and
                #: the dispatcher.
                "delivers": bool(route.get("delivers")),
                "delivers_reason": route.get("reason"),
            }
        )
    return {
        "account_id": str(account["id"]),
        "account_no": account.get("account_no"),
        #: `account_row`'s `name` is the account's own name — *Bramble Bakery*
        #: — which is what the drawing prints under the dialog's heading.
        "customer_name": account.get("name"),
        #: The language this message will go in — the dialog SHOWS it and
        #: never asks for it, and `_queue` pins the template variant from the
        #: same read, so the two cannot disagree.
        #:
        #: ⚠ **THE ACCOUNT'S LANGUAGE AGAIN — AMENDED 2026-10-29 (PO option B,
        #: *"Question: which language should messages be sent in? - B"*,
        #: superseding `OQ-CUS-12619` (a) for messages).** From 2026-09-23 this
        #: was the utility's default. It is now the account's stated language,
        #: or the utility's where the account states none; a class the utility
        #: has not published in it still goes in `fallback_language`.
        "language": language,
        "fallback_language": utility,
        "kinds": list(notifications_seam.message_kinds()),
        #: ⚠ **THE UTILITY'S OWN AGREED WORDING, NOT A BLANK BOX.** PO,
        #: 2026-09-13: *"it should also have ready to use messages from our
        #: Notification rules - user will not write it every time"*. Resolved
        #: in the ACCOUNT's language where published, the utility's otherwise
        #: (PO option B, 2026-10-29), so Rosa's clerk is offered the Spanish
        #: letter where one is published, and served rather than
        #: fetched separately because the dialog already waits on this one
        #: call — a second round trip would open the picker after the clerk had
        #: started typing.
        "templates": list(
            notifications_seam.message_templates(
                language=utility,
                channels=OFFERED_CHANNELS,
                preferred_language=stated,
            )
        ),
        "channels": channels,
    }


def _queue(request: Any, account_id: str) -> Response:
    payload = _payload(request)
    raw_id = str(payload.get("message_id") or "").strip()
    try:
        message_id = UUID(raw_id)
    except (ValueError, AttributeError, TypeError) as bad:
        # ⚠ The id is the IDEMPOTENCY KEY (CLAUDE.md rule 6) and the screen mints
        # it, so a missing one is a bug in the caller rather than a clerk's
        # mistake — refused by name instead of minted here, because a server that
        # minted one would write a second message on every double click.
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="CLAUDE.md rule 6",
            message_key="customers.account.communication.error.badId",
            detail="the compose dialog mints the message id so a second submit finds the "
            "first message instead of writing another.",
        ) from bad

    channels = tuple(str(one) for one in (payload.get("channels") or ()) if str(one).strip())
    if not channels:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-NOT-005",
            message_key="customers.account.communication.error.noChannel",
            detail="a message with no channel is not queued anywhere.",
        )
    unknown = [one for one in channels if one not in OFFERED_CHANNELS]
    if unknown:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-010",
            message_key="customers.account.communication.error.badChannel",
            detail=f"{', '.join(sorted(unknown))} is not a channel this dialog offers.",
        )

    outcome = notifications_seam.queue_account_message(
        message_id=message_id,
        account_id=account_id,
        channels=channels,
        subject=str(payload.get("subject") or ""),
        body=str(payload.get("body") or ""),
        signed_by=str(payload.get("signed_by") or ""),
        on_date=_business_date(payload),
        kind=str(payload.get("kind") or "courtesy"),
        actor=_actor(request),
        # The utility's default — the FALLBACK. `queue_document` reads the
        # account's own language from `account_id` and asks for it first (PO
        # option B, 2026-10-29), the same ladder `_form` offered wording on.
        language=seams.tenant_default_language(),
    )
    if outcome["refused"]:
        # ⚠ **A REFUSAL REACHES THE CLERK AS A REFUSAL.** Every other write in
        # `notifications_seam` reports one as an outcome row on a 200, because
        # there the message rides along with a move that must still stand. Here
        # the message IS the work, and a 200 saying *queued* over a message that
        # was never written is precisely what this screen exists to prevent.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=BR_REF_KIND,
            message_key="customers.account.communication.error.refused",
            detail=str(outcome.get("detail") or "the message could not be queued."),
        )
    return Response(
        {
            "message_id": outcome["message_id"],
            "channels": list(outcome["channels"]),
            #: `created=False` means this exact message was already queued — a
            #: second submit of the same compose. The screen says *already
            #: queued* rather than claiming a second message.
            "outcome": outcome["code"],
            "problems": list(outcome["problems"]),
        },
        status=201,
    )


urlpatterns = [
    path("accounts/<str:account_id>/communication", account_communication),
]
