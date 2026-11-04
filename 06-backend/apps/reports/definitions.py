# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 5 · `P5.1` (definition CRUD — create, update,
#           delete a tenant definition; **copy on write**) · `P5.2` (the four
#           reserved names refused BY NAME, and a definition validated against
#           its dataset's declaration).
#           Screens: 2·2 (the edit panel) · 2·4 (Save as) · 1·2 (Custom)
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — RLS FORCE, and the tenant is
#           read from context, never from a parameter a caller can edit) ·
#           hard rule 7 (every money action writes `audit_log`; a definition is
#           not a money action, and a row is written anyway because the brief's
#           own ⓸ box on p23 says one `audit_log` row per save) ·
#           B14 rule 31 (no database id is ever the visible value of a field —
#           which is why a definition is addressed by `key` on the wire) ·
#           BR-REP-019 (private by default) · `P0.16` (an unlawful total is
#           refused at BUILD time, naming the measure)
# Tests:    06-backend/tests/test_rep_p5_definition_crud.py (SQLite — the
#           vocabulary, the reserved names, the unknown column, copy-on-write)
#           06-backend/tests/test_rep_p5_postgres_isolation.py (`P5.6`/`P5.7`,
#           PostgreSQL ONLY — isolation and private-by-default under RLS)
# Impacts:  apps/reports/api.py (the three routes) · apps/reports/runner.py
#           (`validate()` is called, not re-implemented) ·
#           07-frontend/src/features/reports/ReportEditPanel.tsx (2·2) ·
#           07-frontend/src/features/reports/SaveReportAsModal.tsx (2·4)
# ───────────────────────────────────────────────────────
"""Writing a `report_definitions` row — the only place in this product that does.

⚠ **COPY ON WRITE IS THE WHOLE FILE, AND IT IS NOT A PREFERENCE.**
Phase 0 built the database half: a platform row carries `tenant_id IS NULL`,
`reports/0002`'s `USING` clause admits it to every tenant's SELECT and its
`WITH CHECK` clause admits it to nobody's INSERT, UPDATE or DELETE. So a tenant
session that tries to UPDATE a shipped report does not get a permission error
it can read — it gets **zero rows updated**, silently, which is the worst of
both worlds.

This module therefore never tries. `save()` on a platform row **creates a
tenant row** and leaves ours untouched, which is the brief's §8.3 in one
sentence: *"Editing AR Ageing and saving copies it; the standard row is
untouched and every other utility's is untouched … it is the reason a utility
can change anything here without us shipping them a fork."*

⚠ **THE FOUR RESERVED NAMES ARE REFUSED HERE AND CLAIMED IN THE ROUTER, AND
BOTH HALVES ARE REQUIRED (`P5.2`).**
A report key sits in the same URL position as a tab, so a utility naming a
report *History* shadows the History tab and **the tab stops opening**. The
router already ranks `custom`, `dashboard`, `scheduled` and `history` above
`:reportKey` (App.tsx, `P0.8`) — that is the half that keeps the tab working
for a key already in the table. This is the half that stops the key reaching
the table at all, and a `CHECK` constraint was rejected for it deliberately:
`models.py` says why, and it is that a fifth reserved word would then be a
migration rather than a line in the list the router already keeps.

⚠ **A DEFINITION IS USER INPUT. IT NAMES COLUMNS, NEVER SQL — §8.1.**
Nothing here composes a query. Every name a clerk can type is checked against
`apps/reports/datasets.py`'s declaration by `runner.validate()`, which this
module CALLS rather than re-implements: two validators is two answers, and the
one a save used would drift from the one a run used. *"Every arrow into the
database passes through a reviewed dataset. That is what makes a clerk-authored
report safe."*

⚠ **AND `runner.validate()` IS WHERE THE UNLAWFUL TOTAL IS REFUSED**, so this
file routes THROUGH the sibling refusal rather than around it. A definition
that groups `ar_ageing` by month and totals a balance is refused at save with
the measure named — three months' receivables of $41,220.00, $44,118.50 and
$48,221.14 do not total $133,559.64, and nobody owes that figure. A builder
that could express it would have reintroduced the defect at the one place a
utility can reach.

⚠ **LAW 14 — THE DUPLICATE KEY IS CAUGHT ON A SAVEPOINT, AND THE NAIVE FORM
PASSES THE WHOLE SUITE GREEN.** A save races the unique index on
`(tenant_id, key)`; the obvious `try: insert / except IntegrityError:` works on
SQLite (which the test settings hardcode, in memory, ignoring `DATABASE_URL`)
and loses the entire transaction on PostgreSQL, where a failed statement aborts
it and every later query raises `InFailedSqlTransaction`. The nested
`transaction.atomic()` below is a SAVEPOINT and is the ONLY correct form. Do
not "simplify" it away; `test_rep_p5_postgres_isolation.py` proves it on real
PostgreSQL 16 and the SQLite suite cannot.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction

from core import audit, errors
from core import tenancy as core_tenancy

from . import datasets as reports_datasets
from . import runner as reports_runner

#: The four words a definition's key may never be, refused BY NAME.
#:
#: ⚠ MIRRORED FROM `RESERVED_REPORT_SEGMENTS` IN
#: `07-frontend/src/features/reports/ReportsTabRoute.tsx` AND THAT DUPLICATION
#: IS THE POINT OF `test_rep_p5_definition_crud.py::test_reserved_list_matches_the_router`:
#: the two live in different languages and cannot import each other, so the
#: list is asserted equal rather than assumed equal. Typing an eleventh service
#: by hand in two places is how `fire` failed silently (CLAUDE.md, B14 rule 2's
#: worked case); this is the same shape four segments down, and the test is the
#: only thing standing between it and the same silence.
RESERVED_KEYS: tuple[str, ...] = ("custom", "dashboard", "scheduled", "history")

#: `BR-REP-019`, through the model so the CHECK constraint and this file cannot
#: name different values.
VISIBILITY_PRIVATE = "private"
VISIBILITY_SHARED = "shared"

#: What a clerk's own save defaults to. ⚠ **NOT the model's default**, which is
#: `shared` and is right for the forty-six rows WE ship — nobody owns those and
#: every colleague sees them. A row a person saves is theirs until they say
#: otherwise: *"a half-finished report appearing on a colleague's catalogue is
#: how people stop saving"* (brief §8, `P5.7`). The default is the ruling, not a
#: preference, so it is stated here rather than left to the column.
DEFAULT_TENANT_VISIBILITY = VISIBILITY_PRIVATE

#: Keys on a definition's `filters` that are OURS rather than a dataset's.
#: Re-exported from the runner so the two cannot drift.
BOOKKEEPING_FILTERS = reports_runner._DEFINITION_BOOKKEEPING  # noqa: SLF001

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class DefinitionRefused(Exception):
    """A save this module will not make, with the sentence a clerk reads.

    Carries `message_key` and `params` rather than prose: the PO ruled on
    2026-08-19 that a server's `detail` never reaches a screen, so the words
    come from the catalogue entry and from nothing else. `api.py` turns this
    into the `errors.ValidationError` the envelope needs; it is a plain
    exception here so a management command or a test can catch it without
    standing up a request.
    """

    def __init__(self, message_key: str, **params: Any) -> None:
        self.message_key = message_key
        self.params = params
        super().__init__(f"{message_key} {params!r}")


def slug_for(name: str) -> str:
    """A URL-safe key from the name a person typed.

    ⚠ **THE KEY IS DERIVED AND NEVER SHOWN.** B14 rule 31 forbids a database id
    on screen and a definition has two identifiers — a `id` and a `key` — so
    2·4 collects the NAME and nothing else, and this makes the other one. A
    clerk who types *90+ on route R-01* gets `90-on-route-r-01` and never sees
    it; it appears only in the address bar, where a slug is what a person
    expects to find.

    Unicode is folded rather than dropped: a Korean or Japanese catalogue name
    would otherwise slug to the empty string, and every such report at a utility
    would collide on the same key. When folding leaves nothing, the caller gets
    an empty string back and `save()` refuses with the name named.
    """
    folded = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore")
    return _SLUG_STRIP.sub("-", folded.decode("ascii").lower()).strip("-")


@dataclass(frozen=True)
class SavedDefinition:
    """What a save produced, in the shape the wire wants."""

    id: Any
    key: str
    name: str
    dataset: str
    group_code: str
    sub_group_code: str | None
    visibility: str
    owner_user_id: Any
    based_on: str | None
    created: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            # ⚠ The id is SERVED and never DRAWN — B14 rule 31 is about what a
            # field shows a person, and a client needs something to PATCH. The
            # screens address a definition by `key`; `ReportEditPanel` holds
            # this in state and puts it in a URL path, never in a label.
            "id": str(self.id),
            "key": self.key,
            "name": self.name,
            "dataset": self.dataset,
            "group": self.group_code,
            "sub_group": self.sub_group_code,
            "visibility": self.visibility,
            "owner_user_id": None if self.owner_user_id is None else str(self.owner_user_id),
            "based_on": self.based_on,
            "created": self.created,
        }


def _refuse_reserved(key: str) -> None:
    """`P5.2`'s outcome — the four words, refused by name."""
    if key in RESERVED_KEYS:
        raise DefinitionRefused("reports.definition.reserved_name", name=key)


def _dataset_or_refuse(code: str) -> reports_datasets.Dataset:
    dataset = reports_datasets.BY_CODE.get(code)
    if dataset is None:
        raise DefinitionRefused(
            "reports.definition.unknown_dataset",
            dataset=str(code),
            datasets=", ".join(sorted(reports_datasets.BY_CODE)),
        )
    return dataset


def _validate(candidate: reports_runner.ResolvedDefinition) -> None:
    """Ruling 4, through the runner's own validator and never beside it.

    Every refusal it raises names the thing that is wrong — an unknown column
    names the COLUMN, an unlawful total names the MEASURE and the DIRECTION —
    and each is turned into a catalogue key here so the sentence a clerk reads
    is an authored one. The engineering prose rides in `params.detail` for the
    log, where the 2026-08-19 ruling leaves it.
    """
    try:
        reports_runner.validate(candidate)
    except reports_runner.UnknownParameter as exc:
        raise DefinitionRefused(
            "reports.definition.unknown_column",
            column=_named_in(str(exc)),
            detail=str(exc),
        ) from exc
    except reports_datasets.UnlawfulTotal as exc:
        raise DefinitionRefused(
            "reports.definition.unlawful_total",
            measure=_named_in(str(exc)),
            detail=str(exc),
        ) from exc
    except reports_runner.DatasetNotExecutable as exc:
        raise DefinitionRefused(
            "reports.definition.unknown_dataset",
            dataset=candidate.dataset,
            datasets=", ".join(sorted(reports_datasets.BY_CODE)),
        ) from exc


_QUOTED = re.compile(r"'([^']+)'")
_DOTTED = re.compile(r"\b[a-z_]+\.([a-z_0-9]+)\b")


def _named_in(message: str) -> str:
    """The one name a refusal is ABOUT, pulled out of the runner's sentence.

    ⚠ **THE OUTCOME IS *"refused WITH THE COLUMN NAMED"*, so the name has to
    reach the screen as a PARAMETER and not only inside a sentence the screen
    never renders.** The 2026-08-19 ruling means the clerk reads the catalogue
    entry, which interpolates `{{column}}`; if the name lived only in `detail`
    they would read *"That column does not exist."* and be told nothing they
    could act on.

    Two shapes, because the runner raises two: `ar_ageing produces no column
    'ballance'` and `payments.dso_days is non-additive`. A sentence matching
    neither yields the empty string and the catalogue entry degrades to a
    sentence without a name — which is a worse message, never a crash.
    """
    quoted = _QUOTED.search(message)
    if quoted:
        return quoted.group(1)
    dotted = _DOTTED.search(message)
    return dotted.group(1) if dotted else ""


def _candidate(
    *,
    key: str,
    name: str,
    dataset: str,
    group_code: str,
    sub_group_code: str | None,
    columns: tuple[str, ...],
    filters: dict[str, Any],
    group_by: tuple[str, ...],
    sort: tuple[str, ...],
    service_codes: tuple[str, ...],
) -> reports_runner.ResolvedDefinition:
    return reports_runner.ResolvedDefinition(
        key=key,
        name=name,
        dataset=dataset,
        group_code=group_code,
        sub_group_code=sub_group_code,
        columns=columns,
        filters=filters,
        group_by=group_by,
        sort=sort,
        service_codes=service_codes,
        from_table=True,
    )


def _unique_key(tenant_id: Any, wanted: str) -> str:
    """`wanted`, or `wanted-2`, `wanted-3`… — the first this tenant does not hold.

    ⚠ **THIS IS A READ AND IT IS NOT THE GUARANTEE.** Two clerks pressing Save
    in the same second both read *free* and both try `overdue-60`; the unique
    index refuses the loser and `save()` catches that on a SAVEPOINT and comes
    back here. The loop removes the COMMON case — a person saving *Overdue 60+*
    twice — and the index removes the rest. A read that is treated as a
    reservation is exactly law 11's id collision one table over.
    """
    from apps.reports.models import ReportDefinition

    taken = set(
        ReportDefinition.objects.filter(tenant_id=tenant_id, key__startswith=wanted)
        .values_list("key", flat=True)
    )
    if wanted not in taken:
        return wanted
    suffix = 2
    while f"{wanted}-{suffix}" in taken:
        suffix += 1
    return f"{wanted}-{suffix}"


def save(
    *,
    name: str,
    dataset: str,
    group_code: str,
    sub_group_code: str | None = None,
    columns: Any = (),
    filters: Any = None,
    group_by: Any = (),
    sort: Any = (),
    service_codes: Any = (),
    visibility: str = DEFAULT_TENANT_VISIBILITY,
    owner_user_id: Any = None,
    based_on: str | None = None,
) -> SavedDefinition:
    """2·4's **Save as** — one new tenant row, one `audit_log` row, ours untouched.

    `based_on` is the key the clerk was standing on. It is recorded and it is
    never followed: the copy takes the SHAPE the panel is holding, which is the
    shipped report plus whatever they changed. Recording it is what makes the
    *Based on* column on 1·2 the difference between a catalogue and a junk
    drawer (p22 callout ⑤) — six months in, four reports have similar names and
    nobody remembers which came from where.
    """
    from apps.reports.models import ReportDefinition

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        # Hard rule 1. A write with no tenant context is a forged or orphaned
        # row; refuse loudly rather than write it somewhere.
        raise DefinitionRefused("reports.definition.no_tenant")

    clean_name = str(name or "").strip()
    if not clean_name:
        raise DefinitionRefused("reports.definition.name_required")

    wanted = slug_for(clean_name)
    if not wanted:
        raise DefinitionRefused("reports.definition.name_unusable", name=clean_name)
    _refuse_reserved(wanted)

    dataset_code = str(dataset or "")
    _dataset_or_refuse(dataset_code)

    if visibility not in (VISIBILITY_PRIVATE, VISIBILITY_SHARED):
        raise DefinitionRefused("reports.definition.unknown_visibility", value=str(visibility))

    columns_t = tuple(str(c) for c in (columns or ()))
    filters_d = dict(filters or {})
    group_by_t = tuple(str(g) for g in (group_by or ()))
    sort_t = tuple(str(s) for s in (sort or ()))
    services_t = tuple(str(s) for s in (service_codes or ()))

    _validate(
        _candidate(
            key=wanted,
            name=clean_name,
            dataset=dataset_code,
            group_code=str(group_code or ""),
            sub_group_code=sub_group_code or None,
            columns=columns_t,
            filters=filters_d,
            group_by=group_by_t,
            sort=sort_t,
            service_codes=services_t,
        )
    )

    key = _unique_key(tenant_id, wanted)
    _refuse_reserved(key)

    try:
        # ⚠ LAW 14 — a SAVEPOINT, so a refused INSERT does not abort the
        # request's transaction on PostgreSQL. See the module docstring.
        with transaction.atomic():
            row = ReportDefinition.objects.create(
                tenant_id=tenant_id,
                key=key,
                name=clean_name,
                dataset=dataset_code,
                group_code=str(group_code or ""),
                sub_group_code=sub_group_code or None,
                columns=list(columns_t),
                filters=filters_d,
                group_by=list(group_by_t),
                sort=list(sort_t),
                service_codes=list(services_t),
                visibility=visibility,
                owner_user_id=owner_user_id,
            )
    except IntegrityError as exc:
        # The loser of a race with a sibling save. The transaction is intact
        # because the INSERT ran inside its own savepoint, so a sentence can be
        # raised here rather than the request dying at COMMIT.
        raise DefinitionRefused("reports.definition.name_taken", name=clean_name) from exc

    audit.write_row(
        action="report_definition.created",
        entity_type="report_definition",
        entity_id=row.id,
        actor_user_id=owner_user_id,
        after={
            "key": row.key,
            "name": row.name,
            "dataset": row.dataset,
            "visibility": row.visibility,
            "based_on": based_on,
        },
    )
    return SavedDefinition(
        id=row.id,
        key=row.key,
        name=row.name,
        dataset=row.dataset,
        group_code=row.group_code,
        sub_group_code=row.sub_group_code,
        visibility=row.visibility,
        owner_user_id=row.owner_user_id,
        based_on=based_on,
        created=True,
    )


def update(definition_id: Any, *, actor_user_id: Any = None, **changes: Any) -> SavedDefinition:
    """2·2's **Save** on a row this tenant already owns.

    ⚠ **A PLATFORM ROW IS NEVER REACHED FROM HERE.** The screens send an UPDATE
    only for a tenant row; a shipped report is edited through `save()`, which
    copies. If a platform id arrives anyway — a hand-edited request, or a screen
    that grew a bug — it is refused by name rather than attempted, because the
    policy would make the attempt a silent no-op and the clerk would watch a
    save button do nothing.
    """
    from apps.reports.models import ReportDefinition

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise DefinitionRefused("reports.definition.no_tenant")

    row = ReportDefinition.objects.filter(id=definition_id).first()
    if row is None:
        # Absent, or another tenant's, and the two are indistinguishable by law
        # (HR-1 / BR-TEN-003). RLS has already made the second case look like
        # the first; this line does not undo that.
        raise errors.deny_as_not_found()
    if row.tenant_id is None:
        raise DefinitionRefused("reports.definition.built_in_is_copied", name=row.name)

    before = {
        "name": row.name,
        "columns": list(row.columns or ()),
        "filters": dict(row.filters or {}),
        "group_by": list(row.group_by or ()),
        "sort": list(row.sort or ()),
        "visibility": row.visibility,
    }

    if "name" in changes:
        clean_name = str(changes["name"] or "").strip()
        if not clean_name:
            raise DefinitionRefused("reports.definition.name_required")
        row.name = clean_name
    if "dataset" in changes:
        _dataset_or_refuse(str(changes["dataset"]))
        row.dataset = str(changes["dataset"])
    if "group_code" in changes:
        row.group_code = str(changes["group_code"] or "")
    if "sub_group_code" in changes:
        row.sub_group_code = changes["sub_group_code"] or None
    if "columns" in changes:
        row.columns = [str(c) for c in (changes["columns"] or ())]
    if "filters" in changes:
        row.filters = dict(changes["filters"] or {})
    if "group_by" in changes:
        row.group_by = [str(g) for g in (changes["group_by"] or ())]
    if "sort" in changes:
        row.sort = [str(s) for s in (changes["sort"] or ())]
    if "service_codes" in changes:
        row.service_codes = [str(s) for s in (changes["service_codes"] or ())]
    if "visibility" in changes:
        value = str(changes["visibility"])
        if value not in (VISIBILITY_PRIVATE, VISIBILITY_SHARED):
            raise DefinitionRefused("reports.definition.unknown_visibility", value=value)
        row.visibility = value

    # The key never moves on an update. A report a colleague has bookmarked
    # does not change address because its author renamed it — the NAME is what
    # a person reads (B14 rule 31) and the key is the address.
    _validate(
        _candidate(
            key=row.key,
            name=row.name,
            dataset=row.dataset,
            group_code=row.group_code,
            sub_group_code=row.sub_group_code,
            columns=tuple(row.columns or ()),
            filters=dict(row.filters or {}),
            group_by=tuple(row.group_by or ()),
            sort=tuple(row.sort or ()),
            service_codes=tuple(row.service_codes or ()),
        )
    )

    row.version = (row.version or 1) + 1
    try:
        with transaction.atomic():  # law 14, as above
            row.save()
    except IntegrityError as exc:
        raise DefinitionRefused("reports.definition.name_taken", name=row.name) from exc

    audit.write_row(
        action="report_definition.updated",
        entity_type="report_definition",
        entity_id=row.id,
        actor_user_id=actor_user_id,
        before=before,
        after={
            "name": row.name,
            "columns": list(row.columns or ()),
            "filters": dict(row.filters or {}),
            "group_by": list(row.group_by or ()),
            "sort": list(row.sort or ()),
            "visibility": row.visibility,
        },
    )
    return SavedDefinition(
        id=row.id,
        key=row.key,
        name=row.name,
        dataset=row.dataset,
        group_code=row.group_code,
        sub_group_code=row.sub_group_code,
        visibility=row.visibility,
        owner_user_id=row.owner_user_id,
        based_on=None,
        created=False,
    )


def delete(definition_id: Any, *, actor_user_id: Any = None) -> str:
    """Remove a tenant's own definition. A platform row is refused by name.

    A real DELETE and not a soft one: hard rule 4's financial immutability names
    invoices, invoice lines, payments and journal entries, and a definition is
    none of those — it is a saved question, not a record of money. The
    `audit_log` row is what says it existed and who removed it.
    """
    from apps.reports.models import ReportDefinition

    if core_tenancy.current_tenant_id() is None:
        raise DefinitionRefused("reports.definition.no_tenant")

    row = ReportDefinition.objects.filter(id=definition_id).first()
    if row is None:
        raise errors.deny_as_not_found()
    if row.tenant_id is None:
        raise DefinitionRefused("reports.definition.built_in_is_kept", name=row.name)

    key, name = row.key, row.name
    audit.write_row(
        action="report_definition.deleted",
        entity_type="report_definition",
        entity_id=row.id,
        actor_user_id=actor_user_id,
        before={"key": key, "name": name, "dataset": row.dataset},
    )
    with transaction.atomic():  # law 14
        row.delete()
    return key


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 5 `P5.1`/`P5.2` (05-prototype/09 Reports Build Brief.pdf p16-p17 the task table, p31-p33 screen 2·2, p35 screen 2·4, p91 §8.2, read as IMAGES per B14 rule 42) · PO ruling 2026-09-26 "panel, not wizard" (12-governance/02-decision-log.md)
# screens: 2·2 · 2·4 · 1·2
# generated: 2026-09-27 by lane REP-P5
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see tests/test_rep_p5_definition_crud.py's own gates line
# exceptions: (1) the reserved list is duplicated in the front end's router and asserted equal by a test rather than shared, because the two cannot import each other · (2) `visibility` defaults to `private` HERE and to `shared` on the column, which is deliberate: the column's default is right for the 46 platform rows and wrong for a person's own save
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
