# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 (templates redesign, PO 2026-10-29) — server tasks
#           S1 (customer-category axis), S2 (+ New variant / Duplicate as
#           variant), S3 (Make live again)
#           Screens: Settings › Templates — the template workspace, its
#           New-variant and Duplicate-as-variant dialogs and its History
#           (drawing `05-prototype/templates-redesign-2026-10-29/images/`
#           06, 07, 08, 09, 10, 13, 15, 18)
# Rules:    A1 C (only legal notices need a System Admin's approval) · A3 A (a
#           variant is channel × language × customer category) · A4 B (only the
#           utility's switched-on languages) — decision log 2026-10-29
#           *"twelve questions"* · BR-BIL-026 (an edit is a NEW version; pinned at
#           queue; publishing affects future messages only) · BR-BIL-027
#           (System Admin publishes) · BR-NOT-001 / BR-NOT-006 (the variant axes
#           and the never-blank fallback) · CLAUDE.md rule 1 · rule 4 · rule 7
# Tests:    06-backend/tests/test_cr199_template_variants.py
# ───────────────────────────────────────────────────────
"""Variants and *Make live again* — the two template actions the redesign adds.

THIN ON PURPOSE. Every row is still written by `template_service` (`register`,
`save_draft`, `publish`), so the append-only trigger, the palette check, the role
gates and the audit rows that already guard a template guard these actions too.
This file decides only what is NEW: which combinations are lawful, where a new
variant's wording starts, and what *Make live again* means.

════════════════════════════════════════════════════════════════════════════
WHAT A VARIANT IS (A3 A), AND HOW THE THREE AXES MAP ONTO THE ROWS
════════════════════════════════════════════════════════════════════════════
*"A variant is channel × language × customer category."* The rows already had
two of the three: `notification_templates` is keyed `(code, category, language)`
and the CHANNEL is the class itself — `email_bill_ready` and `sms_bill_ready`
are two classes of one event, each with its own variants and its own history.
So a request for a variant NAMES its channel and the class it is made on must
carry that channel; a mismatch is refused by name rather than quietly creating
an email variant on a text class.

**`default` is "All customers"** on the category axis and **"the utility's own
language"** on the language axis, unchanged. Every row that existed before this
change already reads `category = 'default'` (the seeder writes nothing else), so
"every existing row becomes All customers" needed no data migration — it was
already true, which was measured rather than assumed.

The customer categories are the utility's OWN customer classes (`account_types`,
tenant-owned since the PO's 2026-09-17 *"utility can get their own account
types"*), read through `customers_seam`. ⚠ **PROGRAMMES ARE NOT AN AXIS.** The
drawing shows a *Low-income* option; a drawn value is an illustration (B14 rule
37), and a discount programme cannot be a variant key: an account holds several
enrolments at once and no ruling orders them, so "the most specific variant"
would have no answer. Recorded as a judgment in the decision log the same day.

════════════════════════════════════════════════════════════════════════════
WHICH LANGUAGES ARE "SWITCHED ON" (A4 B) — A JUDGMENT, RECORDED
════════════════════════════════════════════════════════════════════════════
The ruling offers *"only the utility's switched-on languages"*. **Measured: the
product has no per-utility language switch.** Tenancy holds ONE Regional
language (`tenants.language`) and a platform registry of twelve tags it may pick
from. So "switched on" is defined here, from facts the product already holds:

  1. the utility's own Regional language — served as `default`;
  2. every language the utility has itself written a template version in (the
     platform's seeded wording in twelve languages does not count, or every
     language would be on for everyone);
  3. every language at least one of its customers has chosen as their
     preferred language (`accounts.preferred_language`) — under the PO's
     ruling B of the same day a message goes in that language, so it is
     exactly the set this utility must be able to write.

A language outside all three is refused by name. If the PO later wants an
explicit Settings switch, `offered_languages` is the one function that changes.

════════════════════════════════════════════════════════════════════════════
MAKE LIVE AGAIN (S3) — A NEW VERSION, NEVER A MOVED POINTER
════════════════════════════════════════════════════════════════════════════
Two ways to make v1 live again were open: re-publish the v1 ROW, or write v5
holding v1's wording and publish v5. **v5.** The lifecycle moves one way
(draft → published → archived, `template_service.publish` refuses anything
else); re-publishing v1 would overwrite v1's `published_at`, and *when v1 first
went out* is a fact about documents customers already hold. A new row keeps
every existing row byte-identical, needs no change to migration 0006's trigger,
and records `restored_from_version = 1` ON THE ROW (migration 0036) — not only in
`audit_log`, which is pruned (`OQ-1340`). Messages already pinned to v1 or v3
render exactly what they rendered (BR-BIL-026); new messages pin v5.

⚠ **LEGAL NOTICES GO FOR APPROVAL INSTEAD (A1 C).** A class whose catalog makes
the regulator's reference mandatory (`{state_puc_ref}` — the disconnection
notice and its three tiers) is a LEGAL NOTICE. For one of those, *Make live
again* writes the copy as a DRAFT and stops: the existing approval path is the
System Admin publishing that draft (BR-BIL-027), and the version going out today
keeps going out until then. The response says which of the two happened.

Contract classes (effective-dated, BR-NOT-002) are refused: a contract version
is published FOR A DATE, so "make it live again" has no date to mean. The
existing *Restore* (a draft the admin dates and publishes) is their path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.notifications import catalogs, customers_seam, tenancy_seam, template_service
from apps.notifications import template_models as tm
from core import audit

#: The regulator's reference a LEGAL notice may never ship without (A19 r8,
#: US-NOT-007 TC-6). The existing flag A1 C's *"legal notices"* is read from —
#: a class is a legal notice exactly when its catalog makes this mandatory.
LEGAL_NOTICE_MARKER = "{state_puc_ref}"

START_BLANK = "blank"
START_PUBLISHED = "published"
START_VARIANT = "variant"
START_FROM = (START_BLANK, START_PUBLISHED, START_VARIANT)

OUTCOME_LIVE = "live"
OUTCOME_SENT_FOR_APPROVAL = "sent_for_approval"

AUDIT_VARIANT_CREATED = "template.variant_created"
AUDIT_MADE_LIVE_AGAIN = "template.made_live_again"

#: The words a screen draws for the `default` category. Served, so no client
#: types the label out by hand (hard-won law 2's sign-up lesson).
ALL_CUSTOMERS_LABEL = "All customers"


class VariantRefused(template_service.TemplateRefused):
    """A refusal a person can act on, carrying the `message_key` the screen
    shows. `str()` is the diagnostic sentence for support and the server log;
    the clerk reads the catalogue entry for `key` (BR-SHL-020 r2)."""

    def __init__(self, key: str, detail: str, *, params: dict[str, Any] | None = None):
        super().__init__(detail)
        self.key = key
        self.params = params or {}


# ── refusal keys (each in all eleven locale catalogues) ────────────────────
KEY_CHANNEL_MISMATCH = "notifications.templates.variant.channelMismatch"
KEY_LANGUAGE_NOT_ON = "notifications.templates.variant.languageNotOn"
KEY_CATEGORY_UNKNOWN = "notifications.templates.variant.categoryUnknown"
KEY_EXISTS = "notifications.templates.variant.exists"
KEY_NO_SOURCE_WORDING = "notifications.templates.variant.noSourceWording"
KEY_NOT_EARLIER_PUBLISHED = "notifications.templates.history.notEarlierPublished"
KEY_ALREADY_LIVE = "notifications.templates.history.alreadyLive"
KEY_CONTRACT_HAS_DATES = "notifications.templates.history.contractHasDates"


def _tenant_id() -> Any:
    return template_service._tenant_id()


def is_legal_notice(code: str) -> bool:
    """A1 C — does publishing this class go through a System Admin's approval?"""
    klass = catalogs.catalog_for(code)
    return klass is not None and LEGAL_NOTICE_MARKER in tuple(klass.mandatory_content)


# ══════════════════════════════════════════════════════════════════════════
# THE TWO PICK LISTS
# ══════════════════════════════════════════════════════════════════════════
def offered_categories() -> list[dict[str, str]]:
    """`[{value, label}]` — *All customers* first, then the utility's ACTIVE
    customer classes in their own picker order."""
    rows = [{"value": tm.VARIANT_DEFAULT, "label": ALL_CUSTOMERS_LABEL}]
    for row in customers_seam.account_category_options() or []:
        if row["value"] != tm.VARIANT_DEFAULT:
            rows.append(row)
    return rows


def utility_language() -> str | None:
    """The utility's Regional language tag — what `default` means today."""
    return tenancy_seam.tenant_default_language()


def offered_languages() -> list[dict[str, Any]]:
    """`[{value, code, is_utility_language}]` — A4 B's switched-on set.

    `value` is what a request sends (`default` for the utility's own language);
    `code` is the BCP-47 tag a screen names it by. See the module docstring for
    why the set is these three sources and nothing else.
    """
    own = utility_language()
    # AUTHORED by the utility — a version with a person on it. Measured: the
    # provisioning seeder plants several classes in EVERY platform language
    # (`seed_language_variants`, CR-188), so "any variant in the language"
    # would switch all twelve on for every utility and make A4 B say nothing.
    written = set(
        tm.NotificationTemplateVersion.objects.filter(tenant_id=_tenant_id())
        .exclude(template__language=tm.VARIANT_DEFAULT)
        .exclude(created_by__isnull=True)
        .values_list("template__language", flat=True)
        .distinct()
    )
    chosen = set(customers_seam.preferred_languages_in_use())
    others = sorted((written | chosen) - {own, tm.VARIANT_DEFAULT, ""})
    rows: list[dict[str, Any]] = [
        {"value": tm.VARIANT_DEFAULT, "code": own, "is_utility_language": True}
    ]
    rows.extend({"value": tag, "code": tag, "is_utility_language": False} for tag in others)
    return rows


def normalise_language(raw: Any) -> str:
    """`""`/`default`/the utility's own tag → `default`; anything else as sent.

    The utility's own language IS the `default` variant — a separate `en` row
    beside `(…, default)` would be two variants of one language, and resolution
    would pick between them by which code a writer happened to pass.
    """
    value = str(raw or "").strip()
    if not value or value == tm.VARIANT_DEFAULT:
        return tm.VARIANT_DEFAULT
    own = utility_language()
    if own and value.lower() == own.lower():
        return tm.VARIANT_DEFAULT
    return value


def normalise_category(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value or value in (tm.VARIANT_DEFAULT, "all"):
        return tm.VARIANT_DEFAULT
    return value


# ══════════════════════════════════════════════════════════════════════════
# S2 — + NEW VARIANT / DUPLICATE AS VARIANT
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class NewVariant:
    variant: tm.NotificationTemplate
    version: tm.NotificationTemplateVersion | None
    started_from_version: int | None


def _label_of(category: str, language: str) -> str:
    who = ALL_CUSTOMERS_LABEL if category == tm.VARIANT_DEFAULT else category
    tongue = (utility_language() or "utility language") if language == tm.VARIANT_DEFAULT else language
    return f"{who} · {tongue}"


def _source_version(
    code: str, start_from: str, source_variant_id: Any
) -> tm.NotificationTemplateVersion | None:
    """The version whose wording a new variant starts from, or None for blank.

    `published` with no variant named → the All-customers / utility-language
    variant's published wording (what *Start from English* means in the drawing).
    `variant` → the named variant's published wording, else its newest version
    (*Duplicate as variant* copies what is on screen, which for a variant never
    published is its draft).
    """
    if start_from == START_BLANK:
        return None
    tenant_id = _tenant_id()
    variants = tm.NotificationTemplate.objects.filter(tenant_id=tenant_id, code=code)
    if source_variant_id:
        try:
            source = variants.filter(pk=source_variant_id).first()
        except (DjangoValidationError, ValueError, TypeError):  # a malformed id is an absent one
            source = None
    else:
        source = variants.filter(
            category=tm.VARIANT_DEFAULT, language=tm.VARIANT_DEFAULT
        ).first()
    if source is None:
        raise VariantRefused(
            KEY_NO_SOURCE_WORDING,
            f"there is no variant of {code!r} to start from. Start from blank instead.",
        )
    versions = tm.NotificationTemplateVersion.objects.filter(tenant_id=tenant_id, template=source)
    chosen = (
        versions.filter(status=tm.VERSION_PUBLISHED).order_by("-version").first()
        or (versions.order_by("-version").first() if start_from == START_VARIANT else None)
    )
    if chosen is None:
        raise VariantRefused(
            KEY_NO_SOURCE_WORDING,
            f"the {source.category}/{source.language} variant of {code!r} has no wording to "
            "copy. Start from blank instead.",
        )
    return chosen


def create_variant(
    *,
    code: str,
    actor: Any,
    language: Any,
    category: Any,
    channel: str | None = None,
    start_from: str = START_PUBLISHED,
    source_variant_id: Any = None,
    effective_from: date | None = None,
    name: str | None = None,
) -> NewVariant:
    """Create ONE new variant as a DRAFT. Refuses, by name, every combination
    the ruling does not allow. Nothing here publishes anything."""
    tenant_id = _tenant_id()
    _group, class_channel = template_service._class_or_refuse(code)
    if channel and channel != class_channel:
        raise VariantRefused(
            KEY_CHANNEL_MISMATCH,
            f"{code!r} is a {class_channel} template; a {channel} variant is made on the "
            "matching class of the same event.",
            params={"channel": class_channel},
        )
    wanted_language = normalise_language(language)
    if wanted_language != tm.VARIANT_DEFAULT and wanted_language not in {
        row["value"] for row in offered_languages()
    }:
        raise VariantRefused(
            KEY_LANGUAGE_NOT_ON,
            f"{wanted_language!r} is not one of this utility's languages (A4 B).",
            params={"language": wanted_language},
        )
    wanted_category = normalise_category(category)
    if wanted_category not in {row["value"] for row in offered_categories()}:
        raise VariantRefused(
            KEY_CATEGORY_UNKNOWN,
            f"{wanted_category!r} is not one of this utility's customer categories.",
            params={"category": wanted_category},
        )
    if tm.NotificationTemplate.objects.filter(
        tenant_id=tenant_id, code=code, category=wanted_category, language=wanted_language
    ).exists():
        label = _label_of(wanted_category, wanted_language)
        raise VariantRefused(
            KEY_EXISTS,
            f"{label} already exists for {code!r}; open it to change its wording.",
            params={"variant": label},
        )
    if start_from not in START_FROM:
        start_from = START_PUBLISHED
    source = _source_version(code, start_from, source_variant_id)
    listing = catalogs.LISTINGS.get(code)
    with transaction.atomic():
        variant, _created = template_service.register(
            code=code,
            name=(name or "").strip() or str(getattr(listing, "name", None) or code),
            actor=actor,
            category=wanted_category,
            language=wanted_language,
        )
        version = None
        if source is not None:
            version = template_service.save_draft(
                template=variant,
                body=source.body,
                subject=source.subject,
                preheader=source.preheader,
                actor=actor,
                effective_from=effective_from or source.effective_from,
                # CR-199-BRC10 S4 (lane C) — the layout travels with the words.
                body_format=source.body_format,
            )
        audit.money_action(
            actor,
            AUDIT_VARIANT_CREATED,
            "notification_template",
            str(variant.pk),
            after={
                "code": code,
                "channel": class_channel,
                "category": wanted_category,
                "language": wanted_language,
                "start_from": start_from,
                "started_from_template_id": str(source.template_id) if source else None,
                "started_from_version": source.version if source else None,
                "draft_version": version.version if version else None,
            },
        )
    return NewVariant(
        variant=variant,
        version=version,
        started_from_version=source.version if source is not None else None,
    )


# ══════════════════════════════════════════════════════════════════════════
# S3 — MAKE AN EARLIER PUBLISHED VERSION LIVE AGAIN
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MadeLiveAgain:
    outcome: str  # OUTCOME_LIVE | OUTCOME_SENT_FOR_APPROVAL
    version: tm.NotificationTemplateVersion
    restored_from_version: int
    replaced_version: int | None


def was_published_before(row: tm.NotificationTemplateVersion) -> bool:
    """An EARLIER published version: archived after having gone out. An archived
    row that was never published (a draft archived by hand) was never live.

    ⚠ `published_at` ALONE IS NOT THE SIGNAL — measured on a provisioned
    utility: the platform's seeded wording (drawing 07's *"v1 · Platform
    default"*) is written PUBLISHED with `created_by = NULL` and, when the
    seeder is given no timestamp, `published_at = NULL` too. So a version also
    counts when nobody authored it: the seeder is the only writer that leaves
    `created_by` empty, and it only ever writes published rows. A human draft
    always carries its author (`template_service.save_draft` stamps the actor).
    """
    if row.status != tm.VERSION_ARCHIVED:
        return False
    return row.published_at is not None or row.published_by is not None or row.created_by is None


def make_live_again(*, version_row: tm.NotificationTemplateVersion, actor: Any) -> MadeLiveAgain:
    """Copy an earlier published version's wording into a NEW version and make
    it live — or, for a legal notice, leave it as a draft for approval."""
    tenant_id = _tenant_id()
    if version_row.tenant_id != tenant_id:  # belt and braces; RLS is the guarantee
        raise template_service.TemplateRefused("that version belongs to another tenant.")
    variant = version_row.template
    if variant.group in template_service.EFFECTIVE_DATED_GROUPS:
        raise VariantRefused(
            KEY_CONTRACT_HAS_DATES,
            "a contract version is published for a date; restore it as a draft and give it "
            "a date instead.",
        )
    if version_row.status == tm.VERSION_PUBLISHED:
        raise VariantRefused(
            KEY_ALREADY_LIVE,
            f"v{version_row.version} is the version going out now.",
            params={"version": version_row.version},
        )
    if not was_published_before(version_row):
        raise VariantRefused(
            KEY_NOT_EARLIER_PUBLISHED,
            f"v{version_row.version} was never published, so it cannot be made live again; "
            "open it and publish it instead.",
            params={"version": version_row.version},
        )
    live = (
        tm.NotificationTemplateVersion.objects.filter(
            tenant_id=tenant_id, template=variant, status=tm.VERSION_PUBLISHED
        )
        .order_by("-version")
        .first()
    )
    legal = is_legal_notice(variant.code)
    with transaction.atomic():
        copy = template_service.save_draft(
            template=variant,
            body=version_row.body,
            subject=version_row.subject,
            preheader=version_row.preheader,
            actor=actor,
            restored_from_version=version_row.version,
            # CR-199-BRC10 S4 (lane C) — v1 goes out again exactly as it was laid out.
            body_format=version_row.body_format,
        )
        if not legal:
            copy = template_service.publish(version_row=copy, actor=actor)
        outcome = OUTCOME_SENT_FOR_APPROVAL if legal else OUTCOME_LIVE
        audit.money_action(
            actor,
            AUDIT_MADE_LIVE_AGAIN,
            template_service.AUDIT_ENTITY,
            str(copy.pk),
            before={"live_version": live.version if live is not None else None},
            after={
                "code": variant.code,
                "category": variant.category,
                "language": variant.language,
                "version": copy.version,
                "restored_from_version": version_row.version,
                "outcome": outcome,
            },
        )
    return MadeLiveAgain(
        outcome=outcome,
        version=copy,
        restored_from_version=version_row.version,
        replaced_version=(live.version if live is not None and not legal else None),
    )
