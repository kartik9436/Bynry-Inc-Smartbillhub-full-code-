# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 (EP-CWP-12) — help answers in the back office ·
#           US-CWP-072 — the read and the vote · US-CWP-073 — tips ·
#           US-CWP-074 — service centres. Screens: CWP-071 · CWP-072 ·
#           CWP-073 · CWP-074 · CWP-075 (staff) · CWP-011 · CWP-060 (the write)
# Rules:    07-endpoints.md §3 (*"Help, tips and centres stay in tenancy"*) ·
#           B2 §2 (the owning module owns its data; a cross-module write is
#           forbidden) · A4 `settings_lookups` (System Admin Full · Executive
#           View) · DEF-196 (any-role read / admin write is ONE class) ·
#           BR-CWP-022 (sixty a minute per address on the guest route — the
#           existing throttle, reused) · NFR-39 (the portal's per-tenant rate
#           and its in-flight budget on every guest door)
# Tests:    06-backend/tests/test_us_cwp_071_help.py ·
#           test_us_cwp_072_help_portal.py · test_us_cwp_073_tips.py ·
#           test_us_cwp_074_centres.py
# Impacts:  config/urls.py (two includes — the staff list and the guest one) ·
#           07-frontend/src/api/publishedContentEndpoints.ts
# ───────────────────────────────────────────────────────
"""The HTTP surface for help answers, tips and service centres.

THIN by law (B8 / LAW 0): resolve the tenant, hand the work to
`apps.tenancy.published_content`, answer with what it returns. **No ORM here
and no rule here.**

TWO URL LISTS IN ONE FILE, AND WHY
----------------------------------
`urlpatterns` is the **staff** back office — Settings → Configure → Customer
portal, and the Service centres card in Reference data. Every route is gated by
A4's `settings_lookups` cell through the one class that encodes it: an
Executive may read, a System Admin may write, a Billing Clerk is refused on
both.

`guest_urlpatterns` is **one route**, and it is here for a reason worth stating
rather than discovering:

    POST /portal/public/help/{slug}/feedback     a read, or a *did this help?* vote

⚠ **`help_answer_feedback` IS A TENANCY TABLE, SO ONLY TENANCY MAY WRITE IT.**
`03-field-map.md` §2 puts the published content in this module and B2 §2
forbids a cross-module write, so `apps/portal` could not write that row
wherever the endpoint was mounted — and `G81` enforces exactly that, file by
file, over the whole portal package. Mounting the route here is therefore not a
way around `BR-CWP-001`'s four write points; it is the only place the row can
legally be written from.

⚠ **AND `BR-CWP-001` IS NOT BENT BY IT.** The four kinds it names — a payment,
a service request, a meter reading, a preference on the account — are all rows
about a CUSTOMER'S ACCOUNT. This row is about a published paragraph: it carries
the answer, the language it was read in, the event and the day, and **no
customer, no account, no session and no address** (`BR-CWP-021`). It can change
nothing a customer owns, which is `BR-CWP-026` satisfied. The two documents
that disagreed about this — `BR-CWP-001`'s *"exactly four"* and `CP-34`'s *"the
portal's smallest write"* — are `DEF-CWP-3646`, and the reading taken is in the
decision log for 2026-09-04.

⚠ **IT WEARS THE PORTAL'S OWN GUARDS.** A guest door that skipped the per-tenant
rate and the in-flight budget would be the cheapest way to take every worker
the back office needs (`NFR-39`), so this route imports them from
`apps.portal.guards` — a middleware import, not data, and the one place this
module reaches into the portal's package.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.portal.guards import PortalTenantThrottle, portal_admission
from apps.tenancy import published_content
from apps.tenancy import published_content_models as content_models
from apps.tenancy.api import PublicOnboardingThrottle
from core import errors
from core.permissions import SettingsReadAnyWriteSystemAdmin
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a shape — id and name from the session
    user, role SERVER-attached by the identity layer, never client input.
    `name` is what `last_changed_by` shows a clerk (*"last changed 2 September
    by Sarah Miller"* on `CWP-072`)."""
    user = getattr(request, "user", None)
    full_name = getattr(user, "full_name", None) or getattr(user, "name", None)

    class _Actor:
        id = getattr(user, "id", None) or getattr(user, "pk", None)
        role = getattr(request, "tenant_role", None)
        name = full_name

    return _Actor()


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="settings.payload_not_object")
    return data


# ══ CWP-071 · CWP-072 — help answers ═══════════════════════════════════════


@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])  # A4 settings_lookups · DEF-196
def help_answers(request: Any) -> Response:
    """`CWP-071`'s list, and `+ New answer`.

    ⚠ The list holds **all three states** — published, draft and not-shown —
    because it is the one place they are all visible (`BR-CWP-094`).
    """
    tenant_id = require_tenant(request)
    if request.method == "POST":
        return Response(
            published_content.create_answer(_actor(request), tenant_id, _payload(request))
        )
    return Response({"answers": published_content.back_office_answers(tenant_id)})


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def help_answer(request: Any, slug: str) -> Response:
    """`CWP-072` — the editor: the question, *also show on*, and the language
    table where a missing translation is a **visible state**."""
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        return Response(
            published_content.update_answer(_actor(request), tenant_id, slug, _payload(request))
        )
    if request.method == "DELETE":
        published_content.delete_answer(_actor(request), tenant_id, slug)
        return Response(status=204)
    return Response(published_content.back_office_answer(tenant_id, slug))


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def help_answer_publish(request: Any, slug: str) -> Response:
    """⚠ **PUBLISHING TAKES EFFECT IMMEDIATELY — THERE IS NO APPROVAL STEP**
    (`US-CWP-071` TC-9), and `CWP-072` warns about it before this is called."""
    tenant_id = require_tenant(request)
    status = _payload(request).get("status", "published")
    return Response(
        published_content.publish_answer(_actor(request), tenant_id, slug, status=status)
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def help_answers_reorder(request: Any) -> Response:
    """*The order here is the order on the portal* (`US-CWP-071` TC-5)."""
    tenant_id = require_tenant(request)
    order = _payload(request).get("order") or []
    return Response(
        {"answers": published_content.reorder_answers(_actor(request), tenant_id, order)}
    )


# ══ CWP-073 — tips ═════════════════════════════════════════════════════════


@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def tips(request: Any) -> Response:
    """`CWP-073` — every tip, with **why** each one that is not showing is not
    showing (`US-CWP-073` TC-3: two independent reasons, both shown)."""
    tenant_id = require_tenant(request)
    if request.method == "POST":
        return Response(
            {"tips": published_content.create_tip(_actor(request), tenant_id, _payload(request))}
        )
    # ⚠ **THE SIX SCREENS AND THE GUIDANCE TRAVEL WITH THE LIST, AND THE REASON
    # IS THE FIRST PARAGRAPH OF CLAUDE.md.** The eleventh service exists in the
    # database, is served by the API, and does not appear on the sign-up screen
    # — because the front end types that list out by hand. `TIP_SCREENS` is a
    # closed set of exactly the same shape, and the editor's *Where it shows*
    # picker is exactly the screen that would fail silently. So the server sends
    # the set, the same way `service_centres` already sends `all_actions` and
    # `all_payment_methods` one route below.
    return Response(
        {
            "tips": published_content.back_office_tips(tenant_id),
            "all_screens": list(published_content.TIP_SCREENS),
            "word_guidance": content_models.TIP_WORD_GUIDANCE,
        }
    )


@api_view(["PUT", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def tip(request: Any, tip_id: str) -> Response:
    tenant_id = require_tenant(request)
    if request.method == "DELETE":
        return Response({"tips": published_content.delete_tip(_actor(request), tenant_id, tip_id)})
    return Response(
        {
            "tips": published_content.update_tip(
                _actor(request), tenant_id, tip_id, _payload(request)
            )
        }
    )


@api_view(["POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def tips_reorder(request: Any) -> Response:
    """*Top of the list wins where two match* (`BR-CWP-095`)."""
    tenant_id = require_tenant(request)
    order = _payload(request).get("order") or []
    return Response({"tips": published_content.reorder_tips(_actor(request), tenant_id, order)})


# ══ CWP-074 · CWP-075 — service centres ════════════════════════════════════


@api_view(["GET", "POST"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def service_centres(request: Any) -> Response:
    """`CWP-074`, a card in Reference data. ⚠ The list holds the HIDDEN rows
    too — hidden is a state, not a deletion (`BR-CWP-096`)."""
    tenant_id = require_tenant(request)
    if request.method == "POST":
        return Response(
            published_content.create_centre(_actor(request), tenant_id, _payload(request))
        )
    return Response(
        {
            "centres": published_content.back_office_centres(tenant_id),
            "all_actions": list(published_content.CENTRE_ACTIONS),
            "all_payment_methods": list(published_content.CENTRE_PAYMENT_METHODS),
        }
    )


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([SettingsReadAnyWriteSystemAdmin])
def service_centre(request: Any, slug: str) -> Response:
    """`CWP-075`. ⚠ DELETE is the danger tier on the screen and warns that a
    printed address may still be in circulation (`US-CWP-074` TC-9) — hiding is
    what a clerk should reach for, and the screen says so."""
    tenant_id = require_tenant(request)
    if request.method == "PUT":
        return Response(
            published_content.update_centre(_actor(request), tenant_id, slug, _payload(request))
        )
    if request.method == "DELETE":
        published_content.delete_centre(_actor(request), tenant_id, slug)
        return Response(status=204)
    return Response(published_content.back_office_centre(tenant_id, slug))


# ══ The one guest write — see the module docstring ═════════════════════════


@api_view(["POST"])
@authentication_classes([])  # a stale staff cookie must not 401 a visitor
@permission_classes([AllowAny])
@throttle_classes([PublicOnboardingThrottle, PortalTenantThrottle])  # per address AND per tenant
@portal_admission  # the connection budget (NFR-39, NFR-41)
def help_feedback(request: Any, slug: str) -> Response:
    """`POST /portal/public/help/{slug}/feedback` — a read, or a vote.

    ⚠ **TWO DISTINCT EVENTS** (`US-CWP-072` TC-4): opening the page sends
    `read`; pressing *No* sends `not_helpful`. They are separate rows with
    separate names, so the back office's *read this month* column counts reads
    and the vote is its own event — `1,204 → 1,207` after three opens, whatever
    anybody presses.

    ⚠ **NOBODY IS RECORDED** (`BR-CWP-021`). The row carries the answer, the
    language, the event and the day.
    """
    tenant_id = require_tenant(request)
    body = request.data if isinstance(request.data, dict) else {}
    return Response(
        published_content.record_feedback(
            tenant_id,
            slug,
            event=body.get("event", "read"),
            locale=body.get("locale"),
        )
    )


urlpatterns = [
    path("settings/portal/help", help_answers),
    path("settings/portal/help/reorder", help_answers_reorder),
    path("settings/portal/help/<str:slug>", help_answer),
    path("settings/portal/help/<str:slug>/publish", help_answer_publish),
    path("settings/portal/tips", tips),
    path("settings/portal/tips/reorder", tips_reorder),
    path("settings/portal/tips/<str:tip_id>", tip),
    path("settings/reference-data/service-centres", service_centres),
    path("settings/reference-data/service-centres/<str:slug>", service_centre),
]

#: Mounted beside `apps.portal.guest_api` — anonymous, throttled, budgeted.
guest_urlpatterns = [
    path("portal/public/help/<str:slug>/feedback", help_feedback),
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-071..074@d6d31c46 (EP-CWP-12 stories + BR-CWP-093..096 snapshot)
# generated: 2026-09-04 by the CR-068 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔(SettingsCustomerPortalTab.tsx · SettingsReferenceData.tsx · portal/guest/*) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_cwp_07*.py · openapi export re-run (ten new paths) · G9 error envelope · G81 (this file is NOT under apps/portal, and that is the point)
# exceptions: the feedback route is a guest route served by tenancy — stated in the module docstring, DEF-CWP-3646 and the decision log
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
