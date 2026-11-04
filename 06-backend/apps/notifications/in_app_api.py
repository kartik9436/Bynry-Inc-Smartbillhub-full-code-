# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — the in-app inbox: the bell's badge, its list,
#           and marking a message read)   Screens: shell-chrome (the S48 topbar
#           bell and its popover)
# Rules:    BR-NOT-019 (in-app is a real channel with a real store) ·
#           BR-NOT-005 + A11 Addendum r2 §4 (QUEUE ONLY — no `send`, no
#           `test-send`, no route anywhere that transmits inside a request) ·
#           BR-SHL-007 (the bell: newest-first, unread badge capped at 9+) ·
#           BR-SHL-026 (bell events carry catalogued copy) · BR-IDN-009 /
#           BR-SHL-025 (server-enforced access) · CLAUDE.md rule 1
# Tests:    06-backend/tests/test_cr_009_in_app_channel.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           06-backend/openapi/schema.json · 07-frontend/src/api/endpoints.ts ·
#           07-frontend/src/components/ShellWithSession.tsx (the caller that
#           finally passes `bellItems`)
# ───────────────────────────────────────────────────────
"""The signed-in user's own inbox — three routes, and not one of them sends.

THIN by law (B8 / LAW 0): parse → call the service → serialize. No ORM, no
clock, no send.

╔══════════════════════════════════════════════════════════════════════════╗
║  BR-NOT-005 IS INTACT AND THIS FILE IS WHERE THAT IS EASIEST TO DOUBT.  ║
╚══════════════════════════════════════════════════════════════════════════╝
In-app is the first channel this platform can actually deliver on, so it is the
first place somebody could plausibly write `POST /notifications/send` and have
it work. **No such route exists here and none may.** A11 Addendum r2 §4 makes a
synchronous send endpoint a gate failure, and
`test_cr_009__no_send_route_is_minted_by_the_in_app_surface` asserts that
`…/send` and `…/test-send` both answer `Resolver404` on this surface, exactly as
the rules API already does for its own.

What actually delivers a message is the dispatcher draining the queue —
`manage.py dispatch_outbound`, or the cycle a scheduler runs. These three routes
only READ what was delivered and record that a person looked at it.

────────────────────────────────────────────────────────────────────────────
THE THREE ROUTES
────────────────────────────────────────────────────────────────────────────
    GET  /in-app-messages              this user's inbox, newest first, with
                                       the unread count the bell badges
    POST /in-app-messages/{id}/read    mark one read (opening it in the bell)
    POST /in-app-messages/read-all     mark every unread one read

────────────────────────────────────────────────────────────────────────────
WHY THERE IS NO `user` PARAMETER ON ANY OF THEM
────────────────────────────────────────────────────────────────────────────
An in-app message belongs to ONE person. RLS scopes these rows to a tenant and
cannot scope them to a user, so the per-user guarantee is that the service layer
derives the user from the SESSION and has no callable that accepts one from a
request (`apps/notifications/in_app.py`'s module docstring). These routes pass
`_actor(request)` and nothing else, so there is no query string, no body field
and no path segment that could ask for somebody else's mail.

**ANY signed-in role may read their own inbox**, and that is not a loosening of
BR-IDN-009. The permission matrix governs what a person may do to the TENANT'S
data; this is a person's own delivered mail, and a Billing Clerk who cannot read
their own bulk-run summary would be a Billing Clerk who cannot be told that the
run they started failed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import in_app
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The B12 §6a actor shape. `user` travels because the inbox IS the user's."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _refused(detail: str) -> errors.BizError:
    """A service refusal as the ONE catalog exception G9 allows.

    `InboxRefused` is deliberately not a catalog exception — `in_app.py` is
    called by the DISPATCHER as well as by these routes, and a catalog code
    carries an HTTP status — so the translation belongs here, the only layer
    that knows what HTTP is. The refusal's own sentence travels in
    `params.detail`. Same shape as `rules_api._refused`.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-NOT-019",
        message_key="notifications.inApp.refused",
        params={"detail": detail},
    )


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def in_app_messages(request: Any) -> Response:
    """`GET /in-app-messages` — the bell's badge and its popover, in one read.

    One request rather than two, because the badge and the list are drawn
    together and a count fetched separately from the list it counts is a count
    that can disagree with what is on screen.
    """
    require_tenant(request)
    actor = _actor(request)
    try:
        items = in_app.inbox(actor=actor)
        unread = in_app.unread_count(actor=actor)
    except in_app.InboxRefused as refusal:
        raise _refused(str(refusal)) from refusal
    return Response(
        {
            "results": [item.as_wire() for item in items],
            "count": len(items),
            "unread": unread,
            # Stated so the screen never implies the popover is the archive.
            "page_size": in_app.INBOX_PAGE_SIZE,
            # ⚠ The honest posture, carried as DATA beside the messages, the same
            # way `rules_api.RELEASE_POSTURE` is. In-app is the ONE channel that
            # delivers on this deployment; a reader of this response must not
            # conclude that email or SMS do (BR-NOT-013).
            "channel_note": (
                "in-app is delivered by this platform and needs no integration. Email, "
                "SMS and print still have no provider adapter (BR-NOT-013), so a message "
                "here does not mean the same message went out by any other channel."
            ),
        }
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def mark_in_app_message_read(request: Any, message_id: str) -> Response:
    """`POST /in-app-messages/{id}/read` — opening a message in the bell.

    Idempotent: a second click on an already-read message returns the same
    message rather than an error, because clicking twice is not a mistake worth
    reporting to anybody.
    """
    require_tenant(request)
    try:
        item = in_app.mark_read(actor=_actor(request), message_id=message_id)
    except in_app.InboxRefused as refusal:
        raise _refused(str(refusal)) from refusal
    except (ValueError, TypeError) as malformed:
        raise _refused(
            f"{message_id!r} is not a message id. Nothing was marked read."
        ) from malformed
    return Response({**item.as_wire(), "unread": in_app.unread_count(actor=_actor(request))})


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def mark_all_in_app_messages_read(request: Any) -> Response:
    """`POST /in-app-messages/read-all` — the popover's "Mark all read"."""
    require_tenant(request)
    actor = _actor(request)
    try:
        marked = in_app.mark_all_read(actor=actor)
    except in_app.InboxRefused as refusal:
        raise _refused(str(refusal)) from refusal
    # The COUNT travels: "Mark all read" on an empty inbox and on a full one
    # must not look the same in the response.
    return Response({"marked_read": marked, "unread": in_app.unread_count(actor=actor)})


urlpatterns = [
    path("in-app-messages", in_app_messages),
    path("in-app-messages/read-all", mark_all_in_app_messages_read),
    path("in-app-messages/<str:message_id>/read", mark_in_app_message_read),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 fourth ruling set · 04-docs/01-spec/11-api-contracts.md Addendum r2 §4 (no synchronous send endpoint) · apps/notifications/in_app.py (the service) · apps/notifications/rules_api.py, whose route and permission shape this follows)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — all three paths answered django.urls.exceptions.Resolver404 before config/urls.py named this module; the per-user scoping was proved by marking a second user's message read and reading the refusal. Transcripts in the lane report
# exceptions: (1) NO SEND ROUTE AND NO TEST-SEND ROUTE — asserted by name against this surface, because in-app is the first channel where such a route would actually have worked. (2) ANY signed-in role may read their OWN inbox: the permission matrix governs tenant data, and a clerk who cannot read the summary of the run they started is the failure BR-NOT-020 exists to prevent. (3) `read-all` is registered BEFORE `<str:message_id>/read` so the literal path is never swallowed by the parameterised one.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
