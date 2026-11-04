# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 lane TPL-SRV-FACETS (DEF-NOT-10672) — the Templates
#           list's channel chips, Languages column and Language/Status filters
#           (drawing `05-prototype/templates-redesign-2026-10-29/images/01-list.png`)
# Rules:    BR-SHL-011 (list grammar; an unknown `f.*` value falls back) ·
#           A4 B (a utility's languages are the switched-on set —
#           `template_variants.offered_languages`, the ONE definition) ·
#           A1 C (a legal notice needs approval) · NFR-3 (server pagination) ·
#           NFR-5 (no cap) · CLAUDE.md rule 1 (every query tenant-filtered)
# Tests:    06-backend/tests/test_cr199_template_list_facets.py
# ───────────────────────────────────────────────────────
"""The tenant's facts behind each row of `GET /template-catalog`, read in
GROUPED statements, and the list's facets.

WHY THE ROWS ARE FILTERED HERE AND NOT IN A WHERE CLAUSE — argued on this
list's own facts, not by reference to any other read: a row of this list is a
template CLASS, and the classes are platform vocabulary held in
`catalogs.listable_codes()` (87 on 2026-10-29), identical on every tenant. The
row count therefore does not grow with a utility's accounts, customers or
messages — T5 and T7 list the same 87 rows. What DOES grow is the tenant's own
variant and version rows, and those are read here in three grouped statements
whatever their number (one per-tenant fact table), never per row. The previous
read asked three questions per class — 257 statements for one page, 11 now — and
`test_cr199_template_list_facets.py` holds the bound.

THE STATUS IS ONE OF THREE, EXACTLY AS THE ROW'S PILL READS. `draft` (a saved
draft is waiting) beats `published` (a live undated version goes out) beats
`not_published`. They are exclusive so the three counts add up to the list, and
a row filtered under *Published* never shows the *Draft waiting* pill.
`needs_approval` is a separate fact (a legal notice, A1 C) and its own option.

A LANGUAGE IS WRITTEN for a class when some variant of the class in that
language holds a draft or a published version — wording that goes out or is
about to. An archived-only variant is not written: nothing of it goes out.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count, OuterRef, Q, Subquery

from apps.notifications import models, template_variants
from apps.notifications import template_models as tm
from core import tenancy as core_tenancy

#: The chips, in the drawing's order: Email · Text · In-app · Letter.
LIST_CHANNELS: tuple[str, ...] = (
    models.CHANNEL_EMAIL,
    models.CHANNEL_SMS,
    models.CHANNEL_IN_APP,
    models.CHANNEL_PRINT,
)

STATUS_PUBLISHED = "published"
STATUS_DRAFT = "draft"
STATUS_NOT_PUBLISHED = "not_published"
STATUS_NEEDS_APPROVAL = "needs_approval"
#: The Status filter's options, in the drawing's order. The keys are the
#: screen's own (`templates.list.statusOption.<key>` in all eleven catalogues).
LIST_STATUSES: tuple[str, ...] = (
    STATUS_PUBLISHED,
    STATUS_DRAFT,
    STATUS_NOT_PUBLISHED,
    STATUS_NEEDS_APPROVAL,
)


@dataclass
class ClassFacts:
    """What this tenant has written for one class."""

    variants: int = 0
    has_published: bool = False
    has_draft: bool = False
    #: Variant `language` values (`default` = the utility's own) holding a
    #: draft or a published version.
    written: set[str] = field(default_factory=set)
    latest: tm.NotificationTemplateVersion | None = None


def tenant_facts() -> dict[str, ClassFacts]:
    """Every class's facts for the tenant in context — three statements."""
    tenant_id = core_tenancy.current_tenant_id()
    facts: dict[str, ClassFacts] = defaultdict(ClassFacts)

    for row in (
        tm.NotificationTemplate.objects.filter(tenant_id=tenant_id)
        .values("code")
        .annotate(n=Count("id"))
    ):
        facts[row["code"]].variants = row["n"]

    for row in (
        tm.NotificationTemplateVersion.objects.filter(
            tenant_id=tenant_id, status__in=(tm.VERSION_DRAFT, tm.VERSION_PUBLISHED)
        )
        .values("template__code", "template__language", "status")
        .annotate(undated=Count("id", filter=Q(effective_from__isnull=True)))
    ):
        fact = facts[row["template__code"]]
        fact.written.add(row["template__language"])
        if row["status"] == tm.VERSION_DRAFT:
            fact.has_draft = True
        elif row["undated"]:
            # The same test `_live_version` makes: an UNDATED published row.
            fact.has_published = True

    latest_per_class = tm.NotificationTemplateVersion.objects.filter(
        tenant_id=tenant_id, template__code=OuterRef("template__code")
    ).order_by("-updated_at", "-id")
    for version in tm.NotificationTemplateVersion.objects.filter(
        tenant_id=tenant_id, pk=Subquery(latest_per_class.values("pk")[:1])
    ).select_related("template"):
        facts[version.template.code].latest = version
    return facts


def row_status(fact: ClassFacts) -> str:
    if fact.has_draft:
        return STATUS_DRAFT
    if fact.has_published:
        return STATUS_PUBLISHED
    return STATUS_NOT_PUBLISHED


def row_languages(fact: ClassFacts, offered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each switched-on language, written or not. `code` is the BCP-47 tag;
    the screen names it in its own words (`languageName`), so no second table
    of language names is kept here."""
    return [
        {
            "code": language["code"] or language["value"],
            "written": language["value"] in fact.written,
        }
        for language in offered
    ]


def language_value(raw: str | None, offered: list[dict[str, Any]]) -> str | None:
    """`f.language` → the variant value it means, or None (fall back) for a
    language this utility has not switched on."""
    if not raw:
        return None
    value = template_variants.normalise_language(raw)
    if any(language["value"] == value for language in offered):
        return value
    return None


def matches(
    row: dict[str, Any],
    fact: ClassFacts,
    *,
    channel: str | None,
    language: str | None,
    status: str | None,
) -> bool:
    if channel is not None and row["channel"] != channel:
        return False
    if language is not None and language not in fact.written:
        return False
    if status == STATUS_NEEDS_APPROVAL:
        return bool(row["needs_approval"])
    if status is not None and row["status"] != status:
        return False
    return True


def facets(
    rows: list[dict[str, Any]],
    facts: dict[str, ClassFacts],
    offered: list[dict[str, Any]],
    *,
    channel: str | None,
    language: str | None,
    status: str | None,
) -> dict[str, Any]:
    """Each facet counted over the rows every OTHER filter leaves, so a chip
    says what choosing it would return. `rows` are already searched and
    category/kind-filtered; never a page."""

    def keep(**override: Any) -> list[dict[str, Any]]:
        chosen = {"channel": channel, "language": language, "status": status, **override}
        return [row for row in rows if matches(row, facts[row["code"]], **chosen)]

    by_channel = keep(channel=None)
    by_language = keep(language=None)
    by_status = keep(status=None)
    return {
        "channels": [
            {"key": key, "count": sum(1 for row in by_channel if row["channel"] == key)}
            for key in LIST_CHANNELS
        ],
        "channels_total": len(by_channel),
        "languages": [
            {
                "key": entry["code"] or entry["value"],
                "count": sum(
                    1 for row in by_language if entry["value"] in facts[row["code"]].written
                ),
            }
            for entry in offered
        ],
        "statuses": [
            {
                "key": key,
                "count": sum(
                    1
                    for row in by_status
                    if (row["needs_approval"] if key == STATUS_NEEDS_APPROVAL else row["status"] == key)
                ),
            }
            for key in LIST_STATUSES
        ],
    }
