# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (template CRUD, append-only versions, publish rights)
#           Screens: S8 (Settings → Templates tab) · S91 · S92 · S93
# Rules:    BR-BIL-025 (assignment defaults by consumer category, overridable
#           per account) · BR-BIL-026 (edit = new version; publishing affects
#           only FUTURE bills — AMENDED 2026-08-12, OQ-149: v1 ships 3–5
#           PLATFORM layouts and no tenant-authored design) · BR-BIL-027
#           (Clerk drafts + test-prints; System Admin publishes; a version
#           PINNED by any bill can never be deleted — audit-lock) ·
#           B2 Addendum r10 #4 (the two tables) · r10 #15 (exact DDL =
#           Eng-Lead-owned) · CLAUDE.md rule 1 (tenant scoping, RLS FORCE)
# Tests:    06-backend/tests/test_us_bil_021_templates.py
# Impacts:  apps/billing/templates_service.py (the lifecycle above these rows) ·
#           apps/billing/documents.py (renders a pinned version) ·
#           apps/billing/issue.py (stamps the pin — US-BIL-022)
# ───────────────────────────────────────────────────────
"""`bill_templates` + `bill_template_versions` — B2 Addendum r10 #4.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒 path
and these rows decide which document a customer was sent. AI-authored
2026-08-15 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); row owed in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHAT A "VERSION" HOLDS IN V1 — AND WHAT IT DELIBERATELY DOES NOT
════════════════════════════════════════════════════════════════════════════
**PO ruling 2026-08-12, OQ-149 CLOSED, verbatim:** *"out platform will porvide
standard 3 to 5 variouation of printed bill - user can use those only in V1"*.

So a version row carries **a platform LAYOUT KEY plus the tenant's own options**
— never a tenant-authored body. `layout_key` names one of the platform's 3–5
printed-bill variants and is validated against a registry the tenant cannot
extend; `options` carries what a tenant legitimately chooses (its bill messages
and footer — BR-BIL-021 — and per-layout switches).

**THIS IS WHY NO ~200MB RENDERING LIBRARY IS ADDED, and the reasoning is the
ruling's, not a preference.** Rendering tenant HTML/CSS was the thing that
needed WeasyPrint and its Pango/HarfBuzz/fontconfig tree in every container.
Nothing renders tenant markup in v1, so the question does not arrive:
`documents.py` builds both serialisations with the standard library and this
table hands it a KEY, not a page. A `body` column would be an invitation to
start storing markup, and the day something stored markup the library would
follow it in — so the column does not exist and its absence is the guard.

════════════════════════════════════════════════════════════════════════════
⚠ OVERLAP WITH NOTIFICATIONS — REPORTED, NOT DUPLICATED
════════════════════════════════════════════════════════════════════════════
`apps/notifications` is building the same LIFECYCLE right now, and the specs say
which way the dependency runs: **US-NOT-006 declares `depends_on: [US-BIL-021,
US-TEN-010]`** and its own rule rows read *"BR-BIL-026 (generalized)"* and
*"BR-BIL-027 (generalized)"*. This story is the canonical implementation; the
notifications one generalises it to every designer S91+.

WHAT IS GENUINELY SEPARATE, and it is the DATA not the RULES: this table holds
**printed bill/statement** templates (S8's printable group, S91–S93), and
`notification_templates` — US-NOT-006, **not yet built** — holds email/SMS
bodies and contract templates (S94–S106, S67). EP-BIL-06 puts those out of
scope in as many words. `apps/notifications/rendering.py` today takes
`(template_code, template_version)` as ARGUMENTS and looks nothing up, with its
own docstring recording that *"`notification_templates` and its version rows
are US-NOT-006 and are not built"*.

**So there is no duplication in the tree today, and one is about to be
possible.** The transitions here — draft → published → archived, one published
per template, publish is Admin-only, a pinned version can never be deleted —
are `templates_service.py`'s, written once, tenant-agnostic and table-agnostic
where they can be. A second implementation of "one published version per
template" is how two documents start disagreeing about which one is live, which
is precisely the failure the audit-lock exists to prevent. REPORTED to the
caller rather than resolved here: whether notifications reuses this service, or
a shared kernel is extracted, is a cross-module design call above a story lane
and it needs an owner before US-NOT-006 writes its own copy.

════════════════════════════════════════════════════════════════════════════
APPEND-ONLY IS NOT IN THESE CLASSES
════════════════════════════════════════════════════════════════════════════
A Django model cannot refuse a `.save()` — `apps/billing/models.py` says so of
itself and it is true here. What the DATABASE guarantees (migration `0018`):
a PUBLISHED or ARCHIVED version's `layout_key` and `options` are frozen by
trigger, so BR-BIL-026's *"edit = new version"* is structural rather than
remembered; and both tables are RLS ENABLE + FORCE.

The audit-lock (BR-BIL-027 — a version pinned by ANY bill can never be deleted)
is enforced in `templates_service.delete_version`, which COUNTS the invoices
carrying the pin. It is deliberately not a foreign key: `invoices.template_id` /
`.template_version` are plain columns precisely because r10 #3 pinned them
before this table existed (see `models.Invoice`), and turning them into an FK
now would refuse every historical row written in the meantime.
"""

from django.apps import apps as django_apps
from django.db import models
from django.db.models import Q

from core import tenancy as core_tenancy
from core.dbfields import uuid7_pk

#: A19's template types, printable group only. The email/SMS/contract classes
#: are notifications' (US-NOT-006) and are NOT in this vocabulary — a shared
#: enum would be the first step toward a shared table nobody decided to share.
TYPE_BILL = "bill"
TYPE_STATEMENT = "statement"
TEMPLATE_TYPES = (TYPE_BILL, TYPE_STATEMENT)

# ── BR-BIL-025's consumer categories — READ, never typed ────────────────────
#
# ⚠ **THIS WAS FOUR CONSTANTS UNTIL 2026-09-17 AND ONE OF THEM WAS A CODE THIS
# PRODUCT HAS NEVER HAD.** `CATEGORY_GOVT = "govt"` sat beside three real codes
# and looked exactly like them. The ratified vocabulary is `residential ·
# commercial · industrial · agricultural · institutional · municipal ·
# builder_developer`, with `government` LEGACY (`BR-CUS-094`) — `govt` is in no
# row, no migration and no ruling. Meanwhile `apps/notifications/template_
# models.py` spells the same idea `"government"`. **Three spellings of one thing
# in three modules, which only a table read settles.**
#
# ⚠ **NOTHING WAS MIGRATED, AND THAT IS MEASURED RATHER THAN HOPED.**
# `bill_templates` held ZERO rows in every database on the build machine, no
# migration seeds a category, the only production writer (`templates_service.
# ensure_seed_template`) writes `category=None`, and `create_template` — the one
# path that could ever have stored `govt` — is not served by any route
# (`templates_service.py`'s own refusal register: *"STILL NOT SERVED:
# create_template"*). So `govt` was unreachable as well as wrong, and removing
# it is a constant change rather than a data migration. **If that ever stops
# being true, this is the paragraph that says so and the fix becomes a
# migration.**
#
# `BR-CUS-094a` (PO 2026-09-17), verbatim: *"utility can get their own account
# types"* and *"we have to ensure it is not hard coded"*. So the categories are
# the tenant's `account_types` ROWS. `None` still means the template is the
# tenant's fallback for its type — every tenant needs one answer for an account
# whose category has no template of its own.


def _account_types_are_tenant_scoped(model):
    """Does `account_types` carry a tenant column YET? Asked of the MODEL.

    A sibling lane is making the table tenant-owned under the same ruling.
    Asking rather than assuming means neither lane has to land first, and the
    moment the column does land this read is tenant-filtered — which is hard
    rule 1, not tidiness: an unfiltered read would start returning another
    utility's categories.
    """
    return any(f.attname == "tenant_id" for f in model._meta.concrete_fields)


def categories() -> tuple[str, ...]:
    """The consumer categories THIS TENANT holds, in the ruling's own order.

    ── WHY A FUNCTION AND NOT A TUPLE ────────────────────────────────────────
    A module-level tuple is evaluated at import, before any tenant exists, so it
    can only ever hold what was typed into it. That is precisely the shape the
    PO ruled against. This is a call-time read, so no database is touched at
    import and the answer follows the table.

    ── THE THREE OUTCOMES ARE `metering._resolve_unit_type`'s (BR-MET-084) ───
      · the tenant HAS rows → its own ACTIVE codes, ruled order first and its
        own additions after;
      · a row the tenant DEACTIVATED is absent, and the fallback does not
        resurrect it (`BR-TEN-034`);
      · no rows at all → the ruled vocabulary, so a deployment whose seed has
        not run keeps working rather than refusing every category.

    ⚠ **THIS IS A VALIDATION AND OFFER LIST, NOT A STORAGE CHANGE.**
    `bill_templates.category` stays TEXT and every stored row keeps its value.
    A template whose category is no longer in this list simply stops matching in
    `templates_service.resolve_for`, which is the same thing that happened
    yesterday to any category without a template: BR-BIL-025's chain falls
    through to the tenant's NULL-category fallback, so a bill still prints.

    ⚠ **A TENANT THAT HAS DEACTIVATED EVERY ROW GETS AN EMPTY TUPLE**, and the
    fallback deliberately does NOT resurrect them (`BR-TEN-034`). No category
    can then be assigned, every account resolves to the NULL-category fallback
    template, and every bill still prints — which is the safe direction.
    """
    model = django_apps.get_model("customers", "AccountType")
    qs = model.objects.all()
    if _account_types_are_tenant_scoped(model):
        qs = qs.filter(tenant_id=core_tenancy.current_tenant_id())
    held = {row.code: row.active for row in qs.only("code", "active")}
    ruled = tuple(code for code, _name in model.SEVEN_CATEGORIES) + tuple(model.LEGACY_CODES)
    if not held:
        return ruled
    ordered = [code for code in ruled if held.get(code)]
    ordered += sorted(code for code, active in held.items() if active and code not in ruled)
    return tuple(ordered)

#: BR-BIL-026's lifecycle, verbatim: *"draft → published → archived"*. One
#: published per template, enforced by a partial unique index rather than by
#: the service alone — two published versions is a question with no answer at
#: issue time, and a SELECT-then-INSERT check loses the race that produces it.
VERSION_DRAFT = "draft"
VERSION_PUBLISHED = "published"
VERSION_ARCHIVED = "archived"
VERSION_STATUSES = (VERSION_DRAFT, VERSION_PUBLISHED, VERSION_ARCHIVED)


class BillTemplate(models.Model):
    """One template a tenant assigns — "Bill · residential", "Statement".

    The tenant OWNS this row (its name, its type, its category assignment). What
    it does not own is the page: that is `BillTemplateVersion.layout_key`, one
    of the platform's 3–5 variants (OQ-149).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    name = models.TextField()
    template_type = models.TextField(default=TYPE_BILL)

    #: BR-BIL-025 — *"default by consumer category, overridable per account"*.
    #: The ACCOUNT-level override is customers' attribute and is read at issue;
    #: this column is only the category default half. NULL = the tenant's
    #: fallback for this type.
    category = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bill_templates"
        indexes = [
            models.Index(fields=["tenant", "template_type"], name="ix_bill_templates_type"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_bill_templates_name",
            ),
            # ONE default per (type, category). Resolution at issue is
            # override → category default, and a category with two defaults
            # makes the second step a coin toss.
            models.UniqueConstraint(
                fields=["tenant", "template_type", "category"],
                condition=Q(category__isnull=False),
                name="uq_bill_templates_category",
            ),
        ]


class BillTemplateVersion(models.Model):
    """One APPEND-ONLY version (BR-BIL-026) — what a bill's pin points at.

    `version_no` counts from 1 per template and never reuses a number, because
    `invoices.template_version` is frozen at issue and a reused number would
    make a 2026 bill render on a 2031 page while every row still looked right.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        BillTemplate, on_delete=models.PROTECT, db_column="template_id", related_name="versions"
    )
    version_no = models.IntegerField()
    status = models.TextField(default=VERSION_DRAFT)

    #: WHICH of the platform's 3–5 printed-bill variants this version uses
    #: (OQ-149). A KEY, never markup — see the module docstring on why the
    #: absence of a `body` column is the guard that keeps the rendering library
    #: out of the deployment image.
    layout_key = models.TextField()
    #: What the tenant legitimately chooses: its bill messages and footer
    #: (BR-BIL-021) and the layout's own switches. JSON because the option SET
    #: is per-layout, and a column per option puts a migration between a tenant
    #: and its own footer.
    options = models.JSONField(default=dict, blank=True)

    published_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="published_by",
        related_name="bill_template_versions_published",
    )
    #: BR-TEN-043 — the business date, supplied by the caller. `created_at` is
    #: when the row was written and they are not the same fact.
    published_on = models.DateField(null=True, blank=True)

    #: ⚠ **WHEN THIS VERSION STOPPED BEING OFFERED — CR-048 task E9,
    #: `BR-NOT-025`.** The notification side has carried `archived_at` since it
    #: was written; this side carried an archived STATUS and no timestamp, so
    #: the one Templates screen `BR-NOT-026` rules into existence would have
    #: shown two lifecycles, one of which could not answer *when*.
    #:
    #: NULL on every row that already existed, including rows already archived.
    #: That is the honest value rather than a gap: nobody recorded the date, and
    #: back-filling `created_at` or `updated_at` would manufacture one that
    #: reads like evidence. NULL means *retired before this column existed*.
    #:
    #: ⛔ Archiving is not deleting. `BR-NOT-025` and `BR-BIL-027` keep a version
    #: an issued bill pins in the database forever; this column records that it
    #: left the picker, never that it left the table.
    archived_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="created_by",
        related_name="bill_template_versions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bill_template_versions"
        indexes = [
            models.Index(
                fields=["tenant", "template", "status"], name="ix_bill_tpl_versions_status"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "template", "version_no"],
                name="uq_bill_template_version_no",
            ),
            # BR-BIL-026: *"one published per template"*. PARTIAL, so any
            # number of drafts and archives coexist. This is the half a
            # database can hold; `templates_service.publish` archives the
            # incumbent in the same transaction.
            models.UniqueConstraint(
                fields=["tenant", "template"],
                condition=Q(status=VERSION_PUBLISHED),
                name="uq_bill_template_one_published",
            ),
            models.CheckConstraint(
                condition=Q(version_no__gte=1),
                name="ck_bill_template_version_positive",
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-021@2b52def (sha256[:7] over the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md US-BIL-021/US-BIL-022 + the 2026-08-12 OQ-149 scope narrowing · 04-docs/02-decisions/02-database-design-brief.md Addendum r10 #4/#15 · 08-qa/01-e2e/journeys/J22-template-life.md · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md US-NOT-006)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S8's Templates tab has no endpoint; REPORTED) E=deferred(no-frontend-half — S8 Templates tab and S91–S93 are unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff · black · makemigrations --check · pytest · run_gates — see the
#         lane report for the verbatim RED transcript of the one-published-per-
#         template index and the published-version freeze.
# exceptions: (1) NO `body` COLUMN, AND THE ABSENCE IS THE POINT. OQ-149 closed
#         v1 at 3–5 platform layouts; a version stores a `layout_key` plus the
#         tenant's options. A body column would be where tenant markup landed,
#         and tenant markup is what would pull WeasyPrint's ~200MB Pango/
#         HarfBuzz/fontconfig tree into the deployment image.
#         (2) THE AUDIT-LOCK IS A SERVICE CHECK, NOT AN FK.
#         `invoices.template_id` / `.template_version` are plain columns (r10 #3
#         pinned them before this table existed) and an FK now would refuse
#         every historical row. `templates_service.delete_version` counts the
#         pins instead.
#         (3) OVERLAP WITH `apps/notifications` IS REPORTED, NOT RESOLVED.
#         US-NOT-006 depends on this story and generalises BR-BIL-026/027 to
#         every designer S91+; its own tables are unbuilt. Whether it reuses
#         `templates_service` or a shared kernel is extracted is a cross-module
#         call above a story lane.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
