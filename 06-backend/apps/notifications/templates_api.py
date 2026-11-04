# ── Trace ──────────────────────────────────────────────
# Story:    CR-007 (SET-09 template catalog · SET-10 template detail, preview,
#           variants, editing and versioning)   Screens: SET-09 · SET-10
# Rules:    BR-NOT-001 (per-consumer-category variants + a mandatory `default`
#           fallback) · BR-NOT-006 (type × category × language; missing variant
#           → tenant-default fallback, never a blank) · BR-NOT-014 (the
#           disconnect notice has ONE SLOT PER TIER — three, not one) ·
#           BR-NOT-015 (the rights footer is a platform default a System Admin
#           may override; its SENTENCES are not ours to invent — OQ-250) ·
#           BR-BIL-026 (an edit is a NEW version; publishing affects only FUTURE
#           renders) · BR-BIL-027 (System Admin publishes; a pinned version can
#           never be deleted) · BR-NOT-005 (queue only — NO send endpoint may
#           exist anywhere in this module) · BR-SHL-011 (list grammar
#           q/sort/dir/page/per/f.*) · BR-SHL-025 (a forbidden control renders
#           DISABLED WITH ITS REASON, never hidden) · BR-IDN-009 (server-enforced
#           RBAC) · BR-TEN-033 (templates are the notifications module's;
#           tenancy stores no template content) · BR-TEN-043 (a business date is
#           an INPUT, never a clock) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 7 (every action audited)
# Tests:    06-backend/tests/test_cr_007_template_catalog.py
# Impacts:  config/urls.py inclusion (`urlpatterns` exported here) ·
#           07-frontend/src/features/notifications/TemplateCatalog.tsx and
#           TemplateDetail.tsx (SET-09 / SET-10, which call exactly these paths)
# ───────────────────────────────────────────────────────
"""SET-09 · SET-10 — the catalog of everything this platform sends or prints.

THIN by law (B8 / LAW 0): parse → call a service or a selector → serialize.
No ORM writes, no status transitions, no clock and no send.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE ENGINE WAS ALREADY HERE. THIS IS THE DOOR.                         ║
╚══════════════════════════════════════════════════════════════════════════╝
Measured before a line was written, because three CRs in a row have shown that
gap lists built from the design overstate. `apps/notifications/` already held
`template_models.py` (the registry + append-only version rows, with the
publish-once and effective-dated partial indexes), `template_service.py`
(register → save_draft → publish → archive → delete, `resolve` with BR-BIL-025's
five-step fallback, `load_pinned`, `pin_count`), `catalogs.py` (the per-class
merge-variable whitelist), `rendering.py` (`validate_body` + `render`) and
`seed_templates.py`. **All of it reachable only from `GET /notification-
templates`, which is a READ**, whose own trailer says so: *"THE TEMPLATE READ IS
A READ. `template_service` holds a complete draft→publish→archive lifecycle and
none of it is mounted."*

So CR-007's build is: the CATEGORY axis, BR-NOT-014's three disconnect slots,
CR-007's fourteen unspecified classes, and **the seven write routes that make
the shipped lifecycle reachable by a human**. The lifecycle itself is unchanged.

────────────────────────────────────────────────────────────────────────────
THE ROUTES
────────────────────────────────────────────────────────────────────────────
    GET  /template-catalog                    SET-09 — the table, with search,
                                              category chips, sort, pagination
    GET  /template-catalog/{code}             SET-10 — one template: its
                                              variants, versions, merge fields
                                              and a rendered preview
    POST /template-catalog/{code}/variants    add a variant (category+language)
    POST /template-catalog/{code}/preview     render a CANDIDATE body with
                                              sample data — no write
    POST /template-catalog/{code}/draft       save an edit as a NEW version
    POST /template-catalog/{code}/publish     publish a draft (auto-archives
                                              the previous published one)
    POST /template-catalog/{code}/deactivate  archive a variant's live version
    POST /template-catalog/{code}/restore     restore an old version as a new
                                              DRAFT — never by rewriting history

**THERE IS NO SEND ROUTE AND THERE MUST NEVER BE ONE.** A11 Addendum r2 §4:
*"no synchronous send endpoint anywhere (queue only, BR-NOT-005)"*. CR-007 asks
for *"Send test to me"* and it is NOT built — see the next section.

────────────────────────────────────────────────────────────────────────────
PERMISSIONS: SYSTEM ADMIN ONLY, GATED THE WAY `/lookups/*` IS
────────────────────────────────────────────────────────────────────────────
PO ruling 2026-08-16 covering CR-005, CR-006 and CR-007 at once, verbatim:
*"all settingsa re Admin only I believ; follow same rule that we folowed for
settings related permission"*, translated in the register as **every Settings
surface these CRs add is SYSTEM ADMIN ONLY, gated exactly as the shipped
Settings surfaces already are** — `SystemAdminOnly`, the way `/lookups/*` and
Users & roles are gated (BR-IDN-009).

⚠ **THAT IS NARROWER THAN THE SERVICE'S OWN GATE, ON PURPOSE.** BR-BIL-027 lets
a Billing Clerk DRAFT (`@require_role(SYSTEM_ADMIN, BILLING_CLERK)` on
`save_draft`), and that rule is untouched: a clerk drafting through a future
non-Settings surface is still lawful. What the PO ruled is that **this Settings
screen** is Admin-only, so the endpoint is the narrower of the two. Both gates
run; the narrower one refuses first. A Billing Clerk and an Executive can READ
every route above and change nothing, and the read carries `can_edit: false`
with `cannot_edit_reason` so the screen renders the control DISABLED WITH ITS
REASON rather than hiding it (BR-SHL-025).

────────────────────────────────────────────────────────────────────────────
"SEND TEST TO ME" IS BUILT — CR-048 B7, 2026-08-30
────────────────────────────────────────────────────────────────────────────
⚠ **THIS SECTION SAID IT WAS NOT BUILT, AND THE REASON IT GAVE HAD EXPIRED
(DEF-2503).** It read *"'SEND TEST TO ME' IS NOT BUILT, AND THE REASON IS A
RULING NOT A GAP"*, and quoted the PO's *"no email yet"* of 2026-08-16 and the
release posture of the same day. All of that was true when it was written. It
stopped being true when CR-009 shipped `POST /notification-rules/{event}/
queue-test` — a real queue row, addressed to the signed-in user — and nobody
came back to this file, because a hardcoded `False` beside a hardcoded sentence
is not something any check re-measures.

**WHAT THE BUTTON DOES NOW, AND WHAT IT STILL DOES NOT.** `POST
/template-catalog/{code}/queue-test` writes ONE real row on `outbound_messages`
through `services.queue_document` — the one write path — pinned to the version a
real message would resolve, addressed to the person who pressed it and to nobody
else. **It sends nothing.** BR-NOT-005 and A11 r2 §4 still make a synchronous
send endpoint a gate failure, and the response says `will_be_delivered` — the
dispatcher's own verdict — with `provider_seam`'s reason and the channel's line
from the Channel status card (`channel_line`) attached, because *"queued: true"*
alone reads, to the person who just clicked, as *"a test email is on its way"*
(BR-NOT-013). ⚠ AMENDED 2026-10-22 (`DEF-NOT-10537`): this read *"CR-048's scope
still excludes every provider adapter … `will_be_delivered: false`"* — false
once email began to send through the utility's Custom SMTP connector.

`can_test_send` is now DERIVED per template rather than hardcoded, by
`rule_service.template_test_offer`, which runs the same checks in the same order
as the endpoint — so a control drawn enabled can never be refused by the route
it opens (BR-SHL-025). It is FALSE, with its own sentence, for a PRINT class
(this platform holds no postal address for a user — there is no way to post a
test letter to yourself), for a class with no published wording, and for anybody
who is not a System Admin.

**"Download sample PDF" is refused for a DIFFERENT reason and the two are
spelled differently**, because they have different fixes. There is no page
renderer for a notifications class: `apps/billing/documents.py` writes PDF bytes
and it writes BILLS, from billing's own `LAYOUT_SPECS`; `apps/notifications/
rendering.py` produces TEXT and OQ-149 closed with no page-render library in the
image. A printable notice therefore renders and stores its TEXT body
(`rendering.py` exception 2). `can_download_pdf` is `false` with that sentence.

────────────────────────────────────────────────────────────────────────────
WHAT "DEACTIVATE A VARIANT" IS, MECHANICALLY
────────────────────────────────────────────────────────────────────────────
CR-007: *"a variant in use by a notification rule can't be deleted — deactivate
only"*. There is no `active` column on `notification_templates` and this lane
did not add one, because the mechanism already exists and adding a second way to
say it is the drift hard-won law 1 warns about: **a variant is live exactly when
it has a PUBLISHED version**, so deactivating one is `template_service.archive`
on that version. Resolution then falls through BR-NOT-006's ladder to the
`(default, default)` variant — *"never a blank"* — which is the ratified
behaviour and not a side effect.

The response to a deactivate names the CONSUMERS: `pin_count` is how many queue
rows already name that exact version, and those rows keep it forever (rule 4 —
a published body is evidence of what a customer was sent). Deletion is refused
by `template_service.delete_version` for anything that is not an unpinned draft,
and that refusal is quoted to the screen rather than re-worded here.

────────────────────────────────────────────────────────────────────────────
RESTORE CREATES A NEW DRAFT. IT NEVER RE-OPENS AN OLD ROW
────────────────────────────────────────────────────────────────────────────
CR-007: *"version history list with restore; audit-logged"*. Migration 0006's
trigger freezes a non-draft version's `body`, `subject`, `version` and
`effective_from` the instant it leaves draft, and rule 4 is why. So restore
reads v2's body and calls `save_draft`, producing **v4 whose body is v2's** —
the history stays append-only, v2 is untouched, and every document pinned to v2
still renders exactly what it rendered. The audit row records which version the
body came from, because "v4 was typed" and "v4 is v2 restored" are different
facts about a customer-facing document.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from django.db import transaction
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.notifications import catalogs, rendering, seed_templates, template_preview
from apps.notifications import template_changes, template_list
from apps.notifications import template_models as tm
from apps.notifications import template_service, template_variants, unified_templates
# CR-048 B7 — the send test itself. It lives beside the notification-rules one
# so that "where does a test go" and "will it be delivered" have exactly one
# implementation between the two screens that offer the button.
from apps.notifications import rule_service, settings_api
from core import errors, pagination
from core import tenancy as core_tenancy
from core.permissions import AnyTenantRole, SystemAdminOnly
from core.tenancy import require_tenant

#: PO ruling 2026-08-16 (CR-005/006/007), served as DATA so the screen states
#: it rather than a lane remembering it.
READ_ONLY_REASON = (
    "Templates are System Admin only. A Billing Clerk or an Executive can read every "
    "template, every variant, every version and the preview, and can change none of "
    "them — the wording of a disconnect notice is not a clerk's to edit (PO ruling "
    '2026-08-16: "all settingsa re Admin only I believ; follow same rule that we '
    'folowed for settings related permission").'
)

#: ⚠ **`NO_TEST_SEND_REASON` WAS HERE AND IS GONE (CR-048 B7, DEF-2503).** It
#: read *"No test send in this release, on any channel. There is no dispatcher
#: and no provider integration … the PO declined the resend-invite action
#: earlier the same day with 'no email yet' …"* — accurate on 2026-08-17 and
#: false from the day CR-009 shipped a working test on the notification-rules
#: screen. A refusal frozen into a constant is a claim nothing re-measures, and
#: this one was drawn on a live utility's screen for thirteen days. The sentence
#: is now DERIVED per template by `rule_service.template_test_offer`, from the
#: same checks the endpoint runs, so the two cannot disagree.
#:
#: The sample PDF is genuinely still not built and keeps its own reason, because
#: the two have different fixes and always did.
#:
#: ⚠ **DEF-2479 — THIS SENTENCE DREW A PYTHON MODULE PATH AND AN OPEN-QUESTION
#: ID ON A WATER UTILITY'S SCREEN**, which is the exact fault DEF-335 fixed on
#: `set_default_reason` and `language_selection_reason` — its two neighbours on
#: this same payload — and this third field was baselined in
#: `g28_served_dict_baseline.txt` instead of being rewritten with them. The old
#: wording, verbatim: *"No sample PDF for this class. The platform's page writer
#: is billing's (apps/billing/documents.py) and it writes BILLS from billing's
#: own layouts; OQ-149 closed with no page-render library in the deployment
#: image, so a printable NOTICE renders and stores its TEXT body. The preview
#: shows exactly that text."*
#:
#: THE PROVENANCE, KEPT HERE WHERE SUPPORT AND ENGINEERS REACH IT AND A CLERK
#: NEVER DOES: the platform's only page writer is `apps/billing/documents.py`
#: and it writes BILLS from billing's own layouts; OQ-149 closed with no
#: page-render library in the deployment image, so a printable NOTICE renders
#: and stores its TEXT body, and the preview pane shows exactly that text. The
#: honesty is unchanged — there is no PDF and the sentence still says so — and
#: only the provenance moved (G28's own rule: *"keep the honesty, drop the
#: provenance"*).
NO_PDF_REASON = "No sample PDF for this class — the preview shows the text body."

#: The three or four words the SCREEN draws, beside a control that cannot be
#: pressed. The sentence above is the control's tooltip; this is what a person
#: reads without hovering. Served rather than worded by the client for the
#: reason every other refusal on this screen is served — a screen that worded it
#: itself would drift from the ruling the moment either changed.
NO_PDF_LABEL = "No sample PDF"

#: BR-SHL-011 vocabulary for SET-09. Declared here so an undeclared `f.*` is
#: IGNORED rather than refused — and so nobody can filter on a column the
#: screen does not draw.
CATALOG_SORTS: tuple[str, ...] = ("name", "category", "kind", "variants", "edited")
#: CR-199-BRC10 (DEF-NOT-10672) adds the drawing's channel chips and its
#: Language and Status filters — `template_list` holds what each value means.
CATALOG_FILTERS: tuple[str, ...] = (
    "category", "kind", "has_body", "channel", "language", "status",
)
DEFAULT_CATALOG_SORT = "category"

#: CR-007's column list, verbatim: *"Template name | Category | Kind (delivery
#: format) | Variants (count) | Used by (which system event/flow consumes it) |
#: Last edited (date · person) | Actions"*. Served so the column selector is
#: driven by the server's own answer (IS-5 / BR-SHL-027) rather than by a list
#: the client keeps in step by hand.
CATALOG_COLUMNS: tuple[dict[str, Any], ...] = (
    {"key": "name", "always": True},
    {"key": "category", "always": False},
    {"key": "kind", "always": False},
    {"key": "variants", "always": False},
    {"key": "used_by", "always": False},
    {"key": "edited", "always": False},
)


def _actor(request: Any) -> Any:
    """The B12 §6a actor shape — id from the session user, ROLE server-attached
    by the identity layer (BE-04) and never client input."""
    user = getattr(request, "user", None)
    return SimpleNamespace(
        id=getattr(user, "id", None) or getattr(user, "pk", None),
        role=getattr(request, "tenant_role", None),
        user=user,
    )


def _can_edit(request: Any) -> bool:
    return getattr(request, "tenant_role", None) == "system_admin"


def _variants_of(code: str) -> Any:
    """This tenant's variant rows for one class. **Explicitly tenant-scoped.**

    ⚠ THIS FUNCTION EXISTS BECAUSE THE FIRST VERSION OF THIS FILE DID NOT HAVE
    IT (DEF-191). Every queryset here read `NotificationTemplate.objects.filter(
    code=code)` and leaned on RLS to do the scoping — and
    `test_cr_007__another_tenants_variant_is_not_visible_here` went RED on
    exactly that: a variant registered on Lonestar appeared in the variant
    switcher of Brazos Bend's own template detail screen (*"assert 'fr-CA' not
    in {'default', 'fr-CA'}"*).

    CLAUDE.md hard rule 1 has two halves — *"never touch a tenant table without
    `app.tenant_id` set"* AND *"no cross-tenant queryset"* — and RLS answers only
    the first. `template_service.published_versions` and every selector in this
    module filter `tenant_id=` explicitly for the same reason: the policy is the
    floor, not the query.
    """
    return tm.NotificationTemplate.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), code=code
    )


def _versions_of(variant: tm.NotificationTemplate) -> Any:
    """One variant's version rows, tenant-scoped for the same reason."""
    return tm.NotificationTemplateVersion.objects.filter(
        tenant_id=variant.tenant_id, template=variant
    ).select_related("template")


def _payload(request: Any) -> dict[str, Any]:
    data = request.data
    if not isinstance(data, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="notifications.payload_not_object"
        )
    return data


def _refused(detail: str, br_ref: str = "BR-NOT-006") -> errors.BizError:
    """A service-layer refusal as the ONE catalog exception G9 allows.

    `TemplateRefused` and `RenderRefused` are deliberately not catalog
    exceptions — the services are called by provisioning and by jobs as well as
    by requests, and a catalog code carries an HTTP status — so the translation
    belongs here, the only layer that knows what HTTP is. **The refusal's own
    sentence travels verbatim in `params.detail`**, and re-wording it here would
    give support a second, weaker version of the same diagnostic.

    ⚠ `params.detail` IS NOT RENDERED (BR-SHL-020 r2, PO ruling 2026-08-19:
    *"server detail text should not reach customer screens"*). It is kept because
    it is the DIAGNOSTIC: it reaches the BR-AUD-018 attempt row and the server log,
    where support can still read it. What the user sees is the catalogue entry for
    `message_key`, and nothing else — see DEF-322.
    """
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref=br_ref,
        message_key="notifications.templates.refused",
        params={"detail": detail},
    )


def _class_or_refuse(code: str) -> catalogs.TemplateListing:
    """The listing, or a refusal naming which of three absences it is.

    Three different facts, spelled differently because each has a different fix:
    billing's three classes have another home (B2 r10 #4), the superseded single
    `disconnect_notice` was replaced by BR-NOT-014's three, and an unknown code
    is a typo or an expectation of tenant-created classes (OQ-253).

    A 422 with the sentence rather than a bare 404: `errors.NotFoundError`
    carries no message BY DESIGN — its bodies must stay byte-identical so a
    cross-tenant probe cannot tell absent from forbidden (HR-1) — and none of
    these three absences is about a tenant row. Telling a System Admin that the
    bill template lives one tab over is worth more than the status code.
    """
    listing = catalogs.listing_for(code)
    if listing is not None:
        return listing
    if code in template_service.BILLING_OWNED_CLASSES:
        raise _refused(
            f"{code!r} is a BILL template. Bills and statements pin billing's own registry "
            "(`bill_templates`, B2 r10 #4) and are chosen on Settings → Configure → "
            "Templates → Bill layout, not here. One document, one home.",
            "BR-TEN-033",
        )
    superseded = catalogs.superseded_reason(code)
    if superseded is not None:
        raise _refused(superseded, "BR-NOT-014")
    raise _refused(
        f"{code!r} is not a template class this platform knows. The catalog lists "
        f"{len(catalogs.listable_codes())} classes; a class is platform vocabulary and is "
        "not tenant-creatable (OQ-253).",
        "BR-NOT-006",
    )


# ══════════════════════════════════════════════════════════════════════════
# SET-09 · THE CATALOG
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def template_catalog(request: Any) -> Response:
    """`GET /template-catalog` — every document and message this platform sends.

    CR-007's own statement of purpose is drawn on the screen and is worth
    repeating where the data is produced: *"Notifications decide WHEN, Templates
    define WHAT."* Nothing on this route schedules, triggers or sends anything.

    BR-SHL-011 throughout: `q` searches name, category and used-by;
    `f.category` takes the chips; `sort`/`dir`/`page`/`per` are the standard
    grammar and an unknown value FALLS BACK rather than erroring.
    """
    require_tenant(request)
    params = pagination.parse_list_params(
        request.query_params,
        allowed_sorts=CATALOG_SORTS,
        default_sort=DEFAULT_CATALOG_SORT,
        allowed_filters=CATALOG_FILTERS,
    )
    # PO ruling 2026-09-07 — the state is DERIVED FROM ACTUAL USAGE, and the
    # tenant's half of that is one query for the whole list.
    rule_usage = rule_service.template_usage()
    # CR-199-BRC10 (DEF-NOT-10672) — the tenant's variant and version facts in
    # three grouped statements for the whole list, never three per row; and
    # the switched-on languages from their ONE definition (A4 B).
    facts = template_list.tenant_facts()
    offered = template_variants.offered_languages()
    rows = [
        _catalog_row(code, rule_usage, facts[code], offered)
        for code in catalogs.listable_codes()
    ]

    needle = params.q.lower()
    if needle:
        rows = [
            row
            for row in rows
            if needle in row["name"].lower()
            or needle in row["category"].lower()
            or needle in row["used_by"].lower()
            or needle in row["code"].lower()
        ]
    category = params.filters.get("category")
    if category in catalogs.CR_CATEGORIES:
        rows = [row for row in rows if row["category"] == category]
    kind = params.filters.get("kind")
    if kind:
        rows = [row for row in rows if row["kind"].lower() == kind.lower()]
    has_body = params.filters.get("has_body")
    if has_body in ("true", "false"):
        want = has_body == "true"
        rows = [row for row in rows if (row["body_unavailable"] is None) is want]

    # The drawing's chips and two filters. Each facet is counted over what the
    # OTHER filters leave, so a chip says what choosing it returns; an unknown
    # value falls back (BR-SHL-011) rather than returning nothing.
    channel = params.filters.get("channel")
    channel = channel if channel in template_list.LIST_CHANNELS else None
    language = template_list.language_value(params.filters.get("language"), offered)
    status = params.filters.get("status")
    status = status if status in template_list.LIST_STATUSES else None
    list_facets = template_list.facets(
        rows, facts, offered, channel=channel, language=language, status=status
    )
    rows = [
        row
        for row in rows
        if template_list.matches(
            row, facts[row["code"]], channel=channel, language=language, status=status
        )
    ]

    rows.sort(key=_sort_key(params.sort), reverse=params.dir == "desc")

    total = len(rows)
    start = (params.page - 1) * params.per
    page_rows = rows[start : start + params.per]

    return Response(
        {
            "count": total,
            "results": page_rows,
            "page": params.page,
            "per": params.per,
            # The chips, in CR-007's own order, each with its live count so a
            # chip can never offer a filter that returns nothing without saying
            # so first.
            "categories": [
                {
                    "key": key,
                    "count": sum(1 for row in rows if row["category"] == key),
                }
                for key in catalogs.CR_CATEGORIES
            ],
            # CR-199-BRC10 — `channels` · `channels_total` · `languages` ·
            # `statuses`, each over the whole filtered catalogue, never a page.
            **list_facets,
            "columns": [dict(column) for column in CATALOG_COLUMNS],
            "page_sizes": list(pagination.PAGE_SIZES),
            "can_edit": _can_edit(request),
            "cannot_edit_reason": None if _can_edit(request) else READ_ONLY_REASON,
            # OQ-253 — the primary action creates a VARIANT, because a class a
            # tenant invents has no merge-field whitelist and could hold no body.
            "create_action": "variant",
            "create_action_reason": (
                "A template CLASS is platform vocabulary: its merge-field whitelist is what "
                "makes a body checkable, and a class nobody has specified has none — so a "
                "tenant-created class could never hold a body. What this button creates is a "
                "new VARIANT of a listed template (a consumer category and a language). "
                'OQ-253 asks the Product Owner whether that is what "+ New template" means.'
            ),
        }
    )


def _sort_key(sort: str | None) -> Any:
    if sort == "name":
        return lambda row: row["name"].lower()
    if sort == "kind":
        return lambda row: (row["kind"].lower(), row["name"].lower())
    if sort == "variants":
        return lambda row: (row["variants"], row["name"].lower())
    if sort == "edited":
        # Never edited sorts last on an ascending sort: an empty cell is not
        # "the oldest edit", it is "no edit", and the two must not interleave.
        return lambda row: (row["edited_at"] or "", row["name"].lower())
    return lambda row: (
        catalogs.CR_CATEGORIES.index(row["category"]),
        row["name"].lower(),
    )


def _catalog_row(
    code: str,
    rule_usage: dict[str, bool],
    fact: template_list.ClassFacts,
    offered: list[dict[str, Any]],
) -> dict[str, Any]:
    """One SET-09 row. Every cell is a fact this codebase can answer.

    `rule_usage`, `fact` and `offered` are THIS TENANT's answers, resolved ONCE
    by the caller for the whole list and passed down — not read per row
    (CR-199-BRC10: the per-row reads were ~260 statements for one page).
    """
    listing = catalogs.LISTINGS[code]
    klass = catalogs.catalog_for(code)
    latest = fact.latest
    return {
        "code": code,
        "name": listing.name,
        "category": listing.category,
        "category_source": listing.category_source,
        "kind": listing.kind,
        # CR-007's *"Variants (count)"*. Zero is a true and common answer: a
        # class with no variant row has never been registered on this tenant,
        # which is different from having one with no body.
        "variants": fact.variants,
        "used_by": listing.used_by,
        # ⚠ **`DEF-NOT-4531` — THE STATUS IS THE SERVER'S NOW, DERIVED FROM THE
        # TWO CATALOGUES.** `TemplateCatalog.tsx` derived it by regular
        # expression over this sentence and said so in its own comment: *"THE
        # DURABLE FIX IS A SERVER FIELD — a `used_by_state` on the catalog row,
        # beside the sentence — and this lane does not mint it, because
        # `apps/notifications/` belongs to another lane this hour."* This is
        # that field. A sentence that drifts can no longer take the status pill
        # with it, and a test refuses a sentence that contradicts either fact.
        "used_by_state": catalogs.used_by_state(code, rule_usage=rule_usage),
        # ⚠ WHAT THE DERIVATION DID NOT LOOK AT, ON THE WIRE (PO ruling
        # 2026-09-07). A declared blind spot with no number attached is
        # indistinguishable from an empty one — `G32` reported 0 unresolved
        # over 21 live refusals it could not see.
        "used_by_unchecked": list(catalogs.USED_BY_UNCHECKED),
        "edited": _edited_label(latest),
        "edited_at": latest.updated_at.isoformat() if latest is not None else None,
        "group": klass.group if klass is not None else None,
        "channel": klass.channel if klass is not None else None,
        # The two absences DEF-163 taught this module to keep apart, carried on
        # every row: `catalog_unavailable` is "nobody has defined this class's
        # merge fields"; `body_unavailable` is "nobody has written this letter".
        "catalog_unavailable": catalogs.CLASSES_WITHOUT_CATALOG.get(code),
        "body_unavailable": seed_templates.absent_reason(code),
        "has_published": fact.has_published,
        # CR-199-BRC10 (DEF-NOT-10672) — the drawing's Languages and Status
        # cells. `status` is one of three, exactly as the pill reads;
        # `needs_approval` is a legal notice (A1 C). See `template_list`.
        "languages": template_list.row_languages(fact, offered),
        "has_draft": fact.has_draft,
        "status": template_list.row_status(fact),
        "needs_approval": template_variants.is_legal_notice(code),
    }


def _platform_default(code: str) -> dict[str, Any] | None:
    """The wording this platform offers for a class it does not publish.

    CR-011 item 9. Contracts only, and the payload carries three things a screen
    cannot compose for itself: the BODY to pre-fill, the standing NOTICE that it
    is a starting point and not legal advice (`rights_footer`'s own posture), and
    — for the one placeholder — the plain-English list of what the utility must
    get from their bank before it can be used at all.
    """
    offered = seed_templates.default_body_for(code)
    if offered is None:
        return None
    return {
        "body": offered.body,
        "subject": offered.subject,
        "source": offered.source,
        "notice": seed_templates.CONTRACT_DEFAULT_NOTICE,
        "label": seed_templates.CONTRACT_DEFAULT_LABEL,
        # True for exactly one class today. A screen showing this must not offer
        # "publish" as a one-click action beside it without saying what it is:
        # the renderer REFUSES a body that still carries the marker.
        "is_placeholder": seed_templates.is_placeholder(code),
        "placeholder_marker": (
            rendering.PLACEHOLDER_MARK if seed_templates.is_placeholder(code) else None
        ),
        # PO 2026-08-18, second half of the ACH ruling: *"put the details, I will
        # handle it with user"*. Empty tuple for every other class.
        "requires_from_utility": list(catalogs.required_from_utility(code)),
        # BR-NOT-002 in one sentence, on the screen where the date is chosen.
        "requires_effective_date": True,
    }


def _edited_label(version: tm.NotificationTemplateVersion | None) -> str | None:
    """CR-007's *"Last edited (date · person)"*.

    `None` is the honest answer for a class nobody has touched, and a NULL
    person on a row that exists is honest too: the platform seed writes
    `created_by = NULL` on purpose, because no person published it (its audit
    row says `source: provisioning_seed`). A screen showing an invented name
    there would be claiming somebody authorised a page they have never seen.
    """
    if version is None:
        return None
    who = version.published_by or version.created_by
    stamp = version.updated_at.date().isoformat()
    return f"{stamp} · {who}" if who else f"{stamp} · platform seed"


def _author_label(version: tm.NotificationTemplateVersion) -> str:
    """Who this version is attributed to — the id, or the platform, never a name.

    `platform seed` is a REAL answer and not a fallback: provisioning writes
    `created_by = NULL` on purpose, because no person published those bodies,
    and its audit row carries `source: provisioning_seed`. Rendering an invented
    name there would claim somebody authorised a page they have never seen.
    """
    who = version.published_by or version.created_by
    return str(who) if who else "platform seed"


def _live_version(
    template: tm.NotificationTemplate,
) -> tm.NotificationTemplateVersion | None:
    """This variant's live undated version — the one that makes it ACTIVE.

    Undated only: the effective-dated half belongs to the CONTRACT classes
    (BR-NOT-002), where several published versions coexist by design and
    "the live one" depends on a date the caller holds.
    """
    return (
        _versions_of(template)
        .filter(
            status=tm.VERSION_PUBLISHED,
            effective_from__isnull=True,
        )
        .first()
    )


# ══════════════════════════════════════════════════════════════════════════
# SET-10 · ONE TEMPLATE
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([AnyTenantRole])
def template_detail(request: Any, code: str) -> Response:
    """`GET /template-catalog/{code}` — the detail screen's whole payload.

    Header, variant switcher, merge-field palette, version history and a
    rendered preview, in one round trip, because they are one screen and four
    requests for one screen is four ways for it to be half-loaded.

    `?variant=<id>` selects which variant the preview and the version list are
    for; without it the `(default, default)` variant is chosen — BR-NOT-001's
    mandatory fallback, which is also what resolution would pick.
    """
    require_tenant(request)
    listing = _class_or_refuse(code)
    klass = catalogs.catalog_for(code)

    variants = list(_variants_of(code).order_by("category", "language"))
    selected = _selected_variant(variants, request.query_params.get("variant"))

    versions: list[dict[str, Any]] = []
    preview_block: dict[str, Any] | None = None
    preview_unavailable: str | None = None
    if selected is not None:
        rows = _versions_of(selected).order_by("-version")
        # CR-049 task 8 — the chain is already ordered newest-first, so each
        # row's PREDECESSOR is the next item in the list. Pairing them here
        # costs nothing; resolving each one inside `_version_row` would be an
        # extra query per version on the screen that draws every version there
        # is.
        chain = list(rows)
        versions = [
            _version_row(row, chain[index + 1] if index + 1 < len(chain) else None)
            for index, row in enumerate(chain)
        ]
        live = _live_version(selected)
        source = live or rows.first()
        if source is None:
            preview_unavailable = (
                "This variant has no version yet — nothing has been written for it. Save a "
                "draft to see it render."
            )
        else:
            try:
                preview_block = template_preview.preview(
                    template_code=code,
                    body=source.body,
                    version=source.version,
                    subject=source.subject,
                    language=selected.language,
                    body_format=source.body_format,
                )
                preview_block["from_version"] = source.version
                preview_block["from_status"] = source.status
            except rendering.RenderRefused as refusal:
                preview_unavailable = str(refusal)

    can_edit = _can_edit(request)
    # CR-048 B7/E6 — the offer and the route ask the same questions in the same
    # order, so a control drawn ENABLED here cannot be refused by the endpoint
    # it opens. See `rule_service.template_test_offer`.
    test_offer = rule_service.template_test_offer(
        code=code,
        channel=klass.channel if klass is not None else None,
        actor=_actor(request),
        can_edit=can_edit,
    )
    return Response(
        {
            "code": code,
            "name": listing.name,
            "category": listing.category,
            "category_source": listing.category_source,
            "kind": listing.kind,
            "used_by": listing.used_by,
            "used_by_state": catalogs.used_by_state(
                code, rule_usage=rule_service.template_usage()
            ),
            "used_by_unchecked": list(catalogs.USED_BY_UNCHECKED),
            "group": klass.group if klass is not None else None,
            "channel": klass.channel if klass is not None else None,
            # ⚠ **CR-076 item 1 — WHICH SURFACES THIS ONE TEMPLATE IS A FORM
            # FOR, SERVED SO THAT NO SCREEN TYPES THE LIST OUT.** SET-10 lets a
            # person switch the preview between them, and the PO's own ruling on
            # how that list is built is verbatim: *"you are correct - dont use
            # hard coding"*. A fixed five in the client would offer an empty SMS
            # tab on a letter and would keep offering five on the day a sixth
            # surface exists — the sign-up screen's eleventh service, one screen
            # along (hard-won law 2).
            #
            # ⚠ **IT IS NOT `group`, WHICH ANSWERS A DIFFERENT QUESTION.**
            # `group` is the ONE family the class is filed under; `kind` is the
            # prose a person reads (*"Print + email"*), and `CHANNELS_BY_KIND`
            # is the only place in this repo that says what that prose MEANS.
            # The screen must not parse the prose — a drawing decision read out
            # of a label changes behaviour the moment somebody edits copy — so
            # the meaning is resolved here and the list travels.
            #
            # ⚠ **`preview_surfaces` AND NOT `surfaces`, BECAUSE SET-10 ALREADY
            # HAS A CONTROL BY THAT NAME AND IT IS A DIFFERENT AXIS.** The
            # screen's `SurfaceSwitcher` (CR-048 E5) navigates to a SIBLING
            # TEMPLATE CLASS — `sms_bill_ready` beside `email_bill_ready`, two
            # rows with two bodies and two version lists. This list is the forms
            # of THIS ONE class, which has one body, so switching it redraws the
            # page and changes nothing a person is editing. Two things called
            # "surfaces" in one component is how the next lane wires the wrong
            # one.
            "preview_surfaces": list(_surfaces_for(listing, klass)),
            # CR-007's merge-fields panel. The class's OWN whitelist, so
            # insert-on-click can only ever insert a token the save will accept.
            "merge_fields": sorted(klass.tokens) if klass is not None else [],
            # ⚠ THE PANEL IS TWO COLUMNS, NOT A TOKEN LIST (PO, 2026-08-17,
            # showing SET-10.corrected: `{{bill.original_total}}` beside
            # `$32.22`). The right-hand value is the SAMPLE the preview will
            # actually print, resolved through the renderer's own formatter —
            # so money carries the tenant's currency and a date the tenant's
            # format, and the panel cannot disagree with the pane below it.
            #
            # ⚠ AND NOT ONE OF THOSE FIGURES IS COMPUTED. `123.45` is a
            # constant; nothing on this screen reads a rate, sums a total or
            # stores an amount. A template is WORDING — B4's money math is not
            # here and must never be (CR-007 coordinator instruction, and the
            # test `…no_money_is_computed_or_stored` asserts it).
            "merge_field_rows": template_preview.sample_field_rows(code),
            # The preview strip's *"sample data: … · …"*, from the SAME context
            # the pane renders from.
            "sample_identity": template_preview.sample_identity(code),
            "derived_spelling": sorted(klass.derived_spelling) if klass is not None else [],
            "mandatory_content": list(klass.mandatory_content) if klass is not None else [],
            # US-NOT-016 — the SHAPE, never this tenant's live field list
            # (BR-NOT-012 resolves custom fields from the stamped snapshot).
            "custom_field_variables": [
                "{{account.custom.<key>}}",
                "{{premises.custom.<key>}}",
                "{{unit.custom.<key>}}",
            ],
            "catalog_unavailable": catalogs.CLASSES_WITHOUT_CATALOG.get(code),
            "body_unavailable": seed_templates.absent_reason(code),
            # ⚠ **THE PLATFORM'S OFFERED WORDING — CR-011 item 9, PO 2026-08-18:**
            # *"already answer - provide default and allow user to change"*. Four
            # CONTRACT classes carry wording that is NOT published on any tenant,
            # because BR-NOT-002 makes a contract version effective-dated and only
            # a human can choose that date. Served here so the designer can offer
            # it pre-filled: without this the ruling reaches a Python file and no
            # screen, which is hard-won law 2 (*built is not wired*).
            # `None` for every other class — those have a PUBLISHED body and an
            # offer beside a live body would be two sources for one document.
            "platform_default": _platform_default(code),
            "variants": [_variant_row(variant) for variant in variants],
            "selected_variant": str(selected.pk) if selected is not None else None,
            "versions": versions,
            "preview": preview_block,
            "preview_unavailable": preview_unavailable,
            # CR-007's *"plain 160-char counter for SMS"*. Served rather than
            # hardcoded in the client so the counter and any future segment rule
            # have one source. It is a COUNTER, not a limit: nothing here
            # truncates or refuses a longer body, because no signed rule says a
            # 161-character SMS is invalid — A19 r8 records the four SMS bodies'
            # lengths (99–138 chars) and states no cap.
            "sms_character_counter": 160,
            # CR-199-BRC10 S4 — which layouts this class may be written in. An
            # email offers Rich and Plain text (image 02); anything else is plain
            # only and the screen draws no switch.
            "body_formats": (
                list(tm.BODY_FORMATS)
                if klass is not None and klass.channel == "email"
                else [tm.BODY_FORMAT_PLAIN]
            ),
            "can_edit": can_edit,
            "cannot_edit_reason": None if can_edit else READ_ONLY_REASON,
            # BR-SHL-025 — both controls RENDER and each carries its own reason,
            # because the two have different fixes and only ONE of them has been
            # fixed. ⚠ **`can_test_send` WAS HARDCODED `False` HERE UNTIL CR-048
            # B7, BESIDE A SENTENCE THAT HAD STOPPED BEING TRUE (DEF-2503).** The
            # notification-rules screen has queued real test rows since CR-009,
            # so *"No test send in this release, on any channel"* told a utility
            # the product cannot do something the product does. The lesson is the
            # one wave E wrote down the same week: a "cannot" decays like every
            # other claim, and this one was frozen into a constant where nothing
            # re-measured it. It is now DERIVED, once, from the same checks the
            # route runs.
            "can_test_send": test_offer.can_test_send,
            "test_send_reason": test_offer.reason,
            # ── CR-048 wave I · A LABEL ON SCREEN, THE SENTENCE ON HOVER ─────
            # PO, 2026-08-30, walking the deployed v2.83.0 and finding the same
            # fault ten times in one sitting: *"again too much text content
            # breking the UI"*, *"just use 3 or 4 wrods and fix the UI"*.
            # Every `*_label` below is what the SCREEN draws under a control
            # that cannot be pressed; the `*_reason` beside it is that control's
            # tooltip and is unchanged. Nothing is deleted — a control that
            # refuses silently is a worse defect than a long sentence
            # (BR-SHL-025), so the whole explanation is still one hover away.
            "test_send_label": test_offer.label,
            "can_download_pdf": False,
            "download_pdf_label": NO_PDF_LABEL,
            "download_pdf_reason": NO_PDF_REASON,
            # ⚠ DEF-335 — THIS TEXT IS DRAWN ON A UTILITY'S SCREEN, so the
            # PROVENANCE lives here in the comment and on `set_default_br_ref`,
            # never in the sentence (CR-016; the pattern `billing/
            # templates_service.py` set). The honesty is kept and the ids are
            # dropped: the PO photographed the old wording telling a water
            # utility that the default "is the row's KEY, not a flag on it
            # (BR-NOT-001/BR-NOT-006)", that a July letter "would start claiming
            # it was rendered from a row that now says something else
            # (BR-BIL-026)", and that "OQ-252 is with the Product Owner".
            #
            # The rule, for us: the default is WHICH ROW YOU ARE — the variant
            # whose consumer category and language are both "default"
            # (BR-NOT-001 / BR-NOT-006) — so promoting another variant is a
            # RE-KEY, and every message already sent pins (template, version,
            # language) forever (BR-BIL-026). OQ-252 is with the Product Owner.
            "can_set_default": False,
            # CR-048 wave I — three words on screen, the sentence on hover.
            "set_default_label": "Default is fixed",
            "set_default_reason": (
                "You cannot change which variant is the default yet. "
                "Messages already sent must keep the exact wording they used."
            ),
            # A MACHINE field, exempt from G28 by name and by suffix — the
            # screen puts it on `data-br-ref`, where support reaches it and a
            # clerk never does.
            "set_default_br_ref": "BR-NOT-001 · BR-NOT-006 · BR-BIL-026 · OQ-252",
            # ⚠ DEF-335, the same rewrite. Ours: a variant carries a language
            # tag and resolution records which language it actually used
            # (BR-NOT-006). ⚠ AMENDED 2026-09-23 (`OQ-CUS-12619`,
            # `DEF-NOT-6354`): this said *"Nothing stores a customer's
            # preferred language yet. A language variant you add here is never
            # chosen automatically."* The first sentence was false since r15 #2
            # (`accounts.preferred_language` exists). The PO then ruled that a
            # message goes in the UTILITY's default language, never the
            # customer's (*"(a) Portal only; emails in English."*), and the
            # writers now ask the resolver for the utility's Regional code — so
            # a variant tagged with that exact code IS chosen, and any other
            # language never is. That is what the screen now says.
            # CR-048 wave I — three words on screen, the sentence on hover.
            "language_selection_label": "Utility's language only",
            "language_selection_reason": (
                "Messages use your utility's language. Other languages are never chosen."
            ),
            "language_selection_br_ref": "BR-NOT-006 · OQ-CUS-12619",
        }
    )


def _surfaces_for(
    listing: catalogs.TemplateListing, klass: catalogs.TemplateClass | None
) -> tuple[str, ...]:
    """The detail payload's `surfaces`, with the unknown case FAILING TO ONE.

    `catalogs.designer_surfaces` raises for a `kind` nobody has stated channels
    for, and that is right there: a class whose surfaces are unknown must not
    quietly acquire a set somebody assumed. It is wrong HERE, because this is a
    whole screen's payload and a 500 would take the designer down over a tab bar.

    So an unknown kind serves `()`, and the screen's own rule for an empty list
    is to draw no switcher and preview exactly the one surface it drew before
    this field existed. **The fallback of a derivation that cannot answer is the
    OLD screen, never a guessed one** — the shape `templateEvents.ts` states for
    the catalog's grouping, applied to the same question one screen along.
    """
    try:
        return catalogs.designer_surfaces(listing.kind, klass.group if klass else None)
    except catalogs.UnknownTemplateKind:
        return ()


def _selected_variant(
    variants: list[tm.NotificationTemplate], raw: Any
) -> tm.NotificationTemplate | None:
    """The requested variant, else the mandatory `(default, default)` one.

    BR-SHL-011's fall-back-never-error, applied to a path a person can bookmark:
    a stale `?variant=` from a deactivated row lands on the default rather than
    on an error page.
    """
    if raw:
        for variant in variants:
            if str(variant.pk) == str(raw):
                return variant
    for variant in variants:
        if variant.category == tm.VARIANT_DEFAULT and variant.language == tm.VARIANT_DEFAULT:
            return variant
    return variants[0] if variants else None


def _variant_row(variant: tm.NotificationTemplate) -> dict[str, Any]:
    live = _live_version(variant)
    return {
        "id": str(variant.pk),
        "name": variant.name,
        "category": variant.category,
        "language": variant.language,
        # BR-NOT-001's mandatory fallback. Marked rather than inferred by the
        # screen, so "this is the one everything falls back to" is the server's
        # statement (OQ-252's option (a) made visible).
        "is_default": variant.category == tm.VARIANT_DEFAULT
        and variant.language == tm.VARIANT_DEFAULT,
        "active": live is not None,
        "published_version": live.version if live is not None else None,
        "version_count": _versions_of(variant).count(),
    }


def _version_row(
    version: tm.NotificationTemplateVersion,
    previous: tm.NotificationTemplateVersion | None = None,
) -> dict[str, Any]:
    """One history row. `pinned_by` is why a row may be archived and never
    deleted (rule 4, US-NOT-006 TC-5's 3,412 receipts).

    ⚠ **`previous` IS PASSED IN, NOT LOOKED UP (CR-049 task 8).** The caller
    already holds the whole chain ordered by version, so resolving each row's
    predecessor here would be one extra query per version on a screen that draws
    every version there is. Left off — a caller reading a single row — it is
    resolved once, which is correct and is not the list path.
    """
    if previous is None:
        previous = template_changes.previous_of(version)
    return {
        "id": str(version.pk),
        "version": version.version,
        "status": version.status,
        "subject": version.subject,
        "body": version.body,
        # CR-199-BRC10 S4 — `plain` | `rich`, the version's own layout.
        "body_format": version.body_format,
        "effective_from": (version.effective_from.isoformat() if version.effective_from else None),
        "created_by": str(version.created_by) if version.created_by else None,
        "published_by": str(version.published_by) if version.published_by else None,
        "published_at": version.published_at.isoformat() if version.published_at else None,
        "archived_at": version.archived_at.isoformat() if version.archived_at else None,
        "updated_at": version.updated_at.isoformat(),
        # The PO's history line is *"Jul 30 · Priya Menon — softened wording"*.
        # This product holds the DATE and neither of the other two, and OQ-255
        # is why: `created_by` is a plain uuid (identity is another module's
        # table, B11 F-3) and no column anywhere records what an edit changed.
        # Served as an explicit absence rather than a blank, so the panel states
        # it instead of reading as "nobody edited this".
        "author_label": _author_label(version),
        # ⚠ **`DEF-NOT-4531` — WHETHER AN AUTHOR IS RECORDED AT ALL, AS ITS OWN
        # FACT.** The designer header printed *"author not recorded"* on EVERY
        # version unconditionally, and for a seeded body that is exactly true —
        # provisioning writes `created_by = NULL` on purpose. It stops being
        # true the moment a System Admin saves a draft, because `template_service`
        # stamps their id: the author IS then recorded, we simply may not print
        # a uuid (B14 rule 31) and identity publishes no display name (OQ-255).
        # A screen cannot tell those two apart from `author_label`, which serves
        # a uuid in one case and a magic string in the other — so the boolean is
        # served and the line is drawn only when it is TRUE that nobody is on
        # record.
        "author_recorded": bool(version.published_by or version.created_by),
        "change_note": None,
        # ⚠ **DEF-2479 — THIS WAS A CODE COMMENT RENDERED AS A TABLE CELL.** It
        # read: *"No column records what an edit changed, and the author's
        # display name is identity's to publish — this module holds a user id,
        # not a name (OQ-255). The date and the version number are this
        # product's own facts and are shown."* Measured on the deployed
        # v2.83.0 it drew a **645px-tall cell** in a 344px-wide panel, on every
        # version row of every template — the single worst piece of geometry on
        # the screen, and the PO photographed it.
        #
        # A TABLE CELL HOLDS A VALUE. The fact survives — a reader must not
        # conclude "nobody edited this" from a blank — but it is now four words,
        # and the sentence explaining WHY is here, which is what a code comment
        # is for (G28: keep the honesty, drop the provenance).
        "change_note_unavailable": "No change note recorded",
        # The full explanation, for support and for the next lane: OQ-255. This
        # product holds the DATE and neither of the PO's other two fields —
        # `created_by` is a plain uuid because identity is another module's
        # table to publish (B11 F-3), and no column anywhere records WHAT an
        # edit changed. Both are answerable; neither is answered here.
        "change_note_br_ref": "OQ-255 · B11 F-3",
        # ══ CR-049 TASK 8 · WHAT MOVED, AS A VALUE ═══════════════════════════
        # `BR-NOT-027` part 3, and it is the OTHER half of `OQ-255` — the half
        # that IS answerable without asking anybody. `change_note` above stays
        # null because *"softened wording"* is a judgement a person makes and
        # nothing records it; **which FIELDS moved is a fact about two immutable
        # rows** and this product simply never computed it.
        #
        # A LIST OF FIELD NAMES, never a sentence: a table cell holds a value
        # (PO ruling 2026-08-30). The screen writes "Subject · Letter" from
        # these and puts the line counts in the tooltip. An EMPTY list means an
        # edit that moved no wording — a status change, or a draft saved
        # unchanged — and `changed_from_version: null` means the FIRST version,
        # which is the wording ARRIVING and is not the same fact.
        "changed_fields": template_changes.changed_field_names(version, previous),
        "changed_from_version": previous.version if previous is not None else None,
        "pinned_by": template_service.pin_count(version),
        "deletable": version.status == tm.VERSION_DRAFT
        and template_service.pin_count(version) == 0,
        # ══ CR-199-BRC10 S3 · HISTORY'S *MAKE LIVE AGAIN* ═══════════════════
        # Which earlier version this one's wording was copied from (Restore or
        # Make live again), so History can say "v5 · v1 restored". NULL for a
        # version somebody typed.
        "restored_from_version": version.restored_from_version,
        # An EARLIER published version, the only kind the action applies to.
        # The screen draws the button from this, so a button drawn can never be
        # refused by the route it opens (BR-SHL-025).
        "can_make_live_again": template_variants.was_published_before(version)
        and version.template.group not in template_service.EFFECTIVE_DATED_GROUPS,
        # A1 C — a legal notice's button reads "Send for approval" instead.
        "make_live_again_needs_approval": template_variants.is_legal_notice(
            version.template.code
        ),
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-049 TASK 8 — ONE CHANGE, AND WHO IS HOLDING THE WORDING IT MOVED AWAY FROM
# ══════════════════════════════════════════════════════════════════════════
@api_view(["GET"])
@permission_classes([SystemAdminOnly])
def template_change(request: Any, code: str, version_id: str) -> Response:
    """`GET /template-catalog/{code}/changes/{version_id}` — `BR-NOT-027` part 3.

    **The two halves are served together on purpose.** The PO asked them as one
    question — *"any changes to tempalte or any items hsould be noted as
    changed; that way it will keep the santity of the legal documents"* — and a
    caller able to fetch *"what changed"* without *"who is holding the old
    wording"* will, which is the version history that already exists.

      * `changed_fields` / `fields` — WHICH wording fields moved and by how many
        lines. Never a sentence, and never an author's account of WHY: that is
        `OQ-255`(b), open with the Product Owner, and a derived diff dressed as
        a note would be this product putting words in a person's mouth.
      * `superseded` — the version this one replaced, HOW MANY already-sent
        documents still stand on it, and a page of them. Each row carries the id
        of the KEPT COPY where one exists, which opens the existing
        `GET /documents/{id}`. **A storage key is never served** — the caller
        gets a document id it can re-resolve under its own tenant, exactly as
        `CR-049` task 3's routes do.

    ⚠ **`superseded.documents` IS THE TOTAL AND `superseded.sample` IS A PAGE OF
    IT.** They are the same query, so the panel can say *"20 of 3,412"* without
    the two numbers being about different sets — which on this screen would be a
    false statement to a regulator rather than an off-by-one.

    ⚠ **SYSTEM ADMIN, like every other door on this screen.** The endpoint gate
    is narrower than `BR-BIL-027`'s service gate, and deliberately: the PO ruled
    this SETTINGS SURFACE System-Admin-only (exception 4 below), and this route
    lists customers who received a particular letter, which is the most
    sensitive read on it.
    """
    require_tenant(request)
    _class_or_refuse(code)
    version = _version_or_404(code, version_id)
    answer = template_changes.record(version)
    change = answer.change
    return Response(
        {
            "code": code,
            "version": change.version,
            "version_id": change.version_id,
            "previous_version": change.previous_version,
            "is_first_version": change.is_first_version,
            "changed_at": change.changed_at.isoformat() if change.changed_at else None,
            "author_label": change.author_label,
            "changed_fields": [field.field for field in change.fields],
            "fields": [
                {
                    "field": field.field,
                    "lines_added": field.lines_added,
                    "lines_removed": field.lines_removed,
                    "added": field.added,
                    "removed": field.removed,
                }
                for field in change.fields
            ],
            # Still absent, still said out loud — see `_version_row`. A reader
            # must not conclude from this trail that somebody wrote down why.
            "change_note": None,
            "change_note_br_ref": "OQ-255 · B11 F-3",
            "superseded": {
                "version": answer.superseded_version,
                "documents": answer.superseded_documents,
                "truncated": answer.sample_truncated,
                "sample": [
                    {
                        "message_id": impact.message_id,
                        "channel": impact.channel,
                        "status": impact.status,
                        "sent_at": impact.sent_at.isoformat() if impact.sent_at else None,
                        "account_id": impact.account_id,
                        "document_id": impact.document_id,
                        "document_kept": impact.document_kept,
                        "display_name": impact.display_name,
                    }
                    for impact in answer.superseded_sample
                ],
            },
        }
    )


def _version_or_404(code: str, version_id: str) -> tm.NotificationTemplateVersion:
    """One version of one class, tenant-scoped — or the same 404 as a bad id.

    ⚠ **THE CLASS IS PART OF THE LOOKUP, NOT DECORATION.** A version id alone
    would let a caller read any variant's chain through any class's URL, and the
    route would answer happily. Scoped in the app layer AND by RLS, for
    `document_store`'s stated reason: the filter is provable on any vendor, the
    database refuses a foreign row only on PostgreSQL.
    """
    from django.core.exceptions import ValidationError as DjangoValidationError

    tenant_id = core_tenancy.current_tenant_id()
    try:
        row = (
            tm.NotificationTemplateVersion.objects.select_related("template")
            .filter(tenant_id=tenant_id, template__code=code, pk=version_id)
            .first()
        )
    except (DjangoValidationError, ValueError, TypeError) as malformed:
        # A `version_id` that is not a uuid is the SAME answer as one that does
        # not exist. A route that could tell them apart would eventually report
        # the difference (HR-1, and task 3's routes make the same call).
        raise errors.NotFoundError() from malformed
    if row is None:
        raise errors.NotFoundError()
    return row


# ══════════════════════════════════════════════════════════════════════════
# THE WRITES — System Admin only, every one of them audited by the service
# ══════════════════════════════════════════════════════════════════════════
@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def add_variant(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/variants` — CR-007's *"add variant (name
    + language + audience note)"*.

    The "audience note" IS the consumer category: BR-NOT-001's four values are
    the audiences this platform has (residential / commercial / industrial /
    government) plus the mandatory `default` fallback, and a free-text note
    beside them would be a second, unenforced way of saying who a letter is for.
    """
    require_tenant(request)
    _class_or_refuse(code)
    payload = _payload(request)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.templates.nameRequired",
            field_errors=[{"field": "name", "code": errors.VAL_REQUIRED}],
        )
    try:
        variant, created = template_service.register(
            code=code,
            name=name,
            actor=_actor(request),
            category=str(payload.get("category") or tm.VARIANT_DEFAULT),
            language=str(payload.get("language") or tm.VARIANT_DEFAULT),
        )
    except template_service.TemplateRefused as refusal:
        raise _refused(str(refusal), "BR-NOT-001") from refusal
    # DEF-207: 201 CREATED only when something was created. `register` is
    # idempotent on (code, category, language) and that is CORRECT — but a bare
    # 201 told a person who re-added an existing variant that a new one had been
    # made, under the OLD variant's name. 200 is the honest answer for a fetch,
    # and it is the same shape `api.py:522` already uses one module over.
    return Response(_variant_row(variant), status=201 if created else 200)


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def create_from_default(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/from-default` — *Create from our default*.

    `CR-190-BRC10`, PO 2026-10-22, verbatim: *"A: keep your rule (each utility
    publishes its own) but make it one click ('Create from our default')"*.
    DEF-NOT-10442: on a contract class with no variant the platform's wording was
    SHOWN and never usable — *Duplicate as variant* opened a blank editor and the
    admin had to retype the agreement.

    One action, System Admin only, and BR-NOT-002 stands in full: it creates the
    `(default, default)` variant (idempotent, `template_service.register`) and
    saves ONE DRAFT whose subject and body are the platform's offered wording,
    dated with the `effective_from` the admin chose — a contract still needs a
    human's date, and nothing here is PUBLISHED. The admin reads it, edits it if
    they wish, and publishes it with the existing Publish action. A class the
    platform offers no wording for is refused by name; so is a class that
    already has a variant (that variant is the place to edit).
    """
    require_tenant(request)
    _class_or_refuse(code)
    offered = seed_templates.default_body_for(code)
    if offered is None:
        raise _refused(
            f"{code!r} has no platform wording to start from.", "BR-NOT-002"
        )
    if _variants_of(code).exists():
        raise _refused(
            f"{code!r} already has a variant; open it to edit its wording.", "BR-NOT-002"
        )
    payload = _payload(request)
    effective_from = _effective_from_or_400(payload.get("effective_from"))
    actor = _actor(request)
    listing = catalogs.LISTINGS.get(code)
    try:
        with transaction.atomic():
            variant, _created = template_service.register(
                code=code,
                name=str(getattr(listing, "name", None) or offered.name or code),
                actor=actor,
            )
            version = template_service.save_draft(
                template=variant,
                body=offered.body,
                actor=actor,
                subject=offered.subject or None,
                effective_from=effective_from,
            )
    except rendering.RenderRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-026") from refusal
    except template_service.TemplateRefused as refusal:
        raise _refused(str(refusal), "BR-NOT-002") from refusal
    return Response(
        {"variant": _variant_row(variant), "version": _version_row(version)}, status=201
    )


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def preview_body(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/preview` — the LIVE half of the preview.

    A READ despite being a POST: it writes nothing, and it is a POST because a
    candidate body is a document that does not fit in a query string. **Any
    tenant role may call it** — CR-007's *"others read-only + preview"*, and the
    PO's Settings ruling makes reading and previewing the clerk's half.

    It renders the body the editor CURRENTLY HOLDS, not the saved one, which is
    what makes the pane live — and it refuses exactly what the save refuses,
    because both go through `rendering.validate_body`. An editor whose preview
    accepts what its save rejects teaches the wrong lesson.
    """
    require_tenant(request)
    _class_or_refuse(code)
    payload = _payload(request)
    body = payload.get("body")
    if not isinstance(body, str):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.templates.bodyRequired",
            field_errors=[{"field": "body", "code": errors.VAL_REQUIRED}],
        )
    subject = payload.get("subject")
    try:
        block = template_preview.preview(
            template_code=code,
            body=body,
            version=int(payload.get("version") or 0),
            subject=subject if isinstance(subject, str) and subject else None,
            language=payload.get("language") or None,
            body_format=_body_format_or_400(payload.get("body_format")),
        )
    except rendering.RenderRefused as refusal:
        raise _refused(str(refusal), "BR-NOT-006") from refusal
    return Response(block)


def _body_format_or_400(raw: Any) -> str:
    """`CR-199-BRC10` S4 — `plain` (the default, and every version written
    before rich existed) or `rich`. Anything else is refused by name."""
    if raw in (None, ""):
        return tm.BODY_FORMAT_PLAIN
    if raw not in tm.BODY_FORMATS:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.templates.bodyFormatUnknown",
            field_errors=[{"field": "body_format", "code": errors.VAL_FORMAT}],
        )
    return str(raw)


def _markup_refusal(refusal: rendering.RenderRefused) -> errors.BizError | None:
    """`CR-199-BRC10` — the two save refusals a clerk must be able to READ,
    with their own message_key and the token or address in `params`, under the
    body box (image 17: *"{bogus} can't be filled. Pick from the placeholder
    list."*). None for every other refusal, which keeps its generic key."""
    if isinstance(refusal, rendering.PlaceholderUnknown):
        token = refusal.tokens[0]
        key = "notifications.templates.placeholderUnknown"
        params = {"token": token, "placeholder": "{" + token + "}"}
    elif isinstance(refusal, rendering.MarkupRefused):
        key, params = str(refusal.finding["message_key"]), dict(refusal.finding["params"])
    else:
        return None
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-NOT-006",
        message_key=key,
        params={**params, "detail": str(refusal)},
        field_errors=[{"field": "body", "code": errors.VAL_FORMAT}],
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def save_draft(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/draft` — an edit is a NEW version.

    BR-BIL-026: the published version is untouched and keeps rendering until
    somebody publishes this one. **Unknown merge token BLOCKS the save with an
    inline error** (CR-007's own rule, US-NOT-005 TC-5) — the refusal comes from
    `rendering.validate_body` and names the token and the class, and it is
    returned as a field error so the editor can put it under the body box.
    """
    require_tenant(request)
    _class_or_refuse(code)
    payload = _payload(request)
    variant = _variant_or_400(code, payload.get("variant"))
    body = payload.get("body")
    if not isinstance(body, str):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.templates.bodyRequired",
            field_errors=[{"field": "body", "code": errors.VAL_REQUIRED}],
        )
    subject = payload.get("subject")
    # ⚠ **WIRED 2026-08-18 (CR-011 item 9) — AND ITS ABSENCE MADE EVERY CONTRACT
    # CLASS UNUSABLE THROUGH THIS API.** `template_service.save_draft` has always
    # taken `effective_from` and has always REFUSED a contract draft without one
    # (BR-NOT-002); this endpoint never passed it, so every save against any of
    # the four contract classes failed with *"a contract template and every
    # version needs an `effective_from`"* and there was no field a caller could
    # send to satisfy it. Nothing noticed because no class in the group had a
    # body to save. Hard-won law 2, one layer up: the service was built and the
    # door to it was not wired.
    effective_from = _effective_from_or_400(payload.get("effective_from"))
    try:
        version = template_service.save_draft(
            template=variant,
            body=body,
            actor=_actor(request),
            subject=subject if isinstance(subject, str) and subject else None,
            effective_from=effective_from,
            body_format=_body_format_or_400(payload.get("body_format")),
        )
    except rendering.RenderRefused as refusal:
        named = _markup_refusal(refusal)
        if named is not None:
            raise named from refusal
        # The inline error CR-007 asks for. `field: "body"` so the screen puts
        # it against the box the token was typed into rather than in a banner.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-026",
            message_key="notifications.templates.refused",
            params={"detail": str(refusal)},
            field_errors=[{"field": "body", "code": errors.VAL_FORMAT}],
        ) from refusal
    except template_service.TemplateRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-026") from refusal
    return Response(_version_row(version), status=201)


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def publish_version(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/publish` — BR-BIL-027's narrow right.

    Publishing affects FUTURE renders only. The previous published version is
    auto-archived and is retained forever; every document already pinned to it
    still renders from it (J22 step 4: *"Nothing re-renders"*).
    """
    require_tenant(request)
    _class_or_refuse(code)
    version = _version_or_400(code, _payload(request).get("version_id"))
    try:
        published = template_service.publish(version_row=version, actor=_actor(request))
    except template_service.TemplateRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-027") from refusal
    return Response(_version_row(published))


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def deactivate_variant(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/deactivate` — CR-007's *"a variant in use
    can't be deleted — deactivate only, with usage warning listing consumers"*.

    Archives the variant's live version. The response names the consumers
    BEFORE and AFTER, because the warning the CR asks for is only useful if it
    is the server's count and not the screen's guess.
    """
    require_tenant(request)
    _class_or_refuse(code)
    payload = _payload(request)
    variant = _variant_or_400(code, payload.get("variant"))
    live = _live_version(variant)
    if live is None:
        raise _refused(
            f"the {variant.category}/{variant.language} variant has no published version, so "
            "there is nothing to deactivate. A variant is LIVE exactly when it has one — "
            'there is no separate active flag, because a second way of saying "archived" '
            "is how a screen ends up showing a template that renders nothing.",
            "BR-NOT-006",
        )
    pinned = template_service.pin_count(live)
    try:
        archived = template_service.archive(version_row=live, actor=_actor(request))
    except template_service.TemplateRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-027") from refusal
    return Response(
        {
            "variant": _variant_row(variant),
            "version": _version_row(archived),
            # The usage warning, as data.
            "consumers": {
                "queued_messages_pinned_to_this_version": pinned,
                "detail": (
                    f"{pinned} queued message(s) name this exact version and keep it "
                    "forever — a published body is evidence of what a customer was sent "
                    "(CLAUDE.md rule 4), so it is archived and never deleted."
                ),
                "resolution_after": (
                    "Resolution now falls through to the (default, default) variant "
                    "(BR-NOT-006: missing variant → tenant-default fallback, NEVER a "
                    "blank). Deactivating the default variant itself leaves the class with "
                    "nothing to resolve, and generation HOLDS rather than inventing a body."
                ),
            },
        }
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def restore_version(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/restore` — history is never rewritten.

    Restoring v2 saves v2's body as a NEW draft. The old row is untouched
    (migration 0006's trigger would refuse anyway) and every document pinned to
    it renders exactly what it always rendered. The audit trail records which
    version the body came from — "v4 was typed" and "v4 is v2 restored" are
    different facts about a customer-facing document.
    """
    require_tenant(request)
    _class_or_refuse(code)
    payload = _payload(request)
    source = _version_or_400(code, payload.get("version_id"))
    try:
        restored = template_service.save_draft(
            template=source.template,
            body=source.body,
            actor=_actor(request),
            subject=source.subject,
            # CR-199-BRC10 S3 — the row now says which version it restored.
            restored_from_version=source.version,
        )
    except rendering.RenderRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-026") from refusal
    except template_service.TemplateRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-026") from refusal
    return Response(
        {
            **_version_row(restored),
            "restored_from_version": source.version,
            "detail": (
                f"v{restored.version} is a new DRAFT holding v{source.version}'s body. "
                f"v{source.version} is unchanged and every message pinned to it still "
                "renders from it (BR-BIL-026). Publish the draft to make it live."
            ),
        },
        status=201,
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-199-BRC10 — + NEW VARIANT · DUPLICATE AS VARIANT · MAKE LIVE AGAIN
# ══════════════════════════════════════════════════════════════════════════
def _variant_refused(refusal: template_service.TemplateRefused, br_ref: str) -> errors.BizError:
    """A `VariantRefused` carries its own `message_key`; any other refusal from
    the service underneath keeps the generic one (`_refused`)."""
    if isinstance(refusal, template_variants.VariantRefused):
        return errors.BizError(
            errors.BIZ_STATE,
            br_ref=br_ref,
            message_key=refusal.key,
            params={**refusal.params, "detail": str(refusal)},
        )
    return _refused(str(refusal), br_ref)


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def variant_options(request: Any, code: str) -> Response:
    """`GET /template-catalog/{code}/variant-options` — what the *New variant*
    and *Duplicate as variant* dialogs offer (drawing 06, 10, 18).

    Served rather than typed by the screen: the categories are the utility's own
    customer classes and the languages are A4 B's switched-on set, both of which
    change with the utility's data. `taken` lists the combinations that already
    exist so the dialog can say so before the server refuses.
    """
    require_tenant(request)
    _class_or_refuse(code)
    _group, channel = template_service._class_or_refuse(code)
    taken = [
        {"category": row.category, "language": row.language, "variant": str(row.pk)}
        for row in _variants_of(code).order_by("category", "language")
    ]
    return Response(
        {
            "code": code,
            "channel": channel,
            "needs_approval": template_variants.is_legal_notice(code),
            "categories": template_variants.offered_categories(),
            "languages": template_variants.offered_languages(),
            "start_from": list(template_variants.START_FROM),
            "taken": taken,
            "can_edit": _can_edit(request),
        }
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def create_variant(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/new-variant` — *+ New variant* and
    *Duplicate as variant* (A3 A: channel × language × customer category).

    Body: `language` (`default` = the utility's language), `category`
    (`default` = all customers), optional `channel` (must be this class's),
    `start_from` (`published` | `variant` | `blank`), `source_variant` (the
    variant to copy for `variant`), `effective_from` (contracts only), `name`.

    The new variant is a DRAFT — nothing is published. Refused by name: a
    combination that exists, a language the utility has not switched on (A4 B),
    a category it does not have, a channel this class is not.
    """
    require_tenant(request)
    _class_or_refuse(code)
    payload = _payload(request)
    effective_from = _effective_from_or_400(payload.get("effective_from"))
    try:
        made = template_variants.create_variant(
            code=code,
            actor=_actor(request),
            language=payload.get("language"),
            category=payload.get("category"),
            channel=(str(payload.get("channel")) if payload.get("channel") else None),
            start_from=str(payload.get("start_from") or template_variants.START_PUBLISHED),
            source_variant_id=payload.get("source_variant"),
            effective_from=effective_from,
            name=str(payload.get("name") or ""),
        )
    except rendering.RenderRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-026") from refusal
    except template_service.TemplateRefused as refusal:
        raise _variant_refused(refusal, "BR-NOT-006") from refusal
    return Response(
        {
            "variant": _variant_row(made.variant),
            "version": _version_row(made.version) if made.version is not None else None,
            "started_from_version": made.started_from_version,
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def make_live_again(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/make-live-again` — History's action on an
    earlier published version (drawing 07–09, 15).

    Body: `version_id`. Writes a NEW version holding that version's own stored
    wording and publishes it (`outcome: "live"`); the version it replaces stays
    in history and every message already pinned renders what it always did. For
    a legal notice the copy is left as a DRAFT for a System Admin's approval
    (`outcome: "sent_for_approval"`, A1 C) and the live version keeps going out.
    """
    require_tenant(request)
    _class_or_refuse(code)
    source = _version_or_400(code, _payload(request).get("version_id"))
    try:
        made = template_variants.make_live_again(version_row=source, actor=_actor(request))
    except rendering.RenderRefused as refusal:
        raise _refused(str(refusal), "BR-BIL-026") from refusal
    except template_service.TemplateRefused as refusal:
        raise _variant_refused(refusal, "BR-BIL-026") from refusal
    return Response(
        {
            "outcome": made.outcome,
            "version": _version_row(made.version),
            "restored_from_version": made.restored_from_version,
            "replaced_version": made.replaced_version,
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([SystemAdminOnly])
def queue_template_test(request: Any, code: str) -> Response:
    """`POST /template-catalog/{code}/queue-test` — CR-048 B7, from SET-10.

    ⚠ **THE NAME IS THE CONTRACT: IT QUEUES.** BR-NOT-005 and A11 Addendum r2 §4
    make a synchronous send endpoint a gate failure rather than a choice, so
    there is no `send`, no `send-test` and no `test-send` beside this and a test
    asserts those absences as hard as it asserts this presence. What the button
    does is write ONE real row on the outgoing queue, addressed to the person
    who pressed it, and then say plainly whether the dispatcher will send it —
    with the channel's own line (`channel_line`, `DEF-NOT-10537`; this read
    *"say plainly that nothing will leave the building"* until 2026-10-22).
    ⚠ **AND THE SPELLING DIVERGES FROM A11 §11b ON PURPOSE.** The API audit
    lists this as `POST /templates/{id}/send-test`; it is `queue-test` here
    because that is what the notification-rules surface already shipped and one
    product should not name the same act two ways. The divergence is recorded in
    the decision log rather than settled silently.

    ⚠ **THIS IS WHERE THE ROLE IS CHECKED, AND IT IS CHECKED ONCE (DEF-2515).**
    A4 gives Settings & lookup tables to a System Admin in full and to an
    Executive as a view; queueing a row is not viewing. The service behind this
    carries no decorator of its own, because a second check behind the door can
    only ever produce a false refusal.
    """
    require_tenant(request)
    _class_or_refuse(code)
    klass = catalogs.catalog_for(code)
    actor = _actor(request)
    # The OFFER decides, so the enabled control and the endpoint can never
    # disagree — and the refusal a person reads is the same sentence the screen
    # already had beside the disabled button.
    offer = rule_service.template_test_offer(
        code=code, channel=klass.channel if klass is not None else None,
        actor=actor, can_edit=_can_edit(request),
    )
    if not offer.can_test_send or offer.channel is None:
        raise _refused(offer.reason, "BR-SHL-025")
    try:
        result = rule_service.queue_template_test(
            code=code, channel=offer.channel, actor=actor
        )
    except (rule_service.RuleRefused, template_service.TemplateRefused) as refusal:
        raise _refused(str(refusal), "BR-NOT-005") from refusal
    return Response(
        {**result.as_wire(), "channel_line": settings_api.channel_line(offer.channel)}
    )


def _effective_from_or_400(raw: Any) -> date | None:
    """BR-NOT-002's date, off the wire. `None` when the class does not take one.

    Parsed here rather than in the service so the refusal a person sees is a
    FIELD error on the box they typed into. The service still owns the RULE —
    which classes may carry a date and which must — and refuses in both
    directions; this only turns a string into a date or says why it could not.
    """
    if raw in (None, ""):
        return None
    if not isinstance(raw, str):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.templates.effectiveFromFormat",
            field_errors=[{"field": "effective_from", "code": errors.VAL_FORMAT}],
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as bad:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="notifications.templates.effectiveFromFormat",
            field_errors=[{"field": "effective_from", "code": errors.VAL_FORMAT}],
        ) from bad


def _variant_or_400(code: str, raw: Any) -> tm.NotificationTemplate:
    # Tenant-scoped, so another tenant's variant id reads as ABSENT rather than
    # as a permission error — HR-1: existence must not leak (DEF-191).
    variant = _variants_of(code).filter(pk=raw).first() if raw else None
    if variant is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.templates.variantRequired",
            params={
                "detail": (
                    "Name the variant to act on. A template has one variant per (consumer "
                    'category, language), so acting on "the template" would be acting on '
                    "whichever row a query happened to return first."
                )
            },
            field_errors=[{"field": "variant", "code": errors.VAL_REQUIRED}],
        )
    return variant


def _version_or_400(code: str, raw: Any) -> tm.NotificationTemplateVersion:
    version = (
        tm.NotificationTemplateVersion.objects.select_related("template")
        .filter(tenant_id=core_tenancy.current_tenant_id(), template__code=code, pk=raw)
        .first()
        if raw
        else None
    )
    if version is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="notifications.templates.versionRequired",
            params={
                "detail": (
                    'Name the version to act on, by id. There is no "latest" path anywhere '
                    "in this module (BR-BIL-026, US-NOT-005 TC-6): a caller that does not "
                    "hold the version has not read the row it is acting on."
                )
            },
            field_errors=[{"field": "version_id", "code": errors.VAL_REQUIRED}],
        )
    return version


@api_view(["GET"])
@permission_classes([AnyTenantRole])
def template_library(request: Any) -> Response:
    """**THE ONE TEMPLATES LIST — CR-048 task E9, `BR-NOT-026`.**

    S8 → Configure → Templates used to draw TWO lists on one tab: the catalogue
    of everything this utility sends, and, underneath it, billing's bill-layout
    chooser. A person looking for *"the template we print bills on"* had to know
    which of the two panels owned it.

    This serves both as ONE list. Each row says what it stores
    (`content_model`) and which editor it opens (`editor`), because the two
    kinds keep their own editors — the PO's ruling of 2026-08-30 asked for one
    list and one lifecycle and did not ask for one editor, and a text box over a
    layout key would be the wrong screen for both.

    ⚠ **`kind` IS A FILTER, NOT A ROUTE.** Both stores answer the same call and
    neither is the default: omitting it is the whole list, which is the state
    the screen opens in.

    ⛔ **NOTHING HERE READS OR WRITES BILLING'S TABLES.** `unified_templates`
    delegates to `apps.billing.templates_service`, which is the only writer of
    `bill_templates` (B2 §2). This route knows about HTTP and nothing else.
    """
    require_tenant(request)
    kind = request.query_params.get("kind") or None
    try:
        rows = unified_templates.list_templates(kind=kind)
    except unified_templates.UnifiedTemplateRefused as refused:
        raise _refused(str(refused), br_ref="BR-NOT-026") from refused
    return Response(
        {
            "results": [
                {
                    "kind": row.kind,
                    "key": row.key,
                    "name": row.name,
                    "content_model": row.content_model,
                    "editor": row.editor,
                    "live_version": row.live_version,
                    "version_count": row.version_count,
                    "edited": row.edited,
                }
                for row in rows
            ],
            "count": len(rows),
            # The dimension the screen filters on, served rather than hardcoded
            # in the client: a chip for a kind the server does not offer is a
            # filter that returns nothing forever (DEF-782's lesson, applied
            # before it can happen again).
            "kinds": list(unified_templates.KINDS),
        }
    )


urlpatterns = [
    path("template-library", template_library),
    path("template-catalog", template_catalog),
    path("template-catalog/<str:code>", template_detail),
    path("template-catalog/<str:code>/variants", add_variant),
    # CR-190-BRC10 — *Create from our default* (DEF-NOT-10442).
    path("template-catalog/<str:code>/from-default", create_from_default),
    path("template-catalog/<str:code>/preview", preview_body),
    path("template-catalog/<str:code>/draft", save_draft),
    path("template-catalog/<str:code>/publish", publish_version),
    path("template-catalog/<str:code>/deactivate", deactivate_variant),
    path("template-catalog/<str:code>/restore", restore_version),
    # CR-199-BRC10 — the templates redesign's three server actions.
    path("template-catalog/<str:code>/variant-options", variant_options),
    path("template-catalog/<str:code>/new-variant", create_variant),
    path("template-catalog/<str:code>/make-live-again", make_live_again),
    # CR-048 B7. `queue-test` because it QUEUES — BR-NOT-005 forbids a
    # synchronous send route anywhere in this product, and the absence of
    # `send` / `send-test` / `test-send` beside this one is asserted.
    path("template-catalog/<str:code>/queue-test", queue_template_test),
    # CR-049 task 8 — the change trail. A literal segment, so it cannot be
    # confused with any of the action paths above; `<str:version_id>` is
    # resolved as a version of THIS class and 404s otherwise.
    path("template-catalog/<str:code>/changes/<str:version_id>", template_change),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-007@set0910 (12-governance/11-change-requests.md CR-007 + the three PO rulings of 2026-08-16 · 04-docs/01-spec/19-document-templates.md §1/§2/§3 + r8 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-001/002/006/014/015 · 05-prototype/r10-2026-08-16/SMARTBillHub.dc.html SET-09/SET-10)
# generated: 2026-08-17 by story-coder (CR-007 SET-09/10 templates lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every one of the eight paths answered
#         django.urls.exceptions.Resolver404 before `config/urls.py` named this
#         module; the System-Admin gate was proved by calling every write as a
#         billing_clerk; the unknown-token block was proved by saving a body
#         carrying {meter_no} into the receipt class; transcripts in the lane
#         report and in tests/test_cr_007_template_catalog.py
# exceptions: (1) NO TEST SEND, and it is a RULING not a gap — no dispatcher on
#         any channel in R2 (PO: "I already confirm it before it Queue them"),
#         the PO declined resend-invite the same day with "no email yet", and
#         A11 r2 §4 makes a synchronous send endpoint a gate failure. The
#         control renders DISABLED WITH ITS REASON (BR-SHL-025).
#         (2) NO SAMPLE PDF, for a DIFFERENT reason spelled differently: the
#         page writer is billing's and writes bills; OQ-149 closed with no
#         page-render library in the image, so a printable notice renders TEXT.
#         (3) NO "SET DEFAULT" — the default is the row's KEY (BR-NOT-001/006),
#         so setting another variant default is a re-key that would move every
#         pin. Disabled with its reason; OQ-252 with the PO.
#         (4) THE ENDPOINT GATE IS NARROWER THAN THE SERVICE GATE, on purpose.
#         BR-BIL-027 lets a Billing Clerk draft and that rule is untouched; the
#         PO ruled this SETTINGS SURFACE System-Admin-only, so the route is
#         `SystemAdminOnly` and both gates run.
#         (5) "DEACTIVATE" IS `archive` ON THE LIVE VERSION — no `active`
#         column was added, because a variant is live exactly when it has a
#         published version and a second word for "archived" is how a screen
#         shows a template that renders nothing.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
