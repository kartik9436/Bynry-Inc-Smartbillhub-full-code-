# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A3: the read path.
# Rules:    B1 (three routes to the database and no fourth) · BR-RBS-039 (a
#           read of ANOTHER module goes through apps/runbooks/seams/, never a
#           cross-module queryset and never the product's own HTTP API) ·
#           CLAUDE.md hard rule 1 (every read under the tenant context)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  apps/runbooks/seams/ (where a foreign read is allowed to live) ·
#           10-scripts/gates/g115_runbooks_import_census.py
# ───────────────────────────────────────────────────────
"""runbooks reads — this module's OWN seven tables, and nothing else's.

**IT HOLDS EXACTLY THE READS SOMETHING CALLS, AND NOT ONE MORE.** Wave A left
this file empty on purpose — a selector nothing calls is hard-won law 2's dead
code in its quietest form: it reads as progress, every test passes, and the
feature does not exist. Wave B adds two, and both have a caller in
`services.py` in the same commit.

WHAT LANDS HERE, AND WITH WHICH WAVE
------------------------------------
* wave B — the runbook's latest version, which `open_run` pins, and the runbook
  by key. **BUILT — this file.**
* wave D — the catalogue, the template library, the run history, one run, its
  frozen report, its records and the rows behind the two result files
  (`RBS-001`, `RBS-002`, `RBS-006`, `RBS-008`), **every list server-paginated**,
  because `NFR-3` binds every list this module adds and `NFR-5` forbids a
  per-tenant cap. **BUILT — this file, second half.**
* wave H — the work list (`RBS-007`).

⚠ **WAVE B'S TWO SELECTORS DO NOT PAGE AND DO NOT RETURN A LIST.** That is not
an `NFR-3` breach and the distinction is worth keeping so a later reader does
not have to re-derive it: `NFR-3` binds every LIST a screen or an endpoint
serves, and `runbook_by_key` and `latest_version` return one row each. Every
list below pages, with `per` clamped 50/100/200/500/1000 and 50 the default.

THE ONE RULE THIS FILE EXISTS TO HOLD
-------------------------------------
**A read of another module's data does NOT belong here.** It belongs in
`apps/runbooks/seams/<module>_seam.py`, calling that module's own selector by
name, in process, under the tenant context. `BR-RBS-039`, and it is enforced
rather than asserted: `10-scripts/gates/g115_runbooks_import_census.py` fails
any `apps.<other>` import outside `seams/` **by file and line**, and was proved
red on planted violations before it was trusted green.

A selector another module does not expose yet is added **by the module that owns
the table**, never by reaching past a seam. The inventory of every such selector
the defined runbooks will need is `17-runbooks/13-selector-inventory.md`, written
in wave A precisely so it is not discovered in phase 5.
"""


from __future__ import annotations

import itertools
import math
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, OuterRef, Q, Subquery

from apps.runbooks import contract, models, scheduler
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size


def runbook_by_key(tenant_id, key: str) -> models.Runbook | None:
    """One runbook, by the key a run, a work item and a plan item all cite.

    ⚠ **THE TENANT IS AN ARGUMENT AND NOT AN AMBIENT ASSUMPTION.** Hard rule 1:
    never touch a tenant table without `app.tenant_id` set, and no cross-tenant
    queryset. RLS `FORCE` is on for all seven tables on PostgreSQL, so a filter
    forgotten here would be refused by the database rather than silently
    widened — but the filter is written anyway, because the test suite is
    SQLite, where there is no row-level security at all and the omission would
    pass green.
    """
    return models.Runbook.objects.filter(tenant_id=tenant_id, key=key).first()


def runbook_by_template(tenant_id, template_key: str) -> models.Runbook | None:
    """This tenant's copy of a shipped template, or `None` — `BR-RBS-043`.

    A tenant holds at most one copy under the template's own key, and a second
    copy is made by CLONING (`services.clone_runbook`), so this reads at most
    one row. It is what `POST /runbooks` checks before creating, and what the
    library's **Added · Not added** state means one runbook at a time.

    ⚠ **A CLONE CARRIES THE SAME `template_key` AND IS DELIBERATELY NOT THIS
    ROW.** `services.clone_runbook` copies `template_key` onto the copy because
    that pointer is the only thing that finds the copy's CODE — its own key is
    new and the registry holds nothing under it. So a filter on `template_key`
    alone would answer *added* for a tenant that has only ever cloned, and the
    **Add** button on `RBS-002` would disappear for a template they never added.
    `origin` is what separates the two, and it is filtered rather than ordered:
    an ordering would return SOMETHING for a tenant with clones only, and the
    honest answer there is `None`.
    """
    return models.Runbook.objects.filter(
        tenant_id=tenant_id, template_key=template_key, origin=models.ORIGIN_SHIPPED
    ).first()


def latest_version(runbook: models.Runbook) -> models.RunbookVersion | None:
    """The newest version row, or `None` before the first one is written.

    `open_run` compares this row's stored document with the definition it is
    about to run, and mints a new version only when they differ — so
    re-registering unchanged code does not give a runbook one version per
    deploy (`BR-RBS-038`; see `services.ensure_version`).

    Ordered by `version` rather than by `changed_at`: two versions written in
    the same transaction can share a timestamp, and the number is what a run
    pins.
    """
    return (
        models.RunbookVersion.objects.filter(
            tenant_id=runbook.tenant_id, runbook_id=runbook.pk
        )
        .order_by("-version")
        .first()
    )


# ── wave D · US-RBS-003 · US-RBS-018 — the reads the three surfaces need ─────
#
# ⚠ **EVERY LIST BELOW ORDERS AND SLICES IN SQL. THAT SENTENCE IS THE TASK.**
# `NFR-3` binds every list this module adds and `NFR-5` forbids a per-tenant
# cap. CLAUDE.md names four places already in breach and says what they have in
# common: `GET /outstandings` is unpaginated *"ON PURPOSE … one row per DEBTOR
# at a utility under 3,000 connections"* **and sorts in Python**, and
# `GET /cheques`, the bank-rec batch list and their two front-end mirrors do the
# same — correct at T7 and **13× short of T5** (`DEF-PAY-4221`). So there is no
# `sorted(...)` over rows in this file, no `list(queryset)` before a slice, and
# no maximum runbook, run or record count anywhere. `_slice` is the only place a
# window is taken and it is four lines long so that it can be read.
#
# ⚠ **THE SHAPE THESE RETURN IS `{"rows", "page", "per", "total"}` AND IT IS NOT
# THE WIRE.** `api._envelope` renames it to `{count, next, previous, results}`.
# Three shipped Work screens drew empty tables because a front-end type was
# transcribed from THIS side of the boundary (`DEF-WRK-4119`, `DEF-AST-4120`),
# so both shapes are stated in both files rather than left to be inferred.


def _page_number(raw: Any, last: int) -> int:
    """`page` clamps into `[1, last]` and NEVER errors (`BR-SHL-011`).

    A list URL cannot 4xx over its own params, so `page=abc`, `page=-4` and page
    900 of a five-page list all land on a real page.
    """
    try:
        number = int(str(raw))
    except (TypeError, ValueError):
        return 1
    return min(max(number, 1), last)


def _slice(queryset: Any, page: Any, per: Any) -> tuple[Any, dict[str, Any]]:
    """Count, clamp, slice — in that order, all of it in SQL.

    `per` clamps to **50 · 100 · 200 · 500 · 1000, default 50** through
    `core.pagination.clamp_page_size` (IS-2 as amended, PO ruling 2026-08-09),
    so `per=5000` serves 1,000 rows and `per=7` serves 50. There is one page-size
    vocabulary in this product and this module does not mint a second.

    ⚠ **THE QUERYSET MUST ARRIVE ORDERED.** A slice of an unordered queryset is
    a different set of rows each time it is asked, which reads on screen as a
    list that shuffles under the reader between page 1 and page 2. Every caller
    below orders on a column plus `id`, so the order is TOTAL: two rows with the
    same timestamp cannot swap places between two requests.
    """
    total = queryset.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = _page_number(page, last)
    start = (number - 1) * size
    return queryset[start : start + size], {"page": number, "per": size, "total": total}


def _person(user: Any) -> dict[str, Any] | None:
    """A user rendered as a NAME, never as an id (B14 rule 31).

    ⚠ **NO `id` FIELD AT ALL, DELIBERATELY.** Rule 31 — *"no database id is ever
    the visible value of a field"* — is about what a screen RENDERS, and the way
    a payload makes that mistake easy is by carrying an id beside a name that
    might be empty: `full_name` defaults to `""` while a user is still invited
    (`US-IDN-004`), and a screen falling back to `row.id` would draw a uuid in
    the *By* column. Serving no id removes the fallback.

    Reached through the reviewed cross-module FK (B2 Addendum r24), not through
    an import: `apps/runbooks` has no identity seam and `READ_MODULES` does not
    name identity, so `G115` would refuse `from apps.identity...` here. A
    declared FK on this module's own model is the reviewed interface and needs
    no import to walk.
    """
    if user is None:
        return None
    return {"name": (getattr(user, "full_name", "") or "").strip() or None}


def _took_seconds(run: Any) -> float | None:
    """How long the run took, or `None` while it is still going.

    ⚠ **`None` HERE MEANS TWO DIFFERENT THINGS TODAY AND ONE OF THEM IS A
    DEFECT** (`DEF-RBS-4291`): a run in flight has no `finished_at`, which is
    honest — and **`services.open_run` did not stamp `started_at` at all until
    this wave**, so every run written before it reads `None` here and on
    `RBS-008`'s *Started* and *Took* columns. The fix is in `services.open_run`;
    rows written before it keep their null and nothing invents a duration for
    them.
    """
    if run.started_at is None or run.finished_at is None:
        return None
    return (run.finished_at - run.started_at).total_seconds()


# ── the catalogue · `GET /runbooks` ───────────────────────────────────────────


def _visible_to(queryset: Any, role: str | None) -> Any:
    """Narrow a runbook queryset to what this role is SHOWN — `RB-050`, wave `D5`.

    `12-the-contract.md` §5: *"Role visibility defaults from it. Owner and Admin
    see every runbook; the last column says who else does by default; an Admin
    may widen or narrow it per runbook."*

    ⚠ **A FILTER, NEVER A PERMISSION.** Every read route in this module stays
    `AnyTenantRole` and refuses nothing on the strength of this — `07-endpoints.md`
    §1 marks the catalogue *Staff reads*, and a narrower list turning into a 403
    would be `DEF-196`'s shape, where a read and a write shared one gate and a
    whole role could not use the product.

    ⚠ **A `system_admin` SEES EVERYTHING AND SHORT-CIRCUITS**, so no override
    can hide a runbook from the person who has to fix it (see
    `models.roles_that_see`).

    ⚠ **AN UNKNOWN OR ABSENT ROLE IS NOT NARROWED.** A request with no
    `tenant_role` cannot reach these views at all — `AnyTenantRole` refuses it
    first — so `None` here means a caller inside the process (a management
    command, the seed) rather than an anonymous request, and narrowing it would
    make a maintenance script silently see less than the database holds. The
    tenant filter is the one that protects rows, and it is applied by every
    caller before this.

    ⚠ **IT FILTERS IN SQL.** The obvious build reads every row and keeps the
    ones `roles_that_see` admits, which is `NFR-3`'s hazard wearing a different
    hat — the page would be sliced after a Python filter and `count()` would be
    a lie. So the category default becomes an `IN` over the categories this role
    sees, and the override is an `IN` over the whole lists that contain the role.

    ⚠ **THE OBVIOUS `visible_to_roles__contains=[role]` IS POSTGRESQL-ONLY AND
    RAISES A 500 ON SQLITE — WHICH IS HARD-WON LAW 14 RUNNING THE OTHER WAY, AND
    THAT IS THE ONLY REASON IT WAS CAUGHT.** Django's `JSONField` `contains`
    lookup is unsupported on SQLite (`NotSupportedError`), so the first draft
    answered **500** to every Billing Clerk reading the catalogue and
    `test_us_rbs_003_every_signed_in_role_may_read` — a case written for a
    different wave — is what said so. Law 14's usual direction is a build that
    is green on SQLite and broken on PostgreSQL; here the vendors disagree in
    our favour, and the lesson is the same: **the two databases are not one
    database, and a lookup is a vendor question until you have run it on both.**

    ⚠ **SO THE OVERRIDE IS MATCHED BY EXACT LIST, AND THAT IS SOUND BECAUSE THE
    VALUE IS NORMALISED ON THE WAY IN.** `services._validated_setting` stores a
    sorted, de-duplicated list drawn from three role codes, so there are exactly
    eight possible values and four of them contain any given role. Enumerating
    them is an `IN` over four short JSON strings — portable, exact, and
    `test_us_rbs_038_the_override_is_stored_normalised` is what keeps the
    enumeration honest. A fourth role would widen the enumeration automatically
    because it is computed from `VISIBILITY_ROLES` rather than typed out.
    """
    if role is None or role == "system_admin":
        return queryset
    default_categories = [
        name
        for name in models.CATEGORIES
        if role in models.ROLE_VISIBILITY_BY_CATEGORY.get(name, ())
    ]
    others = [one for one in models.VISIBILITY_ROLES if one != role]
    overrides = [
        sorted({role, *subset})
        for size in range(len(others) + 1)
        for subset in itertools.combinations(others, size)
    ]
    return queryset.filter(
        Q(visible_to_roles__isnull=True, category__in=default_categories)
        | Q(visible_to_roles__in=overrides)
    )


def catalogue_page(
    tenant_id: Any,
    *,
    kind: str | None = None,
    category: str | None = None,
    q: str = "",
    role: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /runbooks` — this tenant's runbooks, with each one's last run.

    `07-endpoints.md` row 1: *the catalogue with last-run summary and open-item
    counts; filter by `kind` and `category`*. Ordered by name so the list reads
    like a library rather than like an insertion log, with `key` as the
    tiebreak so the order is total.

    ⚠ **THE LAST RUN AND THE OPEN ITEMS ARE TWO AGGREGATE QUERIES OVER THE PAGE,
    NOT ONE QUERY PER ROW.** The obvious build asks each runbook for its own
    latest run, which is `per` extra queries — 1,000 of them at the top clamp.
    Both are grouped in SQL over the ids ON THIS PAGE, so the cost is three
    queries whatever `per` is.

    ⚠ **THE LATEST RUN IS A `Subquery` ON `(-created_at, -id)`, AND THE OBVIOUS
    `Max("id")` IS WRONG — IT WAS WRITTEN FIRST AND ITS OWN TEST CAUGHT IT.**
    `id` is a uuid7 (`core.dbfields.uuid7_pk`) and uuid7 is time-ordered only to
    the MILLISECOND: RFC 9562 puts a 48-bit unix-ms prefix in front of **12
    RANDOM BITS** (`rand_a = os.urandom(2) & 0x0FFF`) and 62 more, so two rows
    written inside one millisecond order **at random** and the greatest id is
    not the newest. Three runs seeded in a loop are exactly that case, and
    `Max("id")` named the second one. `created_at` is `auto_now_add` at
    microsecond resolution, `id` breaks the remaining tie deterministically, and
    the pair is what makes the answer stable across two reads.

    ⚠ **`started_at` IS NOT USED FOR THIS** even though it is what the screen
    calls *Started*: it is nullable, and an aggregate or an ordering over nulls
    silently answers for the wrong row on one vendor and a different wrong row
    on the other (PostgreSQL sorts NULLs first descending, SQLite last).
    """
    queryset = _visible_to(models.Runbook.objects.filter(tenant_id=tenant_id), role)
    if kind in models.KINDS:
        queryset = queryset.filter(kind=kind)
    if category in models.CATEGORIES:
        queryset = queryset.filter(category=category)
    text = (q or "").strip()
    if text:
        queryset = queryset.filter(Q(name__icontains=text) | Q(key__icontains=text))
    window, meta = _slice(queryset.order_by("name", "key"), page, per)

    rows = list(window)
    ids = [row.pk for row in rows]
    last_runs = _last_run_by_runbook(tenant_id, ids)
    open_items = _open_work_items_by_runbook(tenant_id, ids)
    return {
        "rows": [
            {
                "key": row.key,
                "name": row.name,
                "kind": row.kind,
                "category": row.category,
                "tags": list(row.tags or ()),
                "origin": row.origin,
                "enabled": row.enabled,
                "trigger_kind": row.trigger_kind,
                "cap": row.cap,
                "current_version": row.current_version,
                # `RBS-002.2`'s *What it can touch* and `RBS-004.1`'s *This can*
                # are derived from `ports[]` and from nothing else — never from
                # a hand-written label that could disagree with the constructor
                # (`US-RBS-002`). A runbook the registry does not hold (a clone,
                # wave E) answers `None` rather than claiming either way.
                "writes_nothing": _writes_nothing(row.key),
                "last_run": last_runs.get(row.pk),
                "open_items": open_items.get(row.pk, 0),
            }
            for row in rows
        ],
        **meta,
    }


def _writes_nothing(key: str) -> bool | None:
    """`True` for a Check, `False` for an Action, `None` when unregistered.

    The third answer is the one that matters: a cloned runbook (wave E) has a
    key the shipped registry does not hold, and answering `True` for it would
    tell a screen *Writes: Nothing* about a runbook nobody has asked. An unknown
    is served as unknown.
    """
    definition = _registry_definition(key)
    return None if definition is None else definition.writes_nothing()


def _registry_definition(key: str) -> Any:
    """The shipped definition for a key, or `None`.

    Imported inside the function because `registry` imports `definitions`, which
    imports runbook modules, which import `models` — and this file is imported
    by `services`, which the registry's own load path reaches. A module-level
    import here closes that loop. It names `apps.runbooks.*`, which is what
    `G115` rule 3 permits.
    """
    from apps.runbooks.registry import registry

    try:
        return registry.get(key)
    except Exception:
        return None


def _last_run_by_runbook(tenant_id: Any, runbook_ids: list[Any]) -> dict[Any, dict[str, Any]]:
    """`{runbook_id: last-run summary}` for the page's runbooks, in two queries.

    ⚠ **A `Subquery` AND NOT AN AGGREGATE, AND NOT ONE QUERY PER ROW EITHER.**
    Django has no portable *top-1 per group*: `DISTINCT ON` is PostgreSQL's
    alone and the test database is SQLite. `Max("id")` would be one query and is
    the bug this function's docstring in `catalogue_page` describes; asking each
    runbook for its own latest run would be `per` extra queries, a thousand of
    them at the top clamp. A correlated subquery is one query on both vendors
    and orders on the pair that is actually total.
    """
    if not runbook_ids:
        return {}
    newest = (
        models.RunbookRun.objects.filter(tenant_id=tenant_id, runbook_id=OuterRef("pk"))
        .order_by("-created_at", "-id")
        .values("id")[:1]
    )
    ids = [
        row["last_id"]
        for row in models.Runbook.objects.filter(tenant_id=tenant_id, pk__in=runbook_ids)
        .annotate(last_id=Subquery(newest))
        .values("last_id")
        if row["last_id"] is not None
    ]
    if not ids:
        return {}
    runs = models.RunbookRun.objects.filter(tenant_id=tenant_id, id__in=ids)
    return {
        run.runbook_id: {
            "id": str(run.pk),
            "status": run.status,
            "mode": run.mode,
            "trigger": run.trigger,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "took_seconds": _took_seconds(run),
            "counts": dict(run.counts or {}),
        }
        for run in runs
    }


def _open_work_items_by_runbook(tenant_id: Any, runbook_ids: list[Any]) -> dict[Any, int]:
    """`{runbook_id: open work items}` — the *open-item counts* of row 1.

    Grouped in SQL over the page's runbooks. A work item with no `source_run`
    is a human task nobody's runbook raised, and it is correctly absent from
    every runbook's count rather than attributed to one.

    ⚠ **THIS IS THE `runbooks` MODULE'S `work_items` TABLE, NOT THE `work`
    MODULE'S** (`17-runbooks/03-field-map.md` D-4). `apps/work` owns crews,
    technicians, parts and WORK ORDERS; this is findings, exceptions and human
    tasks on one surface, and the ENGINE writes it — never a runbook, which is
    what lets a Check populate it while holding no writer at all (`BR-RBS-002`).
    """
    if not runbook_ids:
        return {}
    grouped = (
        models.WorkItem.objects.filter(
            tenant_id=tenant_id, status="open", source_run__runbook_id__in=runbook_ids
        )
        .values("source_run__runbook_id")
        .annotate(total=Count("id"))
    )
    return {row["source_run__runbook_id"]: row["total"] for row in grouped}


# ── one runbook · `GET /runbooks/{key}` ──────────────────────────────────────


def runbook_detail(tenant_id: Any, key: str) -> dict[str, Any] | None:
    """`GET /runbooks/{key}` — definition, schedule, caps, guards, next run.

    `07-endpoints.md` row 2. `None` when this tenant has no runbook under that
    key, which the route answers as a 404 identical to the one an unknown key
    gets — the read is filtered by tenant before the key is looked at, so
    another tenant's runbook is indistinguishable from one that never existed
    (`HR-1`).

    ⚠ **`next_run` IS A REAL TIME FROM `CR-075` WAVE I, AND THIS PARAGRAPH SAID
    THE OPPOSITE UNTIL 2026-09-07.** It read *"`next_run` is `None` and it is not
    a placeholder — nothing in this product schedules a runbook yet"*, which was
    exactly true when it was written and is the reason the field was served at
    all: `RB-022` runs both ways, so **a schedule a screen displays must
    actually fire**, and until wave `I` none did. `apps/runbooks/scheduler.py`
    now registers two job kinds with the platform runner and sweeps every
    utility's schedules once a minute, so the mirror is satisfied and the screen
    may say when.

    ⚠ **IT IS COMPUTED AND THERE IS STILL NO `next_run_at` COLUMN**, which is
    deliberate: the answer is a pure function of `cron`, `timezone` and now, so
    a column would be a second copy of a derived fact that goes stale the moment
    an admin edits the schedule and nothing rewrites it. `None` remains a real
    answer — a disabled runbook, a manual or event trigger, no cron, or a cron
    like `0 6 30 2 *` that names no reachable date — and the screen draws the
    absence rather than a guess.

    ⚠ **THE DEFINITION COMES FROM THE COPY'S OWN STORED VERSION, AND THE
    REGISTRY IS ONLY THE BOOTSTRAP. THIS SENTENCE WAS THE OTHER WAY ROUND UNTIL
    WAVE `E3` AND THE SUPERSESSION IS STATED RATHER THAN QUIETLY APPLIED.**

    `D1` served the REGISTRY first and said so, for a reason that was true when
    it was written: *"the registry holds what the NEXT run will pin, so a setup
    screen drawn from the stored version would show a clerk yesterday's
    parameters while tomorrow's run uses today's."* Wave `E3` changed the fact
    underneath it. `services.ensure_version` no longer adopts a changed shipped
    document — `BR-RBS-038`: **a change to a shipped template is OFFERED on a
    tenant's copy and never applied without a person accepting it** — so the
    stored version IS what the next run pins, and serving the registry here
    would show a clerk steps their copy does not have and their next run will
    not use. The divergence is served as `template_update` instead, which is the
    offer, and pressing *Review →* is what makes the two agree.

    A runbook with no version at all — one created directly rather than through
    `POST /runbooks` — falls back to the registry, and one with neither serves
    `definition: None` rather than an empty object that reads like a runbook
    with no steps.
    """
    runbook = runbook_by_key(tenant_id, key)
    if runbook is None:
        return None
    document = _latest_definition_document(runbook)
    if document is None:
        definition = _registry_definition(key)
        document = None if definition is None else definition.as_definition_document()
    last_run = _last_run_by_runbook(tenant_id, [runbook.pk]).get(runbook.pk)
    return {
        "key": runbook.key,
        "name": runbook.name,
        "kind": runbook.kind,
        "category": runbook.category,
        "tags": list(runbook.tags or ()),
        "origin": runbook.origin,
        "template_key": runbook.template_key,
        "subject_type": runbook.subject_type,
        "unit_of_work": runbook.unit_of_work,
        "enabled": runbook.enabled,
        "current_version": runbook.current_version,
        "schedule": {
            "trigger_kind": runbook.trigger_kind,
            "cron": runbook.cron,
            "event_kind": runbook.event_kind,
            "timezone": runbook.timezone,
            # ⚠ **THE TENANT'S OWN CLOCK, RESOLVED TO AN INSTANT HERE** —
            # `BR-RBS-016`. The screen renders it back in the tenant's zone and
            # format from the shell's own publication (`BR-SHL-023`), so the
            # wire carries UTC and exactly one place decides what 06:00 means.
            "next_run": scheduler.next_run_at(runbook),
        },
        "cap": runbook.cap,
        "gate_mode": runbook.gate_mode,
        # `RB-050` — who this runbook is SHOWN to. `visible_to_roles` is the
        # admin's own answer or `None`; `roles` is what that resolves to once
        # the category's default and *Owner and Admin see every runbook* are
        # applied, so a settings sheet can draw both *what you set* and *what it
        # means* without re-deriving the second one on the client.
        "visible_to_roles": (
            None if runbook.visible_to_roles is None else list(runbook.visible_to_roles)
        ),
        "roles": list(models.roles_that_see(runbook.category, runbook.visible_to_roles)),
        # `BR-RBS-036` — the trust ratchet, as a fact rather than a sentence.
        # `dry_run_only` is what `RBS-004.5` needs to say *this runs dry until a
        # clean dry run is reviewed*; a Check is never held, whatever the
        # numbers, because it writes nothing.
        "trusted_version": runbook.trusted_version,
        "dry_run_only": (
            runbook.kind == models.KIND_ACTION
            and runbook.trusted_version != runbook.current_version
        ),
        # `BR-RBS-038` — OFFERED, never applied. `None` when there is nothing to
        # offer; the counts when there is. Nothing on this read applies it.
        "template_update": pending_template_update(runbook),
        # `RBS-004.7`, newest first (`DEF-RBS-4285`'s engine half).
        "activity": runbook_activity(runbook),
        "definition": document,
        # ⚠ **THE INPUTS, AND THIS IS A SECOND LIST BESIDE `definition.
        # parameters` ON PURPOSE — TWO QUESTIONS, NOT ONE FACT TWICE**
        # (`BR-RBS-042`, wave `T`).
        #
        #   `definition.parameters`  what the version this copy PINS declares.
        #                            History. A past run drew its scope from it
        #                            and it must never move (`BR-RBS-038`).
        #   `parameters` (here)      what a tenant may SET and what they have
        #                            set — read from the LIVE declaration,
        #                            because a domain is a fact about the code
        #                            that will run and `services.run_parameters`
        #                            reads exactly the same declaration. The
        #                            picker and the run therefore cannot offer
        #                            and honour different lists.
        #
        # ⚠ **IT CARRIES NO DOMAIN MEMBERS.** The rows a picker draws come from
        # `GET /runbooks/{key}/domains/{parameter}`, which pages — `account` is
        # 40,000 at the top of T5 and `NFR-3` binds every list. Inlining a
        # domain here would put an unpaginated list on a detail payload, which
        # is the fifth of the four breaches CLAUDE.md already names.
        "parameters": _parameter_settings(runbook),
        # ⚠ Derived from `ports[]` and from nothing else (`US-RBS-002`). The
        # guards travel with it because `RBS-004.4` draws a guard DISABLED with
        # its reason rather than hiding it — a guard a clerk cannot see is a
        # guard they will assume is absent.
        "guards": list((document or {}).get("guards") or ()),
        "ports": list((document or {}).get("ports") or ()),
        "writes_nothing": _writes_nothing(key),
        "requires": (document or {}).get("requires"),
        "last_run": last_run,
        "open_items": _open_work_items_by_runbook(tenant_id, [runbook.pk]).get(runbook.pk, 0),
    }


def _parameter_settings(runbook: Any) -> list[dict[str, Any]]:
    """Every input this runbook declares, with what THIS tenant set it to.

    `BR-RBS-042`. One row per declared input:

      `name` · `label` · `type` · `domain` · `multi` · `choices`
      `value`   what runs — the tenant's answer, or the declared default
      `is_set`  did the TENANT choose this, or is it the shipped default?

    ⚠ **`is_set` EXISTS BECAUSE THE TWO ARE THE SAME STRING TODAY AND WILL NOT
    ALWAYS BE** (`DEF-RBS-4338`). Until this wave the Scope tab drew each
    parameter's DECLARED DEFAULT and called it the runbook's scope — accidentally
    right, because no tenant had set anything, and wrong the first time one did,
    with no test failing because every test asserted the definition document
    rather than a tenant's choice. A flag beside the value is what lets a screen
    say *"you have not changed this"* without comparing two strings and guessing.

    ⚠ **`value` IS THE STORED FORM, SO *all* IS THE WORD** (clause 1). It is
    expanded when a RUN starts and never here: a payload that expanded it would
    hand the screen a frozen list, and a screen that then saved it back would
    write exactly the freeze the rule forbids.

    An empty list means the registry holds no module under this runbook's key —
    a template withdrawn, or a row created directly — and the screen keeps
    drawing the pinned definition's rows, which is what it did before this wave.
    """
    from apps.runbooks import services

    definition = services.definition_for(runbook)
    if definition is None:
        return []
    stored = runbook.parameters if isinstance(runbook.parameters, dict) else {}
    rows: list[dict[str, Any]] = []
    for parameter in definition.parameters:
        is_set = parameter.name in stored
        value = stored[parameter.name] if is_set else parameter.default
        rows.append(
            {
                "name": parameter.name,
                "label": parameter.label,
                "type": parameter.type,
                "required": parameter.required,
                "domain": parameter.domain,
                "multi": parameter.multi,
                "choices": list(parameter.choices),
                "setting_key": parameter.setting_key,
                "value": value,
                "is_set": is_set,
                # ⚠ **THE CHOSEN VALUES' OWN WORDS — B14 RULE 31.** A saved
                # `ref:object` value is an account id, and a Scope row that
                # printed it would put a uuid in front of a clerk. Only the
                # values a person CHOSE are resolved, never the domain: the
                # chosen account may be on page 700 of the picker, and the
                # picker is the paged route's job.
                "value_labels": _value_labels(parameter, value),
            }
        )
    return rows


def _value_labels(parameter: Any, value: Any) -> dict[str, str]:
    """`{value: label}` for what is chosen, or `{}` when there is nothing to look up.

    The word *all* has no label here — it is a RULE rather than a value
    (`BR-RBS-042` clause 1) and the screen says *All* in the reader's own
    language, from the catalogue, like every other piece of chrome.
    """
    from apps.runbooks import domains

    if parameter.domain is None or value is None:
        return {}
    chosen = value if isinstance(value, (list, tuple)) else [value]
    wanted = [str(one) for one in chosen if str(one) != contract.PARAM_ALL]
    if not wanted:
        return {}
    try:
        return domains.labels(parameter.domain, wanted)
    except domains.UnknownDomain:
        return {}


def _latest_definition_document(runbook: Any) -> dict[str, Any] | None:
    """The copy's OWN stored definition — the shipped half, without its settings.

    ⚠ **THE SETTINGS ARE STRIPPED BECAUSE THE SCREEN ALREADY HAS THEM.**
    `runbook_detail` serves `cap`, `gate_mode` and `schedule` from the runbook
    row, which is what a clerk just edited; serving them a second time inside
    `definition` would give `RBS-004` two sources for one fact, and the older of
    the two would win on whichever tab read it last.
    """
    from apps.runbooks import services

    version = latest_version(runbook)
    return None if version is None else services.shipped_half(version.definition)


# ── the offer · `BR-RBS-038`, wave E task E3 ─────────────────────────────────


def pending_template_update(runbook: Any) -> dict[str, Any] | None:
    """*Template updated · 1 new step · Review →* — computed, never applied.

    `BR-RBS-038`: **a change to a shipped template is OFFERED on a tenant's copy
    and never applied without a person accepting it.** This function is the
    OFFER and it is a pure read: it writes nothing, mints no version, and moves
    no runbook. `services.accept_template_update` is the only thing that
    applies it, and it runs when a person presses *Review →*.

    ⚠ **IT SERVES COUNTS AND NOT A SENTENCE.** *1 new step* varies by runbook
    and by bump, so it is DATA; *Template updated* and *Review →* are the same
    words for all 26 runbooks, so they are CHROME and belong in the eleven
    catalogues (`setupTypes.ts`'s rule, and B14 rule 35 — a catalogue is written
    in its own language, not translated from English). A server that sent the
    English would put screen copy in Python, which is what `contract.py` already
    refuses one level down for the setup view.

    ⚠ **`None` MEANS THERE IS NOTHING TO OFFER, AND THE THREE WAYS OF GETTING
    THERE ARE DELIBERATELY THE SAME ANSWER**: the runbook has no template behind
    it, the template is not in the registry (a module withdrawn), or the
    documents match. A screen draws nothing for all three, because in all three
    there is nothing a person can usefully press.
    """
    from apps.runbooks import services

    if not getattr(runbook, "template_key", None):
        return None
    definition = _registry_definition(runbook.template_key)
    if definition is None:
        return None
    version = latest_version(runbook)
    if version is None:
        return None
    held = services.shipped_half(version.definition)
    incoming = definition.as_definition_document()
    if held == incoming:
        return None

    def _keys(document: dict[str, Any], part: str) -> list[str]:
        return [str(row.get("key")) for row in (document.get(part) or ()) if isinstance(row, dict)]

    offer: dict[str, Any] = {"available": True, "from_version": version.version}
    for part in ("steps", "guards", "parameters"):
        before, after = set(_keys(held, part)), set(_keys(incoming, part))
        offer[f"{part}_added"] = len(after - before)
        offer[f"{part}_removed"] = len(before - after)
    before_ports = set(held.get("ports") or ())
    after_ports = set(incoming.get("ports") or ())
    offer["ports_added"] = len(after_ports - before_ports)
    offer["ports_removed"] = len(before_ports - after_ports)
    # ⚠ THE CATCH-ALL, AND IT IS NOT DECORATION. A template can change in a way
    # none of the counts above sees — a step RELABELLED, a parameter's default
    # moved, `requires` pointed at a different Check. Without this flag the offer
    # would be `available: true` with every count at zero, and a screen would
    # draw *Template updated · Review →* over nothing a reader can find. It says
    # *something else moved*, which is true and is enough for a person to press
    # Review and look.
    counted = [value for name, value in offer.items() if name.endswith(("_added", "_removed"))]
    offer["other_changed"] = not any(counted)
    return offer


def runbook_activity(runbook: Any, *, limit: int = 50) -> list[dict[str, Any]]:
    """`RBS-004.7` — every version, newest first, with what changed and who.

    ⚠ **THE TAB AN AUDITOR ASKS FOR FIRST, AND IT HAD NO DATA UNTIL THIS WAVE
    (`DEF-RBS-4285`).** The build sheet draws four change summaries — *Cap
    raised to 400* · *Paused* · *Schedule set to Mondays* · *Added from
    templates* — and `runbook_versions` held only a `jsonb` definition, of which
    *a diff of two documents is not those four sentences*. `summary` now carries
    the facts and the screen composes the sentence.

    ⚠ **`version` IS A NUMBER A PERSON READS AND THE ROW ID IS NOT SERVED AT
    ALL** (B14 rule 31, and `08-screen-layouts.md`'s own escape clause: *`4`
    renders as `v4`*). `id` is the version NUMBER here rather than the uuid, so
    there is no database id on this payload to render by accident — the same
    reason `_person` serves no id beside a name.

    ⚠ **IT TAKES A `limit` AND DOES NOT PAGE, AND THE DIFFERENCE MATTERS.**
    `NFR-3` binds a LIST SCREEN; this is a tab region on a detail payload whose
    length is bounded by how many times one runbook has been edited, not by
    tenant size. The window is taken in SQL (`[:limit]`), so a runbook edited
    ten thousand times still costs one bounded query — which is the property
    `NFR-5` actually asks for and what an unpaginated `list(...)` does not give.
    """
    rows = (
        models.RunbookVersion.objects.filter(
            tenant_id=runbook.tenant_id, runbook_id=runbook.pk
        )
        .select_related("changed_by")
        .order_by("-version")[: max(1, int(limit))]
    )
    return [
        {
            "id": row.version,
            "version": row.version,
            "changes": list(row.summary or ()),
            "actor": _person(row.changed_by),
            "when": row.changed_at.isoformat() if row.changed_at else None,
        }
        for row in rows
    ]


# ── the library · `GET /runbooks/templates` ──────────────────────────────────


def templates_page(
    tenant_id: Any,
    *,
    kind: str | None = None,
    category: str | None = None,
    q: str = "",
    role: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /runbooks/templates` — the shipped library, with this tenant's state.

    `07-endpoints.md` row 4: *the shipped library with **Added, Not added or
    Unavailable** per tenant, and the reason when unavailable*.

    ⚠ **IT PAGES, AND `07-endpoints.md` E-1 SAYS TO DO THIS DELIBERATELY RATHER
    THAN BY ACCIDENT.** The library is bounded by what we SHIP rather than by
    tenant size, so it is not `NFR-3`'s hazard — that is a list whose length
    grows with the tenant, as `GET /outstandings` does. It pages anyway, because
    the exception a lane grants a bounded list today is the exception the next
    lane cites for one that is not, and because `RBS-002`'s toolbar already
    draws the controls.

    ⚠ **THE SORT IS THE REGISTRY'S AND THE WINDOW IS A LIST SLICE, NOT SQL** —
    stated rather than hidden, because this file's own rule is *sort in SQL*.
    The templates are Python modules held in `registry`, not rows: there is no
    table to order. `registry.all()` returns them in key order, which is total
    and stable across processes. The ONE database read here is a single query
    for this tenant's `template_key`s, and it is not sorted at all.

    ⚠ **NOTHING IS EVER `unavailable` TODAY AND THAT IS AN ABSENCE, NOT A
    STATE.** A template is unavailable when it needs a switched-off capability
    (`RBS-002.2` — *Budget billing is switched off for you*), which is a read of
    the tenant's settings through the tenancy seam that no shipped runbook
    declares and no seam yet answers. Serving `state: "not_added"` for such a
    template would be wrong in the dangerous direction — it offers a button that
    would refuse — so the field is served with its two reachable values and the
    third is left to the wave that can compute it (`D3`/`D5`).
    """
    definitions = _template_definitions(kind=kind, category=category, q=q, role=role)
    definitions = _in_library_order(tenant_id, definitions)
    added = set(
        models.Runbook.objects.filter(tenant_id=tenant_id, origin=models.ORIGIN_SHIPPED)
        .exclude(template_key=None)
        .values_list("template_key", flat=True)
    )
    total = len(definitions)
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    number = _page_number(page, last)
    start = (number - 1) * size
    window = definitions[start : start + size]
    return {
        "rows": [
            {
                "template_key": one.key,
                "name": one.name,
                "kind": one.kind,
                "category": one.category,
                "tags": list(one.tags),
                "subject_type": one.subject_type,
                "unit_of_work": one.unit_of_work,
                "triggers": list(one.triggers),
                "steps": len(one.steps),
                "ports": list(one.ports),
                "writes_nothing": one.writes_nothing(),
                "state": "added" if one.key in added else "not_added",
                "unavailable_reason": None,
            }
            for one in window
        ],
        "page": number,
        "per": size,
        "total": total,
        # ⚠ **BUILT FROM THE TEMPLATES PRESENT AND NEVER FROM THE FIXED
        # SIXTEEN** (`BR-RBS-025`, `TC-RBS-20`). A chip that filters to nothing
        # is dead UI (hard-won law 2), which is why *Accounts* draws a chip on
        # the strength of one reserved template and *Assets* and *Work* draw
        # none. Derived here so the count has ONE answer rather than one per
        # screen; the chip row itself is `D3`.
        "category_chips": _template_category_chips(role),
        "kind_chips": _template_kind_chips(role),
    }


def _template_definitions(
    *, kind: str | None, category: str | None, q: str, role: str | None = None
) -> list[Any]:
    """The shipped library, filtered. `registry.all()` is already key-ordered.

    ⚠ **THE ROLE FILTER IS THE CATEGORY DEFAULT AND NOTHING ELSE, BECAUSE A
    TEMPLATE HAS NO PER-RUNBOOK OVERRIDE TO READ** (`RB-050`). An override lives
    on a tenant's ROW; a template is a Python module the tenant has not added
    yet, so `ROLE_VISIBILITY_BY_CATEGORY` is the whole answer here.
    `07-endpoints.md`'s worked example is exactly this list: *a Finance user's
    Templates page shows Finance, Payments and Collections runbooks and not
    Platform.*
    """
    from apps.runbooks.registry import registry

    text = (q or "").strip().casefold()
    out = []
    for one in registry.all():
        if kind in models.KINDS and one.kind != kind:
            continue
        if category in models.CATEGORIES and one.category != category:
            continue
        if text and text not in one.name.casefold() and text not in one.key.casefold():
            continue
        if role is not None and role not in models.roles_that_see(one.category):
            continue
        out.append(one)
    return out


def _in_library_order(tenant_id: Any, definitions: list[Any]) -> list[Any]:
    """`BR-RBS-026` — **Onboarding & Cutover first while a plan is open, last once it closes.**

    *"No other category carries an order rule"*, and this is the one place in
    the product where a list re-orders itself on the state of a different table:
    the library reads `cutover_plans.status`. That is what the category is FOR —
    a utility mid-cutover opens Templates to find the cutover runbooks, and the
    same utility six months later never wants to see them first again.

    ⚠ **IT SORTS A PYTHON LIST AND THAT IS NOT THE EXCEPTION IT LOOKS LIKE.**
    This file's own rule is *sort in SQL*, and `templates_page` already records
    why the library is different: the templates are Python modules held in
    `registry`, not rows — **there is no table to order**. One extra query
    (`EXISTS` over this tenant's open plans) decides the direction; the sort is
    over the shipped library, whose length is what WE ship and never grows with
    a tenant. `NFR-3`'s hazard is a list whose length grows with the tenant, and
    this is not one.

    Stable within each group: `registry.all()` is key-ordered and `sorted` is
    stable, so the rule moves ONE category's block and leaves every other row
    exactly where it was.
    """
    if not any(one.category == "onboarding_cutover" for one in definitions):
        return definitions
    plan_open = models.CutoverPlan.objects.filter(tenant_id=tenant_id, status="open").exists()
    first = 0 if plan_open else 1
    return sorted(
        definitions,
        key=lambda one: first if one.category == "onboarding_cutover" else (1 - first),
    )


def _visible_templates(role: str | None) -> tuple[Any, ...]:
    """The shipped library this role is SHOWN — the chips' population.

    ⚠ **THE CHIPS MUST BE BUILT FROM WHAT THIS READER CAN SEE, NOT FROM WHAT WE
    SHIP.** `BR-RBS-025` and hard-won law 2: a chip that filters to nothing is
    dead UI. Before `D5` a Finance user would have been offered a **Platform**
    chip that returned an empty list every time, which is the same defect
    `TC-RBS-20` already covers one cause of — a chip row built from the fixed
    sixteen — arriving from a second direction nobody had filtered.
    """
    from apps.runbooks.registry import registry

    if role is None:
        return registry.all()
    return tuple(
        one for one in registry.all() if role in models.roles_that_see(one.category)
    )


def _template_category_chips(role: str | None = None) -> list[dict[str, Any]]:
    held: dict[str, int] = {}
    for one in _visible_templates(role):
        held[one.category] = held.get(one.category, 0) + 1
    return [
        {"category": name, "count": held[name]} for name in models.CATEGORIES if name in held
    ]


def _template_kind_chips(role: str | None = None) -> list[dict[str, Any]]:
    all_of_them = _visible_templates(role)
    return [
        {"kind": "all", "count": len(all_of_them)},
        {"kind": models.KIND_CHECK, "count": sum(1 for one in all_of_them if one.is_check)},
        {"kind": models.KIND_ACTION, "count": sum(1 for one in all_of_them if not one.is_check)},
    ]


# ── the history · `GET /runbooks/runs` ───────────────────────────────────────

#: What `?f.outcome=` accepts. It is `runbook_runs.status`, and the name on the
#: wire is the screen's word: `RBS-008`'s column is **Outcome** and the chips
#: are *All · Checks · Actions · Failed · Stopped*. One vocabulary, and a value
#: outside it is IGNORED rather than refused (`BR-SHL-011`).
RUN_OUTCOMES = models.RUN_STATUSES


def runs_page(
    tenant_id: Any,
    *,
    runbook_key: str | None = None,
    category: str | None = None,
    kind: str | None = None,
    outcome: str | None = None,
    started_from: Any = None,
    started_to: Any = None,
    q: str = "",
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /runbooks/runs` — every run, newest first, across every runbook.

    `07-endpoints.md` row 8: *history across runbooks, filterable by runbook,
    category, outcome and date*. `RBS-008` is the screen and its columns are
    **Started · Runbook · By · Outcome · Acted · Took**.

    ⚠ **NEWEST FIRST IS `-started_at, -created_at, -id`, AND ALL THREE KEYS DO
    WORK.** `started_at` is what the screen calls *Started* and it is NULLABLE —
    every run written before `DEF-RBS-4291` was fixed carries `None`, and a sort
    on a nullable column alone puts those rows in a vendor-defined position
    (PostgreSQL sorts NULLs FIRST on a descending order, SQLite LAST), so the
    same query divides the rows differently on the two vendors. `created_at` is
    `auto_now_add` and never null. `id` is last and is a pure determinism key.

    ⚠ **`-id` ALONE WOULD NOT DO IT, AND THE FIRST DRAFT OF THIS FUNCTION
    THOUGHT IT WOULD.** uuid7 is time-ordered only to the MILLISECOND: RFC 9562
    puts a 48-bit unix-ms prefix in front of **12 random bits** and 62 more
    (`core.dbfields.uuid7`), so runs opened inside one millisecond order at
    random. A page-1/page-2 pair whose rows overlapped is what found it. The
    three keys together are TOTAL, which is the property a slice needs: the same
    query asked twice returns the same rows in the same places.

    ⚠ **`By` CANNOT BE A PERSON TODAY AND THE PAYLOAD SAYS SO RATHER THAN
    GUESSING** (`DEF-RBS-4292`). `RBS-008` calls that column *"the audit-actor
    question made visible"* and `runbook_runs` carries `approved_by` and
    `stopped_by` and **no `started_by`** — so who pressed **Run ▶** is not
    recorded anywhere. `by` therefore serves the TRIGGER, which is a fact, and
    `by.person` is `None` until the column exists. Filling it from `approved_by`
    would put the approver's name in the *started by* column, which is the kind
    of near-right answer nobody ever re-checks.
    """
    queryset = models.RunbookRun.objects.filter(tenant_id=tenant_id).select_related(
        "runbook", "approved_by", "stopped_by"
    )
    if runbook_key:
        queryset = queryset.filter(runbook__key=runbook_key)
    if category in models.CATEGORIES:
        queryset = queryset.filter(runbook__category=category)
    if kind in models.KINDS:
        queryset = queryset.filter(runbook__kind=kind)
    if outcome in RUN_OUTCOMES:
        queryset = queryset.filter(status=outcome)
    if started_from is not None:
        queryset = queryset.filter(started_at__gte=started_from)
    if started_to is not None:
        queryset = queryset.filter(started_at__lt=started_to)
    text = (q or "").strip()
    if text:
        queryset = queryset.filter(
            Q(runbook__name__icontains=text) | Q(runbook__key__icontains=text)
        )
    window, meta = _slice(queryset.order_by("-started_at", "-created_at", "-id"), page, per)

    rows = list(window)
    records = _record_counts(tenant_id, [row.pk for row in rows])
    return {"rows": [_run_row(run, records.get(run.pk, 0)) for run in rows], **meta}


def _run_row(run: Any, records: int) -> dict[str, Any]:
    """One `RBS-008` row. `id` is here to be LINKED WITH, never rendered.

    B14 rule 31 — *no database id is ever the visible value of a field* — bans
    drawing it, not carrying it: a run has no natural key and `/runs/{id}` is
    its address. What a screen shows is `runbook_name`, and that field is always
    populated, so there is no branch in which an id becomes the visible value.
    """
    return {
        "id": str(run.pk),
        "runbook_key": run.runbook.key,
        "runbook_name": run.runbook.name,
        "kind": run.runbook.kind,
        "category": run.runbook.category,
        "version": run.version,
        "mode": run.mode,
        "trigger": run.trigger,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "took_seconds": _took_seconds(run),
        "counts": dict(run.counts or {}),
        "records": records,
        "by": {"trigger": run.trigger, "person": None},
    }


def _record_counts(tenant_id: Any, run_ids: list[Any]) -> dict[Any, int]:
    """`{run_id: record rows}` for the page, grouped in SQL.

    One query for the whole page rather than one per row — the same reason
    `_last_run_by_runbook` is an aggregate. A volume runbook writes far fewer
    record rows than it examines (`BR-RBS-035`: read validation over 80,000
    meter-days writes **38** rows and a count of 80,000 in `RunbookRun.counts`),
    so this number and `counts` answer two different questions and both travel.
    """
    if not run_ids:
        return {}
    grouped = (
        models.RunbookRunRecord.objects.filter(tenant_id=tenant_id, run_id__in=run_ids)
        .values("run_id")
        .annotate(total=Count("id"))
    )
    return {row["run_id"]: row["total"] for row in grouped}


# ── one run · `GET /runbooks/runs/{id}` · `…/report` · `…/records` ───────────


def run_header(tenant_id: Any, run_id: Any) -> dict[str, Any] | None:
    """`GET /runbooks/runs/{id}` — header, counts, status, approver.

    `07-endpoints.md` row 9. Filtered by tenant BEFORE the id is looked at, so
    another tenant's run and a run that never existed are the same 404 (`HR-1`,
    hard rule 1). On PostgreSQL the row-level policy refuses it as well; the
    filter is written anyway because the test database is SQLite, where there is
    no row-level security at all and the omission would pass green.

    ⚠ **THE REPORT IS NOT IN THIS PAYLOAD.** It is its own route, because
    `RBS-006` draws the header while the blocks are still arriving and because
    a frozen document belongs behind an address that can be cached and diffed —
    which is what `TC-RBS-16` asserts byte-for-byte.
    """
    run = _run(tenant_id, run_id)
    if run is None:
        return None
    records = _record_counts(tenant_id, [run.pk]).get(run.pk, 0)
    row = _run_row(run, records)
    row.update(
        {
            "event_ref": run.event_ref,
            "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
            "scope_fingerprint": run.scope_fingerprint,
            "approved_by": _person(run.approved_by),
            "approved_count": run.approved_count,
            "stopped_by": _person(run.stopped_by),
            "unit_of_work": run.runbook.unit_of_work,
            "subject_type": run.runbook.subject_type,
            # A run that closed cleanly has blocks; one that failed at close may
            # have none. The screen needs to tell those apart before it fetches.
            "has_report": bool(run.report),
        }
    )
    return row


def _run(tenant_id: Any, run_id: Any) -> Any:
    """One run of THIS tenant, or `None` — including for a malformed id.

    A uuid the router accepted can still be a value the column cannot hold on
    some vendors, and a `ValidationError` escaping a read would answer 500 where
    the honest answer is 404. Caught here rather than in the route, because the
    route is thin (B8) and because two routes ask this question.
    """
    try:
        return (
            models.RunbookRun.objects.filter(tenant_id=tenant_id, pk=run_id)
            .select_related("runbook", "approved_by", "stopped_by")
            .first()
        )
    except (DjangoValidationError, ValueError, TypeError):
        return None


def run_report(tenant_id: Any, run_id: Any) -> list[Any] | None:
    """`GET /runbooks/runs/{id}/report` — **the stored block list, UNCHANGED**.

    `BR-RBS-020`, and this function is where that rule either holds or is lost:
    *a run's report is composed once, at CLOSE, from the twelve block types, and
    frozen; a later code change never alters a past result.* So this reads the
    column and returns it. It does not call the runbook's `report()`, does not
    re-derive a block, does not reshape a payload, does not fill in a field a
    newer renderer wants and does not drop one it no longer draws.

    ⚠ **`07-endpoints.md` E-5 NAMES THIS AS THE PLACE THE MISTAKE GETS MADE:**
    *"a build lane that renders from the live definition instead passes every
    test until a runbook is edited, and then rewrites history."* The reason it
    passes every test is that a fresh fixture's live report and its frozen one
    are identical — the difference only appears after an edit, which no test
    fixture performs by accident.

    ⚠ **AND IT MATTERS RIGHT NOW, NOT ONLY AFTER AN EDIT.** `DEF-RBS-4284` is
    open: the engine's six payloads and the wave-C renderer's six types
    disagree, and the fix moves the ENGINE to the renderer's shapes. A run
    closed before that lands is frozen in the old shape and a run closed after
    it in the new one, **and both are correct** — the report is what was
    composed that day. A serializer that "helped" by translating one into the
    other would rewrite the first result the product ever produced.

    `None` when the run is absent or belongs to another tenant — the same 404.
    An EMPTY LIST is a different answer and is served as one: a run that failed
    at close has no blocks, and `[]` says so where `None` would claim the run
    does not exist.
    """
    run = _run(tenant_id, run_id)
    if run is None:
        return None
    return run.report or []


def run_records_page(
    tenant_id: Any,
    run_id: Any,
    *,
    outcome: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any] | None:
    """`GET /runbooks/runs/{id}/records` — the plan and the outcome, per record.

    `07-endpoints.md` row 11: *per-record plan and outcome, filter by outcome*.

    ⚠ **THE PLAN AND THE OUTCOME ARE ONE ROW, WHICH IS WHY THIS LIST IS THE
    AUDIT.** `models.RunbookRunRecord`'s own docstring: *what did it say it
    would do versus what it did* — two tables would make that comparison a join
    and the audit becomes a query nobody writes.

    ⚠ **ORDERED `created_at, id` — AND THE FIRST DRAFT ORDERED BY `id` ALONE,
    WHICH SHUFFLED THE ROWS.** uuid7 is time-ordered only to the MILLISECOND
    (`core.dbfields.uuid7`: a 48-bit unix-ms prefix, then **12 random bits** and
    62 more), so three records written by one loop came back in a different
    order from the one they were written in and the *not done* file listed
    *Mill Yard* before *Oak Street Depot*. `created_at` is `auto_now_add` at
    microsecond resolution and `id` is the deterministic tiebreak underneath it.

    **What that pair guarantees, stated exactly rather than generously:** the
    order is TOTAL and STABLE — the same query asked twice returns the same rows
    in the same places, which is the property paging needs, and it is the same
    order the two result files are written in, so a clerk reading page 2 of the
    table and row 51 of the CSV is looking at the same record. It is write order
    down to the microsecond and no finer; two rows stamped in one microsecond
    are ordered consistently but arbitrarily.
    """
    run = _run(tenant_id, run_id)
    if run is None:
        return None
    queryset = models.RunbookRunRecord.objects.filter(tenant_id=tenant_id, run_id=run.pk)
    if outcome:
        queryset = queryset.filter(outcome=outcome)
    window, meta = _slice(queryset.order_by("created_at", "id"), page, per)
    return {"rows": [_record_row(row) for row in window], **meta}


def _record_row(record: Any) -> dict[str, Any]:
    """One record. **Money carries its currency and neither is a float.**

    Hard rule 2: stored to 4 decimals, displayed at 2, `CHAR(3)` currency, never
    a float. `amount` is a `Decimal` and is serialised as a STRING so the
    4-decimal value survives JSON — `json` renders a float and 12.3400 comes
    back as 12.34 with the two stored decimals gone. Where `amount` is null,
    `currency` is null too (`models.RunbookRunRecord`).
    """
    return {
        "subject_type": record.subject_type,
        "subject_id": str(record.subject_id) if record.subject_id else None,
        "planned_action": record.planned_action,
        "decided_by_rule": record.decided_by_rule,
        "outcome": record.outcome,
        "reason": record.reason,
        "fix_route": record.fix_route,
        "decision": record.decision,
        "decided_at": record.decided_at,
        "amount": None if record.amount is None else str(record.amount),
        "currency": record.currency,
        "data": dict(record.data or {}),
    }


#: The outcome words that mean **the run did it**. Everything else — a skip, a
#: refusal, a failure, a record still queued for a person, and a record with no
#: outcome at all — is in the *not done* file.
DONE_OUTCOMES = ("done", "acted", "sent", "applied", "written", "matched", "queued_notice")


def run_result_records(tenant_id: Any, run_id: Any, *, done: bool) -> Any:
    """The rows behind ONE of the two result files, ordered, unsliced, LAZY.

    `07-endpoints.md` row 14: *the two result files, each row carrying its
    reason and its fix*.

    ⚠ **IT RETURNS A QUERYSET AND THE CALLER STREAMS IT.** A download is the one
    list in this module that is deliberately not paged — a file with a page 2 is
    not a file — and that is exactly where `DEF-PAY-4221`'s mistake would be
    reintroduced if the rows were materialised. `api.py` iterates it into a
    streaming response, so the peak memory is one row and not one run, whatever
    a tenant's size. `NFR-5` is intact: there is no cap on how many rows the
    file may carry, only on how many are in memory at once.

    ⚠ **THE SPLIT IS ON THE OUTCOME AND THE DEFAULT SIDE IS *NOT DONE*.**
    A record with a null outcome — written at evaluation, before any act
    (`BR-RBS-004`) — belongs in the *not done* file: it names something the run
    planned and did not do, which is precisely what a clerk opens that file to
    find. Putting it in *done* would be a file that claims work nobody
    performed.
    """
    queryset = models.RunbookRunRecord.objects.filter(tenant_id=tenant_id, run_id=run_id)
    if done:
        return queryset.filter(outcome__in=DONE_OUTCOMES).order_by("created_at", "id")
    return queryset.exclude(outcome__in=DONE_OUTCOMES).order_by("created_at", "id")


# ══════════════════════════════════════════════════════════════════════════
# CR-075 WAVE H — THE WORK LIST (`US-RBS-006`, `RBS-007`)
#
# One screen holding findings from Checks, exceptions from Actions and human
# tasks from a cutover plan, **upserted by fingerprint so a repeated finding
# ages rather than duplicating** (`BR-RBS-017`). The engine writes the rows
# (`engine/work_items.py`); this reads them.
# ══════════════════════════════════════════════════════════════════════════

#: `RBS-007`'s *Weight* column is a PILL, and these are the four it draws. The
#: stored value is an integer (`work_items.weight`) and no internal code reaches
#: a clerk (B14 rule 32), so the translation happens HERE, at the screen's edge.
#:
#: ⚠ **A HUMAN TASK IS A KIND, NOT A WEIGHT**, and it wins over the number: a
#: cutover item somebody has to sign is not *routine* because nobody typed a
#: priority on it.
WORK_ITEM_PILLS: tuple[tuple[int, str, str], ...] = (
    (100, "blocks_billing", "danger"),
    (50, "before_go_live", "warning"),
    (0, "routine", "neutral"),
)

#: The four filters `RBS-007`'s toolbar declares (`EP-RBS-03`'s capability
#: matrix): source · status · owner · due. An unknown value falls back to
#: unfiltered — a list URL never 4xx's over its own params (`BR-SHL-011`).
WORK_ITEM_STATUSES = ("open", "resolved")


def work_items_page(
    tenant_id: Any,
    *,
    source_kind: str | None = None,
    status: str | None = "open",
    owner_id: Any = None,
    q: str = "",
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /work-items` — the work list, **paged on the server** (`NFR-3`).

    ⚠ **IT PAGES, AND THE ARGUMENT THAT IT NEED NOT IS THE ONE THIS REPOSITORY
    ABANDONED.** `DEF-PAY-4221` names four lists that are unpaginated *on
    purpose* because *"a utility under 3,000 connections"* has few rows. The
    ICP's ceiling moved to **40,000** on 2026-09-06, and a daily sweep over
    40,000 accounts is a work list with five figures of history in it. Nothing
    here caps, truncates or materialises the whole set.

    **Sorted by weight, then age** — `EP-RBS-03`'s capability matrix, in those
    words. ⚠ **AND *AGE* IS OLDEST FIRST**, which is the opposite of every other
    list in the product and is the whole point of the screen: a thing ignored
    for thirty days must rise, not sink. `id` is the third key and is a pure
    determinism key — uuid7 is time-ordered only to the millisecond, so two rows
    written inside one millisecond order at random without it and a page-1 /
    page-2 pair can overlap.
    """
    queryset = models.WorkItem.objects.filter(tenant_id=tenant_id).select_related(
        "owner_user", "source_run", "source_run__runbook"
    )
    if source_kind in models.WORK_ITEM_SOURCE_KINDS:
        queryset = queryset.filter(source_kind=source_kind)
    if status in WORK_ITEM_STATUSES:
        queryset = queryset.filter(status=status)
    if owner_id:
        queryset = queryset.filter(owner_user_id=owner_id)
    text = (q or "").strip()
    if text:
        queryset = queryset.filter(Q(title__icontains=text) | Q(subject_ref__icontains=text))
    window, meta = _slice(queryset.order_by("-weight", "created_at", "id"), page, per)
    return {"rows": [work_item_row(row) for row in window], **meta}


def work_item_row(item: Any) -> dict[str, Any]:
    """One `RBS-007` row — *What needs doing · From · Weight · Owner · Age*.

    ⚠ **`fingerprint` IS NOT IN THIS PAYLOAD AND MUST NEVER BE.** `US-RBS-006`
    §5: *never rendered* (B14 rule 31). It is how the engine finds the row
    again; it is not a fact about the work.

    ⚠ **`age` IS `created_at` AND NEVER `updated_at`.** *"Thirty daily sweeps
    over one missing read are ONE item, THIRTY DAYS OLD"* — a row that showed
    the last sighting would read *3 hours* every morning and the screen would
    lose the only number that tells a clerk something has been ignored.

    ⚠ **`from` IS THE RUNBOOK'S NAME, NOT ITS KEY AND NOT ITS ID**, and it is
    `None` for a human task — which has no run, lawfully, and is why
    `source_run` is nullable.
    """
    pill, tone = _work_item_pill(item)
    run = item.source_run
    return {
        "id": str(item.pk),
        "source_kind": item.source_kind,
        "from": None if run is None else run.runbook.name,
        "run_id": None if run is None else str(run.pk),
        "runbook_key": None if run is None else run.runbook.key,
        "title": item.title,
        "subject_ref": item.subject_ref or None,
        "weight": item.weight,
        "weight_pill": pill,
        "weight_tone": tone,
        "fix_route": item.fix_route or None,
        # `_owner_name` and NOT `_person` — `DEF-RBS-4365`. This field is a bare
        # NAME string; `_person` answers `{"name": …}` for a nullable actor and
        # the two were one name until the shadowing was found.
        "owner": None if item.owner_user_id is None else _owner_name(item.owner_user),
        "owner_id": None if item.owner_user_id is None else str(item.owner_user_id),
        "due_on": item.due_on,
        "status": item.status,
        "created_at": item.created_at,
        "resolved_at": item.resolved_at,
    }


def _work_item_pill(item: Any) -> tuple[str, str]:
    """The pill's machine name and its tone. A human task wins over the number."""
    if item.source_kind == models.WORK_ITEM_SOURCE_HUMAN_TASK:
        return "human_task", "info"
    for floor, name, tone in WORK_ITEM_PILLS:
        if (item.weight or 0) >= floor:
            return name, tone
    return "routine", "neutral"


def _owner_name(user: Any) -> str:
    """What a clerk calls this person. Never an id, never an email (B14 31).

    ⚠ **THIS WAS CALLED `_person` AND IT SHADOWED THE `_person` 1,250 LINES
    ABOVE — `DEF-RBS-4365`, a 500 ON A SHIPPED SCREEN.** Python takes the last
    definition at module scope, silently, so `runbook_activity` — which passes a
    NULLABLE actor and expects `{"name": …} or None` — was calling this one, and
    `GET /runbooks/{key}` raised `AttributeError: 'NoneType' object has no
    attribute 'first_name'` for **every runbook the code added rather than a
    person edited**: `ensure_version` writes v1 with `changed_by` null and wave
    E's own test asserts `activity[1]["actor"] is None`.

    The two answer different questions and only one may keep the name. This one
    takes a REQUIRED owner and returns a bare string; the other takes a nullable
    actor and returns the payload shape `RBS-004.7` draws.
    """
    name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
    return name or (user.email or "").split("@")[0]


def work_item(tenant_id: Any, item_id: Any) -> Any:
    """One row for THIS tenant, or `None`.

    An item of another tenant and an item that never existed are the same
    answer, which is the 404-never-403 boundary (hard rule 1).
    """
    try:
        return (
            models.WorkItem.objects.filter(tenant_id=tenant_id, pk=item_id)
            .select_related("owner_user", "source_run", "source_run__runbook")
            .first()
        )
    except (DjangoValidationError, ValueError, TypeError):
        # A uuid the router accepted can still be a value the column cannot
        # hold; a `ValidationError` escaping a read answers 500 where the
        # honest answer is 404. The same guard `run_header` carries.
        return None


def work_item_counts(tenant_id: Any) -> dict[str, int]:
    """*All 14 · Blocks billing 3 · Mine 5 · Cutover 6* — `RBS-007` region 2.

    ⚠ **THE COUNTS ARE COMPUTED, NOT DERIVED FROM THE PAGE.** A chip that
    counted the rows on screen would read *All 50* on a list of 900 — which is
    the shape `NFR-3` exists to prevent one layer up.
    """
    from django.db.models import Count

    open_items = models.WorkItem.objects.filter(tenant_id=tenant_id, status="open")
    by_kind = {
        row["source_kind"]: row["n"]
        for row in open_items.values("source_kind").annotate(n=Count("id"))
    }
    return {
        "all": sum(by_kind.values()),
        "blocks_billing": open_items.filter(weight__gte=100).count(),
        "findings": by_kind.get(models.WORK_ITEM_SOURCE_FINDING, 0),
        "exceptions": by_kind.get(models.WORK_ITEM_SOURCE_EXCEPTION, 0),
        "human_tasks": by_kind.get(models.WORK_ITEM_SOURCE_HUMAN_TASK, 0),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-041 (EP-RBS-01; CR-075 wave A task A3) · US-RBS-015 (CR-075 wave B task B3)
# generated: 2026-09-06 by the CR-075 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint before wave D) E=n/a(no screen — the renderers are wave C) F✔ G✔ H=n/a(no 🔒 path)
# gates: G115 (the import census) · pytest tests/test_us_rbs_015_conformance.py
# exceptions: none — every selector here has a caller in services.py in the same commit
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
