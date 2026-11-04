# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (template lifecycle, append-only versions, publish
#           rights — the CHOOSER half, which is all R2 has) ·
#           US-BIL-022 (the pin: what the tenant chooses is what future bills
#           pin, and every issued bill keeps its own)
#           Screens: S8 (Settings → Bill layout)
# Rules:    BR-BIL-025 (assignment defaults by consumer category, and the
#           category-less template is the tenant's FALLBACK — exactly one) ·
#           BR-BIL-026 (an edit is a NEW version; ONE published per template;
#           publishing affects only FUTURE bills) · BR-BIL-027 (System Admin
#           publishes; a version pinned by any bill can never be deleted) ·
#           BR-BIL-021 (bill messages and footer are the tenant's copy) ·
#           BR-TEN-043 (event time is an argument) · BR-SHL-025 / BR-IDN-009
#           (server-enforced RBAC) · CLAUDE.md rule 7 (audit)
# Tests:    06-backend/tests/test_us_bil_surface_apis.py
# Impacts:  config/urls.py (the include) · apps/billing/documents.LAYOUT_SPECS
#           (the library this serves) · apps/billing/templates_service.
#           choose_layout (the one write) · 07-frontend BillLayoutTab (S8)
# ───────────────────────────────────────────────────────
"""`/bill-templates` — pick the page your customers receive.

THIN by law: the read composes `templates_service` + `documents`, the one write
is `templates_service.choose_layout`, no ORM here, every refusal a catalog
exception.

════════════════════════════════════════════════════════════════════════════
WHAT THIS IS INSTEAD OF, AND WHY — PO RULING 2026-08-16
════════════════════════════════════════════════════════════════════════════
A1 reserves S91–S96 for a bill-layout DESIGNER: a canvas, blocks, per-block
options, a preview, a test print. **The PO cut all six from R2**, verbatim:

    *"why cant we give 5 differnt tempaltes to start with and ask user to
     choose anyone; we will ahve 1 default tempalte allways"*

So this file serves a LIST and a CHOICE, and that is the whole surface. The
consequences are worth stating because they are what makes the ruling a good
trade rather than a reduction:

  · **No HTML/CSS rendering engine enters the deployment image.** A designer
    needs one (WeasyPrint's Pango/HarfBuzz, or a headless browser); a chooser
    over five layouts the platform wrote does not. `documents.py` renders both
    serialisations with the standard library and nothing else.
  · **Nothing a tenant types can reach a customer's page as markup.**
    `layout_or_refuse` rejects any key the platform does not publish, so no page
    the platform did not write ever has to be rendered.
  · **There is always exactly one default.** Not by convention: the tenant's
    fallback template is seeded at provisioning (DEF-123, and G26's register
    holds it), and `uq_bill_template_one_published` allows one live version of
    it. A tenant cannot reach issue with nothing to render from.

════════════════════════════════════════════════════════════════════════════
WHY CHOOSING PUBLISHES A VERSION RATHER THAN SETTING A COLUMN
════════════════════════════════════════════════════════════════════════════
The obvious implementation is `UPDATE bill_templates SET layout_key = …`. It is
wrong, and the reason is BR-BIL-026: a bill pins template + version at issue and
a reprint renders THAT version forever. If the layout hung off a mutable column,
changing it in August would silently repaper every July bill the day somebody
reprinted one — history rewritten without a single UPDATE to an invoice.

So a choice is a new VERSION: the incumbent is archived, the successor is
published, both are audited with a date and a person, and every bill already
issued keeps rendering from its own pin. *"Why does August's bill look different
from July's?"* is then a query, not an archaeology exercise.

════════════════════════════════════════════════════════════════════════════
THE TWO ROUTES, AND THE FOUR THAT ARE DELIBERATELY NOT HERE
════════════════════════════════════════════════════════════════════════════
    GET  /bill-templates          the library, the live choice, the pin counts
    POST /bill-templates/layout   choose one — System Admin (BR-BIL-027)

    NOT here, and NOT stubbed:
      · creating a SECOND template, and assigning templates per consumer
        category. `create_template` is built and unreachable ON PURPOSE: a
        second category-less template is the two-fallback collision
        `TEMPLATES_UNAVAILABLE` reports, and closing it is a unique index —
        a migration on a 🔒 path, which belongs with the story that needs it.
      · archiving and deleting a version. `archive` and `delete_version` are
        built and audit-locked; with one template and one live version there is
        nothing a human could archive without leaving the tenant unable to bill.
      · a designer of any kind (S91–S96, CUT by the ruling above).

`urlpatterns` is exported for inclusion by config/urls.py.
"""

from datetime import date
from types import SimpleNamespace
from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import documents, templates_service
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import VERSION_PUBLISHED
from core import errors
from core.permissions import AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant


def _actor(request: Any) -> Any:
    """The acting user in the B12 §6a service shape — id from the session user,
    ROLE SERVER-ATTACHED by the identity layer (BE-04) and never client input.

    `templates_service.publish` enforces BR-BIL-027 on `actor.role`, so handing
    it the bare Django `User` would hand it an object with no role — and
    `publish` refuses an actor whose role it cannot resolve, which is the right
    default and the wrong outcome. The same shim `apps/tenancy/api.py` uses, for
    the same reason.
    """
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="billing.payload_not_object")
    return data


def _date_field(payload: dict[str, Any], name: str) -> date:
    """The business date the version is published ON — the caller's, not a clock
    (BR-TEN-043, gate G6). It is stamped on the version and read by nobody as a
    default, so a request from another timezone must not move it."""
    raw = payload.get(name)
    if not isinstance(raw, str) or not raw:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.ops.date_required",
            field_errors=[{"field": name, "code": errors.VAL_REQUIRED}],
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="billing.ops.date_format",
            field_errors=[{"field": name, "code": errors.VAL_FORMAT}],
        ) from bad


def _refusal(broken: BillingRuleError) -> errors.BizError:
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=getattr(broken, "br_ref", None) or "BR-BIL-026",
        message_key="billing.templates.refused",
        params={"detail": str(broken)},
    )


def _library_dict() -> dict[str, Any]:
    """The chooser's whole read: the library, the live choice, the history.

    `pinned_bills` per version is BR-BIL-027's audit-lock number, and it is
    served because it is what makes the version list mean something to a human:
    *"v1 · Standard · 1,847 bills printed on it"* says why that version can
    never be deleted, where a bare status does not.

    A layout the platform lists but cannot RENDER is served with
    `renders: false`, not hidden. Hiding it would leave a tenant unable to
    explain why the list is shorter than the documentation says; the screen
    disables it with the reason instead.
    """
    template = templates_service.tenant_fallback_template()
    live = None if template is None else templates_service.published_version(template)
    versions: list[dict[str, Any]] = []
    if template is not None:
        from apps.billing.template_models import BillTemplateVersion

        rows = BillTemplateVersion.objects.filter(
            tenant_id=template.tenant_id, template=template
        ).order_by("-version_no")
        versions = [
            {
                "id": str(row.pk),
                "version_no": row.version_no,
                "status": row.status,
                "layout_key": row.layout_key,
                "published_on": None if row.published_on is None else row.published_on.isoformat(),
                "pinned_bills": templates_service.pin_count(row),
                "options": dict(row.options or {}),
            }
            for row in rows
        ]
    # DEF-BIL-4458 — CAN a layout be previewed at all, asked ONCE for the whole
    # library rather than per card. The answer is the same for all five (it
    # turns on whether this tenant has ever issued a bill), and a screen that
    # asked five times would draw five frames that each fail on their own.
    from apps.billing import layout_preview_api

    sample = layout_preview_api.sample_invoice()
    preview_blocked = (
        None
        if sample is not None
        else "This utility has not issued a bill yet, so there is no real document to draw "
        "these layouts on. Run a bill run and each one can be seen on a page of your own."
    )
    return {
        # THE TENANT'S TEMPLATE. Null when provisioning's seeder has not run —
        # which is a repairable state, not an empty list, and the screen must be
        # able to tell the two apart (an empty library would be a build defect).
        "template": (
            None
            if template is None
            else {
                "id": str(template.pk),
                "name": template.name,
                "template_type": template.template_type,
                # BR-BIL-025: no category IS the fallback. Served explicitly so
                # a reader does not have to know that null means "the default".
                "is_fallback": template.category is None,
            }
        ),
        "current": (
            None
            if live is None
            else {
                "version_no": live.version_no,
                "layout_key": live.layout_key,
                "published_on": None if live.published_on is None else live.published_on.isoformat(),
                "options": dict(live.options or {}),
            }
        ),
        "versions": versions,
        "layouts": [
            {
                "key": layout.key,
                "label": layout.label,
                "summary": layout.summary,
                "template_type": layout.template_type,
                "renders": layout.renders,
                "is_current": live is not None and live.layout_key == layout.key,
                "is_platform_default": layout.key == documents.DEFAULT_LAYOUT_KEY,
                # DEF-BIL-4458 — WHERE TO SEE IT. A path, not a rendered page:
                # the screen frames it and the browser's own viewer carries
                # print and save. Null when the layout has no renderer, because
                # a frame pointed at a route that will refuse is worse than a
                # named absence (BR-SHL-020) — the card says why instead.
                "preview_url": (
                    f"/bill-templates/layouts/{layout.key}/preview.pdf"
                    if layout.renders
                    else None
                ),
                # …and the ONE reason none of them can be drawn, repeated on
                # each so a caller reading one layout does not have to know the
                # library holds it too.
                "preview_unavailable": preview_blocked,
            }
            for layout in templates_service.PLATFORM_LAYOUTS
        ],
        "publish_role": templates_service.PUBLISH_ROLE,
        "published_status": VERSION_PUBLISHED,
        "unavailable": [dict(entry) for entry in templates_service.TEMPLATES_UNAVAILABLE],
    }


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def bill_templates(request: Any) -> Response:
    """S8's Bill layout tab — what we print on, and what else we could print on."""
    require_tenant(request)
    return Response(_library_dict())


@api_view(["POST"])
@permission_classes([SystemAdminOnly])  # BR-BIL-027 — publishing is the narrow right
def choose_bill_layout(request: Any) -> Response:
    """Choose the tenant's bill layout. **Future bills only** (BR-BIL-026).

    `SystemAdminOnly` at the decorator AND `publish`'s own role check behind it,
    and the doubling is deliberate: BR-BIL-027's TC-2 asks for *"absent/disabled-
    with-reason **and** server-rejected"*, and the service check is what holds
    when the next caller is a script rather than this screen.

    A repeat of the live choice answers 200 with `changed: false` rather than
    minting an identical version — see `choose_layout`. It is not an error: a
    clerk clicking the layout they are already on has asked for the state they
    already have.
    """
    require_tenant(request)
    payload = _payload(request)
    layout_key = payload.get("layout_key")
    if not isinstance(layout_key, str) or not layout_key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="billing.templates.layout_required",
            field_errors=[{"field": "layout_key", "code": errors.VAL_REQUIRED}],
        )
    options = payload.get("options")
    try:
        outcome = templates_service.choose_layout(
            layout_key=layout_key,
            options=options if isinstance(options, dict) else None,
            actor=_actor(request),
            on_date=_date_field(payload, "on_date"),
        )
    except BillingRuleError as refusal:
        raise _refusal(refusal) from refusal
    return Response({**outcome, **_library_dict()})


urlpatterns = [
    # ORDER IS LOAD-BEARING and was checked rather than assumed: `layout` is
    # all-static and there is no `<str:…>` sibling under `bill-templates` at
    # all — deliberately, because there is no per-template route to collide
    # with while a tenant has exactly one template.
    path("bill-templates", bill_templates),
    path("bill-templates/layout", choose_bill_layout),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-021@2b52def (the same four sources apps/billing/templates_service.py was authored from — 04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md · 07-billing/02-business-rules.md · 08-qa/01-e2e/journeys/J22-template-life.md · 10-notifications/06-epics/EP-NOT-02-templates-rendering.md — plus the PO ruling of 2026-08-16 recorded in 12-governance/02-decision-log.md, which CUT S91–S96 and replaced the designer with this chooser)
# generated: 2026-08-16 by story-coder (billing SURFACE lane — the S8 tab templates_service.py recorded as having no endpoint)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_bil_surface_apis.py could not resolve `/bill-templates` through the root URLconf before this file was included, and the five layouts were shown to render one bill into five DIFFERENT documents only after documents.LAYOUT_SPECS landed (the pre-change run had all five identical). Both quoted verbatim in the lane report. pytest✔ · run_gates✔ · golden 33/33✔
# exceptions: E3 S91–S96 (the designer) are CUT by PO ruling 2026-08-16 and nothing here stands in for them — no canvas, no blocks, no per-block options · E3 choosing PUBLISHES A NEW VERSION rather than setting a column, so no already-issued bill can be repapered (BR-BIL-026) · E3 no route creates a second template or assigns per consumer category: a second category-less template is the two-fallback collision TEMPLATES_UNAVAILABLE reports and closing it is a migration on a 🔒 path · E3 a layout the platform lists but cannot render is served `renders: false` rather than hidden, so the screen disables it WITH the reason · E3 `SystemAdminOnly` at the decorator AND `publish`'s server-side role check behind it — BR-BIL-027 TC-2 asks for both
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
