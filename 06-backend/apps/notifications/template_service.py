# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-006 (version lifecycle, publish rights, pinning + category
#           assignment — for EVERY designer S91+ · the SERVICE half)
#           Screens: S8 · S67 · S94–S106
# Rules:    BR-BIL-026 (edit = a new version; publishing affects only FUTURE
#           renders; a render uses the PINNED version) · BR-BIL-027 (Clerk
#           drafts + test-renders · System Admin publishes · a PINNED version
#           can never be deleted — audit-lock) · BR-BIL-025 (assignment defaults
#           by consumer category, overridable per account) · BR-NOT-001
#           (category variants + a mandatory default fallback) · BR-NOT-002
#           (contract versions are effective-dated; the version in effect on the
#           generation date renders) · BR-NOT-006 (type × category × language;
#           missing variant → tenant-default fallback, NEVER a blank) ·
#           A19 rule 6 (every template versioned + audit-logged) ·
#           BR-TEN-043 (a business date is an argument, never a clock read) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (a published body is
#           evidence of what was sent) · rule 7 (every action audited)
# Tests:    06-backend/tests/test_us_not_006_template_lifecycle.py ·
#           06-backend/tests/test_us_not_006_template_isolation.py
# Impacts:  apps/notifications/rendering.py (asks `load_pinned` for a body) ·
#           apps/notifications/services.py (asks `resolve` for the pin it stamps
#           on a queue row) · the S8 templates card and every designer screen.
#           Their US-IDs live in the docstring, not here — G10 reads any US-ID
#           in this block as a completion claim, including on an Impacts line.
# ───────────────────────────────────────────────────────
"""The template lifecycle: draft → publish → archive, resolution, and the pin.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides WHICH body a customer's
document is rendered from and who is allowed to change it. AI-authored
2026-08-15 under the PO ruling of 2026-08-09; row required in
12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  RESOLUTION HAPPENS ONCE, AT QUEUE TIME. RENDERING NEVER RESOLVES.       ║
╚══════════════════════════════════════════════════════════════════════════╝
Two functions and the boundary between them is the whole of BR-BIL-026:

  `resolve(...)`      → picks a version. Called when a message is QUEUED, a
                        contract is GENERATED, a bill is ISSUED. Reads today's
                        published state; is TOLD the account's category and
                        the utility's language (`OQ-CUS-12619`).
  `load_pinned(...)`  → returns the body of an EXACT (template, version). Called
                        at render. Reads no published pointer, applies no
                        fallback, and cannot be asked for "the latest".

US-NOT-005 TC-6 states the consequence as a negative — *"Render requested 'on
latest version' for an issued document → No such path exists"* — and the
separation is what makes that structurally true rather than a rule somebody has
to remember. `rendering.py` imports `load_pinned` and nothing else from here.

────────────────────────────────────────────────────────────────────────────
THE RESOLUTION ORDER (BR-BIL-025 + BR-NOT-001 + BR-NOT-006), AND WHAT IT
RECORDS ABOUT ITSELF
────────────────────────────────────────────────────────────────────────────
04-flows.md §2, verbatim: *"Resolution at render: account override → consumer-
category default → published version (BR-BIL-025)"*, crossed with BR-NOT-006's
language axis and its *"missing variant → tenant-default fallback, never a
blank"*.

So `resolve` tries, in order:

  1. the account's OVERRIDE variant, if one was passed;
  2. `(code, category, language)` — the exact variant;
  3. `(code, default, language)` — the all-customers variant in that language;
  4. `(code, category, default)` — the category's own default-language variant
     (3 and 4 swapped 2026-10-29, `CR-199-BRC10` — see `resolve`);
  5. `(code, default, default)` — the fallback BR-NOT-001 makes mandatory.

**Every result names the step it came from and the language it ACTUALLY used.**
J22 step 3 is explicit that this is not bookkeeping: *"ACC-1203 requests es-MX
but no es-MX variant exists yet → tenant-default fallback (en) is resolved AND
RECORDED on the pin — never a blank, never an unrecorded inference."* The pin
that comes out of here is what a reprint renders from three years later, so a
fallback that left no trace would make a Spanish-preferring customer's July
letter unreproducible: nobody could tell whether it went out in English by
fallback or by choice.

⚠ **THE CATEGORY AND THE LANGUAGE ARE ARGUMENTS, NOT READS.** The category is
a customers-owned fact and customers publishes no read for it; inventing one
here would put a guess about a customer inside a document. It is passed in by
the caller that holds the account — the same call `apps/payments/notices.py`
makes for the medical-hold flag (*"the hold itself is a customers-owned fact and
is passed IN rather than read"*). A caller that passes neither resolves the
`(default, default)` variant, which is a real, ratified answer and not a
degraded one.

⚠ **THE LANGUAGE IS THE UTILITY'S, NOT THE CUSTOMER'S — AMENDED 2026-09-23
(`OQ-CUS-12619`, `BR-NOT-006` amended, `DEF-NOT-6354`).** This paragraph said
both axes were customers-owned facts, and six writers passed
`accounts.preferred_language`. The PO then ruled, verbatim, *"(a) Portal only;
emails in English."*: a message takes the utility's default language and the
account's preference drives the customer portal alone. Writers now pass the
utility's Settings → Regional language; nothing in this file changed, because
the ladder below is the same ladder whoever supplies the code.

────────────────────────────────────────────────────────────────────────────
THE RIGHTS SPLIT IS SERVER-SIDE (BR-BIL-027, US-NOT-006 TC-2)
────────────────────────────────────────────────────────────────────────────
*"Priya attempts Publish; Alex publishes → Clerk publish server-rejected; Admin
publish → v3 published, v2 auto-archived."* `@require_role(SYSTEM_ADMIN)` on
`publish` and `archive`; Clerk or Admin on `save_draft`. On the SERVICE, so it
holds for an endpoint, a job, a shell and an import alike (BR-SHL-025).

────────────────────────────────────────────────────────────────────────────
THE AUDIT-LOCK, AND WHY IT FAILS CLOSED (US-NOT-006 TC-5, T5-02)
────────────────────────────────────────────────────────────────────────────
*"Delete attempted on receipt v1 (pinned by 3,412 sent receipts) → Blocked
forever — audit-lock; archive allowed; an unpinned draft deletes fine."*

`delete_version` refuses:
  * any version that is not a DRAFT — published and archived rows are retained
    forever (NFR-8), which the database also enforces (migration 0006's
    trigger), so this is the readable half of a guarantee that does not depend
    on it;
  * any version with a PIN — a queue row naming it.

The pin count reads `outbound_messages`, which this module owns. It deliberately
does NOT reach into `invoices` or into signed-contract records: bills pin
billing's `bill_templates` (B2 r10 #4, a different registry), and generated
contract documents have no store yet (US-NOT-012 §5's *"signed pdf → account
documents"* is an integrations/customers surface). Since a draft is the only
deletable thing and a draft can never have been pinned by anything, the narrower
count is not a weaker lock — it is the only one that can matter.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE DOES NOT DO
────────────────────────────────────────────────────────────────────────────
* **It does not render.** `rendering.render` does, and it validates the body
  against the class catalog on the way through — which is why `save_draft`
  calls `rendering.validate_body` rather than re-implementing the palette rule.
* **It does not decide whether a class has a catalog.** Seventeen classes have
  none (OQ-206, OQ-207) and a draft may still be SAVED for them only if the
  catalog can validate it — it cannot, so the save is refused with the catalog's
  own reason. A tenant is not blocked from *registering* the variant, because
  the class itself is ratified and the S8 card should show it as awaiting its
  content rather than pretend it does not exist.
* **It does not read a clock.** `on_date` / `at` are arguments (BR-TEN-043).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.db.models import Max, Q

from apps.notifications import catalogs, models, rendering, template_changes
from apps.notifications import template_models as tm
from core import audit, errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: The three classes whose DESIGNERS are billing's (S91–S93, US-BIL-021) and
#: whose tables B2 r10 #4 names separately: *"`bill_templates` +
#: `bill_template_versions`"*. Registering one here would be this module owning
#: billing's tables — the first line of the B1 boundary rule.
BILLING_OWNED_CLASSES: frozenset[str] = frozenset(
    {"bill_residential", "bill_commercial", "statement"}
)

#: BR-NOT-002 applies to the CONTRACTS group and to nothing else: *"Contract
#: templates are effective-date versioned"*. A tenant able to effective-date a
#: receipt would have invented a second publishing model for a class whose spec
#: has one.
EFFECTIVE_DATED_GROUPS: frozenset[str] = frozenset({catalogs.GROUP_CONTRACT})

#: A19 rule 6 — *"every template versioned + AUDIT-LOGGED"*. The dotted
#: `entity.action` grammar `core.audit` documents; the field map §2 names three
#: of them verbatim (*"`template.saved/published/archived`"*).
AUDIT_ENTITY = "notification_template_version"
AUDIT_REGISTERED = "template.registered"
AUDIT_SAVED = "template.saved"
AUDIT_PUBLISHED = "template.published"
AUDIT_ARCHIVED = "template.archived"
AUDIT_DELETED = "template.draft_deleted"

#: How a resolution was reached. CODES, because the pin carries one onto a
#: document that may be reprinted years later and a screen cannot group on a
#: sentence (J22 step 3: the fallback is RECORDED, never inferred).
VIA_ACCOUNT_OVERRIDE = "account_override"
VIA_EXACT = "exact_variant"
VIA_LANGUAGE_FALLBACK = "language_fallback"
VIA_CATEGORY_FALLBACK = "category_fallback"
VIA_DEFAULT_FALLBACK = "default_fallback"


class TemplateRefused(Exception):
    """This template action cannot be performed, and here is why — in a clerk's
    words.

    Deliberately NOT one of the `core.errors` catalog exceptions for the same
    reason `rendering.RenderRefused` is not: resolution runs inside a bill run
    over thousands of documents where the right handling is to record the break
    and carry on (BR-BIL-055's shape). The designer endpoints translate it.
    """


@dataclass(frozen=True)
class ResolvedTemplate:
    """The PIN — what a queue row, an invoice or a contract freezes.

    `language` is the language ACTUALLY used and not the one requested: J22
    step 3 makes the fallback part of the record, so a reprint reproduces the
    English letter that really went out rather than the Spanish one a preference
    column implies should have.
    """

    template_id: Any
    code: str
    version: int
    language: str
    category: str
    via: str
    #: True when the requested (category, language) was not the one used. The
    #: caller shows it, counts it, or ignores it — but it is never invisible.
    fell_back: bool = False


@dataclass(frozen=True)
class PinnedBody:
    """One exact version's stored content, for `rendering.render` to merge."""

    template_id: Any
    code: str
    version: int
    language: str
    category: str
    channel: str
    body: str
    subject: str | None = None
    preheader: str | None = None
    effective_from: date | None = None
    #: `CR-199-BRC10` S4 — `plain` | `rich`, frozen with the body.
    body_format: str = tm.BODY_FORMAT_PLAIN


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _class_or_refuse(code: str) -> tuple[str, str]:
    """`(group, channel)` for a known class, or a refusal naming the boundary."""
    if code in BILLING_OWNED_CLASSES:
        raise TemplateRefused(
            f"{code!r} is a BILLING designer (S91–S93, US-BIL-021) and its versions live in "
            "`bill_templates` / `bill_template_versions` (B2 addendum r10 #4), not in this "
            "registry. Registering it here would mean notifications owning billing's tables, "
            "which the B1 module boundary forbids. US-NOT-006's LIFECYCLE rules apply to "
            "those designers — the tables do not move."
        )
    catalog = catalogs.catalog_for(code)
    if catalog is not None:
        return catalog.group, catalog.channel
    if code in catalogs.CLASSES_WITHOUT_CATALOG:
        # The CLASS is ratified (A19 r8's email/SMS tables, BR-NOT-004's
        # contracts, BR-NOT-007's plan notices) and only its token catalog is
        # missing. The variant may be registered so the S8 card shows it
        # awaiting content; the DRAFT save is what refuses, quoting OQ-206/207.
        group = (
            catalogs.GROUP_CONTRACT
            if code.startswith("contract_")
            else (
                catalogs.GROUP_EMAIL
                if code.startswith("email_")
                else catalogs.GROUP_SMS if code.startswith("sms_") else catalogs.GROUP_PRINTABLE
            )
        )
        channel = (
            models.CHANNEL_EMAIL
            if group == catalogs.GROUP_EMAIL
            else models.CHANNEL_SMS if group == catalogs.GROUP_SMS else models.CHANNEL_PRINT
        )
        return group, channel
    raise TemplateRefused(
        f"{code!r} is not a template class this platform knows. The known set is "
        f"{', '.join(catalogs.known_template_codes())}. A variant registered under an "
        "unknown class is a variant nothing will ever resolve, render or dispatch."
    )


def known_categories() -> frozenset[str]:
    """Every value the CATEGORY axis may hold for this utility.

    ⚠ **WIDENED 2026-10-29 (`CR-199-BRC10` S1, A3 A — a variant is channel ×
    language × CUSTOMER CATEGORY).** This read `tm.CATEGORIES` alone: BR-NOT-001's
    four plus `default`. Since the PO ruling of 2026-09-17 (*"utility can get
    their own account types"*) a utility's customer classes are its OWN rows in
    `account_types`, so a hardcoded four refused an `irrigation` variant at a
    utility that bills irrigation accounts. The axis is now `default` ("All
    customers") plus the utility's ACTIVE class codes, read through
    `customers_seam` (B2 §2: no reach into customers' tables), plus the four
    platform constants, which are seeded codes and keep every existing row
    lawful.
    """
    from apps.notifications import customers_seam  # local: keeps the import graph flat

    _tenant_id()
    codes = set(tm.CATEGORIES)
    codes.update(row["value"] for row in (customers_seam.account_category_options() or []))
    return frozenset(codes)


def _valid_variant(category: str, language: str) -> None:
    if category not in tm.CATEGORIES and category not in known_categories():
        raise TemplateRefused(
            f"{category!r} is not one of this utility's customer categories. A variant's "
            f"customers are {tm.VARIANT_DEFAULT!r} (all customers) or a code from the "
            "utility's own customer classes (Settings › Reference data), spelled as "
            "`account_types.code` so a resolution never has to translate."
        )
    if not language:
        raise TemplateRefused(
            "a variant needs a language, or the sentinel "
            f"{tm.VARIANT_DEFAULT!r} for the tenant's own default-language variant "
            "(BR-NOT-006). An empty language would make the unique key ambiguous and the "
            "fallback silent."
        )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-BIL-027")
def register(
    *,
    code: str,
    name: str,
    actor: Any,
    category: str = tm.VARIANT_DEFAULT,
    language: str = tm.VARIANT_DEFAULT,
) -> tuple[tm.NotificationTemplate, bool]:
    """Create the VARIANT row the S8 card lists and the designers open.

    Idempotent on `(code, category, language)`: the second call returns the row
    the first one made. A tenant clicking twice must not end up with two
    "Residential receipt in es-MX" variants holding different published bodies —
    which resolution would then pick between by insertion order.

    ⚠ RETURNS `(row, created)`, AND THE SECOND HALF IS NOT DECORATION (DEF-207).
    It used to return the row alone, so the route could not tell a create from a
    fetch and answered **201 with the EXISTING variant's name** — a person typing
    "Large print" over a commercial/es-MX that already existed was told
    *"Variant 'Spanish commercial' created."* and nothing was created. The
    idempotency was right; only the report of it was wrong, which is the harder
    kind to notice: the screen says success, the register is correct, and the
    user's mental model is now false.

    `dispatch_config.py:192` and `apps/tenancy` both already unpack `created`
    from their own `get_or_create` — this brings the variant path in line rather
    than inventing a convention.
    """
    tenant_id = _tenant_id()
    group, channel = _class_or_refuse(code)
    _valid_variant(category, language)
    row, created = tm.NotificationTemplate.objects.get_or_create(
        tenant_id=tenant_id,
        code=code,
        category=category,
        language=language,
        defaults={"group": group, "channel": channel, "name": name},
    )
    if created:
        audit.money_action(
            actor,
            AUDIT_REGISTERED,
            "notification_template",
            str(row.pk),
            after={
                "code": code,
                "category": category,
                "language": language,
                "group": group,
                "channel": channel,
            },
        )
    return row, created


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-BIL-027")
def save_draft(
    *,
    template: tm.NotificationTemplate,
    body: str,
    actor: Any,
    subject: str | None = None,
    preheader: str | None = None,
    effective_from: date | None = None,
    restored_from_version: int | None = None,
    body_format: str = tm.BODY_FORMAT_PLAIN,
) -> tm.NotificationTemplateVersion:
    """Every edit is a NEW append-only version (BR-BIL-026, US-NOT-006 TC-1).

    `restored_from_version` (`CR-199-BRC10` S3) is set only by *Restore* and
    *Make live again*: the new row holds an older version's wording and says
    which one, on the row itself (migration 0036 makes it write-once).

    *"Priya edits 'Past-due reminder' email → New draft v3 append-only (v2
    published untouched); designer header shows 'v3 · edited Aug 9, 2026'; save
    audited."*

    The body is validated against its class's palette FIRST (US-NOT-005 TC-5),
    so a receipt carrying `{meter_no}` never reaches the table. That validation
    lives in `rendering.validate_body` and is not repeated here: two copies of
    the palette rule is the drift hard-won law 1 warns about.

    A class with NO catalog (OQ-206 / OQ-207) refuses here, quoting the
    catalog's own reason. That is not this lane declining to work — there is no
    vocabulary to check the body against, and accepting one would mean saving a
    customer-facing document whose variables nobody has defined.
    """
    tenant_id = _tenant_id()
    if template.tenant_id != tenant_id:  # belt and braces; RLS is the guarantee
        raise TemplateRefused("that template belongs to another tenant.")

    dated_allowed = template.group in EFFECTIVE_DATED_GROUPS
    if effective_from is not None and not dated_allowed:
        raise TemplateRefused(
            f"{template.code!r} is in the {template.group!r} group and cannot carry an "
            "effective date. BR-NOT-002 makes CONTRACT templates effective-date versioned "
            "and says nothing about any other class; an effective-dated receipt would be a "
            "second publishing model for a class whose spec has one, and two published "
            "versions of it would make 'the current receipt' ambiguous."
        )
    if effective_from is None and dated_allowed:
        raise TemplateRefused(
            f"{template.code!r} is a contract template and every version needs an "
            "`effective_from` (BR-NOT-002: *'generation picks the version in effect'*). "
            "Without one, generation on a date has no rule for choosing between versions — "
            "and the version chosen is frozen onto a signed agreement forever."
        )

    # US-NOT-005 TC-5 / the palette rule, and the OQ-206/207 refusals with it.
    # CR-199-BRC10 S4 — on an email class the closed markup's rules too (no raw
    # HTML; links only to https:// or a link placeholder). `validate_for_save`
    # calls `validate_body` first, so the palette rule is still checked once.
    rendering.validate_for_save(template.code, body, subject=subject, body_format=body_format)

    with transaction.atomic():
        highest = tm.NotificationTemplateVersion.objects.filter(
            tenant_id=tenant_id, template=template
        ).aggregate(top=Max("version"))["top"]
        version = int(highest or 0) + 1
        row = tm.NotificationTemplateVersion.objects.create(
            tenant_id=tenant_id,
            template=template,
            version=version,
            status=tm.VERSION_DRAFT,
            subject=subject,
            preheader=preheader,
            body=body,
            body_format=body_format,
            effective_from=effective_from,
            restored_from_version=restored_from_version,
            created_by=getattr(actor, "id", None),
        )
        # ══ CR-049 TASK 8 · THE ROW ALREADY EXISTED; IT NOW SAYS *WHAT* ══════
        # `BR-NOT-027` part 3: *"any changes to tempalte or any items hsould be
        # noted as changed"*. Hard rule 7 was already satisfied here — this is
        # not a new audit row and there is no new table. What it did not carry
        # was the one fact a reader of an audit trail is looking for.
        #
        # ⚠ **THE MEASUREMENT THAT MADE THAT WORTH FIXING.** `OQ-255` says
        # *"`audit_log` holds the before/after of `template.saved`"*. It holds
        # the before/after of the ROW — class, variant, version number, status,
        # effective date — and NOT ONE CHARACTER of the wording, so the trail
        # could say an edit happened and never what it did.
        #
        # ⚠ **AND THE WORDING ITSELF IS DELIBERATELY NOT COPIED IN HERE.** The
        # version rows ARE the record and migration 0006's trigger makes a
        # published one immutable; a second copy in `audit_log` is a copy that
        # can disagree with the rows it came from (hard-won law 5), and it would
        # put the whole of every letter a utility has ever written into a table
        # nobody prunes. The FIELDS that moved is the fact; the words stay where
        # they are already kept.
        previous = template_changes.previous_of(row)
        audit.money_action(
            actor,
            AUDIT_SAVED,
            AUDIT_ENTITY,
            str(row.pk),
            after={
                "code": template.code,
                "category": template.category,
                "language": template.language,
                "version": version,
                "status": tm.VERSION_DRAFT,
                "effective_from": effective_from.isoformat() if effective_from else None,
                "changed_fields": template_changes.changed_field_names(row, previous),
                "changed_from_version": previous.version if previous is not None else None,
                "restored_from_version": restored_from_version,
            },
        )
    return row


@require_role(SYSTEM_ADMIN, br_ref="BR-BIL-027")
def publish(
    *,
    version_row: tm.NotificationTemplateVersion,
    actor: Any,
    at: datetime | None = None,
) -> tm.NotificationTemplateVersion:
    """System Admin only. Publishing affects FUTURE renders and nothing else.

    US-NOT-006 TC-2: *"Clerk publish server-rejected; Admin publish → v3
    published, v2 auto-archived (one published per template); only renders AFTER
    see v3."* The auto-archive is 04-flows.md §2's *"ARCHIVED (auto on next
    publish, or manual)"*.

    An EFFECTIVE-DATED version (contracts, BR-NOT-002) archives nothing: v1
    effective Jan 1 and v2 effective Sep 1 are both published on Aug 20, which
    is the only way TC-3's *"generation Aug 20 renders v1, generation Sep 2
    renders v2"* can be true. The DDL says the same thing through two partial
    unique indexes; see `template_models.py`.

    Nothing here re-renders anything. J22 step 4: *"Nothing re-renders: July
    bills still (v2, en); the variant catalog change is data, not history
    surgery."*
    """
    tenant_id = _tenant_id()
    if version_row.tenant_id != tenant_id:
        raise TemplateRefused("that version belongs to another tenant.")
    if version_row.status != tm.VERSION_DRAFT:
        raise TemplateRefused(
            f"version {version_row.version} is already {version_row.status!r}. Only a draft "
            "is published, and a published version is never re-published: the lifecycle is "
            "draft → published → archived and it moves one way (04-flows.md §2). To change "
            "a published body, save a new draft — that is what BR-BIL-026's append-only "
            "versions ARE."
        )
    stamped = at or version_row.created_at
    with transaction.atomic():
        superseded: list[int] = []
        if version_row.effective_from is None:
            # BR-BIL-027 — exactly one ORDINARY published version per variant.
            for previous in tm.NotificationTemplateVersion.objects.filter(
                tenant_id=tenant_id,
                template_id=version_row.template_id,
                status=tm.VERSION_PUBLISHED,
                effective_from__isnull=True,
            ):
                previous.status = tm.VERSION_ARCHIVED
                previous.archived_at = stamped
                previous.save(update_fields=["status", "archived_at", "updated_at"])
                superseded.append(previous.version)
        version_row.status = tm.VERSION_PUBLISHED
        version_row.published_by = getattr(actor, "id", None)
        version_row.published_at = stamped
        version_row.save(update_fields=["status", "published_by", "published_at", "updated_at"])
        audit.money_action(
            actor,
            AUDIT_PUBLISHED,
            AUDIT_ENTITY,
            str(version_row.pk),
            before={"status": tm.VERSION_DRAFT},
            after={
                "status": tm.VERSION_PUBLISHED,
                "version": version_row.version,
                "auto_archived_versions": superseded,
                "effective_from": (
                    version_row.effective_from.isoformat() if version_row.effective_from else None
                ),
                # BR-BIL-026 — the rule id stays in the comment (DEF-2377).
                "affects": "future renders only",
            },
        )
    return version_row


@require_role(SYSTEM_ADMIN, br_ref="BR-BIL-027")
def archive(
    *,
    version_row: tm.NotificationTemplateVersion,
    actor: Any,
    at: datetime | None = None,
) -> tm.NotificationTemplateVersion:
    """Manual archive (04-flows.md §2). Retained forever — never deleted."""
    tenant_id = _tenant_id()
    if version_row.tenant_id != tenant_id:
        raise TemplateRefused("that version belongs to another tenant.")
    if version_row.status == tm.VERSION_ARCHIVED:
        return version_row
    before = version_row.status
    version_row.status = tm.VERSION_ARCHIVED
    version_row.archived_at = at or version_row.updated_at
    version_row.save(update_fields=["status", "archived_at", "updated_at"])
    audit.money_action(
        actor,
        AUDIT_ARCHIVED,
        AUDIT_ENTITY,
        str(version_row.pk),
        before={"status": before},
        after={"status": tm.VERSION_ARCHIVED, "version": version_row.version},
    )
    return version_row


def pin_count(version_row: tm.NotificationTemplateVersion) -> int:
    """How many queue rows name this exact version (US-NOT-006 TC-5's 3,412).

    Counts `outbound_messages`, the pins this module owns. Bills pin billing's
    `bill_templates` (r10 #4) and signed contracts have no store yet, so both
    are outside this count — and both are outside what it has to cover, because
    the only deletable version is a DRAFT and a draft has never been pinned by
    anything. Stated rather than left as an apparent oversight.
    """
    return models.OutboundMessage.objects.filter(
        tenant_id=version_row.tenant_id,
        template_id=version_row.template_id,
        template_version=version_row.version,
    ).count()


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-BIL-027")
def delete_version(*, version_row: tm.NotificationTemplateVersion, actor: Any) -> None:
    """Delete an UNPINNED DRAFT. Anything else is refused, forever (TC-5, T5-02).

    T5-02 step 1: *"Action disabled-with-reason: 'pinned by N bills —
    audit-locked'; server refuses a forced call."* Step 4 is the contrast case
    this allows: *"Billing Clerk attempts to delete an UNPINNED draft version
    (v3-draft) → Allowed for drafts (drafts are not pinned by anything)."*

    Migration 0006's trigger refuses a non-draft DELETE in the database too. The
    check here is the readable half — it names the reason a person can act on —
    and it is deliberately NOT the only one: a shell, a data migration and a
    future endpoint all bypass this function and none of them bypasses the
    trigger.
    """
    tenant_id = _tenant_id()
    if version_row.tenant_id != tenant_id:
        raise TemplateRefused("that version belongs to another tenant.")
    if version_row.status != tm.VERSION_DRAFT:
        raise TemplateRefused(
            f"version {version_row.version} is {version_row.status!r} and can never be "
            "deleted. A published or archived version is what an issued document renders "
            "from (BR-BIL-026) — deleting one would orphan every document pinned to it and "
            "make a reprint impossible (NFR-8: retained FOREVER). Archive is the ratified "
            "door, and publishing a NEW version is how a template changes."
        )
    pins = pin_count(version_row)
    if pins:
        raise TemplateRefused(
            f"version {version_row.version} is pinned by {pins} sent message(s) and is "
            "audit-locked (BR-BIL-027). A pinned version can never be deleted: it is the "
            "evidence of what those customers were actually sent."
        )
    identity = {
        "code": version_row.template.code,
        "version": version_row.version,
        "status": version_row.status,
    }
    version_row.delete()
    audit.money_action(actor, AUDIT_DELETED, AUDIT_ENTITY, None, before=identity)


def _variant(
    tenant_id: Any, code: str, category: str, language: str
) -> tm.NotificationTemplate | None:
    return tm.NotificationTemplate.objects.filter(
        tenant_id=tenant_id, code=code, category=category, language=language
    ).first()


def _published_version(
    template: tm.NotificationTemplate, on_date: date | None
) -> tm.NotificationTemplateVersion | None:
    """The version in force — BR-NOT-002's *"the version in effect"* included.

    An ordinary variant has at most one published, undated version and that is
    the answer. A contract variant has several, one per effective date, and the
    answer is the latest whose `effective_from` is on or before `on_date`:
    US-NOT-006 TC-3, *"generation Aug 20 renders v1, generation Sep 2 renders
    v2"*. A contract asked for with no date has no defensible answer and gets
    None rather than the newest — the newest may not be in force yet, and a
    contract is signed.
    """
    published = tm.NotificationTemplateVersion.objects.filter(
        tenant_id=template.tenant_id, template=template, status=tm.VERSION_PUBLISHED
    )
    undated = published.filter(effective_from__isnull=True).first()
    if undated is not None:
        return undated
    if on_date is None:
        return None
    return (
        published.filter(effective_from__lte=on_date)
        .order_by("-effective_from", "-version")
        .first()
    )


def _own_language_is_default(
    tenant_id: Any, code: str, category: str, language: str, on_date: date | None
) -> str:
    """The utility's OWN language tag means its `default` variant once the
    utility has written that variant itself (`DEF-NOT-10683`).

    ⚠ **THE PLATFORM SEEDS A VARIANT IN EVERY ONE OF ITS LANGUAGES, THE
    UTILITY'S OWN INCLUDED.** On an `en-US` utility that is an `en-US` variant
    beside `default`, both English, and the Templates screen shows and edits
    only `default` (it names it *American English*, and `template_variants.
    normalise_language` folds the utility's tag into `default` for every
    write). Every message is queued asking for the utility's language, so
    resolution found the SEEDED `en-US` row first and a clerk's edits never
    went out. Measured on the walk: Brazos Bend's Bill ready email, `default`
    at v3 after a clerk's restore, pinned the seeded `en-US` v1 for an English
    account.

    **Only once a person has published the `default` wording** (its live
    version has an author) does it win. While both rows are the platform's
    seed, the literal row is kept — that is lane TPL-SRV-LANG's judgment 3 for
    a Spanish-default utility whose seeded `es` row is Spanish and whose
    `default` row may still hold the platform's English."""
    if language == tm.VARIANT_DEFAULT:
        return language
    from apps.notifications import tenancy_seam

    own = tenancy_seam.tenant_default_language()
    if not own or language.lower() != own.lower():
        return language
    for try_category in dict.fromkeys((category, tm.VARIANT_DEFAULT)):
        variant = _variant(tenant_id, code, try_category, tm.VARIANT_DEFAULT)
        live = _published_version(variant, on_date) if variant is not None else None
        if live is not None:
            return tm.VARIANT_DEFAULT if live.created_by is not None else language
    return language


def resolve(
    *,
    code: str,
    category: str | None = None,
    language: str | None = None,
    on_date: date | None = None,
    override_template_id: Any = None,
) -> ResolvedTemplate:
    """Pick the version this document will be PINNED to. BR-BIL-025 order.

    account override → exact (category, language) → category fallback (all
    customers, same language) → language fallback (same category, the
    utility's language) → the mandatory `(default, default)` variant.

    `category` and `language` are ARGUMENTS, so a caller that holds them
    passes them and one that does not resolves the default variant. `category`
    is the account's; `language` is the UTILITY's default, never the account's
    preferred language (`OQ-CUS-12619`, 2026-09-23). See the module docstring —
    inventing either read here would put a guess inside somebody's document.

    `on_date` is BR-NOT-002's generation date for contracts and is an argument,
    never a clock (BR-TEN-043): a contract regenerated for an August date must
    resolve August's version whenever the job happens to run.

    Raises `TemplateRefused` when NOTHING resolves. That refusal is the ratified
    hold — field map N-1: *"dispatch holds safely on missing published template;
    content never invented."* It is never a blank document and never the
    "closest" body.
    """
    tenant_id = _tenant_id()
    _class_or_refuse(code)
    wanted_category = category or tm.VARIANT_DEFAULT
    wanted_language = _own_language_is_default(
        tenant_id, code, wanted_category, language or tm.VARIANT_DEFAULT, on_date
    )
    # The pin still CARRIES the utility's tag when it was folded into
    # `default`: the renderer formats money and dates by it, and `default`
    # alone prints "247.30 USD" where `en-US` prints "$247.30".
    folded_from = language if wanted_language != (language or tm.VARIANT_DEFAULT) else None

    if override_template_id is not None:
        # BR-BIL-025 — *"assignment defaults by consumer category, OVERRIDABLE
        # per account"* (`accounts.template_override_id`, r12 #14 D-4). The
        # override wins outright: a utility that pointed one account at a
        # specific variant meant that variant, not a category default that
        # happens to match.
        override = tm.NotificationTemplate.objects.filter(
            tenant_id=tenant_id, pk=override_template_id
        ).first()
        if override is None:
            raise TemplateRefused(
                f"the account's template override {override_template_id!r} names no "
                "template in this tenant. Resolution stops rather than falling through to "
                "a category default: an override that silently did nothing would render a "
                "document the utility deliberately configured away from."
            )
        version_row = _published_version(override, on_date)
        if version_row is None:
            raise TemplateRefused(
                f"the account's override variant ({override.code}, {override.category}, "
                f"{override.language}) has no published version"
                f"{f' in effect on {on_date.isoformat()}' if on_date else ''}. Nothing is "
                "rendered from a draft (BR-BIL-027) and nothing falls back past an explicit "
                "override."
            )
        return ResolvedTemplate(
            template_id=override.pk,
            code=override.code,
            version=version_row.version,
            language=override.language,
            category=override.category,
            via=VIA_ACCOUNT_OVERRIDE,
            fell_back=(override.language, override.category) != (wanted_language, wanted_category),
        )

    # ⚠ **LANGUAGE BEFORE CATEGORY — REORDERED 2026-10-29 (`CR-199-BRC10` S1).**
    # Steps 2 and 3 were the other way round: the category's own
    # default-language variant beat the all-customers variant in the customer's
    # language. That was harmless while every message went in the utility's
    # language; under the PO's ruling B of the same day (*a message goes in the
    # customer's preferred language, English wherever no Spanish version is
    # published*) it sent Rosa — residential, Español — the RESIDENTIAL ENGLISH
    # bill email although an all-customers Spanish one was published. A reader
    # who cannot read the words gains nothing from a closer audience match, so
    # the language is kept first and the category falls back first. Decision
    # log 2026-10-29, *"Templates: customer-category variants"*.
    attempts: tuple[tuple[str, str, str], ...] = (
        (wanted_category, wanted_language, VIA_EXACT),
        (tm.VARIANT_DEFAULT, wanted_language, VIA_CATEGORY_FALLBACK),
        (wanted_category, tm.VARIANT_DEFAULT, VIA_LANGUAGE_FALLBACK),
        (tm.VARIANT_DEFAULT, tm.VARIANT_DEFAULT, VIA_DEFAULT_FALLBACK),
    )
    seen: set[tuple[str, str]] = set()
    for try_category, try_language, via in attempts:
        if (try_category, try_language) in seen:
            continue
        seen.add((try_category, try_language))
        variant = _variant(tenant_id, code, try_category, try_language)
        if variant is None:
            continue
        version_row = _published_version(variant, on_date)
        if version_row is None:
            continue
        return ResolvedTemplate(
            template_id=variant.pk,
            code=code,
            version=version_row.version,
            language=(
                folded_from
                if folded_from is not None and variant.language == tm.VARIANT_DEFAULT
                else variant.language
            ),
            category=variant.category,
            via=via,
            fell_back=via != VIA_EXACT,
        )

    # ⚠ THIS SENTENCE IS SHOWN TO A UTILITY (CR-016, 2026-08-19). It travels as
    # `published_unavailable` and `SettingsNotificationsTab` renders it in the
    # published-body cell whenever `body_unavailable` is null. It used to read
    # "...and BR-NOT-001 requires a 'default' variant precisely so this cannot
    # happen — *'fallback mandatory'*. Nothing is invented and nothing renders:
    # the message HOLDS in the queue with this reason (field map N-1)..." — a
    # rule id, a quoted rule and a field-map reference, on a Settings screen.
    #
    # Provenance for support, which is all that moved: BR-NOT-001 makes a
    # `default` variant MANDATORY precisely so this cannot happen, and the
    # message HOLDS in the queue with this reason (field map N-1) rather than
    # rendering blank — a blank letter posted to a customer is worse than one
    # that has not gone yet.
    raise TemplateRefused(
        f"This utility has no published wording for {code!r} that applies to "
        f"{wanted_category!r} customers in {wanted_language!r}"
        f"{f' on {on_date.isoformat()}' if on_date else ''}. Every message class "
        "needs a default version that applies to everyone, and this one has "
        "none — so anything waiting to go out on it is held rather than sent "
        "with the letter left blank. Publish a default version to release it."
    )


def load_pinned(*, template_id: Any, version: int) -> PinnedBody:
    """The body of an EXACT version. No fallback, no 'latest', no resolution.

    This is what `rendering.render_for_dispatch` calls, and the reason it takes
    an id and a number rather than a code is US-NOT-005 TC-6: *"Render requested
    'on latest version' for an issued document → No such path exists."* A
    reprint three years from now finds the same bytes or finds a refusal — it
    never finds today's template.

    A DRAFT is loadable on purpose: the designers' test-render (BR-BIL-027,
    US-NOT-007 TC-5) previews a draft before anybody publishes it. What a draft
    can never be is PINNED — `resolve` returns published versions only, so no
    queue row can carry one.
    """
    tenant_id = _tenant_id()
    row = (
        tm.NotificationTemplateVersion.objects.select_related("template")
        .filter(tenant_id=tenant_id, template_id=template_id, version=version)
        .first()
    )
    if row is None:
        raise TemplateRefused(
            f"template {template_id} has no version {version} in this tenant. The pin on "
            "the document names a version that is not here — which is the one thing "
            "append-only versioning exists to make impossible, so it is reported rather "
            "than worked around with the nearest match."
        )
    return PinnedBody(
        template_id=row.template_id,
        code=row.template.code,
        version=row.version,
        language=row.template.language,
        category=row.template.category,
        channel=row.template.channel,
        body=row.body,
        subject=row.subject,
        preheader=row.preheader,
        effective_from=row.effective_from,
        body_format=row.body_format,
    )


def published_versions(*, code: str | None = None) -> list[tm.NotificationTemplateVersion]:
    """The S8 card's "Published vN" column — every live version, tenant-scoped."""
    query = Q(tenant_id=_tenant_id(), status=tm.VERSION_PUBLISHED)
    if code:
        query &= Q(template__code=code)
    return list(
        tm.NotificationTemplateVersion.objects.select_related("template")
        .filter(query)
        .order_by("template__group", "template__name", "-version")
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-006@9a4f21c (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md — US-NOT-006 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-001/002/003/006 — · 10-notifications/04-flows.md §2 · 08-qa/01-e2e/journeys/J22-template-life.md + T4-08 + T4-09 + T5-02)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — the template store)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S8 templates-card endpoints are not in this lane; this service is the interface every caller uses) E=deferred(no-frontend-half — S8/S67/S94–S106 designers not reached; REPORTED) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_006_template_lifecycle.py ·
#         guards proved RED before green (hard-won law 7) — transcripts in the
#         lane report: the Admin-only publish gate, the append-only trigger, the
#         audit-lock on a pinned draft, and the pin-is-not-latest separation
# exceptions: (1) `category` AND `language` ARE ARGUMENTS, NOT READS. The
#         category is customers-owned with no published read; the language is
#         the UTILITY's default (OQ-CUS-12619, 2026-09-23 — never the account's
#         preferred language). A caller that passes neither resolves the
#         (default, default) variant — a ratified answer, not a degraded one.
#         Same call `apps/payments/notices.py` makes for the medical-hold flag.
#         (2) THE THREE BILL/STATEMENT CLASSES ARE REFUSED — S91–S93 are
#         billing's (US-BIL-021) and B2 r10 #4 gives them their own tables.
#         (3) A CLASS WITH NO TOKEN CATALOG (OQ-206/207) MAY BE REGISTERED BUT
#         ITS DRAFT CANNOT BE SAVED — there is no vocabulary to validate the body
#         against, and `rendering.validate_body` refuses with the catalog's own
#         reason. The variant exists so the S8 card shows the class awaiting its
#         content rather than pretending it is not ratified.
#         (4) `pin_count` READS `outbound_messages` ONLY. Bills pin billing's
#         registry and signed contracts have no store; both are outside the
#         count and outside what it must cover, because only a DRAFT is ever
#         deletable and a draft has never been pinned.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
