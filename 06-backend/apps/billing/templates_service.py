# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (template CRUD, append-only versions, publish rights)
#           Screens: S8 (Settings → Templates tab) · S91 · S92 · S93
# Rules:    BR-BIL-025 (assignment defaults by consumer category, overridable
#           per account; resolution order override → category default) ·
#           BR-BIL-026 (edit = a NEW version; one PUBLISHED per template;
#           publishing affects only FUTURE bills — AMENDED 2026-08-12 by
#           OQ-149: 3–5 PLATFORM layouts, no tenant-authored design) ·
#           BR-BIL-027 (Billing Clerk creates/edits drafts + test-prints;
#           System Admin publishes; a version PINNED by ANY bill can never be
#           deleted — audit-lock) · BR-TEN-043 (event time is an argument) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (audit)
# Tests:    06-backend/tests/test_us_bil_021_templates.py
# Impacts:  apps/billing/template_models.py (the rows) · apps/billing/
#           documents.py (renders the pinned version) · apps/billing/issue.py
#           (stamps the pin at issue — US-BIL-022)
# ───────────────────────────────────────────────────────
"""The template version lifecycle: draft → published → archived, append-only.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides which document a
customer was sent and which versions can never be removed, which is the
reproducibility half of a money record. AI-authored 2026-08-15 under the PO
ruling of 2026-08-09; row owed in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
THE THREE RULES, AND WHAT EACH ONE IS ACTUALLY PROTECTING
════════════════════════════════════════════════════════════════════════════
**BR-BIL-026 — an edit is a NEW VERSION, never an edit.** `invoices.
template_version` is stamped at issue and frozen with the money, and
`documents.render_invoice` resolves its layout from that pin and from nothing
else. If a published version's content could change, every bill already pinned
to it would silently start rendering differently — history rewritten without a
single UPDATE to an invoice. So `save_draft` creates rows and `publish`
transitions them; there is no function here that edits published content, and
the database refuses it too (migration `0019`).

**BR-BIL-026 — publishing affects only FUTURE bills.** That is not a rule this
module enforces so much as one it cannot break: publishing moves a status, and
nothing anywhere reads "the latest published version" to render an ISSUED bill.
`documents._layout_for` takes the pinned number and `documents.
LATEST_REGISTERED_VERSION` carries a comment saying in as many words that it is
never consulted on the render path.

**BR-BIL-027 — the audit-lock.** A version pinned by any bill can never be
deleted. `archive` is always available and `delete_version` counts the pins
first. The count is over `invoices.template_id` + `.template_version`, which are
plain columns rather than a foreign key — r10 #3 pinned them before this table
existed, so an FK now would refuse every historical row (`models.Invoice` says
so of itself).

════════════════════════════════════════════════════════════════════════════
WHAT V1 LETS A TENANT CHOOSE — PO 2026-08-12, OQ-149
════════════════════════════════════════════════════════════════════════════
Verbatim: *"out platform will porvide standard 3 to 5 variouation of printed
bill - user can use those only in V1"*. A version names a `layout_key` from
`PLATFORM_LAYOUTS` and carries the tenant's `options` (its bill messages and
footer — BR-BIL-021 — plus per-layout switches). `save_draft` REFUSES a
`layout_key` the platform does not publish, which is the whole of the narrowing
expressed as one check: a tenant cannot smuggle in a layout, so nothing has to
render one, so no HTML/CSS engine and no ~200MB font-shaping tree enters the
deployment image.

⚠ **THIS PARAGRAPH SAID THE PLATFORM SHIPPED ONE LAYOUT AND IT IS REWRITTEN
RATHER THAN LEFT STANDING (hard-won law 1).** It shipped one, said so, and
REPORTED the gap rather than padding the registry with keys that would all
resolve to the same page. **The PO closed it on 2026-08-16**, verbatim: *"why
cant we give 5 differnt tempaltes to start with and ask user to choose anyone;
we will ahve 1 default tempalte allways"* — which also CUT the S91–S96 designers
from R2. So `documents.LAYOUT_SPECS` now holds five, `documents.LAYOUTS_BY_KEY`
renders each of them differently, `PLATFORM_LAYOUTS` below is derived from that
registry rather than asserting alongside it, and what a tenant does is CHOOSE.

The constraint that kept the registry at one has not been relaxed — it has been
met. Each of the five removes or moves a whole A19 section, so no two of them
render one bill identically, and a test asserts exactly that.

════════════════════════════════════════════════════════════════════════════
⚠ THE ROLE GATE IS DECLARED HERE AND ENFORCED WHERE ROLES LIVE
════════════════════════════════════════════════════════════════════════════
BR-BIL-027 splits the rights: a Clerk drafts and test-prints, a System Admin
publishes. `publish` takes an `actor` and refuses one whose role is not the
admin role, using `core.permissions` the same way the rest of this codebase
does. What this module does NOT do is invent a permission: if the actor carries
no resolvable role the call is refused rather than allowed, because a publish
that fell open would put an unreviewed page in front of every customer.

════════════════════════════════════════════════════════════════════════════
⚠ OVERLAP WITH `apps/notifications` — REPORTED, NOT DUPLICATED
════════════════════════════════════════════════════════════════════════════
US-NOT-006 declares `depends_on: [US-BIL-021, …]` and generalises BR-BIL-026 and
BR-BIL-027 to every designer S91+. Its tables are not built and
`apps/notifications/rendering.py` currently takes the version as an argument and
looks nothing up. **This module is the canonical implementation of those
transitions.** Whether notifications reuses it or a shared kernel is extracted
is a cross-module call above a story lane — see `template_models.py`'s docstring
and the lane report. Nothing here was copied from notifications and nothing here
should be copied INTO it without that decision being taken by someone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db import transaction

from apps.billing import delivery_seam, models, template_models
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import (
    TEMPLATE_TYPES,
    TYPE_BILL,
    VERSION_ARCHIVED,
    VERSION_DRAFT,
    VERSION_PUBLISHED,
    BillTemplate,
    BillTemplateVersion,
)
from core import audit
from core import tenancy as core_tenancy


@dataclass(frozen=True)
class PlatformLayout:
    """One of the platform's ready-made printed-bill layouts (OQ-149).

    `key` is what a version stores and what `documents._layout_for` resolves.
    `renders` is TRUE only when `documents.LAYOUTS_BY_KEY` actually holds a
    renderer for that key — so a reader can tell a real variant from one that is
    still owed without running anything, and the chooser can refuse to offer one
    that would print as something else.

    `summary` is written for the person choosing, not for the schema: a clerk
    picks a bill layout once, from a list, and "Compact — description and
    amount only, no per-service band" is a decision they can take where
    `compact-letter-v1` is a string to go and look up.
    """

    key: str
    label: str
    summary: str
    template_type: str
    renders: bool


#: ⚠ **THE LIBRARY — FIVE, PER THE PO's RULING OF 2026-08-16.** Verbatim: *"why
#: cant we give 5 differnt tempaltes to start with and ask user to choose
#: anyone; we will ahve 1 default tempalte allways"*.
#:
#: This tuple used to hold ONE entry with the gap REPORTED beside it, and the
#: reason it held one is worth keeping: *"a chooser offering four identical
#: options is worse than one offering one honest one."* That constraint has not
#: been relaxed — it has been MET. Every key below is backed by a distinct
#: `documents.LayoutSpec` that removes or moves a whole A19 section, so the five
#: differ on the paper and in the HTML, and `test_us_bil_021_templates` asserts
#: that no two of them render one bill identically.
_LAYOUT_CATALOG: tuple[tuple[str, str, str], ...] = (
    (
        "standard-letter-v1",
        "Standard",
        "US Letter. Per-service band, usage and rate columns, summary box under the "
        "charges, remittance stub to tear off and return with a cheque.",
    ),
    (
        "compact-letter-v1",
        "Compact",
        "US Letter. Description and amount only — no usage or rate columns and no "
        "per-service band. For flat-rate services and short bills, where the usage "
        "columns print the same figure twice.",
    ),
    (
        "summary-first-letter-v1",
        "Amount due first",
        "US Letter. The summary box sits directly under the bill details, above the "
        "charges, so the amount due is the first figure on the page.",
    ),
    (
        "no-stub-letter-v1",
        "No remittance stub",
        "US Letter, standard layout, with the tear-off stub omitted. For a utility "
        "collecting by direct debit or portal, where a stub nobody returns is a wasted "
        "third of the page.",
    ),
    (
        "letterhead-letter-v1",
        "Pre-printed letterhead",
        "US Letter. The masthead is left off and space is reserved at the top of the "
        "page, for a utility printing onto its own pre-printed stationery.",
    ),
)


def _platform_layouts() -> tuple[PlatformLayout, ...]:
    """The library, with `renders` READ OFF THE RENDERER — never asserted here.

    Hard-won law 1: *a comment claiming a guarantee is not the guarantee*. A
    hand-written `renders=True` beside a key would keep saying "this prints" for
    exactly as long as it took somebody to remove the spec, and the chooser
    would keep offering a layout that silently printed as something else. So the
    flag is a membership test against `documents.LAYOUTS_BY_KEY`, and a key with
    no renderer arrives at the chooser marked as not-renderable rather than
    presented as a choice.
    """
    from apps.billing import documents

    return tuple(
        PlatformLayout(
            key=key,
            label=label,
            summary=summary,
            template_type=TYPE_BILL,
            renders=key in documents.LAYOUTS_BY_KEY,
        )
        for key, label, summary in _LAYOUT_CATALOG
    )


PLATFORM_LAYOUTS: tuple[PlatformLayout, ...] = _platform_layouts()

#: What is OWED against the ruling, carried as data so a caller can surface it
#: rather than discover it. Same discipline as `issue.ISSUE_UNAVAILABLE`.
TEMPLATES_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "tenant_authors_no_layout_of_its_own",
        "br_ref": "BR-BIL-026 · OQ-149 (CLOSED 2026-08-12, extended 2026-08-16)",
        # History, for the next engineer: this said the platform publishes ONE
        # layout; five ship as of 2026-08-16, so it was rewritten rather than
        # left standing (hard-won law 1). The library is
        # `documents.LAYOUT_SPECS`, the chooser is `GET /bill-templates`, and
        # the PO cut the S91–S96 designers from R2 (*"why cant we give 5
        # differnt tempaltes to start with and ask user to choose anyone"*) —
        # so this is a RULING, not a gap.
        "detail": "You choose from the layouts we provide; you cannot design a page of "
        "your own here. That means no colours, no logo placement, no usage graph and no "
        "barcode. If you need one of those on your bills, talk to us.",
    },
    {
        "code": "account_level_override_not_stored_here",
        "br_ref": "BR-BIL-025",
        # The category half is `bill_templates.category` and is built. The
        # per-account override is a customers-module attribute with no column
        # yet; `resolve_for` takes it as an argument and implements the full
        # order (override → category default → fallback) regardless.
        "detail": "A layout can be set for a whole customer category, but not yet for one "
        "individual account. Every account in a category gets that category's layout.",
    },
    {
        "code": "nothing_stops_a_second_fallback_template",
        "br_ref": "BR-BIL-025",
        # ⚠ ENGINEERING NOTE, deliberately not on screen. A template with NO
        # category is the tenant's fallback and BR-BIL-025 needs exactly one,
        # but `uq_bill_templates_category` is PARTIAL on a non-null category, so
        # the schema permits two and `resolve_for` would take whichever came
        # first — a coin toss over which page a customer receives. Nothing can
        # currently produce that state: provisioning seeds exactly one (DEF-123)
        # and no surface can add a second. REPORTED rather than closed because
        # closing it is a unique index — a migration on a 🔒 path — and it
        # belongs to the story that builds the screen that could create it.
        # The customer-facing sentence says only what a utility can act on.
        "detail": "Exactly one layout is the fallback for customers with no category, and "
        "it is set up for you. You cannot add a second one here.",
    },
    {
        "code": "no_template_crud_only_a_chooser",
        "br_ref": "BR-BIL-027 · OQ-149",
        # History: corrected twice in two days. It first said the whole
        # lifecycle was unreachable (DEF-123, closed by seeding at
        # provisioning), then that the tab had no endpoint —
        # `GET /bill-templates` and `POST /bill-templates/layout` are mounted in
        # `apps/billing/templates_api.py`. STILL NOT SERVED: `create_template`,
        # `archive`, `delete_version` — built, reachable from code and tests
        # only, deliberately, because a second template is what would create the
        # two-fallback collision the entry above describes.
        "detail": "You can choose which layout this utility uses, and every bill already "
        "sent keeps the layout it was printed on. Adding a layout of your own, or "
        "archiving or deleting one, is not offered here.",
    },
    {
        "code": "issue_resolves_the_run_pin_here_but_not_per_account",
        "br_ref": "BR-BIL-025 · BR-BIL-026 · US-BIL-022",
        # History: this said `resolve_for` had no production caller, which
        # stopped being true — `apps/billing/api._template_pin_for` resolves the
        # pin through this service on `POST /billing/runs/{id}/issue`. It
        # resolves ONCE FOR THE RUN while BR-BIL-025 resolves per ACCOUNT;
        # `issue.issue_invoice` takes one `template_id`/`template_version` for
        # the whole pass. Every tenant today has exactly one bill template, so
        # nothing is currently mis-pinned. Per-account resolution inside the
        # issue loop is US-BIL-022's territory and is owed.
        "detail": "A billing run prints every bill in it on the same layout. Choosing a "
        "different layout for particular accounts within one run is not offered yet — "
        "today every utility has one layout, so no bill is affected.",
    },
)

#: BR-BIL-027's publishing right. Resolved through the same role vocabulary the
#: rest of the codebase uses rather than a string invented here.
PUBLISH_ROLE = "system_admin"
DRAFT_ROLES = ("system_admin", "billing_clerk")


def _tenant_id() -> Any:
    """Hard rule 1: never touch a tenant table without `app.tenant_id` set."""
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _role_of(actor: Any) -> str | None:
    return getattr(actor, "role", None)


def _actor_id(actor: Any) -> Any:
    # `core.audit.actor_user_id` is the one answer to this (DEF-BIL-5090).
    return audit.actor_user_id(actor)


def layout_or_refuse(layout_key: str, *, template_type: str) -> PlatformLayout:
    """OQ-149's narrowing, as one check.

    A tenant chooses one of the platform's variants and nothing else. Refusing
    an unknown key here is what keeps tenant-authored markup out of the system:
    if no key can name a page the platform did not write, nothing ever has to
    render one, and the HTML/CSS engine that would have been needed to render
    one never enters the image.
    """
    for layout in PLATFORM_LAYOUTS:
        if layout.key == layout_key and layout.template_type == template_type:
            return layout
    known = ", ".join(
        entry.key for entry in PLATFORM_LAYOUTS if entry.template_type == template_type
    )
    raise BillingRuleError(
        f"{layout_key!r} is not one of the platform's printed-{template_type} layouts. The "
        f"PO ruled on 2026-08-12 (OQ-149) that v1 offers the platform's own 3 to 5 "
        f'variations and no tenant-authored design — *"user can use those only in V1"* — '
        f'and again on 2026-08-16: *"why cant we give 5 differnt tempaltes to start with '
        f'and ask user to choose anyone; we will ahve 1 default tempalte allways"*. This '
        f"build publishes {known or 'none'}. A tenant chooses a layout, its category "
        "assignment, its bill messages and its footer — it does not design the page.",
        br_ref="BR-BIL-026",
    )


@transaction.atomic
def create_template(
    *,
    name: str,
    template_type: str,
    category: str | None = None,
    actor: Any = None,
) -> BillTemplate:
    """A tenant's template — "Bill · residential" (BR-BIL-025's assignment row)."""
    if template_type not in TEMPLATE_TYPES:
        raise BillingRuleError(
            f"{template_type!r} is not a printed template type; this table holds "
            f"{', '.join(TEMPLATE_TYPES)}. Email, SMS and contract templates are "
            "notifications' (US-NOT-006) and are a different table on purpose — EP-BIL-06 "
            "puts them out of scope in as many words.",
            br_ref="BR-BIL-025",
        )
    # BR-CUS-094a (PO 2026-09-17) — the categories are this TENANT's own
    # `account_types` rows, read at call time. A four-name constant here could
    # not see a class the utility invented, which is the ruling exactly.
    known_categories = template_models.categories()
    if category is not None and category not in known_categories:
        raise BillingRuleError(
            f"{category!r} is not a consumer category; BR-BIL-025 names "
            f"{', '.join(known_categories)}. A template with no category is the tenant's "
            "fallback for its type, which every tenant needs exactly one of.",
            br_ref="BR-BIL-025",
        )
    template = BillTemplate.objects.create(
        tenant_id=_tenant_id(), name=name, template_type=template_type, category=category
    )
    audit.money_action(
        actor,
        "template.created",
        "bill_templates",
        str(template.pk),
        after={"name": name, "type": template_type, "category": category},
    )
    return template


@transaction.atomic
def save_draft(
    template: BillTemplate,
    *,
    layout_key: str,
    options: dict[str, Any] | None = None,
    actor: Any = None,
) -> BillTemplateVersion:
    """TC-1 — an edit is a NEW DRAFT VERSION, append-only (BR-BIL-026).

    Priya edits "Bill · residential" and v4 appears; v3 stays published and
    completely untouched, which is the guarantee every bill already pinned to v3
    depends on.

    `version_no` is the template's highest plus one and NEVER a reused number:
    `invoices.template_version` is frozen at issue, so a recycled number would
    make a 2026 bill render on a 2031 page while every row still looked correct.
    Allocated inside the transaction under the unique constraint, so two clerks
    saving at once collide rather than both taking v4.
    """
    role = _role_of(actor)
    if role is not None and role not in DRAFT_ROLES:
        raise BillingRuleError(
            f"a {role!r} does not create template drafts. BR-BIL-027 gives drafting and "
            f"test-printing to {' and '.join(DRAFT_ROLES)}; publishing is narrower still.",
            br_ref="BR-BIL-027",
        )
    layout_or_refuse(layout_key, template_type=template.template_type)
    tenant_id = _tenant_id()
    highest = (
        BillTemplateVersion.objects.filter(tenant_id=tenant_id, template=template)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
        or 0
    )
    version = BillTemplateVersion.objects.create(
        tenant_id=tenant_id,
        template=template,
        version_no=highest + 1,
        status=VERSION_DRAFT,
        layout_key=layout_key,
        options=dict(options or {}),
        created_by_id=_actor_id(actor),
    )
    audit.money_action(
        actor,
        "template.saved",
        "bill_template_versions",
        str(version.pk),
        after={
            "template_id": str(template.pk),
            "version_no": version.version_no,
            "status": VERSION_DRAFT,
            "layout_key": layout_key,
        },
    )
    return version


@transaction.atomic
def publish(version: BillTemplateVersion, *, actor: Any, on_date: date) -> BillTemplateVersion:
    """TC-2 — **System Admin only**, and the incumbent is archived with it.

    BR-BIL-027 gives publishing to the System Admin and the check is SERVER-SIDE:
    a disabled button is a courtesy, not a gate, and the epic's TC-2 says in as
    many words that a Clerk's publish is *"absent/disabled-with-reason **and**
    server-rejected"*.

    One published per template (BR-BIL-026) is held in TWO places on purpose:
    this function archives the incumbent in the same transaction, and
    `uq_bill_template_one_published` refuses a second one if it does not. The
    index is the one that survives a race; the archive is what makes the outcome
    the RIGHT one rather than merely a refusal.

    ⚠ **PUBLISHING TOUCHES NO ISSUED BILL, AND CANNOT.** A bill carries its own
    pin, frozen with its money, and `documents` resolves the layout from that pin
    alone. BR-BIL-026's *"publishing affects only future bills"* is therefore
    structural rather than a rule this function has to remember to honour.

    `on_date` is a PARAMETER, never a clock read (BR-TEN-043).
    """
    if _role_of(actor) != PUBLISH_ROLE:
        raise BillingRuleError(
            f"publishing a bill template is a {PUBLISH_ROLE} action and this actor is "
            f"{_role_of(actor)!r} (BR-BIL-027). A Billing Clerk drafts and test-prints; "
            "publishing puts a page in front of every customer the template is assigned "
            "to, which is why it is the narrower right. The check is server-side: a "
            "disabled button is a courtesy, not a gate.",
            br_ref="BR-BIL-027",
        )
    if version.status != VERSION_DRAFT:
        raise BillingRuleError(
            f"version {version.version_no} is {version.status!r} and only a DRAFT is "
            "published (BR-BIL-026). Re-publishing an archived version would make the "
            "same version number mean two different live periods, and a bill pinned to it "
            "could not say which one it was rendered under.",
            br_ref="BR-BIL-026",
        )
    tenant_id = _tenant_id()
    incumbent = BillTemplateVersion.objects.filter(
        tenant_id=tenant_id, template=version.template, status=VERSION_PUBLISHED
    ).first()
    if incumbent is not None:
        incumbent.status = VERSION_ARCHIVED
        incumbent.save(update_fields=["status", "updated_at"])
        audit.money_action(
            actor,
            "template.archived",
            "bill_template_versions",
            str(incumbent.pk),
            before={"status": VERSION_PUBLISHED},
            after={
                "status": VERSION_ARCHIVED,
                "superseded_by_version_no": version.version_no,
                "on_date": on_date.isoformat(),
            },
        )
    version.status = VERSION_PUBLISHED
    version.published_by_id = _actor_id(actor)
    version.published_on = on_date
    version.save(update_fields=["status", "published_by", "published_on", "updated_at"])
    audit.money_action(
        actor,
        "template.published",
        "bill_template_versions",
        str(version.pk),
        before={"status": VERSION_DRAFT},
        after={
            "status": VERSION_PUBLISHED,
            "version_no": version.version_no,
            "on_date": on_date.isoformat(),
            "affects": "future bills only — issued bills carry their own frozen pin",
        },
    )
    return version


def pin_count(version: BillTemplateVersion) -> int:
    """How many SENT DOCUMENTS are pinned to this version — BR-BIL-027's number.

    Counted over `invoices.template_id` + `.template_version`, which are PLAIN
    COLUMNS and not a foreign key. r10 #3 pinned them before this table existed
    (`models.Invoice` records that), so an FK added now would refuse every
    invoice issued in the meantime — and refusing history to tidy a schema is
    the wrong trade on a money table.

    ⚠ **IT COUNTED `invoices` ALONE UNTIL `DEF-2496` (2026-08-30), AND THAT WAS
    SHORT BY A WHOLE PIN SOURCE.** `outbound_messages.template_id` is
    POLYMORPHIC and nothing said so: measured on the development database, of
    its 181 rows **94 carry a BILL template's id** — every one a `pdf_print` row
    whose `source_type` is `invoice`. So a bill layout pinned by a printed bill
    and by no issued invoice read as UNPINNED here, and `delete_version` — the
    function that exists to refuse exactly that — allowed the delete. BR-NOT-025
    says *any sent document*, and a printed bill is one.

    The print rows are asked for through `delivery_seam` by name, never by
    reading another module's table (B1). ⚠ **AN UNASKABLE COUNT IS NOT ZERO.**
    When notifications publishes no read the seam answers `None`, and this
    RAISES rather than returning the invoice count on its own: a delete allowed
    because a question could not be asked is the shape DEF-127 was about.

    **AND THIS IS THE READABLE HALF.** The guarantee is `billing/0025`'s
    `trg_bill_tpl_version_pin_locked`, which counts both tables in the engine.
    A caller that never calls this function still cannot delete a pinned row.
    """
    bills = models.Invoice.objects.filter(
        tenant_id=version.tenant_id,
        template_id=version.template_id,
        template_version=version.version_no,
    ).count()
    prints = delivery_seam.template_print_pin_count(version.template_id, version.version_no)
    if prints is None:
        raise BillingRuleError(
            f"whether version {version.version_no} is pinned by a printed bill cannot be "
            "determined: apps.notifications.selectors.template_pin_count is not published, "
            "so the delivery queue cannot be asked. This is REFUSED rather than counted as "
            "zero — deleting a template version because a question could not be asked is "
            "how a sent document becomes unreproducible (BR-NOT-025). Archive it instead.",
            br_ref="BR-NOT-025",
        )
    return bills + prints


@transaction.atomic
def archive(
    version: BillTemplateVersion, *, actor: Any, on_date: date, at: datetime | None = None
) -> BillTemplateVersion:
    """Retire a version. ALWAYS available — archive is the answer delete is not.

    ⚠ **`archived_at` IS STAMPED HERE SINCE CR-048 TASK E9 (`BR-NOT-025`).** The
    status flip and the audit row both existed before; the TABLE could not say
    *when*, so the version list on the one Templates screen (`BR-NOT-026`) would
    have shown a date for a notification template and a blank for a bill layout
    doing the same thing. `at` is a caller-supplied instant for the same reason
    `on_date` is (BR-TEN-043 — a business date is an argument, never a clock
    read); the notification side takes the same argument with the same default.
    """
    if version.status == VERSION_ARCHIVED:
        return version
    before = version.status
    version.status = VERSION_ARCHIVED
    version.archived_at = at or version.updated_at
    version.save(update_fields=["status", "archived_at", "updated_at"])
    audit.money_action(
        actor,
        "template.archived",
        "bill_template_versions",
        str(version.pk),
        before={"status": before},
        after={"status": VERSION_ARCHIVED, "on_date": on_date.isoformat()},
    )
    return version


@transaction.atomic
def delete_version(version: BillTemplateVersion, *, actor: Any) -> None:
    """TC-4 — **the audit-lock** (BR-BIL-027). A pinned version is never deleted.

    *"v3 delete attempted while pinned by 1,124 issued bills → Blocked; archive
    allowed, delete never. An unpinned draft version deletes fine."*

    The reason is reproducibility, not tidiness: `documents.render_invoice`
    renders a bill from its pinned version, and a bill whose version is gone can
    never be reprinted as it was sent. The retention window is seven years (B4,
    PO Q&A R1), so "nobody will reprint that" is not a judgement this code is
    allowed to make.

    The refusal NAMES THE COUNT, because "you cannot delete this" without a
    number invites somebody to go looking for a way round it.
    """
    pinned = pin_count(version)
    if pinned:
        raise BillingRuleError(
            f"version {version.version_no} of {version.template.name!r} is pinned by "
            f"{pinned} issued bill(s) and can never be deleted (BR-BIL-027, the "
            "audit-lock). Each of those bills renders from THIS version whenever it is "
            "reprinted, re-sent or disputed, for the full seven-year retention window — "
            "deleting it would leave them unreproducible. Archive it instead: an archived "
            "version stops being offered for new assignments and keeps rendering every "
            "bill already pinned to it.",
            br_ref="BR-BIL-027",
        )
    if version.status == VERSION_PUBLISHED:
        raise BillingRuleError(
            f"version {version.version_no} is PUBLISHED. Publish a replacement or archive "
            "it — a template whose live version simply vanished would leave the next bill "
            "run with nothing to pin (BR-BIL-026).",
            br_ref="BR-BIL-026",
        )
    version_id, version_no = str(version.pk), version.version_no
    template_id = str(version.template_id)
    version.delete()
    audit.money_action(
        actor,
        "template.version_deleted",
        "bill_template_versions",
        version_id,
        before={"template_id": template_id, "version_no": version_no, "pinned_by": 0},
        after={"deleted": True, "reason": "unpinned draft — the audit-lock does not bind"},
    )


def published_version(template: BillTemplate) -> BillTemplateVersion | None:
    """The one live version, or None. Single-valued by index, not by luck."""
    return BillTemplateVersion.objects.filter(
        tenant_id=template.tenant_id, template=template, status=VERSION_PUBLISHED
    ).first()


#: The name of the row every tenant is seeded. It is an INTERNAL label: the
#: rendered document carries `template_version` and never the template's name
#: (see `documents._document_dict`), so this string is what a clerk sees in S8's
#: Templates tab and nothing a customer ever reads. Renaming it is a tenant's
#: right and nothing here re-asserts it — the seeder is insert-missing.
SEED_TEMPLATE_NAME = "Standard bill"
#: The layout a NEW tenant starts on, before anybody has chosen. It is the
#: PO's *"we will ahve 1 default tempalte allways"* expressed as a constant: a
#: tenant that never opens the chooser still has a layout, and it is the one the
#: whole back catalogue of this product already prints on. Named rather than
#: taken from `PLATFORM_LAYOUTS[0]` by position — re-ordering that tuple must
#: not repaper a utility.
SEED_LAYOUT_KEY = "standard-letter-v1"


@transaction.atomic
def seed_platform_default(*, on_date: date, actor: Any = None) -> dict[str, Any]:
    """DEF-123 — **the tenant's fallback bill template, planted at provisioning.**

    ⚠ **WHY THIS FUNCTION EXISTS, AND IT IS THE WHOLE OF DEF-123.** This module
    landed on 2026-08-15 with `resolve_for` implementing BR-BIL-025's resolution
    order in full and its own tests passing — *against rows the TESTS created*.
    In the product no row was ever created: S8's Templates tab has no endpoint,
    provisioning seeded the chart of accounts, the number series and the
    holidays and had no billing seeder, and no migration planted a default. So
    `resolve_for` refused *"this tenant has no bill template … and no fallback"*
    for EVERY tenant, BR-BIL-026 makes the pin non-optional, and **no bill could
    be issued on any deployment.** The engine was built, tested and correct, and
    the thing that would put a row in front of it did not exist. That is
    hard-won law 2 — *built is not wired* — applied to DATA rather than to a
    component prop, which is why G13 looked straight past it.

    **THE SHAPE IS `ledger.seed_chart_of_accounts`', deliberately.** Tenancy
    calls it through a seam resolved BY NAME at provisioning, inside the
    provisioning transaction, and it is INSERT-MISSING: a re-run is a repair
    run, never an overwrite of a tenant's own edit. It writes billing's own
    tables and billing's own audit rows; tenancy never touches this ORM
    (B1 / BR-TEN-013).

    **WHY IT WRITES A PUBLISHED VERSION DIRECTLY RATHER THAN CALLING
    `save_draft` + `publish`.** `publish` is BR-BIL-027's narrow right and its
    check is *server-side, on the actor's role* — a Billing Clerk's publish is
    refused. There is no human in a provisioning transaction, so routing the
    seed through it would mean handing it a synthetic actor carrying a role
    nobody granted, which is exactly the invention `publish` exists to refuse.
    The seed therefore writes its own rows and SAYS SO in the audit trail
    (`source: provisioning_seed`), the same posture `seed_chart_of_accounts`
    takes for the ledger's 22 accounts. **BR-BIL-026 is not weakened by this:**
    the row is written PUBLISHED because only a published version is pinnable,
    the one-published-per-template partial unique index still governs it, and
    the content freeze (migration 0019) binds it the instant it exists — a
    seeded version is as un-editable as any other.

    **IT IS NOT CALLED FROM `POST /billing/runs/{id}/issue`, ON PURPOSE.**
    Seeding a tenant's billing template as a side effect of billing would make
    the first bill run the thing that decides what every future bill looks
    like. Provisioning is where a tenant's rows come from.

    `on_date` is BR-TEN-043's business date and is the CALLER's — there is no
    clock here.

    Returns `{"created": bool, "template_id": str, "version_no": int,
    "already_present": bool, "reason": str}` so a caller can report what landed
    rather than infer it.
    """
    tenant_id = _tenant_id()
    template = BillTemplate.objects.filter(
        tenant_id=tenant_id, template_type=TYPE_BILL, category__isnull=True
    ).first()
    if template is not None:
        live = published_version(template)
        if live is not None:
            return {
                "created": False,
                "already_present": True,
                "template_id": str(template.pk),
                "version_no": live.version_no,
                "reason": (
                    f"tenant already has the fallback bill template {template.name!r} with "
                    f"published version {live.version_no} — insert-missing left it untouched"
                ),
            }
    else:
        template = BillTemplate.objects.create(
            tenant_id=tenant_id,
            name=SEED_TEMPLATE_NAME,
            template_type=TYPE_BILL,
            category=None,  # BR-BIL-025's FALLBACK — the answer for any category
        )
        audit.money_action(
            actor,
            "template.created",
            "bill_templates",
            str(template.pk),
            after={
                "name": SEED_TEMPLATE_NAME,
                "type": TYPE_BILL,
                "category": None,
                "source": "provisioning_seed",
            },
        )
    # A template with NO published version reaches here too — a tenant that
    # archived its only live version has a template that cannot be pinned, and
    # the repair is the same insert.
    layout = layout_or_refuse(SEED_LAYOUT_KEY, template_type=TYPE_BILL)
    highest = (
        BillTemplateVersion.objects.filter(tenant_id=tenant_id, template=template)
        .order_by("-version_no")
        .values_list("version_no", flat=True)
        .first()
        or 0
    )
    version = BillTemplateVersion.objects.create(
        tenant_id=tenant_id,
        template=template,
        version_no=highest + 1,
        status=VERSION_PUBLISHED,
        layout_key=layout.key,
        # EMPTY, and that is a fact rather than a placeholder: BR-BIL-021's bill
        # messages and footer are the TENANT's copy and nobody has written any.
        options={},
        published_on=on_date,
        # `created_by` and `published_by` are LEFT NULL, and the null is the
        # true answer rather than a missing one: **no person published this.**
        # They are FKs into `identity.users` (PROTECT), and the provisioning
        # actor is a shim carrying the owner's id — writing it here would claim
        # a human authorised a page they have never seen, and on a deployment
        # whose identity seam is stubbed it would be a foreign key into a user
        # that does not exist. WHO did it is in the audit row below, as
        # `source: provisioning_seed`.
        created_by_id=None,
        published_by_id=None,
    )
    audit.money_action(
        actor,
        "template.published",
        "bill_template_versions",
        str(version.pk),
        after={
            "template_id": str(template.pk),
            "version_no": version.version_no,
            "status": VERSION_PUBLISHED,
            "layout_key": layout.key,
            "on_date": on_date.isoformat(),
            "source": "provisioning_seed",
            "affects": "future bills only — issued bills carry their own frozen pin",
        },
    )
    return {
        "created": True,
        "already_present": False,
        "template_id": str(template.pk),
        "version_no": version.version_no,
        "reason": (
            f"seeded the platform default {SEED_TEMPLATE_NAME!r} on layout {layout.key!r} "
            f"as published version {version.version_no} (BR-BIL-025 fallback)"
        ),
    }


def tenant_fallback_template() -> BillTemplate | None:
    """The ONE template BR-BIL-025 calls the tenant's fallback, or None.

    The fallback is the template with NO consumer category — the answer for any
    account whose category has no template of its own. Every tenant is seeded
    exactly one (`seed_platform_default`) and this build's only writer of
    `bill_templates` is that seeder, so "the first row" and "the only row" are
    the same row today. `TEMPLATES_UNAVAILABLE`'s
    `nothing_stops_a_second_fallback_template` is why that is stated rather than
    assumed: the partial unique index does not cover a NULL category, so the
    schema would permit two, and the chooser deliberately creates no template at
    all so that no human can produce the collision.
    """
    return BillTemplate.objects.filter(
        tenant_id=_tenant_id(), template_type=TYPE_BILL, category__isnull=True
    ).first()


@transaction.atomic
def choose_layout(
    *, layout_key: str, options: dict[str, Any] | None = None, actor: Any, on_date: date
) -> dict[str, Any]:
    """**THE CHOOSER — the PO's ruling of 2026-08-16, as one call.**

    Verbatim: *"why cant we give 5 differnt tempaltes to start with and ask user
    to choose anyone; we will ahve 1 default tempalte allways"*. So there is no
    designer: the platform publishes `PLATFORM_LAYOUTS` and a tenant picks one.

    ⚠ **CHOOSING IS A NEW VERSION, NOT AN EDIT, AND THAT IS THE WHOLE DESIGN.**
    This function calls `save_draft` and then `publish` — the same two
    transitions any other change makes — because BR-BIL-026 says a published
    version's content can never move. So:

      · every bill ALREADY ISSUED keeps rendering exactly as it was sent, on the
        version its own pin names (BR-CUS-040). Changing the tenant's layout
        cannot reach back into a single customer's document.
      · the change is dated, attributed and audited twice (the archive of the
        incumbent and the publish of the successor), so *"why does August's bill
        look different from July's?"* has an answer that is a query.
      · **exactly one version is published at any moment** — held by
        `publish`'s in-transaction archive AND by `uq_bill_template_one_published`
        — which is the PO's own *"1 default tempalte allways"* enforced by the
        database rather than by this function remembering.

    **A NO-OP IS A NO-OP.** Re-choosing the layout that is already live returns
    the live version untouched rather than minting an identical successor:
    version numbers are frozen into bills forever, and burning one on a change
    that changes nothing makes the chain harder to read for no gain.

    **IT CREATES NO TEMPLATE ROW.** The tenant's fallback is seeded at
    provisioning and this function refuses when it is missing rather than
    seeding one as a side effect — for `seed_platform_default`'s own reason:
    provisioning is where a tenant's rows come from, and a second null-category
    template is a collision `resolve_for` would settle with a coin toss.

    `actor` must hold the publish right; `publish` enforces it server-side.
    `on_date` is BR-TEN-043's business date and is the CALLER's — no clock.
    """
    template = tenant_fallback_template()
    if template is None:
        raise BillingRuleError(
            "this tenant has no bill template to put a layout on. One is planted at "
            "provisioning (DEF-123) and choosing a layout deliberately does not create "
            "one — BR-BIL-025 needs exactly ONE fallback template and a second would make "
            "which page a customer receives a coin toss. Re-run provisioning's billing "
            "seeder to repair it.",
            br_ref="BR-BIL-025",
        )
    layout = layout_or_refuse(layout_key, template_type=template.template_type)
    live = published_version(template)
    # Carry the tenant's OWN copy forward unless this call supplies new copy.
    # BR-BIL-021's bill messages and footer are the tenant's words; a layout
    # change that silently blanked them would be this function editing content
    # nobody asked it to touch.
    carried = dict(live.options or {}) if live is not None else {}
    next_options = dict(options) if options is not None else carried
    if live is not None and live.layout_key == layout.key and next_options == carried:
        return {
            "changed": False,
            "template_id": str(template.pk),
            "version_no": live.version_no,
            "layout_key": live.layout_key,
            "reason": (
                f"this tenant already prints on {layout.label!r} ({layout.key}) as "
                f"published version {live.version_no}. No new version was created: a "
                "version number is frozen into every bill pinned to it, and minting one "
                "for a change that changes nothing makes the chain harder to read."
            ),
        }
    draft = save_draft(template, layout_key=layout.key, options=next_options, actor=actor)
    published = publish(draft, actor=actor, on_date=on_date)
    return {
        "changed": True,
        "template_id": str(template.pk),
        "version_no": published.version_no,
        "layout_key": published.layout_key,
        "previous_version_no": None if live is None else live.version_no,
        "previous_layout_key": None if live is None else live.layout_key,
        "reason": (
            f"published version {published.version_no} on {layout.label!r} "
            f"({layout.key}). Bills issued from now on print on it; every bill already "
            "issued keeps the version its own pin names and is unchanged (BR-BIL-026)."
        ),
    }


def resolve_for(
    *,
    consumer_category: str | None,
    template_type: str = "bill",
    account_override_template_id: Any = None,
) -> tuple[BillTemplate, BillTemplateVersion]:
    """TC-3 — BR-BIL-025's resolution, in its ruled order.

    **account override → category default → the tenant's fallback.** The
    override wins because it is the more specific statement about this customer;
    the fallback exists because an account whose category has no template still
    has to receive a bill.

    ⚠ THE OVERRIDE IS AN ARGUMENT, NOT A LOOKUP. BR-BIL-025 puts it on the
    ACCOUNT and the account is customers' row; billing has one reviewed FK into
    customers (`invoices.account_id`) and no column for this. So the caller
    supplies it and the ORDER is implemented here — which is the half that would
    otherwise be re-guessed at every call site once the column lands.

    Returns the template AND its published version, because a template with no
    published version cannot be pinned and issuing against one would produce a
    bill nothing can render (BR-BIL-033).
    """
    tenant_id = _tenant_id()
    template = None
    if account_override_template_id is not None:
        template = BillTemplate.objects.filter(
            tenant_id=tenant_id, pk=account_override_template_id
        ).first()
        if template is None:
            raise BillingRuleError(
                "this account's template override names a template that does not exist in "
                "this tenant. Billing does not fall back to the category default here: a "
                "silent fallback would send the wrong layout to the one customer somebody "
                "deliberately singled out.",
                br_ref="BR-BIL-025",
            )
    if template is None and consumer_category is not None:
        template = BillTemplate.objects.filter(
            tenant_id=tenant_id, template_type=template_type, category=consumer_category
        ).first()
    if template is None:
        template = BillTemplate.objects.filter(
            tenant_id=tenant_id, template_type=template_type, category__isnull=True
        ).first()
    if template is None:
        raise BillingRuleError(
            f"this tenant has no {template_type} template for consumer category "
            f"{consumer_category!r} and no fallback (BR-BIL-025). A bill cannot be issued "
            "without a template pin, because the pin is what a reprint renders from "
            "(BR-BIL-026/033).",
            br_ref="BR-BIL-025",
        )
    version = published_version(template)
    if version is None:
        raise BillingRuleError(
            f"template {template.name!r} has no PUBLISHED version (BR-BIL-026). A draft is "
            "test-printable but never pinned: a bill pinned to a draft could be edited "
            "after the customer received it, which is the whole thing the version chain "
            "exists to prevent.",
            br_ref="BR-BIL-026",
        )
    return template, version


def test_print(version: BillTemplateVersion) -> dict[str, Any]:
    """TC-1's test-print — SAMPLE DATA, no money event, no delivery row.

    Returns what would be rendered rather than rendering it: `documents.
    render_invoice` needs a stamped invoice payload and a test print has no
    invoice at all. Naming that plainly is the point — a test-print helper that
    quietly rendered a real bill would be a delivery nobody asked for.
    """
    layout = layout_or_refuse(version.layout_key, template_type=version.template.template_type)
    return {
        "template": version.template.name,
        "version_no": version.version_no,
        "status": version.status,
        "layout_key": layout.key,
        "layout_label": layout.label,
        "renders_as_document_layout": layout.renders,
        "options": dict(version.options or {}),
        "sample_data": True,
        "writes": "nothing — no invoice, no delivery row, no audit money event (BR-BIL-027)",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-021@2b52def (sha256[:7] over the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md · 04-docs/05-modules/07-billing/02-business-rules.md · 08-qa/01-e2e/journeys/J22-template-life.md · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S8's Templates tab has no endpoint mounted; REPORTED in TEMPLATES_UNAVAILABLE) E=deferred(no-frontend-half — S8 Templates tab and S91–S93 are unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff · black · makemigrations --check · pytest · run_gates — see the
#         lane report for the verbatim RED transcripts (the one-published-per-
#         template index, the published-version content freeze and the
#         BR-BIL-027 audit-lock were each broken deliberately, RUN, and the
#         measured failure quoted before any was trusted green).
# exceptions: (1) THE PLATFORM SHIPS ONE LAYOUT, NOT THREE TO FIVE. OQ-149 is
#         CLOSED and asks for 3–5; `documents.LAYOUTS` holds one and
#         `PLATFORM_LAYOUTS` therefore holds one. REPORTED as
#         `platform_layout_set_incomplete` rather than padded with keys that
#         would all resolve to the same page. What is owed is layouts, NOT a
#         rendering library — adding one would reopen the scope the ruling shut.
#         (2) THE ACCOUNT-LEVEL OVERRIDE IS AN ARGUMENT, not a lookup:
#         BR-BIL-025 puts it on the customers-owned account row and no column
#         exists. The resolution ORDER is implemented here regardless.
#         (3) NO API OR SCREEN. S8's Templates tab and S91–S93 are unbuilt and
#         no endpoint is mounted; the rights split is still enforced
#         server-side, because a gate that waits for its screen is missing when
#         the first API client arrives.
#         (4) OVERLAP WITH `apps/notifications` (US-NOT-006, which depends on
#         this story) is REPORTED, not resolved — whether it reuses this service
#         or a shared kernel is extracted is a cross-module call above a lane.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
