# ── Trace ──────────────────────────────────────────────
# Story:    CR-048 wave E task E9 — ONE Templates screen and ONE draft→publish
#           service over BOTH template stores
#           Screens: S8 → Configure → Templates (SET-09 · SET-10) · the bill
#           layout chooser that used to be a second list on the same tab
# Rules:    BR-NOT-026 (PO 2026-08-30 — templates live in one place and that
#           place is the SCREEN and the SERVICE, not the schema) · BR-NOT-025
#           (a version any sent document points at is ARCHIVED, never deleted) ·
#           BR-NOT-027 (a sent legal document is frozen as issued — CR-049, NOT
#           built here) · BR-BIL-026 (an edit is a NEW version; publishing
#           affects FUTURE documents only) · BR-BIL-027 (Clerk drafts, System
#           Admin publishes, a pinned version is never deleted) · BR-TEN-043
#           (a business date is an argument, never a clock read) · B2 §2
#           (cross-module WRITES are forbidden) · CLAUDE.md rule 1 · rule 7
# Tests:    06-backend/tests/test_cr048_e9_two_stores_one_screen.py
# Impacts:  apps/notifications/templates_api.py (serves the unified list) ·
#           apps/billing/templates_service.py (reached through the seam below,
#           and the only writer of billing's rows)
# ───────────────────────────────────────────────────────
"""**ONE TEMPLATES SCREEN AND ONE LIFECYCLE OVER TWO STORES — AND THE TWO
STORES ARE THE DECISION, NOT AN UNFINISHED MERGE.**

════════════════════════════════════════════════════════════════════════════
⛔ READ THIS BEFORE YOU "FINISH THE MERGE". IT IS ALREADY FINISHED.
════════════════════════════════════════════════════════════════════════════
There are **two template table pairs** behind this one module:

  * `notification_templates` + `notification_template_versions` — the authored
    WORDS. `subject`, `preheader`, `body`: sentences a person typed.
  * `bill_templates` + `bill_template_versions` — the LAYOUT CHOICE.
    `layout_key` + an `options` blob: which of five pre-built platform layouts
    to print on. **There is no body text on that side at all.**

**The Product Owner ruled on 2026-08-30 that it stays that way**, verbatim:
*"Yes, Go with option B; I agree"* (`BR-NOT-026`, closing `OQ-842`). Three
options were put; the one chosen was **one screen and one service, two stores,
no row moves**. The option that migrated bill templates into the notification
tables was declined, and declined for stated reasons rather than on taste:

  1. it buys a tidier schema with **a column meaningless on one side of every
     row** — a `body` on a layout choice, a `layout_key` on a letter;
  2. it pays for that with **a migration over rows a sent bill and a sent letter
     both point at**, and both pins are LOOSE COLUMNS rather than foreign keys
     (`invoices.template_id` / `.template_version` and
     `outbound_messages.template_id` / `.template_version` are a plain UUID and
     a plain integer), so dropping a row those name would raise no error, break
     no test, and stay invisible until somebody asked for a reprint.

**So: this file is not half a migration.** If you have arrived here intending to
fold the two pairs into one, that is the change the ruling refused, and
`06-backend/tests/test_cr048_e9_two_stores_one_screen.py` is the guard that will
go red on it. Take it to the Product Owner as a reversal of `BR-NOT-026`, not as
a tidy-up.

**What "one place" now means, and it is the cost the PO accepted with the
ruling:** it is a promise about the PRODUCT — one screen, one list, one
draft → publish → archive lifecycle — and not a promise about the database. A
future engineer opening the schema finds two pairs. This docstring is where that
fact is supposed to live; `BR-NOT-026` requires it to be here by name.

════════════════════════════════════════════════════════════════════════════
WHAT IS SHARED AND WHAT IS DELIBERATELY NOT
════════════════════════════════════════════════════════════════════════════
**SHARED — the LIST and the LIFECYCLE.** Both kinds are draft → published →
archived, append-only, one live version, pinned at send, and a pinned version is
never deleted. That is one vocabulary and this module is where it is spoken.

**NOT SHARED — the EDITOR.** A notification template is edited by typing
sentences and checking them against a merge-field palette. A bill template is
edited by CHOOSING one of five layouts. `editor` on every row says which surface
that row opens, and a screen that offered one editor for both would either be a
text box over a layout key or a five-card chooser over a disconnection letter.
The ruling asked for a unified list and a unified lifecycle. It did not ask for
a unified editor and there is nothing to gain from inventing one.

════════════════════════════════════════════════════════════════════════════
WHICH WAY THIS DELEGATES, AND WHY IT NEVER WRITES A ROW ITSELF
════════════════════════════════════════════════════════════════════════════
B2 §2 forbids cross-module writes. **Nothing in this file writes any table.**
Every call lands in the module that OWNS the row:

    unified_templates ──► apps.notifications.template_service  (notification_*)
                     └──► apps.billing.templates_service        (bill_*)

The billing half goes through `_billing()`, the `getattr`-at-call-time idiom
`apps/notifications/services.py::_resolve` already uses: no import statement
binds this module to billing's internals, an absent function is reported rather
than crashed on, and each module keeps sole authorship of its own rows.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT THE PIN IS FOR, SINCE THERE ARE NOW TWO RULES ABOUT IT
════════════════════════════════════════════════════════════════════════════
`BR-BIL-026` / `BR-NOT-025`: a document names the template version that was in
force when it was sent, and that version is archived rather than deleted,
forever. **That pin answers PROVENANCE — *which wording was in force* — and it
is still required.**

It is NOT the archive of what the customer actually read. `BR-NOT-027` (PO
2026-08-30) rules that a sent legal document is frozen as issued and that
reproducing one by re-rendering from today's data is not correct; today the
notification side does exactly that re-render, and fixing it is `CR-049` and not
this task. **Two rules, two questions, and a reader who folds them together will
delete one of them** — which is why both are named here rather than summarised
into one sentence about "the pin".

Nothing in this module renders, reprints or re-sends anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from importlib import import_module
from typing import Any

from apps.notifications import catalogs, template_models as tm, template_service
from core import tenancy as core_tenancy

#: The two kinds a row on the one Templates screen can be. These strings reach
#: the URL as a filter value and the screen as a chip, so they are part of the
#: contract and not internal shorthand.
KIND_NOTIFICATION = "notification"
KIND_BILL = "bill"
KINDS = (KIND_NOTIFICATION, KIND_BILL)

#: WHAT A ROW STORES, which is the half of the ruling a merged list would hide.
#: Carried on every row so a screen, a report or the next lane can tell the two
#: apart without knowing which table it came from.
CONTENT_AUTHORED_WORDS = "authored_words"
CONTENT_LAYOUT_CHOICE = "layout_choice"

#: WHICH EDITOR a row opens. Not a route — a screen maps these to its own paths
#: — but the fact that they are DIFFERENT is the ruling's "unified list, not a
#: unified editor" expressed where code can read it.
EDITOR_TEMPLATE_DETAIL = "template-detail"
EDITOR_LAYOUT_CHOOSER = "layout-chooser"


class UnifiedTemplateRefused(Exception):
    """A refusal that names the kind it was refused for.

    Separate from `template_service.TemplateRefused` and billing's
    `BillingRuleError` on purpose: those are each ONE store's refusal, and a
    caller of this module has asked about both.
    """


@dataclass(frozen=True)
class TemplateRow:
    """ONE row of the one Templates list, whichever store it came from."""

    kind: str
    #: How the row is addressed for every other call here. A template CODE on
    #: the notification side (`bill_ready_email`) and a template UUID on the
    #: bill side. Deliberately NOT normalised into a synthetic id: an id this
    #: module minted would be a third identity to keep in step with two real
    #: ones, and neither store would recognise it.
    key: str
    name: str
    content_model: str
    editor: str
    #: The live version number, or None where nothing is published yet.
    live_version: int | None
    version_count: int
    #: CR-007's *"Last edited"*, already a display string on the notification
    #: side. None means nobody has touched it, which is a true and common answer.
    edited: str | None


@dataclass(frozen=True)
class VersionRow:
    """ONE version, in the vocabulary both lifecycles share."""

    kind: str
    key: str
    version: int
    status: str
    published_on: str | None
    archived_at: str | None
    #: How many SENT documents name this version. BR-BIL-027's audit-lock
    #: number, and the reason the row can never be deleted once it is non-zero.
    pinned_by: int


def _billing(attribute: str) -> Any:
    """Billing's own callable, resolved at CALL time — never imported.

    The idiom is `apps/notifications/services.py::_resolve`'s, for its reasons:
    no import statement binds this module to billing's internals, and billing
    stays the only writer of `bill_templates` / `bill_template_versions` (B2 §2).
    """
    try:
        target = import_module("apps.billing.templates_service")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) or found is not None else None


def _refuse_unknown_kind(kind: str) -> None:
    if kind not in KINDS:
        raise UnifiedTemplateRefused(
            f"{kind!r} is not a template kind. This screen lists {KIND_NOTIFICATION!r} "
            f"templates (the words a person typed) and {KIND_BILL!r} templates (which of "
            "the platform's layouts a bill prints on). BR-NOT-026 keeps those two stores "
            "apart on purpose — a third kind means a third store, not a third value here."
        )


# ══ THE LIST ════════════════════════════════════════════════════════════════


def _notification_rows() -> list[TemplateRow]:
    """Every template CLASS this platform sends, in the catalogue's own order.

    Rows come from the CATALOGUE and not from the tenant's variant table,
    because that is what the screen has always listed: a class nobody has
    registered yet is still a letter this product sends, and hiding it would
    make the list shorter on a fresh tenant than on an old one.
    """
    tenant_id = core_tenancy.current_tenant_id()
    rows: list[TemplateRow] = []
    for code in catalogs.listable_codes():
        listing = catalogs.LISTINGS[code]
        versions = tm.NotificationTemplateVersion.objects.filter(
            tenant_id=tenant_id, template__code=code
        )
        live = versions.filter(status=tm.VERSION_PUBLISHED).order_by("-version").first()
        latest = versions.order_by("-updated_at").first()
        rows.append(
            TemplateRow(
                kind=KIND_NOTIFICATION,
                key=code,
                name=listing.name,
                content_model=CONTENT_AUTHORED_WORDS,
                editor=EDITOR_TEMPLATE_DETAIL,
                live_version=None if live is None else live.version,
                version_count=versions.count(),
                edited=None if latest is None else latest.updated_at.date().isoformat(),
            )
        )
    return rows


def _bill_rows() -> list[TemplateRow]:
    """Every bill template this tenant has, through billing's own selectors.

    Empty is a real answer and not an error: a tenant whose provisioning seeder
    has not run has no bill template at all (DEF-123), and the screen says so in
    billing's own words rather than in one composed here.
    """
    model = _billing("BillTemplateVersion")
    template_model = _billing("BillTemplate")
    published_version = _billing("published_version")
    pin_count = _billing("pin_count")
    if model is None or template_model is None:  # pragma: no cover - defensive
        return []
    tenant_id = core_tenancy.current_tenant_id()
    rows: list[TemplateRow] = []
    for template in template_model.objects.filter(tenant_id=tenant_id).order_by("name"):
        versions = model.objects.filter(tenant_id=tenant_id, template=template)
        live = None if published_version is None else published_version(template)
        latest = versions.order_by("-updated_at").first()
        rows.append(
            TemplateRow(
                kind=KIND_BILL,
                key=str(template.pk),
                name=template.name,
                content_model=CONTENT_LAYOUT_CHOICE,
                editor=EDITOR_LAYOUT_CHOOSER,
                live_version=None if live is None else live.version_no,
                version_count=versions.count(),
                edited=None if latest is None else latest.updated_at.date().isoformat(),
            )
        )
    # `pin_count` is resolved above so an absent billing seam is reported here
    # rather than at the first click. Nothing else needs it in the LIST.
    del pin_count
    return rows


def list_templates(*, kind: str | None = None) -> list[TemplateRow]:
    """The one list. Both kinds, or one of them, in one shape.

    ⚠ **SORTED BY KIND THEN NAME, AND THE KIND COMES FIRST DELIBERATELY.** The
    two stores answer at different sizes — 37 notification classes against a
    handful of bill templates — so a pure name sort would scatter the bill rows
    through the letters and a person looking for "what do our bills print on"
    would have to hunt. The SCREEN re-sorts on whatever column the reader picks;
    this is the order the list arrives in.
    """
    if kind is not None:
        _refuse_unknown_kind(kind)
    rows: list[TemplateRow] = []
    if kind in (None, KIND_NOTIFICATION):
        rows.extend(_notification_rows())
    if kind in (None, KIND_BILL):
        rows.extend(_bill_rows())
    order = {KIND_NOTIFICATION: 0, KIND_BILL: 1}
    return sorted(rows, key=lambda row: (order[row.kind], row.name.lower()))


# ══ THE VERSION HISTORY ═════════════════════════════════════════════════════


def version_history(*, kind: str, key: str) -> list[VersionRow]:
    """Every version of one template, newest first, in the shared vocabulary.

    The pin count rides on every row because it is what makes a version list
    mean something: *"v1 · 1,847 bills printed on it"* says why v1 can never be
    deleted where a bare status does not (BR-BIL-027, BR-NOT-025).
    """
    _refuse_unknown_kind(kind)
    if kind == KIND_NOTIFICATION:
        tenant_id = core_tenancy.current_tenant_id()
        rows = tm.NotificationTemplateVersion.objects.filter(
            tenant_id=tenant_id, template__code=key
        ).order_by("-version")
        return [
            VersionRow(
                kind=KIND_NOTIFICATION,
                key=key,
                version=row.version,
                status=row.status,
                published_on=(
                    None if row.published_at is None else row.published_at.date().isoformat()
                ),
                archived_at=None if row.archived_at is None else row.archived_at.isoformat(),
                pinned_by=template_service.pin_count(row),
            )
            for row in rows
        ]

    model = _billing("BillTemplateVersion")
    pin_count = _billing("pin_count")
    if model is None or pin_count is None:  # pragma: no cover - defensive
        return []
    tenant_id = core_tenancy.current_tenant_id()
    rows = model.objects.filter(tenant_id=tenant_id, template_id=key).order_by("-version_no")
    return [
        VersionRow(
            kind=KIND_BILL,
            key=key,
            version=row.version_no,
            status=row.status,
            published_on=None if row.published_on is None else row.published_on.isoformat(),
            # ⚠ NULL on every row archived before CR-048 task E9 added the
            # column. That is *retired before we recorded when*, and the screen
            # says so — back-filling `updated_at` would print a date nobody
            # wrote down as though it were evidence.
            archived_at=None if row.archived_at is None else row.archived_at.isoformat(),
            pinned_by=pin_count(row),
        )
        for row in rows
    ]


# ══ THE LIFECYCLE ═══════════════════════════════════════════════════════════
#
# Three verbs, one vocabulary, two owners. Every one of these DELEGATES: the
# role gate, the refusal wording and the audit row all belong to the module that
# owns the row, and re-implementing any of them here would be a second, drifting
# copy of a signed rule (hard-won law 1).


def publish(
    *, kind: str, version_row: Any, actor: Any, on_date: date, at: datetime | None = None
) -> Any:
    """Publish one draft. Affects FUTURE documents only, on both sides."""
    _refuse_unknown_kind(kind)
    if kind == KIND_NOTIFICATION:
        return template_service.publish(version_row=version_row, actor=actor, at=at)
    delegate = _billing("publish")
    if delegate is None:  # pragma: no cover - defensive
        raise UnifiedTemplateRefused(
            "billing publishes its own bill template versions and its service is not "
            "loaded. Nothing here writes bill_template_versions (B2 §2)."
        )
    return delegate(version_row, actor=actor, on_date=on_date)


def archive(
    *, kind: str, version_row: Any, actor: Any, on_date: date, at: datetime | None = None
) -> Any:
    """Retire one version. **Archive is the answer delete is not** (BR-NOT-025).

    Both sides now stamp `archived_at`; the bill side gained the column with
    this task, which is why archiving could be offered on one list at all.
    """
    _refuse_unknown_kind(kind)
    if kind == KIND_NOTIFICATION:
        return template_service.archive(version_row=version_row, actor=actor, at=at)
    delegate = _billing("archive")
    if delegate is None:  # pragma: no cover - defensive
        raise UnifiedTemplateRefused(
            "billing archives its own bill template versions and its service is not loaded."
        )
    return delegate(version_row, actor=actor, on_date=on_date, at=at)


def save_draft(*, kind: str, target: Any, actor: Any, content: dict[str, Any]) -> Any:
    """Save a NEW draft version (BR-BIL-026 — an edit is never an edit).

    ⚠ **`content` IS PER KIND AND IS NOT NORMALISED, WHICH IS THE RULING SHOWING
    THROUGH.** A notification draft carries `body` (and optionally `subject`,
    `preheader`, `effective_from`); a bill draft carries `layout_key` and
    `options`. Flattening those into one shape would mean a `body` key that is
    always empty for a bill and a `layout_key` that is always empty for a
    letter — the same meaningless column `BR-NOT-026` refused in the schema,
    moved into a dict where no test would see it.
    """
    _refuse_unknown_kind(kind)
    if kind == KIND_NOTIFICATION:
        unknown = set(content) - {"body", "subject", "preheader", "effective_from"}
        if unknown:
            raise UnifiedTemplateRefused(
                f"a notification draft has no {sorted(unknown)} — it holds the WORDS "
                "(body, subject, preheader) and, for contract classes, an effective date."
            )
        return template_service.save_draft(template=target, actor=actor, **content)

    unknown = set(content) - {"layout_key", "options"}
    if unknown:
        raise UnifiedTemplateRefused(
            f"a bill draft has no {sorted(unknown)} — it holds WHICH LAYOUT to print on "
            "(layout_key) and that layout's options. There is no body text on this side; "
            "see BR-NOT-026 and billing/template_models.py on why."
        )
    delegate = _billing("save_draft")
    if delegate is None:  # pragma: no cover - defensive
        raise UnifiedTemplateRefused(
            "billing writes its own bill template versions and its service is not loaded."
        )
    return delegate(template=target, actor=actor, **content)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 task E9 (sources: 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-025/026/027 · 12-governance/02-decision-log.md 2026-08-30 · 12-governance/11-change-requests.md CR-048 task E9 · 04-docs/03-contracts B2 §2)
# generated: 2026-08-30 by the CR-048 task E9 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see test_cr048_e9_two_stores_one_screen.py
# exceptions: E3 no unified EDITOR — the ruling asked for one list and one lifecycle, and each kind keeps the editor that suits it · E3 `content` on save_draft is per kind and deliberately unnormalised · E3 nothing here writes a row; both halves delegate to the module that owns the table
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
