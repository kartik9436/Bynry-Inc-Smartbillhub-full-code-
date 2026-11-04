# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-004 (S61 viewer list — filter bar, newest-first, hot window) ·
#           US-AUD-005 (detail drawer payload + the entity-scoped read service
#           every per-entity Audit tab consumes) · US-AUD-006 (the row count the
#           export cap is measured against) · US-AUD-008 (archive search — the
#           explicit opt-in that reads the DETACHED cold partitions alongside
#           the hot table, tenant-scoped identically)   Screens: S61 · S21/S50 tabs
# Rules:    BR-AUD-007 (tenant-scoped ONLY — current tenant's rows exclusively) ·
#           BR-AUD-009 (filter vocabulary + the six S61 columns) · BR-AUD-010
#           (per-entity tabs are windows into this store, never copies) ·
#           BR-AUD-013 (server pagination · 2-yr hot window default · EXPLICIT
#           archive only · no unbounded query) · BR-AUD-012 (7-yr retention =
#           the archive window's own floor) · BR-AUD-006 (masked values render
#           exactly as stored — nothing here unmasks) · BR-SHL-011 (q/sort/dir/
#           page/per/f.‹name›; invalid values fall back, never error)
# Tests:    06-backend/tests/test_us_aud_004_006_viewer.py (per-TC; the RLS
#           halves = G5 isolation suite on live Postgres)
# Impacts:  apps/audit/api.py (every read) · apps/audit/services.py (export cap)
# ───────────────────────────────────────────────────────
"""audit read path (B8/LAW 0: api thin → services write → selectors read).

Every query here is tenant-filtered at the app layer AND backed by RLS FORCE on
Postgres (BR-AUD-007). The filter is convenience; RLS is the law — the sqlite
tier exercises the filter, the G5 isolation suite proves RLS.

Bounded by construction (BR-AUD-013): every query starts from a time floor —
the 2-year hot window by default, the 7-year retention horizon (BR-AUD-012)
when the caller passes `archive` explicitly. There is no code path here that
issues an unbounded audit query.

Two honest absences, neither invented:
- **Source (UI/API/job)** — GAP AUD-D2: no B2 column anchors it, so the field
  is served as `null`, present-but-empty exactly as US-AUD-004 §5 requires.
- **module + action-type class filters** — BR-AUD-009 names them and BR-AUD-004
  defines the six classes, but both are properties of the US-AUD-002 EVENT-CODE
  CATALOG, which is not built (no catalog exists in this module). Classifying
  codes here would invent that catalog, so `f.action` filters the action CODE
  and the class/module filters are absent and REPORTED.

Cross-module READ (Eng disposition, recorded — the same one identity/selectors
.py records for its BR-IDN-012 count): the Actor column resolves
`audit_log.actor_user_id` to a display name through identity's `users` model,
read-only, one bulk query per page, never a write across the boundary (B1). A
bulk `identity.selectors.users_by_ids()` seam would be the tidier home for it —
flagged, not reached into.
"""

import re
import uuid as uuid_module
from datetime import datetime, timedelta, timezone as datetime_timezone
from typing import Any

from django.apps import apps as django_apps
from django.db import connection
from django.db.models import Q, QuerySet, TextField
from django.db.models.functions import Cast
from django.utils import timezone

from apps.audit import diagnostics as audit_diagnostics
from apps.audit.models import ArchiveJobRun, AuditLog
from core import archival

# US-AUD-004 capability row: sortable columns → ORM fields (IS-2). "When desc"
# is the default (newest first — the corpus precedent the story cites).
AUDIT_LIST_SORTS = {
    "when": "created_at",
    "actor": "actor_user_id",
    "action": "action",
    "entity": "entity_type",
}
AUDIT_LIST_DEFAULT_SORT = "when"
AUDIT_LIST_DEFAULT_DIR = "desc"

# BR-AUD-009 filter vocabulary, in BR-SHL-011's `f.‹name›` grammar. `entity` is
# the `type:id` shorthand the 11b §2.12 S50 row uses (`f.entity=asset:{id}`);
# `entity_type` + `entity_id` are the same filter spelled out.
#
# ⚠ `outcome` IS THE EIGHTH AND IT IS NOT IN BR-AUD-009 — DEF-3322 / CR-067 B3.
# BR-AUD-009's vocabulary was written when this log had no failure rows to find;
# `sample.block_failed` arrived with CR-039 wave B. The PO asked for the control
# in as many words on 2026-09-02 — *"What I would add to the toolbar is a
# 'Errors only' filter, so you can jump straight to the failures without
# scrolling past 800 rows of successful seeding. - Yes this is required"* — and
# the reporting tenant's own log carries 809 rows. Reported for the BR-AUD-009
# amendment rather than folded in silently.
AUDIT_FILTERS = (
    "actor",
    "action",
    "entity_type",
    "entity_id",
    "entity",
    "from",
    "to",
    "outcome",
    "kind",
)

# ── `f.kind` — one entity's history split by KIND (DEF-CUS-9722) ────────────
# Image 29's *All · Changes · Messages* on a move-in's Audit tab. A message
# queued for an account is audited against the MESSAGE (`outbound_message`,
# its own id) and names the account only in `after.account_id`
# (`notifications.services._audit_created`), so `f.entity_id=<account>` alone
# never found one. With `f.kind`:
#   changes  — the rows against the entity itself (no message rows);
#   messages — `outbound_message` rows, narrowed by `after.account_id` when an
#              entity id is given;
#   all      — the two together, ONE query, paged and counted by the server
#              (NFR-3), so the filter describes the history and not a page.
# Absent → the read is unchanged; any other value falls back (BR-SHL-011).
# No join: the archive's re-pointed SQL (`ArchiveResultSet`) still holds.
KIND_ALL = "all"
KIND_CHANGES = "changes"
KIND_MESSAGES = "messages"
AUDIT_KINDS = (KIND_ALL, KIND_CHANGES, KIND_MESSAGES)
MESSAGE_ENTITY = "outbound_message"

# ── The failure vocabulary (`f.outcome=error`) ──────────────────────────────
# ⚠ **THIS LIST IS THE WHOLE FILTER, AND IT IS A LIST BECAUSE `action` CANNOT
# BE.** `f.action` matches ONE code with `__iexact`, and "did this go wrong?"
# is eight codes today — so no value of the filter that already existed says
# "errors", which is exactly what DEF-3322 records.
#
# ⚠ **AND THE NAIVE VERSION IS WORSE THAN NO FILTER AT ALL.** `parse_list_params`
# DROPS an `f.<name>` it does not recognise rather than refusing it (BR-SHL-011 —
# a list param never 4xx's), so a toolbar toggle sending `f.outcome=error` at a
# server that does not declare it comes back with the WHOLE 809-row list and
# reads as a product with no errors in it. That is why `"outcome"` is in the
# tuple above and this filter is server-side: the count and the pagination are
# the server's, and narrowing one 25-row page in a browser would report "no
# errors" on 32 pages out of 33.
#
# **EVERY CODE BELOW WAS READ OFF ITS WRITER, not inherited from the defect
# row.** In writer order: `apps/tenancy/sample_data.AUDIT_BLOCK_FAILED` ·
# `apps/tenancy/sample_data` + `apps/customers/sample_data` (the incomplete
# run) · `core/audit.REFUSAL_ATTEMPT_ACTION` (BR-AUD-018's refused attempt) ·
# `apps/identity/services` (the failed sign-in and the lockout that follows
# it) · `apps/tenancy/services` (provisioning) · `apps/customers/services`
# (a customer number the matcher refused to mint) ·
# `apps/tenancy/reference_sweep` (the sweep's own failure).
#
# ⚠ **`service_request.refused` IS DELIBERATELY NOT HERE, AND THE NEXT LANE TO
# NOTICE IT SHOULD LEAVE IT OUT TOO.** It is written when a member of staff
# turns an application DOWN — a business decision that worked exactly as
# designed — and the PO's ask is about *"errors [that] will happen run time and
# it is very difficult to reproduce those"*. Putting a correct refusal in a list
# labelled "Errors only" would make the control lie in the other direction: a
# clean log would read as full of faults. Same test for anything added later —
# **did the PRODUCT fail, or did a PERSON say no?**
FAILURE_ACTIONS: tuple[str, ...] = (
    "sample.block_failed",
    "sample.seed_incomplete",
    "security.attempt_refused",
    "auth.sign_in_failed",
    "auth.lockout",
    "tenant.provision_failed",
    "customer.not_created",
    "reference.sweep_failed",
)

#: The only value of `f.outcome` that means anything. Anything else falls back
#: to "no outcome filter" — the same posture `wants_archive` takes, and for the
#: same reason: a typo must never quietly change which rows a person is looking
#: at (BR-SHL-011).
OUTCOME_ERROR = "error"

HOT_WINDOW_DAYS = 730  # BR-AUD-013: the 2-year hot window (the default floor)
RETENTION_DAYS = 2557  # BR-AUD-012: 7 years total — the archive window's floor
ARCHIVE_PARAM = "archive"  # BR-AUD-013: archive reads are EXPLICIT, never implied
#: `f.actor=system` — an UNNAMED system job. ⚠ NARROWED BY US-AUD-010, AND THE
#: NARROWING IS THE POINT OF THE STORY RATHER THAN A SIDE EFFECT. It used to
#: mean "actor_user_id IS NULL", which after US-AUD-010 would sweep up every
#: named runbook alongside every anonymous job — putting back exactly the
#: indistinguishability the story exists to remove, one filter along. `system`
#: is now the unnamed half only.
SYSTEM_ACTOR = "system"  # BR-AUD-003: no user id AND no name = a system job
#: `f.actor=automation` — every actor that NAMES itself (BR-AUD-019). A VALUE of
#: the actor filter BR-AUD-009 already names, not a new filter: the vocabulary
#: is unchanged and `AUDIT_FILTERS` does not move.
AUTOMATION_ACTOR = "automation"

_SUMMARY_FIELD_LIMIT = 3  # keep the S61 Summary cell one line
_SUMMARY_VALUE_LIMIT = 40


def wants_archive(query_params: Any) -> bool:
    """BR-AUD-013: the archive window opens only on an EXPLICIT opt-in.

    Anything other than a truthy token reads as "hot window" — a typo can never
    silently widen the query (and per BR-SHL-011 it never errors either).
    """
    raw = str(query_params.get(ARCHIVE_PARAM, "") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def window_floor(*, archive: bool, now: datetime | None = None) -> datetime:
    """The time floor every audit query starts from (BR-AUD-013 — no unbounded
    endpoint exists). Hot = 2 years; archive = the 7-year retention horizon
    (BR-AUD-012), which is a bound in law, not an invented one."""
    reference = now or timezone.now()
    days = RETENTION_DAYS if archive else HOT_WINDOW_DAYS
    return reference - timedelta(days=days)


def _parse_moment(raw: Any, *, end_of_day: bool) -> datetime | None:
    """`YYYY-MM-DD` or a full ISO timestamp → aware datetime; anything else →
    None so the caller FALLS BACK (BR-SHL-011: list params never 4xx)."""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(text) == 10:  # a bare date bounds the whole day, inclusive
        parsed = (
            parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            if end_of_day
            else parsed
        )
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=datetime_timezone.utc)
    return parsed


def _valid_uuid(value: Any) -> uuid_module.UUID | None:
    try:
        return uuid_module.UUID(str(value))
    except (TypeError, ValueError):
        return None


# ── The support reference, and why an entity id is matched by PREFIX ────────
# PO ruling 2026-08-19 (decision log `3340c68`): a refusal the user cannot act
# on hands them "some identifier that they can report to support", and it must
# be readable aloud. A `trace_id` is `uuid4().hex` — thirty-two characters —
# and nobody dictates that over the phone, so the screen shows the first EIGHT,
# uppercased and grouped: `5F2B-9C1D`.
#
# ⚠ THAT WOULD BE WORSE THAN NOTHING IF SUPPORT COULD NOT LOOK IT UP. The
# ruling says so in as many words: "a shortened id that support cannot search
# by is worse than none, because the user reads it out and the call stalls."
# The BR-AUD-018 attempt row stores the FULL trace id in `entity_id`, so this
# is the other half of the same change — `f.entity_id` accepts a hex PREFIX,
# case-insensitively and with the display dashes stripped, and the S61 viewer
# answers `5F2B-9C1D` with the row that carries `5f2b9c1d…`.
#
# `entity_id` is a UUIDField, so a `startswith` LIKE against it is a type error
# on PostgreSQL (`operator does not exist: uuid ~~ unknown`). Casting to text
# is what makes the prefix comparable, and it works identically on the sqlite
# test tier and on Postgres.
SUPPORT_REF_HEX = 8  # mirrors 07-frontend/src/api/client.ts SUPPORT_REF_HEX
_HEX_ONLY = re.compile(r"[^0-9a-f]")


def _entity_id_prefix(value: str) -> str | None:
    """`5F2B-9C1D` → `5f2b9c1d`, or None when it is not a usable prefix.

    A FULL uuid is not a prefix case — the caller matches those exactly, which
    stays an indexed equality test.
    """
    hex_only = _HEX_ONLY.sub("", str(value).lower())
    if not SUPPORT_REF_HEX <= len(hex_only) < 32:
        return None
    return hex_only


def audit_queryset(
    tenant_id: Any,
    *,
    filters: dict[str, str] | None = None,
    archive: bool = False,
    sort: str | None = None,
    direction: str = AUDIT_LIST_DEFAULT_DIR,
    now: datetime | None = None,
) -> QuerySet:
    """The ONE filtered, time-bounded, tenant-scoped audit query (BR-AUD-007/
    009/013). Every filter is optional; every invalid value falls back.

    US-AUD-004 TC-6: a `from` later than `to` is a hand-edited impossible range
    — the pair falls back to the window floor rather than erroring (BR-SHL-011).
    """
    filters = filters or {}
    queryset = AuditLog.objects.filter(tenant_id=tenant_id)

    floor = window_floor(archive=archive, now=now)
    date_from = _parse_moment(filters.get("from"), end_of_day=False)
    date_to = _parse_moment(filters.get("to"), end_of_day=True)
    if date_from is not None and date_to is not None and date_from > date_to:
        date_from = date_to = None  # impossible range → fall back (TC-6)
    # A `from` inside the window narrows it; one BEFORE the floor cannot widen
    # it — the floor is the law (BR-AUD-013), the filter is the user's wish.
    effective_from = max(floor, date_from) if date_from is not None else floor
    queryset = queryset.filter(created_at__gte=effective_from)
    if date_to is not None:
        queryset = queryset.filter(created_at__lte=date_to)

    actor = str(filters.get("actor", "") or "").strip()
    if actor.lower() == SYSTEM_ACTOR:
        # BR-AUD-003 — an unnamed job: no user id AND no name. The second half
        # is US-AUD-010's; without it this filter answers "every automation",
        # which is the question the story exists to stop anyone having to ask.
        queryset = queryset.filter(actor_user_id__isnull=True, actor_kind__isnull=True)
    elif actor.lower() == AUTOMATION_ACTOR:
        queryset = queryset.filter(actor_kind__isnull=False)  # BR-AUD-019
    elif actor:
        actor_id = _valid_uuid(actor)
        queryset = queryset.filter(actor_user_id=actor_id) if actor_id else queryset.none()

    action = str(filters.get("action", "") or "").strip()
    if action:
        # The CODE, case-insensitively. The action-type CLASS filter needs the
        # US-AUD-002 catalog (absent — module docstring), so it is not served.
        queryset = queryset.filter(action__iexact=action)

    # CR-067 B3 / DEF-3322 — "Errors only". A NAMED set, never a prefix guess:
    # `sample.block_retried` starts with the same word as a failure and records
    # a step that recovered, and `auth.sign_in` is a success. See
    # `FAILURE_ACTIONS` above for why each code is in it and why one is not.
    #
    # ⚠ AND IT IS `AND`-ed WITH `f.action`, WHICH IS THE ONLY HONEST READING.
    # Every filter on this screen narrows (BR-SHL-011); a person who has typed
    # an action code and then ticks Errors only is asking for both. When the
    # two disagree the answer is an empty list, which is TRUE, rather than a
    # wider one that quietly ignored the tick.
    outcome = str(filters.get("outcome", "") or "").strip().lower()
    if outcome == OUTCOME_ERROR:
        queryset = queryset.filter(action__in=FAILURE_ACTIONS)

    entity_type = str(filters.get("entity_type", "") or "").strip()
    entity_id = str(filters.get("entity_id", "") or "").strip()
    combined = str(filters.get("entity", "") or "").strip()
    if combined and ":" in combined:  # 11b §2.12 `f.entity=asset:{id}` shorthand
        shorthand_type, _, shorthand_id = combined.partition(":")
        entity_type = entity_type or shorthand_type.strip()
        entity_id = entity_id or shorthand_id.strip()
    elif combined:
        entity_type = entity_type or combined
    kind = str(filters.get("kind", "") or "").strip().lower()
    if kind not in AUDIT_KINDS:
        kind = ""
    is_message = Q(entity_type__iexact=MESSAGE_ENTITY)
    if kind and entity_id and _valid_uuid(entity_id) is not None and not entity_type:
        target = _valid_uuid(entity_id)
        own = Q(entity_id=target) & ~is_message
        theirs = is_message & Q(after__account_id=str(target))
        chosen = {KIND_CHANGES: own, KIND_MESSAGES: theirs, KIND_ALL: own | theirs}[kind]
        return _sorted(queryset.filter(chosen), sort, direction)
    if kind == KIND_CHANGES:
        queryset = queryset.exclude(is_message)
    elif kind == KIND_MESSAGES:
        queryset = queryset.filter(is_message)
    if entity_type:
        queryset = queryset.filter(entity_type__iexact=entity_type)
    if entity_id:
        target = _valid_uuid(entity_id)
        if target is not None:
            queryset = queryset.filter(entity_id=target)
        else:
            # Not a whole uuid — the support reference a user read off a system
            # error is a PREFIX of one (see `_entity_id_prefix` above).
            prefix = _entity_id_prefix(entity_id)
            queryset = (
                queryset.annotate(_entity_id_text=Cast("entity_id", TextField())).filter(
                    _entity_id_text__startswith=prefix
                )
                if prefix
                else queryset.none()
            )

    return _sorted(queryset, sort, direction)


def _sorted(queryset: QuerySet, sort: str | None, direction: str) -> QuerySet:
    field = AUDIT_LIST_SORTS.get(sort or AUDIT_LIST_DEFAULT_SORT, "created_at")
    prefix = "-" if direction == "desc" else ""
    # Stable secondary sort (IS-2) — id breaks ties inside one timestamp.
    return queryset.order_by(f"{prefix}{field}", "-id" if prefix else "id")


class ArchiveResultSet:
    """US-AUD-008: the hot table AND the detached (cold) partitions, as one
    paginatable result set.

    WHY THE FILTERS ARE NOT WRITTEN TWICE. `audit_queryset` above is the single
    definition of what an audit filter MEANS — the window floor, the impossible-
    range fallback, the `system` actor, the `type:id` shorthand. A second
    hand-written WHERE clause for the archive would be a copy free to drift, and
    the drift would be invisible: both paths would keep passing their own tests
    while answering different questions. So the ORM's own compiled SQL is taken
    and re-pointed at each cold partition by its table name — one filter
    implementation, several tables.

    That substitution is safe because this query has NO JOIN: the compiler emits
    the table's real name as the only qualifier, and the partition names come
    from the catalog (`core.archival.detached_partitions`), never from a caller.

    RLS is untouched and is the point of doing it this way at all: a detached
    partition keeps the tenant policy it was created with (DEF-027), so an
    archive read is scoped by `app.tenant_id` exactly like a hot read
    (BR-AUD-007 / US-AUD-008 TC-7). The `tenant_id = …` term the ORM already
    adds rides along as the app-layer half.

    Implements `count()`, `__len__` and slicing — the three things
    django.core.paginator asks of an object list — so the existing BE-05
    pagination envelope serves archive pages with no special case in the view.
    """

    def __init__(self, queryset: QuerySet, partitions: list[str]) -> None:
        self._queryset = queryset
        self._partitions = partitions
        self._count: int | None = None

    # ── SQL assembly ────────────────────────────────────────────────────────
    def _parts(self) -> tuple[list[str], list[Any]]:
        base_sql, base_params = self._queryset.query.sql_with_params()
        table = AuditLog._meta.db_table
        sqls = [base_sql]
        params: list[Any] = list(base_params)
        for partition in self._partitions:
            sqls.append(base_sql.replace(f'"{table}"', f'"{partition}"'))
            params.extend(base_params)
        return sqls, params

    def _union(self) -> tuple[str, list[Any]]:
        sqls, params = self._parts()
        body = " UNION ALL ".join(
            f"SELECT * FROM ({sql}) AS part_{i}" for i, sql in enumerate(sqls)
        )
        return body, params

    def count(self) -> int:
        if self._count is None:
            if not self._partitions:
                self._count = self._queryset.count()
            else:
                body, params = self._union()
                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT count(*) FROM ({body}) AS combined", params)
                    self._count = int(cursor.fetchone()[0])
        return self._count

    def __len__(self) -> int:
        return self.count()

    #: The model's own columns, in one place — the SELECT list and the row
    #: hydration must agree, and two literal lists would be two things to drift.
    _COLUMNS = (
        "id",
        "tenant_id",
        "actor_user_id",
        # US-AUD-010 — the archive reader hydrates rows itself, so a column
        # missing here would make a named runbook read BLANK in the archive
        # while reading correctly in the hot store: the same row, two answers.
        "actor_kind",
        "actor_label",
        "actor_version",
        "action",
        "entity_type",
        "entity_id",
        "before",
        "after",
        "created_at",
    )

    def __getitem__(self, item: Any) -> Any:
        if not self._partitions:
            return self._queryset[item]
        if not isinstance(item, slice):  # pragma: no cover - paginator slices only
            return list(self)[item]
        offset = item.start or 0
        limit = (item.stop - offset) if item.stop is not None else None
        body, params = self._union()
        columns = ", ".join(self._COLUMNS)
        sql = f"SELECT {columns} FROM ({body}) AS combined ORDER BY created_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params = [*params, limit, offset]
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        # Hydrated by hand rather than through `objects.raw()`: `audit_log`'s
        # primary key is COMPOSITE (tenant_id, created_at, id) and Django's raw
        # queryset refuses a model whose pk attname is not in the SELECT list.
        # The rows are read-only payload for the serializers either way.
        return [AuditLog(**dict(zip(self._COLUMNS, row, strict=True))) for row in rows]

    def __iter__(self) -> Any:
        return iter(self[0:None])


def archive_partitions() -> list[str]:
    """The cold partitions of `audit_log` in THIS database, from the catalog.

    Empty on sqlite and on any host whose retention job has never run — in
    which case an archive query answers from the hot store over the 7-year
    floor, which is what it did before US-AUD-008 and is still honest: those
    are all the rows there are.
    """
    return archival.detached_partitions(AuditLog._meta.db_table)


def audit_result_set(
    tenant_id: Any,
    *,
    filters: dict[str, str] | None = None,
    archive: bool = False,
    sort: str | None = None,
    direction: str = AUDIT_LIST_DEFAULT_DIR,
    now: datetime | None = None,
) -> Any:
    """What the S61 list and the export cap both measure (BR-AUD-013).

    Hot (the default) is the plain queryset. Archive is the SAME query over the
    hot table plus every cold partition — the explicit opt-in of US-AUD-008,
    never implied, and the hot default never touches cold storage.
    """
    queryset = audit_queryset(
        tenant_id, filters=filters, archive=archive, sort=sort, direction=direction, now=now
    )
    if not archive:
        return queryset
    return ArchiveResultSet(queryset, archive_partitions())


def audit_entry(tenant_id: Any, entry_id: Any) -> AuditLog | None:
    """One row of THIS tenant, or None — a row belonging to another tenant is
    absent under this scope, so the API answers a plain 404 (HR-1/G4).

    `pk` is composite (tenant_id, created_at, id), so the lookup names the
    columns instead of the pk shortcut.
    """
    target = _valid_uuid(entry_id)
    if target is None:
        return None
    return AuditLog.objects.filter(tenant_id=tenant_id, id=target).first()


def entity_trail(tenant_id: Any, entity_type: str, entity_id: Any) -> QuerySet:
    """BR-AUD-010: the entity-scoped read service behind every per-entity Audit
    tab (account S21 · premises/unit · asset S50). A WINDOW into this store —
    the same rows S61 shows when filtered to the entity, never a copy. Rides
    `ix_audit_entity` (tenant_id, entity_type, entity_id, created_at).

    No time floor: an entity's own trail is already bounded by the entity, and
    BR-AUD-013's unbounded-query concern is the whole-tenant list. Callers
    paginate (checklist D).
    """
    target = _valid_uuid(entity_id)
    queryset = AuditLog.objects.filter(tenant_id=tenant_id, entity_type=entity_type)
    queryset = queryset.filter(entity_id=target) if target else queryset.none()
    return queryset.order_by("-created_at", "-id")


# ── payload builders (the S61 columns + drawer, US-AUD-004/005 §5) ──────────
def _truncate(value: Any) -> str:
    text = "—" if value is None else str(value)
    return text if len(text) <= _SUMMARY_VALUE_LIMIT else text[: _SUMMARY_VALUE_LIMIT - 1] + "…"


def summarize(before: Any, after: Any) -> str:
    """The S61 Summary column: one line of before → after (BR-AUD-009).

    Reads the BR-AUD-003 payload standard literally — changed fields on an
    update, a snapshot on a create, before-only on a terminal action — and
    renders whatever is stored, masked values included (BR-AUD-006: this never
    unmasks anything).
    """
    before = before if isinstance(before, dict) else None
    after = after if isinstance(after, dict) else None
    if before is None and after is None:
        return ""
    if before is None:  # create: snapshot
        parts = [f"{key}: {_truncate(value)}" for key, value in after.items()]
    elif after is None:  # terminal: before-only
        parts = [f"{key}: {_truncate(value)} → —" for key, value in before.items()]
    else:  # update: changed fields only
        keys = list(before) + [key for key in after if key not in before]
        parts = [
            f"{key}: {_truncate(before.get(key))} → {_truncate(after.get(key))}"
            for key in keys
            if before.get(key) != after.get(key)
        ]
    if not parts:
        return ""
    shown = "; ".join(parts[:_SUMMARY_FIELD_LIMIT])
    extra = len(parts) - _SUMMARY_FIELD_LIMIT
    return shown + (f" (+{extra} more)" if extra > 0 else "")


def actor_names(tenant_id: Any, actor_ids: list[Any]) -> dict[str, str]:
    """Actor id → display name for one page (cross-module READ, see module
    docstring). Users are per-tenant rows (BR-IDN-029), so the lookup is
    tenant-scoped like everything else here."""
    wanted = {str(actor_id) for actor_id in actor_ids if actor_id is not None}
    if not wanted:
        return {}
    user_model = django_apps.get_model("identity", "User")
    rows = user_model.objects.filter(tenant_id=tenant_id, id__in=wanted).values_list(
        "id", "full_name"
    )
    return {str(user_id): full_name for user_id, full_name in rows}


def _actor_payload(row: AuditLog, names: dict[str, str]) -> dict[str, Any] | None:
    """Who acted, in one of THREE shapes — and the third is US-AUD-010's.

    * a NAMED non-person actor (BR-AUD-019) → `{kind, name, version}`. **No id
      at all**, and that is two rules at once: B14 rule 31 says no database id
      is ever the visible value of a field, and BR-RBS-015 says a runbook never
      borrows a user identity, so there is no id to render even if we wanted to.
    * a PERSON → `{id, name}`, byte-identical to what it has always been. Pinned
      by US-AUD-004 TC-1 as the ratified S61 column contract, so US-AUD-010 adds
      a new VALUE and moves no existing one.
    * an UNNAMED system job → `null`, exactly as BR-AUD-003 has always meant it.
      The API says so with null rather than inventing a user.

    ⚠ THE NAMED BRANCH IS TESTED FIRST, AND THE ORDER IS LOAD-BEARING. A row
    cannot lawfully hold both (the writer refuses it and so does the table's
    CHECK), so the order can never change an answer today — but if a row ever
    did, reading it as a PERSON would print a staff name against an automation's
    act, which is the exact harm the story closes. Reading it as an automation
    is the safe wrong answer, so it goes first.
    """
    if row.actor_kind is not None:
        return {
            "kind": row.actor_kind,
            "name": row.actor_label,
            # Absent version stays null rather than "1" — a version nobody
            # established is a fact nobody established. The screen then draws
            # the bare name.
            "version": row.actor_version,
        }
    if row.actor_user_id is None:
        return None
    actor_id = str(row.actor_user_id)
    # A removed/foreign actor id keeps its history (BR-IDN-030 keeps user rows,
    # but the trail outlives any row): name stays null, the id still renders.
    return {"id": actor_id, "name": names.get(actor_id)}


def window_of(row: AuditLog, *, hot_floor: datetime | None = None) -> str:
    """ "hot" | "archive" — US-AUD-008 TC-2's result label, DERIVED not assumed.

    A row is archive if it sits outside the 2-year hot window (BR-AUD-013). The
    label is computed from the row's own timestamp rather than from which query
    fetched it, so it is right even when a hot query and an archive query
    return the same row on the boundary day.
    """
    floor = hot_floor if hot_floor is not None else window_floor(archive=False)
    return "archive" if row.created_at < floor else "hot"


def audit_row(
    row: AuditLog, names: dict[str, str] | None = None, *, hot_floor: datetime | None = None
) -> dict[str, Any]:
    """One S61 list row: When · Actor · Action · Entity · Summary · Source.

    `window` is added ONLY when a hot floor is supplied, i.e. only on an
    archive query (US-AUD-008 TC-2's "Archive" label). The default hot payload
    is left byte-identical on purpose: its key set is pinned by US-AUD-004 TC-1
    as the ratified S61 column contract, and a label nobody asked for has no
    business widening it."""
    payload: dict[str, Any] = {
        "id": str(row.id),
        "created_at": row.created_at.isoformat(),  # UTC; tenant-TZ render is IS-8
        "actor": _actor_payload(row, names or {}),
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": str(row.entity_id) if row.entity_id else None,
        "summary": summarize(row.before, row.after),
        "source": None,  # GAP AUD-D2 — no B2 column; honest-empty, not invented
    }
    if hot_floor is not None:
        payload["window"] = window_of(row, hot_floor=hot_floor)
    return payload


def audit_detail(row: AuditLog, names: dict[str, str] | None = None) -> dict[str, Any]:
    """The US-AUD-005 drawer payload: the list row plus the full before/after
    JSON diff, exactly as stored (BR-AUD-006 — no unmask path exists)."""
    return {
        **audit_row(row, names),
        "before": row.before,
        "after": row.after,
        "request_metadata": None,  # GAP AUD-D2 — renders when anchored
    }


# ── CR-067 B2 / DEF-3321 — the diagnostic, read back onto a screen ──────────
def reference_of(row: AuditLog) -> str | None:
    """The support reference this permanent audit row carries, or None.

    CR-067 task A4 puts `reference` in the FAILURE row's stored payload —
    `apps/tenancy/sample_data._audit_failed_block` writes it, formed server-side
    by `core.diagnostics.support_ref()`. It lives in `after` because that is
    where every other fact about a failed block lives; there is no column for it
    and there deliberately is no foreign key (the two records have different
    lifetimes — `apps/audit/diagnostic_models` says why).

    **None is the ordinary answer for most rows and is not a fault.** A success
    row has no reference, and neither does a failure written before this change
    request landed — which is the state the Product Owner meets first, because
    every row already in their log predates it.
    """
    after = row.after
    if not isinstance(after, dict):
        return None
    value = after.get("reference")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def audit_diagnostic(row: AuditLog) -> dict[str, Any]:
    """The System-Admin read behind `GET /audit-log/{id}/diagnostic`.

    ⚠ **THE ADDRESS IS THE ROW; THE JOIN IS THE REFERENCE — AND THAT IS WHAT
    MAKES 404 MEAN ONE THING (DEF-3321).** The defect row asks for *"a read of
    one diagnostic by the reference the audit row already carries, answering 'no
    longer held' for a swept record rather than 404 with no explanation"*, and
    also that another tenant's record be **absent** rather than forbidden. Both
    sentences are true only if the two absences are different HTTP answers, and
    they can only be different if the thing being addressed is the audit row:

      * **the ROW is missing or belongs to another tenant → 404**, the same
        body `GET /audit-log/{id}` already gives for both, so existence never
        leaks (HR-1/G4);
      * **the row is here and the detail behind its reference is not → 200**
        carrying `held: false` and a reason, because an expired diagnostic is a
        NORMAL state and a 404 would read as a fault.

    Addressing the record by its reference instead would collapse those two into
    one answer and lose whichever sentence it chose. Written down rather than
    quietly resolved — the shape moved by one hop from the defect row's wording
    and the reason is the row's own second requirement.

    Tenant scope is `by_reference`'s (CLAUDE.md rule 1): the id comes from
    context, and `error_diagnostics` is under FORCE RLS besides.
    """
    return {
        # The row it belongs to, so a client cannot render one row's diagnostic
        # under another's heading after a slow response arrives out of order.
        "audit_action": row.action,
        **audit_diagnostics.read_for_reference(reference_of(row)),
    }


def audit_page(
    tenant_id: Any,
    rows: list[AuditLog],
    *,
    archive: bool = False,
    with_values: bool = False,
) -> list[dict[str, Any]]:
    """Serialize one page with a single actor-name lookup for the whole page.

    On an archive page every row carries `window` (US-AUD-008 TC-2); on the hot
    default the payload is unchanged — see `audit_row`.

    ⚠ **`with_values` IS THE SECOND CONDITIONAL KEY ON THIS PAYLOAD AND IT IS
    ADDED THE SAME WAY `window` WAS (`CR-089` wave C task `C6`, `PUJ-17`).**
    The per-entity Audit tab on a premises, a unit, an asset, a route and a
    cycle drew `When · Actor · Action`, with the changed values behind an
    `Expand` — **one press per row**, and the thing a person is on that tab to
    read is precisely *what was it before*. The values are already in memory:
    `summarize()` on the line above reads `row.before` and `row.after` off the
    very rows this function was handed. Serving the structured pair therefore
    costs **no query and no round trip**, where a per-row `GET /audit-log/{id}`
    from the browser would cost twenty-five of them.

    ⚠ **IT IS OFF FOR `GET /audit-log` UNFILTERED, AND THAT IS THE POINT.**
    `audit_row`'s key set is pinned by `US-AUD-004` TC-1 as the ratified S61
    column contract, and S61 pages a whole tenant's log — 809 rows on the
    reporting tenant — where two JSON documents per row is a payload nobody
    reads. An ENTITY-SCOPED query is bounded by the entity and is the only
    caller that turns this on.

    ⚠ **NO NEW EXPOSURE, AND THE ROLE IS THE SAME ROLE.** These are the exact
    bytes `GET /audit-log/{id}` already serves, to the same `AdminOrExecutive`
    permission, from the same columns — `audit_detail` is three lines below.
    `BR-AUD-006` holds unchanged: values are served **as stored**, masked ones
    included, and there is no unmask path here or anywhere else.
    """
    names = actor_names(tenant_id, [row.actor_user_id for row in rows])
    floor = window_floor(archive=False) if archive else None  # once per page, not per row
    page = [audit_row(row, names, hot_floor=floor) for row in rows]
    if with_values:
        for row, payload in zip(rows, page, strict=True):
            payload["before"] = row.before
            payload["after"] = row.after
    return page


# ── US-MET-020 / US-AUD-007: HAS RETENTION EVER RUN? ────────────────────────
#
# `archive_job_runs` has existed since migration 0004 and has been written by
# `core.archival` through a registered recorder since the day the job shipped.
# It appeared in a migration, in a management command and in `core/archival.py`
# **and in no `api.py` anywhere** — no selector, no endpoint, no viewer — so
# nobody could answer the one question an operator subject to a 7-year retention
# obligation actually has: *has this ever run, and what did it move?* That is
# hard-won law 2 on the compliance surface, and it is what these two functions
# close.
#
# ⚠ **THIS TABLE IS NOT TENANT-SCOPED, AND THE REDACTION BELOW IS WHY THAT IS
# SAFE TO SERVE.** A partition is physically shared across every tenant, so a
# run that detaches `audit_log_2026_08` belongs to no tenant and the table
# carries no `tenant_id` column and no RLS policy (see the model docstring).
# Two consequences, both handled here rather than left to a caller:
#
#   1. every archived entry's payload carries a `tenants` LIST of the tenant ids
#      whose rows were in the partition. **That list never leaves this module.**
#      `_archive_entry` drops it and answers a single boolean — was the CALLING
#      tenant among them — so an operator learns that their own data was moved
#      and learns nothing whatever about who else is on the platform. Serving
#      the raw payload would have been a cross-tenant leak on a table RLS cannot
#      catch, precisely because it has no policy to enforce.
#   2. the ROWS are platform-wide, so every tenant sees the same run history.
#      That is correct — the runs ARE platform events, and hiding a month's
#      retention from a tenant whose rows were in it would make the compliance
#      answer wrong — and it is stated rather than assumed.
#
# **AND IT CREATES NO MANUAL PATH.** BR-MET-055 and BR-AUD-012 both say "never
# manual", and `core.archival.run_archival` refuses any caller without the
# scheduler token. These are READS. There is no verb here, no verb in the API
# and no job kind: an operator can see what the scheduler did and cannot make it
# do anything.

#: What the run record says about shipping. `core.archival` registers no
#: cold-store shipper in this repo, so every entry records `shipped: false` with
#: `shipper_absent` — "archived" here means DETACHED, MANIFESTED and STILL
#: QUERYABLE under RLS, and it does not yet mean off-site. The screen prints
#: that distinction; a field claiming a transfer is not the transfer (law 1).
SHIPPER_ABSENT = "shipper_absent"


def _archive_entry(entry: Any, tenant_id: Any) -> dict[str, Any]:
    """One detached (or dropped) partition, with the tenant list REDACTED."""
    if not isinstance(entry, dict):  # a payload shape from a future writer
        return {"partition": None, "row_count": None, "includes_this_tenant": None}
    tenants = entry.get("tenants")
    return {
        "partition": entry.get("partition"),
        "row_count": entry.get("row_count"),
        "sha256": entry.get("sha256"),
        # The ONE thing about the tenant list that may cross this boundary.
        # None when the writer recorded no list at all, which is not the same
        # as "your rows were not in it" and must not render as a No.
        "includes_this_tenant": (
            None
            if not isinstance(tenants, list)
            else str(tenant_id) in {str(value) for value in tenants}
        ),
        "destination": entry.get("destination"),
        "shipped": bool(entry.get("shipped")),
        "shipped_reason": entry.get("shipped_reason"),
    }


def archive_run_row(row: Any, tenant_id: Any) -> dict[str, Any]:
    """One `archive_job_runs` row, as an operator needs to read it."""
    archived = row.archived if isinstance(row.archived, list) else []
    purged = row.purged if isinstance(row.purged, list) else []
    return {
        "id": str(row.id),
        "table_name": row.table_name,
        "run_date": row.run_date.isoformat() if row.run_date else None,
        "recorded_at": row.created_at.isoformat() if row.created_at else None,
        "status": row.status,
        "note": row.note,
        # The bound the run enforced, AS RECORDED ON THE RUN — not read from
        # today's config. A run in 2031 must still say what the law was in 2031
        # if the bound ever changes, which is why the columns exist at all.
        "hot_window_months": row.hot_window_months,
        "retention_months": row.retention_months,
        "archived": [_archive_entry(entry, tenant_id) for entry in archived],
        "purged": [_archive_entry(entry, tenant_id) for entry in purged],
        # Counts beside the lists so a summary row needs no client arithmetic.
        "archived_count": len(archived),
        "purged_count": len(purged),
    }


#: The tables the retention job covers, in the order the two stories name them.
#: Read from `core.archival` rather than restated: a second literal list is a
#: second thing to drift, and this one decides what "never run" means.
def archive_run_list(tenant_id: Any, *, table: str | None = None) -> list[dict[str, Any]]:
    """Every recorded run, newest first. Optionally one table's.

    NOT paginated and deliberately so: this table gains at most one row per
    table per MONTH (twelve a year for two tables), so the whole history of a
    seven-year obligation is under 200 rows. BR-AUD-013's no-unbounded-query
    rule is about `audit_log`, which grows by the million; applying pagination
    here would add a page control to a list that fits on a screen.
    """
    queryset = ArchiveJobRun.objects.all()
    if table:
        queryset = queryset.filter(table_name=table)
    return [
        archive_run_row(row, tenant_id)
        for row in queryset.order_by("-run_date", "-created_at", "-id")
    ]


def archive_status(tenant_id: Any) -> dict[str, Any]:
    """**Has retention ever run?** — the question, answered per table.

    `last_run_date is None` is the answer that matters and it is served as a
    NULL with a reason, never as a zero or an empty string: "the retention job
    has never run on this deployment" is a compliance finding an operator must
    be able to see, and a blank cell is not one.

    `partitions_archived` counts PARTITIONS moved, not rows — the row counts are
    on each entry, and summing them here would produce a headline figure whose
    denominator ("of how many?") this module cannot know.
    """
    rows = list(ArchiveJobRun.objects.all().order_by("-run_date", "-created_at", "-id"))
    tables: list[dict[str, Any]] = []
    for table in archival.ARCHIVED_TABLES:
        for_table = [row for row in rows if row.table_name == table]
        archived = sum(len(row.archived or []) for row in for_table)
        purged = sum(len(row.purged or []) for row in for_table)
        latest = for_table[0] if for_table else None
        tables.append(
            {
                "table_name": table,
                "has_ever_run": latest is not None,
                "last_run_date": latest.run_date.isoformat() if latest else None,
                "last_run_status": latest.status if latest else None,
                "last_run_note": latest.note if latest else None,
                "runs": len(for_table),
                "partitions_archived": archived,
                "partitions_purged": purged,
                # Absent on a table that HAS run — the reason exists to explain
                # a null, and a reason beside a date would read as a warning.
                "never_run_reason": (
                    None
                    if latest is not None
                    else "no run of the retention job has ever been recorded for this table"
                ),
            }
        )
    return {
        # The law, from the one module that states it (core.archival reads the
        # signed partition registry for the hot window rather than restating 24).
        "hot_window_months": archival.HOT_WINDOW_MONTHS,
        "retention_years": archival.RETENTION_YEARS,
        "tables": tables,
        # ⚠ Hard-won law 1, served as DATA rather than written in a comment:
        # nothing in this repo registers a cold-store shipper, so "archived"
        # means detached + manifested + still queryable under RLS, and it does
        # NOT mean off-site. A screen that omitted this would let an operator
        # tell an auditor the data had left the building.
        "off_site_shipping": False,
        "off_site_reason": SHIPPER_ABSENT,
        # There is no manual trigger, by law (BR-MET-055 / BR-AUD-012). Said on
        # the payload so the screen can explain the absence of a button rather
        # than leaving a reader hunting for one.
        "manual_trigger": False,
        "schedule": "monthly, 1st, 02:00 UTC",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-004@009e809 (EP-AUD-02 lead story; also US-AUD-005@009e809 · US-AUD-006@009e809 — hash = sha256/7 of the source epic)
# packet: US-AUD-008@6b3d915 (EP-AUD-03 archive-search story — ArchiveResultSet + the window label, added 2026-08-15)
# generated: 2026-08-09 by story-coder v1 (API-gap lane — the ratified 11b §2.13 audit read API, never built)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S61 is a later lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F — the bar the baseline passes) black✔ py_compile✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: [US-AUD-008 lane 2026-08-15] the archive reader re-points the ORM's OWN compiled SQL at each cold partition by table name rather than restating the filter clause — one filter implementation, several tables; safe only because this query has no join, and the partition names come from the catalog, never from a caller · the `window` label is added to a row payload ONLY on an archive query: US-AUD-004 TC-1 pins the hot payload's key set as the ratified S61 column contract, so the hot default is left byte-identical · on sqlite (and on any host whose retention job has never run) there are no detached partitions, so an archive query answers from the hot store over the 7-year floor — which is all the rows there are, stated rather than faked · BR-AUD-009's MODULE filter and BR-AUD-004's action-type CLASS filter are NOT served — both are properties of the US-AUD-002 event-code catalog, which does not exist; classifying codes here would invent that catalog (REPORTED, not guessed) · Source column + request metadata = GAP AUD-D2, served null (US-AUD-004 §5 "column present, honest-empty until anchor") · archive=true widens the floor to the BR-AUD-012 7-year horizon within the SAME store — cold-storage search is US-AUD-008 (W5, not built), so only rows still in the hot store return; stated, never faked · actor display name is a cross-module READ via django_apps.get_model (identity exposes no bulk selector) — same recorded disposition as identity/selectors.py; a users_by_ids() seam is flagged · the 11b S21 row spells the account filter `f.account_id`; the BR-AUD-009 vocabulary is entity_type+entity_id and that is what is served (the `f.entity=type:id` shorthand of the S50 row is also accepted) — REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
