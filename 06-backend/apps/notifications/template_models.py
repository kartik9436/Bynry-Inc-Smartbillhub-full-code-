# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-006 (version lifecycle, publish rights, pinning + category
#           assignment — for EVERY designer S91+ · the TABLES half)
#           Screens: S8 · S67 · S94–S106
# Rules:    BR-BIL-026 (edit = a new version; the version is PINNED at
#           issue/send; publishing affects only FUTURE renders — generalised to
#           every designer S91+ by A19 addendum b) · BR-BIL-027 (Clerk drafts
#           and test-renders, System Admin publishes; a PINNED version can never
#           be deleted — audit-lock) · BR-BIL-025 (assignment defaults by
#           consumer category, overridable per account) · BR-NOT-001 (contract
#           templates carry per-consumer-category variants — Res/Com/Ind/Gov
#           plus a DEFAULT fallback) · BR-NOT-002 (contract versions are
#           EFFECTIVE-DATED; a generated or signed contract permanently
#           references the exact version used) · BR-NOT-006 (templates gain a
#           LANGUAGE dimension: variants per type × category × language; missing
#           variant → tenant-default fallback, never a blank) · A19 rule 6
#           (every template versioned + audit-logged) · CLAUDE.md rule 1
#           (tenant scoping; RLS FORCE lands in migration 0006) · rule 4
#           (financial immutability — a published version's body is evidence of
#           what a customer was sent and is never rewritten)
# Tests:    06-backend/tests/test_us_not_006_template_lifecycle.py ·
#           06-backend/tests/test_us_not_006_template_isolation.py
# Impacts:  apps/notifications/rendering.py (loads a pinned version's body from
#           these rows instead of refusing every queue row) ·
#           apps/notifications/services.py (stamps the resolved pin onto each
#           queue row at queue time) · every designer screen S94–S106 and S67.
#           Their US-IDs are named in the docstring rather than here — G10 reads
#           any US-ID inside this block as "this file ships that story's test
#           cases", including on an Impacts line, and `apps/notifications/
#           models.py` records being caught by exactly that.
# ───────────────────────────────────────────────────────
"""The template registry and its append-only version rows — the store US-NOT-005
was written against and could not have.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — a published version's body is the document
a customer receives, so these rows sit under CLAUDE.md rule 4 (a rendered
document is evidence of what was sent and is never rewritten) and the publish
right is a role gate. AI-authored 2026-08-15 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"); row required in
12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHY THIS EXISTS AT ALL: NOTHING RENDERED BEFORE IT.                     ║
╚══════════════════════════════════════════════════════════════════════════╝
`apps/notifications/rendering.py` shipped on 2026-08-15 with a
`render_for_dispatch` that REFUSED every queue row, and said why in as many
words: *"`notification_templates` and its append-only version rows are
US-NOT-006 and are not built … the engine itself is here and tested; what is
missing is the store that hands it a body."* This file is that store. The engine
is unchanged; it now has somewhere to read from.

────────────────────────────────────────────────────────────────────────────
THE REGISTRY ROW IS A **VARIANT**, NOT A TEMPLATE — and that is BR-NOT-006's
shape, not a convenience
────────────────────────────────────────────────────────────────────────────
BR-NOT-006, verbatim: *"Templates gain a LANGUAGE dimension: variants per type ×
category × language; version pinning includes the language variant (a reprint
renders its pinned language forever); missing variant → tenant-default fallback,
never a blank."* BR-NOT-001 gives the category axis its values — *"Residential /
Commercial / Industrial / Government plus a default fallback"*.

So the unit that owns a version chain is the TRIPLE `(code, category,
language)`. T4-09 is the journey that settles it: *"Template variant chain gains
the es-MX row"* — the variant has a chain of its own, and step 4 reprints a July
bill in the English it was pinned to while an es-MX variant now exists. If the
chain hung off the CODE and the variant were a column on the version, adding a
language would renumber the English chain, and "v2" would stop being a fact
about one document.

`category` and `language` are NOT NULL and carry the sentinel `"default"`
instead. `apps/notifications/models.py` records the reason in its own key
section and it is the same one here: *"A NULL anywhere in a unique key means no
uniqueness at all in PostgreSQL, so a nullable column would quietly switch the
guarantee off for exactly the rows nobody was watching."* `"default"` is also
the ratified WORD — BR-NOT-001 writes *"plus a default fallback"* — so the
sentinel names itself on every screen that shows it.

────────────────────────────────────────────────────────────────────────────
WHICH CLASSES LIVE HERE, AND THE THREE THAT DO NOT (B1 boundary)
────────────────────────────────────────────────────────────────────────────
Every class in `apps/notifications/catalogs.py` **except** `bill_residential`,
`bill_commercial` and `statement`. Those three are the S91–S93 designers, they
are BILLING's (US-BIL-021), and B2 addendum **r10 #4** gives them their own
tables: *"`bill_templates` + `bill_template_versions` (append-only;
draft|published|archived; audit-locked while pinned; category assignment)"*.
Building them here would be one module owning another's tables, which is the
first line of the B1 boundary rule.

The refusal is in the SERVICE (`template_service.register`) rather than in a
CHECK constraint, because the boundary is a fact about story ownership and not
about data: if r10 #4's tables are ever folded into this one by an Eng-Lead
disposition, that is a decision plus a migration, not a constraint drop.

⚠ CONSEQUENCE, STATED RATHER THAN LEFT TO BE FOUND: **a bill cannot render on
this deployment either**, and not because of anything in this file — `bill_
templates` is unbuilt in billing. A queue row pinned to a bill class still holds
at dispatch with the missing-template reason. Reported, not silently absorbed.

────────────────────────────────────────────────────────────────────────────
ONE PUBLISHED VERSION — EXCEPT WHERE BR-NOT-002 RATIFIES SEVERAL
────────────────────────────────────────────────────────────────────────────
Two ratified rules point in opposite directions and the reconciliation is a
column, so it is written down here:

  * **BR-BIL-027 / US-NOT-006 TC-2** — *"Admin publish → v3 published, v2
    auto-archived (ONE published per template)."*
  * **BR-NOT-002 / US-NOT-006 TC-3** — *"Service-agreement v2 effective Sep 1;
    generation Aug 20 renders v1, generation Sep 2 renders v2."* On Aug 20 both
    v1 and v2 are published, or v2 could not have been authored in advance.

`effective_from` is what separates them. A version with `effective_from IS NULL`
is an ORDINARY version and at most one may be published per variant — the
partial unique index `uq_ntv_one_published_undated` is TC-2 in the DDL. A
version WITH an `effective_from` is an effective-dated one (contracts,
BR-NOT-002) and several may be published at once, one per date — the second
partial index `uq_ntv_published_effective_from` refuses two versions claiming
the same day, because "the version in effect on D" has to be a single row.

Which classes may carry a date is a class rule and lives in the service: the
contracts group requires one, everything else refuses one. A tenant that could
effective-date a receipt would have invented a second publishing model for a
class whose spec has one.

────────────────────────────────────────────────────────────────────────────
APPEND-ONLY IS ENFORCED BY THE DATABASE, NOT BY A DOCSTRING (hard-won law 1)
────────────────────────────────────────────────────────────────────────────
US-NOT-006 TC-6: *"Direct UPDATE of a published version's body → Rejected —
versions are append-only rows; edits create drafts."* A service check alone
would leave `.update()`, a shell, a data migration and a future endpoint outside
it, so migration `0006` installs a trigger: once a version leaves `draft`, its
`body`, `subject`, `version`, `effective_from` and `template_id` are frozen, and
only the lifecycle stamps (`status`, `published_at`, `published_by`,
`archived_at`, `updated_at`) may move. A non-draft row can never be DELETEd —
NFR-8's *"v2 retained FOREVER"* and TC-5's audit-lock are the same guarantee
seen from two sides.

A DRAFT deletes freely while nothing pins it (T5-02 step 4, the contrast case).

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY NOT HERE
────────────────────────────────────────────────────────────────────────────
* **No `deleted_at`.** B2 §2's base `notification_templates` carries one; a
  soft-delete column on a table whose rows can never be deleted is a second,
  weaker way of saying "archived", and two ways of saying it is how a screen
  ends up showing a template that renders nothing.
* **No body validation column.** Whether a body's tokens are legal is
  `catalogs.py` + `rendering.validate_body`, checked at save. Storing the answer
  would let it drift from the catalog that produced it.
* **No PDF.** OQ-149 closed with no page-render library in the image; a
  printable class stores and renders its TEXT body (`rendering.py` exception 2).
"""

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

#: BR-NOT-001's four consumer categories, spelled as `account_types.code`
#: (`apps/customers/models.AccountType`) so a resolution never has to translate:
#: *"residential | commercial | industrial | government"*. `government` is the
#: ratified label — the S8 prototype's "Municipal" is copy, and B2 governs data.
CATEGORY_RESIDENTIAL = "residential"
CATEGORY_COMMERCIAL = "commercial"
CATEGORY_INDUSTRIAL = "industrial"
CATEGORY_GOVERNMENT = "government"

#: BR-NOT-001's *"plus a default fallback"* and BR-NOT-006's *"missing variant →
#: tenant-default fallback, never a blank"* — ONE sentinel serving both axes.
#: A sentinel rather than NULL: see the module docstring's key note.
VARIANT_DEFAULT = "default"

CATEGORIES = (
    CATEGORY_RESIDENTIAL,
    CATEGORY_COMMERCIAL,
    CATEGORY_INDUSTRIAL,
    CATEGORY_GOVERNMENT,
    VARIANT_DEFAULT,
)

#: A19 rule 6 + BR-BIL-026's lifecycle, verbatim from 04-flows.md §2:
#: *"DRAFT (Clerk edits …) → PUBLISHED (System Admin only …) → ARCHIVED (auto on
#: next publish, or manual)"*.
VERSION_DRAFT = "draft"
VERSION_PUBLISHED = "published"
VERSION_ARCHIVED = "archived"
VERSION_STATUSES = (VERSION_DRAFT, VERSION_PUBLISHED, VERSION_ARCHIVED)

#: `CR-199-BRC10` S4 (PO 2026-10-29, ruling 2A). How an EMAIL body is laid out:
#: `rich` carries bold, links, buttons and lists in the email's HTML part;
#: `plain` carries none. Both are written in ONE closed markup
#: (`apps/notifications/rich_text.py`) and both send a plain-text part. The
#: format belongs to the VERSION, not the variant, because a pinned version
#: must reprint exactly as it went out. Non-email classes are always `plain`.
BODY_FORMAT_PLAIN = "plain"
BODY_FORMAT_RICH = "rich"
BODY_FORMATS = (BODY_FORMAT_PLAIN, BODY_FORMAT_RICH)


class NotificationTemplate(models.Model):
    """One template VARIANT: a class, for a consumer category, in a language.

    The registry row the S8 templates card lists and the designers open. It
    holds no body — bodies live on the version rows, because BR-BIL-026 makes
    every edit a new version and a body on the parent would be a body with no
    version number to pin.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: The template CLASS — a key of `apps.notifications.catalogs.CATALOGS` or
    #: of `CLASSES_WITHOUT_CATALOG`. Plain text, validated by the service
    #: against the catalog: B2 r16 #3's lesson is that an enum column turns a
    #: reference-data change into a migration, and A19's class set has already
    #: grown twice (BR-NOT-004's four contracts, BR-NOT-007's three plan
    #: notices).
    code = models.TextField()
    #: The designer group (`printable` | `email` | `sms` | `contracts`), copied
    #: from the class's catalog entry at registration so the S8 card can group
    #: and filter without importing the catalog into a query.
    group = models.TextField()
    #: `pdf_print` | `email` | `sms`, likewise from the catalog. The row it will
    #: render onto carries the same value, and a mismatch is a template that can
    #: never be dispatched.
    channel = models.TextField()

    #: BR-NOT-001 / BR-BIL-025 — the consumer-category axis, or `default`.
    category = models.TextField(default=VARIANT_DEFAULT)
    #: BR-NOT-006 — the language axis, or `default` for the tenant's own
    #: default-language variant. A BCP-47 tag (`es-MX`) elsewhere; the eleven
    #: locale catalogue codes are the platform's set (B2 r17) and this column
    #: does not restate them, because a language is DATA (NFR-37: adding one is
    #: never a code change).
    language = models.TextField(default=VARIANT_DEFAULT)

    #: What a human calls it on the S8 card ("Past-due reminder"). Tenant prose,
    #: deliberately NOT a message_key: it is the tenant's own words about their
    #: own document, in whatever language they wrote it (B2 r17.5's reasoning
    #: for custom-field labels, applied to the same kind of string).
    name = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        indexes = [
            # The S8 card's list: group, then name (EP-NOT-02 capability matrix
            # "default sort: group, then name asc").
            models.Index(fields=["tenant", "group", "name"], name="ix_ntpl_group_name"),
            # Resolution's own lookup — every render starts here.
            models.Index(fields=["tenant", "code", "category", "language"], name="ix_ntpl_variant"),
        ]
        constraints = [
            # ONE variant per (class, category, language). Without it a tenant
            # could hold two "Residential receipt in es-MX" rows with different
            # published bodies and resolution would pick by insertion order —
            # i.e. the document a customer receives would depend on which row a
            # query happened to return first.
            models.UniqueConstraint(
                fields=["tenant", "code", "category", "language"],
                name="uq_ntpl_variant",
            ),
        ]


class NotificationTemplateVersion(models.Model):
    """One APPEND-ONLY version of one variant. The thing a document pins to.

    BR-BIL-026: an edit creates a new row here; publishing affects only FUTURE
    renders; and every issued document, sent message and signed contract holds
    `(template_id, version, language)` forever.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.PROTECT,  # a variant with versions is never deleted
        related_name="versions",
        db_column="template_id",
    )

    #: 1, 2, 3 … per variant. The number a designer header shows ("v3 · edited
    #: Aug 9, 2026" — A19 rule 6) and the number a pin carries.
    version = models.IntegerField()
    status = models.TextField(default=VERSION_DRAFT)  # VERSION_STATUSES

    #: Email carries a subject and a preheader (A19 r8 email table); printable
    #: and SMS classes carry neither. Nullable rather than blank-defaulted so
    #: "this class has no subject" and "somebody saved an empty subject" are
    #: different rows.
    subject = models.TextField(null=True, blank=True)
    preheader = models.TextField(null=True, blank=True)
    body = models.TextField()
    #: `CR-199-BRC10` S4 — `plain` | `rich`. Frozen with the body once the row
    #: leaves draft (`notifications/0037`'s trigger), for the body's reason.
    body_format = models.TextField(default=BODY_FORMAT_PLAIN)

    #: BR-NOT-002 — the contracts group only. NULL on every other class, and
    #: that NULL is load-bearing: the partial unique index below reads it to
    #: tell an ordinary version (at most one published) from an effective-dated
    #: one (several published, one per date). See the module docstring.
    effective_from = models.DateField(null=True, blank=True)

    #: `CR-199-BRC10` S3 — *Make live again* and *Restore* write a NEW version
    #: holding an older one's wording; this is the number of the version it
    #: was copied from, so History can say *"v5 · v1 restored"*. NULL for a
    #: version somebody typed. WRITE-ONCE (migration 0036's trigger), and kept
    #: on the row rather than only in `audit_log`, because `audit_log` is
    #: pruned on a retention schedule (`OQ-1340`) and this fact must outlive it.
    restored_from_version = models.IntegerField(null=True, blank=True)

    #: A19 rule 6 — *"versioned + audit-logged; header shows version + last-
    #: edited date"*. Plain uuids, not FKs to `users`: identity is another
    #: module's table and B11 F-3's deferred-FK convention is what this repo
    #: uses across module lines. The `audit_log` row is the authoritative record
    #: of who did it (rule 7); these are for the designer header.
    created_by = models.UUIDField(null=True, blank=True)
    published_by = models.UUIDField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_template_versions"
        indexes = [
            # Resolution: the published row(s) of a variant, newest effective
            # date first. Partial — a variant's history is mostly archived.
            models.Index(
                fields=["tenant", "template", "-effective_from"],
                condition=Q(status=VERSION_PUBLISHED),
                name="ix_ntv_published",
            ),
            # The designer's version list (A19 rule 6's header + history).
            models.Index(fields=["tenant", "template", "-version"], name="ix_ntv_chain"),
        ]
        constraints = [
            # The version NUMBER is the pin. Two rows sharing one would make a
            # pinned document ambiguous, which is the one thing BR-BIL-026 does
            # not survive.
            models.UniqueConstraint(
                fields=["tenant", "template", "version"],
                name="uq_ntv_version",
            ),
            # US-NOT-006 TC-2 in the DDL: *"one published per template"* — for
            # ORDINARY versions. See the module docstring for why the exception
            # is a column rather than a special case.
            models.UniqueConstraint(
                fields=["tenant", "template"],
                condition=Q(status=VERSION_PUBLISHED, effective_from__isnull=True),
                name="uq_ntv_one_published_undated",
            ),
            # BR-NOT-002: several published versions, one per effective date.
            # Two claiming the same day would make "the version in effect on D"
            # a coin toss on a signed contract.
            models.UniqueConstraint(
                fields=["tenant", "template", "effective_from"],
                condition=Q(status=VERSION_PUBLISHED, effective_from__isnull=False),
                name="uq_ntv_published_effective_from",
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="ck_ntv_version_positive"),
            models.CheckConstraint(condition=Q(status__in=VERSION_STATUSES), name="ck_ntv_status"),
            models.CheckConstraint(
                condition=Q(body_format__in=BODY_FORMATS), name="ck_ntv_body_format"
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-006@9a4f21c (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md — US-NOT-006 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-001/002/003/006 — · 10-notifications/04-flows.md §2 (the template lifecycle) · 08-qa/01-e2e/journeys/J22-template-life.md + T4-08 + T4-09 + T5-02, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — the template store)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S8 templates-card endpoints are not in this lane; the service is the interface) E=deferred(no-frontend-half — S8/S67/S94–S106 designers are frontend work this lane did not reach; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the migration trailers — these classes and 0005/0006 ship together
# exceptions: (1) THE THREE BILL/STATEMENT CLASSES ARE NOT REGISTRABLE HERE.
#         S91–S93 are billing's designers (US-BIL-021) and B2 r10 #4 gives them
#         `bill_templates` + `bill_template_versions`. The refusal lives in
#         `template_service.register`, not in a CHECK constraint, because it is a
#         story-ownership fact. CONSEQUENCE: a bill still cannot render on this
#         deployment, for a reason that is billing's — REPORTED.
#         (2) `category` AND `language` USE THE SENTINEL `"default"` RATHER THAN
#         NULL, because a NULL in a unique key switches uniqueness off in
#         PostgreSQL for exactly the rows nobody is watching (the same call
#         `outbound_messages.source_id` made).
#         (3) TWO PARTIAL UNIQUE INDEXES, NOT ONE. BR-BIL-027's "one published
#         per template" and BR-NOT-002's effective-dated contract versions are
#         both ratified and disagree; `effective_from IS NULL` is what separates
#         them, and WHICH classes may carry a date is a service rule.
#         (4) NO `deleted_at` (B2 §2's base column) — these rows are never
#         deleted once published, and a second weaker word for "archived" is how
#         a screen shows a template that renders nothing.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
